---
phase: 05-reliability-documentation
plan: 01
subsystem: docs
tags: [documentation, troubleshooting, faq, wake-tail, docs-01]
requires:
  - phase: 02-discovery-rebroadcast
    provides: DISC-01 single-call re-broadcast behaviour the fixed advice describes
  - phase: 03-retry-schedule-reshape
    provides: RETRY-01..04 in-request retransmit behaviour the contextualised wrapper guidance describes
provides:
  - "Anchor `#gen4-power-save-wake-tail` in docs/user-guide/troubleshooting.md (heading exactly `### Gen4 Power-Save Wake Tail`) — the anchor plan 05-02's ceiling-lights.md and animation.md cross-links target"
  - "DOCS-01 wake-tail guidance: sub-250 ms bound, gen4 identification one-liner, 15 s polling recipe, no-keepalive admonition"
  - "FAQ entry linking to user-guide/troubleshooting.md#gen4-power-save-wake-tail"
affects: [05-02, 05-03]
tech-stack:
  added: []
  patterns: ["mkdocs-Material admonition with custom title (`!!! note \"...\"`, 4-space body)", "Symptom/Causes/Solution troubleshooting section shape"]
key-files:
  created: []
  modified:
    - docs/user-guide/troubleshooting.md
    - docs/faq.md
key-decisions:
  - "Wake-tail heading pinned exactly as `### Gen4 Power-Save Wake Tail` → anchor `#gen4-power-save-wake-tail` (three pages link to it; do not rename)"
  - "Discovery-timeout examples use timeout=30.0 (not the plan's 10.0) so the examples actually increase the 15.0 s default"
duration: 6min
completed: 2026-07-17
status: complete
---

# Phase 5 Plan 01: Gen4 Wake-Tail Documentation Summary

Gen4 power-save wake tail documented on the troubleshooting page (sub-250 ms latency-only, firmware-major identification, optional 15 s get_color() poll, no-keepalive admonition) with a link-only FAQ entry, plus in-place fixes for the page's stale pre-v1.1 discovery/retry advice.

## Anchor for downstream plans (05-02 depends on this)

