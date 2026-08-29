---
phase: 11-mdns-hardening
plan: 12
subsystem: network
tags: [mdns, diagnostic-probe, deadlines, follow-up-ledger, tdd]

requires:
  - phase: 11-mdns-hardening
    plan: 11
    provides: bounded retained records, exact goodbye lifetime, and usable address selection
provides:
  - Diagnostic-probe parity with production goodbye expiry, PTR retransmission, idle, and overall deadlines
  - Case-insensitive follow-up admission capped at 64 targets with two failed attempts per target
  - Separate attempt and successful-send ledgers with per-target network-failure isolation
  - Deterministic synthetic proof of probe lifetime, traffic, completion, and cleanup semantics
affects: [phase-11-gap-closure, phase-14-thread-validation, mdns-diagnostics]

actuals:
  tokens: 6314
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Probe clock causes run in production order without extending caller-owned deadlines
    - Follow-up attempts consume admission before sending while successful sends are recorded only after transport acceptance
    - Case-folded target identities preserve one work budget across DNS spelling variants

key-files:
  created:
    - .planning/phases/11-mdns-hardening/11-12-SUMMARY.md
  modified:
    - scripts/ipv6_thread_probe.py
    - tests/test_scripts/test_ipv6_thread_probe.py
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Mirror production's literal 64-target and two-attempt bounds in the diagnostic probe without adding public constants or changing production behaviour."
  - "Use separate case-folded attempt and successful-send ledgers so failure consumes retry budget but never suppresses unrelated targets."
  - "Keep probe-parity evidence synthetic; no hardware, multicast listener, broadcast path, or live discovery output is involved."

patterns-established:
  - "Diagnostic parity: operator probes use the same bounded clock and outbound-work semantics as the production path they validate."
  - "Failure isolation: increment an attempt before sending, catch only LifxNetworkError per target, and mark success only after send returns."

requirements-completed: [MDNS-04, MDNS-07]

coverage:
  - id: D1
    description: "The diagnostic sweep expires one-second goodbyes before due retransmissions, honours rescue, clamps receive waits to all four deadlines, resets idle timing after valid packet work, and closes its transport on every terminal path."
    requirement: MDNS-07
    verification:
      - kind: integration
        ref: "tests/test_scripts/test_ipv6_thread_probe.py#TestSweepClockParity"
        status: pass
      - kind: integration
        ref: "Complete diagnostic-probe suite: 64 passed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Follow-up address queries admit at most 64 case-insensitive SRV targets, retry failed sends at most twice, never repeat success, isolate per-target failures, and stop when the cache reports completion."
    requirement: MDNS-04
    verification:
      - kind: integration
        ref: "tests/test_scripts/test_ipv6_thread_probe.py#TestSweepFollowUpLedger: 7 passed"
        status: pass
      - kind: integration
        ref: "Production follow-up parity regressions: 5 passed"
        status: pass
    human_judgment: false
  - id: D3
    description: "The probe changes preserve formatting, typing, signed history, DCO trailers, and the privacy boundary for diagnostic evidence."
    requirement: MDNS-07
    verification:
      - kind: other
        ref: "Scoped Ruff format/check and strict Pyright"
        status: pass
      - kind: other
        ref: "git verify-commit for all four Plan 11-12 task commits"
        status: pass
    human_judgment: false

duration: 38 min
completed: 2026-08-29
status: complete
---

# Phase 11 Plan 12: Diagnostic Probe Lifetime and Follow-up Parity Summary

**The IPv6/Thread diagnostic sweep now matches production mDNS deadline, goodbye, retransmission, and bounded follow-up-query semantics without touching hardware or the broadcast path.**

## Performance

- **Duration:** 38 min across the paused and resumed execution
- **Started:** 2026-08-28T22:26:12Z
- **Completed:** 2026-08-28T23:03:49Z
- **Tasks:** 2
- **Files created/modified:** 2 implementation and test artefacts, plus this summary

## Accomplishments

- Ported production clock ordering into the diagnostic sweep: elapsed goodbye expiry runs before a simultaneous PTR retransmission, and receives wake at the nearest overall, idle, goodbye-expiry, or retransmission deadline.
- Preserved positive-TTL records for the sweep while proving one-second goodbye removal, timely rescue, post-consumer-work idle reset, and transport cleanup on timeout, cancellation, and exception.
- Replaced the probe's unbounded one-shot follow-up set with separate case-folded attempt and successful-send ledgers, capped at 64 admitted targets and two failed attempts each.
- Isolated `LifxNetworkError` to the affected SRV target so one failed query cannot abort the sweep or suppress later targets.

