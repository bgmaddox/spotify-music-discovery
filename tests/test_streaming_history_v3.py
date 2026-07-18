"""v3 aggregation tests: album sessions, one-track wonders, track stories,
track seasons, per-year tracks (receipt), yearbook anthems, and household exclusion
of all new sections.

All tests run against synthetic export dirs — never the real (gitignored) personal data.
Mirrors the style of tests/test_streaming_history.py.
"""

import json

import streaming_history
from streaming_history import (
    _detect_album_sessions,
    _track_season_concentration,
    ALBUM_SESSION_MIN_PLAYS,
    ALBUM_SESSION_MAX_GAP_S,
    ONE_TRACK_WONDER_HIT_MIN,
    ONE_TRACK_WONDER_REST_MAX,
    TRACK_SEASON_MIN_PLAYS,
    TRACK_SEASON_CONCENTRATION,
)


# ------------------------------------------------------------------ helpers

def _event(ts, artist, title, ms, uri="spotify:track:x", album="Self-Titled", **kwargs):
    """Build a minimal synthetic event. Extra kwargs populate optional fields."""
    return {
        "ts": ts,
        "ms_played": ms,
        "master_metadata_track_name": title,
        "master_metadata_album_artist_name": artist,
        "master_metadata_album_album_name": kwargs.get("album_name", album),
        "spotify_track_uri": uri,
        "reason_start": kwargs.get("reason_start", None),
        "reason_end": kwargs.get("reason_end", None),
        "shuffle": kwargs.get("shuffle", False),
        "skipped": kwargs.get("skipped", None),
        "platform": kwargs.get("platform", "android"),
    }


def _write_export(tmp_path, events, year="2020"):
    src = tmp_path / "export"
    src.mkdir(exist_ok=True)
    (src / f"Streaming_History_Audio_{year}.json").write_text(json.dumps(events))
    return str(src)


PLAY = 240_000   # ms — counts as a play (>= 30s)
SKIP = 5_000     # ms — counts as a skip (< 30s)

# A gap of 5 minutes (well within the 10-minute session window).
GAP_5M = "2020-01-01T{:02d}:{:02d}:00Z"


def _sequential_ts(start_hour: int, n: int, gap_minutes: int = 5) -> list[str]:
    """Return n ISO timestamps spaced gap_minutes apart, starting at start_hour:00."""
    result = []
    for i in range(n):
        total_min = start_hour * 60 + i * gap_minutes
        h = total_min // 60
        m = total_min % 60
        result.append(f"2020-01-01T{h:02d}:{m:02d}:00Z")
    return result


# ============================================================
# _detect_album_sessions — pure helper unit tests
# ============================================================


def test_session_exactly_at_min_plays():
    """A run of exactly ALBUM_SESSION_MIN_PLAYS = 1 session."""
    ts_list = _sequential_ts(10, ALBUM_SESSION_MIN_PLAYS)
    events = []
    for i, ts in enumerate(ts_list):
        events.append({
            "ts": ts,
            "ms_played": PLAY,
            "master_metadata_album_album_name": "Great Album",
            "master_metadata_album_artist_name": "Band",
            "reason_start": "clickrow" if i == 0 else "trackdone",
        })
    sessions = _detect_album_sessions(events)
    assert len(sessions) == 1
    assert sessions[0]["album"] == "Great Album"
    assert sessions[0]["track_count"] == ALBUM_SESSION_MIN_PLAYS


