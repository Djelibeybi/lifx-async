---
phase: 10-land-the-ipv6-thread-branch
plan: 08
subsystem: network
tags: [ipv6, mdns, udp, asyncio, cancellation, resource-lifecycle]

requires:
  - phase: 10-07
    provides: "the immutable pre-gap base and deterministic changed-line/branch coverage gate"
  - phase: 10-03
    provides: "the original mDNS OSError cleanup, real-socket ledger, and endpoint-lifecycle regressions"
provides:
  - "cancellation-safe, reopenable mDNS endpoint creation with serialised concurrent opens"
  - "reusable UdpTransport state after cancellation, OSError, and other interrupted opens"
  - "fresh immutable-base evidence for every changed transport line and branch"
affects: [11-mdns-hardening, 12-ipv6-discovery-plumbing, 13-merged-discovery]

actuals:
  tokens: 5685
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Catch BaseException only at an owned-resource boundary, clean up first, wrap OSError alone, and re-raise every other exception unchanged"
    - "Serialise concurrent open attempts while leaving close non-blocking so cancellation can resolve a close-racing-open schedule"

key-files:
  created:
    - .planning/phases/10-land-the-ipv6-thread-branch/10-08-SUMMARY.md
  modified:
    - src/lifx/network/mdns/transport.py
    - tests/test_network/test_mdns/test_transport.py
    - src/lifx/network/transport.py
    - tests/test_network/test_transport.py

key-decisions:
  - "MdnsTransport serialises open() calls with an asyncio.Lock so a concurrent opener waits for cancellation cleanup and then establishes the replacement endpoint"
  - "MdnsTransport.close() remains outside that lock: a close started while endpoint creation is suspended must return, allowing cancellation to perform the authoritative cleanup without deadlock"
  - "Both transports wrap only OSError as LifxNetworkError; CancelledError and representative non-OSError failures are cleaned up and re-raised with their original identity"

patterns-established:
  - "Closed-state invariant: every unsuccessful open clears all fields that is_open or send can observe"
  - "Cancellation evidence: asyncio.Event controls the await boundary and real socket ledgers prove descriptor ownership, with no timing sleeps"

requirements-completed: [IPV6-01, IPV6-04]

coverage:
  - id: D1
    description: "MdnsTransport cancellation closes its owned socket, clears all state, preserves CancelledError, and permits reuse"
    requirement: IPV6-04
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_transport.py::TestMdnsTransportOpenFailureIsClean"
        status: pass
      - kind: integration
        ref: "uv run --frozen pytest tests/test_network/test_mdns/test_transport.py -q -W error::ResourceWarning"
        status: pass
    human_judgment: false
  - id: D2
    description: "Concurrent mDNS open and close-racing-open cancellation schedules leave balanced descriptors and allow a later endpoint"
    requirement: IPV6-04
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_transport.py::TestMdnsTransportOpenConcurrency"
        status: pass
    human_judgment: false
  - id: D3
    description: "UdpTransport cancellation and setup failure restore protocol, transport, and family to one reusable closed state"
    requirement: IPV6-01
    verification:
      - kind: unit
        ref: "tests/test_network/test_transport.py::TestErrorHandling"
        status: pass
      - kind: integration
        ref: "tests/test_network/test_transport.py::TestEndpointLoss, TestSocketFamilySelection, and TestSendFamilyAssertion"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every executable source line and branch changed from the immutable gap base is covered without weakening tests or scope fences"
    verification:
      - kind: other
        ref: "scripts/check_patch_coverage.py: 39 changed executable lines and 10 changed branches passed"
        status: pass
      - kind: integration
        ref: "uv run --frozen pytest -q: 3728 passed, 12 deselected"
        status: pass
    human_judgment: false

duration: 10 min
completed: 2026-08-28
status: complete
---

# Phase 10 Plan 08: Transport Cancellation Gap Closure Summary

