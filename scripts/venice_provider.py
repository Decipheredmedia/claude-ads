"""Venice AI provider — OpenAI-compatible chat completions client.

Provides a provider-abstracted LLM interface with Venice AI as the default
backend.  All generative reasoning steps in the SEO skill (meta description
generation, alt-text generation, schema markup generation, keyword analysis,
content rewriting) route through this module.

Configuration priority (highest → lowest):
  1. Explicit keyword arguments to ``VeniceProvider.__init__``
  2. Environment variable ``VENICE_API_KEY`` (for the key)
  3. Config file at ``~/.claude/skills/seo/config.json``

Usage
-----
>>> from venice_provider import get_provider
>>> provider = get_provider()            # uses env / config file
>>> result = provider.complete([{"role": "user", "content": "Hello"}])
>>> print(result)                        # plain text response

CLI (for smoke-testing)
-----------------------
$ python venice_provider.py --prompt "Generate a meta description for: My bakery"
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

# ─── Constants ────────────────────────────────────────────────────────────────

VENICE_BASE_URL = "https://api.venice.ai/api/v1"
DEFAULT_MODEL = "llama-3.3-70b"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 512
MAX_RETRIES = 4
RETRY_BASE_DELAY = 1.0   # seconds (exponential backoff: 1, 2, 4, 8)

# ─── Provider interface ───────────────────────────────────────────────────────


class LLMProvider:
    """Abstract provider interface — subclass to add a new backend."""

    def complete(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        raise NotImplementedError


# ─── Venice AI provider ───────────────────────────────────────────────────────


class VeniceProvider(LLMProvider):
    """Venice AI chat completions client (OpenAI-compatible API).

    Args:
        api_key:     Venice API key.  Falls back to VENICE_API_KEY env var.
        model:       Model name.  Defaults to ``llama-3.3-70b``.
        base_url:    API base URL.  Defaults to ``https://api.venice.ai/api/v1``.
        temperature: Sampling temperature (0–2).  Defaults to 0.3.
        max_tokens:  Maximum tokens to generate.  Defaults to 512.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        base_url: str = VENICE_BASE_URL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.api_key = api_key or os.environ.get("VENICE_API_KEY", "")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Send a chat completion request and return the assistant's text.

        Args:
            messages:    List of ``{"role": ..., "content": ...}`` dicts.
            system:      Optional system prompt prepended to the message list.
            max_tokens:  Per-call override for max_tokens.
            temperature: Per-call override for temperature.

        Returns:
            The assistant's reply as a plain string.

        Raises:
            RuntimeError: If the API key is missing or all retries are exhausted.
        """
        if not self.api_key:
            raise RuntimeError(
                "Venice API key not configured.  Set VENICE_API_KEY environment "
                "variable or add 'api_key' to ~/.claude/skills/seo/config.json."
            )

        all_messages: list[dict] = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": all_messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

        return self._post_with_retry(payload)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _post_with_retry(self, payload: dict) -> str:
        """POST to Venice API with exponential back-off on transient errors."""
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    self._endpoint(),
                    data=body,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return self._extract_text(data)

            except urllib.error.HTTPError as exc:
                status = exc.code
                if status == 429:
                    # Rate limited — always retry with back-off
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    _warn(f"Venice rate limit (429), retry {attempt + 1}/{MAX_RETRIES} in {delay:.1f}s…")
                    time.sleep(delay)
                    last_error = exc
                elif status in (500, 502, 503, 504):
                    # Transient server error
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    _warn(f"Venice server error ({status}), retry {attempt + 1}/{MAX_RETRIES} in {delay:.1f}s…")
                    time.sleep(delay)
                    last_error = exc
                else:
                    # Client error (4xx other than 429) — don't retry
                    raise RuntimeError(
                        f"Venice API error {status}: {_safe_read(exc)}"
                    ) from exc

            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                _warn(f"Venice connection error, retry {attempt + 1}/{MAX_RETRIES} in {delay:.1f}s…")
                time.sleep(delay)
                last_error = exc

        raise RuntimeError(
            f"Venice API unavailable after {MAX_RETRIES} retries: {last_error}"
        ) from last_error

    @staticmethod
    def _extract_text(response: dict) -> str:
        """Extract plain text from an OpenAI-compatible response dict."""
        try:
            return response["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected Venice response shape: {json.dumps(response)[:200]}"
            ) from exc


# ─── Mock provider (for tests / CI without a real key) ────────────────────────


class MockProvider(LLMProvider):
    """Deterministic mock — returns canned responses keyed by prompt prefix.

    Used in tests to avoid requiring a live VENICE_API_KEY in CI.
    """

    DEFAULT_RESPONSE = "Mock LLM response."

    def __init__(self, responses: Optional[dict[str, str]] = None) -> None:
        self.responses = responses or {}
        self.calls: list[dict] = []

    def complete(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        self.calls.append({"messages": messages, "system": system})
        last_content = messages[-1]["content"] if messages else ""
        for prefix, reply in self.responses.items():
            if last_content.startswith(prefix):
                return reply
        return self.DEFAULT_RESPONSE


# ─── Config-aware factory ─────────────────────────────────────────────────────


def get_provider(config_path: Optional[str] = None) -> LLMProvider:
    """Return a configured ``VeniceProvider`` (or mock if requested via config).

    Loads configuration from:
    1. ``config_path`` (explicit override)
    2. ``~/.claude/skills/seo/config.json`` (default location)
    3. Environment variables only (if no config file found)

    Returns:
        A ``VeniceProvider`` instance ready for use.
    """
    from seo_config import load_config  # local import to avoid circular deps
    cfg = load_config(config_path)

    if cfg.get("provider") == "mock":
        return MockProvider(cfg.get("mock_responses"))

    return VeniceProvider(
        api_key=cfg.get("api_key") or os.environ.get("VENICE_API_KEY", ""),
        model=cfg.get("model", DEFAULT_MODEL),
        base_url=cfg.get("base_url", VENICE_BASE_URL),
        temperature=float(cfg.get("temperature", DEFAULT_TEMPERATURE)),
        max_tokens=int(cfg.get("max_tokens", DEFAULT_MAX_TOKENS)),
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _warn(msg: str) -> None:
    print(f"[venice] {msg}", file=sys.stderr)


def _safe_read(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")[:200]
    except Exception:
        return str(exc)


# ─── CLI ──────────────────────────────────────────────────────────────────────


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Smoke-test the Venice AI provider."
    )
    parser.add_argument("--prompt", required=True, help="Prompt to send")
    parser.add_argument("--system", default=None, help="Optional system prompt")
    parser.add_argument("--config", default=None, help="Path to config JSON")
    args = parser.parse_args()

    provider = get_provider(args.config)
    result = provider.complete(
        [{"role": "user", "content": args.prompt}],
        system=args.system,
    )
    print(result)


if __name__ == "__main__":
    _cli()
