# DEPLOY_MCP.md — putting the discovery server on your phone (Mode C)

Goal: run `mcp_server.py` on the Pi, expose it at a public HTTPS URL, and add it to the
Claude mobile app as a custom connector. Read-only discovery server; playlist writes stay
with Claude's built-in Spotify connector.

> **STATUS: DEPLOYED (2026-06-14).** Live behind a **capability URL** —
> `https://rachett.tail504ae5.ts.net/discovery-mcp-<secret>` (the exact secret path lives
> in the Pi `.env` as `MCP_PATH`, not in this repo). Uses **Tailscale Funnel + Caddy** (not
> Cloudflare — see history note). 🤖 = Claude did it over SSH. 🧑 = you do it (browser/phone).

---

## Architecture (as built)
```
 Phone Claude app ──HTTPS──> Anthropic cloud ──HTTPS──> rachett.tail504ae5.ts.net
                                                          │ (Tailscale Funnel, already on)
                                                     Caddy :80 on the Pi
                                                          │  /discovery-mcp-<secret>*  (no
                                                          │   auth; the secret path IS the
                                                          │   credential — a capability URL)
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
  additive and complementary (discovery signal + taste + knowledge).
- **Why a capability URL, not a bearer:** Claude's managed connector (web/mobile) only
  supports **OAuth (DCR/PKCE) or no-auth** — there is no field to supply a static bearer or
  custom header. A bearer gated at Caddy returns a 401 the connector can't satisfy
  ("couldn't register with the sign-in service"). So we serve **no-auth at an unguessable
  secret path**: the connector treats it as a no-auth server, and the secret in the URL is
  the de-facto credential. Proportionate because the server is **read-only** (music taste).
- The server runs in **proxy-auth mode** (`MCP_TRUST_PROXY_AUTH=1`): a naked
  streamable-http endpoint with no app-level OAuth advertisement, bound to `127.0.0.1` so
  only Caddy reaches it. Caddy routes only the secret path to it; every other path falls
  through (never reaching 8890). Rotate by changing `MCP_PATH` + the Caddy `handle` path.

---

## As-built coordinates

| Piece | Value |
|---|---|
| Pi app dir | `/home/bgmaddox/apps/SpotifyDiscoveryMCP` |
| Service | `spotify-discovery-mcp.service` |
| Local bind | `127.0.0.1:8890`, path `/discovery-mcp-<secret>` (from `MCP_PATH`) |
| Public URL | `https://rachett.tail504ae5.ts.net/discovery-mcp-<secret>` (the capability URL) |
| Auth | none at the proxy — the unguessable secret path is the credential |
| Caddyfile | `/etc/caddy/Caddyfile` (`handle /discovery-mcp-<secret>* → :8890`; backup `.bak.<ts>` per edit) |

`.env` on the Pi (perms 600; `MCP_PATH` holds the secret — treat the file as a credential):
```
SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET / SPOTIPY_REDIRECT_URI   # same Spotify app
LASTFM_API_KEY / LASTFM_SECRET
MCP_TRUST_PROXY_AUTH=1
MCP_HOST=127.0.0.1
MCP_PORT=8890
MCP_PATH=/discovery-mcp-<secret>     # the capability secret; Caddy routes this path only
MCP_PUBLIC_URL=https://rachett.tail504ae5.ts.net/discovery-mcp-<secret>
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

## Add the connector  🧑
The phone app has no "Add custom connector" entry — add it on **claude.ai (web)** or
Claude Desktop and it syncs to mobile. Requires a paid plan (Pro/Max).
1. claude.ai → Settings → Connectors → **Add custom connector**.
2. URL: the full capability URL (`…/discovery-mcp-<secret>` — get it from the Pi `.env`
   `MCP_PATH`, or ask Claude). **Leave OAuth Client ID/Secret blank** — it's a no-auth
   server; the secret path is the credential.
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

# taste data auto-refreshes daily via spotify-discovery-refresh.timer (~04:00).
#   This needs a .cache minted with --read-all (the three taste read scopes). Check/run:
ssh rachett 'systemctl list-timers spotify-discovery-refresh.timer --no-pager'
ssh rachett 'sudo systemctl start spotify-discovery-refresh.service'   # force a refresh now
ssh rachett 'journalctl -u spotify-discovery-refresh.service -n 20 --no-pager'
#   (manual fallback: scp a fresh local dump up)
scp $(ls -t data/taste_*.json | head -1) rachett:/home/bgmaddox/apps/SpotifyDiscoveryMCP/data/

# public smoke test (no auth header — the secret path is the credential)
curl -s -X POST "https://rachett.tail504ae5.ts.net/$(ssh rachett 'grep ^MCP_PATH= /home/bgmaddox/apps/SpotifyDiscoveryMCP/.env | cut -d= -f2 | sed s,^/,,')" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}'
```

