# Phase 15 Specification: Coverage Gate and Test-Suite Health

**Created:** 2026-09-05
**Ambiguity score:** 0.137 (gate: ≤ 0.20)
**Requirements:** 6 locked

## Goal

`scripts/` holds only code that CI executes, coverage measures only the shipped library plus
that CI-run code, and a CI job counts for itself whether a pull request's changed measured lines
were scored, failing the build when they were not.

## Background

The milestone opens by fixing the project's own verification machinery, because Phases 16 to 20
are measured by it.

**The `scripts/` tree has become a dumping ground.** Nine files sit there with no shared
purpose. `generate_theme_data.py` is run by `ci.yml`'s generated-files job. Five are hardware
measurement and audit tools an operator runs by hand against real devices
(`ipv6_thread_probe.py`, `measure_merged_discovery.py`, `measurement_support.py`,
`thread_revalidation.py`, `serial_mac_audit.py`). One, `check_patch_coverage.py`, is maintainer
CI tooling invoked only from GSD phase plans: 16 files across v2.0 phases 10, 11, 13 and 14 call
it, and outside `.planning/` the only reference to it anywhere in the repository is its own test
file. Two are dead: `mdns_probe.py` has not been touched since 2026-04-17 and is superseded by
`ipv6_thread_probe.py`; `test_multiversion.py` has not been touched since 2026-01-14 and predates
the current 3.10 to 3.14 CI matrix.

**Coverage configuration reflects that confusion.** `pyproject.toml:128-131` measures `lifx`,
`generate_theme_data`, `scripts.measurement_support` and `scripts.thread_revalidation`. There is
no stated rule behind that list. CI-01 as written asked for `scripts.ipv6_thread_probe` to be
added, which would have deepened the confusion rather than resolving it: the probe is operator
tooling, is at 66% coverage today (670 statements, 225 missed, 12 partial branches), and is
unlikely to be run again now that v2.0's Thread revalidation is complete.

**The `codecov/patch` gate reported success without measuring anything.** On PR #208 the status
read `Coverage not affected when comparing ed17fdb...d68d36a` while 184 added executable source
lines went unmeasured against the 100% target. Issue #209 attributes this to a documentation-only
head commit causing Codecov to score that commit's diff rather than the PR's full range. **The
evidence gathered during this spec does not support that explanation.** CI ran on `d68d36a`,
under both the `pull_request` and `push` events, both successful, with all five Python-version
flags uploaded. The compare endpoints were correct: `ed17fdb..d68d36a` spans three commits, and
`d68d36a`'s parent is `a56bd2c`, not the base. `codecov/project` reported
`96.69% (target 90.00%)` on that same commit, so the reports themselves were sound. Codecov had
the right base, the right head and five valid reports, and still scored zero lines. The
mechanism is unknown; the leading hypothesis is Codecov's own fetch of the pull request diff
from the GitHub API. Because the cause is not established, this phase ships a cause-agnostic
guard rather than a fix aimed at an unverified theory.

The two states are distinguishable from the plain GitHub combined-status API with no Codecov
authentication, verified against live data during this spec:

| Commit | State | Description |
|--------|-------|-------------|
| `d68d36a` (vacuous) | success | `Coverage not affected when comparing ed17fdb...d68d36a` |
| `0be78e6` (scored)  | success | `100.00% of diff hit (target 100.00%)` |

**The v2.0 Phase 13 deferred item is recorded inconsistently.** `STATE.md:216` says
`deferred-items.md` "was never updated to close it out", while
`.planning/milestones/v2.0-phases/13-merged-discovery/deferred-items.md` already files the item
under `## Resolved`. The fix itself is present: `_GatedDiscoveryProducer` polls with
`await asyncio.sleep(0.001)` at `tests/test_network/test_discovery_coordinator.py:75-76`,
landed in `39bad58`, not the `fc61b98` the v2.0 close assumed. What is missing is evidence that
the fix is load-bearing rather than coincidental.

## Requirements

