"""GDPR extended-history aggregation: play/skip threshold, per-year rollups,
forgotten-favorites windowing, and the lean snapshot shape.

Runs against a synthetic export dir — never the real (gitignored, personal) one.

v2 tests cover: UTC→Eastern timezone conversion, clock bucketing, intentionality
precedence, platform normalization, skip-rate exposure guard, obsession window
detection, rediscovery gap logic, household exclusion, and v1-shape stability.
"""

import json

import streaming_history


def _event(ts, artist, title, ms, uri="spotify:track:x", **kwargs):
    """Build a minimal synthetic event. Extra kwargs populate optional fields."""
    base = {
        "ts": ts,
        "ms_played": ms,
        "master_metadata_track_name": title,
        "master_metadata_album_artist_name": artist,
        "spotify_track_uri": uri,
        # Optional fields default to None / False
        "reason_start": kwargs.get("reason_start", None),
        "reason_end": kwargs.get("reason_end", None),
        "shuffle": kwargs.get("shuffle", False),
        "skipped": kwargs.get("skipped", None),
        "platform": kwargs.get("platform", "android"),
    }
    return base


def _write_export(tmp_path, events, year="2020"):
    src = tmp_path / "export"
    src.mkdir(exist_ok=True)
    (src / f"Streaming_History_Audio_{year}.json").write_text(json.dumps(events))
    return str(src)


# ============================================================
# v1 tests (unchanged behavior)
# ============================================================


def test_play_vs_skip_threshold_and_podcast_drop(tmp_path):
    events = [
        _event("2020-01-01T10:00:00Z", "Spoon", "Inside Out", 240_000),
        _event("2020-01-01T10:05:00Z", "Spoon", "Inside Out", 5_000),  # skip
        # podcast row: no track uri -> dropped entirely
        {"ts": "2020-01-01T11:00:00Z", "ms_played": 900_000, "spotify_track_uri": None},
    ]
    out = tmp_path / "summary.json"
    s = streaming_history.build_history(_write_export(tmp_path, events), str(out))
    assert s["events"] == 2
    assert s["total_plays"] == 1
    a = s["all_time_artists"][0]
    assert a["name"] == "Spoon" and a["plays"] == 1 and a["skip_rate"] == 0.5
    assert s["per_year"]["2020"]["plays"] == 1
    assert out.exists()


def test_forgotten_favorites_windowing(tmp_path, monkeypatch):
    monkeypatch.setattr(streaming_history, "FORGOTTEN_MIN_PLAYS", 3)
    events = (
        # heavy in 2020, silent in the last-2-years window (2021, 2022) -> forgotten
        [_event(f"2020-01-0{i}T10:00:00Z", "OK Go", f"t{i}", 200_000) for i in range(1, 5)]
        # still active in 2022 -> not forgotten
        + [_event(f"2022-01-0{i}T10:00:00Z", "Spoon", f"s{i}", 200_000) for i in range(1, 5)]
        + [_event("2021-06-01T10:00:00Z", "Filler", "f", 200_000)]
    )
    s = streaming_history.build_history(
        _write_export(tmp_path, events), str(tmp_path / "s.json")
    )
    names = [f["name"] for f in s["forgotten_favorites"]]
    assert names == ["OK Go"]
    assert s["forgotten_favorites"][0]["peak_year"] == "2020"


def test_snapshot_shapes(tmp_path):
    events = [
        _event("2019-03-01T10:00:00Z", "Guster", "Satellite", 200_000),
        _event("2020-03-01T10:00:00Z", "Spoon", "Inside Out", 200_000),
    ]
    s = streaming_history.build_history(
        _write_export(tmp_path, events), str(tmp_path / "s.json")
    )
    snap = streaming_history.snapshot(s)
    assert snap["total_plays"] == 2
    assert set(snap["per_year"]) == {"2019", "2020"}
    assert snap["per_year"]["2019"]["top5"] == ["Guster"]

    year = streaming_history.snapshot(s, year="2020")
    assert year["top_artists"] == ["Spoon (1)"]
    assert year["top_tracks"] == ["Spoon — Inside Out (1)"]

    missing = streaming_history.snapshot(s, year="1999")
    assert "error" in missing and missing["years"] == ["2019", "2020"]


# ============================================================
# v1-shape stability: v2 additions must not alter v1 keys
# ============================================================


