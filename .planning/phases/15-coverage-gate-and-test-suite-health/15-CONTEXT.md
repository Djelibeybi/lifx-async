# Phase 15: Coverage Gate and Test-Suite Health - Context

**Gathered:** 2026-09-05
**Status:** Ready for planning

<domain>
## Phase Boundary

The project's own verification machinery: which trees are measured, which tooling leaves the
measured tree, and what fails a build. Delivers the `scripts/` triage, the measured-tree rule,
a CI job that counts for itself whether a pull request's changed measured lines were scored, and
the closure of the v2.0 Phase 13 coordinator teardown item.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**6 requirements are locked.** See `15-SPEC.md` for full requirements, boundaries, and
acceptance criteria.

Downstream agents MUST read `15-SPEC.md` before planning or implementing. Requirements are not
duplicated here.

**In scope (from SPEC.md):**
- Moving five measurement and audit scripts to `.planning/scripts/`
- Moving `check_patch_coverage.py` to `.github/`
- Deleting `mdns_probe.py` and `test_multiversion.py`
- Moving `tests/test_scripts/` alongside its subjects and deselecting it from the default pytest
  run, run manually
- Updating `AGENTS.md`, `[tool.pyright] include`, `pythonpath`, `testpaths`, pytest markers and
  `--cov` targets for the new tree
- Stating the measured-tree rule in `AGENTS.md` and applying it
- Recording CI-01 as reversed and closing issue #214 with that reasoning
- A CI guard job that fails a vacuous `codecov/patch` success
- Correcting issue #209's stated cause
- Running the coordinator teardown test in both directions and reconciling the two records

**Out of scope (from SPEC.md):**
- Backfilling `scripts/ipv6_thread_probe.py` to 100%
- Fixing `check_patch_coverage.py`'s `--source` gap
- Promoting `check_patch_coverage.py` to a required CI status check enforcing the 100% target
- Extending R4's guard to enforce a minimum scored fraction
- Changing `codecov.yml` to fix the vacuous gate
- Diagnosing the underlying Codecov mechanism
- Running the relocated tooling tests in any CI job
- Rewriting archived milestone artefacts under `.planning/milestones/` to the new script paths
- Every other v2.1 requirement (Phases 16 to 20)

</spec_lock>

<decisions>
## Implementation Decisions

### Import and invocation model for relocated tooling

Dot-prefixed directories cannot be Python packages, so `.planning` and `.github` cannot carry a
`scripts.measurement_support`-style import. Three scripts depend on exactly that today
(`ipv6_thread_probe.py:101`, `measure_merged_discovery.py:41`, `thread_revalidation.py:46`).

- **D-01:** Sibling imports become flat: `from measurement_support import ...`. No `sys.path`
  bootstrap and no new `pythonpath` entry. When a file is run directly, Python places the
  script's own directory on `sys.path[0]`, so a flat import resolves with nothing added. This
  keeps every import at the top of the file, as the project's Python conventions require.
- **D-02:** `pythonpath` stays `["src", "scripts"]`. It is **not** reduced. Discussion initially
  proposed dropping the `scripts` entry; that is wrong, because
  `tests/test_theme/test_theme_generator.py:36` does `import generate_theme_data` through it and
  `generate_theme_data.py` is the one file remaining in `scripts/`. The decision is that no new
  entry is added, not that an existing one is removed.
- **D-03:** The four scripts lacking one gain a PEP 723 header mirroring
  `scripts/serial_mac_audit.py:1-7`, including a `[tool.uv.sources]` block binding
  `lifx-async` to the working tree: `{ path = "../../", editable = true }` from
  `.planning/scripts/`. Without that block a PEP 723 script resolves `lifx-async` from PyPI
  rather than the checkout, which would silently measure the published library instead of the
  one under development. The four carry 5 to 15 `lifx` imports each.
  **Reversibility:** costly. Undoing means rewriting the dependency declaration and the
  documented invocation in `AGENTS.md` for every relocated script at once.
- **D-04:** The documented invocation becomes `uv run .planning/scripts/<script>.py`. The
  `python -m scripts.<module>` form and the `AGENTS.md` passage explaining why `-m` was
  necessary (repository root on `sys.path`) are both retired, since the underlying constraint
  disappears with the package-qualified import.
- **D-05:** The relocated tests reach their subjects through a `conftest.py` beside them that
  inserts `.planning/scripts` on `sys.path` at collection. Tests import rather than execute, so
  `sys.path[0]` does not help them. Keeping this in test infrastructure rather than `pyproject`
  confines it to the tooling tests, which are excluded by default anyway.

### Vacuous-gate guard placement

- **D-06:** The guard runs as a **step inside the ubuntu test job**, reading the `coverage.xml`
  already on disk after the Codecov upload step. No artifact upload, no separate job.
- **D-07:** It runs in the designated `ubuntu-latest` + Python `3.10` cell, reusing the cell
  `.github/workflows/ci.yml:193` already singles out as the must-not-skip IPv6 cell, whose
  comment records that it "is present in every matrix configuration, including the reduced
  ubuntu-only path". One evaluation, one result.
