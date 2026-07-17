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

# Artists forced to kids/household regardless of tags.
HOUSEHOLD_ARTISTS: frozenset[str] = frozenset(
    {
        "CoComelon",
        "Pinkfong",
        "Elmo",
        "Bluey",
        "Kristen Bell",
        "Idina Menzel",
        "Auli'i Cravalho",
        "Mark Mancina",
        "Josh Gad",
        "Jonathan Groff",
        "Super Simple Songs",
        "The Wiggles",
        "Bruce Brus",           # white-noise sleep audio (tags say electronic; not taste)
        "Nursery Rhymes Band",
    }
)

_WHITE_NOISE_RE = re.compile(r"white\s+noise", re.IGNORECASE)

# ------------------------------------------------------------------ helpers


def _is_household(name: str) -> bool:
    """True when an artist name is in the household set or matches white-noise pattern."""
    return name in HOUSEHOLD_ARTISTS or bool(_WHITE_NOISE_RE.search(name))


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


# ------------------------------------------------------------------ build entry point


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
    }

    with open(TIMELINE_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

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
