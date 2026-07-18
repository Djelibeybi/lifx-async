---
phase: 05-reliability-documentation
plan: 02
subsystem: docs
tags: [documentation, animation, streaming, flow-control, docs-02, ledfx]
requires:
  - phase: 05-reliability-documentation
    provides: "Plan 05-01's `#gen4-power-save-wake-tail` anchor in docs/user-guide/troubleshooting.md — both cross-links in this plan target it"
  - phase: 04-animation-flow-control
    provides: "ANIM-01/02 ack-gated pacing + latest-frame-wins behaviour (D4-01/D4-02) and the 04-13 operator FPS verdict this plan documents"
provides:
  - "DOCS-02 streaming-consumer guidance: `## Streaming and Flow Control` (`#streaming-and-flow-control`) in docs/user-guide/animation.md — behavioural contract, do-not-reimplement list, minimal loop, per-device-class FPS numbers"
  - "animation.md stale-claim fixes (audit #1–#4): ~20 FPS ceiling framing throughout, 20 FPS example sleeps, saturation-vs-network-loss Flickering entry"
  - "D5-02 inbound cross-links: animation.md → wake-tail and ceiling-lights.md → wake-tail (completes all three D5-02 link directions)"
affects: [05-verification, DOCS-02]
tech-stack:
  added: []
  patterns: ["Behavioural-contract-only documentation of internal flow control (D5-09)", "Primary/secondary cause split in troubleshooting entries"]
key-files:
  created: []
  modified:
    - docs/user-guide/animation.md
    - docs/user-guide/ceiling-lights.md
key-decisions:
  - "Flickering entry references the streaming section by name in prose (no same-page anchor link) so Task 1's build stayed warning-clean before the section existed"
  - "ceiling-lights.md cross-link placed directly after the Supported Devices table — nearest natural first-command context"
duration: 9min
completed: 2026-07-17
status: complete
---

# Phase 5 Plan 02: Streaming-Consumer Guidance Summary

