# config/ — per-user personalization

These files are the knobs a new user edits to make the timeline reflect *their*
listening instead of the original author's. Code falls back to safe defaults if a
file is missing, but both are committed so a fresh clone works out of the box.

| File | What it controls |
|------|------------------|
| `household_artists.txt` | Artists excluded from taste analysis (kids' music, sleep audio). One name per line, `#` comments. A `white noise` name match is always excluded. |
| `tag_buckets.json` | Last.fm tag → genre-bucket mapping used to color/aggregate everything. Ordered: more-specific tags must come before generic ones (first match wins on substring fallback). |

**Bucket names are a fixed set** — they must match the `BUCKETS` array in
`docs/history.html` (which carries the color palette):
`folk/americana, country, soul/blues, indie rock, hip hop, classic rock, pop,
electronic, jazz, metal/punk, soundtrack, other, kids/household`.
Map your tags onto these buckets; don't invent new bucket names unless you also
add them (and a color) to the front-end.
