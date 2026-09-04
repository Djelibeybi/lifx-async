---
phase: 12-ipv6-discovery-plumbing
plan: 03
subsystem: testing
tags: [ipv6, discovery, asyncio, cancellation, concurrency, lifecycle]

requires:
  - phase: 12-01
    provides: family-aware targeted discovery sockets and explicit generator ownership
  - phase: 10-08
    provides: cancellation-safe reusable UDP transport lifecycle
provides:
  - Real-endpoint proof that concurrent public IPv6 targeted lookups remain independent
  - Deterministic post-open cancellation, endpoint cleanup, and immediate reuse evidence
affects: [phase-12-ipv6-discovery-plumbing, phase-13-merged-discovery, find-by-ip]

actuals:
  tokens: 2058
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - Publish one observation record per real discovery transport through a per-test asyncio queue
    - Synchronise cancellation on endpoint-open, receive-started, and close-completed events

key-files:
  created:
    - .planning/phases/12-ipv6-discovery-plumbing/12-03-SUMMARY.md
  modified:
    - tests/test_api/test_ipv6_e2e.py
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Retain the actual discovery transport and endpoint in each observation so independence and closed state are asserted directly rather than inferred from constructor intent."
  - "Signal receive_started immediately before awaiting the real UdpTransport.receive(), then cancel only after that event without sleeps or polling."
  - "Keep concurrency and cancellation/reuse as separate public-API tests so each lifecycle invariant fails independently."

patterns-established:
  - "Lifecycle observation: fresh per-test queues contain per-instance events and real endpoint references, with no module or class mutable registry."
  - "Cancellation proof: wait for the real receive boundary, cancel, assert inner transport closure, then prove a fresh public lookup succeeds."

requirements-completed: [FIND-06]

coverage:
  - id: D1
    description: "Two concurrent public IPv6 targeted lookups use distinct real AF_INET6 transports, endpoints, and ephemeral ports while returning the expected synthetic MatrixLight."
    requirement: FIND-06
    verification:
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py#TestIpv6TargetedDiscoveryLifecycle::test_concurrent_lookups_use_independent_endpoints"
        status: pass
    human_judgment: false
  - id: D2
    description: "Post-open cancellation propagates from the real receive await, closes the retained endpoint, and leaves public IPv6 targeted lookup immediately reusable."
    requirement: FIND-06
    verification:
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py#TestIpv6TargetedDiscoveryLifecycle::test_cancellation_closes_endpoint_and_next_lookup_succeeds"
        status: pass
      - kind: integration
        ref: "uv run pytest tests/test_network/test_transport.py -q -W error::ResourceWarning"
        status: pass
    human_judgment: false

duration: 4 min
completed: 2026-08-29
status: complete
---

# Phase 12 Plan 03: IPv6 Targeted Discovery Lifecycle Summary

**Concurrent and cancelled public IPv6 targeted lookups now have deterministic real-socket evidence for per-call isolation, endpoint cleanup, and immediate path reuse.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-08-29T10:19:42Z
- **Completed:** 2026-08-29T10:23:53Z
- **Tasks:** 2
- **Files modified:** 1 test file, plus this summary and sequential planning state

## Accomplishments

- Proved two explicitly scheduled `find_by_ip("::1")` calls return the expected synthetic `MatrixLight` through distinct real `AF_INET6` discovery transports, endpoints, and ephemeral ports.
- Added per-instance open, receive-started, and close events to the observation-only transport spy while preserving real emulator traffic and production-owned discovery state.
- Proved cancellation occurs only after the real endpoint is open and the real receive is blocked, closes the retained endpoint, propagates `CancelledError`, and permits an immediate fresh public lookup.

## Task Commits

Each task was committed atomically with a GPG signature and DCO sign-off:

1. **Task 1: Prove two IPv6 lookups own independent real endpoints** - `a650cf6` (`test`)
2. **Task 2: Cancel only after blocked receive, prove close, then reuse the path** - `53531dd` (`test`)

The plan metadata is captured by the signed and DCO-compliant commit containing this summary.

## Files Created/Modified

- `tests/test_api/test_ipv6_e2e.py` - Adds the emulator-marked lifecycle class, retained real-transport observations, per-instance events, concurrent endpoint isolation, and cancellation/reuse regressions.
- `.planning/phases/12-ipv6-discovery-plumbing/12-03-SUMMARY.md` - Records implementation, verification, privacy, threat, and close-out evidence.
- `.planning/STATE.md` - Advances sequential execution to Plan 12-04 and records Plan 12-03 metrics and decisions.
- `.planning/ROADMAP.md` - Updates Phase 12 progress to three of four plans complete.

## Decisions Made

- Observation records retain the concrete transport and endpoint because actual OS-managed objects are stronger lifecycle evidence than requested family or bind arguments.
- `receive_started` is set immediately before delegating to the real `UdpTransport.receive()`; the test then waits on that event before cancellation and uses no sleep or polling interval.
- Cancellation cleanup proves the innermost transport context closed the endpoint. The successful-return tests from Plan 12-01 remain the discriminating proof for the two outer `aclosing` owners.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Both tasks add regression evidence for production behaviour completed in Plan 12-01, so their tests passed immediately. No artificial failure or unrelated production change was introduced to manufacture a RED result.
- Focused pytest runs emitted the repository's expected module-not-imported coverage warning for the out-of-scope theme generator. All selected tests passed and `ResourceWarning` remained promoted to an error.
- The managed sandbox could not write the Git index. Approved repository access was used for the required signed and signed-off commits.

## Authentication Gates

None.

## Known Stubs

None. The changed file contains no placeholder branch, skipped test, mock response replacing emulator delivery, or unrun verification.

## Test and Quality Results

- **IPv6 lifecycle E2E:** 2 passed with `ResourceWarning` promoted to an error.
- **UDP transport regression suite:** 57 passed with `ResourceWarning` promoted to an error.
- **Static quality:** Ruff format/check passed; strict Pyright reported 0 errors, 0 warnings, and 0 information messages.
- **Integrity:** `git diff --check` passed; both task commits are GPG-signed by the configured key and carry DCO trailers.

## TDD Gate Compliance

The plan marks both tasks `tdd="true"`, but they are test-only regression tasks for behaviour already shipped by Plan 12-01 and both were green on first execution. Each was committed independently as a test outcome; no false failure or unnecessary production edit was introduced.

## Privacy Boundary

- Tests use only IPv4/IPv6 loopback, ephemeral local ports, and the existing synthetic emulator serial.
- No live serial, MAC address, routable address, hostname, account name, hardware output, raw discovery output, or private mapping was recorded.
- The committed diff was inspected before close-out and no hardware or external-network operation was run.

## Threat Flags

None. This plan adds test-only observation of already planned local UDP lifecycle boundaries and introduces no production endpoint, authentication path, file access, dependency, schema, or trust boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 12-04 can apply the established targeted IPv6 test path to the bounded Windows CI attempt and fixture gate.
- FIND-06 remains shared across Phase 12 and should be marked complete only after every declaring plan has a summary.

## Self-Check: PASSED

- The modified test file and this summary exist on disk.
- Task commits `a650cf6` and `53531dd` exist, have valid signatures from the configured GPG key, and carry DCO sign-off.
- Coverage metadata classifies both deliverables as automatically covered by passing tests, and no tracked file deletion occurred.

---
*Phase: 12-ipv6-discovery-plumbing*
*Completed: 2026-08-29*
