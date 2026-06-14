"""Phase 5 external discovery signal: Last.fm similarity + tags.

Restores the external "what's adjacent to this?" signal that Spotify's deprecated
`related-artists` / `recommendations` endpoints used to provide (see plan §1, §Phase 5).
This stays a DUMB sensing layer: it fetches JSON from Last.fm and returns clean lists.
No recommendation logic lives here — the Claude Code session reasons over these
candidates, consults knowledge/ for a discovery angle, and (mandatory) round-trips
every pick through tools.search_verify before surfacing or adding it. Last.fm's
catalog/name-match quality is uneven, so Spotify search remains the source of truth.

Uses only LASTFM_API_KEY (unauthenticated read methods — getSimilar / getTopTags).
LASTFM_SECRET is for signed write methods (scrobbling) we don't use.

Library use:
    from lastfm import similar_artists, similar_tracks, artist_tags
    sa = similar_artists("Colter Wall")          # [{"name", "match"}]
    st = similar_tracks("Colter Wall", "Sleeping on the Blacktop")
    tg = artist_tags("Colter Wall")              # [{"tag", "count"}]

CLI use:
    python lastfm.py similar-artists "Colter Wall"
    python lastfm.py similar-tracks "Colter Wall" "Sleeping on the Blacktop"
    python lastfm.py artist-tags "Colter Wall"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_ROOT = "https://ws.audioscrobbler.com/2.0/"
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache_lastfm")
CACHE_TTL_S = 7 * 24 * 3600  # similarity/tags are stable; a week-old cache is fine
_MIN_INTERVAL_S = 0.25       # ~4 req/s, comfortably under Last.fm's ~5 req/s limit
_last_call_ts = 0.0


class LastfmError(RuntimeError):
    """Last.fm returned an API error (sent with HTTP 200 + an `error` field)."""


def _cache_path(params: dict) -> str:
    key = json.dumps(params, sort_keys=True)
    digest = hashlib.sha1(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{digest}.json")


def _get(params: dict, use_cache: bool = True) -> dict:
    """Call the Last.fm API (JSON), with disk caching and gentle rate limiting.

    Cache key is the full param set (minus the api_key). Cached responses younger
    than CACHE_TTL_S are returned without a network call.
    """
    global _last_call_ts

    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        raise LastfmError("LASTFM_API_KEY is not set in .env (see .env.example).")

    cache_params = {**params, "format": "json"}
    path = _cache_path(cache_params)
    if use_cache and os.path.exists(path):
        if (time.time() - os.path.getmtime(path)) < CACHE_TTL_S:
            with open(path) as f:
                return json.load(f)

    # gentle client-side rate limit
    delta = time.time() - _last_call_ts
    if delta < _MIN_INTERVAL_S:
        time.sleep(_MIN_INTERVAL_S - delta)

    resp = requests.get(
        API_ROOT,
        params={**cache_params, "api_key": api_key},
        headers={"User-Agent": "spotify-music-discovery/0.1 (personal)"},
        timeout=15,
    )
    _last_call_ts = time.time()
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:  # Last.fm signals API errors in the body, often with HTTP 200
        raise LastfmError(f"Last.fm error {data['error']}: {data.get('message', '')}")

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def _as_list(node):
    """Last.fm collapses single-item collections to a dict; normalize to a list."""
    if node is None:
        return []
    return node if isinstance(node, list) else [node]


def similar_artists(artist: str, limit: int = 30, use_cache: bool = True) -> list[dict]:
    """Artists Last.fm considers similar to `artist`, ranked by match (1.0 = closest).

    Returns [{"name", "match"}]. `autocorrect` fixes minor spelling so a seed pulled
    from a Spotify name still resolves. Empty list if Last.fm knows no neighbors.
    """
    data = _get(
        {"method": "artist.getsimilar", "artist": artist,
         "limit": limit, "autocorrect": 1},
        use_cache=use_cache,
    )
    items = _as_list((data.get("similarartists") or {}).get("artist"))
    out = []
    for it in items:
        try:
            match = float(it.get("match")) if it.get("match") is not None else None
        except (TypeError, ValueError):
            match = None
        out.append({"name": it.get("name"), "match": match})
    return out


def similar_tracks(artist: str, title: str, limit: int = 30,
                   use_cache: bool = True) -> list[dict]:
    """Tracks Last.fm considers similar to `artist - title`, ranked by match.

    Returns [{"artist", "title", "match"}]. Useful as a seed→track candidate source
    (the dead `recommendations` endpoint's job).
    """
    data = _get(
        {"method": "track.getsimilar", "artist": artist, "track": title,
         "limit": limit, "autocorrect": 1},
        use_cache=use_cache,
    )
    items = _as_list((data.get("similartracks") or {}).get("track"))
    out = []
    for it in items:
        try:
            match = float(it.get("match")) if it.get("match") is not None else None
        except (TypeError, ValueError):
            match = None
        out.append({
            "artist": (it.get("artist") or {}).get("name"),
            "title": it.get("name"),
            "match": match,
        })
    return out


def artist_tags(artist: str, limit: int = 10, use_cache: bool = True) -> list[dict]:
    """Top crowd tags for `artist` (genre/mood signal), ranked by `count` (0–100).

    A coarse descriptor to partly replace the dead audio-features endpoint — not a
    feature vector, but enough for the session to reason about register/scene.
    Returns [{"tag", "count"}].
    """
    data = _get(
        {"method": "artist.gettoptags", "artist": artist, "autocorrect": 1},
        use_cache=use_cache,
    )
    items = _as_list((data.get("toptags") or {}).get("tag"))[:limit]
    out = []
    for it in items:
        try:
            count = int(it.get("count")) if it.get("count") is not None else None
        except (TypeError, ValueError):
            count = None
        out.append({"tag": it.get("name"), "count": count})
    return out


# --------------------------------------------------------------------------- CLI


def _cmd_similar_artists(args) -> int:
    rows = similar_artists(args.artist, limit=args.limit)
    if not rows:
        print(f"No similar artists found for {args.artist!r}.", file=sys.stderr)
        return 1
    for r in rows:
        print(r["name"])  # stdout: one artist name per line (pipeable)
    print(f"  {len(rows)} similar artist(s) for {args.artist!r}", file=sys.stderr)
    return 0


def _cmd_similar_tracks(args) -> int:
    rows = similar_tracks(args.artist, args.title, limit=args.limit)
    if not rows:
        print(f"No similar tracks for {args.artist!r} — {args.title!r}.", file=sys.stderr)
        return 1
    for r in rows:
        print(f"{r['artist']}\t{r['title']}")  # stdout: artist<TAB>title per line
    print(f"  {len(rows)} similar track(s) for {args.artist!r} — {args.title!r}",
          file=sys.stderr)
    return 0


def _cmd_artist_tags(args) -> int:
    rows = artist_tags(args.artist, limit=args.limit)
    if not rows:
        print(f"No tags found for {args.artist!r}.", file=sys.stderr)
        return 1
    for r in rows:
        print(f"{r['tag']}\t{r['count']}")  # stdout: tag<TAB>count per line
    print(f"  {len(rows)} tag(s) for {args.artist!r}", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Last.fm discovery signal (Phase 5).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sa = sub.add_parser("similar-artists", help="Artists similar to a seed artist.")
    sa.add_argument("artist")
    sa.add_argument("--limit", type=int, default=30)
    sa.set_defaults(func=_cmd_similar_artists)

    st = sub.add_parser("similar-tracks", help="Tracks similar to a seed track.")
    st.add_argument("artist")
    st.add_argument("title")
    st.add_argument("--limit", type=int, default=30)
    st.set_defaults(func=_cmd_similar_tracks)

    at = sub.add_parser("artist-tags", help="Top crowd tags for an artist.")
    at.add_argument("artist")
    at.add_argument("--limit", type=int, default=10)
    at.set_defaults(func=_cmd_artist_tags)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
