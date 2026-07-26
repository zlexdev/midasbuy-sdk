"""``Page[T]`` — one page of a list endpoint, plus the paging math.

List endpoints answer ``{"items": [...], "total": N, "next_cursor": ...}`` under
the ``data`` envelope and page by ``limit`` / ``offset``. ``Page`` carries the
window; the resources' ``iterate`` walks offsets until the items run out.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """A single window of a listing. Iterate ``items`` directly, or use the
    resource's ``iterate`` to walk every page."""

    items: Sequence[T]
    total: int
    limit: int
    offset: int
    next_cursor: str | None = None

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    @property
    def next_offset(self) -> int:
        return self.offset + self.limit

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)
