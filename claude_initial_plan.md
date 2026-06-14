# Spotify Music Discovery — Implementation Plan

> **Audience:** This document is written to be executed by an AI coding agent (Claude
> Code). Each phase has concrete deliverables, file paths, acceptance criteria, and an
> assigned Claude model. Work phases in order; do not start a phase until the previous
> phase's acceptance criteria pass.

---

## 1. Project summary

A personal music-discovery toolkit for one user (the repo owner). Spotify deprecated its
algorithmic endpoints (recommendations, audio-features, related-artists, audio-analysis,
editorial playlists) for apps registered after 2024-11-27, so **the recommendation
intelligence lives in Claude's reasoning, not in a Spotify endpoint.**

Division of labor:

| Layer | Implemented by | Responsibility |
|-------|---------------|----------------|
| **Sensing** | Own Spotify app (Python + Spotipy) | Read taste data: top artists/tracks, recently played, saved library, playlists |
| **Reasoning** | **Primary: your Claude Code session** (Mode A). Optional: Anthropic API (Mode B). See §8. | Analyze taste, generate candidate recommendations, curate |
| **Acting** | Spotify Web API write scopes (own app) **or** the existing Claude Spotify connector | Create playlists, save tracks, verify a track exists via search |

**Hard constraint:** Do NOT call or depend on `/v1/recommendations`, `/v1/audio-features`,
`/v1/audio-analysis`, `/v1/artists/{id}/related-artists`, or featured/category playlists.
They 403/404 for this app. If a feature seems to need them, redesign it around
Claude-reasoning + `search` verification instead.

---

## 2. Two distinct model decisions

This project invokes Claude in two separate contexts. Keep them straight.

### 2a. Build-time model (the agent writing this code)
Which model *you, the executing agent,* should run as while implementing each phase. Driven
by reasoning difficulty of the coding task. Assigned per-phase in Section 4.

### 2b. Runtime model (the model the finished app calls)
**Mode B only.** In Mode A — the primary build target — there are no runtime API calls; the
reasoning is your Claude Code session. This subsection and §5 apply only if/when you add a
Mode B orchestrator for a feature you want to run unattended.

The shipped Python code makes `anthropic` API calls to do the actual music reasoning. That
model choice is a product decision, assigned per-feature in Section 5.

Default to `claude-opus-4-8` unless a row below says otherwise. Use exact model ID strings;
never append date suffixes.

---

## 3. Tech stack & conventions

- **Python 3.13**, venv at `Spotify/.venv/` (`source .venv/bin/activate` before running).
- **Spotipy** for Spotify OAuth + reads (do not hand-roll OAuth).
- **anthropic** SDK for runtime Claude calls.
- Secrets in `Spotify/.env` (gitignored): `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`,
  `SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback`, `ANTHROPIC_API_KEY`.
- Spotipy token cache `.cache` (gitignored).
- Keep the Python sensing layer **dumb**: it fetches and dumps JSON. No recommendation
  logic in Python — that belongs in Claude prompts.
- Runtime Claude calls use `thinking={"type": "adaptive"}` and set `output_config.effort`
  explicitly per Section 5.

---

## 4. Phases (build order)

### Phase 0 — Scaffolding & auth  ·  build model: `claude-haiku-4-5`
Low-reasoning setup work; cheap model is fine.

**Deliverables**
- `Spotify/.venv/` created; `requirements.txt` with `spotipy`, `python-dotenv` (add
  `anthropic` only if/when Mode B is built — see §8).
- `.gitignore` excluding `.env`, `.cache`, `__pycache__/`, `.venv/`, `*.json` data dumps.
- `Spotify/CLAUDE.md` (lean, per global conventions) and `Spotify/.claude/structure.md`.
- `Spotify/.env.example` documenting required keys (no real secrets).
- `Spotify/auth.py`: a `get_client(scopes)` helper wrapping `spotipy.SpotifyOAuth`.
- `Spotify/probe.py`: probes whether THIS app retains access to the deprecated
  endpoints. Calls `GET /v1/audio-features/{id}` and `GET /v1/recommendations`
  (with a known track seed) and prints, per endpoint, `OK` or `403 restricted`.
  Rationale: the deprecation grandfathered apps in **extended quota mode**, not by
  age — an old development-mode app most likely lost access, but it must be tested,
  not assumed.

