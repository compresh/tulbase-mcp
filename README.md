# tulbase-mcp

**Local MCP server for tulbase** — open-source context compression for LLM agent conversations.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

`tulbase-mcp` is a Model Context Protocol (MCP) server that exposes the
[`tulbase`](https://github.com/compresh/tulbase) compression engine to any
MCP-aware client (Claude Code, Cursor, Cline, Continue, Aider, Cowork, etc.).

## What it does

`tulbase` compresses long agent conversations by:
- Identifying **modality segments** (code blocks, terminal output, JSON dumps,
  stack traces) and **eliding them** to cold storage with content-addressed
  retrieval
- Producing compact **TurnBox** summaries of dialog text (LexRank-based,
  deterministic — typical 30–50 tokens per turn vs ~400–800 raw)
- Preserving the last **N messages verbatim** (Protection Zone)
- Exposing a `fetch_compressed(id=...)` tool so the model can recover any
  elided content on demand

This is the **open-source core**. The proprietary Q-protective ranking and
epistemic classification layers are part of [Compresh](https://compre.sh)
(paid tier, separate distribution).

## Why MCP

MCP (Model Context Protocol) is Anthropic's open protocol for connecting
LLM clients to external tools. Running tulbase as an MCP server means:

- **Zero provider lock-in** — your LLM API keys, OAuth tokens, or
  subscription packages (Claude Pro, ChatGPT Plus, Cursor Pro) never touch
  this process. tulbase only handles memory.
- **Local by default** — stdio transport runs in your own machine. Your
  conversation history stays on your disk.
- **Drop-in for any MCP client** — add tulbase to your MCP config, your
  agent client picks up `compress`, `fetch_compressed`, `list_compressed`
  tools automatically.

## Installation

```bash
pip install tulbase-mcp
```

Or from source:

```bash
git clone https://github.com/compresh/tulbase-mcp
cd tulbase-mcp
pip install -e .
```

## MCP client configuration

### Claude Code (`~/.claude/mcp.json`)

```json
{
  "mcpServers": {
    "tulbase": {
      "command": "python",
      "args": ["-m", "tulbase_mcp.server"],
      "env": {
        "TULBASE_STORAGE_DIR": "~/.tulbase/storage"
      }
    }
  }
}
```

### Cursor (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "tulbase": {
      "command": "python",
      "args": ["-m", "tulbase_mcp.server"]
    }
  }
}
```

### Cline / Continue / Cowork

Use the corresponding MCP config format. All MCP-compatible clients are
supported (stdio transport).

## Tools exposed

| Tool | Description |
|---|---|
| `compress` | Take a list of conversation messages, return optimized message list (TurnBox summaries + Protection Zone tail) |
| `fetch_compressed` | Retrieve original content of a compressed entry by ID |
| `list_compressed` | List compressed entries in the current session, filterable by turn range and modality |
| `stats` | Current session statistics — total turns, compressed entries, char savings |

## Token counter (optional)

For independent token measurement, you can install the optional verification
package:

```bash
pip install tulbase-mcp[verify]
```

This adds:
- **tiktoken** (OpenAI, MIT) — GPT/o-series families
- **transformers** (HuggingFace, Apache 2.0) — Llama/Claude/other families

The MCP server then reports token counts using these independent
tokenizers, so your savings are verifiable against industry-standard
counters — no need to trust tulbase's internal estimation.

## Upgrade path: Compresh paid tier

`tulbase` is the open-source core. For Q-protective ranking,
epistemic deviation detection, and depth-aware compression that
adapts to conversation context, see **[Compresh](https://compre.sh)**.

Compresh adds:
- **Q-protective sentence ranking** — fact-bearing sentences get
  priority preservation when compression capacity is constrained
- **Epistemic marker classification** — verified vs hearsay vs
  corrected vs uncertain claim differentiation
- **Live model adaptation** — Compresh's hosted classification
  receives continuous model updates
- **Three-tier pricing** — free for local/free models, saving-share
  for premium providers

Compresh is not required to use tulbase. tulbase remains fully
functional as a standalone MCP server.

## License

MIT — see [LICENSE](./LICENSE).

## Patents

`tulbase`'s Protection Zone mechanism (the last-N-messages-verbatim
guarantee) is covered by **TR-TPMK patent application 2026/007305**
(Compresh Ltd, May 2026, Claim 1(e)). MIT license grants implementation
rights for non-commercial use within this open-source distribution.
Commercial deployments should review the [LICENSE](./LICENSE) and patent
claims.

## Acknowledgements

- LexRank algorithm — Erkan & Radev (2004)
- Tulving memory taxonomy — Tulving (1972, 1983, 2002)
- MCP protocol — Anthropic
