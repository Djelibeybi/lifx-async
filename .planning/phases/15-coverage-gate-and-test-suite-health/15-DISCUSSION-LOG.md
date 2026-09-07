# Phase 15: Coverage Gate and Test-Suite Health - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-09-05
**Phase:** 15-coverage-gate-and-test-suite-health
**Areas discussed:** Import model for relocated tooling, Guard placement and coverage input,
tooling marker mechanics, TEST-02 re-break mechanics

---

## Import model for relocated tooling

### Sibling imports

| Option | Description | Selected |
|--------|-------------|----------|
| Flat top-level imports, `.planning/scripts` on pythonpath | Smallest diff, matches existing test import route | ✓ (adjusted) |
| Real package inside the dot-directory | `lifx_measure/` namespace, extra nesting level | |
| `sys.path` bootstrap inside each script | Self-contained, import machinery in every file | |

**User's choice:** Asked for a recommendation, stating an inclination against modifying
`pythonpath` in `pyproject.toml`, then accepted "Yes, as recommended".

**Notes:** The recommendation refined the option rather than picking it as written. Running a
file directly puts its own directory on `sys.path[0]`, so flat sibling imports resolve with no
`pythonpath` entry and no bootstrap. The bootstrap option was withdrawn as unnecessary and
because it would place executable code above an import, against the project's Python
conventions.

A correction was issued after the choice: `pythonpath` must stay `["src", "scripts"]`, not drop
to `["src"]` as the option text said. `tests/test_theme/test_theme_generator.py:36` does
`import generate_theme_data` through that entry, and `generate_theme_data.py` is the file
remaining in `scripts/`. The decision is that no new entry is added.

### Documented invocation

| Option | Description | Selected |
|--------|-------------|----------|
| Direct file path | `uv run --frozen python .planning/scripts/<script>.py` | |
| PYTHONPATH-prefixed `python -m` | Keeps the `-m` form, still needs the AGENTS.md note rewritten | |
| PEP 723 inline metadata, run as a script | Self-contained and dependency-declaring | ✓ |

**User's choice:** PEP 723 inline metadata.

**Notes:** Scouting found `scripts/serial_mac_audit.py:1-7` already using this pattern with a
`[tool.uv.sources]` block binding `lifx-async` to the working tree as an editable path
dependency. Without that block a PEP 723 script would resolve `lifx-async` from PyPI rather than
the checkout. The four other scripts carry 5 to 15 `lifx` imports each, so the block is
load-bearing, not decorative.

### Test-side resolution

| Option | Description | Selected |
|--------|-------------|----------|
| `conftest.py` beside the tests | Localised to test infrastructure, keeps pyproject clean | ✓ |
| importlib load by path | No sys.path mutation, more ceremony per file | |
| PEP 723 runner for the tests too | Fully self-contained, furthest from the rest of the suite | |

**User's choice:** `conftest.py` beside the tests.

**Notes:** Raised because tests import their subjects rather than executing them, so
`sys.path[0]` does not help them the way it helps direct script execution.

---

## Guard placement and coverage input

| Option | Description | Selected |
|--------|-------------|----------|
| Step inside the ubuntu test job | coverage.xml already on disk, no artifact plumbing | ✓ |
| Separate job, one uploaded artifact | Clean separation, pinned version choice | |
| Separate job, all five artifacts merged | Most accurate, most plumbing | |

| Option | Description | Selected |
|--------|-------------|----------|
| Union across the matrix | A line counts as scored if any version classifies it | ✓ (then withdrawn) |
| Single pinned version | Simplest, a version-gated branch could read as unscored | |
| Per-version, fail if any cell scores nothing | Strictest, noisy on version-gated code | |

**User's choice:** Step inside the ubuntu test job, then "Designated cell, single report" on the
reconciliation question.

**Notes:** The first two answers were mutually exclusive and this was raised rather than
silently resolved. Matrix cells are separate runners, so a step inside the job cannot see the
other cells' reports; unioning requires artifacts and a following job.

The conflict was resolved by measuring the actual exposure: `src/lifx` contains exactly one
version-gated site (`const.py:175`) and zero platform-gated sites. Because the guard fails only
on total-zero rather than per-line coverage, a false failure would need a pull request changing
only that one block and nothing else measured.

