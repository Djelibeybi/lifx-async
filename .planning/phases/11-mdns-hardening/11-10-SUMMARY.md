---
phase: 11-mdns-hardening
plan: 10
subsystem: network
tags: [mdns, service-provenance, txt-consensus, security, tdd]

requires:
  - phase: 11-mdns-hardening
    plan: 09
    provides: preserved Phase 11 authority, privacy disposition, and fresh baseline gates
provides:
  - Exact case-insensitive LIFX service-instance provenance from cache admission through public device emission
  - SRV-linked address eligibility that cannot be borrowed by unrelated services in mixed packets
  - Linear TXT metadata consensus with immediate conflict rejection and at most one construction attempt
  - Immutable pre-gap base SHA for later changed-line and changed-branch verification
affects: [phase-11-gap-closure, phase-13-merged-discovery, mdns-security]

actuals:
  tokens: 6691
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Canonical DNS names remove one optional terminal root dot and use case-folding without changing label structure
    - Construction records require exact service-instance ownership while address records remain bounded linked candidates
    - TXT metadata retains one parsed effective value per field and returns immediately on disagreement

key-files:
  created:
    - .planning/phases/11-mdns-hardening/11-GAP-BASE.txt
    - .planning/phases/11-mdns-hardening/11-10-SUMMARY.md
  modified:
    - src/lifx/network/mdns/types.py
    - src/lifx/network/mdns/discovery.py
    - tests/test_network/test_mdns/test_discovery.py
    - tests/test_api/test_api_discovery.py
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/WINDOWS.md

key-decisions:
  - "Treat only a non-empty instance immediately beneath the canonical _lifx._udp.local suffix as LIFX construction provenance."
  - "Keep A and AAAA records as bounded candidates until a live SRV owned by an exact LIFX instance links their owner."
  - "Compare parsed effective TXT values in one pass and stop on the second distinct product, firmware, or connectivity value."

patterns-established:
  - "Service provenance: validate exact ownership at cache admission, resolution, pending work, private record emission, and the public generator boundary."
  - "Bounded consensus: hold one value per construction field rather than enumerating a Cartesian product."

requirements-completed: [MDNS-06]
requirements-advanced: [MDNS-03]

coverage:
  - id: D1
    description: "Exact mixed-case LIFX service instances resolve through the public generator while unrelated and lookalike service chains fail closed at every named boundary."
    requirement: MDNS-03
    verification:
      - kind: integration
        ref: "Task 1 exact provenance tracer: 13 passed"
        status: pass
      - kind: integration
        ref: "Plan-wide mDNS discovery/API gate: 215 passed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Address records become eligible only through a live exact-service SRV relationship, including cross-packet and A-before-SRV assembly."
    requirement: MDNS-03
    verification:
      - kind: unit
        ref: "TestLifxRecordCache exact provenance and split-record regressions"
        status: pass
    human_judgment: false
  - id: D3
    description: "TXT product, firmware, and connectivity consensus is linear in retained records, rejects the second effective value early, and constructs at most one record."
    requirement: MDNS-06
    verification:
      - kind: unit
        ref: "Task 2 named TXT consensus gate: 5 passed"
        status: pass
      - kind: integration
        ref: "Complete discovery module: 191 passed"
        status: pass
    human_judgment: false
  - id: D4
    description: "The private converter boundary, public wifi or thread contract, formatting, typing, signatures, and DCO requirements remain intact."
    requirement: MDNS-06
    verification:
      - kind: other
        ref: "Scoped Ruff and strict Pyright"
        status: pass
      - kind: other
        ref: "git verify-commit and value-suppressed DCO audit for all four task commits"
        status: pass
    human_judgment: false

duration: 47 min
completed: 2026-08-29
status: complete
---

# Phase 11 Plan 10: Exact Service Provenance and TXT Consensus Summary

**Exact LIFX service ownership now gates every mDNS construction boundary, and TXT metadata reaches one bounded linear consensus without Cartesian expansion.**

## Performance

- **Duration:** 47 min
- **Started:** 2026-08-28T19:56:44Z
- **Completed:** 2026-08-28T20:44:11Z
- **Tasks:** 2
- **Files created/modified:** 5 implementation and test artefacts

## Accomplishments

- Added one DNS-name normaliser and an exact service-instance predicate, then carried the admitted owner through private records so the public generator can independently reject absent or forged provenance.
- Kept A and AAAA identities as bounded address candidates and granted LIFX activity only when an exact-service SRV record links the address owner, preserving cross-packet and A-before-SRV assembly without mixed-packet privilege borrowing.
- Replaced the TXT construction-set Cartesian expansion with a single pass holding one effective serial, product, firmware, and connectivity value, returning immediately on disagreement.
- Preserved the private low-level mDNS API, public `wifi|thread` connectivity values, the 16-TXT-per-owner ceiling, and all existing serial/product validation.

## Task Commits

1. **Task 1: Carry exact LIFX service provenance from admission to public emission**
   - `f52f8c1` - `test(mdns): add exact service provenance regressions`
   - `8d7ba61` - `fix(mdns): enforce exact service provenance`
2. **Task 2: Replace TXT Cartesian expansion with linear single-value consensus**
   - `bd6f61a` - `test(mdns): add TXT consensus regressions`
   - `18d28ef` - `fix(mdns): resolve TXT metadata linearly`

The plan metadata is captured by the signed and DCO-compliant commit containing this summary.

## Files Created/Modified

