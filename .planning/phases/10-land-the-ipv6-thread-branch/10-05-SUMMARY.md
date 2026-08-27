---
phase: 10-land-the-ipv6-thread-branch
plan: 05
subsystem: testing
tags: [ipv6, thread, uat, hardware, scripts, matrix, animator, coverage]

requires:
  - phase: 10-01
    provides: "scripts/ipv6_thread_probe.py itself, the 521-line three-stage probe replayed onto main by commit b641e22, and the 10-COVERAGE-GAPS.md entry naming this plan as the owner of its coverage treatment"
  - phase: 10-02
    provides: "lifx.network.address, so the probe's target device reaches validate_address() through the one shared rule when it is constructed; the probe adds no address parsing of its own"
  - phase: 10-03
    provides: "the send-time family assertion, so a mismatched target address fails typed in microseconds instead of surfacing as a 16 second timeout inside a UAT run"
provides:
  - "a control UAT stage in scripts/ipv6_thread_probe.py: set_power and set_color roundtrips with readback against the single device named by --serial"
  - "full pre-run state capture and restore for a MatrixLight (every tile's colours, power, and any running firmware effect), in a finally so a failed stage, a timeout or a KeyboardInterrupt still puts the device back"
  - "an opt-in --stream stage delivering bounded Animator frames, recorded as an artefact and absent from the exit-code logic"
  - "--uat-output, writing the 10-UAT-RESULTS.json record plan 10-06's merge gate consumes"
  - "tests/test_scripts/, a new test package, with 38 hardware-free tests over the harness"
  - "a recorded decision on the probe's coverage treatment: scoped local assertion, global --cov untouched"
affects: [10-06, 14]

actuals:
  tokens: 11610
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Mutating hardware stages sit inside one try/finally that restores once, so no exit path can skip restoration"
    - "A hardware script's non-network logic is factored into named module-level helpers so it can be tested without hardware"

key-files:
  created:
    - tests/test_scripts/__init__.py
    - tests/test_scripts/test_ipv6_thread_probe.py
  modified:
    - scripts/ipv6_thread_probe.py

key-decisions:
  - "The probe stays OUT of the global --cov and neither pyproject.toml nor codecov.yml is edited. Widening --cov would drop 521 previously unmeasured lines of a hardware script into a PR carrying a 100% branch patch target, which is the exact false-green pressure T-10-19 exists to prevent. The new logic is covered instead by a scoped assertion over six named helpers"
  - "--uat-output requires --serial (argparse error otherwise). A record naming no device cannot satisfy SPEC AC 19, and producing one would be a repudiation surface, not an honest not_run"
  - "A running firmware effect is captured only when effect_type is not OFF, so restoration never arms an effect the device did not have"
  - "MatrixEffect.speed is milliseconds while set_effect() takes seconds, so restoration divides by 1000. Passing the raw value back would have restored a MORPH 1000 times slower than it was found"
  - "The streaming stage builds its Animator through the module-level _build_animator() seam, so the close-on-exception guarantee is assertable against a double rather than only against hardware"
  - "The fakes subclass the real MatrixLight and Light rather than duck-typing them, because _capture_device_state() branches on isinstance(device, MatrixLight); a duck would silently take the plain-light path and prove nothing"

patterns-established:
  - "Prove the test before trusting it: five mutations of the code under test were applied and reverted, and the one that survived is why the KeyboardInterrupt test exists"
  - "Coverage debt on an unmeasured file is paid by a scoped, committed assertion over named helpers, never by widening the gate's scope inside the PR that would be scored by it"

requirements-completed: [IPV6-01]

