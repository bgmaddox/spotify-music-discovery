"""Propose artists for the Apple plays whose title-join couldn't resolve one.

`apple_history.py` recovers an artist for each Apple Music play by joining the
`Song Name` against the `"Artist - Title"` strings in the two companion export
files, with `config/apple_artist_overrides.json` as a manual fallback. The
songs that survive both are dropped from the history entirely (their plays are
lost) and listed in `data/apple_unresolved.md`.

This module automates what a human does with that report: take the song title
plus its **album hint** (the `Album Name` on those rows) and ask Spotify's
`search` "which artist has this track on this album?". The album hint is the
whole ballgame — it's what makes `Alive 2007` → Daft Punk or `Get Rich or Die
Tryin'` → 50 Cent unambiguous, and it's how the existing hand-seeded overrides
were derived.

    python cli.py apple-resolve                 # propose only (writes the review file)
    python cli.py apple-resolve --apply         # also merge the `high` tier into config/
    python cli.py apple-resolve --min-plays 2   # only bother with repeat plays

## Precedence (unchanged)

The real title-join still wins over everything; `config/apple_artist_overrides.json`
is consulted only when it misses. This module only ever *adds* keys to that file
that aren't already there — an existing manual override is never overwritten,
so a human correction always beats an auto-proposal.

## Confidence tiers

Nothing is auto-applied without `--apply`, and `--apply` only writes the `high`
tier. `high` requires ALL of:

  1. The album hint is *informative* — it isn't just the song title again.
     Half this backlog is remix/EP singles (`Collide (Remixes) - EP`,
     `Starry Eyed (Remixes) - EP`) where the hint carries zero extra signal and
     picking the top search hit would just be guessing by popularity. Those are
     tiered `ambiguous_hint` and left for a human.
  2. A search hit whose **track title** core matches the song (≥ MIN_RATIO)
     AND whose **album name** agrees with the hint — either core similarity
     ≥ MIN_RATIO, or the release name is the hint plus a *parenthesized*
     annotation (`Spring Awakening` → `Spring Awakening (Original Broadway
     Cast Recording)`; see `name_match.parenthetical_extension`).
  3. Every qualifying hit agrees on the same artist. Two different artists with
     the same song on the same-named album means we can't tell them apart, so
     it drops to `review`.

Everything else lands in `review` / `ambiguous_hint` / `non_music` / `no_match`
in the proposals file, each with its evidence, for a human to skim.

Output: `data/apple_overrides_proposed.json` (gitignored — it's derived from
personal listening data).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time

from enrich_meta import _cache_read, _cache_write
from name_match import (
    album_core,
    album_similarity,
    artist_key,
    normalize,
    parenthetical_extension,
    title_similarity,
    track_core,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EVENTS_PATH = os.path.join(DATA_DIR, "apple_history_events.json")
PROPOSALS_PATH = os.path.join(DATA_DIR, "apple_overrides_proposed.json")
OVERRIDES_PATH = os.path.join(BASE_DIR, "config", "apple_artist_overrides.json")

# Search needs an app token but no user scope (same rule as tools.SEARCH_SCOPES),
# so this never needs a write-capable token.
SEARCH_SCOPES: list[str] = []

MIN_RATIO = 0.87      # core-similarity floor for both title and album agreement
SEARCH_LIMIT = 20     # candidates per query
SLEEP_BETWEEN = 0.15  # seconds between uncached searches — be polite to the API

TIER_HIGH = "high"
TIER_REVIEW = "review"
TIER_AMBIGUOUS = "ambiguous_hint"
TIER_NON_MUSIC = "non_music"
TIER_NO_MATCH = "no_match"

APPLIED_TIERS = (TIER_HIGH,)

# Spoken-word / radio / non-song material that should be recognized rather than
# forced onto some artist. Matched (case-insensitively) against title + hint.
# Phrases only — never a bare common word. A song really can be called "Talk",
# "News", or "Station", and mislabeling one as non-music would silently drop a
# real play; missing a stray radio row instead just leaves it in `no_match`,
# which is harmless. Under-detection is the safe direction here.
_NON_MUSIC_PATTERNS = [
    r"\bnpr\b", r"\bbbc (radio|news|world)\b", r"\bespn\b", r"\bpodcast\b",
    r"\bradio hour\b", r"\bradio station\b", r"\btalk radio\b", r"\bnews hour\b",
    r"\bsermon\b", r"\baudiobook\b", r"\bchapter \d", r"\bthis american life\b",
    r"\bted talk\b", r"\bwhite noise\b", r"\bsleep sounds\b",
    r"\bnature sounds\b", r"\bbeats 1\b", r"\bapple music 1\b",
    r"\bnews and culture\b", r"\bguided meditation\b",
]
_NON_MUSIC_RE = re.compile("|".join(_NON_MUSIC_PATTERNS), re.I)


# ------------------------------------------------------------------ classification


def is_non_music(title: str, album_hint: str | None) -> bool:
    """True when the title/album hint reads as radio, spoken word, or ambience.

    Deliberately narrow: `apple_history` already drops STREAM/NON_SONG_CLIP rows
    by Item Type, so anything reaching here is tagged as a song. This only
    catches the leftovers (a radio show logged as a track, a talk recording).
    """
    blob = f"{title} {album_hint or ''}"
    return bool(_NON_MUSIC_RE.search(blob))


def hint_is_uninformative(title: str, album_hint: str | None) -> bool:
    """True when the album hint is just the song title again.

    `Collide` / `Collide (Remixes) - EP`, `Starry Eyed` / `Starry Eyed
    (Remixes) - EP`, `Pogo` / `Pogo - Single`: single/EP/remix releases named
    after their own track. The hint adds no independent evidence, so a search
    can only rank by popularity — a guess, not a resolution.

    Missing hints count as uninformative too.
    """
    if not album_hint:
        return True
    t, a = track_core(title), album_core(album_hint)
    if not a:
        return True
    if t and (t == a or a.startswith(t) or t.startswith(a)):
        return True
    # Also catch the un-stripped forms ("Collide (Remixes)" vs "Collide").
    return title_similarity(title, album_hint) >= MIN_RATIO


# ------------------------------------------------------------------ search


def _queries(title: str, album_hint: str) -> list[str]:
    """Query ladder, most precise first (mirrors tools._best_track's shape).

    The raw fielded query is tried before the punctuation-stripped one because
    Spotify indexes the real title; the stripped form then rescues titles whose
    punctuation Apple and Spotify disagree about (`Sittin' at a Bar`), and the
    loose free-text query is the last resort.
    """
    t_core, a_core = track_core(title), album_core(album_hint)
    out = [
        f'track:"{title}" album:"{album_hint}"',
        f'track:"{t_core}" album:"{a_core}"',
        f"{t_core} {a_core}",
    ]
    seen, uniq = set(), []
    for q in out:
        if q not in seen:
            seen.add(q)
            uniq.append(q)
    return uniq


def _search_and_evaluate(sp, title: str, album_hint: str) -> dict:
    """Walk the query ladder, stopping as soon as a high-confidence match lands.

    Later queries are looser, so an early `high` is the most trustworthy answer
    available; if none of them reaches `high`, the best (weakest) verdict from
    the accumulated candidates is returned so the reason is still informative.
    """
    items: list[dict] = []
    seen: set[str] = set()
    verdict = _evaluate(title, album_hint, [])
    for q in _queries(title, album_hint):
        try:
            res = sp.search(q=q, type="track", limit=SEARCH_LIMIT)
        except Exception as e:  # noqa: BLE001 — one bad query must not kill the run
            print(f"  search error for {q!r}: {e}", file=sys.stderr)
            continue
        time.sleep(SLEEP_BETWEEN)
        for it in ((res.get("tracks") or {}).get("items")) or []:
            if it and it.get("id") not in seen:
                seen.add(it.get("id"))
                items.append(it)
        verdict = _evaluate(title, album_hint, items)
        if verdict["tier"] == TIER_HIGH:
            break
    return verdict


def _evaluate(title: str, album_hint: str, items: list[dict]) -> dict:
    """Turn raw search hits into a tiered proposal (pure — no network)."""
    qualifying: list[dict] = []
    near: list[dict] = []

    for it in items:
        artists = it.get("artists") or []
        cand_artist = (artists[0].get("name") if artists else None) or ""
        cand_title = it.get("name") or ""
        cand_album = ((it.get("album") or {}).get("name")) or ""
        t_ratio = title_similarity(title, cand_title)
        a_ratio = album_similarity(album_hint, cand_album)
        # The official release often annotates the hint in brackets
        # ("Spring Awakening" → "Spring Awakening (Original Broadway Cast
        # Recording)"), which scores badly but is the same record.
        a_prefix = parenthetical_extension(album_hint, cand_album)
        ev = {
            "artist": cand_artist,
            "track": cand_title,
            "album": cand_album,
            "title_ratio": round(t_ratio, 3),
            "album_ratio": round(a_ratio, 3),
            "uri": it.get("uri"),
        }
        if a_prefix:
            ev["album_prefix_match"] = True
        if t_ratio >= MIN_RATIO and (a_ratio >= MIN_RATIO or a_prefix):
            qualifying.append(ev)
        elif t_ratio >= MIN_RATIO:
            near.append(ev)

    if not qualifying:
        if near:
            best = max(near, key=lambda e: e["album_ratio"])
            return {
                "tier": TIER_REVIEW,
                "artist": best["artist"],
                "evidence": best,
                "reason": (
                    "title matched but the album hint did not "
                    f"(album_ratio {best['album_ratio']} < {MIN_RATIO})"
                ),
            }
        return {
            "tier": TIER_NO_MATCH,
            "artist": None,
            "evidence": None,
            "reason": "no search hit matched the title",
        }

    distinct = {artist_key(e["artist"]) for e in qualifying}
    best = max(qualifying, key=lambda e: (e["album_ratio"], e["title_ratio"]))
    if len(distinct) > 1:
        return {
            "tier": TIER_REVIEW,
            "artist": best["artist"],
            "evidence": best,
            "alternatives": sorted({e["artist"] for e in qualifying}),
            "reason": (
                f"{len(distinct)} different artists match this title+album — ambiguous"
            ),
        }
    return {
        "tier": TIER_HIGH,
        "artist": best["artist"],
        "evidence": best,
        "reason": "title and album hint both matched, single artist agrees",
    }


def propose_for_song(sp, entry: dict, use_cache: bool = True) -> dict:
    """Propose an artist for one unresolved-song record from the Apple build.

    `entry` is an item of the `unresolved` list in
    `data/apple_history_events.json`: {title, plays, minutes, album, year_min,
    year_max}. Returns the proposal record written to the review file.
    """
    title = entry.get("title") or ""
    hint = entry.get("album")
    base = {
        "title": title,
        "album_hint": hint,
        "plays": entry.get("plays"),
        "minutes": entry.get("minutes"),
        "years": (
            entry.get("year_min")
            if entry.get("year_min") == entry.get("year_max")
            else f"{entry.get('year_min')}-{entry.get('year_max')}"
        ),
    }

    if is_non_music(title, hint):
        return {
            **base,
            "tier": TIER_NON_MUSIC,
            "artist": None,
            "evidence": None,
            "reason": "reads as radio / spoken word / ambience, not a song",
        }
    if hint_is_uninformative(title, hint):
        return {
            **base,
            "tier": TIER_AMBIGUOUS,
            "artist": None,
            "evidence": None,
            "reason": (
                "album hint is just the song title again (single/EP/remix release) "
                "— no independent evidence, left for a human"
            ),
        }

    key = f"{normalize(title)}||{normalize(hint)}"
    cached = _cache_read("apple_artist", key) if use_cache else None
    if cached is None:
        cached = _search_and_evaluate(sp, title, hint)
        if use_cache:
            _cache_write("apple_artist", key, cached)
    return {**base, **cached}


def propose_all(
    sp, entries: list[dict], min_plays: int = 1, limit: int | None = None
) -> list[dict]:
    """Propose artists for every unresolved song, highest play count first."""
    todo = [e for e in entries if (e.get("plays") or 0) >= min_plays]
    todo.sort(key=lambda e: -(e.get("plays") or 0))
    if limit:
        todo = todo[:limit]
    return [propose_for_song(sp, e) for e in todo]


def tier_counts(proposals: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in proposals:
        counts[p["tier"]] = counts.get(p["tier"], 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


# ------------------------------------------------------------------ I/O


def load_unresolved(events_path: str = EVENTS_PATH) -> list[dict]:
    """Read the `unresolved` list from the last `cli.py apple-build`."""
    with open(events_path) as f:
        return json.load(f).get("unresolved", [])


def write_proposals(proposals: list[dict], path: str = PROPOSALS_PATH) -> str:
    """Write the reviewable proposals file; returns its path."""
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "min_ratio": MIN_RATIO,
        "applied_tiers": list(APPLIED_TIERS),
        "stats": {
            "songs": len(proposals),
            "plays": sum(p.get("plays") or 0 for p in proposals),
            "by_tier": tier_counts(proposals),
            "plays_by_tier": {
                t: sum(p.get("plays") or 0 for p in proposals if p["tier"] == t)
                for t in tier_counts(proposals)
            },
        },
        "proposals": proposals,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return path


def apply_proposals(
    proposals: list[dict],
    overrides_path: str = OVERRIDES_PATH,
    tiers: tuple[str, ...] = APPLIED_TIERS,
) -> tuple[int, int]:
    """Merge the accepted tiers into `config/apple_artist_overrides.json`.

    Returns (added, skipped_existing). Existing keys are NEVER overwritten — a
    hand-written override always beats an auto-proposal (and the real title-join
    still beats both, inside `apple_history`).
    """
    try:
        with open(overrides_path, encoding="utf-8") as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = {}

    # Match apple_history's own normalization so a differently-punctuated key
    # can't sneak in as a "new" duplicate of an existing override.
    existing_keys = {normalize(k) for k in existing}
    added = skipped = 0
    for p in proposals:
        if p.get("tier") not in tiers or not p.get("artist"):
            continue
        if normalize(p["title"]) in existing_keys:
            skipped += 1
            continue
        existing[p["title"]] = p["artist"]
        existing_keys.add(normalize(p["title"]))
        added += 1

    if added:
        with open(overrides_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return added, skipped


# ------------------------------------------------------------------ CLI handler


def _cmd_apple_resolve(args) -> int:
    if not os.path.exists(args.events_path):
        print(
            "no apple history events; run `cli.py apple-build` first", file=sys.stderr
        )
        return 1
    entries = load_unresolved(args.events_path)
    if not entries:
        print("nothing unresolved — no proposals to make", file=sys.stderr)
        return 0

    from auth import get_client

    sp = get_client(SEARCH_SCOPES)
    proposals = propose_all(
        sp, entries, min_plays=args.min_plays, limit=args.limit
    )
    path = write_proposals(proposals, args.out)

    counts = tier_counts(proposals)
    print(path)
    print(
        f"  {len(proposals)} songs → "
        + ", ".join(f"{t} {n}" for t, n in counts.items()),
        file=sys.stderr,
    )
    if args.apply:
        added, skipped = apply_proposals(proposals, args.overrides_path)
        print(
            f"  applied {added} '{TIER_HIGH}' proposal(s) to "
            f"{os.path.basename(args.overrides_path)}"
            + (f" ({skipped} already present)" if skipped else "")
            + " — re-run `cli.py apple-build`",
            file=sys.stderr,
        )
    else:
        n_high = counts.get(TIER_HIGH, 0)
        print(
            f"  {n_high} high-confidence proposal(s) NOT applied — review {path}, "
            "then re-run with --apply",
            file=sys.stderr,
        )
    return 0


def _add_apple_resolve_args(p) -> None:
    p.add_argument(
        "--apply",
        action="store_true",
        help="Merge the high-confidence proposals into config/apple_artist_overrides.json.",
    )
    p.add_argument(
        "--min-plays", type=int, default=1, help="Only consider songs with >= N plays."
    )
    p.add_argument("--limit", type=int, default=None, help="Cap songs processed.")
    p.add_argument("--out", default=PROPOSALS_PATH, help="Proposals output path.")
    p.add_argument("--events-path", default=EVENTS_PATH)
    p.add_argument("--overrides-path", default=OVERRIDES_PATH)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    _add_apple_resolve_args(p)
    p.set_defaults(func=_cmd_apple_resolve)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
