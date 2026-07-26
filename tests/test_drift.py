"""The drift gate — checks FORM against the spec, not just names.

1. Every public route in ``openapi.public.json`` is bound to an SDK method.
2. Every required request field is exposed as a parameter on that method.

The old name-only gate passed while ``activate()`` shipped without ``game`` and
422'd every call. This one fails on exactly that.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from midasbuy_sdk import AsyncMidasbuyClient

SPEC = json.loads(
    (Path(__file__).resolve().parent.parent / "openapi.public.json").read_text("utf-8")
)

# (METHOD, path) -> (resource attribute, method name). One line per public route.
COVERAGE: dict[tuple[str, str], tuple[str, str]] = {
    ("POST", "/v1/accounts/connect"): ("accounts", "connect"),
    ("GET", "/v1/accounts/list"): ("accounts", "list"),
    ("GET", "/v1/accounts/get"): ("accounts", "get"),
    ("GET", "/v1/catalog/games"): ("catalog", "games"),
    ("GET", "/v1/catalog/items"): ("catalog", "items"),
    ("GET", "/v1/catalog/get_item"): ("catalog", "get_item"),
    ("POST", "/v1/inventory/add"): ("inventory", "add"),
    ("GET", "/v1/inventory/list"): ("inventory", "list"),
    ("GET", "/v1/inventory/stock"): ("inventory", "stock"),
    ("POST", "/v1/redeem/activate"): ("redeem", "activate"),
    ("POST", "/v1/redeem/activate-by-denomination"): ("redeem", "activate_by_denomination"),
    ("POST", "/v1/redeem/activate-batch-by-denomination"): (
        "redeem",
        "activate_batch_by_denomination",
    ),
    ("POST", "/v1/redeem/preview"): ("redeem", "preview"),
    ("GET", "/v1/redeem/list"): ("redeem", "list"),
    ("GET", "/v1/redeem/get"): ("redeem", "get"),
    ("POST", "/v1/redeem/status-batch"): ("redeem", "status_batch"),
    ("GET", "/v1/subscription"): ("subscription", "get"),
    ("POST", "/v1/tasks/batch"): ("tasks", "batch"),
    ("POST", "/v1/tasks/package"): ("tasks", "package"),
    ("GET", "/v1/tasks/get"): ("tasks", "get"),
    ("GET", "/v1/tasks/list"): ("tasks", "list"),
    ("GET", "/v1/characters/list"): ("characters", "list"),
    ("GET", "/v1/characters/lookup"): ("characters", "lookup"),
    ("POST", "/v1/characters/refresh"): ("characters", "refresh"),
}

_METHODS = ("get", "post", "put", "patch", "delete")


def _spec_ops() -> set[tuple[str, str]]:
    return {(m.upper(), path) for path, ops in SPEC["paths"].items() for m in ops if m in _METHODS}


def _required_fields(op: dict) -> list[str]:
    try:
        ref = op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    except KeyError:
        return []
    schema = SPEC["components"]["schemas"][ref.split("/")[-1]]
    return list(schema.get("required", []))


def test_every_route_is_covered() -> None:
    assert _spec_ops() == set(COVERAGE), (
        "SDK coverage drifted from the spec:\n"
        f"  missing methods: {_spec_ops() - set(COVERAGE)}\n"
        f"  stale entries:   {set(COVERAGE) - _spec_ops()}"
    )


def test_every_bound_method_exists() -> None:
    client = AsyncMidasbuyClient("k")
    for resource, method in COVERAGE.values():
        assert callable(getattr(getattr(client, resource), method))


def test_required_request_fields_are_exposed() -> None:
    client = AsyncMidasbuyClient("k")
    problems: list[str] = []
    for (http, path), (resource, method) in COVERAGE.items():
        if http != "POST":
            continue
        op = SPEC["paths"][path][http.lower()]
        required = _required_fields(op)
        params = set(inspect.signature(getattr(getattr(client, resource), method)).parameters)
        missing = [f for f in required if f not in params]
        if missing:
            problems.append(f"{resource}.{method} is missing params for required fields {missing}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("http,path", sorted(_spec_ops()))
def test_spec_op_in_coverage(http: str, path: str) -> None:
    assert (http, path) in COVERAGE, f"new endpoint {http} {path} has no SDK method"
