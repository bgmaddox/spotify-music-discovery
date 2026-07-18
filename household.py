"""Shared household / white-noise filter used by streaming_history and build_timeline_data.

The artist list lives in config/household_artists.txt so a new user can adapt it
without touching code. Importing from here instead of from build_timeline_data
avoids a circular import when streaming_history needs these constants.
"""

from __future__ import annotations

import os
import re
import sys

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config", "household_artists.txt"
)


def _load_household(path: str = _CONFIG_PATH) -> frozenset[str]:
    """Read the household artist list; empty set (with a warning) if the file is gone."""
    try:
        with open(path, encoding="utf-8") as f:
            names = {
                line.strip()
                for line in f
                if line.strip() and not line.lstrip().startswith("#")
            }
        return frozenset(names)
    except FileNotFoundError:
        print(
            f"warning: {path} not found — no household artists will be filtered",
            file=sys.stderr,
        )
        return frozenset()


# Artists forced to kids/household regardless of Last.fm tags.
HOUSEHOLD_ARTISTS: frozenset[str] = _load_household()

_WHITE_NOISE_RE = re.compile(r"white\s+noise", re.IGNORECASE)


def is_household(name: str) -> bool:
    """True when an artist name is in the household set or matches white-noise pattern."""
    return name in HOUSEHOLD_ARTISTS or bool(_WHITE_NOISE_RE.search(name))
