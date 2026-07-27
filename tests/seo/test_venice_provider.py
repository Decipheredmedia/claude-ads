"""Tests for Venice AI provider (venice_provider.py).

All tests use the MockProvider — no live VENICE_API_KEY required in CI.
Tests for VeniceProvider use monkeypatching to simulate HTTP responses.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from venice_provider import (  # noqa: E402
    MockProvider,
    VeniceProvider,
    get_provider,
)


# ─── MockProvider ─────────────────────────────────────────────────────────────


def test_mock_provider_default_response():
    provider = MockProvider()
    result = provider.complete([{"role": "user", "content": "Hello"}])
    assert result == MockProvider.DEFAULT_RESPONSE


def test_mock_provider_custom_response():
    provider = MockProvider(responses={"Write a title": "My Custom Title"})
    result = provider.complete([{"role": "user", "content": "Write a title for my page"}])
    assert result == "My Custom Title"


def test_mock_provider_records_calls():
    provider = MockProvider()
    provider.complete([{"role": "user", "content": "Test"}], system="You are a bot")
    assert len(provider.calls) == 1
    assert provider.calls[0]["system"] == "You are a bot"


def test_mock_provider_no_match_returns_default():
    provider = MockProvider(responses={"specific": "answer"})
    result = provider.complete([{"role": "user", "content": "unrelated question"}])
    assert result == MockProvider.DEFAULT_RESPONSE


# ─── VeniceProvider config ────────────────────────────────────────────────────


def test_venice_provider_requires_api_key():
    provider = VeniceProvider(api_key="")
    with pytest.raises(RuntimeError, match="Venice API key not configured"):
        provider.complete([{"role": "user", "content": "Hello"}])


def test_venice_provider_reads_env_key(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "test-key-123")
    provider = VeniceProvider()
    assert provider.api_key == "test-key-123"


def test_venice_provider_explicit_key_wins_over_env(monkeypatch):
    monkeypatch.setenv("VENICE_API_KEY", "env-key")
    provider = VeniceProvider(api_key="explicit-key")
    assert provider.api_key == "explicit-key"


def test_venice_provider_default_model():
    provider = VeniceProvider(api_key="test")
    assert provider.model == "llama-3.3-70b"


def test_venice_provider_custom_model():
    provider = VeniceProvider(api_key="test", model="venice-uncensored")
    assert provider.model == "venice-uncensored"


# ─── VeniceProvider HTTP mocking ──────────────────────────────────────────────


def _make_mock_response(text: str) -> MagicMock:
    """Build a fake urllib response returning a Venice-shaped JSON body."""
    body = json.dumps({
        "choices": [{"message": {"content": text}}]
    }).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_venice_provider_successful_request(monkeypatch):
    mock_resp = _make_mock_response("Generated title: My Page")
    with patch("urllib.request.urlopen", return_value=mock_resp):
        provider = VeniceProvider(api_key="vn-test-key")
        result = provider.complete([{"role": "user", "content": "Generate title"}])
    assert result == "Generated title: My Page"


def test_venice_provider_retries_on_rate_limit(monkeypatch):
    """Provider should retry up to MAX_RETRIES times on 429."""
    call_count = 0

    def fake_urlopen(req, timeout):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise urllib.error.HTTPError(
                url="https://api.venice.ai/api/v1/chat/completions",
                code=429,
                msg="Too Many Requests",
                hdrs={},  # type: ignore[arg-type]
                fp=None,
            )
        return _make_mock_response("Final response after retry")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with patch("time.sleep"):  # Don't actually sleep in tests
            provider = VeniceProvider(api_key="vn-test-key")
            result = provider.complete([{"role": "user", "content": "Hello"}])

    assert result == "Final response after retry"
    assert call_count == 3


def test_venice_provider_raises_on_client_error(monkeypatch):
    """Non-retryable 4xx errors should raise RuntimeError immediately."""
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(
            url="https://api.venice.ai/api/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs={},  # type: ignore[arg-type]
            fp=None,
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        provider = VeniceProvider(api_key="invalid-key")
        with pytest.raises(RuntimeError, match="401"):
            provider.complete([{"role": "user", "content": "Hello"}])


def test_venice_provider_exhausted_retries_raises(monkeypatch):
    """After all retries are exhausted, RuntimeError should be raised."""
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(
            url="https://api.venice.ai/api/v1/chat/completions",
            code=429,
            msg="Rate Limited",
            hdrs={},  # type: ignore[arg-type]
            fp=None,
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with patch("time.sleep"):
            provider = VeniceProvider(api_key="vn-test")
            with pytest.raises(RuntimeError, match="unavailable after"):
                provider.complete([{"role": "user", "content": "Hi"}])


def test_venice_provider_with_system_prompt(monkeypatch):
    """System prompt should be prepended to messages."""
    captured_payload = {}

    def fake_urlopen(req, timeout):
        captured_payload["body"] = json.loads(req.data.decode())
        return _make_mock_response("response")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        provider = VeniceProvider(api_key="vn-test")
        provider.complete(
            [{"role": "user", "content": "Hello"}],
            system="You are an SEO expert.",
        )

    messages = captured_payload["body"]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are an SEO expert."
    assert messages[1]["role"] == "user"


# ─── get_provider factory ─────────────────────────────────────────────────────


def test_get_provider_returns_venice_provider_by_default(monkeypatch, tmp_path):
    """get_provider() with no config should return VeniceProvider (even with empty key)."""
    monkeypatch.setenv("VENICE_API_KEY", "vn-from-env")
    # Point config search to empty dir so no config file is found
    config_path = tmp_path / "nonexistent.json"
    provider = get_provider(str(config_path))
    assert isinstance(provider, VeniceProvider)
    assert provider.api_key == "vn-from-env"


def test_get_provider_returns_mock_from_config(tmp_path):
    """Config with provider='mock' should return MockProvider."""
    config = {"provider": "mock", "api_key": ""}
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps(config))
    provider = get_provider(str(cfg_file))
    assert isinstance(provider, MockProvider)
