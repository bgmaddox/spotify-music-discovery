"""GDPR extended-history aggregation: play/skip threshold, per-year rollups,
forgotten-favorites windowing, and the lean snapshot shape.

Runs against a synthetic export dir — never the real (gitignored, personal) one.
"""

import json

import streaming_history


def _event(ts, artist, title, ms, uri="spotify:track:x"):
    return {
        "ts": ts,
        "ms_played": ms,
        "master_metadata_track_name": title,
        "master_metadata_album_artist_name": artist,
        "spotify_track_uri": uri,
    }


def _write_export(tmp_path, events, year="2020"):
    src = tmp_path / "export"
    src.mkdir()
    (src / f"Streaming_History_Audio_{year}.json").write_text(json.dumps(events))
    return str(src)


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
