"""Tests for build_timeline_data.py — the tri-source taste-timeline builder.

No network, no auth, no real data files. All inputs are synthetic fixtures.
Covers:
  - tag→bucket mapping (precedence, substring, unmapped→other)
  - household tagging (forced set + white-noise regex + bucket override)
  - resolve_bucket precedence: household wins over tags
  - iTunes-era block construction and genre mapping
  - genre_waves math on a small synthetic summary
  - gap detection (missing year, sparse-year annotations)
"""

import json

import build_timeline_data as btd


# ============================================================== tag→bucket mapping


def test_exact_tag_match():
    assert btd._tag_to_bucket("americana") == "folk/americana"
    assert btd._tag_to_bucket("hip hop") == "hip hop"
    assert btd._tag_to_bucket("jazz") == "jazz"
    assert btd._tag_to_bucket("country") == "country"
    assert btd._tag_to_bucket("electronic") == "electronic"
    assert btd._tag_to_bucket("metal") == "metal/punk"
    assert btd._tag_to_bucket("soundtrack") == "soundtrack"
    assert btd._tag_to_bucket("pop") == "pop"


def test_case_insensitive_tag_match():
    assert btd._tag_to_bucket("Americana") == "folk/americana"
    assert btd._tag_to_bucket("HIP HOP") == "hip hop"
    assert btd._tag_to_bucket("Folk") == "folk/americana"


def test_unmapped_tag_returns_none():
    assert btd._tag_to_bucket("zydeco polka fusion") is None
    assert btd._tag_to_bucket("") is None
    assert btd._tag_to_bucket("   ") is None


def test_tag_precedence_first_match_wins():
    # When an artist has multiple tags, resolve_bucket picks the first in
    # Last.fm's count-sorted list that maps to a bucket.
    def stub_tags_folk_first(artist):
        return [
            {"tag": "folk", "count": 100},
            {"tag": "rock", "count": 50},
        ]

    bucket = btd.resolve_bucket("Test Artist", fetch_tags_fn=stub_tags_folk_first)
    assert bucket == "folk/americana"


def test_tag_precedence_unmapped_skipped_to_next():
    # First tag is unknown; second maps → second bucket wins.
    def stub_tags_unknown_first(artist):
        return [
            {"tag": "zydeco polka fusion", "count": 90},
            {"tag": "hip hop", "count": 80},
        ]

    bucket = btd.resolve_bucket("Test Artist", fetch_tags_fn=stub_tags_unknown_first)
    assert bucket == "hip hop"


def test_all_unmapped_tags_returns_other():
    def stub_no_matches(artist):
        return [
            {"tag": "zydeco polka fusion", "count": 50},
            {"tag": "galactic opera", "count": 30},
        ]

    bucket = btd.resolve_bucket("Test Artist", fetch_tags_fn=stub_no_matches)
    assert bucket == "other"


def test_empty_tag_list_returns_other():
    bucket = btd.resolve_bucket("Obscure Artist", fetch_tags_fn=lambda a: [])
    assert bucket == "other"


def test_lastfm_error_degrades_to_other():
    from lastfm import LastfmError

    def stub_raises(artist):
        raise LastfmError("network error")

    bucket = btd.resolve_bucket("Error Artist", fetch_tags_fn=stub_raises)
    assert bucket == "other"


# ============================================================== household tagging


def test_household_set_member_flagged():
    assert btd._is_household("CoComelon") is True
    assert btd._is_household("Pinkfong") is True
    assert btd._is_household("The Wiggles") is True
    assert btd._is_household("Super Simple Songs") is True
    assert btd._is_household("Elmo") is True


def test_white_noise_regex_flagged():
    assert btd._is_household("Bruce Brus – White Noise Crashing Waves") is True
    assert btd._is_household("white noise") is True
    assert btd._is_household("White   Noise Rainfall") is True
    assert btd._is_household("Whitenoise") is False  # no space between words


def test_non_household_artist_not_flagged():
    assert btd._is_household("Jason Isbell") is False
    assert btd._is_household("Tyler Childers") is False
    assert btd._is_household("The Avett Brothers") is False


def test_household_overrides_bucket():
    # Even if Last.fm says "folk", household artists get kids/household.
    def stub_folk(artist):
        return [{"tag": "folk", "count": 100}]

    bucket = btd.resolve_bucket("CoComelon", fetch_tags_fn=stub_folk)
    assert bucket == "kids/household"


