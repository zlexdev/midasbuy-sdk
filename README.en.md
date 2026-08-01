<p align="center">
  <strong>midasbuy-sdk</strong>
</p>

<p align="center">
  <strong>Typed async client for the Midasbuy code-activation API.</strong>
</p>

<p align="center">
  <a href="https://github.com/zlexdev/midasbuy-sdk/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/zlexdev/midasbuy-sdk/ci.yml?branch=master&style=for-the-badge" alt="CI"></a>
  <a href="https://pypi.org/project/midasbuy-sdk/"><img src="https://img.shields.io/pypi/v/midasbuy-sdk?style=for-the-badge" alt="PyPI"></a>
  <a href="https://pypi.org/project/midasbuy-sdk/"><img src="https://img.shields.io/pypi/pyversions/midasbuy-sdk?style=for-the-badge" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"></a>
</p>

**midasbuy-sdk** is the client for a hosted code-activation and in-game purchasing API.
The service itself is closed; this client is open, and the service has a **free tier** —
a key is issued with no signup and no payment.

[Русская версия](README.md) · [Client design](DESIGN.md) · [For AI agents](docs/for_ai/index.md) · [OpenAPI](openapi.public.json) · [Issues](https://github.com/zlexdev/midasbuy-sdk/issues)

## Install

```bash
pip install midasbuy-sdk
```

## Getting a key

Send `/free` to the Telegram bot `@midasbuy_api_bot`.

Attach a link to your seller profile on a marketplace where your reviews and sales are
visible, plus proof the profile is yours — a photo straight into the chat or a link.
That is the only barrier, and it exists so free keys do not end up handed out in bulk to
throwaway accounts. One key per person; a repeat application returns the same one.

The free tier is a **beta** — limits are temporary and will be revisited after it.

## First call

With no `base_url` the client talks to the free contour —
`https://free.midasbuy-api.dev/v1`. Point it at a paid host explicitly:
`AsyncMidasbuyClient("key", base_url="https://api.your-domain/v1")`.

**An account and a player are different things, and this is the one thing to understand
about activation.**

- `account_id` — the Midas account the activation runs **from**. Connected once, then it
  lives on the server.
- `player_id` — the player the goods land **on**. It can be someone else's: your account
  activates a code onto any in-game ID.

Without `player_id` the goods go to the account itself — the default for games with no
characters.

```python
import asyncio

from midasbuy_sdk import AccountStatus, AsyncMidasbuyClient, Country, GameSlug


async def main() -> None:
    async with AsyncMidasbuyClient("your-key") as client:
        # 1. Connect a Midas account — activations run FROM it. The response comes
        #    back as CONNECTING: the login happens on the server, so wait for
        #    CONNECTED before activating anything.
        account = await client.accounts.connect(
            country=Country.RU, email="you@example.com", password="..."
        )
        while (state := (await client.accounts.get(account.account_id)).status) in (
            AccountStatus.connecting,
            AccountStatus.running,
        ):
            await asyncio.sleep(2)
        if state is not AccountStatus.connected:
            raise RuntimeError(f"account did not connect: {state}")

        # 2. Activate a code ONTO A PLAYER and wait for the outcome — one call.
        result = await client.redeem.activate_and_wait(
            "CODE-1234",
            account_id=account.account_id,   # from which account
            game=GameSlug.PUBGM,
            player_id="5544128792",          # to which player
        )
        print(result.status, result.granted_item)


asyncio.run(main())
```

## Constants, not literals

Everything the server declares as a fixed set ships in the package — never retype the
strings:

```python
from midasbuy_sdk import (
    AccountEnv, AccountStatus, ActivationState, CodeStatus,
    Country, GameSlug, SubscriptionStatus, SubscriptionType, TaskState, TaskType,
)

if result.status is ActivationState.success: ...
```

`GameSlug` is the exception, and the difference matters: the games a host serves are rows
in its catalog, not a closed set in the API schema. The enum lists today's, but the
parameter stays `str`, so a new slug works without an SDK release. The authoritative list
is `catalog.games()`.

## Scenarios

Four different approaches, not four ways to call one method. Take the one whose shape
matches your problem.

### One code, one player — a straight line

When there are few activations and you need the outcome right here: a sale in a chat,
manual delivery, a check before buying. `activate_and_wait` hides the polling.

```python
import asyncio

from midasbuy_sdk import ActivationState, AsyncMidasbuyClient, GameSlug


async def sell(code: str, player_id: str) -> str:
    async with AsyncMidasbuyClient("your-key") as client:
        # Check the player BEFORE spending the code — a wrong ID cannot be undone.
        who = await client.characters.lookup(
            account_id="acc_01H...", game=GameSlug.PUBGM, player_id=player_id
        )
        if who.is_ban:
            raise RuntimeError(f"{who.role_name} is banned")

        result = await client.redeem.activate_and_wait(
            code, account_id="acc_01H...", game=GameSlug.PUBGM, player_id=player_id
        )
        if result.status is not ActivationState.success:
            raise RuntimeError(f"failed: {result.failure_code}")
        return result.granted_item or "delivered"


print(asyncio.run(sell("CODE-1234", "5544128792")))
```

### Many codes, many players — concurrent, one poll for all

When an order arrives with dozens of deliveries. Activations are queued concurrently and
the statuses come back in **one** call instead of N polls — which is the reason the client
is async at all.

```python
import asyncio

from midasbuy_sdk import ActivationState, AsyncMidasbuyClient, GameSlug

ORDERS = [("CODE-1", "5544128792"), ("CODE-2", "5544128793")]


async def bulk() -> dict[str, ActivationState]:
    async with AsyncMidasbuyClient("your-key") as client:
        jobs = await asyncio.gather(*(
            client.redeem.activate(
                code,
                account_id="acc_01H...",
                game=GameSlug.PUBGM,
                player_id=player,
                # Your own idempotency key: your retry then collapses into the
                # same activation instead of becoming a second one.
                idempotency_key=f"order-42:{code}",
            )
            for code, player in ORDERS
        ))

        while True:
            rows = await client.redeem.status_batch([j.activation_id for j in jobs])
            done = {
                r.activation_id: r.status
                for r in rows.activations
                if r.status not in (ActivationState.pending, ActivationState.running)
            }
            if len(done) == len(jobs):
                return done
            await asyncio.sleep(2)


print(asyncio.run(bulk()))
```

### Your own code stock — activate by denomination

When codes are bought in advance and held by the service: you name a denomination rather
than a code, and the server picks a free one. This is how automated selling works — the
buyer does not care which code they got.

```python
import asyncio

from midasbuy_sdk import AsyncMidasbuyClient, GameSlug


async def stock_and_sell() -> None:
    async with AsyncMidasbuyClient("your-key") as client:
        # Load the codes you bought (the server drops duplicates itself).
        await client.inventory.add(
            [
                {"code": "CODE-A", "game": GameSlug.PUBGM, "denomination_value": 60},
                {"code": "CODE-B", "game": GameSlug.PUBGM, "denomination_value": 60},
            ],
            idempotency_key="import-2026-08-01",
        )

        # What is actually left, per game and denomination.
        for row in (await client.inventory.stock()).items:
            print(row.game, row.denomination_value, row.available, "of", row.total)

        # Selling: a denomination instead of a code. In bulk — quantity at a time.
        job = await client.redeem.activate_batch_by_denomination(
            account_id="acc_01H...",
            game=GameSlug.PUBGM,
            denomination_value=60,
            quantity=3,
            player_id="5544128792",
        )
        print(job.accepted, "of", job.requested, "accepted")


asyncio.run(stock_and_sell())
```

### A task for an amount + a webhook — no polling at all

When the buyer wants a total, not particular denominations: the server assembles the code
set from stock. The result is delivered to your endpoint, so your process does not have to
outlive the task.

```python
import asyncio

from midasbuy_sdk import AsyncMidasbuyClient, GameSlug, TaskState


async def package() -> None:
    async with AsyncMidasbuyClient("your-key") as client:
        task = await client.tasks.package(
            account_id="acc_01H...",
            game=GameSlug.PUBGM,
            player_id="5544128792",
            amount=660,
            webhook_url="https://your-domain/hooks/midasbuy",
        )
        print(task.task_id, task.state)

        # With no webhook, the summary is fetched the usual way. Three terminals:
        # success (all went through), partial (some), failed (none).
        summary = await client.tasks.get(task.task_id)
        if summary.state is not TaskState.pending:
            print(summary.success_count, "of", summary.item_count)


asyncio.run(package())
```

The webhook URL is validated server-side: loopback, private and metadata addresses are
rejected, and the resolved IP is pinned.

### The sync client — for scripts and notebooks

The same API without `await`, when an event loop costs more than the task.

```python
from midasbuy_sdk import GameSlug, MidasbuyClient

with MidasbuyClient("your-key") as client:
    result = client.redeem.activate_and_wait(
        "CODE-1234", account_id="acc_...", game=GameSlug.PUBGM, player_id="5544128792"
    )
    print(result.status, result.granted_item)
```

## What the client does for you

**Idempotency key.** Every POST carries an `Idempotency-Key` minted **once before** the
attempts and reused across retries, so a timeout, a dropped connection or a 429 never
turns one activation into two. Pass your own and your retry collapses into the same
operation too.

**Retries where they are safe.** 5xx and 429 with exponential backoff, honouring
`Retry-After`. Connection drops and timeouts too: they do not escape as a raw `httpx`
exception — they are retried under the same key and end as `NetworkError`. A daily cap
(429 with `activation_window_limit`) is never retried; waiting cannot make it succeed.

**Typed errors.** `AuthFailed`, `NotFound`, `OutOfStock`, `RateLimited`,
`DailyCapReached`, `ValidationFailed`, `ServerError`, `NetworkError`, `WaitTimeout` — each
carries `code`, `status` and the `request_id` worth quoting to support.

```python
from midasbuy_sdk import DailyCapReached, MidasbuyError, RateLimited

try:
    await client.redeem.activate(...)
except RateLimited as e:
    await asyncio.sleep(e.retry_after or 5)
except DailyCapReached as e:
    print("daily cap spent, resets at", e.reset_at)
except MidasbuyError as e:
    print(e.code, e.request_id)
```

**Pagination.** Lists return a `Page` with `items`, `total`, `has_more`; `iterate()` walks
everything for you:

```python
async for activation in client.redeem.iterate(limit=100):
    print(activation.activation_id, activation.status)
```

**Waiting.** `wait_for(activation_id, poll=2, timeout=300)` polls until terminal and
raises `WaitTimeout` if it never gets there. Note: `WaitTimeout` is not a failure — the
activation is still running, and re-activating that code is not safe.

## API surface

| Resource | Methods |
|---|---|
| `client.accounts` | `connect(country=, email=, password=)` · `list()` · `get(id)` |
| `client.catalog` | `games()` · `items(game=)` · `get_item(item_id)` |
| `client.characters` | `lookup(account_id=, game=, player_id=)` · `list(account_id=, game=)` · `refresh(account_id=)` |
| `client.inventory` | `add(items)` · `list(game=, code_status=)` · `stock()` |
| `client.redeem` | `activate(code, ...)` · `activate_and_wait(...)` · `activate_by_denomination(...)` · `activate_batch_by_denomination(...)` · `preview(...)` · `get(id)` · `list()` · `iterate()` · `status_batch(ids)` · `wait_for(id)` |
| `client.tasks` | `batch(items=)` · `package(amount=)` · `get(id)` · `list()` |
| `client.subscription` | `get()` — key status, expiry, remaining quota, rate |

The full contract is [`openapi.public.json`](openapi.public.json); how the client itself
is built is [`DESIGN.md`](DESIGN.md).

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check . && mypy src
python scripts/codegen.py     # after editing _async/ or refreshing the spec
```

Only `src/midasbuy_sdk/_async/` is hand-written — the sync mirror and the models are
generated (`unasync` + `datamodel-code-generator`), and CI fails if the generated half
drifts from its source.

## Community

Bugs and requests — [issues](https://github.com/zlexdev/midasbuy-sdk/issues).
PRs welcome: run `pytest`, `ruff` and `mypy` before sending one.

<a href="https://github.com/zlexdev"><img src="https://github.com/zlexdev.png" width="48" height="48" style="border-radius:50%" alt="zlexdev" /></a>

## License

[MIT](LICENSE) © zlexdev
