"""Tests for Phase 3 timeline merge: albums / track_stories / lists keys.

No network, no auth, no real data files. All inputs are synthetic fixtures.
Covers:
  - _build_albums_key: join, completion math, stub path when meta absent
  - _build_track_stories_key: lifeline pass-through, enrichment join, stub path
  - _build_lists_key: receipt pass-through, milestone ranking, anthem join,
    deep-cut badge threshold + contrarian score, stub path when meta absent
"""

import build_timeline_data as btd


# ============================================================== shared fixtures


def _sample_meta() -> dict:
    """Minimal enrichment fixture: 2 tracks, 2 albums, 2 artists."""
    return {
        "tracks": {
            "spotify:track:AAA": {
                "duration_ms": 200_000,
                "popularity": 40,
                "album_id": "album_X",
                "album_name": "Album X",
                "artist_ids": ["artist_1"],
                "artist_names": ["Band Alpha"],
            },
            "spotify:track:BBB": {
                "duration_ms": 300_000,
                "popularity": 70,
                "album_id": "album_Y",
                "album_name": "Album Y",
                "artist_ids": ["artist_2"],
                "artist_names": ["Band Beta"],
            },
            "spotify:track:CCC": {
                "duration_ms": 180_000,
                "popularity": 20,
                "album_id": "album_X",  # second track on same album as AAA
                "album_name": "Album X",
                "artist_ids": ["artist_1"],
                "artist_names": ["Band Alpha"],
            },
        },
        "albums": {
            "album_X": {
                "name": "Album X",
                "artist": "Band Alpha",
                "total_tracks": 10,
                "release_year": 2015,
                "thumb_b64": "base64stub==",
                "image_url": "https://example.com/x.jpg",
            },
            "album_Y": {
                "name": "Album Y",
                "artist": "Band Beta",
                "total_tracks": 4,
                "release_year": 2020,
                "thumb_b64": "base64stub_y==",
                "image_url": "https://example.com/y.jpg",
            },
        },
        "artists": {
            "artist_1": {
                "name": "Band Alpha",
                "max_popularity": 75,
                "top_track_name": "Their Big Hit",
            },
            "artist_2": {
                "name": "Band Beta",
                "max_popularity": 72,
                "top_track_name": "Catchy Song",
            },
        },
    }


def _sample_summary() -> dict:
    """Minimal history_summary fixture with albums, track_stories, track_seasons,
    per_year_tracks, and yearbook_anthems sections."""
    return {
        "albums": {
            "top_albums": [
                {
                    "name": "Album X",
                    "artist": "Band Alpha",
                    "plays": 100,
                    "by_year": {"2020": 60, "2021": 40},
                    "session_count": 5,
                    "top_track": {
                        "name": "Song A",
                        "plays": 60,
                        "uri": "spotify:track:AAA",
                    },
                    "sample_uri": "spotify:track:AAA",
                },
                {
                    "name": "Album Y",
                    "artist": "Band Beta",
                    "plays": 50,
                    "by_year": {"2021": 50},
                    "session_count": 2,
                    "top_track": {
                        "name": "Song B",
                        "plays": 50,
                        "uri": "spotify:track:BBB",
                    },
                    "sample_uri": "spotify:track:BBB",
                },
            ],
            "album_sessions": {
                "total_sessions": 7,
                "by_year": {"2020": 3, "2021": 4},
                "session_albums": [{"album": "Album X", "artist": "Band Alpha"}],
            },
            "one_track_wonders": [
                {
                    "album": "Album Z",
                    "artist": "Band Gamma",
                    "hit_track": {
                        "name": "Wonder Song",
                        "plays": 55,
                        "uri": "spotify:track:AAA",
                    },
                    "rest_plays": 1,
                }
            ],
        },
        "track_stories": {
            "tracks": [
                {
                    "artist": "Band Alpha",
                    "title": "Song A",
                    "uri": "spotify:track:AAA",
                    "plays": 60,
                    "ms_played": 7_200_000,  # 2 hours
                    "lifeline": [["2020-06", 30], ["2021-01", 30]],
                    "first_play": "2020-06-01",
                    "last_play": "2021-01-15",
                    "devotion_years": 2,
                    "year_span": ["2020", "2021"],
                },
                {
                    "artist": "Band Beta",
                    "title": "Song B",
                    "uri": "spotify:track:BBB",
                    "plays": 40,
                    "ms_played": 9_000_000,  # 2.5 hours — more ms but fewer plays
                    "lifeline": [["2021-03", 40]],
                    "first_play": "2021-03-01",
                    "last_play": "2021-03-31",
                    "devotion_years": 1,
                    "year_span": ["2021", "2021"],
                },
                {
                    "artist": "Band Alpha",
                    "title": "Song C",
                    "uri": "spotify:track:CCC",
                    "plays": 20,
                    "ms_played": 2_000_000,
                    "lifeline": [["2022-05", 20]],
                    "first_play": "2022-05-01",
                    "last_play": "2022-05-31",
                    "devotion_years": 1,
                    "year_span": ["2022", "2022"],
                },
            ]
        },
        "track_seasons": {
            "tracks": [
                {
                    "artist": "Band Alpha",
                    "title": "Song A",
                    "uri": "spotify:track:AAA",
                    "plays": 60,
                    "season_label": "june",
                    "concentration": 0.9,
                }
            ]
        },
        "per_year_tracks": {
            "by_year": {
                "2020": {
                    "top_tracks": [
                        {
                            "artist": "Band Alpha",
                            "title": "Song A",
                            "uri": "spotify:track:AAA",
                            "plays": 30,
                        }
                    ],
                    "total_hours": 1.5,
                    "total_skips": 3,
                },
                "2021": {
                    "top_tracks": [
                        {
                            "artist": "Band Beta",
                            "title": "Song B",
                            "uri": "spotify:track:BBB",
                            "plays": 40,
                        }
                    ],
                    "total_hours": 2.5,
                    "total_skips": 1,
                },
            }
        },
        "yearbook_anthems": {
            "anthems": [
                {
                    "year": "2020",
                    "artist": "Band Alpha",
                    "title": "Song A",
                    "uri": "spotify:track:AAA",
                    "plays": 30,
                    "concentration": 0.5,
                },
                {
                    "year": "2021",
                    "artist": "Band Beta",
                    "title": "Song B",
                    "uri": "spotify:track:BBB",
                    "plays": 40,
                    "concentration": 0.8,
                },
            ]
        },
    }