1. **Script tree triage** (roadmap CI-01, partial): `scripts/` holds only code CI executes.
   - Current: nine files in `scripts/` with no shared purpose. Two are dead
     (`mdns_probe.py` last touched 2026-04-17, `test_multiversion.py` last touched 2026-01-14),
     five are operator hardware tooling, one is maintainer CI tooling invoked only from GSD
     plans, one is run by `ci.yml`.
   - Target: `ipv6_thread_probe.py`, `measure_merged_discovery.py`, `measurement_support.py`,
     `thread_revalidation.py` and `serial_mac_audit.py` move to `.planning/scripts/`.
     `check_patch_coverage.py` moves to `.github/`. `mdns_probe.py` and `test_multiversion.py`
     are deleted. `scripts/` contains exactly `generate_theme_data.py`.
   - Acceptance: `ls scripts/*.py` lists exactly one file, `scripts/generate_theme_data.py`.
     The five measurement scripts and `check_patch_coverage.py` exist at their new paths and
     nowhere else. `mdns_probe.py` and `test_multiversion.py` exist nowhere. No moved module is
     importable from both an old and a new path.

2. **Reference integrity**: every path reference to a moved or deleted script is updated.
   - Current: `AGENTS.md` documents `python -m scripts.thread_revalidation`,
     `python -m scripts.ipv6_thread_probe` and `python -m scripts.measure_merged_discovery` and
     cites `scripts/serial_mac_audit.py` for the firmware 3.70+ MAC rule. `pyproject.toml` names
     four of the moving scripts in `[tool.pyright] include` at lines 99-106, sets
     `pythonpath = ["src", "scripts"]`, and carries two `--cov=scripts.*` targets.
   - Target: every one of those references names the file's new location, or is removed where
     the file is deleted. The `python -m` invocation form in `AGENTS.md` is retired entirely in
     favour of direct `uv run .planning/scripts/<script>.py` execution under PEP 723, and the
     `sys.path` explanation that made `python -m` necessary goes with it.
   - Acceptance: a repository-wide search for each old path returns no hit in tracked files
     outside the following historical records, each a record of commands run against the tree as
     it stood, so correcting them would rewrite history rather than repair a live instruction:
     `.planning/milestones/`, `.planning/STATE-ARCHIVE.md`, `.planning/MILESTONES.md`,
     `.planning/WINDOWS.md`, `.planning/research/`, and this phase's own before-state artefacts,
     `15-SPEC.md`, `15-CONTEXT.md`, `15-PATTERNS.md`, `15-DISCUSSION-LOG.md`, `15-REVIEWS.md`, and
     the phase's `15-0N-PLAN.md` and `15-0N-SUMMARY.md` files. `uv run pyright` passes. `uv run
     ruff check .` passes.

3. **Measured-tree rule** (roadmap CI-01, reversal): coverage measures the shipped library plus
   code CI executes, and nothing else.
   - Current: `--cov` targets are `lifx`, `generate_theme_data`, `scripts.measurement_support`
     and `scripts.thread_revalidation`, with no stated rule. CI-01 asked to add
     `scripts.ipv6_thread_probe`.
   - Target: the rule is stated in `AGENTS.md` as "measured: `src/lifx`, plus any code a CI job
     executes; not measured: operator and maintainer tooling", and applied. `--cov` targets
     become exactly `lifx` and `generate_theme_data`. CI-01 is recorded as reversed, with the
     reasoning that the probe is operator tooling rather than measured source, and issue #214 is
     closed on that basis.
   - Acceptance: `pyproject.toml`'s `addopts` contains exactly the two `--cov` targets above and
     no `--cov=scripts.*` entry. The rule appears in `AGENTS.md` as prose. `REQUIREMENTS.md`
     records CI-01 as reversed with its reasoning. Issue #214 is closed with that reasoning in
     the closing comment. The full suite runs and `codecov/project` still reports at or above
     its 90% target.

4. **Vacuous-gate guard** (roadmap CI-02): a pull request whose changed measured lines went
   unscored fails the build, established by the project's own count rather than by Codecov's
   report of itself.
   - Current: no such check exists. On PR #208 `codecov/patch` reported success against zero
     scored lines and nothing objected.
   - Target: a CI job computes, from the repository's own data, how many changed measured lines
     the coverage report actually classifies. It intersects the merge-base diff with the
     `coverage.xml` the test job already produces, counting only files the measured-tree rule of
     R3 admits. That computed count is authoritative. The job fails when the changed measured
     set is non-empty and none of those lines appear in the coverage report, and passes when the
     changed measured set is empty, so tests-only, `codecov.yml`-only, `uv.lock`-only and
     `ci.yml`-only pull requests are not broken. The intersection logic is reused from
     `check_patch_coverage.py` at its new `.github/` location by importing the module, not by
     reimplementing it, and the guard derives its own changed-file set rather than being passed
     one, so it does not depend on that tool's `--source` gap.
   - Also: the job reads the `codecov/patch` combined status for the head commit as a
     **cross-check only**. It matches the description against the two recorded forms, the scored
     form (`N% of diff hit (target M%)`) and the vacuous form
     (`Coverage not affected when comparing A...B`), and reports when Codecov's verdict diverges
     from the computed count. Divergence is recorded as evidence toward the mechanism R5 leaves
     unknown. An unrecognised description, or an absent or still-pending status after a bounded
     wait, is reported as an unusable cross-check and does not on its own decide the build,
     because the computed count already has.
   - Acceptance: given a fixture pull request range with at least one changed measured line and
     a `coverage.xml` classifying none of them, the guard fails. Given the same range and a
     report classifying them, it passes. Given a range whose changed files are all unmeasured
     (tests, `codecov.yml`, `uv.lock`, `ci.yml`), it passes regardless of the report. The
     failure output names the vacuous-gate condition and states the computed changed-measured
     and scored counts. Replaying the recorded `d68d36a` status description alongside a
     non-empty computed count produces a logged divergence; replaying `0be78e6` alongside a
     matching count does not. Every one of these runs locally from fixtures, with no pull
     request required.

5. **Issue #209 correction**: the record states what the evidence shows.
   - Current: issue #209 attributes the vacuous gate to a documentation-only head commit causing
     Codecov to score that commit's diff instead of the pull request's full range.
   - Target: #209 carries the corrected finding that CI ran on `d68d36a` under both event types
     with all five flags uploaded, that Codecov compared the correct three-commit range, and
     that `codecov/project` reported real data on the same commit, so the stated cause is not
     supported and the underlying mechanism remains unknown. The guard shipped under R4 is
     recorded as cause-agnostic by design.
   - Acceptance: #209 carries a comment stating each of those four evidence points, and its
     resolution names the guard rather than a root-cause fix.

6. **Coordinator teardown evidence** (roadmap TEST-02): the fix is proven load-bearing and the
   records agree.
   - Current: the fix is present at
     `tests/test_network/test_discovery_coordinator.py:75-76` from `39bad58`, not the `fc61b98`
     the v2.0 close assumed. `STATE.md:216` says `deferred-items.md` was never closed out, while
     that file already files the item under `## Resolved`. No evidence shows the fix is
     load-bearing.
   - Target: `test_non_last_detach_preserves_producer_and_last_detach_reaps_it` is run under a
     hard timeout set well above its observed runtime, and the process is shown to exit rather
     than merely the test to pass. The pre-fix `asyncio.to_thread(self.release.wait)` form is
     then temporarily reintroduced locally and the process is observed. Whatever that second run
     produces is recorded as-is, together with the platform and Python version, with no repeat
     attempts aimed at producing a hang. `deferred-items.md` and `STATE.md:216` are reconciled
     to one outcome naming this evidence.
   - Acceptance: both runs are recorded with their exact commands, timeout values, observed
     process exit behaviour, platform and Python version. `deferred-items.md` and `STATE.md`
     state the same outcome as each other and cite that evidence. If the reintroduced pre-fix
     form did not hang, that is what the records say.

