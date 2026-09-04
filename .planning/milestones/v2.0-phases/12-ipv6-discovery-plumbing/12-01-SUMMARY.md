---
phase: 12-ipv6-discovery-plumbing
plan: 01
subsystem: network
tags: [ipv6, discovery, asyncio, udp, emulator, generator-ownership]

requires:
  - phase: 10-land-the-ipv6-thread-branch
    provides: validated address-family helpers, IPv6 transport support, and the loopback IPv6 emulator
provides:
  - Family-aware targeted discovery sockets for validated IPv4 and IPv6 literals
  - Deterministic nested async-generator finalisation before find_by_ip returns
  - Real-socket emulator regressions for both targeted-discovery family arms
affects: [phase-12-ipv6-discovery-plumbing, phase-13-merged-discovery, find-by-ip]

actuals:
  tokens: 3607
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - Derive the discovery wildcard and IPv4-only broadcast flag from the validated destination family
    - Own every early-exit async-generator layer with contextlib.aclosing
    - Observe the actual asyncio datagram socket while preserving real packet delivery

key-files:
  created:
    - .planning/phases/12-ipv6-discovery-plumbing/12-01-SUMMARY.md
  modified:
    - src/lifx/api.py
    - src/lifx/network/discovery.py
    - src/lifx/network/transport.py
    - tests/test_api/test_ipv6_e2e.py
    - tests/test_network/test_discovery_devices.py
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Select the local wildcard and broadcast capability together from the validated target family; IPv4 keeps broadcast enabled while IPv6 does not request the inapplicable socket option."
  - "Close both find_by_ip's discover_devices generator and discover_devices' packet-response generator explicitly with contextlib.aclosing before returning a device."
  - "Prove socket-family behaviour from the actual endpoint and keep observation state local to each test without replacing real emulator traffic."

patterns-established:
  - "Targeted discovery: the validated destination literal is the single source for both the local wildcard bind and socket-family-specific broadcast capability."
  - "Early async-generator return: every owning layer uses aclosing so nested transport cleanup completes synchronously."

requirements-completed: [FIND-06]

coverage:
  - id: D1
    description: "Public find_by_ip resolves the synthetic IPv6 emulator device through an actual AF_INET6 discovery endpoint bound to the IPv6 wildcard, then closes both generator ownership layers before return."
    requirement: FIND-06
    verification:
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py#TestIpv6TargetedDiscovery::test_find_by_ip_over_ipv6"
        status: pass
      - kind: integration
        ref: "tests/test_network/test_discovery_devices.py#TestDiscoveryGeneratorOwnership::test_close_synchronously_finalises_packet_discovery"
        status: pass
    human_judgment: false
  - id: D2
    description: "Public IPv4 targeted discovery retains its AF_INET wildcard bind, broadcast capability, exact destination, emulator-backed device construction, and synchronous endpoint cleanup."
    requirement: FIND-06
    verification:
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py#TestIpv6TargetedDiscovery::test_find_by_ip_over_ipv4"
        status: pass
    human_judgment: false
  - id: D3
    description: "The address-family change preserves discovery retransmission, validation, timeout, deduplication, formatting, lint, and strict typing invariants."
    requirement: FIND-06
    verification:
      - kind: integration
        ref: "tests/test_network/test_discovery_rebroadcast.py and tests/test_network/test_discovery_errors.py: 33 passed"
        status: pass
      - kind: other
        ref: "Scoped Ruff format/check and strict Pyright"
        status: pass
    human_judgment: false

duration: 17 min
completed: 2026-08-29
status: complete
---

# Phase 12 Plan 01: Family-aware Targeted Discovery Summary

**Public IPv4 and IPv6 targeted lookups now select, exercise, and synchronously close the correct real UDP discovery endpoint while preserving the established discovery loop.**

## Performance

- **Duration:** 17 min across the paused and resumed execution
- **Started:** 2026-08-29T09:39:18Z
- **Completed:** 2026-08-29T09:56:00Z
- **Tasks:** 2
- **Files created/modified:** 5 implementation and test artefacts, plus this summary and sequential tracking files

## Accomplishments

- Made `_discover_with_packet()` bind to the family-appropriate wildcard and retain broadcast mode only for IPv4, without changing the invariant-bearing receive and retransmission loop.
- Made `find_by_ip()` and `discover_devices()` explicitly close their owned async generators so a successful early return completes endpoint cleanup before the caller receives the device.
- Proved real emulator-backed IPv6 and IPv4 targeted lookups from the public API through device construction, using the actual endpoint socket family, wildcard bind, destination, broadcast flag, and close state.

## Task Commits

