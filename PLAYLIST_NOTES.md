# Playlist Notes

Human-readable summaries of each Claude-built playlist — the *why* behind the picks:
the recipe used, how it maps to your taste, and how the tracks are sequenced. The
machine record of exactly which tracks went where lives in `data/discovery_log.jsonl`;
this file is the story version, meant to be read.

Newest first. Each entry: playlist name + link, the recipe/angle, the taste rationale,
the structure, and anything to tweak.

---

## 🤖 Alive — a jam band set list
**Link:** https://open.spotify.com/playlist/67FgyblAzZlAjhf3tJGYwr
**Built:** 2026-07-27 · **Recipe:** 22 — Alive (definitive live cuts), jam-band variant · **16 tracks**

**Why these:** Recipe 22 swaps the *recording*, not the song — zero-risk discovery aimed at
the live/raw-energy preference in `discovery_heuristics.md`. This run narrows the seed pool
to the jam-adjacent bands already in the library (Wood Brothers, Billy Strings, Tedeschi
Trucks, Gov't Mule, Rateliff, Stringdusters, JJ Grey, Trey Anastasio, Khruangbin, The Band)
and takes each artist's live release instead of the studio cut. The Wood Brothers earn three
slots because they're the deepest well in the history — "I Got Loaded" is the #1 all-time
non-household track at 135 plays, and *Live at the Barn* has both it and "Postcards from Hell."

**The set, in order:**
1. Gov't Mule — Mule (*Live at the Roseland Ballroom*) — riff opener
2. Billy Strings — Dust in a Baggie (*Live Vol. 1*, Wilkes-Barre 12/15/23)
3. The Infamous Stringdusters — Fork In The Road (*We'll Do It Live*)
4. The Wood Brothers — I Got Loaded (*Live at the Barn*)
5. The Wood Brothers — Postcards from Hell (*Live at the Barn*)
6. Nathaniel Rateliff & The Night Sweats — Howling At Nothing (*Live at Red Rocks*)
7. JJ Grey & Mofro — Brighter Days (*Brighter Days (Live)*) — swampy breath
8. Tedeschi Trucks Band — Midnight In Harlem (*Everybody's Talkin'*) — first peak
9. Khruangbin — People Everywhere (*Live at Stubb's*) — groove reset
10. The Wood Brothers — Luckiest Man (*Live, Volume 1: Sky High*) — quiet center
11. Billy Strings — Away From The Mire (*Live Vol. 1*, Austin 6/2/23) — the long build
12. Trey Anastasio — First Tube (*TAB at the Fox Theater*) — instrumental peak
13. Tedeschi Trucks Band — Space Captain (*Mad Dogs & Englishmen Revisited, LOCKN' 2015*)
14. Gov't Mule — Soulshine (Angel Orensanz Center, NYC 12/28/2008) — lighters up
15. Nathaniel Rateliff & The Night Sweats — S.O.B. (*Live at Red Rocks*, w/ Preservation Hall Jazz Band) — encore
16. The Band — The Weight (*Rock of Ages*, Academy of Music 1971) — house lights

**Seams:** shaped as one continuous show rather than a mood arc — barn-burner opening run,
a soul/blues middle that breathes, an instrumental peak at First Tube into the communal
Space Captain, then two encores and a closer. The Khruangbin cut is the one stylistic
outlier (Thai-funk groove among roots bands) but it lands where a set needs a palate
cleanser.

**Misses:** Taj Mahal, Marcus King, Lake Street Dive and Sturgill Simpson were all seeded
and dropped — each returned a studio album on verification (Sturgill's *Cuttin' Grass* is a
bluegrass re-record, not a live take). Recipe 22's acceptance bar treats a wrong album as a
miss, so they're out rather than faked.

**Tweak ideas:** a Grateful Dead / Phish anchor would make this read more canonically
"jam band," but neither is in the library — that'd be a Recipe 19 (far cry) job instead.
If the Wood Brothers triple is too heavy, "Luckiest Man" is the droppable one.

**Ledger note:** logged 0 new artists, correctly — Recipe 22 surfaces new *recordings* of
known artists. Two Gov't Mule records slipped past `--new-only` and were purged; cause was a
gap in `known_listened_artists()` (it never walked `top_tracks`), fixed in the same commit.

**Cover:** a night festival stage bathed in amber stage-wash, empty microphone stands and a
drum kit in a haze of lit dust, warm glow swelling outward into humid dark — Recipe 22 has no
entry in the composition table, so it borrows "occasion / mood set" (a single immersive scene
of the occasion). Warm amber/burnt orange against deep indigo dusk, impasto oil, no text,
**seed 2707**.

---

## 🤖 Title Chain — Match Day
**Link:** https://open.spotify.com/playlist/6qJfPTnXFEbJn2def7nLyU
**Built:** 2026-07-19 · **Recipe:** 25 — Title chain (the wordplay game), soccer variant · **14 tracks**

**Why these:** Recipe 25 as written chains titles word-to-word; this run bends the rule
to a themed vocabulary chain instead — every title contains a word that's also a piece of
soccer vocabulary, and the *sequence* of those words narrates one full match from kickoff
to final whistle. Musical picks lean on your Americana/soul/classic-rock lanes so it still
sounds like your playlist and not a novelty reel.

**The chain, in order (linking soccer word in caps):**
1. **KICK** — The Avett Brothers, Kick Drum Heart (kickoff)
2. **PASS** — Iron & Wine, Passing Afternoon
3. **RUN** — Bruce Springsteen, Born to Run
4. **CROSS** — Robert Johnson, Cross Road Blues
5. **SHOT** — Original Broadway Cast of Hamilton, My Shot
6. **SAVE** — Jelly Roll, Save Me (the keeper comes up big)
7. **CORNER** — Common, The Corner
8. **HEADER** — The Fray, Over My Head (Cable Car)
9. **FREE (KICK)** — Zac Brown Band, Free
10. **WALL** — Pink Floyd, Another Brick in the Wall, Pt. 2 (the defensive wall)
11. **BALL** (in the net) — Jerry Lee Lewis, Great Balls of Fire — goal!
12. **CELEBRATION** — Kool & The Gang, Celebration
13. **FULL TIME** — Semisonic, Closing Time
14. **CHAMPIONS** — Queen, We Are the Champions

**Seams:** order is the whole point here (match narrative, not mood arc) — energy still
rides a natural curve: mid-tempo build through the match action, a horn-driven peak at the
goal/celebration pair, then a wind-down through "Closing Time" into the anthemic closer.
Cast mostly outside your usual clusters (classic rock, soul, a Broadway cut) since the
concept needed recognizable soccer-adjacent anthems more than deep cuts — flagged in the
description as chain order, not a taste-matched set.

**Tweak ideas:** could tighten to a strict 90-minutes-elapsed structure (first half /
halftime / second half / stoppage time) if a longer, more literal match arc is wanted later.

---

## 🤖 Back in Action — a recovery story
**Link:** https://open.spotify.com/playlist/3aHHEs8tQB3V46PyTzFAEM
**Built:** 2026-07-16 · **Recipe:** 26 — The concept album (narrative sequence) · **10 tracks**

**Why these:** A get-well gift for your brother after spinal surgery — the first Recipe 26
run, and the first playlist cast for someone *else*: broad crowd-pleasers instead of your
clusters, per your call, with a mixed tone (sincere spine, pun chapters placed where they
lift). The story is the surgery itself, diagnosis → comeback, and order is load-bearing.

**The chapters, in order:**
1. **The diagnosis — Robert Palmer, Bad Case of Loving You (Doctor, Doctor)**: the comic
   opener — "doctor, doctor, gimme the news."
2. **The incision — Cat Stevens, The First Cut Is the Deepest**: the gag only a surgery
   playlist gets to make.
3. **Going under — Pink Floyd, Comfortably Numb**: anesthesia, half wink half sincere —
   "just a little pinprick."
4. **Waking up — The Beatles, Here Comes the Sun**: relief; it's over.
5. **Flat on his back — The Band, The Weight**: "take a load off" — doctor's orders.
6. **Leaning on people — Bill Withers, Lean on Me**: the sincere heart of the album.
7. **First steps — Katrina & The Waves, Walking on Sunshine**: pun + pure joy.
8. **Rehab montage — Kanye West, Stronger**: "that that don't kill me…"
9. **Standing tall — Elton John, I'm Still Standing**: the pun payoff.
10. **Back in action — AC/DC, Back in Black**: the triumphant closer.

**Seams:** the two comic openers ride the same bar-band rock energy before Floyd slows it
down; the middle sag (Beatles → Band → Withers) is the gentle convalescent stretch; then
energy climbs monotonically from Katrina & The Waves through AC/DC — a recovery-shaped arc.

**Verify:** 10/10 passed `search_verify`, 0 misses — every one resolved to the canonical
album version (Abbey Road, The Wall, Big Pink, Still Bill, Graduation…).

**Cover:** a winding road climbing out of a dark indigo valley into golden sunrise —
left-to-right narrative-journey composition, impasto oil, no text. Seed 2607.

**Possible tweaks:** it's private under your account — share the link, or make it public
in the app (client-only toggle) so he can follow it. Easy swaps if a chapter doesn't land:
"Fix You" (Coldplay) for chapter 6, "Ain't No Mountain High Enough" as an alternate closer.

---

## 🤖 Back in rotation — forgotten favorites
**Link:** https://open.spotify.com/playlist/6WpUgwby2tB6NUfVzOcv0S
**Built:** 2026-07-16 · **Recipe:** 29 — Forgotten-favorites revival (deep history) · **13 tracks**

**Why these:** First playlist seeded from the GDPR extended streaming history (2015→2026,
~44k real plays) rather than the API's shallow windows. The new `history-snapshot` surfaced
**forgotten favorites** — artists with ≥40 lifetime plays but zero plays in 2025–26 — with
real peak years and real per-track counts. Every track here is *your own* most-played song
by that artist, from the year you wore it out. Filtered out: Bruce Brus (white noise) and
Christophe Beck (Frozen score) — household plays, not taste.

**The revivals, per track** (lifetime plays · peak year):
- **The Teskey Brothers — Crying Shame** (26 · 2022): the Aussie soul lane, opener.
- **Sister Sparrow — Mama Knows** (41 · 2021): brass-funk stomp.
- **Amy Winehouse — Back To Black** (17 · 2021): 162 lifetime plays across the catalog.
- **Earl St. Clair — Is It Real** (9 · 2021): one-era soul-rock voice, gone since 2021.
- **Nico Segal — Pass the Vibes** (19 · 2019): the Donnie Trumpet sunshine cut.
- **Big Grams — Fell In the Sun** (25 · 2021): Big Boi × Phantogram, the hip-hop pivot.
- **Action Bronson — Baby Blue** (51 · 2019): your single most-played forgotten track.
- **UGK — Int'l Players Anthem** (60 · 2022): the Outkast tie-in classic.
- **OK Go — Get Over It** (41 · 2019): power-pop jolt.
- **Robyn — Dancing On My Own** (40 · 2022): the dance-floor cry, energy peak.
- **Bruce Springsteen — I'm On Fire** (13 · 2021): the comedown turn.
- **Gillian Welch — Everything Is Free** (4 · 2020): quiet roots landing.
- **Old Crow Medicine Show — Wagon Wheel** (15 · 2024): the singalong send-off.

**Structure:** soul block up front (Teskey → Sparrow → Winehouse → St. Clair), the trumpet
bridge into a hip-hop stretch (Segal → Big Grams → Bronson → UGK), a pop peak (OK Go →
Robyn), then the Springsteen comedown into a roots landing (Welch → Wagon Wheel).

**Verify:** 13/13 passed `search_verify`, 0 misses (Winehouse and Welch resolved to newer
canonical URIs than the historical play events — verified ones used).

**Cover:** a dusty crate of vinyl in a dim attic, one sunbeam waking the records in gold —
warm amber/gold against deep indigo shadow, impasto oil, no text. Seed 2207.

**Possible tweaks:** re-runnable — the forgotten list recomputes as taste drifts, and the
ledger keeps editions from repeating. The deeper catalogs flagged here (Teskey Brothers,
Big Grams, Earl St. Clair's lone album) are natural follow-up dives. Threshold knobs live
in `streaming_history.py` (`FORGOTTEN_MIN_PLAYS`, `FORGOTTEN_QUIET_YEARS`).

---

## 🤖 New lanes — Jul 2026
**Link:** https://open.spotify.com/playlist/4MxBBqBRZ3OHomNAOr1Te9
**Built:** 2026-07-16 · **Recipe:** 21 — New-release radar · **11 tracks**

**Why these:** First run of the recipe pinned to *now* — a personal Release Radar reasoned
from your lanes instead of a black box. A 26-artist watchlist (16 owned cores + 10 Last.fm-
adjacent laterals) was swept against Spotify's artist-album feeds; 12 had dropped something
inside the 6-month window (since ~Jan 16). One strongest cut per artist, release dates
verified from the API, not from memory — post-cutoff releases are exactly what a session
can't know. Notably quiet: Childers, Isbell, Sturgill, Avetts, Rateliff, Zach Bryan.

**The fresh drops, per track:**
- **Billy Strings — Burn the Other End** (single, Jun 30): adjacent bluegrass flagship, opener.
- **Sierra Hull — Feelin' Good Again** (single, Jun 26): the mandolinist from your recent plays.
- **Molly Tuttle — My Side of the Mountain** (single, Apr 23): adjacent flatpicking star.
- **Charley Crockett — The Hallelujah Trail** (from *Clovis*, Jul 3 — his *second* album of 2026
  after April's *Age of the Ram*).
- **Marcus King — Honky Tonk Hell** (from the double LP *Darling Blue / No Room For Blue*, May 1).
- **The Red Clay Strays — Demons In Your Choir** (lead single + opener of *Grateful*, Jun 5).
- **Shakey Graves — Time Flies** (from *Fondness, Etc.*, May 15).
- **Margo Price — Deportee (Plane Wreck At Los Gatos)** (from *Days Of Unrest*, Jul 3): the Woody
  Guthrie song, feat. Joan Baez & Memphis Mariachi.
- **Waxahatchee — Six O'Clock News** (single, Mar 24): adjacent Americana-indie lane.
- **Brandi Carlile — Life On The Run** (single, May 22).
- **Gregory Alan Isakov — Fade Into You** (single, Apr 16): the Mazzy Star song, dreamy closer.

**Structure:** bluegrass barn-burners up front (Strings → Hull → Tuttle), through the honky-tonk
/ southern-soul middle (Crockett → King → Red Clay Strays), then the songwriter back half
(Shakey → Margo → Waxahatchee → Brandi) landing on Isakov's hushed "Fade Into You."

**Verify:** all 11 passed `search_verify`, 0 misses; every release date pulled from the API
inside the Jan–Jul 2026 window.

**Cover:** green shoots along a country fence line at first light, sun rays sweeping the sky
like a radar beam — warm amber/gold with fresh spring green, impasto oil, no text. Seed 2126.

**Possible tweaks:** dated name makes this a series — re-run monthly and the ledger keeps
each edition from repeating picks. Deep-dive candidates for future sessions: the two 2026
Crockett albums, the Marcus King double LP, and Red Clay Strays' *Grateful* in full.

---

## 🤖 Rediscovery — the 2010 indie-pop bloom
**Link:** https://open.spotify.com/playlist/2UEAFzIRFcH2TCdfHGtwii
**Built:** 2026-07-15 · **Recipe:** 20 — Rediscovery (abandoned-lane revival) · **18 tracks**

**Why these:** First playlist seeded from the *historical* layer — an old Windows iTunes
library (`data/itunes_history.json`, merged from 2013 + 2014 snapshots), a play-count-weighted
record of late-2000s→2014 listening that Spotify's API can't reconstruct. The library showed a whole **abandoned lane**:
the 2010–2012 synth-and-festival indie-pop moment — Passion Pit ("Sleepyhead" was your #1 track,
127 plays), MGMT (384 plays), Foster the People, The Temper Trap, Edward Sharpe — none of which
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
