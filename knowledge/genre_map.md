# genre_map.md — static genre-adjacency reference

> **What this is.** A frozen lookup of "what sits next to what" for the user's core
> clusters, seeded from the *Every Noise at Once* micro-genre taxonomy (Glenn McDonald's
> Spotify-genre map — no longer updated after his 2023 layoff, but the adjacencies are
> stable). It is a **starting point for an angle**, not live data: use it to pick a
> *direction*, then confirm specific artists with Last.fm (`lastfm.py`) and confirm
> specific tracks with `search_verify`.
>
> **Scope.** Centered on the user's established taste (modern Americana / outlaw-country
> revival, indie folk — per the Phase 3 library scan and taste dumps). Expand it as the
> taste profile grows; this is meant to be edited.
>
> **How to read a row.** `cluster → neighbors`. Neighbors are ordered roughly nearest →
> farthest. Anchor artists are *examples to seed from or verify against*, not a playlist.

---

## Core clusters & their neighbors

### Modern Americana / outlaw-country revival  *(the center of taste)*
Anchors: Tyler Childers, Colter Wall, Sturgill Simpson, Turnpike Troubadours,
Charley Crockett, Zach Bryan, Charles Wesley Godwin.
- **Nearest:** red dirt / Texas country (Turnpike, Cody Jinks, Whiskey Myers),
  alt-country (Jason Isbell, American Aquarium, Drive-By Truckers).
- **One axis back (era):** outlaw originals — Waylon Jennings, Willie Nelson, Merle
  Haggard, Townes Van Zandt, Guy Clark, Billy Joe Shaver.
- **One axis (instrumentation/rootsier):** bluegrass & newgrass (Billy Strings, Tyler
  Childers' acoustic side, Sierra Ferrell, Molly Tuttle), country-blues / hill-country.
- **One axis (vocalist register shift):** women of the scene — Sierra Ferrell, Margo
  Price, Nikki Lane, Brandi Carlile, Kelsey Waldon.
- **Left-field bridge:** gothic/murder-ballad folk (16 Horsepower, Munly), Southern soul
  & swamp (Charley Crockett already bridges here).

### Indie folk / folk-rock  *(the library's 2010s backbone)*
Anchors: Fleet Foxes, Bon Iver, The Tallest Man on Earth, Iron & Wine, Gregory Alan
Isakov, Hozier.
- **Nearest:** chamber/orchestral folk (Sufjan Stevens, José González), folk-pop (The
  Lumineers, The Head and the Heart, Of Monsters and Men).
- **One axis (rootsier):** Americana singer-songwriter (Isbell, Tyler Childers — the
  bridge into the country cluster), freak/psych folk (Devendra Banhart).
- **One axis (era back):** '60s–70s folk & folk-rock — Nick Drake, John Prine, Townes
  Van Zandt, Neil Young, Simon & Garfunkel.
- **Left-field bridge:** slowcore / sad-core (Sun Kil Moon, Mount Eerie), ambient-folk.

### Singer-songwriter / lyric-forward  *(the throughline across both)*
Anchors: John Prine, Jason Isbell, Townes Van Zandt, Gregory Alan Isakov.
- **Nearest:** the two clusters above; literate alt-country.
- **One axis:** folk-blues storytellers, Texas songwriter tradition (Guy Clark, Steve
  Earle, Robert Earl Keen, James McMurtry).
- **Left-field:** Leonard Cohen / Bill Callahan (Smog) deep-lyric register.

---

## Bridges between the user's clusters (best left-field source)
These artists plausibly sit downstream of *two* clusters at once — angle 11 in
`discovery_heuristics.md`:
- **Indie folk × Americana:** Jason Isbell, Sierra Ferrell, Gregory Alan Isakov,
  S. Carey, Andrew Combs.
- **Outlaw country × Southern soul/R&B:** Charley Crockett, Sturgill Simpson
  (*Sound & Fury* era), Robert Finley, Nathaniel Rateliff.
- **Bluegrass × indie:** Billy Strings, Punch Brothers, Nickel Creek, Watchhouse
  (Mandolin Orange).

---

## Region notes (angle 9 — same sound, different geography)
- **UK/Ireland roots & folk:** Lankum, The Mary Wallopers, Ye Vagabonds, This Is The Kit.
- **Australian alt-country/folk:** Courtney Marie Andrews (US but tours the scene),
  The Waifs, Gordi (indie-folk).
- **Canadian:** The Band (foundational), Daniel Romano, Colter Wall (Saskatchewan — the
  user already loves this one), Kacy & Clayton.

---

## Tag → cluster cheat-sheet
When `artist_tags` returns these Last.fm tags, here's which cluster they point at:
| Last.fm tag | Points at |
|---|---|
| `outlaw country`, `red dirt`, `texas country` | Modern Americana revival |
| `americana`, `alt-country` | Americana ↔ singer-songwriter bridge |
| `bluegrass`, `newgrass`, `old-time` | Rootsier axis |
| `indie folk`, `folk-pop`, `chamber pop` | Indie folk cluster |
| `singer-songwriter` | Lyric-forward throughline (could be either cluster) |
| `folk rock`, `60s`, `70s` | Era-back axis |

> **Edit me.** As Last.fm surfaces artists that prove out (verified + liked), add them as
> anchors above so the map sharpens around the actual taste over time.
