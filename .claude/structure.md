entry:        cli.py  (Phase 4, unified) — routes to taste_profile/tools/sensing/lastfm primitives
modules:      probe.py (Phase 0), taste_profile.py (Phase 1), tools.py + sensing.py (Phase 2/3), lastfm.py (Phase 5)
run:          source .venv/bin/activate && python cli.py <subcommand>   (or python <module>.py)
auth:         auth.py  (get_client(scopes) wraps SpotifyOAuth)
tools:        tools.py  (search_verify, verify_detail, build_playlist; lib + CLI)
sensing:      sensing.py  (now_playing, library_scan; lib + CLI)
lastfm:       lastfm.py  (similar_artists, similar_tracks, artist_tags; lib + CLI; caches to .cache_lastfm/)
mcp (Mode C): mcp_server.py  (Phase 6; read-only FastMCP server for mobile Claude) · deploy: DEPLOY_MCP.md
recipes:      RECIPES.md  (1 ladder, 2 now-playing, 3 taste-report, 4 archaeologist, 5 time-machine, 6 lastfm-seeded ladder)
knowledge:    knowledge/  (discovery_heuristics.md = angles, genre_map.md = static adjacencies; read before reasoning)
data:         data/    (taste_*.json, library_*.json dumps, gitignored)
config:       .env  (secrets)  ·  .env.example  (template)
plan:         claude_initial_plan.md
skip:         .venv/, __pycache__/, .cache, .cache_lastfm/
