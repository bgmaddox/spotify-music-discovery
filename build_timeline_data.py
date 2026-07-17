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

# ------------------------------------------------------------------ genre buckets

# Maps messy Last.fm tag strings (lowercased) → canonical bucket names.
# Longer / more-specific entries must appear before shorter ones so the first
# match wins when a tag could satisfy multiple patterns.
TAG_BUCKETS: dict[str, str] = {
    # folk / americana cluster
    "americana": "folk/americana",
    "folk": "folk/americana",
    "alt-country": "folk/americana",
    "alt country": "folk/americana",
    "outlaw country": "folk/americana",
    "red dirt": "folk/americana",
    "bluegrass": "folk/americana",
    "roots rock": "folk/americana",
    "folk rock": "folk/americana",
    "singer-songwriter": "folk/americana",
    "singer songwriter": "folk/americana",
    "appalachian folk": "folk/americana",
    "acoustic": "folk/americana",
    "new americana": "folk/americana",
    # country (mainstream/traditional, NOT bluegrass/americana)
    "country": "country",
    "texas country": "country",
    "traditional country": "country",
    "bro country": "country",
    "nashville sound": "country",
    # indie rock / alternative
    "indie rock": "indie rock",
    "indie pop": "indie rock",
    "indie": "indie rock",
    "alternative": "indie rock",
    "alternative rock": "indie rock",
    "indie folk": "indie rock",
    "dream pop": "indie rock",
    "shoegaze": "indie rock",
    "lo-fi": "indie rock",
    "post-punk": "indie rock",
    "emo": "indie rock",
    # hip hop
    "hip hop": "hip hop",
    "hip-hop": "hip hop",
    "rap": "hip hop",
    "gangsta rap": "hip hop",
    "southern hip hop": "hip hop",
    "east coast hip hop": "hip hop",
    "west coast hip hop": "hip hop",
    "trap": "hip hop",
    "conscious hip hop": "hip hop",
    # classic rock (guitar-driven, pre-2000s mainstream rock)
    "classic rock": "classic rock",
    "rock": "classic rock",
    "hard rock": "classic rock",
    "arena rock": "classic rock",
    "blues rock": "classic rock",
    "70s": "classic rock",
    "80s": "classic rock",
    "southern rock": "classic rock",
    "heartland rock": "classic rock",
    # soul / blues / r&b
    "soul": "soul/blues",
    "blues": "soul/blues",
    "r&b": "soul/blues",
    "rnb": "soul/blues",
    "motown": "soul/blues",
    "funk": "soul/blues",
    "neo soul": "soul/blues",
    "gospel": "soul/blues",
    # pop
    "pop": "pop",
    "electropop": "pop",
    "synthpop": "pop",
    "power pop": "pop",
    "dance pop": "pop",
    "teen pop": "pop",
    # electronic
    "electronic": "electronic",
    "electronica": "electronic",
    "edm": "electronic",
    "house": "electronic",
    "techno": "electronic",
    "ambient": "electronic",
    "downtempo": "electronic",
    "chillout": "electronic",
    "trip-hop": "electronic",
    "idm": "electronic",
    "mashup": "electronic",
    # metal / punk
    "metal": "metal/punk",
    "punk": "metal/punk",
    "punk rock": "metal/punk",
    "heavy metal": "metal/punk",
    "death metal": "metal/punk",
    "black metal": "metal/punk",
    "hardcore": "metal/punk",
    # jazz
    "jazz": "jazz",
    "bossa nova": "jazz",
    "swing": "jazz",
    "big band": "jazz",
    "smooth jazz": "jazz",
    # soundtrack / score
    "soundtrack": "soundtrack",
    "score": "soundtrack",
    "film score": "soundtrack",
    "video game music": "soundtrack",
    "classical": "soundtrack",
    # kids / household — also forced via HOUSEHOLD_ARTISTS
    "children's music": "kids/household",
    "children": "kids/household",
    "kids": "kids/household",
    "nursery rhymes": "kids/household",
}

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
    all_spotify_years = set(summary["per_year"].keys())
    expected_years = {str(y) for y in range(2015, 2027)}
    missing_years = sorted(expected_years - all_spotify_years)

    gaps = [
        {
            "year": y,
            "note": (
                "Absent from GDPR export — Spotify has no play data for this year."
                if y == "2017"
                else "Year missing from streaming export."
            ),
        }
        for y in missing_years
    ]
    # 2015–16 are present but sparse; add a sparse note
    for yr in ["2015", "2016"]:
        if yr in all_spotify_years:
            gaps.append(
                {
                    "year": yr,
                    "note": (
                        "Present but sparse — pre-Spotify era; "
                        "most listening was still on iTunes."
                    ),
                    "sparse": True,
                }
            )
    gaps.sort(key=lambda g: g["year"])

    annotations = [
        {
            "year": "2017",
            "label": "Data gap",
            "note": "No Spotify streaming data for 2017 (absent from GDPR export).",
        },
        {
            "year": "2015",
            "label": "Transition era",
            "note": "Sparse Spotify plays; heavy iTunes use continued into this year.",
        },
        {
            "year": "2016",
            "label": "Transition era",
            "note": "Sparse Spotify plays; transition from iTunes to streaming ongoing.",
        },
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
    print(
        f"  {size_kb:.0f} KB · "
        f"{len(result['artists'])} artists · "
        f"{len(result['tracks'])} tracks · "
        f"{len(result['years'])} years · "
        f"{len(result['genre_waves'])} year waves",
        file=sys.stderr,
    )
    if size_kb > 250:
        print(
            f"  WARNING: output is {size_kb:.0f} KB (target < 250 KB)",
            file=sys.stderr,
        )
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
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
