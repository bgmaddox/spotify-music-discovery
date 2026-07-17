"""Phase 5 (viz expansion): batch Last.fm similarity edges for the taste network.

Reads the artist roster from data/taste_timeline.json (non-household artists only —
same exclusion the behavior sections use), fetches `lastfm.similar_artists` for each
(disk-cached, rate-limited in lastfm.py), and persists a compact edge list to
data/similarity_edges.json:

    {
      "generated_at": "...",
      "nodes":   ["Artist A", ...],          # roster, timeline order
      "edges":   [[i, j, weight, mutual], ...],  # undirected, indices into nodes
      "outside": {"Artist A": [{"name", "match"}, ...], ...},  # adjacent, not in library
      "meta":    {"fetched": n, "no_neighbors": [...], "errors": {...}}
    }

Dumb sensing layer: no reasoning here. The front-end (history.html) renders the
graph; outside neighbors feed the "adjacent to your taste" detail panel.

Library use:
    from build_similarity_data import build_similarity
CLI use:
    python cli.py similarity-build
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TIMELINE_PATH = os.path.join(DATA_DIR, "taste_timeline.json")
EDGES_PATH = os.path.join(DATA_DIR, "similarity_edges.json")

SIMILAR_LIMIT = 100        # neighbors fetched per artist (bigger net → more in-set hits)
OUTSIDE_CAP = 5            # "adjacent, not in your library" kept per artist
OUTSIDE_MIN_MATCH = 0.3    # below this, Last.fm adjacency is too weak to surface
EDGE_MIN_WEIGHT = 0.05     # drop near-zero in-set edges (noise, bloats the graph)


def _norm(name: str) -> str:
    """Normalize an artist name for Spotify↔Last.fm matching.

    Casefold + collapse whitespace + strip diacritics. Deliberately does NOT
    strip a leading "The" — Last.fm's autocorrect already canonicalizes those,
    and stripping would falsely merge distinct artists.
    """
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().split())


def _load_roster(timeline_path: str = TIMELINE_PATH) -> list[str]:
    """Non-household artist names from the timeline, in timeline (plays) order."""
    with open(timeline_path) as f:
        timeline = json.load(f)
    return [a["name"] for a in timeline.get("artists", []) if not a.get("household")]


def build_similarity(
    fetch_similar_fn=None,
    *,
    timeline_path: str = TIMELINE_PATH,
    out_path: str = EDGES_PATH,
    verbose: bool = False,
) -> dict:
    """Fetch similarity neighbors for every roster artist and write the edge list.

    `fetch_similar_fn(name, limit=...)` is injectable for tests; defaults to the
    real `lastfm.similar_artists` (disk-cached, rate-limited).
    """
    if fetch_similar_fn is None:
        from lastfm import similar_artists as fetch_similar_fn  # lazy: needs .env

    nodes = _load_roster(timeline_path)
    index = {_norm(n): i for i, n in enumerate(nodes)}

    # undirected edge accumulator: (lo, hi) -> {"w": max match, "dirs": count}
    acc: dict[tuple[int, int], dict] = {}
    outside: dict[str, list[dict]] = {}
    no_neighbors: list[str] = []
    errors: dict[str, str] = {}

    for i, name in enumerate(nodes):
        if verbose:
            print(f"  [{i + 1}/{len(nodes)}] {name}…" + " " * 20,
                  file=sys.stderr, end="\r")
        try:
            neighbors = fetch_similar_fn(name, limit=SIMILAR_LIMIT)
        except Exception as e:  # LastfmError or network — record and keep going
            errors[name] = str(e)
            continue
        if not neighbors:
            no_neighbors.append(name)
            continue

        out_rows = []
        for nb in neighbors:
            nb_name = nb.get("name")
            match = nb.get("match")
            if not nb_name or match is None:
                continue
            j = index.get(_norm(nb_name))
            if j is not None and j != i:
                if match >= EDGE_MIN_WEIGHT:
                    key = (min(i, j), max(i, j))
                    slot = acc.setdefault(key, {"w": 0.0, "dirs": 0})
                    slot["w"] = max(slot["w"], match)
                    slot["dirs"] += 1
            elif j is None and match >= OUTSIDE_MIN_MATCH and len(out_rows) < OUTSIDE_CAP:
                out_rows.append({"name": nb_name, "match": round(match, 3)})
        if out_rows:
            outside[name] = out_rows

    if verbose:
        print(" " * 70, file=sys.stderr, end="\r")

    edges = [
        [i, j, round(slot["w"], 3), 1 if slot["dirs"] >= 2 else 0]
        for (i, j), slot in sorted(acc.items())
    ]

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": os.path.basename(timeline_path),
        "nodes": nodes,
        "edges": edges,
        "outside": outside,
        "meta": {
            "fetched": len(nodes) - len(errors),
            "no_neighbors": no_neighbors,
            "errors": errors,
        },
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    return out


# ------------------------------------------------------------------ CLI handler


def _cmd_similarity_build(args) -> int:
    verbose = getattr(args, "verbose", False)
    print("  fetching Last.fm similarity edges…", file=sys.stderr)
    try:
        result = build_similarity(verbose=verbose)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    size_kb = os.path.getsize(EDGES_PATH) / 1024
    print(EDGES_PATH)  # stdout: the machine result (path)
    meta = result["meta"]
    print(
        f"  {size_kb:.0f} KB · {len(result['nodes'])} nodes · "
        f"{len(result['edges'])} edges · "
        f"{len(meta['no_neighbors'])} artists with no neighbors · "
        f"{len(meta['errors'])} errors",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Fetch Last.fm similarity edges for the taste network."
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    return _cmd_similarity_build(args)


if __name__ == "__main__":
    raise SystemExit(main())
