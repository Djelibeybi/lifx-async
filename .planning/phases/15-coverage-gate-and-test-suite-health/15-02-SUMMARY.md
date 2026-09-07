---
phase: 15-coverage-gate-and-test-suite-health
plan: 02
subsystem: testing
tags: [ci-tooling, coverage, pyright, pep723, uv, privacy]

requires:
  - phase: 15-01
    provides: "The relocation shape (flat sibling import, tooling conftest sys.path bootstrap, module-level pytestmark, --tooling flag, testpaths reach, marker policy test) proven end to end on check_patch_coverage.py"
provides:
  - "The five operator measurement and audit scripts relocated to .planning/scripts/, scripts/ holding only generate_theme_data.py"
  - "mdns_probe.py and test_multiversion.py deleted; tests/test_scripts/ gone"
  - "Flat sibling imports and PEP 723 headers on all five relocated scripts, resolving from their new location with no sys.path bootstrap and no new pythonpath entry"
  - "The two default-suite library tests (test_discovery_observation.py, test_connection_retry.py) repointed at the relocated measurement_support via a root tests/conftest.py sys.path insert, passing under both a full run and a targeted single-file invocation"
  - "The three relocated tooling tests repointed at their flat-imported subjects and marked pytest.mark.tooling"
  - "pyproject.toml's --cov targets reduced to exactly lifx and generate_theme_data; [tool.pyright] include/extraPaths updated for the new tree"
  - "Four privacy scans and a repository-wide stale-path sweep, each a gate rather than a printout, confirming the relocation carried no hardware identifier and no old-path reference"
affects: [15-03, 15-04, 15-05]

actuals:
  tokens: 18058
  tasks: 4
  commits: 4

tech-stack:
  added: []
  patterns:
    - "PEP 723 [tool.uv.sources] editable path rebased one level deeper (../../) for scripts moved from scripts/ to .planning/scripts/"
    - "Flat sibling import resolution via Path(__file__).resolve()-derived sys.path inserts, distinct for direct execution (sys.path[0]), tooling tests (conftest beside them), and default-suite library tests (root tests/conftest.py, reached under any invocation including a targeted single-file run)"
    - "Privacy scans as gates: git ls-files --cached --others --exclude-standard over the relocated tree, subtracting a measured inventory and exiting non-zero on residue, rather than printing a list for a reader to compare"
    - "Stale-path sweep via normalise-and-rematch: git grep finds candidates, sed rewrites .planning/scripts/ to a token holding no scripts/, then grep re-applies the same pattern so only genuinely stale references survive"

key-files:
  created: []
  modified:
    - .planning/scripts/ipv6_thread_probe.py
    - .planning/scripts/measure_merged_discovery.py
    - .planning/scripts/measurement_support.py
    - .planning/scripts/serial_mac_audit.py
    - .planning/scripts/thread_revalidation.py
    - .planning/scripts/tests/test_ipv6_thread_probe.py
    - .planning/scripts/tests/test_measure_merged_discovery.py
    - .planning/scripts/tests/test_thread_revalidation.py
    - tests/conftest.py
    - tests/test_discovery_observation.py
    - tests/test_network/test_connection_retry.py
    - src/lifx/network/connection.py
    - pyproject.toml
  deleted:
    - scripts/mdns_probe.py
    - scripts/test_multiversion.py
    - tests/test_scripts/__init__.py

key-decisions:
  - "Task 1's pure-rename commit necessarily includes a small pre-commit-forced isort reorder in five of the eight moved files: ruff's import sorter no longer treats scripts.* as first-party once the file's own directory is no longer scripts/, so it fires before the import name itself is even touched. Accepted as unavoidable (the same hook re-fires identically on any retry) rather than bypassed; git still recorded all eight moves as renames at 99-100% similarity."
  - "Adding [tool.pyright] extraPaths (a locked acceptance criterion) surfaced a pre-existing reportPrivateImportUsage diagnostic on ipv6_thread_probe.py's mdns_discovery.MdnsTransport monkeypatch, previously untriggered because pyright treats a file's own directory as an implicit search root without extraPaths. Suppressed with a targeted `# type: ignore[reportPrivateImportUsage]` rather than exporting the symbol from library code, since the script's own docstring already documents this as a deliberate reach into private internals."
  - "Task 3's own literal verify command (a plain grep for scripts/measurement_support\\.py etc.) is a false positive against its own required edits: it has no anchor to distinguish scripts/measurement_support.py from the substring inside .planning/scripts/measurement_support.py, so the docstring citations Task 3's action explicitly requires trip it. Verified actual cleanliness instead using Task 4's normalise-and-rematch technique (already present in this same plan for exactly this class of defect), confirming zero genuinely stale references."

