"""everynoise genre-page parsing: the fragile `_NEARBY` regex + seed dedup/ranking.

everynoise is a frozen site so its HTML won't drift, but a refactor of the regex
could — this locks the parser against a representative fixture. No network: `_find`
and `_fetch_page` are monkeypatched.
"""

import genre_map

# Three nearby items; the first is the SEED itself (everynoise lists it first), so it
# must be skipped. Mixed quoting (&quot; inside onclick, literal " on the title attr)
# mirrors the real markup the regex targets.
FIXTURE = """
<div id=nearbyitem1 onclick="playx(&quot;spotify:track:seed&quot;, &quot;indie folk&quot;)" title="e.g. Bon Iver &quot;>indie folk</div>
<div id=nearbyitem2 onclick="playx(&quot;spotify:track:a&quot;, &quot;chamber pop&quot;)" title="e.g. Sufjan Stevens &quot;>chamber pop</div>
<div id=nearbyitem3 onclick="playx(&quot;spotify:track:b&quot;, &quot;stomp and holler&quot;)" title="e.g. The Lumineers &quot;>stomp and holler</div>
"""


def test_find_exact_before_partial(monkeypatch):
    monkeypatch.setattr(
        genre_map,
        "_CACHE",
        [{"name": "folk"}, {"name": "indie folk"}, {"name": "folk punk"}],
    )
    hits = genre_map._find("folk")
    assert hits[0]["name"] == "folk"  # exact match ranks first
    assert {h["name"] for h in hits} == {"folk", "indie folk", "folk punk"}


def test_nearby_skips_seed_and_ranks(monkeypatch):
    monkeypatch.setattr(
        genre_map, "_find",
        lambda q: [{"name": "indie folk", "href": "indiefolk.html"}],
    )
    monkeypatch.setattr(genre_map, "_fetch_page", lambda href: FIXTURE)

    out = genre_map.nearby("indie folk", limit=10)
    names = [o["name"] for o in out]
    assert "indie folk" not in names                     # seed excluded
    assert names == ["chamber pop", "stomp and holler"]  # everynoise order preserved
    assert [o["rank"] for o in out] == [1, 2]
    assert out[0]["example"] == "Sufjan Stevens"


def test_nearby_respects_limit(monkeypatch):
    monkeypatch.setattr(
        genre_map, "_find",
        lambda q: [{"name": "indie folk", "href": "indiefolk.html"}],
    )
    monkeypatch.setattr(genre_map, "_fetch_page", lambda href: FIXTURE)
    assert len(genre_map.nearby("indie folk", limit=1)) == 1


def test_nearby_missing_genre_raises(monkeypatch):
    monkeypatch.setattr(genre_map, "_find", lambda q: [])
    try:
        genre_map.nearby("no such genre")
    except KeyError:
        return
    raise AssertionError("expected KeyError for an unknown genre")
