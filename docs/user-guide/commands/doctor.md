# `nervapack doctor`

Check system configuration and NervaPack dependencies.

---

## Synopsis

```bash
nervapack doctor
```

---

## Description

`doctor` runs a series of environment checks and reports any issues that would prevent NervaPack from working correctly. Run it after installation or when troubleshooting unexpected errors.

**Checks performed:**

1. **Python version** — must be ≥ 3.9
2. **Tree-sitter grammars** — verifies `tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript` are installed
3. **Embedding backend** — reads `NERVAPACK_EMBEDDINGS` env var; if set to `ollama`, tests connectivity to `localhost:11434`
4. **MCP config** — looks for `.mcp.json` in the current directory or `~/.claude_code/mcp.json`

---

## Examples

```bash
nervapack doctor
```

---

## Output — All systems go

```
NervaPack System Check

✓ Python version: 3.11.4
✓ Tree-sitter grammars: All core grammars installed
✓ Embedding backend configured as: onnx
✓ MCP config: Found

All systems go! NervaPack is ready.
```

## Output — Issues found

```
NervaPack System Check

✓ Python version: 3.11.4
✗ Tree-sitter grammars missing: tree-sitter-javascript, tree-sitter-typescript
✓ Embedding backend configured as: onnx
⚠ MCP config: Not found (Optional)

Recommended Fixes:
  1. Run: pip install tree-sitter-javascript tree-sitter-typescript
  2. If using Claude Code, configure MCP by running:
     claude mcp add nervapack python -m nervapack mcp
```

---

## Environment Variables

| Variable | Effect |
|----------|--------|
| `NERVAPACK_EMBEDDINGS` | `onnx` (default) or `ollama` — controls which embedding backend is checked |

---

## See Also

- [`ingest`](ingest.md) — build the knowledge graph
- [`enrich`](enrich.md) — add semantic doc-code edges
- [Installation guide](../../getting-started/installation.md)
