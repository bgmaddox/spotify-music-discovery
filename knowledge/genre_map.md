# genre_map.md — static genre-adjacency reference

> **What this is.** A frozen lookup of "what sits next to what," **rebuilt from Brett's
> actual taste data** (top artists across all terms + Spotify genres + Last.fm tags, as of
> Jun 2026) rather than generic seeding. It is a **starting point for a direction**, not
> live data: use it to choose an *angle*, then confirm specific artists with Last.fm
> (`lastfm.py`) and specific tracks with `search_verify`. Expand/edit it as the taste grows.
>
> **How to read a row.** `cluster → neighbors`, neighbors ordered roughly nearest → farther.
> Listed artists are *examples to seed from or verify against*, not a ready playlist. An
> artist in **bold** is one already in Brett's taste (use as a seed, don't "discover" it).

> **Going outside these clusters?** This file is the *curated* core — Brett's real
> neighborhood, hand-tuned. For any genre **not** covered here, don't guess: query the full
> everynoise sonic map (6,291 genres) with
> `python cli.py genre-neighbors "<genre>" [--limit N]`. It returns everynoise's own
> ranked "nearby genres" list (scene-lineage adjacency, head = closest). Use `python
> genre_map.py find "<partial>"` to resolve an exact genre name first. **Do not** read
> `knowledge/genres_coords.json` wholesale — it's the machine index behind that tool.
> everynoise is a frozen 2023 snapshot, so treat its output as a *direction* and confirm
> artists with `lastfm.py` + tracks with `search_verify`, same as everything else here.

---

## Derived listening profile (factual, from the dumps)
- **Center of gravity:** modern Americana / outlaw-country / roots — the deepest, most
  consistent cluster (Tyler Childers, Isbell, Sturgill, Avett, Brandi Carlile…).
- **Genuinely multi-cluster:** strong, *separate* pockets of hip-hop, soul/funk/blues,
  vocal jazz & standards, musicals/Broadway, film & game scores, Afrobeats/alté, plus
  reggae, a cappella, electronic, and pop.
- **Seasonal but real:** Christmas/holiday is a top-artist cluster, not an accident — do
  **not** treat it as an avoid.
- **Functional, not taste (exclude from discovery seeds):** CoComelon, Ms. Rachel — kids'
  household listening. Never seed a ladder from these.

---

## Discovery-worthy clusters & their neighbors

### 1. Modern Americana / outlaw-country / roots  *(the spine)*
Anchors: **Tyler Childers, Jason Isbell, Sturgill Simpson, The Avett Brothers,
Brandi Carlile, Nathaniel Rateliff, Paul Cauthen, Lukas Nelson, Shovels & Rope, Shaboozey**.
- **Nearest:** red-dirt / Texas country (Turnpike Troubadours, Cody Jinks), alt-country
  (Drive-By Truckers, American Aquarium, John Moreland), new-traditionalists (Charley
  Crockett, Colter Wall, Vincent Neil Emerson).
- **One axis back (era):** outlaw originals — Waylon Jennings, Willie Nelson, Merle
  Haggard, Townes Van Zandt, Guy Clark, Billy Joe Shaver, John Prine.
- **One axis (women of the scene):** Sierra Ferrell, Margo Price, Sarah Jarosz, Amanda
  Shires, Courtney Marie Andrews, Katie Pruitt.
- **Left-field bridge:** Southern-gothic / murder-ballad folk (16 Horsepower, Ian Noe).

### 2. Bluegrass / newgrass / string-band
Anchors: **David Grisman, The Infamous Stringdusters, Watchhouse, Tyler Childers** (acoustic
side), **Sturgill** & **Avett** (newgrass overlap).
- **Nearest:** Billy Strings, Molly Tuttle, Punch Brothers, Nickel Creek, Sam Bush.
- **One axis (old-time / string-band):** Carolina Chocolate Drops, Old Crow Medicine Show.
- **Left-field:** jam-grass (Greensky Bluegrass) — connects to the **Easy Star/jam** pocket.

### 3. Indie folk / literate indie
Anchors: **The Decemberists, The Mountain Goats, Caamp, Guster, The Avett Brothers,
The Flaming Lips** (neo-psych edge).
- **Nearest:** Blind Pilot, The Head and the Heart, Blitzen Trapper, Dawes, The Milk
  Carton Kids.
- **One axis (chamber/baroque-pop):** Sufjan Stevens, Andrew Bird, Fleet Foxes.
- **One axis (era back):** Nick Drake, Neil Young, Simon & Garfunkel.

