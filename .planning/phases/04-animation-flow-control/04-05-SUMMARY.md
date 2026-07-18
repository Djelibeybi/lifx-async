---
phase: 04-animation-flow-control
plan: 05
subsystem: animation
tags: [animator, ack-gating, hardware-uat, harness, udp]

# Dependency graph
requires:
  - phase: 04-animation-flow-control
    provides: "04-04's shipped AckGate flow control and ack-gated Animator.send_frame (ANIM-01/ANIM-02), plus the port fix, as the exact implementation this harness measures rather than reimplements"
provides:
  - "uat_ack_stream.py: a standalone phase-dir hardware UAT harness measuring the shipped Animator.for_matrix/send_frame ack-gated path against real matrix/ceiling devices -- 20 FPS streaming, concurrent single-shot query-loss prober (max_retries=0), CopyFrameBuffer probe ack RTT observer, tiles/ceiling profiles, and a fixed 0/1/2 exit-code contract"
affects: [04-06-tiles-hardware-uat, 04-07-ceiling-hardware-uat]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Measurement-only private reach: AckRttObserver wraps Animator._ack_gate.track by plain attribute assignment and diffs AckGate._outstanding once per send_frame call to classify each resolved probe sequence as an ack (age <= ACK_EXPIRY_SECONDS) or an expiry -- same private-reach pattern uat_zero_loss.py used for send_packet (03-03 precedent), never touching the library's public surface"
    - "Single-shot concurrent prober on a dedicated DeviceConnection(max_retries=0) so Phase 3's retry schedule cannot mask loss the harness exists to measure"
    - "Fixed exit-code contract (0 PASS / 1 FAIL / 2 ENV-ERROR) with thresholds declared in the file before any run, mirroring uat_zero_loss.py's honest-reporting convention"

key-files:
  created:
    - .planning/phases/04-animation-flow-control/uat_ack_stream.py
  modified: []

key-decisions:
  - "Reachability guard uses the device's normal (retrying) connection with a generous timeout before any streaming, exiting 2 immediately on failure -- an off-network run must never fabricate a pass or spray hundreds of frames at nothing."
  - "Ceiling profile powers the device on and settles 1s before streaming (animation is invisible on a powered-off ceiling), confirms power via get_power(), records the reported tile chain dims (assumption A2 evidence), and asserts every sent frame is exactly 8 packets (7 row-aligned Set64 + 1 CopyFrameBuffer)."
  - "This plan intentionally does NOT mark ANIM-03/ANIM-04 complete in REQUIREMENTS.md, even though both appear in this plan's frontmatter requirements list. The harness only builds and shape-verifies the measurement contract -- it never runs against hardware here. 04-06's frontmatter owns ANIM-03 completion (Tiles hardware run) and 04-07's frontmatter owns ANIM-04 completion (Ceiling hardware run); marking either complete from this plan would misrepresent unproven hardware evidence as closed."

requirements-completed: []

coverage: []

# Metrics
duration: ~20min
completed: 2026-07-17
status: complete
---

# Phase 4 Plan 05: Ack-Gated Streaming Hardware UAT Harness Summary

**Built `uat_ack_stream.py`, a standalone phase-dir harness that drives the shipped `Animator.for_matrix()`/`send_frame()` ack-gated flow control at 20 FPS against real matrix/ceiling devices, with a concurrent single-shot `GetColor` prober and a fixed 0/1/2 exit-code contract, ready for plans 04-06/04-07 to run against real hardware.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-17 (approx)
- **Completed:** 2026-07-17
- **Tasks:** 1 completed
- **Files modified:** 1 created

## Accomplishments