## Boundaries

**In scope:**

- Moving five measurement and audit scripts to `.planning/scripts/`
- Moving `check_patch_coverage.py` to `.github/`
- Deleting `mdns_probe.py` and `test_multiversion.py`
- Moving `tests/test_scripts/` alongside its subjects and deselecting it from the default pytest
  run through the collection hook, run manually by passing the opt-in `--tooling` flag
- Updating `AGENTS.md`, `[tool.pyright] include`, `pythonpath`, `testpaths`, pytest markers and
  `--cov` targets for the new tree
- Stating the measured-tree rule in `AGENTS.md` and applying it
- Recording CI-01 as reversed and closing issue #214 with that reasoning
- A CI guard job that fails a vacuous `codecov/patch` success
- Correcting issue #209's stated cause
- Running the coordinator teardown test in both directions and reconciling the two records

**Out of scope:**

- Backfilling `scripts/ipv6_thread_probe.py` to 100%. It leaves the measured tree entirely, so
  the 225 missed statements and 12 partial branches stop being a coverage question.
- Fixing `check_patch_coverage.py`'s `--source` gap, where a changed file absent from the passed
  list is silently skipped (`11-REVIEWS.md:55`). Explicitly deferred by the operator. R4's guard
  imports the module but derives its own changed-file set, so it does not inherit the gap.
