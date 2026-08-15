---
status: testing
phase: 07-taxonomy-legacy-dispositions
source: [07-VERIFICATION.md]
started: 2026-08-15T03:47:00Z
updated: 2026-08-15T03:47:00Z
---

## Current Test

number: 1
name: Library-category attribution wording
expected: |
  The synthetic `Library` category is always attributed to lifx-async ("defined by this
  library, not the app"; "not app captures"), never presented as a LIFX-app category.
  Sites to read: docs/migration/theme-taxonomy-v1.2.md (category section and Library table
  row, ~lines 30-31), src/lifx/theme/library.py (module docstring ~line 14, and the
  `get_by_category()` docstring).
awaiting: user response

## Tests

### 1. Library-category attribution wording
expected: The synthetic `Library` category is always attributed to lifx-async ("defined by this library, not the app"; "not app captures"), never presented as a LIFX-app category. Verifier's non-authoritative verdict: SATISFIED — exact quotes located at the migration page :30-31 and library.py :14.
result: [pending]

### 2. Disposition split provenance
expected: The 28 orphan dispositions are a verbatim copy of the SPEC R4 locked table with no independent judgement exercised — 9 deprecated pairs and 19 library-only keys exactly match. Verifier's non-authoritative verdict: SATISFIED with deterministic support — exact set equality machine-verified during this run.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