- Heading, written exactly: `### Gen4 Power-Save Wake Tail`
- Generated anchor: `#gen4-power-save-wake-tail`
- Cross-link path from docs root (used by faq.md): `user-guide/troubleshooting.md#gen4-power-save-wake-tail`
- Cross-link path from user-guide pages (for 05-02): `troubleshooting.md#gen4-power-save-wake-tail`

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Gen4 Power-Save Wake Tail section | f4b50a6 | docs/user-guide/troubleshooting.md |
| 2 | Fix stale discovery/retry advice (audit #5–#8) | 015a112 | docs/user-guide/troubleshooting.md |
| 3 | Add wake-tail FAQ entry (link-only) | 15cfb2f | docs/faq.md |

## What Was Done

### Task 1 — wake-tail section (DOCS-01)

New `### Gen4 Power-Save Wake Tail` section under `## Performance Issues`, between "Slow Operations" and "Docker / Container Networking" (no TOC edit needed — a `###` under an already-TOC'd `##`). Follows the page's Symptom/Causes/Solution shape:

- Symptom: first command after ~1 min idle up to ~250 ms instead of single-digit milliseconds; gen4 only; zero packets lost (latency, not reliability); claims scoped to healthy networks; no mechanism narrative (no ESP32/modem-sleep, no mesh claims)
- Identification: `firmware = await device.get_host_firmware()` / `firmware.version_major >= 4`, with the cached `device.host_firmware` note and an explicit "no product-ID list" warning
- Solution: `keep_awake(light)` recipe — `await light.get_color()` + `await asyncio.sleep(15)` with the 10–15 s comment; runs via `asyncio.create_task()`/`asyncio.TaskGroup` with no coordination (library serialises per connection); read-only and far below the ~20 msg/sec budget
- D5-06 admonition: `!!! note "lifx-async deliberately ships no keepalive daemon"` with the zero-idle-loss why
- D5-02 outbound cross-link: page-level `(animation.md)` link (no heading anchor — the streaming section is created by 05-02)

### Task 2 — stale advice fixed in place (audit #5–#8)

- "Partial Device Discovery": multi-pass discovery loop replaced with the DISC-01 statement (single call re-broadcasts `GetService` on an escalating schedule); `timeout` increase is the lever; Symptom/Causes kept intact
- "Discovery Timeout Too Short": `async with discover(...)` API misuse rewritten to async-for iteration; stale "Default is 3.0" corrected to the actual 15.0 s (`DISCOVERY_TIMEOUT`, src/lifx/const.py:28)
- "Connection Drops": retry-wrapper example kept, contextualised — since v1.1 the library retransmits within each request's timeout, so wrappers are for whole-operation failures, not per-packet reliability (no internal constants or schedule shapes named)

### Task 3 — FAQ additions (D5-01, audit #14/#15)

- One combined entry under `## Performance`: "Why is the first command after idle slower on newer devices?" — sub-250 ms, zero loss, no keepalive daemon by design, link to `user-guide/troubleshooting.md#gen4-power-save-wake-tail`
- "Why can't discovery find my devices?" gained one sentence: a single call re-broadcasts automatically on an escalating schedule; increase `timeout`, don't call discovery repeatedly

## Figure Traceability (no invented numbers)

Every figure in the new content traces to 05-RESEARCH.md §Verified Numbers:

| Figure as published | Source row in §Verified Numbers |
|---------------------|--------------------------------|
| "up to ~250 ms" / "sub-250 ms" | Wake-tail bound (max observed 224 ms → sub-250 ms) |
| "zero packets" lost while idle / "idle devices lose zero packets on healthy networks" | Packet loss when idle (0–120 s): zero everywhere |
| gen4 only; gen2/gen3 show no wake tail | Effect concentration |
| `version_major >= 4` identification | Gen4 identification (verified live: fw 2.90 / 3.50 / 4.112) |
| 15 s sleep, "10–15 s keeps the wake tail away" | Polling interval (15 s spike-tested; 10 s Photons precedent) |
| ~20 msg/sec device budget | CLAUDE.md concurrency section (cited in RESEARCH Project Constraints) |
| 15.0 s discovery default | src/lifx/const.py:28 `DISCOVERY_TIMEOUT` (audit #7) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Discovery-timeout example value raised from the plan's 10.0 to 30.0**
- **Found during:** Task 2
- **Issue:** The plan's action text said to pass `timeout=10.0` in the "Discovery Timeout Too Short" example, but the section's stated fix is to *increase* the timeout and the actual default is 15.0 s — an example passing 10.0 would demonstrate decreasing it (the 10.0 was a holdover from when the default was believed to be 3.0)
- **Fix:** Example uses `timeout=30.0`; the inline comment states the 15.0 s default. All must_haves truths and acceptance criteria (async-for shape, 15.0 stated, no 3.0) are met; none required 10.0
- **Files modified:** docs/user-guide/troubleshooting.md
- **Commit:** 015a112

**2. [Rule 1 - Bug] Same 10.0-below-default inconsistency in the FAQ discovery entry being edited**
- **Found during:** Task 3
- **Issue:** The "Why can't discovery find my devices?" entry (which Task 3 edits) recommends "increasing timeout: `discover(timeout=10.0)`" — below the 15.0 s default, contradicting the very sentence the task adds
- **Fix:** Changed to `discover(timeout=30.0)` within the entry already being edited
- **Files modified:** docs/faq.md
- **Commit:** 15cfb2f

No other deviations — remaining work executed exactly as planned.

## Verification Evidence

- `uv run zensical build`: exit 0 after every task; warning count stayed at the 8-warning baseline (all in docs/api/effects.md and docs/api/index.md — pages this phase never edits); zero warnings name troubleshooting.md or faq.md, so the wake-tail anchor resolves
- Prohibition gates on troubleshooting.md: `grep -ci spike` = 0, `grep -ci mesh` = 0, `grep -ci ESP32` = 0
- `git diff --name-only HEAD~3 HEAD` lists only docs/user-guide/troubleshooting.md and docs/faq.md — mkdocs.yml, docs/changelog.md, docs/api/*.md and source untouched
- No file deletions, no untracked files left behind

## Known Stubs

None — no placeholders, empty values, or unwired content; all sections carry final prose and runnable snippets.

## Self-Check: PASSED

- FOUND: docs/user-guide/troubleshooting.md (`### Gen4 Power-Save Wake Tail` present, count 1)
- FOUND: docs/faq.md (anchor link present)
- FOUND: commit f4b50a6
- FOUND: commit 015a112
- FOUND: commit 15cfb2f
