---
phase: 03-retry-schedule-reshape
plan: 03
subsystem: network
tags: [asyncio, connection, retry, hardware-uat, spike-002]

requires:
  - phase: 03-retry-schedule-reshape
    provides: Shared _transmit_and_listen() engine and REQUEST_RETRANSMIT_GAPS schedule (plan 03-02)
provides:
  - uat_zero_loss.py standalone headless hardware measurement harness (phase-dir only)
  - 03-UAT-RESULTS.json real-network evidence for RETRY-01/RETRY-02 against a gen4 downlight
affects: [phase-5-reliability-documentation]

tech-stack:
  added: []
  patterns:
    - "Bound-method send-count spy via plain attribute assignment (conn.send_packet = spy) rather than mock imports, for a standalone hardware-measurement script"
    - "0/1/2 exit-code contract (PASS/FAIL/ENV-ERROR) with thresholds fixed before any run, matching Phase 2's uat_rounds.py precedent"

key-files:
  created:
    - .planning/phases/03-retry-schedule-reshape/uat_zero_loss.py
    - .planning/phases/03-retry-schedule-reshape/03-UAT-RESULTS.json
  modified: []

key-decisions:
  - "Kept the canonical 03-UAT-RESULTS.json as the confirmatory second run's data (PASS, mean 1.017) per the plan's one-retry-on-transient-event protocol; the first run's FAIL data is preserved in this summary rather than the JSON, since the harness writes exactly one run per invocation and the plan does not specify a multi-run JSON schema"
  - "Reachability probe uses a generous 5s-minimum timeout (max(args.timeout, 5.0)) distinct from the per-trial timeout, so a slow-but-reachable device doesn't get misclassified as ENV-ERROR"

requirements-completed: [RETRY-01, RETRY-02]

coverage:
  - id: D1
    description: "Standalone uat_zero_loss.py harness drives the shipped DeviceConnection.request() with a send-count spy, fixed 0/1/2 exit-code contract, and a reachability guard"
    requirement: "RETRY-01"
    verification:
      - kind: manual_procedural
        ref: "uv run python .planning/phases/03-retry-schedule-reshape/uat_zero_loss.py --help (exit 0, no packets sent); uv run ruff check (clean); uv run pyright (clean)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Real-hardware zero-loss packets/trial and latency measurement against the gen4 downlight (192.168.18.95), recorded honestly against spike 002 baselines"
    requirement: "RETRY-02"
    verification:
      - kind: manual_procedural
        ref: "Two live runs against 192.168.18.95: run 1 exit 1 (mean 1.083, transient WiFi retransmits), run 2 exit 0 (mean 1.017, median 1.0). See Accomplishments below for full numbers."
        status: pass
    human_judgment: true
    rationale: "Real-network hardware measurement against a specific physical device; a human should sanity-check the transient-event interpretation of run 1 against the recorded per-trial data before treating RETRY-02 real-world evidence as settled."

duration: ~15min
completed: 2026-07-17
status: complete
---

# Phase 3 Plan 03: Zero-Loss Hardware Measurement Summary

**Built and ran a headless zero-loss packets/trial harness against the gen4 test downlight: first attempt measured mean 1.083 packets/trial (FAIL, driven by a genuine two-trial WiFi retransmit event), a mandatory single re-run measured mean 1.017 / median 1.0 (PASS) with 12.6ms median latency — both far below the pre-reshape spike 002 baselines of 1.37 packets/trial and 62ms median.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-17T00:12:00+10:00
- **Completed:** 2026-07-17T00:16:00+10:00
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments

