---
phase: 15-coverage-gate-and-test-suite-health
plan: 03
subsystem: testing
tags: [coverage-gate, ci, patch-coverage, cobertura, codecov, pyright]

requires:
  - phase: 15-01
    provides: "The relocation shape (flat sibling import, tooling conftest sys.path bootstrap, module-level pytestmark, --tooling flag, testpaths reach, marker policy test) and .github/check_patch_coverage.py at its new location"
  - phase: 15-02
    provides: "The reduced --cov targets, the [tool.pyright] extraPaths entry, and a closed no-red-window across the relocated tree that this plan's task ordering depends on"
provides:
  - ".github/patch_coverage_guard.py, a CI guard that computes both the changed-measured and scored counts from repository data (a merge-base diff plus coverage.py's own source analysis) and fails only when the changed measured set is non-empty and none of it was scored"
  - "26 fixture-driven tests at .planning/scripts/tests/test_patch_coverage_guard.py covering every guard branch locally, with no pull request and no network"
  - "A wired 'Guard against a vacuous coverage gate' step in the designated ubuntu-latest plus Python 3.10 cell of ci.yml's test job, immediately after the Codecov coverage upload, with no failure-tolerance key"
  - "pyproject.toml [tool.pyright] include/extraPaths extended to cover both .github/ CI tools, filesAnalyzed now 96"
affects: ["15-04", "15-05"]

actuals:
  tokens: 11966
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Authoritative-denominator gate: the guard's changed-measured count comes from coverage.py's own analysis2() of the checked-out source under the project's own [tool.coverage.report] configuration, never from the report being judged, so a report that classifies nothing cannot shrink its own denominator to buy a pass"
    - "Best-effort cross-check that never decides the build: a live or replayed codecov/patch status is classified into agree/divergence/unusable and logged, but the exit code is always computed from the merge-base diff and coverage.xml before the status is read"
    - "Reuse-by-import with a documented private-API contract: two underscore-prefixed helpers (_added_numbers, _run_git) are imported from a sibling module in the same directory, with a code comment and an identity-check test pinning the coupling instead of duplicating the git invocation"
    - "Lazy shutil.which() resolution for an optional external tool (gh), so a test can prove a validation failure never reaches the point of consulting PATH for it"

key-files:
  created:
    - .github/patch_coverage_guard.py
    - .planning/scripts/tests/test_patch_coverage_guard.py
  modified:
    - pyproject.toml
    - .github/workflows/ci.yml

key-decisions:
  - "Cache the coverage.Coverage(config_file=...) object per repository root in a module-level dict, so a run touching several changed measured files parses pyproject.toml's exclude_lines once rather than once per file"
  - "Resolve the gh executable lazily via shutil.which() only when the live cross-check path is actually taken, rather than eagerly at import time like check_patch_coverage.py's GIT_EXECUTABLE, so a malformed --head can be proven to never consult PATH for it"
  - "The workflow-shape test (Task 2) skips rather than fails when the named CI step is absent from ci.yml, since Task 2 runs before Task 3 wires the step in; it starts asserting real content the moment Task 3 lands, with no further edit needed"

patterns-established:
  - "Vacuous-gate guards must derive their own denominator from source analysis, not from the artefact under judgement, whenever the artefact could legitimately be incomplete or wrong"

requirements-completed: [CI-02]

