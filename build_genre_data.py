"""One-time parser: everynoise engenremap.html -> knowledge/genres_coords.json.

everynoise.com (Glenn McDonald) is a frozen 2023 snapshot — its live data feeds
died when he was laid off from Spotify, the same deprecation that killed this app's
algorithmic endpoints. But the genre *map* is timeless enough to be useful: each
genre is placed on a 2-D map where position encodes its sonic signature, so genres
that sit near each other sound near each other. We harvest that adjacency ONCE here.

This is data extraction, not recommendation logic — the reasoning still lives in the
Claude session (Mode A). Re-run only if you re-download a newer engenremap.html:

    curl -s https://everynoise.com/engenremap.html -o /tmp/engenremap.html
    python build_genre_data.py /tmp/engenremap.html

Output: knowledge/genres_coords.json — a list of {name, x, y, color, size, example}.
This file is machine-only; do NOT read it wholesale into a reasoning session. Query
it via `python cli.py genre-neighbors "<genre>"`.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "knowledge", "genres_coords.json")

# Each genre is one <div class="genre ..."> with its position baked into the inline
# style (top/left px = its map coordinates) and its name as the 2nd playx() arg.
_DIV = re.compile(r'<div\b[^>]*class="genre[^"]*"[^>]*>', re.IGNORECASE)
_STYLE = re.compile(r'style="([^"]*)"', re.IGNORECASE)
_COLOR = re.compile(r"color:\s*(#[0-9a-fA-F]{3,6})")
_TOP = re.compile(r"top:\s*(-?\d+)px")
_LEFT = re.compile(r"left:\s*(-?\d+)px")
_SIZE = re.compile(r"font-size:\s*(\d+)%")
# onclick="playx(&quot;ID&quot;, &quot;genre name&quot;, this)" — 2nd arg is the name.
_NAME = re.compile(r"playx\(&quot;[^&]*&quot;,\s*&quot;(.*?)&quot;")
# title="e.g. Artist &quot;Track&quot;" — the leading example artist.
_EXAMPLE = re.compile(r'title="e\.g\.\s*(.*?)\s*&quot;')
# the navlink right after the div: <a class=navlink href="engenremap-<slug>.html">
_HREF = re.compile(r'href="(engenremap-[^"]+\.html)"')


def parse(html_text: str) -> list[dict]:
    genres: list[dict] = []
    for m in _DIV.finditer(html_text):
        tag = m.group(0)
        style = _STYLE.search(tag)
        name = _NAME.search(tag)
        top = _TOP.search(style.group(1)) if style else None
        left = _LEFT.search(style.group(1)) if style else None
        if not (name and top and left):
            continue  # skip any div that isn't a fully-positioned genre node
        color = _COLOR.search(style.group(1))
        size = _SIZE.search(style.group(1))
        example = _EXAMPLE.search(tag)
        # the per-genre page link sits in the navlink just after this div's text
        href = _HREF.search(html_text, m.end(), m.end() + 400)
        genres.append(
            {
                "name": html.unescape(name.group(1)),
                "x": int(left.group(1)),
                "y": int(top.group(1)),
                "color": color.group(1) if color else None,
                "size": int(size.group(1)) if size else None,
                "example": html.unescape(example.group(1)) if example else None,
                "href": href.group(1) if href else None,
            }
        )
    return genres


def main(argv: list[str]) -> int:
    src = argv[0] if argv else "/tmp/engenremap.html"
    out = argv[1] if len(argv) > 1 else DEFAULT_OUT
    with open(src, encoding="utf-8") as fh:
        genres = parse(fh.read())
    if not genres:
        print(f"No genres parsed from {src}", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(genres, fh, ensure_ascii=False, separators=(",", ":"))
    print(out)
    print(f"  parsed {len(genres)} genres", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
