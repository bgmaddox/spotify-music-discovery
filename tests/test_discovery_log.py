"""Discovery ledger: append, dedup-set extraction, and recent-tail reads.

Uses a tmp LOG_PATH so it never touches the real data/ ledger.
"""

import discovery_log


def _use_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery_log, "LOG_PATH", str(tmp_path / "discovery_log.jsonl"))


def test_append_stamps_and_loads(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    n = discovery_log.append(
        [
            {"artist": "Tyler Childers", "title": "Feathered Indians"},
            {"artist": "Colter Wall"},
        ],
        recipe="6",
        playlist="http://x",
    )
    assert n == 2
    rows = discovery_log.load()
    assert len(rows) == 2
    assert rows[0]["recipe"] == "6"
    assert rows[0]["playlist"] == "http://x"
    assert "ts" in rows[0]


def test_append_skips_records_without_artist(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    assert discovery_log.append([{"title": "no artist"}, {"artist": "Real"}]) == 1
    assert discovery_log.surfaced_artists() == {"real"}


def test_record_level_keys_win(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    discovery_log.append([{"artist": "A", "recipe": "own"}], recipe="shared")
    assert discovery_log.load()[0]["recipe"] == "own"


def test_surfaced_artists_lowercased_set(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    discovery_log.append([{"artist": "Tyler Childers"}, {"artist": "Colter Wall"}])
    assert discovery_log.surfaced_artists() == {"tyler childers", "colter wall"}


def test_surfaced_uris(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    discovery_log.append([{"artist": "A", "uri": "spotify:track:1"}, {"artist": "B"}])
    assert discovery_log.surfaced_uris() == {"spotify:track:1"}


def test_recent_returns_tail(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    discovery_log.append([{"artist": f"A{i}"} for i in range(5)])
    assert [r["artist"] for r in discovery_log.recent(2)] == ["A3", "A4"]


def test_load_missing_file_is_empty(tmp_path, monkeypatch):
    _use_tmp(tmp_path, monkeypatch)
    assert discovery_log.load() == []
    assert discovery_log.surfaced_artists() == set()
