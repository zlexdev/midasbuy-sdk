from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from midasbuy_sdk._pagination import Page
from midasbuy_sdk._sync.resources._base import Resource
from midasbuy_sdk.models import TaskAccepted, TaskResult, TaskSummary


class Tasks(Resource):
    def batch(
        self,
        *,
        account_id: str,
        items: Sequence[Mapping[str, Any]],
        webhook_url: str | None = None,
        idempotency_key: str | None = None,
    ) -> TaskAccepted:
        """Queue a batch of distinct codes. Each item: ``{"code", "game", "player_id"}``."""
        body: dict[str, Any] = {"account_id": account_id, "items": [dict(i) for i in items]}
        if webhook_url is not None:
            body["webhook_url"] = webhook_url
        data = self._t.request("POST", "/tasks/batch", json=body, idempotency_key=idempotency_key)
        return TaskAccepted.model_validate(data)

    def package(
        self,
        *,
        account_id: str,
        game: str,
        player_id: str,
        amount: int,
        webhook_url: str | None = None,
        idempotency_key: str | None = None,
    ) -> TaskAccepted:
        """Assemble ``amount`` of value for a player from stocked denominations."""
        body: dict[str, Any] = {
            "account_id": account_id,
            "game": game,
            "player_id": player_id,
            "amount": amount,
        }
        if webhook_url is not None:
            body["webhook_url"] = webhook_url
        data = self._t.request("POST", "/tasks/package", json=body, idempotency_key=idempotency_key)
        return TaskAccepted.model_validate(data)

    def get(self, task_id: str) -> TaskResult:
        data = self._t.request("GET", "/tasks/get", params={"id": task_id})
        return TaskResult.model_validate(data)

    def list(self, *, limit: int | None = None, offset: int = 0) -> Page[TaskSummary]:
        lim = self._limit(limit)
        data = self._t.request("GET", "/tasks/list", params={"limit": lim, "offset": offset})
        return self._page(data, TaskSummary.model_validate, limit=lim, offset=offset)
