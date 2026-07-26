"""Regenerate the two machine-authored parts of the SDK.

1. ``models/_generated.py`` — pydantic models from ``openapi.public.json``.
2. ``_sync/`` — the blocking mirror of ``_async/``, produced by ``unasync``.

Run after editing anything in ``_async/`` or after refreshing the spec:

    python scripts/codegen.py

CI runs it too and fails if the working tree changes — so the generated code
can never silently drift from its sources.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import unasync

# Windows consoles default to cp1252; the repo path holds non-ASCII, so printing
# a command line would raise UnicodeEncodeError before any work runs.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "src" / "midasbuy_sdk"
SPEC = ROOT / "openapi.public.json"

# Async token -> sync token. The structural async->sync (async def, await, async
# for/with) is handled by unasync itself; these are our names + stdlib swaps.
_REPLACEMENTS = {
    "AsyncMidasbuyClient": "MidasbuyClient",
    "AsyncTransport": "Transport",
    "AsyncResource": "Resource",
    "AsyncAccounts": "Accounts",
    "AsyncCatalog": "Catalog",
    "AsyncCharacters": "Characters",
    "AsyncInventory": "Inventory",
    "AsyncRedeem": "Redeem",
    "AsyncSubscription": "Subscription",
    "AsyncTasks": "Tasks",
    "AsyncClient": "Client",
    "AsyncIterator": "Iterator",
    "aclose": "close",
    "asyncio": "time",
    "_async": "_sync",
}


def _run(*cmd: str, check: bool = True) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, check=check, cwd=ROOT)


def gen_models() -> None:
    print("==> models from openapi.public.json")
    _run(
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(SPEC),
        "--input-file-type",
        "openapi",
        "--output",
        str(PKG / "models" / "_generated.py"),
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.11",
        "--use-standard-collections",
        "--use-union-operator",
        "--use-annotated",
        "--field-constraints",
        "--collapse-root-models",
        "--use-schema-description",
        "--disable-timestamp",
        "--formatters",
        "black",
        "--formatters",
        "isort",
    )


def gen_sync() -> None:
    print("==> sync mirror from _async (unasync)")
    async_dir = PKG / "_async"
    rule = unasync.Rule(
        fromdir=str(async_dir) + "/",
        todir=str(PKG / "_sync") + "/",
        additional_replacements=_REPLACEMENTS,
    )
    files = [str(p) for p in async_dir.rglob("*.py")]
    unasync.unasync_files(files, [rule])


def fmt() -> None:
    print("==> ruff format + fix (dedupe imports the token-swap produced)")
    # --fix exits 1 when residual (ignored) lints remain — not a codegen failure.
    _run(sys.executable, "-m", "ruff", "check", "--fix", "--quiet", str(PKG / "_sync"), check=False)
    _run(sys.executable, "-m", "ruff", "format", "--quiet", str(PKG))


if __name__ == "__main__":
    gen_models()
    gen_sync()
    fmt()
    print("ok — models + sync mirror regenerated")
