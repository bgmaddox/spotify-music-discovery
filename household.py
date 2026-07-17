"""Shared household / white-noise filter used by streaming_history and build_timeline_data.

Importing from here instead of from build_timeline_data avoids a circular import
when streaming_history needs these constants.
"""

from __future__ import annotations

import re

# Artists forced to kids/household regardless of Last.fm tags.
HOUSEHOLD_ARTISTS: frozenset[str] = frozenset(
    {
        "CoComelon",
        "Pinkfong",
        "Elmo",
        "Bluey",
        "Kristen Bell",
        "Idina Menzel",
        "Auli'i Cravalho",
        "Mark Mancina",
        "Josh Gad",
        "Jonathan Groff",
        "Super Simple Songs",
        "The Wiggles",
        "Bruce Brus",           # white-noise sleep audio (tags say electronic; not taste)
        "Nursery Rhymes Band",
    }
)

_WHITE_NOISE_RE = re.compile(r"white\s+noise", re.IGNORECASE)


def is_household(name: str) -> bool:
    """True when an artist name is in the household set or matches white-noise pattern."""
    return name in HOUSEHOLD_ARTISTS or bool(_WHITE_NOISE_RE.search(name))
