"""Apple Media Services export parsing: artist-title splitting, title-join
normalization, timestamp normalization, ms clamping, dedup, and the schema-
parity regression guards (shuffle/reason_start/spotify_track_uri stay None).

Runs against small inline CSV fixtures written to tmp_path — never the real
(gitignored, personal) export.
"""

import csv
import json
import os

import apple_history
import streaming_history


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(row)


PLAY_ACTIVITY_HEADER = [
    "Event Type", "Song Name", "Album Name", "Event Start Timestamp",
    "Event End Timestamp", "Play Duration Milliseconds",
    "Media Duration In Milliseconds", "End Reason Type", "Feature Name",
    "Media Type", "Item Type", "Client Platform", "Device Type", "Source Type",
    "Client Device Name",
]


def _row(**kw):
    """Build one Play Activity row dict with sane defaults, override via kwargs."""
    base = {
        "Event Type": "PLAY_END",
        "Song Name": "Doses & Mimosas",
        "Album Name": "Year of the Caprese",
        "Event Start Timestamp": "2016-07-01T12:00:00.000Z",
        "Event End Timestamp": "2016-07-01T12:03:00.000Z",
        "Play Duration Milliseconds": "180000",
        "Media Duration In Milliseconds": "180000",
        "End Reason Type": "NATURAL_END_OF_TRACK",
        "Feature Name": "for_you",
        "Media Type": "AUDIO",
        "Item Type": "ITUNES_STORE_CONTENT",
        "Client Platform": "FUSE",
        "Device Type": "",
        "Source Type": "ORIGINATING_DEVICE",
        "Client Device Name":
            "itunesstored/1.0 iOS/10.3.2 model/iPhone8,1 hwp/s8000 build/14F89",
    }
    base.update(kw)
    return [base[h] for h in PLAY_ACTIVITY_HEADER]


def _build(tmp_path, rows, daily_rows=None, track_rows=None, fav_rows=None):
    """Write a minimal Apple export dir and run build_apple_history against it."""
    src = tmp_path / "apple"
    src.mkdir(exist_ok=True)

    _write_csv(src / apple_history.PLAY_ACTIVITY_FILE, PLAY_ACTIVITY_HEADER, rows)

    daily_header = ["Track Description"]
    _write_csv(
        src / apple_history.DAILY_TRACKS_FILE,
        daily_header,
        [[d] for d in (daily_rows or [])],
    )

    track_header = ["Track Name"]
    _write_csv(
        src / apple_history.TRACK_PLAY_HISTORY_FILE,
        track_header,
        [[t] for t in (track_rows or [])],
    )

    if fav_rows is not None:
        fav_header = ["Favorite Type", "Item Reference", "Item Description",
                       "Last Modified", "Preference"]
        _write_csv(src / apple_history.FAVORITES_FILE, fav_header, fav_rows)

    out_path = tmp_path / "apple_events.json"
    stats = apple_history.build_apple_history(str(src), str(out_path))
    return stats, str(out_path)


# ------------------------------------------------------------------ splitting


def test_split_artist_title_basic():
    assert apple_history._split_artist_title("Cherub - Doses & Mimosas") == (
        "Cherub",
        "Doses & Mimosas",
    )


def test_split_artist_title_first_occurrence_with_title_containing_dash():
    # Title itself contains " - " (a live-version suffix) — first-split still
    # correctly separates artist from the (longer) title remainder.
    raw = "Jimmy Buffett - Why Don't We Get Drunk and Screw (Live - 1978 Version)"
    artist, title = apple_history._split_artist_title(raw)
    assert artist == "Jimmy Buffett"
    assert title == "Why Don't We Get Drunk and Screw (Live - 1978 Version)"


def test_split_artist_title_artist_containing_dash():
    # An artist name with a hyphenated collab-style prefix before the real title.
    raw = "Ike & Tina Turner - River Deep - Mountain High"
    artist, title = apple_history._split_artist_title(raw)
    assert artist == "Ike & Tina Turner"
    assert title == "River Deep - Mountain High"


def test_split_artist_title_no_separator_returns_none():
    assert apple_history._split_artist_title("No Separator Here") is None


