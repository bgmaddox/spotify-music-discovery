"""Phase 2 enrichment: batching math, URI collection, cache hit/miss, output shape.

No network, no auth — the Spotify client is replaced with a FakeSp that records calls
and returns canned payloads. All file I/O uses tmp_path (pytest fixture).
"""

import base64
import json
import os

import enrich_meta


# ──────────────────────────────────────────────────────────────────────────────
# Helpers / fake data
# ──────────────────────────────────────────────────────────────────────────────

def _make_track_obj(tid: str, album_id: str = "alb1", popularity: int = 50) -> dict:
    """Minimal Spotify /tracks item."""
    return {
        "id": tid,
        "duration_ms": 200_000,
        "popularity": popularity,
        "album": {"id": album_id, "name": f"Album-{album_id}"},
        "artists": [{"id": f"art_{tid}", "name": f"Artist-{tid}"}],
    }


def _make_album_obj(aid: str, total_tracks: int = 10) -> dict:
    """Minimal Spotify /albums item — includes images at 640/300/64 widths."""
    return {
        "id": aid,
        "name": f"Album-{aid}",
        "artists": [{"name": f"ArtistOf-{aid}"}],
        "total_tracks": total_tracks,
        "release_date": "2020-06-15",
        "images": [
            {"url": f"https://cdn/{aid}/640.jpg", "width": 640, "height": 640},
            {"url": f"https://cdn/{aid}/300.jpg", "width": 300, "height": 300},
            {"url": f"https://cdn/{aid}/64.jpg",  "width": 64,  "height": 64},
        ],
    }


class FakeSp:
    """Minimal fake Spotify client — no auth, no network."""

    def __init__(self, track_objs=(), album_objs=(), top_track_name="Hit"):
        # id → object
        self._tracks = {t["id"]: t for t in track_objs}
        self._albums = {a["id"]: a for a in album_objs}
        self._top_track_name = top_track_name

        # Call recording
        self.track_batches: list[list[str]] = []
        self.album_batches: list[list[str]] = []
        self.artist_calls: list[str] = []

    def tracks(self, ids: list[str]) -> dict:
        self.track_batches.append(list(ids))
        return {"tracks": [self._tracks.get(i) for i in ids]}

    def albums(self, ids: list[str]) -> dict:
        self.album_batches.append(list(ids))
        return {"albums": [self._albums.get(i) for i in ids]}

    def artist_top_tracks(self, artist_id: str, country: str = "US") -> dict:
        self.artist_calls.append(artist_id)
        return {"tracks": [{"name": self._top_track_name, "popularity": 75}]}


def _write_history(tmp_path, summary: dict) -> str:
    p = tmp_path / "history_summary.json"
    p.write_text(json.dumps(summary))
    return str(p)


def _minimal_summary(uris: list[str]) -> dict:
    """Build a minimal history_summary.json that references the given URIs."""
    tracks = [{"artist": "A", "title": "T", "uri": u, "plays": 1, "ms_played": 1000}
              for u in uris]
    return {
        "track_stories": {"note": "", "tracks": tracks},
        "albums": {"top_albums": [], "one_track_wonders": [], "album_sessions": {}},
        "per_year_tracks": {"note": "", "by_year": {}},
        "yearbook_anthems": {"note": "", "anthems": []},
    }


# ──────────────────────────────────────────────────────────────────────────────
# URI collection tests
# ──────────────────────────────────────────────────────────────────────────────

def test_collect_deduplicates_uris():
    """Same URI appearing in multiple sections should be counted once."""
    uri = "spotify:track:abc123"
    summary = {
        "track_stories": {"tracks": [{"uri": uri, "artist": "A", "title": "T", "plays": 1, "ms_played": 1}]},
        "albums": {
            "top_albums": [{"top_track": {"name": "T", "plays": 5, "uri": uri}, "sample_uri": uri}],
            "one_track_wonders": [{"hit_track": {"name": "T", "plays": 5, "uri": uri}}],
        },
        "per_year_tracks": {"by_year": {"2020": {"top_tracks": [{"uri": uri, "artist": "A", "title": "T", "plays": 1}]}}},
        "yearbook_anthems": {"anthems": [{"year": "2020", "uri": uri}]},
    }
    uris = enrich_meta.collect_track_uris(summary)
    assert uris == [uri]


