# Contributing to tulbase-mcp

Thanks for your interest in contributing. `tulbase-mcp` is an open-source
MCP server that exposes the `tulbase` compression engine to any
MCP-aware LLM client.

## Scope

`tulbase-mcp` is intentionally **minimal**:

- Stdio transport (local-only)
- Four tools: `compress`, `fetch_compressed`, `list_compressed`, `stats`
- No network I/O
- No proprietary algorithms

For Q-protective ranking, epistemic markers, semantic store, and other
advanced features, see [Compresh](https://compre.sh) — the hosted paid
tier.

## Out of scope (for this repo)

- HTTP transport (use [Compresh](https://compre.sh) hosted API instead)
- Q matrix classifier (proprietary)
- Cross-session memory or sync (paid tier feature)
- Telemetry / analytics

Pull requests touching these areas will be redirected to the appropriate
project.

## Local development

```bash
git clone https://github.com/compresh/tulbase-mcp
cd tulbase-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest -v
```

Run the server manually (stdio mode, for integration tests):

```bash
python -m tulbase_mcp.server
```

## Pull request checklist

- [ ] `ruff check src tests` passes
- [ ] `mypy src/tulbase_mcp` clean (no new errors)
- [ ] New behavior covered by tests
- [ ] README and tool docstrings updated if interface changes
- [ ] No proprietary algorithm logic introduced

## Reporting bugs

Open an issue with:
- Python version
- MCP client (Claude Code / Cursor / Cline / Cowork / other)
- Minimal reproduction
- Expected vs actual behavior

## License

By contributing, you agree that your contributions will be licensed under
the MIT License, in accordance with the project [LICENSE](./LICENSE).

## Patent notice

Contributions that touch the Protection Zone mechanism (last-N-messages-
verbatim preservation, Claim 1(e) of TR-TPMK patent application 2026/007305)
must be reviewed by Compresh Ltd. This does not restrict use of the
MIT-licensed code, but ensures patent claims remain consistent.
