---
phase: 12-ipv6-discovery-plumbing
plan: 04
subsystem: testing
tags: [ipv6, discovery, windows, ci, asyncio]

requires:
  - phase: 12-01
    provides: family-aware targeted discovery and the public IPv6 tracer
  - phase: 12-02
    provides: IPv6 representation and validation coverage
  - phase: 12-03
    provides: IPv6 lifecycle, cancellation, and concurrency coverage
provides:
  - Narrow Windows/Python 3.10 eligibility for the real targeted IPv6 tracer
  - A required focused CI step with the locked Windows retry policy
  - Authoritative Windows and Ubuntu log-level evidence for D-10
  - Cross-platform canonical IPv6 datagram destinations for asyncio transports
affects: [phase-13-merged-discovery, find-by-ip, github-actions]

actuals:
  tokens: 2255
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - Gate one exact Windows emulator tracer through a dedicated opt-in fixture and CI node ID
    - Pass canonical four-field IPv6 socket addresses to asyncio datagram transports

key-files:
  created:
    - .planning/phases/12-ipv6-discovery-plumbing/12-04-SUMMARY.md
  modified:
    - tests/conftest.py
    - tests/test_api/test_ipv6_e2e.py
    - .github/workflows/ci.yml
    - src/lifx/network/transport.py
    - tests/test_network/test_transport.py

key-decisions:
  - "Keep Windows eligibility behind exact LIFX_WINDOWS_IPV6_DISCOVERY=1 and select only the public tracer node in CI."
  - "Treat current-revision job logs, including collection and per-test results, as D-10 evidence rather than aggregate workflow status."
  - "Normalise AF_INET6 destinations to four-field socket addresses at the transport send boundary while retaining the two-field public input."

patterns-established:
  - "Required cross-runner evidence: inspect the exact current-revision job step and test result; a green workflow alone is insufficient."
  - "IPv6 send compatibility: translate the public host-port pair to host-port-flowinfo-scope-id immediately before datagram send."

requirements-completed: [FIND-06]

coverage:
  - id: D1
    description: "Windows IPv6 emulator eligibility is restricted to an exact opt-in while general Windows emulator tests remain disabled."
    requirement: FIND-06
    verification:
      - kind: unit
        ref: "tests/test_api/test_ipv6_e2e.py#targeted IPv6 eligibility decision tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "The required Windows/Python 3.10 CI step collected and passed the exact public targeted IPv6 tracer."
    requirement: FIND-06
    verification:
      - kind: e2e
        ref: "GitHub Actions PR #219 Windows/Python 3.10 Run targeted IPv6 discovery log"
        status: pass
    human_judgment: false
  - id: D3
    description: "The Ubuntu/Python 3.10 full suite exercised every IPv6 end-to-end test without skipping the module."
    requirement: FIND-06
    verification:
      - kind: integration
        ref: "GitHub Actions PR #219 Ubuntu/Python 3.10 Run unit tests log"
        status: pass
    human_judgment: false
  - id: D4
    description: "Asyncio datagram sends use canonical IPv6 destinations accepted by the Windows proactor transport."
    requirement: FIND-06
    verification:
      - kind: integration
        ref: "tests/test_network/test_transport.py#TestSendFamilyAssertion::test_matching_ipv6_destination_uses_canonical_sockaddr"
        status: pass
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py#TestIpv6TargetedDiscovery::test_find_by_ip_over_ipv6"
        status: pass
    human_judgment: false

duration: 15 min
completed: 2026-08-29
status: complete
---

# Phase 12 Plan 04: Cross-Runner IPv6 Discovery Evidence Summary

**A narrowly opted-in Windows tracer and the unchanged Ubuntu full suite now prove public IPv6 targeted discovery across runners, with canonical datagram destinations for Windows asyncio compatibility.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-29T10:45:49Z
- **Completed:** 2026-08-29T11:00:45Z
- **Tasks:** 3
- **Files modified:** 5 implementation, test, and workflow files, plus this summary and sequential planning state

## Accomplishments

- Added a dedicated, exact Windows opt-in that makes only the public targeted IPv6 tracer eligible while retaining the existing IPv6 availability probe and broader emulator exclusions.
- Added the required Windows/Python 3.10 focused CI step immediately before the unchanged full suite, with the locked pytest retry policy and no allowed-failure route.
- Opened source/test PR #219 and inspected authoritative current-source-revision logs: Windows collected one exact tracer and passed it, while Ubuntu passed every IPv6 end-to-end node in the full 4,027-test suite.
- Corrected the Windows proactor compatibility issue uncovered by the first CI attempt by sending canonical four-field IPv6 socket addresses.

## Task Commits

Tasks and the in-scope CI correction were committed atomically:

1. **Task 1 RED: Add failing Windows IPv6 eligibility regressions** - `88b8979` (`test`)
2. **Task 1 GREEN: Enable the focused Windows IPv6 emulator path** - `d50962e` (`test`)
3. **Task 2: Require targeted Windows IPv6 discovery in CI** - `3458fd6` (`ci`)
4. **Task 3 deviation: Use canonical IPv6 datagram targets** - `33cdc0f` (`fix`)

The plan metadata is captured by the signed and DCO-compliant commit containing this summary.

## Files Created/Modified

