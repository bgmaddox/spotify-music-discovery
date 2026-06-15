"""One-off helper: mint a READ-ONLY Spotify token cache for the headless Pi MCP server.

The Pi's discovery server needs a Spotify token for `search_verify` (no scope) and
`now_playing` (`user-read-currently-playing`). It can't run the browser OAuth flow
headless, so authorize once HERE (on a machine with a browser) and copy the result.

This writes to a SEPARATE cache file (`.cache_pi_readonly`) so your main `.cache`
(which holds the playlist-write superset for local playlist builds) is left untouched.
The minted token carries ONLY `user-read-currently-playing` — a strict read-only subset,
so the Pi can never modify playlists even if the token leaked.

Run:
    python mint_pi_cache.py
Then copy the file to the Pi as `.cache` (the deploy step does this for you).
"""

from __future__ import annotations

from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

CACHE_PATH = ".cache_pi_readonly"
SCOPE = "user-read-currently-playing"  # search needs no scope; this is the only extra


def main() -> None:
    oauth = SpotifyOAuth(scope=SCOPE, cache_path=CACHE_PATH, open_browser=True)
    # Triggers the browser flow (Spotipy auto-captures the redirect on 127.0.0.1:8889)
    # and writes the refresh token to CACHE_PATH.
    oauth.get_access_token(check_cache=False)
    print(f"Wrote {CACHE_PATH} (scope: {SCOPE}).")
    print("Copy it to the Pi as .cache to enable search_verify + now_playing.")


if __name__ == "__main__":
    main()
