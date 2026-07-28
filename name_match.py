"""Fuzzy name matching for catalog lookups (artists, albums, track titles).

Shared by the two Spotify *name-search* fallbacks, which both have to decide
"is this search hit really the thing I asked for?" against messy real-world
metadata:

  - `enrich_meta.search_album_by_name` — cover art for albums that have no
    Spotify track URI to hang off (Apple-Music-only listening).
  - `apple_resolve` — recovering the artist for an Apple play whose title-join
    missed, using the album hint.

Everything here is pure (no network, no I/O) so it can be locked by tests.

## The noise this has to survive

Real catalog strings differ from a user's/export's string in predictable ways:

  - Edition suffixes: `(Deluxe)`, `(Deluxe Version)`, `(Bonus Track Version)`,
    `(2007 Remaster)`, `(Special Edition)`, `(Expanded Edition)`, `- EP`,
    `- Single`.
  - Smart vs straight quotes and dashes: `Sailor’s` vs `Sailor's`,
    `–`/`—` vs `-`. Note `"Awaken, My Love!"` literally contains quote
    characters in its official title.
  - Feature credits: `(feat. Mr Hudson)`, `[feat. Skip Marley]`.
  - Punctuation/case in general, and `&` vs `and`.

`normalize()` flattens all of that; `album_core()` / `track_core()` strip the
qualifiers first. A *wrong* cover or a *wrong* artist is worse than a blank, so
the comparison helpers are deliberately conservative: `artist_matches` only
accepts an exact normalized match or a connector-joined extension of it
("Nathaniel Rateliff" ⊂ "Nathaniel Rateliff & The Night Sweats"), never a bare
substring ("The Band" must NOT match "The Band Perry").
"""

from __future__ import annotations

import difflib
import re
import unicodedata

# Smart punctuation → ASCII, so `Sailor’s` and `Sailor's` compare equal.
_PUNCT_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "―": "-", "−": "-",
    "…": "...", " ": " ",
}
_PUNCT_TABLE = str.maketrans(_PUNCT_MAP)

_NON_ALNUM_RE = re.compile(r"[^0-9a-z]+")
_WS_RE = re.compile(r"\s+")

# Parenthetical/bracketed qualifiers that are edition/format noise rather than
# part of the title. Matched case-insensitively against the group's contents.
_EDITION_WORDS = (
    "deluxe", "remaster", "remastered", "bonus track", "bonus tracks",
    "special edition", "expanded", "expanded edition", "anniversary",
    "reissue", "explicit", "clean", "mono", "stereo", "digital",
    "collector", "legacy edition", "super deluxe", "extended edition",
    "japanese edition", "international version", "us version", "uk version",
    "version",
)
_GROUP_RE = re.compile(r"\s*[\(\[]([^\)\]]*)[\)\]]")
_FEAT_RE = re.compile(r"\s*[\(\[]\s*(feat\.?|ft\.?|featuring|with)\s[^\)\]]*[\)\]]", re.I)
_TRAILING_FEAT_RE = re.compile(r"\s+(feat\.?|ft\.?|featuring)\s+.*$", re.I)

# Trailing format markers Apple/Spotify append after a dash.
_TRAILING_FORMAT_RE = re.compile(
    r"\s+-\s+(ep|single|remixes?|radio edit|edit|deluxe|deluxe version|"
    r"bonus track version|remastered(\s+\d{4})?|\d{4} remaster(ed)?|live)\s*$",
    re.I,
)


def normalize(s: str | None) -> str:
    """Aggressive comparison key: casefold, de-accent, drop all punctuation.

    `"Awaken, My Love!"` → `awaken my love`; `Sailor’s` → `sailors`;
    `AC/DC` → `ac dc`. `&` becomes `and` before punctuation is stripped so
    `Hall & Oates` and `Hall and Oates` collapse together.
    """
    if not s:
        return ""
    s = s.translate(_PUNCT_TABLE)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold().replace("&", " and ")
    s = _NON_ALNUM_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def _strip_edition_groups(s: str) -> str:
    """Drop `(...)`/`[...]` groups whose contents are edition/format noise."""

    def _repl(m: re.Match) -> str:
        inner = m.group(1).casefold()
        if any(w in inner for w in _EDITION_WORDS):
            return " "
        return m.group(0)

    return _GROUP_RE.sub(_repl, s)


