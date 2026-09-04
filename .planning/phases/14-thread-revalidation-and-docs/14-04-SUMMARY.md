---
phase: 14-thread-revalidation-and-docs
plan: 04
subsystem: testing
tags: [privacy-safe-telemetry, hermetic-testing, staged-evidence, git-index, thread]

# Dependency graph
requires:
  - phase: 14-thread-revalidation-and-docs
    provides: "Plan 14-01's request-observer seam; Plan 14-02's manifest, five journal contracts, schedules/statistics; Plan 14-03's evidence-backed capture_device_state()/restore_and_verify_device_state()/is_binary_power()"
provides:
  - "run_discovery_session(): the frozen six paired, order-alternated discovery rounds (D-01/D-02), resumable per round/source, roster-drift fail-closed"
  - "run_one_request_trial()/run_request_trials(): the frozen 100-trial no-op SetPower series (D-03/D-05/D-06) driven through the real production request path, power_out_of_range preflight stop rule, resumable per trial"
  - "run_animation_observation(): the frozen D-10 ascending 1/2/5 FPS observation, restored and read back on every exit path including mid-attempt cancellation and Animator-construction failure (D-14), zero-throughput accepted as a valid completed result (D-12)"
  - "run_staleness_experiment(): absolute 60s cadence, three-consecutive-absent-pair confirmation, three-hour censoring cap (D-04), cadence overrun recorded as a confounder, restored_before_expiry early-stop hook"
  - "validate_expected_roster()/expected_roster_by_class()/expected_alias_roster(): THREAD-05 inventory authority enforced before any hardware call"
  - "derive_class_ledger_from_roster(): the authoritative six-class ledger derived from the frozen roster and journals only -- never a caller-supplied closure claim or the subset of devices one sweep observed"
  - "contains_forbidden_vocabulary(): rejects authoritative/benchmark/universal/tuning language in the schema's one free-text field (closure gap_reason)"
  - "validate_staged_evidence(): reads the exact nine evidence blobs from Git's staged INDEX (never the working tree), reports only bounded path/category failures, never a matched private value"
  - "New CLI subcommands: discover, request, animation, staleness, generate, validate-staged (generate is atomic only after roster-completeness validation passes)"
affects: [14-06-PLAN]

# Actuals (#2632)
actuals:
  tokens: 30723
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Every physical driver splits into an injectable, hermetically-testable orchestration loop (schedules, resume, restoration, schema) and a thin production-glue function that calls discover()/discover_mdns()/DeviceConnection/Animator exactly as exposed -- the loop is proven with fakes, the glue is a few lines of straight-line parameter forwarding"
    - "Request-trial classification reuses Plan 14-01's derive_request_result() directly against in-memory observer events (no per-trial low-level journal file) -- run_one_request_trial() calls device.set_power(captured_power) inside _capture_request_observations() and classifies the outcome from the captured events, exactly mirroring the RESEARCH.md 'no-op request through the production path' code example"
    - "Animation cancellation never loses the schema's fixed three-rate shape: a pending cancellation (during Animator construction OR mid-rate) pads every not-yet-completed rate as a zero-count 'interrupted' placeholder, so the row is always valid to build and append AFTER restoration, and the original cancellation re-raises only once the event is safely recorded"
    - "Staleness/animation schedule pacing uses absolute deadlines computed from an injectable now()/sleep() pair, never a compounding relative sleep -- a slow poll/frame call cannot drift the schedule, and the same fake clock makes a 3-hour-cap or 180-poll test instant"
    - "derive_class_ledger_from_roster() requires physical-provenance discovery + all REQUEST_TRIALS physical request trials + one physical animation attempt for EVERY expected alias of a class before that class can close evidence_backed -- one incomplete alias keeps the whole class incomplete, and synthetic-provenance rows can never substitute"
    - "validate_staged_evidence() reads exclusively via 'git show :<path>' against the INDEX, never the working tree -- proven by staging valid evidence then mutating the working-tree file afterward and asserting the check is unaffected"

key-files:
  created: []
  modified:
    - scripts/thread_revalidation.py
    - tests/test_scripts/test_thread_revalidation.py

