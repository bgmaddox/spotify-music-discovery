"""Auto-proposing artists for unresolved Apple plays: tiering, evidence, apply.

No network, no auth — Spotify `search` is replaced by a fake returning canned
track items. The rules under test are the ones that decide whether a play gets
attributed to the wrong artist, so both the ACCEPT and the REJECT cases are
locked here.
"""

import json

import apple_resolve as ar


# ------------------------------------------------------------------ fixtures


def _item(track, album, artist, tid=None):
    return {
        "id": tid or f"{artist}:{track}",
        "name": track,
        "uri": f"spotify:track:{abs(hash((track, artist))) % 10**8}",
        "album": {"name": album},
        "artists": [{"name": artist}],
    }


class FakeSp:
    """Returns the same canned item list for every query, recording queries."""

    def __init__(self, items):
        self._items = items
        self.queries: list[str] = []

    def search(self, q, type="track", limit=20):
        self.queries.append(q)
        return {"tracks": {"items": self._items}}


# ------------------------------------------------------------------ non-music


def test_non_music_is_flagged_not_matched():
    assert ar.is_non_music("Morning Edition", "NPR News and Culture")
    assert ar.is_non_music("Episode 12", "The Daily Podcast")


def test_common_words_are_not_mistaken_for_non_music():
    """A song really can be called 'Talk' or 'News' — don't drop real plays."""
    assert not ar.is_non_music("Talk", "Ghost Stories")
    assert not ar.is_non_music("News", "Some Album")
    assert not ar.is_non_music("Radio", "Ka-Ching!")
    assert not ar.is_non_music("Now We Are Talking", "Mainstage Music - Best of 2015")


# ------------------------------------------------------------------ hint quality


def test_hint_that_is_just_the_title_is_uninformative():
    """Remix/EP singles named after their own track carry no extra signal."""
    assert ar.hint_is_uninformative("Collide", "Collide (Remixes) - EP")
    assert ar.hint_is_uninformative("Starry Eyed", "Starry Eyed (Remixes) - EP")
    assert ar.hint_is_uninformative("Pogo", "Pogo - Single")
    assert ar.hint_is_uninformative(
        "Fast Car (feat. Dakota)", "Fast Car (feat. Dakota) [Radio Edit] - Single"
    )
    assert ar.hint_is_uninformative("Anything", None)


def test_real_album_hint_is_informative():
    assert not ar.hint_is_uninformative("Touch It / Technologic", "Alive 2007")
    assert not ar.hint_is_uninformative("21 Questions", "Get Rich or Die Tryin'")


# ------------------------------------------------------------------ tiering


def test_high_tier_when_title_and_album_agree():
    items = [_item("Touch It / Technologic", "Alive 2007", "Daft Punk")]
    v = ar._evaluate("Touch It / Technologic", "Alive 2007", items)
    assert v["tier"] == ar.TIER_HIGH
    assert v["artist"] == "Daft Punk"
    assert v["evidence"]["album_ratio"] == 1.0


def test_high_tier_survives_edition_and_live_suffixes():
    items = [_item("Going Home - Live", "Kenny G Live", "Kenny G")]
    v = ar._evaluate("Going Home", "Kenny G Live", items)
    assert v["tier"] == ar.TIER_HIGH
    assert v["artist"] == "Kenny G"


def test_review_when_album_hint_does_not_match():
    """Right title, wrong record → proposed for review, never auto-applied."""
    items = [_item("Champagne Supernova", "Live from Friends Lounge", "Swerve Jr")]
    v = ar._evaluate("Champagne Supernova", "Time Flies... 1994-2009", items)
    assert v["tier"] == ar.TIER_REVIEW
    assert v["tier"] not in ar.APPLIED_TIERS


def test_review_when_two_artists_both_qualify():
    """Karaoke/cover pollution must demote, not pick the first hit."""
    items = [
        _item("21 Questions", "Get Rich Or Die Tryin'", "50 Cent"),
        _item("21 Questions", "Get Rich or Die Tryin'", "GhetSoul Tapes"),
    ]
    v = ar._evaluate("21 Questions", "Get Rich or Die Tryin'", items)
    assert v["tier"] == ar.TIER_REVIEW
    assert set(v["alternatives"]) == {"50 Cent", "GhetSoul Tapes"}


def test_tribute_album_prefix_is_rejected_as_too_weak():
    """THE case that must be rejected.

    `Lioness: Hidden Treasures` (Amy Winehouse) vs the piano-tribute record
    `Lioness: Hidden Treasures, But Piano` shares a whole-word prefix and an
    identical track title, but is a different artist entirely. It must land in
    `review`, not `high` — an auto-applied override here would permanently
    misattribute the play in the listening history.
    """
    items = [_item("Tears Dry", "Lioness: Hidden Treasures, But Piano", "Ava Leclair")]
    v = ar._evaluate("Tears Dry", "Lioness: Hidden Treasures", items)
    assert v["tier"] == ar.TIER_REVIEW
    assert v["tier"] not in ar.APPLIED_TIERS


