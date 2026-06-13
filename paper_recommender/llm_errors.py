"""Shared helpers for reporting LLM provider failures without leaking secrets."""

from __future__ import annotations

import re
from urllib.error import HTTPError, URLError


class LLMProviderError(RuntimeError):
    """Raised when a configured LLM provider is required but unavailable."""


def format_llm_error(
    exc: Exception,
    *,
    base_url: str,
    model: str,
    api_key: str = "",
) -> str:
    provider = _safe_preview(str(base_url).rstrip("/"), api_key, max_chars=180)
    safe_model = _safe_preview(str(model), api_key, max_chars=120)
    message = f"LLM provider request failed for {provider} with model {safe_model}: "

    if isinstance(exc, HTTPError):
        detail = f"HTTP {exc.code}"
        if exc.reason:
            detail += f" {exc.reason}"
        response = _http_error_body(exc)
        preview = _safe_preview(response, api_key)
        if preview:
            detail += f"; response: {preview}"
        return message + detail

    if isinstance(exc, URLError):
        reason = _safe_preview(str(exc.reason), api_key)
        return message + f"{exc.__class__.__name__}: {reason}"

    detail = _safe_preview(str(exc), api_key)
    if detail:
        return message + f"{exc.__class__.__name__}: {detail}"
    return message + exc.__class__.__name__


def _http_error_body(exc: HTTPError) -> str:
    try:
        raw = exc.read()
    except Exception:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def _safe_preview(value: str, api_key: str = "", max_chars: int = 500) -> str:
    text = " ".join(str(value).split())
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED]", text)
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text
