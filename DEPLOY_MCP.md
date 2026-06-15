# DEPLOY_MCP.md — putting the discovery server on your phone (Mode C)

Goal: run `mcp_server.py` on the Pi, expose it at a public HTTPS URL via Cloudflare
Tunnel, and add it to the Claude mobile app as a custom connector. Read-only discovery
server; playlist writes stay with Claude's built-in Spotify connector.

> **Who does what:** 🤖 = Claude can do it for you in a Claude Code session on the right
> machine. 🧑 = you do it (account/dashboard/phone actions Claude can't perform).

---

## Architecture (how the pieces connect)
```
 Phone Claude app ──HTTPS──> Anthropic cloud ──HTTPS──> Cloudflare edge
        │                                                     │ (Tunnel)
        │                                              cloudflared on Pi
        │                                                     │ localhost:8890
        └──(playlist writes go via the built-in Spotify connector, not this server)
                                                       mcp_server.py
                                                       │        │
                                                  Last.fm   Spotify (read, via .cache)
```
Key point: **Anthropic connects from its cloud, not your phone** — so the server must be
reachable on the public internet (Tailscale alone won't work). Cloudflare Tunnel gives a
public HTTPS hostname without opening any ports on your router.

---

## Step 1 — Pre-authorize Spotify, headless-ready  🤖 (local) + 🧑 (one browser click)
The server reads `search_verify` / `now_playing` using the cached refresh token. Do this
on your Mac once (it has the browser):
1. 🤖/🧑 `python cli.py now-playing` to mint a `.cache` whose token carries ONLY the
   read scope the server needs (`user-read-currently-playing`; `search_verify` needs no
   scope at all). You approve the browser consent once.
   - **Don't** seed the Pi's `.cache` via `dump-taste`/`build-playlist` — those widen the
     token to include `playlist-modify-*`, so the public box would hold a write-capable
     token even though the server exposes no write tool. `search_verify`/`now_playing`
     default to read-only scopes (`SEARCH_SCOPES` / `NOW_PLAYING_SCOPES`) precisely so the
     Pi's token can't modify playlists. If your local `.cache` is already the write
     superset, make a clean read-only one for the Pi: `rm .cache && python cli.py now-playing`
     (then re-auth your local session afterward, since playlist builds need the superset).
2. The `.cache` file now has a refresh token that renews silently forever. You'll copy it
   to the Pi in Step 3.

## Step 2 — Generate the server secret  🤖
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Put it in the Pi's `.env` as `MCP_BEARER_TOKEN=...` (Step 3). Keep a copy — you'll paste it
into the Claude connector config in Step 6.

## Step 3 — Deploy the app to the Pi  🤖 (mostly) + 🧑 (sudo)
Following the global "Adding a new app to the Pi" pattern:
1. 🤖 Push this repo (already on GitHub: `bgmaddox/spotify-music-discovery`).
2. 🧑/🤖 On the Pi: clone to `/home/bgmaddox/apps/SpotifyMCP`, make a `.venv`,
   `pip install -r requirements.txt`.
3. 🧑 Copy your Mac's `.env` and `.cache` to the Pi app dir (scp). Add to `.env`:
   `MCP_BEARER_TOKEN`, `MCP_PUBLIC_URL` (filled after Step 4), `MCP_PORT=8890`.
4. 🧑/🤖 Also copy a recent `data/taste_*.json` so `taste_snapshot` has data (or run
   `python cli.py dump-taste` on the Pi using the copied `.cache`).
5. 🧑 Create `/etc/systemd/system/spotify-mcp.service` (template below), then
   `sudo systemctl enable --now spotify-mcp.service`.

```ini
[Unit]
Description=Spotify discovery MCP server
After=network-online.target

[Service]
User=bgmaddox
WorkingDirectory=/home/bgmaddox/apps/SpotifyMCP
EnvironmentFile=/home/bgmaddox/apps/SpotifyMCP/.env
ExecStart=/home/bgmaddox/apps/SpotifyMCP/.venv/bin/python mcp_server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
Verify locally on the Pi: `curl -s localhost:8890/` should respond (401/JSON, not refused).

## Step 4 — Expose it with a Cloudflare Tunnel  🧑 (Cloudflare account) + 🤖 (config help)
A Cloudflare Tunnel is a free outbound connection from the Pi to Cloudflare's edge — no
port-forwarding, automatic HTTPS. You need a domain on Cloudflare (a cheap one is fine).
1. 🧑 `cloudflared` is installed on the Pi; `cloudflared tunnel login`.
2. 🤖/🧑 `cloudflared tunnel create spotify-mcp`; route a hostname, e.g.
   `spotify-mcp.<yourdomain>`, to `http://localhost:8890`.
3. 🧑 Run it as a service: `sudo cloudflared service install` (or a systemd unit).
4. Put the resulting `https://spotify-mcp.<yourdomain>` into the Pi `.env` as
   `MCP_PUBLIC_URL` and restart `spotify-mcp.service`.
> Alternative if you don't want a domain: a Cloudflare **quick tunnel** gives a random
> `*.trycloudflare.com` URL with zero setup — fine for testing, but it changes on every
> restart, so not great for a permanent connector.

## Step 5 — Smoke-test the public endpoint  🤖
```bash
curl -s https://spotify-mcp.<yourdomain>/ -H "Authorization: Bearer $MCP_BEARER_TOKEN"
```
Expect a JSON MCP response, not a connection error or HTML.

## Step 6 — Add the connector in the Claude mobile app  🧑
1. 🧑 Claude app → Settings → Connectors → **Add custom connector**.
2. 🧑 Enter the URL `https://spotify-mcp.<yourdomain>` and the bearer token from Step 2.
3. 🧑 In a chat, confirm the tools appear (`lastfm_similar_artists`, `taste_snapshot`,
   `search_verify`, `now_playing`) and the `knowledge://` resources are attachable.

> ⚠️ **Auth caveat to confirm on first connect:** the MCP connector spec leans on OAuth
> 2.1/PKCE; this server ships a simple static-bearer verifier (right call for one read-only
> user). If the app's connector flow insists on a full OAuth handshake, the fix is to front
> the tunnel with **Cloudflare Access (service token)** or swap `StaticBearerVerifier` for
> an OAuth verifier. We'll verify which the app wants the first time you add it and adjust
> then — it's the one step that genuinely needs a live test.

---

## Using it on the phone
Ask naturally — e.g. *"What's playing? Give me three new artists like it, check they're
real."* Mobile-me will call `now_playing` → `lastfm_similar_artists` → `search_verify`,
consult the `knowledge://` resources for an angle, and hand you verified picks. To actually
build the playlist, it uses the **built-in Spotify connector** (this server can't write).

## Security posture (why this is acceptable)
- **Read-only:** no playlist/library writes on the public server; worst case a leaked token
  exposes your music taste + lets someone run Last.fm/Spotify *searches*. No account writes.
- **Fail-closed auth:** the server refuses to start or serve without `MCP_BEARER_TOKEN`.
- **No secrets in the repo:** `.env` and `.cache` are gitignored and only copied to the Pi.
- Rotate the bearer token any time by changing `.env` + the connector config.
