entry:        cli.py  (Phase 4, unified) — routes to taste_profile/tools/sensing/lastfm primitives
modules:      probe.py (Phase 0), taste_profile.py (Phase 1), tools.py + sensing.py (Phase 2/3), lastfm.py (Phase 5)
run:          source .venv/bin/activate && python cli.py <subcommand>   (or python <module>.py)
auth:         auth.py  (get_client(scopes) wraps SpotifyOAuth)
tools:        tools.py  (search_verify, verify_detail, build_playlist; lib + CLI)
sensing:      sensing.py  (now_playing, library_scan; lib + CLI)
lastfm:       lastfm.py  (similar_artists, similar_tracks, artist_tags; lib + CLI; caches to .cache_lastfm/)
genremap:     genre_map.py  (genre-neighbors / genre-find: everynoise ranked nearby genres; lib + CLI; caches to .cache_everynoise/) · build_genre_data.py rebuilds knowledge/genres_coords.json
ledger:       discovery_log.py  (log-add / log-artists / log-recent: cross-session record of what Claude has already surfaced, for dedup; lib + CLI; appends data/discovery_log.jsonl)
mcp (Mode C): mcp_server.py  (Phase 6; read-only FastMCP server for mobile Claude; DEPLOYED at rachett.tail504ae5.ts.net/discovery-mcp via Tailscale Funnel + Caddy proxy-auth) · mint_pi_cache.py mints the read-only Spotify .cache for the Pi · runbook: DEPLOY_MCP.md
recipes:      RECIPES.md  (1 ladder, 2 now-playing, 3 taste-report, 4 archaeologist, 5 time-machine, 6 lastfm-seeded ladder, 7 genre-ladder)
knowledge:    knowledge/  (discovery_heuristics.md = angles, genre_map.md = curated adjacencies, genres_coords.json = full everynoise map index [machine-only, query via genre-neighbors]; read .md before reasoning)
tests:        tests/  (pytest; pure parsing/normalization logic — no network/auth — run `pytest -q`)
data:         data/    (taste_*.json, library_*.json dumps [newest 5 kept], discovery_log.jsonl; gitignored)
covers:       covers/  (generated playlist cover .jpgs from generate-cover; gitignored — regenerable, already on Spotify. Write new covers here: generate-cover "..." --out covers/<name>.jpg)
docs:         docs/    (recipes.html = showcase page; history.html = data-free timeline TEMPLATE — personal copy is gitignored history.local.html via `cli.py timeline-inject`)
config:       .env  (secrets)  ·  .env.example  (template)  ·  config/  (per-user seeds: household_artists.txt, tag_buckets.json — see config/README.md)
setup:        SETUP.md  (new-user/new-machine guide; GDPR export first, discovery layer while waiting)
plan:         claude_initial_plan.md
skip:         .venv/, __pycache__/, .cache, .cache_lastfm/, .cache_everynoise/, covers/, docs/recipes.html