requirements-completed: [CI-01]

coverage:
  - id: D1
    description: "The five measurement/audit scripts and their three tooling tests moved to .planning/scripts/ by git mv (99-100% rename similarity); mdns_probe.py, test_multiversion.py and tests/test_scripts/__init__.py deleted; scripts/ holds only generate_theme_data.py"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "shell: ls scripts/*.py (scripts/generate_theme_data.py only); git ls-files .planning/scripts/ (10 files); git ls-files | grep -E 'mdns_probe|test_multiversion|test_scripts/' (empty)"
        status: pass
    human_judgment: false
  - id: D2
    description: "All five relocated scripts use flat sibling imports (from measurement_support import ...) and carry PEP 723 headers with a [tool.uv.sources] editable path rebased to ../../; pyproject.toml addopts carries exactly --cov=lifx and --cov=generate_theme_data"
    requirement: CI-01
    verification:
      - kind: integration
        ref: "shell: uv run .planning/scripts/{ipv6_thread_probe,measure_merged_discovery,thread_revalidation}.py --help (all exit 0); uv run --frozen pyright (0 errors, filesAnalyzed 94 == expected 94)"
        status: pass
      - kind: unit
        ref: "shell: grep -c -- '--cov=' pyproject.toml (2: lifx, generate_theme_data)"
        status: pass
    human_judgment: false
  - id: D3
    description: "tests/test_discovery_observation.py and tests/test_network/test_connection_retry.py import measurement_support flatly, resolved via a root tests/conftest.py sys.path insert; both pass under a targeted single-file invocation as well as the full suite"
    requirement: CI-01
    verification:
      - kind: integration
        ref: "shell: uv run --frozen pytest tests/test_discovery_observation.py -q --no-cov (9 passed); uv run --frozen pytest tests/test_network/test_connection_retry.py -q --no-cov (36 passed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The three relocated tooling tests are repointed at flat-imported subjects, carry pytestmark = pytest.mark.tooling, and the full default and --tooling suites are green; four privacy scans and a repository-wide sweep confirm no hardware identifier or stale path survived the relocation"
    requirement: CI-01
    verification:
      - kind: integration
        ref: "shell: uv run --frozen pytest -q (4256 passed, 605 deselected); uv run --frozen pytest --tooling -q (4849 passed, 12 deselected); uv run --frozen pytest .planning/scripts/tests --no-cov -q (593 passed)"
        status: pass
      - kind: unit
        ref: "shell: four privacy scans over git ls-files --cached --others --exclude-standard .planning/scripts (SERIAL-SCAN-OK 20, IPV4-SCAN-OK 17, MAC-SCAN-OK 19, IPV6-SCAN-OK 5); repo-wide sweep (SWEEP-CLEAN); sweep fixture (matched=4)"
        status: pass
    human_judgment: false

duration: 23min
completed: 2026-09-05
status: complete
---

# Phase 15 Plan 02: Relocate the Remaining Measurement Scripts Summary

**Moved the five operator hardware measurement/audit scripts and their tooling tests to `.planning/scripts/`, deleted two dead scripts, converted every `scripts.`-qualified import to a flat sibling import with a PEP 723 header, repointed the two default-suite library tests that consume `measurement_support`, and reduced `pyproject.toml`'s `--cov` targets to exactly `lifx` and `generate_theme_data`.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-09-05T22:23:36Z
- **Completed:** 2026-09-05T22:46:44Z
- **Tasks:** 4
- **Files touched:** 16 (8 renamed, 3 deleted, 5 modified in place)

