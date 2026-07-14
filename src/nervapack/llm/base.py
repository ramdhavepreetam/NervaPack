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

        Pre-filters candidates with keyword overlap so the LLM prompt
        stays small enough for local models to handle reliably.
        """
        if not ast_nodes:
            return []

        # Pre-filter: score each node by keyword overlap with the doc chunk,
        # keep the top 12. This prevents 500+ node prompts that cause local
        # models to hallucinate or time out.
        doc_words = set(self._tokenise(doc_chunk))
        if doc_words:
            scored = []
            for n in ast_nodes:
                node_text = f"{n['node_id']} {n.get('summary', '')}"
                node_words = set(self._tokenise(node_text))
                overlap = len(doc_words & node_words)
                scored.append((overlap, n))
            scored.sort(key=lambda x: -x[0])
            # Only keep nodes with at least 1 word overlap, max 12
            candidates_nodes = [n for score, n in scored if score > 0][:12]
        else:
            candidates_nodes = ast_nodes[:12]

        if not candidates_nodes:
            return []

        candidates = "\n".join([
            f"ID: {n['node_id']} | Summary: {n.get('summary', 'No summary')}"
            for n in candidates_nodes
        ])

        prompt = (
            f"Documentation chunk:\n{doc_chunk[:800]}\n\n"
            f"Which of these code entities does the documentation explain? "
            f"Reply with ONLY the matching IDs as a comma-separated list, or 'None'.\n\n"
            f"Candidates:\n{candidates}\n\n"
            f"Matched IDs:"
        )

        messages = [{"role": "user", "content": prompt}]
        system = (
            "You are a code documentation linker. "
            "Output ONLY a comma-separated list of IDs from the candidates, or the word None. "
            "Do not explain. Do not add text."
        )

        try:
            response = self.chat(messages, system_prompt=system, max_tokens=256).strip()

            if not response or response.lower().startswith("none"):
                return []

            # Extract only IDs that were actually in our candidate list
            valid_ids = {n["node_id"] for n in candidates_nodes}
            ids = [i.strip() for i in response.split(",") if i.strip() in valid_ids]
            return ids

        except Exception:
            return []

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        """Split text into lowercase words ≥4 chars, stripping punctuation."""
        import re
        return [w for w in re.findall(r"[a-zA-Z_]{4,}", text.lower())]


class LLMProviderError(Exception):
    """Exception raised when LLM provider encounters an error."""
    pass