- `.planning/phases/11-mdns-hardening/11-GAP-BASE.txt` - Pins exact pre-gap commit `1b9b564a028c1d3e28f3601077e49e144f37e343` for later coverage gates.
- `src/lifx/network/mdns/types.py` - Carries private service-instance provenance on resolved records.
- `src/lifx/network/mdns/discovery.py` - Enforces exact service ownership and performs linear TXT consensus.
- `tests/test_network/test_mdns/test_discovery.py` - Adds adversarial boundary and consensus regressions plus source-backed fixture corrections.
- `tests/test_api/test_api_discovery.py` - Supplies exact synthetic provenance to legitimate public-generator fixtures.

## Decisions Made

- Canonicalisation removes only one optional terminal root dot and uses `casefold()`. It does not collapse, reorder, or otherwise reinterpret DNS labels.
- TXT and SRV construction owners must be exact service instances. A, AAAA, and packet-source fallback evidence cannot create construction provenance by themselves.
- TXT conflicts remain live resolution ambiguity rather than new per-record diagnostics, preserving the stable privacy-safe rejection vocabulary from earlier Phase 11 plans.
- Missing firmware remains an explicit effective value and all non-exact private connectivity spellings remain the existing WiFi outcome.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated two legacy fixtures that encoded pre-gap provenance assumptions**
- **Found during:** Task 1 full discovery-module verification
- **Issue:** One split-record test expected an SRV-linked address-only packet not to count as LIFX activity, and one private-discovery fixture placed valid TXT construction metadata under an unrelated owner.
- **Fix:** Asserted linked address activity and moved the valid construction fixture under an exact synthetic LIFX service instance.
- **Files modified:** `tests/test_network/test_mdns/test_discovery.py`
- **Commit:** `8d7ba61`

**2. [Rule 2 - Critical] Replaced a touched private-range fixture with a documentation address**
- **Found during:** Task 1 staged privacy review
- **Issue:** A legacy test already being modified contained a private-range address, contrary to the repository rule for synthetic network evidence.
- **Fix:** Replaced it with the stable RFC 5737 address `192.0.2.1` without changing test behaviour.
- **Files modified:** `tests/test_network/test_mdns/test_discovery.py`
- **Commit:** `8d7ba61`

**3. [Rule 1 - Bug] Corrected stale closeout-handler position and roadmap prose**
- **Found during:** Plan metadata closeout
- **Issue:** The normal state handler advanced the orchestrator's temporary Plan 1 marker to Plan 2 rather than the actual next Plan 11 position, and the roadmap still said gap planning was pending.
- **Fix:** Reconciled STATE to Plan 11 of 14 and changed ROADMAP to gap closure in progress while retaining the handler-generated 10/14 counts.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Commit:** Plan metadata commit

All three fixed deviations are recorded as resolved entries in `.planning/WINDOWS.md`.

## Issues Encountered

- The managed sandbox denies UDP socket creation used by the API integration fixtures. The exact socket-dependent gates were rerun in the approved repository environment and passed.
- The managed sandbox cannot read the configured GPG trust database. All four commits verified successfully in the approved environment; DCO checks were performed without printing trailer identities into tracked evidence.
- Commit hooks temporarily set aside the orchestrator-owned `.planning/STATE.md` update and restored it after each task commit, so task commits stayed atomic.
- The summary validator treats the first `Verification` heading as the self-check section and then interprets RED-stage failure evidence as a failed closeout. The results heading was made more specific so the final explicit self-check remains authoritative.

## Authentication Gates

None.

## Known Stubs

None. No goal-blocking placeholder, skipped test, unrun verification, mock-only production path, or unfinished implementation remains.

## Test and Quality Results

- **Task 1 RED:** 10 intended failures across 13 collected cases before implementation.
- **Task 1 tracer:** 13 passed after the signed implementation commit.
- **Task 2 RED:** 1 intended early-conflict failure and 4 passing compatibility controls across 5 collected cases.
- **Task 2 focused gate:** 5 passed after implementation.
- **Complete discovery module:** 191 passed with `ResourceWarning` promoted to an error.
- **Plan-wide integration:** 215 passed across mDNS discovery and API discovery with `ResourceWarning` promoted to an error.
- **Static quality:** Scoped Ruff passed; strict Pyright reported 0 errors, 0 warnings, and 0 information messages.
- **Integrity:** `11-GAP-BASE.txt` matches the full pre-gap SHA; all four task commits have valid cryptographic signatures and DCO trailers; `git diff --check` passed.

## TDD Gate Compliance

- Task 1 RED `f52f8c1` precedes GREEN `8d7ba61`.
- Task 2 RED `bd6f61a` precedes GREEN `18d28ef`.
- Both RED stages failed for their intended missing behaviour before implementation; both GREEN stages passed their exact named gates.

## Privacy Boundary

- All new identifiers are synthetic, and all new or touched network addresses use RFC documentation ranges.
- No live serial, MAC address, IP address, hostname, account name, hardware output, raw packet, or external identity mapping was recorded.
- The separate broadcast-discovery spike finding was not applied to this mDNS-only plan.

## Threat Flags

None. The service-provenance trust boundary and fail-closed TXT consensus were explicitly planned; no unplanned endpoint, authentication path, file-access boundary, schema, dependency, or public API was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-10 closes the exact-service provenance and TXT Cartesian-expansion gaps and leaves the branch ready for Plans 11-11 and 11-12.
- MDNS-06 is complete for this gap run. MDNS-03 remains shared with Plan 11-11's deadline and termination work, so it is advanced but not marked complete yet.
- The immutable gap base is ready for Plan 11-14's changed-line and changed-branch coverage gate.

## Self-Check: PASSED

- Every planned source, test, gap-base, and summary artefact exists.
- Task commits `f52f8c1`, `8d7ba61`, `bd6f61a`, and `18d28ef` exist and match the recorded TDD sequence.
- The complete working diff passes `git diff --check` before metadata closeout.

---
*Phase: 11-mdns-hardening*
*Completed: 2026-08-29*
---
