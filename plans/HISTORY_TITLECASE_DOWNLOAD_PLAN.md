# History-page polish v2 — Title Case, section scroll, downloadable visuals

Working doc for finishing three changes to `docs/history.html` (`/discovery/history`).
Written for AI-agent execution. **The file being edited is the tracked *template*
`docs/history.html`** (data-free, has `__TIMELINE_JSON__` placeholder). Never edit
`docs/history.local.html` — that's the gitignored injected copy the deploy produces.

## Deploy / verify flow (same for every phase)
1. Edit `docs/history.html` (template).
2. Rebuild the injected copy: `python cli.py timeline-inject`
   → writes `docs/history.local.html` (template + real `data/taste_timeline.json`).
3. Verify locally by opening `docs/history.local.html` (Playwright: desktop **1280×900**
   and mobile **390×844**; scroll to the bottom so lazy `reveal`/`hidden` sections
   initialize; assert **zero console errors**).
4. Deploy: `scp docs/history.local.html rachett:/var/www/discovery/history.html`
   (never scp the bare template — it renders the "no data injected" fallback).
5. Commit the template edit to `main` (`docs/history.html` only; `.local.html` is gitignored).

---

## Phase A — Title Case all section headings + nav chips  → **Model: Sonnet**
Mechanical but needs light judgment on minor words, so Sonnet (not Haiku). Use the exact
table below — do **not** improvise casing. Rule used: capitalize first/last word and all
major words; keep lowercase for articles (a/an/the), coordinating conjunctions
(and/or/nor/but), short prepositions (of/on/in/to), and `vs.`. Particles like "Up" and
pronouns like "It"/"You"/"Your" **are** capitalized.

**Only touch static heading text (`<h1>/<h2>/<h3>`) and the `.snchip` nav labels. Do NOT
title-case data-driven strings** — song titles, album names, artist names, era-chapter
titles rendered from `TIMELINE` JSON (e.g. `${esc(t.title)}`, `c.title`, `${name}`) keep
their source casing.

### Already applied in the interrupted session (verify, don't redo)
- `Taste Timeline` (h1 span) · `Genre River · The Streaming Years` · `Focused Year` ·
  `Artist Trajectory` · `Every Artist on Record` · `The Shape of Your Taste` ·
  `Artist Up Close` (netDetailTitle) · `Just Beyond the Edge` · `The Records` ·
  `Album Up Close` (recTitle) · `Album People or Singles People?` · `One-Track Wonders`

### Remaining headings to change (find → replace, each unique)
| Current | → New |
|---|---|
| `The songs` | `The Songs` |
| `Song lifelines` | `Song Lifelines` |
| `The day you met your favorite songs` | `The Day You Met Your Favorite Songs` |
| `Longest devotion` | `Longest Devotion` |
| `Track seasons` | `Track Seasons` |
| `How you listen` | `How You Listen` |
| `The listening clock` | `The Listening Clock` |
| `Autopilot vs. intent` | `Autopilot vs. Intent` |
| `Where it played` | `Where It Played` |
| `Seasons of sound` | `Seasons of Sound` |
| `Artist stories` | `Artist Stories` |
| `Loyalty spans` | `Loyalty Spans` |
| `Left &amp; came back` | `Left &amp; Came Back` |
| `Obsessions` | `Obsessions` (no change) |
| `The skip fingerprint` | `The Skip Fingerprint` |
| `The Claude era` | `The Claude Era` |
| `Keepsakes` | `Keepsakes` (no change) |
| `The receipt` | `The Receipt` |
| `Milestone club` | `Milestone Club` |
| `Yearbook anthems` | `Yearbook Anthems` |
| `Deep cut or hit?` | `Deep Cut or Hit?` |
| `Before streaming · the iTunes library, 2013–14` | `Before Streaming · The iTunes Library, 2013–14` |

### Nav chips (`.snchip`, ~line 511–519)
`Genre River` · `Every Artist` · `Shape of Taste` · `The Records` · `The Songs` ·
`How You Listen` · `Artist Stories` · `Keepsakes` · `iTunes Shelf`

**Watch-outs:** the scroll-spy assumes chip order == DOM order — change label text only,
never reorder chips or `data-target`. Grep for any leftover sentence-case heading after:
`grep -nE '<h[123]' docs/history.html` and eyeball the list.

---