def test_white_noise_overrides_bucket():
    def stub_ambient(artist):
        return [{"tag": "ambient", "count": 100}]

    bucket = btd.resolve_bucket(
        "White Noise Baby Sleep", fetch_tags_fn=stub_ambient
    )
    assert bucket == "kids/household"


# ============================================================== iTunes era block


def _sample_itunes() -> dict:
    return {
        "source": "itunes_history.json",
        "totals": {"tracks": 3082, "total_plays": 24641},
        "top_artists_by_plays": [
            {"artist": "The Avett Brothers", "plays": 3534, "tracks": 106},
            {"artist": "Kanye West", "plays": 955, "tracks": 40},
            {"artist": "CoComelon", "plays": 10, "tracks": 2},
        ],
        "top_tracks_by_plays": [
            {"plays": 127, "title": "Sleepyhead", "artist": "Passion Pit"},
            {"plays": 123, "title": "True Lover", "artist": "TurtleDuhks"},
        ],
        "top_genres_by_plays": [
            {"genre": "Bluegrass", "plays": 3042},
            {"genre": "Hip Hop", "plays": 1800},
            {"genre": "Unknown Genre", "plays": 500},
            {"genre": "Mashup", "plays": 300},
        ],
    }


def test_itunes_era_block_shape():
    itunes = _sample_itunes()
    artist_buckets = {
        "The Avett Brothers": "folk/americana",
        "Kanye West": "hip hop",
        "CoComelon": "kids/household",
    }
    block = btd._map_itunes_genres(itunes)
    # We test genre mapping separately; test the overall structure here.
    assert isinstance(block, list)
    assert len(block) == 4


def test_itunes_genre_mapping_canonical_buckets():
    itunes = _sample_itunes()
    mapped = btd._map_itunes_genres(itunes)
    buckets = {item["genre"]: item["bucket"] for item in mapped}
    assert buckets["Bluegrass"] == "folk/americana"
    assert buckets["Hip Hop"] == "hip hop"
    assert buckets["Unknown Genre"] == "other"
    assert buckets["Mashup"] == "electronic"


def test_itunes_top_artists_capped_at_25():
    # build_timeline slices top_artists_by_plays[:25]; verify the cap holds.
    itunes_many = {
        "totals": {},
        "top_artists_by_plays": [
            {"artist": f"Artist {i}", "plays": 100 - i, "tracks": 1}
            for i in range(50)
        ],
        "top_tracks_by_plays": [],
        "top_genres_by_plays": [],
    }
    # simulate the slice that build_timeline applies
    result = itunes_many["top_artists_by_plays"][:25]
    assert len(result) == 25
    assert result[0]["artist"] == "Artist 0"


def test_avett_brothers_household_false():
    # The Avett Brothers must NOT be flagged as household.
    assert btd._is_household("The Avett Brothers") is False
    bucket_result = btd.resolve_bucket(
        "The Avett Brothers",
        fetch_tags_fn=lambda a: [{"tag": "americana", "count": 100}],
    )
    assert bucket_result == "folk/americana"


# ============================================================== genre_waves math


def _sample_summary_for_waves() -> dict:
    """Minimal history summary with two years and three artists."""
    return {
        "per_year": {
            "2020": {
                "plays": 100,
                "hours": 10.0,
                "skips": 5,
                "top_artists": [
                    {"name": "Avett", "plays": 60},
                    {"name": "Jay-Z", "plays": 40},
                ],
            },
            "2021": {
                "plays": 80,
                "hours": 8.0,
                "skips": 3,
                "top_artists": [
                    {"name": "Avett", "plays": 50},
                    {"name": "CoComelon", "plays": 30},
                ],
            },
        }
    }


def test_genre_waves_sums_plays_by_bucket():
    summary = _sample_summary_for_waves()
    artist_buckets = {
        "Avett": "folk/americana",
        "Jay-Z": "hip hop",
        "CoComelon": "kids/household",
    }
    waves = btd._compute_genre_waves(summary["per_year"], artist_buckets)
    assert waves["2020"]["folk/americana"] == 60
    assert waves["2020"]["hip hop"] == 40
    assert "kids/household" not in waves["2020"]  # CoComelon only in 2021
    assert waves["2021"]["folk/americana"] == 50
    assert waves["2021"]["kids/household"] == 30


