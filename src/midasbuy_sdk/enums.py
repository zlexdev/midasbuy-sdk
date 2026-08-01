"""Hand-written enums — the ones the OpenAPI schema cannot give you.

Everything the server declares (``ActivationState``, ``AccountStatus``, ``Country``,
``TaskState``, …) is generated from the spec and re-exported at the top level; import
those, never retype their strings.

``GameSlug`` is different, and the difference matters: the games a host serves are ROWS
in its catalog, not a closed set in the API schema. Each contour can serve a
different list, and a new one appears without an SDK release. So this enum is a
convenience for the ones that exist today, not a validator:

- it is a ``StrEnum``, so ``GameSlug.PUBGM`` goes anywhere a ``str`` goes —
  ``client.redeem.activate(code, account_id=..., game=GameSlug.PUBGM)`` needs no cast;
- the parameters stay typed ``str`` on purpose, so a slug this release has never
  heard of still works;
- the authoritative list is always ``client.catalog.games()``. Ask it when you need
  certainty, and treat an unknown slug as data, not as an error in your code.
"""

from __future__ import annotations

from enum import StrEnum


class GameSlug(StrEnum):
    """Game slugs served by the public contours today.

    Named ``GameSlug``, not ``Game``: ``Game`` is the catalog DTO the API returns
    (slug + title + prefix), and one name for two things is how the wrong one gets
    imported.

    The value is what the API takes as ``game``. Verify against
    ``client.catalog.games()`` rather than assuming this list is complete.
    """

    PUBGM = "pubgm"
    """PUBG Mobile."""

    CODM = "codm"
    """Call of Duty: Mobile."""
