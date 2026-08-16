---
phase: 08-hardware-fidelity-validation
plan: 03
subsystem: documentation-testing
tags: [theme-library, fidelity, JSONL, pytest, documentation]
requires:
  - phase: 08-02
    provides: Phase 8 runner and evidence-finalisation foundations
provides:
  - Corrected 25-shipped versus 26-raw 16-colour documentation boundary
  - Deterministic regression coverage for the four active Phase 8 documents
affects: [08-04-hardware-uat, FIDELITY-01, Phase-9-documentation]
actuals:
  tokens: 2372
  tasks: 2
  commits: 4
tech-stack:
  added: []
  patterns:
    - Phase-local tests derive documentation facts directly from committed JSONL sources.
    - Active-document scans normalise Markdown whitespace and exclude historical problem descriptions.
key-files:
  created:
    - .planning/phases/08-hardware-fidelity-validation/tests/test_documentation_counts.py
  modified:
    - .planning/PROJECT.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .claude/theme-capture/README.md
key-decisions:
  - "FIDELITY-01 remains pending: its scope is 25 shipped lifx-app themes with literal 16-colour palettes."
  - "Carlton is the excluded AUSSIE RULES raw record explaining 26 raw versus 25 shipped targets."
requirements-completed: []
coverage:
  - id: D1
    description: Active Phase 8 documentation distinguishes 25 shipped themes from 26 raw records and names Carlton as excluded.
    requirement: FIDELITY-01
    verification:
      - kind: unit
        ref: .planning/phases/08-hardware-fidelity-validation/tests/test_documentation_counts.py#test_active_phase_8_documents_use_correct_ceiling_counts
        status: pass
    human_judgment: false
  - id: D2
    description: The committed shipped and raw JSONL sources mechanically yield the 25/26/Carlton boundary.
    requirement: FIDELITY-01
    verification:
      - kind: unit
        ref: .planning/phases/08-hardware-fidelity-validation/tests/test_documentation_counts.py#test_ceiling_inventory_is_25_shipped_from_26_raw
        status: pass
    human_judgment: false
duration: 10min
completed: 2026-08-15
status: complete
---

# Phase 08 Plan 03: Hardware Fidelity Documentation Counts Summary

**Phase 8 now defines its 16-colour determination scope as 25 shipped non-sport `lifx-app` themes, with the 26th raw record identified as excluded Carlton.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-08-15T18:28:01Z
- **Completed:** 2026-08-15T18:32:44Z
- **Tasks:** 2/2
- **Files modified:** 5

## Accomplishments

- Corrected active PROJECT, REQUIREMENTS and ROADMAP claims to distinguish 25 shipped targets from 26 raw exactly-16-colour records.
- Left FIDELITY-01 pending and documented its literal `disposition == "lifx-app"` plus palette-length-16 membership rule.
- Replaced the capture README's stale 21 count and added a two-test, JSONL-derived regression for all four active documents.

## Task Commits

1. **Task 1: Correct PROJECT, REQUIREMENTS and ROADMAP to 25 shipped targets** — `1c03c97` (docs)
2. **Task 2: Correct the capture caveat and add a mechanical active-document regression** — `88cfaf4` (test, RED), `b906f22` (feat, GREEN)

## Files Created/Modified

- `.planning/PROJECT.md` — corrects all active Phase 8 ceiling-scope claims.
- `.planning/REQUIREMENTS.md` — leaves FIDELITY-01 unchecked with its shipped-data predicate.
- `.planning/ROADMAP.md` — corrects Phase 8 success criterion 3.
- `.claude/theme-capture/README.md` — explains raw 26, shipped 25, Carlton and the protocol limit.
- `.planning/phases/08-hardware-fidelity-validation/tests/test_documentation_counts.py` — derives and protects the count boundary.

## Decisions Made

- The evidence-table identity remains the shipped ASCII slug, not raw emoji-bearing display names.
- The active-document scanner is intentionally limited to PROJECT, REQUIREMENTS, ROADMAP and the capture README; SPEC and PATTERNS retain historical stale-count quotations.

## Verification

- Focused Phase 8 documentation-count tests — 2 passed.
- Focused collection reported exactly 2 tests.
- `ruff check` passed for the new test module.
- The direct data check printed `25 shipped / 26 raw / Carlton excluded`.
- The scoped theme-data diff was empty; no hardware-facing command ran.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Normalised Markdown whitespace before matching active claims**
- **Found during:** Task 2
- **Issue:** The first document regression incorrectly treated valid line wrapping in the README as a missing `26 exactly-16-colour` or 17th-colour statement.
- **Fix:** Normalised document whitespace before semantic phrase checks.
- **Files modified:** `.planning/phases/08-hardware-fidelity-validation/tests/test_documentation_counts.py`
- **Verification:** Focused test suite passed 2/2.
- **Committed in:** `b906f22`

**Total deviations:** 1 auto-fixed (Rule 1).
**Impact on plan:** The test now checks the intended document content without making Markdown layout part of the contract.

## Issues Encountered

- The pre-commit Ruff hook removed an extra blank line from the RED test before it could be committed; the formatter adjustment was restaged and the intended RED failure was re-run.

## User Setup Required

None — no external configuration or hardware access was required.

## Next Phase Readiness

Plan 08-04 can consume a deterministic 25-slug FIDELITY-01 scope. Real hardware validation remains the required human-controlled next step.

## Self-Check: PASSED

- All five task files exist and the three task commits (`1c03c97`, `88cfaf4`, `b906f22`) are present in Git history.
- Focused documentation tests passed with exactly two collected tests.
