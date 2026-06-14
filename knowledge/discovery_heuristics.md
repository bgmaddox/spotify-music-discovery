# discovery_heuristics.md — the discovery playbook

> **What this is.** A static reference the Claude Code session reads *before* reasoning
> about recommendations. It is **strategy, not data** — a menu of *angles* for getting
> from "what the user already loves" to "something new they'll love." It keeps discovery
> repeatable across sessions and **editable by the user** (add/remove angles, note your
> own likes/dislikes inline).
>
> **How to use it.** When running a discovery recipe (RECIPES.md 1, 5, 6), don't just
> free-associate — pick 2–3 angles below, name them in your rationales, and let the angle
> dictate the candidate. "Same producer as X" is a better, more defensible pick than "this
> feels similar." Pair these angles with the live Last.fm signal (`lastfm.py`) and the
> static `genre_map.md` adjacencies.
>
> **The hard rule still applies:** every named track is a hypothesis until
> `search_verify` returns a URI. These angles generate ideas; Spotify search is truth.

---

## The discovery angles

Each angle is a *transformation* — take a seed (artist/track/scene the user loves) and
move along exactly one axis. The best ladders mix conservative angles (1–4) with reaching
ones (8–11).

### 1. Last.fm adjacency (the workhorse)
Run `similar_artists(seed)` / `similar_tracks(seed, title)`. Crowd-scrobble similarity is
the closest replacement for Spotify's dead `related-artists`. Treat high `match` (≥0.5) as
center-of-taste, mid `match` (0.2–0.5) as one-axis stretches, the long tail as left-field.
**Cross-reference:** prefer Last.fm names that *aren't already* in the taste dump — that's
the whole point (genuinely new, not resurfaced).

### 2. Tag intersection
Pull `artist_tags(seed)`. Find the 2–3 tags that define *why* the user likes this artist
(e.g. `outlaw country` + `singer-songwriter`, not just `country`). Then look for artists
that sit at the *intersection* of those tags — that's more precise than any single genre.

### 3. Producer lineage
Follow the producer/engineer, not the artist. A producer carries a sonic signature across
acts (e.g. the person who shaped a record the user loves often shaped three others they'd
love). *Source:* Discogs credits (Phase 5 fast-follow) or the session's own knowledge —
either way, **verify the resulting track**.

### 4. Label-mates
Labels curate a scene. "More from the label that put out this record" is a strong, low-risk
angle — the A&R already did taste-matching. Especially good for indie/folk/Americana where
small labels (e.g. roots/Americana imprints) have tight aesthetic identities.

### 5. Sideman / session-musician trail
Follow a *player*, not a frontperson — the fiddle player, the pedal-steel player, the
drummer. Side personnel move between bands in a scene and reveal the connective tissue a
genre tag can't. Great for roots/jazz/bluegrass where instrumentalists are the throughline.

### 6. Tour-opener & bill adjacency
Who an artist *chooses* to tour with (openers, co-headliners, festival bill neighbors) is
curator-grade similarity — they're vouching with their audience. *Source:* Setlist.fm
(Phase 5 fast-follow) or session knowledge.

### 7. Cover / sample / interpolation chains
Follow what an artist covers, who covers *them*, what they sample, who samples them. A cover
is an explicit "I love this" statement that points two directions (the coverer and the
covered). Also: the original behind a song the user loves.

### 8. Adjacent-era, same scene
Hold the scene/sound constant, move the decade. If the user loves a current outlaw-country
revival act, the genuine forebears (the '70s originals) are a one-axis stretch *backward*;
the next-gen acts are a stretch *forward*.

### 9. Adjacent-region, same sound
Hold the sound constant, move the geography. The same micro-genre often has a parallel
scene in another country/region with its own accent (e.g. American vs. UK vs. Australian
takes on the same roots sound). See `genre_map.md` for region notes.

### 10. One-axis register shift
Take a loved track and change exactly one *sonic* variable while keeping the rest: same
energy but acoustic instead of electric; same lyrics-forward writing but a female vocalist
instead of male; same tempo, sparser arrangement. Use `artist_tags` to keep the other axes
fixed.

### 11. Left-field bridge
The genuine reach: find a third artist who is plausibly downstream of *two* things the user
loves at once (a bridge between two of their clusters). Defensible because you can point to
both anchors. This is where the surprising-but-right picks live.

---

## Putting a ladder together (quick procedure)

1. From the taste dump, pick 2–4 **seed artists** that are central *and* distinct from each
   other (don't seed three artists who are basically the same).
2. For each seed, run Last.fm `similar_artists` + `artist_tags` (angles 1–2). Cache makes
   re-runs free.
3. Choose angles per rung:
   - **Center** → angle 1 high-match, angle 2 intersection.
   - **One-axis stretch** → angles 4, 5, 8, 9, or 10 (pick the axis deliberately).
   - **Left-field** → angle 7 or 11 (name both anchors in the rationale).
4. Drop anything already in `top_tracks`/`saved_tracks`/`recently_played` (unless the point
   is a deep cut). The goal is *new*.
5. Name a specific **artist + title** per pick, tag it with the angle used, then
   `search_verify`. Log misses.

---

## User preferences (edit me)

> Brett: record likes/dislikes/avoid-lists here so future sessions honor them.
> Examples to fill in over time:
- **Lean into:** _(e.g. lyric-forward writing, live/raw recordings, pedal steel & fiddle)_
- **Go easy on:** _(e.g. overproduced pop-country, very-low-energy ambient)_
- **Always worth a stretch toward:** _(e.g. older originals behind modern revival acts)_
- **Hard no:** _(e.g. holiday music, comedy tracks)_
