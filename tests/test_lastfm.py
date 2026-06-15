"""Last.fm response-shape handling: the dict-vs-list collapse and numeric coercion.

These are the bits most likely to rot silently — Last.fm collapses single-item
collections to a bare dict, and sends match/count as strings (or omits them). No
network: `_get` is monkeypatched with canned payloads.
"""

import lastfm


def test_as_list_none():
    assert lastfm._as_list(None) == []


def test_as_list_single_dict_wrapped():
    d = {"name": "X"}
    assert lastfm._as_list(d) == [d]


def test_as_list_already_list_passthrough():
    lst = [{"name": "X"}]
    assert lastfm._as_list(lst) is lst


def test_similar_artists_parses_and_coerces(monkeypatch):
    canned = {
        "similarartists": {
            "artist": [
                {"name": "A", "match": "1.0"},
                {"name": "B", "match": "0.5"},
                {"name": "C", "match": None},
                {"name": "D", "match": "not-a-number"},
            ]
        }
    }
    monkeypatch.setattr(lastfm, "_get", lambda params, use_cache=True: canned)
    rows = lastfm.similar_artists("seed")
    assert rows[0] == {"name": "A", "match": 1.0}
    assert rows[1]["match"] == 0.5
    assert rows[2]["match"] is None
    assert rows[3]["match"] is None  # un-parseable string degrades to None, no crash


def test_similar_artists_single_item_collapsed(monkeypatch):
    # Last.fm returns a bare dict (not a list) when there is exactly one result.
    canned = {"similarartists": {"artist": {"name": "Solo", "match": "0.9"}}}
    monkeypatch.setattr(lastfm, "_get", lambda params, use_cache=True: canned)
    assert lastfm.similar_artists("seed") == [{"name": "Solo", "match": 0.9}]


def test_artist_tags_coerces_count(monkeypatch):
    canned = {"toptags": {"tag": [{"name": "folk", "count": "100"}, {"name": "x"}]}}
    monkeypatch.setattr(lastfm, "_get", lambda params, use_cache=True: canned)
    rows = lastfm.artist_tags("seed")
    assert rows[0] == {"tag": "folk", "count": 100}
    assert rows[1]["count"] is None
