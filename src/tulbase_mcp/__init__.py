"""tulbase-mcp — MCP server for tulbase context compression.

Exposes tulbase's compression pipeline to any MCP-aware LLM client
(Claude Code, Cursor, Cline, Continue, Cowork, etc.) via stdio
transport.

Tools:
    - compress(messages) → optimized message list + TurnBox metadata
    - fetch_compressed(id, max_tokens) → original elided content
    - list_compressed(turn_min, turn_max, modality) → entry index
    - stats() → session compression statistics

Open-source core. The proprietary Q-protective ranking and epistemic
classification layers are part of Compresh paid tier (compre.sh).
"""

__version__ = "0.1.0"
__author__ = "Compresh Ltd"
__license__ = "MIT"

from .server import main as run_server

__all__ = ["__version__", "run_server"]