def strip_qualifiers(s: str | None) -> str:
    """Remove feature credits and edition/format qualifiers from a raw name.

    `Coming Home (Deluxe)` → `Coming Home`;
    `Emotionalism (Bonus Track Version)` → `Emotionalism`;
    `Collide (Remixes) - EP` → `Collide (Remixes)` → (remixes is not an edition
    word, so it survives — see `album_core` callers, which treat a hint that
    collapses to the track title as ambiguous rather than trying to be clever).
    """
    if not s:
        return ""
    out = _FEAT_RE.sub(" ", s)
    out = _strip_edition_groups(out)
    # Repeat the trailing-format strip: `... - Remixes - EP` has two markers.
    for _ in range(3):
        new = _TRAILING_FORMAT_RE.sub("", out)
        if new == out:
            break
        out = new
    return _WS_RE.sub(" ", out).strip(" -–—")


def album_core(name: str | None) -> str:
    """Normalized album name with edition/format noise removed."""
    return normalize(strip_qualifiers(name))


def track_core(title: str | None) -> str:
    """Normalized track title with feature credits and format noise removed."""
    if not title:
        return ""
    out = _FEAT_RE.sub(" ", title)
    out = _TRAILING_FEAT_RE.sub("", out)
    out = _strip_edition_groups(out)
    out = _TRAILING_FORMAT_RE.sub("", out)
    return normalize(out)


_LEADING_THE_RE = re.compile(r"^the\s+")


def artist_key(name: str | None) -> str:
    """Normalized artist name, with a leading `The ` dropped.

    `The Avett Brothers` and `Avett Brothers` are the same act; Spotify and
    Apple disagree about the article often enough to matter.
    """
    return _LEADING_THE_RE.sub("", normalize(name))


# Words that legitimately join a base act to an extended billing.
_CONNECTORS = {"and", "with", "featuring", "feat", "ft", "vs", "x", "presents"}


def artist_matches(expected: str | None, candidate: str | None) -> bool:
    """True when `candidate` is the same act as `expected`.

    Accepts an exact normalized match, or one name extending the other across a
    connector word (`Nathaniel Rateliff` ↔ `Nathaniel Rateliff & The Night
    Sweats`). Deliberately rejects plain substring overlap: `The Band` must not
    match `The Band Perry`, and `Bridges` must not match `Leon Bridges`.
    """
    a, b = artist_key(expected), artist_key(candidate)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    st, lt = short.split(), long_.split()
    if len(st) < 2 or len(lt) <= len(st):
        return False
    if lt[: len(st)] != st:
        return False
    return lt[len(st)] in _CONNECTORS


_OPEN_GROUP_RE = re.compile(r"[\(\[]")


def parenthetical_extension(expected: str | None, candidate: str | None,
                            min_tokens: int = 2, min_chars: int = 8) -> bool:
    """True when `candidate` is `expected` plus a *parenthesized* annotation.

    Catches the "official release adds a format note" shape that similarity
    scores badly: an Apple album hint of `Spring Awakening` against Spotify's
    `Spring Awakening (Original Broadway Cast Recording)` (ratio 0.49), or
    `After the Fall` vs `After The Fall (Live)`.

    The parenthesis requirement is what makes this safe. A plain whole-word
    prefix rule also accepts `Lioness: Hidden Treasures` → `Lioness: Hidden
    Treasures, But Piano` — a *different* record by a *different* artist (a
    piano tribute), which would silently misattribute an Amy Winehouse play.
    A bracketed suffix annotates the same release; a bare continuation renames it.

    Also gated on the expected name being substantial (≥2 words, ≥8 chars) so a
    short generic hint like `Live` can't match half the catalog. This is a
    *looser* rule than `similarity` — used for artist recovery, where a
    cross-candidate agreement check backstops it, and deliberately NOT used for
    cover-art matching, where a wrong answer is visible and worse.
    """
    if not expected or not candidate:
        return False
    exp_core = album_core(expected)
    if len(exp_core.split()) < min_tokens or len(exp_core) < min_chars:
        return False
    m = _OPEN_GROUP_RE.search(candidate)
    if not m or m.start() == 0:
        return False
    head = candidate[: m.start()].strip(" -–—:,")
    return similarity(exp_core, album_core(head)) >= 0.87


def similarity(a: str, b: str) -> float:
    """difflib ratio between two already-normalized strings (0.0–1.0)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def album_similarity(expected: str | None, candidate: str | None) -> float:
    """Similarity between two raw album names, compared on their cores."""
    return similarity(album_core(expected), album_core(candidate))


def title_similarity(expected: str | None, candidate: str | None) -> float:
    """Similarity between two raw track titles, compared on their cores."""
    return similarity(track_core(expected), track_core(candidate))
