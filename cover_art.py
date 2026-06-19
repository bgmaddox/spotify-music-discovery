"""Free cover-art generation via Pollinations.ai (no API key, no signup).

Pollinations serves Flux-model images over a plain HTTP GET, so it's the zero-cost
image source for playlist covers. This module only *fetches* an image; uploading it
to a playlist is `tools.set_playlist_image` (the Spotify write half). The two compose:
generate a cover here, then hand the path to `set-playlist-image`.

It's a free public service with no SLA — if it rate-limits or is down, retry, or swap
in another generator later (same fetch-bytes shape).

Library use:
    from cover_art import generate_cover
    path = generate_cover("warm americana wheat field at sunset")  # -> JPEG file path

CLI use:
    python cover_art.py generate-cover "prompt..." [--out cover.jpg] [--size 1024] [--seed N]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import urllib.parse

import requests

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"
DEFAULT_SIZE = 1024  # square; Spotify covers are 1:1
TIMEOUT = 120  # Pollinations can be slow to render on a cold request


def generate_cover(
    prompt: str,
    out_path: str | None = None,
    size: int = DEFAULT_SIZE,
    seed: int | None = None,
) -> str:
    """Generate a square cover image from `prompt` via Pollinations; save it; return the path.

    Free and keyless. Writes the returned JPEG bytes to `out_path` (or a temp .jpg if
    None). `seed` makes the result reproducible. Raises on a non-image response (the
    service occasionally returns an error page under load — treat that as a retry).
    """
    params = {"width": size, "height": size, "nologo": "true"}
    if seed is not None:
        params["seed"] = seed
    url = POLLINATIONS_URL + urllib.parse.quote(prompt) + "?" + urllib.parse.urlencode(params)

    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith("image/"):
        raise RuntimeError(
            f"Pollinations returned non-image content ({ctype!r}) — likely transient; retry."
        )

    if out_path is None:
        fd, out_path = tempfile.mkstemp(prefix="cover_", suffix=".jpg")
        os.close(fd)
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path


# --------------------------------------------------------------------------- CLI


def _cmd_generate_cover(args) -> int:
    try:
        path = generate_cover(
            args.prompt, out_path=args.out, size=args.size, seed=args.seed
        )
    except Exception as e:  # clean message, not a traceback (matches lastfm CLI)
        print(f"cover generation failed: {e}", file=sys.stderr)
        return 1
    print(path)
    print(f"  generated cover ({args.size}x{args.size}) -> {path}", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Free cover-art generation (Pollinations).")
    sub = p.add_subparsers(dest="cmd", required=True)

    gc = sub.add_parser(
        "generate-cover", help="Generate a square cover image via Pollinations (free)."
    )
    gc.add_argument("prompt", help="Image description (no text/words render well).")
    gc.add_argument("--out", help="Output path (default: a temp .jpg).")
    gc.add_argument("--size", type=int, default=DEFAULT_SIZE, help="Square edge in px.")
    gc.add_argument("--seed", type=int, default=None, help="Seed for reproducibility.")
    gc.set_defaults(func=_cmd_generate_cover)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
