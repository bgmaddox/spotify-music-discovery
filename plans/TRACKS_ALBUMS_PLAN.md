# TRACKS_ALBUMS_PLAN.md — Songs & Albums expansion for /discovery/history

Working doc for the third expansion of the taste timeline page. Artists are well
covered (river, gantt, network); this pass adds the two missing dimensions —
**albums** (completely unaggregated today) and **tracks** (only a top-150 list today)
— plus a batch of shareable "fun list" formats.

Status legend: ☐ todo ◐ in progress ☑ done

## Grounding facts (verified 2026-07-18)

- Every raw event carries `master_metadata_album_album_name` — albums exist in the
  export but are aggregated **nowhere** (not in `history_summary.json`, not in the
  timeline, not on the page). Greenfield.
- Track data in the summary is thin: `all_time_tracks` (150, with URIs and distinct
  `years`) and nothing else. The raw export supports lifelines, first-play dates,
  seasonality, and skip behavior at track level (`ts`, `reason_start`, `skipped`,
  `spotify_track_uri`).
- Track URIs → Spotify API enrichment is possible with the existing read-only client
  (`tools.py`): a track fetch yields album id + cover-art URLs; an album fetch yields
  tracklist length; track objects carry `popularity`. All batchable (50/req) and
  disk-cacheable. **No deprecated endpoints involved** (plain `/tracks`, `/albums`).
- Household exclusion must apply everywhere (shared `household.py`), same as v2/v3.

## The 12 features

### A. Albums layer
1. **"Album people or singles people?"** — detect sequential album sessions
   (runs of ≥4 consecutive plays, same album, `reason_start=trackdone`, gap <10 min).
   Per-year album-session score + list of albums genuinely played front-to-back.
2. **The record shelf** — top albums per era as a browsable shelf/crate with real
   cover art; click → that album's play story (plays by year, top track, session count).
3. **One-track wonders** — albums where one song has ≥50 plays and the rest of the
   album ≤2 plays total. List + "the rest is unexplored" discovery hook.
4. **Album completion rings** — for top ~30 albums, % of official tracklist ever
   played (ring/donut per album on the shelf detail).

### B. Song lifelines
5. **Biography of a song** — small-multiples spark-lines (monthly plays) for top
   ~100 tracks: burst, plateau, death, resurrection. Searchable like the artist gantt.
6. **"The day you met your favorite songs"** — first-ever-play date timeline for the
   all-time top tracks.
7. **Longest devotion** — tracks spanning the most distinct years (already derivable
   from `years` arrays; extend with exact first→last span).
8. **Track seasons** — tracks with ≥70% of plays inside one calendar month/season
   (min 12 plays), e.g. "this song is an October song."

### C. Fun lists
9. **The receipt** — a year as a CVS-style itemized receipt: top tracks × play
   counts, subtotal in hours, "tax" = skips, cashier 🤖, barcode footer. Year picker;
   styled for screenshot sharing.
