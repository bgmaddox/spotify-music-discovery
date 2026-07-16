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

## Recipe 8 — Bridge / morph (A → B)

Goal: a playlist that is a **path**, not a bag — it starts at artist/cluster **A** and
audibly *morphs* into artist/cluster **B** over the tracklist, so playing it start-to-finish
is a guided segue between two corners of the user's taste (or one loved artist and one
target). This is the first recipe whose deliverable is *ordered*.

**Why it's different:** every prior recipe collects an unordered set. Here the **sequence
is the product** — track _n_ has to sit between _n−1_ and _n+1_, so a wrong order breaks it.

**Steps**

1. **Pick the endpoints.** A = something central in the taste dump; B = a target (another
   cluster, a new artist, or a left-field reach). Name both.
2. **Walk the graph.** Use `similar_artists(A)` and `similar_artists(B)` and find artists
   whose similarity lists *overlap* — those are the stepping stones in the middle. Aim for
   ~8–12 stops where each is more like its neighbors than like the far endpoint.
3. **One track per stop**, chosen so the *transition* works (shared tempo/key/mood by ear,
   per `artist_tags`). Name artist + title for each.
4. **Verify** every track (`search_verify`/`verify_detail`); log misses. If a miss breaks
   the chain, find a substitute that preserves the segue, not just any track by that artist.
5. **Build in order** — pass the URIs to `build_playlist` in the walked sequence (do **not**
   sort or dedup-reorder). Report the **trail** (A → … → B) so the user sees the path.

**Multi-node morph (A → B → C → …):** each additional node adds ~10 tracks. A two-node
(A→B) chain targets ~10 tracks; three nodes (A→B→C) targets ~20; four nodes ~30; and so on.
Treat each segment as its own mini-bridge — same stepping-stone logic, just chained.

**Acceptance:** ≥8 verified tracks in a deliberate A→B order on a real private playlist,
with the stepping-stone trail reported.

---

## Recipe 9 — Sequenced set / energy arc

Goal: take a candidate set (from Recipe 1/5/6/7, or named by the user) and deliver it
**sequenced into an arc** — warm-up → build → peak → comedown — instead of a flat bag.
Think of it as a finishing pass that any "collect URIs" recipe can hand off to.

**Why it's different:** audio-features are dead to this app, so there's no tempo/energy
column to sort on. The arc is built from `artist_tags` (energy/mood signal) + the session's
own read of each track. Ordering *is* the curation.

**Steps**

1. **Gather candidates** as usual (or accept a list the user gives). Verify them first.
2. **Score each for energy/mood** — use `artist_tags` for coarse signal (e.g. `mellow`,
   `anthemic`, `driving`) and session knowledge for the specific track. A rough 1–5 energy
   tag per track is enough.
3. **Lay the arc:** open low-medium, climb to one or two peaks, ease down to a closer.
   Avoid hard whiplash between adjacent tracks (key/tempo/mood jumps).
