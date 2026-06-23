# Contributing to NervaPack

Thank you for your interest in contributing to NervaPack! This guide will help you get started.

---

## Quick Links

- **GitHub Repository:** [ramdhavepreetam/NervaPack](https://github.com/ramdhavepreetam/NervaPack)
- **Issue Tracker:** [GitHub Issues](https://github.com/ramdhavepreetam/NervaPack/issues)
- **Discussions:** [GitHub Discussions](https://github.com/ramdhavepreetam/NervaPack/discussions)

---

## How Can I Contribute?

### 🐛 Reporting Bugs

Found a bug? Please [open an issue](https://github.com/ramdhavepreetam/NervaPack/issues/new) with:

- **Clear title:** Describe the problem concisely
- **Steps to reproduce:** How can we reproduce the bug?
- **Expected behavior:** What should happen?
- **Actual behavior:** What actually happens?
- **Environment:** OS, Python version, NervaPack version
- **Logs/screenshots:** If applicable

**Example:**
```
Title: "nervapack sync fails with git detached HEAD"

Steps:
1. git checkout <commit-hash>
2. nervapack sync .
3. Error: "Not on a branch"

Expected: Should sync successfully
Actual: Fails with GitPython error

Environment:
- macOS 14.2
- Python 3.11.5
- NervaPack 0.4.1
```

---

### 💡 Suggesting Features

Have an idea? [Open a feature request](https://github.com/ramdhavepreetam/NervaPack/issues/new) with:

- **Use case:** What problem does this solve?
- **Proposed solution:** How should it work?
- **Alternatives considered:** Other approaches you thought about
- **Additional context:** Mockups, examples, etc.

---

### 📖 Improving Documentation

Documentation improvements are always welcome!

- Fix typos or unclear explanations
- Add examples or tutorials
- Improve API docstrings
- Translate documentation (future)

---

### 💻 Code Contributions

Ready to write code? Great! Follow the development workflow below.

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/YOUR_USERNAME/NervaPack.git
cd NervaPack

# Add upstream remote
git remote add upstream https://github.com/ramdhavepreetam/NervaPack.git
```

### 2. Create Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows
```

### 3. Install in Development Mode

```bash
# Install with all extras
pip install -e ".[all]"

# Install development tools
pip install pytest pytest-cov ruff mypy black
```

### 4. Verify Installation

```bash
# Run NervaPack
nervapack --help

# Run tests (when available)
pytest

# Check code style
ruff check src/
```

---

## Development Workflow

### 1. Create a Branch

```bash
# Sync with upstream
git fetch upstream
git checkout master
git merge upstream/master

# Create feature branch
git checkout -b feature/your-feature-name
# or: git checkout -b fix/bug-description
```

**Branch naming:**
- `feature/add-rust-parser` — New features
- `fix/sync-git-error` — Bug fixes
- `docs/improve-quickstart` — Documentation
- `refactor/llm-factory` — Code improvements

### 2. Make Changes

```bash
# Edit code
vim src/nervapack/...

# Test locally
nervapack ingest .
nervapack query "test"
```

**Code style:**
- Follow PEP 8 (enforced by `ruff`)
- Add docstrings to all public functions
- Keep functions focused and small
- Write descriptive variable names

### 3. Add Tests (Important!)

```bash
# Create test file
touch tests/test_your_feature.py

# Write tests
cat > tests/test_your_feature.py <<'EOF'
import pytest
from nervapack.your_module import your_function

def test_your_function():
    result = your_function("input")
    assert result == "expected_output"
EOF

# Run tests
pytest tests/test_your_feature.py
```

### 4. Format and Lint

```bash
# Auto-format code
black src/ tests/

# Check style
ruff check src/ tests/

# Type check
mypy src/nervapack/
```

### 5. Commit Changes

```bash
# Add files
git add src/nervapack/your_file.py tests/test_your_feature.py

# Commit with descriptive message
git commit -m "feat: Add Rust parser support

- Implement tree-sitter-rust integration
- Add Rust-specific node type mappings
- Update documentation with Rust examples
- Add tests for Rust AST parsing

Closes #123"
```

**Commit message format:**
```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code refactoring
- `test:` — Adding tests
- `chore:` — Maintenance (deps, config)

### 6. Push and Create PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Open pull request on GitHub
# Click "Compare & pull request" button
```

**PR template:**
```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- Added X
- Updated Y
- Fixed Z

## Testing
How did you test this?

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Code formatted (black)
- [ ] Linting passes (ruff)
- [ ] No breaking changes (or documented in CHANGELOG)
```

---

## Code Style Guide

### Python Style

```python
# Good
def parse_ast_file(file_path: str, language: str) -> List[ParsedEntity]:
    """
    Parse a file into AST entities using tree-sitter.

    Args:
        file_path: Absolute path to the source file
        language: Language identifier (e.g., "python", "javascript")

    Returns:
        List of parsed entities (classes, functions, imports)

    Raises:
        FileNotFoundError: If file_path doesn't exist
        ValueError: If language is not supported

    Example:
        >>> entities = parse_ast_file("src/main.py", "python")
        >>> len(entities)
        42
    """
    # Implementation...
```

```python
# Bad (no docstring, unclear names)
def parse(f, l):
    # What does this do?
    pass
```

### Import Organization

```python
# Standard library
import os
import sys
from pathlib import Path
from typing import List, Optional

# Third-party
import typer
from rich.console import Console
import networkx as nx

# Local
from nervapack.parser.ast_parser import ASTParser
from nervapack.graph.builder import GraphBuilder
```

### Error Handling

```python
# Good
try:
    graph = builder.load_graph()
except FileNotFoundError:
    console.print("[red]No graph found. Run 'nervapack ingest' first.[/red]")
    raise typer.Exit(1)
except Exception as e:
    console.print(f"[red]Unexpected error:[/red] {e}")
    raise

# Bad (swallowing exceptions)
try:
    graph = builder.load_graph()
except:
    pass  # Silent failure!
```

---

## Testing Guidelines

### Test Structure

```python
# tests/test_graph_builder.py
import pytest
from nervapack.graph.builder import GraphBuilder

class TestGraphBuilder:
    """Tests for GraphBuilder class."""

    def test_build_from_entities(self):
        """Should build graph from parsed entities."""
        # Arrange
        entities = [...]
        builder = GraphBuilder()

        # Act
        graph = builder.build_from_entities(entities)

        # Assert
        assert graph.number_of_nodes() == 10
        assert graph.number_of_edges() == 8

    def test_save_and_load_graph(self, tmp_path):
        """Should persist and load graph from disk."""
        # Test with temporary directory
        pass
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_graph_builder.py

# Run with coverage
pytest --cov=nervapack --cov-report=html

# Run specific test
pytest tests/test_graph_builder.py::TestGraphBuilder::test_save_and_load_graph
```

---

## Documentation Guidelines

### Docstring Style (Google Format)

```python
def query_graph(
    prompt: str,
    max_hops: int = 1,
    n_results: int = 3
) -> GraphRetrieval:
    """
    Query the knowledge graph with natural language.

    Performs vector search to find seed nodes, then expands
    via K-hop BFS to retrieve relevant subgraph context.

    Args:
        prompt: Natural language query string
        max_hops: Maximum traversal depth from seed nodes (default: 1)
        n_results: Number of seed nodes from vector search (default: 3)

    Returns:
        GraphRetrieval object containing:
            - subgraph: NetworkX graph of retrieved nodes
            - context: Markdown-formatted context
            - metadata: Traversal statistics

    Raises:
        ValueError: If prompt is empty or n_results < 1
        RuntimeError: If graph is not loaded

    Example:
        >>> result = query_graph("authentication flow", max_hops=2)
        >>> print(result.context)
        # NervaPack Context Retrieval
        ## File: auth/middleware.py
        ...

    Note:
        This function assumes the graph has been built via `ingest`.
        Run `nervapack status` to check graph state.
    """
```

### Updating Documentation Site

```bash
# Edit markdown files
vim docs/user-guide/commands/query.md

# Test locally
mkdocs serve
# Opens at http://localhost:8000

# Push changes (auto-deploys to Read the Docs)
git push
```

---

## Pull Request Process

1. **Ensure all tests pass** — Run `pytest` locally
2. **Update documentation** — Add/update relevant docs
3. **Update CHANGELOG.md** — Add entry under `[Unreleased]`
4. **Request review** — Tag maintainers if needed
5. **Address feedback** — Make requested changes
6. **Squash commits** (optional) — Keep history clean
7. **Merge** — Maintainer will merge when approved

---

## Release Process (Maintainers Only)

```bash
# 1. Update version in pyproject.toml
vim pyproject.toml  # version = "0.5.0"

# 2. Update CHANGELOG.md
vim docs/changelog.md  # Move [Unreleased] to [0.5.0]

# 3. Commit and tag
git add pyproject.toml docs/changelog.md
git commit -m "chore: Bump version to 0.5.0"
git tag v0.5.0
git push origin master --tags

# 4. Build and publish to PyPI
python -m build
python -m twine upload dist/*

# 5. Create GitHub release
# Go to https://github.com/ramdhavepreetam/NervaPack/releases
# Click "Draft a new release"
# Tag: v0.5.0, Title: "NervaPack 0.5.0", Copy CHANGELOG content
```

---

## Getting Help

- **Questions:** Open a [GitHub Discussion](https://github.com/ramdhavepreetam/NervaPack/discussions)
- **Bugs:** [File an issue](https://github.com/ramdhavepreetam/NervaPack/issues)
- **Chat:** (Future) Discord/Slack community

---

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to build something great together.

---

## Recognition

Contributors will be recognized in:
- `CONTRIBUTORS.md` (future)
- GitHub contributors page
- Release notes for significant contributions

---

**Thank you for contributing to NervaPack!** 🎉
