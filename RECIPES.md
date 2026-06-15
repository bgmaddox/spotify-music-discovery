# RECIPES.md — session-driven workflows

These are **Mode A** recipes: the reasoning happens in the Claude Code session, the
Python tools only sense and act. Every recipe obeys the hard rule — **no track is
surfaced or added until `search_verify` confirms it exists.** Search is the source of
truth; the model is the idea generator.

Tools available:
- `search_verify(artist, title)` → track URI or `None`  *(tools.py)*
- `verify_detail(artist, title)` → `{uri, name, artists, album}` or `None` (for logging)  *(tools.py)*
- `build_playlist(name, uris, description="", public=False)` → playlist URL  *(tools.py)*
- `now_playing()` → `{id, uri, title, artists, album, is_playing, progress_ms, duration_ms}` or `None`  *(sensing.py)*
- `library_scan(cap=500)` → `{count, tracks, path}`; writes `data/library_*.json`  *(sensing.py)*
- `similar_artists(artist)` → `[{name, match}]` (Last.fm crowd similarity)  *(lastfm.py)*
- `similar_tracks(artist, title)` → `[{artist, title, match}]`  *(lastfm.py)*
- `artist_tags(artist)` → `[{tag, count}]` (coarse genre/mood signal)  *(lastfm.py)*

Knowledge library (read *before* reasoning — strategy, not data):
- `knowledge/discovery_heuristics.md` — the menu of discovery *angles* (Last.fm adjacency,
  tag intersection, producer/label lineage, sideman trails, era/region shifts, bridges).
  Name the angle you used in each rationale.
- `knowledge/genre_map.md` — static genre adjacencies for the user's clusters; pick a
  *direction*, then confirm specific artists via Last.fm and tracks via `search_verify`.

CLI equivalents — one unified entry point (`cli.py`, Phase 4). Each prints its
machine-readable result (path or URI) to stdout, human notes to stderr:
```bash
python cli.py dump-taste                                # prints taste dump path
python cli.py dump-taste --max-age 60                   # reuse a dump <60 min old, else refetch
python cli.py search-verify "Artist" "Title"            # prints URI, or MISS (exit 1)
python cli.py build-playlist "Name" --uris-file uris.txt
python cli.py build-playlist "Name" spotify:track:AAA spotify:track:BBB
python cli.py now-playing                               # prints URI + track line, or exit 1
python cli.py library-scan --cap 500                    # prints dump path
python cli.py similar-artists "Tyler Childers"          # one similar artist per line
python cli.py similar-tracks "Tyler Childers" "Feathered Indians"   # artist<TAB>title per line
python cli.py artist-tags "Tyler Childers"              # tag<TAB>count per line
```
The per-module CLIs (`python tools.py …`, `python sensing.py …`,
`python taste_profile.py`) still work and are equivalent; `cli.py` just routes to them.

---

## Recipe 1 — Discovery ladder (the core)

Goal: a private playlist that starts at the center of the user's taste and walks
outward to genuine left-field picks, each with a one-line rationale.

**Steps**