def test_collect_skips_none_uris():
    summary = {
        "track_stories": {"tracks": [{"uri": None}, {"uri": "spotify:track:x"}]},
        "albums": {"top_albums": [], "one_track_wonders": []},
        "per_year_tracks": {"by_year": {}},
        "yearbook_anthems": {"anthems": []},
    }
    uris = enrich_meta.collect_track_uris(summary)
    assert uris == ["spotify:track:x"]


def test_collect_gathers_all_sections():
    """Each of the 5 sections contributes distinct URIs."""
    summary = {
        "track_stories": {"tracks": [{"uri": "spotify:track:t1"}]},
        "albums": {
            "top_albums": [{"top_track": {"uri": "spotify:track:t2"}, "sample_uri": "spotify:track:t3"}],
            "one_track_wonders": [{"hit_track": {"uri": "spotify:track:t4"}}],
        },
        "per_year_tracks": {"by_year": {"2020": {"top_tracks": [{"uri": "spotify:track:t5"}]}}},
        "yearbook_anthems": {"anthems": [{"year": "2020", "uri": "spotify:track:t6"}]},
    }
    uris = enrich_meta.collect_track_uris(summary)
    assert set(uris) == {f"spotify:track:t{i}" for i in range(1, 7)}


# ──────────────────────────────────────────────────────────────────────────────
# Batching / chunking math
# ──────────────────────────────────────────────────────────────────────────────

def test_track_batching_respects_50_limit(tmp_path, monkeypatch):
    """55 tracks → 2 API calls (50 + 5), not 55 or 1."""
    monkeypatch.setattr(enrich_meta, "CACHE_DIR", str(tmp_path / "cache"))

    uris = [f"spotify:track:id{i:03d}" for i in range(55)]
    ids = [f"id{i:03d}" for i in range(55)]
    track_objs = [_make_track_obj(tid) for tid in ids]
    sp = FakeSp(track_objs=track_objs)

    enrich_meta.fetch_tracks(sp, uris)

    assert len(sp.track_batches) == 2
    assert len(sp.track_batches[0]) == 50
    assert len(sp.track_batches[1]) == 5


