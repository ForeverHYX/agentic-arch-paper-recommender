"""Transient-failure retry helper for outbound LLM API calls."""

from __future__ import annotations

import time
from typing import Callable, TypeVar
from urllib.error import HTTPError, URLError


TRANSIENT_HTTP_CODES = frozenset({429, 500, 502, 503, 504})

T = TypeVar("T")


def is_transient_llm_error(error: BaseException) -> bool:
    """HTTP 429/5xx and network-level failures are worth retrying; auth or schema errors are not."""
    if isinstance(error, HTTPError):
        return error.code in TRANSIENT_HTTP_CODES
    return isinstance(error, (URLError, TimeoutError, ConnectionError, OSError))


def call_with_transient_retries(
    func: Callable[[], T],
    attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 20.0,
    sleeper: Callable[[float], None] | None = None,
    on_retry: Callable[[BaseException, float, int], None] | None = None,
) -> T:
    """Run func once, then retry only transient failures with capped exponential backoff."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    pause = sleeper or time.sleep
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as error:
            if attempt == attempts or not is_transient_llm_error(error):
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            if on_retry:
                on_retry(error, delay, attempt)
            pause(delay)
    raise RuntimeError("unreachable")
