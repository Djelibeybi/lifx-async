---
phase: 18
round: 2
reviewers: [codex, opencode, antigravity]
reviewed_at: 2026-09-23T07:25:00Z
plans_reviewed: [18-03-PLAN.md, 18-04-PLAN.md, 18-06-PLAN.md, 18-07-PLAN.md, 18-08-PLAN.md]
prior_round: 18-REVIEWS-ROUND1.md
models:
  codex: "gpt-5.6-sol (reasoning=high)"
  opencode: "openrouter/z-ai/glm-5.3 (reasoning=high)"
  antigravity: "gemini-3.1-pro-high"
model_sources:
  codex: "pinned"
  opencode: "pinned"
  antigravity: "pinned"
trimmed_reviewers:
  opencode:
    budget: null
    omitted: [project, requirements, "CONTEXT D-01 to D-08", review-dispositions-ledgers]
    note_injected: true
    reason: "First run hit the 1200 s lane timeout with no review. Re-run on a focused 158 KB prompt (full prompt 197 KB) with a bounded-verification brief; all 12 tasks kept intact."
---

# Cross-AI Plan Review: Phase 18, round 2

Round 2 reviews the five plans revised after ANIM-05 moved to Phase 20. Round 1 and the
maintainer adjudication are in `18-REVIEWS-ROUND1.md`.

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## Codex Review

# Phase 18 Plan Review

Bottom line: the five implementation plans are technically strong and the emulator 3.7.0 assumptions are accurate. However, the phase should not execute until the post-split canonical artefacts are reconciled: the roadmap assigns ANIM-05 to Phase 20, while the locked Phase 18 SPEC and CONTEXT still require the Thread guard. That is a verification-blocking inconsistency.

## 18-03

### Summary

The typed Move builder is well designed. It funnels through the existing dataclass validation, preserves the raw path, and verifies the actual wire payload. One numeric edge remains: arbitrarily large integers can escape the promised `ValueError` contract as `OverflowError`.

### Strengths

- The builder reuses the existing four-field dataclass and its validation rather than duplicating the raw path ([multizone.py:44](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:44), [multizone.py:49](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:49)).
- Direction really is serialised through `parameters[1]`, so the golden-packet comparison exercises the correct protocol slot ([multizone.py:883](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:883)).
- Emulator 3.7.0 does zero all eight returned Move parameters and stores speed in whole seconds, validating the packet-capture acceptance mechanism ([multizone_handlers.py:193](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/handlers/multizone_handlers.py:193), [multizone_handlers.py:228](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/handlers/multizone_handlers.py:228)).
- The proposed `get_effect()` barrier addresses the real fast-ack ordering: the emulator sends the acknowledgement before invoking `process_packet()` ([server.py:253](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/server.py:253), [server.py:266](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/server.py:266)).

### Concerns

- **MEDIUM:** The plan admits every non-bool `int`, then calls `math.isfinite()` before checking the converted bound ([18-03-PLAN.md:221](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-03-PLAN.md:221)). Under the locked Python, `math.isfinite(10**400)` raises `OverflowError`, not the promised overflow `ValueError`.
- **LOW:** Several plan passages still say the SPEC names emulator 3.10.0 ([18-03-PLAN.md:86](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-03-PLAN.md:86)), but the current SPEC already names 3.7.0 ([18-SPEC.md:135](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-SPEC.md:135)).

### Suggestions

- Handle integers separately from floats, or catch `OverflowError` from `math.isfinite()`.
- Add `speed=10**400` and `duration=10**400` tests asserting `ValueError`.
- Remove the stale 3.10.0 commentary.

### Risk Assessment

**MEDIUM.** The protocol and emulator strategy are sound, but the public numeric-validation contract has one reachable exception leak.

## 18-04

### Summary

This is a cohesive Morph implementation plan with strong preservation evidence. Validation ordering, wire-granularity equality, timeout fallback, and emulator palette round-tripping all match the current code.

### Strengths

- `HSBK.__eq__` already compares wire representations, exactly matching the required single-colour rule ([color.py:282](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/color.py:282)).
- `MatrixEffect` currently owns the exact palette messages that the shared validator will preserve ([matrix.py:261](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/matrix.py:261)).
- Constructing `MatrixEffect` before the new colour read preserves argument-validation ordering ([matrix.py:1248](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/matrix.py:1248)).
- `dataclasses.replace()` is appropriate here: `from_device` has a default, and replacement reruns `__post_init__`.
- Emulator 3.7.0 stores `palette[:palette_count]` and reports it back, making the integration assertion meaningful ([tile_handlers.py:404](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/handlers/tile_handlers.py:404), [tile_handlers.py:453](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/handlers/tile_handlers.py:453)).
- The single-colour paint precondition is valid: `set_matrix_colors()` uses device-wide `SetColor` on a one-tile uniform matrix ([matrix.py:998](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/matrix.py:998)), and emulator 3.7.0 propagates it across all tile pixels ([light_handlers.py:142](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/handlers/light_handlers.py:142)).

### Concerns

