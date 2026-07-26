from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

from midasbuy_sdk._async.resources._base import AsyncResource
from midasbuy_sdk._pagination import Page
from midasbuy_sdk.errors import WaitTimeout
from midasbuy_sdk.models import (
    ActivationAccepted,
    ActivationResult,
    ActivationState,
    BatchActivationAccepted,
    BatchStatusResult,
)

_NON_TERMINAL = frozenset({ActivationState.pending, ActivationState.running})


def _is_terminal(result: ActivationResult) -> bool:
    return result.status not in _NON_TERMINAL


class AsyncRedeem(AsyncResource):
    async def activate(
        self,
        code: str,
        *,
        account_id: str,
        game: str,
        player_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ActivationAccepted:
        """Activate one code. Returns 202 the moment the job is queued."""
        body: dict[str, Any] = {"code": code, "account_id": account_id, "game": game}
        if player_id is not None:
            body["player_id"] = player_id
        data = await self._t.request(
            "POST", "/redeem/activate", json=body, idempotency_key=idempotency_key
        )
        return ActivationAccepted.model_validate(data)

    async def activate_by_denomination(
        self,
        *,
        account_id: str,
        game: str,
        denomination_value: int,
        player_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ActivationAccepted:
        """Activate a random stocked code of one denomination — no code named."""
        body: dict[str, Any] = {
            "account_id": account_id,
            "game": game,
            "denomination_value": denomination_value,
        }
        if player_id is not None:
            body["player_id"] = player_id
        data = await self._t.request(
            "POST",
            "/redeem/activate-by-denomination",
            json=body,
            idempotency_key=idempotency_key,
        )
        return ActivationAccepted.model_validate(data)

    async def activate_batch_by_denomination(
        self,
        *,
        account_id: str,
        game: str,
        denomination_value: int,
        quantity: int,
        player_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> BatchActivationAccepted:
        """Activate up to ``quantity`` random stocked codes of one denomination.
        ``accepted`` may come back below ``quantity`` (trimmed to quota / stock)."""
        body: dict[str, Any] = {
            "account_id": account_id,
            "game": game,
            "denomination_value": denomination_value,
            "quantity": quantity,
        }
        if player_id is not None:
            body["player_id"] = player_id
        data = await self._t.request(
            "POST",
            "/redeem/activate-batch-by-denomination",
            json=body,
            idempotency_key=idempotency_key,
        )
        return BatchActivationAccepted.model_validate(data)

    async def preview(
        self, code: str, *, account_id: str, game: str, player_id: str | None = None
    ) -> ActivationAccepted:
        """Dry-run an activation — validate without spending the code."""
        body: dict[str, Any] = {"code": code, "account_id": account_id, "game": game}
        if player_id is not None:
            body["player_id"] = player_id
        data = await self._t.request("POST", "/redeem/preview", json=body)
        return ActivationAccepted.model_validate(data)

    async def get(self, activation_id: str) -> ActivationResult:
        data = await self._t.request("GET", "/redeem/get", params={"id": activation_id})
        return ActivationResult.model_validate(data)

    async def list(self, *, limit: int | None = None, offset: int = 0) -> Page[ActivationResult]:
        lim = self._limit(limit)
        data = await self._t.request("GET", "/redeem/list", params={"limit": lim, "offset": offset})
        return self._page(data, ActivationResult.model_validate, limit=lim, offset=offset)

    async def status_batch(self, activation_ids: Sequence[str]) -> BatchStatusResult:
        """Statuses for many ids in one call — cheaper than polling each."""
        data = await self._t.request(
            "POST", "/redeem/status-batch", json={"activation_ids": list(activation_ids)}
        )
        return BatchStatusResult.model_validate(data)

    async def iterate(self, *, limit: int | None = None) -> AsyncIterator[ActivationResult]:
        """Walk every activation, page by page."""
        offset = 0
        while True:
            page = await self.list(limit=limit, offset=offset)
            for item in page.items:
                yield item
            if not page.items or not page.has_more:
                return
            offset = page.next_offset

    async def wait_for(
        self, activation_id: str, *, poll: float = 2.0, timeout: float = 300.0
    ) -> ActivationResult:
        """Poll until the activation is terminal (success / failed / indeterminate),
        or raise :class:`~midasbuy_sdk.errors.WaitTimeout`."""
        deadline = time.monotonic() + timeout
        while True:
            result = await self.get(activation_id)
            if _is_terminal(result):
                return result
            if time.monotonic() >= deadline:
                raise WaitTimeout(
                    f"activation {activation_id} still {result.status.value} after {timeout}s"
                )
            await asyncio.sleep(poll)

    async def activate_and_wait(
        self,
        code: str,
        *,
        account_id: str,
        game: str,
        player_id: str | None = None,
        poll: float = 2.0,
        timeout: float = 300.0,
        idempotency_key: str | None = None,
    ) -> ActivationResult:
        """Activate then block until terminal — one call for the common case."""
        accepted = await self.activate(
            code,
            account_id=account_id,
            game=game,
            player_id=player_id,
            idempotency_key=idempotency_key,
        )
        return await self.wait_for(accepted.activation_id, poll=poll, timeout=timeout)
