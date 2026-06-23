# LLM Providers

NervaPack supports multiple LLM providers for document-to-code binding. Choose based on your priorities: privacy, cost, quality, or convenience.

---

## Provider Comparison

| Provider | Privacy | Setup | Cost (1000 calls) | Use Case |
|----------|---------|-------|-------------------|----------|
| **Ollama** | 🔒 100% Local | Medium | Free | Privacy-first |
| **Claude API** | ☁️ Cloud | Easy | ~$0.25 | Quality + convenience |
| **OpenAI API** | ☁️ Cloud | Easy | ~$0.15 | Existing OpenAI users |
| **MCP Delegation** | ☁️ Cloud* | Zero | Included | Claude Code users |

\*Uses Claude through your existing subscription

---

## Option 1: Ollama (Default — Privacy-First, Free)

**Best for:** Privacy-conscious users, offline work, no recurring costs

### Setup

```bash
# 1. Install Ollama
brew install ollama
# or download from https://ollama.com/

# 2. Pull a model
ollama pull llama3

# 3. Start Ollama server
ollama serve
```

### Usage

```bash
# NervaPack auto-detects Ollama
nervapack ingest .

# Or explicitly specify
nervapack ingest . --llm ollama
```

### Pros & Cons

✅ **Pros:**
- Free (no recurring costs)
- 100% private (code never leaves your machine)
- Works offline
- No API keys needed

❌ **Cons:**
- ~4GB model download (one-time)
- Uses local CPU/GPU resources
- Slower than cloud APIs

### Recommended Models

- **llama3** (default) — Best balance of speed and quality
- **phi3** — Faster, smaller model
- **mistral** — Good for code understanding
- **codellama** — Specialized for code tasks

Change the model in `.nervapack/config.yaml` (optional):

```yaml
llm:
  provider: ollama
  model: llama3
```

---

## Option 2: Claude API (Cloud — Fast, High Quality)

**Best for:** Users who want best results without local setup

### Setup

```bash
# 1. Install Claude support
pip install "nervapack[claude]"

# 2. Get API key from https://console.anthropic.com
export ANTHROPIC_API_KEY=sk-ant-...

# Or add to ~/.bashrc or ~/.zshrc for persistence
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc
```

### Usage

```bash
# Use Claude API
nervapack ingest . --llm claude

# Specify model (optional)
nervapack ingest . --llm claude --model claude-3-5-sonnet-20241022
```

### Pros & Cons

✅ **Pros:**
- No local installation (beyond pip)
- High quality binding
- Fast (cloud-powered)
- Latest models

❌ **Cons:**
- Sends code to cloud (privacy trade-off)
- Costs money
- Requires internet

### Cost Estimate

**For a typical project:**
- 100 markdown chunks × ~$0.0025 per call = **~$0.25**
- One-time cost per `ingest`
- `sync` only re-processes changed docs

**Available models:**
- `claude-3-haiku-20240307` — Fastest, cheapest (default) — **$0.25/$1.25 per MTok**
- `claude-3-5-sonnet-20241022` — Best quality — **$3/$15 per MTok**

### Configuration

Optional `.nervapack/config.yaml`:

```yaml
llm:
  provider: claude
  model: claude-3-haiku-20240307
  # api_key loaded from ANTHROPIC_API_KEY env var
```

---

## Option 3: OpenAI API (Cloud — Widely Available)

**Best for:** Users with existing OpenAI accounts

### Setup

```bash
# 1. Install OpenAI support
pip install "nervapack[openai]"

# 2. Get API key from https://platform.openai.com/api-keys
export OPENAI_API_KEY=sk-...

# Or persist it
echo 'export OPENAI_API_KEY=sk-...' >> ~/.zshrc
```

### Usage

```bash
# Use OpenAI API
nervapack ingest . --llm openai

# Specify model (optional)
nervapack ingest . --llm openai --model gpt-4o
```

### Pros & Cons

✅ **Pros:**
- Widely available
- Good quality
- Fast
- Familiar to most developers

❌ **Cons:**
- Sends code to cloud
- Costs money
- Requires internet

### Cost Estimate

**For a typical project:**
- 100 markdown chunks × ~$0.0015 per call = **~$0.15**
- One-time cost per `ingest`

**Available models:**
- `gpt-4o-mini` — Cheapest, good quality (default) — **$0.150/$0.600 per MTok**
- `gpt-4o` — Best quality — **$2.50/$10 per MTok**

### Configuration