- Promoting `check_patch_coverage.py` to a required CI status check that enforces the 100%
  branch target. Considered and declined once its actual usage was established. R4 calls into
  the same intersection logic to answer a strictly weaker question, whether the changed measured
  set was scored at all, and does not enforce a coverage percentage.
- Extending R4's guard to enforce a minimum scored fraction. The computed count would make that
  nearly free, but it would turn the guard into the enforcement gate that was declined above.
  `codecov/patch` remains the enforcer of the 100% target.
- Changing `codecov.yml` to fix the vacuous gate. The patch status options are `target`,
  `threshold`, `branches`, `if_ci_failed`, `only_pulls`, `flags`, `paths`, `informational` and
  `if_not_found`; `base` was deprecated in July 2020. None addresses a diff that comes back
  empty, and the cause is unestablished, so a config change would target an unverified theory.
- Diagnosing the underlying Codecov mechanism. The guard is cause-agnostic by design; #209
  records the mechanism as unknown.
- Running the relocated tooling tests in any CI job. They are run manually.
- Rewriting archived milestone artefacts under `.planning/milestones/` to the new script paths.
  They are historical records of commands that were run against the tree as it stood.
- Every other v2.1 requirement. MDNS-09, DOCS-07, DOCS-08 and TEST-01 belong to Phase 16;
  DISC-04 and MDNS-10 to Phase 17; ANIM-05 and the typed Move effect to Phase 18; the theme
  library work to Phase 19; DOCS-09's em dash sweep to Phase 20.

## Constraints

- CI requires 100% **branch** patch coverage on changed measured lines, not just line coverage.
  Branch partials count.
- Zero runtime dependencies. Python 3.10 floor, so no `asyncio.TaskGroup`.
- Generated files (`src/lifx/protocol/*`, `src/lifx/products/registry.py`,
  `src/lifx/theme/data.py`) are never hand-edited.
- `docs/changelog.md` is produced by the release workflow and is not edited here.
- No live device serial, MAC address, IP address or hostname may reach a committed artefact.
  This binds R1 and R2 directly: the relocated measurement scripts and their 10,049 lines of
  tests are exactly the files most likely to carry hardware identifiers.
- Australian English in all prose and comments. No em dashes: recast the sentence rather than
  substituting a spaced hyphen.
- `.planning/**` is not in `ci.yml`'s `pull_request.paths` filter, so a change confined to the
  relocated scripts does not trigger CI. This is consistent with running their tests manually,
  and is a deliberate consequence of the chosen destination.
- Commits use Conventional Commit messages with `git commit -S -s`.