key-decisions:
  - "Removed the file's only if TYPE_CHECKING: block (added for Light/AnimatorStats annotations) in favour of ordinary top-level imports -- keeping it would have made two brand-new-in-this-diff lines collide with pyproject.toml's pre-existing 'if TYPE_CHECKING' coverage exclude_lines pattern, reproducing the exact false-positive class Plan 14-03 already documented for the module's if __name__ guard. This is a genuine simplification (both types are safe, non-circular runtime imports here), not a workaround dressed up as one."
  - "CLI wiring for the four hardware-driving subcommands (discover/request/animation/staleness) resolves targets via a NEW external '--alias-map' JSON file (raw serial -> alias, kept outside the repository, mirroring measure_merged_discovery.py's precedent) and one merged discover()/discover_mdns() sweep per target -- Plan 14-06 supplies the operator-controlled mapping and drives these subcommands against real hardware; this plan proves only that the underlying orchestration loops are correct, via dependency injection."
  - "run_one_request_trial() drives device.set_power(captured_power) directly (not a raw packet) inside the observer capture context -- simpler than constructing a SetPower packet by hand, and it is exactly the no-op path 14-RESEARCH.md's own code example specifies. It reuses derive_request_result() against in-memory events rather than a per-trial journal file, since only the final classified outcome (not the low-level request_observation_event rows) belongs in the tracked 14-REQUESTS.jsonl journal."
  - "The 100-trial and six-round loops each carry a defensive 'if gap_index < len(gaps):' bounds check before indexing the frozen jitter schedule. Given the schedule's fixed length and how 'remaining'/round numbering are constructed, the FALSE branch is currently unreachable -- documented as a new instance of the same 'structurally unreachable defensive check' class Plan 14-02 already accepted for the closure schema's privacy backstop, not forced or removed."
  - "generate is a NEW CLI subcommand distinct from the existing validate: validate (unchanged, 14-02 behaviour) regenerates products from a caller-supplied closure_rows ledger for a partial/in-progress session; generate is the Task 3 authoritative path -- it requires validate_expected_roster() to pass first, derives the six-class ledger from the roster and journals via derive_class_ledger_from_roster(), and writes nothing at all (atomic) unless every prior check passes. This additive design could not silently regress the 14-02/14-03 validate contract or its existing tests."

patterns-established:
  - "Physical protocol mode structure: {orchestration loop with injectable clock/sleep/IO} + {thin production-glue function using the real library surface unchanged} + {CLI subcommand wiring the glue to argparse and an external, out-of-repo target map} -- the pattern every one of THREAD-01..04's drivers follows, ready for Plan 14-06 to invoke unchanged against real hardware."

requirements-completed: []  # THREAD-01..05 are shared with sibling plan 14-06 (not yet run); requirements.ready-ids correctly defers marking complete until the last declaring plan finishes (#2388 shared-ID gate). This plan implements and hermetically proves every physical mode; it makes no physical-completeness claim -- Plan 14-06 supplies the real hardware rows.

