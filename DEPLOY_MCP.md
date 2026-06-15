# DEPLOY_MCP.md — putting the discovery server on your phone (Mode C)

Goal: run `mcp_server.py` on the Pi, expose it at a public HTTPS URL, and add it to the
Claude mobile app as a custom connector. Read-only discovery server; playlist writes stay
with Claude's built-in Spotify connector.

> **STATUS: DEPLOYED (2026-06-14).** Live at
> `https://rachett.tail504ae5.ts.net/discovery-mcp`. This runbook documents the
> *as-built* setup, which uses **Tailscale Funnel + Caddy** (not Cloudflare — see history
> note at the bottom). 🤖 = Claude did it over SSH. 🧑 = you do it (browser/phone).

---

## Architecture (as built)
```
 Phone Claude app ──HTTPS──> Anthropic cloud ──HTTPS──> rachett.tail504ae5.ts.net
                                                          │ (Tailscale Funnel, already on)
                                                     Caddy :80 on the Pi
                                                          │  /discovery-mcp*  (gated by a
                                                          │   static bearer at Caddy)
                                                     mcp_server.py @ 127.0.0.1:8890
                                                          │        │
                                                     Last.fm   Spotify (read, via .cache)
```
Key facts that shaped this:
- **Anthropic connects from its cloud, not your phone** — the server must be public.
  Tailscale **Funnel** (already enabled on the Pi → Caddy on :80) provides that; no
  Cloudflare, no router ports.
- A **sibling MCP server already lives here**: the Node `spotify-mcp-server` (playback +
  playlist writes) at `apps/SpotifyMCP`, exposed via supergateway on `/mcp`. Ours is
  additive and complementary (discovery signal + taste + knowledge), on `/discovery-mcp`.
- The Node server proved the Claude mobile app **accepts a plain static bearer** gated at
  the proxy — no OAuth handshake needed. So ours runs in **proxy-auth mode**
  (`MCP_TRUST_PROXY_AUTH=1`): a naked streamable-http endpoint, with Caddy holding the
  bearer. Bound to `127.0.0.1` so only Caddy (not the whole tailnet) can reach the port.

---

## As-built coordinates

| Piece | Value |
|---|---|
| Pi app dir | `/home/bgmaddox/apps/SpotifyDiscoveryMCP` |
| Service | `spotify-discovery-mcp.service` |
| Local bind | `127.0.0.1:8890`, path `/discovery-mcp` |
| Public URL | `https://rachett.tail504ae5.ts.net/discovery-mcp` |
| Auth | static bearer matched at Caddy (`@discoveryAuthed`); separate from the Node token |
| Caddyfile | `/etc/caddy/Caddyfile` (backup `.bak.<ts>` written on each edit) |

`.env` on the Pi (perms 600):
```
SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET / SPOTIPY_REDIRECT_URI   # same Spotify app
LASTFM_API_KEY / LASTFM_SECRET
MCP_TRUST_PROXY_AUTH=1
MCP_HOST=127.0.0.1
MCP_PORT=8890
MCP_PATH=/discovery-mcp
MCP_PUBLIC_URL=https://rachett.tail504ae5.ts.net/discovery-mcp
MCP_ALLOWED_HOSTS=rachett.tail504ae5.ts.net,127.0.0.1:8890,localhost:8890
SPOTIPY_NONINTERACTIVE=1
```
Two non-obvious env vars, both learned the hard way during deploy:
- **`MCP_ALLOWED_HOSTS`** — the MCP streamable-http transport validates the `Host` header
  (DNS-rebinding protection). Behind the proxy the upstream sees the public hostname, so it
  must be whitelisted or every request 421s.
- **`SPOTIPY_NONINTERACTIVE=1`** — without a cached token Spotipy's OAuth flow blocks
  forever waiting for a pasted redirect URL; this makes `get_client` fail fast instead.

---

## Enabling `search_verify` + `now_playing` (the Spotify `.cache`)  🧑 browser + 🤖 copy

4 of 6 tools (the three `lastfm_*` + `taste_snapshot`) and all `knowledge://` resources
work with no Spotify token. `search_verify` and `now_playing` need a read-only Spotify
token cached on the Pi. Mint it on your Mac (it has the browser):

1. 🧑 `python mint_pi_cache.py` — approve the consent once. Writes `.cache_pi_readonly`
   (scope `user-read-currently-playing` only) **without touching your main `.cache`**.
2. 🤖 Copy it to the Pi as `.cache` and restart:
   ```bash
   scp .cache_pi_readonly rachett:/home/bgmaddox/apps/SpotifyDiscoveryMCP/.cache
   ssh rachett 'sudo systemctl restart spotify-discovery-mcp.service'
   ```
The token renews silently forever; `SPOTIPY_NONINTERACTIVE=1` means a bad/expired cache
just surfaces a tidy error rather than hanging.

---

## Add the connector in the Claude mobile app  🧑
1. Claude app → Settings → Connectors → **Add custom connector**.
2. URL: `https://rachett.tail504ae5.ts.net/discovery-mcp` — and the bearer token (stored
   in the Pi's Caddyfile under `@discoveryAuthed`; ask Claude/look there if you need it).
3. In a chat, confirm the tools appear (`lastfm_similar_artists`, `lastfm_similar_tracks`,
   `lastfm_artist_tags`, `taste_snapshot`, `search_verify`, `now_playing`) and the
   `knowledge://` resources are attachable.

---

## Operating it

```bash
# health / restart / logs
ssh rachett 'systemctl status spotify-discovery-mcp.service'
ssh rachett 'sudo systemctl restart spotify-discovery-mcp.service'
ssh rachett 'journalctl -u spotify-discovery-mcp.service -n 50 --no-pager'

# deploy a code change
ssh rachett 'cd /home/bgmaddox/apps/SpotifyDiscoveryMCP && git pull --ff-only && sudo systemctl restart spotify-discovery-mcp.service'

# refresh taste data on the Pi (taste_snapshot reads the newest data/taste_*.json)
#   copy a fresh dump up, or run dump-taste on the Pi once a .cache is present
scp $(ls -t data/taste_*.json | head -1) rachett:/home/bgmaddox/apps/SpotifyDiscoveryMCP/data/

# public smoke test
curl -s -X POST https://rachett.tail504ae5.ts.net/discovery-mcp \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}'
```

## Using it on the phone
Ask naturally — e.g. *"What's playing? Give me three new artists like it, check they're
real."* Mobile-me will call `now_playing` → `lastfm_similar_artists` → `search_verify`,
consult the `knowledge://` resources for an angle, and hand you verified picks. To actually
build the playlist, it uses the **built-in Spotify connector** (this server can't write).

## Security posture
- **Read-only:** no playlist/library writes on the public server. The Spotify token is
  scoped `user-read-currently-playing` only — it can't modify your account.
- **Bound to localhost:** the app listens on `127.0.0.1:8890`; only Caddy reaches it. The
  bearer is enforced at Caddy (`/discovery-mcp*` without it → 401).
- **No secrets in the repo:** `.env` and `.cache` are gitignored, only copied to the Pi.
- Rotate the bearer any time: edit `@discoveryAuthed` in the Caddyfile, `sudo systemctl
  reload caddy`, and update the connector config.

---

## History note
The original plan targeted a **Cloudflare Tunnel** (Steps 1–6 of the prior draft). On
deploy we found the Pi already had Tailscale Funnel + Caddy running a sibling Spotify MCP
server, so we mirrored that proven path instead — simpler, no domain/Cloudflare account,
and it confirmed the static-bearer connector flow works. The Cloudflare route remains a
valid fallback if the Funnel is ever retired.