coverage:
  - id: D1
    description: "The guard fails a pull request whose changed measured lines went unscored, in both shapes the report can take (file absent, file present but nothing classified), and passes when they were scored or when every changed file is unmeasured"
    requirement: CI-02
    verification:
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_vacuous_file_absent_from_report"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_vacuous_file_present_but_classifies_no_changed_lines"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_scored_passes"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_unmeasured_only_passes_regardless_of_report"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_partial_scoring_warns_and_passes"
        status: pass
    human_judgment: false
  - id: D2
    description: "The authoritative changed-measured denominator comes from coverage.py's own source analysis under the project's configuration, never from the coverage report, so comment/blank/configured-exclusion-only changes pass regardless of the report's contents"
    requirement: CI-02
    verification:
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_comment_and_blank_only_change_passes_when_report_contains_file"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_comment_and_blank_only_change_passes_when_report_omits_file"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_configured_exclusion_only_change_passes"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_missing_source_on_disk_warns_and_does_not_fail_alone"
        status: pass
    human_judgment: false
  - id: D3
    description: "The guard derives its own changed-file set (no --source option) and reuses check_patch_coverage.py's diff parsing and added-line intersection by import, with no second implementation in the tree"
    requirement: CI-02
    verification:
      - kind: unit
        ref: "shell: build_parser() rejects an unrecognised --source argument"
        status: pass
      - kind: unit
        ref: "shell: identity check that CoverageEntry, PatchCoverageError, validate_base, diff_added_lines, _added_numbers and _run_git on patch_coverage_guard are the same objects as on check_patch_coverage"
        status: pass
      - kind: unit
        ref: "shell: grep for HUNK_HEADER or class AddedLine in patch_coverage_guard.py returns zero hits"
        status: pass
    human_judgment: false
  - id: D4
    description: "The Cobertura <source> adapter resolves both real coverage.xml shapes and refuses path-traversal via an outside <source>, falling back to the raw filename only when the document carries no <source> element at all"
    requirement: CI-02
    verification:
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_source_root_joining_src_rooted_shape"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_source_root_joining_repo_rooted_shape"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_source_root_traversal_refusal_contributes_no_entry"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_no_sources_element_falls_back_to_raw_filename"
        status: pass
    human_judgment: false
  - id: D5
    description: "The codecov/patch combined status is read only as a cross-check: divergence and agreement are logged from the two recorded description forms, and an unrecognised, absent or pending status is unusable, none of the four outcomes ever changing the exit code"
    requirement: CI-02
    verification:
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_cross_check_divergence_on_vacuous_description"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_cross_check_agreement_on_scored_description"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_cross_check_unusable_no_patch_entry"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_cross_check_unusable_pending_entry"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_cross_check_unusable_unrecognised_description"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every unreadable or malformed input (missing/invalid coverage report, malformed base, invalid head, missing pyproject.toml) fails closed with exit 2 rather than reading as an empty, passing set"
    requirement: CI-02
    verification:
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_missing_coverage_report_is_operational_error"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_malformed_base_is_operational_error"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_invalid_head_is_operational_error_before_any_subprocess"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_malformed_xml_report_is_operational_error"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_non_integer_hits_attribute_is_operational_error"
        status: pass
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_missing_pyproject_toml_is_operational_error"
        status: pass
    human_judgment: false
  - id: D7
    description: "The guard's measured-tree constants stay in lockstep with pyproject.toml and codecov.yml, checked by a dedicated drift test, and are type-checked by pyright alongside its sibling with a proven filesAnalyzed count"
    requirement: CI-02
    verification:
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_measured_tree_constants_match_project_configuration"
        status: pass
      - kind: unit
        ref: "shell: uv run --frozen pyright --outputjson reports filesAnalyzed 96 == expected 96, 0 errors"
        status: pass
    human_judgment: false
  - id: D8
    description: "The step is wired into the designated CI cell immediately after the Codecov upload, with no failure-tolerance key, correct permissions, and a fetch-depth expression that gives only that cell full history"
    requirement: CI-02
    verification:
      - kind: unit
        ref: ".planning/scripts/tests/test_patch_coverage_guard.py::test_ci_workflow_guard_step_carries_no_failure_tolerance"
        status: pass
      - kind: unit
        ref: "shell: step-order, permissions, fetch-depth and --status-timeout gates in this plan's Task 3 verify block"
        status: pass
    human_judgment: true
    rationale: "The step's structural correctness is fully proven locally, but whether it actually fires and reports sensible counts against a real pull request's diff and Codecov upload can only be observed on the phase's own pull request in live CI, which this plan cannot run."

duration: 33min
completed: 2026-09-06
status: complete
---

# Phase 15 Plan 03: Vacuous-Gate Guard Summary

**A CI guard that counts changed-measured and scored lines itself from a merge-base diff and coverage.py's own source analysis, wired into the designated ubuntu-latest plus Python 3.10 test cell right after the Codecov upload, with a codecov/patch cross-check that never decides the build.**

## Performance

