"""Merge the three history layers into a viz-ready taste-timeline JSON.

Combines:
  1. data/history_summary.json  — GDPR Spotify streaming history (2015–2026)
  2. data/itunes_history.json   — iTunes library snapshot (2013–14 era block)
  3. data/taste_*.json (newest) — Spotify taste dump for the 2026 "now" panel

Last.fm artist_tags() provides genre enrichment; results are disk-cached in
.cache_lastfm/ (7-day TTL) so repeated builds are cheap.

Output: data/taste_timeline.json  (target < 250 KB)

    python cli.py timeline-build       # build / rebuild the timeline JSON
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

import taste_profile
from lastfm import LastfmError, artist_tags

# ------------------------------------------------------------------ paths

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HISTORY_SUMMARY_PATH = os.path.join(DATA_DIR, "history_summary.json")
ITUNES_PATH = os.path.join(DATA_DIR, "itunes_history.json")
TIMELINE_PATH = os.path.join(DATA_DIR, "taste_timeline.json")
DISCOVERY_LOG_PATH = os.path.join(DATA_DIR, "discovery_log.jsonl")
SIMILARITY_EDGES_PATH = os.path.join(DATA_DIR, "similarity_edges.json")
TRACK_ALBUM_META_PATH = os.path.join(DATA_DIR, "track_album_meta.json")

# A year with fewer plays than this across ALL imported services is reported as
# "sparse" rather than drawn as a real year. Data-driven, so a later export that
# fills a thin year silently promotes it.
SPARSE_PLAYS_THRESHOLD = 200

# ------------------------------------------------------------------ genre buckets

# Maps messy Last.fm tag strings (lowercased) → canonical bucket names.
# Lives in config/tag_buckets.json so a new user can re-seed it for their own
# genre clusters without touching code. Order matters: longer / more-specific
# entries must appear before shorter ones so the first match wins when a tag
# could satisfy multiple patterns (JSON object order is preserved on load).
TAG_BUCKETS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config", "tag_buckets.json"
)


def _load_tag_buckets(path: str = TAG_BUCKETS_PATH) -> dict[str, str]:
    try:
        with open(path, encoding="utf-8") as f:
            return {str(k): str(v) for k, v in json.load(f).items()}
    except FileNotFoundError:
        print(
            f"warning: {path} not found — all tags will fall through to 'other'",
            file=sys.stderr,
        )
        return {}


TAG_BUCKETS: dict[str, str] = _load_tag_buckets()

# iTunes genre strings → canonical buckets (direct label match, case-insensitive).
ITUNES_GENRE_MAP: dict[str, str] = {
    "bluegrass": "folk/americana",
    "folk": "folk/americana",
    "americana": "folk/americana",
    "country": "country",
    "hip hop": "hip hop",
    "hip hop/rap": "hip hop",
    "hip-hop": "hip hop",
    "rap": "hip hop",
    "rock": "classic rock",
    "alternative & punk": "metal/punk",
    "alternative": "indie rock",
    "pop": "pop",
    "r&b/soul": "soul/blues",
    "r&b": "soul/blues",
    "soul": "soul/blues",
    "jazz": "jazz",
    "blues": "soul/blues",
    "electronic": "electronic",
    "dance": "electronic",
    "metal": "metal/punk",
    "punk": "metal/punk",
    "classical": "soundtrack",
    "soundtrack": "soundtrack",
    "children's music": "kids/household",
    "children": "kids/household",
    "mashup": "electronic",
    "unknown genre": "other",
}

# HOUSEHOLD_ARTISTS, _WHITE_NOISE_RE re-exported from household.py for backward
# compatibility with tests and any external importers.
# household.py is the canonical source; edit there, not here.
from household import HOUSEHOLD_ARTISTS, _WHITE_NOISE_RE  # noqa: F401  (re-export)

# ------------------------------------------------------------------ helpers


def _is_household(name: str) -> bool:
    """True when an artist name is in the household set or matches white-noise pattern."""
    from household import is_household
    return is_household(name)


def _tag_to_bucket(tag: str) -> str | None:
    """Map a single Last.fm tag string to a canonical bucket, or None if unmapped."""
    lower = tag.lower().strip()
    if not lower:
        return None
    # exact match first
    if lower in TAG_BUCKETS:
        return TAG_BUCKETS[lower]
    # substring match (e.g. "indie-folk" matches "indie folk" key via substring)
    for key, bucket in TAG_BUCKETS.items():
        if key in lower or lower in key:
            return bucket
    return None


def resolve_bucket(
    artist_name: str,
    fetch_tags_fn=None,
    *,
    verbose: bool = False,
) -> str:
    """Return the canonical genre bucket for an artist.

    Order of precedence:
      1. household override (always wins)
      2. highest-count Last.fm tag that maps to a known bucket
      3. "other" fallback

    `fetch_tags_fn` must match the signature of `lastfm.artist_tags(name)` and
    return [{tag, count}]. Defaults to the real `artist_tags`. Pass a stub for tests.
    """
    if _is_household(artist_name):
        return "kids/household"

    if fetch_tags_fn is None:
        fetch_tags_fn = artist_tags

    try:
        tags = fetch_tags_fn(artist_name)
    except LastfmError:
        tags = []
    except Exception:
        tags = []

    for item in tags:  # already sorted by count desc from Last.fm
        tag = item.get("tag") or ""
        bucket = _tag_to_bucket(tag)
        if bucket is not None:
            if verbose:
                print(f"  {artist_name}: {tag!r} → {bucket}", file=sys.stderr)
            return bucket

    return "other"


def _collect_unique_artists(summary: dict, itunes: dict) -> list[str]:
    """Deduplicated list of artist names from all sources."""
    seen: set[str] = set()
    out: list[str] = []

    def _add(name: str):
        if name and name not in seen:
            seen.add(name)
            out.append(name)

    for a in summary.get("all_time_artists", []):
        _add(a["name"])
    for year_d in summary.get("per_year", {}).values():
        for a in year_d.get("top_artists", []):
            _add(a["name"])
    for a in itunes.get("top_artists_by_plays", []):
        _add(a["artist"])

    return out


def _map_itunes_genres(itunes: dict) -> list[dict]:
    """Convert iTunes top_genres_by_plays into canonical-bucket totals."""
    out = []
    for g in itunes.get("top_genres_by_plays", []):
        genre = g.get("genre", "")
        plays = g.get("plays", 0)
        bucket = ITUNES_GENRE_MAP.get(genre.lower(), None)
        if bucket is None:
            # try partial-key match
            for key, val in ITUNES_GENRE_MAP.items():
                if key in genre.lower():
                    bucket = val
                    break
        out.append({"genre": genre, "plays": plays, "bucket": bucket or "other"})
    return out


def _latest_taste_dump() -> str | None:
    """Newest data/taste_*.json path, or None."""
    # Timestamped dumps only (taste_20260614T043631Z.json) — the bare taste_*.json
    # glob would also match this module's own output, taste_timeline.json.
    paths = [
        p
        for p in glob.glob(os.path.join(taste_profile.DATA_DIR, "taste_*.json"))
        if re.search(r"taste_\d{8}T\d{6}Z\.json$", p)
    ]
    return max(paths, key=os.path.getmtime) if paths else None


def _load_now_panel() -> dict:
    """Extract the 2026 'now' panel from the newest taste dump.

    Returns a minimal dict — enough for the viz without pulling 55k tokens.
    """
    path = _latest_taste_dump()
    if path is None:
        return {"error": "no taste dump found; run `cli.py dump-taste` first"}

    with open(path) as f:
        d = json.load(f)

    top = d.get("top_artists", {}).get("long_term", [])[:30]
    genres: dict[str, int] = {}
    for a in top:
        for g in a.get("genres", []):
            genres[g] = genres.get(g, 0) + 1

    return {
        "dump_path": os.path.basename(path),
        "generated_at": d.get("generated_at"),
        "top_artists_long_term": [a.get("name") for a in top],
        "top_genres": sorted(genres, key=genres.get, reverse=True)[:15],
    }


def _compute_genre_waves(
    per_year: dict,
    artist_buckets: dict[str, str],
) -> dict[str, dict[str, int]]:
    """Per-year play totals per canonical bucket.

    Weights each year's top-artist plays by that artist's resolved bucket.
    Artists not in artist_buckets fall to "other".
    """
    waves: dict[str, dict[str, int]] = {}
    for year, yd in per_year.items():
        bucket_plays: dict[str, int] = {}
        for a in yd.get("top_artists", []):
            bucket = artist_buckets.get(a["name"], "other")
            bucket_plays[bucket] = bucket_plays.get(bucket, 0) + a["plays"]
        waves[year] = bucket_plays
    return waves


# ------------------------------------------------------------------ v3 behavior helpers


def _build_behavior_clock(clock: dict) -> dict:
    """Clock grids compacted to 7×24 count arrays (rows=weekday Mon–Sun, cols=hour).

    The summary stores each grid as a list of {wd, h, n} cells — ~4× heavier in the
    embedded JSON than a plain nested array. The front end only needs the counts.
    """
    grids_out: dict[str, list[list[int]]] = {}
    for era, cells in clock.get("data", {}).items():
        grid = [[0] * 24 for _ in range(7)]
        for c in cells:
            wd, h = c.get("wd"), c.get("h")
            if isinstance(wd, int) and isinstance(h, int) and 0 <= wd < 7 and 0 <= h < 24:
                grid[wd][h] = c.get("n", 0)
        grids_out[era] = grid
    return {
        "eras": clock.get("eras", []),
        "rows": "weekday 0=Mon..6=Sun; cols hour 0-23 (America/New_York)",
        "grids": grids_out,
    }


def _build_behavior_intentionality(intentionality: dict) -> dict:
    """Per-year deliberate/passive/shuffle/other counts (drop reason_start_counts)."""
    by_year_out: dict[str, dict] = {}
    for year, yd in intentionality.get("by_year", {}).items():
        by_year_out[year] = {
            "deliberate": yd.get("deliberate", 0),
            "passive": yd.get("passive", 0),
            "shuffle": yd.get("shuffle", 0),
            "other": yd.get("other", 0),
            "total": yd.get("total", 0),
        }
    return {"by_year": by_year_out}


def _build_behavior_seasonality(
    seasonality: dict,
    artist_buckets: dict[str, str],
) -> dict:
    """Genre-bucketed seasonality: month (1–12) × bucket play weights + plain totals.

    Uses the summary's artist_by_month slice (top-200 artists, household-excluded).
    Artists not in artist_buckets fall to "other" (same fallback as genre_waves).
    """
    # Plain month totals: sum across all years from by_year
    month_totals: dict[int, int] = {m: 0 for m in range(1, 13)}
    for year_data in seasonality.get("by_year", {}).values():
        for month_str, plays in year_data.items():
            try:
                m = int(month_str)
                month_totals[m] = month_totals.get(m, 0) + plays
            except ValueError:
                pass

    # Genre-bucketed month weights from artist_by_month
    # Structure: {year: {month_str: {artist: plays}}}
    bucket_by_month: dict[int, dict[str, int]] = {m: {} for m in range(1, 13)}
    for year_data in seasonality.get("artist_by_month", {}).values():
        for month_str, artist_plays in year_data.items():
            try:
                m = int(month_str)
            except ValueError:
                continue
            for artist, plays in artist_plays.items():
                bucket = artist_buckets.get(artist, "other")
                bucket_by_month[m][bucket] = bucket_by_month[m].get(bucket, 0) + plays

    return {
        "month_totals": {str(m): month_totals[m] for m in range(1, 13)},
        "bucket_by_month": {str(m): bucket_by_month[m] for m in range(1, 13)},
    }


def _build_behavior_platforms(platforms: dict) -> dict:
    """Per-year platform bucket totals (drop platform_map — audit data)."""
    by_year_out: dict[str, dict] = {}
    for year, yd in platforms.get("by_year", {}).items():
        by_year_out[year] = dict(yd)
    return {"by_year": by_year_out}


def _build_behavior_skip(
    artist_skip: dict,
    artist_buckets: dict[str, str],
) -> dict:
    """Derived skip lists + per-year skip series.

    never_skip  — top 15 lowest skip_rate (exposure guard applied by summary)
    most_skipped — top 15 highest skip_rate
    per_year    — summary's existing per-year skip totals

    Each list entry: {name, plays, skips, skip_rate, bucket}.
    The exposure guard (plays+skips >= threshold) is already applied in the summary.
    """
    guard = artist_skip.get("exposure_guard", 20)
    artists = [
        a for a in artist_skip.get("artists", [])
        if (a.get("plays", 0) + a.get("skips", 0)) >= guard
    ]

    def _entry(a: dict) -> dict:
        return {
            "name": a["name"],
            "plays": a["plays"],
            "skips": a["skips"],
            "skip_rate": a["skip_rate"],
            "bucket": artist_buckets.get(a["name"], "other"),
        }

    by_skip_rate = sorted(artists, key=lambda a: a["skip_rate"])
    never_skip = [_entry(a) for a in by_skip_rate[:15]]
    most_skipped = [_entry(a) for a in reversed(by_skip_rate[-15:])]

    return {
        "exposure_guard": guard,
        "never_skip": never_skip,
        "most_skipped": most_skipped,
    }


def _build_behavior_obsessions(obsession_episodes: dict, cap: int = 30) -> list:
    """Pass-through obsession episodes, capped at `cap`."""
    episodes = obsession_episodes.get("episodes", [])
    # Sort by plays descending (intensity), then cap
    episodes_sorted = sorted(episodes, key=lambda e: e.get("plays", 0), reverse=True)
    return episodes_sorted[:cap]


def _build_behavior_rediscoveries(rediscoveries: dict, cap: int = 25) -> list:
    """Pass-through rediscovery artists, capped at `cap` by total plays."""
    artists = rediscoveries.get("artists", [])
    artists_sorted = sorted(
        artists, key=lambda a: a.get("total_plays", 0), reverse=True
    )
    return artists_sorted[:cap]


# ------------------------------------------------------------------ v3 loyalty (V6)


def _build_loyalty(
    all_time_artists: list[dict],
    artist_buckets: dict[str, str],
    top_n: int = 120,
) -> list[dict]:
    """V6 loyalty spans derived from all_time_artists[].by_year trajectories.

    For the top `top_n` artists by total plays: first_year, last_year,
    active_years (count of years with plays), total plays, bucket, still_active
    (plays in 2025 or 2026). Household artists are included (they have spans too).
    Sorted by first_year ascending, then plays descending.
    """
    # Take top N by plays
    top_artists = sorted(
        all_time_artists, key=lambda a: a.get("plays", 0), reverse=True
    )[:top_n]

    out: list[dict] = []
    for a in top_artists:
        by_year = a.get("by_year", {})
        if not by_year:
            continue
        years_with_plays = [int(y) for y, p in by_year.items() if p > 0]
        if not years_with_plays:
            continue
        first_year = min(years_with_plays)
        last_year = max(years_with_plays)
        active_years = len(years_with_plays)
        still_active = any(int(y) in (2025, 2026) for y, p in by_year.items() if p > 0)
        out.append(
            {
                "name": a["name"],
                "bucket": artist_buckets.get(a["name"], "other"),
                "first_year": first_year,
                "last_year": last_year,
                "active_years": active_years,
                "plays": a["plays"],
                "still_active": still_active,
                "household": _is_household(a["name"]),
            }
        )

    # Sort by first_year asc, then plays desc
    out.sort(key=lambda x: (x["first_year"], -x["plays"]))
    return out


# ------------------------------------------------------------------ v3 discovery (V8)


def _build_discovery(
    log_path: str,
    all_time_artists: list[dict],
    taste_dump_path: str | None,
    artist_buckets: dict[str, str],
) -> dict:
    """V8 discovery overlay derived from the discovery ledger.

    Parses discovery_log.jsonl; dedupes by artist (keeps earliest date).
    `stuck` = True when the artist appears in the streaming history all_time_artists
    OR in the taste dump's known/top artists.
    Malformed lines are silently skipped.
    """
    # Build the "known" set from streaming history
    known_from_history: set[str] = {
        a["name"].lower() for a in all_time_artists if a.get("name")
    }

    # Build from taste dump
    known_from_taste: set[str] = set()
    if taste_dump_path and os.path.exists(taste_dump_path):
        try:
            with open(taste_dump_path) as f:
                taste = json.load(f)
            for tier in taste.get("top_artists", {}).values():
                for a in tier:
                    if a.get("name"):
                        known_from_taste.add(a["name"].lower())
            # saved_tracks / recently_played carry artist names too — the raw dump
            # has no precomputed known_artists key (that's a taste-snapshot derivation)
            for section in ("saved_tracks", "recently_played"):
                for t in taste.get(section, []):
                    for a in t.get("artists", []) or []:
                        if isinstance(a, dict) and a.get("name"):
                            known_from_taste.add(a["name"].lower())
        except Exception:
            pass  # non-fatal

    all_known = known_from_history | known_from_taste

    # Parse ledger — dedupe by artist keeping earliest ts
    if not os.path.exists(log_path):
        events: list[dict] = []
    else:
        earliest: dict[str, dict] = {}  # lower(artist) → record
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue  # malformed — skip
                artist = rec.get("artist")
                if not artist:
                    continue
                key = artist.lower()
                existing = earliest.get(key)
                if existing is None or rec.get("ts", "") < existing.get("ts", ""):
                    earliest[key] = rec

        events = []
        for key, rec in sorted(earliest.items(), key=lambda x: x[1].get("ts", "")):
            artist = rec["artist"]
            entry: dict = {
                "date": rec.get("ts", "")[:10],
                "artist": artist,
                "bucket": artist_buckets.get(artist, "other"),
                "stuck": key in all_known,
            }
            if rec.get("playlist"):
                # store only the playlist id — the URL prefix is constant and the
                # 194-event list is embedded in the page
                entry["playlist"] = rec["playlist"].rstrip("/").rsplit("/", 1)[-1]
            if rec.get("recipe"):
                entry["recipe"] = rec["recipe"]
            events.append(entry)

    stuck_count = sum(1 for e in events if e["stuck"])
    return {
        "note": (
            "Discovery ledger starts mid-2026 (~3 weeks of data). "
            "'stuck' = artist found in streaming history or taste dump after being surfaced."
        ),
        "events": events,
        "total": len(events),
        "stuck_count": stuck_count,
    }


# ------------------------------------------------------------------ Phase 3 merge helpers


def _load_track_album_meta(path: str) -> dict | None:
    """Load enrichment file; return None when absent (forker / not-yet-enriched path)."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _build_albums_key(summary: dict, meta: dict | None, top_n: int = 35) -> dict:
    """Merge Phase 1 album aggregates with Phase 2 enrichment.

    Returns `albums` timeline key:
      enriched: bool — whether meta was available
      top_albums: list of up to `top_n` records, sorted by plays desc:
        name, artist, plays, by_year, session_count, top_track,
        release_year (null without meta), total_tracks (null without meta),
        completion (fraction 0-1 or null), thumb_b64 (null without meta),
        image_url (null without meta)
      session_score: {total, by_year} — album-session totals
      session_albums: list of {album, artist} listened front-to-back
      one_track_wonders: list of {album, artist, hit_track, rest_plays,
        image_url (null without meta), thumb_b64 (null without meta)}

    Completion is the fraction of the official tracklist that the user has played
    at least once, computed from the top-100 track_stories URIs via enrichment.
    Because track_stories only covers the top 100 tracks, completion is a lower-bound
    estimate for high-play albums and may be null when total_tracks is absent.
    """
    raw_albums = summary.get("albums", {})
    top_albums_raw = raw_albums.get("top_albums", [])[:top_n]
    album_sessions = raw_albums.get("album_sessions", {})
    one_track_wonders_raw = raw_albums.get("one_track_wonders", [])

    # Build URI→album_id lookup from enrichment (for completion + art)
    uri_to_meta: dict[str, dict] = {}  # uri → track meta record
    album_id_to_meta: dict[str, dict] = {}  # album_id → album meta record

    if meta is not None:
        uri_to_meta = meta.get("tracks", {})
        album_id_to_meta = meta.get("albums", {})

    # Build album_id → set of distinct played URIs (from track_stories)
    album_played_uris: dict[str, set[str]] = {}
    for t in summary.get("track_stories", {}).get("tracks", []):
        uri = t.get("uri")
        if uri and uri in uri_to_meta:
            aid = uri_to_meta[uri].get("album_id")
            if aid:
                album_played_uris.setdefault(aid, set()).add(uri)

    # Build enriched top_albums list
    top_albums_out = []
    for alb in top_albums_raw:
        sample_uri = alb.get("sample_uri")
        album_id = None
        alb_enrichment: dict = {}

        if meta is not None and sample_uri and sample_uri in uri_to_meta:
            album_id = uri_to_meta[sample_uri].get("album_id")
            if album_id and album_id in album_id_to_meta:
                alb_enrichment = album_id_to_meta[album_id]

        # Completion: distinct played URIs ÷ total_tracks
        total_tracks = alb_enrichment.get("total_tracks") if alb_enrichment else None
        played_count = len(album_played_uris.get(album_id, set())) if album_id else 0
        completion: float | None = (
            round(played_count / total_tracks, 3)
            if (total_tracks and total_tracks > 0 and meta is not None)
            else None
        )

        top_albums_out.append(
            {
                "name": alb["name"],
                "artist": alb["artist"],
                "plays": alb["plays"],
                "by_year": alb.get("by_year", {}),
                "session_count": alb.get("session_count", 0),
                "top_track": alb.get("top_track"),
                "release_year": alb_enrichment.get("release_year"),
                "total_tracks": total_tracks,
                "completion": completion,
                "thumb_b64": alb_enrichment.get("thumb_b64"),
                "image_url": alb_enrichment.get("image_url"),
            }
        )

    # Enrich one-track wonders with art from the hit_track URI
    wonders_out = []
    for w in one_track_wonders_raw:
        hit_uri = w.get("hit_track", {}).get("uri")
        wonder_enrichment: dict = {}
        if meta is not None and hit_uri and hit_uri in uri_to_meta:
            hit_album_id = uri_to_meta[hit_uri].get("album_id")
            if hit_album_id and hit_album_id in album_id_to_meta:
                wonder_enrichment = album_id_to_meta[hit_album_id]
        wonders_out.append(
            {
                "album": w["album"],
                "artist": w["artist"],
                "hit_track": w["hit_track"],
                "rest_plays": w.get("rest_plays", 0),
                "image_url": wonder_enrichment.get("image_url"),
                "thumb_b64": wonder_enrichment.get("thumb_b64"),
            }
        )

    return {
        "enriched": meta is not None,
        "top_albums": top_albums_out,
        "session_score": {
            "total": album_sessions.get("total_sessions", 0),
            "by_year": album_sessions.get("by_year", {}),
        },
        "session_albums": album_sessions.get("session_albums", []),
        "one_track_wonders": wonders_out,
    }