# ============================================================== _build_albums_key


def test_albums_key_shape_with_meta():
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_albums_key(summary, meta)

    assert result["enriched"] is True
    assert len(result["top_albums"]) == 2
    assert result["session_score"]["total"] == 7
    assert result["session_score"]["by_year"] == {"2020": 3, "2021": 4}
    assert len(result["session_albums"]) == 1
    assert len(result["one_track_wonders"]) == 1


def test_albums_enrichment_fields_joined():
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_albums_key(summary, meta)

    album_x = result["top_albums"][0]
    assert album_x["name"] == "Album X"
    assert album_x["release_year"] == 2015
    assert album_x["total_tracks"] == 10
    assert album_x["thumb_b64"] == "base64stub=="
    assert album_x["image_url"] == "https://example.com/x.jpg"


def test_albums_completion_math():
    """Completion = distinct played URIs from track_stories ÷ total_tracks."""
    summary = _sample_summary()
    meta = _sample_meta()
    # track_stories has AAA and CCC both on album_X (total_tracks=10) → 2/10 = 0.2
    result = btd._build_albums_key(summary, meta)
    album_x = result["top_albums"][0]
    assert album_x["completion"] == 0.2  # 2 distinct URIs / 10 tracks

    # album_Y has only BBB played → 1/4 = 0.25
    album_y = result["top_albums"][1]
    assert album_y["completion"] == 0.25


def test_albums_stub_when_meta_absent():
    """Without enrichment, enriched=False and optional fields are null."""
    summary = _sample_summary()
    result = btd._build_albums_key(summary, None)

    assert result["enriched"] is False
    for alb in result["top_albums"]:
        assert alb["release_year"] is None
        assert alb["total_tracks"] is None
        assert alb["completion"] is None
        assert alb["thumb_b64"] is None
        assert alb["image_url"] is None
    # Core fields still present
    assert result["top_albums"][0]["name"] == "Album X"
    assert result["top_albums"][0]["plays"] == 100


def test_albums_wonders_art_joined():
    """one_track_wonders get image_url from hit_track URI → album enrichment."""
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_albums_key(summary, meta)
    wonder = result["one_track_wonders"][0]
    # hit_track uri=AAA → album_X → image_url joined
    assert wonder["image_url"] == "https://example.com/x.jpg"
    assert wonder["album"] == "Album Z"
    assert wonder["rest_plays"] == 1


def test_albums_wonders_stub_when_meta_absent():
    summary = _sample_summary()
    result = btd._build_albums_key(summary, None)
    wonder = result["one_track_wonders"][0]
    assert wonder["image_url"] is None
    assert wonder["thumb_b64"] is None


def test_albums_capped_at_top_n():
    """top_albums list is capped at the top_n parameter (default=35, passable)."""
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_albums_key(summary, meta, top_n=1)
    assert len(result["top_albums"]) == 1
    assert result["top_albums"][0]["name"] == "Album X"


# ============================================================== _build_track_stories_key


def test_track_stories_shape_with_meta():
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_track_stories_key(summary, meta)

    assert result["enriched"] is True
    assert len(result["tracks"]) == 3
    assert len(result["seasons"]) == 1


