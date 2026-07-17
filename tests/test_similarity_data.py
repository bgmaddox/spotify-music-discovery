"""Tests for build_similarity_data.py — the Phase 5 similarity edge fetcher.

No network, no real data files. The Last.fm fetch is injected as a stub and the
timeline roster is a synthetic fixture written to tmp_path. Covers:
  - name normalization (case, whitespace, diacritics; leading "The" preserved)
  - roster loading (household excluded, order preserved)
  - undirected edge dedup (max weight kept, mutual flag from both directions)
  - self-edges and sub-threshold edges dropped
  - outside-neighbor capture (cap, min match)
  - per-artist error capture without aborting the batch
  - _load_network graceful absent/present behavior in build_timeline_data
"""

import json

import build_similarity_data as bsd
import build_timeline_data as btd


# ------------------------------------------------------------- fixtures/helpers


def _write_timeline(tmp_path, artists):
    p = tmp_path / "taste_timeline.json"
    p.write_text(json.dumps({"artists": artists}))
    return str(p)


def _roster_timeline(tmp_path):
    return _write_timeline(
        tmp_path,
        [
            {"name": "The Avett Brothers", "household": False},
            {"name": "Jason Isbell", "household": False},
            {"name": "CoComelon", "household": True},
            {"name": "Sturgill Simpson", "household": False},
        ],
    )


def _build(tmp_path, fetch_fn, timeline_path=None):
    out_path = str(tmp_path / "similarity_edges.json")
    result = bsd.build_similarity(
        fetch_fn,
        timeline_path=timeline_path or _roster_timeline(tmp_path),
        out_path=out_path,
    )
    return result, out_path


# ------------------------------------------------------------------ _norm


def test_norm_case_and_whitespace():
    assert bsd._norm("  Jason   ISBELL ") == "jason isbell"


def test_norm_strips_diacritics():
    assert bsd._norm("Beyoncé") == "beyonce"


def test_norm_keeps_leading_the():
    # "The Head and the Heart" must not merge with a hypothetical "Head and the Heart"
    assert bsd._norm("The Avett Brothers") == "the avett brothers"


# ------------------------------------------------------------------ roster


def test_roster_excludes_household_preserves_order(tmp_path):
    roster = bsd._load_roster(_roster_timeline(tmp_path))
    assert roster == ["The Avett Brothers", "Jason Isbell", "Sturgill Simpson"]


# ------------------------------------------------------------------ edges


def test_in_set_edge_built_with_mutual_flag(tmp_path):
    def fetch(name, limit=100):
        if name == "The Avett Brothers":
            return [{"name": "Jason Isbell", "match": 0.8}]
        if name == "Jason Isbell":
            return [{"name": "the avett brothers", "match": 0.6}]  # case-insensitive
        return []

    result, _ = _build(tmp_path, fetch)
    # one undirected edge, max weight kept, mutual (both directions returned it)
    assert result["edges"] == [[0, 1, 0.8, 1]]


def test_one_directional_edge_not_mutual(tmp_path):
    def fetch(name, limit=100):
        if name == "The Avett Brothers":
            return [{"name": "Sturgill Simpson", "match": 0.5}]
        return []

    result, _ = _build(tmp_path, fetch)
    assert result["edges"] == [[0, 2, 0.5, 0]]


def test_sub_threshold_and_self_edges_dropped(tmp_path):
    def fetch(name, limit=100):
        if name == "Jason Isbell":
            return [
                {"name": "Jason Isbell", "match": 0.9},        # self → dropped
                {"name": "Sturgill Simpson", "match": 0.01},   # < EDGE_MIN_WEIGHT
            ]
        return []

    result, _ = _build(tmp_path, fetch)
    assert result["edges"] == []


# ------------------------------------------------------------------ outside


def test_outside_neighbors_capped_and_thresholded(tmp_path):
    def fetch(name, limit=100):
        if name != "Jason Isbell":
            return []
        rows = [{"name": f"Unknown {i}", "match": 0.9 - i * 0.1} for i in range(8)]
        return rows  # 0.9 … 0.2 — the 0.2 one is below OUTSIDE_MIN_MATCH

    result, _ = _build(tmp_path, fetch)
    out = result["outside"]["Jason Isbell"]
    assert len(out) == bsd.OUTSIDE_CAP
    assert all(r["match"] >= bsd.OUTSIDE_MIN_MATCH for r in out)
    assert out[0] == {"name": "Unknown 0", "match": 0.9}


def test_in_set_neighbor_not_listed_as_outside(tmp_path):
    def fetch(name, limit=100):
        if name == "Jason Isbell":
            return [{"name": "Sturgill Simpson", "match": 0.7}]
        return []

    result, _ = _build(tmp_path, fetch)
    assert "Jason Isbell" not in result["outside"]


# ------------------------------------------------------------------ errors/meta


def test_error_recorded_batch_continues(tmp_path):
    def fetch(name, limit=100):
        if name == "Jason Isbell":
            raise RuntimeError("Last.fm error 8: boom")
        return [{"name": "nobody known", "match": 0.5}]

    result, out_path = _build(tmp_path, fetch)
    assert result["meta"]["errors"] == {"Jason Isbell": "Last.fm error 8: boom"}
    assert result["meta"]["fetched"] == 2
    # file written despite the per-artist failure
    assert json.load(open(out_path))["nodes"] == result["nodes"]


def test_no_neighbors_recorded(tmp_path):
    def fetch(name, limit=100):
        return []

    result, _ = _build(tmp_path, fetch)
    assert set(result["meta"]["no_neighbors"]) == {
        "The Avett Brothers", "Jason Isbell", "Sturgill Simpson"
    }


# ------------------------------------------------------- _load_network (merge)


def test_load_network_absent_returns_stub(tmp_path):
    net = btd._load_network(str(tmp_path / "nope.json"))
    assert net["nodes"] == [] and net["edges"] == [] and "note" in net


def test_load_network_present_passes_through(tmp_path):
    p = tmp_path / "similarity_edges.json"
    p.write_text(json.dumps({
        "generated_at": "2026-07-17T00:00:00Z",
        "nodes": ["A", "B"],
        "edges": [[0, 1, 0.5, 1]],
        "outside": {"A": [{"name": "C", "match": 0.4}]},
        "meta": {},
    }))
    net = btd._load_network(str(p))
    assert net["nodes"] == ["A", "B"]
    assert net["edges"] == [[0, 1, 0.5, 1]]
    assert net["outside"]["A"][0]["name"] == "C"