## Acceptance Criteria

- [ ] `ls scripts/*.py` lists exactly `scripts/generate_theme_data.py`
- [ ] The five measurement and audit scripts exist under `.planning/scripts/` and nowhere else
- [ ] `check_patch_coverage.py` exists under `.github/` and nowhere else
- [ ] `mdns_probe.py` and `test_multiversion.py` exist nowhere in the tree
- [ ] No moved module is importable from both its old and its new path
- [ ] A repository-wide search for each old script path returns no hit in tracked files outside
      the historical records enumerated in requirement 2's acceptance criterion
- [ ] `AGENTS.md` documents the direct `uv run .planning/scripts/<script>.py` invocations for the
      new locations, and no module-form invocation survives anywhere in the file
- [ ] `uv run pyright` passes and `uv run ruff check .` passes
- [ ] `pyproject.toml` `addopts` contains exactly `--cov=lifx` and `--cov=generate_theme_data`,
      and no `--cov=scripts.*`
- [ ] The measured-tree rule appears in `AGENTS.md` as prose
- [ ] The default pytest run imports the relocated tooling tests and then deselects them, so no
      tooling node id appears in its selected collection and the summary reports a non-zero
      deselected count; passing `--tooling` re-admits them
- [ ] `REQUIREMENTS.md` records CI-01 as reversed with its reasoning
- [ ] Issue #214 is closed with that reasoning in the closing comment
- [ ] The full suite passes and `codecov/project` reports at or above its 90% target
- [ ] The guard fails when the changed measured set is non-empty and `coverage.xml` classifies
      none of those lines
- [ ] The guard passes when the changed measured set is non-empty and the report classifies
      those lines
- [ ] The guard passes when every changed file is unmeasured (tests, `codecov.yml`, `uv.lock`,
      `ci.yml`), whatever the report says
- [ ] The guard's failure output names the vacuous-gate condition and states the computed
      changed-measured and scored counts
- [ ] The guard derives its own changed-file set rather than accepting a passed source list
- [ ] The guard reuses `check_patch_coverage.py`'s intersection logic by import, with no second
      implementation of it in the tree
- [ ] Replaying the recorded `d68d36a` description alongside a non-empty computed count logs a
      divergence; replaying `0be78e6` alongside a matching count does not
- [ ] An unrecognised, absent or pending `codecov/patch` status is reported as an unusable
      cross-check and does not by itself decide the build
- [ ] Every guard behaviour above is exercisable locally from fixtures, with no pull request
- [ ] Issue #209 carries a comment stating all four evidence points that contradict its recorded
      cause
- [ ] The coordinator test is recorded as run under a hard timeout with observed process exit
- [ ] The reintroduced pre-fix form's observed outcome is recorded as-is with platform and
      Python version
- [ ] `deferred-items.md` and `STATE.md:216` state the same outcome and cite the same evidence
- [ ] MUST NOT weaken coverage configuration, exclusions or tests to make this phase's own
      checks pass
- [ ] MUST NOT ship the R4 guard with `continue-on-error`, `|| true`, or any soft-fail that
      makes it incapable of failing the build
- [ ] MUST NOT let a live serial, MAC address, IP address or hostname reach a committed file
      while relocating the measurement scripts and their tests

## Edge Coverage

