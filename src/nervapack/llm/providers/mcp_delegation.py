"""
MCP Delegation Provider - delegates LLM calls back to the MCP client.

When NervaPack is used through Claude Code/Cursor, this provider
returns structured prompts that the MCP client answers using its
own authenticated LLM session.

This means:
- No separate API keys needed
- No additional costs beyond Claude subscription
- Uses the same LLM that's already running
"""
from typing import List, Dict, Optional
from ..base import LLMProvider, LLMProviderError


class MCPDelegationProvider(LLMProvider):
    """
    MCP Delegation provider - returns prompts for MCP client to answer.

    This is a "virtual" provider that doesn't make actual LLM calls.
    Instead, it formats the request as a structured prompt that gets
    returned to the MCP client (Claude Code), which then uses its own
    LLM to generate the answer.

    This is implemented through special MCP tools that handle the
    request/response cycle.
    """

    def __init__(self):
        """Initialize MCP delegation provider."""
        self._pending_requests = []
        self._is_mcp_context = self._detect_mcp_context()

    def _detect_mcp_context(self) -> bool:
        """
        Detect if we're running in an MCP context.

        MCP servers run with stdio transport, so we can check
        if stdin/stdout are pipes rather than terminals.
        """
        import sys
        import os

        # Check for MCP-specific environment variables
        if os.getenv("MCP_SERVER_NAME") == "nervapack":
            return True

        # Check if stdin/stdout are pipes (typical for MCP stdio transport)
        if not sys.stdin.isatty() and not sys.stdout.isatty():
            return True

        return False

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024
    ) -> str:
        """
        Delegate chat request to MCP client.

        In MCP delegation mode, this returns a special marker that
        the calling code can detect and handle appropriately.

        The actual implementation uses MCP tools to create a
        request/response cycle.
        """
        # This is a placeholder - actual delegation happens through
        # MCP tools (prepare_binding, save_bindings) that are called
        # by the CLI/ingestion code.

        raise LLMProviderError(
            "Direct chat() not supported in MCP delegation mode. "
            "Use bind_docs_to_ast_delegated() instead."
        )

    def bind_docs_to_ast_delegated(
        self,
        doc_chunk: str,
        ast_nodes: List[Dict[str, str]]
    ) -> Dict[str, any]:
        """
        Prepare binding request for MCP client to process.

        Instead of making an LLM call, this returns a structured
        request that the MCP client can process.

        Returns:
            Dict with {
                "type": "binding_request",
                "doc_chunk": str,
                "candidates": List[Dict],
                "prompt": str  # Formatted prompt for Claude to answer
            }
        """
        if not ast_nodes:
            return {"type": "binding_response", "matched_ids": []}

        # Build candidate list
        candidates = [
            {
                "id": n["node_id"],
                "summary": n.get("summary", "No summary"),
                "type": n.get("type", "unknown"),
                "name": n.get("name", ""),
            }
            for n in ast_nodes
        ]

        # Format prompt for Claude
        candidates_text = "\n".join([
            f"ID: {c['id']}\n"
            f"  Type: {c['type']}\n"
            f"  Name: {c['name']}\n"
            f"  Summary: {c['summary']}\n"
            for c in candidates
        ])

        prompt = (
            f"I'm analyzing a codebase and need to create semantic links "
            f"between documentation and code.\n\n"
            f"**Documentation chunk:**\n{doc_chunk}\n\n"
            f"**Code entities (candidates):**\n{candidates_text}\n\n"
            f"**Question:** Which code entity IDs does this documentation "
            f"explain or implement? Return only a comma-separated list of IDs, "
            f"or 'None' if no clear matches.\n\n"
            f"**Your answer (IDs only):**"
        )

        return {
            "type": "binding_request",
            "doc_chunk": doc_chunk,
            "candidates": candidates,
            "prompt": prompt,
        }

    def validate_config(self) -> bool:
        """Check if we're in MCP context."""
        return self._is_mcp_context

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "mcp-delegation"

    def estimate_cost(self, num_calls: int) -> Optional[float]:
        """
        MCP delegation uses existing Claude subscription.

        Cost is included in user's Claude Code subscription,
        not billed separately.
        """
        return None  # Included in subscription
