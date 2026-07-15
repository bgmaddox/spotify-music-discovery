# Playlist Notes

Human-readable summaries of each Claude-built playlist — the *why* behind the picks:
the recipe used, how it maps to your taste, and how the tracks are sequenced. The
machine record of exactly which tracks went where lives in `data/discovery_log.jsonl`;
this file is the story version, meant to be read.

Newest first. Each entry: playlist name + link, the recipe/angle, the taste rationale,
the structure, and anything to tweak.

---

## 🤖 Rediscovery — the 2010 indie-pop bloom
**Link:** https://open.spotify.com/playlist/2UEAFzIRFcH2TCdfHGtwii
**Built:** 2026-07-15 · **Recipe:** 20 — Rediscovery (abandoned-lane revival) · **18 tracks**

**Why these:** First playlist seeded from the *historical* layer — your 2013 Windows iTunes
library (`data/itunes_history_2013.json`), a play-count-weighted record of late-2000s→2013
listening that Spotify's API can't reconstruct. The library showed a whole **abandoned lane**:
the 2010–2012 synth-and-festival indie-pop moment — Passion Pit ("Sleepyhead" was your #1 track,
127 plays), MGMT (378 plays), Foster the People, The Temper Trap, Edward Sharpe — none of which
survive in your current Americana-narrowed taste. The move: reopen that lane. A few genuine
drifted-favorite **anchors** for the nostalgia hook, extended with era-neighbors you never dug
into (Last.fm-seeded off the anchors, filtered against both current `known_artists` and the
discovery ledger, so every new artist is genuinely new).

**The anchors (yours, drifted):** Passion Pit — Sleepyhead · MGMT — Electric Feel ·
Foster the People — Helena Beat · The Temper Trap — Sweet Disposition.

**The new-to-you neighbors (14):** STRFKR — Julius · Two Door Cinema Club — What You Know ·
Miike Snow — Animal · Cut Copy — Lights & Music · Capital Cities — Safe and Sound ·
Matt & Kim — Daylight · Grouplove — Colours · Young the Giant — Cough Syrup ·
Walk the Moon — Anna Sun · Saint Motel — My Type · Atlas Genius — Trojans ·
The Naked and Famous — Young Blood · Ra Ra Riot — Boy · Electric Guest — This Head I Hold.

**Structure — nostalgia into discovery:** open on the strongest anchor (Sleepyhead) to hook the
memory, then alternate a known anchor with a cluster of new neighbors so the familiar keeps
vouching for the unfamiliar. Energy builds through the synth-pop middle (Capital Cities →
Grouplove → Cough Syrup → Anna Sun → My Type) and lands soft on The Temper Trap's soaring
"Sweet Disposition" — the anchor that feels most like an ending.

**Verify:** all 18 passed `search_verify`, 0 misses.

**Cover:** a winding path leading to a glowing outdoor festival stage under strings of warm
bulbs, neon-blue/violet dusk with a warm center-glow — the "discovery ladder" composition
(a path radiating out from a warm, remembered center), impasto oil, no text. Seed 20100.

