# Spotify Music Discovery

A personal, single-user music-discovery toolkit. The big idea: **Claude is the brain,
Python is the hands.** Spotify killed the algorithmic endpoints this kind of app used to
rely on (recommendations, audio-features, related-artists — they all return 403/404 now),
so the actual *taste reasoning* happens inside a Claude session. The Python here just
senses (reads your listening data) and acts (verifies tracks, builds playlists). Last.fm
fills in the "what's similar?" signal Spotify took away.

You don't run most of this by hand. You **talk to Claude** ("find me something new in the
roots/Americana vein", "what's playing and where does it come from?", "build me a playlist
from my Isbell/Sturgill cluster") and Claude drives the tools below.

> **Want to run this against your own Spotify account?** See **`SETUP.md`** — the
> discovery layer is a ~1-hour setup; the history visualizations need Spotify's
> Extended Streaming History export (up to ~30 days), so request that first.

---

## What it can do

### Sense your taste
- **Taste snapshot** — pulls your top artists, top tracks, and recently-played from Spotify.
- **Library scan** — reads your saved/Liked tracks (currently ~259) for analysis.
- **Now playing** — sees whatever track is on right now, to riff off it.

### Find new music
- **Last.fm similarity** — similar artists, similar tracks, and crowd "tags" (genres/moods)
  for any seed. This is the external signal that replaces Spotify's dead endpoints.
- **Discovery reasoning** — Claude proposes candidates using a playbook of discovery angles
  (see `knowledge/`), filtered against what you already know so it surfaces genuinely *new*
  artists, not stuff already in your library.
- **Verify-before-surface** — every track Claude suggests is checked against Spotify search
  first, so you never get hallucinated or mis-titled tracks.

### Build playlists
- **Build playlist** — creates a **private** playlist from verified tracks. It never touches
  your Liked Songs (playlist-add only).
- Every Claude-built playlist is named with a **`🤖 ` prefix** (so they group together —
  create a "Claude" folder in the Spotify app once and drag them in; the Web API can't make
  folders itself) and gets a **brief description summarizing the actual artists/mood/theme**.

### Use it from your phone (Phase 6, not yet deployed)
- An MCP server (`mcp_server.py`) exposes the read-only discovery tools so the **Claude
  mobile app** can drive discovery from a phone. Tooling is built and smoke-tested;
  deploying it to the Pi is the remaining step (`DEPLOY_MCP.md` is the runbook).

---

## The recipes (workflows Claude follows)

Full detail in `RECIPES.md`. In plain terms:

1. **Discovery ladder** *(the core)* — proposes ~9 tracks in three rungs: safe picks in your
   wheelhouse, one-axis stretches, and a few real left-field reaches. Verifies all, builds a
   playlist, reports what hit and what missed.
2. **Now-playing companion** — takes the current track and maps its lineage / rabbit hole
   plus a few verified next steps.
3. **Taste report + blind spots** — summarizes your taste and points out gaps worth exploring.
4. **Library archaeologist** — mines your *existing* saved tracks for a themed playlist.
5. **Time machine** — discovery anchored to a particular era.
6. **Lateral discovery** — Last.fm-seeded ladder: seed a few loved artists, gather similar
   ones, filter to new, build.

---

## Running it yourself (CLI)

You rarely need this, but every primitive has a command-line entry point:

```bash
source .venv/bin/activate          # Python 3.13 venv in project root
python cli.py -h                   # one entry point for everything

python cli.py dump-taste [--max-age MIN] [--force]   # snapshot taste → data/taste_*.json
python cli.py library-scan [--cap 500]               # saved tracks → data/library_*.json
python cli.py now-playing                            # current track
python cli.py search-verify "Artist" "Title"         # does this track exist? print URI
python cli.py build-playlist "🤖 Name" spotify:track:xxx --description "…"
python cli.py similar-artists "Colter Wall" [--limit 30]
python cli.py similar-tracks "Colter Wall" "Sleeping on the Blacktop"
python cli.py artist-tags "Colter Wall"
python cli.py genre-neighbors "indie folk"           # everynoise's nearby genres
python cli.py genre-find "americana"                 # resolve an exact genre name
python cli.py log-add --artist "Tyler Childers" --recipe 6   # record a surfaced pick
python cli.py log-artists                            # what Claude already suggested
python cli.py log-recent
```

Convention: machine output (a path or URI) goes to stdout; human notes go to stderr.

### Tests

```bash
pip install -r requirements.txt   # includes pytest
pytest -q
```

The suite covers the pure, fragile logic — Last.fm response shapes, the everynoise
genre-page regex, track-match fallback, and the discovery ledger — with no network or
auth, so it runs offline in well under a second.

---

## What lives where

| File / dir | Purpose |
|---|---|
| `cli.py` | Single entry point routing to every primitive |
| `taste_profile.py` | Dumps your taste data (top artists/tracks, recents) |
| `sensing.py` | `now-playing` + `library-scan` |
| `tools.py` | `search-verify` + `build-playlist` |
| `lastfm.py` | Similar artists/tracks + tags (the discovery signal) |
| `genre_map.py` | `genre-neighbors` / `genre-find` over the everynoise genre map |
| `discovery_log.py` | Cross-session ledger of what Claude has already surfaced (dedup) |
| `mcp_server.py` | Read-only server for the Claude mobile app (Phase 6) |
| `probe.py` | Confirms which Spotify endpoints are dead |
| `SETUP.md` | Set this up on your own machine / Spotify account |
| `config/` | Per-user personalization: household filter + tag→genre buckets |
| `RECIPES.md` | The discovery workflows Claude follows |
| `knowledge/` | `discovery_heuristics.md` (angles) + `genre_map.md` (adjacencies) |
| `tests/` | `pytest` suite over the pure parsing/normalization logic |
| `data/` | Cached taste/library dumps (newest 5 kept) + `discovery_log.jsonl` |
| `CLAUDE.md` | Instructions for Claude (not a user doc) |
| `DEPLOY_MCP.md` | Pi + Cloudflare Tunnel deploy runbook for the mobile server |
| `plans/claude_initial_plan.md` | The original phase-by-phase build plan |

---

## Constraints worth knowing

- **Dead Spotify endpoints:** recommendations, audio-features, audio-analysis,
  related-artists, and featured/category playlists all 403/404 for this app. That's *why*
  the reasoning lives in Claude + Last.fm. (Re-confirm anytime with `python probe.py`.)
- **No folders via API:** Spotify's Web API can't create playlist folders or move playlists
  into them. The `🤖 ` name prefix is the workaround — you make the "Claude" folder manually.
- **Never touches Liked Songs:** playlists are build-and-add only.
- **Auth:** OAuth via Spotipy, token cached in `.cache`. Redirect URI is
  `http://127.0.0.1:8889/callback` (port 8889 — 8888 is taken by a Jupyter server).
- **Secrets** live in `.env` (gitignored); `.env.example` shows the shape.
```
