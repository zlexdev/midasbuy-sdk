from __future__ import annotations

from midasbuy_sdk._async.resources._base import AsyncResource
from midasbuy_sdk.models import SubscriptionStatusPublic


class AsyncSubscription(AsyncResource):
    async def get(self) -> SubscriptionStatusPublic:
        """Your key: status, expiry, per-minute budget and remaining quota."""
        data = await self._t.request("GET", "/subscription")
        return SubscriptionStatusPublic.model_validate(data)