def test_track_stories_enrichment_joined():
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_track_stories_key(summary, meta)

    track_a = result["tracks"][0]
    assert track_a["title"] == "Song A"
    assert track_a["duration_ms"] == 200_000
    assert track_a["popularity"] == 40
    assert track_a["lifeline"] == [["2020-06", 30], ["2021-01", 30]]
    assert track_a["first_play"] == "2020-06-01"
    assert track_a["devotion_years"] == 2


def test_track_stories_stub_when_meta_absent():
    summary = _sample_summary()
    result = btd._build_track_stories_key(summary, None)

    assert result["enriched"] is False
    for t in result["tracks"]:
        assert t["duration_ms"] is None
        assert t["popularity"] is None
    # Core fields preserved
    assert result["tracks"][0]["title"] == "Song A"
    assert result["tracks"][0]["ms_played"] == 7_200_000


def test_track_stories_seasons_pass_through():
    summary = _sample_summary()
    result = btd._build_track_stories_key(summary, None)
    assert result["seasons"][0]["season_label"] == "june"
    assert result["seasons"][0]["concentration"] == 0.9


# ============================================================== _build_lists_key


def test_lists_receipt_shape():
    summary = _sample_summary()
    result = btd._build_lists_key(summary, None)
    receipt = result["receipt"]

    assert "2020" in receipt
    assert "2021" in receipt
    assert receipt["2020"]["total_hours"] == 1.5
    assert receipt["2020"]["total_skips"] == 3
    assert len(receipt["2020"]["top_tracks"]) == 1
    assert receipt["2020"]["top_tracks"][0]["title"] == "Song A"


def test_lists_milestones_ranked_by_ms_played():
    """Milestones must be sorted by ms_played desc (Song B > Song A > Song C)."""
    summary = _sample_summary()
    result = btd._build_lists_key(summary, None)
    milestones = result["milestones"]

    assert milestones[0]["title"] == "Song B"   # 9_000_000 ms
    assert milestones[1]["title"] == "Song A"   # 7_200_000 ms
    assert milestones[2]["title"] == "Song C"   # 2_000_000 ms


def test_lists_milestones_hours_computed():
    summary = _sample_summary()
    result = btd._build_lists_key(summary, None)
    m = result["milestones"][1]  # Song A — 7_200_000 ms
    assert m["hours_played"] == 2.0


def test_lists_milestones_enrichment_adds_duration_and_estimate():
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_lists_key(summary, meta)

    # Song A: duration_ms=200_000, plays=60 → estimated_plays_hours = 60*200000/3600000
    song_a = next(m for m in result["milestones"] if m["title"] == "Song A")
    assert song_a["duration_ms"] == 200_000
    expected = round(60 * 200_000 / 3_600_000, 2)
    assert song_a["estimated_plays_hours"] == expected


def test_lists_milestones_no_estimated_hours_without_meta():
    summary = _sample_summary()
    result = btd._build_lists_key(summary, None)
    for m in result["milestones"]:
        assert m["duration_ms"] is None
        assert m["estimated_plays_hours"] is None


def test_lists_anthems_pass_through_with_enrichment():
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_lists_key(summary, meta)
    anthems = result["anthems"]

    assert len(anthems) == 2
    a2020 = anthems[0]
    assert a2020["year"] == "2020"
    assert a2020["duration_ms"] == 200_000   # from meta for AAA
    assert a2020["popularity"] == 40


def test_lists_anthems_stub_fields_null_without_meta():
    summary = _sample_summary()
    result = btd._build_lists_key(summary, None)
    for a in result["anthems"]:
        assert a["duration_ms"] is None
        assert a["popularity"] is None
    assert result["anthems"][0]["year"] == "2020"


# ============================================================== deep cuts


def test_deep_cut_badge_threshold():
    """diff >= 15 AND title != artist top_track → is_deep_cut=True."""
    summary = _sample_summary()
    # Patch: artist_1 has max_popularity=75, user track AAA has popularity=40 → diff=35
    meta = _sample_meta()
    result = btd._build_lists_key(summary, meta)
    items = result["deep_cuts"]["items"]

    # Find Band Alpha entry (user_track = Song A, pop=40, artist max=75, diff=35)
    alpha = next(i for i in items if i["artist"] == "Band Alpha")
    assert alpha["diff"] == 35
    assert alpha["is_deep_cut"] is True   # 35 >= 15, "Song A" != "Their Big Hit"


def test_deep_cut_no_badge_when_diff_below_threshold():
    """diff < 15 → is_deep_cut=False even when title differs."""
    summary = _sample_summary()
    meta = _sample_meta()
    # Band Beta: user track BBB pop=70, artist max=72 → diff=2 < 15
    result = btd._build_lists_key(summary, meta)
    items = result["deep_cuts"]["items"]

    beta = next(i for i in items if i["artist"] == "Band Beta")
    assert beta["diff"] == 2
    assert beta["is_deep_cut"] is False


