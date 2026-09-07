---
phase: 15
phase_name: "Coverage Gate and Test-Suite Health"
project: "lifx-async"
generated: "2026-09-07"
counts:
  decisions: 9
  lessons: 8
  patterns: 7
  surprises: 6
missing_artifacts: []
---

# Phase 15 Learnings: Coverage Gate and Test-Suite Health

## Decisions

### Reverse CI-01 rather than implement it

The requirement asked for the IPv6 Thread probe to be added to coverage collection. The phase
recorded it as reversed instead: the probe is operator tooling an operator runs by hand against
real hardware, and nothing in CI executes it.

**Rationale:** Adding it would have contradicted the Measured Tree rule the same phase was
writing, that coverage measures the shipped library plus code a CI job executes and nothing else.
A requirement can be wrong, and the honest resolution is to record the reversal with its reasoning
rather than satisfy the letter of it.
**Source:** 15-05-SUMMARY.md, REQUIREMENTS.md, 15-ISSUE-214-COMMENT.md

### Flat sibling imports over a sys.path bootstrap for the relocated scripts

Relocated scripts import their shared helper as `from measurement_support import ...` rather than
through a package path or an injected `sys.path` entry.

**Rationale:** Python places a directly executed script's own directory on `sys.path[0]`, so the
import resolves with nothing added. This kept the scripts runnable as `uv run <path>` and removed
the `python -m` requirement that the previous package-qualified form imposed.
**Source:** 15-02-SUMMARY.md, 15-CONTEXT.md (D-01)

### Derive the guard's authoritative line set from coverage.py, never from the report under test

`patch_coverage_guard.py` computes each changed file's executable-line set through
`Coverage(config_file=...).analysis2(path)` against the checked-out source, not from the
`coverage.xml` it is checking.

**Rationale:** A report that fails to classify a line would otherwise define that line out of
existence, which is precisely the vacuous-pass failure the guard exists to catch. Sourcing the
denominator independently is what makes the comparison meaningful.
**Source:** 15-03-PLAN.md, 15-03-SUMMARY.md

### Treat codecov/patch as an advisory cross-check that can never decide the build

The guard reads the `codecov/patch` combined status, reports agreement, divergence or
unusability, and fixes its own exit code before that read happens.

**Rationale:** The component most likely to have failed on the originating incident is the one
that would otherwise be trusted. A cause-agnostic guard computing both sides from repository data
does not inherit the suspect component's failure mode.
**Source:** 15-03-PLAN.md, COVERAGE.md

### Deselect tooling tests by collection hook rather than a marker expression in addopts

`addopts` carries no `-m` expression. Deselection happens in `pytest_collection_modifyitems`,
keyed on an explicit flag table and reported through `config.hook.pytest_deselected`.

**Rationale:** The deselected count stays visible in the run summary, so the exclusion is
announced rather than silent. A default run still imports the tooling modules before deselecting
them, so an import error or top-level side effect there still reaches the default run.
**Source:** 15-01-SUMMARY.md, 15-CONTEXT.md (D-09, D-12)

### Widen the existing bandit exclude rather than invent a new exemption mechanism

When the relocated tooling test stopped matching bandit's `^tests/` exclude, the fix widened that
one pattern to `^(tests/|\.planning/scripts/tests/)`.

**Rationale:** The relocated files are ordinary test files that changed path. Their
`subprocess.run(["git", ...])` calls were already unflagged at the old location, so the finding
was a path artefact rather than new risk.
**Source:** 15-01-SUMMARY.md

### Record the pre-fix reproduction in a scratch worktree via a committed patch

The defective `await asyncio.to_thread(self.release.wait)` form was reintroduced only inside a
throwaway `git worktree`, applied from a committed patch file, and never entered the tracked tree.

**Rationale:** The patch file becomes the reproducible artefact while the defective code never
reaches a commit on the branch. The worktree baseline is captured after removing any stale
experiment worktree, so the cleanup gate cannot be satisfied by an entry it should have required
absent.
**Source:** 15-04-PLAN.md, 15-04-SUMMARY.md

### Amend the locked SPEC rather than let a plan widen the boundary by assumption

`15-SPEC.md` R2's acceptance criterion was formally amended from a single exclusion to a
twelve-name enumeration, and the plan's sweep pathspec was made to match it item for item.

**Rationale:** A plan cannot widen a locked acceptance boundary by recording an assumption. The
enumeration and the sweep's pathspecs are one list written twice, so a file missing from either
becomes a gate that fails on a record nobody is allowed to correct.
**Source:** 15-05-SUMMARY.md

### Close issue #209 alongside #214, diverging from SPEC R5

At the Task 4 checkpoint the operator selected `publish-both-close-209`, closing an issue whose
underlying mechanism remains unestablished.

**Rationale:** CI-02's guard mitigates the failure mode the issue describes, and the published
comment states the mechanism as unknown rather than asserting an unsupported cause. The divergence
from R5 is recorded in the publication record rather than glossed.
**Source:** 15-ISSUE-PUBLICATION-RECORD.md, 15-05-SUMMARY.md

---

