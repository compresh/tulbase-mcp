"""MCP server implementation for tulbase.

Exposes four tools via stdio transport:
    - compress
    - fetch_compressed
    - list_compressed
    - stats

The server creates a per-session DuckDB compression log and cold storage
directory (default ``~/.tulbase/storage/<session_id>/``). Sessions persist
across server restarts — the client passes ``session_id`` in each request.

Privacy:
    All state is local. No outbound network calls. Conversation content
    never leaves the user's machine. This is the open-source distribution;
    for hosted Q-protective ranking, see https://compre.sh.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import mcp.types as mcp_types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

# tulbase is a separately-published package (MIT, github.com/compresh/tulbase).
# For local development, install editable from the Compresh monorepo:
#   pip install -e <compresh-repo>/migration-staging/proxy
# In production, ``pip install tulbase`` once PyPI publish is done.
from tulbase import (  # type: ignore[import-not-found]
    ColdStorage,
    CompressionLog,
    Pipeline,
    Retriever,
    Tier1Summarizer,
    compose_compresh_history,
)

logger = logging.getLogger("tulbase-mcp")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_STORAGE_DIR = Path(
    os.environ.get("TULBASE_STORAGE_DIR", "~/.tulbase/storage")
).expanduser()

DEFAULT_PROTECTION_MODE = os.environ.get("TULBASE_PROTECTION_MODE", "balanced")

USE_TIKTOKEN = os.environ.get("TULBASE_USE_TIKTOKEN", "false").lower() == "true"
USE_TRANSFORMERS = (
    os.environ.get("TULBASE_USE_TRANSFORMERS", "false").lower() == "true"
)

# Protection Zone N mapping (Patent TR-TPMK 2026/007305 Claim 1(e))
_PROTECTION_ZONE_N = {"off": 0, "aggressive": 2, "balanced": 4, "conservative": 8}


# ---------------------------------------------------------------------------
# Per-session state cache
# ---------------------------------------------------------------------------


class SessionState:
    """Per-session DuckDB + cold storage + pipeline."""

    __slots__ = ("cold", "log", "pipeline", "retriever", "session_id", "workdir")

    def __init__(self, session_id: str, root: Path):
        self.session_id = session_id
        self.workdir = root / session_id
        self.workdir.mkdir(parents=True, exist_ok=True)

        self.log = CompressionLog(str(self.workdir / "log.duckdb"))
        self.log.ensure_schema()
        self.cold = ColdStorage(str(self.workdir / "cold"))

        # Open-source default: protect_mode="off". Compresh paid tier
        # overrides to "balanced" + auto-init QMatrixClassifier (not
        # available in this distribution).
        self.pipeline = Pipeline(
            log=self.log,
            cold=self.cold,
            enable_q_matrix=False,
            summarizer=Tier1Summarizer(protect_mode="off"),
        )
        self.retriever = Retriever(log=self.log, cold=self.cold)


_sessions: dict[str, SessionState] = {}


def _get_session(session_id: str) -> SessionState:
    if session_id not in _sessions:
        _sessions[session_id] = SessionState(session_id, DEFAULT_STORAGE_DIR)
        logger.info("created session %s", session_id)
    return _sessions[session_id]


# ---------------------------------------------------------------------------
# Optional independent token counter
# ---------------------------------------------------------------------------


def _count_tokens(text: str, hint_model: str | None = None) -> int:
    """Best-effort token count. Falls back to char/4 heuristic."""
    if USE_TIKTOKEN:
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception as e:
            logger.warning("tiktoken failed, falling back: %s", e)
    if USE_TRANSFORMERS and hint_model:
        try:
            from transformers import AutoTokenizer

            tok = AutoTokenizer.from_pretrained(hint_model)
            return len(tok.encode(text))
        except Exception as e:
            logger.warning("transformers failed, falling back: %s", e)
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Tool: compress
# ---------------------------------------------------------------------------


async def tool_compress(
    session_id: str,
    messages: list[dict[str, Any]],
    protection_mode: str = DEFAULT_PROTECTION_MODE,
) -> dict[str, Any]:
    """Compress a conversation message list.

    See module docstring + README for full semantics.
    """
    if protection_mode not in _PROTECTION_ZONE_N:
        return {
            "ok": False,
            "error": f"protection_mode must be one of {list(_PROTECTION_ZONE_N)}",
        }

    state = _get_session(session_id)
    n_zone = _PROTECTION_ZONE_N[protection_mode]

    # Short-conversation pass-through: entire history is inside Protection Zone.
    if len(messages) <= n_zone + 1:
        return {
            "ok": True,
            "applied": False,
            "reason": "conversation_within_protection_zone",
            "optimized_messages": messages,
            "compresh_md": "",
            "raw_tail": messages,
            "n_compressed_turns": 0,
            "n_compressed_entries": 0,
            "n_total": len(messages),
            "saving_chars": 0,
            "session_id": session_id,
            "protection_mode": protection_mode,
            "protection_zone_n": n_zone,
            "tools_hint": ["fetch_compressed", "list_compressed"],
        }

    # Run pipeline turn-by-turn.
    turn_boxes = []
    for i, m in enumerate(messages):
        content = m.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content)
        try:
            pr = state.pipeline.run(
                content,
                session_id=session_id,
                turn_idx=i,
                speaker=_normalize_speaker(m.get("role", "user")),
            )
            turn_boxes.append(pr.turn_box)
        except Exception as e:
            logger.warning("pipeline.run failed at turn %d: %s", i, e)
            # Fail-safe: pass-through this turn rather than aborting.
            return {
                "ok": False,
                "error": f"pipeline error at turn {i}: {type(e).__name__}",
                "optimized_messages": messages,
                "n_total": len(messages),
                "session_id": session_id,
            }

    # Compose with Protection Zone.
    composed = compose_compresh_history(
        messages,
        turn_boxes,
        upto_idx=len(messages) - 1,
        mode=protection_mode,
    )

    raw_chars = sum(
        len(m.get("content") or "")
        for m in messages[:-1]
        if isinstance(m.get("content"), str)
    )
    optimized_chars = (
        len(composed.compresh_md or "")
        + sum(
            len(m.get("content") or "")
            for m in composed.raw_tail
            if isinstance(m.get("content"), str)
        )
    )
    saving_chars = max(0, raw_chars - optimized_chars)

    n_compressed_entries = sum(
        len(b.compressed_refs) for b in turn_boxes[: composed.n_compressed]
    )

    optimized_messages: list[dict[str, Any]] = []
    if composed.compresh_md:
        optimized_messages.append(
            {
                "role": "system",
                "content": (
                    "Below is a compressed memory of older turns "
                    "(the most recent turns follow as raw messages):\n\n"
                    + composed.compresh_md
                ),
            }
        )
    optimized_messages.extend(composed.raw_tail)

    return {
        "ok": True,
        "applied": True,
        "tulbase": True,
        "optimized_messages": optimized_messages,
        "compresh_md": composed.compresh_md or "",
        "raw_tail": list(composed.raw_tail),
        "n_compressed_turns": composed.n_compressed,
        "n_compressed_entries": n_compressed_entries,
        "n_total": len(messages),
        "saving_chars": saving_chars,
        "session_id": session_id,
        "protection_mode": protection_mode,
        "protection_zone_n": n_zone,
        "tools_hint": ["fetch_compressed", "list_compressed"],
    }


def _normalize_speaker(role: str) -> str:
    """Map MCP/OpenAI roles to tulbase speaker enum."""
    role = (role or "user").lower()
    if role in ("assistant", "model", "ai"):
        return "assistant"
    if role in ("system", "tool", "function"):
        return role
    return "user"


# ---------------------------------------------------------------------------
# Tool: fetch_compressed
# ---------------------------------------------------------------------------


async def tool_fetch_compressed(
    session_id: str,
    entry_id: str,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    """Retrieve original content of a compressed entry."""
    state = _get_session(session_id)
    result = state.retriever.fetch(entry_id, max_tokens=max_tokens)
    return result.to_tool_response()


# ---------------------------------------------------------------------------
# Tool: list_compressed
# ---------------------------------------------------------------------------


async def tool_list_compressed(
    session_id: str,
    turn_min: int | None = None,
    turn_max: int | None = None,
    modality: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """List compressed entries in a session, optionally filtered."""
    state = _get_session(session_id)

    where: list[str] = []
    params: list[Any] = []
    if turn_min is not None:
        where.append("turn_idx >= ?")
        params.append(turn_min)
    if turn_max is not None:
        where.append("turn_idx <= ?")
        params.append(turn_max)
    if modality:
        where.append("modality = ?")
        params.append(modality)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(limit, 1000))

    sql = (
        f"SELECT id, turn_idx, modality, summary_short, n_chars "
        f"FROM compression_log {where_sql} "
        f"ORDER BY turn_idx ASC LIMIT {limit}"
    )

    rows = state.log.conn.execute(sql, params).fetchall()  # type: ignore[attr-defined]
    entries = [
        {
            "id": r[0],
            "turn_idx": r[1],
            "modality": r[2],
            "summary_short": r[3],
            "chars": r[4],
        }
        for r in rows
    ]

    total = state.log.conn.execute(  # type: ignore[attr-defined]
        f"SELECT COUNT(*) FROM compression_log {where_sql}",
        params,
    ).fetchone()[0]

    return {"ok": True, "entries": entries, "total": total, "session_id": session_id}


# ---------------------------------------------------------------------------
# Tool: stats
# ---------------------------------------------------------------------------


async def tool_stats(session_id: str) -> dict[str, Any]:
    """Session-level compression statistics."""
    state = _get_session(session_id)

    row = state.log.conn.execute(  # type: ignore[attr-defined]
        """
        SELECT
            COUNT(DISTINCT turn_idx)            AS n_turns,
            COUNT(*)                            AS n_entries,
            COALESCE(SUM(n_chars), 0)           AS total_chars_raw
        FROM compression_log
        """
    ).fetchone()

    tokenizer = (
        "tiktoken"
        if USE_TIKTOKEN
        else "transformers"
        if USE_TRANSFORMERS
        else "internal"
    )

    return {
        "ok": True,
        "session_id": session_id,
        "n_turns": int(row[0] or 0),
        "n_compressed_entries": int(row[1] or 0),
        "total_chars_raw": int(row[2] or 0),
        "storage_path": str(state.workdir),
        "tokenizer_used": tokenizer,
    }


# ---------------------------------------------------------------------------
# Tool schemas (JSON Schema for MCP `inputSchema`)
# ---------------------------------------------------------------------------

_TOOLS: list[mcp_types.Tool] = [
    mcp_types.Tool(
        name="compress",
        description=(
            "Compress a conversation message list using tulbase. Elides code blocks, "
            "terminal output, JSON dumps, and stack traces to cold storage with "
            "retrievable IDs. Summarizes dialog text via LexRank. Preserves the last "
            "N messages verbatim (Protection Zone)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Unique conversation thread identifier.",
                },
                "messages": {
                    "type": "array",
                    "description": "OpenAI-style message list (role + content).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["role", "content"],
                    },
                },
                "protection_mode": {
                    "type": "string",
                    "enum": ["off", "aggressive", "balanced", "conservative"],
                    "default": "balanced",
                    "description": (
                        "Trailing-message Protection Zone size: "
                        "off=0, aggressive=2, balanced=4, conservative=8."
                    ),
                },
            },
            "required": ["session_id", "messages"],
        },
    ),
    mcp_types.Tool(
        name="fetch_compressed",
        description=(
            "Retrieve the original content of a compressed entry by ID. "
            "Use when answering specifics about a compressed item (code, terminal "
            "output, JSON dump, quote details). If the entry is not retrievable, "
            "say so — do not fabricate."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "entry_id": {
                    "type": "string",
                    "description": "Compression entry ID (format: compr-*).",
                },
                "max_tokens": {
                    "type": "integer",
                    "default": 2000,
                    "minimum": 1,
                    "maximum": 32000,
                },
            },
            "required": ["session_id", "entry_id"],
        },
    ),
    mcp_types.Tool(
        name="list_compressed",
        description=(
            "List compressed entries in the current session. Filter by turn range "
            "and/or modality. Use for broad recall before answering questions like "
            '"what did we cover in turns 10-20?".'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "turn_min": {"type": "integer"},
                "turn_max": {"type": "integer"},
                "modality": {
                    "type": "string",
                    "enum": ["code", "terminal_output", "json_dump", "stack_trace"],
                },
                "limit": {
                    "type": "integer",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
            "required": ["session_id"],
        },
    ),
    mcp_types.Tool(
        name="stats",
        description="Session-level compression statistics.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
            },
            "required": ["session_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# MCP server wiring
# ---------------------------------------------------------------------------


app: Server = Server("tulbase-mcp")


@app.list_tools()
async def _list_tools() -> list[mcp_types.Tool]:
    return _TOOLS


@app.call_tool()
async def _call_tool(
    name: str, arguments: dict[str, Any]
) -> list[mcp_types.TextContent]:
    try:
        if name == "compress":
            result = await tool_compress(
                session_id=arguments["session_id"],
                messages=arguments["messages"],
                protection_mode=arguments.get("protection_mode", DEFAULT_PROTECTION_MODE),
            )
        elif name == "fetch_compressed":
            result = await tool_fetch_compressed(
                session_id=arguments["session_id"],
                entry_id=arguments["entry_id"],
                max_tokens=arguments.get("max_tokens", 2000),
            )
        elif name == "list_compressed":
            result = await tool_list_compressed(
                session_id=arguments["session_id"],
                turn_min=arguments.get("turn_min"),
                turn_max=arguments.get("turn_max"),
                modality=arguments.get("modality"),
                limit=arguments.get("limit", 100),
            )
        elif name == "stats":
            result = await tool_stats(session_id=arguments["session_id"])
        else:
            result = {"ok": False, "error": f"unknown tool: {name}"}
    except KeyError as e:
        result = {"ok": False, "error": f"missing required argument: {e}"}
    except Exception as e:
        logger.exception("tool %s failed", name)
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return [mcp_types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


async def serve() -> None:
    DEFAULT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("tulbase-mcp starting (storage=%s)", DEFAULT_STORAGE_DIR)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="tulbase-mcp",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    """Console entry point for ``tulbase-mcp`` command."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(serve())


if __name__ == "__main__":
    main()