4. **Build in that exact order** (don't let `build_playlist` reorder) and report the arc
   shape — which tracks are the warm-up, the peak, the landing.

**Optional helper:** if this gets used a lot, a tiny `sequence.py` that takes
`uri<TAB>energy` lines and prints a reasonable arc order would remove the manual ordering —
but it's not needed; the session can order by hand. Flag for later, don't build now.

**Acceptance:** a verified set delivered in a deliberate energy arc (not source order),
with the warm-up/peak/comedown structure named in the report.

---

## Recipe 10 — Deep cuts (anti-hits)

Goal: inward discovery instead of lateral. Take artists the user **already loves** and
surface their *non-single, deep-catalog* tracks they probably skipped — "you know the hits,
here's the album they're buried on."

**Why it's different:** Recipes 1/6/7 push *outward* to new artists. This pushes *inward* —
same artists, deeper catalog — using the **popularity band** the taste dump already records.

**Steps**

1. **Sense.** From the taste dump, pick ~4–6 artists in `top_artists` (favor prolific ones
   with real catalogs, not single-album acts).
2. **Propose deep cuts** — for each artist, name 2–3 album tracks that are *not* the obvious
   singles (B-sides, late-album tracks, deep catalog). Skip anything in `top_tracks`/
   `recently_played` (those are already the user's hits).
3. **Verify with `verify_detail`** — confirm the match is the right artist *and* check the
   returned `album`/name to make sure it's the deep cut you meant, not the radio edit or a
   re-recording. Treat a popular-single match as a miss for this recipe's purpose.
4. **Build** a private `🤖 ` playlist and report each track with the album it's pulled from,
   so the user sees the catalog spelunking.

**Acceptance:** ≥8 verified non-single tracks from artists already in `top_artists`, each
reported with its source album, none of them existing `top_tracks`.

---

## Recipe 11 — Covers & originals (pairs)

Goal: a playlist built from **pairs** — `[a version the user loves] → [the original it
descends from]`, or `[a song they love] → [a great cover of it]`. Promotes discovery angle 7
(cover/sample/interpolation chains) to a first-class recipe with a distinctive paired shape.

**Why it's different:** the output is *coupled* — every track earns its place by its
relationship to its neighbor, so the playlist teaches a lineage rather than just listing
songs.

**Steps**

1. **Seed from loved tracks.** Pick songs from `top_tracks`/`saved`/now-playing that are
   either *covers* (point back to an original) or *much-covered originals* (point forward to
   notable covers).
2. **Name the partner** for each — the original behind a cover, or a strong cover of an
   original. Session knowledge generates these; `similar_tracks` can help find cover versions.
3. **Verify both halves** of every pair (`search_verify`); if one half misses, either fix
   the title or drop the whole pair (a lone half breaks the concept).
4. **Build with pairs adjacent** (original immediately before/after its cover) and report
   each pairing with one line on the lineage (who covered whom, when, why it's interesting).

**Acceptance:** ≥4 verified pairs (≥8 tracks) on a real private playlist, each pair's two
halves adjacent in the tracklist and its lineage explained.

---

## Recipe 12 — Rotation / re-engagement

Goal: re-surface the user's **own** music they've drifted from — heavy in `long_term` but
faded from `short_term`. "Songs you forgot you loved." Lowest-risk recipe here: every track
is already theirs, so there's no hallucination surface and nothing new to learn.

**Why it's different:** it mines the **short_term vs long_term split** the taste dump
already captures — a signal no other recipe uses — and builds *backward* into the user's
history instead of outward.

**Steps**

1. **Sense.** Read a fresh `data/taste_*.json`. Compare `long_term` vs `short_term`
   `top_artists`/`top_tracks` (and optionally `library_scan` for older saves).
2. **Find the fade.** Artists/tracks strong in `long_term` but absent/declining in
   `short_term` = drifted-from favorites. Note a few standouts.
3. **Assemble** mostly from tracks that already carry real `id`/`uri`s in the dump (build
   `spotify:track:<id>` directly); for an artist who's faded but whose specific track isn't
   in the dump, name a representative one and `search_verify` it.
4. **Build** a private `🤖 ` playlist and report the through-line ("heavy in your long-term,
   quiet lately") so the re-engagement framing is clear.

**Acceptance:** ≥8 tracks that are strong in `long_term` but faded from `short_term`, on a
real private playlist, with the fade framing reported.

---

## Recipe 13 — Occasion in *your* style

Goal: an occasion/activity set — dinner party, road trip, Sunday morning, **Christmas** —
but built from the user's *own* taste rather than Spotify's generic editorial set. Since the
editorial/category endpoints are dead to this app (see guardrails), this is the *only* way
to get an occasion playlist, and it comes out personal instead of generic.

**Why it's different:** Recipe 5 (time machine) anchors on an *era/vibe*; this anchors on an
*occasion/function* and explicitly bends it through the user's known clusters (e.g. an
Americana Christmas, a bluegrass road-trip set — note Christmas is a real top cluster for
this user, per `discovery_heuristics.md`).

**Steps**

1. **Take the occasion** (dinner, drive, focus, holiday). Translate it into constraints:
   energy level, foreground/background, lyric density, tempo feel.
2. **Bend through their clusters.** Pull dominant genres/artists from the taste dump and
   pick tracks that satisfy *both* the occasion constraints and the user's taste — e.g.
   "warm, low-foreground, but from your roots/Americana cluster, not generic lounge."
3. **Propose** ~10–15 tracks (mix owned favorites with a few new-but-fitting picks), one
   line each on why it fits the occasion *and* the taste.
4. **Verify** every named track (`search_verify`); log misses.
5. **Build** a private `🤖 ` playlist and, optionally, **sequence it** (hand off to Recipe 9)
   since occasion sets benefit from an arc. Report the occasion framing and the taste anchor.

**Acceptance:** ≥10 verified tracks fitting both the named occasion and the user's taste, on
a real private playlist, with the occasion-through-taste rationale reported.

---

## Recipe 14 — Genre chronology / lineage (history over time)

Goal: a playlist that **teaches a genre by walking it through time** — either *evolution*
(one genre traced era by era: roots → classic period → modern revival) or *lineage* (a root
genre branching into the styles it spawned). Playing it top to bottom is a guided tour of how
the sound developed. Like Recipe 8, the **deliverable is ordered** — chronology *is* the
product.

**Why it's different:** Recipe 7 walks genre *topology* (what scene sits *next to* this one —
a spatial axis). This walks the *temporal* axis (how this scene *became* what it is). Recipe 5
(time machine) anchors on the user's own nostalgia era; this is genre-education, not personal
memory, and it deliberately includes artists the user may not know. It can sit *outside* the
taste dump entirely — the goal is a faithful arc of the genre, not strictly-new-to-you
discovery (though it should still avoid recycling the same picks via the ledger).

**The chronology comes from session knowledge, not scraped dates.** Spotify
`album.release_date` is unreliable for this — remasters and reissues report the *reissue* year,
so a 1969 track can show as 2014 and misorder the whole arc. So: Claude orders by *known era*
from its own musical knowledge; release dates from `verify_detail` are a sanity *cross-check*
(flag a wild mismatch), never the sort key.

**Steps**

1. **Pick the genre and the shape.** Name the genre and decide *evolution* (one lineage
   through time) or *lineage* (root → branches). Sketch the **era buckets** up front —
   e.g. 4–6 phases, each with a 1-line definition and its rough years.
2. **Populate each era with representative artists/tracks.** Lean on session knowledge for
   *who defines each phase* (treated as hypothesis until verified). Optionally widen a thin
   era with `similar_artists` on a known anchor (Recipe 6 step 2) or `genre-neighbors` /
   `artist_tags` to confirm an artist belongs to that phase. Aim for ~2–3 tracks per era.
3. **Pick the era-defining track per artist** — the one that *exemplifies that phase's
   sound*, not necessarily their biggest hit. Name artist + title + era for each.
4. **Verify** every track (`search_verify`/`verify_detail`); log misses. Cross-check the
   returned release date against the assigned era — if it's wildly off, suspect a reissue or
   a wrong match and confirm before keeping. If a track is missing, substitute one that holds
   the *same era slot* (don't let a gap collapse the timeline).
5. **Build in chronological order** — pass URIs to `build_playlist` in era sequence (do
   **not** let it reorder). For lineage shape, order root-first then branch by branch.
6. **Report the timeline:** the playlist URL plus the **era trail** (`era → years → artists`)
   so the user reads the arc, with a one-line gloss on what each era contributed to the genre.

**Acceptance:** ≥10 verified tracks spanning ≥3 named eras in deliberate chronological (or
root→branch lineage) order on a real private playlist, with the era trail and per-era gloss
reported.

**Variant — single-artist career arc:** the same mechanics aimed at *one artist's*
discography instead of a genre — early/breakthrough/peak/late phases, one or two tracks each,
in release order. Same date caveat (order by known album sequence, not Spotify dates); same
ordered build. Report the career-phase trail instead of an era trail.

---

## Recipe 15 — Samples & sources (origin → sample)

Goal: pair tracks with the **records they sample or interpolate** — the funk/soul/jazz break
sitting under a hip-hop song, or the old hook a modern track flips. Playing it is hearing the
DNA: source, then what was built on it.

**Why it's different:** Recipe 11 pairs *covers* (same song, new performer). This pairs a
song with a *different* song it's **built from** — a production-lineage link, not a
re-performance. For this user it also bridges the two halves of their taste (the soul/funk
source and the hip-hop that sampled it).

**Steps**

1. **Pick seeds.** A few hip-hop/electronic tracks (from the taste dump, now-playing, or
   named) whose samples you're confident about. Favor well-documented flips over obscure ones.
2. **Name the source for each** from session knowledge — the original record sampled or
   interpolated (artist + title). Treat every link as a *hypothesis* until both sides verify;
   sample facts are exactly the kind of thing the cutoff gets wrong.
3. **Order each pair source-first, then the track that sampled it** (origin → result). For a
   one-to-many source (a break sampled by several tracks), do source then its descendants.
4. **Verify both sides** of every pair (`search_verify`/`verify_detail`); log misses. If the
   *source* is missing, drop the whole pair — a sample track with no origin defeats the point.
   Watch for re-recordings/compilations that aren't the sampled master; flag if unsure.
5. **Build in pair order** (don't let `build_playlist` reorder) and **report the lineage** —
   `source → sampler` for each pair, with a one-line note on what was flipped (the break, the
   vocal hook, the bassline).

**Acceptance:** ≥5 verified source→sample pairs (≥10 tracks) in deliberate pair order on a
real private playlist, each pair's lineage and what-was-sampled noted. Low-confidence sample
claims are dropped, not guessed.

---

## Recipe 16 — Thematic thread (songs about X)

Goal: a playlist anchored on **what the songs are about** — trains, rivers, leaving town, a
named city, money, outlaws, the road — pulling across genres and eras as long as the lyrical
subject holds.

**Why it's different:** every other recipe anchors on *sound* (similarity, genre, era,
texture) or *function* (occasion). This anchors on **lyrical content**, which no audio signal
or similarity graph captures — it's purely a session-reasoning play, which makes it a clean
Mode-A fit.

**Steps**

1. **Fix the theme** — a concrete subject, not a mood (mood is Recipe 13). Sharper is better:
   "songs about leaving a small town" beats "sad songs."
2. **Range across the user's taste *and* beyond it** for tracks that genuinely treat the
   theme — span genres/eras deliberately so the thread, not the style, is the through-line.
   Mix a few owned favorites with new-but-fitting picks; note which are which.
3. **Justify the fit per track** in one line — *how* the song is about the theme (chorus,
   narrative, a key image). Drop anything that only fits via a stretch; the thread must be
   audible to the listener.
4. **Verify** every track (`search_verify`); log misses. Watch for same-title wrong songs —
   a title can match the theme by coincidence; confirm it's the song you meant.
5. **Build** a private `🤖 ` playlist; optionally **sequence** (hand off to Recipe 9) since a
   thematic set often reads as a loose narrative. **Report the thread** and the per-track
   justification so the user hears the connection.

**Acceptance:** ≥10 verified tracks that all genuinely treat one named lyrical theme,
spanning ≥2 genres or eras, on a real private playlist, with the per-track fit reported.

---

## Recipe 17 — Sound of a place (scene / geography)

Goal: a playlist that captures the sound of a **place/scene** — Muscle Shoals, Laurel Canyon,
Bakersfield, Memphis, Athens GA, Lagos, Bristol — the artists, studios, and styles that a
specific geography produced.

**Why it's different:** Recipe 7 steps between *genres*; Recipe 14 walks *time*. A scene is
**neither** — it spans genres and eras but is bound by geography and a shared local lineage
(the same studio, label, players, or city circuit). The anchor is *where*, not *what* or
*when*.

**Steps**

1. **Name the place and its window** — the scene and roughly the years it was a scene
   (Laurel Canyon ≈ late '60s–'70s; Muscle Shoals ≈ the FAME/Swampers era). One line on what
   *defined* the local sound (the studio band, the label, the venue).
2. **Populate from the scene's roster** using session knowledge — core artists plus the
   one-degree players (session musicians, the house band) that make a scene cohere. Optionally
   confirm an artist's tie with `artist_tags`/`similar_artists`; treat membership as a
   hypothesis until verified.
3. **Pick a track per artist that *sounds like the place*** — the one cut where the scene's
   signature comes through, not necessarily their biggest hit.
4. **Verify** every track (`search_verify`); log misses. Sanity-check that the recording sits
   in the scene's window (a later track by the same artist may have left the sound behind).
5. **Build** a private `🤖 ` playlist (era order is a nice default but not required) and
   **report the scene framing** — place, window, and the studio/label/players that bind it,
   plus a line per artist on their role in the scene.

**Acceptance:** ≥10 verified tracks tied to one named place/scene, with the scene's defining
thread (studio/label/players/venue) reported and each artist's tie to it noted, on a real
private playlist.

---

## Recipe 18 — Family tree (personnel graph)

Goal: start from one band/artist the user loves and branch out along **who played with whom**
— members' side projects and solo work, supergroups, the producer's other records, the
session players' day jobs. A people graph, not a sound graph.

**Why it's different:** every similarity recipe (1, 6, 7) walks a *sonic/co-listening* graph.
This walks a **personnel** graph — connections that are often sonically *surprising* (a
metal drummer's jazz side project), which is the whole appeal. It's the recipe most likely to
land somewhere you'd never reach by "sounds like."

**Steps**

1. **Pick the root** — a band/artist with a real web of personnel (members, frequent
   producer, notable session players). Single-person acts with no collaborators are poor roots.
2. **Walk the personnel edges** from session knowledge: each member's other bands/solo work,
   supergroups they joined, the producer's signature records, recurring session players. Note
   the *relationship type* for each hop (ex-member, producer, side project).
3. **One track per node**, chosen to *show the connection* (often deliberately different from
   the root's sound — that contrast is the point). Treat every personnel claim as a hypothesis
   until verified — credits are exactly what the cutoff gets wrong.
4. **Verify** every track (`search_verify`/`verify_detail`); log misses. If a personnel link
   turns out shaky on reflection, drop it rather than ship a wrong connection.
5. **Build** a private `🤖 ` playlist and **report the tree** — `root → node (relationship)`
   for each branch, so the user sees *why* each track is connected, not just that it is.

**Acceptance:** ≥8 verified tracks reached from one root via stated personnel links (≥3
distinct relationship types), on a real private playlist, with the relationship named for
each branch and low-confidence links dropped.

---

## Recipe 19 — Far cry (deliberate anti-bubble)

Goal: a deliberate **maximum-distance** stretch — tracks chosen to sit as far from every
cluster the user owns as possible, while still offering one real handhold so it's a stretch,
not noise.

**Why it's different:** Recipes 6 and 7 step *one scene over* (adjacent, comfortable). This is
the anti-recipe — it aims for the parts of the map the taste dump *never* touches (genre,
language, era, culture). The discipline is that "far" must still be *defensible*, not random.

**Steps**

1. **Map the bubble.** From the taste dump, name the clusters the user lives in (their top
   genres/regions/eras). The targets are the *negative space* — what's conspicuously absent.
2. **Pick far targets** — genres/scenes/traditions with little or no overlap with the bubble
   (e.g. for a roots+hip-hop listener: Carnatic classical, Norwegian black metal, Japanese
   city pop, Tuvan throat singing). Use `genre-neighbors` *in reverse* (look at the tail/
   distant entries) or session knowledge of what's genuinely far.
3. **For each pick, find the one handhold** — the single element that lets *this* listener in
   (a groove, a melodic hook, a production touch that rhymes with something they love). No
   handhold, no pick; that's the line between a stretch and noise.
4. **Verify** every track (`search_verify`); log misses. Cross-check against the taste dump
   *and* the ledger so "far" is actually far (not something already surfaced).
5. **Build** a private `🤖 ` playlist and **report the reach** — for each track, name *how far*
   it is from the user's map *and* the handhold that earns its place.

**Acceptance:** ≥8 verified tracks drawn from genres/scenes with no overlap in the taste dump,
each with a stated handhold connecting it to the user's taste, on a real private playlist.

---

## Recipe 20 — Rediscovery (abandoned-lane revival)

Goal: mine a **historical listening record** — an old iTunes library export
(`data/itunes_history.json`), and eventually the GDPR extended-history export — for a whole
*lane* the user once lived in and later abandoned, then reopen it: a few genuine drifted
favorites as **anchors**, extended with era-neighbors they never dug into.

**Why it's different:** Recipe 12 re-surfaces fades within the API's shallow window
(`long_term` vs `short_term` — months). This reaches *years* further back, to taste the
current profile has no memory of at all, and it doesn't just resurface — it uses the old
lane as a **seed for new discovery** (nostalgia as the handhold).

**Steps**

1. **Sense the history.** Read the historical layer (`data/itunes_history.json` — play-count
   weighted). Compare against the current taste dump: which heavy old clusters have *no*
   presence in today's `known_artists`? That's an abandoned lane.
2. **Pick the lane and its anchors** — 3–5 tracks the user demonstrably loved (high play
   counts), now absent from current taste. These are resurfaced on purpose (the nostalgia
   hook), so the usual "no known artists" filter is deliberately waived *for anchors only*.
3. **Extend with era-neighbors.** `similar_artists` off the anchors; filter candidates
   against BOTH current `known_artists` and the discovery ledger — the *extensions* must be
   genuinely new. Aim for roughly 1 anchor : 3 new neighbors.
4. **Verify** everything (`search_verify`); log misses (old catalog gaps are real — some
   2010-era acts are thin on Spotify).
5. **Build with anchors interleaved** — alternate a known anchor with a cluster of new
   neighbors so the familiar keeps vouching for the unfamiliar. Report which tracks are
   anchors (yours, drifted) vs. neighbors (new), and the play-count evidence for the lane.

**Acceptance:** ≥3 anchors with historical play-count evidence + ≥8 verified genuinely-new
era-neighbors, interleaved on a real private playlist, with the abandoned-lane story reported.

---

## Recipe 21 — New-release radar

Goal: surface **music released in the last ~6 months** that fits the user's lanes — the one
axis no other recipe touches. A personal replacement for Spotify's dead editorial Release
Radar, reasoned from *your* clusters instead of a black box.

**Why it's different:** every other recipe is era-agnostic or backward-looking. This one is
pinned to *now* — and since the session's music knowledge has a training cutoff, it's the
recipe where Spotify search does the most work: the session proposes **lanes and artists to
check**, and search (with `year:` filters and artist-album lookups) is the ground truth for
what actually just dropped.

**Steps**

1. **Sense.** From the taste dump, list the top ~10 artists plus 5–10 Last.fm-adjacent
   artists (Recipe 6 filtering) worth watching.
2. **Check for fresh releases.** For each, query Spotify search with a year filter (e.g.
   `artist:"X" year:2026`) or pull the artist's latest album/single via the API. **Do not
   name a "new release" from session knowledge alone** — post-cutoff releases are exactly
   what the session can't know; search results are the only source of truth here.
3. **Filter to genuinely fresh:** released inside the window (~6 months), not already in
   `recently_played`/saved, not in the ledger.
4. **Pick per artist** the strongest fresh track (lead single or a standout album cut) and
   **verify** normally.
5. **Build** a private `🤖 ` playlist, dated in the name (e.g. "New lanes — Jul 2026") so
   re-runs become a series. Report each track's release date and why that artist was watched.

**Acceptance:** ≥8 verified tracks all released inside the stated window, each tied to a
watched artist (owned or adjacent), release dates reported. Re-runnable monthly.

---

## Recipe 22 — Alive (definitive live cuts)

Goal: for songs the user already loves, find the **superior live recording** — the version
where the song became what it was meant to be. Zero-risk discovery (same songs, new skin)
aimed straight at a stated preference: *live / raw energy over studio polish*.

**Why it's different:** Recipes 10/12 go deeper or backward in the catalog; Recipe 11 pairs
different performers. This keeps the same artist *and* song and swaps the **recording** —
an axis nothing else uses, and the only recipe built on a documented user preference from
`discovery_heuristics.md`.

**Steps**

1. **Seed from loved tracks** (taste dump / library scan), favoring artists known as live
   acts (jam-adjacent roots, soul revues, harmony bands).
2. **Name the live version** from session knowledge — the specific live album or famous
   recording (venue/year), not "any live take." Treat each as a hypothesis.
3. **Verify with `verify_detail`** and check the returned *album*: it must be a real live
   release, not the studio cut, a re-master, or a random "Live" playlist edit. Wrong album =
   miss.
4. **Build** a private `🤖 ` playlist; sequencing like a set list (openers → peak → encore)
   is a natural fit (hand off to Recipe 9). Report each track's live source (album, venue,
   year) and what the live take adds.

**Acceptance:** ≥8 verified tracks that are genuine live recordings of songs the user
already loves, each with its live source named, none of them studio versions.

---

## Recipe 23 — Answer songs & feuds (musical dialogues)

Goal: pairs of songs **in conversation** — one written in response to the other. Answer
songs, diss tracks, rebuttals, tributes-with-teeth ("Southern Man" → "Sweet Home Alabama").
Playing the pair is hearing both sides of an argument.

**Why it's different:** Recipe 11 pairs re-performances; Recipe 15 pairs production lineage.
This pairs **dialogue** — the link is what the lyrics *say to each other*, not shared audio.
It also bridges the user's roots and hip-hop halves naturally (both traditions run on
answer records).

**Steps**

1. **Collect dialogues** from session knowledge: classic answer-song pairs, hip-hop
   beef exchanges, country/rock rebuttals. Favor well-documented exchanges; treat every
   claimed link as a hypothesis (this is exactly the kind of lore the cutoff garbles).
2. **Anchor at least a few pairs in the user's taste** (one side by an artist they know);
   the rest can be canon-famous exchanges worth knowing.
3. **Order each pair statement-first, answer-second.** For multi-round feuds, keep the
   volley order.
4. **Verify both sides**; if either side misses or the link feels shaky on reflection,
   drop the whole pair — half a conversation is worse than none.
5. **Build in pair order** (no reordering) and **report each dialogue** — who fired first,
   what the answer answers, one line of the backstory.

**Acceptance:** ≥4 verified pairs (≥8 tracks) in statement→answer order on a real private
playlist, each exchange's backstory told, low-confidence links dropped.

---

## Recipe 24 — Class of 19XX (single-year cross-section)

Goal: freeze **one year** and cut across *all* the user's clusters — what country, soul,
hip-hop, jazz, and indie folk each sounded like in, say, 1972 or 1997. A vertical slice of
music history filtered through their map.

**Why it's different:** Recipe 14 walks time *longitudinally* (one genre, many years); this
holds the year fixed and walks *sideways* across genres. Recipe 5 anchors on the user's own
nostalgia; this can pick any year — including one suggested by the iTunes historical layer
("your 2010, across every lane").

**Steps**

1. **Pick the year** (user-named, or propose one that was strong across several of their
   clusters). State it up front.
2. **One or two tracks per cluster**, each actually *released* that year — session
   knowledge proposes, but year-claims are hypothesis until checked.
3. **Cross-check the year** via `verify_detail`'s album/release info, with the Recipe 14
   caveat: reissues report reissue dates, so a mismatch means *investigate*, not
   auto-drop — confirm the original release year before keeping or cutting.
4. **Verify** everything; **build** a private `🤖 ` playlist (grouping by cluster reads
   well). **Report the slice:** the year, and per cluster what that scene was doing that
   year in one line.

**Acceptance:** ≥10 verified tracks all originally released in the named year, spanning ≥4
of the user's clusters, with the per-cluster year-story reported.

---

## Recipe 25 — Title chain (the wordplay game)

Goal: a playlist that is a **puzzle** — each track's title connects to the next by a stated
rule (shared word; last word → first word; or the titles read as a sentence). The listener
can spot the game from the tracklist alone.

**Why it's different:** the constraint is **textual, not musical** — pure session reasoning,
which makes it the most Mode-A recipe in the book. Musical coherence is the *secondary*
constraint: the chain must still play well, filtered through the user's taste.

**Steps**

1. **Fix the rule** and say it in the description (subtly — half the fun is spotting it).
2. **Draft the chain** ~10–15 titles long, drawing mostly from the user's clusters so it
   sounds like their playlist, not a gimmick reel. Every link must satisfy the rule
   *exactly* (no "close enough" — a broken link kills the game).
3. **Verify** every track; a miss breaks the chain, so re-solve from the broken link (find
   a substitute title that satisfies both neighbors) rather than just dropping.
4. **Build in chain order** (order *is* the puzzle) and **report the rule + the chain**
   with the linking word highlighted per hop.

**Acceptance:** ≥10 verified tracks in an unbroken chain under one stated rule, in chain
order on a real private playlist, the rule and every link reported.

---

## Recipe 26 — The concept album (narrative sequence)

Goal: sequence tracks from *different* artists so the **lyrics tell one continuous story**
— meet → fall → fracture → leave → look back. A concept album assembled from other people's
songs, aimed at the user's storyteller spine.

**Why it's different:** Recipe 16 is one static lyrical subject, unordered. This is a
**narrative with an arc** — each track is a *chapter*, and order is load-bearing (like
Recipes 8/14, but the through-line is story, not sound or time).

**Steps**

1. **Outline the story** first: 5–7 named chapters, one line each ("the leaving," "the
   first doubt," "the return"). The outline is the spec the tracks must fit.
2. **Cast each chapter** with a track whose lyrics genuinely carry that beat — lean on the
   user's lyric-forward clusters (narrative songwriters are the natural casting pool). One
   line per track on *how* its lyrics tell that chapter.
3. **Check the seams:** adjacent tracks should also work musically (no mood whiplash that
   breaks immersion) — Recipe 9's arc thinking applies inside the narrative order.
4. **Verify** everything; a missed track means re-casting that chapter, not skipping it (a
   missing chapter breaks the story).
5. **Build in chapter order** and **report the story** — the chapter outline with each
   track's casting rationale, so the user can read the album like liner notes.

**Acceptance:** ≥8 verified tracks in deliberate chapter order telling one stated story
arc, with the chapter outline and per-track casting reported.

---

## Recipe 27 — Cross-cluster duets

Goal: collaborations where the artists on **one track** come from *different* corners of
the user's taste — roots × hip-hop, jazz × indie, soul × country. The bridge isn't inferred;
it's literally recorded.

**Why it's different:** angle 11 (left-field bridge) finds a third artist *plausibly*
downstream of two clusters. Here the connection is **on the record** — a feature credit or
duet — so every pick is self-evidencing. The rarest shape in the book: one track, two
anchors.

**Steps**

1. **Name the cluster pairs** worth bridging from the taste dump (pick 2–4 pairings).
2. **Collect collab tracks** from session knowledge: features, duets, one-off pairings
   where each side maps to one of the user's clusters. At least one side should be an
   artist they know; both sides is even better.
3. **Verify with `verify_detail`** and confirm the *credited artists* on the returned track
   actually include both names (features are exactly where search matches drift — a solo
   version or a cover of the duet is a miss).
4. **Build** a private `🤖 ` playlist and **report each pairing** — which two clusters it
   bridges and which side is the user's anchor.

**Acceptance:** ≥8 verified tracks, each with both credited artists confirmed and mapped to
two different clusters of the user's taste, pairings reported.

---

## Recipe 28 — Before they were them (debuts & first recordings)

Goal: the **earliest recordings** of artists the user loves — debut singles, first-album
deep openers, pre-fame bands — back when they sounded different. The hook is *origin*: hear
the artist before the sound the user fell for existed.

**Why it's different:** Recipe 10 digs for *obscure* tracks anywhere in the catalog; the
career-arc variant of Recipe 14 spans a whole discography. This takes exactly **one slice —
the beginning** — and the payoff is contrast with the version of the artist the user knows.

**Steps**

1. **Pick ~6–8 loved artists** with real history (a debut that predates their known sound;
   artists whose first record *is* their sound are poor picks — no contrast, no story).
2. **Name the earliest recording** from session knowledge — debut single, first-album cut,
   or the pre-fame band (which adds a Recipe 18 personnel flavor). Hypothesis until
   verified.
3. **Verify with `verify_detail`** and sanity-check the album: early catalog is rife with
   re-recordings and anthology masters — prefer the original release; flag it if only a
   re-record exists.
4. **Build** a private `🤖 ` playlist and **report the then-vs-now** per artist: what year,
   what they sounded like then, and what changed on the way to the artist the user loves.

**Acceptance:** ≥6 verified early recordings of artists in the user's taste, each with its
year and a then-vs-now line reported, re-recordings flagged.

---

## Recipe 29 — Forgotten-favorites revival (deep history)

Goal: bring back tracks the user **provably loved and then dropped** — seeded from the
GDPR extended streaming history (real per-play counts, 2015→present), not the API's
recency-weighted windows or session guesses. The hook is *evidence*: every pick is the
user's own most-played track by an artist they've gone silent on.

**Why it's different:** Recipe 20 revives an *abandoned lane* reconstructed from the old
iTunes library (pre-Spotify, inferred); this works from **measured Spotify plays** — the
`history-snapshot` digest names the artists, the peak years, and the exact tracks with
counts. Zero hypothesis about what the user liked; the only judgment is curation.

**Steps**

1. **Refresh the layer** if a newer export landed: `cli.py history-build`; then read
   `cli.py history-snapshot` — its `forgotten_favorites` block lists artists with ≥40
   lifetime plays and no plays in the last 2 calendar years (knobs in
   `streaming_history.py`).
2. **Filter non-taste plays:** white noise, kids' music, film scores, Christmas — the
   household layer is heavy in this history (CoComelon is the #1 all-time artist).
3. **Pick each artist's signature track** — their most-played in the export (a targeted
   pass over `_iter_events` gets per-artist track counts; the summary's top-150 won't
   cover the tail artists).
4. **Verify every URI via `search_verify`** even though the export carries URIs — old
   events can point at delisted/re-released editions; the search result is canonical.
5. **Build** a private `🤖 ` playlist, sequence by mood arc (not by play count), and
   report each track's lifetime plays + peak year — the receipts are the story.
6. **Log to the ledger** with the recipe tag so later re-runs don't repeat an edition.

**Acceptance:** ≥10 verified tracks, each a genuine past favorite (real play counts cited),
none played in the quiet window, non-taste household plays excluded.

---

## Notes & guardrails

- **Knowledge-cutoff guardrail:** the session's music knowledge has a training cutoff.
  Treat any track you name as a *hypothesis* until `search_verify` returns a URI.
- **Dedup across sessions:** the taste dump shows what the *user* already knows; the
  discovery ledger (`cli.py log-artists`) shows what *Claude* has already surfaced in past
  sessions. Filter new candidates against both so a good lateral pick isn't recycled weeks
  later. After building a playlist, record the picks: `cli.py log-add --from-tsv picks.tsv
  --recipe N --playlist URL` (one `artist<TAB>title<TAB>uri` per line).
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