## Accomplishments

- `scripts/` now holds exactly `generate_theme_data.py`; `.planning/scripts/` holds the five
  relocated measurement/audit scripts plus a `tests/` directory of ten files (three relocated by
  this plan, two already there from plan 15-01). `mdns_probe.py`, `test_multiversion.py` and the
  now-empty `tests/test_scripts/__init__.py` are deleted. All eight file moves were recorded by
  git as renames at 99-100% similarity, preserving `git log --follow` history.
- Every `scripts.measurement_support`/`scripts.thread_revalidation` import in the five relocated
  scripts became a flat sibling import (`from measurement_support import ...`), resolving via
  Python's own `sys.path[0]` placement for direct execution with no `sys.path` bootstrap and no
  new `pythonpath` entry. Four scripts gained a PEP 723 header (`ipv6_thread_probe.py`,
  `measure_merged_discovery.py`, `measurement_support.py`, `thread_revalidation.py`);
  `serial_mac_audit.py`'s existing header had its `[tool.uv.sources]` path rebased from `../` to
  `../../` for the one-level-deeper location. Every prose and comment citation of an old
  `scripts/...` path across the five files was corrected.
- `tests/test_discovery_observation.py` and `tests/test_network/test_connection_retry.py`, the
  two **default-suite library tests** that import `measurement_support` at module scope, were
  repointed to a flat import, resolved through a new sys.path insert in the root
  `tests/conftest.py` (not the tooling conftest, which a targeted single-file invocation never
  loads). Both pass standalone as well as inside the full suite. `src/lifx/network/connection.py`'s
  two stale path citations (a seam comment and a docstring) were corrected to the flat module name.
- The three relocated tooling tests had every `scripts.`-qualified reference (imports, `patch()`
  target strings, one `runpy.run_module` call, 33 references total) rewritten to the flat form,
  and each gained module-scope `pytestmark = pytest.mark.tooling`, closing the marker-policy test
  plan 15-01 added. `pyproject.toml`'s `[tool.pyright] include`/`extraPaths` were updated for the
  new tree and `addopts` now names exactly `--cov=lifx` and `--cov=generate_theme_data`.
- Four privacy scans (serial, IPv4, MAC, IPv6 shapes) and a repository-wide stale-path sweep, each
  a gate that exits non-zero on residue rather than a printout, confirmed the relocated tree on
  disk carries exactly the recorded synthetic inventories (20/17/19/5 values respectively) and no
  reference to an old `scripts.`-qualified or `scripts/`-pathed name survives anywhere in tracked
  code.

## Task Commits

Each task was committed atomically:

1. **Task 1: Relocate the five scripts and their tests, delete the two dead scripts** -
   `52e489b` (feat)
2. **Task 2: Flat sibling imports, PEP 723 headers, and the pyproject configuration for the new
   tree** - `7f311c5` (feat)
3. **Task 3: Repoint the two default-suite consumers of measurement_support and the library
   comments that cite it** - `d6e58a6` (fix)
4. **Task 4: Repoint the relocated tooling tests and inspect the moved tree for hardware
   identifiers** - `eb764b0` (fix)

## Files Created/Modified

- `.planning/scripts/{ipv6_thread_probe,measure_merged_discovery,measurement_support,serial_mac_audit,thread_revalidation}.py` -
  relocated, flat imports, PEP 723 headers, corrected path citations; `measure_merged_discovery.py`
  also had a directory-depth bug fixed in `_load_alias_map()`
- `.planning/scripts/tests/{test_ipv6_thread_probe,test_measure_merged_discovery,test_thread_revalidation}.py` -
  relocated, flat imports/patch targets, `pytestmark = pytest.mark.tooling` added
- `tests/conftest.py` - new `.planning/scripts` sys.path insert serving the two default-suite
  library consumers of `measurement_support`
- `tests/test_discovery_observation.py`, `tests/test_network/test_connection_retry.py` - flat
  imports, corrected docstring path citations
