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
import base64
import io
import sys

from auth import get_client

# One superset scope set: reads (so a search-only session reuses the Phase 1 cache
# when widened) plus private-playlist writes and cover-image upload. First write/upload
# triggers one re-auth, then everything reuses the widened token.
SCOPES = [
    "user-top-read",
    "user-read-recently-played",
    "user-library-read",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-modify-private",
    "playlist-modify-public",
    "ugc-image-upload",
]

# Search needs an app token but NO user scope. verify/search default to this empty set
# so a read-only context (e.g. the public MCP server on the Pi) never holds a
# write-capable token just to confirm tracks exist. It's a subset of SCOPES, so a local
# session that also builds playlists still reuses one cached token without re-auth churn.
SEARCH_SCOPES: list[str] = []

ADD_CHUNK = 100  # Spotify caps playlist_add_items at 100 URIs per call
COVER_MAX_B64 = 256 * 1024  # Spotify caps the base64 cover payload at 256 KB


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


def _encode_cover_jpeg(image_path: str) -> str:
    """Read an image and return a base64 JPEG string within Spotify's 256 KB cap.

    A file that's already a small-enough JPEG is sent as-is. Otherwise (wrong format
    or too large — e.g. a PNG from an image generator) it's re-encoded via Pillow:
    converted to RGB, then stepped down in size/quality until the base64 payload fits.
    """
    with open(image_path, "rb") as f:
        raw = f.read()
    is_jpeg = raw[:3] == b"\xff\xd8\xff"
    b64 = base64.b64encode(raw).decode("ascii")
    if is_jpeg and len(b64) <= COVER_MAX_B64:
        return b64

    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            f"{image_path} is not a JPEG under 256 KB and Pillow isn't installed to "
            "convert it. Run `pip install Pillow`, or pass a small JPEG."
        ) from e

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    for size in (640, 512, 400, 320, 256):
        img.thumbnail((size, size))  # in place, shrink-only — progressively smaller
        for quality in (90, 80, 70, 60, 50):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            if len(b64) <= COVER_MAX_B64:
                return b64
    raise RuntimeError(
        "Could not compress the image under Spotify's 256 KB cover limit."
    )


def set_playlist_image(playlist: str, image_path: str, sp=None) -> None:
    """Upload a cover image to an existing playlist.

    `playlist` may be a Spotify playlist ID, URI, or URL (Spotipy normalizes it).
    The image is encoded/compressed to a JPEG within Spotify's 256 KB base64 cap.
    Requires the `ugc-image-upload` scope (in SCOPES), so the first use re-auths once.
    """
    sp = sp or get_client(SCOPES)
    b64 = _encode_cover_jpeg(image_path)
    sp.playlist_upload_cover_image(playlist, b64)


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


def _cmd_set_playlist_image(args) -> int:
    set_playlist_image(args.playlist, args.image)
    print(args.playlist)
    print(f"  uploaded cover from {args.image}", file=sys.stderr)
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

    spi = sub.add_parser(
        "set-playlist-image", help="Upload a cover image to an existing playlist."
    )
    spi.add_argument("playlist", help="Playlist ID, URI, or URL.")
    spi.add_argument("image", help="Path to an image (auto-converted to JPEG ≤256 KB).")
    spi.set_defaults(func=_cmd_set_playlist_image)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
