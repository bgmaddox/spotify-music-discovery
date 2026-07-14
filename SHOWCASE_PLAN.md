# Showcase Plan — Playlist journal → phone-accessible page

Goal: fold `PLAYLIST_NOTES.md` into the existing `docs/recipes.html` as a second
tab, and host the page publicly so it can be pulled up on a phone and shown to
people. Written for an AI agent to execute; each phase names the Claude model to use.

## Decisions (locked)
- **Layout:** one tabbed page — `[ Recipes ] [ Playlists ]` toggle in `docs/recipes.html`,
  sharing the same search bar, filter chips, and visual system.
- **Hosting:** Pi + Tailscale Funnel. Add a Caddy static route so the page is public at
  `https://rachett.tail504ae5.ts.net/discovery`. Reuses the MCP deploy infra.
- **Spotify links:** flip the 20 playlists to **public** first, so viewers can open/play them.
- **Data source:** hand-transcribe `PLAYLIST_NOTES.md` into a `PLAYLISTS` JS array (mirrors
  how `RECIPES` is authored). No Markdown parser now — see the future-generator fork in Phase 2.

## Model summary
| Phase | Model | Why |
|---|---|---|
| 0 Public flip | Sonnet | API mechanics + scope re-auth, low judgment |
| 1 Data extraction | Sonnet | Structured transcription |
| 2 Tabbed page | **Opus** | Matching a hand-tuned design system + interaction |
| 3 Pi deploy | Sonnet | Known runbook, some infra judgment |
| 4 Docs/commit | Haiku | Deterministic |

Fable: **not** used in this plan (build phases are precision/correctness work, not prose).
Candidate later as the dedicated writer for new `PLAYLIST_NOTES.md` entries + playlist
descriptions — an additive experiment, not a build dependency.

---

## Phase 0 — Prep & the public-playlist flip · Sonnet
1. Audit the 20 playlist IDs from `PLAYLIST_NOTES.md` against `data/discovery_log.jsonl`.
2. Flip all 20 playlists to **public**.
   - ⚠️ Blocker to check first: current token has `playlist-modify-private` +
     `playlist-read-private` but likely **not** `playlist-modify-public`. Add it to
     `SCOPES` in `tools.py`, then a one-time **local** re-auth (delete `.cache`,
     re-consent). Do this from the local CLI, not the read-only MCP.
3. Confirm each link opens in an incognito window.

## Phase 1 — Data extraction from PLAYLIST_NOTES.md · Sonnet
- Parse each entry into: `name`, `url`, `date`, `recipe`, `trackCount`, `why`,
  `structure`, `cover` seed, `tweaks`, and a `cat` tag reusing the existing filter
  taxonomy (`discover`/`inward`/`ordered`/`report`) so playlists share the recipe chips.
- Emit a `PLAYLISTS` JS array literal ready to paste.
- Flag backlog/reconstructed entries so the card can show a small "reconstructed" badge
  (honest provenance).

## Phase 2 — Build the tabbed page · Opus
- Add a `[ Recipes ] [ Playlists ]` toggle above the sticky controls; reuse the same
  search input and filter chips against whichever dataset is active.
- Author a `.playlist-card` variant reusing existing card CSS tokens (`--panel`,
  `--radius`, accent colors). Face: name + recipe tag + track count; expandable:
  why / structure / tweaks; a "▶ Open on Spotify" button.
- Update the footer count line ("20 playlists · 13 recipes") and the header lede.
- **Future-generator fork:** if the Pi's daily timer should rebuild this, add a separate
  small `build_showcase.py` reading a strict front-matter block (not the loose prose).
  Defer unless requested.

## Phase 3 — Deploy to the Pi (Caddy static route) · Sonnet
1. Copy `docs/recipes.html` → Pi static dir (e.g. `apps/SpotifyDiscoveryMCP/public/`),
   renamed `index.html` so `/discovery` resolves clean.
2. Add a Caddy route: `handle /discovery*` → `file_server` rooted at that dir.
3. Reload Caddy; verify `https://rachett.tail504ae5.ts.net/discovery` loads over the
   Funnel **on cellular** (phone off wifi = true "out and about" test).
4. Mirror the sync step into `DEPLOY_MCP.md` so future page edits redeploy the same way.

## Phase 4 — Docs & commit · Haiku
- Update `CLAUDE.md` (showcase page + `/discovery` URL) and `DEPLOY_MCP.md` (static route).
- Commit `docs/recipes.html`; push. Covers/`.cache` stay gitignored.

---

## Flags before starting
1. **Scope re-auth** (Phase 0) is the only step touching the local `.cache` / needing an
   interactive Spotify consent. Everything else is non-interactive.
2. **Funnel = fully public.** `/discovery` is reachable by anyone with the URL; the page
   exposes taste profile + playlist reasoning publicly — intended for a portfolio piece.