The designated cell reuses `.github/workflows/ci.yml:193`, already singled out for the
must-not-skip IPv6 test, whose comment records that it is present in every matrix configuration
including the reduced ubuntu-only path.

---

## tooling marker mechanics

### Marker application

| Option | Description | Selected |
|--------|-------------|----------|
| Module-level `pytestmark` per file | Explicit and greppable, four lines | ✓ |
| conftest auto-marks by path | Nothing can be forgotten, marker invisible at the file | |
| testpaths exclusion, no marker | Simplest, conflicts with the SPEC's manual-run wording | |

### Deselection mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Extend to `-m "not benchmark and not tooling"` | One-line change, matches existing benchmark handling | (initially) |
| Drop the relocated dir from testpaths as well | Belt and braces, more friction than the SPEC asks | |
| Marker only, leave addopts alone | Contradicts the locked SPEC decision | |
| **Opt-in flags via the existing collection hook** | `--tooling`/`--benchmark`, no `-m` in addopts | ✓ |

**User's choice:** Initially the extended negation, then reopened mid-turn with "can't it be the
opposite? Excluded unless we specify" and settled on opt-in flags.

**Notes:** The reopening was correct and changed the outcome. The explanation given: `-m` is a
selection filter, not an additive switch. `-m benchmark` means "run only benchmarks", and
`-m "benchmark and tooling"` would select the intersection, which is empty, so there is no `-m`
spelling of "the normal suite plus tooling". The exclusion the user wanted already existed, but
only as a negation that grows with each new category.

`tests/conftest.py:141` already implements `pytest_collection_modifyitems` and already adds
markers conditionally, so the opt-in flag pattern extends an existing hook rather than
introducing a mechanism. Benchmarks migrate to the same model so the two do not coexist.

Consequence recorded: `tests/test_pytest_policy.py:76` asserts on `addopts` and must be updated
to assert the new mechanism.

### Collection reach

| Option | Description | Selected |
|--------|-------------|----------|
| testpaths gains the relocated directory | Both trees collected, chosen mechanism does the excluding | ✓ |
| Tests stay under tests/, subjects move | Collection unchanged, splits tests from subjects | |
| Path-only, no collection config | Marker becomes documentation rather than mechanism | |

**Notes:** Raised because `testpaths = ["tests"]` means a relocated directory is never collected,
which would have made the marker decision moot and the exclusion an accident of configuration.

---

## TEST-02 re-break mechanics

### Reintroducing the pre-fix form

| Option | Description | Selected |
|--------|-------------|----------|
| Patch file kept as phase evidence | Replayable later, nothing defective in the tree | ✓ |
| Scratch worktree, patch not retained | Lighter, reverted code described rather than replayable | |
| Transcript only | Diff pasted into the evidence document | |

### Observation method

| Option | Description | Selected |
|--------|-------------|----------|
| Subprocess under a wall-clock timeout | Exit code and elapsed time recorded | |
| Same, plus a faulthandler thread dump on timeout | Evidence names the blocked worker | ✓ |
| Rely on the CI job timeout | Coarse evidence, ten minutes per observation | |

**Notes:** Raised because the Phase 13 record shows the test *passes* and pytest then hangs in
`threading._shutdown` awaiting `concurrent.futures.thread._python_exit`. That is after the test
reports, so the suite's `timeout = 60` with `timeout_method = "thread"` cannot catch it and
detection must be at process level.

The thread dump matters because SPEC R6 permits a non-hanging second run to be recorded as-is: a
dump distinguishes "did not reproduce" from "hung for an unrelated reason".

---

## Deferred Ideas

- **Union coverage across the matrix** if the single-report guard ever misfires. Recorded so a
  future failure is a known upgrade rather than a rediscovery.
- **`check_patch_coverage.py` `--source` derivation.** Already out of scope in the SPEC;
  restated because the guard sits next to it.
- **Enforcing a minimum scored fraction in the guard.** Nearly free once counts are computed,
  but it would turn the guard into the enforcement gate that was deliberately declined.

## Claude's Discretion

Flag names and help text, the relocated test directory's layout, patch and evidence filenames,
the wall-clock timeout value, the guard script's location and internal structure, and the
ordering and commit granularity of the moves.

---

*Phase: 15-coverage-gate-and-test-suite-health*
*Discussion logged: 2026-09-05*
