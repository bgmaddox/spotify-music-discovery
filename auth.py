"""Spotify OAuth helper.

Wraps spotipy.SpotifyOAuth so every script gets an authenticated client the same
way. Credentials come from .env (see .env.example). Token cache lives in .cache
(gitignored); the browser flow runs only on first use or when scopes widen.
"""

from __future__ import annotations

import os

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

_REQUIRED = ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI")

# On a headless host (the Pi MCP server) there's no browser/stdin: if the cached token
# is missing or unrefreshable, Spotipy's interactive flow would BLOCK forever waiting
# for a pasted redirect URL. Set SPOTIPY_NONINTERACTIVE=1 there so get_client raises a
# clean error instead — the read tools surface a tidy failure rather than hanging.
NONINTERACTIVE = os.getenv("SPOTIPY_NONINTERACTIVE", "").lower() in ("1", "true", "yes")


def _check_env() -> None:
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Missing Spotify credentials in environment/.env: "
            + ", ".join(missing)
            + "\nCopy .env.example to .env and fill in your Developer Dashboard values."
        )


def get_client(scopes: list[str] | str) -> spotipy.Spotify:
    """Return an authenticated Spotipy client for the requested scopes.

    `scopes` may be a list or a space-separated string. Spotipy caches the token
    in .cache and refreshes it automatically; re-auth in the browser is only
    triggered when the requested scope set is not already covered by the cache.
    """
    _check_env()
    if isinstance(scopes, (list, tuple)):
        scopes = " ".join(scopes)
    auth_manager = SpotifyOAuth(scope=scopes, open_browser=not NONINTERACTIVE)
    if NONINTERACTIVE:
        # Require an already-valid (or silently-refreshable) cached token; never prompt.
        token = auth_manager.cache_handler.get_cached_token()
        if not token or not auth_manager.validate_token(token):
            raise RuntimeError(
                "No valid cached Spotify token and SPOTIPY_NONINTERACTIVE is set "
                "(headless host). Pre-authorize locally and copy .cache here."
            )
    return spotipy.Spotify(auth_manager=auth_manager)
