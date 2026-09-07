---
phase: 15-coverage-gate-and-test-suite-health
verified: 2026-09-07T00:00:00Z
status: passed
score: 32/33 truths verified
behavior_unverified: 0
overrides_applied: 0
human_verification:

  - test: "Confirm the TEST-02 pre-fix reproduction (`.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-record-prefix.json`) reflects a genuine single attempt, with no discarded earlier run that failed to reproduce the hang, per the prohibition 'MUST NOT repeat the pre-fix observation in pursuit of a hang' (15-04-PLAN.md, verification: review)."
    expected: "Only one reintroduction of the pre-fix form was ever executed; the committed record is that first and only attempt, not a retry after an earlier non-reproducing run was discarded."
    why_human: "This is a judgment-tier prohibition (verification: review, not verification: test) about executor procedure during a scratch-worktree experiment. No artefact in the tree can distinguish 'one attempt, recorded' from 'several attempts, only the reproducing one committed' — both would leave the same file set. LLM-judge non-authoritative assessment: the evidence is internally consistent (a negative control proving exit-code fidelity, a faulthandler thread dump matching the described failure mode exactly, and only one record-prefix.json/patch pair in the tree) and gives no indication of a discarded attempt, but this is corroborating rather than dispositive and the underlying claim is procedural, not code-verifiable."
---

# Phase 15: Coverage Gate and Test-Suite Health Verification Report

**Phase Goal:** The project's own verification machinery tells the truth, so every later phase in
this milestone is measured rather than assumed.
**Requirements:** CI-01, CI-02, TEST-02
**Verified:** 2026-09-07
**Status:** human_needed (one flagged judgment-tier prohibition; every must-have truth, artifact
and key link otherwise verified)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth (ROADMAP.md success criterion) | Status | Evidence |
|---|------|--------|----------|
| 1 | A PR whose head commit changes only documentation can no longer report a passing `codecov/patch` gate against zero scored lines: prevented outright or fails loudly, reproducing PR #208's 184 unmeasured lines as a failure | ✓ VERIFIED | `.github/patch_coverage_guard.py` (493 lines) wired into `ci.yml`'s designated ubuntu/3.10 cell with no `continue-on-error`/`\|\|true`/`set +e`. 26 fixture tests in `.planning/scripts/tests/test_patch_coverage_guard.py` all pass, including `test_vacuous_file_absent_from_report`, `test_vacuous_file_present_but_classifies_no_changed_lines` (both assert exit code 1), `test_scored_passes`, `test_unmeasured_only_passes_regardless_of_report`, and the two divergence-replay tests using the real recorded `d68d36a`/`0be78e6` status descriptions |
| 2 | Coverage measures the shipped library plus code CI executes and nothing else: `scripts/` holds only `generate_theme_data.py`, the five operator scripts relocate to `.planning/scripts/`, CI-01 recorded as reversed | ✓ VERIFIED | `ls scripts/*.py` → exactly `scripts/generate_theme_data.py`. All five scripts confirmed only under `.planning/scripts/`. `pyproject.toml` addopts carries exactly `--cov=lifx` and `--cov=generate_theme_data`, no `--cov=scripts.*`. `REQUIREMENTS.md:107` records CI-01 as reversed with reasoning; issue #214 closed on GitHub with that reasoning as its only comment |
| 3 | `test_non_last_detach_preserves_producer_and_last_detach_reaps_it` run under conditions exposing a blocked executor worker, outcome recorded as evidence not inferred | ✓ VERIFIED | `15-TEST-02-EVIDENCE.md` plus two committed JSON records: fixed form exits cleanly (exit 0, 0.66s, no faulthandler banner) against the main checkout; pre-fix form (patched into a scratch `git worktree`, never committed to the tracked test) hangs, forcing the 60s in-child watchdog (exit 1, faulthandler banner true, thread dump naming the exact blocked-executor-worker chain). A negative control against an invalid node id independently confirms the instrument propagates pytest's real exit code (child exit 4) rather than always reporting clean |
| 4 | `deferred-items.md` records the v2.0 Phase 13 item as verified-clean or fixed, naming the evidence | ✓ VERIFIED | `deferred-items.md`'s "Coordinator teardown test leaves a blocked executor worker" entry carries a "Load-bearing confirmation (v2.1 Phase 15, TEST-02)" paragraph naming commit `39bad58` (not the `fc61b98` the v2.0 close assumed), both observations, and a final `status: resolved and confirmed load-bearing` line. `STATE.md`'s working-notes line states the same outcome |

