---
phase: 15-coverage-gate-and-test-suite-health
plan: 04
subsystem: testing
tags: [pytest, faulthandler, subprocess, git-worktree, evidence, coordinator-teardown]

requires:
  - phase: 15-01
    provides: "The .planning/scripts/tests/ relocation shape, read for the standalone maintainer script docstring/argument-parsing style this plan's runner follows"
  - phase: 15-02
    provides: "The relocated .planning/scripts/serial_mac_audit.py read for style; a working-tree dependency only, since 15-02's tasks 1-2 leave the suite red until task 3 closes it, and this plan's observations require a clean, comparable tree"
provides:
  - "A reusable, stdlib-only observation runner (15-TEST-02-observe.py) that launches one pytest node in a child interpreter under a wall-clock watchdog and records process exit as the evidence signal, not the test result"
  - "Two committed, redacted, machine-readable records proving the coordinator teardown fix (39bad58) is load-bearing: the fixed form exits cleanly, the pre-fix form (reintroduced once in a scratch git worktree, never committed to the tracked test file) hangs and its faulthandler dump names the exact blocked executor worker deferred-items.md describes"
  - "deferred-items.md and STATE.md reconciled to state one outcome and cite one evidence file, closing the v2.0 Phase 13 deferred item"
affects: [15-05]

actuals:
  tokens: 7900
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Child-interpreter observation with faulthandler.dump_traceback_later(timeout, exit=True) armed before importing pytest, forcing a hard process exit past a hang inside threading._shutdown that suite-level pytest-timeout's thread method cannot reach"
    - "Child exit code propagated via raise SystemExit(pytest.main([...])), never a bare pytest.main(...) call, with a negative control against an invalid node id proving the propagation"
    - "Four-root redaction (repository root, scratch worktree root, venv root, home directory) applied before any write, mapping the resolved --repo-root to a placeholder classified by comparison against the runner's own detected repo root rather than by raw path"
    - "Stale-worktree pre-clean before baseline capture: clear any registration naming the experiment first, then capture the git worktree list baseline, so the two cleanup gates (baseline-diff and no-experiment-worktree) cannot contradict each other"
    - "Patch generated inside the scratch worktree via git -C <worktree> diff, so the defective form is never present in the main working tree at any point, not even transiently"

key-files:
  created:
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-prefix-executor-wait.patch
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-record-fixed.json
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-record-prefix.json
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-EVIDENCE.md
  modified:
    - .planning/milestones/v2.0-phases/13-merged-discovery/deferred-items.md
    - .planning/STATE.md

key-decisions:
  - "repo_root is recorded as a symbolic placeholder (<repo> or <worktree>), classified by comparing the resolved --repo-root argument against the runner's own git-detected repository root, rather than as a raw path -- this is what lets the two committed records be distinguishable from each other while carrying no absolute path"
  - "child_argv's sys.executable element (an absolute venv path) is redacted through the same four-root replacement as stderr before the record is written; the initial draft redacted only stderr and left this path exposed, caught by the plan's own absolute-path scan before committing"
  - "bandit's B404/B603/B607 findings on the new subprocess.run calls (git and the child interpreter) were suppressed with the same # nosec convention already used across the repository's other measurement scripts, not by widening any pre-commit exclude"

requirements-completed: [TEST-02]

coverage:
  - id: D1
    description: "The fixed form is observed under a 60s hard timeout with process exit, not just test result, as the signal: exit 0, no faulthandler banner, 0.66s elapsed, no PEP 723 header, --output required with no default, negative control against an invalid node id records a non-zero exit (4)"
    requirement: TEST-02
    verification:
      - kind: unit
        ref: "shell: uv run --frozen python 15-TEST-02-observe.py --node <valid-node> --timeout 60 --repo-root . --output 15-TEST-02-record-fixed.json (exit_code 0, faulthandler_banner false, elapsed_seconds 0.66)"
        status: pass
      - kind: unit
        ref: "shell: uv run --frozen python 15-TEST-02-observe.py --node <invalid-node> --timeout 60 --repo-root . --output <tmp> (exit_code 4, non-committed negative control)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The pre-fix form is reintroduced exactly once, in a scratch git worktree never touching the tracked test file, and the observed outcome (a genuine hang, forced to a hard exit at the 60s watchdog with a faulthandler dump naming the blocked executor worker) is recorded as-is with no repeat attempts"
    requirement: TEST-02
    verification:
      - kind: integration
        ref: "shell: uv run --frozen python <main>/15-TEST-02-observe.py --repo-root <worktree> --output 15-TEST-02-record-prefix.json, run once from inside the scratch worktree (exit_code 1, bound_fired child_watchdog, faulthandler_banner true, elapsed_seconds 60.05)"
        status: pass
      - kind: unit
        ref: "shell: git apply --check 15-TEST-02-prefix-executor-wait.patch; git diff --exit-code HEAD -- tests/test_network/test_discovery_coordinator.py; git worktree list diffed against the pre-experiment baseline"
        status: pass
    human_judgment: false
  - id: D3
    description: "The evidence document and both reconciled records (deferred-items.md, STATE.md) state one outcome, cite the same evidence file by name, name the load-bearing fix commit (39bad58, correcting the v2.0-assumed fc61b98), and the tracked test file is untouched"
    requirement: TEST-02
    verification:
      - kind: unit
        ref: "shell: grep -c 15-TEST-02-EVIDENCE.md across deferred-items.md and STATE.md (>=1 each); grep -c 39bad58 across the evidence doc and deferred-items.md (>=1 each); git diff --exit-code HEAD -- tests/test_network/test_discovery_coordinator.py (empty)"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen pytest tests/test_network/test_discovery_coordinator.py -q --no-cov -p no:cacheprovider (56 passed)"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-09-05
