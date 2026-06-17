"""
LLM Provider implementations for NervaPack.
"""
from .ollama import OllamaProvider
from .mcp_delegation import MCPDelegationProvider

__all__ = [
    "OllamaProvider",
    "MCPDelegationProvider",
]

# Optional cloud providers (only imported if dependencies available)
try:
    from .claude_api import ClaudeAPIProvider
    __all__.append("ClaudeAPIProvider")
except ImportError:
    ClaudeAPIProvider = None

try:
    from .openai_api import OpenAIProvider
    __all__.append("OpenAIProvider")
except ImportError:
    OpenAIProvider = None