1. **Task 1: Trace public IPv6 lookup through a real family-aware discovery socket**
   - `943bb5e` - `test: add failing IPv6 targeted discovery regressions`
   - `83da3fe` - `feat: make targeted discovery address-family aware`
2. **Task 2: Pin the IPv4 half of the family-selection contract**
   - `0a94c0a` - `test: pin IPv4 targeted discovery socket contract`

The plan metadata is captured by the signed and DCO-compliant commit containing this summary.

## Files Created/Modified

- `src/lifx/api.py` - Owns and closes the targeted `discover_devices()` generator and documents validated IPv4, IPv6, and zoned link-local literals.
- `src/lifx/network/discovery.py` - Selects the family-appropriate wildcard and broadcast flag, and owns the inner packet-response generator.
- `src/lifx/network/transport.py` - Corrects the endpoint-loss comment for family-appropriate wildcard binds without exposing bind values.
- `tests/test_api/test_ipv6_e2e.py` - Observes real targeted-discovery sockets and proves both public IPv6 and IPv4 lookup arms.
- `tests/test_network/test_discovery_devices.py` - Proves closing `discover_devices()` synchronously finalises its inner packet-discovery generator.
- `.planning/phases/12-ipv6-discovery-plumbing/12-01-SUMMARY.md` - Records execution, verification, privacy, threat, and close-out evidence.

## Decisions Made

- Reused `family_for()` and `wildcard_for()` as the single family-selection rule and derived IPv4-only broadcast capability at the same construction seam.
- Followed the existing `discover_mdns()` ownership pattern with `contextlib.aclosing` at both targeted-discovery generator layers, preserving Python 3.10 support.
- Patched only the transport imported by `lifx.network.discovery`; device capability detection and packet delivery remained real.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The managed shell did not expose the existing `uv` binary and its default cache was outside the writable sandbox. Verification used the existing binary with a task-specific writable `UV_CACHE_DIR`; no dependency or lock file changed.
- The managed sandbox could not write the Git index. Approved repository access was used for the signed Task 2 and metadata commits.
- Task 2 intentionally pins preserved IPv4 behaviour, so its new regression was green immediately against Task 1's production commit. No artificial production change was introduced to manufacture a RED result.
- Focused pytest runs emitted the repository's expected module-not-imported coverage warning because the theme generator is outside the selected test population. `ResourceWarning` was promoted to an error where required and none occurred.

## Authentication Gates

None.

## Known Stubs

None. No placeholder data source, skipped test, unfinished branch, or unrun verification remains in the plan diff.

## Test and Quality Results

- **Targeted family E2E:** 2 passed with `ResourceWarning` promoted to an error.
- **Nested generator ownership:** 1 passed with `ResourceWarning` promoted to an error.
- **Discovery invariants:** 33 passed across the unchanged rebroadcast and error suites.
- **Static quality:** Ruff format/check passed; strict Pyright reported 0 errors, 0 warnings, and 0 information messages.
- **Integrity:** `git diff --check` passed; all three task commits contain GPG signatures and DCO trailers.

## TDD Gate Compliance

- Task 1 RED `943bb5e` precedes GREEN `83da3fe` and the approved tracer was re-run successfully before Task 2.
- Task 2 is regression-only coverage for behaviour the plan explicitly requires to remain unchanged. Its test passed immediately against the Task 1 production tree and was committed independently as `0a94c0a`; no false failure was introduced.

## Privacy Boundary

- Tests use only the existing synthetic serial fixtures and IPv4/IPv6 loopback addresses.
- No live serial, MAC address, IP address, hostname, account name, hardware output, raw discovery output, or private mapping was recorded.
- The staged and committed diff was inspected before close-out; no hardware or live-network operation was run.

## Threat Flags

None. The planned spoofing and denial-of-service mitigations remain covered by the unchanged validation, timeout, retransmission, UDP-service, and first-wins invariant suites; no unplanned endpoint, dependency, public API, persistence field, or trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 12-01 establishes the public-to-socket vertical slice required by the remaining Phase 12 representation, lifecycle, concurrency, fixture, and CI plans.
- FIND-06 is delivered by this plan; phase-level acceptance remains open until Plans 12-02 through 12-04 complete their broader proof and Windows evidence.
- Plan 12-02 can extend the proven family-selection seam without changing the discovery timing loop.

## Self-Check: PASSED

- All five planned implementation and test artefacts plus this summary exist on disk.
- Task commits `943bb5e`, `83da3fe`, and `0a94c0a` exist in order, contain GPG signatures and DCO trailers, and no tracked file deletion occurred.
- Coverage metadata classifies all three deliverables as automatically covered by passing evidence; the final diff passes whitespace, privacy, formatting, lint, typing, and threat-surface checks.

---
*Phase: 12-ipv6-discovery-plumbing*
*Completed: 2026-08-29*
