"""Phase 3 sensing tools: now_playing + library_scan.

Read-only primitives a Claude Code session drives (Mode A). No recommendation
logic lives here — these fetch state; the session does the reasoning (lineage /
"rabbit hole" commentary, taste reports + blind spots, library archaeology,
time-machine playlists). See RECIPES.md for the workflows that build on them.

Both reuse the same auth/cache as the rest of the tool layer (auth.py, .cache).
`library_scan` reuses Phase 1's saved-tracks fetcher so there's one fetch path.

Library use:
    from sensing import now_playing, library_scan
    np = now_playing()                 # dict, or None if nothing is playing
    lib = library_scan(cap=500)        # {"count", "tracks", "path"}

CLI use:
    python sensing.py now-playing
    python sensing.py library-scan --cap 500
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from auth import get_client
from taste_profile import DATA_DIR, _track_record, fetch_saved_tracks

# Minimal scopes per primitive. Kept separate from tools.py's write superset so a
# read-only session never requests playlist-modify just to see what's playing.
NOW_PLAYING_SCOPES = ["user-read-currently-playing"]
LIBRARY_SCOPES = ["user-library-read"]


def now_playing(sp=None) -> dict | None:
    """Return the currently-playing track, or None if nothing is playing.

    Shape: {id, uri, title, artists, album, is_playing, progress_ms, duration_ms}.
    `artists` is a comma-joined string for easy display; the raw id/uri are kept
    so the session can feed them straight into search/verify or playlist tools.
    """
    sp = sp or get_client(NOW_PLAYING_SCOPES)
    current = sp.current_user_playing_track()
    if not current:
        return None
    track = current.get("item")
    if not track:  # could be an ad or a non-track context
        return None
    return {
        "id": track.get("id"),
        "uri": track.get("uri"),
        "title": track.get("name"),
        "artists": ", ".join(a.get("name", "") for a in track.get("artists", [])),
        "album": (track.get("album") or {}).get("name"),
        "is_playing": current.get("is_playing"),
        "progress_ms": current.get("progress_ms"),
        "duration_ms": track.get("duration_ms"),
    }


def library_scan(cap: int = 500, sp=None, write: bool = True) -> dict:
    """Fetch the user's saved tracks and (optionally) dump them to JSON.

    Reuses Phase 1's `fetch_saved_tracks` so the library fetch has a single
    implementation. Returns {"count", "tracks", "path"} where `path` is the
    written file (or None if write=False). Records carry the Phase 1 metadata
    (name, id, popularity, artists, album, release_date, added_at) — no
    audio-features.
    """
    sp = sp or get_client(LIBRARY_SCOPES)
    tracks = fetch_saved_tracks(sp, cap=cap)
    path = None
    if write:
        os.makedirs(DATA_DIR, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = os.path.join(DATA_DIR, f"library_{stamp}.json")
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(tracks),
            "tracks": tracks,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
    return {"count": len(tracks), "tracks": tracks, "path": path}


# --------------------------------------------------------------------------- CLI


def _fmt_ms(ms: int | None) -> str:
    if not ms:
        return "?:??"
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _cmd_now_playing(args) -> int:
    np = now_playing()
    if not np:
        print("Nothing is currently playing.", file=sys.stderr)
        return 1
    state = "▶" if np["is_playing"] else "⏸"
    print(np["uri"])
    print(
        f"  {state} {np['title']} — {np['artists']} ({np['album']})  "
        f"[{_fmt_ms(np['progress_ms'])}/{_fmt_ms(np['duration_ms'])}]",
        file=sys.stderr,
    )
    return 0


def _cmd_library_scan(args) -> int:
    result = library_scan(cap=args.cap, write=not args.no_write)
    if result["path"]:
        print(result["path"])
    print(f"  scanned {result['count']} saved track(s)", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Spotify sensing tools (Phase 3).")
    sub = p.add_subparsers(dest="cmd", required=True)

    npc = sub.add_parser("now-playing", help="Print the currently-playing track.")
    npc.set_defaults(func=_cmd_now_playing)

    lsc = sub.add_parser("library-scan", help="Dump saved tracks to data/library_*.json.")
    lsc.add_argument("--cap", type=int, default=500, help="Max saved tracks to fetch.")
    lsc.add_argument("--no-write", action="store_true", help="Don't write a JSON dump.")
    lsc.set_defaults(func=_cmd_library_scan)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
