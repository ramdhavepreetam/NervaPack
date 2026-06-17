"""
Ollama provider for local LLM inference.

Privacy-first option - all processing happens locally.
"""
import ollama
from typing import List, Dict, Optional
from ..base import LLMProvider, LLMProviderError


class OllamaProvider(LLMProvider):
    """
    Ollama provider for local LLM inference.

    Requires Ollama to be installed and running:
        brew install ollama
        ollama pull llama3
        ollama serve
    """

    def __init__(
        self,
        model: str = "llama3",
        base_url: Optional[str] = None
    ):
        """
        Initialize Ollama provider.

        Args:
            model: Model name (e.g., "llama3", "mistral", "codellama")
            base_url: Custom Ollama server URL (default: http://localhost:11434)
        """
        self.model = model
        self.base_url = base_url or "http://localhost:11434"

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024
    ) -> str:
        """Send chat request to Ollama."""
        # Prepend system message if provided
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt}
            ] + messages

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            )
            return response['message']['content']

        except Exception as e:
            raise LLMProviderError(
                f"Ollama request failed: {e}\n"
                f"Make sure Ollama is running: ollama serve"
            )

    def validate_config(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            # Try to list models - will fail if Ollama not running
            ollama.list()
            return True
        except Exception:
            return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"ollama:{self.model}"

    def estimate_cost(self, num_calls: int) -> Optional[float]:
        """Ollama is free (local processing)."""
        return None  # Free!