status: complete
---

# Phase 15 Plan 04: Coordinator Teardown Evidence Summary

**Reintroduced the pre-fix coordinator-teardown hang in a scratch worktree, proved the present fix (`39bad58`) load-bearing by observing both forms exit under a wall-clock watchdog, and reconciled `deferred-items.md`/`STATE.md` to the same outcome.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-09-05T23:14:00Z
- **Completed:** 2026-09-05T23:38:25Z
- **Tasks:** 3
- **Files modified:** 7 (5 created, 2 modified)

## Accomplishments

- Built a stdlib-only, no-PEP-723-header observation runner
  (`15-TEST-02-observe.py`) that launches a pytest node in a child interpreter
  under `sys.executable`, arming `faulthandler.dump_traceback_later(timeout,
  exit=True)` before importing pytest so a hang inside `threading._shutdown`
  (past where suite-level `pytest-timeout` can act) still forces a hard exit
  and a thread dump. The child propagates pytest's own exit code via
  `raise SystemExit(pytest.main([...]))` rather than a bare, discarded call; a
  negative control against a deliberately invalid node id confirmed a
  non-zero exit (4), proving the propagation before either real record was
  trusted.
- Ran the fixed form against the main checkout: exit 0, no faulthandler
  banner, 0.66s elapsed against the 60s watchdog. The process exited, which
  is a stronger claim than the test passing.
- Reintroduced the pre-fix `await asyncio.to_thread(self.release.wait)` form
  exactly once, as a patch generated inside a throwaway `git worktree` and
  applied only there. Observed once (per SPEC R6, no retries): the child
  hung, the in-child watchdog fired at 60s forcing a hard exit (exit 1), and
  the faulthandler dump named a default-executor worker blocked in
  `threading.Event.wait()` under `concurrent.futures.thread`, with the main
  thread blocked in `_python_exit` awaiting `threading._shutdown`. This is
  exactly the failure mode `deferred-items.md` describes, settling that the
  fix is load-bearing rather than coincidental.
- Wrote `15-TEST-02-EVIDENCE.md` transcribing both records side by side, and
  reconciled `deferred-items.md` (adds a load-bearing confirmation section,
  naming `39bad58` rather than the `fc61b98` the v2.0 close assumed) and
  `STATE.md` (Deferred Items row and v2.1 working note) to state the same
  outcome and cite the same evidence file. The tracked
  `tests/test_network/test_discovery_coordinator.py` is unchanged throughout;
  the scratch worktree was removed and `git worktree list` matched the
  pre-experiment baseline before this plan's final commit.

## Task Commits

Each task was committed atomically:

1. **Task 1: Observe the fixed form under a hard timeout, with process exit as the signal** -
   `fdcbbc4` (feat)
2. **Task 2: Reintroduce the pre-fix form once, in a scratch checkout, and record what happens** -
   `0b998dd` (test)
3. **Task 3: Write the evidence document and reconcile the two disagreeing records** -
   `cfa669e` (docs)

## Files Created/Modified

- `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py` - stdlib-only
  observation runner, no PEP 723 header, four-root redaction, negative-control-proven exit-code
  propagation
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-prefix-executor-wait.patch` -
  the pre-fix form as a replayable diff, generated inside the scratch worktree
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-record-fixed.json` - the
  fixed-form observation against the main checkout
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-record-prefix.json` - the
  pre-fix-form observation against the scratch worktree
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-EVIDENCE.md` - both records
  transcribed side by side with the settled conclusion