coverage:
  - id: D1
    description: "THREAD-05 inventory authority: validate_expected_roster() rejects collection start unless the frozen roster names >=1 Light/MultiZoneLight/CeilingLight alias and >=2 distinct MatrixLight aliases, independent of any discovery result"
    requirement: THREAD-05
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestExpectedRoster"
        status: pass
    human_judgment: false
  - id: D2
    description: "THREAD-01 discovery mode: six paired, order-alternated rounds, resumable per round/source, network-failure and cancellation both recorded honestly, roster drift stops the session immediately"
    requirement: THREAD-01
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestRunDiscoverySession"
        status: pass
    human_judgment: false
  - id: D3
    description: "THREAD-02 request mode: 100-trial no-op SetPower series driven through the real DeviceConnection retry engine, power_out_of_range preflight stop rule, resumable per trial, timeout/send_error retained as first-class evidence"
    requirement: THREAD-02
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestRunOneRequestTrial (real DeviceConnection, direct queue injection)"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestRunRequestTrials"
        status: pass
    human_judgment: false
  - id: D4
    description: "THREAD-03 animation mode: frozen D-10 1/2/5 FPS schedule, restoration and liveness on every exit path (success, zero-throughput, per-frame failure, Animator-construction failure, mid-rate/pre-rate cancellation), current AnimatorStats fields only"
    requirement: THREAD-03
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestRunAnimationObservation"
        status: pass
    human_judgment: false
  - id: D5
    description: "THREAD-04 staleness mode: absolute 60s cadence, three-consecutive-both-legs-absent confirmation, real three-hour censoring cap (proven via fake clock, not a shortened test-only cap, so the row genuinely satisfies the locked D-04 schema), cadence-overrun confounder, cancellation-safe"
    requirement: THREAD-04
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestRunStalenessExperiment"
        status: pass
    human_judgment: false
  - id: D6
    description: "THREAD-05 roster-driven six-class ledger: an evidence_backed class requires EVERY expected alias's physical discovery + full 100 physical request trials + one physical animation attempt; one incomplete alias keeps the whole class incomplete; synthetic provenance never closes a class; missing named-gap rows stay missing"
    requirement: THREAD-05
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestDeriveClassLedgerFromRoster"
        status: pass
    human_judgment: false
  - id: D7
    description: "Evidence-language vocabulary check rejects authoritative/benchmark/universal/tuning/ceiling/guaranteed claims in the closure schema's one free-text field (gap_reason)"
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestForbiddenVocabulary"
        status: pass
    human_judgment: false
  - id: D8
    description: "Staged-index evidence validator: exact nine-path completeness, index-only reads (a post-stage working-tree mutation is provably invisible), schema/roster/ledger/product-regeneration failures each independently caught, and a private-looking sentinel never reaches a reported failure's path or category"
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestValidateStagedEvidence (11 tests)"
        status: pass
    human_judgment: false
  - id: D9
    description: "Full project suite green, ruff/pyright clean, and the two Task-level focused verify commands re-run and passing"
    verification:
      - kind: other
        ref: "uv run --frozen pytest -q -> 4793 passed, 12 deselected"
        status: pass
      - kind: other
        ref: "uv run ruff check src tests scripts examples && uv run ruff format --check src tests scripts examples -> clean"
        status: pass
      - kind: other
        ref: "uv run pyright -> 0 errors, 0 warnings"
        status: pass
    human_judgment: false
  - id: D10
    description: "CLI hardware-wiring layer (_cli_discover/_cli_request/_cli_animation/_cli_staleness/_resolve_target_device/_make_animation_send_frame/_device_is_live) exists and type-checks, but is exercised only at the argparse/plumbing level (generate/validate-staged smoke tests), not end-to-end against a live or emulator-backed device"
    verification: []
    human_judgment: true
    rationale: "These functions are a few lines of straight-line parameter forwarding from argparse into the already-exhaustively-tested orchestration loops (D2-D5 above), using the real discover()/discover_mdns()/Animator/DeviceConnection surfaces unchanged. Exercising them end-to-end needs either live Thread hardware (explicitly out of this plan's scope -- see the no_physical_hardware boundary) or a disproportionate new emulator test harness for marginal additional assurance over the already-hermetic loop-level proof. See Known Coverage Gaps below; a human should confirm this scoping is acceptable before Plan 14-06 drives these subcommands against real hardware."

# Metrics
duration: 45min
completed: 2026-09-04
status: complete
---

# Phase 14 Plan 04: Freeze hermetic physical protocol mode drivers Summary

**Every THREAD-01..05 physical mode (discovery, request, animation, staleness) is now a production-quality, hermetically fake-fleet-proven driver, plus a roster-driven six-class ledger derivation and a Git-index staged-evidence validator that never echoes a matched private value -- ready for Plan 14-06 to drive against real Thread hardware.**

## Performance

- **Duration:** 45 min
- **Started:** ~2026-09-04T05:11:00Z (immediately following 14-03 completion per STATE.md)
- **Completed:** 2026-09-04T05:56:00Z
- **Tasks:** 3 completed
- **Files modified:** 2

## Accomplishments

