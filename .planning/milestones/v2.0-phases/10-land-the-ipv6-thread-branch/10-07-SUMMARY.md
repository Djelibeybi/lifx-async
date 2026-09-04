---
phase: 10-land-the-ipv6-thread-branch
plan: 07
subsystem: network
tags: [ipv6, mdns, discovery, resilience, patch-coverage]

requires:
  - phase: 10-03
    provides: "the shared address validator, strict public-entry validation, and branch-aware mDNS coverage baseline"
  - phase: 10-06
    provides: "the landed IPv6/Thread implementation and verification amendment identifying the two mDNS availability gaps"
provides:
  - "per-record degradation for unusable bare IPv6 link-local mDNS records without weakening direct construction"
  - "resolved-record-first mDNS delivery with two-attempt per-target retries and a 64-target admission cap"
  - "a standard-library changed-line, changed-branch, and test-weakening coverage gate anchored to one immutable base"
affects: [10-08, 11-mdns-hardening, 12-ipv6-discovery-plumbing, 13-merged-discovery]

actuals:
  tokens: 11850
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Validate untrusted discovery records immediately before construction and degrade only the expected validation failure"
    - "Deliver resolved cache results before awaiting auxiliary network work"
    - "Measure patch coverage from an immutable full Git SHA using coverage.py JSON as the executable-line and branch authority"

key-files:
  created:
    - .planning/phases/10-land-the-ipv6-thread-branch/10-GAP-BASE.txt
    - scripts/check_patch_coverage.py
    - tests/test_scripts/test_check_patch_coverage.py
    - .planning/phases/10-land-the-ipv6-thread-branch/10-07-SUMMARY.md
  modified:
    - src/lifx/network/mdns/discovery.py
    - tests/test_network/test_mdns/test_discovery.py

key-decisions:
  - "Bare link-local mDNS records are validated and skipped inside discover_devices_mdns(), while create_device_from_record() and all four user-input entry points retain strict ValueError behaviour"
  - "Resolved service records are yielded before fallible follow-up sends; successful targets remain one-shot, failed targets receive at most two attempts, and failed attempts count towards the 64-target cap"
  - "10-GAP-BASE.txt captures b4e9b365f4f388ad4dd6800be8e7f9144f027bd6 once, and the repository-local coverage gate fails closed on malformed evidence, exclusions, skips, deleted tests, or coverage-configuration changes"

patterns-established:
  - "Narrow degradation: catch ValueError only around shared address validation, never around device construction"
  - "Independent traffic ledgers: successful sends and attempted targets answer different bounded-resource questions"
  - "Fresh patch evidence: every changed executable line and every outgoing changed branch must be present and covered in branch-aware JSON"

requirements-completed: [IPV6-01, IPV6-02, IPV6-03]

coverage:
  - id: D1
    description: "A bare IPv6 link-local mDNS record is skipped without terminating the public device sweep, while later valid records are yielded"
    requirement: IPV6-02
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_discovery.py::TestDiscoverDevicesMdns"
        status: pass
    human_judgment: false
  - id: D2
    description: "Resolved records are delivered before auxiliary query sends, with exact-once serial delivery, one retry, and a 64-target traffic cap"
    requirement: IPV6-01
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py::TestMdnsFollowUpAddressQueries and TestMdnsSerialDeduplication"
        status: pass
      - kind: integration
        ref: "uv run --frozen pytest tests/test_network/test_mdns/test_discovery.py -q - 63 passed"
        status: pass
    human_judgment: false
  - id: D3
    description: "Strict shared address validation remains authoritative at direct construction and all four public address entry points"
    requirement: IPV6-03
    verification:
      - kind: integration
        ref: "uv run --frozen pytest tests/test_network/test_address.py tests/test_devices/test_base.py tests/test_api/test_api_discovery.py -q - 120 passed"
        status: pass
    human_judgment: false
  - id: D4
    description: "A standard-library local gate rejects uncovered changed source, partial changed branches, exclusions, skip mechanisms, deleted tests, malformed reports, and a mutable base"
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_check_patch_coverage.py - 44 passed with 100% statement and branch coverage of the checker"
        status: pass
      - kind: other
        ref: "combined 10-07 gate - 225 changed executable lines and 94 changed branches passed"
        status: pass
    human_judgment: false

duration: 18 min
completed: 2026-08-28
status: complete
---

