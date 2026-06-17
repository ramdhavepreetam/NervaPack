"""
LLMSummarizer - Backwards compatibility wrapper.

DEPRECATED: This module is maintained for backwards compatibility.
New code should use nervapack.llm.factory.get_llm_provider() instead.

This wrapper delegates to the new provider system, which supports:
- Ollama (local, privacy-first)
- Claude API (cloud)
- OpenAI API (cloud)
- MCP Delegation (Claude Code/Cursor integration)
"""
from typing import List, Dict, Optional
from nervapack.parser.ast_parser import ParsedEntity
from .factory import get_llm_provider
from .base import LLMProvider


class LLMSummarizer:
    """
    DEPRECATED: Use nervapack.llm.factory.get_llm_provider() instead.

    This class is maintained for backwards compatibility with existing code.
    It wraps the new provider system.
    """

    def __init__(
        self,
        model_name: str = "llama3",
        provider: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize LLM summarizer.

        Args:
            model_name: Model name (Ollama model or cloud model)
            provider: LLM provider ("ollama", "claude", "openai", "mcp")
            api_key: API key for cloud providers
        """
        self.model_name = model_name

        # Get appropriate provider
        if provider:
            self._provider = get_llm_provider(
                provider=provider,
                model=model_name,
                api_key=api_key
            )
        else:
            # Auto-detect best provider
            self._provider = get_llm_provider(
                model=model_name,
                api_key=api_key
            )

    def summarize_entity(self, entity: ParsedEntity) -> str:
        """
        Generate a quick summary for an AST node using configured LLM.

        DEPRECATED: This method is rarely used in production.
        Most code uses raw content instead of summaries.
        """
        return self._provider.summarize_entity(
            entity_type=entity.type,
            entity_name=entity.name,
            content=entity.content
        )

    def bind_docs_to_ast(
        self,
        doc_chunk: str,
        ast_nodes: List[Dict[str, str]]
    ) -> List[str]:
        """
        Takes a documentation chunk and a list of candidate AST nodes.
        Returns a list of node_ids that the documentation EXPLAINS or IMPLEMENTS.

        This is the primary LLM call during ingestion.
        """
        return self._provider.bind_docs_to_ast(doc_chunk, ast_nodes)

    def get_provider(self) -> LLMProvider:
        """
        Get the underlying provider instance.

        Returns:
            LLMProvider instance
        """
        return self._provider
