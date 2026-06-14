"""Phase 4 ergonomics: one entry point dispatching to every tool primitive.

This is a thin router over the Phase 1–3 modules — it adds no recommendation or
sensing logic of its own (that stays in taste_profile.py / tools.py / sensing.py,
and the *reasoning* stays in the Claude Code session per Mode A). It exists so a
session can drive each primitive with a single uniform command:

    python cli.py dump-taste [--max-age MIN] [--force]
    python cli.py search-verify "Radiohead" "Weird Fishes/Arpeggi"
    python cli.py build-playlist "My Playlist" spotify:track:xxx [...] [--uris-file f]
    python cli.py now-playing
    python cli.py library-scan [--cap 500] [--no-write]

Convention: the machine-readable result (a path or URI) goes to stdout; human
notes go to stderr — so `$(python cli.py dump-taste)` captures just the path.

Optional polish (plan §4): `dump-taste --max-age N` reuses the most recent
data/taste_*.json if it's younger than N minutes, avoiding a redundant API pull.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

import taste_profile
from sensing import _cmd_library_scan, _cmd_now_playing
from tools import _cmd_build_playlist, _cmd_search_verify


def _latest_taste_dump() -> str | None:
    """Return the path of the newest data/taste_*.json, or None if none exist."""
    paths = glob.glob(os.path.join(taste_profile.DATA_DIR, "taste_*.json"))
    return max(paths, key=os.path.getmtime) if paths else None


def _cmd_dump_taste(args) -> int:
    """Fetch fresh taste data, or reuse a recent dump if --max-age allows.

    Without --max-age (or with --force) it always re-fetches. With --max-age N it
    prints the latest existing dump when that file is younger than N minutes,
    skipping the API round-trip entirely.
    """
    if not args.force and args.max_age is not None:
        latest = _latest_taste_dump()
        if latest is not None:
            age_min = (time.time() - os.path.getmtime(latest)) / 60
            if age_min <= args.max_age:
                print(latest)
                print(
                    f"  reused dump from {age_min:.0f} min ago "
                    f"(<= --max-age {args.max_age})",
                    file=sys.stderr,
                )
                return 0

    # taste_profile.main() prints "Wrote <path>" + a summary to stdout; capture the
    # path so this command's stdout stays just the path, like the other commands.
    taste_profile.main()
    latest = _latest_taste_dump()
    if latest:
        print(latest)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        prog="cli.py",
        description="Spotify discovery toolkit — one entry point for all primitives.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    dt = sub.add_parser("dump-taste", help="Dump taste data to data/taste_*.json.")
    dt.add_argument(
        "--max-age",
        type=float,
        default=None,
        metavar="MIN",
        help="Reuse the latest dump if younger than MIN minutes instead of refetching.",
    )
    dt.add_argument(
        "--force", action="store_true", help="Always refetch, ignoring --max-age."
    )
    dt.set_defaults(func=_cmd_dump_taste)

    sv = sub.add_parser(
        "search-verify", help="Print a track URI if it exists, else MISS."
    )
    sv.add_argument("artist")
    sv.add_argument("title")
    sv.set_defaults(func=_cmd_search_verify)

    bp = sub.add_parser("build-playlist", help="Create a private playlist from URIs.")
    bp.add_argument("name")
    bp.add_argument("uris", nargs="*", help="Track URIs (or use --uris-file).")
    bp.add_argument("--uris-file", help="File with one track URI per line.")
    bp.add_argument("--description", default="", help="Playlist description.")
    bp.add_argument("--public", action="store_true", help="Make the playlist public.")
    bp.set_defaults(func=_cmd_build_playlist)

    npc = sub.add_parser("now-playing", help="Print the currently-playing track.")
    npc.set_defaults(func=_cmd_now_playing)

    lsc = sub.add_parser(
        "library-scan", help="Dump saved tracks to data/library_*.json."
    )
    lsc.add_argument("--cap", type=int, default=500, help="Max saved tracks to fetch.")
    lsc.add_argument("--no-write", action="store_true", help="Don't write a JSON dump.")
    lsc.set_defaults(func=_cmd_library_scan)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
