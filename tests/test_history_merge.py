"""Multi-service merge: Apple Music events folded into the Spotify history.

Locks the seam added in `streaming_history._iter_events()` — chronological
ordering of the merged stream, service tagging/provenance, the reversibility
guard (`include_apple=False` must reproduce the Spotify-only aggregate), the
pre-Spotify era, the discovery-guard consequence (an Apple-only artist must
reach `all_time_artists`), and the crux: Apple's null `reason_start`/`shuffle`
must keep it OUT of `intentionality` rather than flooding it with "other".

Runs entirely against synthetic fixtures written to tmp_path — never the real
(gitignored, personal) Spotify or Apple exports. The Apple events file is
resolved as a sibling of the export dir (`_default_apple_path`), so writing it
next to the synthetic export is what wires it in.
"""

import json

import streaming_history


# ------------------------------------------------------------------ fixtures


def _spotify_event(ts, artist, title, ms=240_000, uri="spotify:track:x", **kw):
    """A synthetic Spotify export row (full field set)."""
    return {
        "ts": ts,
        "ms_played": ms,
        "master_metadata_track_name": title,
        "master_metadata_album_artist_name": artist,
        "master_metadata_album_album_name": kw.get("album", "An Album"),
        "spotify_track_uri": uri,
        "reason_start": kw.get("reason_start", "clickrow"),
        "reason_end": kw.get("reason_end", None),
        "shuffle": kw.get("shuffle", False),
        "skipped": kw.get("skipped", None),
        "platform": kw.get("platform", "android"),
    }


def _apple_event(ts, artist, title, ms=240_000, **kw):
    """A synthetic Apple event in the exact shape apple_history.py emits.

    The weak fields are None on purpose — that is the real export's behavior and
    the whole point of these tests.
    """
    return {
        "ts": ts,
        "ms_played": ms,
        "master_metadata_album_artist_name": artist,
        "master_metadata_track_name": title,
        "master_metadata_album_album_name": kw.get("album", "An Apple Album"),
        "spotify_track_uri": None,
        "platform": kw.get("platform", "iOS"),
        "reason_start": None,
        "shuffle": None,
        "skipped": kw.get("skipped", False),
        "service": "apple",
        "apple_feature": None,
        "apple_end_reason": kw.get("end_reason", "NATURAL_END_OF_TRACK"),
    }


def _write_corpus(tmp_path, spotify_events, apple_events=None, year="2020"):
    """Write a synthetic Spotify export dir (+ optional sibling Apple file).

    Returns the export dir path. The Apple file lands at
    `<tmp_path>/apple_history_events.json`, which is exactly where
    `_default_apple_path()` looks given `<tmp_path>/export`.
    """
    src = tmp_path / "export"
    src.mkdir(parents=True, exist_ok=True)
    (src / f"Streaming_History_Audio_{year}.json").write_text(json.dumps(spotify_events))
    if apple_events is not None:
        (tmp_path / "apple_history_events.json").write_text(
            json.dumps({
                "generated_at": "2026-07-27T00:00:00Z",
                "source": "Apple Music Activity",
                "stats": {"events_emitted": len(apple_events), "total_rows": len(apple_events)},
                "events": apple_events,
            })
        )
    return str(src)


# ------------------------------------------------------------------ ordering


def test_merged_stream_is_chronological_and_has_both_services(tmp_path):
    """The merged stream must be sorted by ts, interleaving the two services."""
    spotify = [
        _spotify_event("2016-05-01T10:00:00Z", "Spoon", "Overlap"),
        _spotify_event("2020-01-01T10:00:00Z", "Spoon", "Later"),
        _spotify_event("2026-01-01T10:00:00Z", "Spoon", "Latest"),
    ]
    apple = [
        _apple_event("2015-09-01T10:00:00Z", "Cherub", "Early"),
        _apple_event("2016-06-01T10:00:00Z", "Cherub", "Middle"),
        _apple_event("2018-03-01T10:00:00Z", "Cherub", "Late"),
    ]
    src = _write_corpus(tmp_path, spotify, apple)

    merged = list(streaming_history._iter_events(src))
    stamps = [e["ts"] for e in merged]
    assert stamps == sorted(stamps), f"merged stream is not chronological: {stamps}"
    assert len(merged) == 6
    # An Apple event must actually land BETWEEN two Spotify events — proving the
    # merge interleaves rather than concatenating.
    services = [e["service"] for e in merged]
    assert services == ["apple", "spotify", "apple", "apple", "spotify", "spotify"]


