# Taste Timeline — Interactive Musical-Taste Visualization (project plan)

> Multi-session working document. **Update the Status section as phases complete** so any
> future session can pick up mid-stream. Approved by the user 2026-07-16.

## Status

| Phase | State | Notes |
|---|---|---|
| 1. Data pipeline | ✅ done (2026-07-16) | `build_timeline_data.py` + `cli.py timeline-build` → `data/taste_timeline.json` (126 KB, 200 artists, 150 tracks, 11 years). 53 tests green (`tests/test_timeline_data.py`, 24 new). Bucket mapping reviewed; not yet committed. |
| 2. Stitch concepts | ✅ done (2026-07-16) | 3 concepts in Stitch project `736909309262027176`; screenshots in `docs/stitch_concepts/`. |
| — checkpoint | ✅ done | **User picked Hybrid A+B**: genre river as main view + era chapter captions + B's explicit "2017 — no data" divider / dimmed sparse-2015–16 treatment. Drop Stitch inventions (left nav, profile rail, "clean timeline" widget). |
| 3. Build `docs/history.html` | ✅ v2 built (2026-07-16) | 399 KB self-contained (D3 v7 + data inlined). v1 reviewed by user → v2 redesign: river is streaming-only 2018–2026; iTunes era gets its own "shelf" section; era chapters rewritten around musical moves; new all-artists bubble field (search + genre filter). All interactions verified via Playwright (0 console errors, mobile OK). |
| — checkpoint | ✅ done | User approved the v2 local preview (2026-07-16) |
| 4. Verify + deploy | ✅ done (2026-07-16) | Live at `https://rachett.tail504ae5.ts.net/discovery/history`. Caddy `@history` route added (Caddyfile backed up, validated, reloaded); `/discovery` + MCP path verified unaffected (all 200). "Taste timeline ↗" link added to the showcase tabs; `CLAUDE.md` + `DEPLOY_MCP.md` updated; committed + pushed. |

**PROJECT COMPLETE.** Future work: refresh data with `cli.py timeline-build` + re-inject +
`scp` (runbook in `DEPLOY_MCP.md`); add life-event `annotations` to the timeline JSON; merge
any newly-found iTunes Library.xml snapshots into the shelf.

Decisions log (append as they happen):
- 2026-07-16 — Deploy target: new page at `/discovery/history` on the Pi Funnel. Data: all
  layers, household toggle, genre waves. Design: Stitch explores 3 concepts. Interactivity:
  rich exploration. (User answers to planning questions.)
- 2026-07-16 — Bucket-mapping review: added "Bruce Brus" (white-noise sleep audio; Last.fm
  tags said electronic) and "Nursery Rhymes Band" to `HOUSEHOLD_ARTISTS`; rebuilt. The
  white-noise regex applies to artist names only — artists whose *tracks* are white noise
  get handled via the explicit set instead.
- 2026-07-16 — Bugfix: `_latest_taste_dump()` glob `taste_*.json` matched the module's own
  output `taste_timeline.json`, emptying the "now" panel on rebuild. Tightened to the
  timestamped pattern + regression test (suite now 54).
- 2026-07-16 — v1 design feedback (user): drop the woven-in gaps/iTunes block from the
  river — streaming-only post-2017; visualize the iTunes library separately (generalizes
  to future Library.xml imports); era cards should describe musical leanings and moves;
  add a way to browse ALL artists, not just each year's top set. → v2 implements: river
  2018–2026 only; "Before streaming" shelf panel (genre composition bar + top-artist bars,
  thin-years footnote); 5 rewritten chapters; "Every artist on record" bubble field
  (d3.pack, sized by plays, colored by bucket, search + genre-chip filter, click →
  trajectory).
- Rebuild note: `docs/history.html` is generated from an inline template + injection —
  D3 (`/*__D3__*/`) and `data/taste_timeline.json` (`__TIMELINE_JSON__`) are inlined via a
  small Python replace (see session; d3.min.js v7.9.0 from jsdelivr). If the data changes,
  re-run `cli.py timeline-build` and re-inject.

---

## Context

