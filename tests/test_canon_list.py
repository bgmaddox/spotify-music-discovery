"""Tests for canon_list — the Recipe 35 candidate pool.

Pure/offline: every test builds its own play-count maps and its own tiny list file,
so nothing here touches the network, the Spotify cache, or the user's real history.
"""

import json

import pytest

import canon_list
import name_match


@pytest.fixture
def tiny_list(tmp_path):
    doc = {
        "source": "Test List",
        "url": "http://example.invalid",
        "albums": [
            {"rank": 1, "artist": "Stevie Wonder", "album": "Innervisions", "year": 1973},
            {"rank": 2, "artist": "The Beatles", "album": "Abbey Road", "year": 1969},
            {"rank": 3, "artist": "Camarón", "album": "La leyenda del tiempo", "year": 1979},
            {"rank": 4, "artist": "Dolly Parton", "album": "Coat of Many Colors", "year": 1971},
        ],
    }
    p = tmp_path / "list.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def key(name):
    return name_match.artist_key(name)


def test_load_rejects_empty_list(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"albums": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        canon_list.load_list(str(p))


def test_shipped_list_has_intact_ranks():
    """The real list must be complete and gap-free.

    Guards the parse bug that produced it: rank 269's album title is 30 words long
    and overflowed the heading regex, dropping the row without any error.
    """
    doc = canon_list.load_list()
    ranks = [a["rank"] for a in doc["albums"]]
    assert ranks == list(range(1, len(ranks) + 1))
    assert len(ranks) == 300
    for a in doc["albums"]:
        assert a["artist"] and a["album"] and isinstance(a["year"], int)


def test_four_tiers_by_play_depth(tiny_list):
    artist = {key("Stevie Wonder"): 52, key("Dolly Parton"): 66, key("The Beatles"): 47}
    album = {
        (key("Stevie Wonder"), name_match.album_core("Innervisions")): 40,
        (key("The Beatles"), name_match.album_core("Abbey Road")): 3,
    }
    t = canon_list.tier_list(artist, album, tiny_list)

    assert [r["album"] for r in t["lived_in"]] == ["Innervisions"]
    assert [r["album"] for r in t["brushed"]] == ["Abbey Road"]
    # artist known (66 plays), album never opened -> the money tier
    assert [r["album"] for r in t["near_miss"]] == ["Coat of Many Colors"]
    # artist never played at all
    assert [r["album"] for r in t["unheard"]] == ["La leyenda del tiempo"]
    assert t["counts"] == {"lived_in": 1, "brushed": 1, "near_miss": 1, "unheard": 1}


def test_lived_in_threshold_is_exclusive_below(tiny_list):
    """LIVED_IN_PLAYS is the floor for lived_in; one play under stays 'brushed'."""
    ac = name_match.album_core("Innervisions")
    at = key("Stevie Wonder")

    below = canon_list.tier_list(
        {at: 52}, {(at, ac): canon_list.LIVED_IN_PLAYS - 1}, tiny_list
    )
    assert [r["album"] for r in below["brushed"]] == ["Innervisions"]

    at_floor = canon_list.tier_list(
        {at: 52}, {(at, ac): canon_list.LIVED_IN_PLAYS}, tiny_list
    )
    assert [r["album"] for r in at_floor["lived_in"]] == ["Innervisions"]


def test_thin_artist_is_unheard_not_near_miss(tiny_list):
    """A near-miss requires the artist to be genuinely liked, not merely brushed."""
    thin = canon_list.tier_list(
        {key("Dolly Parton"): canon_list.NEAR_MISS_MIN_ARTIST_PLAYS - 1}, {}, tiny_list
    )
    assert any(r["album"] == "Coat of Many Colors" for r in thin["unheard"])

    liked = canon_list.tier_list(
        {key("Dolly Parton"): canon_list.NEAR_MISS_MIN_ARTIST_PLAYS}, {}, tiny_list
    )
    assert any(r["album"] == "Coat of Many Colors" for r in liked["near_miss"])


def test_known_artists_rescues_thin_export_counts(tiny_list):
    """Regression: the export is not the whole truth.

    Erykah Badu had 1 export play but sat in the live taste dump, and tiered as
    "unheard" until tier_list started consulting known_listened_artists(). An
    artist the user demonstrably knows must never be reported as unheard.
    """
    plays = {key("Dolly Parton"): 1}  # below NEAR_MISS_MIN_ARTIST_PLAYS

    without = canon_list.tier_list(plays, {}, tiny_list)
    assert any(r["album"] == "Coat of Many Colors" for r in without["unheard"])

    with_known = canon_list.tier_list(
        plays, {}, tiny_list, known_artists={key("Dolly Parton")}
    )
    assert any(r["album"] == "Coat of Many Colors" for r in with_known["near_miss"])
    assert not any(r["album"] == "Coat of Many Colors" for r in with_known["unheard"])


def test_library_only_flag_when_export_shows_nothing(tiny_list):
    """Zero export plays + in library => near_miss carrying the library_only flag."""
    t = canon_list.tier_list({}, {}, tiny_list, known_artists={key("Dolly Parton")})
    rec = next(r for r in t["near_miss"] if r["album"] == "Coat of Many Colors")
    assert rec["library_only"] is True
    assert rec["artist_plays"] == 0

    # an artist with real plays is a near-miss but is NOT library_only
    t2 = canon_list.tier_list(
        {key("Dolly Parton"): 66}, {}, tiny_list, known_artists={key("Dolly Parton")}
    )
    rec2 = next(r for r in t2["near_miss"] if r["album"] == "Coat of Many Colors")
    assert "library_only" not in rec2


def test_album_matching_survives_reissue_suffixes(tiny_list):
    """Loose containment match: an edition/remaster suffix must still count.

    A false negative here would tell the user they've never heard a record they
    play constantly, which is the worse of the two errors.
    """
    at = key("Camarón")
    album = {(at, name_match.album_core("La Leyenda Del Tiempo (Remastered 2018)")): 30}
    t = canon_list.tier_list({at: 30}, album, tiny_list)
    assert [r["album"] for r in t["lived_in"]] == ["La leyenda del tiempo"]


def test_artist_key_normalization_matches_leading_the(tiny_list):
    """'The Beatles' in the list must match a history keyed without the article."""
    at = key("Beatles")
    assert at == key("The Beatles")
    t = canon_list.tier_list(
        {at: 47}, {(at, name_match.album_core("Abbey Road")): 20}, tiny_list
    )
    assert [r["album"] for r in t["lived_in"]] == ["Abbey Road"]


def test_snapshot_truncates_but_reports_true_counts(tiny_list):
    artist = {key("Stevie Wonder"): 52, key("Dolly Parton"): 66}
    snap = canon_list.snapshot(artist, {}, tiny_list, near_miss_n=1, unheard_n=1)

    assert snap["total"] == 4
    # counts describe the whole tier, not the truncated window
    assert snap["counts"]["near_miss"] == 2
    assert len(snap["near_miss"]) == 1
    assert snap["counts"]["unheard"] == 2
    assert len(snap["unheard"]) == 1
    assert snap["source"] == "Test List"


def test_snapshot_rows_carry_rank_and_receipts(tiny_list):
    snap = canon_list.snapshot({key("Dolly Parton"): 66}, {}, tiny_list)
    row = next(r for r in snap["near_miss"] if "Coat of Many Colors" in r)
    assert row.startswith("#4 ")
    assert "artist 66" in row and "album 0" in row


def test_near_miss_sorted_by_artist_affinity(tiny_list):
    artist = {key("Dolly Parton"): 66, key("Stevie Wonder"): 52, key("The Beatles"): 47}
    t = canon_list.tier_list(artist, {}, tiny_list)
    assert [r["artist_plays"] for r in t["near_miss"]] == [66, 52, 47]


def test_unheard_sorted_by_critic_rank(tiny_list):
    t = canon_list.tier_list({}, {}, tiny_list)
    assert [r["rank"] for r in t["unheard"]] == [1, 2, 3, 4]