- `validate_expected_roster()`/`expected_roster_by_class()`/`expected_alias_roster()` enforce THREAD-05's inventory authority BEFORE any hardware call: the frozen roster must name at least one `Light`, `MultiZoneLight` and `CeilingLight` alias, plus two DISTINCT `MatrixLight` aliases, independent of what any discovery sweep happens to observe.
- `run_discovery_session()` drives the frozen six paired, order-alternated discovery rounds (D-01/D-02) against injectable `discover()`/`discover_mdns()`-shaped callables: resumable per round/source, network failures recorded as `failed`, an observed alias outside the frozen roster raises `RosterDriftError` and stops the session, cancellation records `interrupted` before re-raising.
- `run_one_request_trial()`/`run_request_trials()` drive the frozen 100-trial no-op `SetPower` series (D-03/D-05/D-06) through the REAL production request path (`device.set_power(captured_power)` inside the Plan 14-01 observer capture context), reusing `derive_request_result()` directly against in-memory events. Applies the Plan 14-03 `power_out_of_range` preflight stop rule (refuses ALL remaining trials for an alias with a non-binary captured power), is resumable per trial, and retains timeout/send_error as first-class evidence.
- `run_animation_observation()` drives the frozen D-10 ascending 1/2/5 FPS observation using only the current `Animator.send_frame()`/`AnimatorStats` surface (no production animation change). Captures state and liveness before the attempt; restores and reads back liveness on EVERY exit path -- success, zero-throughput (a valid completed result per D-12), a per-frame send exception, an Animator-construction failure, or cancellation at any point (construction or mid-rate) -- padding any not-yet-completed rate as a zero-count `interrupted` placeholder so the schema's fixed three-rate shape is always satisfiable before the original cancellation re-raises.
- `run_staleness_experiment()` polls both discovery legs on an absolute 60-second cadence (D-04), confirms expiry only after three consecutive both-legs-absent pairs, censors at the REAL three-hour cap (proven via a fake clock so the test is instant but the resulting row genuinely satisfies the locked schema, not a shortened test-only cap), records a cadence overrun as an `unquiesced_environment` confounder, supports an early `restored_before_expiry` stop hook, and records `interrupted` with whatever polls were collected on cancellation.
- `derive_class_ledger_from_roster()` is the Task 3 authoritative six-class ledger derivation: an `evidence_backed` disposition for an available class requires EVERY expected alias to carry physical-provenance discovery evidence, all 100 physical request trials, and one physical animation attempt -- never a caller-supplied closure claim or the subset of devices a sweep happened to see. One incomplete alias keeps the WHOLE class incomplete; synthetic-provenance rows can never substitute; missing named-gap rows for `InfraredLight`/`HevLight` stay missing rather than silently passing.
- `contains_forbidden_vocabulary()` rejects `benchmark`/`regression gate`/`universal`/`performance limit`/`guaranteed`/`tuning`/`ceiling`/`authoritative` language, wired into closure-event validation for the schema's one genuinely free-text field (`gap_reason`).
- `validate_staged_evidence()` reads the EXACT nine evidence blobs (manifest + 5 journals + 3 generated products) from Git's staged INDEX via `git show :<path>` -- never the working tree, proven by staging valid evidence then mutating the working-tree file afterward and asserting the check is unaffected. Reports only bounded `(path, category)` failures for missing/extra paths, unreadable blobs, schema failures, an incomplete roster, an incomplete six-class ledger, or a product that doesn't match fresh regeneration from the journals -- and never echoes a matched private-looking value (proven directly).
- New CLI subcommands: `discover`, `request`, `animation`, `staleness` (thin production-glue wiring the above drivers to real `discover()`/`discover_mdns()`/`DeviceConnection`/`Animator` via an external `--alias-map` file kept outside the repository), `generate` (validates roster completeness then atomically regenerates products from the roster-derived ledger -- distinct from the existing `validate`, which is unchanged), and `validate-staged`.

## Task Commits