- **D-08:** Single-report semantics are accepted, with a known narrow gap recorded rather than
  closed. Matrix cells are separate runners and cannot union their reports without artifacts, so
  D-06 and a matrix union are mutually exclusive. The gap is bounded by measurement: the library
  contains exactly **one** version-gated site (`src/lifx/const.py:175`,
  `if sys.version_info < (3, 11)`) and **zero** platform-gated sites. Because the guard fails
  only on total-zero rather than per-line coverage, a false failure needs a pull request that
  changes only that one block and nothing else measured. If it ever misfires, the upgrade path
  is artifacts plus a union job.

### Test selection mechanism

- **D-09:** Deselection is **opt-in flags via the existing collection hook**, not a growing `-m`
  negation. `tests/conftest.py:141` already implements `pytest_collection_modifyitems` and adds
  markers conditionally; the same hook deselects any item carrying an opt-in marker unless its
  flag was passed. `addopts` carries no `-m` expression at all afterwards.
  **Reversibility:** costly. Reverting means restoring the `-m` expression in `addopts` and
  re-teaching every caller, including `tests/test_pytest_policy.py`, which asserts on `addopts`.

  Rationale: `-m` is a selection filter, not an additive switch. `-m benchmark` means "run only
  benchmarks", and `-m "benchmark and tooling"` would select the intersection, which is empty.
  There is no `-m` spelling of "the normal suite plus tooling". Flags compose additively and a
  future fifth category becomes a table entry rather than a longer negation.
- **D-10:** `--tooling` and `--benchmark` are the flags. Benchmarks migrate to the same
  mechanism so one model governs both, rather than leaving two coexisting.
- **D-11:** The marker is applied as module-level `pytestmark = pytest.mark.tooling` in each of
  the four relocated test files. Explicit and greppable: a new tooling test that omits it is
  visibly wrong rather than silently included.
- **D-12:** `testpaths` becomes `["tests", ".planning/scripts/tests"]`. Without this the
  relocated tests are never collected and no marker or flag can act on them, which would make
  the exclusion an accident of `testpaths` rather than the chosen mechanism.
- **D-13:** `tests/test_pytest_policy.py:76` asserts on `addopts` and must be updated as part of
  D-09, not left to fail. It is the repository's guard on pytest policy, so it should assert the
  new mechanism rather than merely stop asserting the old one.

### TEST-02 evidence mechanics

- **D-14:** The pre-fix `asyncio.to_thread(self.release.wait)` form is reintroduced through a
  `.patch` file committed under the phase directory and applied only to a scratch checkout. The
  patch is the reproducible artefact; the defective form never enters the tree.
- **D-15:** The observation is a **subprocess under a wall-clock timeout**, recording exit code
  and elapsed time. Suite-level `pytest-timeout` explicitly cannot serve here: the Phase 13
  record shows the test *passes* and pytest then hangs in `threading._shutdown` awaiting
  `concurrent.futures.thread._python_exit`, which is after the test reports, and
  `timeout_method = "thread"` never fires.
- **D-16:** On timeout the run captures a `faulthandler` thread dump, so the evidence names the
  blocked worker and `_python_exit` rather than recording only that something hung. This matters
  because SPEC R6 permits a non-hanging second run to be recorded as-is: a dump distinguishes
  "did not reproduce" from "hung for an unrelated reason".

### Claude's Discretion

- Exact flag names and their `--help` text, the deselect reporting form, and how the opt-in
  marker set is registered.
- The relocated test directory's exact name and layout beneath `.planning/scripts/`.
- Patch filename, evidence filenames, and the evidence document's structure.
- The wall-clock timeout value, provided it is far above the test's observed 0.02s runtime.
- Guard script location, language, and internal structure, provided it imports
  `check_patch_coverage.py`'s intersection logic rather than reimplementing it and derives its
  own changed-file set.
- Ordering and commit granularity of the moves, deletions and configuration edits.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-SPEC.md`: Locked requirements,
  boundaries and acceptance criteria. MUST read before planning.
- `.planning/ROADMAP.md`: Phase 15 goal, success criteria, and the v2.1 constraints binding
  every phase.
- `.planning/REQUIREMENTS.md`: CI-01, CI-02 and TEST-02 as originally written. CI-01 is
  reversed by this phase and the file records that reversal.

### Repository guidance
- `AGENTS.md`: Canonical shared guidance. Carries the privacy rule, the measurement-script
  invocation docs that D-04 rewrites, and the measured-tree rule that R3 adds. `CLAUDE.md` is an
  `@AGENTS.md` import only, per Phase 14 D-24.
- `.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-CONTEXT.md`: D-17 and
  D-19 on shared measurement primitives and in-memory identity resolution; D-24 on the
  `AGENTS.md`/`CLAUDE.md` split.

### Configuration under change
- `pyproject.toml`: `addopts`, `testpaths`, `pythonpath`, markers, `[tool.coverage.run]`,
  `[tool.pyright] include` (lines 99-106 name four of the moving scripts).
- `codecov.yml`: Flag paths, the 90% project target, the 100% patch target and the ignore list.
  Not edited by this phase; read to understand what the guard sits beside.
- `.github/workflows/ci.yml`: The `changes` job's `gh pr diff` filter, the `pull_request.paths`
  filter, the test matrix, and line 193's designated always-present cell.

### TEST-02 subject and records
- `tests/test_network/test_discovery_coordinator.py:75-76`: The present fix, polling with
  `await asyncio.sleep(0.001)`, landed in `39bad58`.
- `.planning/milestones/v2.0-phases/13-merged-discovery/deferred-items.md`: Files the item
  under `## Resolved` with root cause and resolution notes.
