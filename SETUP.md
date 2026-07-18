# SETUP.md — make this project yours

A sequenced guide for setting this toolkit up on your own machine with your own
Spotify account. Written to be read by **you and your AI agent together** — if you
use Claude Code (or similar), point it at this file and `CLAUDE.md` and it can
drive most of the steps.

The one thing to know up front: the project has **two layers with very different
setup times**.

| Layer | What it gives you | Ready in |
|-------|-------------------|----------|
| Discovery tooling | Taste snapshot, Last.fm similarity, verified playlist building, the recipes | ~1 hour |
| History visualizations | The `/history` timeline page (genre river, listening clock, artist stories, similarity network) | **up to ~30 days** — it needs Spotify's Extended Streaming History export |

So: **do Step 0 first, today**, then enjoy the discovery layer while you wait.

---

## Step 0 — Request your Spotify data export (do this first!)

Go to [spotify.com/account/privacy](https://www.spotify.com/account/privacy/) and
request the **Extended streaming history** (not the basic "Account data" package).
Spotify emails a download link when it's ready — typically 1–4 weeks. Nothing in
the visualization layer works without it, and nothing can shortcut the wait.

While you're waiting, everything below works immediately.

## Step 1 — Credentials

1. **Spotify developer app** — create one at
   [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard).
   Add a redirect URI of exactly `http://127.0.0.1:8888/callback` (the loopback
   IP, not `localhost`; pick another free port if 8888 is taken, and use the same
   value in `.env`).
2. **Last.fm API key** — free at
   [last.fm/api/account/create](https://www.last.fm/api/account/create). Only the
   API key is needed (read-only similarity/tag lookups).
3. Copy `.env.example` → `.env` and fill in the three values.

## Step 2 — Environment

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python probe.py        # sanity check: confirms which Spotify endpoints you have
python cli.py -h       # the single entry point for everything
```

The first command that touches your Spotify data (e.g. `python cli.py dump-taste`)
opens a browser window for OAuth; approve it once and the token is cached in
`.cache` (gitignored).

## Step 3 — Use the discovery layer (no waiting required)

This project's design: **the AI agent is the brain, Python is the hands.** You
don't run recipes by hand — you tell your agent things like:

- "Dump my taste and give me a taste report with blind spots."
- "Find me something new near <artist I love> — build me a playlist."
- "What's playing right now, and where does it come from?"

The agent should read `RECIPES.md` and `knowledge/` before reasoning, and follow
the conventions in `CLAUDE.md` (verify every track, 🤖-prefix playlists, log to
the discovery ledger).

## Step 4 — Personalize the config

The genre/household seeds in this repo are tuned to the original author's taste
(Americana/indie-folk clusters, toddler-heavy household). Make them yours:

- `config/household_artists.txt` — artists to exclude from taste analysis
  (kids' music, sleep audio). Start by emptying it and adding your own.
- `config/tag_buckets.json` — Last.fm tag → genre bucket mapping. Works fine
  as-is for most tastes; if your core genres map badly to buckets, re-seed it
  (see `config/README.md` — bucket *names* are fixed, the tag mappings are yours).
- `knowledge/genre_map.md` — static genre-adjacency notes your agent reads while
  reasoning. Have your agent rewrite it around *your* top genres after your first
  `dump-taste`.
- `PLAYLIST_NOTES.md` and the `PLAYLISTS` array in `docs/recipes.html` are the
  original author's playlist journal — clear them and start your own.

## Step 5 — When the export lands: build your timeline

Unzip the export into `data/` (the folder is gitignored; the raw files contain
IPs/device strings, so they never leave your machine). Then:

```bash
python cli.py history-build      # aggregate the raw export → history_summary.json
python cli.py dump-taste         # fresh taste dump for the "now" panel
python cli.py timeline-build     # merge everything → data/taste_timeline.json
python cli.py similarity-build   # optional: Last.fm edges for the network view
python cli.py timeline-build     # re-run to fold the similarity edges in
python cli.py timeline-inject    # inline your data → docs/history.local.html
open docs/history.local.html
```

`docs/history.html` in the repo is a **data-free template** — your personal page
is the gitignored `history.local.html`, so your listening history never ends up
in git. An optional iTunes-era layer (`data/itunes_history.json`) fills in
pre-streaming years if you have an old `Library.xml`; skip it otherwise.

## What's intentionally not covered

`DEPLOY_MCP.md` documents the original author's Raspberry Pi / Tailscale
deployment (public showcase page + a phone-accessible MCP server). It's a
worked example, not a setup guide — everything above runs fine purely locally.
