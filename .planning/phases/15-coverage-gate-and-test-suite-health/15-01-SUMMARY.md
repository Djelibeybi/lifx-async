---
phase: 15-coverage-gate-and-test-suite-health
plan: 01
subsystem: testing
tags: [pytest, ci-tooling, coverage, collection-hooks]

requires:
  - phase: none
    provides: n/a (first plan in phase, no dependencies)
provides:
  - "check_patch_coverage.py relocated to .github/, its test relocated to .planning/scripts/tests/"
  - "A local conftest.py bootstrapping flat sibling imports for the tooling test tree"
  - "An opt-in flag mechanism (--tooling, --benchmark) replacing the -m \"not benchmark\" filter"
  - "A policy test asserting the new mechanism structurally, including the module-level marker"
affects: [15-02, 15-03, 15-04, 15-05]

actuals:
  tokens: 3248
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Opt-in marker deselection via pytest_collection_modifyitems(config, items), reported through config.hook.pytest_deselected"
    - "Flat sibling imports from a directory conftest.py that inserts sys.path entries derived only from Path(__file__).resolve()"
    - "Structural (ast-based) assertion of a module-level marker instead of a substring search"

key-files:
  created:
    - .planning/scripts/tests/conftest.py
  modified:
    - .github/check_patch_coverage.py (relocated, content unchanged)
    - .planning/scripts/tests/test_check_patch_coverage.py (relocated, import + marker added)
    - tests/conftest.py
    - tests/test_pytest_policy.py
    - pyproject.toml
    - .pre-commit-config.yaml

key-decisions:
  - "D-09: deselection via opt-in flags through the existing collection hook, not a growing -m negation"
  - "Extended bandit's pre-commit exclude to also cover .planning/scripts/tests/, since those test files were only ever exempted by their old tests/ path"
  - "Task 1's commit folds in the tests/test_pytest_policy.py caller-signature fix so the default suite is never red, per the plan's explicit no-red-window requirement"

requirements-completed: [CI-01]

coverage:
  - id: D1
    description: "check_patch_coverage.py lives only at .github/check_patch_coverage.py; its test lives only under .planning/scripts/tests/"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "shell: git ls-files scripts/check_patch_coverage.py tests/test_scripts/test_check_patch_coverage.py (empty output)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Default pytest run imports then deselects the tooling test, reporting a non-zero deselected count; --tooling re-admits it; an unmarked item is never deselected"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "tests/test_pytest_policy.py::test_deselection_hook_drops_opt_in_items_with_all_flags_off"
        status: pass
      - kind: unit
        ref: "tests/test_pytest_policy.py::test_deselection_hook_readmits_tooling_when_its_flag_is_set"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen pytest -q (4805 passed, 56 deselected); uv run --frozen pytest --tooling -q (4849 passed, 12 deselected)"
        status: pass
    human_judgment: false
  - id: D3
    description: "addopts carries no -m expression at all; the marker/flag table is complete in both directions"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "tests/test_pytest_policy.py::test_addopts_carries_no_marker_expression"
        status: pass
      - kind: unit
        ref: "tests/test_pytest_policy.py::test_opt_in_marker_flags_are_fully_registered"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every tooling test module declares pytestmark = pytest.mark.tooling at module scope, verified structurally (ast), not by substring search"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "tests/test_pytest_policy.py::test_every_tooling_test_module_declares_the_marker_at_module_scope"
        status: pass
    human_judgment: false
  - id: D5
    description: "No commit in this plan leaves the default suite red: the hook signature change and its two positional callers land in the same commit as Task 1"
    requirement: CI-01
    verification:
      - kind: integration
        ref: "shell: uv run --frozen pytest -q run after Task 1's commit and again after Task 2's commit, both green"
        status: pass
    human_judgment: false

duration: 27min
completed: 2026-09-05
status: complete
---

# Phase 15 Plan 01: Tracer relocation of check_patch_coverage.py Summary

**Moved `check_patch_coverage.py` to `.github/` and its test to `.planning/scripts/tests/`, replacing the `-m "not benchmark"` collection filter with opt-in `--tooling`/`--benchmark` flags driven through the existing `pytest_collection_modifyitems` hook.**

## Performance

- **Duration:** 27 min
- **Started:** 2026-09-05T21:49:59Z
- **Completed:** 2026-09-05T22:17:04Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- `check_patch_coverage.py` now lives only at `.github/check_patch_coverage.py`; its test lives
  only under `.planning/scripts/tests/test_check_patch_coverage.py`, with a local `conftest.py`
  that bootstraps three flat sibling-import roots (`.planning/scripts`, `.github`, repo root)
  from `Path(__file__).resolve()`, with no `os.getcwd()` or environment-variable dependence.
- The default pytest run collects then deselects the relocated tooling test (and the existing
  benchmark tests), reporting the drop through `config.hook.pytest_deselected` so it stays visible
  in the summary as a "deselected" count instead of silently vanishing. `--tooling` and
  `--benchmark` each independently re-admit their own category.
