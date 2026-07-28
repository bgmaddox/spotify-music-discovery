"""Name normalization + the match/reject gates shared by the two name searches.

Pure functions only — no network, no auth, no files. These lock the specific
real-world noise the fallbacks were built for (smart quotes, edition suffixes,
feature credits) AND the cases that must be REJECTED, since a wrong cover or a
wrong artist is worse than a blank.
"""

import name_match as nm


# ---------------------------------------------------------------- normalize


def test_normalize_flattens_punctuation_and_case():
    assert nm.normalize('"Awaken, My Love!"') == "awaken my love"
    assert nm.normalize("A Sailor’s Guide to Earth") == nm.normalize(
        "A Sailor's Guide to Earth"
    )
    assert nm.normalize("Hall & Oates") == nm.normalize("Hall and Oates")
    assert nm.normalize("AC/DC") == "ac dc"
    assert nm.normalize(None) == ""


def test_normalize_strips_diacritics():
    assert nm.normalize("Benicàssim") == "benicassim"
    assert nm.normalize("JAŸ-Z") == nm.normalize("JAY Z")


# ---------------------------------------------------------------- album_core


def test_album_core_strips_edition_noise():
    for raw in (
        "Coming Home (Deluxe)",
        "Coming Home (Deluxe Version)",
        "Coming Home (Bonus Track Version)",
        "Coming Home (2007 Remaster)",
        "Coming Home (Expanded Edition)",
        "Coming Home - EP",
        "Coming Home - Single",
    ):
        assert nm.album_core(raw) == "coming home", raw


def test_album_core_keeps_meaningful_parentheticals():
    """Only edition/format words are noise — a real subtitle stays."""
    assert nm.album_core("Collide (Remixes) - EP") == "collide remixes"
    assert nm.album_core("34th & 8th (Live)") == "34th and 8th live"


def test_track_core_drops_feature_credits():
    assert nm.track_core("Here Comes the Night (feat. Mr Hudson)") == (
        "here comes the night"
    )
    assert nm.track_core("Fast Car (feat. Dakota)") == "fast car"
    assert nm.track_core("Frontin' (feat. JAŸ-Z)") == "frontin"


# ---------------------------------------------------------------- artist match


def test_artist_matches_accepts_same_act():
    assert nm.artist_matches("CHVRCHES", "Chvrches")
    assert nm.artist_matches("The Avett Brothers", "Avett Brothers")
    assert nm.artist_matches("Nathaniel Rateliff", "Nathaniel Rateliff & The Night Sweats")
    assert nm.artist_matches("Sturgill Simpson", "sturgill  simpson")


def test_artist_matches_rejects_mere_substring():
    """`The Band` must not match `The Band Perry` — different acts."""
    assert not nm.artist_matches("The Band", "The Band Perry")
    assert not nm.artist_matches("Bridges", "Leon Bridges")
    assert not nm.artist_matches("Nico Segal", "The Beach Boys")
    assert not nm.artist_matches("", "Anybody")


# ---------------------------------------------------------------- similarity


def test_album_similarity_rejects_near_miss():
    """Deluxe editions are the same record; a live album is not.

    This is the threshold case for enrich_meta.ALBUM_SEARCH_MIN_RATIO (0.87):
    it must accept the first and reject the second.
    """
    assert nm.album_similarity("Coming Home (Deluxe)", "Coming Home") == 1.0
    assert nm.album_similarity("Coming Home (Deluxe)", "Coming Home Live") < 0.87


# ---------------------------------------------------------------- extension


def test_parenthetical_extension_accepts_annotated_release():
    assert nm.parenthetical_extension(
        "Spring Awakening", "Spring Awakening (Original Broadway Cast Recording)"
    )
    assert nm.parenthetical_extension("After the Fall", "After The Fall (Live)")


def test_parenthetical_extension_rejects_renamed_record():
    """The tribute-album trap: same prefix, no bracket, different artist.

    `Lioness: Hidden Treasures` (Amy Winehouse) vs `Lioness: Hidden Treasures,
    But Piano` (a piano cover record) — accepting this misattributes the play.
    """
    assert not nm.parenthetical_extension(
        "Lioness: Hidden Treasures", "Lioness: Hidden Treasures, But Piano"
    )
    # A short/generic hint can never prefix-match its way in.
    assert not nm.parenthetical_extension("Live", "Live (Deluxe Edition)")
    assert not nm.parenthetical_extension("Gold", "Gold (Remastered)")
    assert not nm.parenthetical_extension("Surf", "Surf (Original Motion Picture)")
    # No bracket at all.
    assert not nm.parenthetical_extension("Coming Home", "Coming Home Live")