def _build_track_stories_key(summary: dict, meta: dict | None) -> dict:
    """Merge Phase 1 track lifelines with Phase 2 enrichment.

    Returns `track_stories` timeline key:
      enriched: bool
      tracks: top-100 list, each:
        artist, title, uri, plays, ms_played,
        lifeline: [[YYYY-MM, count], ...] sparse monthly array,
        first_play: YYYY-MM-DD, last_play: YYYY-MM-DD,
        devotion_years: int, year_span: [first, last],
        duration_ms (null without meta), popularity (null without meta)
      seasons: list from track_seasons (pass-through, already household-excluded)
    """
    raw_tracks = summary.get("track_stories", {}).get("tracks", [])
    uri_to_meta: dict[str, dict] = {}
    if meta is not None:
        uri_to_meta = meta.get("tracks", {})

    tracks_out = []
    for t in raw_tracks:
        uri = t.get("uri")
        t_enrichment = uri_to_meta.get(uri, {}) if (meta is not None and uri) else {}
        tracks_out.append(
            {
                "artist": t["artist"],
                "title": t["title"],
                "uri": uri,
                "plays": t["plays"],
                "ms_played": t["ms_played"],
                "lifeline": t.get("lifeline", []),
                "first_play": t.get("first_play"),
                "last_play": t.get("last_play"),
                "devotion_years": t.get("devotion_years", 0),
                "year_span": t.get("year_span", []),
                "duration_ms": t_enrichment.get("duration_ms"),
                "popularity": t_enrichment.get("popularity"),
            }
        )

    # Pass-through track_seasons (already household-excluded in Phase 1)
    seasons = summary.get("track_seasons", {}).get("tracks", [])

    return {
        "enriched": meta is not None,
        "tracks": tracks_out,
        "seasons": seasons,
    }


