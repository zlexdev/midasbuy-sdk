# midasbuy-sdk — redesign (v0.2)

Design of record for the rebuilt client. English in code, this doc frozen before
any rewrite. The published `0.1.x` is superseded.

## Why rebuild

The `0.1.x` client is a flat god-object with sync and async hand-duplicated,
covers ~10 of 23 public endpoints, guesses response shapes with
`x.get("a") or x.get("b")`, parses the wrong error envelope (`error.code` — the
API sends top-level `error_code`), drops pagination, and its drift gate compares
route *names* only (so it shipped a `422` `activate()` in `0.1.0`). Every one of
those is structural, not a bug to patch.

## Decision (frozen)

Codegen level: **models generated from `openapi.public.json` + sync produced from async by
`unasync`.** Ergonomic layer (transport, resources, pagination, `wait_for`) hand-written once
against async. This kills the two structural defects (model drift, sync/async duplication) at the
toolchain level; the cost is two dev-time build steps (`datamodel-code-generator`, `unasync`) and a
CI target that regenerates and fails on a diff.

## Principles

1. **One source of truth per method.** Write the async client once; the sync
   client is produced mechanically (`unasync`), never hand-copied.
2. **Models are the contract.** Response/request models are generated from the
   service's `openapi.public.json`, not hand-written — drift becomes impossible,
   not merely tested-for.
3. **Cover the WHOLE public surface** from the first release. A client that stops
   where the free tier stops gets rewritten the day someone pays (sdk-design).
4. **Async is primary, sync is the supplement.** A `202`-and-poll API is called
   in batches; the fast-start example is async.
5. **The drift gate checks FORM, not names.** Every public route must have a
   method whose request/response models match the spec's schemas — a missing
   field fails CI.

## Public surface — resource-grouped (all 23 endpoints)

`client.<resource>.<method>()`. Same tree on sync and async.

- **accounts** — `connect(cookies, game, *, idempotency_key=None)` · `list(*, cursor=None)` · `get(account_id)`
- **catalog** — `games()` · `items(game, *, cursor=None)` · `get_item(item_id)`
- **inventory** — `add(...)` · `list(*, cursor=None)` · `stock(game=None)`
- **redeem** — `activate(code, *, account_id, game, player_id=None, idempotency_key=None)` ·
  `activate_by_denomination(...)` · `activate_batch_by_denomination(...)` ·
  `preview(...)` · `list(*, cursor=None)` · `get(activation_id)` · `status_batch(ids)`
- **tasks** — `batch(...)` · `package(...)` · `get(task_id)`
- **subscription** — `get()`  *(the key's status / daily-cap headroom)*
- **characters** *(paid host only — 404 on free, surfaced as `EndpointNotOnThisTier`)* —
  `refresh(...)` · `list(...)` · `lookup(...)`

Ergonomic helpers layered on top (hand-written, not per-endpoint):
- `redeem.wait_for(activation_id, *, poll=2, timeout=300)` → terminal `Activation` or `WaitTimeout`
- `redeem.activate_and_wait(...)` → activate then wait, one call
- every `list(...)` returns a typed `Page[T]`; `iterate(...)` is an (async) generator over cursors

## Module layout

```
src/midasbuy_sdk/
  __init__.py            # exports: AsyncMidasbuyClient, MidasbuyClient, errors, models, __version__
  _client_async.py       # AsyncMidasbuyClient — the ONE hand-written client (resources wired here)
  _client_sync.py        # GENERATED from _client_async.py by unasync — never edited by hand
  _transport.py          # AsyncTransport: auth header, retry+backoff (Retry-After aware),
                          # Idempotency-Key, request-id capture, envelope unwrap, error mapping
  _pagination.py         # Page[T], cursor iterator (async; unasync'd to sync)
  resources/
    _base.py             # Resource base: holds a transport, builds requests
    accounts.py catalog.py inventory.py redeem.py tasks.py subscription.py characters.py
  models/
    _generated.py        # datamodel-code-generator output from openapi.public.json (pydantic v2)
    __init__.py          # re-exports the generated models under stable names + enums
  errors.py              # exception hierarchy, mapped from the API's public_code set + status
  py.typed               # PEP 561 — ships types
tests/
  test_transport.py test_pagination.py test_errors.py
  test_drift.py          # THE gate: every openapi path has a method; request/response models match
  test_unasync.py        # asserts _client_sync.py is up to date with _client_async.py
scripts/
  codegen.py             # regenerate models/_generated.py + _client_sync.py; run in CI + pre-commit
```

## Transport (the single core, written once)

- Auth: `Authorization: Bearer <key>` set once.
- **Idempotency:** every POST carries `Idempotency-Key` (caller value or a per-call uuid4); a
  retry reuses the SAME key, so a timeout never doubles an activation. GET carries none.
- **Retry+backoff:** 429 + 5xx retried up to `max_retries`; honours `Retry-After`, else exp
  backoff capped at 30s. By the time a `RateLimited` reaches the caller, retries are spent.
- **Envelope:** success is `{"data": <obj|list>}` → unwrap `data`; list endpoints carry
  `{"items", "total", "next_cursor"}` → `Page[T]`. Error is top-level
  `{"error_code", "message", "request_id"}` — mapped, never `str(exc)`.
- **request_id** captured from body/header onto every error for support quoting.

## Models & drift

- `scripts/codegen.py` runs `datamodel-code-generator` over `openapi.public.json` → pydantic v2
  models with real field names, enums for status/public_code, `Decimal` for money, `datetime`
  for timestamps. Regenerated in CI; a diff fails the build (models can't silently drift).
- `test_drift.py`: load the spec, assert (a) every public path has a bound SDK method, (b) each
  method's request model fields ⊇ the spec's required request fields, (c) the response model
  matches the spec's response schema. This is the FORM check the old name-only gate lacked.
- The service's `openapi.public.json` is vendored into the SDK repo (committed) and refreshed by
  a small CI job that pulls it from the API repo's `scripts/gen_openapi.sh` output — so the SDK
  builds offline and the drift gate has something to compare against.

## Errors

One hierarchy under `MidasbuyError` (keeps `code`, `status`, `request_id`):
`AuthFailed(401)` · `RateLimited(429, retry_after)` · `DailyCapReached(reset_at)` ·
`OutOfStock` · `NotFound` · `ValidationFailed(400/409/422)` · `EndpointNotOnThisTier(404 on a
paid path from the free host)` · `ServerError(5xx)` · `WaitTimeout` (client-side).
Mapping table is keyed by the API's `public_code` **enum** (generated from the spec), with a
status fallback — not a hand-maintained dict of three strings.

## Packaging & versioning

- `py.typed`, pydantic v2 + httpx as the only runtime deps.
- `DEFAULT_BASE_URL = "https://free.midasbuy-api.dev/v1"` (real free host, DNS + `/health` checked); `base_url=` for paid.
- SemVer tracks the API's public contract major. Publish via PyPI Trusted Publisher (OIDC), tag =
  release. No token in CI.
- First rebuilt release: **0.2.0** (0.1.x superseded; not yank-worthy, just eclipsed).

## Testing

`respx`-mocked transport for unit tests (retry, idempotency-key reuse, envelope, pagination,
each error mapping); the drift gate against the real spec; a `test_unasync` guard that the sync
mirror is regenerated. No live-network test in CI (a smoke script against the free host is manual).

## Migration from 0.1.x

`from midasbuy_sdk import AsyncMidasbuyClient` still works. Flat methods (`client.activate(...)`)
become `client.redeem.activate(...)`; a thin deprecation shim can keep the old names for one minor
if wanted (decision below).