- **Duration:** 33 min
- **Started:** 2026-09-05T22:49:34Z
- **Completed:** 2026-09-05T23:22:56Z
- **Tasks:** 3
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- `.github/patch_coverage_guard.py`: computes `changed_measured` and `scored` from repository
  data rather than from the coverage report being judged. The authoritative denominator comes
  from `coverage.Coverage(config_file="pyproject.toml").analysis2(path)` applied to the
  checked-out file, which already has the project's `exclude_lines` removed, so a report that
  classifies nothing cannot shrink its own denominator to buy a pass, while a docstring/comment/
  configured-exclusion-only change still passes cleanly.
- Reuses `check_patch_coverage.py`'s diff parsing and added-line intersection by import
  (`CoverageEntry`, `PatchCoverageError`, `validate_base`, `diff_added_lines`, `_added_numbers`,
  `_run_git`), with no second implementation of hunk parsing anywhere in the new file, and derives
  its own changed-file set from `git merge-base` rather than accepting a `--source` list, so it
  cannot inherit that tool's silent-skip gap.
- A Cobertura `<source>` adapter (`load_coverage_xml`) that resolves both real report shapes
  (`src`-rooted and repository-rooted), refuses a path-traversal candidate rather than re-keying
  it inside the repository, and falls back to the raw filename only when the document carries no
  `<sources>` element at all.
- A best-effort `codecov/patch` cross-check (`read_patch_status`) that classifies a live or
  replayed combined-status payload into agree/divergence/unusable against the two recorded
  description forms, and never changes the exit code the merge-base diff and coverage report
  already decided.
- 26 fixture-driven tests at `.planning/scripts/tests/test_patch_coverage_guard.py`, covering
  every branch above from a temporary Git repository, plus a configuration-drift test and a
  workflow-shape test, with no pull request and no network anywhere in the suite.
- A `Guard against a vacuous coverage gate` step wired into `ci.yml`'s `test` job, immediately
  after `Upload coverage to Codecov`, gated to the designated always-present cell, passing
  `--status-timeout 0` so the live cross-check performs one bounded read rather than polling for a
  result this plan predicts will not exist yet.

## Task Commits

Each task was committed atomically:

1. **Task 1: The guard, computing both sides from repository data** - `175d251` (feat)
2. **Task 2: Fixture-driven tests covering every guard branch locally** - `ac55cc4` (test)
3. **Task 3: Wire the guard into the designated ubuntu test cell** - `1de3827` (ci)

**Plan metadata:** committed alongside this summary.

## Files Created/Modified

- `.github/patch_coverage_guard.py` - the vacuous-gate guard: measured-tree constants, the
  Cobertura adapter, `authoritative_statements()`, `measured_changed_lines()`, the
  `codecov/patch` cross-check, and the CLI
- `.planning/scripts/tests/test_patch_coverage_guard.py` - 26 tests covering every guard branch
  from fixtures
- `pyproject.toml` - `[tool.pyright] include` gains `.github/patch_coverage_guard.py` and
  `.github/check_patch_coverage.py`; `extraPaths` gains `.github`; comment extended to name both
  files; no other key touched
- `.github/workflows/ci.yml` - `test` job gains a `permissions` block, the checkout step gains a
  `fetch-depth` expression for the designated cell, and the guard step is inserted after the
  Codecov coverage upload

## Decisions Made

- Cached the `coverage.Coverage` object per repository root at module scope, so a run touching
  several changed measured files parses `pyproject.toml`'s `exclude_lines` once.
- Resolved the `gh` executable lazily via `shutil.which()` only when the live cross-check path is
  actually taken, unlike `check_patch_coverage.py`'s eagerly-resolved `GIT_EXECUTABLE`, so a test
  can prove a malformed `--head` never reaches the point of consulting `PATH` for `gh`.
- The workflow-shape test (written in Task 2, before Task 3 wires the CI step) skips rather than
  fails when the named step is absent from `ci.yml`, then starts asserting real content the
  moment Task 3 lands, with no further edit to the test needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Bandit flagged the bare `xml.etree.ElementTree` import, not only the parse call**
- **Found during:** Task 1 (bandit verification before commit)
- **Issue:** The plan's action required annotating "the XML parse" (B314) but Bandit separately
  flags the blacklisted import itself (B405: `xml.etree.ElementTree`), which the plan text did not
  name explicitly.
- **Fix:** Added `# nosec B405` on the `from xml.etree import ElementTree` import line, alongside
  the existing `# nosec B314` on the `ElementTree.parse()` call, both attributing provenance to
  the job-produced `coverage.xml`.