- `src/lifx/network/connection.py` - two stale path citations corrected (comment, docstring)
- `pyproject.toml` - `[tool.pyright] include`/`extraPaths` updated for the new tree; `addopts`
  drops the two `--cov=scripts.*` targets
- `scripts/mdns_probe.py`, `scripts/test_multiversion.py`, `tests/test_scripts/__init__.py` -
  deleted

## Decisions Made

- Accepted the pre-commit-forced isort reorder in Task 1's commit (see key-decisions above)
  rather than fighting an unavoidable, mechanically-identical re-trigger.
- Suppressed the `extraPaths`-surfaced `reportPrivateImportUsage` diagnostic with a targeted
  `type: ignore` comment on the one monkeypatch line, rather than exporting the private symbol
  from library code or dropping the locked `extraPaths` acceptance criterion.
- Verified Task 3's "no stale reference" intent via Task 4's normalise-and-rematch sweep rather
  than Task 3's own literal grep, which is a false positive against Task 3's own required edits
  (see key-decisions above).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-commit ruff hook forces an isort reorder in five of the eight moved files**
- **Found during:** Task 1 (first commit attempt)
- **Issue:** ruff's import sorter no longer classifies `scripts.measurement_support`/
  `scripts.thread_revalidation` as first-party once the importing file's own directory is
  `.planning/scripts/` rather than `scripts/`, so it reorders the import block relative to
  `lifx.*` imports. This fires purely from the location change, before Task 2 even touches the
  import name, and re-fires identically on any retry (restoring the original content and
  recommitting reproduces the same hook failure).
- **Fix:** Accepted the mechanical reorder (verified as import-block-only via diff inspection, no
  logic change) as part of Task 1's commit.
- **Files modified:** `.planning/scripts/ipv6_thread_probe.py`, `measure_merged_discovery.py`,
  `thread_revalidation.py`, `tests/test_measure_merged_discovery.py` (as staged then, now
  `.planning/scripts/tests/`), `tests/test_thread_revalidation.py` (as staged then)
- **Verification:** `git status --short` still shows all eight moves as `R` renames after the
  reorder; `git diff --cached -M --stat` confirms 99-100% similarity.
