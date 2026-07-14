# `nervapack enrich`

Add semantic doc-to-code edges to an existing graph without full re-ingestion.

---

## Synopsis

```bash
nervapack enrich [PATH] [OPTIONS]
```

---

## Description

`enrich` reads the existing graph (built by `nervapack ingest`) and uses an LLM to create `EXPLAINS` edges between markdown documentation nodes and AST code nodes. This is useful when:

- You ran `ingest` without an LLM (structural graph only) and now want to add semantic bindings.
- You added new documentation and want to bind it to existing code without re-parsing the entire codebase.
- You want to upgrade the binding quality (e.g., switch from keyword-based to LLM-based).

The command **requires a running LLM** (Ollama, Claude, or OpenAI). Unlike `ingest`, it will error if no LLM is available, since its sole purpose is semantic binding.

---

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `PATH` | Path to the repository | `.` (current) |
| `--llm` | LLM provider (`ollama`, `claude`, `openai`, `mcp`) | Auto-detect |
| `--model` | Model name (provider-specific) | Provider default |
| `--api-key` | API key for cloud providers | From env vars |

---

## Examples

### Enrich with local Ollama
```bash
nervapack enrich .
nervapack enrich . --llm ollama --model llama3
```

### Enrich with Claude (shows cost estimate before proceeding)
```bash
nervapack enrich . --llm claude
```

### Enrich a different repo
```bash
nervapack enrich /path/to/repo --llm openai --model gpt-4o
```

---

## Expected Output

```
Enriching repository at .

Setting up LLM provider...
Using LLM provider: ollama (llama3:latest)

Adding semantic edges for 24 markdown chunks...
Enrichment complete. Added 87 semantic edges.
```

For cloud providers, a cost estimate is shown before binding starts:

```
💰 Cost Estimate
Provider: claude (claude-haiku-4-5-20251001)
Markdown chunks to bind: 24
Estimated cost: $0.03
Proceed with cloud LLM binding? [y/n]:
```

---

## Notes

- Existing `EXPLAINS` edges are preserved — only new edges are added (no duplicates).
- If the graph doesn't exist yet, run `nervapack ingest .` first.
- To re-bind from scratch, delete `.nervapack/graph.graphml` and run `ingest` again.

---

## See Also

- [`ingest`](ingest.md) — build the full graph (includes structural + optional semantic binding)
- [`doctor`](doctor.md) — verify your LLM and environment are correctly configured
- [`sync`](sync.md) — update the graph after code changes
