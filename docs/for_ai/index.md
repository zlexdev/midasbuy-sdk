# midasbuy-sdk — map for coding agents

Read this instead of the source when you need the shape of the package. It is the
compressed version: what lives where, which halves are generated, and the invariants a
patch must not break.

## Layout

```
src/midasbuy_sdk/
  __init__.py            public surface — clients, DEFAULT_BASE_URL, every error, every enum
  enums.py               HAND-WRITTEN: GameSlug (catalog-driven, not a closed set)
  errors.py              typed hierarchy + error_for() (error_code wins over status)
  _pagination.py         Page[T] — items/total/has_more/next_offset
  _async/                THE SOURCE OF TRUTH — edit only here
    _client.py           AsyncMidasbuyClient + DEFAULT_BASE_URL
    _transport.py        auth, retries, idempotency, unwrap
    resources/           accounts · catalog · characters · inventory · redeem · subscription · tasks
  _sync/                 GENERATED from _async by unasync — never hand-edit
  models/_generated.py   GENERATED from openapi.public.json — never hand-edit
```

`python scripts/codegen.py` regenerates both generated halves; CI fails if the working
tree changes after it runs.

## Invariants

- **One idempotency key per logical call**, minted before the retry loop and reused by
  every attempt. Minting per attempt turns a retry into a second activation.
- **The retry loop wraps the transport call**, not only the response status: timeouts
  and connection errors are retried and finally surface as `NetworkError`.
- **A 429 carrying `activation_window_limit` is answered, never retried** — it is a
  daily cap, and waiting cannot make it succeed.
- **`next_offset` counts what arrived** (`offset + len(items)`), never `offset + limit`.
- **Server-declared enums are exported from the package root.** A caller who has to
  reach into `.models` writes a literal instead.
- **`GameSlug` is a convenience, not a validator.** Games are rows in the contour's
  catalog; parameters stay typed `str` so an unreleased slug still works. The real list
  is `client.catalog.games()`.
- **`DEFAULT_BASE_URL` is verified by request, not by belief** — a test pins it against
  the host named in the docs; it once shipped pointing at a domain with no DNS record.

## Domain shape

`account_id` is the Midas account the activation runs FROM; `player_id` is the player it
lands ON, and it is optional (absent → the account itself). Activations are async: a
POST returns `202` with an id, and the terminal state arrives via `redeem.get`,
`redeem.status_batch`, `wait_for`, or a task's `webhook_url`.

Terminal activation states: `success`, `failed`, `indeterminate`. Terminal task states:
`success`, `partial`, `failed`.

## Where to look next

- `DESIGN.md` — why the client is shaped this way.
- `openapi.public.json` — the wire contract the models are generated from.
- `tests/test_sdk.py` — behavioural pins (retries, idempotency, pagination, waiting).
- `tests/test_drift.py` — every route has a method and every required body field is a
  parameter.
