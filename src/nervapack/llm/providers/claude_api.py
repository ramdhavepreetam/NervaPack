"""
Claude API provider for direct Anthropic API access.

Requires anthropic package and API key.
Install with: pip install "nervapack[claude]"
"""
from typing import List, Dict, Optional
from ..base import LLMProvider, LLMProviderError

try:
    from anthropic import Anthropic, APIError
except ImportError:
    raise ImportError(
        "Claude API provider requires anthropic package. "
        "Install with: pip install 'nervapack[claude]'"
    )


class ClaudeAPIProvider(LLMProvider):
    """
    Claude API provider using direct Anthropic API access.

    Requires ANTHROPIC_API_KEY environment variable or explicit api_key.
    Get your key at: https://console.anthropic.com/

    Cost estimate: ~$0.25 per 1000 binding calls (Haiku model)
    """

    # Pricing per million tokens (as of 2024)
    PRICING = {
        "claude-3-haiku-20240307": {
            "input": 0.25,
            "output": 1.25,
        },
        "claude-3-5-sonnet-20241022": {
            "input": 3.00,
            "output": 15.00,
        },
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-haiku-20240307"
    ):
        """
        Initialize Claude API provider.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Model to use (haiku, sonnet, etc.)
        """
        self.api_key = api_key
        self.model = model
        self.client = Anthropic(api_key=api_key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024
    ) -> str:
        """Send chat request to Claude API."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt if system_prompt else None,
                messages=messages
            )
            return response.content[0].text

        except APIError as e:
            raise LLMProviderError(
                f"Claude API request failed: {e}\n"
                f"Check your API key: https://console.anthropic.com/"
            )
        except Exception as e:
            raise LLMProviderError(f"Claude API error: {e}")

    def validate_config(self) -> bool:
        """Check if API key is properly configured."""
        if not self.api_key:
            return False

        # Check if key has correct format
        if not self.api_key.startswith("sk-ant-"):
            return False

        # Optionally, could make a test API call here
        # but that costs money, so just validate format
        return True

    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"claude-api:{self.model}"

    def estimate_cost(self, num_calls: int) -> Optional[float]:
        """
        Estimate cost for N binding calls.

        Assumes average of:
        - 500 tokens input per call (doc chunk + candidates)
        - 50 tokens output per call (just IDs)
        """
        pricing = self.PRICING.get(self.model, self.PRICING["claude-3-haiku-20240307"])

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