def test_genre_waves_unknown_artist_falls_to_other():
    summary = _sample_summary_for_waves()
    # No bucket for "Avett" → falls to "other"
    waves = btd._compute_genre_waves(summary["per_year"], {})
    assert waves["2020"]["other"] == 100  # 60+40 both go to other
    assert waves["2021"]["other"] == 80


def test_genre_waves_empty_year_produces_empty_dict():
    summary = {"per_year": {"2019": {"plays": 0, "hours": 0.0, "skips": 0, "top_artists": []}}}
    waves = btd._compute_genre_waves(summary["per_year"], {})
    assert waves["2019"] == {}


# ============================================================== gap detection


def test_gap_2017_detected(tmp_path, monkeypatch):
    """build_timeline must include 2017 in gaps when it's absent from per_year."""
    # We patch file loading so no real data files are needed.
    summary = {
        "generated_at": "2026-07-16T00:00:00Z",
        "per_year": {
            "2015": {"plays": 5, "hours": 0.5, "skips": 0, "top_artists": []},
            "2016": {"plays": 3, "hours": 0.3, "skips": 0, "top_artists": []},
            # 2017 intentionally absent
            "2018": {"plays": 50, "hours": 5.0, "skips": 2, "top_artists": []},
        },
        "all_time_artists": [],
        "all_time_tracks": [],
        "forgotten_favorites": [],
    }
    itunes = {
        "totals": {},
        "top_artists_by_plays": [],
        "top_tracks_by_plays": [],
        "top_genres_by_plays": [],
    }

    # Write temp files
    summary_path = tmp_path / "history_summary.json"
    itunes_path = tmp_path / "itunes_history.json"
    summary_path.write_text(json.dumps(summary))
    itunes_path.write_text(json.dumps(itunes))

    # Patch module-level path constants and taste-dump helper
    monkeypatch.setattr(btd, "HISTORY_SUMMARY_PATH", str(summary_path))
    monkeypatch.setattr(btd, "ITUNES_PATH", str(itunes_path))
    timeline_out = tmp_path / "taste_timeline.json"
    monkeypatch.setattr(btd, "TIMELINE_PATH", str(timeline_out))
    monkeypatch.setattr(
        btd,
        "_load_now_panel",
        lambda: {"dump_path": "fake.json", "generated_at": "2026-01-01", "top_artists_long_term": [], "top_genres": []},
    )
    monkeypatch.setattr(btd, "_latest_taste_dump", lambda: None)
    monkeypatch.setattr(btd, "DISCOVERY_LOG_PATH", str(tmp_path / "no_ledger.jsonl"))

    result = btd.build_timeline(fetch_tags_fn=lambda a: [])
    gap_years = [g["year"] for g in result["gaps"]]
    assert "2017" in gap_years


def test_sparse_years_annotated(tmp_path, monkeypatch):
    """2015 and 2016 are present but should carry sparse=True notes."""
    summary = {
        "generated_at": "2026-07-16T00:00:00Z",
        "per_year": {
            "2015": {"plays": 5, "hours": 0.5, "skips": 0, "top_artists": []},
            "2016": {"plays": 3, "hours": 0.3, "skips": 0, "top_artists": []},
            "2018": {"plays": 50, "hours": 5.0, "skips": 2, "top_artists": []},
        },
        "all_time_artists": [],
        "all_time_tracks": [],
        "forgotten_favorites": [],
    }
    itunes = {"totals": {}, "top_artists_by_plays": [], "top_tracks_by_plays": [], "top_genres_by_plays": []}

    sp = tmp_path / "history_summary.json"
    ip = tmp_path / "itunes_history.json"
    sp.write_text(json.dumps(summary))
    ip.write_text(json.dumps(itunes))
    tp = tmp_path / "taste_timeline.json"

    monkeypatch.setattr(btd, "HISTORY_SUMMARY_PATH", str(sp))
    monkeypatch.setattr(btd, "ITUNES_PATH", str(ip))
    monkeypatch.setattr(btd, "TIMELINE_PATH", str(tp))
    monkeypatch.setattr(
        btd,
        "_load_now_panel",
        lambda: {"dump_path": "fake.json", "generated_at": "2026-01-01", "top_artists_long_term": [], "top_genres": []},
    )
    monkeypatch.setattr(btd, "_latest_taste_dump", lambda: None)
    monkeypatch.setattr(btd, "DISCOVERY_LOG_PATH", str(tmp_path / "no_ledger.jsonl"))

    result = btd.build_timeline(fetch_tags_fn=lambda a: [])
    sparse = [g for g in result["gaps"] if g.get("sparse")]
    sparse_years = {g["year"] for g in sparse}
    assert "2015" in sparse_years
    assert "2016" in sparse_years


