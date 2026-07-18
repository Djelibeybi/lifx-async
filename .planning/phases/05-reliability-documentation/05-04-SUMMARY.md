---
phase: 05-reliability-documentation
plan: 04
subsystem: docs
tags: [documentation, gap-closure, accuracy, version-attribution]
requires:
  - phase: 05-reliability-documentation
    plan: 01
    provides: Wake-tail troubleshooting section and discovery-timeout guidance
  - phase: 05-reliability-documentation
    plan: 02
    provides: Streaming and Flow Control section in the animation guide
  - phase: 05-reliability-documentation
    plan: 03
    provides: Fire-and-forget rescope and contextualised retry guidance
provides:
  - Version-neutral wire-behaviour claims at both former CR-01 sites (D5-12)
  - Accurate discover() docstring default (15.0 s) matching DISCOVERY_TIMEOUT (D5-13)
  - Accurate ~4 s idle-timeout figure in CLAUDE.md Discovery DoS Protection (WR-01)
  - Six copy-paste-safe code examples verified against the shipped API (WR-03..WR-08)
  - Diagram-consistent Layer 1-8 prose numbering with a Utilities section (IN-02)
  - Honest ~20 FPS prose intro on docs/api/animation.md (F1, D5-14)
affects: []
tech-stack:
  added: []
  patterns: []
key-files:
  created: []
  modified:
    - docs/user-guide/animation.md
    - docs/user-guide/troubleshooting.md
    - docs/faq.md
    - docs/architecture/overview.md
    - docs/user-guide/advanced-usage.md
    - docs/api/animation.md
    - CLAUDE.md
    - src/lifx/api.py
decisions:
  - "D5-12 implemented verbatim: version clause stripped at both sites, no substitute attribution of any kind"
  - "D5-13 fence held: git diff vs 55545b5 shows exactly src/lifx/api.py, 1 insertion, 1 deletion under src/"
  - "D5-14 fence held: git diff vs 55545b5 under docs/api + docs/changelog.md names exactly docs/api/animation.md"
  - "IN-02 resolved by renumbering prose to match the mermaid diagram (planner-recorded choice) — new Layer 1: Utilities section derives only from the diagram boxes and CLAUDE.md's Utilities entry"
metrics:
  duration: ~6min
  completed: 2026-07-17
status: complete
---

# Phase 05 Plan 04: Gap Closure — Version-Neutral Claims and Example Accuracy Summary

Stripped the false "Since v1.1" package-version attribution from both shipped guides (CR-01/D5-12) and closed the full operator-opted residual set: stale defaults, six broken examples, layer renumbering, and the inflated FPS intro.

## What Was Done

### Task 1: Version-neutral wire-behaviour claims + stale-figure fixes (e961d02)

- Both CR-01 sites now open with the exact D5-12 sentences: the animation guide's Streaming and Flow Control paragraph and the troubleshooting Connection Drops solution carry no version attribution; latest-frame-wins framing and the whole-operation try/except wrapper guidance preserved untouched.
- CLAUDE.md idle-timeout bullet corrected to ~4 seconds (max_response_time × idle_timeout_multiplier), matching MAX_RESPONSE_TIME 1.0 × IDLE_TIMEOUT_MULTIPLIER 4.0 in src/lifx/const.py (WR-01).
- discover() docstring timeout line corrected to (default 15.0), matching `timeout: float = DISCOVERY_TIMEOUT` and the discover_mdns() docstring style (WR-02, the sole D5-13 source edit).
- Australian spelling: "visualisers" in the animation guide integrations bullet (IN-01).
- Gates: zero "Since v1.1" anywhere in docs/, CLAUDE.md, or src/; `uv run --frozen pytest tests/test_api -q` 63 passed; build at baseline.

### Task 2: Six broken/misleading examples fixed against shipped source (def489f)

- faq.md direct-connection workaround no longer awaits the plain `Light(...)` constructor; double spaces before `ip=` collapsed in both examples (WR-03, IN-03).
- faq.md and architecture/overview.md protocol examples import the real generated `LightHsbk` class, pass raw uint16 values (32768/65535/52428 preserving the original 180°/1.0/0.8 intent), and use `duration=1000` integer milliseconds (WR-04, WR-05). Device-layer examples keep the float `HSBK` class.
- advanced-usage.md: all five membership-style capability tests replaced with `ProductInfo.has_capability(...)` guarded for None (WR-06).
- troubleshooting.md registry example uses `len(registry)` instead of the non-existent `registry.items()` (WR-07); both connection-reuse `set_color` calls rebalanced so saturation/brightness/kelvin sit inside the HSBK constructor (WR-08).