## Lessons

### Relocation breaks path arithmetic that no type checker or linter sees

`measure_merged_discovery.py` computed its repository root as `parents[1]`, correct at
`scripts/` and one level too shallow at `.planning/scripts/`. Nothing static caught it; it
surfaced only when the full tooling suite ran.

**Context:** The failure was silent in the sense that mattered. The function stopped rejecting an
alias-map path inside the repository, so a safety check quietly stopped checking.
**Source:** 15-02-SUMMARY.md (deviation 2)

### A gate can be red for reasons that have nothing to do with what it guards

The coverage-exemption sweep was permanently red on a defensive `pragma` in `.github/` and a
fixture string literal, both outside the measured tree by the phase's own rule. The gate's
pathspec contradicted the rule the same phase wrote.

**Context:** A gate whose cheapest resolution is deleting legitimate code is worse than no gate.
The correct fix was narrowing its scope to match the rule, then proving the narrowing was not a
blinding by re-testing against three real exemptions.
**Source:** 15-SECURITY.md, 15-05-SUMMARY.md

### An accepted risk can be narrower than the exposure it names

T-15-31 accepted that the guard's tests sat outside CI, with "a broken guard fails closed" as the
compensating control. That control presupposed the guard runs, and `.github/**` was also missing
from the trigger, so for a pull request confined to `.github/*.py` the guard did not run either.

**Context:** Acceptance was recorded at plan time against a correct reading of one path, and the
phase then moved a second file into the same uncovered space. The acceptance did not follow.
**Source:** 15-SECURITY.md, 15-REVIEW.md

### Moving a file out of a CI path filter silently removes it from CI

Before the phase, `check_patch_coverage.py` matched `scripts/**` and its test matched `tests/**`.
After relocation into `.github/`, neither matched anything in `pull_request.paths`.

**Context:** The relocation was correct on its own terms and the trigger filter was never
touched, so nothing flagged the regression. The lesson is that a path filter is part of a file's
contract, and moving the file breaks it.
**Source:** 15-SECURITY.md, 15-REVIEW.md

### A staged-add failure can land a commit that looks complete and is not

An early `git add` listing a since-renamed path failed atomically, and the narrower retry never
re-included the relocated test file's content edit. Task 1's first commit landed the bare `git mv`
without the import and marker edit.

**Context:** Caught only by a deliberate post-commit `git diff HEAD~1..HEAD` inspection before
moving on. The habit of reading back what actually landed is what saved it.
**Source:** 15-01-SUMMARY.md

### Adding pyright extraPaths can surface diagnostics in files it did not previously reach

`extraPaths = [".planning/scripts"]` changed pyright's execution-environment resolution enough
that a pre-existing monkeypatch line, unchanged since before the phase, began reporting
`reportPrivateImportUsage`.

**Context:** The diagnostic was real but the code was not new. Suppressing it at the one line was
right; exporting the private symbol from library code to satisfy a tooling config would have been
the tail wagging the dog.
**Source:** 15-02-SUMMARY.md (deviation 3)

### Bandit flags a blacklisted import separately from the call that uses it

The plan called for annotating the XML parse (B314). Bandit also flags the
`from xml.etree import ElementTree` import itself (B405), which the plan text did not name.

**Context:** Two annotations were needed where the plan anticipated one. Worth knowing when
budgeting for a security-linted new file.
**Source:** 15-03-SUMMARY.md (deviation 1)

### A validator's expected schema is not always the schema the artefact was written to

The `api-coverage` gate parses exactly three columns and reads the decision from column index 1.
`COVERAGE.md` carried four columns with an endpoint ahead of the disposition, so every row failed
despite every row carrying a valid decision and reason.

**Context:** Nine errors that read like an undecided matrix were a table-shape mismatch. Reading
the validator's source settled in one minute what the error text framed misleadingly.
**Source:** api-coverage.cjs, COVERAGE.md

---

## Patterns

### Prove a narrowed gate is not a blinded gate

After narrowing the exemption sweep's pathspec, re-test it against three real violations: a
`pragma` in shipped source, a `pragma` at a post-move path inside the newly excluded parent, and
a skip decorator in an untracked new file. Confirm the resolved-path floor still holds.

**When to use:** Any time a gate's scope is reduced to clear a false positive. Narrowing and
blinding are indistinguishable from the green result alone.
**Source:** 15-SECURITY.md

### Non-vacuity floors on scoped gates

The exemption sweep prints `measured-scope-files=` and fails below 100; the em dash sweep prints
`gated-added-lines=` and fails below 200. A mistyped or stale pathspec fails loudly instead of
certifying an empty scan.

**When to use:** Any gate whose scope is a pathspec. The floor is what distinguishes "found
nothing" from "looked nowhere".
**Source:** 15-05-PLAN.md, 15-02-PLAN.md

### Idempotent publication with a committed pre-publication baseline

Before the first irreversible public write, commit a record of issue state and comment count.
After each post, append a transaction line carrying the returned identifier and the draft's blob
hash. On resume, look for the approved body on the issue before posting anything.