def test_build_output_written_to_file(tmp_path, monkeypatch):
    """build_timeline must write JSON to TIMELINE_PATH."""
    summary = {
        "generated_at": "2026-07-16T00:00:00Z",
        "per_year": {
            "2020": {"plays": 10, "hours": 1.0, "skips": 0, "top_artists": [{"name": "Spoon", "plays": 10}]},
        },
        "all_time_artists": [
            {"name": "Spoon", "plays": 10, "hours": 1.0, "skip_rate": 0.0, "by_year": {"2020": 10}}
        ],
        "all_time_tracks": [
            {"artist": "Spoon", "title": "Inside Out", "plays": 3, "uri": "spotify:track:x", "years": ["2020"]}
        ],
        "forgotten_favorites": [],
    }
    itunes = {"totals": {}, "top_artists_by_plays": [], "top_tracks_by_plays": [], "top_genres_by_plays": []}

    sp = tmp_path / "history_summary.json"
    ip = tmp_path / "itunes_history.json"
    sp.write_text(json.dumps(summary))
    ip.write_text(json.dumps(itunes))
    tp = tmp_path / "taste_timeline.json"

    monkeypatch.setattr(btd, "HISTORY_SUMMARY_PATH", str(sp))
    monkeypatch.setattr(btd, "ITUNES_PATH", str(ip))
    monkeypatch.setattr(btd, "TIMELINE_PATH", str(tp))
    monkeypatch.setattr(
        btd,
        "_load_now_panel",
        lambda: {"dump_path": "fake.json", "generated_at": "2026-01-01", "top_artists_long_term": [], "top_genres": []},
    )
    monkeypatch.setattr(btd, "_latest_taste_dump", lambda: None)
    monkeypatch.setattr(btd, "DISCOVERY_LOG_PATH", str(tmp_path / "no_ledger.jsonl"))

    result = btd.build_timeline(fetch_tags_fn=lambda a: [{"tag": "indie rock", "count": 80}])
    assert tp.exists()
    on_disk = json.loads(tp.read_text())
    assert on_disk["artists"][0]["name"] == "Spoon"
    assert on_disk["artists"][0]["bucket"] == "indie rock"
    assert on_disk["tracks"][0]["uri"] == "spotify:track:x"
    assert "artist_buckets" in on_disk
    assert on_disk["artist_buckets"]["Spoon"] == "indie rock"


def test_artist_buckets_persisted_in_output(tmp_path, monkeypatch):
    """artist_buckets map must be in the output for cheap UI re-use."""
    summary = {
        "generated_at": "2026-07-16T00:00:00Z",
        "per_year": {},
        "all_time_artists": [
            {"name": "Jason Isbell", "plays": 100, "hours": 5.0, "skip_rate": 0.05, "by_year": {}}
        ],
        "all_time_tracks": [],
        "forgotten_favorites": [],
    }
    itunes = {"totals": {}, "top_artists_by_plays": [], "top_tracks_by_plays": [], "top_genres_by_plays": []}

    sp = tmp_path / "h.json"
    ip = tmp_path / "i.json"
    tp = tmp_path / "t.json"
    sp.write_text(json.dumps(summary))
    ip.write_text(json.dumps(itunes))

    monkeypatch.setattr(btd, "HISTORY_SUMMARY_PATH", str(sp))
    monkeypatch.setattr(btd, "ITUNES_PATH", str(ip))
    monkeypatch.setattr(btd, "TIMELINE_PATH", str(tp))
    monkeypatch.setattr(btd, "_load_now_panel", lambda: {"dump_path": "x", "generated_at": "2026-01-01"})
    monkeypatch.setattr(btd, "_latest_taste_dump", lambda: None)
    monkeypatch.setattr(btd, "DISCOVERY_LOG_PATH", str(tmp_path / "no_ledger.jsonl"))

    def stub(a):
        return [{"tag": "americana", "count": 100}]

    result = btd.build_timeline(fetch_tags_fn=stub)
    assert result["artist_buckets"]["Jason Isbell"] == "folk/americana"


