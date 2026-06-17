"""
OpenAI API provider for direct OpenAI API access.

Requires openai package and API key.
Install with: pip install "nervapack[openai]"
"""
from typing import List, Dict, Optional
from ..base import LLMProvider, LLMProviderError

try:
    from openai import OpenAI, APIError
except ImportError:
    raise ImportError(
        "OpenAI API provider requires openai package. "
        "Install with: pip install 'nervapack[openai]'"
    )


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider using direct OpenAI API access.

    Requires OPENAI_API_KEY environment variable or explicit api_key.
    Get your key at: https://platform.openai.com/api-keys

    Cost estimate: ~$0.15 per 1000 binding calls (GPT-4o-mini model)
    """

    # Pricing per million tokens (as of 2024)
    PRICING = {
        "gpt-4o-mini": {
            "input": 0.150,
            "output": 0.600,
        },
        "gpt-4o": {
            "input": 2.50,
            "output": 10.00,
        },
        "gpt-3.5-turbo": {
            "input": 0.50,
            "output": 1.50,
        },
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        """
        Initialize OpenAI API provider.

        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model to use (gpt-4o-mini, gpt-4o, etc.)
        """
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024
    ) -> str:
        """Send chat request to OpenAI API."""
        # Prepend system message if provided
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt}
            ] + messages

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content

        except APIError as e:
            raise LLMProviderError(
                f"OpenAI API request failed: {e}\n"
                f"Check your API key: https://platform.openai.com/api-keys"
            )
        except Exception as e:
            raise LLMProviderError(f"OpenAI API error: {e}")

    def validate_config(self) -> bool:
        """Check if API key is properly configured."""
        if not self.api_key:
            return False

        # Check if key has correct format
        if not self.api_key.startswith("sk-"):
            return False

        return True

    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"openai-api:{self.model}"

    def estimate_cost(self, num_calls: int) -> Optional[float]:
        """
        Estimate cost for N binding calls.

        Assumes average of:
        - 500 tokens input per call (doc chunk + candidates)
        - 50 tokens output per call (just IDs)
        """
        pricing = self.PRICING.get(self.model, self.PRICING["gpt-4o-mini"])

        # Tokens per call (rough estimate)
        input_tokens_per_call = 500
        output_tokens_per_call = 50

        # Cost per million tokens
        input_cost_per_m = pricing["input"]
        output_cost_per_m = pricing["output"]

        # Calculate total cost
        total_input_tokens = num_calls * input_tokens_per_call
        total_output_tokens = num_calls * output_tokens_per_call

        cost = (
            (total_input_tokens / 1_000_000) * input_cost_per_m +
            (total_output_tokens / 1_000_000) * output_cost_per_m
        )

        return round(cost, 4)
