"""Cross-session discovery ledger.

Append-only record of the artists/tracks Claude has surfaced across sessions, so a
future session can (a) dedupe against past suggestions — don't re-recommend the same
lateral pick weeks apart — and (b) see what actually landed. DUMB layer: it records
and reads JSON lines; the session decides what to log and how to use it. The taste
dump tells you what the user *already knows*; this log tells you what *Claude has
already proposed*. Filter new candidates against BOTH.

Stored at data/discovery_log.jsonl (gitignored), one JSON object per line:
  {"ts", "artist", "title"?, "uri"?, "recipe"?, "playlist"?, "kept"?}

Library use:
    from discovery_log import append, surfaced_artists, recent
    append([{"artist": "Tyler Childers", "title": "Feathered Indians"}], recipe="6")
    known = surfaced_artists()          # lowercased set, for dedup

CLI use:
    python discovery_log.py add --artist "Tyler Childers" [--title T] [--uri U] \
        [--recipe 6] [--playlist URL]
    python discovery_log.py add --from-tsv picks.tsv [--recipe 6] [--playlist URL]
        # picks.tsv = artist<TAB>title<TAB>uri per line (title/uri optional)
    python discovery_log.py artists        # known surfaced artist names, one per line
    python discovery_log.py recent [--limit 20]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOG_PATH = os.path.join(DATA_DIR, "discovery_log.jsonl")


def append(records: list[dict], recipe: str | None = None,
           playlist: str | None = None) -> int:
    """Append `records` to the ledger, stamping each with a UTC ts (+ recipe/playlist).

    Each record should carry at least an "artist"; "title"/"uri" are optional. A
    record's own keys win over the shared `recipe`/`playlist`. Returns the count
    written. Records without an artist are skipped.
    """
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for rec in records:
        if not rec.get("artist"):
            continue
        base = {"ts": now}
        if recipe is not None:
            base["recipe"] = recipe
        if playlist is not None:
            base["playlist"] = playlist
        rows.append({**base, **rec})
    if not rows:
        return 0
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def load() -> list[dict]:
    """Return every ledger entry in write order ([] if the log doesn't exist)."""
    if not os.path.exists(LOG_PATH):
        return []
    out = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def surfaced_artists() -> set[str]:
    """Lowercased set of artist names Claude has already surfaced (for dedup)."""
    return {r["artist"].lower() for r in load() if r.get("artist")}


def surfaced_uris() -> set[str]:
    """Set of track URIs already surfaced (precise per-track dedup)."""
    return {r["uri"] for r in load() if r.get("uri")}


def recent(limit: int = 20) -> list[dict]:
    """The last `limit` ledger entries (most recent last)."""
    rows = load()
    return rows[-limit:] if limit else rows


# --------------------------------------------------------------------------- CLI


def _records_from_tsv(path: str) -> list[dict]:
    """Parse artist<TAB>title<TAB>uri lines (title/uri optional) into records."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if not parts or not parts[0].strip():
                continue
            rec = {"artist": parts[0].strip()}
            if len(parts) > 1 and parts[1].strip():
                rec["title"] = parts[1].strip()
            if len(parts) > 2 and parts[2].strip():
                rec["uri"] = parts[2].strip()
            records.append(rec)
    return records


def _cmd_log_add(args) -> int:
    if args.from_tsv:
        records = _records_from_tsv(args.from_tsv)
    elif args.artist:
        rec = {"artist": args.artist}
        if args.title:
            rec["title"] = args.title
        if args.uri:
            rec["uri"] = args.uri
        records = [rec]
    else:
        print("Provide --artist or --from-tsv.", file=sys.stderr)
        return 1
    n = append(records, recipe=args.recipe, playlist=args.playlist)
    print(LOG_PATH)
    print(f"  logged {n} discovery record(s)", file=sys.stderr)
    return 0 if n else 1


def _cmd_log_artists(args) -> int:
    names = sorted(surfaced_artists())
    for n in names:
        print(n)
    print(f"  {len(names)} distinct artist(s) surfaced to date", file=sys.stderr)
    return 0


def _cmd_log_recent(args) -> int:
    rows = recent(args.limit)
    for r in rows:
        title = f" — {r['title']}" if r.get("title") else ""
        tag = f"  [{r['recipe']}]" if r.get("recipe") else ""
        print(f"{r.get('ts', '?')}\t{r.get('artist', '?')}{title}{tag}")
    print(f"  {len(rows)} recent entr(ies)", file=sys.stderr)
    return 0


def _add_log_add_args(parser) -> None:
    """Shared so cli.py and this module declare the `add` flags identically."""
    parser.add_argument("--artist", help="Single artist to log.")
    parser.add_argument("--title", help="Track title (optional).")
    parser.add_argument("--uri", help="Spotify track URI (optional).")
    parser.add_argument("--from-tsv", help="File: artist<TAB>title<TAB>uri per line.")
    parser.add_argument("--recipe", help="Recipe/angle tag, applied to all records.")
    parser.add_argument("--playlist", help="Playlist URL these picks went into.")


def main() -> int:
    p = argparse.ArgumentParser(description="Cross-session discovery ledger.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="Append surfaced artist(s)/track(s) to the ledger.")
    _add_log_add_args(a)
    a.set_defaults(func=_cmd_log_add)

    ar = sub.add_parser("artists", help="Print distinct artist names surfaced to date.")
    ar.set_defaults(func=_cmd_log_artists)

    rc = sub.add_parser("recent", help="Print the most recent ledger entries.")
    rc.add_argument("--limit", type=int, default=20)
    rc.set_defaults(func=_cmd_log_recent)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