def test_deep_cut_no_badge_when_title_matches_artist_top():
    """Even a large diff must not badge when user's track IS the artist's top track."""
    summary = _sample_summary()
    meta = _sample_meta()
    # Override: artist_1 top_track_name = "Song A" (same as user fav)
    meta["artists"]["artist_1"]["top_track_name"] = "Song A"
    result = btd._build_lists_key(summary, meta)
    items = result["deep_cuts"]["items"]

    alpha = next(i for i in items if i["artist"] == "Band Alpha")
    assert alpha["is_deep_cut"] is False


def test_deep_cut_contrarian_score():
    """contrarian_score = fraction of artists where is_deep_cut=True."""
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_lists_key(summary, meta)
    dc = result["deep_cuts"]

    assert dc["enriched"] is True
    # 1 of 2 artists (Band Alpha) is a deep cut → 0.5
    assert dc["contrarian_score"] == 0.5


def test_deep_cuts_stub_when_meta_absent():
    summary = _sample_summary()
    result = btd._build_lists_key(summary, None)
    dc = result["deep_cuts"]
    assert dc["enriched"] is False
    assert dc["contrarian_score"] is None
    assert dc["items"] == []


def test_deep_cuts_sorted_deep_cuts_first():
    """Deep-cut items must sort with is_deep_cut=True first, then by diff desc."""
    summary = _sample_summary()
    meta = _sample_meta()
    result = btd._build_lists_key(summary, meta)
    items = result["deep_cuts"]["items"]
    # First item must be a deep cut
    assert items[0]["is_deep_cut"] is True
    # Non-deep-cuts follow
    non_deep = [i for i in items if not i["is_deep_cut"]]
    deep = [i for i in items if i["is_deep_cut"]]
    assert items[: len(deep)] == deep


# ============================================ album-art fallback (name search)


def _uriless_summary() -> dict:
    """An Apple-Music-only album: no sample_uri anywhere, so no URI→art path."""
    summary = _sample_summary()
    summary["albums"]["top_albums"].append(
        {
            "name": "Coming Home (Deluxe)",
            "artist": "Leon Bridges",
            "plays": 162,
            "by_year": {"2016": 162},
            "session_count": 1,
            "top_track": {"name": "River", "plays": 20, "uri": None},
            "sample_uri": "",
        }
    )
    return summary


def _meta_with_name_lookup() -> dict:
    meta = _sample_meta()
    meta["albums"]["album_deluxe"] = {
        "name": "Coming Home (Deluxe)",
        "artist": "Leon Bridges",
        "total_tracks": 15,
        "release_year": 2015,
        "thumb_b64": "b64_deluxe==",
        "image_url": "https://example.com/deluxe.jpg",
    }
    import enrich_meta

    meta["album_name_lookup"] = {
        enrich_meta.album_name_key("Leon Bridges", "Coming Home (Deluxe)"): {
            "matched": True,
            "album_id": "album_deluxe",
            "matched_name": "Coming Home (Deluxe)",
            "matched_artist": "Leon Bridges",
            "confidence": 1.0,
        }
    }
    return meta


def test_albums_art_falls_back_to_name_search():
    """An album with no track URI still gets its cover via the name index."""
    result = btd._build_albums_key(_uriless_summary(), _meta_with_name_lookup())
    alb = result["top_albums"][-1]
    assert alb["name"] == "Coming Home (Deluxe)"
    assert alb["thumb_b64"] == "b64_deluxe=="
    assert alb["image_url"] == "https://example.com/deluxe.jpg"
    assert alb["art_source"] == "name_search"
    # URI-resolved albums stay labelled as such — the join is auditable
    assert result["top_albums"][0]["art_source"] == "uri"


def test_albums_art_stays_blank_when_name_search_missed():
    """A recorded miss must NOT borrow some other album's art."""
    meta = _meta_with_name_lookup()
    import enrich_meta

    key = enrich_meta.album_name_key("Leon Bridges", "Coming Home (Deluxe)")
    meta["album_name_lookup"][key] = {"matched": False, "reason": "artist mismatch"}

    result = btd._build_albums_key(_uriless_summary(), meta)
    alb = result["top_albums"][-1]
    assert alb["thumb_b64"] is None
    assert alb["image_url"] is None
    assert alb["art_source"] is None


def test_albums_key_tolerates_meta_without_name_lookup():
    """Older meta files (and forkers') have no album_name_lookup key at all."""
    meta = _sample_meta()
    assert "album_name_lookup" not in meta
    result = btd._build_albums_key(_uriless_summary(), meta)
    assert result["top_albums"][-1]["art_source"] is None
    assert result["top_albums"][0]["art_source"] == "uri"