def test_album_batching_respects_20_limit(tmp_path, monkeypatch):
    """25 album ids → 2 API calls (20 + 5)."""
    monkeypatch.setattr(enrich_meta, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(enrich_meta, "THUMB_CAP", 0)  # skip thumb downloads

    aids = [f"alb{i:03d}" for i in range(25)]
    album_objs = [_make_album_obj(aid) for aid in aids]
    sp = FakeSp(album_objs=album_objs)

    enrich_meta.fetch_albums(sp, aids)

    assert len(sp.album_batches) == 2
    assert len(sp.album_batches[0]) == 20
    assert len(sp.album_batches[1]) == 5


# ──────────────────────────────────────────────────────────────────────────────
# Cache hit / miss
# ──────────────────────────────────────────────────────────────────────────────

def test_track_cache_hit_skips_api(tmp_path, monkeypatch):
    """A track already in cache should not trigger an API call."""
    monkeypatch.setattr(enrich_meta, "CACHE_DIR", str(tmp_path / "cache"))

    uri = "spotify:track:cached1"
    tid = "cached1"
    rec = {"duration_ms": 180_000, "popularity": 60, "album_id": "a1",
           "album_name": "Alb", "artist_ids": ["art1"], "artist_names": ["Art"]}
    enrich_meta._cache_write("track", tid, rec)

    sp = FakeSp()
    result = enrich_meta.fetch_tracks(sp, [uri])

    assert sp.track_batches == []       # no API call
    assert result[uri]["popularity"] == 60


def test_track_cache_miss_hits_api(tmp_path, monkeypatch):
    """A track NOT in cache should trigger an API call and then cache the result."""
    monkeypatch.setattr(enrich_meta, "CACHE_DIR", str(tmp_path / "cache"))

    uri = "spotify:track:fresh1"
    tid = "fresh1"
    sp = FakeSp(track_objs=[_make_track_obj(tid, popularity=42)])

    result = enrich_meta.fetch_tracks(sp, [uri])

    assert len(sp.track_batches) == 1
    assert result[uri]["popularity"] == 42
    # Second call should be a cache hit
    sp2 = FakeSp()
    result2 = enrich_meta.fetch_tracks(sp2, [uri])
    assert sp2.track_batches == []
    assert result2[uri]["popularity"] == 42


def test_album_cache_hit_skips_api(tmp_path, monkeypatch):
    monkeypatch.setattr(enrich_meta, "CACHE_DIR", str(tmp_path / "cache"))

    aid = "alb_cached"
    rec = {"name": "CachedAlb", "artist": "X", "total_tracks": 8,
           "release_year": 2018, "thumb_b64": None, "image_url": "http://cdn/x.jpg"}
    enrich_meta._cache_write("album", aid, rec)

    sp = FakeSp()
    result = enrich_meta.fetch_albums(sp, [aid])

    assert sp.album_batches == []
    assert result[aid]["total_tracks"] == 8


# ──────────────────────────────────────────────────────────────────────────────
# Thumb cap
# ──────────────────────────────────────────────────────────────────────────────

def test_thumb_cap_limits_downloads(tmp_path, monkeypatch):
    """With THUMB_CAP=2, only 2 thumbs downloaded even if 5 albums fetched."""
    monkeypatch.setattr(enrich_meta, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(enrich_meta, "THUMB_CAP", 2)

    # Patch _download_thumb_b64 to return a fake b64 without network
    monkeypatch.setattr(enrich_meta, "_download_thumb_b64",
                        lambda url: base64.b64encode(b"fake").decode() if url else None)

    aids = [f"alb{i}" for i in range(5)]
    album_objs = [_make_album_obj(aid) for aid in aids]
    sp = FakeSp(album_objs=album_objs)

    result = enrich_meta.fetch_albums(sp, aids)

    thumbs = [v["thumb_b64"] for v in result.values() if v.get("thumb_b64")]
    assert len(thumbs) == 2


def test_thumb_cap_respected_via_thumb_count_param(tmp_path, monkeypatch):
    """thumb_count param lets callers pass in pre-existing thumb count.

    fetch_albums starts counting from `thumb_count`; when that already equals
    THUMB_CAP, no new thumbnails are downloaded even for un-cached albums.
    """
    monkeypatch.setattr(enrich_meta, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(enrich_meta, "THUMB_CAP", 2)
    monkeypatch.setattr(enrich_meta, "_download_thumb_b64",
                        lambda url: base64.b64encode(b"img").decode() if url else None)

    aids = ["alb_new1", "alb_new2", "alb_new3"]
    album_objs = [_make_album_obj(a) for a in aids]
    sp = FakeSp(album_objs=album_objs)

    # Tell fetch_albums that 1 thumb already exists → cap has 1 slot remaining
    result = enrich_meta.fetch_albums(sp, aids, thumb_count=1)
    new_thumbs = [v["thumb_b64"] for v in result.values() if v.get("thumb_b64")]
    assert len(new_thumbs) == 1  # only 1 new download (cap 2 - existing 1)


# ──────────────────────────────────────────────────────────────────────────────
# Output shape (full pipeline with mocked client)
# ──────────────────────────────────────────────────────────────────────────────

def test_enrich_output_shape(tmp_path, monkeypatch):
    """End-to-end: enrich() writes a valid track_album_meta.json with correct shape."""
    monkeypatch.setattr(enrich_meta, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(enrich_meta, "THUMB_CAP", 1)
    monkeypatch.setattr(enrich_meta, "_download_thumb_b64",
                        lambda url: base64.b64encode(b"px").decode() if url else None)

    uris = ["spotify:track:t1", "spotify:track:t2"]
    summary = _minimal_summary(uris)
    hist = _write_history(tmp_path, summary)
    out = str(tmp_path / "meta.json")

    sp = FakeSp(
        track_objs=[_make_track_obj("t1", album_id="a1"), _make_track_obj("t2", album_id="a2")],
        album_objs=[_make_album_obj("a1"), _make_album_obj("a2")],
        top_track_name="Banger",
    )

    path = enrich_meta.enrich(history_path=hist, output_path=out, sp=sp)

    assert path == out
    with open(out) as f:
        data = json.load(f)

    # meta block
    assert "fetched_at" in data["meta"]
    assert data["meta"]["tracks"] == 2
    assert data["meta"]["albums"] == 2
    assert data["meta"]["artists"] == 2

    # tracks section
    assert "spotify:track:t1" in data["tracks"]
    tr = data["tracks"]["spotify:track:t1"]
    assert tr["duration_ms"] == 200_000
    assert tr["popularity"] == 50
    assert tr["album_id"] == "a1"
    assert tr["artist_names"] == ["Artist-t1"]

    # albums section
    assert "a1" in data["albums"]
    al = data["albums"]["a1"]
    assert al["total_tracks"] == 10
    assert al["release_year"] == 2020
    assert "image_url" in al
    # thumb_b64 present for at least 1 album (cap=1)
    thumb_count = sum(1 for v in data["albums"].values() if v.get("thumb_b64"))
    assert thumb_count == 1

    # artists section
    assert len(data["artists"]) == 2
    art = list(data["artists"].values())[0]
    assert art["max_popularity"] == 75
    assert art["top_track_name"] == "Banger"


def test_enrich_missing_history_exits_cleanly(tmp_path, monkeypatch):
    """enrich() raises FileNotFoundError when history_summary.json is absent."""
    import pytest
    with pytest.raises(FileNotFoundError, match="History summary not found"):
        enrich_meta.enrich(
            history_path=str(tmp_path / "nonexistent.json"),
            output_path=str(tmp_path / "out.json"),
        )


# ──────────────────────────────────────────────────────────────────────────────
# id_from_uri helper
# ──────────────────────────────────────────────────────────────────────────────

def test_id_from_uri_valid():
    assert enrich_meta._id_from_uri("spotify:track:abc123") == "abc123"


def test_id_from_uri_invalid():
    assert enrich_meta._id_from_uri(None) is None
    assert enrich_meta._id_from_uri("") is None
    assert enrich_meta._id_from_uri("not:a:track:uri") is None


# ──────────────────────────────────────────────────────────────────────────────
# Graceful-failure path
# ──────────────────────────────────────────────────────────────────────────────

def test_artist_top_tracks_error_is_skipped(tmp_path, monkeypatch):
    """An artist fetch that raises should be skipped, not crash the whole run."""
    monkeypatch.setattr(enrich_meta, "CACHE_DIR", str(tmp_path / "cache"))

    class ErrorSp:
        def artist_top_tracks(self, artist_id, country="US"):
            raise Exception("network error")

    # Should return empty dict (not raise)
    result = enrich_meta.fetch_artist_top_tracks(ErrorSp(), ["art_bad"])
    assert result == {}


def test_pick_image_returns_closest():
    images = [
        {"url": "big.jpg", "width": 640},
        {"url": "med.jpg", "width": 300},
        {"url": "small.jpg", "width": 64},
    ]
    assert enrich_meta._pick_image(images, 300) == "med.jpg"
    assert enrich_meta._pick_image(images, 64) == "small.jpg"
    assert enrich_meta._pick_image([], 300) is None