## Static showcase page (`/discovery`)

The playlist journal + recipe book is served as a single self-contained HTML page at
`https://rachett.tail504ae5.ts.net/discovery` (public over the same Funnel, no auth — it's a
portfolio piece). Source of truth is `docs/recipes.html` in the repo; on the Pi it lives at
`/var/www/discovery/index.html`, served by Caddy `file_server`.

- **Why `/var/www`, not the app dir:** `/home/bgmaddox` is `drwx------`, so the `caddy`
  user can't traverse into it (file_server 403). `/var/www/discovery` is world-traversable
  and owned by `bgmaddox`, so redeploys need no sudo and Caddy can still read it.
- **Caddy route** (in `/etc/caddy/Caddyfile`): an **exact-match** named matcher so it can
  never shadow the MCP capability path (`/discovery-mcp-<secret>*`) — order-independent:
  ```
  @discovery path /discovery /discovery/
  handle @discovery {
      root * /var/www/discovery
      rewrite * /index.html
      file_server
  }
  ```

```bash
# redeploy the page after editing docs/recipes.html (no Caddy change, no restart)
scp docs/recipes.html rachett:/var/www/discovery/index.html
# verify over the Funnel
curl -s -o /dev/null -w "%{http_code}\n" https://rachett.tail504ae5.ts.net/discovery   # 200
```

### Taste timeline page (`/discovery/history`)

The interactive taste-timeline visualization (`docs/history.html`, self-contained: D3 v7 +
`data/taste_timeline.json` inlined) is served the same way from the same directory. Its
Caddy route is a second exact-match matcher (the `@discovery` matcher is exact, so it never
serves subpaths):

```
@history path /discovery/history /discovery/history/
handle @history {
    root * /var/www/discovery
    rewrite * /history.html
    file_server
}
```

```bash
# redeploy after editing docs/history.html (no Caddy change, no restart)
scp docs/history.html rachett:/var/www/discovery/history.html
curl -s -o /dev/null -w "%{http_code}\n" https://rachett.tail504ae5.ts.net/discovery/history  # 200
```

If the underlying data changes, rebuild + re-embed first: `python cli.py timeline-build`,
then re-inject the JSON into `docs/history.html` (see `TASTE_TIMELINE_PLAN.md` → rebuild
note) before the `scp`.

## Using it on the phone
Ask naturally — e.g. *"What's playing? Give me three new artists like it, check they're
real."* Mobile-me will call `now_playing` → `lastfm_similar_artists` → `search_verify`,
consult the `knowledge://` resources for an angle, and hand you verified picks. To actually
build the playlist, it uses the **built-in Spotify connector** (this server can't write).

## Security posture
- **Capability URL:** auth is the unguessable secret in the path (≈32 random chars). This
  is "anyone with the link" — proportionate here because the data is **read-only music
  taste**, not account access. Worst case if the URL leaked: someone could read your taste +
  current track and run Spotify/Last.fm searches — no writes. Leak risk is low (the URL
  travels server-to-server over HTTPS, not browser history).
- **Read-only token:** the Spotify cache is scoped `user-read-currently-playing` only — it
  cannot modify your account even if exfiltrated.
- **Bound to localhost:** the app listens on `127.0.0.1:8890`; only Caddy reaches it, and
  Caddy routes *only* the secret path there — every other path falls through.
- **No secrets in the repo:** `.env` (which holds `MCP_PATH`, the secret) and `.cache` are
  gitignored, only on the Pi.
- **Rotate** any time: change `MCP_PATH` in `.env` and the `handle` path in the Caddyfile,
  `reload caddy` + `restart` the service, then update the connector URL.
- **Want real auth later?** Implement OAuth (DCR/PKCE) in `mcp_server.py` — the connector's
  native path, and free (no Cloudflare/domain needed). Scoped but not yet built.

---

## History note
Two pivots from the original plan, both on contact with reality:
1. **Cloudflare → Tailscale Funnel.** The plan targeted a Cloudflare Tunnel, but the Pi
   already had Tailscale Funnel + Caddy running a sibling Spotify MCP server, so we mirrored
   that — simpler, no domain/Cloudflare account.
2. **Static bearer → capability URL.** We first gated the route with a static bearer at
   Caddy (assuming, from the sibling server, that the app accepts one). It doesn't: Claude's
   managed connector only does OAuth (DCR/PKCE) or no-auth, with no field for a bearer/header
   — so the bearer 401 failed with "couldn't register with the sign-in service." We switched
   to a no-auth secret path. (Cloudflare Access was considered but doesn't help: its machine
   auth is header-based service tokens the connector also can't supply.)
