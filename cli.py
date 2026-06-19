"""Phase 4 ergonomics: one entry point dispatching to every tool primitive.

This is a thin router over the Phase 1–3 modules — it adds no recommendation or
sensing logic of its own (that stays in taste_profile.py / tools.py / sensing.py,
and the *reasoning* stays in the Claude Code session per Mode A). It exists so a
session can drive each primitive with a single uniform command:

    python cli.py dump-taste [--max-age MIN] [--force]
    python cli.py taste-snapshot   # lean summary + known-artist set (vs reading raw JSON)
    python cli.py search-verify "Radiohead" "Weird Fishes/Arpeggi"
    python cli.py build-playlist "My Playlist" spotify:track:xxx [...] [--uris-file f]
    python cli.py generate-cover "warm americana wheat field at sunset" [--out f --seed N]
    python cli.py set-playlist-image <playlist-url|uri|id> cover.png
    python cli.py now-playing
    python cli.py library-scan [--cap 500] [--no-write]
    python cli.py similar-artists "Colter Wall" [--limit 30]
    python cli.py similar-tracks "Colter Wall" "Sleeping on the Blacktop" [--limit 30]
    python cli.py artist-tags "Colter Wall" [--limit 10]
    python cli.py genre-neighbors "indie folk" [--limit 15]
    python cli.py genre-find "americana"
    python cli.py log-add --artist "Tyler Childers" [--title T --uri U --recipe 6 --playlist URL]
    python cli.py log-artists          # artists already surfaced (cross-session dedup)
    python cli.py log-recent [--limit 20]

Convention: the machine-readable result (a path or URI) goes to stdout; human
notes go to stderr — so `$(python cli.py dump-taste)` captures just the path.

Optional polish (plan §4): `dump-taste --max-age N` reuses the most recent
data/taste_*.json if it's younger than N minutes, avoiding a redundant API pull.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import taste_profile
from discovery_log import (
    _add_log_add_args,
    _cmd_log_add,
    _cmd_log_artists,
    _cmd_log_recent,
)
from cover_art import _cmd_generate_cover
from genre_map import _cmd_find as _cmd_genre_find
from genre_map import _cmd_neighbors as _cmd_genre_neighbors
from lastfm import _cmd_artist_tags, _cmd_similar_artists, _cmd_similar_tracks
from sensing import _cmd_library_scan, _cmd_now_playing
from tools import _cmd_build_playlist, _cmd_search_verify, _cmd_set_playlist_image


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


def _track_artist_names(track: dict) -> list[str]:
    """Artist names on a track, tolerating both {name:...} dicts and plain strings.

    (Same str-vs-dict shape tolerance as mcp_server._artist_names — a dump can carry
    either, and a mismatch here once crashed taste_snapshot. See tests.)
    """
    return [
        (a if isinstance(a, str) else a.get("name", ""))
        for a in track.get("artists", [])
    ]


def _cmd_taste_snapshot(args) -> int:
    """Print a compact taste summary as JSON — the lean alternative to reading the
    full ~55k-token data/taste_*.json into the session.

    Mirrors mcp_server.taste_snapshot (top long-term artists, top genres, recent
    plays) and adds `known_artists`: the full deduped set of artist names across
    every top-artist term, top tracks, and saved tracks. That set is what the
    discovery filter needs to drop already-known candidates — the bit the bespoke
    per-session one-liners were recomputing. stdout = the JSON; stderr = notes.
    """
    latest = _latest_taste_dump()
    if latest is None:
        print("no taste dump found; run `cli.py dump-taste` first", file=sys.stderr)
        return 1
    d = json.load(open(latest))

    top = d.get("top_artists", {}).get("long_term", [])[:30]
    genres: dict[str, int] = {}
    for a in top:
        for g in a.get("genres", []):
            genres[g] = genres.get(g, 0) + 1
    top_genres = sorted(genres, key=genres.get, reverse=True)[:15]

    recent = [
        f"{t.get('name')} — {', '.join(n for n in _track_artist_names(t) if n)}"
        for t in d.get("recently_played", [])[:15]
    ]

    # Full known-artist set, for filtering candidates down to genuinely-new names.
    known: set[str] = set()
    for term in d.get("top_artists", {}).values():
        known.update(a.get("name", "") for a in term)
    for term in d.get("top_tracks", {}).values():
        for t in term:
            known.update(_track_artist_names(t))
    for t in d.get("saved_tracks", []):
        known.update(_track_artist_names(t))
    known_artists = sorted(n for n in known if n)

    out = {
        "generated_at": d.get("generated_at"),
        "top_artists_long_term": [a.get("name") for a in top],
        "top_genres": top_genres,
        "recently_played": recent,
        "known_artists": known_artists,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(
        f"  from {os.path.basename(latest)} · {len(known_artists)} known artists",
        file=sys.stderr,
    )
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

    ts = sub.add_parser(
        "taste-snapshot",
        help="Print a lean taste summary (+ known-artist filter set) as JSON.",
    )
    ts.set_defaults(func=_cmd_taste_snapshot)

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

    gc = sub.add_parser(
        "generate-cover", help="Generate a square cover image via Pollinations (free)."
    )
    gc.add_argument("prompt", help="Image description (no text/words render well).")
    gc.add_argument("--out", help="Output path (default: a temp .jpg).")
    gc.add_argument("--size", type=int, default=1024, help="Square edge in px.")
    gc.add_argument("--seed", type=int, default=None, help="Seed for reproducibility.")
    gc.set_defaults(func=_cmd_generate_cover)

    spi = sub.add_parser(
        "set-playlist-image", help="Upload a cover image to an existing playlist."
    )
    spi.add_argument("playlist", help="Playlist ID, URI, or URL.")
    spi.add_argument("image", help="Path to an image (auto-converted to JPEG ≤256 KB).")
    spi.set_defaults(func=_cmd_set_playlist_image)

    npc = sub.add_parser("now-playing", help="Print the currently-playing track.")
    npc.set_defaults(func=_cmd_now_playing)

    lsc = sub.add_parser(
        "library-scan", help="Dump saved tracks to data/library_*.json."
    )
    lsc.add_argument("--cap", type=int, default=500, help="Max saved tracks to fetch.")
    lsc.add_argument("--no-write", action="store_true", help="Don't write a JSON dump.")
    lsc.set_defaults(func=_cmd_library_scan)

    sa = sub.add_parser(
        "similar-artists", help="Last.fm artists similar to a seed artist."
    )
    sa.add_argument("artist")
    sa.add_argument("--limit", type=int, default=30)
    sa.set_defaults(func=_cmd_similar_artists)

    st = sub.add_parser(
        "similar-tracks", help="Last.fm tracks similar to a seed track."
    )
    st.add_argument("artist")
    st.add_argument("title")
    st.add_argument("--limit", type=int, default=30)
    st.set_defaults(func=_cmd_similar_tracks)

    at = sub.add_parser("artist-tags", help="Last.fm top crowd tags for an artist.")
    at.add_argument("artist")
    at.add_argument("--limit", type=int, default=10)
    at.set_defaults(func=_cmd_artist_tags)

    gn = sub.add_parser(
        "genre-neighbors",
        help="everynoise's ranked nearby genres for a genre (cached web lookup).",
    )
    gn.add_argument("genre")
    gn.add_argument("--limit", type=int, default=15)
    gn.set_defaults(func=_cmd_genre_neighbors)

    gf = sub.add_parser(
        "genre-find", help="Substring search for an exact everynoise genre name."
    )
    gf.add_argument("query")
    gf.add_argument("--limit", type=int, default=20)
    gf.set_defaults(func=_cmd_genre_find)

    la = sub.add_parser(
        "log-add", help="Record surfaced artist(s)/track(s) in the discovery ledger."
    )
    _add_log_add_args(la)
    la.set_defaults(func=_cmd_log_add)

    lar = sub.add_parser(
        "log-artists", help="Print artists already surfaced (for cross-session dedup)."
    )
    lar.set_defaults(func=_cmd_log_artists)

    lr = sub.add_parser("log-recent", help="Print the most recent ledger entries.")
    lr.add_argument("--limit", type=int, default=20)
    lr.set_defaults(func=_cmd_log_recent)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
