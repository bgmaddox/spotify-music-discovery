"""Track verification: the fielded→loose query fallback in `_best_track`.

A fake Spotify client records queries and returns canned results, so this runs with
no auth and no network. Confirms the precise query is tried first and the loose one
rescues a near-miss.
"""

import tools

ITEM = {
    "uri": "spotify:track:x",
    "name": "Song",
    "artists": [{"name": "Artist"}],
    "album": {"name": "Alb"},
}
FIELDED = 'track:"Song" artist:"Artist"'
LOOSE = "Artist Song"


class FakeSp:
    """Minimal stand-in: maps an exact query string to the items it should return."""

    def __init__(self, by_query):
        self.by_query = by_query
        self.queries = []

    def search(self, q, type, limit):
        self.queries.append(q)
        return {"tracks": {"items": self.by_query.get(q, [])}}


def test_best_track_tries_fielded_then_loose():
    sp = FakeSp({LOOSE: [ITEM]})  # fielded query returns nothing
    res = tools._best_track(sp, "Artist", "Song")
    assert res is ITEM
    assert sp.queries == [FIELDED, LOOSE]  # precise query attempted first


def test_best_track_short_circuits_on_fielded_hit():
    sp = FakeSp({FIELDED: [ITEM]})
    assert tools._best_track(sp, "Artist", "Song") is ITEM
    assert sp.queries == [FIELDED]  # loose query never needed


def test_best_track_miss_returns_none():
    sp = FakeSp({})
    assert tools._best_track(sp, "Artist", "Song") is None
    assert sp.queries == [FIELDED, LOOSE]


def test_search_verify_returns_uri():
    sp = FakeSp({FIELDED: [ITEM]})
    assert tools.search_verify("Artist", "Song", sp=sp) == "spotify:track:x"


def test_verify_detail_shapes_match():
    sp = FakeSp({FIELDED: [ITEM]})
    d = tools.verify_detail("Artist", "Song", sp=sp)
    assert d == {
        "uri": "spotify:track:x",
        "name": "Song",
        "artists": "Artist",
        "album": "Alb",
    }