- **LOW:** The initial golden class includes the pre-change palette-less Morph case ([18-04-PLAN.md:202](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-04-PLAN.md:202)). After the implementation, that same call must explicitly represent a multi-colour device. Task 2 adds equivalent coverage, but does not explicitly say to adapt the original golden test, leaving room for a predictable failure or duplicate test.
- **LOW:** The new Morph path adds at least one network read before sending. The plan documents this correctly, but it is a real start-up latency and failure-surface increase.

### Suggestions

- Explicitly instruct Task 2 to update the original `_GOLDEN_MORPH_NO_PALETTE_BEFORE` test with a multi-colour `get_all_tile_colors()` stub.
- Keep the pre-change golden commit immutable; only change the later test setup, not the recorded hex constant.

### Risk Assessment

**LOW.** Behaviour, validation, timeout handling, and preservation tests are comprehensive. The remaining issue is execution clarity around one golden test.

## 18-06

### Summary

The device-level typed API is correctly layered over plans 03 and 04. The sequencing of validation, optional derivation, paint, and effect send is explicit, and the revised StateUnhandled test now proves the error originates from `set_effect()`.

### Strengths

- Dependencies correctly require both the builder and shared palette helper before this plan starts ([18-06-PLAN.md:6](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-06-PLAN.md:6)).
- The raw sender remains isolated and sends direction from the existing parameter list ([multizone.py:834](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:834)).
- `apply_theme()` really does generate a shuffled, blended zone list and paint it through the extended-or-legacy abstraction ([multizone.py:1168](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:1168), [generators.py:100](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/generators.py:100)).
- The StateUnhandled fixture is valid: product 70 is added to the same emulator server ([tests/conftest.py:862](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/conftest.py:862)), unsupported packets generate StateUnhandled inside `process_packet()` ([device.py:287](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/devices/device.py:287)), and the connection raises `LifxUnsupportedCommandError` before returning ([connection.py:1207](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/network/connection.py:1207)).
- The timeout scenario is credible because emulator 3.7.0 drops the request before sending any acknowledgement or reply ([server.py:245](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/server.py:245)).

### Concerns

- **LOW:** “Explicit palette, with no zone read” is slightly misleading. It avoids `get_all_color_zones()`, but `apply_theme()` still calls `get_zone_count()` and `get_power()` before painting ([multizone.py:1170](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:1170)). The tests correctly assert only that the colour-zone read is skipped.
- **LOW:** This plan repeats the stale claim that the SPEC still names emulator 3.10.0 ([18-06-PLAN.md:80](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-06-PLAN.md:80)).

### Suggestions

- Replace “no zone read” with “does not call `get_all_color_zones()`” throughout the truths, docs, and tests.
- Remove the obsolete 3.10.0 qualification.

### Risk Assessment

**LOW.** The implementation and integration evidence are carefully ordered and source-backed.

## 18-07

### Summary

The documentation plan addresses real broken examples and has strong build, execution, and scope gates. Its main local weakness is that one purportedly multiline-aware stale-call scan is not multiline-aware for `set_move_effect`. More importantly, this plan exposes the unresolved Phase 18 SPEC/CONTEXT split contradiction.

### Strengths

- The cited documentation defects are real: the migration guide shows the nonexistent keyword-first method ([effect-api-changes.md:45](/Volumes/External/Developer/Djelibeybi/lifx-async/docs/migration/effect-api-changes.md:45)), while the API page calls `MultiZoneLight.set_effect()` with unsupported keywords for both MOVE and OFF ([devices.md:647](/Volumes/External/Developer/Djelibeybi/lifx-async/docs/api/devices.md:647), [devices.md:660](/Volumes/External/Developer/Djelibeybi/lifx-async/docs/api/devices.md:660)).
- Executing every Python block in the new guide section is stronger than merely building the page.
- The region-scoped `set_effect(effect_type=...)` scan correctly avoids false positives from `MatrixLight`, where that signature is valid.
- Strict Zensical build, llms.txt validation, patch coverage, full tests, Australian English, changelog protection, and split-boundary checks form a strong final gate set.

### Concerns

- **MEDIUM:** The plan truth says split-line keyword-first `set_move_effect` calls are forbidden ([18-07-PLAN.md:26](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-07-PLAN.md:26)), but the scan only checks the literal substring `set_move_effect(speed=` ([18-07-PLAN.md:236](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-07-PLAN.md:236)). A form such as `set_move_effect(\n    speed=...)` passes.
- **HIGH:** The plan correctly treats Thread documentation as Phase 20 scope ([18-07-PLAN.md:73](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-07-PLAN.md:73)), but the canonical locked SPEC still requires that documentation in Phase 18 ([18-SPEC.md:153](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-SPEC.md:153)). An executor following the plan and a verifier following the SPEC will disagree.

### Suggestions

- Use `re.compile(r"set_move_effect\\(\\s*speed\\s*=")` alongside the existing multiline Move `set_effect` regex.
- Reconcile the SPEC and CONTEXT before executing this plan.

### Risk Assessment