coverage:
  - id: D1
    description: "The probe runs a control UAT (set_power and set_color with readback) against the single device named by --serial, and marks control not_run when the flag is absent"
    requirement: IPV6-01
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestStageTarget::test_a_device_that_applies_writes_passes_control"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestStageTarget::test_a_device_that_ignores_writes_fails_control"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestSelectTarget (6 tests: match, formatting, absent serial, empty sweep, zoneless link-local, relay-only product)"
        status: pass
      - kind: other
        ref: "uv run python scripts/ipv6_thread_probe.py --help | grep -q -- --serial"
        status: pass
    human_judgment: false
  - id: D2
    description: "A MatrixLight's full pre-run state (every tile's colours, power, running firmware effect) is captured and restored in a finally, so a failed readback, a failing restore or a KeyboardInterrupt cannot leave a production device mid-run"
    requirement: IPV6-01
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestCaptureDeviceState (3 tests: matrix tiles/power/effect, OFF captures no effect, plain-light get_color path)"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestRestoreDeviceState (6 tests: per-tile exact colours then power then effect, ms-to-seconds speed, no effect when none ran, light path, colourless capture, failing restore reported)"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestStageTarget::test_restoration_runs_after_a_keyboard_interrupt"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestStageTarget::test_restoration_runs_after_an_injected_control_failure"
        status: pass
    human_judgment: false
  - id: D3
    description: "With --uat-output the probe emits a JSON record carrying schema_version, kind, phase, device_serial, device_ip, an ISO 8601 timestamp with timezone, library_head, per-stage passed/failed/not_run and a restored boolean"
    requirement: IPV6-01
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestBuildUatRecord (4 tests: full key set, tz-aware timestamp, library_head None without git, library_head None when rev-parse fails)"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestWriteUatRecord (2 tests: JSON round-trip in tmp_path, serial is a 12-char hex string never bytes)"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestStageResult (4 tests: passed, failed, raised, not_run)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The optional --stream stage delivers bounded Animator frames, closes its socket in a finally, and never affects the exit code"
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestStreamingStage::test_close_runs_even_when_the_frame_run_raises"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestStreamingStage::test_a_failed_stream_does_not_change_the_exit_code"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_ipv6_thread_probe.py::TestExitCode (3 tests, including a failed stream alone exiting zero)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The probe's coverage debt is closed by a scoped assertion with the global gate untouched: the six named helpers carry zero missing lines and zero partial branches, and neither pyproject.toml nor codecov.yml changed"
    verification:
      - kind: other
        ref: "uv run --frozen pytest tests/test_scripts/test_ipv6_thread_probe.py --cov=ipv6_thread_probe --cov-branch --cov-report=json:.cov-probe.json + the AST/JSON assertion from the plan's verify: 'probe helper coverage ok'"
        status: pass
      - kind: other
        ref: "git diff main HEAD --name-only -- pyproject.toml codecov.yml (empty)"
        status: pass
      - kind: other
        ref: "missing_branches intersected with the six helpers' line ranges is empty (checked beyond the plan's line-only assertion)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The harness is fit for the plan 10-06 hardware run against a real Thread MatrixLight"
    verification: []
    human_judgment: true
    rationale: "No test can prove a harness behaves correctly against firmware it has never met. Every stage is exercised against fakes here; the physical run, and the judgement that its record reflects a genuine run, is plan 10-06's blocking operator gate by design (D-22, SPEC R9)."

duration: 23 min
completed: 2026-08-27
status: complete
---

# Phase 10 Plan 05: Thread Hardware UAT Harness Summary

**`scripts/ipv6_thread_probe.py` grew a `--serial`-targeted control UAT with full matrix-image and firmware-effect restore in a `finally`, an opt-in non-gating `--stream` stage, and `--uat-output` emitting the record plan 10-06's merge gate reads, backed by 38 hardware-free tests whose assertions were each proven able to fail.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-08-27T13:24:30Z (approximate)
- **Completed:** 2026-08-27T13:47:00Z
- **Tasks:** 3
- **Files modified:** 3 (1 modified, 2 created)

## Accomplishments

