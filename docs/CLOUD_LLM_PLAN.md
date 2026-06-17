# Cloud LLM Support - Implementation Plan

> **Created:** 2026-06-17
> **Status:** Planning Phase
> **Priority:** HIGH - Removes major barrier to entry (Ollama requirement)

---

## Executive Summary

Add support for cloud-based LLMs (Claude, OpenAI, etc.) as an alternative to local Ollama. This gives users a choice:
- **Privacy-first users**: Keep using Ollama (100% local, no cloud)
- **Convenience-first users**: Use Claude/OpenAI (no local install needed)

This removes the biggest barrier to trying NervaPack: having to download and run Ollama.

---

## Current State Analysis

### How LLMs Are Used Today

**Location:** `src/nervapack/llm/summarizer.py`

**Two use cases:**
1. **Code Summarization** (currently unused in production)
   - Method: `summarize_entity(entity)`
   - Purpose: Generate 1-3 sentence summary of code blocks
   - Usage: Was designed for better embeddings, but current code uses raw content

2. **Doc-to-Code Binding** (CRITICAL PATH)
   - Method: `bind_docs_to_ast(doc_chunk, ast_nodes)`
   - Purpose: Identify which code entities a markdown chunk explains
   - Usage: During `ingest` and `sync` commands
   - **This is the only LLM call that matters**

### Current Limitations

**Hard dependency on Ollama:**
```bash
# Users must do this before NervaPack works:
brew install ollama
ollama pull llama3
ollama serve  # Must keep running
```

**Barriers:**
- ~4GB model download
- Uses RAM/CPU while running
- Setup complexity for non-technical users
- Doesn't work well on low-resource machines
- Regional availability issues (Ollama not everywhere)

---

## Proposed Solution: Multi-Provider LLM System

### Architecture

```
┌─────────────────────────────────────────────────────┐
│           LLM Provider Abstraction                  │
└─────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┬──────────────┐
        │               │               │              │
   OllamaProvider  ClaudeProvider  OpenAIProvider  GeminiProvider
   (local, free)   (cloud, paid)   (cloud, paid)   (cloud, paid)
```

### Configuration Options

**Option 1: Environment Variables (Simplest)**
```bash
# Use Ollama (default, backwards compatible)
nervapack ingest .

# Use Claude
export NERVAPACK_LLM_PROVIDER=claude
export ANTHROPIC_API_KEY=sk-ant-...
nervapack ingest .

# Use OpenAI
export NERVAPACK_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
nervapack ingest .
```

**Option 2: Config File (More Flexible)**
```yaml
# .nervapack/config.yaml
llm:
  provider: claude  # ollama, claude, openai, gemini
  model: claude-3-haiku-20240307
  api_key: ${ANTHROPIC_API_KEY}  # or hardcoded (not recommended)

  # Provider-specific settings
  ollama:
    model: llama3
    base_url: http://localhost:11434

  claude:
    model: claude-3-haiku-20240307
    max_tokens: 1024

  openai:
    model: gpt-4o-mini
    temperature: 0.0
```

**Option 3: CLI Flags (Most Explicit)**
```bash
nervapack ingest . --llm claude --model claude-3-haiku-20240307
nervapack ingest . --llm openai --model gpt-4o-mini
nervapack ingest . --llm ollama --model llama3  # default
```

**Recommendation:** Implement all three, with priority order:
1. CLI flags (highest priority)
2. Environment variables
3. Config file
4. Defaults (Ollama for backwards compatibility)

---

## Implementation Plan

### Phase 1: Abstraction Layer (2-3 hours)

**Tasks:**
1. Create `LLMProvider` abstract base class
2. Implement `OllamaProvider` (refactor existing code)
3. Add provider factory pattern
4. Add configuration loading

**Files to Create:**
```
src/nervapack/llm/
├── __init__.py
├── base.py              # [NEW] Abstract LLMProvider
├── providers/           # [NEW]
│   ├── __init__.py
│   ├── ollama.py        # [NEW] Refactored OllamaProvider
│   ├── claude.py        # [NEW] ClaudeProvider
│   ├── openai.py        # [NEW] OpenAIProvider
│   └── gemini.py        # [NEW] GeminiProvider (optional)
├── factory.py           # [NEW] Provider factory
└── summarizer.py        # [MODIFY] Use factory
```

**Code Sketch:**