### 4. Hip-hop  *(Southern + West Coast + conscious)*
Anchors: **Outkast, Kendrick Lamar, Eminem, André 3000, Childish Gambino, Big Boi**.
- **Nearest (Southern/funk-soul lineage, per Outkast's funk/soul tags):** Goodie Mob,
  Anderson .Paak, Curtis Mayfield-sampling soul-rap.
- **One axis (jazz-rap):** Robert Glasper, Kamasi Washington (also links cluster 7),
  Digable Planets, A Tribe Called Quest.
- **Left-field bridge:** country-rap / genre-blend — **Shaboozey** (already loved) bridges
  straight into cluster 1.

### 5. Soul / funk / blues / retro-soul
Anchors: **Stevie Wonder, Taj Mahal, The California Honeydrops, Teddy Swims,
Nathaniel Rateliff** (bridges to roots).
- **Nearest:** St. Paul & The Broken Bones, Leon Bridges, Charles Bradley, Durand Jones.
- **One axis (blues):** modern blues (Gary Clark Jr.), country-blues originals.
- **Left-field bridge:** retro-soul ↔ Americana (Honeydrops, Rateliff already straddle it).

### 6. Vocal jazz, standards & crooners
Anchors: **Frank Sinatra, Bing Crosby, Dean Martin, Ella Fitzgerald, Michael Bublé,
The Andrews Sisters** (medium-term/seasonal pull).
- **Nearest:** Nat King Cole, Tony Bennett, Sarah Vaughan, Billie Holiday.
- **One axis (modern):** Gregory Porter, Jamie Cullum, Norah Jones.
- **Overlap:** big-band/swing and Christmas (cluster 11) share heavily here.

### 7. Instrumental / piano jazz
Anchors: **Keith Jarrett, Gregoire Maret** (jazz harmonica), **André 3000** (*New Blue
Sun* ambient-jazz flute).
- **Nearest:** Brad Mehldau, Bill Evans, Vince Guaraldi, Pat Metheny.
- **Bridge:** jazz ↔ hip-hop via Robert Glasper / Kamasi (links to cluster 4).

### 8. Musicals & Broadway
Anchors: **Lin-Manuel Miranda, Leslie Odom Jr., Idina Menzel, Jonathan Groff,
Kristen Bell, Auli'i Cravalho** (Hamilton / Frozen / Moana).
- **Nearest:** original-cast recordings — Hadestown, Dear Evan Hansen, Hadestown's Anaïs
  Mitchell (who is *also* a folk artist → bridge to cluster 3).
- **Bridge:** Hamilton already fuses musical theater × hip-hop (cluster 4).

### 9. Film & game scores / soundtracks
Anchors: **Hans Zimmer, Mark Mancina, Christophe Beck, Video Games Live** (Moana, Lion
King, Frozen, game OSTs).
- **Nearest:** Alan Silvestri, John Powell, Ramin Djawadi, Austin Wintory (game scores).
- **One axis (post-rock-adjacent score):** Ólafur Arnalds, Max Richter, Nils Frahm.

### 10. Afrobeats / alté  *(small but distinct)*
Anchor: **Juls**.
- **Nearest:** Wizkid, Burna Boy, Mr Eazi, Show Dem Camp, Odunsi (The Engine).
- ⚠️ **Tag caveat:** Last.fm mis-tags Juls as `rap/hip-hop/trap/UK`; Spotify's genres
  (`afrobeats/alté/afroswing`) are correct. For this cluster, trust Spotify genres over
  Last.fm tags and verify candidates carefully — a textbook "Last.fm is uneven" case.

---

## Smaller pockets (real, but thin — seed cautiously)
- **Pop:** **Taylor Swift, Chappell Roan** → folk-pop / synth-pop neighbors; Swift's
  `folklore`/`evermore` bridge toward indie folk (cluster 3).
- **Electronic / house:** **Daft Punk** → French house (Justice), filter-house, Stevie-soul
  sampling electronic (links to cluster 5).
- **Reggae / dub:** **Easy Star All-Stars** → roots reggae, dub, jam-band reggae.
- **A cappella:** **Pentatonix** → vocal arrangements; overlaps Christmas (cluster 11).

---

## Cross-cluster bridges  *(best source for left-field — angle 11)*
These plausibly sit downstream of *two* of Brett's clusters at once:
- **Roots × hip-hop/R&B:** Carolina Chocolate Drops (string-band cover of an R&B hit),
  **Shaboozey** (country-rap), Nathaniel Rateliff.
- **Roots × soul:** The California Honeydrops, St. Paul & The Broken Bones, Leon Bridges.
- **Hip-hop × jazz:** **André 3000** (already), Robert Glasper, Anderson .Paak, Kamasi
  Washington.
- **Standards × instrumental jazz:** Sinatra ↔ Keith Jarrett — same harmonic world, two
  registers.
- **Bluegrass × indie:** Punch Brothers, Nickel Creek, **Watchhouse**.
- **Musicals × folk:** Anaïs Mitchell (Hadestown ↔ indie folk), bridging clusters 8 and 3.

---

## Region notes (angle 9 — same sound, different geography)
- **UK/Ireland roots & folk:** Lankum, The Mary Wallopers, This Is The Kit.
- **Canadian roots:** The Band, Daniel Romano, Kacy & Clayton (**Colter Wall**'s scene).
- **West African (cluster 10):** Ghana/Nigeria alté & Afrobeats — Juls' home scene.

---

## Tag → cluster cheat-sheet
When `artist_tags` (or Spotify genres) return these, here's the cluster they point at:
| Tag / genre | Points at |
|---|---|
| `outlaw country`, `red dirt`, `texas country`, `alt country` | 1 Americana spine |
| `americana`, `roots rock`, `southern gothic` | 1 ↔ 5 (roots/soul border) |
| `bluegrass`, `newgrass`, `old-time`, `mandolin` | 2 String-band |
| `indie folk`, `baroque pop`, `folk rock`, `neo-psychedelic` | 3 Indie folk |
| `hip hop`, `rap`, `southern hip hop`, `west coast` | 4 Hip-hop |
| `soul`, `funk`, `motown`, `retro soul`, `blues` | 5 Soul/funk/blues |
| `vocal jazz`, `swing`, `big band`, `adult standards`, `oldies` | 6 Standards/crooners |
| `jazz`, `jazz ballads`, `ambient jazz` | 7 Instrumental jazz |
| `musicals`, `hamilton`, `original cast` | 8 Musicals |
| `soundtrack`, `score` | 9 Scores |
| `afrobeats`, `alté`, `afroswing`, `afropop` | 10 Afrobeats *(distrust Last.fm here — see §10)* |
| `christmas`, `holiday` | 11 Seasonal (loved — not an avoid) |

> **Edit me.** As Last.fm + `search_verify` surface artists that prove out (verified +
> liked), promote them to anchors in the relevant cluster so the map sharpens around the
> real taste over time.