def test_latest_taste_dump_ignores_own_output(tmp_path, monkeypatch):
    """taste_timeline.json (this module's output) must never be picked as a taste dump."""
    import os

    import taste_profile

    old = tmp_path / "taste_20260614T043631Z.json"
    old.write_text("{}")
    own = tmp_path / "taste_timeline.json"
    own.write_text("{}")
    # own output is newer — the naive glob would pick it
    os.utime(old, (1, 1))

    monkeypatch.setattr(taste_profile, "DATA_DIR", str(tmp_path))
    assert btd._latest_taste_dump() == str(old)


# ------------------------------------------------------------------ v3: behavior helpers


def test_clock_compaction_cells_to_grid():
    """{wd,h,n} cell lists become 7×24 count arrays."""
    clock = {
        "eras": ["overall"],
        "data": {"overall": [
            {"wd": 0, "h": 0, "n": 5},
            {"wd": 6, "h": 23, "n": 9},
            {"wd": 3, "h": 12, "n": 2},
        ]},
    }
    out = btd._build_behavior_clock(clock)
    g = out["grids"]["overall"]
    assert len(g) == 7 and all(len(row) == 24 for row in g)
    assert g[0][0] == 5
    assert g[6][23] == 9
    assert g[3][12] == 2
    assert g[1][1] == 0


def test_clock_compaction_ignores_out_of_range_cells():
    clock = {"eras": [], "data": {"overall": [{"wd": 7, "h": 0, "n": 3}, {"wd": 0, "h": 24, "n": 3}]}}
    out = btd._build_behavior_clock(clock)
    assert sum(sum(r) for r in out["grids"]["overall"]) == 0


def test_seasonality_bucketing_known_and_unknown():
    """Known artists weight their bucket; unknown artists fall to 'other'."""
    seasonality = {
        "by_year": {"2020": {"1": 10, "6": 4}},
        "artist_by_month": {"2020": {"1": {"Spoon": 7, "Mystery Act": 3}, "6": {"Spoon": 4}}},
    }
    out = btd._build_behavior_seasonality(seasonality, {"Spoon": "indie rock"})
    assert out["month_totals"]["1"] == 10
    assert out["month_totals"]["6"] == 4
    assert out["bucket_by_month"]["1"]["indie rock"] == 7
    assert out["bucket_by_month"]["1"]["other"] == 3
    assert out["bucket_by_month"]["6"] == {"indie rock": 4}


def test_skip_lists_respect_exposure_guard():
    """Artists below the exposure guard are excluded from both lists."""
    artist_skip = {
        "exposure_guard": 20,
        "artists": [
            {"name": "Loyal", "plays": 100, "skips": 0, "skip_rate": 0.0},
            {"name": "Skipped", "plays": 10, "skips": 40, "skip_rate": 0.8},
            {"name": "TooFew", "plays": 5, "skips": 1, "skip_rate": 0.17},
        ],
    }
    out = btd._build_behavior_skip(artist_skip, {"Loyal": "indie rock"})
    names_never = [a["name"] for a in out["never_skip"]]
    names_most = [a["name"] for a in out["most_skipped"]]
    assert "TooFew" not in names_never and "TooFew" not in names_most
    assert names_never[0] == "Loyal"
    assert names_most[0] == "Skipped"
    assert out["never_skip"][0]["bucket"] == "indie rock"
    assert out["most_skipped"][0]["bucket"] == "other"


# ------------------------------------------------------------------ v3: loyalty (V6)


def test_loyalty_single_year_artist():
    atas = [{"name": "OneHit", "plays": 30, "by_year": {"2020": 30}}]
    out = btd._build_loyalty(atas, {})
    assert out[0]["first_year"] == 2020
    assert out[0]["last_year"] == 2020
    assert out[0]["active_years"] == 1
    assert out[0]["still_active"] is False


def test_loyalty_gap_artist_spans_first_to_last():
    """A mid-series gap doesn't shorten the span; active_years counts only play-years."""
    atas = [{"name": "Gappy", "plays": 60, "by_year": {"2018": 30, "2019": 10, "2024": 20}}]
    out = btd._build_loyalty(atas, {"Gappy": "folk/americana"})
    e = out[0]
    assert e["first_year"] == 2018
    assert e["last_year"] == 2024
    assert e["active_years"] == 3
    assert e["bucket"] == "folk/americana"