# ------------------------------------------------------------------ title normalization


def test_norm_title_case_and_whitespace():
    assert apple_history._norm_title("  Doses  &   Mimosas ") == "doses & mimosas"
    assert apple_history._norm_title("DOSES & MIMOSAS") == "doses & mimosas"


def test_join_succeeds_via_normalized_title(tmp_path):
    rows = [_row(**{"Song Name": "  Doses  &   Mimosas "})]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    assert stats["events_emitted"] == 1
    assert stats["dropped"]["artist_unresolved"] == 0
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events[0]["master_metadata_album_artist_name"] == "Cherub"


# ------------------------------------------------------------------ artist resolution / drop


def test_unresolved_artist_drops_event_and_counts_in_stats(tmp_path):
    rows = [_row(**{"Song Name": "Totally Unknown Song"})]
    stats, out_path = _build(tmp_path, rows)  # no daily/track rows to resolve against
    assert stats["events_emitted"] == 0
    assert stats["dropped"]["artist_unresolved"] == 1
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events == []


# ------------------------------------------------------------------ timestamps


def test_timestamp_normalization_drops_fractional_seconds(tmp_path):
    rows = [_row(**{"Event Start Timestamp": "2018-08-25T06:11:11.347Z"})]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events[0]["ts"] == "2018-08-25T06:11:11Z"


def test_timestamp_falls_back_to_event_end(tmp_path):
    rows = [_row(**{
        "Event Start Timestamp": "",
        "Event End Timestamp": "2016-07-01T12:03:45.500Z",
    })]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events[0]["ts"] == "2016-07-01T12:03:45Z"


# ------------------------------------------------------------------ skipped


def test_skipped_true_only_for_track_skipped_forwards(tmp_path):
    rows = [
        _row(**{"End Reason Type": "TRACK_SKIPPED_FORWARDS",
                "Event Start Timestamp": "2016-07-01T12:00:00Z"}),
        _row(**{"End Reason Type": "NATURAL_END_OF_TRACK",
                "Event Start Timestamp": "2016-07-01T13:00:00Z"}),
        _row(**{"End Reason Type": "TRACK_SKIPPED_BACKWARDS",
                "Event Start Timestamp": "2016-07-01T14:00:00Z"}),
    ]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    with open(out_path) as f:
        events = json.load(f)["events"]
    skipped_flags = {e["ts"]: e["skipped"] for e in events}
    assert skipped_flags["2016-07-01T12:00:00Z"] is True
    assert skipped_flags["2016-07-01T13:00:00Z"] is False
    assert skipped_flags["2016-07-01T14:00:00Z"] is False


# ------------------------------------------------------------------ ms_played clamping


def test_negative_ms_played_clamped_to_zero(tmp_path):
    rows = [_row(**{"Play Duration Milliseconds": "-5000"})]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    assert stats["ms_clamped_negative"] == 1
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events[0]["ms_played"] == 0


def test_runaway_ms_played_clamped_to_media_duration(tmp_path):
    rows = [_row(**{
        "Play Duration Milliseconds": "9000000",
        "Media Duration In Milliseconds": "200000",
    })]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    assert stats["ms_clamped_runaway"] == 1
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events[0]["ms_played"] == 200000


def test_ms_played_not_clamped_when_within_2x(tmp_path):
    rows = [_row(**{
        "Play Duration Milliseconds": "300000",
        "Media Duration In Milliseconds": "180000",
    })]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    assert stats["ms_clamped_runaway"] == 0
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events[0]["ms_played"] == 300000


# ------------------------------------------------------------------ dedup


def test_dedup_identical_ts_title_ms(tmp_path):
    rows = [
        _row(**{"Event Start Timestamp": "2016-07-01T12:00:00Z"}),
        _row(**{"Event Start Timestamp": "2016-07-01T12:00:00Z"}),  # exact duplicate
    ]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    assert stats["events_emitted"] == 1
    assert stats["dropped"]["duplicate"] == 1


# ------------------------------------------------------------------ schema-parity regression guards


def test_shuffle_reason_start_uri_are_none(tmp_path):
    rows = [_row()]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    with open(out_path) as f:
        events = json.load(f)["events"]
    e = events[0]
    assert e["shuffle"] is None
    assert e["reason_start"] is None
    assert e["spotify_track_uri"] is None
    assert e["service"] == "apple"