- **Files modified:** `.github/patch_coverage_guard.py`
- **Verification:** `bandit -c pyproject.toml .github/patch_coverage_guard.py` reports zero issues
  (four suppressions accounted for: B404, B603, B314, B405).
- **Committed in:** `175d251` (Task 1 commit)

**2. [Rule 3 - Blocking] Pyright could not resolve `coverage.exceptions` from `import coverage` alone**
- **Found during:** Task 1 (pyright verification)
- **Issue:** `coverage.exceptions.NoSource` and `coverage.exceptions.CoverageException` are used as
  exception types, but pyright reported `reportAttributeAccessIssue` on `coverage.exceptions`
  since only `coverage` (not its `exceptions` submodule) was imported.
- **Fix:** Added `import coverage.exceptions` alongside `import coverage` inside the same
  try/except guard.
- **Files modified:** `.github/patch_coverage_guard.py`
- **Verification:** `uv run --frozen pyright` reports 0 errors.
- **Committed in:** `175d251` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3, blocking).
**Impact on plan:** Both were required to make the guard's own required checks (Bandit, pyright)
pass at all; neither changed the guard's behaviour or public surface. No scope creep.

## Issues Encountered

None beyond the two deviations documented above, both resolved during Task 1.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The guard is structurally proven end to end from fixtures: every branch in SPEC R4's acceptance
  list runs locally with no pull request. `uv run --frozen pytest -q` (4256 passed, 631
  deselected) and `uv run --frozen pytest --tooling -q` (4874 passed, 12 deselected) are both
  green; `.planning/scripts/tests/test_patch_coverage_guard.py` alone is 26/26 passed once the CI
  step exists. `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .` and
  `uv run --frozen pyright` (0 errors, `filesAnalyzed` 96) are all clean.
- `.planning/**` remains outside `ci.yml`'s `pull_request.paths` filter (T-15-31, accepted under
  D-09's manual-run model), so this guard's own fixture suite never runs in CI. The guard step
  itself fails closed if it is broken outright; the residual exposure is narrow: a regression
  that made `measured_changed_lines` *over-permissive* rather than broken would surface only at
  the next genuinely vacuous gate or the next manual `uv run --frozen pytest --tooling` run.
- `codecov.yml` is byte-identical to before this plan; `pyproject.toml`'s
  `[tool.coverage.run] omit`, `[tool.coverage.report] exclude_lines` and
  `[tool.pytest.ini_options] addopts` are unchanged, verified by a dedicated gate in Task 1's own
  `<verify>` block.
- The one item this plan cannot establish locally: whether the wired step actually fires and
  reports sensible counts against a real pull request's diff, and what the live `codecov/patch`
  cross-check reports there. That is observed on the phase's own pull request, not here.
- No blockers. Plans 15-04 (issue corrections) and 15-05 (reference sweep) can proceed against the
  tree as it now stands.

## Self-Check: PASSED

- `test -f .github/patch_coverage_guard.py` -> FOUND
- `test -f .planning/scripts/tests/test_patch_coverage_guard.py` -> FOUND
- `git log --oneline --all | grep -q 175d251` -> FOUND
- `git log --oneline --all | grep -q ac55cc4` -> FOUND
- `git log --oneline --all | grep -q 1de3827` -> FOUND
- `uv run --frozen pytest .planning/scripts/tests/test_patch_coverage_guard.py --no-cov -q` -> 26 passed
- `uv run --frozen pytest -q` -> 4256 passed, 631 deselected
- `uv run --frozen pytest --tooling -q` -> 4874 passed, 12 deselected
- `uv run --frozen pyright` -> 0 errors, filesAnalyzed 96 == expected 96
- `uv run --frozen ruff check .` -> All checks passed
- `uv run --frozen ruff format --check .` -> 283 files already formatted
- `bandit -c pyproject.toml .github/patch_coverage_guard.py` -> No issues identified
- Coverage-config-untouched gate -> COVERAGE-CONFIG-UNTOUCHED
- Configuration-drift sensitivity check (fifth `omit` entry, third `--cov=` target) -> both
  independently fail the drift test as expected; both reverted before commit
- Vacuous-comparison inversion sensitivity check -> both the vacuous and unmeasured-only tests
  fail as expected; reverted before commit

---
*Phase: 15-coverage-gate-and-test-suite-health*
*Completed: 2026-09-06*
