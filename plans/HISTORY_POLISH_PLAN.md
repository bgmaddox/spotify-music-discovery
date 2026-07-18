# History page polish plan — layout, flow & copy

Audit + fix pass on `/discovery/history` after all feature sections landed
(genre river → iTunes shelf, plus How-you-listen, Artist-stories, similarity
network, records, songs, fun lists). Goal: make labels/titles/blurbs and the
overall flow as good as the pieces now inside them. Audited live 2026-07-18
(desktop 1280px + mobile 390px, all sections lazy-revealed, console clean).

## Ground rules for the executing agent
- **Edit the template, not the injected copy.** All markup/CSS/JS copy edits go in
  `docs/history.html` (tracked, data-free template). NEVER hand-edit
  `docs/history.local.html` — it is gitignored and regenerated.
- **Rebuild + deploy after each shipped phase:**
  `python cli.py timeline-inject` → produces `docs/history.local.html` →
  `scp docs/history.local.html rachett:/var/www/discovery/history.html`.
  (No data rebuild needed — copy/CSS/nav changes don't touch the timeline JSON.)
- **Verify every phase with Playwright** at 1280px AND 390px: zero console
  errors, and `document.documentElement.scrollWidth === clientWidth` at 390px
  (no horizontal overflow). Trigger every lazy section (scroll to bottom slowly)
  before measuring.
- Keep the page self-contained; no new network deps.

---

## Phase 0 — Fix mobile horizontal overflow (BUG)  ·  Model: **Sonnet**
The page scrolls sideways on a 390px phone (document width 463px). Culprit is the
**Milestone club** rows in *Fun lists*: `#msList` / `.msrow` with the fixed
right-hand `.ms-h` ("X.X h · inside") column — the row's fixed columns don't fit
at phone width and push the whole document wide.

- **Files:** `docs/history.html` (the `.msrow` / `.ms-h` / `.ms-main` CSS block).
- **Do:** Make the milestone row responsive — allow the right-hand hours column to
  wrap or shrink under ~420px (e.g. flex-wrap the row, or drop `.ms-h` to a second
  line / reduce its fixed width) so no descendant exceeds the viewport. Confirm
  the same wrapping pattern isn't lurking in sibling list rows (`.dclist`,
  `.devlist`, `.netrows`) at 390px while you're in there.
- **Acceptance:** At 390px, `scrollWidth === clientWidth`; Milestone club reads
  cleanly; desktop layout of the row visually unchanged at ≥900px.
- **Why Sonnet:** tightly scoped responsive-CSS fix with a hard, measurable pass
  condition — no product judgment needed.

## Phase 1 — Copy pass: hero lede, title voice, disclaimer trim  ·  Model: **Opus**
Language/voice work — the judgment-heavy phase.

- **1a — Rewrite the stale hero lede** (`<p class="lede">`, ~line 454). It currently
  previews only river + iTunes shelf + bubble field. Rewrite so it previews the
  page as it now exists: genres → the artists (roster + similarity map) → records →
  songs → how & when you listen. Keep it ~2–3 sentences, same voice, don't turn it
  into a table of contents.
- **1b — Harmonize section titles** to the evocative register the majority already
  use. Priority: **"Fun lists"** (weakest — give it a real name). Also weigh
  "How you listen" and "Every artist on record" against neighbors; only change them
  if the new title is clearly better. Do NOT rename anything that other copy or the
  (future) section-nav references without updating those too.
- **1c — Trim the repeated "household plays are filtered out" disclaimer.** It
  appears in 4 section blurbs + the footer + the toggle tooltip. Keep it where it
  first matters and in the footer; cut or shorten the redundant repeats so it reads
  as reassurance, not boilerplate.
- **Files:** `docs/history.html` only (static copy).
- **Acceptance:** Fable reviews the new lede + titles for voice before deploy. No
  layout regression at either width.
- **Why Opus:** this is taste/voice writing that carries the page's tone — the part
  a smaller model tends to make generic.

## Phase 2 — Sticky in-page section nav + records whitespace  ·  Model: **Sonnet**
- **2a — Section nav.** The page is ~16,500px of single scroll with no way to jump.
  Add a lightweight sticky jump-nav (e.g. a slim top bar or a right-rail chip list)
  linking each `<section>` by its heading, respecting the existing dark theme and
  the reveal animations. Must not add horizontal overflow at 390px (collapse to a
  compact control on mobile). Anchor targets = existing section ids
  (`howyoulisten`, `artiststories`, `tastenet`, `records`, `songs`, `funlists`, +
  ids to add for the river/roster/itunes sections that lack them).
- **2b — Records whitespace (minor).** In *The records*, "Album people or singles
  people?" has a tall empty lower region because its grid sibling is much taller.
  Balance it (align content, or let the shorter card not stretch).
- **Files:** `docs/history.html`.
- **Acceptance:** Nav jumps to every section incl. lazy ones (clicking a not-yet-
  revealed section still scrolls + triggers its reveal); zero overflow at 390px;
  desktop + mobile screenshots reviewed.
- **Why Sonnet:** standard, well-bounded HTML/CSS/JS feature with clear acceptance.

## Phase 3 — Verify + deploy  ·  Model: **Sonnet**
- Run the full Playwright verification (both widths, all sections revealed, console
  clean, no overflow) against the injected local copy served over a temp HTTP
  server, then deploy per the runbook and smoke-check HTTP 200 on the live URL.
- Update `CLAUDE.md` history-page entry + `plans/` note that the polish pass shipped.
- **Why Sonnet:** mechanical execution of an existing runbook.

## Phase 4 — (GATED) Narrative reorder — what-then-how  ·  Model: **Opus**
**Do not start without explicit user go-ahead** (decision: keep gated). Regroup
sections into a clean arc: the *what*-zoom (genre river → every artist → shape of
your taste → records → songs) then the *how/when* cluster (how you listen → artist
stories → fun lists), iTunes shelf last.

- **Risk to manage:** lazy-init `IntersectionObserver`, reveal animations, and
  cross-section click wiring (an artist clicked anywhere drives the trajectory
  panel) all assume current DOM order. Move whole `<section>` blocks; re-verify
  every lazy section still inits and every cross-section click still fires.
- **Files:** `docs/history.html`.
- **Acceptance:** every section reveals + all interactions work post-move; both
  widths clean; Fable reviews the new flow before deploy.
- **Why Opus:** judgment-heavy ordering + the trickiest breakage surface on the page.

---

## Model-assignment summary
| Phase | Work | Model | Rationale |
|------|------|-------|-----------|
| 0 | Mobile overflow bug | **Sonnet** | scoped fix, hard pass condition |
| 1 | Copy / voice pass | **Opus** | taste-driven writing carries the page tone |
| 2 | Section nav + whitespace | **Sonnet** | standard bounded feature |
| 3 | Verify + deploy | **Sonnet** | mechanical runbook |
| 4 | Reorder (gated) | **Opus** | high judgment + high breakage risk |

Orchestration (Fable): spec, per-phase review, and deploy go/no-go — consistent
with the songs/albums expansion pattern.

## Deferred / not in scope
- Two similar all-artist blobs (bubble field vs. network): keep both — one reads
  magnitude, the other relationships. Revisit only if the reorder makes the
  redundancy feel heavier.