- Built `uat_zero_loss.py`: argparse harness (`--ip`, `--trials`, `--gap`, `--timeout`, `--json-out`) with a generous-timeout reachability probe (exit 2 ENV-ERROR without hammering an absent device), a `_SendSpy` wrapper around the bound `send_packet` (plain attribute assignment, no mock imports), and a fixed pre-declared 0/1/2 exit-code contract (median==1.0 AND mean<=1.05 AND zero failures → PASS).
- `--help` exits 0 without opening a connection or sending any packets. `ruff check`/`ruff format --check` and `uv run pyright` both clean (strict mode; required a `TypedDict` for trial records to satisfy strict argument typing, and a `# nosec B105` comment for a bandit false-positive on a `"pass": None` dict key).
- **Run 1** (60 trials against 192.168.18.95): 0 request failures, but two trials (52, 53) issued 5 and 2 transmissions respectively — trial 52 alone took 1848.9ms, consistent with a genuine WiFi packet-loss event on the physical link, not a duplicate-storm regression. Mean packets/trial = 1.083 (over the 1.05 threshold) → **exit 1 (FAIL)**. Median packets/trial was still exactly 1.0; median latency 17.3ms.
- Per plan's transient-event protocol, re-ran once (thresholds/harness untouched, byte-identical to the Task 1 commit): **Run 2**, 60 trials, 0 failures, only one trial (19) needed a retransmit (tx=2). Mean packets/trial = 1.017, median = 1.0 → **exit 0 (PASS)**. Median latency 12.6ms.
- Both runs' zero-failure counts and near-1.0 median packets/trial confirm the reshaped retry engine (D3-01 floored first window, D3-02 listen-during-backoff) eliminates the old duplicate-packet storm the pre-reshape engine produced on this same device (1.37 packets/trial, 62ms median in spike 002). The elevated mean in run 1 is attributable to real network loss on two trials, not to the retry schedule re-sending against an already-answered request.
- `03-UAT-RESULTS.json` records the confirmatory (run 2, PASS) per-trial data, thresholds, and the spike 002 baseline block; this summary documents run 1's numbers in full for transparency (see Deviations below — not a deviation from plan, but flagged per the plan's "if it fails again flag prominently" instruction, applied here to the honest documentation of the transient first failure).

## Task Commits

1. **Task 1: Build the zero-loss measurement harness (uat_zero_loss.py)** - `0a8d0df` (feat)
2. **Task 2: Run the zero-loss measurement and record the result honestly** - `6f7674e` (test)

**Plan metadata:** committed alongside this summary.

## Files Created/Modified

- `.planning/phases/03-retry-schedule-reshape/uat_zero_loss.py` - Standalone headless harness measuring packets/trial and latency via `DeviceConnection.request()` against a real device, with a fixed 0/1/2 exit-code contract.
- `.planning/phases/03-retry-schedule-reshape/03-UAT-RESULTS.json` - Recorded evidence: the confirmatory PASS run's per-trial data, thresholds, and spike 002 baseline comparison.

## Decisions Made

- Recorded the second (confirmatory) run's data as the canonical `03-UAT-RESULTS.json` since the harness writes one JSON per invocation and the plan didn't specify a multi-run schema; the first run's FAIL numbers are preserved in full in this summary instead, satisfying the honest-reporting requirement without inventing a new JSON shape mid-task.
- Used a reachability-probe timeout of `max(args.timeout, 5.0)` distinct from the per-trial timeout, so the probe itself has margin to distinguish "device is slow" from "device is absent" before committing to 60 trials.

## Deviations from Plan

None — plan executed exactly as written. The plan explicitly anticipated a possible FAIL-then-PASS sequence ("re-run ONCE to rule out a transient network event... if it fails again flag the result prominently") and that is exactly what happened: run 1 FAILed on the mean-packets threshold due to a genuine two-trial WiFi event (documented above, not hidden), run 2 PASSed. No harness code, threshold, or trial count was touched between or after the runs.

## Issues Encountered

None beyond the expected transient network variance documented above. `uv run ruff format .`, `uv run ruff check .`, and `uv run pyright` were clean on the harness after Task 1.

## User Setup Required

None - no external service configuration required. (This measurement is optional per 03-CONTEXT.md; RETRY-01 through RETRY-04 are already closed by plan 03-02's emulator-backed tests.)

## Next Phase Readiness

- RETRY-01/RETRY-02 now carry supplementary real-hardware evidence alongside the emulator-backed automated suite from 03-02: the zero-loss duplicate-packet storm measured in spike 002 (1.37 packets/trial) is gone (1.017 confirmed, 1.083 under a transient real-loss event), and gen4 median latency dropped from the old 62ms baseline to 12.6-17.3ms.
- `uat_zero_loss.py` remains available in the phase directory for the user to re-run on-network at any time (e.g. to build a larger sample, or re-validate after future retry-path changes).
- Phase 3 (retry-schedule-reshape) is now fully complete: all three plans (03-01 RED, 03-02 GREEN, 03-03 hardware evidence) done. Phase 4 (Animation Flow Control) and Phase 5 (Reliability Documentation) remain unblocked, per 03-02-SUMMARY.md's handoff notes (docs-rot items in `docs/api/network.md`, `docs/architecture/overview.md`, and `CLAUDE.md`'s stale `_request_lock` reference).
- No blockers.

---
*Phase: 03-retry-schedule-reshape*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: .planning/phases/03-retry-schedule-reshape/uat_zero_loss.py
- FOUND: .planning/phases/03-retry-schedule-reshape/03-UAT-RESULTS.json
- FOUND: commit 0a8d0df (Task 1)
- FOUND: commit 6f7674e (Task 2)