# ------------------------------------------------------------------ row filtering


def test_lyric_display_dropped(tmp_path):
    rows = [_row(**{"Event Type": "LYRIC_DISPLAY"})]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    assert stats["events_emitted"] == 0
    assert stats["dropped"]["event_type"] == 1


def test_blank_event_type_is_kept(tmp_path):
    rows = [_row(**{"Event Type": ""})]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    assert stats["events_emitted"] == 1


def test_video_media_type_dropped(tmp_path):
    rows = [_row(**{"Media Type": "VIDEO"})]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    assert stats["events_emitted"] == 0
    assert stats["dropped"]["non_music_media_type"] == 1


def test_radio_item_type_dropped(tmp_path):
    rows = [_row(**{"Song Name": "NPR News and Culture", "Item Type": "STREAM"})]
    stats, out_path = _build(tmp_path, rows)
    assert stats["events_emitted"] == 0
    assert stats["dropped"]["non_music_item_type"] == 1


def test_no_song_name_dropped(tmp_path):
    rows = [_row(**{"Song Name": ""})]
    stats, out_path = _build(tmp_path, rows)
    assert stats["events_emitted"] == 0
    assert stats["dropped"]["no_song_name"] == 1


# ------------------------------------------------------------------ platform bucketing


def test_platform_from_device_name_ios():
    raw = "itunesstored/1.0 iOS/10.3.2 model/iPhone8,1 hwp/s8000 build/14F89 (6; dt:120)"
    assert apple_history._platform_from_device_name(raw) == "iOS"


def test_platform_from_device_name_ipad_folds_into_ios():
    raw = "itunesstored/1.0 iOS/12.1 model/iPad6,11 hwp/t8010 build/16B92"
    assert apple_history._platform_from_device_name(raw) == "iOS"


def test_platform_from_device_name_macintosh():
    raw = "iTunes/12.8 (Macintosh; OS X 10.13.6) AppleWebKit/605.3.8 (dt:1)"
    assert apple_history._platform_from_device_name(raw) == "Macintosh"


def test_platform_from_device_name_windows():
    raw = "iTunes/12.9.0.167 (Windows; Microsoft Windows 10 x64 Business Edition)"
    assert apple_history._platform_from_device_name(raw) == "Windows"


def test_platform_from_device_name_android():
    raw = "AppleMusic/2.1 Android/9 model/Pixel3"
    assert apple_history._platform_from_device_name(raw) == "Android"


def test_platform_from_device_name_empty_and_unrecognized_are_unknown():
    assert apple_history._platform_from_device_name("") == "unknown"
    assert apple_history._platform_from_device_name(None) == "unknown"
    assert apple_history._platform_from_device_name("SomeWeirdClient/3.0") == "unknown"


def test_platform_tokens_bucket_correctly_via_normalize_platform():
    """Round-trip check: every non-'unknown' token this module can emit must
    hit the intended bucket in streaming_history._normalize_platform(),
    without any change to _PLATFORM_RULES."""
    assert streaming_history._normalize_platform("iOS") == "mobile"
    assert streaming_history._normalize_platform("Macintosh") == "desktop"
    assert streaming_history._normalize_platform("Windows") == "desktop"
    assert streaming_history._normalize_platform("Android") == "mobile"


def test_event_platform_field_uses_clean_token_not_raw_ua(tmp_path):
    rows = [_row(**{"Client Device Name":
                    "itunesstored/1.0 iOS/10.3.2 model/iPhone8,1 hwp/s8000 build/14F89"})]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events[0]["platform"] == "iOS"
    assert stats["platforms"] == {"iOS": 1}


# ------------------------------------------------------------------ manual overrides


def _write_overrides(tmp_path, mapping):
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    return str(path)