An interactive HTML visualization of 13 years of listening (2013–2026), built from the
project's three history layers and deployed to the Pi showcase alongside `/discovery`.

- **Deploy:** new page on the Pi (Tailscale Funnel), sibling of `docs/recipes.html`
- **Data:** all layers (iTunes 2013–14 + GDPR 2015–2026 + current taste); household/kids
  plays filterable via toggle (tagged, never deleted); genre evolution included
- **Design:** Stitch explores 3 visual concepts, user picks one, then we build it for real
- **Interactivity:** rich exploration — year scrubbing, artist trajectories, hover detail,
  Spotify links, era annotations, gap markers. Self-contained HTML with embedded JSON
  (same zero-network-dependency pattern as `docs/recipes.html`)

### What exists already (reuse, don't rebuild)

| Asset | Path | Relevance |
|---|---|---|
| Aggregated Spotify history | `data/history_summary.json` (88 KB) | `per_year` (plays/hours/skips/top-25 artists per year 2015–2026, 2017 missing), `all_time_artists` (top 200 with `by_year` — the artist-trajectory data), `all_time_tracks` (top 150 with URIs), `forgotten_favorites` |
| iTunes 2013–14 layer | `data/itunes_history.json` (11 KB) | 24.6k plays; top artists/tracks **and top genres** already computed |
| Current taste | `cli.py taste-snapshot` | top long-term artists + genres for the 2026 "now" panel |
| Genre lookup | `lastfm.py artist_tags` (cached `.cache_lastfm/`, rate-limited) | artist→tags for genre enrichment |
| Aggregation pattern | `streaming_history.py` + `tests/test_streaming_history.py` | module + test template the new builder mirrors |
| Design tokens | `docs/recipes.html` lines 8–22 | `--bg:#0a0a0c`, panels `#141418/#1b1b21`, text `#e9e9ee`; accents green `#1db954`, amber `#e3a008`, blue `#5b8def`, violet `#a274ff`; radial-glow bg; system fonts |
| Deploy pattern | `DEPLOY_MCP.md` (static-site section) | Caddy `file_server` at `/var/www/discovery`, exact-match `@discovery` matcher, `scp` deploy, no restart |

**Household artists seeding the filter:** CoComelon (1,610 plays), Pinkfong, Elmo, Bluey,
Frozen cluster (Kristen Bell / Idina Menzel / Auli'i Cravalho / Mark Mancina / Josh Gad /
Jonathan Groff), Super Simple Songs, The Wiggles, white-noise tracks (regex on name/title).

**Data gaps to render honestly:** 2017 absent entirely; 2015–16 nearly empty; the iTunes
layer is *cumulative library play counts as of the 2013/2014 snapshots*, not per-year
events — present it as an "era block", never fake per-year resolution.

---

## Phases (each sized for one agent/session; model per phase)

### Phase 1 — Data pipeline: `build_timeline_data.py` → `data/taste_timeline.json`
**Model: Sonnet** (deterministic ETL). The genre-bucket mapping (`TAG_BUCKETS`) is the one
judgment-heavy piece — the orchestrating session reviews it before it's frozen.

1. **Merge layers:** iTunes era block (2013–14, incl. its genre table) + `per_year` +
   `all_time_artists.by_year` trajectories + latest taste dump ("now" panel). Output
   < ~250 KB so it embeds cleanly.
2. **Household filter:** `HOUSEHOLD_ARTISTS` set constant; tag `household: true`, never delete.
3. **Genre enrichment:** `lastfm.artist_tags` for ~250 unique artists → `TAG_BUCKETS` maps
   messy tags to ~10–14 canonical buckets (folk/americana, country, indie rock, hip hop,
   classic rock, soul/blues, pop, electronic, metal/punk, jazz, soundtrack, kids/household,
   other). Weight per-year plays by bucket → `genre_waves`. Persist artist→bucket in output.
4. **Era annotations:** `annotations` list (year, label, note) seeded with gap notes only;
   user adds life events later. Explicit `gaps` markers for 2017 + sparse 2015–16.
