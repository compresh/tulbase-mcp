"""MCP server implementation for tulbase.

Exposes four tools via stdio transport:
    - compress
    - fetch_compressed
    - list_compressed
    - stats

The server creates a per-session DuckDB compression log and cold storage
directory (default `~/.tulbase/storage/<session_id>/`). Sessions persist
across server restarts — the client passes `session_id` in each request.

Privacy:
    All state is local. No outbound network calls. Conversation content
    never leaves the user's machine. This is the open-source distribution;
    for hosted Q-protective ranking, see https://compre.sh.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

# MCP SDK imports (filled in during implementation)
# from mcp.server import Server
# from mcp.server.stdio import stdio_server
# from mcp.types import Tool, TextContent

# tulbase imports (from pip-installed package)
# from tulbase import (
#     ColdStorage,
#     CompressionLog,
#     Pipeline,
#     Retriever,
#     compose_compresh_history,
# )

logger = logging.getLogger("tulbase-mcp")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_STORAGE_DIR = Path(
    os.environ.get("TULBASE_STORAGE_DIR", "~/.tulbase/storage")
).expanduser()

DEFAULT_PROTECTION_MODE = os.environ.get("TULBASE_PROTECTION_MODE", "balanced")

# Token counter — optional independent verification
USE_TIKTOKEN = os.environ.get("TULBASE_USE_TIKTOKEN", "false").lower() == "true"
USE_TRANSFORMERS = (
    os.environ.get("TULBASE_USE_TRANSFORMERS", "false").lower() == "true"
)


# ---------------------------------------------------------------------------
# Tool: compress
# ---------------------------------------------------------------------------


async def tool_compress(
    session_id: str,
    messages: list[dict[str, Any]],
    protection_mode: str = DEFAULT_PROTECTION_MODE,
) -> dict[str, Any]:
    """Compress a conversation message list.

    Args:
        session_id: Unique identifier for this conversation thread.
            Used to partition cold storage and compression log.
        messages: OpenAI-style message list (role + content). Tool calls
            and assistant messages with multi-modal content are supported.
        protection_mode: "off" | "conservative" | "balanced" | "aggressive".
            Determines how many trailing messages stay verbatim:
            off=0, conservative=8, balanced=4, aggressive=2.

    Returns:
        dict with:
            optimized_messages: list of dict — system + compresh_md + raw_tail
            compresh_md: str — the compressed history markdown block
            raw_tail: list of dict — Protection Zone messages (verbatim)
            n_compressed_turns: int
            n_compressed_entries: int — code/terminal/JSON elided to cold storage
            saving_chars: int
            session_id: str
            tools_hint: list of MCP tool names the client should expose
                to the upstream model so it can call fetch_compressed
                ("fetch_compressed", "list_compressed")
    """
    # TODO: implement once mcp + tulbase imports wired
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Tool: fetch_compressed
# ---------------------------------------------------------------------------


async def tool_fetch_compressed(
    session_id: str,
    entry_id: str,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    """Retrieve original content of a compressed entry.

    Args:
        session_id: Conversation thread identifier.
        entry_id: Compression entry ID (format: compr-*).
        max_tokens: Max tokens to return. Defaults to 2000.

    Returns:
        dict with:
            ok: bool
            id: str
            content: str (if ok)
            modality: str (e.g. "code_block", "terminal_output")
            truncated: bool
            error: str (if not ok)
    """
    raise NotImplementedError


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
    """List compressed entries in a session, optionally filtered.

    Args:
        session_id: Conversation thread identifier.
        turn_min: Lower bound turn index (inclusive).
        turn_max: Upper bound turn index (inclusive).
        modality: Filter by modality (code | terminal_output | json_dump | stack_trace).
        limit: Max entries to return (default 100, max 1000).

    Returns:
        dict with:
            entries: list of {id, turn_idx, modality, summary_short, chars}
            total: int — total entries before limit
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Tool: stats
# ---------------------------------------------------------------------------


async def tool_stats(session_id: str) -> dict[str, Any]:
    """Session-level compression statistics.

    Returns:
        dict with:
            session_id: str
            n_turns: int
            n_compressed_entries: int
            total_chars_raw: int
            total_chars_optimized: int
            saving_ratio: float — 0.0 to 1.0
            storage_path: str
            tokenizer_used: str — "internal" | "tiktoken" | "transformers"
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------


async def serve() -> None:
    """Run the MCP stdio server."""
    DEFAULT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("tulbase-mcp starting (storage=%s)", DEFAULT_STORAGE_DIR)

    # TODO:
    # 1. Create Server() from mcp.server
    # 2. Register four tools (compress, fetch_compressed, list_compressed, stats)
    # 3. Wire async stdio_server() transport
    # 4. Wait for client connection
    raise NotImplementedError


def main() -> None:
    """Console entry point for `tulbase-mcp` command."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(serve())


if __name__ == "__main__":
    main()
