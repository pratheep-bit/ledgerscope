"""
llm_client.py — Anthropic API client wrapper for Ledgerscope narration.

Thin wrapper so narrate.py doesn't import the SDK directly. If the SDK
isn't installed or no API key is set, this raises on construction, and
narrate.py's existing try/except in the caller falls back to the template
exactly as it already does for any other failure — no special-casing
needed in narrate.py itself.
"""
import os


class AnthropicNarrationClient:
    """Thin wrapper around Anthropic SDK for finding narration."""

    def __init__(self, model="claude-sonnet-4-6"):
        import anthropic  # raises ImportError if not installed — caller catches this
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system_prompt: str, user_content: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text