- The probe can now be pointed at exactly one device by serial and driven through a `set_power` and a `set_color` roundtrip with readback, reporting each in its existing result-line style. Without `--serial` nothing is written to any light: a fleet-wide write is the thing T-10-13 forbids.
- Full-state capture and restore for a `MatrixLight`: every tile's colours via `get_all_tile_colors()`, the power level, and any running firmware effect, restored tile by tile through `set_matrix_colors()` then `set_power()` then `set_effect()`. Both mutating stages sit inside one `try/finally` that restores once, so no exit path skips it.
- `--stream` delivers a bounded Animator frame run strictly after control, closes the animator in a `finally`, and is absent from `_exit_code()`. Control passing while streaming fails is a first-class outcome (SPEC R9, the R9 adjacency edge).
- `--uat-output` writes the machine-checkable record: `schema_version` 1, `kind` `thread-hardware-uat`, `phase` `10`, `device_serial`, `device_ip`, a timezone-aware ISO 8601 `timestamp`, `library_head` from `git rev-parse HEAD`, per-stage `passed`/`failed`/`not_run`, and `restored`.
- `tests/test_scripts/` is a new test package with 38 tests covering all of it against fakes. Suite went from 3623 to 3661 passing; pyright, `ruff check` and `ruff format --check` all clean.

## Task Commits

1. **Task 1: control stage, `--serial`, full-state capture/restore, `--uat-output`** - `a9f1c5f` (feat)
2. **Task 2: opt-in streaming stage, recorded but never gating** - `d6f8895` (feat)
3. **Task 3: hardware-free tests with a scoped coverage assertion** - `a99091d` (test)

**Plan metadata:** the commit carrying this file.

All four are GPG-signed under key `66D6066620F03B05` with `Signed-off-by: Avi Miller <me@dje.li>`. Nothing was pushed to any remote (D-24).

## Files Created/Modified

- `scripts/ipv6_thread_probe.py` - +521/-10. Adds stages 4 and 5, the `--serial` / `--stream` / `--uat-output` flags, and the six named helpers plus `_hue_delta()`, `_exit_code()`, `_build_animator()`, `run_control_stage()`, `run_streaming_stage()` and `stage_target()`.
- `tests/test_scripts/__init__.py` - new test package marker, matching the other test subpackages.
- `tests/test_scripts/test_ipv6_thread_probe.py` - 706 lines, 38 tests, no socket and no emulator.

## The `--cov` scope decision (restated for plan 10-06)

Plan 10-01 escalated this to plan 10-05 and this plan settled it. **The decision is: do not widen `--cov`, and do not touch `codecov.yml`.** Plan 10-06 Task 1 should verify this treatment, not reopen it.

The facts, re-verified here rather than taken on trust:

