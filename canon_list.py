"""Published critics' canon lists, tiered against the user's own listening history.

The point of this module is Recipe 35 ("Canon crawl"): a playlist whose candidate
pool is *fixed* to a published greatest-albums list, so the only judgment left is
which rungs of that list to climb and in what order.

A raw 300-row list is useless to a session on its own — the interesting structure
is the **overlap** with what the user has actually played. So the accessor here
does not hand back the list; it hands back the list *sorted into tiers*:

  lived_in    — the album itself has real play depth (>= LIVED_IN_PLAYS)
  brushed     — the album was touched, but barely (1 .. LIVED_IN_PLAYS-1 plays)
  near_miss   — the ARTIST is known and liked, but this record was never opened.
                The richest tier: low risk, high payoff, and the biggest.
  unheard     — the artist has never been played at all

``near_miss`` is the reason the module exists. "Dolly Parton, 66 plays, zero of
*Coat of Many Colors*" is a far better playlist candidate than either a record
the user already wears out or a total stranger, and nothing else in the toolkit
surfaces that shape.

Follows the project's summarizing-accessor convention (``taste-snapshot``,
``history-snapshot``): sessions call ``cli.py canon-snapshot`` (~2k tokens) and
never read ``knowledge/paste300_albums.json`` (~300 rows) directly.

Name matching reuses ``name_match`` — the same normalization the album-art
name-search path uses. Do NOT hand-roll a second normalizer here; a canon album
matching under one set of rules and failing under another is exactly the drift
that ``name_match`` exists to prevent.
"""

from __future__ import annotations

import collections
import json
import os

import name_match

LISTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")
DEFAULT_LIST = os.path.join(LISTS_DIR, "paste300_albums.json")

# An album with this many plays counts as genuinely "lived in" rather than sampled.
# Below it, a record almost always means "one track came up on shuffle once" —
# 110 of the 300 sat at exactly 1 play on the first run, which is not listening.
LIVED_IN_PLAYS = 15

# Artist plays below this are too thin to call the artist "known and liked", so a
# near-miss on them is really an unheard record with a coincidental brush.
NEAR_MISS_MIN_ARTIST_PLAYS = 4


def load_list(path: str = DEFAULT_LIST) -> dict:
    """Load a canon list file. Returns the full document (meta + ``albums``)."""
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    albums = doc.get("albums") or []
    if not albums:
        raise ValueError(f"{path}: no albums in list")
    return doc


def _album_matches(want_core: str, got_core: str) -> bool:
    """Is ``got_core`` the same record as ``want_core``?

    Deliberately looser than the album-art search gate (which needs >= 0.87
    similarity before it will paint a cover onto a record). Here a false positive
    only demotes a candidate out of the playlist pool, while a false negative
    would tell the user they've never heard a record they play constantly — the
    more embarrassing error. So a containment hit counts, which catches reissue
    and edition drift ("Aquemini" vs "Aquemini (Explicit)") without a threshold.
    """
    if not want_core or not got_core:
        return False
    return want_core == got_core or want_core in got_core or got_core in want_core


def tier_list(
    artist_plays: collections.Counter | dict,
    album_plays: collections.Counter | dict,
    path: str = DEFAULT_LIST,
    known_artists: set[str] | None = None,
) -> dict:
    """Sort a canon list into the four overlap tiers.

    ``artist_plays`` maps ``name_match.artist_key(artist) -> play count``.
    ``album_plays`` maps ``(artist_key, album_core) -> play count``.
    Both are built by the caller from the merged history (see
    ``cli.py canon-snapshot``), so this function stays pure and testable.

    ``known_artists`` (artist_key strings) is the second opinion, and it is not
    optional in practice. The export is not the whole truth: on the first run
    Erykah Badu showed a single play across 13 years of history — below
    ``NEAR_MISS_MIN_ARTIST_PLAYS``, so "unheard" — yet sat in the taste dump's
    ``top_tracks``, because the Spotify API's recency-weighted windows see plays
    newer than the export's last event. Calling her unheard would have told the
    user they'd never met an artist they were playing that week. Any artist in
    this set is therefore at minimum a ``near_miss``, regardless of export count,
    and is flagged ``library_only`` when the export shows nothing at all.
    """
    doc = load_list(path)
    known_artists = known_artists or set()

    by_artist: dict[str, list] = collections.defaultdict(list)
    for (akey, acore), n in dict(album_plays).items():
        by_artist[akey].append((acore, n))

    tiers: dict[str, list] = {"lived_in": [], "brushed": [], "near_miss": [], "unheard": []}

    for row in doc["albums"]:
        akey = name_match.artist_key(row["artist"])
        acore = name_match.album_core(row["album"])
        ap = int(dict(artist_plays).get(akey, 0))

        bp = 0
        for got_core, n in by_artist.get(akey, ()):
            if _album_matches(acore, got_core):
                bp += int(n)

        in_library = akey in known_artists
        rec = dict(row, artist_plays=ap, album_plays=bp)
        if in_library and ap == 0:
            rec["library_only"] = True

        if bp >= LIVED_IN_PLAYS:
            tiers["lived_in"].append(rec)
        elif bp > 0:
            tiers["brushed"].append(rec)
        elif ap >= NEAR_MISS_MIN_ARTIST_PLAYS or in_library:
            tiers["near_miss"].append(rec)
        else:
            tiers["unheard"].append(rec)

    tiers["lived_in"].sort(key=lambda r: -r["album_plays"])
    tiers["brushed"].sort(key=lambda r: (-r["album_plays"], -r["artist_plays"]))
    tiers["near_miss"].sort(key=lambda r: -r["artist_plays"])
    tiers["unheard"].sort(key=lambda r: r["rank"])

    return {
        "source": doc.get("source"),
        "url": doc.get("url"),
        "total": len(doc["albums"]),
        "counts": {k: len(v) for k, v in tiers.items()},
        **tiers,
    }