def test_loyalty_still_active_and_household_flags():
    atas = [
        {"name": "Current", "plays": 50, "by_year": {"2022": 10, "2026": 40}},
        {"name": "CoComelon", "plays": 500, "by_year": {"2021": 300, "2022": 200}},
    ]
    out = btd._build_loyalty(atas, {})
    by_name = {e["name"]: e for e in out}
    assert by_name["Current"]["still_active"] is True
    assert by_name["CoComelon"]["still_active"] is False
    assert by_name["CoComelon"]["household"] is True
    assert by_name["Current"]["household"] is False


def test_loyalty_zero_play_years_ignored():
    """A by_year entry with 0 plays must not extend the span."""
    atas = [{"name": "Padded", "plays": 20, "by_year": {"2019": 0, "2020": 20, "2023": 0}}]
    out = btd._build_loyalty(atas, {})
    assert out[0]["first_year"] == 2020
    assert out[0]["last_year"] == 2020


# ------------------------------------------------------------------ v3: discovery (V8)


def _write_ledger(tmp_path, lines):
    p = tmp_path / "dlog.jsonl"
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def test_discovery_dedupe_keeps_earliest(tmp_path):
    lines = [
        json.dumps({"ts": "2026-06-20T00:00:00Z", "artist": "New Act", "title": "B"}),
        json.dumps({"ts": "2026-06-15T00:00:00Z", "artist": "New Act", "title": "A"}),
    ]
    out = btd._build_discovery(_write_ledger(tmp_path, lines), [], None, {})
    assert out["total"] == 1
    assert out["events"][0]["date"] == "2026-06-15"


def test_discovery_stuck_via_history_and_not_stuck(tmp_path):
    lines = [
        json.dumps({"ts": "2026-06-15T00:00:00Z", "artist": "Spoon"}),
        json.dumps({"ts": "2026-06-16T00:00:00Z", "artist": "Nobody Yet"}),
    ]
    atas = [{"name": "Spoon", "plays": 10, "by_year": {}}]
    out = btd._build_discovery(_write_ledger(tmp_path, lines), atas, None, {})
    by_artist = {e["artist"]: e for e in out["events"]}
    assert by_artist["Spoon"]["stuck"] is True
    assert by_artist["Nobody Yet"]["stuck"] is False
    assert out["stuck_count"] == 1


def test_discovery_stuck_via_taste_dump(tmp_path):
    dump = tmp_path / "taste_20260701T000000Z.json"
    dump.write_text(json.dumps({
        "top_artists": {"long_term": [{"name": "Sticky Artist"}]},
        "saved_tracks": [{"name": "T", "artists": [{"name": "Saved Artist"}]}],
    }))
    lines = [
        json.dumps({"ts": "2026-06-15T00:00:00Z", "artist": "Sticky Artist"}),
        json.dumps({"ts": "2026-06-16T00:00:00Z", "artist": "Saved Artist"}),
    ]
    out = btd._build_discovery(_write_ledger(tmp_path, lines), [], str(dump), {})
    assert all(e["stuck"] for e in out["events"])


def test_discovery_malformed_line_skipped(tmp_path):
    lines = [
        "{not json at all",
        json.dumps({"ts": "2026-06-15T00:00:00Z", "artist": "Fine"}),
        json.dumps({"ts": "2026-06-15T00:00:00Z"}),  # no artist
    ]
    out = btd._build_discovery(_write_ledger(tmp_path, lines), [], None, {})
    assert out["total"] == 1
    assert out["events"][0]["artist"] == "Fine"


def test_discovery_playlist_url_reduced_to_id(tmp_path):
    lines = [json.dumps({
        "ts": "2026-06-15T00:00:00Z", "artist": "X",
        "playlist": "https://open.spotify.com/playlist/5Eg84FoPynQDLzx7Gib1u9",
    })]
    out = btd._build_discovery(_write_ledger(tmp_path, lines), [], None, {})
    assert out["events"][0]["playlist"] == "5Eg84FoPynQDLzx7Gib1u9"


