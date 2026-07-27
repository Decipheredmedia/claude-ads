"""SEO skill configuration loader.

Loads Venice AI / SEO skill settings from (in priority order):
  1. Explicit ``config_path`` argument
  2. ``~/.claude/skills/seo/config.json``  (default)
  3. Environment variables (VENICE_API_KEY, VENICE_MODEL, etc.)

The merged config dict is returned; callers may override any key.

Config file schema (all keys optional)
---------------------------------------
{
  "api_key":     "vn-...",          // Venice AI API key
  "model":       "llama-3.3-70b",   // Venice model name
  "base_url":    "https://api.venice.ai/api/v1",
  "temperature": 0.3,
  "max_tokens":  512,
  "provider":    "venice"           // set to "mock" for tests without a key
}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# Default config file location (mirrored per-host by the installer)
_DEFAULT_CONFIG_PATHS = [
    Path.home() / ".claude" / "skills" / "seo" / "config.json",
    Path.home() / ".codex" / "skills" / "seo" / "config.json",
    Path.home() / ".config" / "goose" / "skills" / "seo" / "config.json",
]

_DEFAULTS: dict = {
    "api_key": "",
    "model": "llama-3.3-70b",
    "base_url": "https://api.venice.ai/api/v1",
    "temperature": 0.3,
    "max_tokens": 512,
    "provider": "venice",
}


def load_config(config_path: Optional[str] = None) -> dict:
    """Load SEO skill configuration.

    Args:
        config_path: Explicit path to a JSON config file.  If ``None``,
                     the default search paths are tried in order.

    Returns:
        Dict with merged config (defaults → file → env overrides).
    """
    config: dict = dict(_DEFAULTS)

    # 1. Try config file
    resolved_path: Optional[Path] = None
    if config_path:
        resolved_path = Path(config_path).expanduser()
    else:
        for candidate in _DEFAULT_CONFIG_PATHS:
            if candidate.exists():
                resolved_path = candidate
                break

    if resolved_path and resolved_path.exists():
        try:
            file_data = json.loads(resolved_path.read_text(encoding="utf-8"))
            config.update({k: v for k, v in file_data.items() if k in _DEFAULTS})
        except (json.JSONDecodeError, OSError):
            pass  # Malformed config: fall through to env var only

    # 2. Environment variable overrides (always win over file)
    _env_overrides = {
        "VENICE_API_KEY": "api_key",
        "VENICE_MODEL": "model",
        "VENICE_BASE_URL": "base_url",
        "VENICE_TEMPERATURE": "temperature",
        "VENICE_MAX_TOKENS": "max_tokens",
    }
    for env_var, key in _env_overrides.items():
        val = os.environ.get(env_var)
        if val:
            config[key] = val

    # Coerce numeric types after env override (env vars are always strings)
    try:
        config["temperature"] = float(config["temperature"])
    except (TypeError, ValueError):
        config["temperature"] = _DEFAULTS["temperature"]
    try:
        config["max_tokens"] = int(config["max_tokens"])
    except (TypeError, ValueError):
        config["max_tokens"] = _DEFAULTS["max_tokens"]

    return config


def write_config(api_key: str, config_path: Optional[str] = None, **kwargs) -> Path:
    """Write a Venice AI config file to disk.

    Creates parent directories if needed.  Existing config is merged
    (new values win).

    Args:
        api_key:     Venice AI API key.
        config_path: Path to write.  Defaults to ``~/.claude/skills/seo/config.json``.
        **kwargs:    Additional config keys (model, temperature, max_tokens, etc.).

    Returns:
        The ``Path`` that was written.
    """
    target = Path(config_path).expanduser() if config_path else _DEFAULT_CONFIG_PATHS[0]
    target.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config to merge
    existing: dict = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    merged = {**_DEFAULTS, **existing, "api_key": api_key, **kwargs}
    target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return target