def _build_lists_key(summary: dict, meta: dict | None) -> dict:
    """Compute the fun-lists payload (Phase 1 + Phase 2 combined).

    Returns `lists` timeline key:
      receipt: {YYYY: {top_tracks: [{artist,title,uri,plays}], total_hours, total_skips}}
        — straight from per_year_tracks, top 15 tracks per year
      milestones: top-20 tracks by total ms_played, each:
        artist, title, uri, ms_played, hours_played,
        duration_ms (null without meta), estimated_plays_hours (null without meta)
      anthems: [{year, artist, title, uri, plays, concentration,
        duration_ms (null), popularity (null)}]
      deep_cuts: {
        enriched: bool,
        contrarian_score: float (fraction) or null,
        items: [{artist, user_track, user_uri, user_popularity,
                 artist_top_track, artist_max_popularity, diff, is_deep_cut}]
      }
    """
    uri_to_meta: dict[str, dict] = {}
    artist_id_to_meta: dict[str, dict] = {}
    if meta is not None:
        uri_to_meta = meta.get("tracks", {})
        artist_id_to_meta = meta.get("artists", {})

    # --- receipt ---
    receipt: dict[str, dict] = {}
    for year, yd in summary.get("per_year_tracks", {}).get("by_year", {}).items():
        receipt[year] = {
            "top_tracks": yd.get("top_tracks", []),
            "total_hours": yd.get("total_hours", 0.0),
            "total_skips": yd.get("total_skips", 0),
        }

    # --- milestones: top 20 by ms_played ---
    raw_tracks = summary.get("track_stories", {}).get("tracks", [])
    milestones_sorted = sorted(
        raw_tracks, key=lambda t: t.get("ms_played", 0), reverse=True
    )[:20]

    milestones_out = []
    for t in milestones_sorted:
        uri = t.get("uri")
        t_enrichment = uri_to_meta.get(uri, {}) if (meta is not None and uri) else {}
        dur = t_enrichment.get("duration_ms")
        hours_played = t.get("ms_played", 0) / 3_600_000
        # plays × duration gives the "should-have-been" hours if listened front-to-back
        estimated_plays_hours = (
            round(t.get("plays", 0) * dur / 3_600_000, 2) if dur else None
        )
        milestones_out.append(
            {
                "artist": t["artist"],
                "title": t["title"],
                "uri": uri,
                "ms_played": t.get("ms_played", 0),
                "hours_played": round(hours_played, 2),
                "duration_ms": dur,
                "estimated_plays_hours": estimated_plays_hours,
            }
        )

    # --- anthems: pass-through, join with enrichment ---
    anthems_raw = summary.get("yearbook_anthems", {}).get("anthems", [])
    anthems_out = []
    for a in anthems_raw:
        uri = a.get("uri")
        t_enrichment = uri_to_meta.get(uri, {}) if (meta is not None and uri) else {}
        anthems_out.append(
            {
                "year": a["year"],
                "artist": a["artist"],
                "title": a["title"],
                "uri": uri,
                "plays": a.get("plays", 0),
                "concentration": a.get("concentration"),
                "duration_ms": t_enrichment.get("duration_ms"),
                "popularity": t_enrichment.get("popularity"),
            }
        )

    # --- deep cuts ---
    deep_cuts_items: list[dict] = []
    if meta is not None:
        # Build per-artist best track (most played) from track_stories
        artist_best: dict[str, dict] = {}
        for t in raw_tracks:
            art = t["artist"]
            if art not in artist_best or t["plays"] > artist_best[art]["plays"]:
                artist_best[art] = t

        artists_with_data = 0
        deep_cut_count = 0
        seen_artist_ids: set[str] = set()

        for artist, track in artist_best.items():
            uri = track.get("uri")
            if not uri or uri not in uri_to_meta:
                continue
            track_meta = uri_to_meta[uri]
            user_pop = track_meta.get("popularity")
            if user_pop is None:
                continue

            # Resolve artist-level meta via artist_ids on the track
            for aid in track_meta.get("artist_ids", []):
                if aid in seen_artist_ids or aid not in artist_id_to_meta:
                    continue
                seen_artist_ids.add(aid)
                art_meta = artist_id_to_meta[aid]
                art_max = art_meta.get("max_popularity")
                top_track_name = art_meta.get("top_track_name")
                if art_max is None:
                    continue

                artists_with_data += 1
                diff = art_max - user_pop
                is_deep_cut = diff >= 15 and track["title"] != top_track_name
                if is_deep_cut:
                    deep_cut_count += 1

                deep_cuts_items.append(
                    {
                        "artist": artist,
                        "user_track": track["title"],
                        "user_uri": uri,
                        "user_popularity": user_pop,
                        "artist_top_track": top_track_name,
                        "artist_max_popularity": art_max,
                        "diff": diff,
                        "is_deep_cut": is_deep_cut,
                    }
                )
                break  # one artist-level entry per track

        # Sort: deep cuts first, then by diff desc
        deep_cuts_items.sort(key=lambda x: (-int(x["is_deep_cut"]), -x["diff"]))
        contrarian_score = (
            round(deep_cut_count / artists_with_data, 3) if artists_with_data > 0 else 0.0
        )
        deep_cuts: dict = {
            "enriched": True,
            "contrarian_score": contrarian_score,
            "items": deep_cuts_items,
        }
    else:
        deep_cuts = {
            "enriched": False,
            "contrarian_score": None,
            "items": [],
        }

    return {
        "receipt": receipt,
        "milestones": milestones_out,
        "anthems": anthems_out,
        "deep_cuts": deep_cuts,
    }


