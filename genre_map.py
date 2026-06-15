"""Query layer over the everynoise genre map — the "what sits next to X?" tool.

Background: everynoise.com (Glenn McDonald) is a frozen 2023 snapshot whose live
feeds died with his Spotify layoff — the same deprecation that killed this app's
algorithmic endpoints. But its genre adjacency is timeless enough to be useful as a
*sonic* complement to Last.fm's listening-based artist similarity.

Two layers, so a reasoning session never reads the whole 6,300-genre dump:
  * `find`      — offline substring lookup over knowledge/genres_coords.json, just to
                  resolve the exact genre name (and its per-genre page link).
  * `neighbors` — everynoise's OWN ranked "nearby genres" list for that genre, lazily
                  fetched from its per-genre page and cached forever in
                  .cache_everynoise/ (the site is frozen, so the cache never staleness).

Why the per-genre list and not raw map distance: the flat map crams texturally-similar
but culturally-unrelated genres together (steel guitar next to marathi balgeet). The
per-genre "nearby" list uses everynoise's proper metric and gives scene-lineage
adjacency (outlaw country → texas country → alt-country → roots rock). The list is
PRE-RANKED: trust the head, treat the tail as left-field — it degrades into
texture-matches. As always in Mode A: these are *directions*; confirm real artists with
lastfm.py and real tracks with search_verify.

CLI:
    python genre_map.py neighbors "indie folk" [--limit 15]
    python genre_map.py find "americana"           # find the exact genre name
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "knowledge", "genres_coords.json")
CACHE_DIR = os.path.join(HERE, ".cache_everynoise")
BASE_URL = "https://everynoise.com/"

# In a per-genre page the ranked nearby genres are the <div id=nearbyitemN ...> nodes;
# the 2nd playx() arg is the genre name, the title gives an example artist.
_NEARBY = re.compile(
    r"id=nearbyitem\d+.*?"
    r"playx\(&quot;[^&]*&quot;,\s*&quot;(?P<name>.*?)&quot;.*?"
    r'(?:title="e\.g\.\s*(?P<example>.*?)\s*&quot;)?>',
    re.IGNORECASE | re.DOTALL,
)

_CACHE: list[dict] | None = None


def _load() -> list[dict]:
    global _CACHE
    if _CACHE is None:
        with open(DATA, encoding="utf-8") as fh:
            _CACHE = json.load(fh)
    return _CACHE


def _find(query: str) -> list[dict]:
    """Genres whose name contains `query` (case-insensitive), exact match first."""
    q = query.strip().lower()
    exact = [g for g in _load() if g["name"].lower() == q]
    partial = [g for g in _load() if q in g["name"].lower() and g["name"].lower() != q]
    return exact + partial


def _fetch_page(href: str) -> str:
    """Return the per-genre page HTML, from .cache_everynoise/ if present (no TTL)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, href)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    req = urllib.request.Request(
        BASE_URL + href, headers={"User-Agent": "spotify-discovery/1.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (trusted host)
        text = resp.read().decode("utf-8", "replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text


def nearby(genre: str, limit: int = 15) -> list[dict]:
    """everynoise's ranked nearby genres for `genre` (the seed itself excluded).

    Resolves `genre` by exact name (else first substring match), fetches its
    per-genre page (cached), and returns up to `limit` neighbors in everynoise's
    own relatedness order — each as {name, example, rank}.
    """
    matches = _find(genre)
    if not matches:
        raise KeyError(genre)
    seed = matches[0]
    if not seed.get("href"):
        raise KeyError(f"{seed['name']} (no per-genre page link)")
    out: list[dict] = []
    seen = {seed["name"].lower()}
    for m in _NEARBY.finditer(_fetch_page(seed["href"])):
        name = html.unescape(m.group("name"))
        if name.lower() in seen:  # the seed appears first; later dups are noise
            continue
        seen.add(name.lower())
        ex = m.group("example")
        out.append(
            {
                "seed": seed["name"],
                "rank": len(out) + 1,
                "name": name,
                "example": html.unescape(ex) if ex else None,
            }
        )
        if len(out) >= limit:
            break
    return out


def _cmd_neighbors(args) -> int:
    try:
        hits = nearby(args.genre, args.limit)
    except KeyError as e:
        print(f"MISS — no genre matching {args.genre!r}", file=sys.stderr)
        print("  try: python genre_map.py find <partial name>", file=sys.stderr)
        return 1
    if not hits:
        print(f"no nearby genres found for {args.genre!r}", file=sys.stderr)
        return 1
    print(
        f"nearby {len(hits)} to {hits[0]['seed']!r} "
        f"(everynoise order — head is closest):",
        file=sys.stderr,
    )
    for g in hits:
        ex = f"  e.g. {g['example']}" if g.get("example") else ""
        print(f"{g['rank']:>3}. {g['name']}{ex}")
    return 0


def _cmd_find(args) -> int:
    hits = _find(args.query)
    if not hits:
        print(f"MISS — no genre matching {args.query!r}", file=sys.stderr)
        return 1
    for g in hits[: args.limit]:
        ex = f"  e.g. {g['example']}" if g.get("example") else ""
        print(f"{g['name']}{ex}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="genre_map.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("neighbors", help="everynoise's ranked nearby genres.")
    n.add_argument("genre")
    n.add_argument("--limit", type=int, default=15)
    n.set_defaults(func=_cmd_neighbors)

    f = sub.add_parser("find", help="Substring search for an exact genre name.")
    f.add_argument("query")
    f.add_argument("--limit", type=int, default=20)
    f.set_defaults(func=_cmd_find)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
