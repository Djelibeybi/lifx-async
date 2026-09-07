---
phase: 15
reviewers: [codex, opencode, antigravity]
reviewed_at: 2026-09-05T07:08:40Z
plans_reviewed: [15-01-PLAN.md, 15-02-PLAN.md, 15-03-PLAN.md, 15-04-PLAN.md, 15-05-PLAN.md]
plans_at_commit: 9d6d214
review_round: 3
models:
  codex: "gpt-5.6-sol (reasoning=high)"
  opencode: "openrouter/z-ai/glm-5.3 (reasoning=high)"
  antigravity: "gemini-3.1-pro-high"
model_sources:
  codex: "pinned"
  opencode: "pinned"
  antigravity: "pinned"
---

# Cross-AI Plan Review — Phase 15 (round 3)

> Round 3, against the plans as revised at `9d6d214`. Round 2 reviewed `ef1cee0` and is
> superseded; it remains in git at `4811b07`. Round 1 is at `47932c3`.
>
> Lanes dispatched concurrently: 14.5 minutes wall clock. The prompt named what rounds 1 and 2
> already closed, so reviewers spent their budget on new ground rather than re-reporting fixed
> defects. It also forbade writing scratch files into the working tree, after round 2 left seven
> behind; `git status --porcelain` was empty at the end of this round.

## Codex Review

# Cross-AI Plan Review

## Overall assessment

The implementation design is strong and unusually well evidenced, but the phase is not ready to execute unchanged. The main blocker is that Plan 15-05 deliberately preserves several stale statements in the locked spec, leaving the completed phase unable to satisfy its own global acceptance criteria. I also reproduced two classes of false-green shell gate: collection pipelines that ignore pytest’s exit code, and stale-path sweeps that suppress `git grep` operational failures.

Executed checks included:

- Pyright analysed the expected 94 files with zero errors.
- The current coordinator test passed in approximately 0.03 seconds.
- The stale-path fixture returned the intended `matched=4`.
- The locked-spec hash matched `4b2a40d7889fa7111951a21250aff6f64243d3cd`.
- Simulated failing collection and broken `git grep` commands both produced exit code zero through the proposed gates.

No repository files or external issue state were changed.

## Plan 15-01: Tooling relocation tracer

### Summary

The tracer is technically sound and extends existing pytest machinery instead of inventing a parallel mechanism. Its direct policy tests are well designed, but three collection verification pipelines can report success despite pytest itself failing.

### Strengths

- The plan correctly extends the existing `pytest_addoption` and `pytest_collection_modifyitems` hooks found in [tests/conftest.py](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/conftest.py:105) and [tests/conftest.py](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/conftest.py:140).
- It accurately acknowledges that tooling modules are imported before deselection, including the remaining import-time exposure, in [15-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-01-PLAN.md:28).
- The AST-based module-marker policy test is substantially stronger than a source-text search.
- The default, `--tooling`, `--benchmark`, and unmarked-item behaviours are all covered directly.

### Concerns

- **MEDIUM:** The negated collection gate at [15-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-01-PLAN.md:260) uses the exit status of `grep`, not pytest. I reproduced a collection command exiting 2 with no matching node IDs and the complete gate still exited 0.
- **MEDIUM:** The positive `--tooling` pipeline at [15-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-01-PLAN.md:262) has the converse problem: a failing producer that prints one matching node ID makes `grep` return 0.
- **LOW:** The “deselected” count check at line 264 proves that something was deselected, not specifically the expected benchmark and tooling items. The direct policy tests mitigate this substantially.

### Suggestions

- Capture collection output and pytest’s exit code separately. Assert pytest returned zero before applying positive or negative `grep` checks.
- Retain the direct hook tests as the authoritative selection-policy verification; treat output parsing as an integration backstop.

### Risk Assessment

**MEDIUM.** The implementation mechanism is good, but the end-to-end collection gates do not currently prove successful collection.

## Plan 15-02: Remaining script relocation

### Summary

This plan has good ownership coverage and now accounts for the two default-suite consumers that would otherwise break collection. The PEP 723 and pyright design checks out. The principal remaining weakness is that the repository-wide stale-path sweep suppresses its own operational failures.

### Strengths

- The plan correctly owns real current consumers in [tests/test_discovery_observation.py](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/test_discovery_observation.py:21), [tests/test_network/test_connection_retry.py](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/test_network/test_connection_retry.py:32), and [src/lifx/network/connection.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/network/connection.py:53).
- The local-source PEP 723 binding follows the established pattern in [scripts/serial_mac_audit.py](/Volumes/External/Developer/Djelibeybi/lifx-async/scripts/serial_mac_audit.py:1).
- The pyright analysed-file count is a valuable non-vacuity gate. I ran its underlying calculation and confirmed 94 expected and 94 analysed files with zero errors.
- The privacy inventories match the current relocating corpus: 20 serials, 17 IPv4 addresses, 19 MAC addresses and 5 IPv6 addresses.

### Concerns

- **MEDIUM:** The stale-path sweep at [15-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-02-PLAN.md:753) places `|| true` around the entire pipeline. A `git grep` operational error therefore becomes empty output and `SWEEP-CLEAN`. I reproduced this using an invalid regular expression; the proposed gate exited 0.
- **LOW:** Revision prose still says the solution uses a PCRE negative lookbehind at [15-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-02-PLAN.md:232), while the runnable gate correctly uses normalisation and re-matching at lines 751–754.
- **LOW:** The privacy prohibition includes hostnames and account names in [AGENTS.md](/Volumes/External/Developer/Djelibeybi/lifx-async/AGENTS.md:19), but the automated gates cover only serials, IPv4, IPv6 and MAC-shaped values at [15-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-02-PLAN.md:755). The required staged-diff human inspection should be stated explicitly here.