def test_v1_shape_stability(tmp_path):
    """All original top-level keys must remain present and structurally correct."""
    events = [
        _event("2021-06-15T20:00:00Z", "Spoon", "Inside Out", 240_000,
               reason_start="clickrow"),
        _event("2021-06-15T20:05:00Z", "Spoon", "Inside Out", 5_000,
               reason_start="trackdone"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))

    v1_keys = {
        "generated_at", "source", "events", "first_play", "last_play",
        "total_plays", "total_hours", "unique_artists", "unique_tracks",
        "per_year", "all_time_artists", "all_time_tracks", "forgotten_favorites",
    }
    assert v1_keys.issubset(set(s.keys())), f"Missing v1 keys: {v1_keys - set(s.keys())}"

    # snapshot() shape unchanged
    snap = streaming_history.snapshot(s)
    snap_keys = {
        "generated_at", "span", "total_plays", "total_hours",
        "unique_artists", "per_year", "all_time_top_artists", "forgotten_favorites",
    }
    assert snap_keys.issubset(set(snap.keys()))

    # v2 keys must NOT appear in snapshot
    for k in ("clock", "intentionality", "platforms", "artist_skip",
               "obsession_episodes", "rediscoveries", "seasonality"):
        assert k not in snap, f"v2 key {k!r} leaked into snapshot()"


# ============================================================
# UTC → Eastern timezone conversion
# ============================================================


