# IMPROVEMENTS.md — Spotify Discovery backlog

Running list of ideas, deferred work, and "don't forget this" items for the
discovery toolkit. Not a phase spec (that's `claude_initial_plan.md`, all done) —
this is the open-ended backlog. Newest / highest-priority items near the top.

Status legend: 🔜 planned · 🚧 in progress · ⏳ blocked/waiting · 💡 idea · ✅ done

---

## ⏳ Extended streaming history (GDPR data export)

**Status:** waiting on Spotify — user requested the export ~2026-07-15, delivery can
take up to ~30 days.

**Why:** the Web API has no true lifetime-history endpoint. Everything the toolkit
pulls today is a rolling/recency-weighted window:
- `top/*` long-term ≈ fuzzy "all-time" (recency-weighted, opaque decay), not full history
- `top/*` medium ≈ last 6 months · short ≈ last 4 weeks
- `recently-played` = hard cap of the **last 50 plays** (a day or two at most)
- Liked Songs = the only truly datable long-range signal, via each track's `added_at`

The GDPR **Extended Streaming History** export is the only source of genuine
multi-year, per-play history (timestamped stream events back to account creation).

**Plan when the data arrives:**
- [ ] Land the export files somewhere gitignored (they're personal data — never commit).
- [ ] Write a loader (`streaming_history.py`?) that parses the `Streaming_History_Audio_*.json`
      files into a normalized play-event table (ts, artist, track, ms_played, reason_start/end).
- [ ] New primitives on top of it, e.g.:
      - true all-time top artists/tracks (real counts, real dates — not the API's weighted guess)
      - listening timeline / "on this day" / era detection (what was I into in year X)
      - skip-rate and completion signals (ms_played vs track length) as a real taste signal
      - "forgotten favorites" — heavy past plays that dropped off recently (revival angle)
- [ ] Consider a new discovery recipe seeded from deep history rather than the shallow API window.
- [ ] Decide whether any of this reaches the MCP server / Stats tab, or stays local-only
      (the export is bulky and private — lean toward local-only unless there's a clear win).

**Notes / open questions:**
- Two export tiers exist: the standard "Account data" (short, ~1yr) vs. the fuller
  "Extended streaming history" (all-time, requested separately). Confirm which one arrives.
- Format is per-year JSON arrays; schema is stable but verify field names on arrival.

---

## 💡 Ideas / parking lot

_(add loose ideas here; promote to a real section when they get concrete)_

- Backfill: nothing yet.
