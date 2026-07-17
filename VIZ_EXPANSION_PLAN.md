# Taste Timeline v3 — "How You Listen" Visualization Expansion (project plan)

> Multi-session working document. **Update the Status section as phases complete** so any
> future session can pick up mid-stream. Successor to `TASTE_TIMELINE_PLAN.md` (complete);
> extends the live page at `/discovery/history`, does not replace it.

## Status

| Phase | State | Notes |
|---|---|---|
| 1. Aggregation v2 (`streaming_history.py`) | ✅ done 2026-07-16 | 7 new sections; household.py shared module; 95 tests green; 287 KB output |
| — checkpoint: bucket/mapping review | ✅ done 2026-07-16 | platform map accepted; reason_start adjusted (remote→deliberate, appload→passive); 97 tests green |
| 2. Timeline data merge (`build_timeline_data.py`) | ✅ done 2026-07-17 | `behavior`/`loyalty`/`discovery` keys in taste_timeline.json (215 KB < 220); 112 tests green; agent was cut off mid-phase, orchestrator finished the wiring + tests |
| 3a. Front-end batch 1 — "How you listen" | ✅ built 2026-07-17 | 4 views (clock/intent/platforms/seasonality) + v3 JSON re-injected (470 KB file); Playwright: 0 console errors, mobile 390px clean, old views regression-checked |
| — checkpoint: user preview | ✅ done 2026-07-18 | user approved batch 1 as-is (all 4 views, placement kept) |
| 3b. Front-end batch 2 — "Artist stories" | ✅ built 2026-07-18 | 5 views (loyalty gantt + search, rediscovery cards, obsession dots, skip lists, Claude-era panel) + 🤖 river marker; Playwright: 0 errors, mobile clean, regression pass |
| — checkpoint: user preview | ✅ done 2026-07-18 | user approved; deploy authorized |
| 4. Verify, deploy, document | ✅ done 2026-07-18 | live at `/discovery/history` (200; `/discovery` unaffected); 112 tests green; docs updated; committed |
| 5. Similarity network | ✅ done 2026-07-18 | "The shape of your taste" force graph live at `/discovery/history`; 187 nodes / 864 Last.fm edges via new `cli.py similarity-build`; 125 tests green; 0 console errors, mobile clean; user approved preview |

Decisions log (append as they happen):
- 2026-07-18 — Phase 5 as-built notes: kept it a **section on the existing page** (not its
  own page) — zero Caddy changes, inherits the visual system; the force simulation
  lazy-inits via IntersectionObserver so the rest of the page pays nothing. Data:
  `build_similarity_data.py` fetches `similar_artists` (limit 100) for the 187
  non-household timeline artists → in-set edges (match ≥ 0.05, undirected, mutual flag)
  + top-5 outside-library neighbors (match ≥ 0.3) per artist → `data/similarity_edges.json`
  (63 KB); `_load_network` merges it into the timeline's `network` key (graceful stub when
  absent). Timeline dump switched to compact JSON separators — 315 KB (indent=1 put every
  edge number on its own line) → 204 KB, *smaller than v3's 215 KB despite the new data*.
  Graph: one giant 162-node component + an 11-node cluster + 12 isolated ("float free" in
  the caption); wheel-zoom requires ⌘/ctrl and touch-zoom two fingers so the map never
  hijacks page scroll; auto-fit on simulation end (critical on mobile); 🤖-stuck artists get
  dashed green rings; node click also feeds the existing trajectory panel. Known quirk:
  `Florence + The Machine` returns no Last.fm neighbors (name form). Page: 549 KB.
- 2026-07-18 — Phase 3b as-built notes: the plan's per-year skip-rate sparkline was dropped —
  the only per-year skip series available (`TIMELINE.years`) includes household plays, which
  would contradict the section's household-excluded promise; the skip card is the two lists.
  V8's "markers on the river" became a single dashed 🤖 line at the first ledger date (all
  194 events cluster in one month). Loyalty gantt: scrollable list of all 120, respects the
  household toggle, mobile hides the years column + shows only edge axis labels.