**Coverage:** 10/17 applicable edges resolved · 0 unresolved (7 dismissed, 1 backstop)

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | A stale copy at an old path shadowing the moved module. Criterion: no moved module importable from both paths |
| empty | R1 | ✅ covered | A stale-path search that finds nothing passes vacuously. Resolved positively instead: `scripts/` asserted to contain exactly one named file |
| ordering | R1 | ⛔ dismissed | The order of file moves carries no semantics; there is no equal-compare case |
| unclassified | R2 | ✅ covered | Marker silently deselecting a library test. Criterion: default run imports then deselects the tooling tests, reporting a non-zero deselected count; `--tooling` re-admits them. Operator chose ordinary checks over a count assertion |
| unclassified | R3 | ✅ covered | Dropping `scripts.measurement_support` and `scripts.thread_revalidation` from `--cov` changes project coverage. Criterion: exact target list, plus `codecov/project` still at or above 90% |
| adjacency | R4 | ✅ covered | The zero/nonzero scored boundary. Guard fires when the computed changed-measured set is non-empty and the report classifies none of it. Both sides are counted from repository data, so the boundary is measured rather than inferred |
| empty | R4 | ✅ covered | Tests-only, `codecov.yml`-only, `uv.lock`-only and `ci.yml`-only pull requests legitimately score zero. Criterion: guard passes on an empty computed changed-measured set |
| concurrency | R4 | ✅ covered | Codecov may not have posted the status when the guard runs. Resolved by demoting the status to a cross-check: an absent or pending status is reported as unusable and does not decide the build, because the computed count already has. The guard no longer races Codecov |
| encoding | R4 | ⛔ dismissed | No non-ASCII paths exist in this repository; byte versus code-point path length has no bearing |
| ordering | R4 | ⛔ dismissed | Status checks have no equal-compare ordering semantics |
| partial | R4 | 🧪 backstop | Added after the edge probe. A degraded diff fetch could yield a *partially* scored report, which a description parse reads as ordinary success. The guard still **fails** only on total-zero, since enforcing a fraction is out of scope, but the computed counts make a shortfall visible: when scored < changed-measured it logs a warning naming both numbers. Carry to plan-phase as a held-out test that a partially scored fixture warns without failing |
| adjacency | R5 | ⛔ dismissed | Posting one correction to one issue has no boundary case |
| empty | R5 | ⛔ dismissed | Posting one correction to one issue has no empty case |
| ordering | R5 | ⛔ dismissed | Posting one correction to one issue has no ordering case |
| adjacency | R6 | ✅ covered | The timeout boundary. Criterion: hard timeout set well above the observed 0.02s runtime, and hang detection is process exit rather than test result |
| empty | R6 | ✅ covered | The reintroduced pre-fix form may not hang. Criterion: record the outcome as-is with platform and Python version, no repeat attempts aimed at producing a hang |
| ordering | R6 | ⛔ dismissed | Two sequential observation runs have no equal-compare ordering semantics |

## Prohibitions (must-NOT)

**Coverage:** 3/4 applicable prohibitions resolved · 0 unresolved (1 dismissed)

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT add `pragma: no cover`, `coverage: ignore`, skip decorators, or edit coverage configuration in `codecov.yml` or `pyproject.toml` to make this phase's own checks pass | R3, R4 | resolved | verification: test. `check_patch_coverage.py --check-weakening-only` already detects exactly these patterns and treats `codecov.yml` and `pyproject.toml` as protected coverage files. Descriptor not captured: the wired check is a Python CLI rather than a `node-test` or `lint-rule`, so it stays fail-closed downstream per the soft-capture rule |
| MUST NOT ship the R4 guard with `continue-on-error`, `\|\| true`, or any soft-fail that makes it incapable of failing the build | R4 | resolved | verification: test. A gate that cannot fail is precisely the defect under repair, reintroduced. Descriptor not captured; check to be wired at plan time |
| MUST NOT let a live serial, MAC address, IP address or hostname reach a committed file while relocating the measurement scripts and their 10,049 lines of tests | R1, R2 | resolved | verification: test. Staged-diff privacy inspection, per the `AGENTS.md` privacy rule and the precedent set in v2.0 Phases 11 and 14. Descriptor not captured; check to be wired at plan time |
| MUST NOT close #209 or #214, or write a deferred-items outcome, stating a cause the gathered evidence does not support | R3, R5, R6 | dismissed | Operator judgement: not minted as a criterion. Covered by ordinary review discipline and by R5's and R6's own evidence-naming acceptance criteria |

