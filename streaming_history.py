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
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
EXPORT_DIR = os.path.join(DATA_DIR, "Spotify Extended Streaming History")
SUMMARY_PATH = os.path.join(DATA_DIR, "history_summary.json")

PLAY_MS = 30_000  # >= 30s listened counts as a play (Spotify's own threshold)
FORGOTTEN_MIN_PLAYS = 40  # lifetime plays needed to call an artist a past favorite
FORGOTTEN_QUIET_YEARS = 2  # no plays in this many recent years => "forgotten"


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


def build_history(src_dir: str = EXPORT_DIR, out_path: str = SUMMARY_PATH) -> dict:
    """Aggregate the raw export into one summary dict and write it to out_path."""
    artists: dict[str, dict] = defaultdict(
        lambda: {"plays": 0, "ms": 0, "skips": 0, "years": defaultdict(int)}
    )
    tracks: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"plays": 0, "ms": 0, "uri": None, "years": set()}
    )
    years: dict[str, dict] = defaultdict(lambda: {"plays": 0, "ms": 0, "skips": 0})
    n_events = 0
    first_ts, last_ts = None, None

    for e in _iter_events(src_dir):
        n_events += 1
        ts = e["ts"]
        year = ts[:4]
        ms = e.get("ms_played") or 0
        artist = e["master_metadata_album_artist_name"]
        title = e.get("master_metadata_track_name") or "?"

        first_ts = ts if first_ts is None or ts < first_ts else first_ts
        last_ts = ts if last_ts is None or ts > last_ts else last_ts

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
            t["uri"] = e["spotify_track_uri"]
            t["years"].add(year)
        else:
            a["skips"] += 1
            y["skips"] += 1

    def _hours(ms: int) -> float:
        return round(ms / 3_600_000, 1)

    # All-time artists (top 200), with per-year play curves for era detection.
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

    # Per-year leaderboards.
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

    # Forgotten favorites: heavy lifetime plays, silent in the recent years.
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

    summary = {
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
