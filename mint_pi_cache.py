"""One-off helper: mint a READ-ONLY Spotify token cache for the headless Pi MCP server.

The Pi's discovery server needs a Spotify token for `search_verify` (no scope) and
`now_playing` (`user-read-currently-playing`). If the Pi also self-refreshes its taste
dump (the systemd timer), the token additionally needs the three taste read scopes
(`user-top-read`, `user-read-recently-played`, `user-library-read`). The Pi can't run the
browser OAuth flow headless, so authorize once HERE (on a machine with a browser) and
copy the result.

This writes to a SEPARATE cache file (`.cache_pi_readonly`) so your main `.cache`
(which holds the playlist-write superset for local playlist builds) is left untouched.
Every scope option below is READ-ONLY — no `playlist-modify` — so the Pi can never modify
your account even if the token leaked.

Run (minimal — search + now_playing only):
    python mint_pi_cache.py

Run (read-all — also lets the Pi self-refresh the taste dump; use this for the timer):
    python mint_pi_cache.py --read-all

Then copy the file to the Pi as `.cache` (the deploy step does this for you).
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

CACHE_PATH = ".cache_pi_readonly"
MINIMAL_SCOPE = "user-read-currently-playing"  # search needs no scope; this is the extra
# Read-only superset: the above + the three taste read scopes (no write scopes ever).
READ_ALL_SCOPES = " ".join(
    [
        "user-read-currently-playing",
        "user-top-read",
        "user-read-recently-played",
        "user-library-read",
    ]
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Mint a read-only Spotify cache for the Pi.")
    ap.add_argument(
        "--read-all",
        action="store_true",
        help="Include the taste read scopes so the Pi can self-refresh dump-taste.",
    )
    ap.add_argument(
        "--scopes",
        help="Explicit space/comma-separated scope list (overrides --read-all).",
    )
    args = ap.parse_args()

    if args.scopes:
        scope = " ".join(s.strip() for s in args.scopes.replace(",", " ").split())
    elif args.read_all:
        scope = READ_ALL_SCOPES
    else:
        scope = MINIMAL_SCOPE

    oauth = SpotifyOAuth(scope=scope, cache_path=CACHE_PATH, open_browser=True)
    # Triggers the browser flow (Spotipy auto-captures the redirect on 127.0.0.1:8889)
    # and writes the refresh token to CACHE_PATH.
    oauth.get_access_token(check_cache=False)
    print(f"Wrote {CACHE_PATH} (scopes: {scope}).")
    print("Copy it to the Pi as .cache.")


if __name__ == "__main__":
    main()