- `.planning/STATE.md:216`: Records the same item as never closed out. The two disagree; R6
  reconciles them.

### Prior findings that bind this phase
- `.planning/milestones/v2.0-phases/11-mdns-hardening/11-REVIEWS.md:55`: The
  `check_patch_coverage.py` `--source` silent-skip finding. Out of scope to fix; the guard
  avoids inheriting it by deriving its own file set.
- `.planning/STATE.md:139`: `check_patch_coverage.py` cannot pass its changed-excluded-line
  rule for a new script's own `if __name__ == "__main__":` guard. Relevant when the relocated
  scripts are re-checked.

### External issues
- https://github.com/Djelibeybi/lifx-async/issues/209: The vacuous patch gate. Its stated cause
  is contradicted by evidence recorded in `15-SPEC.md`; R5 corrects it.
- https://github.com/Djelibeybi/lifx-async/issues/214: Probe coverage collection. Closed by
  reversal under R3.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/serial_mac_audit.py:1-7`: The exact PEP 723 plus `[tool.uv.sources]` editable-path
  pattern D-03 replicates. Already proven in this repository; do not invent a variant.
- `tests/conftest.py:141`: `pytest_collection_modifyitems` already exists and already adds
  markers conditionally. D-09's opt-in deselection extends this hook rather than introducing a
  new mechanism.
- `scripts/check_patch_coverage.py`: Branch-aware diff-to-coverage intersection with 541 lines
  of tests behind it. The guard imports this; it does not reimplement the intersection.
- `.github/workflows/ci.yml:193`: The designated `ubuntu-latest` + `3.10` cell, with a comment
  explaining why it is always present. D-07 reuses that designation rather than minting another.

### Established Patterns
- Tests mirror source structure, and planning-adjacent tests can sit outside the default
  collection: `tests/test_theme/test_ceiling_supersession.py:17` documents that phase
  directories move to `.planning/milestones/` at milestone close and that `testpaths`
  deliberately excludes that harness. Precedent for tooling tests living apart from the library
  suite.
- Benchmarks are marked and excluded by default, so the repository already separates
  "run always" from "run when asked". D-09 changes the mechanism, not the principle.
- Ruff has no `exclude`, and pre-commit excludes only `^\.planning/phases/.*-EVENTS\.jsonl$`, so
  relocated scripts under `.planning/scripts/` stay linted and hooked without extra
  configuration.

### Integration Points
- The guard attaches after the Codecov upload step in the ubuntu test job, where `coverage.xml`
  is already on disk.
- `.planning/**` is absent from `ci.yml`'s `pull_request.paths` filter, so a change confined to
  the relocated scripts does not trigger CI at all. This is consistent with D-09's manual-run
  model and is a deliberate consequence of the destination.
- `--cov=scripts.measurement_support` and `--cov=scripts.thread_revalidation` disappear with the
  move, so project coverage shifts. R3's acceptance requires `codecov/project` to stay at or
  above its 90% target afterwards.

</code_context>

<specifics>
## Specific Ideas

- The operator explicitly preferred not to add a `pythonpath` entry in `pyproject.toml` for the
  relocated scripts. D-01 satisfies that by relying on `sys.path[0]` for direct execution and
  confining the test-side need to a local `conftest.py`.
- The operator questioned whether the deselection could be inverted so that categories are
  excluded unless named. That is what D-09 delivers, and it is the reason the mechanism changed
  from an `-m` negation to opt-in flags.
- `scripts/` was described as a place where things accumulated that "were created to test or
  check an assumption but probably no longer need to exist". That framing, not CI-01's literal
  wording, is what drove the triage.

</specifics>

<deferred>
## Deferred Ideas

- **Union coverage across the matrix**: If D-08's single-report guard ever misfires on the one
  version-gated site, the fix is artifact uploads plus a union job. Recorded so a future failure
  is a known upgrade rather than a rediscovery.
- **`check_patch_coverage.py` `--source` derivation**: Already out of scope in `15-SPEC.md`;
  restated here because the guard sits next to it and a planner may be tempted to fix it in
  passing.
- **Enforcing a minimum scored fraction in the guard**: The computed counts make this nearly
  free, but it would turn the guard into the enforcement gate that was deliberately declined.
  `codecov/patch` stays the enforcer of the 100% target.

</deferred>

---

*Phase: 15-coverage-gate-and-test-suite-health*
*Context gathered: 2026-09-05*
