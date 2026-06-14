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
    auth_manager = SpotifyOAuth(scope=scopes, open_browser=True)
    return spotipy.Spotify(auth_manager=auth_manager)