```python
# src/nervapack/llm/base.py
from abc import ABC, abstractmethod
from typing import List, Dict

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]],
             system_prompt: str = "") -> str:
        """
        Send a chat completion request.

        Args:
            messages: List of {role: str, content: str}
            system_prompt: Optional system message

        Returns:
            Response text content
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Check if provider is properly configured."""
        pass

    def summarize_entity(self, entity_type: str, entity_name: str,
                        content: str) -> str:
        """Generate summary for code entity (shared logic)."""
        prompt = f"Summarize this {entity_type} named {entity_name}:\n\n{content}"
        messages = [{"role": "user", "content": prompt}]
        system = "You are a concise code summarizer. Output only 1-3 sentences."
        return self.chat(messages, system)

    def bind_docs_to_ast(self, doc_chunk: str,
                         ast_nodes: List[Dict]) -> List[str]:
        """Find which AST nodes a doc chunk explains (shared logic)."""
        candidates = "\n".join([
            f"ID: {n['node_id']} | Summary: {n['summary']}"
            for n in ast_nodes
        ])
        prompt = (
            f"Documentation:\n{doc_chunk}\n\n"
            f"Which code entities does it explain? "
            f"Return comma-separated IDs or 'None'.\n\n"
            f"Candidates:\n{candidates}"
        )
        messages = [{"role": "user", "content": prompt}]
        system = "Output ONLY comma-separated IDs."

        response = self.chat(messages, system).strip()
        if response.lower() == "none" or not response:
            return []
        return [i.strip() for i in response.split(",") if i.strip()]
```

```python
# src/nervapack/llm/providers/ollama.py
import ollama
from ..base import LLMProvider

class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama3", base_url: str = None):
        self.model = model
        self.base_url = base_url or "http://localhost:11434"

    def chat(self, messages, system_prompt=""):
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        response = ollama.chat(model=self.model, messages=messages)
        return response['message']['content']

    def validate_config(self) -> bool:
        try:
            ollama.list()  # Check if Ollama is running
            return True
        except:
            return False
```

```python
# src/nervapack/llm/providers/claude.py
from anthropic import Anthropic
from ..base import LLMProvider

class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str = None,
                 model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key
        self.model = model
        self.client = Anthropic(api_key=api_key)

    def chat(self, messages, system_prompt=""):
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )
        return response.content[0].text

    def validate_config(self) -> bool:
        return self.api_key is not None and self.api_key.startswith("sk-ant-")
```

```python
# src/nervapack/llm/providers/openai.py
from openai import OpenAI
from ..base import LLMProvider

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str = None,
                 model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def chat(self, messages, system_prompt=""):
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.0
        )
        return response.choices[0].message.content

    def validate_config(self) -> bool:
        return self.api_key is not None and self.api_key.startswith("sk-")
```

```python
# src/nervapack/llm/factory.py
import os
from typing import Optional
from .base import LLMProvider
from .providers.ollama import OllamaProvider
from .providers.claude import ClaudeProvider
from .providers.openai import OpenAIProvider

def get_llm_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> LLMProvider:
    """
    Factory function to get LLM provider.

    Priority order:
    1. Explicit parameters
    2. Environment variables
    3. Config file (.nervapack/config.yaml)
    4. Defaults (Ollama)
    """
    # 1. Check explicit parameters
    provider = provider or os.getenv("NERVAPACK_LLM_PROVIDER", "ollama")

    # 2. Get provider-specific config
    if provider == "ollama":
        model = model or os.getenv("OLLAMA_MODEL", "llama3")
        return OllamaProvider(model=model)

    elif provider == "claude":
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        model = model or os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")
        if not api_key:
            raise ValueError(
                "Claude API key required. Set ANTHROPIC_API_KEY "
                "or pass api_key parameter."
            )
        return ClaudeProvider(api_key=api_key, model=model)

    elif provider == "openai":
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY "
                "or pass api_key parameter."
            )
        return OpenAIProvider(api_key=api_key, model=model)

    else:
        raise ValueError(f"Unknown provider: {provider}")
```

---

### Phase 2: CLI Integration (1-2 hours)

**Update commands to accept LLM flags:**

