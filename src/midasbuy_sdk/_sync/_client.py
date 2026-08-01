"""AsyncMidasbuyClient — the one hand-written client; sync is unasync'd from it."""

from __future__ import annotations

from midasbuy_sdk._sync._transport import Transport
from midasbuy_sdk._sync.resources.accounts import Accounts
from midasbuy_sdk._sync.resources.catalog import Catalog
from midasbuy_sdk._sync.resources.characters import Characters
from midasbuy_sdk._sync.resources.inventory import Inventory
from midasbuy_sdk._sync.resources.redeem import Redeem
from midasbuy_sdk._sync.resources.subscription import Subscription
from midasbuy_sdk._sync.resources.tasks import Tasks

DEFAULT_BASE_URL = "https://free.midasbuy-api.dev/v1"
"""The free contour. Point at your paid host by passing ``base_url=``.

Verified by request, not by belief: the previous default (``free.midas.chqcode.dev``)
had no DNS record at all, so a fresh install failed on name resolution before it ever
spoke to us. A host is confirmed the day it ships — ``/health`` answers 200 and an
unauthenticated ``/v1/*`` answers our own ``401 {"error_code": "unauthorized"}``. The
apex domain answers 200 with HTML (it serves the landing page) and is NOT the API.
"""


class MidasbuyClient:
    """Resource-grouped async client. Use as an async context manager to close
    the connection pool.

        async with AsyncMidasbuyClient("your-key") as client:
            result = await client.redeem.activate_and_wait(
                "CODE-1234", account_id="acc_...", game="pubgm"
            )
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self._t = Transport(api_key, base_url=base_url, timeout=timeout, max_retries=max_retries)
        self.accounts = Accounts(self._t)
        self.catalog = Catalog(self._t)
        self.inventory = Inventory(self._t)
        self.redeem = Redeem(self._t)
        self.tasks = Tasks(self._t)
        self.subscription = Subscription(self._t)
        self.characters = Characters(self._t)

    def __enter__(self) -> MidasbuyClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._t.close()
