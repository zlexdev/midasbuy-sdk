"""Behavioural tests — transport, errors, idempotency, pagination, both clients."""

from __future__ import annotations

import httpx
import pytest
import respx

from midasbuy_sdk import (
    AsyncMidasbuyClient,
    AuthFailed,
    DailyCapReached,
    MidasbuyClient,
    OutOfStock,
    RateLimited,
)

BASE = "https://api.test/v1"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _anap(_: float) -> None:
        return None

    monkeypatch.setattr("midasbuy_sdk._async._transport.asyncio.sleep", _anap)
    monkeypatch.setattr("midasbuy_sdk._sync._transport.time.sleep", lambda _: None)


def _client() -> MidasbuyClient:
    return MidasbuyClient("k", base_url=BASE)


@respx.mock
def test_unwraps_data_envelope() -> None:
    respx.get(f"{BASE}/subscription").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"status": "active", "type": "duration", "rate_limit_per_min": 120}},
        )
    )
    with _client() as c:
        sub = c.subscription.get()
    assert sub.status.value == "active"
    assert sub.rate_limit_per_min == 120


@respx.mock
def test_catalog_games_bare_list() -> None:
    respx.get(f"{BASE}/catalog/games").mock(
        return_value=httpx.Response(
            200, json={"data": [{"slug": "pubgm", "title": "PUBG Mobile", "item_id_prefix": "PM"}]}
        )
    )
    with _client() as c:
        games = c.catalog.games()
    assert games[0].slug == "pubgm"


@respx.mock
def test_pagination_page() -> None:
    respx.get(f"{BASE}/accounts/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "items": [{"account_id": "a1", "status": "connected"}],
                    "total": 3,
                    "next_cursor": "n",
                }
            },
        )
    )
    with _client() as c:
        page = c.accounts.list(limit=1, offset=0)
    assert len(page) == 1 and page.total == 3 and page.has_more is True
    assert page.next_offset == 1


@respx.mock
def test_post_carries_idempotency_key_and_reuses_it_on_retry() -> None:
    seen: list[str | None] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("idempotency-key"))
        if len(seen) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error_code": "x"})
        return httpx.Response(200, json={"data": {"activation_id": "act1", "status": "pending"}})

    respx.post(f"{BASE}/redeem/activate").mock(side_effect=_capture)
    with _client() as c:
        accepted = c.redeem.activate("CODE", account_id="acc", game="pubgm")
    assert accepted.activation_id == "act1"
    assert len(seen) == 2 and seen[0] is not None and seen[0] == seen[1]


@respx.mock
def test_caller_idempotency_key_is_sent() -> None:
    route = respx.post(f"{BASE}/redeem/activate").mock(
        return_value=httpx.Response(200, json={"data": {"activation_id": "a", "status": "pending"}})
    )
    with _client() as c:
        c.redeem.activate("C", account_id="acc", game="pubgm", idempotency_key="mine-1")
    assert route.calls.last.request.headers["idempotency-key"] == "mine-1"


@respx.mock
def test_activate_sends_game_field() -> None:
    """The 0.1.0 defect: activate() omitted `game` and 422'd every call."""
    route = respx.post(f"{BASE}/redeem/activate").mock(
        return_value=httpx.Response(200, json={"data": {"activation_id": "a", "status": "pending"}})
    )
    with _client() as c:
        c.redeem.activate("C", account_id="acc", game="pubgm")
    import json

    body = json.loads(route.calls.last.request.content)
    assert body["game"] == "pubgm" and body["code"] == "C" and body["account_id"] == "acc"


@respx.mock
def test_401_maps_to_auth_failed() -> None:
    respx.get(f"{BASE}/subscription").mock(
        return_value=httpx.Response(
            401,
            headers={"x-request-id": "rq1"},
            json={"error_code": "unauthorized", "message": "no"},
        )
    )
    with _client() as c, pytest.raises(AuthFailed) as ei:
        c.subscription.get()
    assert ei.value.request_id == "rq1" and ei.value.code == "unauthorized"


@respx.mock
def test_error_code_maps_before_status() -> None:
    respx.post(f"{BASE}/redeem/activate-by-denomination").mock(
        return_value=httpx.Response(409, json={"error_code": "code_out_of_stock", "message": "no"})
    )
    with _client() as c, pytest.raises(OutOfStock):
        c.redeem.activate_by_denomination(account_id="a", game="pubgm", denomination_value=60)


@respx.mock
def test_rate_limited_carries_retry_after() -> None:
    respx.get(f"{BASE}/subscription").mock(
        return_value=httpx.Response(
            429,
            headers={"retry-after": "7"},
            json={"error_code": "rate_limited", "message": "slow"},
        )
    )
    with MidasbuyClient("k", base_url=BASE, max_retries=0) as c, pytest.raises(RateLimited) as ei:
        c.subscription.get()
    assert ei.value.retry_after == 7.0


@respx.mock
def test_daily_cap_carries_reset_at() -> None:
    respx.post(f"{BASE}/redeem/activate").mock(
        return_value=httpx.Response(
            429,
            json={
                "error_code": "activation_window_limit",
                "message": "cap",
                "reset_at": "2026-07-27",
            },
        )
    )
    with (
        MidasbuyClient("k", base_url=BASE, max_retries=0) as c,
        pytest.raises(DailyCapReached) as ei,
    ):
        c.redeem.activate("C", account_id="a", game="pubgm")
    assert ei.value.reset_at == "2026-07-27"


@respx.mock
async def test_async_client_activate() -> None:
    respx.post(f"{BASE}/redeem/activate").mock(
        return_value=httpx.Response(
            200, json={"data": {"activation_id": "act9", "status": "pending"}}
        )
    )
    async with AsyncMidasbuyClient("k", base_url=BASE) as c:
        accepted = await c.redeem.activate("C", account_id="a", game="pubgm")
    assert accepted.activation_id == "act9"


@respx.mock
async def test_async_wait_for_polls_until_terminal() -> None:
    states = iter(["running", "running", "success"])
    respx.get(f"{BASE}/redeem/get").mock(
        side_effect=lambda _: httpx.Response(
            200, json={"data": {"activation_id": "a", "game": "pubgm", "status": next(states)}}
        )
    )
    async with AsyncMidasbuyClient("k", base_url=BASE) as c:
        result = await c.redeem.wait_for("a", poll=0)
    assert result.status.value == "success"
