"""Apple Media Services music export loader — Apple's sensing layer.

Parses the Apple Media Services GDPR-style export
(`data/Apple_Media_Services/Apple Music Activity/`, gitignored — contains IPs
and device strings) into normalized play events that match the EXACT schema
`streaming_history.py` already consumes for Spotify's Extended Streaming
History (`ts`, `ms_played`, `master_metadata_album_artist_name`, ...). This
module only builds and serves that normalized event stream; merging it into
the timeline (`build_timeline_data.py`) and deciding how to treat the
Apple-only fields (`apple_feature`, `apple_end_reason`) is a later phase.

    python apple_history.py build            # raw export -> data/apple_history_events.json
    python apple_history.py stats            # print the stats dict for the last build
    python cli.py apple-build                # same, wired through the thin router

## The artist-recovery problem

`Apple Music Play Activity.csv` is the real event stream (one row per play,
~17.9k rows, Aug 2015 -> Oct 2018) but its `Container Artist Name` column is
populated for only ~2 of 17,928 rows — Apple's export does not carry the
artist on the event row. The two smaller companion exports do carry artist
info, packed into a single `"Artist - Title"` string:

  - `Apple Music - Play History Daily Tracks.csv` -> `Track Description`
  - `Apple Music - Track Play History.csv`        -> `Track Name`

We build a `normalized title -> artist` map from those two files (splitting
on the FIRST " - ", since some titles/artists themselves contain " - ") and
join it back onto the Play Activity rows by song title. Rows whose title
doesn't resolve are DROPPED (never emitted with a null artist — downstream
code indexes `master_metadata_album_artist_name` directly). Verified against
the real export: ~96% of unique songs resolve this way.

## Row filtering, investigated

`Event Type` in Play Activity breaks down as PLAY_END 12,670 / blank 5,249 /
LYRIC_DISPLAY 9. Investigation (timestamp ranges + Event ID overlap) showed
the blank-Event-Type rows are NOT duplicates of PLAY_END rows: they span
2015-08-17 -> 2016-05-04 (the earliest, pre-`Event Type`-field logging era of
this account's data), while PLAY_END rows start 2016-02-19 and run through
2018-10-15 — only a ~3-month overlap and just 1 shared Event ID across the
5,249 vs 12,670 rows. They're a genuinely distinct, earlier tranche of plays
(same "FUSE" client platform, same row shape, all real Song Name / duration
data) that predate Apple populating the `Event Type` column — not a parallel
duplicate log. They are KEPT. Only `LYRIC_DISPLAY` (a lyrics-panel-open
telemetry event, not a play) is dropped by Event Type.

Non-music rows are dropped by inspecting the actual `Media Type` / `Item
Type` values seen in the real export:
  - `Media Type == "VIDEO"` (14 rows) -> music videos, not audio plays.
  - `Item Type` in {STREAM, NON_SONG_CLIP, ARTIST_UPLOADED_CONTENT,
    TIMED_METADATA_PING} -> internet-radio stations (NPR/BBC/ESPN/Apple
    Music 1/Festival streams), non-song audio clips, uploaded video-ish
    content, and radio metadata pings respectively. `STREAM` rows are mostly
    literal radio station names but do include a handful (~8) of real song
    titles picked up incidentally from radio; those are accepted collateral
    loss to keep the radio-station rule simple — flag for a reviewer if that
    matters later.
  - `Song Name` in {"NPR News and Culture", "Apple Music 1"} -> belt-and-
    suspenders drop by name (redundant with the STREAM rule above in this
    export, but cheap insurance against a differently-tagged row).
  - Rows with no `Song Name` (394, all `AGGREGATE_NON_CATALOG_PLAY_TIME`) or
    no usable timestamp are dropped.

## `ms_played` clamp

`Play Duration Milliseconds` has 346 negative rows across the raw export
(clamped to 0 where they survive earlier filters — 336 do, in the real
export) and 204 rows where it exceeds 2x `Media Duration In Milliseconds`
(a known Apple export quirk — one row reports ~2.75M ms, i.e. ~46 minutes,
against a 120s media duration). In the real export, though, ALL 204 runaway
rows turn out to be `AGGREGATE_NON_CATALOG_PLAY_TIME` rows with no `Song
Name` — they're already dropped by the no-song-name filter before reaching
the clamp step, so `ms_clamped_runaway` reports 0 against the live data. The
clamp logic and its counter are still exercised directly by
`tests/test_apple_history.py` (a synthetic runaway row) since a differently
shaped future export could hit it on rows that DO carry a song name. Both
counts are reported in the stats dict (`ms_clamped_negative`,
`ms_clamped_runaway`).

## `platform`

`Client Platform` (constant `"FUSE"` on every row) and `Device Type` (blank
on every row) carry no signal in this export, and `Source Type` is just
`ORIGINATING_DEVICE`/blank. The real device/OS signal lives in `Client
Device Name`, a user-agent-ish string, e.g.
`"itunesstored/1.0 iOS/10.3.2 model/iPhone8,1 hwp/s8000 build/14F89 ..."` or
`"iTunes/12.8 (Macintosh; OS X 10.13.6) AppleWebKit/605.3.8 ..."`.

We deliberately do NOT emit that raw string. `_platform_from_device_name()`
maps it to one of a small fixed vocabulary — `"iOS"` / `"Macintosh"` /
`"Windows"` / `"Android"` / `"unknown"` — with no device model, hardware,
or OS build info retained. Two reasons: (1) `streaming_history.
build_history()` persists a raw-string -> bucket map into
`history_summary.json`, and hundreds of distinct UA strings would bloat it;
(2) that summary feeds `data/taste_timeline.json`, which is inlined into a
PUBLICLY deployed page (`docs/history.html`) — raw UA strings would ship
device/OS fingerprints publicly. The five tokens are chosen to substring-
match the EXISTING `streaming_history._PLATFORM_RULES` unchanged: "iOS" ->
mobile, "Macintosh" -> desktop, "Windows" -> desktop, "Android" -> mobile.
iPadOS is folded into "iOS" rather than split out — the real export has
zero rows where "ipad" appears without also matching the iPhone/iOS
pattern, so a separate bucket isn't genuinely distinguishable here. Verified
against the real 16,606-event export: iOS 10,303 · Macintosh 6,130 ·
Android 173 · unknown 0 (post-filtering/dedup counts — lower than the raw
per-row totals on the full 17,928-row file since dropped/deduped rows never
reach this step).
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
APPLE_DIR = os.path.join(DATA_DIR, "Apple_Media_Services", "Apple Music Activity")
APPLE_EVENTS_PATH = os.path.join(DATA_DIR, "apple_history_events.json")
UNRESOLVED_REPORT_PATH = os.path.join(DATA_DIR, "apple_unresolved.md")

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
OVERRIDES_PATH = os.path.join(CONFIG_DIR, "apple_artist_overrides.json")

PLAY_ACTIVITY_FILE = "Apple Music Play Activity.csv"
DAILY_TRACKS_FILE = "Apple Music - Play History Daily Tracks.csv"
TRACK_PLAY_HISTORY_FILE = "Apple Music - Track Play History.csv"
FAVORITES_FILE = "Apple Music - Favorites.csv"

# Event Type values to drop outright (not real plays). Blank Event Type is an
# older logging era and IS kept — see module docstring investigation above.
_DROP_EVENT_TYPES = {"LYRIC_DISPLAY"}

# Item Type values that indicate radio stations / non-song audio / uploaded
# clips rather than a song play (see module docstring for the breakdown).
_DROP_ITEM_TYPES = {
    "STREAM",
    "NON_SONG_CLIP",
    "ARTIST_UPLOADED_CONTENT",
    "TIMED_METADATA_PING",
}

# Explicit non-music Song Name values to drop (belt-and-suspenders; mostly
# redundant with the Item Type rule above, since these are almost always
# tagged STREAM, but a cheap extra guard).
_DROP_SONG_NAMES = {"NPR News and Culture", "Apple Music 1"}

# Runaway ms_played guard: clamp to media duration if ms_played exceeds this
# multiple of the media's own duration (and media duration is known/nonzero).
_RUNAWAY_MULTIPLE = 2


# ------------------------------------------------------------------ helpers


def _split_artist_title(raw: str) -> tuple[str, str] | None:
    """Split an `"Artist - Title"` string on the FIRST " - ".

    Splitting on the first occurrence (not the last, and not by picking the
    "shortest" side) is correct for Apple's `Artist - Title` convention even
    when the artist or the title itself contains " - " later in the string
    (e.g. a title with a "(Live - 1978 Version)" suffix, or a two-part
    artist name) — the remainder after the first " - " belongs to the title.

    Returns (artist, title), both stripped, or None if no " - " is present.
    """
    if not raw:
        return None
    idx = raw.find(" - ")
    if idx == -1:
        return None
    artist = raw[:idx].strip()
    title = raw[idx + 3:].strip()
    if not artist or not title:
        return None
    return artist, title


_WS_RE = re.compile(r"\s+")


def _norm_title(title: str) -> str:
    """Casefold + collapse internal whitespace + strip, for join-key matching."""
    return _WS_RE.sub(" ", title).strip().casefold()


def _build_artist_map(src_dir: str) -> dict[str, str]:
    """Build {normalized_title: artist} from the two companion history files.

    Daily Tracks (`Track Description`) is preferred over Track Play History
    (`Track Name`) when both resolve the same title to different artists.
    """
    artist_map: dict[str, str] = {}

    # Track Play History first (lower priority) so Daily Tracks can overwrite it.
    track_play_path = os.path.join(src_dir, TRACK_PLAY_HISTORY_FILE)
    if os.path.exists(track_play_path):
        with open(track_play_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                pair = _split_artist_title(row.get("Track Name") or "")
                if pair is None:
                    continue
                artist, title = pair
                artist_map[_norm_title(title)] = artist

    # Daily Tracks second (preferred) so it wins on conflicts.
    daily_path = os.path.join(src_dir, DAILY_TRACKS_FILE)
    if os.path.exists(daily_path):
        with open(daily_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                pair = _split_artist_title(row.get("Track Description") or "")
                if pair is None:
                    continue
                artist, title = pair
                artist_map[_norm_title(title)] = artist

    return artist_map


def _parse_ts(raw: str) -> str | None:
    """Normalize an Apple timestamp (`2018-08-25T06:11:11.347Z`) to
    `"%Y-%m-%dT%H:%M:%SZ"` UTC, matching the Spotify export's format exactly.

    Returns None if `raw` is empty or unparseable.
    """
    if not raw:
        return None
    # Drop fractional seconds if present, then parse via fromisoformat.
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _platform_from_device_name(raw: str | None) -> str:
    """Map a raw `Client Device Name` user-agent-ish string to one of a small,
    fixed, non-identifying vocabulary: "iOS" / "Macintosh" / "Windows" /
    "Android" / "unknown".

    We do NOT return the raw string. `Client Device Name` values look like
    `"itunesstored/1.0 iOS/10.3.2 model/iPhone8,1 hwp/s8000 build/14F89 ..."`
    or `"iTunes/12.8 (Macintosh; OS X 10.13.6) AppleWebKit/605.3.8 ..."` —
    device model, hardware, and OS build strings that must not ship. Those
    identifiers eventually flow into `data/taste_timeline.json`, which is
    inlined into a PUBLICLY deployed page, so only a clean bucket token
    leaves this function.

    iPadOS is folded into "iOS" rather than split out: the real export has
    zero rows where "ipad" appears without also matching the iOS/iPhone
    pattern, so a separate bucket wouldn't be genuinely distinguishable here.

    These tokens are chosen to deliberately substring-match
    `streaming_history._PLATFORM_RULES` (case-insensitive): "iOS" contains
    "ios" -> mobile; "Macintosh" contains "mac" -> desktop; "Windows"
    contains "windows" -> desktop; "Android" contains "android" -> mobile.
    """
    if not raw:
        return "unknown"
    lower = raw.lower()
    if "ios/" in lower or "iphone" in lower or "ipad" in lower:
        return "iOS"
    if "macintosh" in lower or "os x" in lower or "mac os" in lower:
        return "Macintosh"
    if "windows" in lower:
        return "Windows"
    if "android" in lower:
        return "Android"
    return "unknown"


def _best_platform(row: dict) -> str:
    """Clean platform bucket derived from `Client Device Name` (the only
    column in this export that actually carries device/OS signal — see
    `_platform_from_device_name`). `Client Platform` is a constant "FUSE" on
    every real row and `Device Type` is blank on every real row, so neither
    is useful; `Source Type` is `ORIGINATING_DEVICE`/blank and carries no
    device signal either. Always returns a small fixed-vocabulary token,
    never a raw string.
    """
    return _platform_from_device_name(row.get("Client Device Name"))


def _load_overrides(path: str = OVERRIDES_PATH) -> dict[str, str]:
    """Load manual title -> artist overrides from `config/apple_artist_overrides.json`.

    Follows the same per-user-seed loading convention as `household.py`
    (`config/household_artists.txt`): a missing file is non-fatal — warn to
    stderr and return an empty map, no crash, no traceback.

    Keys in the JSON file are plain human-readable song titles (as seen in
    `Song Name`); they're normalized here with the SAME `_norm_title()` the
    parser uses for its real title-join, so a hand-written key matches
    exactly what the join would have looked up. Consulted only as a fallback
    when the real join fails to resolve an artist — see `build_apple_history`,
    where the override lookup only runs after `artist_map.get(...)` misses,
    so it can never shadow a genuine join hit.
    """
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        print(
            f"warning: {path} not found — no manual artist overrides will be applied",
            file=sys.stderr,
        )
        return {}
    return {_norm_title(title): artist for title, artist in raw.items()}


def _to_int(val: str | None) -> int | None:
    if val is None:
        return None
    val = val.strip()
    if not val:
        return None
    try:
        return int(float(val))
    except ValueError:
        return None


# ------------------------------------------------------------------ build_apple_history


def build_apple_history(src_dir: str = APPLE_DIR, out_path: str = APPLE_EVENTS_PATH) -> dict:
    """Parse the Apple Media Services export into normalized play events.

    Writes `{"generated_at", "source", "stats", "events"}` to `out_path` and
    returns the `stats` dict (also embedded in the written JSON).
    """
    artist_map = _build_artist_map(src_dir)
    # Look up the module global at call time (not as a bound default arg) so
    # tests can monkeypatch apple_history.OVERRIDES_PATH.
    overrides = _load_overrides(OVERRIDES_PATH)

    play_activity_path = os.path.join(src_dir, PLAY_ACTIVITY_FILE)

    total_rows = 0
    dropped = {
        "event_type": 0,       # LYRIC_DISPLAY etc.
        "no_song_name": 0,
        "no_timestamp": 0,
        "non_music_media_type": 0,   # VIDEO
        "non_music_item_type": 0,    # STREAM / NON_SONG_CLIP / ...
        "non_music_song_name": 0,    # NPR News and Culture / Apple Music 1
        "artist_unresolved": 0,
        "duplicate": 0,
    }
    ms_clamped_negative = 0
    ms_clamped_runaway = 0
    artist_resolved_via_override = 0

    events: list[dict] = []
    seen_keys: set[tuple[str, str, int]] = set()

    unique_songs_seen: set[str] = set()
    unique_songs_resolved: set[str] = set()

    # Detail on songs that remain unresolved even after overrides — feeds the
    # `apple-unresolved` report so the user can identify + fill gaps.
    # {norm_title: {"title": raw title first seen, "plays": int, "ms": int,
    #               "albums": Counter, "years": set[str]}}
    unresolved_detail: dict[str, dict] = {}

    with open(play_activity_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            total_rows += 1

            if row.get("Event Type") in _DROP_EVENT_TYPES:
                dropped["event_type"] += 1
                continue

            song_name = (row.get("Song Name") or "").strip()
            if not song_name:
                dropped["no_song_name"] += 1
                continue

            if (row.get("Media Type") or "").strip().upper() == "VIDEO":
                dropped["non_music_media_type"] += 1
                continue

            if (row.get("Item Type") or "").strip() in _DROP_ITEM_TYPES:
                dropped["non_music_item_type"] += 1
                continue

            if song_name in _DROP_SONG_NAMES:
                dropped["non_music_song_name"] += 1
                continue

            ts = _parse_ts(row.get("Event Start Timestamp") or "") or _parse_ts(
                row.get("Event End Timestamp") or ""
            )
            if ts is None:
                dropped["no_timestamp"] += 1
                continue

            norm_title = _norm_title(song_name)
            unique_songs_seen.add(norm_title)
            raw_ms = _to_int(row.get("Play Duration Milliseconds")) or 0

            # Real title-join always wins; the override map is consulted ONLY
            # as a fallback when the join misses, so it can never shadow a
            # genuine join hit.
            artist = artist_map.get(norm_title)
            via_override = False
            if not artist:
                artist = overrides.get(norm_title)
                via_override = artist is not None

            if not artist:
                dropped["artist_unresolved"] += 1
                d = unresolved_detail.setdefault(
                    norm_title,
                    {"title": song_name, "plays": 0, "ms": 0, "albums": Counter(), "years": set()},
                )
                d["plays"] += 1
                d["ms"] += max(raw_ms, 0)
                album_hint = (row.get("Album Name") or "").strip()
                if album_hint:
                    d["albums"][album_hint] += 1
                d["years"].add(ts[:4])
                continue

            unique_songs_resolved.add(norm_title)
            if via_override:
                artist_resolved_via_override += 1

            ms_played = raw_ms
            if ms_played < 0:
                ms_played = 0
                ms_clamped_negative += 1

            media_ms = _to_int(row.get("Media Duration In Milliseconds"))
            if media_ms and media_ms > 0 and ms_played > media_ms * _RUNAWAY_MULTIPLE:
                ms_played = media_ms
                ms_clamped_runaway += 1

            dedup_key = (ts, norm_title, ms_played)
            if dedup_key in seen_keys:
                dropped["duplicate"] += 1
                continue
            seen_keys.add(dedup_key)

            album_name = (row.get("Album Name") or "").strip() or None
            end_reason = (row.get("End Reason Type") or "").strip() or None
            feature = (row.get("Feature Name") or "").strip() or None
            platform = _best_platform(row)

            events.append(
                {
                    "ts": ts,
                    "ms_played": ms_played,
                    "master_metadata_album_artist_name": artist,
                    "master_metadata_track_name": song_name,
                    "master_metadata_album_album_name": album_name,
                    "spotify_track_uri": None,
                    "platform": platform,
                    "reason_start": None,
                    "shuffle": None,
                    "skipped": end_reason == "TRACK_SKIPPED_FORWARDS",
                    "service": "apple",
                    "apple_feature": feature,
                    "apple_end_reason": end_reason,
                }
            )

    events.sort(key=lambda e: e["ts"])

    unique_artists = {e["master_metadata_album_artist_name"] for e in events}
    unique_tracks = {
        (e["master_metadata_album_artist_name"], e["master_metadata_track_name"])
        for e in events
    }

    per_year: dict[str, int] = {}
    for e in events:
        year = e["ts"][:4]
        per_year[year] = per_year.get(year, 0) + 1
    per_year = dict(sorted(per_year.items()))

    platforms: dict[str, int] = {}
    for e in events:
        tok = e["platform"] or "unknown"
        platforms[tok] = platforms.get(tok, 0) + 1
    platforms = dict(sorted(platforms.items(), key=lambda kv: -kv[1]))

    resolution_rate = (
        round(len(unique_songs_resolved) / len(unique_songs_seen), 4)
        if unique_songs_seen
        else 0.0
    )

    stats = {
        "total_rows": total_rows,
        "dropped": dropped,
        "events_emitted": len(events),
        "unique_artists": len(unique_artists),
        "unique_tracks": len(unique_tracks),
        "unique_songs_seen": len(unique_songs_seen),
        "unique_songs_resolved": len(unique_songs_resolved),
        "artist_resolution_rate": resolution_rate,
        "per_year": per_year,
        "first_play": events[0]["ts"] if events else None,
        "last_play": events[-1]["ts"] if events else None,
        "ms_clamped_negative": ms_clamped_negative,
        "ms_clamped_runaway": ms_clamped_runaway,
        "platforms": platforms,
        "artist_resolved_via_override": artist_resolved_via_override,
    }

    # Songs still unresolved after overrides — feeds `apple-unresolved`'s
    # human-readable report. Kept OUTSIDE `stats` (not printed by
    # `apple-stats`) since it's a list, not a summary figure.
    unresolved_out = []
    for d in unresolved_detail.values():
        years = sorted(d["years"])
        unresolved_out.append(
            {
                "title": d["title"],
                "plays": d["plays"],
                "minutes": round(d["ms"] / 60_000, 1),
                "album": d["albums"].most_common(1)[0][0] if d["albums"] else None,
                "year_min": years[0] if years else None,
                "year_max": years[-1] if years else None,
            }
        )
    unresolved_out.sort(key=lambda x: -x["plays"])

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": os.path.basename(src_dir.rstrip(os.sep)),
        "stats": stats,
        "unresolved": unresolved_out,
        "events": events,
    }

    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    return stats


def iter_apple_events(path: str = APPLE_EVENTS_PATH):
    """Yield normalized Apple play events from the built JSON.

    Yields nothing (generator produces no items) if `path` doesn't exist —
    this is the seam a later phase calls to merge Apple events into the
    Spotify-derived timeline.
    """
    if not os.path.exists(path):
        return
    with open(path) as f:
        data = json.load(f)
    for e in data.get("events", []):
        yield e


def apple_favorites(src_dir: str = APPLE_DIR) -> list[dict]:
    """Parse Favorites.csv into a list of {"artist","title","liked_at","preference"}."""
    path = os.path.join(src_dir, FAVORITES_FILE)
    out: list[dict] = []
    if not os.path.exists(path):
        return out
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pair = _split_artist_title(row.get("Item Description") or "")
            if pair is None:
                continue
            artist, title = pair
            out.append(
                {
                    "artist": artist,
                    "title": title,
                    "liked_at": (row.get("Last Modified") or "").strip() or None,
                    "preference": (row.get("Preference") or "").strip() or None,
                }
            )
    return out


def write_unresolved_report(
    events_path: str = APPLE_EVENTS_PATH, out_path: str = UNRESOLVED_REPORT_PATH
) -> int:
    """Render the `unresolved` list from the last build into a human-readable
    Markdown report at `out_path` (default `data/apple_unresolved.md` —
    gitignored, personal listening data; never write this under the repo
    root or `docs/`). Returns the number of unresolved songs.

    Raises FileNotFoundError if `events_path` doesn't exist yet (caller
    should run `build_apple_history` / `cli.py apple-build` first).
    """
    with open(events_path) as f:
        data = json.load(f)
    unresolved = data.get("unresolved", [])

    lines = [
        "# Apple history — unresolved artists",
        "",
        f"Generated from `{os.path.basename(events_path)}` "
        f"(built {data.get('generated_at', '?')}).",
        "",
        "These songs appear in the Apple Music Play Activity export but their "
        "artist could not be resolved — via the title-join against the "
        "companion history files, or via `config/apple_artist_overrides.json` "
        "— so their plays are currently dropped from the parsed history.",
        "",
        "**To recover a song's plays:** add a line to "
        "`config/apple_artist_overrides.json` mapping its exact title (as "
        "shown below) to the correct artist, then re-run "
        "`.venv/bin/python cli.py apple-build`. The `Album hint` column is "
        "the `Album Name` seen on those rows — usually enough to identify "
        "the artist even for an ambiguous title.",
        "",
        "**Or automate the easy ones:** `.venv/bin/python cli.py apple-resolve` "
        "searches Spotify by title + album hint and writes tiered proposals "
        "with evidence to `data/apple_overrides_proposed.json`; re-run it with "
        "`--apply` to merge the high-confidence ones into the overrides file "
        "(hand-written entries are never overwritten). What's left below is "
        "mostly remix/EP singles whose album hint is just the song title "
        "again — those need a human.",
        "",
        f"**{len(unresolved)} unresolved songs, "
        f"{sum(u['plays'] for u in unresolved)} plays, "
        f"{round(sum(u['minutes'] for u in unresolved), 1)} minutes total.**",
        "",
        "| Title | Plays | Minutes | Album hint | Years |",
        "|---|---:|---:|---|---|",
    ]
    for u in unresolved:
        years = (
            u["year_min"]
            if u["year_min"] == u["year_max"]
            else f"{u['year_min']}–{u['year_max']}"
        ) if u["year_min"] else "?"
        album = u["album"] or "_(none logged)_"
        # Escape pipes so a title/album with "|" in it doesn't break the table.
        title = u["title"].replace("|", "\\|")
        album = album.replace("|", "\\|")
        lines.append(
            f"| {title} | {u['plays']} | {u['minutes']} | {album} | {years} |"
        )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return len(unresolved)


# ---------------------------------------------------------------- CLI handlers


def _cmd_apple_build(args) -> int:
    path = os.path.join(args.src, PLAY_ACTIVITY_FILE)
    if not os.path.exists(path):
        print(f"no {PLAY_ACTIVITY_FILE} under {args.src}", file=sys.stderr)
        return 1
    stats = build_apple_history(args.src)
    print(APPLE_EVENTS_PATH)
    print(
        f"  {stats['total_rows']} rows -> {stats['events_emitted']} events, "
        f"{stats['unique_artists']} artists, {stats['artist_resolution_rate']:.1%} resolved "
        f"({stats['artist_resolved_via_override']} via override), "
        f"{stats['first_play']}→{stats['last_play']}",
        file=sys.stderr,
    )
    return 0


def _cmd_apple_stats(args) -> int:
    if not os.path.exists(APPLE_EVENTS_PATH):
        print("no apple history events; run `cli.py apple-build` first", file=sys.stderr)
        return 1
    with open(APPLE_EVENTS_PATH) as f:
        data = json.load(f)
    print(json.dumps(data.get("stats", {}), ensure_ascii=False, indent=2))
    print(f"  from {os.path.basename(APPLE_EVENTS_PATH)}", file=sys.stderr)
    return 0


def _cmd_apple_unresolved(args) -> int:
    if not os.path.exists(APPLE_EVENTS_PATH):
        print("no apple history events; run `cli.py apple-build` first", file=sys.stderr)
        return 1
    n = write_unresolved_report()
    print(UNRESOLVED_REPORT_PATH)
    print(f"  {n} songs still unresolved after overrides", file=sys.stderr)
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--src", default=APPLE_DIR)
    b.set_defaults(func=_cmd_apple_build)

    st = sub.add_parser("stats")
    st.set_defaults(func=_cmd_apple_stats)

    un = sub.add_parser("unresolved")
    un.set_defaults(func=_cmd_apple_unresolved)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