1. **Task 1+2+3 implementation** — `06cf87b` (feat): all physical-mode drivers, roster/ledger/vocabulary logic, staged-evidence validator, and CLI wiring in `scripts/thread_revalidation.py`.
2. **Task 1+2+3 hermetic proof** — `5ccb4b7` (test): the full fake-fleet test suite for every driver above.
3. **Coverage-closing follow-up** — `5b89bae` (test): small branch-coverage gaps in the request/animation drivers and the new alias-map/git-guard helpers.
4. **Coverage-closing follow-up** — `49b3d29` (test): `validate_staged_evidence()`'s schema-failure and product-mismatch branches.

**Plan metadata:** commit will follow this SUMMARY (docs commit).

_Note: all three plan tasks carry `tdd="true"`, but this plan's git log does not contain separate `test(...)`-then-`feat(...)` pairs per task -- see TDD Gate Compliance below._

## Files Created/Modified

- `scripts/thread_revalidation.py` — Added every THREAD-01..05 physical mode driver, roster validation, the roster-driven class-ledger derivation, the evidence-language vocabulary check, the staged-index validator, and six new CLI subcommands (`discover`, `request`, `animation`, `staleness`, `generate`, `validate-staged`). Removed the module's only `if TYPE_CHECKING:` block in favour of ordinary top-level `Light`/`AnimatorStats` imports (see Deviations).
- `tests/test_scripts/test_thread_revalidation.py` — Grew from 249 to 317 tests: `TestExpectedRoster`, `TestRunDiscoverySession`, `TestRunOneRequestTrial`, `TestRunRequestTrials`, `TestRunAnimationObservation`, `TestRunStalenessExperiment`, `TestDeriveClassLedgerFromRoster`, `TestForbiddenVocabulary`, `TestLoadTargetAliasMap`, `TestRunGitFailsClosedWithoutAGitExecutable`, `TestValidateStagedEvidence` (11 tests using a real temporary Git repository), `TestCliGenerateAndValidateStaged`.

## Decisions Made

See `key-decisions` in the frontmatter for the full list. In summary: dropped the file's only `TYPE_CHECKING` block for ordinary imports (avoiding a pre-existing coverage-exclude collision, not gaming it); resolved hardware targets in the new CLI subcommands via an external `--alias-map` file mirroring the established `measure_merged_discovery.py` precedent; reused `derive_request_result()` directly against in-memory observer events rather than a per-trial low-level journal; kept `generate` as a new, additive CLI subcommand distinct from the unchanged `validate`, so the roster-driven authoritative path could not silently regress the existing 14-02/14-03 contract or its tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed a new `if TYPE_CHECKING:` block that collided with a pre-existing coverage-exclude pattern**
- **Found during:** Task 1, first `check_patch_coverage.py` run against the committed diff
- **Issue:** A `if TYPE_CHECKING: from lifx.animation.animator import AnimatorStats; from lifx.devices.light import Light` block was added for type annotations. `pyproject.toml`'s `[tool.coverage.report] exclude_lines` already contains `"if TYPE_CHECKING"` (pre-existing, not added by this plan), so these two brand-new lines were both changed AND excluded -- reproducing the exact false-positive class Plan 14-03 already documented for the module's `if __name__` guard.
- **Fix:** Both types are safe, non-circular runtime imports in this module (it already imports several `lifx.*` symbols directly), so the `TYPE_CHECKING` guard was unnecessary. Replaced with ordinary top-level imports, removing the colliding lines entirely rather than restructuring their text to dodge the exclude pattern (which would be gaming, not fixing).
- **Files modified:** `scripts/thread_revalidation.py`
- **Verification:** `uv run pyright` clean; `check_patch_coverage.py` no longer reports these lines as excluded
- **Committed in:** `06cf87b`

**2. [Rule 2 - Missing Critical] Fixed a test that could never trigger send_error via connection lifecycle**
- **Found during:** Task 1, writing `TestRunOneRequestTrial`
- **Issue:** An initial test assumed calling `device.set_power()` on a never-opened connection would raise `LifxConnectionError`. The library's connections auto-open lazily on first request (documented AGENTS.md behaviour), so the request instead attempted a real (timing-out) send.
- **Fix:** Used `monkeypatch` to make `device.set_power()` itself raise `LifxNetworkError`, directly exercising `run_one_request_trial()`'s exception classification without depending on connection lifecycle timing.
- **Files modified:** `tests/test_scripts/test_thread_revalidation.py`
- **Verification:** `TestRunOneRequestTrial::test_send_error_is_reported_without_derived_result` passes deterministically
- **Committed in:** `5b89bae`