```python
# src/nervapack/cli.py
@app.command()
def ingest(
    path: str = typer.Argument(".", help="Path to repository"),
    llm: str = typer.Option("ollama", help="LLM provider: ollama, claude, openai"),
    model: str = typer.Option(None, help="Model name (provider-specific)"),
    api_key: str = typer.Option(None, help="API key for cloud providers")
):
    """Ingest repository with specified LLM provider."""
    from nervapack.llm.factory import get_llm_provider

    console.print(f"[bold blue]Using LLM provider: {llm}[/bold blue]")

    try:
        llm_provider = get_llm_provider(
            provider=llm,
            model=model,
            api_key=api_key
        )

        if not llm_provider.validate_config():
            console.print("[bold red]LLM provider not properly configured![/bold red]")
            if llm == "ollama":
                console.print("Make sure Ollama is running: ollama serve")
            else:
                console.print(f"Make sure {llm.upper()}_API_KEY is set")
            return

        console.print("[green]✓[/green] LLM provider validated")

        # ... rest of ingest logic, but use llm_provider instead of LLMSummarizer

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
```

---

### Phase 3: Config File Support (1 hour)

**Add config loading:**

```python
# src/nervapack/config.py
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

class Config:
    """NervaPack configuration manager."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.config_path = self.project_root / ".nervapack" / "config.yaml"
        self._config: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        """Load config from file."""
        if not self.config_path.exists():
            return self._default_config()

        with open(self.config_path) as f:
            return yaml.safe_load(f) or {}

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration."""
        return {
            "llm": {
                "provider": "ollama",
                "model": "llama3"
            }
        }

    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration."""
        config = self.load()
        return config.get("llm", {})
```

---

### Phase 4: Documentation & UX (1-2 hours)

**Tasks:**
1. Update README with LLM provider options
2. Add setup guides for each provider
3. Add cost estimation warnings
4. Create troubleshooting guide

**README additions:**

```markdown
## LLM Provider Options

NervaPack supports multiple LLM providers. Choose based on your priorities:

### Option 1: Ollama (Default, 100% Private)

**Best for:** Privacy-conscious users, offline work, no costs

```bash
# One-time setup
brew install ollama
ollama pull llama3
ollama serve

# Use NervaPack
nervapack ingest .
```

**Pros:** Free, private, works offline
**Cons:** ~4GB download, uses local resources

---

### Option 2: Claude (Cloud, Fast, High Quality)

**Best for:** Users who want best results without local setup

```bash
# Get API key from https://console.anthropic.com
export ANTHROPIC_API_KEY=sk-ant-...

# Use NervaPack with Claude
nervapack ingest . --llm claude --model claude-3-haiku-20240307
```

**Cost estimate:** ~$0.25 per 1000 API calls
**Model options:**
- `claude-3-haiku-20240307` (fastest, cheapest)
- `claude-3-5-sonnet-20241022` (best quality, moderate cost)

**Pros:** No local install, high quality, fast
**Cons:** Requires API key, costs money, sends code to cloud

---

### Option 3: OpenAI (Cloud, Widely Available)

**Best for:** Users with existing OpenAI accounts

```bash
# Get API key from https://platform.openai.com
export OPENAI_API_KEY=sk-...

# Use NervaPack with OpenAI
nervapack ingest . --llm openai --model gpt-4o-mini
```

**Cost estimate:** ~$0.15 per 1000 API calls
**Model options:**
- `gpt-4o-mini` (cheapest, good quality)
- `gpt-4o` (best quality, higher cost)

**Pros:** Widely available, good quality
**Cons:** Costs money, sends code to cloud

---

### Privacy Comparison

| Provider | Code Privacy | Setup Effort | Cost |
|----------|--------------|--------------|------|
| Ollama   | ✅ 100% Local | Medium (install + model) | Free |
| Claude   | ❌ Sent to Anthropic | Low (just API key) | ~$0.25/1K calls |
| OpenAI   | ❌ Sent to OpenAI | Low (just API key) | ~$0.15/1K calls |

### Cost Calculator

Typical ingestion for a medium-sized repo (500 files, 50 markdown docs):
- Ollama: **$0** (free)
- Claude Haiku: **~$1.25** (50 binding calls × $0.25/1K)
- OpenAI GPT-4o-mini: **~$0.75** (50 calls × $0.15/1K)

**Note:** After initial ingestion, only `nervapack sync` makes LLM calls, and only for changed files.
```

---

### Phase 5: Safety & Validation (1 hour)

**Add safety checks:**