def test_utc_to_eastern_hour_bucketing(tmp_path):
    """A play at 02:00 UTC = 22:00 Eastern (EST, UTC-5) on previous calendar day."""
    # 2021-01-15 02:00 UTC → 2021-01-14 21:00 EST (UTC-5 in January)
    events = [
        _event("2021-01-15T02:00:00Z", "Spoon", "Day Cross", 240_000,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    clock_data = s["clock"]["data"]["overall"]
    # The play must land at h=21 (9pm EST), not h=2 (UTC).
    assert any(cell["h"] == 21 for cell in clock_data), (
        "Expected hour=21 (9pm EST) but got: " + str(clock_data)
    )
    assert not any(cell["h"] == 2 for cell in clock_data), (
        "UTC hour 2 leaked into clock — conversion not applied"
    )


def test_utc_to_eastern_crosses_midnight(tmp_path):
    """A play at 03:30 UTC in July = 23:30 Eastern (EDT, UTC-4) on previous calendar day."""
    # 2021-07-20 03:30 UTC → 2021-07-19 23:30 EDT (UTC-4 in summer)
    events = [
        _event("2021-07-20T03:30:00Z", "Spoon", "Night Track", 240_000,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    clock_data = s["clock"]["data"]["overall"]
    # Should land at h=23 (11pm EDT)
    assert any(cell["h"] == 23 for cell in clock_data), (
        "Expected hour=23 (11pm EDT) after midnight crossover, got: " + str(clock_data)
    )


# ============================================================
# Clock bucketing and era assignment
# ============================================================


def test_clock_era_bucketing(tmp_path):
    """Plays in different years land in the correct era buckets."""
    events = [
        # 2018 era: 2018-06-15 15:00 UTC → 11:00 EDT (UTC-4)
        _event("2018-06-15T15:00:00Z", "Artist2018", "Song", 240_000,
               reason_start="playbtn"),
        # 2020 era (2019-2020): 2020-03-01 16:00 UTC → 12:00 EST? No, March EST = UTC-5
        # Actually March 1 2020 = before DST, so EST (UTC-5): 16-5=11:00 EST
        _event("2020-03-01T16:00:00Z", "Artist2020", "Song", 240_000,
               reason_start="playbtn"),
        # 2025 era (2025-2026): 2025-09-10 20:00 UTC → 16:00 EDT (UTC-4)
        _event("2025-09-10T20:00:00Z", "Artist2025", "Song", 240_000,
               reason_start="playbtn"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    clock = s["clock"]["data"]

    assert len(clock["2018"]) == 1, "2018 era should have exactly 1 cell"
    assert len(clock["2019-2020"]) == 1, "2019-2020 era should have exactly 1 cell"
    assert len(clock["2025-2026"]) == 1, "2025-2026 era should have exactly 1 cell"
    assert len(clock["overall"]) == 3, "overall should have 3 cells"
    # 2021-2022 and 2023-2024 eras should be empty
    assert clock["2021-2022"] == []
    assert clock["2023-2024"] == []


# ============================================================
# Intentionality
# ============================================================


def test_intentionality_deliberate(tmp_path):
    """clickrow reason_start, shuffle=False → deliberate."""
    events = [
        _event("2021-03-01T14:00:00Z", "Spoon", "T1", 240_000,
               reason_start="clickrow", shuffle=False),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    y = s["intentionality"]["by_year"]["2021"]
    assert y["deliberate"] == 1
    assert y["passive"] == 0
    assert y["shuffle"] == 0


def test_intentionality_passive(tmp_path):
    """trackdone reason_start, shuffle=False → passive."""
    events = [
        _event("2021-03-01T14:00:00Z", "Spoon", "T1", 240_000,
               reason_start="trackdone", shuffle=False),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    y = s["intentionality"]["by_year"]["2021"]
    assert y["passive"] == 1
    assert y["deliberate"] == 0
    assert y["shuffle"] == 0


def test_intentionality_remote_is_deliberate(tmp_path):
    """remote = play started from another device (Connect/voice) → deliberate."""
    events = [
        _event("2021-03-01T14:00:00Z", "Spoon", "T1", 240_000,
               reason_start="remote", shuffle=False),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    y = s["intentionality"]["by_year"]["2021"]
    assert y["deliberate"] == 1
    assert y["passive"] == 0


def test_intentionality_appload_is_passive(tmp_path):
    """appload = app auto-resumed on launch, no track choice made → passive."""
    events = [
        _event("2021-03-01T14:00:00Z", "Spoon", "T1", 240_000,
               reason_start="appload", shuffle=False),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    y = s["intentionality"]["by_year"]["2021"]
    assert y["passive"] == 1
    assert y["deliberate"] == 0


def test_intentionality_shuffle_wins_over_clickrow(tmp_path):
    """shuffle=True overrides clickrow → shuffle (shuffle has highest precedence)."""
    events = [
        _event("2021-03-01T14:00:00Z", "Spoon", "T1", 240_000,
               reason_start="clickrow", shuffle=True),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    y = s["intentionality"]["by_year"]["2021"]
    assert y["shuffle"] == 1, "shuffle=True must win over deliberate reason_start"
    assert y["deliberate"] == 0


def test_intentionality_shuffle_wins_over_trackdone(tmp_path):
    """shuffle=True overrides trackdone → shuffle."""
    events = [
        _event("2021-03-01T14:00:00Z", "Spoon", "T1", 240_000,
               reason_start="trackdone", shuffle=True),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    y = s["intentionality"]["by_year"]["2021"]
    assert y["shuffle"] == 1
    assert y["passive"] == 0


def test_intentionality_other(tmp_path):
    """unknown reason_start, shuffle=False → other."""
    events = [
        _event("2021-03-01T14:00:00Z", "Spoon", "T1", 240_000,
               reason_start="unknown", shuffle=False),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    y = s["intentionality"]["by_year"]["2021"]
    assert y["other"] == 1


def test_intentionality_reason_start_counts_present(tmp_path):
    """reason_start_counts must be present for auditing."""
    events = [
        _event("2021-03-01T14:00:00Z", "Spoon", "T1", 240_000,
               reason_start="clickrow", shuffle=False),
        _event("2021-03-02T14:00:00Z", "Spoon", "T2", 240_000,
               reason_start="trackdone", shuffle=False),
        _event("2021-03-03T14:00:00Z", "Spoon", "T3", 240_000,
               reason_start="trackdone", shuffle=False),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    rc = s["intentionality"]["by_year"]["2021"]["reason_start_counts"]
    assert rc.get("clickrow") == 1
    assert rc.get("trackdone") == 2


def test_intentionality_skips_not_counted(tmp_path):
    """Sub-30s events (skips) must not appear in intentionality counts."""
    events = [
        _event("2021-03-01T14:00:00Z", "Spoon", "T1", 240_000,
               reason_start="clickrow", shuffle=False),
        _event("2021-03-01T14:05:00Z", "Spoon", "T2", 5_000,  # skip
               reason_start="trackdone", shuffle=False),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    y = s["intentionality"]["by_year"]["2021"]
    assert y["total"] == 1  # only the play counts


# ============================================================
# Platform normalization
# ============================================================


def test_platform_mobile_android(tmp_path):
    events = [
        _event("2020-06-01T14:00:00Z", "Spoon", "T1", 240_000,
               platform="Android OS 10 API 29 (samsung, SM-N960U)", reason_start="playbtn"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["platforms"]["by_year"]["2020"].get("mobile", 0) == 1


def test_platform_desktop_osx(tmp_path):
    events = [
        _event("2020-06-01T14:00:00Z", "Spoon", "T1", 240_000,
               platform="OS X 10.15.3 [x86 8]", reason_start="playbtn"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["platforms"]["by_year"]["2020"].get("desktop", 0) == 1


def test_platform_desktop_windows(tmp_path):
    events = [
        _event("2020-06-01T14:00:00Z", "Spoon", "T1", 240_000,
               platform="windows", reason_start="playbtn"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["platforms"]["by_year"]["2020"].get("desktop", 0) == 1


def test_platform_speaker_tv_amazon(tmp_path):
    events = [
        _event("2020-06-01T14:00:00Z", "Spoon", "T1", 240_000,
               platform="Partner amazon_salmon Amazon;Echo_Dot;id;;tpapi", reason_start="remote"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["platforms"]["by_year"]["2020"].get("speaker_tv", 0) == 1


def test_platform_web(tmp_path):
    events = [
        _event("2020-06-01T14:00:00Z", "Spoon", "T1", 240_000,
               platform="Partner spotify web_player", reason_start="playbtn"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["platforms"]["by_year"]["2020"].get("web", 0) == 1


def test_platform_unknown_goes_to_other(tmp_path):
    """A totally unknown platform string must land in 'other'."""
    events = [
        _event("2020-06-01T14:00:00Z", "Spoon", "T1", 240_000,
               platform="not_applicable", reason_start="playbtn"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["platforms"]["by_year"]["2020"].get("other", 0) == 1


def test_platform_map_present(tmp_path):
    """platform_map must be present and contain the raw strings seen."""
    events = [
        _event("2020-06-01T14:00:00Z", "Spoon", "T1", 240_000,
               platform="android", reason_start="playbtn"),
        _event("2020-06-02T14:00:00Z", "Spoon", "T2", 240_000,
               platform="windows", reason_start="playbtn"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    pm = s["platforms"]["platform_map"]
    assert "android" in pm and pm["android"] == "mobile"
    assert "windows" in pm and pm["windows"] == "desktop"


# ============================================================
# Artist skip
# ============================================================


def test_artist_skip_exposure_guard(tmp_path):
    """exposure field lets callers apply the SKIP_EXPOSURE_MIN guard themselves."""
    events = [
        _event("2020-06-01T14:00:00Z", "Rare Artist", "T1", 240_000,
               reason_start="playbtn"),
        _event("2020-06-02T14:00:00Z", "Rare Artist", "T1", 5_000,
               reason_start="trackdone"),  # skip
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    guard = s["artist_skip"]["exposure_guard"]
    assert guard == streaming_history.SKIP_EXPOSURE_MIN

    rare = next(
        (a for a in s["artist_skip"]["artists"] if a["name"] == "Rare Artist"), None
    )
    assert rare is not None
    assert rare["plays"] == 1
    assert rare["skips"] == 1
    assert rare["exposure"] == 2  # below guard → caller filters it out
    assert rare["skip_rate"] == 0.5


def test_artist_skip_rate_calculation(tmp_path):
    """skip_rate = skips / (plays + skips)."""
    events = (
        [_event(f"2020-06-0{i}T14:00:00Z", "Heavy", f"T{i}", 240_000,
                reason_start="playbtn") for i in range(1, 4)]  # 3 plays
        + [_event(f"2020-06-1{i}T14:00:00Z", "Heavy", f"S{i}", 5_000,
                  reason_start="trackdone") for i in range(1, 3)]  # 2 skips
    )
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    heavy = next(a for a in s["artist_skip"]["artists"] if a["name"] == "Heavy")
    assert heavy["plays"] == 3
    assert heavy["skips"] == 2
    assert heavy["skip_rate"] == round(2 / 5, 3)


# ============================================================
# Obsession episodes
# ============================================================


def test_obsession_exactly_at_threshold(tmp_path, monkeypatch):
    """Exactly OBSESSION_MIN_PLAYS plays in window → one episode."""
    monkeypatch.setattr(streaming_history, "OBSESSION_MIN_PLAYS", 3)
    # 3 plays of same track on consecutive days (well within 30-day window)
    events = [
        _event(f"2021-0{m}-{d:02d}T14:00:00Z", "Spoon", "Obsessed", 240_000,
               reason_start="clickrow")
        for m, d in [(3, 1), (3, 5), (3, 10)]
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    episodes = s["obsession_episodes"]["episodes"]
    assert len(episodes) == 1
    assert episodes[0]["artist"] == "Spoon"
    assert episodes[0]["title"] == "Obsessed"
    assert episodes[0]["plays"] == 3


def test_obsession_below_threshold_no_episode(tmp_path, monkeypatch):
    """Below OBSESSION_MIN_PLAYS → no episode."""
    monkeypatch.setattr(streaming_history, "OBSESSION_MIN_PLAYS", 5)
    events = [
        _event(f"2021-03-{d:02d}T14:00:00Z", "Spoon", "Just3", 240_000,
               reason_start="clickrow")
        for d in [1, 5, 10]
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["obsession_episodes"]["episodes"] == []


def test_obsession_window_straddling_month_boundary(tmp_path, monkeypatch):
    """Window that straddles a month boundary must still detect the episode."""
    monkeypatch.setattr(streaming_history, "OBSESSION_MIN_PLAYS", 3)
    # 3 plays: Jan 25, Feb 1, Feb 10 (all within 30 days of Jan 25)
    events = [
        _event("2021-01-25T14:00:00Z", "Spoon", "MonthCross", 240_000, reason_start="clickrow"),
        _event("2021-02-01T14:00:00Z", "Spoon", "MonthCross", 240_000, reason_start="clickrow"),
        _event("2021-02-10T14:00:00Z", "Spoon", "MonthCross", 240_000, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    episodes = s["obsession_episodes"]["episodes"]
    # All 3 plays fall within Jan 25 + 30 days = Feb 24, so should detect 1 episode
    assert len(episodes) == 1
    assert episodes[0]["plays"] == 3


def test_obsession_outside_window_no_episode(tmp_path, monkeypatch):
    """Plays spread > 30 days apart → no single episode."""
    monkeypatch.setattr(streaming_history, "OBSESSION_MIN_PLAYS", 2)
    # 2 plays 31 days apart (outside the 30-day window)
    events = [
        _event("2021-01-01T14:00:00Z", "Spoon", "Spread", 240_000, reason_start="clickrow"),
        _event("2021-02-02T14:00:00Z", "Spoon", "Spread", 240_000, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["obsession_episodes"]["episodes"] == []


# ============================================================
# Rediscoveries
# ============================================================


def test_rediscovery_two_year_gap_detected(tmp_path):
    """Artist active in 2018, silent 2019+2020, active 2021 → gap=2, detected."""
    events = (
        [_event(f"2018-06-{d:02d}T14:00:00Z", "Comeback Band", f"T{d}", 240_000,
                reason_start="playbtn") for d in range(1, 5)]
        + [_event(f"2021-06-{d:02d}T14:00:00Z", "Comeback Band", f"N{d}", 240_000,
                  reason_start="clickrow") for d in range(1, 5)]
    )
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    rediscoveries = s["rediscoveries"]["artists"]
    names = [r["artist"] for r in rediscoveries]
    assert "Comeback Band" in names
    rec = next(r for r in rediscoveries if r["artist"] == "Comeback Band")
    assert rec["gap_last_before"] == 2018
    assert rec["gap_first_after"] == 2021
    assert rec["gap_years"] == 2  # 2019, 2020 = 2 silent years


def test_rediscovery_one_year_gap_not_detected(tmp_path):
    """Artist active 2018, silent 2019, active 2020 → gap=1 < 2 → NOT a rediscovery."""
    events = (
        [_event(f"2018-06-{d:02d}T14:00:00Z", "NoGap", f"T{d}", 240_000,
                reason_start="playbtn") for d in range(1, 5)]
        + [_event(f"2020-06-{d:02d}T14:00:00Z", "NoGap", f"N{d}", 240_000,
                  reason_start="clickrow") for d in range(1, 5)]
    )
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    names = [r["artist"] for r in s["rediscoveries"]["artists"]]
    assert "NoGap" not in names, "1-year gap should NOT qualify as a rediscovery"


def test_rediscovery_gap_at_series_start_not_counted(tmp_path):
    """Artist who only started playing in 2021 (no earlier plays) → NOT a rediscovery."""
    events = [
        _event(f"2021-06-{d:02d}T14:00:00Z", "NewArtist", f"T{d}", 240_000,
               reason_start="clickrow") for d in range(1, 5)
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    names = [r["artist"] for r in s["rediscoveries"]["artists"]]
    assert "NewArtist" not in names, "Gap at series start must not count"


def test_rediscovery_gap_at_series_end_not_counted(tmp_path):
    """Artist who played 2018-2020 and then disappeared → NOT a rediscovery (no comeback)."""
    events = (
        [_event(f"2018-06-{d:02d}T14:00:00Z", "FadedArt", f"T{d}", 240_000,
                reason_start="playbtn") for d in range(1, 5)]
        + [_event(f"2019-06-{d:02d}T14:00:00Z", "FadedArt", f"N{d}", 240_000,
                  reason_start="clickrow") for d in range(1, 5)]
    )
    # No plays after 2019 → if there were a gap after 2019 it's at the series end
    # The implementation finds gaps within sorted_years where both sides have plays.
    # 2018→2019 has no gap (consecutive), so no rediscovery.
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    names = [r["artist"] for r in s["rediscoveries"]["artists"]]
    assert "FadedArt" not in names


def test_rediscovery_by_year_series_present(tmp_path):
    """Rediscovery artist must include a by_year play series."""
    events = (
        [_event(f"2018-06-{d:02d}T14:00:00Z", "ReturnBand", f"T{d}", 240_000,
                reason_start="playbtn") for d in range(1, 5)]
        + [_event(f"2021-06-{d:02d}T14:00:00Z", "ReturnBand", f"N{d}", 240_000,
                  reason_start="clickrow") for d in range(1, 5)]
    )
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    rec = next(r for r in s["rediscoveries"]["artists"] if r["artist"] == "ReturnBand")
    assert "by_year" in rec
    assert "2018" in rec["by_year"]
    assert "2021" in rec["by_year"]


# ============================================================
# Household exclusion
# ============================================================


def test_household_excluded_from_clock(tmp_path):
    """CoComelon plays must not appear in the clock section."""
    events = [
        _event("2021-06-15T14:00:00Z", "CoComelon", "Baby Shark", 240_000,
               reason_start="clickrow"),
        _event("2021-06-15T15:00:00Z", "Spoon", "Inside Out", 240_000,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    # Only 1 play (Spoon) should appear in the overall clock — 1 non-zero cell.
    total_clock_plays = sum(
        cell["n"] for cell in s["clock"]["data"]["overall"]
    )
    assert total_clock_plays == 1, (
        f"Clock should have exactly 1 play (Spoon), got {total_clock_plays}"
    )


def test_household_excluded_from_intentionality(tmp_path):
    """CoComelon plays must not appear in intentionality counts."""
    events = [
        _event("2021-06-15T14:00:00Z", "CoComelon", "Baby Shark", 240_000,
               reason_start="clickrow"),
        _event("2021-06-15T15:00:00Z", "Spoon", "Inside Out", 240_000,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    y = s["intentionality"]["by_year"]["2021"]
    assert y["deliberate"] == 1  # only Spoon
    assert y["total"] == 1


def test_household_excluded_from_artist_skip(tmp_path):
    """CoComelon must not appear in artist_skip section."""
    events = [
        _event("2021-06-15T14:00:00Z", "CoComelon", "Baby Shark", 240_000,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    names = [a["name"] for a in s["artist_skip"]["artists"]]
    assert "CoComelon" not in names


def test_household_excluded_from_rediscoveries(tmp_path):
    """CoComelon must not appear in rediscoveries."""
    events = (
        [_event(f"2018-06-{d:02d}T14:00:00Z", "CoComelon", f"T{d}", 240_000,
                reason_start="playbtn") for d in range(1, 5)]
        + [_event(f"2021-06-{d:02d}T14:00:00Z", "CoComelon", f"N{d}", 240_000,
                  reason_start="clickrow") for d in range(1, 5)]
    )
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    names = [r["artist"] for r in s["rediscoveries"]["artists"]]
    assert "CoComelon" not in names


def test_household_excluded_from_obsessions(tmp_path, monkeypatch):
    """CoComelon plays must not appear in obsession_episodes."""
    monkeypatch.setattr(streaming_history, "OBSESSION_MIN_PLAYS", 2)
    events = [
        _event(f"2021-03-{d:02d}T14:00:00Z", "CoComelon", "Baby Shark", 240_000,
               reason_start="clickrow")
        for d in range(1, 10)  # 9 plays well above any threshold
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    for ep in s["obsession_episodes"]["episodes"]:
        assert ep["artist"] != "CoComelon", "CoComelon must not appear in obsession episodes"


def test_household_excluded_plays_count(tmp_path):
    """household_excluded_plays must equal the count of household plays."""
    events = [
        _event("2021-06-15T14:00:00Z", "CoComelon", "Baby Shark", 240_000,
               reason_start="clickrow"),
        _event("2021-06-15T14:30:00Z", "CoComelon", "Wheels on Bus", 240_000,
               reason_start="clickrow"),
        _event("2021-06-15T15:00:00Z", "Spoon", "Inside Out", 240_000,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["v2_meta"]["household_excluded_plays"] == 2


def test_white_noise_excluded(tmp_path):
    """An artist matching the white-noise regex must also be excluded."""
    events = [
        _event("2021-06-15T14:00:00Z", "White Noise Baby Sleep", "Track", 240_000,
               reason_start="clickrow"),
        _event("2021-06-15T15:00:00Z", "Spoon", "Inside Out", 240_000,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    total_clock_plays = sum(cell["n"] for cell in s["clock"]["data"]["overall"])
    assert total_clock_plays == 1
    assert s["v2_meta"]["household_excluded_plays"] == 1


# ============================================================
# Seasonality
# ============================================================


def test_seasonality_monthly_totals(tmp_path):
    """Monthly totals must match play counts per month."""
    events = [
        _event("2021-01-15T14:00:00Z", "Spoon", "T1", 240_000, reason_start="clickrow"),
        _event("2021-01-20T14:00:00Z", "Spoon", "T2", 240_000, reason_start="clickrow"),
        _event("2021-03-10T14:00:00Z", "Guster", "T3", 240_000, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    m = s["seasonality"]["by_year"]["2021"]
    assert m.get("1") == 2  # January
    assert m.get("3") == 1  # March
    assert m.get("2") is None  # February — no plays


def test_seasonality_artist_by_month_top_artist_present(tmp_path):
    """Top artists must appear in the artist_by_month slice."""
    events = [
        _event("2021-06-01T14:00:00Z", "Spoon", "T1", 240_000, reason_start="clickrow"),
        _event("2021-06-15T14:00:00Z", "Spoon", "T2", 240_000, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    abm = s["seasonality"]["artist_by_month"]
    assert "2021" in abm
    june = abm["2021"].get("6", {})
    assert june.get("Spoon") == 2


# ============================================================
# v2 section metadata
# ============================================================


def test_v2_sections_present(tmp_path):
    """All seven v2 sections must be present as top-level keys."""
    events = [
        _event("2021-06-15T14:00:00Z", "Spoon", "Inside Out", 240_000,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    for key in ("clock", "intentionality", "seasonality", "platforms",
                "artist_skip", "obsession_episodes", "rediscoveries", "v2_meta"):
        assert key in s, f"Missing v2 section: {key!r}"


def test_clock_section_structure(tmp_path):
    """clock section must have 'data' with 'overall' and era slugs."""
    events = [
        _event("2021-06-15T14:00:00Z", "Spoon", "T1", 240_000, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    clock = s["clock"]
    assert "data" in clock
    assert "overall" in clock["data"]
    for era in streaming_history.STREAMING_ERAS:
        assert era["slug"] in clock["data"], f"Missing era slug: {era['slug']}"


def test_obsession_min_plays_constant_in_output(tmp_path):
    """obsession_min_plays must be echoed in the output metadata."""
    events = [
        _event("2021-06-15T14:00:00Z", "Spoon", "T1", 240_000, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    assert s["obsession_episodes"]["obsession_min_plays"] == streaming_history.OBSESSION_MIN_PLAYS