- Created `.planning/phases/04-animation-flow-control/uat_ack_stream.py` (482 lines): imports and drives the SHIPPED `Animator.for_matrix`/`send_frame` gate directly -- no reimplemented gating, no header manipulation, no template access beyond the documented measurement-only ack RTT observer.
- `argparse` contract: `--ip` (required), `--profile {tiles,ceiling}` (required), `--fps` (20.0), `--duration` (30.0s ~= 600 offered frames/round), `--rounds` (3, mandatory repetition for loss claims per STATE blocker), `--query-rate` (2.0/s), `--query-timeout` (2.0s), `--json-out` (required). `--help` exits 0 without sending any packets (verified).
- Reachability guard: one generous-timeout `GetColor` probe on the device's normal retrying connection before round 1; on failure, exits 2 (ENV-ERROR) immediately, writing an honest skipped-result JSON without streaming a single frame.
- Ceiling profile: powers the device on (`set_power(True)`) and settles 1s before streaming (animation is invisible on a powered-off ceiling), confirms power via `get_power()`, records the reported tile chain width x height (assumption A2 evidence, expected 13x26), and asserts every sent frame is exactly 8 packets (7 row-aligned Set64 + 1 final CopyFrameBuffer) -- deviations recorded in `packet_shape_ok`, never silently ignored.
- `AckRttObserver`: wraps `Animator._ack_gate.track` (plain attribute assignment, same private-reach pattern `uat_zero_loss.py` used for `send_packet`) to record `{sequence: sent_at}`, then diffs `AckGate._outstanding` once per `send_frame()` call -- a resolved sequence with age <= `ACK_EXPIRY_SECONDS` (1.0s) is an ack RTT sample, older is an expiry. RTT resolution is documented as one frame tick (~50ms at 20 FPS), not true wire RTT.
- Concurrent query prober: a dedicated `DeviceConnection(max_retries=0)` issuing single-shot `GetColor` requests at `--query-rate`, counting ok/lost and latency -- Phase 3's retry schedule cannot mask loss here by design.
- Fixed exit-code contract declared in the file before any run: 0 PASS (every round `query_loss_pct == 0` AND `delivered_ratio >= 0.85`; ceiling additionally requires `packet_shape_ok` AND >= 1 ack RTT sample per round), 1 FAIL (thresholds missed, reported honestly), 2 ENV-ERROR (reachability probe failed, no streaming attempted).
- Every run writes a full JSON results file: per-round offered/sent/gated/delivered_ratio, query ok/lost/loss_pct/latency median, ack RTT median/p95/sample count/expiries, ceiling packet-shape flag, tile chain dims, the fixed thresholds, the spike 003 baseline block, and the pass verdict/exit code.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the ack-stream measurement harness (uat_ack_stream.py)** - `0dee328` (feat)

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified

- `.planning/phases/04-animation-flow-control/uat_ack_stream.py` - New: standalone hardware UAT harness (never imported from `src/` or `tests/`, never shipped). Drives shipped `Animator`/`DeviceConnection`; tiles/ceiling profiles; `AckRttObserver`; fixed 0/1/2 exit-code contract; JSON evidence output.

## Verification Evidence

```
uv run python .planning/phases/04-animation-flow-control/uat_ack_stream.py --help
  -> exit 0, full usage printed, no packets sent

uv run ruff check .planning/phases/04-animation-flow-control/uat_ack_stream.py
  -> All checks passed!

uv run ruff format --check .planning/phases/04-animation-flow-control/uat_ack_stream.py
  -> 1 file already formatted

uv run pyright .planning/phases/04-animation-flow-control/uat_ack_stream.py
  -> 0 errors, 0 warnings, 0 notices

uvx prek run --files .planning/phases/04-animation-flow-control/uat_ack_stream.py
  -> trim trailing whitespace: Passed
  -> fix end of files: Passed
  -> check for added large files: Passed
  -> check for case conflicts: Passed
  -> check for merge conflicts: Passed
  -> detect private key: Passed
  -> mixed line ending: Passed
  -> check docstring is first: Passed
  -> debug statements (python): Passed
  -> ruff format: Passed
  -> ruff (legacy alias): Passed
  -> bandit: Passed (after targeted # nosec B105 on the ENV-ERROR "pass": False
     verdict placeholder, same precedent as uat_zero_loss.py's "pass": None)
  -> codespell: Passed

git status --short
  -> ?? .planning/phases/04-animation-flow-control/uat_ack_stream.py (before commit)
  -> clean after commit
```