```python
# src/nervapack/llm/safety.py
from typing import Dict, Any
from rich.console import Console
from rich.prompt import Confirm

console = Console()

def check_privacy_consent(provider: str, config: Dict[str, Any]) -> bool:
    """
    Warn user about privacy implications of cloud LLMs.
    Returns True if user consents, False otherwise.
    """
    if provider == "ollama":
        return True  # No privacy concerns

    # First-time cloud provider usage
    consent_file = Path(".nervapack") / f".{provider}_consent"
    if consent_file.exists():
        return True  # Already consented

    console.print(f"\n[bold yellow]⚠️  Privacy Notice[/bold yellow]")
    console.print(f"You are about to use {provider.upper()}, a cloud-based LLM.")
    console.print(f"\n[bold]What this means:[/bold]")
    console.print(f"  • Your code and documentation will be sent to {provider}")
    console.print(f"  • This may violate your company's data policies")
    console.print(f"  • API calls will incur costs (~$0.15-$0.25 per 1000 calls)")
    console.print(f"\n[bold]Alternative:[/bold] Use --llm ollama for 100% local processing\n")

    if Confirm.ask("Do you understand and accept these terms?"):
        consent_file.parent.mkdir(exist_ok=True)
        consent_file.touch()
        return True

    return False

def estimate_cost(provider: str, num_markdown_chunks: int) -> None:
    """Display cost estimate before ingestion."""
    if provider == "ollama":
        console.print("[green]Cost: $0 (local processing)[/green]")
        return

    cost_per_1k = {
        "claude": 0.25,
        "openai": 0.15,
        "gemini": 0.10
    }

    estimated_cost = (num_markdown_chunks / 1000) * cost_per_1k.get(provider, 0.20)

    console.print(f"\n[bold yellow]💰 Cost Estimate[/bold yellow]")
    console.print(f"Provider: {provider}")
    console.print(f"Markdown chunks: {num_markdown_chunks}")
    console.print(f"Estimated cost: ${estimated_cost:.2f}")
    console.print(f"(Actual cost may vary based on content length)\n")
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_llm_providers.py
import pytest
from nervapack.llm.factory import get_llm_provider
from nervapack.llm.providers.ollama import OllamaProvider

def test_factory_default():
    """Test factory returns Ollama by default."""
    provider = get_llm_provider()
    assert isinstance(provider, OllamaProvider)

def test_factory_claude():
    """Test factory returns Claude with API key."""
    provider = get_llm_provider(
        provider="claude",
        api_key="sk-ant-test123"
    )
    assert provider.model == "claude-3-haiku-20240307"

def test_provider_validation():
    """Test provider config validation."""
    # Ollama should work without API key
    ollama = get_llm_provider("ollama")
    # Will fail if Ollama not running, but that's expected

    # Claude should fail without API key
    with pytest.raises(ValueError):
        get_llm_provider("claude")
```

### Integration Tests

```bash
# Test with each provider (requires API keys)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...

# Test Ollama
nervapack ingest test-repo/ --llm ollama

# Test Claude
nervapack ingest test-repo/ --llm claude

# Test OpenAI
nervapack ingest test-repo/ --llm openai

# Verify all produce same graph structure
```

---

## Dependencies

### New Required Dependencies

```toml
# pyproject.toml
[project.optional-dependencies]
# Existing
metrics = ["tiktoken>=0.5.2"]
dashboard = ["streamlit>=1.29.0", "plotly>=5.18.0"]
mcp = ["mcp>=0.1.0"]

# NEW: Cloud LLM support
claude = ["anthropic>=0.18.0"]
openai = ["openai>=1.12.0"]
gemini = ["google-generativeai>=0.3.0"]  # optional

# Combined
cloud-llm = ["anthropic>=0.18.0", "openai>=1.12.0"]
all = [
    "tiktoken>=0.5.2",
    "streamlit>=1.29.0",
    "plotly>=5.18.0",
    "mcp>=0.1.0",
    "anthropic>=0.18.0",
    "openai>=1.12.0"
]
```

### Installation Options

```bash
# Default (Ollama only)
pip install nervapack

# With Claude support
pip install "nervapack[claude]"

# With OpenAI support
pip install "nervapack[openai]"

# With all cloud providers
pip install "nervapack[cloud-llm]"

# Everything
pip install "nervapack[all]"
```

---

## Migration Path

### Backwards Compatibility

**Must maintain 100% backwards compatibility:**
- Default to Ollama if no provider specified
- Existing commands work exactly as before
- No breaking changes to API

**Migration guide for users:**

```markdown
## Migrating from Ollama-only to Multi-Provider

**Existing users:** Nothing changes. Keep using Ollama as before.

**New users:** Choose your provider:

```bash
# Privacy-first: Ollama (existing workflow)
ollama pull llama3
nervapack ingest .

