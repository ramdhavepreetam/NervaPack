# Installation

NervaPack supports multiple installation methods. Choose the one that best fits your workflow.

---

## Prerequisites

Before installing NervaPack, ensure you have:

- **Python 3.10+** (check with `python --version`)
- **Git** (your project must be a git repository - run `git init` if needed)
- **LLM Provider** (choose one):
    - **Ollama** (local, privacy-first) — [ollama.com](https://ollama.com/)
    - **Claude API** (cloud) — [console.anthropic.com](https://console.anthropic.com/)
    - **OpenAI API** (cloud) — [platform.openai.com](https://platform.openai.com/api-keys)
    - **Claude Code/Cursor** (MCP integration) — uses your existing session

---

## Installation Methods

### Option A: Homebrew (macOS/Linux — Recommended)

The easiest way to install on macOS or Linux:

```bash
brew tap ramdhavepreetam/nervapack
brew install nervapack
```

Verify installation:
```bash
nervapack --help
```

---

### Option B: pipx (Isolated Install — Recommended)

Best for avoiding dependency conflicts:

```bash
# Install pipx if you don't have it
python -m pip install --user pipx
python -m pipx ensurepath

# Install NervaPack
pipx install nervapack
```

Verify installation:
```bash
nervapack --help
```

---

### Option C: pip (Standard Python Install)

Install directly into your Python environment:

```bash
pip install nervapack
```

Verify installation:
```bash
nervapack --help
```

---

## Optional Features

Install additional features as needed:

### Exact Token Counting
```bash
pip install "nervapack[metrics]"
```
Adds `tiktoken` for precise token counting (vs character-based estimates).

### Web Dashboard
```bash
pip install "nervapack[dashboard]"
```
Adds Streamlit and Plotly for the interactive web dashboard (`nervapack serve`).

### MCP Server (Claude Code/Cursor Integration)
```bash
pip install "nervapack[mcp]"
```
Enables the MCP server for seamless integration with Claude Code and Cursor.

### Cloud LLM Providers
```bash
# Claude API support
pip install "nervapack[claude]"

# OpenAI API support
pip install "nervapack[openai]"

# Both cloud providers
pip install "nervapack[cloud-llm]"
```

### All Features
```bash
pip install "nervapack[all]"
```
Installs all optional features (metrics, dashboard, MCP, cloud LLMs).

---

## Additional Language Support

NervaPack bundles Python, JavaScript, and TypeScript support. Add more languages:

```bash
# Individual languages
pip install "nervapack[go]"      # Go
pip install "nervapack[rust]"    # Rust
pip install "nervapack[java]"    # Java
pip install "nervapack[c]"       # C / C headers
pip install "nervapack[cpp]"     # C++
pip install "nervapack[ruby]"    # Ruby
pip install "nervapack[csharp]"  # C#

# All languages at once
pip install "nervapack[all-languages]"
```

---

## First-Time Setup

On first run, NervaPack will:

1. **Download ChromaDB models** (~1-2 minutes, one-time)
    - ONNX runtime embedding models
    - Stored in your system cache

2. **Compile tree-sitter grammars** (~30 seconds, one-time)
    - Language parsers for AST extraction
    - Cached for future use

!!! tip "First run"
    The initial setup is automatic. Subsequent runs are instant!

---

## Upgrading

### Homebrew
```bash
brew update
brew upgrade nervapack
```

### pipx
```bash
pipx upgrade nervapack
```

### pip
```bash
pip install --upgrade nervapack
```

Check your version:
```bash
nervapack --version
# or
pip show nervapack
```

---

## Uninstalling

### Homebrew
```bash
brew uninstall nervapack
```

### pipx
```bash
pipx uninstall nervapack
```

### pip
```bash
pip uninstall nervapack
```

To remove all NervaPack data (graphs, caches):
```bash
# Remove project-specific graphs
rm -rf .nervapack/

# Remove ChromaDB cache (optional)
rm -rf ~/.cache/chroma
```

---

## Troubleshooting Installation

### Python version errors
```
ERROR: Package requires Python 3.10 or higher
```

**Solution:** Install Python 3.10+ from [python.org](https://www.python.org/downloads/)

### Permission errors on macOS
```
WARNING: The directory '/Users/xxx/Library/Caches/pip' is not owned by you
```

**Solution:** Use `--user` flag:
```bash
pip install --user nervapack
```

Or use pipx (recommended).

### Dependency conflicts
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed
```

**Solution:** Use pipx for isolated installation, or create a virtual environment:
```bash
python -m venv nervapack-env
source nervapack-env/bin/activate  # On Windows: nervapack-env\Scripts\activate
pip install nervapack
```

### tree-sitter compilation errors
**Rare on modern systems. If you encounter this:**

1. Ensure you have a C compiler:
    - **macOS:** `xcode-select --install`
    - **Linux:** `sudo apt install build-essential` (Debian/Ubuntu)
    - **Windows:** Install Visual Studio Build Tools

2. Retry installation

---

## Next Steps

Now that NervaPack is installed, let's set up your LLM provider:

[LLM Provider Setup →](llm-providers.md){ .md-button .md-button--primary }

Or jump straight to the quick start tutorial:

[Quick Start Tutorial →](quick-start.md){ .md-button }