1. **Sense.** Run `python taste_profile.py` (or reuse the newest `data/taste_*.json`
   if it's fresh enough). Read it. Note dominant artists, genres, eras, popularity
   band, and what's conspicuously recent in `recently_played`.

2. **Propose a ladder** of ~12 candidates, in three rungs, each with a one-line why:
   - **~4 center-of-taste** — squarely in the user's wheelhouse; safe, high-confidence.
   - **~4 one-axis stretches** — change exactly one variable (a near genre, an adjacent
     era, a collaborator/side-project, a different scene from a loved artist).
   - **~4 left-field** — a real reach that's still defensible from something they love.

   Avoid tracks already in `top_tracks`/`saved_tracks`/`recently_played` unless the
   point is a deep cut. Name a specific **artist + title** for each — not a vibe.

3. **Verify every candidate.** Call `search_verify` (or `verify_detail` for nicer
   logs) on each. Collect the URIs that hit. **Log every miss** with the name as
   proposed — a miss usually means a hallucinated/mis-titled track, so don't silently
   drop it; note it and optionally retry with a corrected title.

4. **Build.** `build_playlist("🤖 <descriptive name>", verified_uris,
   description="<brief thematic summary>")`. Private by default.
   - **Name:** prefix every Claude-built playlist with `🤖 ` so they group together
     and the user can drag them into a "Claude" folder (the Web API can't create or
     move folders — that step is manual, one-time).
   - **Description:** a 1–2 sentence summary of *this* playlist — the artists, mood,
     era, or through-line that makes it interesting. **Not** "Claude curated" or any
     description of the tooling. (Spotify caps descriptions at 300 chars.)

5. **Report** to the user: the playlist URL, the verified tracks grouped by rung with
   their rationales, and the list of dropped candidates (with why each missed).

**Acceptance:** ≥10 verified tracks on a real private playlist, rationales given,
dropped candidates reported.

---

## Recipe 2 — Now-playing companion (rabbit hole)

Goal: take whatever is playing right now and give the user the lineage / "rabbit
hole" around it — where this track sits, who it descends from, and a few verified
next steps.

**Steps**

1. **Sense.** Call `now_playing()`. If it returns `None`, tell the user nothing is
   playing and stop. Otherwise note artist, title, album.
2. **Commentary.** Write a short lineage read: the artist's scene/era, key
   influences and contemporaries, and where this specific track fits. Keep it tight.
3. **Next steps (optional but encouraged).** Propose ~3–5 follow-on tracks that
   continue the thread (deeper cut, an influence, a descendant). Name artist+title.
4. **Verify** each with `search_verify`/`verify_detail`; drop and log misses.
5. **Offer** to `build_playlist` the verified next-steps if the user wants to keep
   the rabbit hole. Don't build unprompted — this recipe is conversational.

---

## Recipe 3 — Taste report + blind spots

Goal: a narrative read of the user's taste, plus genres/scenes suspiciously absent
given what they clearly love.

**Steps**

1. **Sense.** Run `python taste_profile.py` (or reuse a fresh `data/taste_*.json`).
   Optionally `library_scan` for a fuller saved-library picture.
2. **Read.** Summarize dominant artists, genres, eras, popularity band, and how
   `short_term` vs `long_term` differ (what's rising/fading).
3. **Blind spots.** Name 3–6 genres/scenes/eras that are conspicuously *missing*
   given the established taste — adjacent things a listener like this usually has.
   Justify each from something they actually love.
4. **Report.** Narrative + bulleted blind spots. No playlist required; if the user
   wants one, hand off to Recipe 1 or 5. (No tracks are *named as existing* here
   without `search_verify`; blind-spot **genres** are fine to name unverified.)

---

## Recipe 4 — Library archaeologist

Goal: surface patterns in the user's *own* saved library and propose playlists built
entirely from tracks they already own.

**Steps**

1. **Sense.** `library_scan(cap=500)`; read `data/library_*.json`.
2. **Dig.** Find clusters: a recurring sub-genre, an era pocket, a mood thread, a
   producer/label run, songs added in the same window. Pick 1–3 worth a playlist.
3. **Assemble** from the library dump itself — these tracks already have real
   `id`/`uri`s, so build URIs directly (`spotify:track:<id>`). Still sanity-check
   with `verify_detail` if you're unsure an id is current.
4. **Build** with `build_playlist` and report the through-line of each playlist.

---

## Recipe 5 — Time machine

Goal: a playlist for a given vibe / era / theme the user names.

**Steps**

1. **Take the brief** (e.g. "late-90s UK garage", "rainy Sunday jazz", "2008 indie
   blog-house"). Anchor it against the taste dump so it still feels personal.
2. **Propose** ~10–15 tracks that fit the brief, artist+title each, with a one-line
   why. Mix recognizable anchors with deeper cuts.
3. **Verify** every candidate with `search_verify`; log misses (likely
   hallucinations — retry with a corrected title or drop).
4. **Build** with `build_playlist`, then report the verified set and any drops.

---

## Recipe 6 — Lateral discovery (Last.fm-seeded ladder)

Goal: the discovery ladder (Recipe 1), but powered by an *external* similarity signal so
the picks are genuinely new — artists the user has never touched — rather than recombined
from their own taste dump. This is the recipe Phase 5 exists for.

**Why it's different from Recipe 1:** Recipe 1 reasons only from the taste dump (a closed
loop). Recipe 6 injects fresh candidates from Last.fm and steers them with the
`knowledge/` angles, so it can reach past what the session already associates with the
user. It directly replaces what Spotify's dead `related-artists`/`recommendations` did.

**Steps**

1. **Sense.** Run/reuse a `data/taste_*.json` dump. Pick **2–4 seed artists** that are
   central *and* distinct from each other (don't seed near-duplicates).
2. **Gather external candidates.** For each seed:
   - `similar_artists(seed)` — split by `match`: ≥0.5 center, 0.2–0.5 stretch, tail
     left-field.
   - `artist_tags(seed)` — note the 2–3 defining tags (the *why*, per angle 2).
   - Optionally `similar_tracks(seed, <a loved title>)` for track-level candidates.
   Cache makes re-runs free.
3. **Filter to genuinely new.** **Drop any candidate already in the taste dump**
   (`top_artists`, `top_tracks`, `recently_played`, and — if scanned — saved library).
   The acceptance bar is *new* artists, not resurfaced ones.
4. **Steer with knowledge/.** Read `discovery_heuristics.md` and `genre_map.md`. Assign
   each surviving candidate a rung and a **named angle** (e.g. "tag intersection: outlaw
   country × singer-songwriter", "genre_map bridge: bluegrass × indie"). Prefer mid-`match`
   Last.fm names that the genre map confirms sit in an adjacent cluster.
5. **Pick a track per artist.** For each chosen artist, name a specific entry-point
   **artist + title** (their best-known or most representative track, or a `similar_tracks`
   hit). A new *artist* isn't enough — you need a concrete track to verify.
6. **Verify** every candidate with `search_verify`/`verify_detail`; log misses. Last.fm
   name-matching is uneven, so this step is doing real work — watch for wrong-artist or
   cover matches (treat as miss).
7. **Build** with `build_playlist` (private), then **report**: the playlist URL, tracks
   grouped by rung with their Last.fm `match` + the named angle, the seed→candidate trail
   (so the user sees *why* each new artist surfaced), and dropped/missed candidates.

**Acceptance:** ≥3 artists **absent from the current taste dump** (genuinely new), each
`search_verify`'d, on a real private playlist, each rationale citing its discovery angle and
the seed it came from.

---

## Recipe 7 — Genre-ladder discovery (everynoise-seeded)

Goal: the discovery ladder, but the *lateral move is along genre topology* instead of
artist similarity. Last.fm (Recipe 6) answers "who sounds like this artist?"; everynoise
answers "what genre sits next to this genre?" — a different axis. Use this when you want
to step *sideways into an adjacent scene* the user has barely touched, then populate it
with real artists.

**Why it's different from Recipe 6:** Recipe 6 walks an artist→artist graph (listening
co-occurrence). Recipe 7 walks a genre→genre map (sonic/scene adjacency), so it can jump
to a whole *neighboring style* (e.g. outlaw country → cosmic american, or indie folk →
chamber pop) and only *then* find artists in it. The two compose well: pick the genre with
Recipe 7, fill it with Recipe 6.

**Steps**

1. **Anchor on a genre.** From the taste dump (or a now-playing track), name the genre the
   user is centered in. If unsure of the exact everynoise name, resolve it:
   `python cli.py … ` → `python genre_map.py find "<partial>"`.
2. **Step sideways.** `python cli.py genre-neighbors "<genre>" --limit 15`. The list is
   **pre-ranked** — the head is the closest scene-lineage neighbor, the tail degrades into
   loose texture-matches (good for a left-field rung, per angle 11). Pick a neighbor genre
   that is *adjacent but under-represented* in the taste dump — that's the discovery target.
   For genres inside Brett's curated clusters, `knowledge/genre_map.md` is the faster,
   hand-tuned lookup; use `genre-neighbors` for anything outside it.
3. **Fill the genre with artists.** The genre map names genres, not a ready artist list.
   Get artists two ways and cross-reference: (a) the `example` artist `find` shows for that
   genre as a seed, then `similar_artists` on it (Recipe 6 step 2); (b) the session's own
   knowledge of who defines that genre — treated as a *hypothesis* until verified.
4. **Filter to genuinely new.** Drop anything already in the taste dump (same bar as
   Recipe 6 step 3).
5. **Pick a track per artist**, **verify** each with `search_verify`/`verify_detail`
   (log misses), and **build** a private `🤖 `-prefixed playlist.
6. **Report:** the playlist URL, plus the *genre trail* (`seed genre → neighbor genre →
   artists`) so the user sees they were moved one scene over — and which everynoise rung
   (head = close, tail = left-field) each neighbor came from.

**Acceptance:** ≥3 verified, genuinely-new artists drawn from a *neighboring genre*
(not the anchor genre itself), on a real private playlist, each rationale naming the
seed genre, the everynoise neighbor it stepped to, and that neighbor's rank in the list.

---

## Notes & guardrails

- **Knowledge-cutoff guardrail:** the session's music knowledge has a training cutoff.
  Treat any track you name as a *hypothesis* until `search_verify` returns a URI.
- **Match sanity:** `verify_detail` returns the matched name/artist/album. If the match
  drifts (wrong artist, a karaoke/cover, a wildly different title), treat it as a miss
  rather than adding the wrong track.
- **Re-auth:** the first `build_playlist` of a session may pop a browser OAuth consent
  to widen scopes to `playlist-modify-private`. That's expected and happens once.
- **Deprecated endpoints stay off-limits** (see CLAUDE.md): no audio-features,
  recommendations, related-artists, or editorial playlists — design around search. The
  external similarity signal those endpoints used to provide now comes from **Last.fm**
  (`lastfm.py`, Recipe 6) — but it's an *input to* the session's reasoning, never a
  black-box autopilot, and every track it suggests still passes through `search_verify`.
- **Last.fm match quality is uneven** for very obscure or very new artists: names can
  mis-resolve. The crowd similarity is a strong *idea source*, not ground truth — Spotify
  `search` remains the source of truth for whether a track exists.
- **everynoise is a frozen 2023 snapshot** (`genre-neighbors`, Recipe 7): its feeds died
  with Glenn McDonald's Spotify layoff, so genres coined since 2023 are missing and artist
  examples are stale. Use the *head* of the nearby list (closest neighbors); the tail is
  loose texture-matching. It supplies a genre-adjacency *direction* only — artists still
  come from Last.fm/session knowledge and every track still passes `search_verify`.
