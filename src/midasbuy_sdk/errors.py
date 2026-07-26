"""Typed errors — one per way a call can fail, carrying the facts you need.

Every error keeps ``code`` (the stable machine string the API sends as
``error_code``) and ``request_id``, so a support message can quote something the
operator can find. Mapping is by ``error_code`` first, then HTTP status.
"""

from __future__ import annotations


class MidasbuyError(Exception):
    """Base for everything this client raises."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.request_id = request_id

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f"code={self.code}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return " · ".join(parts)


class AuthFailed(MidasbuyError):
    """The key is missing, wrong, expired or revoked.

    The API answers a single neutral 401 for all of those on purpose, so this
    error cannot tell you which — get a fresh key if you believe it is live.
    """


class RateLimited(MidasbuyError):
    """Calling faster than the key's per-minute budget. Nothing was consumed.

    By the time this reaches you the client's own retries are spent. Wait
    ``retry_after`` seconds and continue — it is normal back-pressure, not a wall.
    """

    def __init__(self, message: str, *, retry_after: float = 1.0, **kw: object) -> None:
        super().__init__(message, **kw)  # type: ignore[arg-type]
        self.retry_after = retry_after


class DailyCapReached(MidasbuyError):
    """The key's daily activation stop-loss is spent; it resets at ``reset_at``."""

    def __init__(self, message: str, *, reset_at: str | None = None, **kw: object) -> None:
        super().__init__(message, **kw)  # type: ignore[arg-type]
        self.reset_at = reset_at


class OutOfStock(MidasbuyError):
    """No code of that denomination is in your inventory."""


class NotFound(MidasbuyError):
    """No such object — or it belongs to someone else, or (for a paid-only
    method against the free host) the route is not mounted. The API answers a
    single 404 for all three, so neither does this error distinguish them."""


class ValidationFailed(MidasbuyError):
    """The request was rejected before anything happened (bad field, 4xx)."""


class ServerError(MidasbuyError):
    """The service failed. Retried automatically; this means it kept failing."""


class WaitTimeout(MidasbuyError):
    """``wait_for`` gave up before the activation reached a terminal status.

    The activation is still running — poll ``redeem.get`` later. It is NOT safe
    to re-activate the code: that would spend it twice.
    """


# error_code (the API's stable machine string) → the narrowest class.
_BY_CODE: dict[str, type[MidasbuyError]] = {
    "code_out_of_stock": OutOfStock,
    "activation_window_limit": DailyCapReached,
    "rate_limited": RateLimited,
    "unauthorized": AuthFailed,
    "not_found": NotFound,
}


def error_for(status: int, code: str | None, message: str, request_id: str | None) -> MidasbuyError:
    """Map an API failure onto the narrowest error class available."""
    kw = {"code": code, "status": status, "request_id": request_id}
    cls = _BY_CODE.get(code or "")
    if cls is not None:
        return cls(message, **kw)  # type: ignore[arg-type]
    if status == 401:
        return AuthFailed(message, **kw)  # type: ignore[arg-type]
    if status == 404:
        return NotFound(message, **kw)  # type: ignore[arg-type]
    if status == 429:
        return RateLimited(message, **kw)  # type: ignore[arg-type]
    if status in (400, 409, 422):
        return ValidationFailed(message, **kw)  # type: ignore[arg-type]
    if status >= 500:
        return ServerError(message, **kw)  # type: ignore[arg-type]
    return MidasbuyError(message, **kw)  # type: ignore[arg-type]
