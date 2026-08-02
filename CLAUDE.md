# CLAUDE.md — Spotify Music Discovery

Personal single-user music-discovery toolkit. Spotify's algorithmic endpoints are
deprecated for this app, so the recommendation reasoning lives in the Claude Code
session, not in a Spotify endpoint. Python is a dumb sensing + acting layer.

## Progress (see plans/claude_initial_plan.md for full phase specs)
> Open backlog / deferred ideas live in `IMPROVEMENTS.md` (e.g. GDPR extended-history import, waiting on Spotify's export).

- **Phase 0 — done.** Scaffolding + auth complete. OAuth works (user: bgmaddox).
  Probe confirmed deprecated endpoints are dead: `audio-features` → 403,
  `recommendations` → 404. The hard constraint holds.
- **Phase 1 — done.** `taste_profile.py` dumps taste data to `data/taste_*.json`.
- **Phase 2 — done (tooling).** `tools.py` exposes `search_verify` / `verify_detail` /
  `build_playlist` (lib + CLI). `RECIPES.md` documents the discovery-ladder recipe.
  Playlists use this app's own creds via Spotipy (not the Claude connector) for a single
  auth/codepath. One superset scope set re-auths once for `playlist-modify-private`.
  Acceptance (build a real ≥7-track playlist from the user's data) is run in-session.
- **Phase 3 — done (tooling).** `sensing.py` exposes `now_playing` / `library_scan`
  (lib + CLI). `RECIPES.md` adds recipes 2–5 (now-playing companion, taste report +
  blind spots, library archaeologist, time machine). `now_playing` uses a minimal
  `user-read-currently-playing` scope; that scope was added to `tools.py`'s SCOPES
  superset so the single Spotipy `.cache` re-auths once and never churns (minimal
  read scopes stay a subset of the cached superset). Verified in-session:
  `library_scan` → 259 saved tracks, `now_playing` → clean (no 403s).
- **Phase 4 — done.** `cli.py` is a thin router over all primitives (`dump-taste`,
  `search-verify`, `build-playlist`, `now-playing`, `library-scan`) — no new logic, just
  one uniform entry point; stdout = machine result (path/URI), stderr = human notes.
  Cache polish: `dump-taste --max-age MIN` reuses the newest `data/taste_*.json` if it's
  younger than MIN minutes (`--force` always refetches). Verified all five subcommands run
  clean (no 403s): fresh `dump-taste` → 50/50/50/259, cache reuse hit, `search-verify` and
  `now-playing` resolved real tracks. The per-module CLIs still work and are equivalent.
- **Phase 5 — done (tooling).** `lastfm.py` restores the external similarity signal that
  Spotify's dead `related-artists`/`recommendations` provided: `similar_artists` /
  `similar_tracks` / `artist_tags` (lib + CLI), disk-cached to `.cache_lastfm/` (7-day TTL)
  with client-side rate limiting. Uses only `LASTFM_API_KEY` (read methods; the secret is
  unused). Three subcommands wired into `cli.py`. `knowledge/` library added —
  `discovery_heuristics.md` (the menu of discovery angles) + `genre_map.md` (static genre
  adjacencies seeded for the Americana/indie-folk clusters), read before reasoning.
  `RECIPES.md` adds Recipe 6 (Last.fm-seeded lateral ladder). Verified in-session: all three
  CLI subcommands return real data with caching; Recipe 6 chain (gather → filter-to-new →
  `search_verify`) run end-to-end: seeded from Isbell/Avett/Sturgill/Carlile, surfaced 58
  genuinely-new candidates (filtered vs. 307 known artists), built a real 10-track private
  playlist ("Lateral roots — Last.fm ladder"), 0 verify misses. Acceptance bar cleared.
- **Phase 6 — DEPLOYED (Mode C), 2026-06-14.** `mcp_server.py` is a read-only FastMCP
  server (`streamable-http`) exposing the discovery primitives (`lastfm_*`,
  `taste_snapshot`, `search_verify`, `now_playing`) as tools and the knowledge base
  (`RECIPES.md`, `knowledge/*.md`) as `knowledge://` resources, so the Claude **mobile app**
  can drive discovery from a phone. No write tools — playlist writes stay with Claude's
  built-in Spotify connector. Live at `https://rachett.tail504ae5.ts.net/discovery-mcp`.
  - **As-built differs from the original plan:** the Pi already had **Tailscale Funnel +
    Caddy** running a sibling Node Spotify MCP server (playback/writes, on `/mcp`), so we
    mirrored that proven path instead of standing up Cloudflare. Ours is additive on
    `/discovery-mcp`, port 8890, dir `apps/SpotifyDiscoveryMCP`, service
    `spotify-discovery-mcp.service`, proxy-auth mode (`MCP_TRUST_PROXY_AUTH=1`), bound to
    127.0.0.1.
  - **Auth = capability URL (no bearer).** First gated it with a static bearer at Caddy,
    but Claude's managed connector only supports OAuth (DCR/PKCE) or no-auth — no
    bearer/header field — so the bearer 401'd ("couldn't register with the sign-in
    service"). Switched to **no-auth at an unguessable secret path** (`MCP_PATH` =
    `/discovery-mcp-<32-char secret>`; Caddy routes only that path to :8890). Proportionate
    for read-only music-taste data; the secret in the URL is the credential. Cloudflare
    Access was ruled out (its machine auth is header service-tokens the connector can't
    supply either). Real OAuth remains the free upgrade path if wanted.
  - **Three deploy-time code fixes** (all committed, default/local behavior unchanged):
    `MCP_TRUST_PROXY_AUTH` + `MCP_PATH` (run naked behind a proxy at a custom path);
    `MCP_ALLOWED_HOSTS` → `TransportSecuritySettings` (the transport's Host-header check
    421'd proxied requests until the public host was whitelisted); `SPOTIPY_NONINTERACTIVE`
    (headless Spotipy would block forever on the OAuth prompt — now fails fast).
    `mint_pi_cache.py` mints a read-only Spotify `.cache` without touching the local
    superset cache. Full as-built runbook in `DEPLOY_MCP.md`.
  - **Verified live through the funnel:** auth gates (401 without/with wrong bearer),
    `initialize` 200, `tools/list` = 6 tools. ALL SIX work: `taste_snapshot` + `lastfm_*`
    return real data; the read-only Spotify `.cache` was minted via `mint_pi_cache.py`
    (scope `user-read-currently-playing` only) and copied up, so `search_verify` (e.g.
    Tyler Childers "Feathered Indians" → real URI) and `now_playing` resolve too. All six
    verified through the funnel via the capability URL with **no auth header**. Connector
    added on claude.ai (syncs to mobile) — **live on the phone, tools confirmed showing.**
  - **Daily taste refresh (autonomous).** `spotify-discovery-refresh.timer` runs
    `cli.py dump-taste` on the Pi daily ~04:00 (`Persistent=true`, catches up after
    downtime); `prune_dumps` keeps the newest 5. Needs a `.cache` minted with `--read-all`
    (the 3 taste read scopes + currently-playing; still no write scopes), so the Pi token
    is now read-only-everything rather than currently-playing-only — a small, write-free
    blast-radius bump that lets the Pi self-refresh. Verified: timer run wrote a fresh dump
    (50/50/50/259) and `taste_snapshot` served it through the connector.
- **Hardening pass — done.** Five improvements landed together: (1) **tests** — `tests/`
  (pytest, 26 cases) locks the pure/fragile logic with no network/auth: Last.fm dict-vs-list
  collapse + numeric coercion, the everynoise `_NEARBY` regex + seed dedup, `_best_track`
  fielded→loose fallback, the MCP artist-normalization regression, and the discovery ledger.
  Run `pytest -q`. (2) **MCP read-only token** — `search_verify`/`verify_detail` now default to
  `SEARCH_SCOPES = []` (search needs no scope), so the public Pi box never holds a
  write-capable token; `DEPLOY_MCP.md` Step 1 updated to seed `.cache` read-only. (3) **Discovery
  ledger** — `discovery_log.py` (`log-add`/`log-artists`/`log-recent`) records what Claude has
  already surfaced across sessions → `data/discovery_log.jsonl`; filter new candidates against
  BOTH the taste dump (what the user knows) and the ledger (what Claude already proposed).
  **Always log discoveries with `log-add --new-only`** — it drops seeds/sample-sources/
  rediscovery picks (any artist already in `known_listened_artists()` = history all-time ∪
  newest taste dump) so only genuinely-new artists land in the ledger; logging whole
  playlists unfiltered is what mislabeled long-time favorites (Childers, Sturgill, Kendrick…)
  as "found" and inflated the timeline's "surfaced" count (audited + purged 2026-07-18,
  194→156). **The guard had a blind spot until 2026-07-27:** `known_listened_artists()`
  walked `top_artists`/`saved_tracks`/`recently_played` but never `top_tracks`, so an artist
  known only through individual songs (Gov't Mule, in short- *and* medium-term top tracks)
  still logged as a genuine discovery. Fixed + locked by two regression tests in
  `tests/test_discovery_log.py`; the known set grew 420→436. Spot-check `--new-only`'s
  "skipped" line against the taste dump when a pick looks suspiciously familiar.
  (4) **CLI drift fixed** — `genre-find` is now exposed in `cli.py` (was module-only). (5)
  **Hygiene** — dumps self-prune to newest 5 (`prune_dumps`), Last.fm CLI prints clean errors
  instead of tracebacks, `import html` hoisted in `genre_map.py`. All five primitives + new
  commands verified clean.
- **Extended history layer — done, 2026-07-16.** The GDPR Extended Streaming History
  export arrived (2015→2026, ~49k events, ~40 MB, gitignored under `data/`).
  `streaming_history.py` aggregates it once into `data/history_summary.json` (~88 KB);
  sessions read only `cli.py history-snapshot [--year YYYY]` (~2k tokens: per-year top
  artists, true all-time counts, forgotten favorites). **Never read the raw export
  files** — 40 MB and they contain IPs/device strings; re-run `history-build` if a
  newer export lands. ~~Known gaps: 2017 absent, 2015–16 nearly empty~~ — **closed
  2026-07-28 by the Apple Music layer below**; the Spotify export alone still has those
  gaps, so always reason from the merged `history_summary.json`, never from Spotify-only
  counts. Before that, the pre-2018 record was only the iTunes 2013–14 layer.
  Caveat: a heavy kids-music layer (CoComelon = #1
  all-time artist) is household plays, not taste signal — filter it out when reasoning.
  Tests in `tests/test_streaming_history.py`.
- **Taste timeline page — DEPLOYED, 2026-07-16.** `docs/history.html` is an interactive
  visualization of 13 years of listening, live at
  `https://rachett.tail504ae5.ts.net/discovery/history` (own Caddy exact-match route →
  `/var/www/discovery/history.html`; linked from the showcase tabs). Self-contained
  (~400 KB): D3 v7 + `data/taste_timeline.json` inlined, zero network deps. Views:
  genre-river streamgraph (streaming years 2018–2026 only), clickable era chapters,
  focused-year + artist-trajectory panels, an all-artists bubble field (search + genre
  filter), and a separate "Before streaming" iTunes-library shelf (2013–14; extendable if
  more Library.xml snapshots turn up). 2015–17 are reported as thin/absent, never drawn.
  Data side: `build_timeline_data.py` + `cli.py timeline-build` merge the history summary,
  iTunes layer, and newest taste dump into `data/taste_timeline.json` (~127 KB) with a
  Last.fm tag→bucket genre mapping (`TAG_BUCKETS`) and a `HOUSEHOLD_ARTISTS` tag (UI
  toggle, hidden by default). Design explored via Google Stitch (3 concepts, user picked a
  hybrid; reference PNGs in `docs/stitch_concepts/`). Working doc: `plans/TASTE_TIMELINE_PLAN.md`;
  redeploy runbook in `DEPLOY_MCP.md`. Tests in `tests/test_timeline_data.py` (25).
- **Taste timeline v3 ("How you listen" expansion) — DEPLOYED, 2026-07-18.** Two new
  sections on `/discovery/history` built from previously-unused GDPR export fields
  (timestamps, `skipped`, `shuffle`, `platform`, `reason_start`). **"How you listen"**:
  hour×weekday listening clock with era chips (peak: Saturdays ~4 pm), autopilot-vs-intent
  stacked bars (only 8% of plays are deliberately chosen), device share per year, and a
  genre×month seasonality heatmap. **"Artist stories"**: loyalty-span gantt (all 120 top
  artists, searchable), rediscovery cards (left/came-back), obsession-episode dot timeline
  (top: OK Go "Get Over It", 35 plays in 30 days), never-skip/quick-to-skip lists, and a
  "Claude era" panel from the discovery ledger (194 surfaced, 20% take rate) plus a 🤖
  marker on the river. Data side: `streaming_history.py` v2 emits 7 behavioral sections
  (all **household-excluded at aggregation**; shared `household.py` module;
  `reason_start` map: remote=deliberate, appload=passive; `OBSESSION_MIN_PLAYS=15`);
  `build_timeline_data.py` merges them into `behavior`/`loyalty`/`discovery` keys
  (215 KB JSON, clock grids compacted to 7×24 arrays). Page is ~485 KB self-contained;
  112 tests green. Working doc: `plans/VIZ_EXPANSION_PLAN.md` (Phase 5 similarity network
  deferred). Redeploy unchanged: rebuild → re-inject `__TIMELINE_JSON__` → `scp`.
- **Similarity network ("The shape of your taste") — DEPLOYED, 2026-07-18.** Phase 5 of
  `plans/VIZ_EXPANSION_PLAN.md`: a lazy-initialized D3 force-directed map on `/discovery/history`
  of all 187 non-household artists linked by 864 Last.fm similarity edges — clusters read
  as scenes (americana mass, hip-hop island, soul corridor; 12 artists float free). Click a
  node → in-library neighbors ranked by match **and** a "Just beyond the edge" card of
  similar artists NOT in the library (the discovery frontier, linked to Spotify search);
  search, genre chips, node drag, pinch/⌘-scroll zoom (never hijacks page scroll), auto-fit
  on settle, 🤖 dashed rings for discovery-stuck artists. Data: `build_similarity_data.py`
  + `cli.py similarity-build` batch `lastfm.similar_artists` over the timeline roster
  (cached `.cache_lastfm/`) → `data/similarity_edges.json` (63 KB); `timeline-build` merges
  it as the timeline's `network` key (graceful stub when absent). Timeline JSON now dumps
  compact — 204 KB, smaller than v3's 215 despite the new data; page 549 KB self-contained;
  125 tests green (13 new in `tests/test_similarity_data.py`). After a taste shift:
  `similarity-build` → `timeline-build` → re-inject → scp (runbook unchanged).
- **Shareability pass — done, 2026-07-18.** Made the repo forkable by strangers (+ their
  AI agents) without leaking the user's data. (1) `docs/history.html` is now a **data-free
  template**: the inlined personal timeline JSON was replaced with the `__TIMELINE_JSON__`
  placeholder (563→355 KB) plus a friendly "no data injected yet" fallback screen; the
  personal deployable copy is the **gitignored `docs/history.local.html`**, produced by the
  new `cli.py timeline-inject` (formalizes the old ad-hoc replace; escapes `</` inside JSON
  strings). **Redeploy flow is now: `timeline-build` → `timeline-inject` →
  `scp docs/history.local.html rachett:/var/www/discovery/history.html`** — never scp
  `docs/history.html` itself (it's the empty template). (2) Per-user seeds moved to a
  tracked `config/` dir (`!config/*.json` gitignore negation): `household_artists.txt`
  (loaded by `household.py`; warning + empty set if missing) and `tag_buckets.json` (loaded
  by `build_timeline_data.py`, order-preserving; bucket names stay fixed to the front-end
  `BUCKETS` palette — see `config/README.md`). (3) `SETUP.md` = new-user guide sequenced
  around the ~30-day GDPR export wait (request export day 1, run the discovery layer
  meanwhile, personalize config, build the timeline when it lands); README links it.
  133 tests green (8 new in `tests/test_config_inject.py`); both pages verified in-browser
  (injected copy renders the full viz, bare template shows the fallback). Note:
  `PLAYLIST_NOTES.md` + the `PLAYLISTS` array in `docs/recipes.html` intentionally still
  carry the user's real playlist journal (it's the showcase); SETUP.md tells forkers to
  clear them.
- **Songs & albums expansion — DEPLOYED, 2026-07-18.** `plans/TRACKS_ALBUMS_PLAN.md` phases 0–7
  complete: 12 features across three new sections on `/discovery/history`, built from the
  two dimensions the page lacked (albums were aggregated nowhere; tracks were a bare
  top-150). **"The records"**: 35-album cover-art crate (base64 thumbs, progressive CDN
  swap) with per-album play story + completion ring, album-session score (513 full-album
  sessions, 236 records front-to-back), one-track wonders. **"The songs"**: searchable
  lifeline sparkline grid (top 100 tracks, shared time axis), first-listen dot timeline,
  longest-devotion list, track-seasons card. **"Fun lists"**: CVS-style year receipt
  (year picker, screenshot-styled, skips as tax), milestone club (hours-inside-one-song),
  yearbook anthems mixtape with copy-tracklist button, deep-cut-or-hit dumbbells
  (contrarian score 15%). Data side: `streaming_history.py` v3 (album/track aggregation,
  session detection, lifelines), **`enrich_meta.py` + `cli.py enrich-meta`** — the new
  cached Spotify metadata step (plain `/tracks` + `/albums`, batch 50, read-only scopes,
  caches `.cache_spotify_meta/` → `data/track_album_meta.json`), merged by
  `timeline-build` into `albums`/`track_stories`/`lists` keys (graceful stubs when
  enrichment absent). **Rebuild order is now: `history-build` → `enrich-meta` →
  `timeline-build` → `timeline-inject` → scp.** Page 859 KB self-contained; 202 tests
  green (+69); verified desktop + 390×844 + template fallback, zero console errors.
  Orchestration note: phases 1–3 Sonnet subagents, 4–6 Opus subagents, verify Sonnet —
  Fable only spec'd/reviewed/deployed.
- **History-page polish pass — DEPLOYED, 2026-07-18.** `plans/HISTORY_POLISH_PLAN.md`
  all 5 phases shipped: mobile overflow fix (390px milestone rows), copy pass (new lede,
  "Fun lists"→"Keepsakes", disclaimer trim), sticky section nav with scroll-spy +
  records whitespace, and the gated **Phase 4 narrative reorder** — sections regrouped
  what-then-how (river → every artist → shape of taste → records → songs, then how you
  listen → artist stories → keepsakes, iTunes shelf last). Only `howyoulisten` and
  `artiststories` moved; nav chips reordered to match (scroll-spy assumes chip order =
  DOM order). Phase 4 done by Fable directly (high breakage surface), Playwright verify
  by a Sonnet subagent: both widths clean, 0 console messages, no overflow, all 9 nav
  jumps land, cross-section clicks fire.
- **Apple Music layer (2015–2018 gap fill) — done, 2026-07-28.** An Apple Media Services
  export (`data/Apple_Media_Services/`, gitignored) filled the hole the Spotify export
  left. **`apple_history.py` + `cli.py apple-build`** parse `Apple Music Play Activity.csv`
  into `data/apple_history_events.json` using the EXACT Spotify event schema, so the merge
  happens at the `_iter_events` seam and every downstream section gained the years for free.
  Per-year plays before→after: **2015 14→1,598 · 2016 1→6,026 · 2017 absent→2,979 ·
  2018 876→3,125**; totals 43,850→56,687 plays, 6,957→7,934 artists. Only the music files
  are read — `Stores Activity/`, billing, TV/podcasts/books are ignored (payment data + IPs).
  - **Apple's export has no artist column** (`Container Artist Name` is populated in 2 of
    17,928 rows). The artist is recovered by joining `Song Name` against the `"Artist - Title"`
    strings in `Play History Daily Tracks.csv` + `Track Play History.csv` — 96.8% resolve.
    Gaps are closed by **`config/apple_artist_overrides.json`** (tracked per-user seed, same
    convention as `household_artists.txt`), which the parser consults before dropping an
    event; the map join always wins over an override. **`cli.py apple-unresolved`** writes
    `data/apple_unresolved.md` (gitignored) listing what's still unresolved with play counts
    and **album hints** — the album name is what makes a mystery title identifiable. 207 plays
    across 138 songs remain, mostly remixes/EP singles whose album is just the song title again.
  - **Weak fields stay null, never guessed.** Apple records no `shuffle` and no `reason_start`,
    so Apple events are **excluded from `intentionality` entirely** (absent, not zeroed) and
    from album-session detection (an interleaved Apple play would also *split* a genuine
    Spotify session). A new **`coverage`** block records which sections have real data for
    which years; the page drives its hatched "not recorded" columns off it rather than
    hardcoding years. `skipped` needs no special case — skips are `ms_played < 30s` for both
    services. `platform` comes from `Client Device Name` reduced to a fixed 5-token vocabulary
    (iOS 10.3k / Macintosh 6.1k / Android 173) — **never the raw user-agent**, which carries
    device/build fingerprints that would flow into the publicly deployed page.
  - **27 case-variant artist names canonicalized** at the merge seam (Apple lowercases
    articles): `Outkast`/`OutKast` → 523 plays, `Florence + the Machine` → 365, plus
    `twenty one pilots`, `Cage the Elephant`, `The War on Drugs`, `TV on the Radio`… Election
    = most plays wins, ties go to the Spotify spelling. **Case-only** — no fuzzy/punctuation
    matching (`&` vs `and`, feat. variants) — that class is riskier and stays unauthorized.
  - **`ALL_TIME_ARTISTS_TOP_N` 200 → 400.** The merge initially *regressed*
    `known_listened_artists()` (456→442) by pushing 44 Apple-era artists out of the capped
    list — the Gov't Mule blind spot reintroduced by a different route. Now **598 known**.
    Note this doubles the timeline's artist roster, so the page payload grew (859→883 KB).
  - **Bug found + fixed en route:** the v1 `tracks` accumulator did an unguarded
    `t["uri"] = uri`, so a track played on both services had its Spotify URI blanked by
    whichever Apple play sorted last (silently breaking cover art). Now guarded.
  - **Rebuild order is now: `apple-build` → `history-build` → `enrich-meta` →
    `timeline-build` → `timeline-inject` → scp.** 272 tests green (+70).
    Orchestration: parse Sonnet, aggregator + front-end Opus, verify Sonnet.
- **Two Spotify name-search fallbacks — 2026-07-28.** New shared module **`name_match.py`**
  (pure, no I/O) holds the normalization + accept/reject gates both use: smart-quote/accent
  folding, edition-suffix stripping (`(Deluxe)`, `(Bonus Track Version)`, `(2007 Remaster)`,
  `- EP`), feature-credit stripping, and `artist_matches`, which accepts connector-joined
  extensions (`Nathaniel Rateliff` ↔ `… & The Night Sweats`) but rejects bare substrings
  (`The Band` ≠ `The Band Perry`).
  - **(1) Album art by name** (`enrich_meta.search_album_by_name` / `resolve_albums_by_name`).
    An album played only on Apple Music has no `spotify_track_uri` anywhere, so the
    URI→album→cover path can't reach it. `enrich-meta` now searches artist+album name for
    those, gated on artist match AND album-core similarity ≥ **0.87** (accepts `Coming Home
    (Deluxe)`, rejects `Coming Home Live` at 0.815) — low confidence stays blank rather than
    guessing. Results (including negatives) cache under `.cache_spotify_meta/album_search/`;
    the output gains an **`album_name_lookup`** index plus `art_source` (`uri` |
    `name_search`) on every album so a wrong cover is auditable. `build_timeline_data`
    consumes it via the shared `album_name_key()` (both sides MUST use that one function).
    Also fixed the real cause of the *other* blank tiles: `fetch_albums` now **refills
    thumbnails** for cached albums that missed `THUMB_CAP` on an earlier run (they were
    permanently thumb-less and rendered as letter placeholders).
  - **(2) `cli.py apple-resolve` / `apple_resolve.py`** proposes artists for the songs
    `apple-build` still drops, searching title + **album hint**. Writes
    `data/apple_overrides_proposed.json` (gitignored) with per-song evidence and a tier;
    **nothing is written to `config/apple_artist_overrides.json` without `--apply`**, which
    only applies the `high` tier and never overwrites an existing key (manual override wins;
    the map join still beats both). `high` = informative hint (not just the song title again)
    + title AND album agreement + all qualifying hits agree on one artist. Deliberate
    rejections: remix/EP singles (`Collide (Remixes) - EP`) → `ambiguous_hint`; cover/karaoke
    collisions (`21 Questions` also on a "GhetSoul Tapes" release) → `review`; tribute records
    that merely share a prefix (`Lioness: Hidden Treasures, But Piano`) → `review`. Only a
    **parenthesized** annotation counts as the same release (`Spring Awakening (Original
    Broadway Cast Recording)`). First run: 138 songs → **52 high (applied) / 43 ambiguous /
    29 review / 14 no-match**; after `apple-build`, unresolved dropped **138→86 songs,
    207→141 plays**, resolution **96.8%→98.0%**, +66 plays recovered. 311 tests green (+39). The ⤓ card export rendered the "not recorded"
  gap years **blank**, because `gapHatch` lived in a root-level `<svg><defs>` outside the
  subtree `html-to-image` captures — a shared image would have read as "zero listening",
  the exact misreading the hatch exists to prevent. `hatchFill(el)` now defines the pattern
  inside each chart's own `<svg>` with a per-svg unique id, re-added after each redraw
  (callers clear via `selectAll("*").remove()`). Verified by decoding the exported PNG:
  hatch column samples 30 distinct colors vs 1 for a flat bar and 1 for background.
- **Known, pre-existing (not caused by the Apple work):** at 390px the page reports
  `scrollWidth` 489. Culprit isolated — the **"The Skip Fingerprint"** and **"The Claude
  Era"** cards in Artist Stories render 446.5px wide; their `.hylgrid` media query collapses
  to one column correctly, but the track's default `minmax(auto,1fr)` floors at the
  min-content width of `.skiprow`/`.stuckwrap`, clipping percentages ("1.1%"→"1."). Fix is
  `min-width:0` on the grid item plus wrapping rules inside the rows.
- **Canon-list layer (Recipe 35) — done, 2026-08-02.** A published critics' greatest-albums
  list as a *closed* candidate pool: `knowledge/paste300_albums.json` (Paste's 300 Greatest
  Albums, tracked via a `.gitignore` negation like `genres_coords.json`), `canon_list.py`, and
  `cli.py canon-snapshot`. **Never `Read` the raw list** — the accessor tiers it against the
  merged play history into `lived_in` (≥15 album plays) / `brushed` (1–14) / `near_miss`
  (artist ≥4 plays, album never opened) / `unheard`, which is the only interesting structure
  in it. First run: 31 / 103 / 46 / 120. **`near_miss` is the point** — Dolly Parton 66 plays
  and zero of *Coat of Many Colors* beats both a worn-out record and a stranger.
  - **The export is not the whole truth.** `tier_list` cross-checks
    `discovery_log.known_listened_artists()`, because Erykah Badu had 1 export play (below the
    near-miss floor → "unheard") while sitting in the live taste dump's `top_tracks`: the GDPR
    export ends at its export date, the API's recency windows don't. Any artist in the known
    set is at minimum `near_miss`, flagged `library_only` when the export shows nothing.
    Don't remove that cross-check; regression-tested.
  - Album matching is **deliberately looser** than the album-art gate (containment, no 0.87
    threshold): a false positive only drops a candidate from the pool, a false negative would
    claim the user has never heard a record they play constantly. Name normalization reuses
    `name_match` — do not hand-roll a second normalizer.
  - Loader is list-agnostic (`--list-path`); adding a list needs no code change. **Verify rank
    integrity after parsing** — Paste's rank 269 has a 30-word album title that overflowed a
    naive heading regex and silently dropped a row. Docs: `knowledge/canon_lists.md`.
    329 tests green (+13 in `tests/test_canon_list.py`).
- **Deviation:** redirect URI uses port **8889** (not the plan's 8888) because an
  SNL Jupyter server permanently holds 8888. Recorded in `.env`.
- **Showcase page — done, 2026-07-14.** `docs/recipes.html` is now a tabbed
  `[ Recipes ] [ Playlists ]` page: the recipe book plus the full playlist journal
  (20 playlists hand-transcribed from `PLAYLIST_NOTES.md` into a `PLAYLISTS` JS array,
  sharing the same search/filter/visual system; reconstructed entries carry a badge).
  Deployed public over the Pi Funnel at `https://rachett.tail504ae5.ts.net/discovery`
  (served from `/var/www/discovery/index.html` via a Caddy `file_server` route). Redeploy =
  `scp docs/recipes.html rachett:/var/www/discovery/index.html`. Runbook in `DEPLOY_MCP.md`.
  When you add a playlist to `PLAYLIST_NOTES.md`, also add its object to the `PLAYLISTS`
  array in `docs/recipes.html` and redeploy. **Note:** the Spotify Web API cannot flip a
  playlist's public/private flag (PUT returns 200 but no-ops — a known platform limitation);
  making a playlist public is a client-only toggle, like moving playlists into folders.

## Run
```bash
source .venv/bin/activate          # Python 3.13 venv in project root
python probe.py                    # verify deprecated-endpoint access (Phase 0)
python cli.py -h                   # one entry point for every primitive (Phase 4)
```

## Conventions
- Secrets in `.env` (gitignored); see `.env.example`. Redirect URI must be the
  loopback IP `http://127.0.0.1:8889/callback` (port 8889 — see deviation above),
  not `localhost`.
- Spotipy token cache is `.cache` (gitignored).
- **Never** call `/v1/recommendations`, `/v1/audio-features`, `/v1/audio-analysis`,
  `/v1/artists/{id}/related-artists`, or featured/category playlists — they 403/404
  for this app (re-confirm via `probe.py`).
- Keep Python dumb: it fetches JSON and acts. No recommendation logic in Python —
  that belongs in the Claude session (Mode A). See `plans/claude_initial_plan.md` for phases.
- **Reading taste data: use `cli.py taste-snapshot`, never `Read` the raw
  `data/taste_*.json`.** The raw dump is ~55k tokens of mostly-unused metadata; the
  snapshot is ~2k and carries everything a session needs — top long-term artists, top
  genres, recent plays, and `known_artists` (the full deduped name set for filtering
  candidates to genuinely-new artists). Don't hand-write a `python -c` extractor for this.
- Every track Claude proposes MUST be verified via Spotify `search` before it is
  surfaced or added to a playlist.
- **When building playlists, never add tracks to Liked Songs** — playlist-add only.
  The Python tool (`build_playlist`) already does this correctly. If building live via
  Claude's Spotify connector, create + add items only; do **not** call `add_to_library`.
- **Playlist naming:** prefix every Claude-built playlist name with `🤖 ` so they all
  group together. The Spotify Web API can't create folders or move playlists into them
  (client-only feature), so the user keeps a "Claude" folder and drags new playlists in
  — the prefix makes them trivial to find and multi-select. Applies to both
  `build_playlist` and the connector.
- **Playlist descriptions:** write a brief (1–2 sentence) summary of the actual
  playlist — the artists, mood, era, or theme that makes it interesting. Never use a
  generic "Claude curated" label or describe the tooling. Cap ~300 chars.
- **Playlist notes journal:** after building a playlist, append a human-readable
  summary to `PLAYLIST_NOTES.md` (newest first) — the recipe/angle used, the taste
  rationale, the sequencing, cover seed, and possible tweaks. This is the story version
  the user reads later; `data/discovery_log.jsonl` stays the machine record. Mirror the
  in-chat summary; keep entries to the existing template.
- **Playlist covers:** the Claude-built playlists share a "Painterly worlds" visual
  system so they read as one collection (the visual counterpart to the `🤖 ` prefix).
  **Read `knowledge/cover_style.md` before generating any cover** — it fixes the style
  (textured impasto oil, no text) and maps palette→genre and composition→recipe. Flow:
  `cli.py generate-cover "<prompt>" --out covers/<name>.jpg` → `cli.py set-playlist-image <id> covers/<name>.jpg`.
  Generated covers live in the gitignored `covers/` folder (regenerable, already on Spotify).
  Runs from the local CLI or Pi (needs the write token), never the read-only MCP.

## Mode
Building Mode A (Claude-Code-native). Mode B (standalone Anthropic API) is a later,
additive option — only then add `anthropic` to requirements and an `ANTHROPIC_API_KEY`.