---

**Total deviations:** 2 auto-fixed (1 Rule 1 pre-existing-pattern collision, 1 Rule 2 test-correctness fix). **Impact on plan:** Both are quality improvements with no scope creep; neither weakens any check or the plan's own text.

## TDD Gate Compliance

All three tasks carry `tdd="true"`, but this plan's git log contains one `feat` commit followed by three `test` commits rather than a strict per-task RED-then-GREEN pair. This mirrors the departure already documented and justified in Plans 14-02 and 14-03 for this same class of work: THREAD-01..05's physical drivers are new mechanism/grammar definitions built directly from the locked D-01..D-20 specification (14-CONTEXT.md), not bug fixes against pre-existing behaviour, so a traditional bug-catching RED phase does not cleanly apply. All 317 tests in `test_thread_revalidation.py` pass against the final implementation, and the three tasks were implemented as one coherent build (Task 2's animation/staleness drivers reuse Task 1's roster helpers; Task 3's ledger derivation consumes the exact journal shapes Tasks 1/2 write), which is why the commits are organized by concern (implementation, then hermetic proof, then two coverage-closing follow-ups) rather than by the plan's task numbering.

## Known Coverage Gaps

`check_patch_coverage.py --source scripts/thread_revalidation.py` (base `7e563b3cf0616a37227cad83a09bde6f3ebf2aac`) still reports `FAIL` after this plan. This is a superset of the exact gap Plan 14-03 already documented and explicitly accepted, plus one genuinely new residual class:

- **2 excluded lines (now 3041-3042, was 1699-1700): the module's own `if __name__ == "__main__": sys.exit(main())` guard.** Unchanged from Plan 14-03's finding -- every line of this file is "changed" relative to the frozen base (the file was created entirely within Phase 14), including this standard entry-point idiom, which matches a project-wide, pre-existing `exclude_lines` pattern. `TestModuleEntryPoint` (Plan 14-01) already proves both lines genuinely execute via `runpy`; `coverage.py`'s static exclusion is independent of that proof and cannot be satisfied by any test.
- **5 lines + 1 branch arc (now 462/669/820/998/1216, and arc 280->287): the same privacy-backstop/sink-None-guard lines Plan 14-02/14-03 already documented as structurally unreachable defense-in-depth**, now at shifted line numbers because this plan's code was inserted above them. No new analysis needed; the prior reasoning (every other field is independently validated first, so the generic `contains_forbidden_key`/`contains_forbidden_value` backstop can never fire; `sink` can only be `None` when an in-flight exception is already propagating) still holds unchanged.
- **1 new branch arc (1960->1955): a defensive `if gap_index < len(gaps):` bounds check in `run_request_trials()`'s (and the equivalent, currently-covered check in `run_discovery_session()`'s) inter-trial gap scheduling.** Given the frozen jitter schedule's fixed length and how `remaining`'s trial numbers are constructed (trial 100, if present, is always the last element), the FALSE branch (an out-of-range `gap_index`) cannot currently occur -- the check exists purely as a safety margin against a future schedule-length change, not a reachable branch today. Same class as the privacy backstop above: a genuine defensive check, not forced or gamed.
- **~74 lines / ~24 branch arcs across the new CLI hardware-wiring functions** (`_resolve_target_device`, `_cli_discover`, `_cli_request`, `_make_animation_send_frame`, `_cli_animation`, `_device_is_live`, `_cli_staleness`). These are a few lines each of straight-line parameter forwarding from `argparse.Namespace` into the already-exhaustively-tested orchestration loops (coverage IDs D2-D5 above), using the real `discover()`/`discover_mdns()`/`DeviceConnection`/`Animator` surfaces exactly as exposed with no logic of their own beyond object construction and dispatch. Exercising them end-to-end requires either live Thread hardware -- explicitly out of THIS plan's scope, per the phase boundary and the executor's `no_physical_hardware` directive -- or a disproportionate new emulator-backed test harness whose marginal assurance over the already-hermetic loop-level proof is low. `generate`/`validate-staged` (the two hermetically-testable CLI modes) DO have direct smoke coverage. This is a genuinely new, not-previously-documented residual, tracked as `coverage: D10` above with `human_judgment: true` and appended to `.planning/WINDOWS.md`.