# Convenience-first: Claude (new workflow)
export ANTHROPIC_API_KEY=sk-ant-...
nervapack ingest . --llm claude
```

**Switching providers:**
NervaPack stores the graph, not LLM output, so you can switch providers anytime:

```bash
# Initial ingest with Ollama
nervapack ingest . --llm ollama

# Later sync with Claude (works fine!)
nervapack sync . --llm claude
```
```

---

## Rollout Plan

### Week 1: Core Implementation
- [ ] Day 1-2: Abstract base class + Ollama refactor
- [ ] Day 3-4: Claude + OpenAI providers
- [ ] Day 5: Factory pattern + config loading

### Week 2: Integration & Polish
- [ ] Day 1-2: CLI integration + flags
- [ ] Day 3: Privacy consent + cost estimation
- [ ] Day 4-5: Testing + bug fixes

### Week 3: Documentation & Release
- [ ] Day 1-2: Update all documentation
- [ ] Day 3: Create migration guide
- [ ] Day 4: Test on real repos
- [ ] Day 5: Release v0.4.0

---

## Success Metrics

### Adoption Metrics
- [ ] 50%+ of new users choose cloud LLM option
- [ ] <5% support tickets related to LLM setup
- [ ] Zero complaints about privacy warnings

### Technical Metrics
- [ ] 100% backwards compatibility (all existing tests pass)
- [ ] <5% performance overhead from abstraction layer
- [ ] All three providers produce equivalent graph quality

### User Feedback
- [ ] "Much easier to get started"
- [ ] "Love the flexibility"
- [ ] "Appreciate the privacy warnings"

---

## Risks & Mitigations

### Risk 1: API Key Leakage
**Risk:** Users accidentally commit API keys to git

**Mitigation:**
- Warn users to use environment variables
- Add `.nervapack/config.yaml` to `.gitignore`
- Never log API keys
- Add pre-commit hook to detect keys

### Risk 2: Unexpected Costs
**Risk:** Users rack up large API bills

**Mitigation:**
- Show cost estimate before ingestion
- Require explicit consent for cloud providers
- Document costs clearly
- Add `--dry-run` flag to preview LLM calls

### Risk 3: Quality Variance
**Risk:** Different providers give different binding results

**Mitigation:**
- Use same prompts across all providers
- Test all providers on same repos
- Document any known quality differences
- Allow users to easily switch providers

### Risk 4: Dependency Bloat
**Risk:** Adding 3+ new dependencies increases install size

**Mitigation:**
- Make all cloud providers optional extras
- Keep default install lightweight (Ollama only)
- Use lazy imports where possible

---

## Future Enhancements

### Phase 6: Additional Providers (Future)
- Google Gemini support
- Azure OpenAI support
- Cohere support
- Local alternatives (LLaMA.cpp, etc.)

### Phase 7: Smart Provider Selection (Future)
- Auto-detect best available provider
- Fallback chain (try Claude, fallback to OpenAI, fallback to Ollama)
- Provider benchmarking and recommendations

### Phase 8: Cost Optimization (Future)
- Cache LLM responses to avoid re-calling same content
- Batch API calls where possible
- Use cheaper models for simple tasks

---

## Open Questions

1. **Should we support local OpenAI-compatible APIs?**
   - LM Studio, LocalAI, etc. use OpenAI-compatible APIs
   - Could be middle ground: OpenAI interface, local privacy
   - Answer: Yes, add `--openai-base-url` flag

2. **Should we add rate limiting?**
   - To avoid hitting API rate limits
   - To control costs
   - Answer: Yes, add configurable rate limits

3. **Should we store which provider was used?**
   - In graph metadata
   - For reproducibility
   - Answer: Yes, store in `.nervapack/metadata.json`

4. **Should we support multiple providers in one repo?**
   - Different providers for different file types?
   - Answer: No, keep it simple for v1

---

## Conclusion

This plan adds critical flexibility to NervaPack while maintaining its privacy-first ethos. Users get to choose:

- **Privacy + Free** → Ollama (existing workflow)
- **Convenience + Quality** → Claude/OpenAI (new option)

**Estimated effort:** 2-3 weeks
**Breaking changes:** None
**User impact:** Massive (removes #1 barrier to entry)
**Recommended priority:** HIGH

**Next steps:**
1. Get feedback on this plan
2. Prioritize against other roadmap items (Phase 4, Phase 5)
3. Start implementation with Phase 1

---

**Status:** ✅ Ready for implementation
**Estimated completion:** 3 weeks from start
**Version target:** v0.4.0