def test_session_3_plays_rejected():
    """A run of 3 consecutive plays must NOT qualify (below ALBUM_SESSION_MIN_PLAYS=4)."""
    ts_list = _sequential_ts(10, 3)
    events = [
        {"ts": ts_list[0], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "clickrow"},
        {"ts": ts_list[1], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": ts_list[2], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
    ]
    sessions = _detect_album_sessions(events)
    assert sessions == []


def test_session_reason_start_break_stops_run():
    """A non-trackdone reason_start on the 2nd play breaks the run before threshold."""
    ts_list = _sequential_ts(10, 5)
    events = [
        {"ts": ts_list[0], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "clickrow"},
        # 2nd play has clickrow (not trackdone) → breaks continuation
        {"ts": ts_list[1], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "clickrow"},
        {"ts": ts_list[2], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": ts_list[3], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": ts_list[4], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
    ]
    # Run starts at index 0: ts[0] clickrow, ts[1] clickrow → breaks after 1 play (run=1, <4)
    # Then new attempt at index 1: ts[1] clickrow, ts[2] trackdone, ts[3] trackdone, ts[4] trackdone
    # → run = [ts1, ts2, ts3, ts4] = 4 plays, qualifies
    sessions = _detect_album_sessions(events)
    assert len(sessions) == 1
    assert sessions[0]["track_count"] == 4


def test_session_album_change_breaks_run():
    """Switching albums mid-run terminates the current run."""
    ts_list = _sequential_ts(10, 6)
    events = [
        {"ts": ts_list[0], "ms_played": PLAY, "master_metadata_album_album_name": "Alb A",
         "master_metadata_album_artist_name": "Art", "reason_start": "clickrow"},
        {"ts": ts_list[1], "ms_played": PLAY, "master_metadata_album_album_name": "Alb A",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        # Switch to Album B
        {"ts": ts_list[2], "ms_played": PLAY, "master_metadata_album_album_name": "Alb B",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": ts_list[3], "ms_played": PLAY, "master_metadata_album_album_name": "Alb B",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": ts_list[4], "ms_played": PLAY, "master_metadata_album_album_name": "Alb B",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": ts_list[5], "ms_played": PLAY, "master_metadata_album_album_name": "Alb B",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
    ]
    # Alb A run = 2 plays → no session.
    # Alb B: ts[2] non-trackdone → can't start continuation run from ts[3] without ts[2].
    # Actually ts[2] can start a new attempt: ts[2] (any reason ok as first), ts[3,4,5] trackdone
    # → run = 4 → qualifies.
    sessions = _detect_album_sessions(events)
    assert len(sessions) == 1
    assert sessions[0]["album"] == "Alb B"


def test_session_gap_boundary_rejected():
    """A gap >= ALBUM_SESSION_MAX_GAP_S seconds breaks the run."""
    # 4 plays but the 2nd-to-3rd gap is exactly 10 minutes (600s) — should break.
    events = [
        {"ts": "2020-01-01T10:00:00Z", "ms_played": PLAY,
         "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "clickrow"},
        {"ts": "2020-01-01T10:05:00Z", "ms_played": PLAY,
         "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        # Gap of exactly 600s = boundary — should break (>= not <)
        {"ts": "2020-01-01T10:15:00Z", "ms_played": PLAY,
         "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": "2020-01-01T10:20:00Z", "ms_played": PLAY,
         "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
    ]
    sessions = _detect_album_sessions(events)
    assert sessions == [], "600s gap must break the run (< 600s required)"


def test_session_gap_just_inside_boundary_accepted():
    """A gap of 599s (just inside the 10-minute window) must still extend the run."""
    events = [
        {"ts": "2020-01-01T10:00:00Z", "ms_played": PLAY,
         "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "clickrow"},
        {"ts": "2020-01-01T10:04:59Z", "ms_played": PLAY,
         "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": "2020-01-01T10:09:58Z", "ms_played": PLAY,
         "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": "2020-01-01T10:14:57Z", "ms_played": PLAY,
         "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
    ]
    sessions = _detect_album_sessions(events)
    assert len(sessions) == 1
    assert sessions[0]["track_count"] == 4


def test_session_skips_not_counted():
    """Events with ms_played < PLAY_MS must not count toward a session."""
    ts_list = _sequential_ts(10, 5)
    events = [
        {"ts": ts_list[0], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "clickrow"},
        # skip — must not count
        {"ts": ts_list[1], "ms_played": SKIP, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": ts_list[2], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": ts_list[3], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
        {"ts": ts_list[4], "ms_played": PLAY, "master_metadata_album_album_name": "Alb",
         "master_metadata_album_artist_name": "Art", "reason_start": "trackdone"},
    ]
    # Only plays: ts[0], ts[2], ts[3], ts[4].
    # After filtering skips, ts[2]'s previous play is ts[0] — but ts[2] has trackdone ok.
    # However ts[0]→ts[2] gap is 10min (2 * 5min) = 600s → boundary, rejected.
    sessions = _detect_album_sessions(events)
    # The skip is removed, so the gap between ts[0] and ts[2] is 10 minutes = 600s → breaks.
    assert sessions == []


# ============================================================
# _track_season_concentration — pure helper unit tests
# ============================================================


def test_season_concentration_single_month():
    """All plays in one month → concentration = 1.0."""
    label, frac = _track_season_concentration({10: 20})
    assert label == "october"
    assert frac == 1.0


def test_season_concentration_summer():
    """Plays split across June/July/August → summer."""
    label, frac = _track_season_concentration({6: 8, 7: 7, 8: 5})
    assert label == "summer"
    assert frac >= TRACK_SEASON_CONCENTRATION


def test_season_concentration_below_threshold():
    """Plays spread evenly across all months → no season."""
    counts = {m: 1 for m in range(1, 13)}
    label, frac = _track_season_concentration(counts)
    assert label is None


def test_season_concentration_month_beats_season():
    """If one month alone meets the threshold, prefer month label over season."""
    # 80% of plays in January — winter would also be high but January should win.
    label, frac = _track_season_concentration({1: 80, 2: 10, 3: 10})
    assert label == "january"


# ============================================================
# build_history — v3 sections via synthetic export
# ============================================================


def test_v3_sections_present(tmp_path):
    """All five v3 top-level keys must appear after build_history."""
    events = [
        _event("2020-06-01T14:00:00Z", "Spoon", "T1", PLAY, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    for key in ("albums", "track_stories", "track_seasons", "per_year_tracks", "yearbook_anthems"):
        assert key in s, f"Missing v3 section: {key!r}"


def test_albums_top_albums_shape(tmp_path):
    """top_albums must include name/artist/plays/by_year/session_count/top_track/sample_uri."""
    events = [
        _event("2020-06-01T14:00:00Z", "Spoon", "T1", PLAY, reason_start="clickrow",
               album_name="Gimme Fiction"),
        _event("2020-06-01T14:05:00Z", "Spoon", "T2", PLAY, reason_start="trackdone",
               album_name="Gimme Fiction"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    albums = s["albums"]["top_albums"]
    assert len(albums) >= 1
    alb = albums[0]
    assert alb["name"] == "Gimme Fiction"
    assert alb["artist"] == "Spoon"
    assert alb["plays"] == 2
    assert "by_year" in alb
    assert "session_count" in alb
    assert "top_track" in alb
    assert "sample_uri" in alb


def test_album_session_detected_in_build(tmp_path):
    """A qualifying front-to-back session must appear in albums.album_sessions."""
    ts_list = _sequential_ts(10, ALBUM_SESSION_MIN_PLAYS)
    events = [
        _event(ts, "Spoon", f"T{i}", PLAY,
               reason_start="clickrow" if i == 0 else "trackdone",
               album_name="Gimme Fiction")
        for i, ts in enumerate(ts_list)
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    sess = s["albums"]["album_sessions"]
    assert sess["total_sessions"] >= 1
    assert any(a["album"] == "Gimme Fiction" for a in sess["session_albums"])


def test_one_track_wonder_detected(tmp_path, monkeypatch):
    """Album with one dominant track must appear in one_track_wonders."""
    monkeypatch.setattr(streaming_history, "ONE_TRACK_WONDER_HIT_MIN", 5)
    monkeypatch.setattr(streaming_history, "ONE_TRACK_WONDER_REST_MAX", 1)
    # 5 plays of "Hit Song", 1 play of "B-Side"
    events = (
        [_event(f"2020-0{m}-01T14:00:00Z", "Artist", "Hit Song", PLAY,
                uri="spotify:track:hit", album_name="Wonder Album", reason_start="clickrow")
         for m in range(1, 6)]
        + [_event("2020-06-01T14:00:00Z", "Artist", "B-Side", PLAY,
                  album_name="Wonder Album", reason_start="clickrow")]
    )
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    wonders = s["albums"]["one_track_wonders"]
    assert any(w["album"] == "Wonder Album" for w in wonders)
    w = next(w for w in wonders if w["album"] == "Wonder Album")
    assert w["hit_track"]["name"] == "Hit Song"
    assert w["hit_track"]["plays"] == 5
    assert w["rest_plays"] == 1


def test_one_track_wonder_not_triggered_when_rest_too_high(tmp_path, monkeypatch):
    """If rest-of-album plays exceed the threshold, it must NOT appear in one_track_wonders."""
    monkeypatch.setattr(streaming_history, "ONE_TRACK_WONDER_HIT_MIN", 3)
    monkeypatch.setattr(streaming_history, "ONE_TRACK_WONDER_REST_MAX", 1)
    events = (
        [_event(f"2020-0{m}-01T14:00:00Z", "Artist", "Hit", PLAY,
                album_name="NotWonder", reason_start="clickrow") for m in range(1, 4)]
        # 2 plays of other tracks — exceeds rest_max=1
        + [_event(f"2020-0{m}-02T14:00:00Z", "Artist", f"Other{m}", PLAY,
                  album_name="NotWonder", reason_start="clickrow") for m in range(1, 3)]
    )
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    wonders = s["albums"]["one_track_wonders"]
    assert not any(w["album"] == "NotWonder" for w in wonders)


def test_track_stories_shape(tmp_path):
    """track_stories.tracks must contain the required fields for each top track."""
    events = [
        _event("2020-01-01T14:00:00Z", "Spoon", "Inside Out", PLAY,
               uri="spotify:track:abc", reason_start="clickrow"),
        _event("2020-03-01T14:00:00Z", "Spoon", "Inside Out", PLAY,
               uri="spotify:track:abc", reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    tracks = s["track_stories"]["tracks"]
    assert len(tracks) >= 1
    t = tracks[0]
    assert t["artist"] == "Spoon"
    assert t["title"] == "Inside Out"
    assert t["uri"] == "spotify:track:abc"
    assert t["plays"] == 2
    assert "ms_played" in t
    assert "lifeline" in t
    assert "first_play" in t
    assert "last_play" in t
    assert "devotion_years" in t
    assert "year_span" in t
    # lifeline must be a list of [YYYY-MM, count] pairs
    for entry in t["lifeline"]:
        assert len(entry) == 2
        ym, cnt = entry
        assert len(ym) == 7 and ym[4] == "-"
        assert isinstance(cnt, int) and cnt >= 1


def test_track_stories_lifeline_correct(tmp_path):
    """Monthly lifeline counts must match synthetic plays."""
    events = [
        _event("2020-01-10T14:00:00Z", "Guster", "Satellite", PLAY, reason_start="clickrow"),
        _event("2020-01-20T14:00:00Z", "Guster", "Satellite", PLAY, reason_start="clickrow"),
        _event("2020-03-05T14:00:00Z", "Guster", "Satellite", PLAY, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    t = next(t for t in s["track_stories"]["tracks"] if t["title"] == "Satellite")
    lifeline = dict(t["lifeline"])
    assert lifeline.get("2020-01") == 2
    assert lifeline.get("2020-03") == 1
    assert "2020-02" not in lifeline


def test_track_stories_first_last_play(tmp_path):
    """first_play and last_play must be date strings in YYYY-MM-DD format."""
    events = [
        _event("2019-06-01T14:00:00Z", "Guster", "Satellite", PLAY, reason_start="clickrow"),
        _event("2021-11-15T14:00:00Z", "Guster", "Satellite", PLAY, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    t = next(t for t in s["track_stories"]["tracks"] if t["title"] == "Satellite")
    assert t["first_play"] == "2019-06-01"
    assert t["last_play"] == "2021-11-15"
    assert t["devotion_years"] == 2
    assert t["year_span"] == ["2019", "2021"]


def test_track_season_detected_in_build(tmp_path):
    """A track with highly concentrated plays must appear in track_seasons."""
    # 12 plays in October + 1 in June = 13 total → concentration = 12/13 ≈ 0.92 ≥ 0.70
    # 13 >= TRACK_SEASON_MIN_PLAYS=12, so qualifies.
    events = (
        [_event(f"2020-10-{d:02d}T14:00:00Z", "Spoon", "October Song", PLAY,
                reason_start="clickrow") for d in range(1, 13)]
        + [_event("2020-06-01T14:00:00Z", "Spoon", "October Song", PLAY,
                  reason_start="clickrow")]
    )
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    seasons = s["track_seasons"]["tracks"]
    # Should find October Song — 10/11 plays in October ≈ 91% ≥ 70%
    found = [t for t in seasons if t["title"] == "October Song"]
    assert found, "October Song should be a track season"
    assert found[0]["season_label"] == "october"
    assert found[0]["concentration"] >= 0.7


def test_track_season_not_triggered_below_min_plays(tmp_path, monkeypatch):
    """Tracks below TRACK_SEASON_MIN_PLAYS must never appear in track_seasons."""
    monkeypatch.setattr(streaming_history, "TRACK_SEASON_MIN_PLAYS", 10)
    # 9 plays all in January → concentrated but below threshold
    events = [
        _event(f"2020-01-{d:02d}T14:00:00Z", "Art", "Short Run", PLAY,
               reason_start="clickrow") for d in range(1, 10)
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    found = [t for t in s["track_seasons"]["tracks"] if t["title"] == "Short Run"]
    assert not found, "Track below TRACK_SEASON_MIN_PLAYS must not appear in track_seasons"


def test_per_year_tracks_shape(tmp_path):
    """per_year_tracks must contain top_tracks, total_hours, total_skips per year."""
    events = [
        _event("2020-01-01T14:00:00Z", "Spoon", "T1", PLAY, reason_start="clickrow"),
        _event("2020-01-02T14:00:00Z", "Spoon", "T2", PLAY, reason_start="clickrow"),
        _event("2020-01-02T14:05:00Z", "Spoon", "T3", SKIP, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    yr = s["per_year_tracks"]["by_year"].get("2020")
    assert yr is not None
    assert "top_tracks" in yr
    assert "total_hours" in yr
    assert "total_skips" in yr
    assert yr["total_skips"] >= 1
    # top track must have artist/title/uri/plays
    for t in yr["top_tracks"]:
        assert "artist" in t and "title" in t and "uri" in t and "plays" in t


def test_yearbook_anthems_one_per_year(tmp_path):
    """yearbook_anthems must emit exactly one anthem per year with data."""
    events = [
        _event("2019-06-01T14:00:00Z", "Guster", "Satellite", PLAY, reason_start="clickrow"),
        _event("2019-06-02T14:00:00Z", "Guster", "Satellite", PLAY, reason_start="clickrow"),
        _event("2019-07-01T14:00:00Z", "Guster", "Rainy Day", PLAY, reason_start="clickrow"),
        _event("2020-01-01T14:00:00Z", "Spoon", "Inside Out", PLAY, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    anthems = s["yearbook_anthems"]["anthems"]
    years = [a["year"] for a in anthems]
    assert "2019" in years
    assert "2020" in years
    # No year should appear twice
    assert len(years) == len(set(years))


def test_yearbook_anthem_picks_max_plays(tmp_path):
    """Anthem for a year = track with most plays that year."""
    events = [
        # "Runner Up" gets 1 play
        _event("2020-01-01T14:00:00Z", "Art", "Runner Up", PLAY, reason_start="clickrow"),
        # "The One" gets 3 plays in 2020
        _event("2020-02-01T14:00:00Z", "Art", "The One", PLAY, reason_start="clickrow"),
        _event("2020-02-02T14:00:00Z", "Art", "The One", PLAY, reason_start="clickrow"),
        _event("2020-02-03T14:00:00Z", "Art", "The One", PLAY, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    anthem_2020 = next(a for a in s["yearbook_anthems"]["anthems"] if a["year"] == "2020")
    assert anthem_2020["title"] == "The One"
    assert anthem_2020["plays"] == 3


def test_yearbook_anthem_tiebreak_by_concentration(tmp_path):
    """When two tracks tie on plays, the one with higher concentration wins."""
    # Track A: 3 plays all in 2020, 0 other years → concentration = 3/3 = 1.0
    # Track B: 3 plays in 2020 but also 3 plays in 2019 → concentration = 3/6 = 0.5
    events = [
        _event("2019-05-01T14:00:00Z", "Art", "Track B", PLAY, reason_start="clickrow"),
        _event("2019-05-02T14:00:00Z", "Art", "Track B", PLAY, reason_start="clickrow"),
        _event("2019-05-03T14:00:00Z", "Art", "Track B", PLAY, reason_start="clickrow"),
        _event("2020-01-01T14:00:00Z", "Art", "Track A", PLAY, reason_start="clickrow"),
        _event("2020-01-02T14:00:00Z", "Art", "Track A", PLAY, reason_start="clickrow"),
        _event("2020-01-03T14:00:00Z", "Art", "Track A", PLAY, reason_start="clickrow"),
        _event("2020-02-01T14:00:00Z", "Art", "Track B", PLAY, reason_start="clickrow"),
        _event("2020-02-02T14:00:00Z", "Art", "Track B", PLAY, reason_start="clickrow"),
        _event("2020-02-03T14:00:00Z", "Art", "Track B", PLAY, reason_start="clickrow"),
    ]
    s = streaming_history.build_history(
        _write_export(tmp_path, events, year="2019_2020"),
        str(tmp_path / "s.json"),
    )
    anthem_2020 = next(a for a in s["yearbook_anthems"]["anthems"] if a["year"] == "2020")
    # Both have 3 plays in 2020; Track A has concentration 1.0 vs Track B 0.5
    assert anthem_2020["title"] == "Track A"


# ============================================================
# Household exclusion for v3 sections
# ============================================================


def test_household_excluded_from_albums(tmp_path):
    """CoComelon plays must not appear in albums.top_albums."""
    events = [
        _event("2020-01-01T14:00:00Z", "CoComelon", "Baby Shark", PLAY,
               album_name="Kids Songs", reason_start="clickrow"),
        _event("2020-01-02T14:00:00Z", "Spoon", "Inside Out", PLAY,
               album_name="Gimme Fiction", reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    artist_names = [a["artist"] for a in s["albums"]["top_albums"]]
    assert "CoComelon" not in artist_names
    assert "Spoon" in artist_names


def test_household_excluded_from_track_stories(tmp_path):
    """CoComelon tracks must not appear in track_stories."""
    events = [
        _event("2020-01-01T14:00:00Z", "CoComelon", "Baby Shark", PLAY,
               reason_start="clickrow"),
        _event("2020-01-02T14:00:00Z", "Spoon", "Inside Out", PLAY,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    artists = [t["artist"] for t in s["track_stories"]["tracks"]]
    assert "CoComelon" not in artists
    assert "Spoon" in artists


def test_household_excluded_from_yearbook_anthems(tmp_path):
    """CoComelon must not appear as a yearbook anthem."""
    events = [
        _event("2020-01-01T14:00:00Z", "CoComelon", "Baby Shark", PLAY,
               reason_start="clickrow"),
        _event("2020-01-02T14:00:00Z", "CoComelon", "Baby Shark", PLAY,
               reason_start="clickrow"),
        _event("2020-01-03T14:00:00Z", "Spoon", "Inside Out", PLAY,
               reason_start="clickrow"),
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    for anthem in s["yearbook_anthems"]["anthems"]:
        assert anthem["artist"] != "CoComelon"


def test_household_excluded_from_album_sessions(tmp_path):
    """CoComelon sessions must not appear in album_sessions."""
    ts_list = _sequential_ts(10, ALBUM_SESSION_MIN_PLAYS)
    events = [
        _event(ts, "CoComelon", f"Track{i}", PLAY,
               reason_start="clickrow" if i == 0 else "trackdone",
               album_name="Kids Album")
        for i, ts in enumerate(ts_list)
    ]
    s = streaming_history.build_history(_write_export(tmp_path, events), str(tmp_path / "s.json"))
    # No sessions from CoComelon
    for a in s["albums"]["album_sessions"].get("session_albums", []):
        assert a["artist"] != "CoComelon"
    assert s["albums"]["album_sessions"]["total_sessions"] == 0
