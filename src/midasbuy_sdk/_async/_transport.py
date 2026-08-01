"""AsyncTransport — the single request core (auth, retry, idempotency, unwrap).

The sync twin (``_sync/_transport.py``) is generated from this file by
``scripts/codegen.py`` (unasync). Edit only this one.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from midasbuy_sdk.errors import (
    DailyCapReached,
    NetworkError,
    RateLimited,
    error_for,
)

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_BACKOFF_S = 30.0
# A 429 that carries this code is a daily cap, not a burst: no amount of waiting
# inside one call turns it into a success, so it is answered rather than retried.
_TERMINAL_CODES = frozenset({"activation_window_limit"})


def _error_code(response: httpx.Response) -> str | None:
    """The API's stable machine string, or ``None`` if the body is not ours."""
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    code = payload.get("error_code") or payload.get("code")
    return code if isinstance(code, str) else None


def _retry_after(response: httpx.Response, *, default: float = 1.0) -> float:
    raw = response.headers.get("retry-after")
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class AsyncTransport:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required — get a free one from the Telegram bot")
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "midasbuy-sdk",
        }
        self._http = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = dict(self._headers)
        if method == "POST":
            # One key per logical call, reused across retries: a timeout or a 429
            # can never turn one activation into two.
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        url = f"{self._base_url}{path}"
        last_network_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http.request(
                    method, url, json=json, params=clean, headers=headers
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                # A dropped connection is as transient as a 503, and until this was
                # caught here it escaped as a raw httpx error PAST the retry loop —
                # so the caller retried the call itself, got a fresh idempotency key
                # and could spend one code twice.
                last_network_error = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(min(2.0**attempt, _MAX_BACKOFF_S))
                    continue
                raise NetworkError(f"{method} {path} failed: {exc}") from exc
            retriable = response.status_code in _RETRY_STATUSES and (
                response.status_code != 429 or _error_code(response) not in _TERMINAL_CODES
            )
            if retriable and attempt < self._max_retries:
                await asyncio.sleep(self._backoff(attempt, response))
                continue
            return self._unwrap(response)
        raise NetworkError(  # pragma: no cover — the loop always returns or raises above
            f"{method} {path} failed after {self._max_retries} retries"
        ) from last_network_error

    def _backoff(self, attempt: int, response: httpx.Response) -> float:
        explicit = _retry_after(response, default=0.0)
        if explicit > 0:
            return min(explicit, _MAX_BACKOFF_S)
        return min(2.0**attempt, _MAX_BACKOFF_S)

    def _unwrap(self, response: httpx.Response) -> Any:
        request_id = response.headers.get("x-request-id")
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.is_success:
            return payload.get("data") if isinstance(payload, dict) else payload

        code: str | None = None
        message = response.reason_phrase
        reset_at: str | None = None
        if isinstance(payload, dict):
            code = payload.get("error_code") or payload.get("code")
            message = payload.get("message") or _detail_message(payload) or message
            request_id = payload.get("request_id") or request_id
            reset_at = payload.get("reset_at") or (payload.get("context") or {}).get("reset_at")
        exc = error_for(response.status_code, code, message, request_id)
        if isinstance(exc, RateLimited):
            exc.retry_after = _retry_after(response)
        if isinstance(exc, DailyCapReached):
            exc.reset_at = reset_at
        raise exc


def _detail_message(payload: dict[str, Any]) -> str | None:
    """FastAPI's 422 shape is ``{"detail": [{"loc", "msg", ...}]}``."""
    detail = payload.get("detail")
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            loc = ".".join(str(x) for x in first.get("loc", [])[1:])
            return f"{loc}: {first.get('msg', 'invalid')}" if loc else first.get("msg")
    if isinstance(detail, str):
        return detail
    return None