**When to use:** Any workflow step that cannot be undone, only edited, with the edit history
publicly visible. The baseline is what makes the comment-count postcondition measurable at all.
**Source:** 15-ISSUE-PUBLICATION-RECORD.md, 15-05-PLAN.md

### Detect a hang by process exit and wall time, not by the test result line

The TEST-02 observation ran the child under `faulthandler.dump_traceback_later(exit=True)` and
judged the outcome on whether the process exited, because the recorded failure mode happens after
the test reports, inside `threading._shutdown`.

**When to use:** Any teardown, shutdown or atexit-adjacent hang. `pytest-timeout`'s thread method
cannot fire on a hang that occurs after the result is printed.
**Source:** 15-04-PLAN.md, 15-TEST-02-EVIDENCE.md

### Negative control on the instrument before trusting its readings

The observation runner was run against a deliberately invalid node id to prove it propagates
pytest's real exit code (recorded as child exit 4) rather than always reporting a clean teardown.

**When to use:** Whenever an instrument's clean result is the evidence. A tool that cannot report
failure has not reported success.
**Source:** 15-TEST-02-EVIDENCE.md

### Assert a marker policy through the AST, not a source-text search

The tooling marker policy test reaches its verdict via `ast.parse` and a walk of `Module.body`
rather than grepping source text.

**When to use:** Any check on module-level declarations. A text search is satisfied by a comment,
a docstring or a function-local assignment, none of which the runtime reads as a module-level
marker, so a search-based guard would itself report success on a file it never checked.
**Source:** 15-01-PLAN.md

### A test that skips before its subject exists and asserts the moment it lands

The workflow-shape test was written in Task 2, before Task 3 wired the CI step. It skips when the
named step is absent and starts asserting real content once the step exists, with no further edit.

**When to use:** Cross-task ordering within a phase, where a test naturally precedes its subject.
Avoids both a failing test and a forgotten follow-up edit.
**Source:** 15-03-SUMMARY.md

---

## Surprises

### The pre-fix hang reproduced on the single permitted attempt

The plan forbade repeating the observation in pursuit of a hang, so a non-reproduction would have
been recorded as-is. It reproduced first time: the child watchdog fired at 60s with a thread dump
naming a default-executor worker blocked in `threading.Event.wait()`.

**Impact:** Settled the v2.0 Phase 13 deferred item on evidence, and identified commit `39bad58`
rather than the `fc61b98` the v2.0 close had assumed as the load-bearing fix. The record now
names the right commit.
**Source:** 15-TEST-02-EVIDENCE.md, 15-04-SUMMARY.md

### The phase shipped a guard against vacuous coverage while leaving the weakening check evadable

`check_weakening()` reads `fields[0]` and `fields[-1]` from `git diff --name-status`, so a rename
never starts with `D` and only the new basename is tested. Renaming a test out of `tests/`, or
renaming `pyproject.toml` while editing it, evades both checks.

**Impact:** Reproduced against git 2.50.1 defaults. It predates the phase (100% rename similarity
across the fork) and the tool is invoked by no workflow and no pre-commit hook, so it is a latent
robustness defect rather than a live control failure. Carried forward as a follow-up rather than
fixed in-phase.
**Source:** 15-REVIEW.md, 15-SECURITY.md

### The relocation moved 549 tests out of the default suite

The default run went from 4805 passed / 56 deselected to 4256 passed / 631 deselected. The total
is unchanged at 4861; the tooling tests are now opt-in behind `--tooling`.

**Impact:** Intended and correct, but the headline pass count dropping by 549 is the kind of
number that reads as a regression at a glance. Worth stating explicitly wherever the figure
appears.
**Source:** 15-01-SUMMARY.md, 15-02-SUMMARY.md

### Two independent reviews found the CI path filter gap separately

The deep code review flagged `.github/**` missing from `pull_request.paths` as a blocker, and the
security audit reached the same file from the opposite direction, by testing whether T-15-31's
accepted risk actually covered the exposure it named.

**Impact:** Convergence from two different starting points raised confidence enough to fix it
in-phase rather than defer. The audit's framing was sharper: it established the regression was
phase-introduced, not inherited.
**Source:** 15-REVIEW.md, 15-SECURITY.md

### A GitHub API read-back adds a trailing newline

The retrieved comment bodies did not diff empty against the committed drafts. One extra trailing
newline separated them.

**Impact:** Momentarily looked like a content divergence on an irreversible public write. Resolved
by stripping exactly one trailing newline from both sides and by confirming the recorded blob
hashes matched the committed drafts exactly.
**Source:** 15-05-SUMMARY.md

### Ruff reclassifies first-party imports purely from the importing file's location

Moving the scripts made ruff stop treating `scripts.measurement_support` as first-party, so it
reordered the import block relative to `lifx.*` imports. This fired from the location change
alone, before the import name was touched, and re-fired identically on retry.

**Impact:** Five of the eight moved files carried a mechanical import reorder in the relocation
commit. Verified as import-block-only, and the moves still recorded as renames at 99 to 100%
similarity.
**Source:** 15-02-SUMMARY.md (deviation 1)