- `tests/conftest.py`'s `pytest_collection_modifyitems` hook signature widened to `(config,
  items)`; the two positional callers in `tests/test_pytest_policy.py` were fixed in the same
  commit as the signature change, so no commit in this plan ever leaves the default suite unable
  to run itself.
- `tests/test_pytest_policy.py` gained six new tests: `addopts` carries no `-m` expression, the
  `_OPT_IN_MARKER_FLAGS` table is complete in both directions (every marker is registered, every
  flag is known to the parser), the deselection branch drops and re-admits items correctly under
  both flag states, and every relocated tooling test module declares its marker at module scope
  -- verified with `ast.parse` over `Module.body` rather than a substring search, so a marker
  hidden in a comment, a docstring, or a function body still fails the check.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end tooling relocation on one subject, wired through collection** -
   `4631c36` (feat), with a staging-omission fix landed immediately after in `3ddd91a` (fix)
2. **Task 2: Make the pytest policy test assert the new mechanism** - `f40efdf` (test)

_Note: Task 1's own commit initially omitted the working-tree edit to the relocated test file's
import line and marker (a `git add` pathspec error aborted an earlier attempt to stage it, and the
narrower follow-up `git add` never re-included that file). The gap was caught before Task 2 began
and closed in `3ddd91a`; both commits are documented above rather than squashed, per this
executor's no-amend policy._

## Files Created/Modified

- `.github/check_patch_coverage.py` - relocated maintainer CI tool, content unchanged
- `.planning/scripts/tests/conftest.py` - new; bootstraps `.planning/scripts`, `.github` and the
  repo root onto `sys.path` at collection, with a comment recording that this is an
  initial-argument conftest reached through `testpaths` and therefore session-wide
- `.planning/scripts/tests/test_check_patch_coverage.py` - relocated test; import rewritten to
  `import check_patch_coverage as checker`, `pytestmark = pytest.mark.tooling` added
- `tests/conftest.py` - `--tooling`/`--benchmark` flags registered, `_OPT_IN_MARKER_FLAGS` table
  added, `pytest_collection_modifyitems` widened to accept `config` and gained a deselection
  branch
- `tests/test_pytest_policy.py` - caller sites updated for the new hook signature; six new tests
  asserting the replacement mechanism
- `pyproject.toml` - `testpaths` gained `.planning/scripts/tests`; `-m "not benchmark"` removed
  from `addopts`; `tooling` marker added; `benchmark` marker description reworded to name
  `--benchmark` and drop its em dash
- `.pre-commit-config.yaml` - bandit's `exclude` pattern widened to also cover
  `.planning/scripts/tests/`, since those files were only ever exempted by their old `tests/` path

## Decisions Made

- Kept the bandit pre-commit exclude fix scoped to widening the existing `tests/`-only pattern
  rather than inventing a new exemption mechanism, since the relocated files are ordinary test
  files that happened to change path.
- Did not squash the staging-omission fix commit into Task 1's commit; created a new commit
  instead, per the no-amend rule, and documented both hashes against Task 1 in this summary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] bandit pre-commit hook failed on the relocated tooling test**
- **Found during:** Task 1 (first commit attempt)
- **Issue:** `.pre-commit-config.yaml`'s bandit hook excluded `^tests/` only. The relocated test
  file at `.planning/scripts/tests/test_check_patch_coverage.py` no longer matched that exclude
  and bandit flagged its `subprocess.run(["git", ...])` calls (B404/B603/B607), none of which are
  new code -- the same calls existed unflagged at the old `tests/test_scripts/` path.
- **Fix:** Widened the bandit `exclude` regex to `^(tests/|\.planning/scripts/tests/)`.
- **Files modified:** `.pre-commit-config.yaml`
- **Verification:** `git commit -S -s` succeeded on retry with the bandit hook passing.
- **Committed in:** `4631c36` (part of Task 1's commit)

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** Necessary to make the relocation commit-able at all; no scope creep beyond
the one exclude-pattern line.

## Issues Encountered

- An earlier `git add` invocation listing both a since-renamed path and several still-pending
  paths failed atomically with `fatal: pathspec ... did not match any files`, and the narrower
  retry that followed never re-included the relocated test file's content edit. Task 1's first
  commit therefore landed the bare `git mv` without the import/marker edit. Caught via a
  post-commit `git diff HEAD~1..HEAD` inspection before proceeding to Task 2, and closed with a
  small follow-up commit (`3ddd91a`) rather than an amend.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The relocation shape (flat sibling import, local conftest path bootstrap, module-level marker,
  opt-in flag through the existing collection hook, testpaths reach, policy test) is proven end
  to end on one subject and ready for plan 15-02 to repeat across the remaining five scripts and
  three test files.
- `pyproject.toml`'s `--cov=scripts.measurement_support` and `--cov=scripts.thread_revalidation`
  targets, and the `[tool.pyright] include` entries for the four scripts still in `scripts/`, are
  deliberately untouched here -- they belong to plan 15-02/15-03's measured-tree work.
- No blockers.

## Self-Check: PASSED

- `test -e .github/check_patch_coverage.py` -> FOUND
- `test -e .planning/scripts/tests/conftest.py` -> FOUND
- `test -e .planning/scripts/tests/test_check_patch_coverage.py` -> FOUND
- `git log --oneline --all | grep -q 4631c36` -> FOUND
- `git log --oneline --all | grep -q 3ddd91a` -> FOUND
- `git log --oneline --all | grep -q f40efdf` -> FOUND
- `uv run --frozen pytest -q` -> 4805 passed, 56 deselected
- `uv run --frozen pytest --tooling -q` -> 4849 passed, 12 deselected
- `uv run --frozen pyright` -> clean (0 errors, 0 warnings)
- `uv run --frozen ruff check .` -> All checks passed
- `uv run --frozen ruff format --check .` -> 284 files already formatted

---
*Phase: 15-coverage-gate-and-test-suite-health*
*Completed: 2026-09-05*