**Possible tweaks:** a second historical playlist could reopen the *other* abandoned lane —
the mashup / party-DJ streak (Girl Talk 711 plays, Super Mash Bros., Pretty Lights, RJD2,
3LAU), though that lane is thin on Spotify (Girl Talk/Super Mash Bros. aren't fully available).
Or a blue-eyed-soul revival off the Amy Winehouse / Cee-Lo / Aloe Blacc thread.

---

## 🤖 Far cry — the anti-bubble
**Link:** https://open.spotify.com/playlist/4Mu3S92nGdiWGGIqP72Qpm
**Built:** 2026-07-15 · **Recipe:** 19 — Far cry (deliberate anti-bubble) · **11 tracks**

**Why these:** The anti-recipe. Instead of stepping one scene over (Recipes 6/7), this aims
for the parts of the map your taste dump *never* touches — non-Western scales, ritual/choral
traditions, languages you don't listen in. The discipline: "far" must stay *defensible*, so
every pick carries one real handhold into your Americana/roots/soul/hip-hop world. The ledger
already covered a lot of lateral ground (French touch, reggae, Latin, K-hip-hop, city-pop-
adjacent Bobby Caldwell), so these are chosen to be far from *both* the library and the ledger.

**The reach + handhold, per track:**
- **Mariya Takeuchi — Plastic Love** (Japanese city pop): the easiest door in — pure funk/disco/
  Stevie DNA, just in Japanese.
- **Mulatu Astatke — Yekermo Sew** (Ethio-jazz): you already own **The Budos Band**, literal
  Ethio-soul disciples; this is the source.
- **Innov Gnawa — Toura Toura** (Moroccan Gnawa trance): hypnotic bass-ostinato groove = jam/funk
  repetition.
- **Mdou Moctar — Afrique Victime** (Tuareg desert blues): it's the *blues* — hypnotic electric
  guitar (Gary Clark Jr., Kingfish, Taj Mahal).
- **The HU — Yuve Yuve Yu** (Mongolian folk-metal): throat singing + gallop, rock-backed — the
  energy peak.
- **Huun-Huur-Tu — Orphan's Lament** (Tuvan throat singing): acoustic string-drone + horse-gait
  rhythm = bluegrass drive (Grisman / "Tom Bombadil").
- **Ravi Shankar — Raga Jogeshwari: Alap** (Hindustani raga): long-form improvisational unspooling
  = jam-band exploration (Trey, Grisman).
- **Nusrat Fateh Ali Khan — Mustt Mustt** (Qawwali): ecstatic call-and-response vocal build =
  soul-revival fervor (Rateliff, St. Paul & The Broken Bones).
- **Wardruna — Helvegen** (Nordic ritual folk): folk at the root — drums, drone, nature, harmony.
- **Le Mystère des Voix Bulgares — Kalimankou Denkou** (Bulgarian choral): close vocal harmony
  (Secret Sisters, CSNY, Punch Brothers).
- **Mariza — Ó Gente da Minha Terra** (Portuguese fado): solo lament + guitar storytelling =
  Townes / outlaw ballad.

**Structure — an outward-and-back arc:** groove entry (city pop → Ethio-jazz → Gnawa) → energy
peak (desert blues → Mongolian gallop) → meditative deep middle (Tuvan drone → Hindustani raga)
→ ecstatic climb (Qawwali) → ritual/choral cool-down (Wardruna → Bulgarian choir) → intimate fado
lament to bring it home to *song*.

**Verify:** all 11 passed `search_verify`, 0 misses; cover-prone picks (Plastic Love, the Bulgarian
choir, Ravi Shankar) confirmed authentic via `verify_detail` — no karaoke/covers.

**Cover:** a warm campfire glow in the foreground dissolving into cold distant mountains and a
starlit horizon — the "home cluster left far behind, cool unknown ahead" made literal (impasto
oil, no text).

**Possible tweaks:** push even further out (Carnatic vocal, Tenores di Bitti Sardinian polyphony,
harsh noise, gamelan) at the cost of thinner handholds; or split into two shorter sets — a
"groove-forward far" and a "vocal/ritual far."

---

## 🤖 Neon Disco — house & lofi
**Link:** https://open.spotify.com/playlist/4inZqjEH4MPU7nK7iQBEB0
**Built:** 2026-07-14 · **Recipe:** house/nu-disco energy arc (Last.fm adjacency) · **23 tracks**

**Why these:** Pulled the electronic thread running quietly under a mostly
Americana/hip-hop library — Daft Punk, ODESZA, Chromeo, Breakbot, Alan Braxe,
Röisín Murphy — and used Last.fm adjacency to grow it into a full **French-touch /
nu-disco / house** set. Fulfills the ask: fun-beat house with lofi/downtempo breathers.
A few grounding anchors already known (Cassius, DJ Mehdi, Braxe + Falcon); the bulk is
genuinely new to the library.

**Structure — energy arc:** dancefloor front, sunset comedown back.
- *Fun-beat front half:* Chromeo → Breakbot → Tuxedo → Franc Moody → Miami Horror →
  Cut Copy → Holy Ghost! → Justice → SebastiAn → Cassius → Gaspard Augé → Braxe + Falcon
  → DJ Mehdi → The Paradise → Yuksek → Myd → Flight Facilities.
- *Lofi wind-down:* Poolside (×2) → Parra for Cuva → Lane 8 → Tourist → Tycho.

**Cover:** neon-dusk dancefloor easing to violet twilight (energy-arc composition), seed 704.

**Possible tweaks:** lean harder into four-on-the-floor house, stretch toward lofi
hip-hop beats, or add a peak-time French-touch banger block.

---

> **Backlog note:** the entries below were reconstructed on 2026-07-14 from the machine
> ledger (`data/discovery_log.jsonl`) and the live playlist descriptions on Spotify.
> They predate the notes journal, so the "why" is inferred rather than captured live —
> accurate on tracks and angle, lighter on the in-the-moment reasoning.

---

## 🤖 Miles' children — a jazz family tree
**Link:** https://open.spotify.com/playlist/0Ebv1IHPv67sB52LbllFVc
**Built:** 2026-06-29 · **Recipe:** sideman/lineage trail · **12 tracks**

**Why these:** A jazz playlist built as a genealogy rather than a mood — start at Miles
Davis and branch out by *who played in his bands*, feeding your Keith Jarrett / modal-jazz
leaning. Every pick is one hop from Miles.

**Structure — lineage tree:** the Miles alumni first (Coltrane, Cannonball, Bill Evans,
Wayne Shorter, Herbie Hancock, Tony Williams), then the fusion empires those sidemen went
on to build — Weather Report, Return to Forever, Mahavishnu Orchestra — closing on the
solo-piano vastness of Jarrett's *Köln Concert*. One sideman, one new world.

## 🤖 Wheels Up: 11 Hours to Greece
**Link:** https://open.spotify.com/playlist/4Zjo3ig17ngBz8qIjrZSpc
**Built:** 2026-06-27 · **Recipe:** occasion / energy arc · **49 tracks** (19 new artists logged)

**Why these:** Purpose-built for a specific occasion — an 11-hour flight to Greece — so
the sequencing *is* the point. Anchored in your soul/roots/Americana core, then drifting
geographically toward the destination.

**Structure — a full travel arc:** soul/roots takeoff (St. Paul & The Broken Bones,
Vulfpeck) → Americana cruising → indie-folk daydream → a hip-hop stretch (Anderson .Paak,
Phonte) → funk-soul groove (Curtis Mayfield, Charles Bradley) → sunshine reggae (Desmond
Dekker) → a Mediterranean/Greek approach (Vangelis, Theodorakis, Manu Chao, Gipsy Kings)
→ quiet jazz & folk (Iron & Wine, Novo Amor) for the descent. Yiamas.

## 🤖 Samples & Sources: Hip-Hop DNA
**Link:** https://open.spotify.com/playlist/1FOMDGuAHWPGHOomAur4gP
**Built:** 2026-06-24 · **Recipe:** sample lineage (source→song pairs) · **16 tracks**

**Why these:** Feeds the hip-hop half of your taste by revealing where it came from —
eight classics paired with the record each one sampled, **source first**. An ear-training
exercise disguised as a playlist.

**Structure — paired A→B (source then song):** Lou Reed→Tribe, Mtume→Biggie, Chaka
Khan→Kanye, Daft Punk→Kanye ("Stronger"), Ahmad Jamal→Nas, Isley Brothers→Kendrick,
Bobby Caldwell→Common, Joe Cocker→2Pac. Play it in order and you hear the seam each time.

## 🤖 Outlaw Country: A History
**Link:** https://open.spotify.com/playlist/1ZDa4xRhLvte7IMJJrCpxV
**Built:** 2026-06-24 · **Recipe:** genre chronology · **19 tracks**

**Why these:** Dead center of your taste (Childers, Sturgill, Cody Jinks, Colter Wall) —
so instead of just picking favorites, this traces the whole lineage of outlaw country as
a timeline, so the deep roots explain the modern artists you already love.

**Structure — chronological:** Bakersfield roots (Buck Owens, Haggard) → the '70s founders
(Waylon, Willie, Kristofferson, Billy Joe Shaver) → the Highwaymen-era peak → '80s–90s
torchbearers (Steve Earle, Dwight Yoakam) → the modern revival (Stapleton, Sturgill,
Colter Wall, Childers). A straight line from Bakersfield to today.

## 🤖 Deep cuts — the songs you skipped to
**Link:** https://open.spotify.com/playlist/0JkCnWdBNRUYxf59NEMEPQ
**Built:** ~2026-06-23 · **Recipe:** deep cuts (anti-hits) · **21 tracks**

**Why these:** No new artists at all — the twist is *depth*. Buried album tracks from
artists already dead-center in your library, deliberately avoiding the singles. The songs
you'd hit "next" to get to.

**Structure — by artist cluster:** Childers, Isbell, Sturgill, the Avetts, Stevie Wonder's
*Songs in the Key of Life* (three cuts), Outkast's *Aquemini*, Brandi Carlile, and Rateliff.
Album deep-enders, live takes, and the tracks between the hits.

## 🤖 Alt rock around the world
**Link:** https://open.spotify.com/playlist/3RoWXoQDURWt3PhnbkBKhr
**Built:** 2026-06-23 · **Recipe:** genre ladder, global (region shift) · **15 tracks**

**Why these:** A deliberate stretch — alternative rock from 15 different countries, one
defining act each, **none already in your library**. Pure discovery, using the genre you
know as the passport.

**Structure — one country per track:** Fontaines D.C. (IE), The Hives (SE), Måneskin (IT),
Tame Impala (AU), Metric (CA), Phoenix (FR), Asian Kung-Fu Generation (JP), Hyukoh (KR),
Café Tacvba (MX), Soda Stereo (AR), Os Mutantes (BR), Vetusta Morla (ES), Sigur Rós (IS),
Mogwai (UK). A passport through the global scene.

## 🤖 Worldwide Bars — global hip-hop
**Link:** https://open.spotify.com/playlist/6uJ4Q8b6jjYjH3uYCemJ6d
**Built:** 2026-06-23 · **Recipe:** genre ladder, global (region shift) · **16 tracks**

**Why these:** The hip-hop companion to *Alt rock around the world* — rap from 14 countries,
extending your Kendrick/Outkast/Tribe axis outward across languages and scenes.

**Structure — one country per track:** Little Simz & Loyle Carner (UK), Sampa the Great (AU),
Stogie T (ZA), DIVINE (IN), Awich (JP), Epik High (KR), Oxxxymiron (RU), MC Solaar (FR),
Ghali (IT), C. Tangana (ES), Ana Tijoux (CL), Criolo (BR), Orishas (CU), Daara J Family (SN).
One verse, one passport stamp at a time.

## 🤖 Reggae Roots: Covers & Originals
**Link:** https://open.spotify.com/playlist/0z18B89muuuHVRniFtpEWc
**Built:** 2026-06-21 · **Recipe:** cross-version pairs (bridge) · **22 tracks**

**Why these:** An on-ramp into roots reggae *through songs you already know* — each reggae
cut is set next to its "other life" as a pop/rock hit, so the familiar version pulls you
into the original.

**Structure — paired versions:** Marley vs Clapton ("I Shot the Sheriff"), the Paragons vs
Blondie ("The Tide Is High"), Toots vs the Clash ("Pressure Drop"), the Melodians vs Boney M.
("Rivers of Babylon"), plus "Red Red Wine" (Diamond/UB40) and more. Reggae is the thread
between every pair.

## 🤖 Lukas Nelson → The Killers → Taj Mahal
**Link:** https://open.spotify.com/playlist/6BHSYpbI6C9NvzxG3ejFuW
**Built:** ~2026-06-19 · **Recipe:** Morph (A→B→C) · **20 tracks**

**Why these:** A three-stop Morph across worlds you'd never think to connect — Americana
roots, anthemic indie rock, and delta blues — with each track a stepping stone so the
seams don't show.

**Structure — A→B→C journey:** Lukas Nelson's Americana (Marcus King, Tedeschi Trucks,
Gov't Mule, Blackberry Smoke) → a Tom Petty / Arcade Fire / War on Drugs hinge into
anthemic indie rock (Kings of Leon, The Killers, The National) → guitar-forward crossover
(Black Keys, Jack White, Gary Clark Jr.) → classic blues (Robert Cray, Bonnie Raitt,
Keb' Mo', Buddy Guy) landing on Taj Mahal. You never feel the jump.

## 🤖 Sparkle Pop Party
**Link:** https://open.spotify.com/playlist/5PQgQHV3kwk3U9LGfwsgJ4
**Built:** ~2026-06-16 · **Recipe:** occasion (for a specific listener) · **20 tracks**

**Why these:** Off-taste on purpose — built for a young *KPop Demon Hunters* fan, not your
own profile. Bright, bouncy, sing-along, and all clean.

**Structure — bubbly K-pop meets clean pop hooks:** NewJeans, TWICE, aespa, ITZY, LE
SSERAFIM, Red Velvet on the K-pop side; Chappell Roan, Katy Perry, Dua Lipa, Taylor Swift,
Sabrina Carpenter, Carly Rae Jepsen on the big-hook pop side. All upbeat, all family-safe.

## 🤖 Dinnertime Bossa — warm & easy
**Link:** https://open.spotify.com/playlist/4VXADXu7rzPG56fzanpXbU
**Built:** ~2026-06-16 · **Recipe:** occasion / mood set · **20 tracks**

**Why these:** A single-mood set for family dinners on shuffle — warm, mostly-instrumental
bossa nova and cool jazz that sits in the background without demanding attention.

**Structure — one immersive mood:** Jobim, Stan Getz & João Gilberto, Wes Montgomery, Bill
Evans, Cal Tjader, Baden Powell, João Donato, George Benson. No sequencing arc by design —
it's built to shuffle.

## 🤖 Songs you forgot you loved
**Link:** https://open.spotify.com/playlist/3VZmLrJfH8FVzct6aX8kq8
**Built:** ~2026-06-16 · **Recipe:** time machine (long-term vs. recent) · **16 tracks**

**Why these:** Mines the gap between your *long-term* favorites and your *recent* rotation —
artists that rank high all-time but have gone quiet lately. All familiar, none new; the
pleasure is rediscovery.

**Structure — cross-genre reunion:** Chappell Roan, The Shins, Future Islands, M83, Bear's
Den, Lake Street Dive, Paul Cauthen, the Stringdusters, The Mountain Goats, Greta Van Fleet.
Stuff you forgot you loved.

## 🤖 Jazz, your way
**Link:** https://open.spotify.com/playlist/0z4qdLplaGAalBa0YF85jx
**Built:** 2026-06-15 · **Recipe:** occasion / genre in the user's style · **15 tracks**

**Why these:** A personal jazz set anchored on your specific leanings — Keith Jarrett,
Christmas-jazz, Bing Crosby — rather than a generic "jazz 101." Warm and vocal-forward,
with a bridge back to your hip-hop side.

**Structure — mood clusters:** warm piano (Evans, Brubeck, Monk) → vocal standards (Chet
Baker, Nat Cole, Ella, Nina) → bossa & soul-jazz (Getz, Cannonball) → a jazz-rap bridge
(A Tribe Called Quest, Robert Glasper) linking to your Outkast/Kendrick side.

## 🤖 Daft Punk → Outkast (a bridge)
**Link:** https://open.spotify.com/playlist/5Eg84FoPynQDLzx7Gib1u9
**Built:** 2026-06-15 · **Recipe:** Bridge (A↔B) · **11 tracks**

**Why these:** A guided segue between two things you love — French house and Atlanta
hip-hop — with funk as the connective tissue. The classic Bridge recipe: start at A,
end at B, make every step feel inevitable.

**Structure — A→B segue:** French house (Stardust, Breakbot, Chromeo) → disco DNA
(Jamiroquai, Chic's "Good Times" — the bassline that birthed hip-hop) → funk-rock
crossover (N.E.R.D, Gnarls Barkley) → Atlanta hip-hop (The Roots, Big Boi). Funk is the
throughline the whole way across.

## 🤖 Roots & Hollers — library dig
**Link:** https://open.spotify.com/playlist/7Cm8sdHTDtobUBYrnFhbjW
**Built:** 2026-06-14 · **Recipe:** library archaeologist · **25 tracks**

**Why these:** Not discovery — excavation. A dig through your *own saved tracks* to pull the
Americana / roots-revival thread into one place. Everything here is already in your library;
the value is the curation.

**Structure — the roots thread:** the TurtleDuhks, the Avetts (four from *Emotionalism*),
Childers live cuts, Sturgill's *A Sailor's Guide*, Rateliff, Lake Street Dive, the Wood
Brothers, Watchhouse, the Steeldrivers. A cross-section of your roots collection.

## 🤖 Discovery Ladder — 2026-06-14
**Link:** https://open.spotify.com/playlist/2XvfNUHbB9Ty3djjGIIqi8
**Built:** 2026-06-14 · **Recipe:** Discovery ladder (the core recipe) · **9 tracks**

**Why these:** The canonical recipe — start at the center of your taste and walk outward in
rungs, each pick one measured step further out than the last.

**Structure — center → stretch → left-field:** center (Common, Punch Brothers, Colter Wall)
→ one-axis stretches (Chris Thile & Brad Mehldau, Khruangbin, Shakey Graves) → left-field
reaches still defensible from what you love (Robert Glasper, BADBADNOTGOOD, and Fela Kuti as
the far edge).

## 🤖 Lateral roots — Last.fm ladder (Jun 2026)
**Link:** https://open.spotify.com/playlist/64y4IEXrNF8ku0Y5UbtwIx
**Built:** 2026-06-14 · **Recipe:** Last.fm-seeded lateral ladder (Recipe 6) · **10 tracks**

**Why these:** Uses Last.fm crowd-similarity to restore the "related artists" signal Spotify
killed. Seeded from Isbell / Avett / Sturgill / Carlile, filtered to **10 artists new to your
taste**, then walked center → left-field.

**Structure — center → left-field:** Amanda Shires, Justin Townes Earle, Sarah Jarosz, the
Milk Carton Kids (near-in) → Ray LaMontagne, John Moreland, Courtney Marie Andrews → the
Carolina Chocolate Drops and Blitzen Trapper at the edge.

## 🤖 Lateral hip-hop — Last.fm ladder (Jun 2026)
**Link:** https://open.spotify.com/playlist/75pWaypKhFCUPo6zh0Ko6l
**Built:** 2026-06-14 · **Recipe:** Last.fm-seeded lateral ladder (Recipe 6) · **10 tracks**

**Why these:** The hip-hop twin of the roots ladder — seeded from Outkast / Kendrick /
Eminem / Gambino, steered toward your lyric-forward + soul + live-energy lean, with the
left-field rung bridging into your soul & jazz clusters.

**Structure — center → bridge-out:** The Roots (w/ Badu & Eve), Common, Black Star
(lyric-forward core) → Freddie Gibbs, JID, Denzel Curry, Vince Staples → Anderson .Paak,
Smino, and Glasper's "Afro Blue" bridging into jazz.

## 🤖 Blacktop rabbit hole
**Link:** https://open.spotify.com/playlist/66n6yXVSKD1uVxFavWWkxo
**Built:** 2026-06-14 · **Recipe:** single-song rabbit hole (lineage + contemporaries) · **5 tracks**

**Why these:** A tight dig off one song — Colter Wall's "Sleeping on the Blacktop" — tracing
both its Western/outlaw lineage and its modern peers. Small and focused by design.

**Structure — lineage + contemporaries:** the forebears (Townes Van Zandt, Marty Robbins,
Blaze Foley) alongside present-day kin (Charley Crockett, Ian Noe).
