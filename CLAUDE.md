# CLAUDE.md — Spotify Music Discovery

Personal single-user music-discovery toolkit. Spotify's algorithmic endpoints are
deprecated for this app, so the recommendation reasoning lives in the Claude Code
session, not in a Spotify endpoint. Python is a dumb sensing + acting layer.

## Progress (see claude_initial_plan.md for full phase specs)
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
    `spotify-discovery-mcp.service`. The Node server proved the mobile app accepts a
    **static bearer gated at Caddy** (no OAuth handshake) — so ours runs proxy-auth mode
    (`MCP_TRUST_PROXY_AUTH=1`), bound to 127.0.0.1, bearer enforced by Caddy.
  - **Three deploy-time code fixes** (all committed, default/local behavior unchanged):
    `MCP_TRUST_PROXY_AUTH` + `MCP_PATH` (run naked behind a proxy at a custom path);
    `MCP_ALLOWED_HOSTS` → `TransportSecuritySettings` (the transport's Host-header check
    421'd proxied requests until the public host was whitelisted); `SPOTIPY_NONINTERACTIVE`
    (headless Spotipy would block forever on the OAuth prompt — now fails fast).
    `mint_pi_cache.py` mints a read-only Spotify `.cache` without touching the local
    superset cache. Full as-built runbook in `DEPLOY_MCP.md`.
  - **Verified live through the funnel:** auth gates (401 without/with wrong bearer),
    `initialize` 200, `tools/list` = 6 tools, `taste_snapshot` + `lastfm_*` return real
    data, `now_playing`/`search_verify` fail cleanly (0.1s) until the Spotify `.cache` is
    copied up. **Remaining 🧑 steps:** run `mint_pi_cache.py` (browser) to enable the two
    Spotify tools, and add the connector in the mobile app.
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
  (4) **CLI drift fixed** — `genre-find` is now exposed in `cli.py` (was module-only). (5)
  **Hygiene** — dumps self-prune to newest 5 (`prune_dumps`), Last.fm CLI prints clean errors
  instead of tracebacks, `import html` hoisted in `genre_map.py`. All five primitives + new
  commands verified clean.
- **Deviation:** redirect URI uses port **8889** (not the plan's 8888) because an
  SNL Jupyter server permanently holds 8888. Recorded in `.env`.

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
  that belongs in the Claude session (Mode A). See `claude_initial_plan.md` for phases.
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

## Mode
Building Mode A (Claude-Code-native). Mode B (standalone Anthropic API) is a later,
additive option — only then add `anthropic` to requirements and an `ANTHROPIC_API_KEY`.
