# Canon lists — published greatest-albums lists as a fixed candidate pool

Read this before running **Recipe 35 (Canon crawl)**. It explains what the list files
are, how to read them, and how to add another one.

## What's here

| File | List | Retrieved |
|---|---|---|
| `paste300_albums.json` | Paste Magazine — *The 300 Greatest Albums of All Time* | 2026-08-02 |

Schema is flat and list-agnostic:

```json
{"source": "...", "url": "...", "retrieved": "YYYY-MM-DD", "note": "...",
 "albums": [{"rank": 1, "artist": "Stevie Wonder", "album": "Songs in the Key of Life", "year": 1976}, ...]}
```

`rank` 1 = best. These are tracked in git (static reference data, not a personal dump) via
a `.gitignore` negation, since `*.json` is ignored by default — the same treatment
`knowledge/genres_coords.json` gets.

## How to read it

**Never `Read` a list file directly** — 300 rows is a lot of tokens for data that is
uninteresting on its own. Use the accessor:

```bash
python cli.py canon-snapshot                      # ~2k tokens, tiered against your history
python cli.py canon-snapshot --near-miss 80       # widen the near-miss window
python cli.py canon-snapshot --list-path knowledge/<other>.json
```

The raw list is only a pool. The useful structure is the **overlap** with what the user
has actually played, which is what `canon_list.py` computes:

- **`lived_in`** — album has ≥15 plays. Anchors only.
- **`brushed`** — 1–14 plays. Usually means one track surfaced on shuffle once; treat as
  unheard unless the count is genuinely high.
- **`near_miss`** — artist is known and liked, this album never opened. **The good tier.**
- **`unheard`** — artist never played at all.

## Two things that will bite you

1. **The export is not the whole truth.** Tiering reads the merged GDPR + Apple history,
   which ends at its last export date. The Spotify API's recency-weighted windows know
   about newer plays. `canon_list.py` cross-checks `discovery_log.known_listened_artists()`
   for exactly this reason — without it, Erykah Badu tiered as "unheard" on the first run
   despite sitting in the current taste dump. Don't remove that cross-check.

2. **Album matching is deliberately loose.** `_album_matches` accepts containment, so
   reissues and edition suffixes still match. This is the opposite of the album-art search
   gate (≥0.87 similarity), and on purpose: here a false positive only drops a candidate
   from the pool, while a false negative would tell the user they've never heard a record
   they play constantly.

## Adding another list

1. Parse it to the schema above and save as `knowledge/<name>_albums.json`.
2. Add a `.gitignore` negation (`!knowledge/<name>_albums.json`).
3. Add a row to the table above.
4. Run it with `cli.py canon-snapshot --list-path knowledge/<name>_albums.json`.

No code changes needed — the loader is list-agnostic. Verify rank integrity after parsing
(the Paste page's rank 269 has a 30-word album title that overflowed a naive heading regex
and silently dropped a row on the first attempt; check for gaps in `1..N` before saving).