**Cancellation-safe mDNS and UDP endpoint creation now restores coherent closed state, releases owned resources, preserves exception semantics, and remains reusable across IPv4 and IPv6 paths.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-08-27T22:31:15Z
- **Completed:** 2026-08-27T22:40:56Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Closed the cancellation half of Phase 10 success criterion 4 with real-descriptor evidence, unchanged `CancelledError` propagation, three coherent internal references, and successful reuse.
- Serialised concurrent mDNS opens so a second caller cannot return from transient `_protocol` state; deterministic concurrent-open and close-racing-open schedules now balance the socket ledger.
- Restored `UdpTransport` after cancellation, endpoint `OSError`, representative non-`OSError`, and post-assignment setup failure while retaining IPv4, IPv6, zoned-link-local, send-family, and peer-error behaviour.
- Proved the combined 10-07/10-08 gap patch has 39 covered changed executable lines and 10 covered changed branches, with no dependency, coverage target, reliability constant, Thread UAT, skipped test, deleted test, or coverage exemption changed.

## Task Commits

Each task was committed atomically with GPG signature and DCO sign-off:

1. **Task 1: Make mDNS endpoint creation cancellation-safe and reopenable** - `bf83941` (fix)
2. **Task 2: Restore UdpTransport to a reusable closed state after interrupted open** - `c20d8c9` (fix)

## Files Created/Modified

- `src/lifx/network/mdns/transport.py` - Serialised open lifecycle and BaseException-safe owned-socket cleanup.
- `tests/test_network/test_mdns/test_transport.py` - Real-socket cancellation, concurrent-open, racing-close, exception-identity, and reuse regressions.
- `src/lifx/network/transport.py` - Three-field reset and assigned-endpoint closure for every unsuccessful open.
- `tests/test_network/test_transport.py` - Deterministic cancellation, OSError reuse, post-assignment cleanup, and non-OSError identity regressions.

## Decisions Made

The mDNS lock covers `open()` only. Extending it across `close()` deadlocked the existing SPEC R4 schedule where close is deliberately invoked while endpoint creation is suspended; leaving close non-blocking lets it observe no established endpoint, after which cancellation performs the single authoritative cleanup. Concurrent openers still wait behind the lock and retry against the cleaned state.

Both failure paths catch `BaseException` narrowly around endpoint setup because `asyncio.CancelledError` does not derive from `Exception`. Cleanup happens before exception classification: `OSError` retains the public `LifxNetworkError` wrapper, while cancellation and other failures are re-raised unchanged.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first lock placement also covered `MdnsTransport.close()`, which deadlocked the existing close-racing-open backstop. The lock was narrowed to `open()` before Task 1 was committed; all three cancellation schedules then passed deterministically.
- The default uv cache was outside the writable execution sandbox. Verification used `UV_CACHE_DIR=/private/tmp/lifx-async-uv-cache`; dependency resolution and the committed lockfile remained unchanged.

## Known Stubs

None.

## Threat Flags

None. The plan's existing cancellation and asyncio endpoint trust boundaries were hardened; no new network endpoint, authentication path, file-access pattern, dependency, or schema boundary was introduced.

## Verification Record

| Check | Result |
|---|---|
| Focused mDNS and UDP transport suites | 95 passed; 7 existing deprecation warnings; ResourceWarning promoted to error |
| Full repository suite | 3,728 passed, 12 deselected, 7 existing deprecation warnings |
| IPv6 must-not-skip emulator gate | 10 passed with `LIFX_REQUIRE_IPV6=1` |
| Ruff check and format | passed |
| Pyright | 0 errors, 0 warnings, 0 information messages |
| Immutable-base patch coverage | 39 changed executable lines, 10 changed branches, all covered |
| Coverage-checker regression pins | 11 passed |
| Weakening-only scan | passed |
| Protected-file and deleted-test prohibitions | passed |
| Task commit signatures and DCO trailers | both passed |

API-coverage verification uses the phase's reasoned declaration in `COVERAGE.md`: these local UDP and mDNS lifecycle changes integrate no external API, SDK, or service. Assumption-delta matches on incidental wording do not alter the library's core identity or phase boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 10's three code-review gaps are closed. Phases 11 and 12 can proceed from transport wrappers whose cancellation, resource ownership, address-family selection, and reuse invariants are now fully regression-tested.

## Self-Check: PASSED

- All four implementation files exist.
- Task commits `bf83941` and `c20d8c9` exist, are GPG-valid, and carry DCO sign-off.
- Every plan verification and prohibition command passed against committed `HEAD`.
- No generated or unrelated file remains untracked.

---
*Phase: 10-land-the-ipv6-thread-branch*
*Completed: 2026-08-28*