### Suggestions

- Capture `git grep` output and status separately. Accept statuses 0 and 1, but fail on anything greater than 1 before normalising the output.
- Correct the stale PCRE revision text.
- Add an explicit final staged-diff privacy inspection covering hostnames and account names.

### Risk Assessment

**MEDIUM.** The relocation itself is well planned, but a principal integrity gate can false-green on operational failure.

## Plan 15-03: Vacuous coverage guard

### Summary

The guard’s core design is excellent: executable changed lines come from static coverage analysis, while `coverage.xml` supplies only the classified numerator. Its fixture matrix is thorough. Two verification semantics need tightening.

### Strengths

- The denominator is independent of the report being audited, directly addressing the vacuous-report failure class in [15-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-03-PLAN.md:503).
- The plan covers absent, present-but-unclassified, partially classified, excluded-only, malformed and configuration-drift cases.
- Placement after coverage generation is compatible with the current workflow at [.github/workflows/ci.yml](/Volumes/External/Developer/Djelibeybi/lifx-async/.github/workflows/ci.yml:182).
- Operational errors are explicitly separated from a genuine gate failure, which is the right contract for verification infrastructure.

### Concerns

- **MEDIUM:** The default-collection exclusion check at [15-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-03-PLAN.md:613) repeats Plan 15-01’s false-green negated pipeline.
- **MEDIUM:** The XML adapter instructions conflict internally. They say an outside source-root candidate must be refused, but then require fallback to the raw filename whenever no root resolves at [15-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-03-PLAN.md:326). An outside `<source>` plus `filename="src/lifx/example.py"` can therefore be re-keyed inside the repository through fallback, contrary to the promised traversal test at line 514.
- **LOW:** The plan accepts that changes confined to the guard or its tooling tests do not trigger CI. That follows from the current workflow filter, which excludes `.planning/**` and `.github/*.py`, at [.github/workflows/ci.yml](/Volumes/External/Developer/Djelibeybi/lifx-async/.github/workflows/ci.yml:9). This is documented, but remains a real maintenance risk.

### Suggestions

- Fix the collection pipeline as recommended for Plan 15-01.
- Permit raw-filename fallback only when `<sources>` is absent or empty. If source roots are present but all resolve outside the repository, reject or ignore that class entry without fallback.
- Consider a narrowly scoped workflow path for `.github/patch_coverage_guard.py`, even if the broader `.planning/**` tooling suite remains manual.

### Risk Assessment

**MEDIUM.** The coverage logic is strong, but the source-root contract needs an unambiguous safe implementation.

## Plan 15-04: Coordinator teardown evidence

### Summary

The observer and evidence design directly measures process termination instead of relying on a passing pytest result. That is exactly the correct test for the historical problem. The resume recovery path, however, contradicts the worktree-baseline postcondition.

### Strengths

- The plan correctly targets the current cancellation-safe polling implementation in [test_discovery_coordinator.py](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/test_network/test_discovery_coordinator.py:75).
- It resolves the real record disagreement between [deferred-items.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/milestones/v2.0-phases/13-merged-discovery/deferred-items.md:9) and [STATE.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/STATE.md:165).
- Propagating `pytest.main()` through `SystemExit`, adding a negative control, and combining an in-child faulthandler watchdog with a parent timeout are all strong evidence mechanics.
- The current focused test exits cleanly in approximately 0.03 seconds, supporting the chosen 60/90-second bounds.

### Concerns

- **MEDIUM:** The plan captures the worktree baseline before stale-worktree recovery at [15-04-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-04-PLAN.md:414). If that baseline contains a stale `15-TEST-02` registration, recovery removes it at lines 424–427. The final list can then neither equal the baseline nor contain zero experiment worktrees, contradicting both gates at lines 488–491.
- **LOW:** The non-zero pre-fix result classification relies on faulthandler or bound metadata to distinguish a hang from an ordinary failure. The evidence document must preserve stderr even for ordinary non-zero exits to support that distinction.

### Suggestions

- Clean any stale experiment worktree before capturing the baseline, or compare against a baseline filtered to exclude `15-TEST-02` entries.
- Keep the separate final assertion that no experiment worktree survives.

### Risk Assessment

**MEDIUM.** The central experiment is well designed, but its documented recovery route cannot satisfy its own cleanup gates.

## Plan 15-05: Documentation and external reconciliation

### Summary

The human approval and idempotent GitHub publication flow are excellent. This plan nevertheless contains the phase’s only clear blocker: it amends one locked-spec paragraph while explicitly preserving other acceptance statements that contradict the planned implementation.

### Strengths

- Public issue writes are gated by explicit human approval.
- Exact-body discovery before posting makes publication safely resumable at [15-05-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-05-PLAN.md:707).
- Returned comment identifiers are used for read-back rather than relying on the latest comment.
- The stale-path fixture is good and executed successfully with `matched=4` at [15-05-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-05-PLAN.md:488).
- The locked-spec outside-R2 hash currently reproduces exactly as documented at [15-05-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-05-PLAN.md:619).

### Concerns

- **HIGH:** Plan 15-05 requires every byte outside requirement 2 to remain unchanged at [15-05-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-05-PLAN.md:604), but the locked spec still says:
  - tooling is run by “passing the marker” at [15-SPEC.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-SPEC.md:181);
  - only `.planning/milestones/` is excluded from the global path sweep at [15-SPEC.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-SPEC.md:243);
  - `AGENTS.md` must document corrected `python -m` invocations at line 245;
  - the default run “collects only library tests” at lines 250–251, contrary to Plan 15-01’s explicit collect-then-deselect design.

  Executing the plan as written therefore leaves the completed phase failing its own locked acceptance criteria.
