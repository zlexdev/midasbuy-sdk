from __future__ import annotations

from midasbuy_sdk._pagination import Page
from midasbuy_sdk._sync.resources._base import Resource
from midasbuy_sdk.models import Account, AccountConnectAccepted


class Accounts(Resource):
    def connect(
        self,
        *,
        country: str,
        email: str,
        password: str,
        env: str | None = None,
        label: str | None = None,
        offer_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> AccountConnectAccepted:
        """Link a Midas account by credentials. Returns 202 CONNECTING — poll
        ``list`` / ``get`` until the status is CONNECTED."""
        body = {"country": country, "email": email, "password": password}
        if env is not None:
            body["env"] = env
        if label is not None:
            body["label"] = label
        if offer_id is not None:
            body["offer_id"] = offer_id
        data = self._t.request(
            "POST", "/accounts/connect", json=body, idempotency_key=idempotency_key
        )
        return AccountConnectAccepted.model_validate(data)

    def list(self, *, limit: int | None = None, offset: int = 0) -> Page[Account]:
        lim = self._limit(limit)
        data = self._t.request("GET", "/accounts/list", params={"limit": lim, "offset": offset})
        return self._page(data, Account.model_validate, limit=lim, offset=offset)

    def get(self, account_id: str) -> Account:
        data = self._t.request("GET", "/accounts/get", params={"id": account_id})
        return Account.model_validate(data)