10. **Milestone club** — total-time-inside-a-song leaderboard ("9.4 hours inside this
    3-minute song") = plays × track duration (duration from enrichment).
11. **Yearbook anthems** — one defining track per year 2015→2026 as a mixtape
    tracklist. Selection heuristic: max plays that year, tie-break by concentration
    (plays that year ÷ all-time plays). Include copyable track list so a real `🤖`
    playlist can be built in-session afterward (per RECIPES/playlist conventions —
    the page itself stays read-only, no write calls).
12. **Deep cut or hit?** — for each top artist, compare your #1 track's Spotify
    `popularity` vs the artist's most-popular track → per-artist "deep cut" badge and
    an overall contrarian score.

## Architectural decisions (made up front)

- **Cover art:** inline 64px base64 thumbnails (~3–5 KB each, cap 40 albums) so the
  page stays self-contained/offline-safe; carry the Spotify CDN URL alongside and
  progressively swap to the larger image when online. Budget: page ≤ ~800 KB.
- **Enrichment is a separate cached step** (`enrich_meta.py` + `cli.py enrich-meta`),
  NOT part of `history-build`: reads the aggregation output, fetches only what's
  missing into `.cache_spotify_meta/` (JSON per id), writes
  `data/track_album_meta.json`. Read-only scopes (`SEARCH_SCOPES = []` pattern).
  Volume ≈ 40 album fetches + ~250 track fetches — trivial, batched 50/req.
- **Data flow stays the established pipeline:**
  `history-build` (aggregation v3) → `enrich-meta` → `timeline-build` (merge) →
  `timeline-inject` → scp `docs/history.local.html`. The template
  (`docs/history.html`) stays data-free; forkers without enrichment get graceful
  stubs (same pattern as the `network` key).
- **New timeline keys:** `albums` (shelf + sessions + wonders + completion),
  `track_stories` (lifelines/first-play/seasons/devotion), `lists` (receipt data,
  milestones, anthems, deep-cut). Compact dumps; keep monthly lifeline series to
  top ~100 tracks to control size.
- **Page structure:** two new sections — **"The records"** (albums layer) and
  **"The songs"** (lifelines + fun lists as sub-views), matching the existing
  section/nav idiom. Lazy-init heavy views (same trick as the network graph).

## Phases × agent assignment

Orchestration model: this session (Fable) is the architect/orchestrator and does
design-heavy or judgment-heavy work inline; well-specified mechanical phases go to
subagents. Each phase ends with `pytest -q` green and a one-paragraph report.

| Phase | Work | Model / agent | Why this tier |
|-------|------|---------------|---------------|
| 0 ☑ | Data audit, feature list, architecture decisions (this doc) | Fable, in-session | Judgment calls |
| 1 ☑ | **Aggregation v3** — extend `streaming_history.py`: album aggregates + session detection (#1), one-track wonders (#3), per-track monthly lifelines + first-play + seasons + devotion (#5–8), per-year top tracks + receipt stats (#9), time-in-song plays basis (#10), anthem heuristic (#11). Household-excluded. Tests mirror `tests/test_streaming_history.py` style. | Sonnet subagent | Mechanical, well-specified, testable; pattern already exists (v2) |
| 2 ☑ | **Spotify enrichment** — `enrich_meta.py` (+ `cli.py enrich-meta`): batch fetch track meta (duration, popularity, album id) and album meta (tracklist length, cover URLs), download + base64 64px thumbs, cache dir, graceful offline/missing behavior. Tests with a mocked client. | Sonnet subagent | Small, isolated, API-shaped; needs care with caching not creativity |
| 3 ☑ | **Timeline merge** — `build_timeline_data.py` merges `albums` / `track_stories` / `lists` keys (graceful stubs when enrichment absent), size budget check, compact dump. Tests in `tests/test_timeline_data.py` style. | Sonnet subagent | Follows the exact pattern of the v3/network merges |
| 4 ☑ | **Front-end A: "The records"** — shelf with cover art + album detail (play story, completion ring), album-session score chart, one-track wonders card. | Fable in-session (or Opus subagent if parallelizing) | Design-heavy D3 + visual taste; the page's signature look must hold |
| 5 ☑ | **Front-end B: "The songs"** — lifeline small-multiples grid (searchable), first-listen timeline, devotion + seasons lists. | Fable in-session / Opus subagent | Design-heavy, mirrors artist-gantt idiom |
| 6 ☑ | **Front-end C: fun lists** — receipt (year picker, screenshot-ready CSS), milestone club, yearbook mixtape, deep-cut badges. | Opus subagent | Charm > novel viz engineering; strongly templated HTML/CSS work |
| 7 ☑ | **Verify + deploy** — Playwright pass (desktop + 390×844 mobile, zero console errors, template-fallback still renders), full `pytest -q`, rebuild → inject → scp, update `DEPLOY_MCP.md` / `CLAUDE.md` / `.claude/structure.md`, commit + push. | Sonnet subagent (verify) + Fable (deploy/docs/commit) | Checklist work; deploy touches the Pi so the orchestrator owns it |

Sequencing: 1 → 2 → 3 strictly serial (each consumes the last). 4/5/6 can run after
3 and are independent of each other, but they edit the same `docs/history.html` —
run serially OR give parallel subagents worktree isolation and merge. Default:
serial (4 → 5 → 6), simplest and the file is one big HTML.

## Acceptance bar

- All 12 features render with real data on `history.local.html`; bare template shows
  the fallback screen untouched.
- Album-session detection sanity-checked against at least one known full-album
  listen; one-track wonders list passes the smell test.
- Page ≤ ~800 KB; zero console errors desktop + mobile; no network calls required
  for first paint (CDN art is progressive-only).
- Full test suite green (target: +30–40 new cases across phases 1–3).
- Deployed to `/discovery/history`, docs updated, committed.