### Task 3: Layer renumbering, FPS prose fix, baseline hold (cf75b2f)

- overview.md prose headings renumbered to match the page's own mermaid diagram: sequence now 1–8 with a new `### Layer 1: Utilities` section (Purpose, three bullets, Key Files: color.py and products/registry.py) derived only from the diagram boxes and CLAUDE.md's Utilities entry (IN-02).
- docs/api/animation.md line 5 now reads "optimised for real-time effects at up to ~20 FPS" (F1, the sole D5-14 docs/api edit).

## Fence Confirmation (plan output requirement 1)

- **D5-13 held:** `git diff 55545b5..HEAD --stat -- src/` → exactly `src/lifx/api.py | 2 +-` (1 insertion, 1 deletion). No other source file or docstring touched.
- **D5-14 held:** `git diff 55545b5..HEAD --name-only -- docs/api docs/changelog.md` → exactly `docs/api/animation.md`. docs/changelog.md and all docstring-fed docs/api/ content byte-identical.
- mkdocs.yml untouched (D5-01); no new pages, no nav changes.

## Flagged Edge-Probe Assumptions Carried Forward (plan output requirement 2)

1. **DOCS-01 / idempotency:** every edit was an exact-string replacement gated by exact-count greps; re-execution against the fixed files is a detectable no-op. Carried to verification.
2. **DOCS-01 / concurrency:** tasks ran sequentially with one atomic signed commit each; every task independently ended with a green `uv run zensical build`, so any interruption point was clean and buildable. Carried to verification.
3. **DOCS-02 / unclassified (honest residue):** the version-attribution edge is now explicitly closed (D5-12 + zero-occurrence gate), but the probe cannot enumerate further accuracy edges in the streaming guidance (future API drift, figures invalidated by later hardware evidence). The verifier should independently probe the factual claims in the edited sections rather than treat the truths above as exhaustive.

## Build Baseline (plan output requirement 3)

`uv run zensical build` exits 0 after every task. Final state: **8 issues found — exactly the pre-existing baseline** (5× api/effects.md anchor warnings, 3× api/index.md anchor warnings). No issue names docs/api/animation.md, overview.md, or any other page edited by this plan.

## Requirements (plan output requirement 4)

DOCS-01 and DOCS-02 remain marked complete — `requirements.mark-complete` reported both `already_complete` with no writes applied. The gap was an accuracy defect inside already-satisfied requirements; no REQUIREMENTS.md change was needed, as the plan predicted.

## Deviations from Plan

### Observations (no fixes required)

**1. [Plan-literal imprecision] Acceptance grep named the wrong exception class**
- **Found during:** Task 1 / plan-level verification
- **Issue:** The acceptance criterion checked `except LifxTimeoutError` count "unchanged from pre-edit" as the proxy for the retry wrapper surviving; that literal was 0 both before and after (the wrapper has always used `except LifxError`).
- **Resolution:** Verified the real invariant directly — 2 `except Lifx*` blocks in troubleshooting.md pre- and post-edit; the whole-operation try/except wrapper is intact and the deletion prohibition held. No file change; criterion satisfied as written (0 == 0) and in intent.

Otherwise: plan executed exactly as written — all target lines matched the plan's descriptions on first read, so the STOP-on-discrepancy instruction never triggered.

## Known Stubs

None — no placeholder content, empty-value wiring, or TODO markers introduced.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or trust-boundary changes. All three plan threat mitigations (T-05-06/07/08) delivered: examples source-verified, no FPS figure raised (one lowered), version claim removed rather than substituted.

## Commits

| Task | Commit | Description |
| ---- | ------- | ----------- |
| 1 | e961d02 | Version attributions removed; stale defaults fixed (CR-01, WR-01, WR-02, IN-01) |
| 2 | def489f | Six broken examples fixed against shipped API (WR-03..WR-08, IN-03) |
| 3 | cf75b2f | Layer renumbering + Utilities section; ~20 FPS prose (IN-02, F1) |

## Self-Check: PASSED

- All 8 modified files present on disk with expected content (verified by task gates)
- Commits e961d02, def489f, cf75b2f present in git log
- Zero "Since v1.1" in docs/, CLAUDE.md, src/ (CR-01 closed)
- Build at 8-issue baseline after final task
