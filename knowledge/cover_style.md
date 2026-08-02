# Cover-art style — the Claude-playlist visual system

Read this before generating any playlist cover (via `cli.py generate-cover`). It's the
visual counterpart to the `🤖 ` name prefix: a consistent look so the user's Claude-built
playlists read as one curated collection. Lock the **style**, vary the **content**.

Generation is free/keyless via Pollinations (`cover_art.py`); upload is
`cli.py set-playlist-image`. Covers are square (1:1). Always run from the local CLI or
Pi (needs the app's write token), never the read-only MCP.

## The chosen direction: "Painterly worlds"

Each cover is a textured oil painting of an evocative scene matched to the playlist's
mood, with the *composition* mirroring the recipe that built it. Painterly hides AI
artifacts (garbled hands/instruments) far better than photoreal — lean into it.

## Prompt template

```
<subject/scene from the playlist's content>,
<composition rule from the recipe — see below>,
textured painterly impasto oil painting, soft cinematic light,
<palette mapped to genre/mood>, 1:1 album cover composition,
no text, no words, no lettering
```

Keep the last line verbatim every time — Pollinations otherwise sprinkles garbled text.

## Layer 1 — style (CONSTANT, the brand)

`textured painterly impasto oil painting, soft cinematic light, 1:1 album cover
composition, no text, no words, no lettering`. Don't drift from this — it's what makes
the set cohere.

## Layer 2 — content (varies per playlist)

Subject + palette from the playlist's genre and mood. Palette guide:

| Genre / mood            | Palette                                  |
|-------------------------|------------------------------------------|
| Americana / country     | warm amber, gold, burnt orange, dusk     |
| Indie / electronic      | neon blue, violet, cool city dusk        |
| Blues / roots           | deep indigo, brown, river twilight       |
| Hip hop / rap           | concrete grey, brass, warm streetlight   |
| Jazz / bossa            | candlelit amber, deep teal, smoky        |
| Christmas / winter      | cold blue, warm hearth gold, snow        |

Pick a subject that *says* the genre without text — instruments, landscapes, light,
weather, architecture. Avoid faces/figures (AI mangles them).

## Layer 3 — composition (mirrors the RECIPE — the meaningful bit)

| Recipe                  | Composition rule                                          |
|-------------------------|----------------------------------------------------------|
| Morph (A→B→C)           | left-to-right panoramic gradient journey across scenes   |
| Bridge (A↔B)            | two distinct elements meeting / fusing in the center     |
| Energy arc              | a rising-then-falling form (dawn→noon→dusk, swelling wave)|
| Deep cuts (anti-hits)   | subterranean, nocturnal, hidden-underground imagery       |
| Discovery ladder        | a path winding outward from a warm glowing center        |
| Occasion / mood set     | a single immersive scene of that occasion (dinner, drive) |
| Live cuts (Recipe 22)   | one immersive stage/venue scene — instruments and light, no crowd |
| Instrument portrait (30)| the instrument itself, single and central, against a horizon that shifts across scenes left-to-right |

## Conventions

- **Seed:** record the `--seed` used per cover so a cover can be regenerated identically.
- **One subject, uncluttered.** A single strong image beats a busy collage at thumbnail size.
- **No text, ever** — the playlist name carries the words; the cover is pure atmosphere.