- **Committed in:** `52e489b` (Task 1's commit)

**2. [Rule 1 - Bug] `_load_alias_map()`'s repository-root computation was one directory level too shallow**
- **Found during:** Task 4 (full `--tooling` suite run)
- **Issue:** `measure_merged_discovery.py`'s `_load_alias_map()` computed the repository root as
  `Path(__file__).resolve().parents[1]`, correct when the file lived at `scripts/` (one level
  below repo root) but one level too shallow now that it lives at `.planning/scripts/` (two
  levels below). This silently stopped the function from rejecting an alias-map path inside the
  repository, failing `test_alias_map_must_be_external_and_normalises_serials`.
- **Fix:** Changed `parents[1]` to `parents[2]`.
- **Files modified:** `.planning/scripts/measure_merged_discovery.py`
- **Verification:** `uv run --frozen pytest .planning/scripts/tests/test_measure_merged_discovery.py`
  (53 passed); full `--tooling` suite re-run (4849 passed, 12 deselected).
- **Committed in:** `eb764b0` (Task 4's commit)

**3. [Rule 3 - Blocking] `extraPaths` surfaces a pre-existing `reportPrivateImportUsage` diagnostic**
- **Found during:** Task 2 (pyright verify)
- **Issue:** Adding `[tool.pyright] extraPaths = [".planning/scripts"]` (a locked acceptance
  criterion) changes pyright's execution-environment resolution enough that
  `ipv6_thread_probe.py:536`'s pre-existing `mdns_discovery.MdnsTransport` monkeypatch (unchanged
  since before this plan, confirmed by diffing against the pre-Phase-15 committed content) starts
  reporting `reportPrivateImportUsage`. Without `extraPaths` the same line is clean, but
  `extraPaths` is required by the plan's own acceptance criteria.
- **Fix:** Added a targeted `# type: ignore[reportPrivateImportUsage]` on the one read access,
  since the script's own module docstring already documents this file as deliberately reaching
  into private library internals.
- **Files modified:** `.planning/scripts/ipv6_thread_probe.py`
- **Verification:** `uv run --frozen pyright` (0 errors, `filesAnalyzed` 94 == expected 94).
- **Committed in:** `7f311c5` (Task 2's commit)

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug).
**Impact on plan:** All three were necessary to complete the relocation without weakening any
check or leaving the pre-existing behaviour silently broken. No scope creep: each fix is scoped to
the exact line the relocation itself perturbed.

## Privacy Inspection Record

Per `AGENTS.md`'s privacy rule and this plan's task 4 requirement, a staged-diff inspection for
hostnames and account names (the two categories no automated shape scan can enumerate) was
performed by hand before each of this plan's four commits. Nothing was found in any of the four:
the diffs contain only path citations, module names, dependency declarations, and the pre-existing
`_lifx._udp.local` DNS-SD service-name constant (not a real hostname). The four automated shape
scans (serial, IPv4, MAC, IPv6) additionally confirmed the relocated tree on disk carries exactly
the twenty/seventeen/nineteen/five recorded synthetic values and nothing else.

## Issues Encountered

None beyond the three deviations documented above, all resolved during execution.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `scripts/` now holds only code CI executes (`generate_theme_data.py`); the measured-tree rule
  plan 15-03 states in `AGENTS.md` prose has a tree to describe.
- `codecov/project` staying at or above its 90% target after dropping the two `--cov=scripts.*`
  targets is the one acceptance item this plan cannot establish locally: it is checked on the
  phase's pull request per the plan's own `<verification>` section, not by any command run here.
- No blockers. Plans 15-03 (vacuous-gate guard), 15-04 (issue corrections) and 15-05 (reference
  sweep across `AGENTS.md` and planning records) can proceed against the tree as it now stands.

## Self-Check: PASSED

- `test -f .planning/scripts/ipv6_thread_probe.py` -> FOUND
- `test -f .planning/scripts/measure_merged_discovery.py` -> FOUND
- `test -f .planning/scripts/measurement_support.py` -> FOUND
- `test -f .planning/scripts/serial_mac_audit.py` -> FOUND
- `test -f .planning/scripts/thread_revalidation.py` -> FOUND
- `test -f .planning/scripts/tests/test_ipv6_thread_probe.py` -> FOUND
- `test -f .planning/scripts/tests/test_measure_merged_discovery.py` -> FOUND
- `test -f .planning/scripts/tests/test_thread_revalidation.py` -> FOUND
- `test ! -e scripts/mdns_probe.py` -> CONFIRMED ABSENT
- `test ! -e scripts/test_multiversion.py` -> CONFIRMED ABSENT
- `test ! -d tests/test_scripts` -> CONFIRMED ABSENT
- `git log --oneline --all | grep -q 52e489b` -> FOUND
- `git log --oneline --all | grep -q 7f311c5` -> FOUND
- `git log --oneline --all | grep -q d6e58a6` -> FOUND
- `git log --oneline --all | grep -q eb764b0` -> FOUND
- `uv run --frozen pytest -q` -> 4256 passed, 605 deselected
- `uv run --frozen pytest --tooling -q` -> 4849 passed, 12 deselected
- `uv run --frozen pytest .planning/scripts/tests --no-cov -q` -> 593 passed
- `uv run --frozen pyright` -> 0 errors, filesAnalyzed 94 == expected 94
- `uv run --frozen ruff check .` -> All checks passed
- `uv run --frozen ruff format --check .` -> 281 files already formatted
- Repository-wide sweep -> SWEEP-CLEAN; fixture check -> matched=4
- Four privacy scans -> SERIAL-SCAN-OK 20, IPV4-SCAN-OK 17, MAC-SCAN-OK 19, IPV6-SCAN-OK 5

---
*Phase: 15-coverage-gate-and-test-suite-health*
*Completed: 2026-09-05*