- `pyproject.toml` `addopts` declares `--cov=lifx --cov=generate_theme_data`. `scripts/ipv6_thread_probe.py` is under neither, so it produces no entry in `coverage.xml` at all. It is **unmeasured, not uncovered** — a reporting gap, not a coverage gap.
- `codecov.yml` **does** carry a `flags:` block (CONTEXT D-18's claim that it does not is stale, as plan 10-01 already flagged), and each of the five Python flags scopes `paths:` to both `src/lifx/` and `scripts/`. So `scripts/` is inside Codecov's flag paths while outside pytest's `--cov` scope.

Why widening was rejected:

1. This PR introduces the whole 521-line file via replayed commit `b641e22`, so every line would enter the patch diff at once, against `patch.default.target: 100%` with branch partials counted.
2. The probe's three original stages (`records`, `ports`, `connect`) cannot execute without real Thread hardware and an mDNS responder. No test can drive them, so a large fraction of those lines is untestable in CI by construction.
3. The only ways to make that number work would be lowering the patch target, adding `pragma: no cover`, or skipping tests. All three are explicitly prohibited by this phase's SPEC negative criteria and by prohibition 3, and the resulting pressure is exactly threat T-10-19.
4. `scripts/mdns_probe.py` and `scripts/serial_mac_audit.py` are equally unmeasured hardware diagnostics. Adding only this one would be inconsistent as well as unsafe.

What was done instead: the new non-network logic is factored into six named module-level helpers, all of them tested, and Task 3's verify runs a **scoped** coverage report over the probe for this test module alone and fails if any line inside those helpers is missing. Verified result:

```
$ uv run --frozen pytest tests/test_scripts/test_ipv6_thread_probe.py -q \
      --cov=ipv6_thread_probe --cov-branch --cov-report=json:.cov-probe.json
38 passed in 2.04s
$ <AST/JSON assertion over _select_target, _capture_device_state, _restore_device_state,
   _stage_result, _build_uat_record, _write_uat_record>
probe helper coverage ok

$ git diff main HEAD --name-only -- pyproject.toml codecov.yml
(no output)
```

One check beyond what the plan asked for: `missing_branches` intersected with the six helpers' line ranges is also **empty**, so the helpers carry zero partial branches, not merely zero missing lines. That matters because this project's Codecov gate scores branch partials (auto-memory `project_codecov_branch_patch`), so a line-only assertion would have been the weaker of the two available standards. The one partial branch that existed at first (`_restore_device_state`'s defensive `if state.color is not None` false arm) is now covered by `test_power_alone_is_restored_when_no_colour_was_captured`.

`.cov-probe.json` is generated by the verify and deleted by it; `git status --porcelain` is clean of it.

`10-COVERAGE-GAPS.md` was deliberately **not** annotated as closed, matching plan 10-03's treatment: it is the independent checklist plan 10-06 verifies against, and ticking it here would invite a rubber-stamp. The closure evidence lives in this section.

## Proving the tests can fail

Following the standard plans 10-01 and 10-04 set, no assertion was trusted until it had been observed failing. Five mutations were applied to `scripts/ipv6_thread_probe.py` and reverted:

| Mutation | Result |
|---|---|
| `_exit_code()` also reads `outcome.streaming` | 2 failed |
| `animator.close()` moved out of its `finally` | 2 failed |
| restore stops re-applying the firmware effect | 2 failed |
| `_capture_device_state()` drops the per-tile image | 7 failed |
| the restore moved out of the outer `finally` onto the happy path | **37 passed — survived** |

The survivor was the useful one. Every per-stage handler catches `Exception`, so a control or streaming failure never escapes to the outer `try`, which means the outer `finally` was only ever exercised on the normal path. A `KeyboardInterrupt` is the one thing that does escape, and the plan named it explicitly ("a failed readback, a timeout or a KeyboardInterrupt still puts the device back"). `test_restoration_runs_after_a_keyboard_interrupt` was added, and the same mutation then failed 1 test. `scripts/ipv6_thread_probe.py` was restored to its committed state after each mutation and `git status` confirmed clean; no mutation was committed.

## Decisions Made

- **`--uat-output` requires `--serial`.** argparse errors out otherwise. An honest `not_run` is always a valid stage value, but a *record* naming no device cannot satisfy SPEC AC 19 and would be a repudiation surface (T-10-14) rather than useful evidence.
- **A firmware effect is captured only when it is actually running.** `get_effect()` always returns a `MatrixEffect`, including `OFF`. Storing `OFF` as "an effect to restore" would have made restoration send a `set_effect(OFF)` the device never needed; storing `None` instead means "nothing to re-arm".
- **`MatrixEffect.speed` is milliseconds, `set_effect(speed=)` is seconds.** Restoration divides by 1000. Passing the captured value straight back would have restored a MORPH at 5000 seconds per cycle instead of 5.
- **`_build_animator()` exists as a seam.** The three `Animator` factories all query the device, so the `close()`-on-exception guarantee could otherwise only be checked against hardware.
- **The fakes subclass `MatrixLight` and `Light`.** `_capture_device_state()` branches on `isinstance(device, MatrixLight)`; a duck-typed double would take the plain-light path and the matrix capture test would pass while proving the opposite of its name.
- **`git rev-parse` is resolved through `shutil.which("git")`.** This makes the "git unavailable" arm real rather than hypothetical, and it removes bandit's B607 partial-path finding honestly instead of suppressing it. The remaining B404/B603 use the repository's existing `# nosec` convention from `src/lifx/products/generator.py` and `src/lifx/protocol/generator.py`.
- **Streaming constants are module-level, not new CLI flags.** `_STREAM_SECONDS = 3.0` and `_STREAM_FPS = 10.0` keep the operator surface at the three flags plan 10-06 depends on. Tests shrink them via `monkeypatch`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The pre-commit bandit hook rejected the `git rev-parse` call**

- **Found during:** Task 1 (first commit attempt)
- **Issue:** `_build_uat_record()` shells out to `git rev-parse HEAD` for `library_head`, which the local pre-commit bandit hook flagged with three Low/High-confidence findings: B404 (importing subprocess), B607 (partial executable path) and B603 (subprocess call). CI only runs `bandit -r src/`, but the pre-commit hook covers everything outside `tests/`, so the commit was blocked. The plan specified the behaviour but not how to get it past the hook.
- **Fix:** Resolved the executable with `shutil.which("git")` and passed the absolute path, which removes B607 for a real reason rather than by suppression, and additionally turns "git is not installed" into a directly testable branch. B404 and B603 use the repository's existing `# nosec B404` / `# nosec B603` convention, already established in both protocol and products generators.
- **Files modified:** scripts/ipv6_thread_probe.py
- **Verification:** `bandit` pre-commit hook Passed; `test_library_head_is_none_when_git_is_not_on_the_path` and `test_library_head_is_none_when_git_rev_parse_fails` cover both arms
- **Committed in:** `a9f1c5f`

**2. [Rule 2 - Missing Critical] The plan's coverage assertion checks lines only, not branch partials**

- **Found during:** Task 3
- **Issue:** The plan's verify command asserts on `missing_lines` inside the six helpers. This project's Codecov gate scores **partial branches** as well (auto-memory `project_codecov_branch_patch`), and the first run left one: `_restore_device_state`'s `if state.color is not None` false arm, at line 656. A line-only assertion would have declared the helpers covered while a branch arm went unexercised, which is the weaker of the two standards the project actually holds.
- **Fix:** Added `test_power_alone_is_restored_when_no_colour_was_captured`, which drives the defensive arm directly. The plan's verify command was run **unchanged** and passes; the branch check was run alongside it as an additional assertion and is now also empty.
- **Files modified:** tests/test_scripts/test_ipv6_thread_probe.py
- **Verification:** `missing_branches` intersected with the helpers' line ranges is `[]`
- **Committed in:** `a99091d`

**3. [Rule 2 - Missing Critical] The outer `finally` had no test that could fail**

- **Found during:** Task 3 (mutation testing)
- **Issue:** Moving `_restore_device_state()` out of the outer `finally` and onto the happy path left all 37 tests passing. Every per-stage handler catches `Exception`, so no ordinary failure reaches the outer block; only a `BaseException` does. The plan's own wording named `KeyboardInterrupt` as a case the restore must survive, and nothing asserted it.
- **Fix:** Added `test_restoration_runs_after_a_keyboard_interrupt`, which injects a `KeyboardInterrupt` from `set_color`, asserts it propagates, and asserts the per-tile restore still ran. The same mutation now fails.
- **Files modified:** tests/test_scripts/test_ipv6_thread_probe.py
- **Verification:** mutation re-run gives `1 failed, 37 passed`; probe restored to its committed state afterwards
- **Committed in:** `a99091d`

### Plan structure note (not a deviation to fix)

Task 3 carries `tdd="true"`, but its subject is a test module for code that Tasks 1 and 2 had already landed by design. A genuine RED commit was therefore impossible: any test written at that point either passes immediately or is wrong. The TDD gate's fail-fast rule ("if the test passes before any implementation, STOP and investigate") is satisfied by investigation rather than by a red commit — the implementation legitimately pre-exists. Mutation testing was used in place of the RED gate to prove each assertion is load-bearing, which is a stronger check than observing a single import error fail. See `## TDD Gate Compliance` below.

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 missing critical)
**Impact on plan:** No scope creep. Deviation 1 was a tooling constraint the plan did not anticipate and the fix improved testability. Deviations 2 and 3 both strengthened the evidence rather than changing behaviour: no production line changed as a result of either.

## TDD Gate Compliance

Task 3 is `tdd="true"`. Commit sequence for `10-05`:

| Gate | Commit | Present |
|---|---|---|
| RED (`test(10-05)`) | `a99091d` | Yes, but authored after GREEN |
| GREEN (`feat(10-05)`) | `a9f1c5f`, `d6f8895` | Yes |
| REFACTOR (`refactor(10-05)`) | — | Not needed |

**Violation, and why it is inherent to the plan rather than to its execution:** the `feat` commits precede the `test` commit. Plan 10-05 assigns the implementation to Tasks 1 and 2 and the tests to Task 3, so RED-before-GREEN is unreachable without contradicting the plan's own task ordering. Recorded here rather than silently ignored. The mitigation applied was mutation testing (see above), which demonstrates each assertion fails against broken code — the property RED exists to establish.

## Issues Encountered

- **A shell `cp -i` alias silently defeated the first mutation run.** The mutate/revert loop used `cp` to restore the probe between mutations; the interactive alias prompted, answered "n" by default, and left every mutation stacked on the previous one and the file dirty afterwards. Caught by `git diff --stat` immediately after the loop, before any commit. The file was restored with `git checkout -- scripts/ipv6_thread_probe.py` and the whole run redone using `git checkout` as the revert mechanism throughout. No mutated code reached a commit; `git status` was verified clean before each of the three task commits.

## Known Stubs

None. Every code path added by this plan is either exercised by a test or is a network call to real hardware that plan 10-06 exercises by design.

## Threat Flags

None. The plan's `<threat_model>` already names the surface this work introduces (T-10-13 device-state tampering, T-10-14 repudiation, T-10-15 and T-10-22 DoS), and every `mitigate` disposition was implemented: single-serial targeting, full-state capture and restore in a `finally`, the `restored` boolean in the record, observed-only stage values, strictly sequential stages, and `Animator.close()` in a `finally`. No new network endpoint, auth path or trust boundary was added — the probe opens no socket of its own and drives only the library's existing primitives.

## Verification Record

```
$ uv run python scripts/ipv6_thread_probe.py --help          # exit 0
  ... lists --serial, --stream and --uat-output by name

$ grep -c "get_all_tile_colors\|set_matrix_colors" scripts/ipv6_thread_probe.py
2

$ uv run ruff format --check .        258 files already formatted
$ uv run ruff check .                 All checks passed!
$ uv run pyright                      exit 0 - 0 errors, 0 warnings
$ uv run --frozen pytest -q           3661 passed, 12 deselected  (was 3623)

$ grep -rn '":" in ' src/lifx/        (no output — SPEC AC 8 not regressed)
$ git diff main HEAD --name-only -- pyproject.toml codecov.yml
                                      (no output)
```

No hardware was contacted at any point in this plan. The three network stages and the physical control run belong to plan 10-06.

## User Setup Required

None. No external service configuration was required.

## Next Phase Readiness

- **Plan 10-06's precondition is satisfied:** `uv run python scripts/ipv6_thread_probe.py --help` lists `--serial`, `--uat-output` and `--stream`, which its Task 2 step 0 checks before asking the operator to touch hardware.
- **The operator command in 10-06 Task 2 runs as written.** `--stage` defaults to `all`, so records, ports and connect all run before the control stage; add `--stream` for a streaming artefact.
- **The record shape matches what 10-06's automated check reads:** `device_serial` (12-digit hex string), `schema_version` 1, `kind` `thread-hardware-uat`, tz-aware `timestamp`, `library_head` equal to `git rev-parse HEAD` at run time, `stages.control`, and `restored`. If `restored` is `false` the device was genuinely left mid-run and the probe printed a warning naming it.
- **The exit code is usable as a gate:** non-zero only when `connect` or `control` failed. A failed streaming run exits zero.
- **The `--cov` question is closed with reasoning above.** Plan 10-06 Task 1 should confirm the treatment is recorded, not re-litigate it.
- **No blockers.**

## Self-Check: PASSED

`scripts/ipv6_thread_probe.py`, `tests/test_scripts/__init__.py` and
`tests/test_scripts/test_ipv6_thread_probe.py` all exist on disk. All three task
commits resolve in `git log --all`: `a9f1c5f`, `d6f8895`, `a99091d`, each with a good
signature (`%G?` = `G`, key `66D6066620F03B05`) and a `Signed-off-by: Avi Miller
<me@dje.li>` trailer. None of the three deleted a tracked file. The working tree was
clean before and after every commit, `.cov-probe.json` is absent, and nothing was
pushed to any remote. This documentation commit's own hash is not quoted because a
commit cannot name itself.

---
*Phase: 10-land-the-ipv6-thread-branch*
*Completed: 2026-08-27*
