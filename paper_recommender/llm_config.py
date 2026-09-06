"""Shared DeepSeek/OpenAI-compatible LLM environment configuration."""

from __future__ import annotations

import os


DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


def api_key() -> str:
    """Read the preferred DeepSeek key, with legacy compatibility for local runs."""
    return os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY", "")


def base_url() -> str:
    return (
        os.environ.get("DEEPSEEK_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or DEFAULT_BASE_URL
    )


def model() -> str:
    return os.environ.get("DEEPSEEK_MODEL") or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