- `tests/conftest.py` - Adds the narrow Windows eligibility decision and fixture while retaining the existing IPv6 probe.
- `tests/test_api/test_ipv6_e2e.py` - Covers the eligibility boundary and applies the locked retry marker to the real tracer.
- `.github/workflows/ci.yml` - Adds the required Windows/Python 3.10 focused step before the unchanged full suite.
- `src/lifx/network/transport.py` - Converts IPv6 destinations to canonical four-field socket addresses at send time.
- `tests/test_network/test_transport.py` - Proves matching IPv6 destinations are sent using canonical socket-address form.
- `.planning/phases/12-ipv6-discovery-plumbing/12-04-SUMMARY.md` - Records implementation, external evidence, deviations, privacy, and close-out status.
- `.planning/STATE.md` and `.planning/ROADMAP.md` - Record sequential Phase 12 completion and execution metrics.

## Decisions Made

- The Windows opt-in remains exact and test-only; exact pytest node selection, not a broadened emulator fixture, defines the CI attempt's narrow boundary.
- D-10 is satisfied only by current-source-revision job logs showing the exact node was collected and passed on Windows and the IPv6 module ran without skips in Ubuntu's full suite.
- IPv6 socket-address normalisation belongs at the datagram send boundary because the public and internal discovery APIs continue to accept a stable host-port pair.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Windows proactor rejection of abbreviated IPv6 datagram destinations**

- **Found during:** Task 3 (confirm cross-runner evidence)
- **Issue:** The first required Windows run collected the exact tracer but failed because the Windows asyncio proactor rejected a two-field IPv6 destination during datagram send.
- **Fix:** Convert AF_INET6 destinations to the canonical host, port, flow-info, and scope-id tuple immediately before `sendto`, and update the transport regression to require that form.
- **Files modified:** `src/lifx/network/transport.py`, `tests/test_network/test_transport.py`
- **Verification:** The focused test passed; the network and IPv6 modules passed; Ruff and Pyright passed; the full local suite passed; the replacement Windows and Ubuntu CI jobs passed with the required non-skipped evidence.
- **Committed in:** `33cdc0f`

---

**Total deviations:** 1 auto-fixed bug (Rule 1)
**Impact on plan:** The fix was required for the planned Windows evidence and preserves the existing API, scope, retry policy, and test boundary.

## Issues Encountered

- The first Windows/Python 3.10 CI attempt was an honest failure rather than a skip: the named step collected the tracer and reached the Windows datagram send boundary. The in-scope transport correction resolved it on the replacement run.
- The checkout remains one commit behind `origin/main`, as instructed. GitHub reports the PR as behind but open and testable; no mergeability action or history rewrite was required.
- The managed sandbox required approved repository access for Git index writes and GPG keyring verification.

## Authentication Gates

None.

## Known Stubs

None. No new placeholder branch, skipped test, mock result, or unrun verification remains. Existing environment-availability skips and the transport's documented zero-serial placeholder are intentional established behaviour, not plan stubs.

## Test and Quality Results

- **Focused transport and tracer:** 10 passed.
- **Transport and IPv6 modules:** 82 passed with `ResourceWarning` promoted to an error.
- **Full local suite:** 4,027 passed, 12 deselected.
- **Static quality:** Ruff format/check passed; strict Pyright reported no errors or warnings.
- **Windows/Python 3.10 CI:** the required named step collected exactly one tracer and passed it.
- **Ubuntu/Python 3.10 CI:** every IPv6 module node passed in the unchanged full suite; 4,027 tests passed and 12 were deselected.
- **Integrity:** `git diff --check` passed; the in-scope correction commit is GPG-signed by the configured key and carries a DCO trailer.

## TDD Gate Compliance

Task 1 followed RED/GREEN with separate regression and implementation commits. The Task 3 compatibility correction was reproduced by changing the transport assertion first, observing the expected failure, then applying the minimal source fix and passing focused and full gates.

## Privacy Boundary

- Tests and CI evidence use only loopback networking, ephemeral ports, and synthetic emulator identities.
- The branch diff was inspected before publication without emitting matched values; no live serial, MAC address, routable address, hostname, account identifier, private mapping, or raw discovery output was committed.
- CI logs were inspected in place and were not copied into the repository.

## Threat Flags

None. The transport correction changes the representation passed to an already planned local UDP send and introduces no endpoint, authentication path, file access, dependency, schema, or new trust boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 12's four plans now provide implementation, representation, lifecycle, and cross-runner evidence for FIND-06.
- PR #219 remains open and unmerged. Phase 13 can consume the completed family-aware targeted discovery contract after the normal review and merge gates.
- No D-11 requirement drop or durable exception record was needed.

## Self-Check: PASSED

- All five modified implementation, test, and workflow files and this summary exist on disk.
- Task commits `88b8979`, `d50962e`, `3458fd6`, and `33cdc0f` exist; the new correction commit has a valid configured-key signature and DCO sign-off.
- Authoritative replacement-run logs show the Windows exact-node pass and the Ubuntu non-skipped IPv6 full-suite pass for the recorded source revision.
- No tracked file deletion, known stub, unrun verification, or unresolved high-severity threat remains.

---
*Phase: 12-ipv6-discovery-plumbing*
*Completed: 2026-08-29*