**MEDIUM locally, HIGH while the canonical scope conflict remains.** The documentation work is sound, but verification cannot be deterministic against the current locked artefacts.

## 18-08

### Summary

The PLC0415 sweep is mechanically careful. The corrected `-qq` collection command works under locked pytest 9.1.1 and produces 263 node IDs, and the repository contains exactly the claimed 20 current violations.

### Strengths

- The current lint configuration has the two precise exemptions this plan removes ([pyproject.toml:90](/Volumes/External/Developer/Djelibeybi/lifx-async/pyproject.toml:90)).
- The measured sites are accurate: 18 are in `test_animator.py`, and two are in the existing MultiZoneEffect tests ([test_animator.py:159](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/test_animation/test_animator.py:159), [test_multizone.py:835](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/test_devices/test_multizone.py:835)).
- The baseline command fails closed on dirty target paths, collection failure, and an empty node-ID stream ([18-08-PLAN.md:153](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-08-PLAN.md:153)).
- Exact before/after node-ID equality is the right invariant for an import-only sweep ([18-08-PLAN.md:219](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-08-PLAN.md:219)).
- The positive stdin probes and full default suite guard against a vacuous lint success and module-level import cycles.

### Concerns

- **MEDIUM:** The final phase tree will modify `tests/test_devices/test_multizone.py`, while locked R6 says those tests pass “unmodified” ([18-SPEC.md:142](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-SPEC.md:142)). The plan deliberately sequences the proof before the import-only sweep ([18-08-PLAN.md:65](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-08-PLAN.md:65)), but a final diff-based verifier will still see a modification.
- **LOW:** “Let `ruff check --fix` and `ruff format` settle ordering” is not explicitly scoped to the owned files ([18-08-PLAN.md:207](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-08-PLAN.md:207)). A repository-wide auto-fix could alter unrelated work.

### Suggestions

- Amend R6 to permit an import-only hygiene change while requiring all assertions, fixtures, and node IDs to remain unchanged.
- Run formatting and auto-fix against the two owned test paths only.
- Add a diff gate that rejects non-import changes to both swept test files, not only a prose acceptance statement.

### Risk Assessment

**MEDIUM.** The sweep itself is low risk, but its final-state evidence conflicts with the locked wording of R6.

# Cross-plan assessment

## Dependency and scope quality

The dependency graph is correct:

- 18-03 and 18-04 are genuinely independent.
- 18-06 needs both.
- 18-07 transitively receives both through 18-06.
- 18-08 waits for the plans that must first prove the raw tests unmodified.

No obsolete emulator-bump or IPv6/Thread fixture dependency remains in the five plans.

## Verification-blocking scope conflict

The Phase 18 split was not fully propagated through the canonical artefacts:

- The roadmap assigns only EFFECT-01 and EFFECT-02 to Phase 18 and ANIM-05 to Phase 20 ([ROADMAP.md:289](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/ROADMAP.md:289), [REQUIREMENTS.md:180](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/REQUIREMENTS.md:180)).
- `18-SPEC.md` still says ten requirements are locked and retains the Thread guard in the goal, requirements, boundaries, and checklist ([18-SPEC.md:5](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-SPEC.md:5), [18-SPEC.md:64](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-SPEC.md:64), [18-SPEC.md:221](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-SPEC.md:221)).
- `18-CONTEXT.md` simultaneously says the Thread decisions moved to Phase 20 and still declares them locked and in scope ([18-CONTEXT.md:21](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-CONTEXT.md:21), [18-CONTEXT.md:63](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-CONTEXT.md:63)).
- Its canonical references also still describe the emulator Thread release as a Phase 18 prerequisite ([18-CONTEXT.md:242](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-CONTEXT.md:242)).

This should be fixed before execution by either splitting/reissuing the SPEC or explicitly marking R1-R3/R8 and their Thread acceptance criteria as moved to Phase 20. The R6 import-only exception should be clarified at the same time.

## Emulator verdict

The reviewed emulator claims are confirmed:

- Exact installed version: 3.7.0 ([uv.lock:299](/Volumes/External/Developer/Djelibeybi/lifx-async/uv.lock:299)).
- Move GetEffect zeroes parameters and reports whole-second speed.
- Fast acknowledgements precede `process_packet()`.
- Scenario drops happen before acknowledgements.
- `server.get_device(serial)` returns the patched device object.
- Tile palettes round-trip through SetEffect/GetEffect.
- StateUnhandled is produced inside `process_packet()` for the switch.

## Overall Risk Assessment

**HIGH until the SPEC/CONTEXT split is reconciled; MEDIUM after that.**

The proposed implementation itself is credible and well tested. The highest risk is currently procedural: a compliant executor and a compliant verifier can reach opposite conclusions because the locked source of truth still describes the pre-split phase.

Prior memory was used only to identify the Phase 18 planning context; every substantive claim above was refreshed against the current checkout and installed emulator.



---

## OpenCode Review

## 18-03

