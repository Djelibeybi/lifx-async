---
phase: 05-reliability-documentation
plan: 03
subsystem: docs
tags: [documentation, stale-content-audit, advanced-usage, architecture-overview, claude-md]
requires:
  - phase: 04-animation-flow-control
    provides: "Ack-gated animation flow control (flow.py) and ~20 FPS platform-ceiling framing this plan documents"
  - phase: 02-discovery-rebroadcast
    provides: "DISC-01 internal re-broadcast behaviour that supersedes the two-pass discovery workaround"
  - phase: 03-retry-reshape
    provides: "RETRY-01..04 internal retransmission that contextualises the app-level retry guidance"
provides:
  - "advanced-usage.md free of pre-v1.1 workarounds (audit #9–#11): no two-pass discovery, fire-and-forget scoped to one-shots, retry wrapper contextualised"
  - "architecture/overview.md Layer 5 describing ack-gated pacing with animation/flow.py in Key Files (audit #12–#13)"
  - "CLAUDE.md aligned with shipped code: ~20 FPS framing and 15.0 s discovery default (finding F2)"
affects: []
tech-stack:
  added: []
  patterns:
    - "Behavioural wording only for internal flow control — no tuning constants in user-facing docs (D5-09)"
key-files:
  created: []
  modified:
    - docs/user-guide/advanced-usage.md
    - docs/architecture/overview.md
    - CLAUDE.md
key-decisions:
  - "Batched Discovery section removed entirely, replaced with a short paragraph noting discover_devices() re-broadcasts internally and timeout is the lever for slow networks"
  - "Fire-and-forget example converted from an unbounded while-True streaming loop to a bounded ~20 FPS sweep, removing the flooding-prone framing (T-05-07)"
  - "DOCS-02 not marked complete in REQUIREMENTS.md — plan 05-02 (the primary DOCS-02 streaming-guidance plan) is still pending; marking deferred to its completion"
duration: 8min
completed: 2026-07-17
status: complete
---

# Phase 05 Plan 03: Stale-Content Audit Fixes (advanced-usage, overview, CLAUDE.md) Summary

**One-liner:** Removed pre-v1.1 workaround recipes (two-pass discovery, fast=True streaming loops) and inflated 30+ FPS claims from advanced-usage.md, architecture/overview.md and CLAUDE.md, so no published page or repo instruction contradicts the v1.1 wire behaviour.

## What Was Done

### Task 1: advanced-usage.md (audit #9–#11) — commit dfc94bb

- **Audit #9:** Deleted the "Batched Discovery" two-pass quick/thorough pattern (superseded by DISC-01). A short paragraph now notes that a single `discover_devices()` call re-broadcasts internally on an escalating schedule, and that a longer `timeout` is the lever for slow networks. No TOC edit needed (page TOC lists `##` entries only).
- **Audit #10:** Retitled the fire-and-forget section to `### Fire-and-Forget Mode for Low-Latency One-Shots`. The framing sentence now directs sustained streaming to the [Animation Guide](animation.md) (page-level link, no anchor fragment — the streaming anchor is created in parallel by plan 05-02). `fast=True` stays documented for occasional low-latency one-shots. The example was converted from an unbounded `while True` loop at ~30 FPS (`sleep(0.033)`) to a bounded colour sweep at ~20 FPS (`asyncio.sleep(0.05)`); the "When to use" bullets no longer recommend high-frequency animation loops.
- **Audit #11:** "Robust Error Handling" contextualised, not deleted: new prose notes the library already retransmits each request within its timeout, so the wrapper is for whole-operation failures, not per-packet reliability. The try/except example is kept.

### Task 2: overview.md (audit #12–#13) + CLAUDE.md (finding F2) — commit 46501fd

- **Audit #12:** Layer 5 purpose reworded to "up to ~20 FPS over WiFi" (was 30+ FPS).
- **Audit #13:** Added an "Ack-Gated Pacing" bullet (frame delivery paced against device acknowledgements, latest-frame-wins, internal behaviour — no consumer configuration) and `animation/flow.py - Ack-gated flow control` to Key Files. Behavioural wording only; no tuning constants (D5-09).
- **Finding F2 (repo hygiene, "if you see it, fix it"):** CLAUDE.md Animation Layer bullet corrected to "(up to ~20 FPS)"; Discovery DoS Protection overall-timeout default corrected from 5.0 to 15.0 (`DISCOVERY_TIMEOUT`, src/lifx/const.py:28).

## Findings

Surfaced for the operator, NOT fixed (outside the locked D5-10/D5-11 audit scope):

- **F1:** `docs/api/animation.md:5` (hand-written prose intro, not docstring-fed) still says "optimized for real-time effects at 30+ FPS" — api/ pages are outside the D5-10 audit scope. One-line prose fix if the operator opts in (it is NOT a docstring). Verified still present at execution time.
- **F3:** No flatly wrong docstrings were found in the animation layer — the `Animator`/`AnimatorStats` docstrings were updated in Phase 4 and correctly describe ack-gated behaviour. Nothing to escalate under D5-11.

## Scope Confirmation

- `docs/api/*.md`: untouched
- `docs/changelog.md`: untouched
- Source files (`src/`): untouched
- `mkdocs.yml`: untouched (D5-01)
- `uv run zensical build` exits 0 after each task; 8 issues total, unchanged from the pre-edit baseline recorded in RESEARCH.md — all in docs/api/ pages this phase never edits; none name advanced-usage.md or overview.md

## Deviations from Plan

### Noted Adjustments

**1. DOCS-02 requirement marking deferred**
- **Found during:** State updates
- **Issue:** This plan's frontmatter lists `requirements: [DOCS-02]`, but plan 05-02 (the primary DOCS-02 streaming-guidance plan, running in parallel/next) also carries DOCS-02 and is incomplete. Marking DOCS-02 complete now would falsely flag the requirement done.
- **Resolution:** Deferred `requirements mark-complete DOCS-02` to plan 05-02's completion.
- **Files modified:** None

Otherwise: plan executed exactly as written.

## Verification Results

| Check | Result |
|-------|--------|
| No 'Batched Discovery' in advanced-usage.md; 're-broadcast' mentioned | PASS |
| No `0.033` / `~30 FPS` framing in advanced-usage.md | PASS |
| `### Fire-and-Forget Mode for Low-Latency One-Shots` heading; `fast=True` kept | PASS |
| Page-level `(animation.md)` link, zero anchor fragments (`animation.md#`) | PASS |
| Retry wrapper example kept + retransmit-within-timeout sentence added | PASS |
| No `30+ FPS` in overview.md; `~20 FPS` present; latest-frame-wins bullet; no tuning constants | PASS |
| `animation/flow.py` in overview.md Key Files | PASS |
| No `(30+ FPS)` / `default: 5.0` in CLAUDE.md; `~20 FPS` + `default: 15.0` present | PASS |
| No docs/api/, changelog, or src/ paths in the diff | PASS |
| `uv run zensical build` exit 0, 8-warning baseline held, no warning names edited pages | PASS |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | dfc94bb | docs(05-03): fix superseded workaround patterns in advanced-usage.md |
| 2 | 46501fd | docs(05-03): align overview.md Layer 5 and CLAUDE.md with shipped animation behaviour |

## Self-Check: PASSED

All modified files present on disk; commits dfc94bb and 46501fd verified in git log.
