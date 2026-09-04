---
phase: 10-land-the-ipv6-thread-branch
plan: 09
subsystem: network
tags: [ipv6, asyncio, lifecycle, concurrency, specification, gap-closure]
requires:
  - phase: 10-08
    provides: cancellation-safe transport cleanup
provides:
  - atomic mDNS and UDP endpoint publication under concurrent lifecycle operations
  - close-wins invalidation for endpoints completing after close returns
  - retrying DeviceConnection open waiters after opener failure
  - corrected Phase 10 shipment, coverage and UAT acceptance contract
affects: [11-mdns-hardening, 12-ipv6-discovery-plumbing, 13-merged-discovery]
key-files:
  modified:
    - src/lifx/network/mdns/transport.py
    - src/lifx/network/transport.py
    - src/lifx/network/connection.py
    - tests/test_network/test_mdns/test_transport.py
    - tests/test_network/test_transport.py
    - tests/test_network/test_connection.py
    - .planning/phases/10-land-the-ipv6-thread-branch/10-SPEC.md
key-decisions:
  - "Endpoint fields become observable only after complete setup; is_open requires the complete state tuple."
  - "close increments a generation so any suspended open that completes later closes its endpoint without publishing it."
  - "DeviceConnection keeps its loop-agnostic opener flag but waiters retry the decision instead of returning after failure."
  - "D-26 to D-29 supersede the premature-main, functional-coverage and restoration gates."
requirements-completed: [IPV6-01, IPV6-02, IPV6-03, IPV6-04]
duration: 25 min
completed: 2026-08-28
status: complete
commits:
  - e31185c07476807768043343f3af7c70bfd16710
---

# Phase 10 Plan 09: Operator-directed gap closure summary

Phase 10 now has a coherent shipment contract and deterministic transport lifecycle behaviour.
The accepted tree remains on `gsd/phase-10-land-the-ipv6-thread-branch`; D-26 explicitly forbids
merging it to `main` before the phase shipment workflow.

## What changed

- Rewrote the SPEC and roadmap so Phase 10 proves a branch ready to ship. Main ancestry is a
  post-phase shipment action, patch coverage is advisory/operator-overridable, and UAT restoration
  is best-effort.
- Made `MdnsTransport` and `UdpTransport` serialise open attempts, retain setup state locally,
  publish only complete endpoints and discard a late endpoint after a racing close.
- Made `DeviceConnection.open()` waiters re-check and retry after opener failure, with failed
  transport cleanup before the original exception propagates.
- Added event-controlled regressions for successful open/close races and the failed-opener waiter.

## Verification

- Focused network lifecycle suite: 146 passed.
- Full frozen suite: 3,731 passed, 12 deselected.
- Ruff: passed.
- Pyright: 0 errors, 0 warnings.
- Strict mDNS resource test: 33 passed with ResourceWarning and unraisable warnings treated as
  errors.
- `git merge-base --is-ancestor HEAD main`: exit 1, the required pre-shipment branch state.

No dependency, reliability constant, recorded UAT result or coverage configuration changed.
