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
  `search_verify`) surfaced 25 genuinely-new candidates from 2 seeds and verified 3 of them
  (Vincent Neil Emerson, 49 Winchester, Flatland Cavalry). Live playlist build not yet run.
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

## Mode
Building Mode A (Claude-Code-native). Mode B (standalone Anthropic API) is a later,
additive option — only then add `anthropic` to requirements and an `ANTHROPIC_API_KEY`.
