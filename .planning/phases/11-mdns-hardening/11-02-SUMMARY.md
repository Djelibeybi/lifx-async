---
phase: 11-mdns-hardening
plan: 02
subsystem: network-discovery
tags: [mdns, dns-cache, ipv6, validation, tdd]

requires:
  - phase: 11-mdns-hardening
    plan: 01
    provides: connectivity metadata propagation and legacy-unicast transport proof
provides:
  - Complete live DNS RR identity retention with bounded owners and non-evicting TXT/SRV ceilings
  - Lossless immutable advertised-address membership with locked IPv4, ULA, GUA, scoped-link-local selection
  - Exact unicast TXT serial validation and fail-closed TXT construction and SRV endpoint consensus
  - Synthetic IPv6 Thread probe reporting against the revised cache inspection seam
affects: [11-03, 11-04, 11-05, 11-06, phase-13-merged-discovery]

actuals:
  tokens: 14634
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - Complete DNS RR identity keyed by lower-case owner, type, masked class, and raw rdata
    - Non-evicting first-admission ceilings for untrusted TXT/SRV identities
    - Set-consensus validation where ordering is never a trust selector

key-files:
  created: []
  modified:
    - src/lifx/network/mdns/discovery.py
    - src/lifx/network/mdns/types.py
    - scripts/ipv6_thread_probe.py
    - tests/test_network/test_mdns/test_discovery.py
    - tests/test_scripts/test_ipv6_thread_probe.py

key-decisions:
  - "The 1,024-entry bound admits distinct owner names; admitted A/AAAA identities remain lossless, while TXT and SRV independently retain the first 16 identities without eviction."
  - "Advertised address membership is an immutable frozenset, while a separate first-learned view supplies the private same-class tie-break after the locked IPv4, ULA, GUA, scoped-link-local classification."
  - "TXT metadata and SRV endpoints resolve only through full live-set consensus; arrival order and raw-record sorting never select a trusted winner."

patterns-established:
  - "Cache identity: lower-case owner plus numeric type plus cache-flush-masked class plus raw rdata."
  - "Identity validation: inspect every raw TXT string, validate before normalisation, and preserve absence as an explicit construction value."

requirements-completed: [MDNS-03, MDNS-05, MDNS-06]

coverage:
  - id: D1
    description: "Service-instance records accumulate across arbitrary packet boundaries without duplicate replay or hostile TXT/SRV identity floods displacing admitted records."
    requirement: MDNS-03
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py#TestLifxRecordCache and TestLifxRecordCacheBounds"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every admitted valid A/AAAA address is retained as unordered membership while selection follows IPv4, ULA, GUA, then scoped link-local, with fallback kept separate."
    requirement: MDNS-05
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py#address selection and retention tests"
        status: pass
      - kind: integration
        ref: "tests/test_scripts/test_ipv6_thread_probe.py#synthetic cache reporting tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "Only exact 12-hex unicast TXT IDs resolve, and live TXT construction or SRV endpoint conflicts remain unresolved under every tested order."
    requirement: MDNS-06
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py#TXT ID, construction metadata, and SRV conflict matrix"
        status: pass
    human_judgment: false
  - id: D4
    description: "The revised cache and probe remain compatible with the complete library and strict static-analysis gates."
    verification:
      - kind: other
        ref: "uv run --frozen pytest -q (3804 passed, 12 deselected)"
        status: pass
      - kind: other
        ref: "uv run pyright (0 errors)"
        status: pass
    human_judgment: false

duration: 22 min
completed: 2026-08-28
status: complete
---

# Phase 11 Plan 02: Live RR Identity and Consensus Hardening Summary

**Complete live DNS record retention with lossless advertised addresses, locked address-class selection, and fail-closed TXT/SRV construction consensus**

## Performance

- **Duration:** 22 min
- **Started:** 2026-08-28T07:39:59Z
- **Completed:** 2026-08-28T08:02:18Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Replaced last-wins cache slots with complete live RR identities, a 1,024-owner admission bound, independent first-16 non-evicting TXT/SRV ceilings, and privacy-safe limit aggregates.
- Retained every valid advertised A/AAAA address for admitted owners as immutable unordered membership while selecting only IPv4, ULA, GUA, or scoped link-local candidates in the locked class order.
- Validated every raw TXT `id=` value as an exact 12-hex unicast identity and required one construction tuple across product, firmware, and connectivity metadata.
- Required all live SRV records for an instance to agree on normalised target and port, keeping conflicts isolated and recoverable rather than selecting a first, last, or sorted winner.
- Adapted the synthetic IPv6 Thread probe to the cache inspection seam without accessing hardware or recording live identifiers.