Optional `.nervapack/config.yaml`:

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  # api_key loaded from OPENAI_API_KEY env var
```

---

## Option 4: MCP Delegation (Claude Code/Cursor)

**Best for:** Users already in Claude Code or Cursor

### Setup

```bash
# Install MCP support
pip install "nervapack[mcp]"

# No API key needed!
# Uses your existing Claude Code/Cursor session
```

### Usage

When using NervaPack through Claude Code:

```bash
# Auto-detects MCP context
nervapack ingest .
```

Or create `.mcp.json` in your project:

```json
{
  "mcpServers": {
    "nervapack": {
      "command": "nervapack-mcp",
      "description": "NervaPack knowledge graph"
    }
  }
}
```

### Pros & Cons

✅ **Pros:**
- Zero configuration
- Uses existing Claude subscription
- No separate API key
- Seamless integration

⚠️ **Cons:**
- Only works in MCP-compatible tools (Claude Code, Cursor)
- Requires Claude subscription

---

## Provider Selection Logic

NervaPack auto-detects the best provider:

```
1. MCP context detected? → Use MCP Delegation
2. --llm flag specified? → Use specified provider
3. ANTHROPIC_API_KEY set? → Use Claude API
4. OPENAI_API_KEY set? → Use OpenAI API
5. Ollama running (localhost:11434)? → Use Ollama
6. Otherwise → Prompt user to set up a provider
```

### Force a Specific Provider

```bash
# Always use Ollama (even if API keys exist)
nervapack ingest . --llm ollama

# Always use Claude
nervapack ingest . --llm claude
```

---

## Privacy Comparison

### Ollama (Most Private)
- ✅ Code never leaves your machine
- ✅ Embeddings generated locally (ChromaDB)
- ✅ LLM runs locally
- ✅ No telemetry

### Cloud APIs (Privacy Trade-off)
- ⚠️ Markdown chunks sent to cloud for binding
- ⚠️ AST code content NOT sent (only summaries)
- ⚠️ Check provider's data retention policies:
    - [Anthropic Privacy](https://www.anthropic.com/privacy)
    - [OpenAI Privacy](https://openai.com/privacy/)

!!! warning "Sensitive codebases"
    If your codebase contains proprietary algorithms or trade secrets, **use Ollama** for 100% privacy.

---

## Performance Comparison

Based on a 500-file Python project with 50 markdown docs:

| Provider | Binding Time | Quality | Cost |
|----------|--------------|---------|------|
| Ollama (llama3) | ~10 minutes | Good | $0 |
| Claude Haiku | ~2 minutes | Excellent | ~$0.12 |
| Claude Sonnet | ~2 minutes | Best | ~$0.30 |
| GPT-4o-mini | ~2 minutes | Good | ~$0.08 |
| GPT-4o | ~2 minutes | Excellent | ~$0.50 |

---

## Switching Providers

You can change providers anytime:

```bash
# Original ingest with Ollama
nervapack ingest .

# Later, re-bind docs with Claude (faster, higher quality)
nervapack ingest . --llm claude

# Existing AST graph is preserved
# Only doc-to-code bindings are re-computed
```

---

## Troubleshooting

### "Ollama not running"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve
```

### "Invalid API key" (Claude/OpenAI)
```bash
# Check if env var is set
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY

# Re-export if needed
export ANTHROPIC_API_KEY=sk-ant-...
```

### "Provider not found"
```bash
# Install the optional extra
pip install "nervapack[claude]"
pip install "nervapack[openai]"
pip install "nervapack[mcp]"
```

---

## Recommended Setup by Use Case

### Personal Projects (Privacy-First)
```bash
# Use Ollama
ollama pull llama3
nervapack ingest .
```

### Commercial Projects (Balance)
```bash
# Use Claude Haiku (good quality, low cost)
pip install "nervapack[claude]"
export ANTHROPIC_API_KEY=...
nervapack ingest . --llm claude
```

### Enterprise (Maximum Privacy)
```bash
# Use Ollama with self-hosted model
ollama pull llama3
nervapack ingest . --llm ollama
```

### Claude Code Users (Convenience)
```bash
# Use MCP delegation (zero config)
pip install "nervapack[mcp]"
nervapack ingest .
```

---

## Next Steps

Now that you've chosen your LLM provider:

[Quick Start Tutorial →](quick-start.md){ .md-button .md-button--primary }

Or learn about the architecture:

[How NervaPack Works →](../user-guide/concepts/architecture.md){ .md-button }