## Phase B — Scroll-cap "Milestone Club" + "Deep Cut or Hit?"  → **Model: Sonnet**
Both sections render tall variable-length lists and blow up the section height. Reuse the
**existing shipped precedent** — the Song Lifelines grid (`.lifegrid`, ~line 325):
`max-height` + `overflow-y:auto` + thin themed scrollbar.

- **Milestone Club** list container: `#msList` (line 774).
- **Deep Cut or Hit?** list container: `#dcList` (line 792).

Add a scoped CSS rule for each (mirror `.lifegrid`'s scrollbar styling — `scrollbar-width:thin;
scrollbar-color:var(--green-dim) transparent` + the `::-webkit-scrollbar*` trio):
```css
#msList, #dcList { max-height: 420px; overflow-y:auto; padding-right:6px;
  scrollbar-width:thin; scrollbar-color:var(--green-dim) transparent; }
#msList::-webkit-scrollbar,#dcList::-webkit-scrollbar{width:8px}
#msList::-webkit-scrollbar-thumb,#dcList::-webkit-scrollbar-thumb{background:var(--green-dim);border-radius:4px}
#msList::-webkit-scrollbar-track,#dcList::-webkit-scrollbar-track{background:transparent}
```
Tune `max-height` (~400–450px) so ~6–8 rows show before scroll. Verify at 390px that the
list scrolls internally and doesn't reintroduce horizontal page overflow. The lifelines
"fade cue at bottom" is **optional** here — skip unless it's trivial; a plain scrollbar is
acceptable and lower-risk.

---

## Phase C — Per-visual "Save image" / download button  → **Model: Opus**
Higher design + cross-cutting risk (touches every section, mixed HTML+SVG), so Opus.

**Feasibility: yes, and not too hard — but do it uniformly.** All charts are inline **SVG
(23 uses, zero `<canvas>`)**, but several "visuals" are actually HTML/CSS (card grids,
receipt, dumbbells). Two viable routes:

- **Pragmatist — inline a tiny `dom-to-image`-style helper (recommended).** Bundle one
  small (~4 KB) HTML+SVG→PNG serializer *inline* in the page (keeps the "zero network deps,
  self-contained" invariant — do **not** add a CDN `<script>`). One `downloadVisual(nodeEl,
  filename)` handles both HTML cards and SVG charts identically. Add a small ⤓ button to each
  section/card header; on click, rasterize that card's root node to PNG and trigger download.
  - *Enables:* one code path, every visual shareable, consistent output.
- **Skeptic — native SVG serialization only.** `XMLSerializer` → `<img>` → `<canvas>` →
  `toBlob`. No library, but (a) only works for SVG, not the HTML-card visuals; (b) SVG fills/
  strokes here come from the page's external CSS classes and **won't carry** into a
  serialized standalone SVG unless every computed style is inlined first — that inlining is
  most of what a dom-to-image lib already does. Rolling it by hand is more code and more
  breakage than bundling the small helper.
- **Recommendation:** the inline dom-to-image helper. If bundle-size is a concern, scope
  buttons to the highest-share visuals first (Genre River, The Records crate, Song Lifelines,
  Milestone Club, Yearbook Anthems) rather than all ~25.

**Design notes for the agent**
- Reuse the existing `.copybtn` styling (see `#anthemCopy`, line 784) for the download
  button so it reads as one system; label it `⤓ Save` or icon-only with `aria-label`.
- Render PNG at 2× device scale for crisp sharing; set background to the page panel color
  (transparent PNGs look broken when pasted into chats).
- Lazy sections are `hidden` until scrolled — the button must rasterize the node *after* its
  render fn has run; wire buttons in each section's render fn, not at page load.
- Filename: `taste-<section>-<yyyymmdd>.png`.
- **Verify** the produced PNG actually contains the chart (not a blank/clipped node) for at
  least one SVG visual and one HTML-card visual, at both widths.

**If Phase C proves heavier than expected,** ship A + B first (they're independent and
low-risk), then do C as its own commit.

---

## Suggested execution order & orchestration
1. **A (Sonnet)** → inject → verify → commit. Fast, isolated.
2. **B (Sonnet)** → inject → verify → commit. Independent of A.
3. **C (Opus)** → inject → verify (PNG output check) → commit.
Each phase deploys via the flow at top. A and B can be one combined commit if done together;
keep C separate. Fable/Opus (this session) spec'd the plan and should review C's diff before deploy.
