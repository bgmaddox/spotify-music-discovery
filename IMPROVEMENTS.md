# IMPROVEMENTS.md — Spotify Discovery backlog

Running list of ideas, deferred work, and "don't forget this" items for the
discovery toolkit. Not a phase spec (that's `claude_initial_plan.md`, all done) —
this is the open-ended backlog. Newest / highest-priority items near the top.

Status legend: 🔜 planned · 🚧 in progress · ⏳ blocked/waiting · 💡 idea · ✅ done

---

## ✅ Extended streaming history (GDPR data export) — landed 2026-07-16

**Status:** done. The full Extended tier arrived 2026-07-15 (11 audio files,
2015→2026, ~40 MB, ~49k events), gitignored at
`data/Spotify Extended Streaming History/`. `streaming_history.py` collapses it
into `data/history_summary.json` (~88 KB) in one pass; sessions read only the
lean digest via `cli.py history-snapshot [--year YYYY]` — never the raw files
(they carry IPs/device strings). Covered by `tests/test_streaming_history.py`.
Follow-ups promoted to the parking lot below.

**Why:** the Web API has no true lifetime-history endpoint. Everything the toolkit
pulls today is a rolling/recency-weighted window:
- `top/*` long-term ≈ fuzzy "all-time" (recency-weighted, opaque decay), not full history
- `top/*` medium ≈ last 6 months · short ≈ last 4 weeks
- `recently-played` = hard cap of the **last 50 plays** (a day or two at most)
- Liked Songs = the only truly datable long-range signal, via each track's `added_at`

The GDPR **Extended Streaming History** export is the only source of genuine
multi-year, per-play history (timestamped stream events back to account creation).

**Delivered (2026-07-16):**
- [x] Export landed gitignored (covered by the existing `data/` ignore; verified with `git check-ignore`).
- [x] `streaming_history.py` loader — parses all `Streaming_History_Audio_*.json`, music-only
      (podcast/audiobook rows dropped), ≥30s = play / <30s = skip (Spotify's own threshold).
- [x] Primitives in the summary: true all-time top artists/tracks with real counts + per-year
      play curves (era detection), per-year leaderboards, skip rates, forgotten favorites
      (≥40 lifetime plays, silent in the last 2 calendar years).
- [x] Wired into `cli.py` as `history-build` / `history-snapshot [--year YYYY]`.

**Still open (parking lot):**
- [x] A deep-history discovery recipe — Recipe 29 (forgotten-favorites revival) shipped
      2026-07-16 with the "🤖 Back in rotation" playlist.
- [ ] Decide whether the history digest reaches the MCP server / Stats tab, or stays local-only
      (leaning local-only; the digest is small but still personal).

**Notes (confirmed on arrival):**
- The full Extended tier arrived; schema matched expectations (`ts`, `ms_played`,
  `master_metadata_*`, `spotify_track_uri`, `skipped`, `reason_*`).
- Gaps: 2017 missing entirely; 2015–2016 nearly empty (15 plays total) — Spotify use
  didn't really start until 2018. The 2013–2014 iTunes layer covers the pre-Spotify era.
- Caveat discovered: a heavy kids-music layer (CoComelon is the #1 all-time artist,
  plus Pinkfong/Disney soundtracks) — discovery reasoning should treat these as
  household plays, not taste signal.

---

## 💡 Ideas / parking lot

_(add loose ideas here; promote to a real section when they get concrete)_

- Backfill: nothing yet.
