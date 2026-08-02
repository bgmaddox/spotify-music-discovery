"""Regression: the newest-taste-dump finders must ignore data/taste_timeline.json.

`taste_timeline.json` is the viz build's output, not a taste dump — it has none of a
dump's keys. It matches the bare `taste_*.json` glob and, because `timeline-build`
rewrites it, it is almost always the newest match. That silently emptied
`cli.py taste-snapshot`'s `known_artists` (332 real artists → 0), which is the set every
discovery recipe filters candidates against. `build_timeline_data` and `discovery_log`
already guarded against it; `cli` and `mcp_server` did not.
"""

import os

import pytest

import build_timeline_data
import cli
import taste_profile


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(taste_profile, "DATA_DIR", str(tmp_path))
    return tmp_path


def _touch(path, mtime):
    path.write_text("{}")
    os.utime(path, (mtime, mtime))


def test_ignores_timeline_even_when_newest(data_dir):
    _touch(data_dir / "taste_20260720T025155Z.json", 1_000)
    _touch(data_dir / "taste_timeline.json", 9_999)  # newer, but not a dump
    assert os.path.basename(cli._latest_taste_dump()) == "taste_20260720T025155Z.json"


def test_picks_newest_real_dump(data_dir):
    _touch(data_dir / "taste_20260623T050024Z.json", 1_000)
    _touch(data_dir / "taste_20260720T025155Z.json", 2_000)
    _touch(data_dir / "taste_timeline.json", 9_999)
    assert os.path.basename(cli._latest_taste_dump()) == "taste_20260720T025155Z.json"


def test_none_when_only_timeline_present(data_dir):
    _touch(data_dir / "taste_timeline.json", 9_999)
    assert cli._latest_taste_dump() is None


def test_matches_build_timeline_data_behavior(data_dir):
    """The two implementations must agree — they select the same file."""
    _touch(data_dir / "taste_20260720T025155Z.json", 1_000)
    _touch(data_dir / "taste_timeline.json", 9_999)
    assert cli._latest_taste_dump() == build_timeline_data._latest_taste_dump()


def test_mcp_server_taste_snapshot_ignores_timeline(data_dir, monkeypatch):
    import json

    import mcp_server

    (data_dir / "taste_20260720T025155Z.json").write_text(
        json.dumps({"generated_at": "real-dump", "top_artists": {"long_term": []}})
    )
    _touch(data_dir / "taste_timeline.json", 9_999)
    assert mcp_server.taste_snapshot()["generated_at"] == "real-dump"
