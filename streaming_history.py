"""Extended Streaming History loader — the GDPR export's sensing layer.

The `data/Spotify Extended Streaming History/` folder holds Spotify's full
per-play export (Streaming_History_Audio_*.json, 2015→present, ~40 MB). It is
personal data (IP addresses, device strings) and lives gitignored; no session
should ever read the raw files. This module collapses them once into a compact
`data/history_summary.json`, and `history-snapshot` prints the lean digest a
session actually reasons over (per-era top artists, true all-time counts,
forgotten favorites).

    python cli.py history-build                     # raw export -> summary JSON
    python cli.py history-snapshot                  # lean all-time digest
    python cli.py history-snapshot --year 2019      # zoom into one year

Play counting follows Spotify's own royalty convention: an event counts as a
play at >= 30s listened; under that it counts toward the skip rate.

v2 additions (additive — v1 keys and snapshot() shape unchanged):
  clock            — plays by hour × weekday, overall + per streaming era
  intentionality   — per year: deliberate / passive / shuffle / other + raw reason_start counts
  seasonality      — per year: monthly play totals + month×artist for top-200 artists
  platforms        — per year: normalized bucket counts + raw platform_map for review
  artist_skip      — top-200 artists: plays, skips, skip_rate (exposure guard ≥ 20)
  obsession_episodes — rolling 30-day window track obsessions (≥ OBSESSION_MIN_PLAYS plays)
  rediscoveries    — artists with ≥ 2-year gap who returned (cap 40)
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

from household import HOUSEHOLD_ARTISTS, is_household

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
EXPORT_DIR = os.path.join(DATA_DIR, "Spotify Extended Streaming History")
SUMMARY_PATH = os.path.join(DATA_DIR, "history_summary.json")

PLAY_MS = 30_000  # >= 30s listened counts as a play (Spotify's own threshold)
FORGOTTEN_MIN_PLAYS = 40  # lifetime plays needed to call an artist a past favorite
FORGOTTEN_QUIET_YEARS = 2  # no plays in this many recent years => "forgotten"

# Minimum exposure for artist_skip "extreme" lists (plays + skips combined).
SKIP_EXPOSURE_MIN = 20

# Rolling window for obsession detection (calendar days).
OBSESSION_WINDOW_DAYS = 30
# Minimum plays within that window to qualify as an obsession episode.
# Tuned against the real data: 15 yielded a reasonable number of episodes.
OBSESSION_MIN_PLAYS = 15

# Minimum full-calendar-year gap (both sides must have plays) to qualify as a rediscovery.
REDISCOVERY_MIN_GAP = 2

# Eastern timezone for clock bucketing (export timestamps are UTC).
_EASTERN = ZoneInfo("America/New_York")

# ------------------------------------------------------------------ era definitions
# Mirror the CHAPTERS array in docs/history.html (streaming years only: 2018+).
# Each era is identified by a short slug used as a JSON key.
STREAMING_ERAS: list[dict] = [
    {"slug": "2018",      "from": 2018, "to": 2018},
    {"slug": "2019-2020", "from": 2019, "to": 2020},
    {"slug": "2021-2022", "from": 2021, "to": 2022},
    {"slug": "2023-2024", "from": 2023, "to": 2024},
    {"slug": "2025-2026", "from": 2025, "to": 2026},
]


def _era_for_year(year: int) -> str | None:
    """Return the era slug for a given year, or None if outside streaming eras."""
    for era in STREAMING_ERAS:
        if era["from"] <= year <= era["to"]:
            return era["slug"]
    return None


# ------------------------------------------------------------------ platform normalization
# Maps raw platform string patterns → normalized bucket.
# Rules applied in order; first match wins.
# "not_applicable" → other (no Spotify client — partner API / internal).
# Pattern: substring match, case-insensitive.
_PLATFORM_RULES: list[tuple[str, str]] = [
    # Speaker / TV / Cast / Amazon Echo / Fire TV / Samsung TV / Chromecast
    ("amazon", "speaker_tv"),
    ("echo", "speaker_tv"),
    ("cast", "speaker_tv"),
    ("tizen", "speaker_tv"),
    ("android_tv", "speaker_tv"),
    ("fire", "speaker_tv"),
    # Web player
    ("web_player", "web"),
    # Desktop (macOS / Windows / Linux)
    ("osx", "desktop"),
    ("os x", "desktop"),
    ("windows", "desktop"),
    ("linux", "desktop"),
    ("mac", "desktop"),
    # Mobile (Android / iOS)
    ("android", "mobile"),
    ("ios", "mobile"),
    ("iphone", "mobile"),
    ("ipad", "mobile"),
]

# Human-readable mapping persisted in JSON for review.
# Built lazily from actual seen strings during build_history().
# Keys: exact raw platform strings; values: bucket name.
_PLATFORM_BUCKET_CACHE: dict[str, str] = {}


def _normalize_platform(raw: str) -> str:
    """Map a raw platform string to a normalized bucket."""
    if raw in _PLATFORM_BUCKET_CACHE:
        return _PLATFORM_BUCKET_CACHE[raw]

    lower = raw.lower()
    for pattern, bucket in _PLATFORM_RULES:
        if pattern in lower:
            _PLATFORM_BUCKET_CACHE[raw] = bucket
            return bucket

    _PLATFORM_BUCKET_CACHE[raw] = "other"
    return "other"


# ------------------------------------------------------------------ intentionality

# Precedence for intentionality classification (applied top-to-bottom; first match wins):
#
#   1. shuffle=True  → "shuffle"  (counted as its own exclusive category)
#      Rationale: shuffle is the strongest signal about the listening *mode* (passive
#      algorithmic queue), overriding even a click that started it.
#   2. reason_start in DELIBERATE_REASONS → "deliberate"
#      (user actively chose this track via search, click, or explicit play/back button)
#   3. reason_start in PASSIVE_REASONS → "passive"
#      (track followed automatically from the previous one)
#   4. everything else → "other"

DELIBERATE_REASONS: frozenset[str] = frozenset(
    {"clickrow", "playbtn", "backbtn", "remote"}
)
# clickrow  — user clicked a row in search results / album / playlist
# playbtn   — user pressed the play button (explicit start)
# backbtn   — user pressed back (deliberate revisit)
# remote    — playback started from another device (Spotify Connect / voice) — still
#             a user-initiated play, just not on this device

PASSIVE_REASONS: frozenset[str] = frozenset(
    {"trackdone", "appload", "fwdbtn"}
)
# trackdone — previous track finished naturally (autoplay)
# appload   — app launched and auto-resumed where it left off (no track choice made)
# fwdbtn    — user skipped forward (passive queue navigation, not a fresh selection)


def _classify_intent(reason_start: str, shuffle: bool) -> str:
    """Return intentionality bucket for one event."""
    if shuffle:
        return "shuffle"
    if reason_start in DELIBERATE_REASONS:
        return "deliberate"
    if reason_start in PASSIVE_REASONS:
        return "passive"
    return "other"


# ------------------------------------------------------------------ _iter_events


def _iter_events(src_dir: str = EXPORT_DIR):
    """Yield music play events from every Streaming_History_Audio_*.json.

    Podcast/audiobook events (no spotify_track_uri) are dropped — this toolkit
    only reasons about music.
    """
    for path in sorted(glob.glob(os.path.join(src_dir, "Streaming_History_Audio_*.json"))):
        with open(path) as f:
            for e in json.load(f):
                if e.get("spotify_track_uri") and e.get("master_metadata_album_artist_name"):
                    yield e


# ------------------------------------------------------------------ build_history


def build_history(src_dir: str = EXPORT_DIR, out_path: str = SUMMARY_PATH) -> dict:
    """Aggregate the raw export into one summary dict and write it to out_path."""

    # ---- v1 accumulators ----
    artists: dict[str, dict] = defaultdict(
        lambda: {"plays": 0, "ms": 0, "skips": 0, "years": defaultdict(int)}
    )
    tracks: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"plays": 0, "ms": 0, "uri": None, "years": set()}
    )
    years: dict[str, dict] = defaultdict(lambda: {"plays": 0, "ms": 0, "skips": 0})
    n_events = 0
    first_ts, last_ts = None, None

    # ---- v2 accumulators (household-excluded) ----
    household_excluded_plays = 0

    # clock: {era_slug: [[hour0..23] for weekday 0..6 (Mon=0)]}
    # overall clock is stored under slug "overall"
    _clock_all_slugs = ["overall"] + [e["slug"] for e in STREAMING_ERAS]
    clock_raw: dict[str, list[list[int]]] = {
        slug: [[0] * 24 for _ in range(7)]
        for slug in _clock_all_slugs
    }

    # intentionality: {year: {bucket: count, "reason_start_counts": {rs: count}}}
    intentionality_raw: dict[str, dict] = defaultdict(
        lambda: {
            "deliberate": 0, "passive": 0, "shuffle": 0, "other": 0,
            "reason_start_counts": defaultdict(int),
        }
    )

    # seasonality: {year: {month(1-12): count}}  (totals for all non-household)
    seasonality_totals: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    # month × artist: {(year, month, artist): count} — only for top-200 later
    seasonality_artist: dict[tuple[str, int, str], int] = defaultdict(int)

    # platforms: {year: {bucket: count}}, plus raw string accumulation
    platforms_raw: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    platform_map_seen: dict[str, str] = {}  # raw string → bucket (all seen strings)

    # artist_skip (household-excluded): same shape as v1 artists but only for non-hh
    # {artist: {"plays": int, "skips": int, "skipped_plays": int}}
    # "skipped_plays" = plays that ended in a skip (skipped=True AND ms>=PLAY_MS)
    artist_skip_raw: dict[str, dict] = defaultdict(
        lambda: {"plays": 0, "skips": 0}
    )

    # obsession_episodes: per (artist, title) → sorted list of Eastern-local dates (for plays)
    track_play_dates: dict[tuple[str, str], list] = defaultdict(list)
    # store URI for each (artist, title)
    track_uri_map: dict[tuple[str, str], str] = {}

    # rediscoveries: {artist: set(years)} — non-household plays only
    rediscovery_years: dict[str, set[str]] = defaultdict(set)

    # ---- single pass ----
    for e in _iter_events(src_dir):
        n_events += 1
        ts = e["ts"]
        year = ts[:4]
        ms = e.get("ms_played") or 0
        artist = e["master_metadata_album_artist_name"]
        title = e.get("master_metadata_track_name") or "?"
        uri = e.get("spotify_track_uri") or ""

        first_ts = ts if first_ts is None or ts < first_ts else first_ts
        last_ts = ts if last_ts is None or ts > last_ts else last_ts

        # --- v1 accounting (all artists, including household) ---
        a = artists[artist]
        y = years[year]
        a["ms"] += ms
        y["ms"] += ms
        if ms >= PLAY_MS:
            a["plays"] += 1
            a["years"][year] += 1
            y["plays"] += 1
            t = tracks[(artist, title)]
            t["plays"] += 1
            t["ms"] += ms
            t["uri"] = uri
            t["years"].add(year)
        else:
            a["skips"] += 1
            y["skips"] += 1

        # --- household guard for v2 sections ---
        if is_household(artist):
            if ms >= PLAY_MS:
                household_excluded_plays += 1
            continue  # skip ALL v2 accounting for household artists

        # --- parse timestamp to Eastern local time ---
        # ts format: "2020-01-15T14:32:00Z"
        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt_east = dt_utc.astimezone(_EASTERN)
        hour = dt_east.hour
        weekday = dt_east.weekday()  # 0=Monday, 6=Sunday
        month = dt_east.month
        local_date = dt_east.date()

        # --- clock (plays only) ---
        if ms >= PLAY_MS:
            era_slug = _era_for_year(dt_east.year)
            clock_raw["overall"][weekday][hour] += 1
            if era_slug is not None:
                clock_raw[era_slug][weekday][hour] += 1

        # --- intentionality (plays only) ---
        if ms >= PLAY_MS:
            reason_start = e.get("reason_start") or "unknown"
            shuffle = bool(e.get("shuffle"))
            bucket = _classify_intent(reason_start, shuffle)
            ir = intentionality_raw[year]
            ir[bucket] += 1
            ir["reason_start_counts"][reason_start] += 1

        # --- seasonality (plays only) ---
        if ms >= PLAY_MS:
            seasonality_totals[year][month] += 1
            seasonality_artist[(year, month, artist)] += 1

        # --- platforms (plays only) ---
        if ms >= PLAY_MS:
            raw_platform = e.get("platform") or "not_applicable"
            bucket = _normalize_platform(raw_platform)
            platform_map_seen[raw_platform] = bucket
            platforms_raw[year][bucket] += 1

        # --- artist_skip (all events, not just plays, to capture real skip rate) ---
        asr = artist_skip_raw[artist]
        if ms >= PLAY_MS:
            asr["plays"] += 1
        else:
            asr["skips"] += 1

        # --- track play dates (plays only) for obsession detection ---
        if ms >= PLAY_MS:
            key = (artist, title)
            track_play_dates[key].append(local_date)
            if uri:
                track_uri_map[key] = uri

        # --- rediscovery years (plays only) ---
        if ms >= PLAY_MS:
            rediscovery_years[artist].add(year)

    # ======================================================================
    # Build v1 output sections (unchanged)
    # ======================================================================

    def _hours(ms: int) -> float:
        return round(ms / 3_600_000, 1)

    top_artists = sorted(artists.items(), key=lambda kv: -kv[1]["plays"])[:200]
    all_time_artists = [
        {
            "name": name,
            "plays": d["plays"],
            "hours": _hours(d["ms"]),
            "skip_rate": round(d["skips"] / (d["plays"] + d["skips"]), 2)
            if d["plays"] + d["skips"]
            else 0.0,
            "by_year": dict(sorted(d["years"].items())),
        }
        for name, d in top_artists
    ]

    top_tracks = sorted(tracks.items(), key=lambda kv: -kv[1]["plays"])[:150]
    all_time_tracks = [
        {
            "artist": artist,
            "title": title,
            "plays": d["plays"],
            "uri": d["uri"],
            "years": sorted(d["years"]),
        }
        for (artist, title), d in top_tracks
    ]

    per_year = {}
    for year in sorted(years):
        ranked = sorted(
            ((n, d["years"].get(year, 0)) for n, d in artists.items()),
            key=lambda kv: -kv[1],
        )
        per_year[year] = {
            "plays": years[year]["plays"],
            "hours": _hours(years[year]["ms"]),
            "skips": years[year]["skips"],
            "top_artists": [
                {"name": n, "plays": p} for n, p in ranked[:25] if p > 0
            ],
        }

    all_years = sorted(years)
    quiet_cutoff = all_years[-FORGOTTEN_QUIET_YEARS:] if all_years else []
    forgotten = sorted(
        (
            {
                "name": name,
                "plays": d["plays"],
                "peak_year": max(d["years"], key=d["years"].get),
                "last_year": max(d["years"]),
            }
            for name, d in artists.items()
            if d["plays"] >= FORGOTTEN_MIN_PLAYS
            and not any(d["years"].get(y) for y in quiet_cutoff)
        ),
        key=lambda x: -x["plays"],
    )

    # ======================================================================
    # Build v2 output sections
    # ======================================================================

    # ---- clock ----
    # Convert [[hour per weekday]] to a JSON-friendly structure.
    def _clock_to_dict(grid: list[list[int]]) -> list[dict]:
        """Convert the [7][24] grid to [{weekday, hour, plays}] list."""
        out = []
        for wd in range(7):
            for hr in range(24):
                cnt = grid[wd][hr]
                if cnt > 0:
                    out.append({"wd": wd, "h": hr, "n": cnt})
        return out

    clock_out: dict[str, list] = {}
    for slug in _clock_all_slugs:
        clock_out[slug] = _clock_to_dict(clock_raw[slug])

    clock_section = {
        "note": (
            "Plays by local time (America/New_York). "
            "wd=0 Monday … wd=6 Sunday. h=0–23. "
            "Household artists excluded."
        ),
        "eras": [e["slug"] for e in STREAMING_ERAS],
        "data": clock_out,
    }

    # ---- intentionality ----
    # Precedence documented at module level (_classify_intent).
    intentionality_out: dict[str, dict] = {}
    for year in sorted(intentionality_raw):
        ir = intentionality_raw[year]
        total = ir["deliberate"] + ir["passive"] + ir["shuffle"] + ir["other"]
        intentionality_out[year] = {
            "deliberate": ir["deliberate"],
            "passive": ir["passive"],
            "shuffle": ir["shuffle"],
            "other": ir["other"],
            "total": total,
            "reason_start_counts": dict(
                sorted(ir["reason_start_counts"].items(), key=lambda kv: -kv[1])
            ),
        }

    intentionality_section = {
        "note": (
            "Per-year play counts by listening mode. "
            "Precedence: shuffle=True → 'shuffle'; "
            "else reason_start in {clickrow,playbtn,backbtn,remote} → 'deliberate'; "
            "else reason_start in {trackdone,appload,fwdbtn} → 'passive'; "
            "else → 'other'. "
            "Household artists excluded. Plays only (ms_played >= 30000)."
        ),
        "by_year": intentionality_out,
    }

    # ---- seasonality ----
    # top-200 non-household artists by all-time plays
    top200_nh = sorted(
        ((name, d) for name, d in artists.items() if not is_household(name)),
        key=lambda kv: -kv[1]["plays"],
    )[:200]
    top200_names: set[str] = {name for name, _ in top200_nh}

    seasonality_months_out: dict[str, dict[str, int]] = {}
    for year in sorted(seasonality_totals):
        seasonality_months_out[year] = {
            str(m): seasonality_totals[year][m]
            for m in range(1, 13)
            if seasonality_totals[year][m] > 0
        }

    # Build month×artist slice (only top-200 artists)
    # Structure: {year: {month: {artist: count}}}
    seasonality_artist_out: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for (year, month, art), cnt in seasonality_artist.items():
        if art in top200_names:
            seasonality_artist_out[year][str(month)][art] = cnt

    seasonality_section = {
        "note": (
            "Monthly play counts per year (America/New_York local date). "
            "Household artists excluded. "
            "artist_by_month covers only the top-200 non-household artists by all-time plays."
        ),
        "by_year": seasonality_months_out,
        "artist_by_month": {
            yr: {mo: arts for mo, arts in months.items()}
            for yr, months in sorted(seasonality_artist_out.items())
        },
    }

    # ---- platforms ----
    platforms_out: dict[str, dict[str, int]] = {}
    for year in sorted(platforms_raw):
        pb = platforms_raw[year]
        platforms_out[year] = dict(sorted(pb.items()))

    platforms_section = {
        "note": (
            "Per-year play counts bucketed by platform. "
            "Buckets: mobile / desktop / web / speaker_tv / other. "
            "Raw platform strings→buckets in platform_map. "
            "Household artists excluded."
        ),
        "by_year": platforms_out,
        "platform_map": dict(sorted(platform_map_seen.items())),
    }

    # ---- artist_skip ----
    # top-200 non-household artists by (plays + skips)
    top200_skip = sorted(
        (
            (name, d)
            for name, d in artist_skip_raw.items()
        ),
        key=lambda kv: -(kv[1]["plays"] + kv[1]["skips"]),
    )[:200]

    artist_skip_out = []
    for name, d in top200_skip:
        total_events = d["plays"] + d["skips"]
        skip_rate = round(d["skips"] / total_events, 3) if total_events else 0.0
        artist_skip_out.append(
            {
                "name": name,
                "plays": d["plays"],
                "skips": d["skips"],
                "skip_rate": skip_rate,
                "exposure": total_events,
            }
        )

    artist_skip_section = {
        "note": (
            f"Top-200 non-household artists by total events (plays+skips). "
            f"Exposure guard for 'extreme' lists: SKIP_EXPOSURE_MIN={SKIP_EXPOSURE_MIN} "
            f"(plays+skips must be >= {SKIP_EXPOSURE_MIN} for reliable skip_rate). "
            f"skip_rate = skips / (plays+skips)."
        ),
        "exposure_guard": SKIP_EXPOSURE_MIN,
        "artists": artist_skip_out,
    }

    # ---- obsession_episodes ----
    # For each track, sort play dates and use a sliding window.
    episodes: list[dict] = []
    window = timedelta(days=OBSESSION_WINDOW_DAYS)

    for key, dates in track_play_dates.items():
        if len(dates) < OBSESSION_MIN_PLAYS:
            continue  # fast path: can't possibly have an episode
        artist_name, title = key
        sorted_dates = sorted(dates)
        # Sliding window: for each date i as window start, count plays within 30 days.
        i = 0
        while i < len(sorted_dates):
            start = sorted_dates[i]
            end = start + window
            # Count how many plays fall in [start, end)
            count = 0
            j = i
            while j < len(sorted_dates) and sorted_dates[j] < end:
                count += 1
                j += 1
            if count >= OBSESSION_MIN_PLAYS:
                uri = track_uri_map.get(key, "")
                episodes.append(
                    {
                        "artist": artist_name,
                        "title": title,
                        "uri": uri,
                        "window_start": str(start),
                        "plays": count,
                    }
                )
                # Advance past this window to avoid double-counting the same episode.
                i = j
            else:
                i += 1

    # Sort by intensity (plays), cap at top 50.
    episodes.sort(key=lambda e: -e["plays"])
    episodes = episodes[:50]

    obsession_section = {
        "note": (
            f"Track obsession episodes: >= {OBSESSION_MIN_PLAYS} plays of the same track "
            f"within any rolling {OBSESSION_WINDOW_DAYS}-day window. "
            f"Household artists excluded. "
            f"Capped at top 50 episodes by play count."
        ),
        "obsession_min_plays": OBSESSION_MIN_PLAYS,
        "window_days": OBSESSION_WINDOW_DAYS,
        "episodes": episodes,
    }

    # ---- rediscoveries ----
    # Artists with a gap of >= REDISCOVERY_MIN_GAP full calendar years (zero plays),
    # where plays exist on BOTH sides of the gap.
    rediscovery_out: list[dict] = []

    for artist_name, year_set in rediscovery_years.items():
        if len(year_set) < 2:
            continue
        sorted_years = sorted(int(y) for y in year_set)
        # Find all gaps >= REDISCOVERY_MIN_GAP years
        found_gap = False
        gap_last_before = None
        gap_first_after = None

        for idx in range(len(sorted_years) - 1):
            y_before = sorted_years[idx]
            y_after = sorted_years[idx + 1]
            gap = y_after - y_before - 1  # full silent years between
            if gap >= REDISCOVERY_MIN_GAP:
                # Must have plays before AND after (guaranteed by sorted_years[0] and [-1])
                # Pick the largest gap as the defining one
                if gap_last_before is None or gap > (gap_first_after - gap_last_before - 1):
                    gap_last_before = y_before
                    gap_first_after = y_after
                found_gap = True

        if not found_gap:
            continue

        # per-year play series from artist_skip_raw or from the main artists dict
        # We use the main artists dict (includes all years).
        main_d = artists.get(artist_name, {})
        year_plays = dict(sorted(main_d.get("years", {}).items()))

        rediscovery_out.append(
            {
                "artist": artist_name,
                "gap_last_before": gap_last_before,
                "gap_first_after": gap_first_after,
                "gap_years": gap_first_after - gap_last_before - 1,
                "total_plays": main_d.get("plays", 0),
                "by_year": year_plays,
            }
        )

    # Sort by total plays, cap at 40.
    rediscovery_out.sort(key=lambda x: -x["total_plays"])
    rediscovery_out = rediscovery_out[:40]

    rediscoveries_section = {
        "note": (
            f"Artists with a gap of >= {REDISCOVERY_MIN_GAP} full calendar years (zero plays) "
            f"who returned after it. Gaps at series start/end are ignored "
            f"(plays must exist on both sides). Household artists excluded. Capped at top 40."
        ),
        "min_gap_years": REDISCOVERY_MIN_GAP,
        "artists": rediscovery_out,
    }

    # ---- assemble output ----
    summary = {
        # v1 keys (unchanged)
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": os.path.basename(src_dir),
        "events": n_events,
        "first_play": first_ts,
        "last_play": last_ts,
        "total_plays": sum(y["plays"] for y in years.values()),
        "total_hours": _hours(sum(y["ms"] for y in years.values())),
        "unique_artists": len(artists),
        "unique_tracks": len(tracks),
        "per_year": per_year,
        "all_time_artists": all_time_artists,
        "all_time_tracks": all_time_tracks,
        "forgotten_favorites": forgotten,
        # v2 keys (additive)
        "v2_meta": {
            "household_excluded_plays": household_excluded_plays,
            "note": (
                "All v2 behavioral sections exclude plays by household artists "
                f"({len(HOUSEHOLD_ARTISTS)} named artists + white-noise regex). "
                f"Excluded plays: {household_excluded_plays}."
            ),
        },
        "clock": clock_section,
        "intentionality": intentionality_section,
        "seasonality": seasonality_section,
        "platforms": platforms_section,
        "artist_skip": artist_skip_section,
        "obsession_episodes": obsession_section,
        "rediscoveries": rediscoveries_section,
    }

    with open(out_path, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    return summary


def load_summary(path: str = SUMMARY_PATH) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def snapshot(summary: dict, year: str | None = None) -> dict:
    """Reduce the summary to the lean digest a session reads (~2k tokens).

    With `year`, zoom into that year instead of the all-time view.
    Shape is identical to v1 — v2 keys are never included here.
    """
    if year is not None:
        y = summary["per_year"].get(year)
        if y is None:
            return {"error": f"no data for {year}", "years": sorted(summary["per_year"])}
        return {
            "year": year,
            "plays": y["plays"],
            "hours": y["hours"],
            "top_artists": [f"{a['name']} ({a['plays']})" for a in y["top_artists"]],
            "top_tracks": [
                f"{t['artist']} — {t['title']} ({t['plays']})"
                for t in summary["all_time_tracks"]
                if year in t["years"]
            ][:20],
        }

    return {
        "generated_at": summary["generated_at"],
        "span": f"{summary['first_play'][:10]} → {summary['last_play'][:10]}",
        "total_plays": summary["total_plays"],
        "total_hours": summary["total_hours"],
        "unique_artists": summary["unique_artists"],
        "per_year": {
            y: {
                "plays": d["plays"],
                "hours": d["hours"],
                "top5": [a["name"] for a in d["top_artists"][:5]],
            }
            for y, d in summary["per_year"].items()
        },
        "all_time_top_artists": [
            f"{a['name']} ({a['plays']} plays, {a['hours']}h)"
            for a in summary["all_time_artists"][:40]
        ],
        "forgotten_favorites": [
            f"{f['name']} ({f['plays']} plays, peak {f['peak_year']}, last {f['last_year']})"
            for f in summary["forgotten_favorites"][:30]
        ],
    }


# ---------------------------------------------------------------- CLI handlers


def _cmd_history_build(args) -> int:
    if not glob.glob(os.path.join(args.src, "Streaming_History_Audio_*.json")):
        print(f"no Streaming_History_Audio_*.json under {args.src}", file=sys.stderr)
        return 1
    s = build_history(args.src)
    print(SUMMARY_PATH)
    print(
        f"  {s['events']} events → {s['total_plays']} plays, {s['total_hours']}h, "
        f"{s['unique_artists']} artists, {s['first_play'][:10]}→{s['last_play'][:10]}",
        file=sys.stderr,
    )
    return 0


def _cmd_history_snapshot(args) -> int:
    s = load_summary()
    if s is None:
        print("no history summary; run `cli.py history-build` first", file=sys.stderr)
        return 1
    print(json.dumps(snapshot(s, args.year), ensure_ascii=False, indent=2))
    print(f"  from {os.path.basename(SUMMARY_PATH)}", file=sys.stderr)
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--src", default=EXPORT_DIR)
    b.set_defaults(func=_cmd_history_build)
    sn = sub.add_parser("snapshot")
    sn.add_argument("--year", default=None)
    sn.set_defaults(func=_cmd_history_snapshot)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