## Task Commits

1. **Task 1: Apply production goodbye, retransmission, and receive-deadline semantics in the probe**
   - `0edb2a9` - `test(mdns): add probe deadline parity regressions`
   - `05c9772` - `fix(mdns): align probe deadline semantics`
2. **Task 2: Enforce the production 64-target and two-attempt follow-up ledger**
   - `7dc80a7` - `test(mdns): cover bounded probe follow-up ledger`
   - `bbdfaa8` - `fix(mdns): bound probe follow-up queries`

The plan metadata is captured by the signed and DCO-compliant commit containing this summary.

## Files Created/Modified

- `scripts/ipv6_thread_probe.py` - Mirrors production lifetime, deadline, retransmission, and bounded follow-up ledger behaviour.
- `tests/test_scripts/test_ipv6_thread_probe.py` - Adds deterministic fake-clock, fake-cache, and fake-transport coverage for both tasks.
- `.planning/phases/11-mdns-hardening/11-12-SUMMARY.md` - Records the TDD sequence, verification evidence, privacy boundary, and close-out state.

## Decisions Made

- The diagnostic probe follows the live production literals rather than introducing shared public limits or changing the private API boundary.
- Target identity is case-folded for both admission and success, while the original SRV-owned spelling is used to build the outbound query.
- A failed send increments its target's attempt count and consumes one of the 64 admission slots; a successful send is recorded separately and is never repeated.
- Probe validation remains entirely synthetic. The live probe, hardware, multicast membership, and Phase 10 broadcast schedule are outside this plan.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first Task 2 executor stalled twice without a fresh file update or commit. The structured handoff preserved its 207-line test draft; execution resumed inline, confirmed the intended RED failures, and completed without replaying Task 1.
- Focused pytest invocations emitted the repository's expected module-not-imported coverage warning because the theme generator is outside the selected test population. `ResourceWarning` was promoted to an error as required and none occurred.
- The managed sandbox could not access the Git index or GPG trust database. Approved repository access was used for staging and signature verification; all four task commits verified successfully.
- Commit hooks temporarily stashed the session-continuity edit and restored it after each task commit, keeping task commits atomic.

## Authentication Gates

None.

## Known Stubs

None. No skipped test, placeholder ledger, hardware dependency, background listener, or unfinished production path remains.

## Test and Quality Results

- **Task 2 RED:** 5 intended failures and 2 compatibility passes across 7 selected follow-up tests.
- **Task 2 GREEN:** 7 passed after the bounded attempt/success ledger implementation.
- **Complete diagnostic probe:** 64 passed with `ResourceWarning` promoted to an error.
- **Production parity controls:** 5 passed for the live 64-target, retry, success, and failure-isolation behaviours.
- **Static quality:** Ruff format/check passed; strict Pyright reported 0 errors, 0 warnings, and 0 information messages.
- **Integrity:** `git diff --check` passed, and all four Plan 11-12 task commits have valid cryptographic signatures, DCO trailers, and plan-correlation lines.

## TDD Gate Compliance

- Task 1 RED `0edb2a9` precedes GREEN `05c9772`.
- Task 2 RED `7dc80a7` precedes GREEN `bbdfaa8`.
- Task 2's preserved draft was run before any production edit and failed only for the missing failure isolation, retry, cap, and case-folded success behaviours.

## Privacy Boundary

- Every new hostname, address, serial-shaped value, packet token, and failure is explicitly synthetic; network literals use documentation or non-live test ranges.
- No live serial, MAC address, IP address, hostname, account name, hardware output, raw packet, or external identity mapping was recorded.
- No live probe or hardware operation was run during Plan 11-12.

## Threat Flags

None. The planned denial-of-service and stale-cache threats are closed by deadline clamping, bounded work ledgers, failure isolation, and deterministic lifetime tests; no new dependency, endpoint, public API, or trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-12 closes the diagnostic-probe parity warnings and leaves Phase 11 ready for Plan 11-13's repository-instruction and static-scan corrections.
- MDNS-04 and MDNS-07 are complete for this gap run.
- Plan 11-14 retains ownership of final changed-line coverage, full-suite, privacy, and phase verification gates.

## Self-Check: PASSED

- Both planned implementation and test artefacts exist and the complete probe suite is green.
- Task commits `0edb2a9`, `05c9772`, `7dc80a7`, and `bbdfaa8` exist in the required RED/GREEN order and verify cryptographically.
- The plan diff passes formatting, typing, privacy, and whitespace checks before metadata close-out.

---
*Phase: 11-mdns-hardening*
*Completed: 2026-08-29*
