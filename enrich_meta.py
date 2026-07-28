"""Phase 2 Spotify enrichment: batch-fetch track/album/artist metadata.

Reads `data/history_summary.json` (produced by `streaming_history.py history-build`),
collects the distinct track URIs from every Phase 1 section, and enriches them with:

  - Track metadata  (/tracks, 50 ids/req): duration_ms, popularity, album_id, artist info
  - Album metadata  (/albums, 20 ids/req): total_tracks, release_year, cover art URLs,
    and a base64-encoded 64 px thumbnail (capped at 40 albums to keep the page lean)
  - Artist top-tracks (/artists/{id}/top-tracks, ~50 artists): the artist's globally
    most-popular track + its popularity score — the "deep cut" baseline for Phase 3.

Output: `data/track_album_meta.json` — compact, keyed by URI or id:

    {
      "meta": { "fetched_at": "...", "tracks": N, "albums": N, "artists": N },
      "tracks": {
        "spotify:track:XYZ": {
          "duration_ms": 213000,
          "popularity": 54,
          "album_id": "abc",
          "album_name": "Some Album",
          "artist_ids": ["def"],
          "artist_names": ["Some Artist"]
        }, ...
      },
      "albums": {
        "abc": {
          "name": "Some Album",
          "artist": "Some Artist",
          "total_tracks": 12,
          "release_year": 2019,
          "thumb_b64": "...",       # 64 px JPEG base64 (None if fetch failed)
          "image_url": "..."        # 300 px CDN URL for progressive upgrade
        }, ...
      },
      "artists": {
        "def": {
          "name": "Some Artist",
          "max_popularity": 72,
          "top_track_name": "Hit Song"
        }, ...
      }
    }

Disk cache: `.cache_spotify_meta/` — one JSON file per resource id (SHA-1 keyed).
Re-runs fetch only what is missing; a fully-warm cache makes zero network calls.

Forkers without Spotify API access simply never run `enrich-meta`; `build_timeline_data`
stubs gracefully when `data/track_album_meta.json` is absent (same pattern as the
`similarity_edges.json` stub).

CLI use:
    python enrich_meta.py enrich
    python enrich_meta.py enrich --meta-path data/track_album_meta.json

Library use:
    from enrich_meta import enrich
    path = enrich()          # returns str path to the written output file
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import os
import sys
import urllib.request
from typing import Any

from auth import get_client
from name_match import (
    album_core,
    album_similarity,
    artist_key,
    artist_matches,
    normalize,
)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(BASE_DIR, "data", "history_summary.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "track_album_meta.json")
CACHE_DIR = os.path.join(BASE_DIR, ".cache_spotify_meta")

# Use no-scope token (read-only; /tracks and /albums are public catalog endpoints)
ENRICH_SCOPES: list[str] = []

TRACK_BATCH = 50   # Spotify /tracks accepts up to 50 ids
ALBUM_BATCH = 20   # Spotify /albums accepts up to 20 ids
THUMB_CAP = 40     # max albums to download + base64 the 64 px thumbnail
ARTIST_CAP = 50    # max distinct artists to fetch top-tracks for

# Name-search fallback (albums with no Spotify track URI — Apple-Music-only
# listening). A wrong cover is worse than a blank tile, so both gates are hard:
# the candidate's primary artist must be the same act (name_match.artist_matches)
# AND the album-name cores must be at least this similar. 0.87 accepts edition
# noise that survives core-stripping and rejects near-misses like
# "Coming Home (Deluxe)" vs "Coming Home Live" (0.815).
ALBUM_SEARCH_MIN_RATIO = 0.87
ALBUM_SEARCH_LIMIT = 10   # candidates to consider per query
ALBUM_SEARCH_CAP = 25     # max name searches per enrich() run
# How many top albums the crate shows — keep in sync with
# build_timeline_data._build_albums_key(top_n=35). Only these are worth a
# name search, since only these get rendered.
ALBUM_CRATE_N = 35


# ──────────────────────────────────────────────────────────────────────────────
# Cache helpers
# ──────────────────────────────────────────────────────────────────────────────

def _cache_path(resource_type: str, resource_id: str) -> str:
    """Deterministic path: .cache_spotify_meta/<type>/<first2>/<sha1>.json"""
    digest = hashlib.sha1(f"{resource_type}:{resource_id}".encode()).hexdigest()
    return os.path.join(CACHE_DIR, resource_type, digest[:2], f"{digest}.json")


def _cache_read(resource_type: str, resource_id: str) -> dict | None:
    path = _cache_path(resource_type, resource_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _cache_write(resource_type: str, resource_id: str, data: dict) -> None:
    path = _cache_path(resource_type, resource_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


# ──────────────────────────────────────────────────────────────────────────────
# URI collection
# ──────────────────────────────────────────────────────────────────────────────

def _id_from_uri(uri: str) -> str | None:
    """Extract the Spotify id from a URI like spotify:track:XXXX."""
    if uri and uri.startswith("spotify:track:"):
        return uri.split(":")[-1]
    return None


def collect_track_uris(summary: dict) -> list[str]:
    """Return a deduplicated list of Spotify track URIs from all Phase 1 sections."""
    seen: set[str] = set()
    uris: list[str] = []

    def _add(uri: str | None) -> None:
        if uri and uri not in seen:
            seen.add(uri)
            uris.append(uri)

    # 1. track_stories.tracks (top 100 tracks)
    for t in summary.get("track_stories", {}).get("tracks", []):
        _add(t.get("uri"))

    # 2. albums.top_albums — top_track.uri + sample_uri
    for a in summary.get("albums", {}).get("top_albums", []):
        _add((a.get("top_track") or {}).get("uri"))
        _add(a.get("sample_uri"))

    # 3. albums.one_track_wonders — hit_track.uri
    for w in summary.get("albums", {}).get("one_track_wonders", []):
        _add((w.get("hit_track") or {}).get("uri"))

    # 4. per_year_tracks.by_year — top_tracks per year
    by_year = summary.get("per_year_tracks", {}).get("by_year", {})
    for yr_data in by_year.values():
        for t in yr_data.get("top_tracks", []):
            _add(t.get("uri"))

    # 5. yearbook_anthems.anthems
    for a in summary.get("yearbook_anthems", {}).get("anthems", []):
        _add(a.get("uri"))

    return uris


# ──────────────────────────────────────────────────────────────────────────────
# Spotify batch fetches (cache-aware)
# ──────────────────────────────────────────────────────────────────────────────

def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def fetch_tracks(sp, uris: list[str]) -> dict[str, dict]:
    """Fetch track metadata for a list of URIs; returns dict keyed by URI.

    Uses the disk cache: only ids absent from cache hit the API.
    Per track keeps: duration_ms, popularity, album_id, album_name, artist_ids, artist_names.
    """
    result: dict[str, dict] = {}

    # Separate cached vs. missing
    missing_uris: list[str] = []
    for uri in uris:
        tid = _id_from_uri(uri)
        if tid is None:
            continue
        cached = _cache_read("track", tid)
        if cached is not None:
            result[uri] = cached
        else:
            missing_uris.append(uri)

    if not missing_uris:
        return result

    # Batch-fetch missing ids
    missing_ids = [_id_from_uri(u) for u in missing_uris if _id_from_uri(u)]
    for chunk in _chunks(missing_ids, TRACK_BATCH):
        resp = sp.tracks(chunk)
        for track in (resp.get("tracks") or []):
            if not track:
                continue
            tid = track.get("id")
            if not tid:
                continue
            album = track.get("album") or {}
            artists = track.get("artists") or []
            rec = {
                "duration_ms": track.get("duration_ms"),
                "popularity": track.get("popularity"),
                "album_id": album.get("id"),
                "album_name": album.get("name"),
                "artist_ids": [a.get("id") for a in artists if a.get("id")],
                "artist_names": [a.get("name") for a in artists if a.get("name")],
            }
            uri = f"spotify:track:{tid}"
            _cache_write("track", tid, rec)
            result[uri] = rec

    return result


def _pick_image(images: list[dict], target_size: int) -> str | None:
    """Return the CDN URL closest to target_size px (Spotify serves 640/300/64)."""
    if not images:
        return None
    # Exact match first, then nearest by abs difference
    best = min(images, key=lambda im: abs((im.get("width") or 0) - target_size))
    return best.get("url")


def _download_thumb_b64(url: str | None) -> str | None:
    """Download a small image and return its base64 encoding, or None on failure."""
    if not url:
        return None
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "spotify-music-discovery/0.1 (personal)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        return base64.b64encode(data).decode("ascii")
    except Exception:
        return None


def fetch_albums(
    sp, album_ids: list[str], thumb_count: int = 0, refill_thumbs: bool = True
) -> dict[str, dict]:
    """Fetch album metadata for a list of album ids; returns dict keyed by album id.

    Downloads the 64 px thumbnail for the first (THUMB_CAP - thumb_count) albums
    not already caching a thumb; the 300 px URL is always stored for progressive upgrade.

    `refill_thumbs` re-fetches albums whose CACHED record has no `thumb_b64`
    (the thumb cap was hit on an earlier run, or the CDN download failed) while
    budget remains. `album_ids` arrives in display order — crate albums first —
    so the refill spends its budget on the tiles the user actually sees. Without
    this, an album that missed the cap once stayed permanently thumb-less and
    rendered as a letter placeholder until the CDN swap finished.
    """
    result: dict[str, dict] = {}
    missing_ids: list[str] = []
    refill_ids: list[str] = []
    thumb_downloaded = thumb_count

    for idx, aid in enumerate(album_ids):
        cached = _cache_read("album", aid)
        if cached is not None:
            result[aid] = cached
            # Only the leading THUMB_CAP ids are ever rendered as tiles, so only
            # those are worth a refill — this also keeps repeat runs from slowly
            # back-filling a thumbnail for every album ever seen.
            if refill_thumbs and idx < THUMB_CAP and not cached.get("thumb_b64"):
                refill_ids.append(aid)
        else:
            missing_ids.append(aid)

    # Refill first: cached crate albums missing their thumbnail get first claim
    # on the budget, since those are the tiles that render blank.
    budget = max(THUMB_CAP - thumb_downloaded, 0)
    refill_ids = refill_ids[:budget]
    if refill_ids:
        for chunk in _chunks(refill_ids, ALBUM_BATCH):
            try:
                resp = sp.albums(chunk)
            except Exception as e:  # noqa: BLE001 — refill is best-effort
                print(f"  album thumb refill error: {e}", file=sys.stderr)
                continue
            for album in (resp.get("albums") or []):
                if not album:
                    continue
                aid = album.get("id")
                if not aid or aid not in result:
                    continue
                thumb_b64 = _download_thumb_b64(_pick_image(album.get("images") or [], 64))
                if not thumb_b64:
                    continue
                rec = dict(result[aid])
                rec["thumb_b64"] = thumb_b64
                if not rec.get("image_url"):
                    rec["image_url"] = _pick_image(album.get("images") or [], 300)
                _cache_write("album", aid, rec)
                result[aid] = rec
                thumb_downloaded += 1

    if not missing_ids:
        return result

    for chunk in _chunks(missing_ids, ALBUM_BATCH):
        resp = sp.albums(chunk)
        for album in (resp.get("albums") or []):
            if not album:
                continue
            aid = album.get("id")
            if not aid:
                continue
            images = album.get("images") or []
            image_url = _pick_image(images, 300)

            # Download 64 px thumb if under cap (by total thumbs written this run)
            thumb_b64: str | None = None
            if thumb_downloaded < THUMB_CAP:
                thumb_url = _pick_image(images, 64)
                thumb_b64 = _download_thumb_b64(thumb_url)
                if thumb_b64:
                    thumb_downloaded += 1

            artists = album.get("artists") or []
            release_date = album.get("release_date") or ""
            release_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

            rec = {
                "name": album.get("name"),
                "artist": artists[0].get("name") if artists else None,
                "total_tracks": album.get("total_tracks"),
                "release_year": release_year,
                "thumb_b64": thumb_b64,
                "image_url": image_url,
            }
            _cache_write("album", aid, rec)
            result[aid] = rec

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Album-art fallback: resolve an album by NAME when there is no track URI
# ──────────────────────────────────────────────────────────────────────────────

def album_name_key(artist: str | None, name: str | None) -> str:
    """Stable lookup key for the name-search index: `<artist_key>||<normalized name>`.

    `build_timeline_data` recomputes this from the history summary to find the
    album a name search resolved, so both sides MUST use this one function.

    The key normalizes but does NOT strip edition qualifiers: the crate can hold
    both `Coming Home` and `Coming Home (Deluxe)` by the same artist, and those
    are different records that must not collide. (Edition-stripping still happens
    inside the *matching* logic, where it belongs.)
    """
    return f"{artist_key(artist)}||{normalize(name)}"


def _score_album_candidate(
    artist: str, name: str, cand: dict
) -> tuple[bool, float, str]:
    """Judge one Spotify /search album hit. Returns (accepted, ratio, reason)."""
    cand_artists = cand.get("artists") or []
    cand_artist = (cand_artists[0].get("name") if cand_artists else None) or ""
    cand_name = cand.get("name") or ""
    if not artist_matches(artist, cand_artist):
        return False, 0.0, f"artist mismatch (got {cand_artist!r})"
    ratio = album_similarity(name, cand_name)
    if ratio < ALBUM_SEARCH_MIN_RATIO:
        return (
            False,
            ratio,
            f"album name too different (got {cand_name!r}, ratio {ratio:.2f} "
            f"< {ALBUM_SEARCH_MIN_RATIO})",
        )
    return True, ratio, "ok"


def search_album_by_name(sp, artist: str, name: str) -> dict:
    """Find a Spotify album id for (artist, album name) via plain `search`.

    Used for albums the user only ever played on Apple Music: those events carry
    `spotify_track_uri = None` by design, so there is no URI to reach the album
    (and hence its cover art) through. Search needs no OAuth scope.

    Returns a record that is ALWAYS cached, including the negative case, so a
    miss doesn't re-hit the API on every rebuild:

        {"matched": True, "album_id": ..., "matched_name": ..., "matched_artist": ...,
         "confidence": 0.0-1.0, "query": "...", "reason": "ok"}
        {"matched": False, "reason": "why it was rejected/not found"}

    Low confidence deliberately yields a MISS (blank tile) rather than a guess —
    a wrong cover is worse than no cover.
    """
    key = album_name_key(artist, name)
    cached = _cache_read("album_search", key)
    if cached is not None:
        return cached

    core = album_core(name)
    queries = [
        f'album:"{core}" artist:"{artist}"',
        f"{artist} {core}",
    ]
    best: dict | None = None
    best_ratio = 0.0
    rejections: list[str] = []

    for q in queries:
        try:
            res = sp.search(q=q, type="album", limit=ALBUM_SEARCH_LIMIT)
        except Exception as e:  # noqa: BLE001 — one bad query must not kill the run
            rejections.append(f"search error: {e}")
            continue
        items = ((res.get("albums") or {}).get("items")) or []
        for cand in items:
            if not cand:
                continue
            ok, ratio, reason = _score_album_candidate(artist, name, cand)
            if not ok:
                if len(rejections) < 3:
                    rejections.append(reason)
                continue
            if ratio > best_ratio:
                best_ratio = ratio
                cand_artists = cand.get("artists") or []
                best = {
                    "matched": True,
                    "album_id": cand.get("id"),
                    "matched_name": cand.get("name"),
                    "matched_artist": (
                        cand_artists[0].get("name") if cand_artists else None
                    ),
                    "confidence": round(ratio, 3),
                    "query": q,
                    "reason": "ok",
                }
        if best is not None and best_ratio >= 0.999:
            break  # exact core match — no need for the looser query

    rec = best or {
        "matched": False,
        "reason": "; ".join(rejections) or "no album search results",
    }
    _cache_write("album_search", key, rec)
    return rec


def resolve_albums_by_name(
    sp, wanted: list[tuple[str, str]], cap: int = ALBUM_SEARCH_CAP
) -> dict[str, dict]:
    """Run `search_album_by_name` over (artist, album) pairs lacking a URI.

    Returns `{album_name_key: record}` for every pair attempted — matched and
    unmatched alike, so the output file records *why* a tile stayed blank.
    """
    out: dict[str, dict] = {}
    for artist, name in wanted[:cap]:
        key = album_name_key(artist, name)
        if key in out:
            continue
        rec = search_album_by_name(sp, artist, name)
        rec = dict(rec)
        rec["artist"] = artist
        rec["album"] = name
        out[key] = rec
    return out


def fetch_artist_top_tracks(sp, artist_ids: list[str]) -> dict[str, dict]:
    """Fetch each artist's most-popular track (market=US); returns dict keyed by artist id.

    This is the deep-cut baseline: compare the user's #1 track popularity vs the
    artist's globally most popular track. Capped at ARTIST_CAP artists.
    """
    result: dict[str, dict] = {}
    for aid in artist_ids[:ARTIST_CAP]:
        cached = _cache_read("artist", aid)
        if cached is not None:
            result[aid] = cached
            continue
        try:
            resp = sp.artist_top_tracks(aid, country="US")
        except Exception as e:
            print(f"  artist top-tracks error for {aid}: {e}", file=sys.stderr)
            continue
        tracks = (resp.get("tracks") or [])
        if not tracks:
            rec = {"name": None, "max_popularity": None, "top_track_name": None}
        else:
            # top-tracks are already sorted by popularity (desc) by Spotify
            top = max(tracks, key=lambda t: t.get("popularity") or 0)
            rec = {
                "name": None,  # filled in from track data
                "max_popularity": top.get("popularity"),
                "top_track_name": top.get("name"),
            }
        _cache_write("artist", aid, rec)
        result[aid] = rec
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Main enrichment entry point
# ──────────────────────────────────────────────────────────────────────────────

def enrich(
    history_path: str = HISTORY_PATH,
    output_path: str = OUTPUT_PATH,
    sp=None,
) -> str:
    """Run the full enrichment pipeline; return the path to the written output file.

    Steps:
      1. Collect distinct track URIs from history_summary.json
      2. Batch-fetch track metadata (duration, popularity, album/artist ids)
      3. Batch-fetch album metadata for unique album ids (cover art, tracklist length)
      4. Fetch artist top-tracks for unique artist ids (deep-cut baseline)
      5. Write data/track_album_meta.json

    All three fetch steps are cache-aware: a warm cache produces no network calls.
    """
    if not os.path.exists(history_path):
        raise FileNotFoundError(
            f"History summary not found: {history_path}\n"
            "Run `python cli.py history-build` first."
        )

    with open(history_path) as f:
        summary = json.load(f)

    # 1. Collect URIs
    uris = collect_track_uris(summary)
    print(f"  Collected {len(uris)} distinct track URIs", file=sys.stderr)

    # 2. Spotify client (no-scope — /tracks and /albums are catalog endpoints)
    sp = sp or get_client(ENRICH_SCOPES)

    # 3. Fetch track metadata
    print(f"  Fetching track metadata …", file=sys.stderr)
    tracks_data = fetch_tracks(sp, uris)
    print(f"  Got {len(tracks_data)} track records", file=sys.stderr)

    # 4. Collect unique album ids (from tracks + top_albums sample_uris)
    album_ids_ordered: list[str] = []
    seen_albums: set[str] = set()
    for rec in tracks_data.values():
        aid = rec.get("album_id")
        if aid and aid not in seen_albums:
            seen_albums.add(aid)
            album_ids_ordered.append(aid)

    # Prioritise the top_albums order (shelf display) by prepending those album ids
    # We resolve top_album URIs → album_ids via the track records
    top_album_uris = []
    for a in summary.get("albums", {}).get("top_albums", []):
        u = a.get("sample_uri") or (a.get("top_track") or {}).get("uri")
        if u:
            top_album_uris.append(u)
    top_album_ids: list[str] = []
    seen_top: set[str] = set()
    for u in top_album_uris:
        tr = tracks_data.get(u, {})
        aid = tr.get("album_id")
        if aid and aid not in seen_top:
            seen_top.add(aid)
            top_album_ids.append(aid)

    # Final album id list: top albums first, then the rest
    final_album_ids: list[str] = []
    final_seen: set[str] = set()
    for aid in top_album_ids + album_ids_ordered:
        if aid not in final_seen:
            final_seen.add(aid)
            final_album_ids.append(aid)

    print(f"  Fetching album metadata for {len(final_album_ids)} albums …", file=sys.stderr)
    albums_data = fetch_albums(sp, final_album_ids)
    thumb_count = sum(1 for a in albums_data.values() if a.get("thumb_b64"))
    print(f"  Got {len(albums_data)} album records ({thumb_count} thumbs)", file=sys.stderr)

    # 4b. Name-search fallback for albums with no resolvable URI.
    # An album the user only ever played on Apple Music has no
    # `spotify_track_uri` anywhere in the history, so steps 3–4 can never reach
    # it and its crate tile renders blank. Search Spotify by artist + album name
    # instead, under strict artist/name gates (see search_album_by_name).
    unresolved_pairs: list[tuple[str, str]] = []
    for a in summary.get("albums", {}).get("top_albums", [])[:ALBUM_CRATE_N]:
        su = a.get("sample_uri")
        aid = (tracks_data.get(su) or {}).get("album_id") if su else None
        if aid and aid in albums_data:
            continue
        if a.get("artist") and a.get("name"):
            unresolved_pairs.append((a["artist"], a["name"]))

    album_name_lookup: dict[str, dict] = {}
    name_search_ids: set[str] = set()
    if unresolved_pairs:
        print(
            f"  {len(unresolved_pairs)} album(s) have no track URI — "
            f"trying the name-search fallback …",
            file=sys.stderr,
        )
        album_name_lookup = resolve_albums_by_name(sp, unresolved_pairs)
        found_ids = [
            r["album_id"]
            for r in album_name_lookup.values()
            if r.get("matched") and r.get("album_id")
        ]
        if found_ids:
            # Fetch their metadata/art the normal way, now that we have ids.
            extra = fetch_albums(sp, found_ids, thumb_count=thumb_count)
            albums_data.update(extra)
            name_search_ids.update(found_ids)
        n_ok = sum(1 for r in album_name_lookup.values() if r.get("matched"))
        print(
            f"  name search resolved {n_ok}/{len(album_name_lookup)}",
            file=sys.stderr,
        )
        for r in album_name_lookup.values():
            if r.get("matched"):
                print(
                    f"    ✓ {r['artist']} — {r['album']}  →  "
                    f"{r['matched_artist']} — {r['matched_name']} "
                    f"(conf {r['confidence']})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"    ✗ {r['artist']} — {r['album']}: {r['reason']}",
                    file=sys.stderr,
                )

    # Provenance: how each album's art was reached, so a wrong cover is auditable.
    for aid, rec in albums_data.items():
        rec["art_source"] = "name_search" if aid in name_search_ids else "uri"

    # 5. Collect unique artist ids (across all track records, cap at ARTIST_CAP)
    artist_ids_ordered: list[str] = []
    seen_artists: set[str] = set()
    for rec in tracks_data.values():
        for aid in rec.get("artist_ids") or []:
            if aid not in seen_artists:
                seen_artists.add(aid)
                artist_ids_ordered.append(aid)

    artist_ids_to_fetch = artist_ids_ordered[:ARTIST_CAP]
    print(
        f"  Fetching top-tracks for {len(artist_ids_to_fetch)} artists …",
        file=sys.stderr,
    )
    artists_data = fetch_artist_top_tracks(sp, artist_ids_to_fetch)

    # Backfill artist names from track records
    for uri, rec in tracks_data.items():
        for aid, name in zip(rec.get("artist_ids") or [], rec.get("artist_names") or []):
            if aid in artists_data and artists_data[aid].get("name") is None:
                artists_data[aid]["name"] = name

    print(f"  Got {len(artists_data)} artist records", file=sys.stderr)

    # 6. Write output
    output = {
        "meta": {
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "tracks": len(tracks_data),
            "albums": len(albums_data),
            "artists": len(artists_data),
            "albums_via_name_search": len(name_search_ids),
        },
        "tracks": tracks_data,
        "albums": albums_data,
        "artists": artists_data,
        # {album_name_key: record} — every URI-less album we attempted by name,
        # matched or not (with the rejection reason). build_timeline_data reads
        # this to hang cover art off name matches; humans read it to audit them.
        "album_name_lookup": album_name_lookup,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_kb = os.path.getsize(output_path) // 1024
    print(
        f"  Wrote {output_path} ({size_kb} KB) — "
        f"{len(tracks_data)} tracks, {len(albums_data)} albums, {len(artists_data)} artists",
        file=sys.stderr,
    )
    return output_path


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def _cmd_enrich(args) -> int:
    try:
        path = enrich(
            history_path=args.history_path,
            output_path=args.meta_path,
        )
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    except RuntimeError as e:
        # auth errors (SPOTIPY_NONINTERACTIVE, missing creds) surface as RuntimeError
        print(f"Spotify auth error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Enrichment failed: {e}", file=sys.stderr)
        return 1
    print(path)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Spotify enrichment — Phase 2 metadata fetch.")
    sub = p.add_subparsers(dest="cmd", required=True)

    en = sub.add_parser(
        "enrich",
        help="Batch-fetch track/album/artist metadata → data/track_album_meta.json.",
    )
    en.add_argument(
        "--history-path",
        default=HISTORY_PATH,
        help="Path to history_summary.json (default: data/history_summary.json).",
    )
    en.add_argument(
        "--meta-path",
        default=OUTPUT_PATH,
        help="Output path for track_album_meta.json (default: data/track_album_meta.json).",
    )
    en.set_defaults(func=_cmd_enrich)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
