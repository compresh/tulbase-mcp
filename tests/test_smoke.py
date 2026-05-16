"""Smoke tests — verify imports and tool schema integrity.

Heavier integration tests (real tulbase pipeline, MCP transport round-trip)
will be added once tulbase is reachable in CI (PyPI publish pending).
"""

from __future__ import annotations


def test_package_importable() -> None:
    """`tulbase_mcp` package imports without side effects."""
    import tulbase_mcp

    assert tulbase_mcp.__version__ == "0.1.0"
    assert tulbase_mcp.__license__ == "MIT"


def test_tool_schemas_present() -> None:
    """All four MCP tools are declared with valid schemas."""
    # Import inside test so missing optional deps (mcp SDK) don't fail
    # collection for unrelated tests.
    from tulbase_mcp.server import _TOOLS

    names = {t.name for t in _TOOLS}
    assert names == {"compress", "fetch_compressed", "list_compressed", "stats"}

    for tool in _TOOLS:
        assert tool.description, f"{tool.name} missing description"
        assert tool.inputSchema, f"{tool.name} missing inputSchema"
        assert tool.inputSchema.get("type") == "object"
        assert "properties" in tool.inputSchema


def test_protection_zone_mapping() -> None:
    """Protection Zone N values match Patent Claim 1(e) modes."""
    from tulbase_mcp.server import _PROTECTION_ZONE_N

    assert _PROTECTION_ZONE_N == {
        "off": 0,
        "aggressive": 2,
        "balanced": 4,
        "conservative": 8,
    }


def test_speaker_normalization() -> None:
    """Role → speaker enum mapping handles MCP/OpenAI/Anthropic variants."""
    from tulbase_mcp.server import _normalize_speaker

    assert _normalize_speaker("user") == "user"
    assert _normalize_speaker("USER") == "user"
    assert _normalize_speaker("assistant") == "assistant"
    assert _normalize_speaker("model") == "assistant"
    assert _normalize_speaker("ai") == "assistant"
    assert _normalize_speaker("system") == "system"
    assert _normalize_speaker("tool") == "tool"
    assert _normalize_speaker("function") == "function"
    assert _normalize_speaker("") == "user"
    assert _normalize_speaker("unknown_role") == "user"