def test_bracketed_annotation_still_reaches_high():
    """The looser rule that IS allowed: a parenthesized release annotation."""
    items = [
        _item(
            "There Once Was A Pirate",
            "Spring Awakening (Original Broadway Cast Recording)",
            "Duncan Sheik",
        )
    ]
    v = ar._evaluate("There Once Was a Pirate", "Spring Awakening", items)
    assert v["tier"] == ar.TIER_HIGH
    assert v["artist"] == "Duncan Sheik"


def test_no_match_when_nothing_resembles_the_title():
    items = [_item("Totally Different Song", "Some Album", "Someone")]
    v = ar._evaluate("Bartender Song", "Graffiti the World", items)
    assert v["tier"] == ar.TIER_NO_MATCH
    assert v["artist"] is None


# ------------------------------------------------------------------ pipeline


def test_propose_for_song_short_circuits_ambiguous_hint(tmp_path, monkeypatch):
    """An uninformative hint must not even hit the API."""
    monkeypatch.setattr(ar, "_cache_read", lambda *a, **k: None)
    monkeypatch.setattr(ar, "_cache_write", lambda *a, **k: None)
    sp = FakeSp([_item("Collide", "Collide", "Some Popular Act")])

    p = ar.propose_for_song(
        sp, {"title": "Collide", "album": "Collide (Remixes) - EP", "plays": 6}
    )

    assert p["tier"] == ar.TIER_AMBIGUOUS
    assert p["artist"] is None
    assert sp.queries == []


def test_propose_for_song_carries_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "SLEEP_BETWEEN", 0)
    sp = FakeSp([_item("Ignition", "Chocolate Factory", "R. Kelly")])

    p = ar.propose_for_song(
        sp,
        {"title": "Ignition", "album": "Chocolate Factory", "plays": 1,
         "minutes": 3.1, "year_min": "2016", "year_max": "2016"},
        use_cache=False,
    )

    assert p["tier"] == ar.TIER_HIGH
    assert p["artist"] == "R. Kelly"
    assert p["evidence"]["album"] == "Chocolate Factory"
    assert p["plays"] == 1 and p["years"] == "2016"


def test_propose_all_orders_by_plays(monkeypatch):
    monkeypatch.setattr(ar, "SLEEP_BETWEEN", 0)
    sp = FakeSp([])
    entries = [
        {"title": "A", "album": None, "plays": 1},
        {"title": "B", "album": None, "plays": 9},
    ]
    out = ar.propose_all(sp, entries)
    assert [p["title"] for p in out] == ["B", "A"]

    out = ar.propose_all(sp, entries, min_plays=5)
    assert [p["title"] for p in out] == ["B"]


# ------------------------------------------------------------------ apply


def _overrides_file(tmp_path, data):
    p = tmp_path / "apple_artist_overrides.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_apply_writes_only_high_tier(tmp_path):
    path = _overrides_file(tmp_path, {})
    proposals = [
        {"title": "Ignition", "artist": "R. Kelly", "tier": ar.TIER_HIGH},
        {"title": "Tears Dry", "artist": "Ava Leclair", "tier": ar.TIER_REVIEW},
        {"title": "Collide", "artist": None, "tier": ar.TIER_AMBIGUOUS},
    ]
    added, skipped = ar.apply_proposals(proposals, path)

    written = json.load(open(path))
    assert added == 1 and skipped == 0
    assert written == {"Ignition": "R. Kelly"}


def test_apply_never_overwrites_an_existing_manual_override(tmp_path):
    """A hand-written override always wins over an auto-proposal."""
    path = _overrides_file(tmp_path, {"Ignition": "The Right Answer"})
    proposals = [{"title": "ignition", "artist": "Wrong Guess", "tier": ar.TIER_HIGH}]

    added, skipped = ar.apply_proposals(proposals, path)

    assert (added, skipped) == (0, 1)
    assert json.load(open(path)) == {"Ignition": "The Right Answer"}


def test_write_proposals_reports_tier_stats(tmp_path):
    proposals = [
        {"title": "A", "artist": "X", "tier": ar.TIER_HIGH, "plays": 3},
        {"title": "B", "artist": None, "tier": ar.TIER_AMBIGUOUS, "plays": 2},
        {"title": "C", "artist": "Y", "tier": ar.TIER_HIGH, "plays": 1},
    ]
    path = ar.write_proposals(proposals, str(tmp_path / "props.json"))
    out = json.load(open(path))

    assert out["stats"]["songs"] == 3
    assert out["stats"]["plays"] == 6
    assert out["stats"]["by_tier"][ar.TIER_HIGH] == 2
    assert out["stats"]["plays_by_tier"][ar.TIER_HIGH] == 4
    assert out["applied_tiers"] == [ar.TIER_HIGH]