5. **CLI + tests:** `timeline-build` wired into `cli.py` (thin router); fixture-based
   pytest in `tests/test_timeline_data.py` (no network) — bucketing, household tagging,
   iTunes block, genre_waves math, gap detection.

### Phase 2 — Stitch design exploration (3 concepts → user picks)
**Model: inherit (Opus-class) via the `stitch-kit:stitch-kit` agent.**

1. Design brief = real data shape + `recipes.html` tokens (the 4 accents as genre hues).
2. Three concepts in one Stitch project (desktop, dark):
   - **A. Genre river** — streamgraph 2013→2026, artist labels at peaks, year scrubber,
     2017 gap as a visible break
   - **B. Era timeline** — horizontal chapter cards per era with trajectory sparklines
     threading across, annotation captions, per-era genre bar
   - **C. Radial rings** — concentric year rings, genre-colored arcs, "now" outer ring
3. Screenshots land in `docs/stitch_concepts/concept_{a,b,c}.png`; user picks (hard gate).
   Optional one `generate_variants` round on the winner.
4. Stitch output is the **visual direction only** — the D3 build happens in Phase 3.

### Phase 3 — Build `docs/history.html` (the real thing)
**Model: Fable/Opus, main session + `frontend-design` skill** (craft-heavy, user-in-the-loop).

1. Single self-contained file like `recipes.html`: tokens copied over, embedded `TIMELINE`
   JSON const, **D3 v7 minified inlined** (~280 KB raw — fine; keeps zero network deps).
2. The picked concept with rich interactivity: year scrubber/brush; hover tooltips (plays,
   hours, rank); click artist → highlight full trajectory + Spotify link (URIs where
   available); **household toggle** (default off) recomputes the view; genre-wave layer
   with the bucket palette; era annotations as captions; gaps drawn hatched/dimmed, never
   interpolated; nav chip to/from `/discovery`.
3. Mobile-usable: responsive, touch-friendly scrubber (it's shared over the Funnel).

### Phase 4 — Verify, deploy, document
**Model: Sonnet** (mechanical but touches SSH + Caddy).

1. **Local verify:** Playwright — screenshot, exercise toggle/scrubber/artist-click, zero
   console errors.
2. **Deploy:** `scp docs/history.html rachett:/var/www/discovery/history.html`. The
   existing `@discovery` matcher is exact-match, so add (timestamped `.bak` first, then
   reload Caddy):
   ```
   @history path /discovery/history /discovery/history/
   handle @history {
       root * /var/www/discovery
       rewrite * /history.html
       file_server
   }
   ```
   Verify `curl -s -o /dev/null -w "%{http_code}" https://rachett.tail504ae5.ts.net/discovery/history`
   → 200; confirm `/discovery` and the MCP capability path still work. Page is public like
   `/discovery` (same portfolio posture) — flag to the user if they'd rather gate it.
3. **Document:** update `CLAUDE.md` progress + `DEPLOY_MCP.md` runbook; add the nav link in
   `recipes.html` and redeploy it too; commit + push (repo is private).

---

## Orchestration summary

| Phase | Worker | Model | Why |
|---|---|---|---|
| 1. Data pipeline | general-purpose agent | **Sonnet** | deterministic ETL, fully specified |
| 2. Design concepts | `stitch-kit:stitch-kit` agent | **inherit (Opus-class)** | creative direction + Stitch MCP |
| 3. Build the page | main session + `frontend-design` | **Fable/Opus** | craft-heavy D3, user-in-the-loop |
| 4. Verify + deploy | main session | **Sonnet** | mechanical, but live infra |

User checkpoints: after Phase 2 (pick a concept) and after Phase 3 local preview (before
anything touches the Pi).

## Verification (end-to-end)

- `pytest -q` green (existing suite + new timeline tests)
- `python cli.py timeline-build` → `data/taste_timeline.json` < 250 KB; spot-checks:
  CoComelon tagged household, 2017 gap present, Avett Brothers trajectory spans
  iTunes era → Spotify years
- Playwright pass on the local file (interactions + zero console errors)
- Live URL 200 over the Funnel; `/discovery` + MCP path unaffected; loads on the phone