## Task Commits

Each TDD step was committed atomically:

1. **Task 1: Retain live RR identities and select from unordered advertised addresses**
   - `abc5b5a` — `test(mdns): add live record cache regressions`
   - `4dda1b6` — `feat(mdns): retain complete live record identities`
2. **Task 2: Validate live TXT/SRV construction identity and preserve recoverable conflicts**
   - `9b18d25` — `test(mdns): add identity consensus regressions`
   - `2e4759a` — `feat(mdns): require identity construction consensus`

## Files Created/Modified

- `src/lifx/network/mdns/discovery.py` — Complete record identities, admission bounds, lossless address retention and selection, strict TXT ID validation, and live-set consensus resolution.
- `src/lifx/network/mdns/types.py` — Trailing immutable advertised-address membership on the internal service record.
- `scripts/ipv6_thread_probe.py` — Revised cache inspection and selected/advertised address reporting.
- `tests/test_network/test_mdns/test_discovery.py` — Permutation, replay, capacity, address-class, serial-shape, TXT construction, and SRV conflict regressions.
- `tests/test_scripts/test_ipv6_thread_probe.py` — Synthetic probe compatibility and cache-report coverage.

## Decisions Made

- The global cache cap applies to distinct owners, not total records. Once an owner is admitted, valid A/AAAA records are lossless; only TXT and SRV have per-owner identity ceilings.
- TXT/SRV ceilings never evict. Every unseen over-cap observation increments only the stable `rr_identity_limit` and record-type aggregate, including replay of a rejected identity.
- Address set membership is public only to the internal record; same-class first-learned order remains a private implementation detail and is never asserted as a contract.
- Construction conflicts fail closed across the complete live set. Deterministic iteration can support storage or presentation but cannot select effective device metadata or endpoints.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced incomplete mocked DNS records in legacy discovery tests**
- **Found during:** Task 1 full mDNS module verification
- **Issue:** Four older discovery tests supplied `MagicMock` records without the owner, class, and raw rdata required by the new complete-identity cache, so their synthetic packets failed before reaching the behaviour under test.
- **Fix:** Replaced those records with genuine `DnsResourceRecord` fixtures using synthetic service names and documentation-range addresses.
- **Files modified:** `tests/test_network/test_mdns/test_discovery.py`
- **Verification:** The full mDNS/probe gate passed 223 tests after the fixture correction; the final plan-focused gate passed 164 tests.
- **Committed in:** `4dda1b6`

---

**Total deviations:** 1 auto-fixed blocking issue.
**Impact on plan:** The correction strengthened fixture fidelity without changing scope or production behaviour.

## Issues Encountered

- Restricted sandbox access initially prevented uv cache use. Approved escalated commands used the existing project environment; no dependency or lockfile changed.
- The first broad mDNS command named a non-existent legacy test module. The corrected directory-level gate ran immediately and passed all 223 collected mDNS/probe tests.

## Verification

- Task 1 focused gate: `83 passed`.
- Task 2 focused gate: `29 passed, 88 deselected`.
- Plan-focused discovery/probe gate: `164 passed`.
- Full frozen suite: `3804 passed, 12 deselected`.
- Ruff check passed; Ruff format reported all five targeted files already formatted.
- Pyright passed with `0 errors, 0 warnings, 0 information messages`.
- Python compileall completed successfully for `src/lifx` and the probe.
- Added-line privacy audit found no live device serial, MAC address, private infrastructure address, hostname, or raw discovery output.
- Stub scan found only normal empty-collection initialisation and negative test assertions; no goal-blocking placeholder or unwired data source exists.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-03 can attach TTL, goodbye grace, rescue, and expiry scheduling to the exact cached identities introduced here.
- Stable aggregate reason codes and `expires_at` are in place for later sweep reporting and timed conflict recovery.
- No blockers; hardware, daemons, multicast routing, and live network state were not used or changed.

## Self-Check: PASSED

- All five modified implementation/test artefacts exist.
- All four task commits exist and are GPG-good with the required signing key.
- Coverage metadata classifies all four deliverables as automatically covered by passing evidence.

---
*Phase: 11-mdns-hardening*
*Completed: 2026-08-28*