**Canon referral:** path traversal and command injection in the R4 guard script are canon
security, owned by `/gsd-secure-phase` and Bandit. Not minted here.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                                        |
|--------------------|-------|------|--------|--------------------------------------------------------------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Reframed from "add the probe to coverage" to a tree rule      |
| Boundary Clarity   | 0.88  | 0.70 | ✓      | Four significant exclusions locked, each with reasoning       |
| Constraint Clarity | 0.78  | 0.65 | ✓      | Privacy constraint binds R1/R2 directly                       |
| Acceptance Criteria| 0.86  | 0.70 | ✓      | 30 pass/fail criteria, of which 3 are negative                |
| **Ambiguity**      | 0.137 | ≤0.20| ✓      | Amended after post-spec review of R4                         |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

**Previously flagged, now resolved.** An earlier revision recorded R4's trigger predicate as
derived rather than locked, because "at least one changed measured line" was an inference about
which pull request shapes legitimately score zero. The amendment making the computed count
authoritative dissolves that: the guard measures both sides from repository data instead of
inferring either, so the predicate is exact. No dimension is below minimum and nothing is left
for the planner to treat as an assumption.

## Interview Log

| Round | Perspective     | Question summary                                  | Decision locked                                                                 |
|-------|-----------------|---------------------------------------------------|---------------------------------------------------------------------------------|
| 1 | Researcher      | CI-02 mechanism: prevent or detect?               | Both a CI gate and a guard (later narrowed to guard only in round 5)             |
| 1 | Researcher      | CI-01 scope beyond the named probe                | Reframed by operator: question whether these scripts should exist in `scripts/`  |
| 1 | Researcher      | Accept the probe's 66% against the project gate?  | Superseded: if included it must be 100%, which drove the relocation instead      |
| 2 | Simplifier      | Backfill the probe to 100%?                       | Superseded: the probe is unlikely to run again, so it leaves the measured tree   |
| 2 | Simplifier      | Handling of unreferenced and stale scripts        | Measurement scripts to `.planning/scripts/`, `check_patch_coverage.py` to `.github/`, `mdns_probe.py` and `test_multiversion.py` deleted |
| 3 | Boundary Keeper | Fate of the 593 relocated tooling tests           | Move with their subjects, deselected by default, run manually                    |
| 3 | Boundary Keeper | How to record CI-01 being asked wrongly           | Reversal plus a stated general rule for which trees are measured                 |
| 3 | Boundary Keeper | Where `serial_mac_audit.py` lands                 | Moves with the measurement scripts                                               |
| 4 | Failure Analyst | Is `check_patch_coverage.py` even used?           | Established: GSD plans only, 16 files, never CI. Promotion to CI declined        |
| 4 | Failure Analyst | Fix the `--source` silent-skip gap?               | Out of scope; tracked for a later phase                                          |
| 4 | Failure Analyst | Evidence standard for TEST-02                     | Bounded reproduction in both directions                                          |
| 5 | Seed Closer     | Is there a `codecov.yml` fix?                     | No. Established that #209's stated cause is unsupported; guard is cause-agnostic |
| 5 | Seed Closer     | Which trees are measured                          | Shipped library plus CI-run code                                                 |
| 6 | Seed Closer     | How the relocated tooling tests get run           | `tooling` marker, run manually, no CI job                                        |
| 6 | Seed Closer     | Anti-vacuity assertions on the phase's own checks | Ordinary checks are enough                                                       |
| 6 | Seed Closer     | Guard mechanism, given Codecov uncertainty        | Parse the status description, fail-closed on anything unrecognised               |
| 7 | Failure Analyst | Post-spec review: is the parse the right mechanism? | Amended. Computed count from merge-base diff intersected with `coverage.xml` is authoritative; the status parse is demoted to a cross-check. Driven by the parse's blindness to a *partially* scored report and by its dependence on the component most likely to have failed |

---

*Phase: 15-coverage-gate-and-test-suite-health*
*Spec created: 2026-09-05*
*Next step: /gsd-discuss-phase 15 for implementation decisions (guard job placement, marker naming, move mechanics)*