def test_every_event_carries_a_service_tag(tmp_path):
    """Spotify events are tagged on the fly; Apple events keep their own tag."""
    src = _write_corpus(
        tmp_path,
        [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")],
        [_apple_event("2016-01-01T10:00:00Z", "Cherub", "T2")],
    )
    tags = {e["service"] for e in streaming_history._iter_events(src)}
    assert tags == {"spotify", "apple"}


def test_apple_events_absent_when_no_sibling_file(tmp_path):
    """No Apple file next to the export → the Spotify-only stream, no crash."""
    src = _write_corpus(tmp_path, [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")])
    merged = list(streaming_history._iter_events(src))
    assert len(merged) == 1
    assert merged[0]["service"] == "spotify"


# ------------------------------------------------------------------ reversibility


def test_no_apple_reproduces_spotify_only_aggregate(tmp_path):
    """include_apple=False must be a byte-for-byte regression baseline.

    Same Spotify corpus, once with an Apple file sitting right there and once
    without it: with include_apple=False the two summaries must be identical
    apart from the timestamp and the provenance block.
    """
    spotify = [
        _spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1", reason_start="clickrow"),
        _spotify_event("2020-01-01T10:05:00Z", "Spoon", "T2", 5_000, reason_start="trackdone"),
        _spotify_event("2021-06-01T10:00:00Z", "Guster", "T3", reason_start="playbtn"),
    ]
    apple = [_apple_event(f"2016-0{m}-01T10:00:00Z", "Cherub", f"A{m}") for m in range(1, 6)]

    with_apple_dir = _write_corpus(tmp_path / "a", spotify, apple)
    plain_dir = _write_corpus(tmp_path / "b", spotify, None)

    a = streaming_history.build_history(
        with_apple_dir, str(tmp_path / "a.json"), include_apple=False
    )
    b = streaming_history.build_history(plain_dir, str(tmp_path / "b.json"))

    volatile = {"generated_at", "service_meta", "coverage"}
    for key in set(a) | set(b):
        if key in volatile:
            continue
        assert a[key] == b[key], f"include_apple=False diverged from Spotify-only on {key!r}"

    assert a["service_meta"]["include_apple"] is False
    assert a["service_meta"]["services"] == ["spotify"]


def test_apple_merge_actually_changes_the_aggregate(tmp_path):
    """Sanity guard on the test above: with Apple ON, the numbers do move."""
    spotify = [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")]
    apple = [_apple_event(f"2016-0{m}-01T10:00:00Z", "Cherub", f"A{m}") for m in range(1, 6)]
    src = _write_corpus(tmp_path, spotify, apple)

    off = streaming_history.build_history(src, str(tmp_path / "off.json"), include_apple=False)
    on = streaming_history.build_history(src, str(tmp_path / "on.json"), include_apple=True)

    assert off["total_plays"] == 1
    assert on["total_plays"] == 6
    assert "2016" not in off["per_year"]
    assert on["per_year"]["2016"]["plays"] == 5


# ------------------------------------------------------------------ the crux


def test_apple_excluded_from_intentionality(tmp_path):
    """Apple years must be ABSENT from intentionality, not filled with 'other'."""
    spotify = [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1", reason_start="clickrow")]
    apple = [_apple_event(f"2016-0{m}-01T10:00:00Z", "Cherub", f"A{m}") for m in range(1, 6)]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )

    by_year = s["intentionality"]["by_year"]
    assert "2016" not in by_year, (
        "An Apple-only year must not appear in intentionality at all — a zeroed or "
        "all-'other' row is exactly the misleading output this guards against"
    )
    assert by_year["2020"]["deliberate"] == 1
    assert by_year["2020"]["total"] == 1
    assert s["intentionality"]["services"] == ["spotify"]
    assert s["intentionality"]["years_covered"] == ["2020"]


def test_apple_still_counts_toward_plays_artists_and_years(tmp_path):
    """Excluded from intentionality ≠ excluded from the history."""
    spotify = [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")]
    apple = [_apple_event(f"2016-0{m}-01T10:00:00Z", "Cherub", f"A{m}") for m in range(1, 6)]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )

    assert s["per_year"]["2016"]["plays"] == 5
    assert s["per_year"]["2016"]["top_artists"][0] == {"name": "Cherub", "plays": 5}
    names = {a["name"] for a in s["all_time_artists"]}
    assert {"Cherub", "Spoon"} <= names
    # Clock/seasonality are ts-derived and must include Apple.
    assert sum(c["n"] for c in s["clock"]["data"]["overall"]) == 6
    assert s["seasonality"]["by_year"]["2016"]


def test_mixed_year_intentionality_counts_only_spotify(tmp_path):
    """In 2018 (both services), only the Spotify plays reach intentionality."""
    spotify = [
        _spotify_event("2018-06-01T10:00:00Z", "Spoon", "S1", reason_start="clickrow"),
        _spotify_event("2018-06-02T10:00:00Z", "Spoon", "S2", reason_start="trackdone"),
    ]
    apple = [_apple_event(f"2018-03-0{d}T10:00:00Z", "Cherub", f"A{d}") for d in range(1, 5)]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple, year="2018"), str(tmp_path / "s.json")
    )

    y = s["intentionality"]["by_year"]["2018"]
    assert y["total"] == 2, "Apple's 4 plays must not inflate the 2018 intentionality total"
    assert y["other"] == 0, "Apple must not appear as 'other'"
    assert s["per_year"]["2018"]["plays"] == 6, "but all 6 plays count in the history"


def test_album_sessions_are_spotify_only(tmp_path):
    """Apple has no reason_start, so it is not fed to the session detector."""
    apple = [
        _apple_event(f"2016-01-01T10:0{d}:00Z", "Cherub", f"A{d}", album="Year of the Caprese")
        for d in range(0, 6)
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")], apple),
        str(tmp_path / "s.json"),
    )
    sessions = s["albums"]["album_sessions"]
    assert sessions["total_sessions"] == 0
    assert sessions["services"] == ["spotify"]
    # ...but the Apple album's PLAY total is still counted.
    caprese = next(
        a for a in s["albums"]["top_albums"] if a["name"] == "Year of the Caprese"
    )
    assert caprese["plays"] == 6
    assert caprese["session_count"] == 0


def test_apple_only_track_uri_stays_empty_not_null(tmp_path):
    """Apple tracks carry no spotify_track_uri; downstream expects "" not None."""
    apple = [_apple_event("2016-01-01T10:00:00Z", "Cherub", "Doses & Mimosas")]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")], apple),
        str(tmp_path / "s.json"),
    )
    t = next(t for t in s["all_time_tracks"] if t["title"] == "Doses & Mimosas")
    assert t["uri"] == ""


def test_spotify_uri_survives_a_later_apple_play_of_the_same_track(tmp_path):
    """A track played on both services must keep its real Spotify URI."""
    spotify = [_spotify_event("2018-01-01T10:00:00Z", "Spoon", "Shared", uri="spotify:track:real")]
    apple = [_apple_event("2018-06-01T10:00:00Z", "Spoon", "Shared")]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple, year="2018"), str(tmp_path / "s.json")
    )
    t = next(t for t in s["all_time_tracks"] if t["title"] == "Shared")
    assert t["plays"] == 2
    assert t["uri"] == "spotify:track:real", (
        "the later Apple play (spotify_track_uri=None) blanked the real URI"
    )