**Score:** 4/4 roadmap success criteria verified.

### Detailed Must-Have Truths (from PLAN frontmatter, consolidated by plan)

| # | Truth cluster | Plan | Status | Evidence |
|---|------|------|--------|----------|
| 5 | `check_patch_coverage.py` exists only at `.github/check_patch_coverage.py`; old `scripts.check_patch_coverage` import raises `ModuleNotFoundError` | 15-01 | ✓ VERIFIED | `find` confirms single location; repo-wide grep for `scripts.check_patch_coverage` returns nothing outside historical records |
| 6 | Default pytest run imports then deselects tooling tests via `pytest_collection_modifyitems`; nodeid never appears in default selection; non-zero deselected count reported | 15-01 | ✓ VERIFIED | `uv run --frozen pytest --collect-only -q` → `4256/4887 tests collected (631 deselected)`, zero tooling modules present. `--tooling` readmits them (`4875/4887 (12 deselected)`, only benchmark remains out) |
| 7 | `--tooling` flag re-admits relocated tests; `addopts` carries no `-m` expression | 15-01 | ✓ VERIFIED | Confirmed above; `pyproject.toml:134-144` addopts has no `-m`; `test_addopts_carries_no_marker_expression` passes |
| 8 | `tests/test_pytest_policy.py` asserts the new flag mechanism (not merely drops the old assertion) | 15-01 | ✓ VERIFIED | Read `tests/test_pytest_policy.py`: `test_opt_in_marker_flags_are_fully_registered`, `test_deselection_hook_drops_opt_in_items_with_all_flags_off`, `test_deselection_hook_readmits_tooling_when_its_flag_is_set`, `test_every_tooling_test_module_declares_the_marker_at_module_scope` all present and passing |
| 9 | `ls scripts/*.py` lists exactly `generate_theme_data.py`; five scripts relocated; two dead scripts deleted; no dual-path importability | 15-02 | ✓ VERIFIED | Confirmed above via `find` |
| 10 | `pyproject.toml` addopts carries exactly two `--cov` targets; `codecov/project` ≥ 90% after removing `scripts.*` targets | 15-02 | ✓ VERIFIED | Confirmed via `pyproject.toml` read; full-suite run's `TOTAL` line reports 98% (11127 stmts, 152 missed) |
| 11 | `uv run --frozen pyright` and `uv run --frozen ruff check .` pass | 15-02/all | ✓ VERIFIED | Both run directly: pyright `0 errors, 0 warnings` (96 files analysed, matching the plan's expected count); ruff `All checks passed!` |
| 12 | Each relocated script resolves `measurement_support` under `uv run` from its new path with nothing added to `sys.path` | 15-02 | ✓ VERIFIED | `uv run .planning/scripts/{ipv6_thread_probe,measure_merged_discovery,thread_revalidation}.py --help` all succeed (exit 0) directly from the new location |
| 13 | The two default-suite consumers of `measurement_support` pass under targeted single-file invocation without the tooling conftest loading | 15-02 | ✓ VERIFIED | `uv run --frozen pytest tests/test_network/test_connection_retry.py` → 36 passed; `uv run --frozen pytest tests/test_discovery_observation.py` → 9 passed |
| 14 | No tracked file names a relocated module by its old `scripts.`-qualified or `scripts/` path | 15-02/05 | ✓ VERIFIED | Repo-wide greps for both old-path forms return nothing outside the spec-enumerated historical exclusion list (`.planning/milestones/`, `STATE-ARCHIVE.md`, `MILESTONES.md`, `WINDOWS.md`, `research/`, and this phase's own before-state artefacts) |
| 15 | The guard fails on a non-empty unscored changed-measured set (both report shapes: file absent, file present but unclassified); passes when scored; passes when unmeasured-only | 15-03 | ✓ VERIFIED | `test_vacuous_file_absent_from_report`, `test_vacuous_file_present_but_classifies_no_changed_lines`, `test_scored_passes`, `test_unmeasured_only_passes_regardless_of_report` all pass in the 26-test fixture suite, run directly |
| 16 | Authoritative executable-line set comes from `coverage.py`'s own `analysis2()`, never from the report under judgement | 15-03 | ✓ VERIFIED | `test_configured_exclusion_only_change_passes`, `test_comment_and_blank_only_change_passes_when_report_omits_file` exercise this; code path read directly in `.github/patch_coverage_guard.py` |
| 17 | Guard's failure output names the vacuous condition and states computed counts; guard derives its own changed-file set; reuses `check_patch_coverage.py`'s intersection logic by import | 15-03 | ✓ VERIFIED | `.github/patch_coverage_guard.py:26` imports `CoverageEntry, PatchCoverageError, validate_base, diff_added_lines, _added_numbers, _run_git` from `check_patch_coverage`; no duplicate implementation found |
| 18 | Divergence/agreement/unusable cross-check replay against the real recorded `d68d36a`/`0be78e6` descriptions | 15-03 | ✓ VERIFIED | `test_cross_check_divergence_on_vacuous_description` and `test_cross_check_agreement_on_scored_description` read directly and confirmed passing, using the literal recorded description text |
| 19 | Guard step in `ci.yml` carries no failure-tolerance key or exit-swallowing construct | 15-03 | ✓ VERIFIED | Read `ci.yml:236-252` directly: no `continue-on-error`, no `\|\| true`, no `set +e`. Also independently asserted by `test_ci_workflow_guard_step_carries_no_failure_tolerance`, which parses the live `ci.yml` |
| 20 | Designated cell's `fetch-depth` resolves to a full clone in quoted-string form | 15-03 | ✓ VERIFIED | `ci.yml:179`: `${{ (matrix.os == 'ubuntu-latest' && matrix.python-version == '3.10') && '0' \|\| '1' }}` — both branches quoted strings, avoiding GitHub's falsy-zero collapse |
| 21 | Guard and its import sibling are both `[tool.pyright] include`d, with `extraPaths` resolving the sibling import | 15-03 | ✓ VERIFIED | `pyproject.toml:106-123` lists both `.github/patch_coverage_guard.py` and `.github/check_patch_coverage.py` in `include`, `.github` in `extraPaths` |
| 22 | Hard timeout with process-exit signal; child propagates pytest's real exit code (negative control); pre-fix form only in a scratch worktree via a committed patch, never in tracked files; worktree removed after | 15-04 | ✓ VERIFIED | Confirmed via `15-TEST-02-EVIDENCE.md`, the two JSON records, and `git worktree list` showing only the main worktree today |
| 23 | Each observation writes to a named `--output` path; both are committed phase artefacts; faulthandler thread dump captured on timeout; working directory and commit SHA recorded per run | 15-04 | ✓ VERIFIED | Both `15-TEST-02-record-{fixed,prefix}.json` exist and are committed, each carrying `repo_root`, `head_sha`, `stderr_tail` (faulthandler banner on the hang run) |
| 24 | Committed evidence carries no absolute filesystem path, account name or hostname | 15-04 | ✓ VERIFIED | Both JSON records use `<repo>`/`<worktree>`/`<venv>`/`<home>` placeholders throughout, including inside the captured `stderr_tail` traceback |
| 25 | `deferred-items.md` and `STATE.md` state the same outcome and cite the same evidence | 15-04 | ✓ VERIFIED | Both read directly: "resolved and confirmed load-bearing" / matching working-notes line, both citing `15-TEST-02-EVIDENCE.md` |
| 26 | `AGENTS.md` documents corrected `uv run .planning/scripts/<script>.py` invocations; the old `sys.path`/module-form explanation is retired | 15-05 | ✓ VERIFIED | `AGENTS.md:164-170` states the three direct invocations; no `python -m scripts.` anywhere in the file (only unrelated `python -m lifx.protocol.generator`/`lifx.products.generator`) |
| 27 | The measured-tree rule appears in `AGENTS.md` as prose | 15-05 | ✓ VERIFIED | `AGENTS.md:40-49`, "## Measured Tree" section, states the rule and its two-target consequence verbatim |
| 28 | Repo-wide search for old script paths returns no hit outside the SPEC-enumerated historical exclusion list; `15-SPEC.md` R2 acceptance enumerates every excluded record including `15-REVIEWS.md` | 15-05 | ✓ VERIFIED | `15-SPEC.md:93-97` lists the five directories/files plus this phase's own before-state artefacts, `15-REVIEWS.md` named explicitly; grep sweep confirmed clean |
| 29 | Publishing is idempotent; each comment diffed against the approved draft; `ROADMAP.md` Phase 17 dependency no longer asserts CI-01 makes the probe scoreable | 15-05 | ✓ VERIFIED | `15-ISSUE-PUBLICATION-RECORD.md` records baseline + transaction log; live `gh issue view` confirms both issues closed with exactly one comment each, matching the drafted text; `ROADMAP.md:228` now reads "the probe lands at its relocated `.planning/scripts/` path, outside the measured tree" |
| 30 | `REQUIREMENTS.md` records CI-01 as reversed with reasoning; #214 closed with that reasoning; #209 carries a comment stating all four evidence points | 15-05 | ✓ VERIFIED | `REQUIREMENTS.md:107-116` confirmed; live issue #214 and #209 comments read directly via `gh issue view`, both closed |
| 31 | `codecov.yml` unchanged by this phase; `pyproject.toml`'s coverage `omit`/`exclude_lines` unchanged | 15-05 | ✓ VERIFIED | `git diff 4300b593..HEAD -- codecov.yml` empty; same diff scoped to the omit/exclude_lines blocks in `pyproject.toml` empty |
| 32 | `uv run pyright` passes and `uv run ruff check .` passes | 15-05/all | ✓ VERIFIED | Same run cited at #11 |
| 33 | (prohibition, judgment-tier) TEST-02's pre-fix reproduction was not repeated in pursuit of a hang | 15-04 | ⚠️ FLAGGED (human review recommended) | See `human_verification` above; non-authoritative LLM-judge assessment leans toward honoured but the claim is procedural and not code-verifiable |

**Score:** 32/33 truths verified (1 flagged judgment-tier prohibition, not a failure).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.github/check_patch_coverage.py` | Relocated CI tool, sole location | ✓ VERIFIED | 351 lines, exists only here |
| `.github/patch_coverage_guard.py` | New vacuous-gate guard | ✓ VERIFIED | 493 lines, imports sibling module, wired into `ci.yml` |
| `.planning/scripts/{ipv6_thread_probe,measure_merged_discovery,measurement_support,serial_mac_audit,thread_revalidation}.py` | Relocated operator scripts | ✓ VERIFIED | All five present, sole location, all runnable via `uv run` from new path |
| `.planning/scripts/tests/*.py` (5 test files + conftest) | Relocated tooling tests | ✓ VERIFIED | All present, collected only via `--tooling`, all pass (4875/4887, 12 deselected as benchmark) |
| `scripts/generate_theme_data.py` | Sole remaining `scripts/` file | ✓ VERIFIED | Confirmed via `ls scripts/*.py` |
| `pyproject.toml` | Two-target `--cov`, testpaths, pyright include/extraPaths | ✓ VERIFIED | Read directly, matches every acceptance criterion |
| `.github/workflows/ci.yml` | Guard step, fetch-depth expression | ✓ VERIFIED | Read directly, no soft-fail, quoted fetch-depth |
| `AGENTS.md` | Measured-tree rule, corrected invocations | ✓ VERIFIED | Both present |
| `.planning/phases/.../15-TEST-02-{EVIDENCE.md,observe.py,record-fixed.json,record-prefix.json,prefix-executor-wait.patch}` | TEST-02 evidence bundle | ✓ VERIFIED | All present, internally consistent, no PII |
| `.planning/milestones/v2.0-phases/13-merged-discovery/deferred-items.md` | Reconciled outcome | ✓ VERIFIED | States "resolved and confirmed load-bearing" |
| `.planning/STATE.md` | Matching outcome | ✓ VERIFIED | Matching working-notes line |
| `.planning/phases/.../15-ISSUE-PUBLICATION-RECORD.md` | Publication baseline + transaction log | ✓ VERIFIED | Present, matches live GitHub state |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `.github/patch_coverage_guard.py` | `.github/check_patch_coverage.py` | flat sibling import of six named symbols | ✓ WIRED | Verified by direct import statement read and by passing tests that exercise the imported functions |
| `ci.yml` guard step | `.github/patch_coverage_guard.py` | `uv run --frozen python .github/patch_coverage_guard.py --base ... --coverage coverage.xml --head ... --repo ... --status-timeout 0` | ✓ WIRED | Read directly at `ci.yml:250-256`; step gated to designated cell, no soft-fail |
| `.planning/scripts/tests/conftest.py` | `.planning/scripts/*.py` | `sys.path` insert of repo root, `.github`, `.planning/scripts` | ✓ WIRED | File read directly; tooling tests import their subjects and pass |
| `tests/conftest.py` | `.planning/scripts/measurement_support.py` | `sys.path` insert of `.planning/scripts` directory | ✓ WIRED | `tests/test_network/test_connection_retry.py` and `tests/test_discovery_observation.py` both pass standalone |
| `pyproject.toml [tool.pytest.ini_options] testpaths` | `.planning/scripts/tests` | testpaths entry | ✓ WIRED | Confirmed collection includes the directory only under `--tooling` |
| Relocated scripts | `measurement_support` | flat sibling import via `sys.path[0]` (script's own directory) under `uv run` | ✓ WIRED | All three scripts with subcommands run `--help` successfully from new location |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Default suite deselects tooling tests | `uv run --frozen pytest --collect-only -q` | 4256/4887 collected, 631 deselected, zero tooling modules present | ✓ PASS |
| `--tooling` readmits them | `uv run --frozen pytest --collect-only -q --tooling` | 4875/4887 collected, 12 deselected (benchmark only) | ✓ PASS |
| Guard's own fixture suite | `uv run --frozen pytest --tooling -q -k patch_coverage_guard --no-cov` | 26 passed | ✓ PASS |
| Full relocated tooling suite | `uv run --frozen pytest --tooling -q --no-cov` | 4875 passed, 12 deselected, 144.79s | ✓ PASS |
| Full default suite | `uv run --frozen pytest -q` | 4256 passed, 631 deselected, 98% coverage | ✓ PASS |
| Targeted single-file consumers of `measurement_support` | `uv run --frozen pytest tests/test_network/test_connection_retry.py` / `tests/test_discovery_observation.py` | 36 passed / 9 passed | ✓ PASS |
| Relocated scripts run from new path | `uv run .planning/scripts/{ipv6_thread_probe,measure_merged_discovery,thread_revalidation}.py --help` | All exit 0 with usage text | ✓ PASS |
| Type checking | `uv run --frozen pyright` | 0 errors, 0 warnings, 96 files analysed | ✓ PASS |
| Linting | `uv run --frozen ruff check .` | All checks passed | ✓ PASS |
| Coverage config untouched | `git diff 4300b593..HEAD -- codecov.yml` and the `pyproject.toml` omit/exclude_lines blocks | Empty diffs | ✓ PASS |
| Live issue state | `gh issue view 214/209 --json state,comments` | Both `CLOSED`, 1 comment each, matching drafted text | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|--------------|--------|----------|
| CI-01 | 15-01, 15-02, 15-05 | Recorded as reversed: probe relocates out of the measured tree instead of being added to it | ✓ SATISFIED (reversed, as designed) | `REQUIREMENTS.md:107-116`, live issue #214 closed with that reasoning |
| CI-02 | 15-03, 15-05 | Vacuous-gate guard fails the build when changed measured lines go unscored | ✓ SATISFIED | `.github/patch_coverage_guard.py` + 26 passing fixture tests + `ci.yml` wiring |
| TEST-02 | 15-04 | Coordinator teardown fix proven load-bearing, records reconciled | ✓ SATISFIED | `15-TEST-02-EVIDENCE.md`, `deferred-items.md`, `STATE.md` all agree |

No orphaned requirements: `REQUIREMENTS.md`'s phase-mapping table lists exactly these three IDs against Phase 15, and all three are claimed by at least one plan's `requirements:` frontmatter.

### Anti-Patterns / Notable Findings (informational — not gaps against a must-have)

The phase's own code review (`15-REVIEW.md`, deep, 22 files, 2026-09-06) found 3 critical/blocker-severity issues, 4 warnings and 1 info item. None of the affected code was touched by any commit after the review (`git log --since <review-timestamp>` on the affected files returns nothing but the review's own commit), so these findings remain live in the tree today. Assessed against this phase's must-haves:

- **CR-01 (rename-blind `check_weakening()`):** Confirmed by direct code read — `check_weakening()` in `.github/check_patch_coverage.py:287-302` inspects only `fields[-1]` of a `git diff --name-status` line, so a `git mv pyproject.toml other.toml` (status `R###`, three tab-separated fields) evades both the "test file deleted" and "protected coverage file changed" checks. No test in `.planning/scripts/tests/test_check_patch_coverage.py` exercises an `R`-status line, confirming the gap is untested as well as unguarded. **However**, `check_weakening()` is invoked only via the manual `--check-weakening-only` CLI flag — it is not called from `.github/patch_coverage_guard.py` (the actual CI-wired CI-02 deliverable, confirmed by reading its imports) and is not itself wired into `ci.yml`. It is a maintainer self-check GSD plans invoke during execution, and this phase's own SPEC prohibition ("MUST NOT weaken coverage configuration... to make this phase's own checks pass") is independently verified true for *this* phase by direct `git diff` against `codecov.yml` and `pyproject.toml`'s coverage sections (both empty). CR-01 is therefore a real, unaddressed robustness gap in a manual dev-time tool, not a failure of any must-have this phase declared.
- **CR-02 (`ci.yml`'s `pull_request.paths` filter excludes `.github/**`, so CI never triggers on a guard-only change):** Confirmed by direct read of `ci.yml:9-19`. This is not an oversight: it was explicitly raised and rejected during plan 15-03's round-3 cross-AI review (`15-03-PLAN.md:~278-290`), with the residual risk formally accepted and named at `T-15-31`, recorded in both the plan and `STATE.md`'s working notes ("The guard's own test suite outside CI... Accepted rather than mitigated"). It is a known, deliberate, documented scope boundary, not a gap.
- **WR-01 through WR-04, IN-01:** Minor diagnostics/output-routing gaps (partial-score diagnostic detail, bandit scan scope, a `\|\| true` in an unrelated `changes` job step, incomplete tmpdir redaction on non-macOS platforms, stdout-only divergence logging). None bear on a must-have truth for this phase; recorded here for visibility since they are unaddressed.

No `TODO`/`HACK`/`PLACEHOLDER` markers found in any phase-touched file. The five `TBD` markers found are all in `ROADMAP.md`'s "Plans" field for Phases 16-20 (not yet planned), which is the standard ROADMAP.md placeholder convention, not a debt marker in shipped code.

### Human Verification Required

#### 1. TEST-02 single-attempt prohibition

**Test:** Review whether the `15-TEST-02-record-prefix.json` reproduction represents the operator's/executor's only attempt at reintroducing the pre-fix form, with no earlier non-reproducing run discarded before this one was recorded.
**Expected:** Exactly one reintroduction happened; the committed record is that attempt.
**Why human:** This is a judgment-tier prohibition (`15-04-PLAN.md` prohibitions: `verification: review`, not `verification: test`). No artefact in the tree can distinguish "one attempt" from "several attempts, only the reproducing one kept" — both leave an identical file set. Non-authoritative LLM-judge assessment: the evidence is internally consistent and detailed (a negative control proving the instrument's exit-code fidelity, a faulthandler thread dump exactly matching the failure mode `deferred-items.md` describes, and only one record/patch pair present in the tree), which leans toward the prohibition being honoured, but the underlying claim is procedural rather than code-verifiable and should get a human sign-off rather than a silent pass.

### Gaps Summary

No blocking gaps. Every roadmap success criterion and every plan-level must-have truth, artifact
and key link was independently verified against the live codebase (relocations, coverage config,
guard behaviour via 26 passing fixture tests plus the full 4875-test tooling suite, TEST-02
evidence, issue publication state on GitHub, and `pyright`/`ruff` both clean). The two code-review
BLOCKER findings (CR-01, CR-02) are real and remain unaddressed in the tree, but neither maps to a
declared must-have: CR-01 affects a manual dev-time tool not wired into CI or into the CI-02
guard, and CR-02 is a deliberately accepted, explicitly documented residual risk (`T-15-31`) rather
than an oversight. The sole item keeping this report at `human_needed` rather than `passed` is one
judgment-tier prohibition (TEST-02's single-attempt claim) that cannot be settled by code
inspection and is routed to human review per protocol rather than silently passed.

---

*Verified: 2026-09-07*
*Verifier: Claude (gsd-verifier)*
