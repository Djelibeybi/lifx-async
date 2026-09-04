---
phase: 12-ipv6-discovery-plumbing
plan: 05
subsystem: network
tags: [ipv6, udp, scope-id, discovery, ci]

requires:
  - phase: 12-02
    provides: Public IPv6 representation and validation coverage
  - phase: 12-03
    provides: Real-endpoint lifecycle, cancellation, and concurrency coverage
  - phase: 12-04
    provides: Windows and Ubuntu targeted IPv6 CI path and canonical IPv6 sockaddr baseline
provides:
  - Scope-preserving numeric and named IPv6 datagram destinations at the production send boundary
  - Immediate typed failures for unknown named and out-of-range numeric IPv6 zones
  - Exact current-revision Windows and Ubuntu evidence for the repaired scope contract
affects: [phase-13-merged-discovery, find-by-ip, udp-transport]

actuals:
  tokens: 1497
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - Resolve IPv6 zone suffixes only at the UDP send boundary and pass scope in the native sockaddr field
    - Translate permanent zone-resolution failures before datagram send or discovery timeout handling

key-files:
  created:
    - .planning/phases/12-ipv6-discovery-plumbing/12-05-SUMMARY.md
  modified:
    - src/lifx/network/transport.py
    - tests/test_network/test_transport.py

key-decisions:
  - "Convert numeric IPv6 zones directly and resolve named zones with socket.if_nametoindex(), while stripping the suffix from the host passed to sendto."
  - "Translate invalid IPv6 zone resolution and range failures to LifxNetworkError before sendto without closing the reusable endpoint."
  - "Accept only exact current-revision named-job evidence for the Windows and Ubuntu compatibility gate."

patterns-established:
  - "Scoped IPv6 send conversion: `(host%zone, port)` becomes `(host, port, 0, scope_id)` immediately before datagram send."
  - "Permanent address configuration errors fail before network retry or receive deadlines begin."

requirements-completed: [FIND-06]

coverage:
  - id: D1
    description: "Numeric and named IPv6 zones cross the real UDP send boundary in the native scope field."
    requirement: FIND-06
    verification:
      - kind: integration
        ref: "tests/test_network/test_transport.py#TestSendFamilyAssertion numeric and named zoned IPv6 cases"
        status: pass
    human_judgment: false
  - id: D2
    description: "Unknown named and out-of-range numeric zones fail immediately with LifxNetworkError before sendto and leave the endpoint reusable."
    requirement: FIND-06
    verification:
      - kind: unit
        ref: "tests/test_network/test_transport.py#TestSendFamilyAssertion invalid zone cases"
        status: pass
    human_judgment: false
  - id: D3
    description: "The complete focused and frozen local suites plus Ruff and Pyright pass on the repaired tree."
    requirement: FIND-06
    verification:
      - kind: integration
        ref: "Phase 12 Plan 12-05 local closure command"
        status: pass
    human_judgment: false
  - id: D4
    description: "The exact gap revision passes the required Windows focused tracer and Ubuntu full-suite IPv6 evidence gates."
    requirement: FIND-06
    verification:
      - kind: e2e
        ref: "GitHub Actions PR #219 exact-revision Windows/Python 3.10 and Ubuntu/Python 3.10 jobs"
        status: pass
    human_judgment: false

duration: 32 min
completed: 2026-08-29
status: complete
---

# Phase 12 Plan 05: IPv6 Scope Preservation Gap Closure Summary

**Numeric and named IPv6 zones now survive the real UDP send conversion, while invalid zones fail immediately with a typed network error and current-revision Windows and Ubuntu jobs prove the repaired path.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-08-29T12:18:00Z
- **Completed:** 2026-08-29T12:50:00Z
- **Tasks:** 3
- **Files modified:** 2 implementation and test files, plus this summary and sequential planning state

## Accomplishments

- Preserved numeric and named IPv6 zone information as the native `scope_id` in the canonical four-field destination passed to the real datagram endpoint.
- Added immediate `LifxNetworkError` handling for unknown named zones and numeric scopes outside the unsigned 32-bit range, before `sendto` and without invalidating the open endpoint.
- Passed the focused Phase 12 regressions, the 4,031-test frozen local suite, Ruff format/lint, strict Pyright, diff and privacy checks, plus exact current-revision Windows and Ubuntu CI evidence.

## Task Commits

The two TDD implementation tasks were committed with separate RED and GREEN gates:

1. **Task 1 RED: Expose IPv6 send scope loss** - `0b3cd54` (`test`)
2. **Task 1 GREEN: Preserve IPv6 scope identifiers** - `5aeb11e` (`feat`)
3. **Task 2 RED: Add invalid IPv6 zone regressions** - `be89748` (`test`)
4. **Task 2 GREEN: Fail invalid IPv6 zones before send** - `9dc4d79` (`fix`)
5. **Task 3: Confirm current-revision Windows and Ubuntu evidence** - recorded by the signed plan metadata commit containing this summary

## Files Created/Modified

- `src/lifx/network/transport.py` - Splits zoned IPv6 hosts, resolves numeric or named scopes, builds the canonical sockaddr, and translates permanent zone errors.
- `tests/test_network/test_transport.py` - Proves numeric, named, unzoned, unknown, and out-of-range behaviour through the real `UdpTransport.send()` implementation.
- `.planning/phases/12-ipv6-discovery-plumbing/12-05-SUMMARY.md` - Records the gap repair, local verification, exact-revision runner evidence, and remaining PR-level blocker.
- `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/REQUIREMENTS.md` - Record sequential Plan 12-05 completion and FIND-06 closure.

## Decisions Made

- Numeric zone suffixes are parsed directly, while named zones use the operating system interface-index resolver; neither path introduces a competing interface table or address validator.
- The public two-field address contract remains unchanged. Native IPv6 sockaddr construction stays immediately adjacent to `sendto` and leaves IPv4 behaviour untouched.
- A permanent zone configuration error is a network-layer failure, not a discovery timeout or endpoint death, so it propagates immediately as `LifxNetworkError` while preserving endpoint ownership.
- Task 3 accepted only the exact gap revision's named Windows and Ubuntu job evidence. No prior run, aggregate status, skip, or allowed failure was substituted.

## Deviations from Plan

None - plan execution followed the specified gap scope exactly.

## Issues Encountered

- The PR's DCO check remains `ACTION_REQUIRED` because three earlier Phase 12 documentation commits lack sign-off trailers. All four Plan 12-05 gap commits are signed and carry sign-off trailers. Repairing the earlier history would require an explicitly authorised history rewrite and force-push, so this plan did not alter it.

## Authentication Gates

None.

## Known Stubs

None. The implementation adds no placeholder return, skipped regression, incomplete branch, or mock-only production path.

## Test and Quality Results

- **Focused Phase 12 gate:** 129 passed with `ResourceWarning` promoted to an error.
- **Full frozen suite:** 4,031 passed, 12 deselected.
- **Static quality:** Ruff format/check passed; strict Pyright reported no errors or warnings.
- **Windows/Python 3.10:** the exact current gap revision's required focused step collected and passed the public targeted IPv6 tracer; the full Windows suite also passed.
- **Ubuntu/Python 3.10:** the exact current gap revision's required full suite ran the IPv6 end-to-end and transport boundary coverage without skipping and passed.
- **Integrity:** `git diff --check` passed; each of the four gap commits has a valid configured-key signature and a DCO trailer.

## TDD Gate Compliance

Task 1 and Task 2 each used a separate failing regression commit followed by the minimal passing implementation commit. RED commits `0b3cd54` and `be89748` precede GREEN commits `5aeb11e` and `9dc4d79` respectively.

## Privacy Boundary

- Implementation and tests use only synthetic zone names plus loopback or documentation-range literals.
- The in-scope diff was inspected without emitting matched values; no live serial, interface, address, hostname, account identifier, private mapping, or raw discovery output was committed.
- CI logs were inspected in place. Only job/test categories, conclusions, and aggregate counts are recorded here.

## Threat Flags

None. The repaired code stays within the plan's caller-literal-to-local-UDP trust boundary and introduces no new endpoint, authentication path, file access, dependency, or schema.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- FIND-06 is now implemented and evidenced across the public representation and real UDP send boundaries; Phase 13 can consume the completed targeted IPv6 discovery contract.
- PR #219 remains open. Its source/test gap revision has passed the required compatibility jobs, but the separate DCO history issue must be resolved before merge.

## Self-Check: PASSED

- Both modified source/test files and this summary exist on disk.
- Task commits `0b3cd54`, `5aeb11e`, `be89748`, and `9dc4d79` exist, have valid signatures, and carry sign-off trailers.
- Exact-revision Windows and Ubuntu job metadata confirms the required steps succeeded; the detailed logs establish collection and non-skipped execution without being copied into the repository.
- No tracked deletion, known stub, unrun verification, or unresolved in-scope high-severity threat remains.

---
*Phase: 12-ipv6-discovery-plumbing*
*Completed: 2026-08-29*
