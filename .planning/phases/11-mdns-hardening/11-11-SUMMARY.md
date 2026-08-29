---
phase: 11-mdns-hardening
plan: 11
subsystem: network
tags: [mdns, memory-bounds, address-selection, thread, security, tdd]

requires:
  - phase: 11-mdns-hardening
    plan: 10
    provides: exact LIFX service provenance, bounded record identities, and linear TXT consensus
provides:
  - Exact 4,096-byte per-record and 262,144-byte per-sweep retained-payload budgets
  - Symmetric byte accounting across refresh, goodbye grace, rescue, and expiry
  - Usability-first address selection with deterministic class and lexical ordering
  - Cache-to-public regressions for mixed unusable IPv4 and valid Thread ULA evidence
affects: [phase-11-gap-closure, phase-13-merged-discovery, mdns-security]

actuals:
  tokens: 6903
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Retained cache identities store one exact variable-payload cost used for both admission and removal
    - Permanent owner/type and sweep incompleteness fail closed without evicting attacker-chosen records
    - Address usability is decided before IPv4, ULA, GUA, and scoped-link-local ranking

key-files:
  created:
    - .planning/phases/11-mdns-hardening/11-11-SUMMARY.md
  modified:
    - src/lifx/network/mdns/discovery.py
    - tests/test_network/test_mdns/test_discovery.py

key-decisions:
  - "Charge only retained variable payload: UTF-8 owner, raw RDATA, four type/class bytes, and the canonical parsed payload."
  - "Keep syntactically valid but unusable addresses as bounded cache evidence while excluding them before endpoint ranking."
  - "Use lexical ordering inside the established IPv4, ULA, GUA, scoped-link-local classes so arrival order cannot choose an endpoint."

patterns-established:
  - "Symmetric accounting: store the admitted byte cost on the cached identity and release that value only when expiry removes it."
  - "Usability before preference: unsupported addresses never participate in family or class ranking."

requirements-completed: [MDNS-03, MDNS-05, MDNS-06]

coverage:
  - id: D1
    description: "Every retained mDNS record has one exact variable-payload cost bounded at 4,096 bytes, and the sweep fails closed above 262,144 bytes without weakening count ceilings."
    requirement: MDNS-03
    verification:
      - kind: unit
        ref: "Task 1 retained-payload, count-bound, goodbye-expiry, and rejection-diagnostic gate: 54 passed"
        status: pass
      - kind: integration
        ref: "Complete mDNS discovery module: 211 passed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Duplicate refresh, positive-TTL retention, one-second goodbye grace, rescue, and expiry preserve or release the stored byte charge exactly once."
    requirement: MDNS-03
    verification:
      - kind: unit
        ref: "TestLifxRecordCacheByteBounds and TestLifxRecordCacheGoodbyeExpiry"
        status: pass
    human_judgment: false
  - id: D3
    description: "Unspecified, mapped, and unscoped link-local candidates remain bounded evidence but cannot suppress a valid ULA or produce an unusable public device."
    requirement: MDNS-05
    verification:
      - kind: integration
        ref: "Task 2 cache and public-generator address-usability gate: 9 passed"
        status: pass
      - kind: integration
        ref: "Mixed unusable IPv4 plus valid ULA yields one Thread device at the ULA"
        status: pass
    human_judgment: false
  - id: D4
    description: "Capacity failures retain privacy-safe reason/count diagnostics and every task commit satisfies formatting, typing, signature, DCO, and plan-correlation requirements."
    requirement: MDNS-06
    verification:
      - kind: other
        ref: "Scoped Ruff and strict Pyright"
        status: pass
      - kind: other
        ref: "git verify-commit, DCO audit, and Plan trailer audit for all four task commits"
        status: pass
    human_judgment: false

duration: 22 min
completed: 2026-08-29
status: complete
---

# Phase 11 Plan 11: Retained Payload and Address Usability Summary

**mDNS discovery now bounds retained attacker-controlled payload bytes through their exact cache lifetime and ranks only usable endpoints, allowing a valid Thread ULA to survive unusable IPv4 evidence.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-08-28T20:55:47Z
- **Completed:** 2026-08-28T21:17:27Z
- **Tasks:** 2
- **Files created/modified:** 2 implementation and test artefacts, plus this summary

## Accomplishments

- Added exact retained-payload accounting with a 4,096-byte record limit and 262,144-byte sweep limit while preserving the independent 256-per-owner and 1,024-per-sweep address identity ceilings.
- Stored each admitted record's cost once, avoided duplicate-refresh charging, retained the charge through positive TTL and goodbye grace, preserved it on rescue, and released it exactly once on expiry removal.
- Made per-record overruns permanently incomplete for that owner/type and sweep overruns permanently incomplete for the call, with no eviction and only stable reason/count diagnostics.
- Centralised address usability before ranking, rejecting unspecified IPv4/IPv6, IPv4-mapped IPv6, and unscoped link-local IPv6 while retaining their syntactically valid cache evidence.
- Preserved the locked IPv4, ULA, GUA, scoped-link-local preference classes, added deterministic lexical tie-breaking, and proved the private cache plus public generator yield the valid Thread ULA in a mixed-address chain.

## Task Commits