**Summary**: Builds `MultiZoneEffect.move(direction, speed, duration=0)` on a private `_coerce_direction()` and a seconds-to-wire converter with uint32/uint64 bounds, widens the `direction` setter to enum-or-name, and proves the raw Home Assistant path byte-identical via a golden-packet backstop plus an untouched existing test file. The design is tight and the two open contract decisions (TypeError for non-numeric, asymmetric property) are settled in-plan with a stop-and-report escape hatch.

**Strengths**:
- Golden backstop uses the issue #191 construction verbatim and compares `pack()` bytes through `set_effect()`, which is exactly the right invariance proof for R6 given `set_effect` builds `MultiZoneEffectSettings` from the fields (src/lifx/devices/multizone.py:876-895).
- Boundary arithmetic is real, not aspirational: I executed the conversions and got `round((2**32-1)/1000*1000) == 4294967295`, `round(2**32/1000*1000) == 4294967296`, `round(2.5*1e9) == 2500000000`, so the accept/raise must_haves hold exactly as written.
- Existing setter callers all pass `Direction` members (tests/test_devices/test_multizone.py:938-1039), so widening cannot break the byte-identical test file.

**Concerns**:
- LOW: the raw-path contract technically narrows in one undocumented corner: the old setter accepted any `int` (untyped `int(value)` at multizone.py:118-132), the new `_coerce_direction` raises ValueError for ints. D-09 frames it as a widening (enum-only to enum-or-name), which is correct per the annotation, but callers passing `effect.direction = 1` today get a break. No existing test does, and the prohibition only promises wire-payload identity, so this is acceptable; worth one line in the migration guide.
- LOW: `direction` accepts a bool as ValueError while `speed`/`duration` accept a bool as TypeError; inconsistent for `move(True, True)`. Decided per D-09/L541, tested, documented in Raises; noting only so the docs state it.

**Suggestions**: Note the int-to-ValueError setter change in the migration guide's Move section (plan 07 already rewrites it; one sentence suffices).

**Risk Assessment**: LOW — the plan's verified claims (floats, Direction members, existing callers, set_effect capture seam) all check out against the tree.

## 18-04

**Summary**: Adds the pure `derive_effect_palette()` and shared `validate_effect_palette()` in component_state.py, wires MORPH-only derivation into `MatrixLight.set_effect()` via `dataclasses.replace()`, and pins five golden payloads captured before the change. The replace-through-validator design correctly routes derived palettes through the same size rule (matrix.py:215-216 validates only non-None palettes, so the None rebuild stays on the existing path).

**Strengths**:
- Goldens-before-change with a test-only capture commit and a grep gate proving no `src/` file rode along; the capture evidence is auditable.
- `replace()` with the defaulted InitVar is sound: I executed the exact dataclass shape and `replace(a, x=2)` works; `from_device: InitVar[bool] = False` is confirmed at matrix.py:198, and `__post_init__` re-runs `_validate_palette` on the derived palette (matrix.py:215-216).
- The two existing tests are correctly diagnosed: `test_set_effect_without_palette` (tests/test_devices/test_matrix.py:491-504) would otherwise see a derived palette and fail `effect.palette is None`, and `test_set_effect_other_effects_skip_the_gate` (:914-924) hits the unstubbed read; the plan's fixes are minimal and intent-preserving.
- Emulator claims (SetColor repaints all pixels, SetEffect/GetEffect palette round trip, 2500-9000 K registry range) marked as verified; consistent with everything I could check offline.

**Concerns**:
- **MEDIUM**: `TestTileSetEffectGoldens`' own `_GOLDEN_MORPH_NO_PALETTE_BEFORE` case goes red the moment matrix.py gains the derivation. The golden mock is built like `_matrix_light()` (send_packet=AsyncMock), and `mock_device_factory` leaves `connection.request = AsyncMock()` (tests/test_devices/conftest.py:50); post-change the case calls `get_all_tile_colors()` → `get_device_chain()` → `await self.connection.request(...)` (matrix.py:462-465), which returns a MagicMock and raises something other than LifxTimeoutError, so it propagates out of `_derive_morph_palette`. Task 1's own verify runs the whole module after the matrix.py edit, so the executor hits this with no instruction. The plan already contains the fix pattern (Task 2 stubs `get_all_tile_colors` multi-colour for test_matrix.py:914); the golden case needs the same stub, and it must be multi-colour for the payload to remain `_GOLDEN_MORPH_NO_PALETTE_BEFORE`. A single-colour stub would silently invalidate the golden.
- LOW: `speed_ms = round(speed * 1000) if speed else 3000` (matrix.py:1246) means MORPH `speed=0` silently becomes 3000; pre-existing, not this plan's to fix, but the derivation tests should keep using non-zero speeds (they do).

**Suggestions**: Add one sentence to Task 1: after wiring the derivation, stub `get_all_tile_colors` to a multi-colour result in the `_GOLDEN_MORPH_NO_PALETTE_BEFORE` golden case so the pre-change bytes are preserved and the module stays green.

**Risk Assessment**: MEDIUM — one concrete red-module sequencing gap (the golden MORPH case), otherwise verified and well designed.