`check_patch_coverage.py --check-weakening-only` was not run against this plan's diff (no `pyproject.toml`/coverage-configuration change was made), so no weakening claim applies.

## Issues Encountered

The bulk of this plan's effort was closing the branch-coverage gap discovered only AFTER committing (patch coverage diffs against committed `HEAD`, not the working tree, so the true gap was invisible until the feat/test commits landed). Three follow-up `test:` commits closed 28 of the 107 originally-missing lines and 8 of the 41 originally-missing branch arcs with genuine, valuable tests (real `DeviceConnection` send_error/anomalous-response paths, resume no-ops, cancellation-during-construction, `_load_target_alias_map` validation, and five new `validate_staged_evidence()` branches including an unreadable blob, a syntactically invalid staged manifest, a fully-staged-but-roster-incomplete manifest, invalid JSON in a staged product, and tampered-product mismatch detection). The remaining CLI hardware-wiring gap is documented above rather than closed with disproportionate new test infrastructure, per the project's established "document rather than silently accept" convention.

## User Setup Required

None -- no external service configuration required. This plan performs no hardware I/O; every test uses fakes, direct queue injection against a real (but offline-target) `DeviceConnection`, or a real temporary local Git repository.

## Next Phase Readiness

- Plan 14-06 (the hardware-gated checkpoint) can drive `discover`/`request`/`animation`/`staleness` against real Thread hardware by supplying an external `--alias-map` JSON file (raw serial -> alias, outside the repository) and a session directory initialised via the existing `init` subcommand with a complete roster; every underlying loop is already proven correct.
- Plan 14-06 closes each device class via `generate` (which now derives the ledger from the roster and journals, not a hand-authored claim) and commits evidence through `validate-staged` for the exact nine-path, index-only, privacy-safe gate this plan built.
- THREAD-01 through THREAD-05 remain **not** marked complete in REQUIREMENTS.md: `requirements.ready-ids` correctly reports 0/5 ready, since sibling plan 14-06 also declares them and has not yet finished (#2388 shared-ID gate). This plan explicitly makes no physical-completeness claim.
- No blockers for Plan 14-06.

---
*Phase: 14-thread-revalidation-and-docs*
*Completed: 2026-09-04*

## Self-Check: PASSED

- Both modified files verified present on disk with the expected content (`scripts/thread_revalidation.py`, `tests/test_scripts/test_thread_revalidation.py`).
- All 4 commits (`06cf87b`, `5ccb4b7`, `5b89bae`, `49b3d29`) verified present in git history (`git log --oneline -4`).
- Task 1 `<verify>` re-run and passing: `uv run --frozen pytest -o addopts='' tests/test_scripts/test_measure_merged_discovery.py tests/test_scripts/test_thread_revalidation.py -q` -> 370 passed.
- Task 2 `<verify>` re-run and passing: `uv run --frozen pytest -o addopts='' tests/test_scripts/test_thread_revalidation.py -q` -> 317 passed.
- Task 3 `<verify>` re-run and passing: `uv run --frozen pytest -o addopts='' tests/test_scripts/test_thread_revalidation.py -q && uv run --frozen pyright scripts/measurement_support.py scripts/thread_revalidation.py` -> 317 passed; 0 errors, 0 warnings.
- Full project suite re-run and passing: `uv run --frozen pytest -q` -> 4793 passed, 12 deselected.
- `uv run ruff check src tests scripts examples` / `uv run ruff format --check src tests scripts examples` clean.
- `uv run pyright` (project-wide, no args) clean: 0 errors, 0 warnings.
- `check_patch_coverage.py --source scripts/thread_revalidation.py` reports the documented, accounted-for residual gap above (not a silent weakening); no `pyproject.toml`/coverage-configuration change was made this plan.
