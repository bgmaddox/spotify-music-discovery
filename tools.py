"""Phase 2 acting tools: verify tracks exist, and build playlists.

These are the *primitives* a Claude Code session drives (Mode A). No recommendation
logic lives here — the session reasons about what to recommend; this module only
(a) confirms a proposed track is real via Spotify `search`, and (b) writes a private
playlist from verified URIs. See RECIPES.md for the discovery-ladder workflow.

Design choice (per plan §4 Phase 2): playlists are built with THIS app's own Spotify
credentials via Spotipy, not the Claude Spotify connector — it keeps the whole tool
layer in one auth/codepath (auth.py) and one cache. The connector remains a fallback.

Scopes: one superset (`SCOPES`) covers search + playlist writes so a session re-auths
at most once when it first needs write access, then everything reuses the same token.

Library use:
    from tools import search_verify, build_playlist
    uri = search_verify("Radiohead", "Weird Fishes/Arpeggi")
    url = build_playlist("Ladder 2026-06", [uri])

CLI use:
    python tools.py search-verify "Radiohead" "Weird Fishes/Arpeggi"
    python tools.py build-playlist "My Playlist" --uris-file uris.txt
    python tools.py build-playlist "My Playlist" spotify:track:xxx spotify:track:yyy
"""

from __future__ import annotations

import argparse
import sys

from auth import get_client

# One superset scope set: reads (so a search-only session reuses the Phase 1 cache
# when widened) plus private-playlist writes. First write triggers one re-auth.
SCOPES = [
    "user-top-read",
    "user-read-recently-played",
    "user-library-read",
    "user-read-currently-playing",
    "playlist-modify-private",
    "playlist-modify-public",
]

# Search needs an app token but NO user scope. verify/search default to this empty set
# so a read-only context (e.g. the public MCP server on the Pi) never holds a
# write-capable token just to confirm tracks exist. It's a subset of SCOPES, so a local
# session that also builds playlists still reuses one cached token without re-auth churn.
SEARCH_SCOPES: list[str] = []

ADD_CHUNK = 100  # Spotify caps playlist_add_items at 100 URIs per call


def _best_track(sp, artist: str, title: str) -> dict | None:
    """Return the best-matching Spotify track dict for (artist, title), or None.

    Tries a fielded query first (`track:... artist:...`) for precision, then falls
    back to a loose free-text query so light metadata differences (punctuation,
    remaster suffixes, feat. credits) don't cause false misses.
    """
    queries = [
        f'track:"{title}" artist:"{artist}"',
        f"{artist} {title}",
    ]
    for q in queries:
        try:
            res = sp.search(q=q, type="track", limit=5)
        except Exception as e:  # surface but don't crash a batch of candidates
            print(f"  search error for {q!r}: {e}", file=sys.stderr)
            continue
        items = (res.get("tracks") or {}).get("items") or []
        if items:
            return items[0]
    return None


def search_verify(artist: str, title: str, sp=None) -> str | None:
    """Return a Spotify track URI for (artist, title) if it exists, else None.

    The session MUST call this on every proposed track before surfacing or adding
    it — search is the source of truth, the model is only the idea generator.
    Pass an existing `sp` client to avoid re-creating one per candidate in a loop.
    """
    sp = sp or get_client(SEARCH_SCOPES)
    track = _best_track(sp, artist, title)
    return track.get("uri") if track else None


def verify_detail(artist: str, title: str, sp=None) -> dict | None:
    """Like search_verify but returns match metadata for logging/display.

    Returns {uri, name, artists, album} of the matched track, or None on a miss.
    """
    sp = sp or get_client(SEARCH_SCOPES)
    track = _best_track(sp, artist, title)
    if not track:
        return None
    return {
        "uri": track.get("uri"),
        "name": track.get("name"),
        "artists": ", ".join(a.get("name", "") for a in track.get("artists", [])),
        "album": (track.get("album") or {}).get("name"),
    }


def build_playlist(
    name: str,
    uris: list[str],
    description: str = "",
    public: bool = False,
    sp=None,
) -> str:
    """Create a playlist (private by default) and add the given track URIs.

    Returns the playlist's public Spotify URL. Adds URIs in chunks of 100 to
    respect the API limit. Raises ValueError if `uris` is empty.
    """
    if not uris:
        raise ValueError("build_playlist called with no URIs")
    sp = sp or get_client(SCOPES)
    user_id = sp.current_user()["id"]
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=public,
        description=description,
    )
    for i in range(0, len(uris), ADD_CHUNK):
        sp.playlist_add_items(playlist["id"], uris[i : i + ADD_CHUNK])
    return playlist["external_urls"]["spotify"]


# --------------------------------------------------------------------------- CLI


def _cmd_search_verify(args) -> int:
    detail = verify_detail(args.artist, args.title)
    if detail:
        print(detail["uri"])
        print(
            f"  matched: {detail['name']} — {detail['artists']} ({detail['album']})",
            file=sys.stderr,
        )
        return 0
    print("MISS", file=sys.stderr)
    return 1


def _cmd_build_playlist(args) -> int:
    uris = list(args.uris)
    if args.uris_file:
        with open(args.uris_file) as f:
            uris += [ln.strip() for ln in f if ln.strip()]
    if not uris:
        print("No URIs provided (positional or --uris-file).", file=sys.stderr)
        return 1
    url = build_playlist(
        args.name, uris, description=args.description, public=args.public
    )
    print(url)
    print(f"  added {len(uris)} track(s)", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Spotify acting tools (Phase 2).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sv = sub.add_parser("search-verify", help="Print a track URI if it exists, else MISS.")
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

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