## 18-06

**Summary**: Adds `MultiZoneLight.set_move_effect(direction, speed, duration=0, palette=None)` building on plan 03's builder and plan 04's helpers, painting through `apply_theme(Theme(palette), duration=0)` per D-20, with a thorough emulator/mock matrix covering explicit palettes, multi-colour strips, the raw path's exact `[508, 507]` capture, timeouts and error propagation. The interface claims all check out against the tree.

**Strengths**:
- Every fixture and seam claim verified: `apply_theme` at multizone.py:1142-1189 with the in-method generator import at :1168 (the lazy `Theme` import mirrors it, and `src/**` carries the PLC0415 ignore); `Theme` is TYPE_CHECKING-only at :27-28; stale class-docstring calls at :215 and :222 exactly as described; `MultiZoneLight.__init__(serial, ip, port, ...)` at :228; `emulator_devices[4]` is the `d073d5000005` strip at tests/conftest.py:774-780 with timeout 2.0/max_retries 2; `switch_device` yields a `DeviceConnection` with serial/ip/port at conftest.py:887-893; `scenario_manager` matches its description at :899-979.
- The StateUnhandled test is well constructed: explicit palette removes the zone read, mocked `apply_theme` removes the paint, so the raise is attributable to `set_effect()` alone.
- The permutation-candidate assertion is sound: `get_theme_colors` calls `theme.shuffled()` (generators.py:110) which uses module-level `random.shuffle` (theme.py:170), and HSBK equality is uint16-based (color.py:282-291), so the paint/read-back round trip is stable against the hand-computed candidates.

**Concerns**:
- LOW: the tracer test wraps `apply_theme` with `wraps=` on the session-scoped strip instance; the patch exits before the capture barrier, so no cross-test leakage. Fine, but the plan should remind the executor the patch must cover only the `set_move_effect` call (it does by structure).
- LOW: `_derive_move_palette`'s DEBUG record claims `"method": "set_move_effect"` while the module's convention logs the method the record is emitted from; cosmetic and consistent with the sibling `_derive_morph_palette`, no action needed.
- LOW: dropping 511 with max_retries=2 means the derivation read takes roughly two 2-second timeouts before the DEBUG fallback; within emulator limits but the test budget accounts for it only implicitly.

**Suggestions**: None material.

**Risk Assessment**: LOW — the highest-risk claims (fixture indices, signatures, docstring staleness, switch fixture) are all verified correct.

## 18-07

**Summary**: Documents the typed Move API in the user guide with a verbatim-executed example, rewrites the migration guide and devices API page off the nonexistent keyword forms, widens the AGENTS.md component_state line, and runs phase-wide gates including the split-boundary scan. All stale-content anchors are accurate.

**Strengths**:
- Anchors verified: `## Next Steps` at docs/user-guide/effects.md:892; migration keyword calls at :45, :78, :130 and the `effect_type=FirmwareEffect.MOVE` forms at :54, :84, :142 and the Summary of Removals at :236; devices.md `### MultiZone Control` at :622 with the invalid MOVE call at :647-651 and OFF at :660, while the second `set_effect(effect_type=FirmwareEffect.OFF)` at :690 sits under `### Tile Control` (:663) where the keyword form is valid on MatrixLight, so the multizone-scoped scan is the right shape, not an oversight.
- The whole-tree stale scan is multi-line-aware and fail-closed on a wrong path (`scanned > 100`).
- The pure-additive gate on effects.md and the planned-docs-only gate correctly fence Phase 20's Thread notes out.

**Concerns**:
- **MEDIUM**: the split-boundary gate whitelists `+import threading` (`grep -vxE "\+import threading"` in Task 3). That is a stale carve-out from the pre-split version of this plan: after the ANIM-05 split nothing in Phase 18 should add `threading` to src/lifx, and the exemption pokes a hole precisely in the boundary the gate exists to enforce. If the split is correct the line is dead weight; if it ever fires, it is hiding exactly the leak the gate must catch.
- LOW: Task 1's verbatim test executes every python block in the new section in order against one strip; the plan should state the examples must be order-independent or intentionally sequential (they are: typed then builder), so a future editor adding a third block does not silently break ordering assumptions.
- LOW: the removed-lines gate on effects.md (must be 0) could collide with a heading-adjacent blank-line adjustment; trivial for the executor to satisfy additively.

**Suggestions**: Delete the `+import threading` exclusion from the split-boundary gate so any threading import under src/lifx fails the phase boundary outright.

**Risk Assessment**: LOW (MEDIUM if the threading carve-out is left in, since it weakens the phase-boundary gate).

## 18-08

**Summary**: Closes the Phase 16 D-05 handoff by hoisting all inline imports in `tests/test_animation/**` and `tests/test_devices/test_multizone.py` and deleting the two per-file-ignore lines, with fail-closed node-ID set comparison and stdin probes proving PLC0415 is live afterwards. Every measurable claim is accurate.