- **MEDIUM:** The action correctly rejects the old anchor at [15-05-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/15-coverage-gate-and-test-suite-health/15-05-PLAN.md:443), but acceptance criterion line 547 still requires that exact `(^|[^/])` anchor.
- **MEDIUM:** Both repository and draft sweeps suppress `git grep` failures through whole-pipeline `|| true` at lines 490 and 492. I reproduced a broken `git grep` command passing this gate with empty output.
- **LOW:** Pre-publication baselines and transaction records exist only in “working notes” at lines 701–735. Idempotence survives interruption through remote body matching, but the claimed original comment-count baseline may not.

### Suggestions

- Amend the locked spec in all affected locations, not only requirement 2:
  - replace “passing the marker” with the appropriate flag/direct-directory invocation;
  - update the global exclusion list;
  - replace `python -m` with direct PEP 723 invocations;
  - describe import-then-deselect accurately.
- Recompute the outside-edit hash after authorising those specific spec changes.
- Remove the stale anchored-pattern acceptance criterion and require normalisation/re-matching instead.
- Make `git grep` operational errors fatal.
- Persist pre-publication baselines in a named phase artefact before posting, or relax the acceptance claim for interruption recovery.

### Risk Assessment

**HIGH.** The external workflow is careful, but the locked acceptance contract and the planned final state cannot both be true.

## Final recommendation

Revise before execution. The minimum blocking changes are:

1. Reconcile all stale locked-spec statements with the chosen pytest and invocation mechanisms.
2. Make collection and stale-path verification preserve producer exit codes.
3. Correct Plan 15-04’s stale-worktree recovery order.
4. Remove the obsolete anchored-pattern acceptance criterion.
5. Clarify Plan 15-03’s source-root fallback rule.

After those changes, the phase should fall to **MEDIUM-LOW implementation risk**; its core architecture and test coverage are otherwise strong.


---

## OpenCode Review

# Cross-AI Plan Review — Phase 15 (Coverage Gate and Test-Suite Health)

Repo access confirmed: I read the working tree and executed commands where safe (pyright, coverage `analysis2`, pytest collection, privacy scans, the sweep fixture, `gh` queries). All scratch work stayed in `${TMPDIR}`; the repo tree is clean (`git status --porcelain` empty).

## Summary

These are the strongest plans I have reviewed in this series: after two cross-AI rounds, the load-bearing mechanisms are not merely argued but, in most cases, already executed against the real tree. I independently reproduced the pyright file-count math (`filesAnalyzed=94`), the coverage `analysis2` docstring/exclusion behaviour, the privacy-scan inventories (20/17/19/5 values, exact), the SPEC blob-hash gate, the ROADMAP block-comparison gate, and the GitHub issue state. The revision history has, however, left one genuine self-contradiction inside plan 15-05 (a round-1 acceptance criterion that the round-2 revision invalidated but did not rewrite), plus a cluster of count-based gates whose exit semantics disagree with their own `fails_when`, and one red-window verification gap in 15-01.

## Strengths

