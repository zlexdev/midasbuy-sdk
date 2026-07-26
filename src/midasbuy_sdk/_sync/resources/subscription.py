from __future__ import annotations

from midasbuy_sdk._sync.resources._base import Resource
from midasbuy_sdk.models import SubscriptionStatusPublic


class Subscription(Resource):
    def get(self) -> SubscriptionStatusPublic:
        """Your key: status, expiry, per-minute budget and remaining quota."""
        data = self._t.request("GET", "/subscription")
        return SubscriptionStatusPublic.model_validate(data)
