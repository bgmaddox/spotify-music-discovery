"""Phase 6: remote MCP server — read-only discovery primitives for mobile Claude.

This is "Mode C": instead of a Claude Code session reading the repo, a remote Claude
client (e.g. the phone app) connects to this server over the internet and calls these
tools. It exposes ONLY read-only discovery primitives — the Last.fm signal, a taste
snapshot, search-verify, now-playing — plus the knowledge base (RECIPES.md +
knowledge/*.md) as MCP **resources** so the remote model can still follow the recipes
and discovery angles it can't read off disk.

By design it has NO write capability: playlist creation / saving stays with Claude's
built-in Spotify connector (decision: smallest public attack surface — see plan §Phase 6).

Hosting: behind a Cloudflare Tunnel on the Pi (public HTTPS). See DEPLOY_MCP.md.
Auth: a static bearer token (MCP_BEARER_TOKEN in .env) — single-user, read-only.
Spotify auth: reuses the cached refresh token (.cache); pre-authorize once locally and
copy .cache to the Pi (search/now-playing refresh silently, never opening a browser).

Run locally for a smoke test:
    MCP_BEARER_TOKEN=dev python mcp_server.py            # serves on 0.0.0.0:8890
"""

from __future__ import annotations

import glob
import json
import os

from dotenv import load_dotenv
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

import lastfm
import sensing
import taste_profile
import tools

load_dotenv()

HERE = os.path.dirname(__file__)
PUBLIC_URL = os.getenv("MCP_PUBLIC_URL", "http://localhost:8890")
HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "8890"))


class StaticBearerVerifier(TokenVerifier):
    """Verify the single shared bearer token from MCP_BEARER_TOKEN.

    Adequate for a single-user, read-only personal server. If MCP_BEARER_TOKEN is
    unset the server refuses every request (fail closed) rather than running open.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        expected = os.getenv("MCP_BEARER_TOKEN")
        if expected and token == expected:
            return AccessToken(token=token, client_id="brett-mobile", scopes=["read"])
        return None


mcp = FastMCP(
    "Spotify Discovery (read-only)",
    stateless_http=True,
    json_response=True,
    host=HOST,
    port=PORT,
    token_verifier=StaticBearerVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(PUBLIC_URL),
        resource_server_url=AnyHttpUrl(PUBLIC_URL),
        required_scopes=["read"],
    ),
)


# ------------------------------------------------------------------- tools (read)


@mcp.tool()
def lastfm_similar_artists(artist: str, limit: int = 30) -> list[dict]:
    """Last.fm artists similar to a seed artist, ranked by match (1.0 = closest).

    Use as the external discovery signal (Recipe 6): high match = center-of-taste,
    mid = one-axis stretch, tail = left-field. Prefer names NOT already in the user's
    taste (call `taste_snapshot` to check). Returns [{name, match}].
    """
    return lastfm.similar_artists(artist, limit=limit)


@mcp.tool()
def lastfm_similar_tracks(artist: str, title: str, limit: int = 30) -> list[dict]:
    """Last.fm tracks similar to a seed track. Returns [{artist, title, match}]."""
    return lastfm.similar_tracks(artist, title, limit=limit)


@mcp.tool()
def lastfm_artist_tags(artist: str, limit: int = 10) -> list[dict]:
    """Top crowd tags for an artist (coarse genre/mood signal). Returns [{tag, count}].

    Note: Last.fm tags can mis-resolve for some artists (e.g. Afrobeats) — cross-check
    against the genre map resource and trust Spotify genres when they conflict.
    """
    return lastfm.artist_tags(artist, limit=limit)


def _artist_names(track: dict) -> str:
    """Join a track's artist names, tolerating both shapes a dump can carry.

    Artist entries are normally {name: ...} dicts, but some dumps store plain strings;
    this normalizes either to a comma-joined string and drops blanks. (Regression: a
    str-vs-dict mismatch here once crashed taste_snapshot — see the test.)
    """
    names = [a if isinstance(a, str) else a.get("name", "") for a in track.get("artists", [])]
    return ", ".join(n for n in names if n)


@mcp.tool()
def taste_snapshot() -> dict:
    """A compact summary of the user's taste from the latest local dump.

    Returns {generated_at, top_artists_long_term, top_genres, recently_played} for
    grounding recommendations and for filtering candidates to genuinely-new artists.
    Reads the newest data/taste_*.json on the server (refreshed out-of-band); does not
    hit Spotify. Returns {error: ...} if no dump is present.
    """
    paths = glob.glob(os.path.join(taste_profile.DATA_DIR, "taste_*.json"))
    if not paths:
        return {"error": "no taste dump on server; run dump-taste and sync data/"}
    d = json.load(open(max(paths, key=os.path.getmtime)))
    top = d.get("top_artists", {}).get("long_term", [])[:30]
    genres: dict[str, int] = {}
    for a in top:
        for g in a.get("genres", []):
            genres[g] = genres.get(g, 0) + 1
    top_genres = sorted(genres, key=genres.get, reverse=True)[:15]

    recent = [
        f"{t.get('name')} — {_artist_names(t)}"
        for t in d.get("recently_played", [])[:15]
    ]
    return {
        "generated_at": d.get("generated_at"),
        "top_artists_long_term": [a.get("name") for a in top],
        "top_genres": top_genres,
        "recently_played": recent,
    }


@mcp.tool()
def search_verify(artist: str, title: str) -> dict:
    """Confirm a track exists on Spotify before recommending it (the hard rule).

    Every track the model names MUST pass through this. Returns
    {found: bool, uri, name, artists, album}. A miss means a hallucinated/mis-titled
    track — drop it or retry with a corrected title.
    """
    detail = tools.verify_detail(artist, title)
    if not detail:
        return {"found": False}
    return {"found": True, **detail}


@mcp.tool()
def now_playing() -> dict:
    """What the user is currently playing, or {playing: False} if nothing is.

    Returns {playing, uri, title, artists, album} for now-playing companion / rabbit-hole
    workflows. Uses the server's cached Spotify token (read-only scope).
    """
    np = sensing.now_playing()
    if not np:
        return {"playing": False}
    return {
        "playing": True,
        "uri": np["uri"],
        "title": np["title"],
        "artists": np["artists"],
        "album": np["album"],
    }


# --------------------------------------------------------------- resources (read)


def _read(rel: str) -> str:
    path = os.path.join(HERE, rel)
    if not os.path.exists(path):
        return f"(missing on server: {rel})"
    with open(path) as f:
        return f.read()


@mcp.resource("knowledge://recipes")
def recipes() -> str:
    """The session-driven discovery workflows (RECIPES.md), incl. Recipe 6."""
    return _read("RECIPES.md")


@mcp.resource("knowledge://heuristics")
def heuristics() -> str:
    """The discovery angles + user preferences (discovery_heuristics.md)."""
    return _read("knowledge/discovery_heuristics.md")


@mcp.resource("knowledge://genre-map")
def genre_map() -> str:
    """Static genre adjacencies for the user's clusters (genre_map.md)."""
    return _read("knowledge/genre_map.md")


if __name__ == "__main__":
    if not os.getenv("MCP_BEARER_TOKEN"):
        raise SystemExit("Refusing to start: set MCP_BEARER_TOKEN in .env first.")
    mcp.run(transport="streamable-http")