# ------------------------------------------------------------------ build entry point


def _load_network(edges_path: str) -> dict:
    """Load the Phase 5 similarity edge list into the timeline's `network` key.

    Returns an "absent" stub (nodes/edges empty + note) when similarity-build
    hasn't been run, so the front-end can degrade gracefully.
    """
    if not os.path.exists(edges_path):
        return {
            "note": "No similarity edges built yet — run `cli.py similarity-build`.",
            "nodes": [],
            "edges": [],
            "outside": {},
        }
    with open(edges_path) as f:
        sim = json.load(f)
    return {
        "generated_at": sim.get("generated_at"),
        "nodes": sim.get("nodes", []),
        "edges": sim.get("edges", []),
        "outside": sim.get("outside", {}),
    }


def _service_meta(summary: dict) -> dict:
    """Forward history_summary's per-service provenance into the timeline.

    Returns a single-service "spotify" stub when the summary predates the
    multi-service merge, so the front end can always read the same shape.
    """
    sm = summary.get("service_meta")
    if isinstance(sm, dict) and sm.get("by_service"):
        # `artist_name_merges` is a build-time audit trail (~7 KB) that the page
        # never reads — it stays in history_summary.json, out of the inlined page.
        return {k: v for k, v in sm.items() if k != "artist_name_merges"}
    return {
        "note": "No service_meta in history_summary — assuming a Spotify-only export.",
        "services": ["spotify"],
        "include_apple": False,
        "by_service": {},
        "by_year": {},
    }