**Acceptance**
- `python -c "from auth import get_client; print(get_client(['user-top-read']).current_user()['display_name'])"`
  completes the browser OAuth flow once and prints the username.
- `python probe.py` prints a clear verdict per endpoint. **This result decides whether
  §1's constraint holds or relaxes — report it to the user before starting Phase 1.**
  If the endpoints are live, revisit the plan: audio-features and recommendations
  become available as inputs and candidate sources.

> ⚠️ Phase 0 requires the user to have registered their Spotify app and added Client ID /
> Secret to `.env`. If `.env` is missing those, STOP and ask the user to complete Spotify
> Developer Dashboard setup before proceeding.

### Phase 1 — Sensing layer (taste dumper)  ·  build model: `claude-sonnet-4-6`
Straightforward API plumbing; Sonnet balances quality and cost.

**Deliverables**
- `Spotify/taste_profile.py` that fetches and writes `data/taste_<timestamp>.json`:
  - top artists & tracks for `short_term`, `medium_term`, `long_term`
  - last 50 recently played
  - saved tracks (paginated, capped at e.g. 500)
- Each track/artist record carries only surviving metadata: name, id, popularity,
  genres (artist-level), release date, album. **No audio-features.**

**Acceptance**
- Running it produces a JSON file with non-empty `top_artists.long_term` and
  `recently_played`. No 403s in output.

### Phase 2 — Acting tools + discovery-ladder recipe (the core)  ·  build model: `claude-opus-4-8`
Reasoning happens in the Claude Code session (Mode A), so this phase builds the **tool
primitives** the session drives plus a documented **recipe**. No API calls in shipped code.

