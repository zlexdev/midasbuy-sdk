from __future__ import annotations

from midasbuy_sdk._async.resources._base import AsyncResource
from midasbuy_sdk._pagination import Page
from midasbuy_sdk.models import CatalogItem, Game


class AsyncCatalog(AsyncResource):
    async def games(self) -> list[Game]:
        """Games the catalog supports — ``Game.slug`` is the ``game`` argument
        used everywhere else."""
        data = await self._t.request("GET", "/catalog/games")
        return [Game.model_validate(row) for row in (data or [])]

    async def items(
        self, game: str, *, limit: int | None = None, offset: int = 0
    ) -> Page[CatalogItem]:
        lim = self._limit(limit)
        data = await self._t.request(
            "GET", "/catalog/items", params={"game": game, "limit": lim, "offset": offset}
        )
        return self._page(data, CatalogItem.model_validate, limit=lim, offset=offset)

    async def get_item(self, item_id: str) -> CatalogItem:
        data = await self._t.request("GET", "/catalog/get_item", params={"id": item_id})
        return CatalogItem.model_validate(data)
