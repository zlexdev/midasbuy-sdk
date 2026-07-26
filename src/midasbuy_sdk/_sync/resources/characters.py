from __future__ import annotations

from midasbuy_sdk._sync.resources._base import Resource
from midasbuy_sdk.models import Character, CharacterList, RefreshAccepted


class Characters(Resource):
    """Paid-host only. On the free host these routes are not mounted and every
    call raises :class:`~midasbuy_sdk.errors.NotFound`."""

    def list(self, *, account_id: str, game: str) -> CharacterList:
        data = self._t.request(
            "GET", "/characters/list", params={"account_id": account_id, "game": game}
        )
        return CharacterList.model_validate(data)

    def lookup(
        self, *, account_id: str, game: str, player_id: str, zone_id: str | None = None
    ) -> Character:
        data = self._t.request(
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

    def refresh(self, *, account_id: str, idempotency_key: str | None = None) -> RefreshAccepted:
        data = self._t.request(
            "POST",
            "/characters/refresh",
            json={"account_id": account_id},
            idempotency_key=idempotency_key,
        )
        return RefreshAccepted.model_validate(data)
