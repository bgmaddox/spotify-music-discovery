"""Probe whether THIS Spotify app still has access to the deprecated endpoints.

Spotify deprecated several algorithmic endpoints for apps registered after
2024-11-27, grandfathering only apps that were in *extended quota mode*. Age
alone does not decide access, so we must test, not assume.

Run:  python probe.py
Prints, per endpoint, OK or "<status> restricted". The verdict decides whether
the plan's hard constraint (no algorithmic endpoints) holds or relaxes.
"""

from __future__ import annotations

import spotipy

from auth import get_client

# A well-known, stable track seed: Rick Astley - Never Gonna Give You Up.
SEED_TRACK = "4PTG3Z6ehGkBFwjybzWkR8"


def _probe(label: str, fn) -> None:
    try:
        fn()
        print(f"{label}: OK — endpoint is accessible")
    except spotipy.SpotifyException as e:
        print(f"{label}: {e.http_status} restricted — {e.msg or e.reason}")
    except Exception as e:  # noqa: BLE001 — surface anything unexpected
        print(f"{label}: ERROR — {type(e).__name__}: {e}")


def main() -> None:
    # Reads only; no write scopes needed to test the deprecated read endpoints.
    sp = get_client(["user-top-read"])

    print("Probing deprecated Spotify endpoints for this app...\n")
    _probe("audio-features", lambda: sp.audio_features([SEED_TRACK]))
    _probe(
        "recommendations",
        lambda: sp.recommendations(seed_tracks=[SEED_TRACK], limit=1),
    )

    print(
        "\nVerdict: if both report 'restricted', the plan's constraint holds — keep "
        "recommendation reasoning in Claude. If either is OK, report it; the plan can relax."
    )


if __name__ == "__main__":
    main()