**Strengths**:
- Independently verified by execution: exactly 20 PLC0415 violations under `ruff check --isolated --select PLC0415` (18 in test_animator.py, 2 in test_multizone.py at :835 and :873, matching the plan's line anchors); `pytest --collect-only -qq` does print `::` node IDs (63 collected for test_multizone.py) and the `-q`-prints-nothing trap is real, so the round 1 fix (L255) is correctly baked in.
- pyproject.toml:90-104 matches the described handoff comment and entry list exactly; the baseline command's clean-tree precondition, `set -o pipefail` and exact-set `diff` address every Phase 16 lesson (silent de-collection, vacuous gates).
- The Phase 19 parallel-entry interplay is handled (keep its removal if it landed first).

**Concerns**:
- LOW: the pyproject artifact contract says the file `contains: "tests/test_theme/**" = ["PLC0415"]`, which is false if Phase 19 (parallel wave 3) already removed its entry; the verify block tolerates that case but the artifact spec does not.
- LOW: Task 1's suggested commit message (`test: hoist multizone test imports...`) covers a commit that also edits pyproject.toml; cosmetic type inaccuracy.

**Suggestions**: Reword the pyproject artifact to "the two Phase 18 entries absent" rather than naming the Phase 19 line as content.

**Risk Assessment**: LOW — the plan's numbers, anchors and collection mechanics were all reproduced live.

## Overall verdict

APPROVE WITH MINOR REVISIONS. The wave structure, dependency ordering and split boundary are correct, EFFECT-01/02 and all three success criteria are fully covered, and the raw-path safety nets (goldens, untouched test files, packet-capture proofs) are genuinely strong. Two items should be fixed before execution: (1) 18-04 must stub `get_all_tile_colors` multi-colour in the `_GOLDEN_MORPH_NO_PALETTE_BEFORE` golden case post-change, otherwise Task 1's own verify goes red on an unstubbed mock read; (2) 18-07 should drop the `+import threading` whitelist from the split-boundary gate. Everything else is LOW-severity polish.


---

## Antigravity Review

## 18-03

**Summary**  
This plan adds `MultiZoneEffect.move()`, a typed builder for the firmware Move effect, and modifies the `MultiZoneEffect` dataclass to handle asymmetric `direction` properties. It successfully decouples input validation from network serialization by trapping invalid values immediately, before any packets hit the network.

**Strengths**  
- **Asymmetric Typing**: Implementing the `direction` property with a getter of `Direction | None` and a setter of `Direction | str` correctly reflects the API usage without causing type check failures (passes `pyright` standard mode).
- **Strict Input Validation**: The explicit check for `bool` alongside `int`/`float` in the speed and duration helpers enforces strict standard python conventions (since `bool` subclasses `int`), explicitly raising a `TypeError`.
- **Direct Mock Assertions**: Using `server.get_device(serial).process_packet` allows tests to intercept and verify the exact `MultiZone.SetEffect` packet emitted to `lifx-emulator-core`, entirely avoiding state read-back delays or emulator quirks.

**Concerns**  
- None. (LOW)

**Suggestions**  
- Ensure that the TypeErrors are consistently raised using `isinstance(value, bool)` before `isinstance(value, (int, float))`, exactly as prescribed, to catch `True`/`False` before they are coerced to `1`/`0`.

**Risk Assessment**  
LOW. The changes cleanly isolate the new builder on `MultiZoneEffect` (`src/lifx/devices/multizone.py`), keeping the legacy `set_effect()` raw path byte-for-byte identical, so existing integrations face zero regression risk.

## 18-04

**Summary**  
This plan introduces a shared `derive_effect_palette()` utility in `src/lifx/devices/component_state.py` and uses it to automatically populate a three-color palette for MORPH effects on Matrix devices when the user supplies none. It employs `dataclasses.replace` to invoke validation safely.

**Strengths**  
- **Validation Bypass Avoided**: Rebinding `effect = replace(effect, palette=...)` successfully triggers `MatrixEffect.__post_init__`, ensuring that the firmware-derived colors are subjected to the exact same validation rules as a user-supplied palette. (Verified `InitVar[bool]` correctly supports `dataclasses.replace`).
- **Regression Safety Net**: Caching golden payloads prior to any `src/` changes locks the `FLAME` and `SKY` effects into their existing byte sequences, forming an unassailable baseline.
- **Pure Derivation Logic**: Extracting the color derivation logic into the standalone `derive_effect_palette(colors, min_kelvin, max_kelvin)` allows exhaustively testing the 17-color bounds and shuffling algorithm synchronously.

**Concerns**  
- **Latency Penalty**: For MORPH effects invoked without a palette, a blocking `get_all_tile_colors()` request sequence is introduced before the `SetEffect` packet is emitted. (LOW)

**Suggestions**  
- Explicitly document this `get_all_tile_colors()` latency addition in the `set_effect()` docstring, as users expecting instantaneous triggering might otherwise observe a slight delay on multi-tile chains.

**Risk Assessment**  
LOW. The fallback implementation uses the device's configured timeout behavior (`LifxTimeoutError`), ensuring that a single dropped packet during the read phase does not indefinitely halt the effect application.

## 18-06

**Summary**  
This plan ties the Phase 18 goals together for MultiZone by adding `MultiZoneLight.set_move_effect()` (`src/lifx/devices/multizone.py`). It applies a one-call Move method that correctly paints an initial shuffled palette via `apply_theme()` before issuing the Move command.

**Strengths**  
- **Exception Inheritance**: By routing the final call through the existing `await self.set_effect(effect)`, the new method effortlessly inherits correct error propagation, such as `LifxUnsupportedCommandError` for devices returning `StateUnhandled` (like the switch device `d073d5000200` in `tests/conftest.py`).
- **Clean State Tracking**: Leveraging the pre-existing `apply_theme()` behavior correctly propagates the `MultiZoneGenerator` shuffled blend rules across the zones for single-colored strips.
- **Test Precision**: Mocking `apply_theme` with `AsyncMock(return_value=None)` in the integration tests successfully prevents premature test failures when testing `StateUnhandled` exceptions, verifying the exception originates from `SetEffect`.

**Concerns**  
- **Emulator Quirks Dependency**: Relying on extracting the direction from the captured packet (because `lifx-emulator-core 3.7.0` zeroes the `parameters` in `GetEffect`) firmly binds the test execution strategy to emulator internals (`server.get_device(serial).process_packet`). (LOW)

**Suggestions**  
- None. The plan handles the emulator 3.7.0 limitations efficiently and documents the exact reasons why it intercepts packets this way.

**Risk Assessment**  
LOW. The fallback for a `LifxTimeoutError` correctly logs at `DEBUG` and sends the effect anyway, avoiding any denial of service on the primary function of the method.

## 18-07

**Summary**  
This documentation plan writes user guides and migration docs for the newly typed effect API and aggressively roots out instances of the legacy `set_effect(effect_type=...)` keyword pattern. It relies on executing the docs in real-time to prevent drift.

**Strengths**  
- **Executable Documentation**: Using `_markdown_section_examples` combined with `ast.PyCF_ALLOW_TOP_LEVEL_AWAIT` ensures that all Python examples in the `docs/` tree are lexically valid, semantically executable against the emulator, and syntactically correct.
- **Strict RegEx Gates**: The build gates ensuring `set_effect(effect_type=FirmwareEffect.MOVE)` is banned across the repository prevent any accidental re-introduction of the older, non-typed API usage.
- **Strict Scope Boundaries**: Explicitly prohibits edits to Phase 20 Thread docs and auto-generated changelogs, maintaining a clean git history.

**Concerns**  
- **Regex Fragility**: The regex used to detect `set_effect(effect_type=FirmwareEffect.MOVE)` could potentially miss multiline breaks or unusual spacing (`set_effect( \n effect_type=`), although this is heavily mitigated by the project-wide `ruff format`. (LOW)

**Suggestions**  
- Consider utilizing an AST parsing approach rather than standard Regex searching if Python parsing ever becomes a bottleneck for documentation auditing.

**Risk Assessment**  
LOW. This plan only touches `docs/`, `tests/`, and comment lines, guaranteeing zero runtime production risk to the `lifx-async` payload.

## 18-08

**Summary**  
This plan finalizes a previous phase's hygiene goal by hoisting function-local imports to module scope inside `tests/test_devices/test_multizone.py` and `tests/test_animation/test_animator.py`, removing their corresponding `PLC0415` exemptions from `pyproject.toml:84-104`.

**Strengths**  
- **Bulletproof Validation**: Piping `uv run --frozen pytest --collect-only -qq` through `grep "::" | sort` and validating exact output parity via `diff` guarantees that no test cases are silently de-collected or stripped by `ruff` changes.
- **Strict Failure Gates**: Using `set -o pipefail` ensures that an upstream `pytest` crashing or an empty `grep` immediately trips the gate and aborts the task, preventing accidental "success" on an empty diff.
- **Pure Refactor Boundaries**: Limits itself purely to import positioning without executing any behavioral adjustments to test fixtures or function blocks.

**Concerns**  
- None. (LOW)

**Suggestions**  
- The bash line `B=$(grep -vc "::" .cache/phase-18/nodeids-before.txt || true); test "$B" -eq 0` successfully prevents the summary footer from breaking node parity. Since `.cache/phase-18/nodeids-before.txt` is generated via a pipeline already ending in `grep "::"`, the result will always be 0. It serves as an excellent invariant assertion.

**Risk Assessment**  
LOW. The rigorous test node comparison effectively neutralizes the risk of silently dropping tests.


---

## Consensus Summary

All three reviewers ran source-grounded, cited `file:line` evidence and covered all five plans.
Codex and OpenCode confirmed the emulator 3.7.0 mechanics independently: GetEffect zeroes the
Move parameters, the fast ack precedes `process_packet()`, scenario drops happen before the ack,
and tile palettes round-trip. The wave graph (03 and 04, then 06, then 07 and 08) is correct and
no split leftovers remain in the plans. Antigravity's review is the thinnest and found no
MEDIUM or higher issues.

### Agreed Strengths

- Golden-packet backstops and untouched existing test files prove the raw `MultiZoneEffect` and
  `MatrixLight.set_effect()` paths byte-identical (all three).
- Direction is proven from the captured `MultiZone.SetEffect` because 3.7.0 zeroes Move
  parameters in GetEffect (all three).
- `dataclasses.replace()` reruns `MatrixEffect.__post_init__`, so derived palettes pass the same
  validator as user-supplied ones (all three).
- 18-06's StateUnhandled test attributes the error to `set_effect()` alone (all three).
- 18-08's `-qq` node-ID set comparison under `pipefail` is fail-closed; 20 PLC0415 sites and
  263 node IDs reproduced live (Codex, OpenCode).

### Agreed Concerns

1. **18-04 golden MORPH case goes red after the derivation lands** (OpenCode MEDIUM, Codex LOW).
   `_GOLDEN_MORPH_NO_PALETTE_BEFORE` runs on a mock whose `connection.request` is a bare
   `AsyncMock`, so once `set_effect()` reads tile colours the case raises. Task 1's verify runs
   the whole module after the `matrix.py` edit with no instruction to stub it. Fix: stub
   `get_all_tile_colors` with a multi-colour result in that case (a single colour would
   invalidate the golden) and never edit the recorded hex constant.
2. **18-07 stale-example scans are not fully multi-line aware** (Codex MEDIUM, Antigravity LOW).
   `'set_move_effect(speed=' in text` misses `set_move_effect(\n    speed=...)`, contradicting the
   plan's own truth at 18-07-PLAN.md:26. Fix: `re.compile(r"set_move_effect\(\s*speed\s*=")`.
3. **Morph without a palette now adds a colour read before SetEffect** (Codex, Antigravity, both
   LOW). Already documented in the plan; keep the note in the `set_effect()` docstring.

### Single-reviewer findings worth acting on (verified by the orchestrator)

- **HIGH, Codex: 18-SPEC and 18-CONTEXT still describe the pre-split phase.** Verified: the SPEC
  title, "10 locked" requirements, R1 to R3, R8, the Thread boundaries and checklist are still
  present (18-SPEC.md:1, :5, :64, :221); CONTEXT's `<domain>`/`spec_lock` and Canonical
  References still list the Thread guard and the emulator pin bump (18-CONTEXT.md:18-22,
  :240-246). An executor following the plans and a verifier following the SPEC would disagree.
  Fix before execution: mark R1 to R3 and R8 (with their edges, prohibitions and checklist
  items) as moved to Phase 20, retitle the SPEC, and drop the stale CONTEXT references.
- **MEDIUM, Codex: 18-03 numeric validation leaks `OverflowError`.** Verified:
  `math.isfinite(10**400)` raises `OverflowError: int too large to convert to float`, so a huge
  `int` speed or duration escapes the promised `ValueError`. Fix: bound-check ints before
  `math.isfinite`, or catch `OverflowError`; add `10**400` tests for speed and duration.
- **MEDIUM, Codex: R6 says `tests/test_devices/test_multizone.py` passes "unmodified", but 18-08
  edits it.** The plan sequences the proof first, but a final-diff verifier will see the change.
  Fix: amend R6 to allow an import-only hygiene change, and add a diff gate rejecting non-import
  changes to the two swept files. Also scope 18-08's `ruff check --fix` / `ruff format` to the
  owned paths.
- **MEDIUM, OpenCode: 18-07's split-boundary gate whitelists `+import threading`.** Verified at
  18-07-PLAN.md:292. A pre-split carve-out that now pokes a hole in the gate it belongs to.
  Fix: delete the `grep -vxE "\+import threading"` exclusion.
- **LOW, OpenCode: the `direction` setter narrows for raw ints.** Today it accepts any int via
  `int(value)` (src/lifx/devices/multizone.py:118-132); `_coerce_direction()` rejects ints. No
  caller does this, but add one sentence to the migration guide.
- **LOW, Codex:** plan prose still says the SPEC "names 3.10.0" (18-03-PLAN.md:86,
  18-06-PLAN.md:80); the SPEC now says 3.7.0. 18-06's "no zone read" should read "does not call
  `get_all_color_zones()`" since `apply_theme()` still reads zone count and power.
- **LOW, OpenCode:** 18-08's pyproject artefact names the Phase 19 `tests/test_theme/**` line as
  required content, which is false if Phase 19 lands first; reword to "the two Phase 18 entries
  absent".

### Divergent Views

- **Overall risk:** Codex rates the phase HIGH until the SPEC/CONTEXT split is reconciled
  (MEDIUM after); OpenCode says approve with minor revisions; Antigravity rates every plan LOW.
  The difference is scope: only Codex audited the canonical SPEC and CONTEXT against the split.
- **18-07 regex:** Antigravity considers the multi-line gap mitigated by `ruff format`; Codex
  notes `ruff format` does not touch Markdown in `docs/`, so the gap is real there.