- `.planning/milestones/v2.0-phases/13-merged-discovery/deferred-items.md` - load-bearing
  confirmation section added, naming `39bad58` and citing the evidence document
- `.planning/STATE.md` - Deferred Items row and v2.1 working note updated to state the settled
  outcome

## Decisions Made

- `repo_root` is written as a symbolic placeholder (`<repo>` or `<worktree>`), decided by
  comparing the resolved `--repo-root` argument against the runner's own git-detected repository
  root, rather than as any form of the raw path. This is what makes the two committed records
  distinguishable from each other while carrying no absolute path, satisfying both the
  distinctness requirement and the redaction requirement at once.
- `child_argv`'s `sys.executable` element is redacted through the same four-root replacement as
  `stderr_tail`, applied to every argument in the list before the record is written.
- Bandit's B404/B603/B607 findings on the runner's `git`/child-interpreter `subprocess.run` calls
  were suppressed with the repository's existing `# nosec` convention (the same pattern already
  used in `.planning/scripts/serial_mac_audit.py` and its siblings), rather than widening any
  pre-commit exclude pattern.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `child_argv`'s `sys.executable` element reached the record unredacted**
- **Found during:** Task 1 (first run against the main checkout, before committing)
- **Issue:** The runner's redaction pass was applied only to `stderr_tail`. The recorded
  `child_argv` list still carried the raw absolute path to the venv interpreter
  (`sys.executable`), which would have failed the plan's own absolute-path scan and violated the
  repository's privacy rule had it been committed.
- **Fix:** Applied the same `_redact()` pass to every element of `child_argv` before writing the
  record, turning the interpreter path into `<venv>/bin/python3`.
- **Files modified:** `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py`
- **Verification:** Re-ran the observation; the absolute-path scan
  (`grep -nE '(^|[[:space:]"'"'"'`(])/[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+'`) against the record
  printed nothing.
- **Committed in:** `fdcbbc4` (Task 1's commit; caught before the first commit attempt)

**2. [Rule 3 - Blocking] bandit flagged the new subprocess calls on first commit attempt**
- **Found during:** Task 1 (first `git commit` attempt)
- **Issue:** `.pre-commit-config.yaml`'s bandit hook flagged the `subprocess` import (B404) and
  four `subprocess.run` calls (B603, three of them also B607 for the partial `git` executable
  path) as new, unexempted findings in the new file.
- **Fix:** Added `# nosec B404` on the import and `# nosec B603 B607` (or `# nosec B603` for the
  one call using the full `sys.executable` path) on each call site, matching the identical
  convention already established across every other measurement script in
  `.planning/scripts/`.
- **Files modified:** `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py`
- **Verification:** `git commit -S -s` succeeded on retry with the bandit hook passing.
- **Committed in:** `fdcbbc4` (Task 1's commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking).
**Impact on plan:** Both were necessary for the runner to be safe to commit and to lint-pass; no
scope creep beyond the exact lines the two findings touched.

## Issues Encountered

None beyond the two deviations documented above, both caught and resolved during Task 1 before
either committed record existed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The v2.0 Phase 13 deferred item is closed with evidence: the coordinator teardown fix at
  `tests/test_network/test_discovery_coordinator.py:75-76` (`39bad58`) is confirmed load-bearing,
  not coincidental.
- `deferred-items.md` and `STATE.md` now agree with each other and cite
  `15-TEST-02-EVIDENCE.md`, closing the inconsistency the v2.0 close left open.
- No blockers. Plan 15-05 (reference sweep across `AGENTS.md` and planning records) can proceed.

## Self-Check: PASSED

- `test -f .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py` -> FOUND
- `test -f .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-prefix-executor-wait.patch` -> FOUND
- `test -f .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-record-fixed.json` -> FOUND
- `test -f .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-record-prefix.json` -> FOUND
- `test -f .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-EVIDENCE.md` -> FOUND
- `git log --oneline --all | grep -q fdcbbc4` -> FOUND
- `git log --oneline --all | grep -q 0b998dd` -> FOUND
- `git log --oneline --all | grep -q cfa669e` -> FOUND
- `uv run --frozen pytest tests/test_network/test_discovery_coordinator.py -q --no-cov -p no:cacheprovider` -> 56 passed
- `git diff --exit-code HEAD -- tests/test_network/test_discovery_coordinator.py` -> empty (unchanged)
- `git worktree list` -> matches pre-experiment baseline, no `15-TEST-02` entry survives
- `uv run --frozen ruff check .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py` -> All checks passed
- `uv run --frozen ruff format --check .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py` -> already formatted

---
*Phase: 15-coverage-gate-and-test-suite-health*
*Completed: 2026-09-05*
