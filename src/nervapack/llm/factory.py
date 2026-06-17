"""
LLM Provider Factory - intelligently selects the best provider.

Priority order:
1. MCP Delegation (if in Claude Code/Cursor context)
2. Explicit CLI flags (--llm, --model)
3. Environment variables (NERVAPACK_LLM_PROVIDER, *_API_KEY)
4. Config file (.nervapack/config.yaml)
5. Ollama (default fallback)
"""
import os
import sys
from typing import Optional
from pathlib import Path

from .base import LLMProvider
from .providers.ollama import OllamaProvider
from .providers.mcp_delegation import MCPDelegationProvider

# Optional cloud providers
try:
    from .providers.claude_api import ClaudeAPIProvider
except ImportError:
    ClaudeAPIProvider = None

try:
    from .providers.openai_api import OpenAIProvider
except ImportError:
    OpenAIProvider = None


def detect_mcp_context() -> bool:
    """
    Detect if NervaPack is running in an MCP context.

    Returns:
        True if running as MCP server (e.g., through Claude Code)
    """
    # Check for MCP-specific environment variables
    if os.getenv("MCP_SERVER_NAME") == "nervapack":
        return True

    # Check if stdin/stdout are pipes (typical for MCP stdio transport)
    if not sys.stdin.isatty() and not sys.stdout.isatty():
        # Additional check: MCP servers typically don't have $TERM set
        if not os.getenv("TERM"):
            return True

    return False


def get_llm_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    prefer_mcp: bool = True
) -> LLMProvider:
    """
    Get the appropriate LLM provider based on context and configuration.

    Priority order:
    1. MCP delegation (if in MCP context and prefer_mcp=True)
    2. Explicit parameters (provider, model, api_key)
    3. Environment variables
    4. Config file
    5. Ollama (default)

    Args:
        provider: Explicit provider name ("ollama", "claude", "openai", "mcp")
        model: Model name (provider-specific)
        api_key: API key for cloud providers
        prefer_mcp: If True, auto-detect and prefer MCP delegation

    Returns:
        Configured LLM provider

    Raises:
        ValueError: If provider is invalid or required config is missing
    """
    # Priority 1: MCP delegation (if in MCP context)
    if prefer_mcp and provider != "ollama":  # Allow explicit Ollama override
        if detect_mcp_context() or provider == "mcp":
            return MCPDelegationProvider()

    # Priority 2: Get provider from parameters or environment
    provider = provider or os.getenv("NERVAPACK_LLM_PROVIDER", "ollama")
    provider = provider.lower()

    # Priority 3: Dispatch to appropriate provider
    if provider == "ollama":
        model = model or os.getenv("OLLAMA_MODEL", "llama3")
        base_url = os.getenv("OLLAMA_BASE_URL")
        return OllamaProvider(model=model, base_url=base_url)

    elif provider in ["claude", "claude-api", "anthropic"]:
        if ClaudeAPIProvider is None:
            raise ValueError(
                "Claude API provider not available. "
                "Install with: pip install 'nervapack[claude]'"
            )
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        model = model or os.getenv("CLAUDE_MODEL", "claude-3-haiku-20240307")

        if not api_key:
            raise ValueError(
                "Claude API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter. Get your key at: "
                "https://console.anthropic.com/"
            )

        return ClaudeAPIProvider(api_key=api_key, model=model)

    elif provider in ["openai", "openai-api", "gpt"]:
        if OpenAIProvider is None:
            raise ValueError(
                "OpenAI API provider not available. "
                "Install with: pip install 'nervapack[openai]'"
            )
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        if not api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter. Get your key at: "
                "https://platform.openai.com/api-keys"
            )

        return OpenAIProvider(api_key=api_key, model=model)

    elif provider == "mcp":
        return MCPDelegationProvider()

    else:
        raise ValueError(
            f"Unknown provider: {provider}\n"
            f"Available providers: ollama, claude, openai, mcp"
        )


def load_config_file(project_root: str = ".") -> dict:
    """
    Load configuration from .nervapack/config.yaml.

    Args:
        project_root: Project root directory

    Returns:
        Config dict, or empty dict if file doesn't exist
    """
    config_path = Path(project_root) / ".nervapack" / "config.yaml"

    if not config_path.exists():
        return {}

    try:
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # PyYAML not installed - that's okay, just skip config file
        return {}
    except Exception:
        # Config file exists but can't be parsed - skip it
        return {}
