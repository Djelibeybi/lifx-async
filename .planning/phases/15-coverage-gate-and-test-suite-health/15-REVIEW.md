---
phase: 15-coverage-gate-and-test-suite-health
reviewed: 2026-09-06T23:10:23Z
depth: deep
files_reviewed: 22
files_reviewed_list:
  - .github/check_patch_coverage.py
  - .github/patch_coverage_guard.py
  - .github/workflows/ci.yml
  - .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py
  - .planning/scripts/ipv6_thread_probe.py
  - .planning/scripts/measure_merged_discovery.py
  - .planning/scripts/measurement_support.py
  - .planning/scripts/serial_mac_audit.py
  - .planning/scripts/thread_revalidation.py
  - .planning/scripts/tests/conftest.py
  - .planning/scripts/tests/test_check_patch_coverage.py
  - .planning/scripts/tests/test_ipv6_thread_probe.py
  - .planning/scripts/tests/test_measure_merged_discovery.py
  - .planning/scripts/tests/test_patch_coverage_guard.py
  - .planning/scripts/tests/test_thread_revalidation.py
  - .pre-commit-config.yaml
  - AGENTS.md
  - pyproject.toml
  - src/lifx/network/connection.py
  - tests/conftest.py
  - tests/test_discovery_observation.py
  - tests/test_network/test_connection_retry.py
  - tests/test_pytest_policy.py
findings:
  critical: 3
  warning: 4
  info: 1
  total: 8
status: issues_found
---

# Phase 15: Code Review Report

**Reviewed:** 2026-09-06T23:10:23Z
**Depth:** deep
**Files Reviewed:** 22
**Status:** issues_found

## Summary

This phase relocated maintainer/operator tooling out of the coverage-measured tree and built
`.github/patch_coverage_guard.py`, a new gate that fails the build when changed measured lines go
unscored by `coverage.xml`. The gate's own logic — diff parsing, `analysis2()`-derived authoritative
statement counting, Cobertura `<source>` resolution, and the `codecov/patch` advisory cross-check —
is sound and extensively fixture-tested; I could not construct an input that makes it exit 0 when
the changed-measured set is non-empty and unscored. The `_STREAM_IDLE_TIMEOUT`/retransmit observer
plumbing added to `src/lifx/network/connection.py` for Phase 14 is similarly solid and well covered.

However, I found two BLOCKER-level gaps in the surrounding machinery that the gate depends on to
actually run and to actually prevent tampering, plus one BLOCKER-level bypass in the sibling
anti-weakening script's own logic:

1. `check_patch_coverage.py`'s `check_weakening()` anti-tampering check inspects only the *new* path
   of a git `--name-status` line and only fires on status `D`. A rename (`R###`, which this
   environment's default git configuration emits with no special config) evades both the
   "deleted test file" and the "protected coverage file changed" checks. Verified with a live git
   repro in this review.
2. `ci.yml`'s `pull_request.paths` filter does not include `.github/**` (only
   `.github/workflows/ci.yml` specifically), so a pull request that touches only
   `.github/patch_coverage_guard.py` or `.github/check_patch_coverage.py` — the two files this
   phase says matter most — never triggers the workflow that tests, lints, type-checks or
   bandit-scans them.

I also found four WARNING-level gaps (a diagnostics omission in the guard's partial-score path, a
CI bandit-scan scope gap that leaves every `# nosec` in the new maintainer tooling unverified by the
blocking CI job, a silent-degrade path in the `changes` job's matrix-scoping shell logic, and an
incomplete path-redaction list in the committed `15-TEST-02-observe.py` evidence tool) and one INFO
item.

## Critical Issues

### CR-01: `check_weakening()`'s anti-tampering checks are blind to renames

**File:** `.github/check_patch_coverage.py:287-302`
**Issue:**

```python
status, changed_path = fields[0], fields[-1]
if status.startswith("D") and (
    changed_path == "tests" or changed_path.startswith("tests/")
):
    raise PatchCoverageError(f"{changed_path}: test file deleted")
if PurePosixPath(changed_path).name in PROTECTED_COVERAGE_FILES:
    raise PatchCoverageError(f"{changed_path}: coverage configuration changed")
```

`git diff --name-status` reports a rename as `R<similarity>\t<old>\t<new>` (three tab-separated
fields), and this repository's git configuration detects renames with no special flags — I verified
this directly:

```
$ git mv tests/test_x.py moved_test_x.py && git commit ...
$ git diff --name-status HEAD~1..HEAD
R100	tests/test_x.py	moved_test_x.py
```

Both checks only ever look at `fields[-1]` (the *new* path):

- Renaming a test file out of `tests/` (e.g. `tests/test_flaky.py` → `test_flaky.py.bak`, or into any
  non-`tests/` directory) has the same net effect on the suite as deleting it, but `status` here is
  `"R100"`, not `"D..."`, so the "test file deleted" branch never fires.
- Renaming a protected coverage-config file (`pyproject.toml`, `codecov.yml`, `.coveragerc`,
  `setup.cfg`, `tox.ini`) to any other name — including while simultaneously editing its content, as
  I also verified (`R088  pyproject.toml  renamed_config.toml`) — makes `fields[-1]` no longer match
  any name in `PROTECTED_COVERAGE_FILES`, so the "coverage configuration changed" branch never fires
  either.

