from __future__ import annotations

from midasbuy_sdk._async.resources._base import AsyncResource
from midasbuy_sdk.models import Character, CharacterList, RefreshAccepted


class AsyncCharacters(AsyncResource):
    """Paid-host only. On the free host these routes are not mounted and every
    call raises :class:`~midasbuy_sdk.errors.NotFound`."""

    async def list(self, *, account_id: str, game: str) -> CharacterList:
        data = await self._t.request(
            "GET", "/characters/list", params={"account_id": account_id, "game": game}
        )
        return CharacterList.model_validate(data)

    async def lookup(
        self, *, account_id: str, game: str, player_id: str, zone_id: str | None = None
    ) -> Character:
        data = await self._t.request(
            "GET",
            "/characters/lookup",
            params={
                "account_id": account_id,
                "game": game,
                "player_id": player_id,
                "zone_id": zone_id,
            },
        )
        return Character.model_validate(data)

    async def refresh(
        self, *, account_id: str, idempotency_key: str | None = None
    ) -> RefreshAccepted:
        data = await self._t.request(
            "POST",
            "/characters/refresh",
            json={"account_id": account_id},
            idempotency_key=idempotency_key,
        )
        return RefreshAccepted.model_validate(data)