- **The guard's core mechanism is verified, not asserted.** I ran `Coverage(config_file='pyproject.toml').analysis2()` against the real config: docstrings and comments are not statements, `if __name__ == "__main__":` plus body lands in the excluded set, and no data file is needed. The source-authoritative denominator (T-15-27) holds; both the present-but-unclassified false pass and the docstring-only true pass are reachable through one mechanism. (`coverage 7.15.0`, this repo.)
- **T-15-32's dot-directory reasoning is empirically true.** I built a transient `.tmp-pyright-probe/` with a deliberate type error and an explicit `exclude` list: pyright analyzed it (diagnostic reported). The relocated `.planning/scripts/*.py` include strategy is sound, and the `filesAnalyzed==expected` count gate (15-02 task 2) computes 94 both sides, matching a real run exactly.
- **Privacy inventories are measured, not recalled.** I ran all four scan patterns over the actual relocating file set: exactly 20 serials, 17 IPv4, 19 MAC, 5 IPv6, and the values match the plans' inventories item for item. The round-2 fixes (serial pattern `\b[0-9a-f]{12}\b`, tree-on-disk corpus, `fe80::`/MAC inventory widening) were necessary and are correct.
- **The sweep normalise-and-rematch pattern is correct.** I traced the five-line fixture: lines 1, 2, 3 and the mixed line 5 match; the relocated-only line 4 is normalised away; `matched=4` is the right expectation. 15-02 and 15-05's patterns are identical as claimed.
- **The locked-spec blob gate reproduces**: `awk`-minus-requirement-2 of `15-SPEC.md` hashes to `4b2a40d7889fa7111951a21250aff6f64243d3cd`, exactly as recorded. Same for the ROADMAP block gate: block sizes `{16:16, 17:17, 18:17, 19:17, 20:15}`, `CHANGED []`.
- **The ROADMAP stale-path surface is exactly the licensed edit surface.** `git grep` over `.planning/ROADMAP.md` finds stale `scripts/...` citations only at lines 122/146/185 (Phase 15 blocks) and 227 (Phase 17's `Depends on`, the named exception). Phase 16's `Depends on` (line 211) cites no script path. Task 2's edits and the block-compare gate do not collide — verified against the current tree, not inferred.
- **CI facts check out**: `ci.yml:192` is the quoted-result precedent for `fetch-depth`; only one step is named `Upload coverage to Codecov` (index-based placement verify is unambiguous); workflow-level permissions are `contents: read` only (the `statuses: read` addition is needed); `.planning/**` is absent from the `paths` filter as stated; exactly one version-gated site (`src/lifx/const.py:175`) and zero real platform-gated sites (the `os.name` grep hits are "hostname" substring false positives).
- **`pytest-benchmark 5.2.3` registers no bare `--benchmark` and no `benchmark` dest** — the new flag cannot collide with the plugin's options.
- **The real `coverage.xml` shape is handled by the adapter**: `<source>` is the repo root and `<class filename>` is `src/lifx/__init__.py`-style; source-root joining plus repo-relative normalisation resolves it correctly.
- **TEST-02 subject verified**: the polling fix is at `tests/test_network/test_discovery_coordinator.py:75-76`; `39bad58` created that file; `fc61b98` is "stop the fork coordinator test racing its own thread pool" — the fc61b98-assumption correction is factually right. `--collect-only -q` really does print "(12 deselected)" in the summary, so the deselection-visibility gate has a real signal. Issues #214/#209 are OPEN with 0 comments; `gh issue view --json state,comments` works; auth is the `Djelibeybi` account — the checkpoint precondition is satisfiable.
- **The guard's own introduction PR will pass itself**: pyproject/ci.yml/.github/.planning changes are all unmeasured, and the one measured-file change in the phase (`connection.py`) is comment-only, which `analysis2` excludes. Self-consistent by construction.

## Concerns

**HIGH — 15-05 task 2 acceptance criterion contradicts its own action and verify.** The action says: "Do not replace it with a negative lookbehind or reintroduce the anchor" and the verify runs the normalise-and-rematch pattern with the `matched=4` fixture. But the acceptance criteria still contain the round-1 leftover: "The search's path alternative is anchored with `(^|[^/])`, so a relocated `.planning/scripts/<name>.py` reference is not reported as a stale one." That criterion is doubly unsatisfiable: the anchor is the exact defect T-15-38 records (it misses `./scripts/` and slash-prefixed forms), and it contradicts the neighbouring criterion requiring the pattern be "character for character the ones plan 15-02 task 4 uses" (15-02's is anchor-free). An executor or a later auditor working from the acceptance list rather than the verify block would reintroduce the round-1 defect while "passing" a criterion. This is the same class of stale round-1 text that the round-2 pass caught in `15-PATTERNS.md` — this one survived because the revision rewrote the action and verify but not the criteria list. Fix: replace that criterion with "the sweep normalises `.planning/scripts/` to a token containing no `scripts/` and re-matches; the `(^|[^/])` anchor appears in no runnable command."

**MEDIUM — 15-01 task 1 leaves the default suite red, and no task-1 gate can see it.** `tests/test_pytest_policy.py:93,102` call `pytest_collection_modifyitems([item])` positionally with one argument. Task 1 changes the signature to `(config, items)`; task 2 fixes the callers. Task 1's five verify commands run only the tooling directory, `--collect-only` runs (which import but do not execute the callers), and file checks — none executes `test_pytest_policy.py`. An executor following task 1's verify block exactly sees all green, commits, and that commit breaks every default-suite run with a `TypeError`. 15-02 documents its red windows explicitly; 15-01 does not, and its gates are structurally blind to this one. Fix: either fold the two-line caller fix into task 1's commit (the commit-granularity section already folds other edits in), or add `uv run --frozen pytest tests/test_pytest_policy.py -q --no-cov` to task 1's verify with the red window stated in the action.

**MEDIUM — count-based gates whose exit code disagrees with their `fails_when` (the class round 2 fixed for expected-zero, now in expected-N form):**
- 15-02 task 1: `git status --porcelain | grep -c '^R'` — `fails_when` says "count less than 8", but grep exits 0 at any count ≥ 1. Six renames plus two delete+add pairs pass the gate while history tracking is lost.
- 15-02 task 1: `git ls-files .planning/scripts/ | wc -l | tr -d ' '` — `fails_when` says "anything other than 10", but `wc -l` exits 0 always; the gate is a printout with adjudication left to the executor.
- 15-05 task 1: `grep -c 'uv run .planning/scripts/...' AGENTS.md` — `fails_when` says "count less than 3", but the command exits 0 at counts 1 and 2.
- 15-01 task 2 acceptance, 15-04 task 2, 15-05 task 1: several `grep -c` "exactly 1" criteria (e.g. `'^## Measured Tree'`, `'while not self.release.is_set()'`) exit 0 at count 2, so the "exactly" half is unenforced.

The zero-count variants of this class were rewritten in round 2 as `test "$( ... || true)" -eq 0`; the non-zero variants were not. Fix: wrap each in `test "$( ... | grep -c ... || true)" -eq N`.

**MEDIUM — 15-03 does not repeat the pyright `filesAnalyzed` count gate when it adds the `.github` include entries.** 15-02 introduced that gate precisely because exit-code-only pyright verification "is a vacuous pass, which is the defect class this phase exists to close" (T-15-32). 15-03 adds two include entries and verifies with: pyright exit code, a toml superset assertion (which does pin the exact strings, so a typo fails), and nothing that proves pyright actually analyzed the two dot-directory files. I verified empirically that the mechanism works today, so this is an asymmetry rather than a live defect — but a phase whose thesis is "gates that cannot fail" should carry its own strongest gate onto its own edit. The plan text even states "Plan 15-03 adds two `.github` entries and takes it to 96" — no gate asserts 96. Fix: re-run the 15-02 count gate with expected 96 in 15-03 task 1's verify.

**LOW — 15-03's prose misdescribes the real Cobertura shape.** Task 1 claims "a filename reads `lifx/api.py` under a source root that ends in `src`". The actual report (verified) has `<source>` = repo root and filenames `src/lifx/__init__.py`-style. The adapter's try-each-root join handles both shapes, so the code is correct, but the task-2 fixture exercises only the `src`-root shape and a future maintainer following the prose would not recognise the real file. Fix: correct the prose and add one fixture replicating the real shape (source = repo root, filename = `src/lifx/...`).

**LOW — 15-02's "seven references across the three files" import count is off.** `scripts/ipv6_thread_probe.py:101-102` is two import lines; with `measure_merged_discovery.py:41` and `thread_revalidation.py:46` that is four import statements, plus prose citations like `thread_revalidation.py:265` that the blanket instruction covers but the enumeration does not name. The task-4 sweep catches any residue, so the gate is safe; the enumeration is just imprecise enough to slow an executor doing checklist-driven edits.

**LOW — 15-05 task 1's em-dash check only covers `git diff -- AGENTS.md` added lines.** Correct for AGENTS.md (which task 1 owns), but tasks 2/3 prose edits to REQUIREMENTS/ROADMAP/SPEC have no em-dash gate at all despite the same "no em dashes" instruction. The SPEC amendment gate checks added lines for em dashes (task 3 has one); ROADMAP and REQUIREMENTS edits do not. A single phase-level `git diff -- .planning | grep '^+' | grep -F '—'` would close it.

**LOW — 15-04's absolute-path scan requires a two-segment path.** A single-segment absolute reference (e.g. a bare `/etc/...`-style root token) would not match. Acceptable given the four-root redaction covers everything this environment emits (verified: the venv stdlib lives under `~/.local/share/uv/...`, inside `<home>`), but worth knowing the backstop's edge.

## Suggestions

- Rewrite the stale 15-05 anchor acceptance criterion (HIGH above) before execution; it is a one-line fix in the plan text.
- Add `uv run --frozen pytest tests/test_pytest_policy.py -q --no-cov` to 15-01 task 1, marked expected-red until task 2, or fold the caller fix into task 1's commit.
- Convert the four count-printout gates to `test "$( ... || true)" -eq N` form, matching the convention round 2 established.
- Reuse 15-02's `filesAnalyzed` count script in 15-03 with expected 96.
- In 15-03 task 2, add one Cobertura fixture matching the project's real report shape (`<source>` = temp repo root, filename `src/lifx/example_module.py`).
- Consider a phase-level added-line em-dash gate over `.planning/` and `AGENTS.md` diffs in 15-05's verification section.

## Risk Assessment

**Overall: MEDIUM** — down from the HIGH of earlier rounds, and the reduction is earned: the previously disputed mechanisms (source-authoritative denominator, dot-directory pyright reach, privacy inventories, sweep shape coverage, idempotent publication) all reproduce under execution. The residual risk is concentrated in two places: the 15-05 anchor-criterion contradiction, which can reintroduce the round-1 sweep defect through the acceptance back door, and the 15-01 intra-plan red window, which can produce one broken intermediate commit under per-task commit discipline. Neither blocks the phase's goals; both are cheap to fix in plan text before execution. The phase's four success criteria are fully covered by the five plans, the wave ordering is correct (15-04's observation-dependency on a green tree is explicitly reasoned), and the CI-01 reversal is documented end-to-end rather than silently dropped. The verification machinery these plans build is, with the fixes above, actually capable of failing when the thing it checks is wrong — which is the phase's own definition of done.

---

## Antigravity Review

> [reviewed-without-source-citations] This reviewer declared source-grounded evidence but cited no file:line source evidence, so it reviewed the pasted plan text only — down-weight its verdict in the Consensus Summary.

# Cross-AI Plan Review: lifx-async v2.1 Phase 15

## 1. Summary

The plans for Phase 15 provide a highly structured and meticulous approach to relocating CI tools, fixing testing debt, and ensuring the repository's verification machinery remains pristine. The use of scratch worktrees, strict git hygiene, and idempotency checks (especially for the GitHub issue publication in Plan 15-05) demonstrates a strong architectural understanding. However, the execution relies heavily on an `<automated>` verification runner whose semantics assume non-zero exit codes for failure. Across multiple plans, there are critical gaps where commands will silently exit `0` despite violating their `<fails_when>` text. Because this phase is fundamentally about reliable verification, these defective gates pose a significant risk, allowing incorrect states to pass as verified.

## 2. Strengths

- **Idempotency in Public Actions**: Plan 15-05 Task 5 is a masterclass in safety for irreversible actions. By pulling the remote comment body via `gh api` and comparing it instead of relying on local state files or crude list counts, it prevents duplicate postings.
- **Opt-in Tooling Isolation**: Plan 15-01 correctly moves from a negative `-m "not tooling"` pattern to an additive deselection hook (`pytest_collection_modifyitems`), keeping `addopts` clean and avoiding complex negation expressions.
- **Traceable Worktree Backstops**: Plan 15-04 safely executes the blocked-worker teardown test inside a scratch worktree with a `faulthandler` thread dump, preventing experimental changes from contaminating the main checkout.
- **Robust Path Regex Sweep**: The regex sweep effectively normalises the matched target path before applying the match, ensuring mixed lines with both old and new paths are not accidentally ignored (Plan 15-02).

## 3. Concerns

- **HIGH: `git diff` and `git status` gates cannot fail on output**
  Multiple gates rely on `git diff` or `git status --porcelain` to ensure files are unchanged, but without `--exit-code` or a piped evaluation, these commands always exit `0` even if there are changes. The automated runner will silently pass.
  - Plan 15-04, Task 3: `<automated>git status --porcelain tests/test_network/test_discovery_coordinator.py</automated>` and `<automated>git diff HEAD -- tests/test_network/test_discovery_coordinator.py</automated>`
  - Plan 15-05, Task 4: `<automated>git diff main -- codecov.yml</automated>`
  - Plan 15-05, Task 5: `<automated>git diff --stat -- .planning/phases/15-coverage-gate-and-test-suite-health/15-SPEC.md</automated>`

- **HIGH: Masked exit codes in semicolon-separated commands**
  - Plan 15-03, Task 5: `<automated>git diff -- codecov.yml; git diff -- pyproject.toml | grep -E '^[+-].*(omit|exclude_lines|--cov|fail_under|pragma)'; test $? -eq 1</automated>`
    Because of the `;`, any output (and the `0` exit code) from `git diff -- codecov.yml` is discarded in terms of the test evaluation. If `codecov.yml` is modified but `pyproject.toml` is not, the `grep` fails (exits 1), the `test 1 -eq 1` succeeds (exits 0), and the gate passes, completely missing the unauthorised `codecov.yml` edit.

- **HIGH: Overly permissive grep counting**
  - Plan 15-02, Task 1: `<automated>git status --porcelain | grep -c '^R'</automated>`
    The `<fails_when>` requires the count to be at least 8. However, `grep -c` exits `0` as long as it finds *at least one match*. If only 5 renames occurred, `grep -c` outputs `5` and exits `0`, incorrectly passing the gate.

- **HIGH: Commands that purely emit stdout evaluate as `0`**
  - Plan 15-02, Task 1: `<automated>git ls-files .planning/scripts/ | wc -l | tr -d ' '</automated>`
    `tr` and `wc -l` always exit `0` regardless of the number of lines. The `<fails_when>` dictates it must be exactly 10, but the runner only sees the exit code.
  - Plan 15-05, Task 5: `<automated>awk '...' | sort -u</automated>` and `<automated>awk '...' | git hash-object --stdin</automated>`
    Both `sort -u` and `git hash-object` exit `0` as long as they process data successfully, meaning they cannot enforce the strict output/hash constraints detailed in the `<fails_when>`.

## 4. Suggestions

- **Use `--exit-code` for Git queries**: Update all bare `git diff` and `git diff --stat` gates to `git diff --exit-code ... > /dev/null`. This correctly forces a non-zero exit if there are unstaged or uncommitted changes. Update `git status --porcelain` to pipe to `grep -q .` or `test -z "$(git status --porcelain ...)"`.
- **Wrap multi-command checks in `bash -c` with logic**: Replace `git diff -- codecov.yml; git diff -- pyproject.toml | grep ...` with a `bash -c` block that explicitly tests the output of *both*: `bash -c 'test -z "$(git diff -- codecov.yml)" && ! git diff -- pyproject.toml | grep -qE "^[+-].*(omit|...)"'`.
- **Use numeric evaluation for counts**: Replace `grep -c` or `wc -l` gates with explicit numeric shell tests. For example, change `git status --porcelain | grep -c '^R'` to `bash -c 'N=$(git status --porcelain | grep -c "^R" || true); test "$N" -ge 8'`.
- **Validate exact output inside `bash -c`**: Replace the `awk | sort -u` and `awk | git hash-object` gates with explicit string comparisons: `bash -c 'H=$(awk "..." | git hash-object --stdin); test "$H" = "4b2a40d7889fa7111951a21250aff6f64243d3cd"'`.

## 5. Risk Assessment

**HIGH**. While the actual code and documentation logic within the plans are sound and well-reasoned, the verification machinery for these plans contains significant vulnerabilities. The `<automated>` blocks act as the ultimate safety net for this autonomous workflow. Because multiple critical gates will silently pass when their `<fails_when>` constraints are violated, there is a high risk of merging defective states or violating stated scope boundaries without detection. Fixing the exit semantics of these gates is mandatory before execution.

---

## Consensus Summary

**Verdict: HIGH risk. Revision required before execution.** Two independent HIGH findings were
reproduced by the orchestrator against the repository, and both are the same shape: **a round-1
statement that a later revision invalidated but did not rewrite.** The plans' runnable machinery
is in good order; what is stale is the prose and acceptance text that surrounds it, and in one
case the locked SPEC itself.

### Evidence weighting

Codex and OpenCode both ran source-grounded with executed checks and cite `file:line` throughout;
both count at full weight. Between them they independently reproduced the pyright count
(`filesAnalyzed=94`), the `analysis2()` exclusion behaviour, all four privacy inventories
(20/17/19/5, exact), the sweep fixture's `matched=4`, the SPEC blob hash, the ROADMAP block gate,
and the GitHub issue state. OpenCode explicitly confirmed it kept scratch work in `${TMPDIR}`.

**Antigravity carries `[reviewed-without-source-citations]` and is weighted down**, but not
dismissed. It cited no repo `file:line` evidence, so it reviewed the pasted plan text only. Its
findings quote the plans' own `<automated>` commands, where the command text is legitimately the
evidence, and it produced the round's most focused treatment of the gate-semantics theme. Its
severity rating, however, rests on a premise that is wrong (below).

### The premise dispute, settled

**Antigravity rates the count-based gates HIGH on the grounds that "the automated runner will
silently pass" because commands like `wc -l` and `grep -c` exit 0 regardless of output.** That
premise does not hold. `gsd-core/references/failing-direction.md` states the purpose of
`<fails_when>` directly: *"The same class of error with a command that exits 0 on a no-op passes
green and silently. Requiring a stated failing direction is the only shape that catches the silent
case."* The executor adjudicates output against `<fails_when>`; it is not a bare exit-code runner.
If exit status decided everything, `<fails_when>` would have no reason to exist.

So the class is real but the severity is not HIGH. OpenCode frames it correctly at MEDIUM: *"the
gate is a printout with adjudication left to the executor."* That is a robustness gap in a phase
whose thesis distrusts exactly that kind of dependence, and the round-2 pass already rewrote the
**expected-zero** variants into self-failing form. The **expected-N** variants were not, and that
asymmetry is what should be closed.

### Agreed Strengths

- **The load-bearing mechanisms now reproduce under execution, not argument.** Both full-weight
  reviewers independently re-derived the same figures: pyright 94/94 with zero errors, the four
  privacy inventories to the value, `matched=4` on the sweep fixture, and the locked-spec hash.
  OpenCode additionally built a transient dot-directory with a deliberate type error and confirmed
  pyright analyses it, which is the empirical basis for `T-15-32` that round 2 could only argue.
- **The guard's denominator is independent of the report it audits**, which is the correct answer
  to the vacuous-report class, and the fixture matrix covers absent, present-but-unclassified,
  partially classified, excluded-only, malformed, and configuration-drift shapes.
- **Publication safety is genuinely resumable.** Resolving against GitHub's own comment bodies
  rather than a local state file survives the interruption that makes resume necessary, which
  Antigravity singles out as "a masterclass in safety for irreversible actions".
- **OpenCode verified the phase is self-consistent by construction:** the guard's own introduction
  PR will pass its own gate, because every file the phase touches is unmeasured except one
  comment-only change in `connection.py`, which `analysis2()` excludes.

### Agreed Concerns

**1. HIGH — the locked SPEC's global acceptance criteria contradict the implementation in four
places, and the R2-only amendment cannot reach them.** Raised by Codex. **Orchestrator note:
confirmed against `15-SPEC.md`.** The SPEC states the same commitments twice: once per-requirement
under `## Requirements` (where R2's acceptance sits at :91, which 15-05 Task 3 amends) and again
in the phase-global `## Acceptance Criteria` section at :236+, which no plan touches. That second
section still says:
- `:243-244` — a repository-wide search returns no hit outside `.planning/milestones/`. This is
  the *same* exclusion boundary the R2 amendment widens, stated a second time in a place the
  amendment does not reach.
- `:245` — "`AGENTS.md` documents the corrected `python -m` invocations". The plans *remove*
  `python -m` in favour of direct PEP 723 invocation, and 15-05 Task 1 asserts its absence.
- `:249-250` — "The default pytest run collects only library tests; the relocated tooling tests
  collect only when the `tooling` marker is passed". Contradicts both 15-01's collect-then-deselect
  design and D-09's move from a marker expression to opt-in flags.
- `:181-182` (`## Boundaries`) — "deselecting it ... behind a `tooling` marker, run manually by
  passing the marker". Same marker-versus-flag contradiction.

Meanwhile 15-05 Task 3's blob gate asserts every byte outside requirement 2 is unchanged. Executing
the plans as written therefore lands the phase failing its own locked acceptance contract in four
places. **The structural lesson is that a narrow R2-only amendment was never sufficient**, because
the SPEC duplicates its commitments across sections. Fix: amend all four locations in one authorised
edit, and recompute the outside-R2 hash afterwards.

**2. HIGH — 15-05's acceptance criteria still require the anchor its own verify proves must be
absent.** Raised by OpenCode. **Orchestrator note: confirmed.** `15-05-PLAN.md:547` reads: *"The
search's path alternative is anchored with `(^|[^/])`, so a relocated `.planning/scripts/<name>.py`
reference is not reported as a stale one."* The runnable verify at `:489` asserts `matched=4`, and
its own `<fails_when>` says *"`matched=1` means the round-1 `(^|[^/])` anchor is still in place"*.
The criterion and the gate cannot both be satisfied. `:155` carries the same stale claim in present
tense. An executor or auditor working the criteria list rather than the verify block would
reintroduce the round-1 defect while "passing" a criterion. This is the identical failure mode
round 2 caught in `15-PATTERNS.md`; it survived because the revision rewrote the action and the
verify but not the criteria. Fix: replace the criterion with one describing normalisation and
re-matching, and assert the anchor appears in no runnable command.

**3. MEDIUM — expected-N count gates leave adjudication to the executor.** Raised by all three
(HIGH from Antigravity on a false premise, MEDIUM from OpenCode, and consistent with Codex's
exit-code findings). Round 2 rewrote the expected-**zero** variants into `test "$(... || true)" -eq 0`
form; the expected-**N** variants were left as printouts:
- `15-02` Task 1: `git status --porcelain | grep -c '^R'` — `fails_when` wants at least 8, but grep
  exits 0 at any count ≥ 1, so six renames plus two delete/add pairs pass while history tracking is
  lost.
- `15-02` Task 1: `git ls-files .planning/scripts/ | wc -l | tr -d ' '` — `wc -l` always exits 0.
- `15-05` Task 1: `grep -c 'uv run .planning/scripts/...' AGENTS.md` — wants ≥ 3, exits 0 at 1 or 2.
- Several `grep -c` "exactly 1" criteria (`'^## Measured Tree'`,
  `'while not self.release.is_set()'`) exit 0 at count 2, so the "exactly" half is unenforced.
Fix: `test "$( ... | grep -c ... || true)" -eq N`, matching the convention round 2 established.

**4. MEDIUM — collection pipelines report success even when pytest itself failed.** Raised by
Codex, which reproduced it: a collection command exiting 2 with no matching node ids still left the
whole gate at exit 0, because the gate takes `grep`'s status, not pytest's. Affects
`15-01-PLAN.md:260` (negated form) and `:262` (positive form, where a failing producer that prints
one matching node id makes grep return 0), and `15-03-PLAN.md:613` repeats the pattern. Fix:
capture output and pytest's exit code separately, and assert pytest returned zero before applying
the grep check.

**5. MEDIUM — `|| true` around the whole sweep pipeline suppresses `git grep` operational
failure.** Raised by Codex, reproduced with an invalid regular expression: the gate printed
`SWEEP-CLEAN` and exited 0. Affects `15-02-PLAN.md:753` and `15-05-PLAN.md:490,492`. A sweep that
cannot distinguish "no stale paths" from "the search never ran" is the phase's own defect class.
Fix: capture status separately, accept 0 and 1, fail on anything greater.

### Divergent Views

- **Codex alone: 15-04's stale-worktree recovery contradicts its own cleanup gates.** The baseline
  is captured *before* recovery at `:414`; if it contains a stale `15-TEST-02` registration,
  recovery removes it at `:424-427`, and the final list can then neither equal the baseline nor
  contain zero experiment worktrees, failing both gates at `:488-491`. Fix: clean stale experiment
  worktrees before capturing the baseline, or filter the baseline.
- **Codex alone: 15-03's XML source-root instructions conflict internally.** They require refusing
  an outside-repository source-root candidate, then require falling back to the raw filename
  whenever no root resolves (`:326`). An outside `<source>` plus `filename="src/lifx/example.py"`
  can therefore be re-keyed inside the repository through the fallback, contrary to the traversal
  test at `:514`. Fix: permit raw-filename fallback only when `<sources>` is absent or empty.
- **OpenCode alone: 15-01 Task 1 leaves the default suite red and no Task 1 gate can see it.**
  Task 1 changes `pytest_collection_modifyitems` to `(config, items)`; the positional callers at
  `tests/test_pytest_policy.py:93,102` are fixed in Task 2. Task 1's five verifies run only the
  tooling directory, `--collect-only` (which imports but does not execute the callers), and file
  checks. An executor following Task 1 exactly sees green, commits, and that commit breaks every
  default-suite run with a `TypeError`. 15-02 documents its red windows; 15-01 does not. Fix: fold
  the caller fix into Task 1's commit, or add `uv run --frozen pytest tests/test_pytest_policy.py`
  to Task 1 with the red window stated.
- **OpenCode alone: 15-03 does not carry 15-02's `filesAnalyzed` gate onto its own pyright edit.**
  15-02 introduced that gate because exit-code-only pyright verification is a vacuous pass. 15-03
  adds two `.github` include entries and verifies with exit code plus a toml assertion, but nothing
  proves pyright analysed them. The plan text even says the count goes to 96; no gate asserts 96.
  An asymmetry rather than a live defect, but a phase about gates that can fail should carry its
  strongest gate onto its own edit.
- **Codex alone, LOW but worth noting: the privacy gates cover only serials, IPv4, IPv6 and MAC
  shapes**, while `AGENTS.md:19` also prohibits hostnames and account names. The staged-diff human
  inspection should be stated explicitly rather than implied.
- **OpenCode alone, LOW: 15-03's prose misdescribes the real Cobertura shape.** It claims a filename
  reads `lifx/api.py` under a source root ending in `src`; the actual report has `<source>` = repo
  root and `src/lifx/...`-style filenames. The adapter's try-each-root join handles both, so the
  code is right and only the prose and fixture coverage are off.
- **Antigravity alone: bare `git diff` / `git status --porcelain` gates.** It flags several as
  unable to fail. Under the `<fails_when>` contract they are adjudicated on output, so they are not
  silent passes, but `git diff --exit-code` and `test -z "$(git status --porcelain ...)"` are
  strictly better and cost nothing. Worth folding into the finding-3 sweep.
- **Antigravity alone: `15-03` Task 5's semicolon-separated gate.** `git diff -- codecov.yml; git
  diff -- pyproject.toml | grep -E ...; test $? -eq 1` — the first command's output is not part of
  the evaluation, so an unauthorised `codecov.yml` edit passes if `pyproject.toml` is clean. This
  one is a genuine logic defect independent of the exit-code premise, and should be fixed.

### Risk ratings

Codex HIGH, OpenCode MEDIUM, Antigravity HIGH (on a false premise). The two full-weight reviewers
agree the runnable mechanisms are sound and the residual risk is concentrated in stale text: Codex
rates HIGH because the locked-spec contradiction leaves the phase unable to satisfy its own
acceptance contract, OpenCode rates MEDIUM because neither of its two headline findings blocks the
phase goals and both are cheap plan-text edits. The orchestrator sides with HIGH: finding 1 is not
a plan-text nit but a contract the completed phase would demonstrably fail.

### Priority revisions

1. Amend all four stale locked-SPEC locations in one authorised edit (`:181-182`, `:243-244`,
   `:245`, `:249-250`), and recompute the outside-R2 blob hash afterwards. A narrow R2-only
   amendment is structurally insufficient because the SPEC duplicates its commitments.
2. Replace `15-05-PLAN.md:547`'s anchor acceptance criterion, and the stale present-tense claim at
   `:155`, with text matching the normalise-and-rematch verify. Check `15-02` for the same
   leftovers.
3. Convert the expected-N count gates to `test "$( ... || true)" -eq N`, and fold in the bare
   `git diff` / `git status` gates while there.
4. Make collection pipelines preserve pytest's exit code before applying grep checks
   (`15-01:260,262`, `15-03:613`).
5. Make `git grep` operational failure fatal in both sweeps (`15-02:753`, `15-05:490,492`).
6. Fix `15-03` Task 5's semicolon-separated gate so an unauthorised `codecov.yml` edit cannot pass.
7. Clean stale experiment worktrees before capturing 15-04's baseline, or filter the baseline.
8. Permit 15-03's raw-filename fallback only when `<sources>` is absent or empty.
9. Resolve 15-01's Task 1 red window: fold the caller fix in, or gate and document it.
10. Carry the `filesAnalyzed` count gate onto 15-03's own pyright edit, expecting 96.