def test_override_resolves_when_join_misses(tmp_path, monkeypatch):
    overrides_path = _write_overrides(tmp_path, {"Doses & Mimosas": "Cherub"})
    monkeypatch.setattr(apple_history, "OVERRIDES_PATH", overrides_path)

    rows = [_row()]  # no daily/track rows -> the real join can't resolve this title
    stats, out_path = _build(tmp_path, rows)

    assert stats["events_emitted"] == 1
    assert stats["dropped"]["artist_unresolved"] == 0
    assert stats["artist_resolved_via_override"] == 1
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events[0]["master_metadata_album_artist_name"] == "Cherub"


def test_override_never_shadows_a_real_join_hit(tmp_path, monkeypatch):
    # Override deliberately disagrees with the real join, to prove the join wins.
    overrides_path = _write_overrides(tmp_path, {"Doses & Mimosas": "Wrong Artist"})
    monkeypatch.setattr(apple_history, "OVERRIDES_PATH", overrides_path)

    rows = [_row()]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])

    assert stats["artist_resolved_via_override"] == 0
    with open(out_path) as f:
        events = json.load(f)["events"]
    assert events[0]["master_metadata_album_artist_name"] == "Cherub"


def test_missing_overrides_file_is_non_fatal(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(apple_history, "OVERRIDES_PATH", str(tmp_path / "nope.json"))
    rows = [_row()]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    assert stats["events_emitted"] == 1  # still works, just no overrides applied
    assert stats["artist_resolved_via_override"] == 0
    err = capsys.readouterr().err
    assert "not found" in err


# ------------------------------------------------------------------ unresolved report


def test_unresolved_report_lists_song_details(tmp_path, monkeypatch):
    monkeypatch.setattr(apple_history, "OVERRIDES_PATH", str(tmp_path / "nope.json"))
    rows = [
        _row(**{
            "Song Name": "Some Mystery Song",
            "Album Name": "Mystery Album",
            "Event Start Timestamp": "2016-01-01T10:00:00Z",
            "Play Duration Milliseconds": "60000",
        }),
        _row(**{
            "Song Name": "Some Mystery Song",
            "Album Name": "Mystery Album",
            "Event Start Timestamp": "2017-06-01T10:00:00Z",
            "Play Duration Milliseconds": "120000",
        }),
    ]
    stats, out_path = _build(tmp_path, rows)  # no daily/track rows -> unresolved
    assert stats["dropped"]["artist_unresolved"] == 2

    report_path = tmp_path / "apple_unresolved.md"
    n = apple_history.write_unresolved_report(out_path, str(report_path))
    assert n == 1
    text = report_path.read_text(encoding="utf-8")
    assert "Some Mystery Song" in text
    assert "Mystery Album" in text
    assert "2016" in text and "2017" in text
    assert "apple_artist_overrides.json" in text  # points the user at the fix


# ------------------------------------------------------------------ favorites


def test_apple_favorites_parses_artist_title(tmp_path):
    src = tmp_path / "apple"
    src.mkdir(exist_ok=True)
    _write_csv(
        src / apple_history.PLAY_ACTIVITY_FILE, PLAY_ACTIVITY_HEADER, []
    )
    fav_header = ["Favorite Type", "Item Reference", "Item Description",
                  "Last Modified", "Preference"]
    _write_csv(
        src / apple_history.FAVORITES_FILE,
        fav_header,
        [["Song", "944357683", "Tobias Jesso Jr. - How Could You Babe",
          "2017-06-20T19:57:21.646Z", "LIKE"]],
    )
    favs = apple_history.apple_favorites(str(src))
    assert favs == [{
        "artist": "Tobias Jesso Jr.",
        "title": "How Could You Babe",
        "liked_at": "2017-06-20T19:57:21.646Z",
        "preference": "LIKE",
    }]


# ------------------------------------------------------------------ iter_apple_events


def test_iter_apple_events_yields_nothing_when_file_absent(tmp_path):
    missing_path = str(tmp_path / "does_not_exist.json")
    assert list(apple_history.iter_apple_events(missing_path)) == []


def test_iter_apple_events_yields_events_from_built_file(tmp_path):
    rows = [_row()]
    stats, out_path = _build(tmp_path, rows, daily_rows=["Cherub - Doses & Mimosas"])
    events = list(apple_history.iter_apple_events(out_path))
    assert len(events) == 1
    assert events[0]["master_metadata_album_artist_name"] == "Cherub"