1. **Task 1: Enforce exact retained-payload byte budgets through goodbye grace**
   - `10a9654` - `test(mdns): add retained byte budget regressions`
   - `aa27d41` - `fix(mdns): bound retained discovery payloads`
2. **Task 2: Filter unusable addresses before family and class priority**
   - `224dbea` - `test(mdns): add address usability regressions`
   - `10289d0` - `fix(mdns): filter unusable address candidates`

The plan metadata is captured by the signed and DCO-compliant commit containing this summary.

## Files Created/Modified

- `src/lifx/network/mdns/discovery.py` - Accounts for retained bytes across record lifetime and filters unusable addresses before deterministic ranking.
- `tests/test_network/test_mdns/test_discovery.py` - Adds exact byte boundaries, count-bound independence, goodbye/rescue lifetime, mixed-address, and public-generator regressions.
- `.planning/phases/11-mdns-hardening/11-11-SUMMARY.md` - Records execution evidence and close-out state.

## Decisions Made

- The byte cost covers only attacker-controlled variable payload copied into cache state. Existing entry and identity ceilings continue to bound fixed Python object overhead.
- Byte pressure cannot recover eligibility by evicting earlier records: owner/type or sweep incompleteness remains permanent for one discovery call.
- Syntactically valid unusable addresses remain available as bounded evidence, but selection considers only candidates consistent with the public address validator.
- Same-class endpoint selection is lexical rather than first-learned, removing packet-arrival influence without changing class priority.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reconciled partial close-out handler updates**
- **Found during:** Plan metadata close-out
- **Issue:** The requirements handler marked MDNS-03 complete but could not update MDNS-05's amended status, while STATE retained Plan 10 activity prose and the roadmap handler removed one table-cell space.
- **Fix:** Marked MDNS-05 complete on both requirement surfaces, updated STATE to the completed Plan 11 activity and next Plan 12, and restored valid roadmap table spacing.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
- **Commit:** Plan metadata commit

## Issues Encountered

- The first Task 1 implementation pass exposed an SRV byte-incompleteness path that could have fallen back to packet-source evidence; the implementation was corrected before its GREEN commit so incomplete SRV construction remains fail closed.
- The first two task commit commands encoded newline escapes literally around the required Plan trailer. Before close-out, all four unpushed plan commits were replayed and re-signed so every commit contains a real `Plan: 11-11` body line and DCO trailer.
- The managed sandbox cannot read the configured GPG trust database. All four task commits were verified successfully in the approved repository environment without recording signer identity in tracked evidence.

## Authentication Gates

None.

## Known Stubs

None. No goal-blocking placeholder, skipped test, unrun verification, mock-only production path, or unfinished implementation remains.

## Test and Quality Results

- **Task 1 RED:** The exact limit, sweep, lifetime, and fail-closed regressions exposed the missing retained-byte accounting before implementation.
- **Task 1 tracer:** 54 passed across byte bounds, existing count bounds, goodbye expiry, and privacy-safe rejection diagnostics.
- **Task 2 RED:** The focused gate exposed unspecified IPv4 selection, unusable-only emission, public Thread suppression, and arrival-dependent same-class choice before implementation.
- **Task 2 focused gate:** 9 passed after implementation.
- **Complete discovery module:** 211 passed with `ResourceWarning` promoted to an error.
- **Static quality:** Scoped Ruff passed; strict Pyright reported 0 errors, 0 warnings, and 0 information messages.
- **Integrity:** All four task commits have valid cryptographic signatures, DCO trailers, and real `Plan: 11-11` body lines; `git diff --check` passed.

## TDD Gate Compliance

- Task 1 RED `10a9654` precedes GREEN `aa27d41`.
- Task 2 RED `224dbea` precedes GREEN `10289d0`.
- Both RED stages demonstrated the planned missing behaviour before implementation, and both GREEN stages passed their exact named gates.

## Privacy Boundary

- All new identifiers, hostnames, and addresses are synthetic; IPv4 examples use RFC 5737 documentation space and IPv6 examples use deliberate test-only values.
- No live serial, MAC address, IP address, hostname, account name, hardware output, raw packet, or external identity mapping was recorded.
- Capacity diagnostics contain only stable reason/type/count fields, never owner names, targets, addresses, serials, or TXT values.
- The separate broadcast-discovery spike finding was not applied to this mDNS-only plan.

## Threat Flags

None. Retained cache memory, selected endpoints, and the public Device boundary were explicitly covered by the plan's threat model; no unplanned endpoint, authentication path, file-access boundary, schema, dependency, or public API was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-11 closes the retained-payload and unusable-address suppression gaps and leaves the branch ready for Plan 11-12's deadline and termination work.
- MDNS-03 and MDNS-05 are complete for implementation tracking; later plans retain independent re-verification and coverage ownership.
- The immutable gap base remains available for Plan 11-14's changed-line and changed-branch coverage gate.

## Self-Check: PASSED

- The planned source, test, and summary artefacts exist.
- Task commits `10a9654`, `aa27d41`, `224dbea`, and `10289d0` exist and match the recorded TDD sequence.
- The complete working diff passes `git diff --check` before metadata close-out.

---
*Phase: 11-mdns-hardening*
*Completed: 2026-08-29*
