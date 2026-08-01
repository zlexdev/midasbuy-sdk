"""midasbuy-sdk — a typed client for the Midasbuy code-activation API.

``AsyncMidasbuyClient`` is the primary client: activation is an I/O-bound,
``202``-and-poll job people run in batches, so the fast path is async.

    import asyncio
    from midasbuy_sdk import AsyncMidasbuyClient

    async def main() -> None:
        async with AsyncMidasbuyClient("your-key") as client:
            games = await client.catalog.games()
            result = await client.redeem.activate_and_wait(
                "CODE-1234", account_id="acc_...", game=games[0].slug
            )
            print(result.status, result.granted_item)

    asyncio.run(main())

``MidasbuyClient`` is the same surface, blocking — for scripts and notebooks
where an event loop is more ceremony than the task deserves.

The free tier is a **beta**: its limits are temporary and will be re-set from
what the beta measures. Get a key from the Telegram bot — see the README.
"""

from __future__ import annotations

from midasbuy_sdk import models
from midasbuy_sdk._async._client import DEFAULT_BASE_URL, AsyncMidasbuyClient
from midasbuy_sdk._pagination import Page
from midasbuy_sdk._sync._client import MidasbuyClient
from midasbuy_sdk.errors import (
    AuthFailed,
    DailyCapReached,
    MidasbuyError,
    NetworkError,
    NotFound,
    OutOfStock,
    RateLimited,
    ServerError,
    ValidationFailed,
    WaitTimeout,
)

# The states a quickstart has to branch on live at the top level with the client:
# the first example must run exactly as copied, and `from midasbuy_sdk.models import
# AccountStatus` is one indirection more than a first screen may cost.
from midasbuy_sdk.models import AccountStatus, ActivationState

__version__ = "0.3.0"

__all__ = [
    "DEFAULT_BASE_URL",
    "AccountStatus",
    "ActivationState",
    "AsyncMidasbuyClient",
    "AuthFailed",
    "DailyCapReached",
    "MidasbuyClient",
    "MidasbuyError",
    "NetworkError",
    "NotFound",
    "OutOfStock",
    "Page",
    "RateLimited",
    "ServerError",
    "ValidationFailed",
    "WaitTimeout",
    "__version__",
    "models",
]