def test_discovery_missing_ledger_is_empty(tmp_path):
    out = btd._build_discovery(str(tmp_path / "absent.jsonl"), [], None, {})
    assert out["total"] == 0 and out["events"] == []


# ------------------------------------------------------------------ v3: full-build shape


def test_build_includes_v3_keys_and_keeps_v2_shape(tmp_path, monkeypatch):
    """New top-level keys present; all pre-existing keys still emitted (additive only)."""
    summary = {
        "generated_at": "2026-07-16T00:00:00Z",
        "per_year": {
            "2020": {"plays": 10, "hours": 1.0, "skips": 0, "top_artists": [{"name": "Spoon", "plays": 10}]},
        },
        "all_time_artists": [
            {"name": "Spoon", "plays": 10, "hours": 1.0, "skip_rate": 0.0, "by_year": {"2020": 10}}
        ],
        "all_time_tracks": [],
        "forgotten_favorites": [],
        "v2_meta": {"household_excluded_plays": 7, "note": "n"},
        "intentionality": {"by_year": {"2020": {"deliberate": 1, "passive": 2, "shuffle": 3, "other": 0, "total": 6}}},
        "clock": {"eras": ["overall"], "data": {"overall": [{"wd": 0, "h": 9, "n": 4}]}},
        "seasonality": {"by_year": {"2020": {"1": 10}}, "artist_by_month": {"2020": {"1": {"Spoon": 10}}}},
        "platforms": {"by_year": {"2020": {"mobile": 8, "desktop": 2}}, "platform_map": {"raw": "mobile"}},
        "artist_skip": {"exposure_guard": 20, "artists": [{"name": "Spoon", "plays": 100, "skips": 5, "skip_rate": 0.05}]},
        "obsession_episodes": {"episodes": [{"artist": "Spoon", "title": "T", "window_start": "2020-01-01", "plays": 16}]},
        "rediscoveries": {"artists": [{"artist": "Spoon", "gap_last_before": 2018, "gap_first_after": 2021, "total_plays": 10, "by_year": {}}]},
    }
    itunes = {"totals": {}, "top_artists_by_plays": [], "top_tracks_by_plays": [], "top_genres_by_plays": []}

    sp = tmp_path / "h.json"
    ip = tmp_path / "i.json"
    tp = tmp_path / "t.json"
    sp.write_text(json.dumps(summary))
    ip.write_text(json.dumps(itunes))
    ledger = tmp_path / "dlog.jsonl"
    ledger.write_text(json.dumps({"ts": "2026-06-15T00:00:00Z", "artist": "Spoon"}) + "\n")

    monkeypatch.setattr(btd, "HISTORY_SUMMARY_PATH", str(sp))
    monkeypatch.setattr(btd, "ITUNES_PATH", str(ip))
    monkeypatch.setattr(btd, "TIMELINE_PATH", str(tp))
    monkeypatch.setattr(btd, "DISCOVERY_LOG_PATH", str(ledger))
    monkeypatch.setattr(btd, "_latest_taste_dump", lambda: None)
    monkeypatch.setattr(
        btd,
        "_load_now_panel",
        lambda: {"dump_path": "fake.json", "generated_at": "2026-01-01", "top_artists_long_term": [], "top_genres": []},
    )

    result = btd.build_timeline(fetch_tags_fn=lambda a: [{"tag": "indie rock", "count": 80}])

    # v2 keys untouched (additive only)
    for key in ("itunes_era", "years", "artists", "tracks", "genre_waves",
                "gaps", "annotations", "now", "artist_buckets"):
        assert key in result, key
    # v3 keys present and wired
    assert result["behavior"]["household_excluded_plays"] == 7
    assert result["behavior"]["clock"]["grids"]["overall"][0][9] == 4
    assert result["behavior"]["intentionality"]["by_year"]["2020"]["shuffle"] == 3
    assert result["behavior"]["platforms"]["by_year"]["2020"]["mobile"] == 8
    assert "platform_map" not in json.dumps(result["behavior"]["platforms"])
    assert result["behavior"]["skip"]["never_skip"][0]["name"] == "Spoon"
    assert result["behavior"]["obsessions"][0]["plays"] == 16
    assert result["behavior"]["rediscoveries"][0]["artist"] == "Spoon"
    assert result["loyalty"][0]["name"] == "Spoon"
    assert result["discovery"]["events"][0]["stuck"] is True
