---
status: complete
phase: 07-taxonomy-legacy-dispositions
source: [07-VERIFICATION.md]
started: 2026-08-15T03:47:00Z
updated: 2026-08-15T04:01:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Library-category attribution wording
expected: The synthetic `Library` category is always attributed to lifx-async ("defined by this library, not the app"; "not app captures"), never presented as a LIFX-app category. Verifier's non-authoritative verdict: SATISFIED — exact quotes located at the migration page :30-31 and library.py :14.
result: pass
history:
  - result: issue
    reported: "The v1.2 milestone version has no meaning outside this repo's internal planning so it should be replaced by a date, or a lifx-async release version"
    severity: major
    note: The attribution wording itself read correctly at both sites; the defect found while reading them was a separate one — internal milestone numbering (`v1.2`) leaking into shipped docs and source docstrings. Tracked as G-07-1.
  - result: pass
    note: Re-tested after G-07-1 was fixed in a97796d. Attribution confirmed at docs/migration/theme-taxonomy-6.4.0.md:30-31 (prose plus the table's `Defined by` column), src/lifx/theme/library.py:14 ("not app captures") and :182 (get_by_category() docstring).

### 2. Disposition split provenance
expected: The 28 orphan dispositions are a verbatim copy of the SPEC R4 locked table with no independent judgement exercised — 9 deprecated pairs and 19 library-only keys exactly match. Verifier's non-authoritative verdict: SATISFIED with deterministic support — exact set equality machine-verified during this run.
result: pass
confirmed: data/themes.jsonl re-counted during UAT — 138 lifx-app / 19 library-only / 9 deprecated across 166 records, matching the SPEC R4 locked table.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0
issues_found_and_resolved: 1
deferred_follow_ups: 1

## Gaps

- gap_id: G-07-1
  truth: "User-facing docs and docstrings identify the taxonomy migration by a reference meaningful outside this repository"
  status: resolved
  resolved_by: "direct fix during UAT (no gap-closure plan — mechanical rename, decision locked by user)"
  resolved_at: 2026-08-15
  resolution: "docs/migration/theme-taxonomy-v1.2.md renamed to theme-taxonomy-6.4.0.md; all v1.2 references replaced with 6.4.0 across the migration page, docs/api/themes.md, src/lifx/theme/library.py (including the get_by_category() ValueError text), mkdocs.yml nav and llmstxt paths, and the two theme test modules that pin the error string. Also replaced the unrelated `v2.0 decision` milestone leak on the migration page with `major-version decision`. Verified: full suite passes, pyright 0 errors, ruff clean, zensical build reports no issues (no dead link to the old path)."
  reason: "User reported: The v1.2 milestone version has no meaning outside this repo's internal planning so it should be replaced by a date, or a lifx-async release version"
  severity: major
  test: 1
  root_cause: "`v1.2` is the .planning/ milestone number for the Theme Library Update milestone, not a lifx-async release. The library ships at 6.2.0 (pyproject.toml:3, latest tag v6.2.0). Phase 7 authored the migration page and the library.py docstrings using the internal milestone label, so 18 references across 5 files leak internal planning vocabulary into published output."
  artifacts:
    - path: "docs/migration/theme-taxonomy-v1.2.md"
      issue: "Filename, H1 title, and 8 body references use v1.2 (:1, :5, :7, :23, :25, :31, :52, :71, :90, :94, :121)"
    - path: "docs/api/themes.md"
      issue: "3 references plus a link to the v1.2-named page (:69, :70, :72, :73)"
    - path: "src/lifx/theme/library.py"
      issue: "7 references in shipped docstrings and a user-visible error message (:6, :15, :31, :53, :182, :184, :193, :210)"
    - path: "mkdocs.yml"
      issue: "llmstxt include and nav entry point at the v1.2-named path (:151, :226)"
  missing:
    - "Rename docs/migration/theme-taxonomy-v1.2.md to theme-taxonomy-6.4.0.md (git mv)"
    - "Replace every `v1.2` with `6.4.0` across the four files, including the get_by_category() ValueError text"
    - "Update mkdocs.yml nav and llmstxt paths to the new filename"
    - "No redirect for the old URL — the page is unreleased (branch chore/theme-taxonomy, absent from 6.2.0)"
  decision: "User selected a release version over a date; no redirect for the old URL (the page has never shipped in a release)."
  version_correction: "First applied as 6.3.0 in db1ae95, computed from a stale local checkout where `git tag` reported v6.2.0 and pyproject.toml read 6.2.0. A fetch during /gsd-ship revealed origin/main already carried ca52da5 \"6.3.0\" (python-semantic-release, 2026-08-15 00:58 UTC) and tag v6.3.0 — Phase 6's release from PR #196. 6.3.0 was therefore a version that shipped BEFORE this work, the same class of error the gap was raised to fix. Corrected to 6.4.0 after rebasing onto origin/main, which brought pyproject.toml to 6.3.0 locally so the next-version computation is verifiable from the tree rather than remembered. Lesson: fetch before deriving a version from tags or pyproject.toml."
  debug_session: ""

## Deferred Follow-Ups

- test: 2
  idea: "There are em dashes in docs/api/themes.md — user expected a no-em-dash rule to already apply repo-wide. Raised while reading for test 2; not a verdict on that test."
  scope: "Repo-wide house style, not a Phase 7 regression: ~200 em dashes across docs/ (44 in docs/api/effects.md, 42 in docs/user-guide/effects.md). In docs/api/themes.md only :71 came from Phase 7 (b299464); :41 predates it (47e2864). No no-em-dash rule is recorded anywhere in the repo."
  resolution_preference: "Recast each sentence so no dash is needed (commas, colons, brackets, or a sentence split per case) rather than swapping the character."
  deferred_at: 2026-08-15
  deferred_by: user