def _coverage(summary: dict) -> dict:
    """Forward history_summary's per-section coverage map into the timeline.

    `services_by_year` lets the page answer "does year X have data for this
    section?" from the JSON instead of a hardcoded year list;
    `spotify_only_sections` names the sections Apple cannot feed. Absent →
    an empty stub, which the front end reads as "assume everything covered".
    """
    cov = summary.get("coverage")
    if isinstance(cov, dict) and cov.get("sections"):
        return cov
    return {
        "note": "No coverage block in history_summary — no per-section gaps recorded.",
        "services_by_year": {},
        "spotify_only_sections": {},
        "sections": {},
    }


def build_timeline(
    fetch_tags_fn=None,
    *,
    verbose: bool = False,
) -> dict:
    """Merge all history layers into the taste_timeline.json structure.

    `fetch_tags_fn` is injectable for tests (avoids network calls). When None,
    the real `lastfm.artist_tags` is used.
    """
    # --- load inputs ---
    if not os.path.exists(HISTORY_SUMMARY_PATH):
        raise FileNotFoundError(f"history summary not found: {HISTORY_SUMMARY_PATH}")
    if not os.path.exists(ITUNES_PATH):
        raise FileNotFoundError(f"iTunes history not found: {ITUNES_PATH}")

    with open(HISTORY_SUMMARY_PATH) as f:
        summary: dict = json.load(f)
    with open(ITUNES_PATH) as f:
        itunes: dict = json.load(f)

    # --- collect all unique artists and resolve buckets (one Last.fm call each) ---
    unique_artists = _collect_unique_artists(summary, itunes)
    artist_buckets: dict[str, str] = {}
    for i, name in enumerate(unique_artists):
        if verbose:
            print(
                f"  [{i+1}/{len(unique_artists)}] resolving {name!r}…",
                file=sys.stderr,
                end="\r",
            )
        artist_buckets[name] = resolve_bucket(name, fetch_tags_fn, verbose=False)
    if verbose:
        print(f"  resolved {len(artist_buckets)} artists" + " " * 30, file=sys.stderr)

    # --- annotate per_year with buckets + household flags ---
    years_out: dict[str, dict] = {}
    for year, yd in sorted(summary["per_year"].items()):
        annotated_artists = []
        for a in yd.get("top_artists", []):
            name = a["name"]
            annotated_artists.append(
                {
                    "name": name,
                    "plays": a["plays"],
                    "bucket": artist_buckets.get(name, "other"),
                    "household": _is_household(name),
                }
            )
        years_out[year] = {
            "plays": yd["plays"],
            "hours": yd["hours"],
            "skips": yd["skips"],
            "top_artists": annotated_artists,
        }

    # --- artists trajectory table ---
    artists_out = []
    for a in summary.get("all_time_artists", []):
        name = a["name"]
        artists_out.append(
            {
                "name": name,
                "plays": a["plays"],
                "hours": a["hours"],
                "skip_rate": a["skip_rate"],
                "by_year": a["by_year"],
                "bucket": artist_buckets.get(name, "other"),
                "household": _is_household(name),
            }
        )

    # --- tracks table (keep URI for Spotify links) ---
    tracks_out = [
        {
            "artist": t["artist"],
            "title": t["title"],
            "plays": t["plays"],
            "uri": t["uri"],
            "years": t["years"],
        }
        for t in summary.get("all_time_tracks", [])
    ]

    # --- genre waves (per-year bucket totals) ---
    genre_waves = _compute_genre_waves(summary["per_year"], artist_buckets)

    # --- iTunes era block ---
    itunes_genre_table = _map_itunes_genres(itunes)
    top_itunes_artists = [
        {
            "artist": a["artist"],
            "plays": a["plays"],
            "tracks": a.get("tracks", 0),
            "bucket": artist_buckets.get(a["artist"], "other"),
            "household": _is_household(a["artist"]),
        }
        for a in itunes.get("top_artists_by_plays", [])[:25]
    ]
    top_itunes_tracks = [
        {"title": t.get("title"), "artist": t.get("artist"), "plays": t.get("plays")}
        for t in itunes.get("top_tracks_by_plays", [])[:20]
    ]
    itunes_era = {
        "era": "2013–2014",
        "note": (
            "Cumulative iTunes library play counts as of the 2013/2014 snapshots. "
            "Not per-year events — treat as a single pre-Spotify era block."
        ),
        "source": os.path.basename(ITUNES_PATH),
        "totals": itunes.get("totals", {}),
        "top_artists": top_itunes_artists,
        "top_tracks": top_itunes_tracks,
        "genres": itunes_genre_table,
    }

    # --- data gaps and annotations ---
    # Derived from the merged (multi-service) history, never hardcoded years:
    # a year is a GAP if no service logged it at all, and SPARSE if it is present
    # but below SPARSE_PLAYS_THRESHOLD plays (too thin to read as a real year).
    all_history_years = set(summary["per_year"].keys())
    expected_years = {str(y) for y in range(2015, 2027)}
    missing_years = sorted(expected_years - all_history_years)

    gaps = [
        {
            "year": y,
            "note": "No listening data for this year in any imported export.",
        }
        for y in missing_years
    ]
    for yr in sorted(all_history_years):
        plays = (summary["per_year"].get(yr) or {}).get("plays", 0)
        if plays < SPARSE_PLAYS_THRESHOLD:
            gaps.append(
                {
                    "year": yr,
                    "note": (
                        f"Present but sparse — only {plays} plays logged "
                        "across all imported services."
                    ),
                    "sparse": True,
                }
            )
    gaps.sort(key=lambda g: g["year"])

    annotations = [
        {
            "year": g["year"],
            "label": "Thin year" if g.get("sparse") else "Data gap",
            "note": g["note"],
        }
        for g in gaps
    ]

    # --- 2026 "now" panel ---
    now = _load_now_panel()

    # --- v3: behavior sections (household already excluded at aggregation) ---
    v2_meta = summary.get("v2_meta", {})
    behavior = {
        "note": v2_meta.get("note", ""),
        "household_excluded_plays": v2_meta.get("household_excluded_plays", 0),
        "clock": _build_behavior_clock(summary.get("clock", {})),
        "intentionality": _build_behavior_intentionality(
            summary.get("intentionality", {})
        ),
        "seasonality": _build_behavior_seasonality(
            summary.get("seasonality", {}), artist_buckets
        ),
        "platforms": _build_behavior_platforms(summary.get("platforms", {})),
        "skip": _build_behavior_skip(summary.get("artist_skip", {}), artist_buckets),
        "obsessions": _build_behavior_obsessions(
            summary.get("obsession_episodes", {})
        ),
        "rediscoveries": _build_behavior_rediscoveries(
            summary.get("rediscoveries", {})
        ),
    }

    # --- v3: loyalty spans (V6) + discovery overlay (V8) ---
    loyalty = _build_loyalty(summary.get("all_time_artists", []), artist_buckets)
    discovery = _build_discovery(
        DISCOVERY_LOG_PATH,
        summary.get("all_time_artists", []),
        _latest_taste_dump(),  # full path (now["dump_path"] is just the basename)
        artist_buckets,
    )

    # --- v4: similarity network (Phase 5; optional — built by similarity-build) ---
    network = _load_network(SIMILARITY_EDGES_PATH)

    # --- Phase 3: albums / track_stories / lists (optional enrichment) ---
    enrichment_meta = _load_track_album_meta(TRACK_ALBUM_META_PATH)
    albums_key = _build_albums_key(summary, enrichment_meta)
    track_stories_key = _build_track_stories_key(summary, enrichment_meta)
    lists_key = _build_lists_key(summary, enrichment_meta)

    # --- assemble output ---
    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "streaming_history": os.path.basename(HISTORY_SUMMARY_PATH),
            "itunes": os.path.basename(ITUNES_PATH),
            "taste_dump": now.get("dump_path"),
            "streaming_history_generated_at": summary.get("generated_at"),
            "taste_dump_generated_at": now.get("generated_at"),
        },
        "service_meta": _service_meta(summary),
        "coverage": _coverage(summary),
        "itunes_era": itunes_era,
        "years": years_out,
        "artists": artists_out,
        "tracks": tracks_out,
        "genre_waves": genre_waves,
        "gaps": gaps,
        "annotations": annotations,
        "now": now,
        "artist_buckets": artist_buckets,  # persist resolved map for cheap UI/re-runs
        "behavior": behavior,
        "loyalty": loyalty,
        "discovery": discovery,
        "network": network,
        "albums": albums_key,
        "track_stories": track_stories_key,
        "lists": lists_key,
    }

    # compact separators: this file is machine-read only (inlined into the page),
    # and indent=1 puts every edge/grid number on its own line (~35% bloat)
    with open(TIMELINE_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    return out


# ------------------------------------------------------------------ CLI handler


def _cmd_timeline_build(args) -> int:
    verbose = getattr(args, "verbose", False)
    print("  building taste timeline…", file=sys.stderr)
    try:
        result = build_timeline(verbose=verbose)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    size_kb = os.path.getsize(TIMELINE_PATH) / 1024
    print(TIMELINE_PATH)  # stdout: the machine result (path)
    alb = result.get("albums", {})
    ts = result.get("track_stories", {})
    lists = result.get("lists", {})
    print(
        f"  {size_kb:.0f} KB · "
        f"{len(result['artists'])} artists · "
        f"{len(result['tracks'])} tracks · "
        f"{len(result['years'])} years · "
        f"{len(result['genre_waves'])} year waves · "
        f"{len(alb.get('top_albums', []))} albums · "
        f"{len(ts.get('tracks', []))} track lifelines · "
        f"enriched={alb.get('enriched', False)}",
        file=sys.stderr,
    )
    dc = lists.get("deep_cuts", {})
    if dc.get("enriched"):
        print(
            f"  deep-cut contrarian score: {dc.get('contrarian_score', 0):.1%} "
            f"({sum(1 for i in dc.get('items', []) if i['is_deep_cut'])} of {len(dc.get('items', []))} artists)",
            file=sys.stderr,
        )
    if size_kb > 450:
        print(
            f"  WARNING: output is {size_kb:.0f} KB (target < 450 KB for ≤800 KB page)",
            file=sys.stderr,
        )
    return 0


# ------------------------------------------------------------------ inject

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "docs", "history.html"
)
INJECTED_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "docs", "history.local.html"
)
_PLACEHOLDER = "__TIMELINE_JSON__"