def known_artist_keys() -> set[str]:
    """``discovery_log.known_listened_artists()`` re-keyed through ``name_match``.

    That function returns lowercased raw names; every key in this module is an
    ``artist_key`` (leading "the" dropped, punctuation folded). Comparing the two
    directly would silently miss "The Beatles" vs "beatles".
    """
    try:
        import discovery_log
    except Exception:
        return set()
    try:
        return {name_match.artist_key(n) for n in discovery_log.known_listened_artists()}
    except Exception:
        return set()


def snapshot(
    artist_plays,
    album_plays,
    path: str = DEFAULT_LIST,
    near_miss_n: int = 60,
    unheard_n: int = 45,
    known_artists: set[str] | None = None,
) -> dict:
    """A token-bounded digest of ``tier_list`` — what a session actually reads.

    Truncates the two big discovery tiers (``near_miss`` is ~85 rows, ``unheard``
    ~80) to their most useful heads: near-misses ranked by how much the user
    already likes the artist, unheard ranked by the critics' own ordering. The
    untruncated counts stay in ``counts`` so a session can tell it is looking at
    a window rather than the whole tier.
    """
    t = tier_list(artist_plays, album_plays, path, known_artists)

    def fmt(rows):
        return [
            f"#{r['rank']} {r['artist']} — {r['album']} ({r['year']})"
            f" · album {r['album_plays']} · artist {r['artist_plays']}"
            + (" · in library, unplayed in export" if r.get("library_only") else "")
            for r in rows
        ]

    return {
        "source": t["source"],
        "total": t["total"],
        "counts": t["counts"],
        "lived_in": fmt(t["lived_in"]),
        "brushed": fmt(t["brushed"][:40]),
        "near_miss": fmt(t["near_miss"][:near_miss_n]),
        "unheard": [
            f"#{r['rank']} {r['artist']} — {r['album']} ({r['year']})"
            for r in t["unheard"][:unheard_n]
        ],
    }


def counts_from_history(src_dir: str | None = None) -> tuple[dict, dict]:
    """Build the two play-count maps ``tier_list`` needs from the merged history.

    One pass over the unified Spotify+Apple event stream. The summary's
    ``top_albums`` cannot serve here — it is capped at 80 records, and the whole
    point of the tiering is to reach the long tail where the near-misses live.

    Household plays are excluded (the kids-music layer would otherwise put
    CoComelon-adjacent noise nowhere useful, and it is not taste signal anyway).
    """
    import streaming_history as sh
    from household import is_household

    artist_plays: dict = collections.Counter()
    album_plays: dict = collections.Counter()

    kwargs = {"src_dir": src_dir} if src_dir else {}
    for e in sh._iter_events(**kwargs):
        if (e.get("ms_played") or 0) < sh.PLAY_MS:
            continue
        artist = e.get("master_metadata_album_artist_name")
        if not artist or is_household(artist):
            continue
        akey = name_match.artist_key(artist)
        artist_plays[akey] += 1
        album = e.get("master_metadata_album_album_name")
        if album:
            album_plays[(akey, name_match.album_core(album))] += 1

    return artist_plays, album_plays


def _cmd_canon_snapshot(args) -> int:
    import json as _json
    import sys

    path = getattr(args, "list_path", None) or DEFAULT_LIST
    if not os.path.exists(path):
        print(f"no canon list at {path}", file=sys.stderr)
        return 1
    artist_plays, album_plays = counts_from_history()
    snap = snapshot(
        artist_plays,
        album_plays,
        path,
        near_miss_n=args.near_miss,
        unheard_n=args.unheard,
        known_artists=known_artist_keys(),
    )
    print(_json.dumps(snap, ensure_ascii=False, indent=2))
    c = snap["counts"]
    print(
        f"  {snap['source']}: {snap['total']} albums · lived-in {c['lived_in']} · "
        f"brushed {c['brushed']} · near-miss {c['near_miss']} · unheard {c['unheard']}",
        file=sys.stderr,
    )
    return 0
