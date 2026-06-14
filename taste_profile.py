"""Phase 1 sensing layer: dump the user's Spotify taste data to JSON.

Dumb fetcher — no recommendation logic. Pulls top artists/tracks across all three
time ranges, recently played, and the saved-tracks library, keeping only metadata
that survived Spotify's 2024 deprecations (name, id, popularity, artist genres,
release date, album). NO audio-features.

Run:  python taste_profile.py
Writes: data/taste_<UTC-timestamp>.json
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from auth import get_client

SCOPES = [
    "user-top-read",
    "user-read-recently-played",
    "user-library-read",
]

TIME_RANGES = ("short_term", "medium_term", "long_term")
TOP_LIMIT = 50          # Spotify max per top request
RECENT_LIMIT = 50       # Spotify max for recently-played
SAVED_CAP = 500         # cap on saved tracks pulled
PAGE = 50               # page size for paginated saved tracks

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _artist_record(a: dict) -> dict:
    return {
        "name": a.get("name"),
        "id": a.get("id"),
        "popularity": a.get("popularity"),
        "genres": a.get("genres", []),
    }


def _track_record(t: dict) -> dict:
    album = t.get("album") or {}
    return {
        "name": t.get("name"),
        "id": t.get("id"),
        "popularity": t.get("popularity"),
        "artists": [{"name": ar.get("name"), "id": ar.get("id")} for ar in t.get("artists", [])],
        "album": {
            "name": album.get("name"),
            "id": album.get("id"),
            "release_date": album.get("release_date"),
        },
    }


def fetch_top(sp) -> dict:
    top = {"artists": {}, "tracks": {}}
    for rng in TIME_RANGES:
        artists = sp.current_user_top_artists(limit=TOP_LIMIT, time_range=rng)
        top["artists"][rng] = [_artist_record(a) for a in artists.get("items", [])]
        tracks = sp.current_user_top_tracks(limit=TOP_LIMIT, time_range=rng)
        top["tracks"][rng] = [_track_record(t) for t in tracks.get("items", [])]
    return top


def fetch_recently_played(sp) -> list[dict]:
    resp = sp.current_user_recently_played(limit=RECENT_LIMIT)
    out = []
    for item in resp.get("items", []):
        rec = _track_record(item.get("track", {}))
        rec["played_at"] = item.get("played_at")
        out.append(rec)
    return out


def fetch_saved_tracks(sp, cap: int = SAVED_CAP) -> list[dict]:
    out: list[dict] = []
    offset = 0
    while len(out) < cap:
        resp = sp.current_user_saved_tracks(limit=PAGE, offset=offset)
        items = resp.get("items", [])
        if not items:
            break
        for item in items:
            rec = _track_record(item.get("track", {}))
            rec["added_at"] = item.get("added_at")
            out.append(rec)
        offset += PAGE
        if resp.get("next") is None:
            break
    return out[:cap]


def main() -> None:
    sp = get_client(SCOPES)
    me = sp.current_user()

    profile = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user": {"id": me.get("id"), "display_name": me.get("display_name")},
        "top_artists": {},
        "top_tracks": {},
        "recently_played": [],
        "saved_tracks": [],
    }

    top = fetch_top(sp)
    profile["top_artists"] = top["artists"]
    profile["top_tracks"] = top["tracks"]
    profile["recently_played"] = fetch_recently_played(sp)
    profile["saved_tracks"] = fetch_saved_tracks(sp)

    os.makedirs(DATA_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(DATA_DIR, f"taste_{stamp}.json")
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"Wrote {path}")
    print(
        "Summary: "
        f"top_artists.long_term={len(profile['top_artists'].get('long_term', []))}, "
        f"top_tracks.long_term={len(profile['top_tracks'].get('long_term', []))}, "
        f"recently_played={len(profile['recently_played'])}, "
        f"saved_tracks={len(profile['saved_tracks'])}"
    )


if __name__ == "__main__":
    main()