DOCS-02 streaming guidance (ack-gated pacing, latest-frame-wins, do-not-reimplement list, ~20/~10 FPS per-device-class numbers from the 04-13 operator verdict) written into animation.md alongside in-place fixes for that page's stale 30+ FPS claims, plus the two remaining D5-02 wake-tail cross-links.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix animation.md's stale pre-v1.1 claims (audit #1–#4) | 2fb7afd | docs/user-guide/animation.md |
| 2 | Add streaming-consumer section + D5-02 cross-links | e417142 | docs/user-guide/animation.md, docs/user-guide/ceiling-lights.md |

## What Was Done

### Task 1 — stale claims fixed in place (D5-10 audit #1–#4)

- Intro reworded from "push color data at 30+ FPS" to the ~20 FPS platform-ceiling framing (a ceiling of the WiFi/Set64 wire path, not a client limitation)
- "High frame rates" bullet adjusted to "up to ~20 FPS"
- All three example sleeps (`1 / 30`) changed to `asyncio.sleep(1 / 20)`; the trailing comment now reads "# 20 FPS"
- "Flickering or Glitches" rewritten with a primary/secondary cause split: device saturation (latest-frame-wins drops frames → stutter, by design, never a backlog or freeze; fix by reducing FPS, observable via `stats.gated`) versus genuine network loss (weak WiFi signal). The "accept that some packet loss is normal for UDP" advice removed entirely

### Task 2 — `## Streaming and Flow Control` (D5-07/D5-08/D5-09) + cross-links (D5-02)

New section inserted between Performance Tips and Troubleshooting, written from the D4-01/D4-02 behavioural summary (not the Animator docstring):

- Narrative: since v1.1 the layer paces frame delivery against device acknowledgements; when a device falls behind, new frames are dropped, never queued — latest-frame-wins; no consumer-facing configuration
- Do-not-reimplement list (LedFx pattern): no own acknowledgement tracking, no keepalive daemons, no frame-retry wrappers — retrying a dropped frame is actively wrong; the correct recovery is simply the next frame
- Minimal streaming loop in the page's existing style (uint16 tuples, synchronous `send_frame()`, try/finally + `animator.close()`), pinned at `target_fps = 20`
- Per-device-class FPS guidance: ~20 FPS WiFi/Set64 ceiling; the Ceiling Capsule (16×8 zones — 128 zones — at 3 packets per frame) sustains ~10 FPS; oversending symptom is stutter — degradation by design; monitoring aside notes `stats.gated` / `stats.acks_outstanding` (public AnimatorStats fields)
- D5-02 cross-link sentence to `troubleshooting.md#gen4-power-save-wake-tail` (anchor verified against 05-01-SUMMARY.md before writing)
- ceiling-lights.md gained one sentence after the Supported Devices table: Ceiling devices are gen4, linking to the same wake-tail anchor. No other changes to that page

All three D5-02 link directions now exist: troubleshooting→animation (05-01), animation→wake-tail and ceiling-lights→wake-tail (this plan).

## Flagged DOCS-02 Edge-Probe Assumption (carried to verification)

The planner's edge probe could not classify DOCS-02 ("unclassified — review manually"). Planner assumption, carried forward for the verifier: DOCS-02's edge risk is fully covered by the D5-08 truths (concrete per-device FPS numbers) and D5-09 truths (behavioural-contract-only scope — no internal constants). If the verifier finds an uncovered DOCS-02 edge, route it back as a gap rather than passing silently.

## D5-09 Boundary Confirmation

No internal tuning constants appear in either page: `grep -c 'expiry' docs/user-guide/animation.md` = 0; `grep -cE 'gate (of|at) 2|2 outstanding'` = 0. Neither the ack-probe placement, the outstanding-ack gate threshold, nor the ack expiry duration is stated anywhere in user-guide prose. The section was written from the D4-01/D4-02 behavioural summary in 05-RESEARCH.md §Shipped Animation Behaviour, not from the Animator docstring (Pitfall 3 avoided).

## Figure Traceability (no invented numbers)

| Figure as published | Source |
|---------------------|--------|
| ~20 FPS platform ceiling over WiFi/Set64 | 05-RESEARCH.md §Verified Numbers (REQUIREMENTS.md Out of Scope; animation-flow-control.md Constraints) |
| Capsule ~10 FPS at 16×8 zones (128 zones), 3 packets/frame | STATE.md 04-13 operator verdict, earmarked for DOCS-02 |
| Stutter = latest-frame-wins degradation by design, never a backlog or freeze | STATE.md 04-13 operator verdict verbatim context |

## Deviations from Plan

None - plan executed exactly as written. (Task 1's prose reference to the streaming section is by name rather than an anchor link — placement discretion, keeping the Task 1 build warning-clean before the section existed in Task 2.)

## Verification Evidence

- `uv run zensical build`: exit 0 after each task; issue count stayed at the 8-issue baseline (5 in docs/api/effects.md, 3 in docs/api/index.md — pages this phase never edits); zero warnings name animation.md, ceiling-lights.md, or troubleshooting.md, so both new anchor links resolve
- Task 1 gates: `1 / 30` count 0, `1 / 20` count 3, `30\+ FPS` count 0, `~20 FPS` present, `packet loss is normal` count 0, `instead of 30` count 0, `stats.gated` present
- Task 2 gates: `^## Streaming and Flow Control` count 1; `latest-frame-wins`, `~20 FPS`, `~10 FPS`, `target_fps = 20`, `send_frame(`, `stutter` all present; wake-tail cross-link count 1 in each of animation.md and ceiling-lights.md
- `git diff --name-only HEAD~2 HEAD` lists only docs/user-guide/animation.md and docs/user-guide/ceiling-lights.md — mkdocs.yml, docs/api/*.md, docs/changelog.md, and source untouched (D5-01/D5-11 held)
- No file deletions, no untracked files left behind

## Known Stubs

None — no placeholders, empty values, or unwired content; all sections carry final prose and runnable snippets.

## Threat Flags

None — no new security-relevant surface; the two threat-register mitigations (T-05-04 constants boundary, T-05-05 20 FPS example pinning) are both applied and verified above.

## Self-Check: PASSED

- FOUND: docs/user-guide/animation.md (`## Streaming and Flow Control` present, count 1)
- FOUND: docs/user-guide/ceiling-lights.md (wake-tail anchor link present, count 1)
- FOUND: commit 2fb7afd
- FOUND: commit e417142