# Phase 10 Plan 07: mDNS Discovery Gap Closure Summary

**Resilient mDNS delivery now skips unusable records, preserves already-resolved devices across auxiliary send failures, and proves every changed executable line and branch from one immutable base.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-08-27T22:06:58Z
- **Completed:** 2026-08-27T22:24:17Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Kept `discover_devices_mdns()` productive after a bare `fe80::1` record, without weakening direct construction or the four strict public address entry points.
- Reordered mDNS processing so resolved records are yielded before fallible follow-up sends, while bounding failed targets to two attempts and 64 distinct admitted targets.
- Added a dependency-free patch-coverage utility with 44 tests and fresh evidence covering 225 changed executable lines and 94 changed branches across both changed production sources.
- Preserved every scope fence: no dependency, coverage configuration, discovery constant, Thread UAT record, deleted test, skip, or coverage exemption changed.

## Task Commits

Each task was committed atomically with GPG signature and DCO sign-off:

1. **Task 1: Keep the public mDNS device sweep alive after a bare link-local record** - `a9cd141` (fix)
2. **Task 2: Deliver resolved records before fallible follow-up address queries** - `4ac33de` (fix)
3. **Task 3: Enforce changed-line and changed-branch coverage from one pre-gap base** - `9462da4` (chore)

## Files Created/Modified

- `.planning/phases/10-land-the-ipv6-thread-branch/10-GAP-BASE.txt` - Immutable common pre-gap SHA for plans 10-07 and 10-08.
- `src/lifx/network/mdns/discovery.py` - Narrow invalid-record degradation plus resolved-record-first, bounded follow-up query handling.
- `tests/test_network/test_mdns/test_discovery.py` - Public-generator, error-propagation, exact-once, retry, and traffic-cap regressions.
- `scripts/check_patch_coverage.py` - Standard-library Git diff and coverage.py JSON assertion utility.
- `tests/test_scripts/test_check_patch_coverage.py` - Temporary-repository and synthetic-report coverage of all gate success and failure paths.

## Decisions Made

See `key-decisions` above. The central boundary is that discovery availability improves without synthesising scope identifiers, changing address preference, or weakening strict user-input validation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Resolved Git before invoking the coverage subprocess**

- **Found during:** Task 3 commit verification.
- **Issue:** The Bandit commit hook rejected importing `subprocess` and launching `git` by a partial executable path.
- **Fix:** Resolve Git to an absolute path with `shutil.which()`, fail closed when absent, retain a shell-free argument vector, and narrowly document the two reviewed Bandit findings.
- **Files modified:** `scripts/check_patch_coverage.py`, `tests/test_scripts/test_check_patch_coverage.py`.
- **Verification:** The dedicated missing-Git test passes, the checker retains 100% statement and branch coverage, and the Bandit commit hook passes.
- **Committed in:** `9462da4`.

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking issue).
**Impact on plan:** The fix strengthened executable resolution and fail-closed behaviour without changing scope or dependencies.

## Issues Encountered

- The first Task 3 commit attempt was correctly blocked by Bandit; the security finding was fixed before any commit was created.

## Known Stubs

None.

## Verification Record

| Check | Result |
|---|---|
| Full repository suite | 3,721 passed, 12 deselected, 7 existing deprecation warnings |
| mDNS discovery suite | 63 passed |
| Strict address and public-entry suites | 120 passed |
| Patch-checker suite | 44 passed; checker at 100% statements and branches |
| Combined changed-source gate | 225 changed executable lines and 94 changed branches passed |
| Ruff check and format | passed |
| Pyright | 0 errors, 0 warnings, 0 information messages |
| Weakening-only full-diff scan | passed |
| Protected-file and deleted-test prohibitions | passed |
| Task commit GPG signatures and DCO trailers | passed for all three commits |

## User Setup Required

None.

## Next Phase Readiness

Plan 10-08 can consume the same immutable `10-GAP-BASE.txt` and the committed coverage utility to close the remaining transport cancellation gap. No blocker remains from 10-07.

## Self-Check: PASSED

- All five implementation artefacts exist.
- Task commits `a9cd141`, `4ac33de`, and `9462da4` exist, are GPG-valid, and carry DCO sign-off.
- Every plan verification and prohibition command passed against committed `HEAD`.

---
*Phase: 10-land-the-ipv6-thread-branch*
*Completed: 2026-08-28*