This defeats the stated purpose of `check_weakening()` ("Reject newly added coverage exemptions,
skips, and gate weakening") for exactly the two protections it exists to provide, via a trivially
available rename. `.planning/scripts/tests/test_check_patch_coverage.py` has no test exercising an
`R` status line at all, confirming this path is untested as well as unguarded.

**Fix:** Check every path field on a rename/copy line (`status[0] in "RC"` implies `len(fields) == 3`
with `fields[1]` = old path, `fields[2]` = new path), and apply both the "was this a test file"
and "is this a protected file" checks to *both* the old and new paths, e.g.:

```python
paths_to_check = fields[1:] if status[0] in ("R", "C") else [changed_path]
if status.startswith("D") or status[0] in ("R", "C"):
    # A rename/copy whose OLD path was a test file removes it from tests/
    # just as effectively as a delete when the new path is not also under tests/.
    old_path = fields[1] if len(fields) > 1 else changed_path
    if (old_path == "tests" or old_path.startswith("tests/")) and not (
        changed_path == "tests" or changed_path.startswith("tests/")
    ):
        raise PatchCoverageError(f"{old_path}: test file removed from tests/")
for path in paths_to_check:
    if PurePosixPath(path).name in PROTECTED_COVERAGE_FILES:
        raise PatchCoverageError(f"{path}: coverage configuration changed")
```

---

### CR-02: `ci.yml`'s pull-request path filter never triggers CI for changes to the guard scripts themselves

**File:** `.github/workflows/ci.yml:9-19`
**Issue:**

```yaml
pull_request:
    paths:
    - src/**
    - tests/**
    - data/**
    - scripts/**
    - pyproject.toml
    - uv.lock
    - .pre-commit-config.yaml
    - .github/workflows/ci.yml
    - codecov.yml
```

`.github/patch_coverage_guard.py` and `.github/check_patch_coverage.py` are not covered by any
pattern here (only the workflow file itself, `.github/workflows/ci.yml`, is listed). A pull request
that touches only one of these two files — the files this phase's own context document names as
"the highest-value target" and the thing that "must be capable of failing the build and must not
produce false passes" — does not trigger the `CI` workflow at all. No tests run
(`.planning/scripts/tests/test_patch_coverage_guard.py`, `test_check_patch_coverage.py`), no
`ruff`/`pyright` check runs, and the (already narrow — see WR-02) `bandit` scan doesn't run either.
Depending on branch-protection configuration this either silently permits the PR to merge with zero
validation, or blocks it forever on a required check that will never report — either outcome is a
defect in a workflow whose entire job is to gate merges reliably. Contrast this with `push` (no path
filter at all), meaning the first time these scripts are actually exercised by CI may be *after* they
have already reached `main`.

**Fix:** Add an explicit `.github/**` (or at minimum `.github/*.py` and `.github/workflows/**`) entry
to `pull_request.paths`, mirroring the existing single-file carve-out for `ci.yml`:

```yaml
    paths:
    - src/**
    - tests/**
    - data/**
    - scripts/**
    - .github/**
    - pyproject.toml
    - uv.lock
    - .pre-commit-config.yaml
    - codecov.yml
```

---

### CR-03: (see CR-01) — rename-blind protected-file detection is a second, independent instance of the same root cause

Filed under CR-01 above; listed here only to make explicit that this is two distinct exploitable
gaps (test-deletion evasion and coverage-config-change evasion) sharing one root cause and one fix.

## Warnings

### WR-01: Guard's partial-scoring branch drops the `unscored_paths` diagnostic it already computed

**File:** `.github/patch_coverage_guard.py:469-473`
**Issue:** `measured_changed_lines()` already returns `unscored_paths` — every measured path whose
changed lines the report did not fully classify — and the `scored == 0` (vacuous) branch prints it.
The `elif scored < changed_measured:` (partial) branch discards the same information:

```python
elif scored < changed_measured:
    print(
        "WARNING: partially scored "
        f"changed_measured={changed_measured} scored={scored}"
    )
```

An operator seeing this warning in CI output has no way to tell *which* changed file(s) are
under-scored without re-deriving it by hand.
**Fix:**

```python
elif scored < changed_measured:
    paths = ", ".join(unscored_paths) or "(none)"
    print(
        "WARNING: partially scored "
        f"changed_measured={changed_measured} scored={scored} "
        f"unscored paths: {paths}"
    )
```

### WR-02: CI's blocking `bandit` step never scans the maintainer scripts carrying `# nosec`

**File:** `.github/workflows/ci.yml:97-100`
**Issue:** The `quality` job runs `uv run bandit -c pyproject.toml -r src/` — restricted to `src/`.
None of `.github/patch_coverage_guard.py`, `.github/check_patch_coverage.py`, or any file under
`.planning/scripts/` (all of which carry `# nosec B404`/`B603`/`B405`/`B314` suppressions reviewed
in this report) are ever scanned by the required, blocking CI job. `pyproject.toml`'s own
`[tool.pyright] include` list explicitly enumerates these same files as "hand-written path handling
and subprocess plumbing… included too rather than checking one and silently skipping its sibling" —
the same reasoning applies to `bandit` but was not carried through. The `.pre-commit-config.yaml`
`bandit` hook *does* cover them (it excludes only `tests/` and `.planning/scripts/tests/`), but that
hook only runs via local `pre-commit run` or the separate, non-required `pre-commit.ci` service —
not via the GitHub Actions `CI` workflow that gates merges.
**Fix:** Extend the CI bandit invocation to cover the same tree pyright already does, e.g.
`uv run bandit -c pyproject.toml -r src/ .github/*.py .planning/scripts/*.py` (excluding
`.planning/scripts/tests/`), or add a second bandit step scoped to `.github` and
`.planning/scripts`.

### WR-03: The `changes` job silently downgrades the test matrix if `gh pr diff` fails

**File:** `.github/workflows/ci.yml:52-63`
**Issue:**

```bash
CHANGED=$(gh pr diff "${{ github.event.number }}" --name-only | grep -cE '^(src/|tests/|...)' || true)
```

GitHub Actions runs `run:` blocks under `bash -e -o pipefail` by default. If `gh pr diff` fails (API
error, rate limit, permission hiccup), `pipefail` makes the pipeline's exit status non-zero; the
trailing `|| true` swallows that failure rather than surfacing it. `$CHANGED` is then whatever
`grep -c` counted from empty/partial output (typically `0`), so `source` is set to `false` and the
job silently falls back to the reduced Ubuntu-only matrix — for a PR that may in fact touch `src/`
extensively. This is the opposite of the fail-loudly posture the rest of this phase is built around
(see e.g. `check_patch_coverage.py`'s explicit "fail-closed" `PatchCoverageError`, or the guard's
own `PatchCoverageError`/`VacuousGateError` distinction).
**Fix:** Distinguish "the tool failed" from "the tool ran and found nothing":

```bash
if ! DIFF_OUTPUT=$(gh pr diff "${{ github.event.number }}" --name-only); then
  echo "::error::gh pr diff failed; cannot determine change scope" >&2
  exit 1
fi
CHANGED=$(printf '%s\n' "$DIFF_OUTPUT" | grep -cE '^(src/|tests/|data/|scripts/|\.github/workflows/ci\.yml|pyproject\.toml|uv\.lock)' || true)
```

### WR-04: `15-TEST-02-observe.py`'s path redaction does not cover platform temp directories

**File:** `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py:192-200`
**Issue:** The redaction list is built from exactly four roots:

```python
replacements: list[tuple[str, str]] = [
    (str(real_repo_root), "<repo>"),
    (str(resolved_repo_root), repo_root_placeholder),
    (str(venv_root), "<venv>"),
    (str(home_dir), "<home>"),
]
```

AGENTS.md requires that "absolute filesystem paths carrying an account name inside captured process
output" never reach a committed file, and this module's own docstring calls out that it must
redact before writing. On Linux, pytest's default `tmp_path`/`tmp_path_factory` base directory is
`/tmp/pytest-of-$USER/...`, which is not nested under any of the four redacted roots (unlike macOS,
where `TMPDIR` is typically under `/var/folders/...`, and unlike Windows, where `%TEMP%` is usually
under the user's home directory). A future observed test whose traceback or captured stderr
references a `tmp_path`-derived path on a Linux runner would leak the operator's OS account name into
the committed JSON record verbatim. The two record files already committed
(`15-TEST-02-record-prefix.json`, `15-TEST-02-record-fixed.json`) were both captured on macOS and
happen not to trigger this gap, but the redaction mechanism itself is incomplete.
**Fix:** Add the resolved `tempfile.gettempdir()` (and, defensively, `os.environ.get("TMPDIR")`) to
the `replacements` list before it is used, e.g.:

```python
import tempfile
...
tmp_root = Path(tempfile.gettempdir()).resolve()
replacements.append((str(tmp_root), "<tmp>"))
```

## Info

### IN-01: `read_patch_status()`'s cross-check output goes only to stdout, even on divergence

**File:** `.github/patch_coverage_guard.py:370-379, 388-393`
**Issue:** `CROSS-CHECK DIVERGENCE` — the one outcome an operator would most want surfaced
prominently (Codecov and the guard's own authoritative count disagree) — is printed with a plain
`print(...)` to stdout, identically to `CROSS-CHECK AGREE`/`CROSS-CHECK UNUSABLE`. Since this
function is documented to "never change the caller's exit code" by design, stdout-only output means
a divergence can scroll past in CI logs with no distinguishing signal (no `::warning::` annotation,
no stderr routing) even though it is exactly the condition this cross-check exists to catch.
**Fix:** Route the `CROSS-CHECK DIVERGENCE` message through `print(..., file=sys.stderr)` and/or a
GitHub Actions `::warning::` annotation so it is visible in the job summary without changing the
(intentionally non-gating) exit code.

---

_Reviewed: 2026-09-06T23:10:23Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
