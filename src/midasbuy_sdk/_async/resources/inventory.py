from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from midasbuy_sdk._async.resources._base import AsyncResource
from midasbuy_sdk._pagination import Page
from midasbuy_sdk.models import AddCodesResult, CodeStock, InventoryItem


class AsyncInventory(AsyncResource):
    async def add(self, items: Sequence[Mapping[str, Any]]) -> AddCodesResult:
        """Import codes into your stock. Each item:
        ``{"code", "game", "denomination_value", "currency"?}``."""
        data = await self._t.request(
            "POST", "/inventory/add", json={"items": [dict(i) for i in items]}
        )
        return AddCodesResult.model_validate(data)

    async def list(
        self,
        *,
        game: str | None = None,
        code_status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> Page[InventoryItem]:
        lim = self._limit(limit)
        data = await self._t.request(
            "GET",
            "/inventory/list",
            params={"game": game, "code_status": code_status, "limit": lim, "offset": offset},
        )
        return self._page(data, InventoryItem.model_validate, limit=lim, offset=offset)

    async def stock(self, *, limit: int | None = None, offset: int = 0) -> Page[CodeStock]:
        """Aggregated available counts per (game, denomination)."""
        lim = self._limit(limit)
        data = await self._t.request(
            "GET", "/inventory/stock", params={"limit": lim, "offset": offset}
        )
        return self._page(data, CodeStock.model_validate, limit=lim, offset=offset)