# ------------------------------------------------------------------ provenance


def test_service_meta_provenance(tmp_path):
    spotify = [
        _spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1"),
        _spotify_event("2020-01-02T10:00:00Z", "Spoon", "T2", 5_000),  # skip
    ]
    apple = [
        _apple_event("2016-01-01T10:00:00Z", "Cherub", "A1"),
        _apple_event("2016-02-01T10:00:00Z", "Cherub", "A2"),
        _apple_event("2017-03-01T10:00:00Z", "Cherub", "A3"),
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    meta = s["service_meta"]

    assert meta["services"] == ["apple", "spotify"]
    assert meta["include_apple"] is True

    assert meta["by_service"]["apple"]["events"] == 3
    assert meta["by_service"]["apple"]["plays"] == 3
    assert meta["by_service"]["apple"]["first_play"] == "2016-01-01T10:00:00Z"
    assert meta["by_service"]["apple"]["last_play"] == "2017-03-01T10:00:00Z"

    assert meta["by_service"]["spotify"]["events"] == 2
    assert meta["by_service"]["spotify"]["plays"] == 1
    assert meta["by_service"]["spotify"]["skips"] == 1

    # per-year per-service breakdown
    assert meta["by_year"]["2016"] == {"apple": {"events": 2, "plays": 2}}
    assert meta["by_year"]["2020"] == {"spotify": {"events": 2, "plays": 1}}

    # the Apple parser's own stats, carried verbatim
    assert meta["apple_parser_stats"]["events_emitted"] == 3


def test_coverage_block_distinguishes_no_data_from_zero(tmp_path):
    """The front end must be able to tell 'no intentionality data' from '0% intent'."""
    spotify = [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")]
    apple = [_apple_event("2016-01-01T10:00:00Z", "Cherub", "A1")]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    cov = s["coverage"]

    assert cov["services_by_year"]["2016"] == ["apple"]
    assert cov["services_by_year"]["2020"] == ["spotify"]

    intent = cov["sections"]["intentionality"]
    assert intent["services"] == ["spotify"]
    assert "2016" not in intent["years_covered"]
    assert "2020" in intent["years_covered"]

    both = cov["sections"]["clock"]
    assert set(both["services"]) == {"apple", "spotify"}
    assert {"2016", "2020"} <= set(both["years_covered"])

    assert "intentionality" in cov["spotify_only_sections"]
    assert "album_sessions" in cov["spotify_only_sections"]


# ------------------------------------------------------------------ eras


def test_2016_event_lands_in_the_pre_spotify_era(tmp_path):
    """Apple's years now have an era; the pre-existing slugs are unchanged."""
    assert streaming_history._era_for_year(2016) == "2015-2017"
    assert streaming_history._era_for_year(2015) == "2015-2017"
    assert streaming_history._era_for_year(2017) == "2015-2017"
    # existing slugs must not shift
    assert streaming_history._era_for_year(2018) == "2018"
    assert streaming_history._era_for_year(2020) == "2019-2020"
    assert streaming_history._era_for_year(2026) == "2025-2026"
    assert streaming_history._era_for_year(2014) is None

    apple = [_apple_event("2016-06-15T18:00:00Z", "Cherub", "A1")]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")], apple),
        str(tmp_path / "s.json"),
    )
    clock = s["clock"]["data"]
    assert "2015-2017" in s["clock"]["eras"]
    assert sum(c["n"] for c in clock["2015-2017"]) == 1
    assert sum(c["n"] for c in clock["2019-2020"]) == 1


# ------------------------------------------------------------------ discovery guard


def test_apple_only_heavy_hitter_reaches_all_time_artists(tmp_path):
    """The discovery-guard fix: an artist known ONLY from the Apple era must land
    in `all_time_artists`, which is what `discovery_log.known_listened_artists()`
    reads to decide whether Claude has already "discovered" someone.
    """
    # A Spotify-era artist with modest plays, and an Apple-era artist with more.
    spotify = [
        _spotify_event(f"2020-01-{d:02d}T10:00:00Z", "Modern Band", f"S{d}")
        for d in range(1, 6)
    ]
    apple = [
        _apple_event(f"2016-{(d % 12) + 1:02d}-{(d % 27) + 1:02d}T10:00:00Z",
                     "Macklemore & Ryan Lewis", f"A{d}")
        for d in range(1, 21)
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )

    ranked = [a["name"] for a in s["all_time_artists"]]
    assert "Macklemore & Ryan Lewis" in ranked, (
        "an Apple-only artist absent from all_time_artists would be mislabeled a "
        "genuine discovery by discovery_log's --new-only guard"
    )
    assert ranked.index("Macklemore & Ryan Lewis") < ranked.index("Modern Band")
    mack = next(a for a in s["all_time_artists"] if a["name"] == "Macklemore & Ryan Lewis")
    assert mack["plays"] == 20
    assert set(mack["by_year"]) == {"2016"}


def test_household_filter_applies_to_apple_events(tmp_path):
    """household.py is service-agnostic — an Apple household play is still excluded."""
    apple = [
        _apple_event("2016-01-01T10:00:00Z", "CoComelon", "Baby Shark"),
        _apple_event("2016-01-02T10:00:00Z", "Cherub", "Doses"),
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")], apple),
        str(tmp_path / "s.json"),
    )
    assert s["v2_meta"]["household_excluded_plays"] == 1
    # household plays still count in v1 totals (unchanged behavior), but not the clock
    assert s["per_year"]["2016"]["plays"] == 2
    assert sum(c["n"] for c in s["clock"]["data"]["overall"]) == 2  # Cherub + Spoon


# ------------------------------------------------------------------ canonical names


def test_election_picks_the_higher_play_variant(tmp_path):
    """The case variant with more PLAYS wins the display name."""
    # Spotify spells it "Outkast" (many plays), Apple spells it "OutKast" (few).
    spotify = [
        _spotify_event(f"2020-01-{d:02d}T10:00:00Z", "Outkast", f"S{d}") for d in range(1, 9)
    ]
    apple = [
        _apple_event(f"2016-01-{d:02d}T10:00:00Z", "OutKast", f"A{d}") for d in range(1, 3)
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    names = [a["name"] for a in s["all_time_artists"]]
    assert "Outkast" in names
    assert "OutKast" not in names


def test_election_picks_higher_play_variant_even_when_apple(tmp_path):
    """Play count beats service: the Apple spelling wins if it has more plays."""
    # Apple's "Florence + the Machine" outplays Spotify's "Florence + The Machine".
    spotify = [
        _spotify_event(f"2020-01-{d:02d}T10:00:00Z", "Florence + The Machine", f"S{d}")
        for d in range(1, 4)
    ]
    apple = [
        _apple_event(f"2016-01-{d:02d}T10:00:00Z", "Florence + the Machine", f"A{d}")
        for d in range(1, 10)
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    names = [a["name"] for a in s["all_time_artists"]]
    assert "Florence + the Machine" in names, "the higher-play (Apple) spelling must win"
    assert "Florence + The Machine" not in names


def test_tie_breaks_toward_the_spotify_spelling(tmp_path):
    """Equal plays → the Spotify spelling wins (larger, ongoing corpus)."""
    spotify = [
        _spotify_event(f"2020-01-{d:02d}T10:00:00Z", "Cage The Elephant", f"S{d}")
        for d in range(1, 4)
    ]
    apple = [
        _apple_event(f"2016-01-{d:02d}T10:00:00Z", "Cage the Elephant", f"A{d}")
        for d in range(1, 4)
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    names = [a["name"] for a in s["all_time_artists"]]
    assert "Cage The Elephant" in names, "a tie must break toward the Spotify spelling"
    assert "Cage the Elephant" not in names


def test_play_counts_actually_sum_after_merge(tmp_path):
    """The whole point: the split halves become one total, not two entries."""
    spotify = [
        _spotify_event(f"2020-01-{d:02d}T10:00:00Z", "TV On The Radio", f"S{d}")
        for d in range(1, 5)
    ]
    apple = [
        _apple_event(f"2016-01-{d:02d}T10:00:00Z", "TV on the Radio", f"A{d}")
        for d in range(1, 7)
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    matching = [a for a in s["all_time_artists"] if a["name"].casefold() == "tv on the radio"]
    assert len(matching) == 1, "the artist must appear exactly once, not once per spelling"
    assert matching[0]["plays"] == 10, "4 Spotify + 6 Apple plays must sum"
    assert matching[0]["by_year"] == {"2016": 6, "2020": 4}


def test_name_differing_by_more_than_case_is_not_merged(tmp_path):
    """Punctuation / word differences must NOT be collapsed — case-only by design."""
    spotify = [
        _spotify_event("2020-01-01T10:00:00Z", "Florence + The Machine", "S1"),
        _spotify_event("2020-01-02T10:00:00Z", "Florence and the Machine", "S2"),
        _spotify_event("2020-01-03T10:00:00Z", "Florence + The Machines", "S3"),
    ]
    apple = [_apple_event("2016-01-01T10:00:00Z", "Cherub", "A1")]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    names = {a["name"] for a in s["all_time_artists"]}
    assert {
        "Florence + The Machine",
        "Florence and the Machine",
        "Florence + The Machines",
    } <= names, "only case-identical names may be merged"
    assert s["service_meta"]["artist_name_merges"]["count"] == 0


def test_merge_provenance_recorded(tmp_path):
    """Every merge is auditable from the summary."""
    spotify = [
        _spotify_event(f"2020-01-{d:02d}T10:00:00Z", "Outkast", f"S{d}") for d in range(1, 9)
    ]
    apple = [
        _apple_event(f"2016-01-{d:02d}T10:00:00Z", "OutKast", f"A{d}") for d in range(1, 3)
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    block = s["service_meta"]["artist_name_merges"]
    assert block["count"] == 1
    m = block["merges"][0]
    assert m["canonical"] == "Outkast"
    assert m["merged_from"] == ["OutKast"]
    assert m["combined_plays"] == 10
    assert {v["name"] for v in m["variants"]} == {"Outkast", "OutKast"}
    assert {v["services"][0] for v in m["variants"]} == {"spotify", "apple"}


def test_canonicalization_reaches_every_section(tmp_path):
    """Applied at the seam → tracks/albums/seasonality all see one identity."""
    spotify = [
        _spotify_event("2020-01-01T10:00:00Z", "Dispatch", "Shared Song", album="Bang Bang"),
        _spotify_event("2020-01-02T10:00:00Z", "Dispatch", "Shared Song", album="Bang Bang"),
        _spotify_event("2020-01-03T10:00:00Z", "Dispatch", "Shared Song", album="Bang Bang"),
    ]
    apple = [
        _apple_event("2016-01-01T10:00:00Z", "DISPATCH", "Shared Song", album="Bang Bang"),
        _apple_event("2016-01-02T10:00:00Z", "DISPATCH", "Shared Song", album="Bang Bang"),
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    assert [t["artist"] for t in s["all_time_tracks"]] == ["Dispatch"]
    assert s["all_time_tracks"][0]["plays"] == 5
    assert [a["artist"] for a in s["albums"]["top_albums"]] == ["Dispatch"]
    assert s["albums"]["top_albums"][0]["plays"] == 5
    assert s["seasonality"]["artist_by_month"]["2016"]["1"] == {"Dispatch": 2}
    assert [a["name"] for a in s["artist_skip"]["artists"]] == ["Dispatch"]


def test_no_apple_skips_canonicalization(tmp_path):
    """--no-apple stays a clean pre-merge baseline — no renaming applied."""
    spotify = [
        _spotify_event("2020-01-01T10:00:00Z", "Outkast", "S1"),
        _spotify_event("2020-01-02T10:00:00Z", "OutKast", "S2"),
    ]
    apple = [_apple_event("2016-01-01T10:00:00Z", "Cherub", "A1")]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json"), include_apple=False
    )
    names = {a["name"] for a in s["all_time_artists"]}
    assert {"Outkast", "OutKast"} <= names
    assert s["service_meta"]["artist_name_merges"]["count"] == 0


def test_canonicalization_is_order_independent(tmp_path):
    """Deterministic election regardless of which variant is seen first."""
    a_first = _elect = streaming_history._elect_canonical_names
    events = [
        {"master_metadata_album_artist_name": "Fun.", "ms_played": 240_000, "service": "apple"},
        {"master_metadata_album_artist_name": "fun.", "ms_played": 240_000,
         "service": "spotify"},
    ]
    aliases_a, _ = a_first(events)
    aliases_b, _ = _elect(list(reversed(events)))
    assert aliases_a == aliases_b
    # 1 play each → tie → Spotify spelling ("fun.") wins
    assert aliases_a == {"Fun.": "fun."}


def test_household_names_are_not_disturbed_by_canonicalization(tmp_path):
    """A household artist must keep filtering after a case merge elsewhere.

    household.py matches its config list case-SENSITIVELY, so this guards that
    canonicalization never quietly renames a name the filter depends on.
    """
    spotify = [
        _spotify_event("2020-01-01T10:00:00Z", "CoComelon", "S1"),
        _spotify_event("2020-01-02T10:00:00Z", "Outkast", "S2"),
    ]
    apple = [
        _apple_event("2016-01-01T10:00:00Z", "CoComelon", "A1"),
        _apple_event("2016-01-02T10:00:00Z", "OutKast", "A2"),
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, spotify, apple), str(tmp_path / "s.json")
    )
    assert s["v2_meta"]["household_excluded_plays"] == 2
    merged_names = {
        n for m in s["service_meta"]["artist_name_merges"]["merges"] for n in m["merged_from"]
    }
    merged_names |= {
        m["canonical"] for m in s["service_meta"]["artist_name_merges"]["merges"]
    }
    assert not (merged_names & set(streaming_history.HOUSEHOLD_ARTISTS))


def test_apple_platform_tokens_map_into_existing_buckets(tmp_path):
    """Apple's fixed platform vocabulary must land in the existing buckets."""
    apple = [
        _apple_event("2016-01-01T10:00:00Z", "Cherub", "A1", platform="iOS"),
        _apple_event("2016-01-02T10:00:00Z", "Cherub", "A2", platform="Macintosh"),
        _apple_event("2016-01-03T10:00:00Z", "Cherub", "A3", platform="unknown"),
    ]
    s = streaming_history.build_history(
        _write_corpus(tmp_path, [_spotify_event("2020-01-01T10:00:00Z", "Spoon", "T1")], apple),
        str(tmp_path / "s.json"),
    )
    p2016 = s["platforms"]["by_year"]["2016"]
    assert p2016.get("mobile") == 1
    assert p2016.get("desktop") == 1
    assert p2016.get("other") == 1  # "unknown" has no rule → other
