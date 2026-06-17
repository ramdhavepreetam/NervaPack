"""
Base LLM Provider abstraction for NervaPack.

Supports multiple LLM backends:
- MCP Delegation (Claude Code/Cursor - uses existing auth)
- Ollama (local, privacy-first)
- Claude API (cloud, direct)
- OpenAI API (cloud, direct)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024
    ) -> str:
        """
        Send a chat completion request.

        Args:
            messages: List of {role: str, content: str}
            system_prompt: Optional system message
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate

        Returns:
            Response text content

        Raises:
            LLMProviderError: If the request fails
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Check if provider is properly configured.

        Returns:
            True if provider can make requests, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the provider name for logging/display.

        Returns:
            Provider name (e.g., "ollama", "claude-api", "mcp-delegation")
        """
        pass

    @abstractmethod
    def estimate_cost(self, num_calls: int) -> Optional[float]:
        """
        Estimate cost for N API calls.

        Args:
            num_calls: Number of binding calls to estimate

        Returns:
            Estimated cost in USD, or None if free/unknown
        """
        pass

    def summarize_entity(
        self,
        entity_type: str,
        entity_name: str,
        content: str
    ) -> str:
        """
        Generate a summary for a code entity.

        This is shared logic across all providers.

        Args:
            entity_type: Type of entity (function, class, etc.)
            entity_name: Name of the entity
            content: Code content to summarize

        Returns:
            1-3 sentence summary
        """
        prompt = (
            f"Summarize the following {entity_type} named '{entity_name}':\n\n"
            f"```\n{content}\n```\n\n"
            f"Summary (1-3 sentences):"
        )
        messages = [{"role": "user", "content": prompt}]
        system = (
            "You are a concise code summarizer. "
            "Output only a 1-3 sentence summary of what the code does."
        )

        try:
            return self.chat(messages, system_prompt=system)
        except Exception as e:
            return f"Summary unavailable: {str(e)}"

    def bind_docs_to_ast(
        self,
        doc_chunk: str,
        ast_nodes: List[Dict[str, str]]
    ) -> List[str]:
        """
        Identify which AST nodes a documentation chunk explains.

        This is the critical LLM call during ingestion.

        Args:
            doc_chunk: Markdown documentation text
            ast_nodes: List of {node_id, summary, ...} dicts

        Returns:
            List of node_ids that the doc chunk explains
        """
        if not ast_nodes:
            return []

        # Build candidate list
        candidates = "\n".join([
            f"ID: {n['node_id']} | Summary: {n.get('summary', 'No summary')}"
            for n in ast_nodes
        ])

        prompt = (
            f"Given the following documentation chunk:\n\n{doc_chunk}\n\n"
            f"Which of the following code entities does it explain or implement? "
            f"Return a comma-separated list of IDs only, or 'None' if none match.\n\n"
            f"Candidates:\n{candidates}\n\n"
            f"Matched IDs:"
        )

        messages = [{"role": "user", "content": prompt}]
        system = (
            "You are an AI binding engine. "
            "Output ONLY a comma-separated list of IDs, or 'None'."
        )

        try:
            response = self.chat(messages, system_prompt=system).strip()

            # Parse response
            if response.lower() == "none" or not response:
                return []

            # Extract IDs
            ids = [i.strip() for i in response.split(",") if i.strip()]
            return ids

        except Exception:
            return []


class LLMProviderError(Exception):
    """Exception raised when LLM provider encounters an error."""
    pass