def inject_timeline(
    template_path: str = TEMPLATE_PATH,
    data_path: str = TIMELINE_PATH,
    out_path: str = INJECTED_PATH,
) -> str:
    """Inline data/taste_timeline.json into the history.html template.

    The committed docs/history.html is a data-free template with a
    __TIMELINE_JSON__ placeholder; this writes the personal, deployable copy
    to docs/history.local.html (gitignored). Returns the output path.
    """
    template = open(template_path, encoding="utf-8").read()
    if _PLACEHOLDER not in template:
        raise ValueError(
            f"{template_path} has no {_PLACEHOLDER} placeholder — "
            "it may already be an injected copy"
        )
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    # a "</script>" inside a JSON string would end the tag early; "<\/" is
    # identical JSON but inert in HTML
    payload = payload.replace("</", "<\\/")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(template.replace(_PLACEHOLDER, payload, 1))
    return out_path


def _cmd_timeline_inject(args) -> int:
    try:
        out = inject_timeline()
    except FileNotFoundError as e:
        print(
            f"error: {e}\n  (run `python cli.py timeline-build` first)", file=sys.stderr
        )
        return 1
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(out)  # stdout: the machine result (path)
    size_kb = os.path.getsize(out) / 1024
    print(f"  {size_kb:.0f} KB self-contained page ready to open/deploy", file=sys.stderr)
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    tb = sub.add_parser("build", help="Merge history layers → data/taste_timeline.json.")
    tb.add_argument(
        "--verbose", "-v", action="store_true", help="Print per-artist bucket resolution."
    )
    tb.set_defaults(func=_cmd_timeline_build)
    ti = sub.add_parser(
        "inject", help="Inline the timeline JSON into docs/history.local.html."
    )
    ti.set_defaults(func=_cmd_timeline_inject)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