**Deliverables**
- `Spotify/tools.py` (or small CLI subcommands) exposing:
  - `search_verify(artist, title)` → Spotify track URI if it exists, else `None`.
  - `build_playlist(name, uris)` → creates a private playlist (`playlist-modify-private`)
    and adds the verified URIs. (Mode A may instead use the existing Claude Spotify
    connector's `create_playlist` — pick whichever is less friction; document the choice.)
- `Spotify/RECIPES.md` (or a section in `CLAUDE.md`) documenting the **discovery-ladder
  recipe** so any session executes it consistently:
  1. Run `taste_profile.py`; read the latest `data/taste_*.json`.
  2. Propose a ladder: ~3 center-of-taste, ~3 one-axis stretches, ~3 left-field picks,
     each with a one-line rationale.
  3. `search_verify` every candidate; drop and log misses.
  4. `build_playlist` from the verified hits; report rationales + dropped candidates.

**Acceptance**
- In a Claude Code session, following the recipe on the user's real data produces a private
  Spotify playlist of ≥7 verified tracks, with rationales and dropped candidates reported.

> **Mode B (optional, later):** move step 2's reasoning into an `anthropic` call inside a
> `discover.py` so the ladder runs unattended. The tools above are reused unchanged.

### Phase 3 — Additional sensing tools + recipes  ·  build model: `claude-opus-4-8`
Same shape as Phase 2: build any missing **sensing/acting primitives**, then document each
feature as a **recipe** the session executes. Reasoning stays in-session.

**Deliverables (each independently shippable; do in order)**
- `now_playing` tool — returns the currently-playing track (id, artist, title). Recipe:
  session adds lineage / "rabbit hole" commentary.
- `library_scan` tool — dumps saved tracks (reuse Phase 1 fetch). Recipes that build on it:
  - **Taste report + blind spots** — session writes a narrative read of the taste dump and
    flags genres suspiciously absent given what the user loves.
  - **Library archaeologist** — session finds patterns in saved tracks and proposes
    playlists from the user's *own* library (build via `build_playlist`).
  - **Time machine** — session takes a vibe/era/theme, proposes tracks, `search_verify`s
    them, builds the playlist.

**Acceptance (per recipe)**
- In a session, produces its output with no 403s; every track claimed to exist is
  `search_verify`'d before being surfaced or added.

> **Mode B (optional, later):** any recipe can be promoted to a standalone API script using
> the §5 model assignments. The tool primitives are unchanged.

### Phase 4 — Ergonomics  ·  build model: `claude-sonnet-4-6`
- A thin `cli.py` (argparse or `click`) dispatching to the **tool primitives**
  (`dump-taste`, `search-verify`, `build-playlist`, `now-playing`, `library-scan`) so the
  session can call them with one command each.
- Update `CLAUDE.md` / `structure.md` with final layout; ensure `RECIPES.md` is current.
- Optional: simple disk caching of taste dumps to avoid re-fetching every run.

**Acceptance**
- `python cli.py dump-taste` and `python cli.py now-playing` run cleanly, and the
  discovery-ladder recipe (Phase 2) can be driven end-to-end in a session using these
  commands.

---

## 5. Runtime model assignments (Mode B only — optional)

Applies only when a feature is promoted to a standalone API script (§8 Mode B). In Mode A
there is no runtime model — the session is the reasoner.

| Feature | Runtime model | effort | Rationale |
|---------|--------------|--------|-----------|
| Discovery ladder (`discover.py`) | `claude-opus-4-8` | `high` | Core taste-matching + left-field reasoning; quality is the whole point |
| Taste report + blind spots | `claude-opus-4-8` | `high` | Insight quality is the deliverable |
| Time-machine / themed playlists | `claude-opus-4-8` | `medium` | Generation + verification; medium balances cost |
| Now-playing companion | `claude-sonnet-4-6` | `medium` | Lighter, conversational; latency matters more than depth |
| Library archaeologist | `claude-opus-4-8` | `medium` | Pattern-finding over a large list |

All runtime calls: `thinking={"type": "adaptive"}`. Default `max_tokens` 16000 (non-stream).
Stream if a response could be large.

**Knowledge-cutoff guardrail:** the runtime model's music knowledge has a training cutoff,
so any track it proposes MUST be reality-checked via Spotify `search` before it is surfaced
or added to a playlist. This is non-negotiable and applies to every feature that names
tracks. Treat search verification as the source of truth, the model as the idea generator.

### Cost expectations (API mode only)
Applies only if the app calls the Anthropic API directly (see §8 for the alternative).
Personal/hobby scale: **likely under $5/month.** Per-call estimates at current pricing
(Opus 4.8 $5/M in, $25/M out; Sonnet 4.6 $3/M in, $15/M out):

| Call | Est. cost/call |
|------|----------------|
| Discovery ladder (Opus, high) | $0.10–0.20 |
| Taste report (Opus, high) | $0.15–0.25 |
| Time-machine (Opus, medium) | $0.05–0.12 |
| Now-playing (Sonnet, medium) | $0.01–0.03 |

A typical evening of use ≈ $1. The cost lever is `effort` (adaptive-thinking tokens bill
at the output rate); drop a feature to `medium` to roughly halve its output cost. Spotify
`search` verification is free. In-session, wrap the taste JSON in a `cache_control`
breakpoint so repeated calls within ~5 min read it at ~10% input price (Phase 4 polish).

---

## 6. Out of scope (do not build)
- Anything depending on deprecated Spotify endpoints (see §1 constraint).
- Paid third-party "audio features" replacements — revisit only if the user explicitly asks.
- A web UI — CLI only unless the user requests otherwise.
- Multi-user / auth-for-others — this is a single-user personal tool.

---

## 7. Open items for the user (resolve before/at Phase 0)
- Confirm the Spotify Developer app is registered and Client ID/Secret are in `.env`.
- Confirm the redirect URI `http://127.0.0.1:8888/callback` is added to the app's settings
  in the Spotify Dashboard (must match exactly, loopback IP not `localhost`).

---

## 8. Operating modes

- **Mode A — Claude-Code-native (primary build target).** The Python layer is sensing +
  acting tools only. Reasoning happens in your Claude Code session, driven by the recipes
  in `RECIPES.md` / `CLAUDE.md`. No Anthropic API key, no per-token billing beyond your
  Claude Code plan. Trade-off: requires you to be in a session — cannot run unattended or
  on a schedule.
- **Mode B — standalone API (optional, additive).** A thin orchestrator calls the Anthropic
  API to run a recipe's reasoning without a human, enabling cron / Pi / Streamlit use.
  Reuses the same tool primitives; adds only the API call, the §5 model/effort choices, and
  the §5 cost. Build per-feature, only for what you actually want automated.

**Decision: build Mode A now; keep the tool layer API-agnostic so Mode B is a later
add-on.** No reasoning logic in Python during Phases 0–4 — the tools fetch and act, the
session reasons.