## Decisions Made

- Ack RTT measurement piggybacks on `send_frame()`'s own cadence (once per call) rather than an independent socket poll -- explicitly documented as one-frame-tick resolution (~50ms at 20 FPS), matching the plan's stated measurement-only scope.
- Query prober constructs its own `DeviceConnection` with `max_retries=0` at the constructor level (not per-request override) so every `request()` call is single-shot by construction -- no risk of accidentally inheriting a retrying default.
- Used `lifx.const.TIMEOUT_ERRORS` (the project's existing Python 3.10/3.11+ compatibility tuple) instead of a bare `except TimeoutError` when waiting on `stop.wait()`, since `asyncio.TimeoutError` is not a subclass of the builtin on 3.10.
- Chain-dimension mismatch (e.g. ceiling reporting something other than 13x26) is recorded in the JSON but is NOT a hard exit-code gate -- only query loss, delivered ratio, and (for ceiling) packet-shape/ack-RTT-sample-count gate the verdict, per the plan's exit-code contract.
- Deliberately did not mark ANIM-03/ANIM-04 complete in REQUIREMENTS.md from this plan (see key-decisions in frontmatter) -- those requirements' "hardware validation" clauses are only satisfied once 04-06 (Tiles) and 04-07 (Ceiling) actually run this harness against real devices.

## Deviations from Plan

None - plan executed exactly as written. The harness implements every numbered requirement in the plan's `<action>` block (module docstring, argparse contract, device setup with power-on/settle, streaming arm with monotonic-deadline scheduling, ack RTT observer, concurrent single-shot prober, reachability guard, results JSON, fixed exit-code contract, style/import conventions).

## Issues Encountered

- `bandit` (run via `uvx prek run`) flagged the literal `"pass": False` JSON key as `B105:hardcoded_password_string` (a known false positive on the word "pass" as a dict key, not a password) -- resolved with a targeted `# nosec B105` comment, the exact precedent already established in `03-retry-schedule-reshape/uat_zero_loss.py`.
- `prek` was not preinstalled locally; ran via `uvx prek` (project's `.pre-commit-config.yaml` hooks execute the same regardless of which runner invokes them). Confirmed all hooks pass before the commit went through (git's own pre-commit hook fired identically during `git commit -s`).

## User Setup Required

None - no external service configuration required. This plan builds the harness only; plans 04-06/04-07 will need a real Tiles device and a real 13x26 Ceiling device on the local network respectively.

## Next Phase Readiness

- The measurement contract exists on disk, fixed before any hardware run, driving only shipped code paths (`Animator.for_matrix`/`send_frame`, `DeviceConnection`).
- Plan 04-06 (Tiles hardware UAT, ANIM-03) should run:
  ```
  uv run python .planning/phases/04-animation-flow-control/uat_ack_stream.py \
      --ip <tiles-ip> --profile tiles \
      --json-out .planning/phases/04-animation-flow-control/04-06-tiles-RESULTS.json
  ```
- Plan 04-07 (Ceiling hardware UAT, ANIM-04) should run:
  ```
  uv run python .planning/phases/04-animation-flow-control/uat_ack_stream.py \
      --ip <ceiling-ip> --profile ceiling \
      --json-out .planning/phases/04-animation-flow-control/04-07-ceiling-RESULTS.json
  ```
- Both runs need a human visual-smoothness checkpoint alongside these numbers (04-CONTEXT.md) -- the harness never asserts visual quality itself.
- No blockers for plans 04-06/04-07.

---
*Phase: 04-animation-flow-control*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: .planning/phases/04-animation-flow-control/uat_ack_stream.py
- FOUND: 0dee328 (Task 1 commit)
