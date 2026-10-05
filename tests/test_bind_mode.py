"""Doc-binding mode selection for ingest/sync.

The regression: ingest auto-detected a running Ollama and pushed every
markdown chunk through whatever model was installed first, turning a ~20s
ingest into hours. An LLM must only be used when explicitly asked for.
"""

import pytest
import typer

from nervapack.cli import _resolve_bind_mode


@pytest.fixture(autouse=True)
def _no_env_mode(monkeypatch):
    monkeypatch.delenv("NERVAPACK_INGEST_MODE", raising=False)


def test_default_is_fast_even_with_ollama_running():
    assert _resolve_bind_mode(None, None) == "fast"


def test_explicit_modes():
    assert _resolve_bind_mode("fast", None) == "fast"
    assert _resolve_bind_mode("LLM", None) == "llm"


def test_passing_a_provider_implies_llm():
    assert _resolve_bind_mode(None, "claude") == "llm"


def test_explicit_fast_wins_over_provider():
    assert _resolve_bind_mode("fast", "ollama") == "fast"


def test_env_var_sets_default(monkeypatch):
    monkeypatch.setenv("NERVAPACK_INGEST_MODE", "llm")
    assert _resolve_bind_mode(None, None) == "llm"
    assert _resolve_bind_mode("fast", None) == "fast"


def test_unknown_env_value_falls_back_to_fast(monkeypatch):
    monkeypatch.setenv("NERVAPACK_INGEST_MODE", "turbo")
    assert _resolve_bind_mode(None, None) == "fast"


def test_no_bind_is_fast_alias():
    assert _resolve_bind_mode(None, "ollama", no_bind=True) == "fast"
    with pytest.raises(typer.BadParameter):
        _resolve_bind_mode("llm", None, no_bind=True)


def test_invalid_mode_rejected():
    with pytest.raises(typer.BadParameter):
        _resolve_bind_mode("turbo", None)