- 2026-07-17 — Phase 2 as-built notes: clock grids compacted to 7×24 arrays (24 KB → 4 KB);
  discovery playlist URLs reduced to bare ids; "stuck" check also harvests artists from the
  taste dump's saved_tracks/recently_played (raw dumps have no known_artists key); loyalty
  entries carry a `household` flag (CoComelon is #1 all-time) so the UI can default-hide.
  Full-build tests now monkeypatch `DISCOVERY_LOG_PATH` + `_latest_taste_dump` to stay
  hermetic. Spot-checks: Avett 2018→2026 (9 active years, still_active); never-skip =
  Gillian Welch / The National / The Supremes; most-skipped = Ariana Grande 59%; discovery
  194 events / 38 stuck; folk/americana peaks in May.
- 2026-07-16 — Checkpoint review of Phase 1 normalization: platform_map accepted as built.
  reason_start map corrected: `remote` (1,122 plays) moved passive→**deliberate** (Spotify
  Connect / voice = user pressed play on another device); `appload` (899) moved
  deliberate→**passive** (auto-resume on app launch, no track chosen). Two locking tests
  added. Adjusted all-time totals: deliberate 3,410 / passive 24,643 / shuffle 12,689.
  OBSESSION_MIN_PLAYS frozen at 15 (24 episodes). household_excluded_plays = 3,094.
  Clock peak sanity: Saturday 4pm Eastern — plausible.
- 2026-07-16 — Plan approved structure: extend `history.html` (one destination), all heavy
  computation in Python (browser only draws), front-end split into two batches with user
  checkpoints. Household plays excluded **at aggregation time** for all new behavioral
  buckets (not just a UI toggle).

---

## Context

The taste timeline (`docs/history.html`, live at `/discovery/history`) currently answers
*what* the user listened to. This expansion adds the *how*: time-of-day patterns, skip
behavior, deliberate-vs-passive listening, device eras, artist loyalty/churn, rediscovery
arcs, track obsessions, and the discovery-engine's own footprint.

The GDPR export's raw events carry fields the current aggregate ignores: full timestamps,
`ms_played`, `skipped`, `shuffle`, `platform`, `reason_start`/`reason_end`. Everything in
this plan derives from those plus data already on disk.

### Hard rules for every agent on this project

1. **Never `Read` the raw export files** under `data/Spotify Extended Streaming History/`
   — 40 MB, contain IPs/device strings. Only `streaming_history.py::_iter_events` touches
   them, and only inside `history-build`.
2. **Household filter at aggregation time.** Kids/white-noise plays (see
   `HOUSEHOLD_ARTISTS` + `_WHITE_NOISE_RE` in `build_timeline_data.py`) would swamp the
   listening clock and skip stats with daytime CoComelon. All new behavioral buckets are
   computed **with household plays excluded**; record `household_excluded_plays` per
   bucket group so the omission is honest. (The existing what-you-listened-to views keep
   their UI toggle — unchanged.)
3. Existing conventions all apply: `.venv/` Python 3.13, `pytest -q` must stay green,
   fixture-based tests (no network, no raw export), `cli.py` stays a thin router,
   no recommendation logic in Python.
4. `docs/history.html` is generated-then-hand-tuned: D3 v7 + `data/taste_timeline.json`
   are **inlined** (see rebuild note in `TASTE_TIMELINE_PLAN.md`). Any data change means
   re-injecting `__TIMELINE_JSON__`. Never break self-containedness (zero network deps).

### What exists already (reuse, don't rebuild)

| Asset | Path | Relevance |
|---|---|---|
| Aggregator + tests | `streaming_history.py`, `tests/test_streaming_history.py` | extend in place; mirror its fixture pattern |
| Timeline builder + tests | `build_timeline_data.py`, `tests/test_timeline_data.py` (25) | extend; has `HOUSEHOLD_ARTISTS`, `TAG_BUCKETS`, size discipline |
| History summary | `data/history_summary.json` (88 KB) | per-year plays/hours/skips/top-25 artists, `all_time_artists.by_year` |
| Timeline data | `data/taste_timeline.json` (~127 KB) | the browser payload; budget below |
| Discovery ledger | `data/discovery_log.jsonl` + `discovery_log.py` | when Claude surfaced each artist (Phase 2 overlay input) |
| Live page | `docs/history.html` (791 lines) | design tokens, section scaffolding, bubble-field + trajectory panels |
| Deploy runbook | `DEPLOY_MCP.md` | `scp` → `/var/www/discovery/history.html`, Caddy `@history` route already exists — **no Caddy changes needed this time** |

---

## The eight visualizations (and where each is computed)

| # | View | Computed in | Drawn as |
|---|---|---|---|
| V1 | Listening clock | Phase 1 | hour × weekday heatmap, per-era selector |
| V2 | Intentionality ratio | Phase 1 | per-year stacked bars: deliberate / passive / shuffle |
| V3 | Seasonality | Phase 1 | month × genre-bucket heatmap |
| V4 | Platform eras | Phase 1 | thin per-year stacked strip under the river |
| V5 | Skip fingerprint | Phase 1 | "never skip" vs "always skip" artist panels + per-year skip-rate line |
| V6 | Artist loyalty spans | Phase 2 (from existing `by_year`) | gantt of first-seen→last-seen for top artists |
| V7 | Rediscovery arcs + track obsessions | Phase 1 (episodes) + Phase 2 | small-multiple comeback curves; obsession episode timeline |
| V8 | Discovery-engine overlay | Phase 2 (from ledger) | markers on the river + a "Claude era" panel |

Deferred: **V9 similarity network** (Last.fm edge graph) — Phase 5, separate effort.

---

## Phases (each sized for one agent; model per phase)

### Phase 1 — Aggregation v2: extend `streaming_history.py` → `history_summary.json` v2
**Model: Sonnet** (deterministic ETL, fully specified). One judgment piece — the
`platform` and `reason_start` normalization maps — gets reviewed by the orchestrating
session before freeze (checkpoint).

Add to `build_history()` (single pass, same `_iter_events` loop; household plays
excluded from all of the following — resolve household membership by importing
`HOUSEHOLD_ARTISTS`/`_WHITE_NOISE_RE` from `build_timeline_data`, or lift them into a
shared module if the import is circular):

1. **`clock`** — plays by (hour-of-day 0–23 × weekday 0–6), overall **and** per era
   (eras = the year-ranges already used by the page: 2018–19, 2020–21, 2022–23,
   2024–26 — read the exact chapter ranges from `history.html` / timeline JSON, don't
   invent). Timestamps are UTC in the export → convert to `America/New_York` before
   bucketing (`zoneinfo`, stdlib).
2. **`intentionality`** — per year: counts for `deliberate` (reason_start in clickrow /
   playbtn / search-ish), `passive` (trackdone / autoplay-ish), `shuffle` (shuffle flag
   true, counted separately, overlaps allowed — document the precedence), `other`.
   Ship the raw reason_start value counts too (`reason_start_counts` per year) so the
   normalization can be re-derived without re-reading the export.
3. **`seasonality`** — plays per calendar month (1–12) per year, per artist top-N slice
   sufficient for genre-bucket weighting in Phase 2 (persist month × artist for the
   top ~200 artists only; month totals for everyone).
4. **`platforms`** — per year: normalized platform buckets (`mobile` / `desktop` / `web` /
   `speaker_tv` / `other`) from the messy platform strings. Persist the raw
   string→bucket map used (`platform_map`) in the output for review. **Never persist raw
   platform strings beyond the map keys** (they can carry device model names — that's
   fine, but no counts keyed by raw string in the main sections).
5. **`artist_skip`** — per artist (top ~200 by plays): plays, skips, skip_rate, plus
   per-year skip totals overall. Include minimum-exposure guard (≥ 20 plays+skips) so
   the "never skip" list isn't noise.
6. **`obsession_episodes`** — track-level: for each track, monthly play counts; an
   episode = ≥ N plays within a rolling 30-day window (start N=15, tune against real
   output; expose as a module constant). Persist only the episodes (track, artist, uri
   if known from `all_time_tracks`, window start, play count) — max ~50, sorted by
   intensity. Do **not** ship raw monthly series for all 16k tracks.
7. **`rediscoveries`** — artist-level: artists with a ≥ 2-full-year play gap who
   returned after it, with per-year play series (only for those artists), gap span, and
   comeback year. Cap ~40 by total plays.
8. **Honesty metadata** — `household_excluded_plays` total + per-section notes; keep
   the existing v1 sections byte-compatible (additive change only; `snapshot()` and the
   MCP `taste_snapshot` path must not change shape).

**Output budget:** `history_summary.json` stays < 300 KB.
**Tests** (`tests/test_streaming_history.py`, fixture events — extend the existing
synthetic-event fixtures): timezone conversion, clock bucketing, intentionality
precedence, platform normalization, skip-rate guard, obsession window detection
(boundary: exactly N, window straddling month edge), rediscovery gap detection
(gap at series start/end must not count). **Acceptance:** `pytest -q` green;
`python cli.py history-build` runs clean on the real export; orchestrator spot-checks
the two normalization maps + one known fact (evening-heavy clock is plausible; CoComelon
absent from every new section).

### Phase 2 — Timeline data merge: extend `build_timeline_data.py` → `taste_timeline.json` v3
**Model: Sonnet** (deterministic merge; specified below).

1. Merge every Phase-1 section into `taste_timeline.json` under a new top-level
   `behavior` key (clock, intentionality, seasonality→**genre-bucketed** via the existing
   artist→bucket map, platforms, artist_skip, obsession_episodes, rediscoveries).
2. **V6 loyalty spans** — computed here from existing `all_time_artists.by_year`:
   first year, last year, active-year count, total plays, bucket; top ~120 artists;
   flag `still_active` (played in 2025–26).
3. **V8 discovery overlay** — parse `data/discovery_log.jsonl`: per Claude-surfaced
   artist, date first surfaced + whether it subsequently appears in the taste dump /
   history (i.e. "did it stick"). Output `discovery_events` (date, artist, playlist if
   recorded, stuck: bool). The ledger only starts mid-2026 — small; render honestly.
4. **Size budget:** final `taste_timeline.json` < 220 KB (currently ~127 KB). If over,
   trim series lengths (obsessions → top 30, rediscoveries → top 25) before trimming views.
5. **CLI:** no new subcommand — `cli.py timeline-build` picks the new sections up.
   **Tests** (`tests/test_timeline_data.py`, fixtures): loyalty-span derivation
   (single-year artist, gap artist, still-active flag), discovery-ledger parse ("stuck"
   logic, malformed-line tolerance), seasonality genre-bucketing math, size guard,
   v2-shape backward compatibility (old keys untouched).
   **Acceptance:** `pytest -q` green; rebuilt JSON validates; spot-check: an Avett
   Brothers loyalty span covers iTunes-era→2026, at least one real rediscovery looks true.

### Phase 3a — Front-end batch 1: "How you listen" section
**Model: Fable/Opus, main session + `frontend-design` skill** (craft-heavy D3,
user-in-the-loop). Batch = V1 clock, V2 intentionality, V4 platform strip, V3 seasonality.

1. New top-level section in `history.html` after the era chapters: **"How you listen"**
   — same tokens/typography; each view gets the established panel treatment.
2. V1 clock: hour × weekday heatmap (D3), era selector chips (reuse the chip pattern from
   the bubble field), local-time axis labels, a one-line auto-caption of the peak cell.
3. V2 intentionality: per-year stacked bars with a plain-English legend ("you pressed
   play" / "autoplay kept going" / "shuffle"); annotate the biggest year-over-year shift.
4. V4 platform strip: thin stacked strip aligned under the genre river's year axis.
5. V3 seasonality: month × bucket heatmap using the existing bucket palette.
6. Re-inject data (`cli.py timeline-build` → `__TIMELINE_JSON__`), keep the file
   self-contained; Playwright pass: zero console errors, interactions work, mobile
   390×844 renders. **Hard gate: user previews locally before Phase 3b starts** —
   feedback may change batch-2 treatment.

### Phase 3b — Front-end batch 2: "Artist stories" section
**Model: Fable/Opus, main session + `frontend-design` skill.** Batch = V6 loyalty gantt,
V7 rediscoveries + obsessions, V5 skip fingerprint, V8 discovery overlay.

1. **"Artist stories"** section: loyalty gantt (top ~60 visible, bucket-colored bars,
   search box reusing the bubble-field search; click → existing trajectory panel).
2. Rediscovery small multiples ("you left X in YYYY and came back in YYYY") + obsession
   episode timeline (dot per episode on a year axis, size = intensity, hover = track).
3. Skip fingerprint: two short lists ("never skip" / "most skipped", with the exposure
   guard) + per-year skip-rate sparkline.
4. Discovery overlay: markers on the main genre river at Claude-surfaced dates +
   a small "Claude era" panel (artists surfaced, how many stuck). Render the tiny sample
   size honestly ("3 weeks of data").
5. Same verification bar as 3a. **Hard gate: user preview before deploy.**

### Phase 4 — Verify, deploy, document
**Model: Sonnet** (mechanical; touches SSH but **no Caddy changes** — the
`/discovery/history` route already exists).

1. Full `pytest -q`; Playwright end-to-end on the final file (every new view + all
   pre-existing interactions still work — regression pass on the river, chapters,
   bubble field, household toggle).
2. `scp docs/history.html rachett:/var/www/discovery/history.html`; curl 200 on
   `/discovery/history`; confirm `/discovery` + MCP path unaffected.
3. Docs: `CLAUDE.md` progress entry, `DEPLOY_MCP.md` (only if the runbook changes),
   this file's Status table, mark the backlog item in `IMPROVEMENTS.md` if listed.
   Commit + push (repo private).

### Phase 5 — Similarity network (deferred; do not start without user prompt)
**Model: split.** Edge-fetch = **Sonnet** (batch `lastfm.similar_artists` over
`known_artists`, cached `.cache_lastfm/`, rate-limited, persist an edge list JSON);
force-graph build = **Fable/Opus** (likely its own page or a heavy new section — decide
then). Kept out of scope so Phases 1–4 ship on their own.

---

## Orchestration summary

| Phase | Worker | Model | Why |
|---|---|---|---|
| 1. Aggregation v2 | general-purpose agent | **Sonnet** | deterministic ETL, fully specified, fixture-tested |
| 2. Timeline merge | general-purpose agent | **Sonnet** | deterministic merge + derivations, fixture-tested |
| 3a. "How you listen" | main session + `frontend-design` | **Fable/Opus** | craft-heavy D3 in a hand-tuned file, user-in-the-loop |
| 3b. "Artist stories" | main session + `frontend-design` | **Fable/Opus** | same |
| 4. Verify + deploy | main session | **Sonnet** | mechanical, live infra, no Caddy changes |
| 5. Network (deferred) | split | Sonnet + Fable/Opus | fetch vs. craft |

Phases 1→2 are sequential (2 consumes 1's output). 3a and 3b are sequential by design
(user feedback between). No Stitch round this time: the visual system is already
established by the live page — new views inherit it.

**User checkpoints (hard gates):** after 3a local preview, after 3b local preview.
**Orchestrator checkpoints:** Phase 1 normalization maps + spot-checks before Phase 2.

## Verification (end-to-end)

- `pytest -q` green throughout (suite currently 54; expect ~75+ after Phases 1–2)
- `history_summary.json` < 300 KB; `taste_timeline.json` < 220 KB
- CoComelon/household absent from every `behavior` section; `household_excluded_plays` present
- Known-fact spot checks: clock shape plausible; ≥ 1 rediscovery and ≥ 1 obsession episode
  ring true to the user; Avett Brothers loyalty span spans eras
- Playwright: zero console errors, all new + old interactions, mobile 390×844
- Live URL 200; `/discovery` + MCP path unaffected; loads on the phone
