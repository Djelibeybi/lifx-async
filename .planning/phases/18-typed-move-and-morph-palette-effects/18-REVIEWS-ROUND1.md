---
phase: 18
reviewers: [codex, opencode, antigravity]
reviewed_at: 2026-09-23T04:42:08Z
plans_reviewed: [18-01-PLAN.md, 18-02-PLAN.md, 18-03-PLAN.md, 18-04-PLAN.md, 18-05-PLAN.md, 18-06-PLAN.md, 18-07-PLAN.md, 18-08-PLAN.md]
models:
  codex: "gpt-5.6-sol (reasoning=high)"
  opencode: "openrouter/z-ai/glm-5.3 (reasoning=high)"
  antigravity: "gemini-3.1-pro-high"
model_sources:
  codex: "pinned"
  opencode: "pinned"
  antigravity: "pinned"
plan_coverage:
  opencode:
    total: 8
    missing: ["18-01", "18-02", "18-03", "18-04", "18-05", "18-06", "18-07", "18-08"]
---

# Cross-AI Plan Review — Phase 18

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## Codex Review

## 18-01

### Summary

The emulator prerequisite is technically well founded and matches both repositories. The plan correctly identifies the API breaks introduced by 3.10.0 and provides a credible shared Thread fixture. Its main risk is the breadth of the fixture refactor, not the design itself.

### Strengths

- The current lock is 3.7.0, so the proposed dependency transition is real and measurable ([uv.lock:299](/Volumes/External/Developer/Djelibeybi/lifx-async/uv.lock:299)).
- Emulator 3.10.0 genuinely supports the required mechanisms: per-device connectivity is accepted by the factories, and Thread replies set the frame-address bit ([factory.py:16](/Volumes/External/Developer/Djelibeybi/lifx-emulator/packages/lifx-emulator-core/src/lifx_emulator/factories/factory.py:16), [device.py:97](/Volumes/External/Developer/Djelibeybi/lifx-emulator/packages/lifx-emulator-core/src/lifx_emulator/devices/device.py:97)).
- The port-zero and dual-stack migration directly addresses current fixture weaknesses: the existing suite pre-probes IPv4 ports and maintains a custom IPv6 server ([tests/conftest.py:302](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/conftest.py:302), [tests/conftest.py:503](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/conftest.py:503)), while 3.10.0 atomically establishes an IPv4/IPv6 pair and sets `IPV6_V6ONLY` before binding ([server.py:884](/Volumes/External/Developer/Djelibeybi/lifx-emulator/packages/lifx-emulator-core/src/lifx_emulator/server.py:884)).
- The teardown repair is necessary: the three existing fixtures call `remove_device()` synchronously, but 3.10.0 defines it as async ([tests/conftest.py:858](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/conftest.py:858), [server.py:649](/Volumes/External/Developer/Djelibeybi/lifx-emulator/packages/lifx-emulator-core/src/lifx_emulator/server.py:649)).
- The real receive path records the correlated reply bit at the correct point, so this fixture will test production behaviour rather than a surrogate ([connection.py:1075](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/network/connection.py:1075)).

### Concerns

- **MEDIUM:** The plan describes `>=3.10.0` as a pin. It is a minimum constraint; reproducibility comes from `uv.lock`, not `pyproject.toml`. A future targeted lock refresh may select a later compatible release.
- **LOW:** The V6ONLY assertion intentionally reaches into `_ipv6_transport`, a private emulator field. That is acceptable against the exact lock but should be identified as a version-coupled test seam.
- **LOW:** This plan changes shared session fixtures used by most of the suite. The full-suite gate is appropriate, but failures could be difficult to attribute if the fixture migration and new Thread fixture land in the same commit.

### Suggestions

- Describe `>=3.10.0` as the minimum and `uv.lock` as the exact resolution.
- Keep the lock/fixture migration and Thread fixture as separate signed commits, even if executed within the same plan.
- Record the private `_ipv6_transport` dependency explicitly in the summary so a future emulator upgrade knows what to replace.

### Risk Assessment

**MEDIUM.** The design is correct and source-backed, but it changes foundational test infrastructure and depends on an exact emulator API.

## 18-02

### Summary

This is a strong implementation plan. The guard placements preserve existing WiFi behaviour, catch connectivity first observed during factory queries, and avoid touching direct `Animator` construction.

### Strengths

- The proposed placement after `FrameBuffer.for_matrix()` and before `_zones_changed()` is correct: current code queries/builds at lines 228–237, mutates component tracking at line 251, and constructs only at line 253 ([animator.py:228](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/animation/animator.py:228)).
- The multizone placement after `get_zone_count()` likewise uses the freshest reply-derived connectivity ([animator.py:291](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/animation/animator.py:291), [animator.py:313](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/animation/animator.py:313)).
- Keeping `for_light()` synchronous is consistent with its current query-free path ([animator.py:323](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/animation/animator.py:323)).
- The exception hierarchy choice is compatible with current callers because `LifxUnsupportedCommandError` already derives from `LifxError` ([exceptions.py:65](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/exceptions.py:65)).
- The claim that refusal creates no socket is sound: the socket is opened lazily only by `send_frame()` ([animator.py:420](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/animation/animator.py:420)).

### Concerns

- **LOW:** The “guard sends no packet” comparison uses two fresh device objects but a shared session emulator. The count delta should be captured immediately around each call, as planned, to avoid unrelated asynchronous traffic contaminating the comparison.
- **LOW:** The repository-wide `os.environ|getenv` grep is broader than ANIM-05. An unrelated future library feature could make this phase gate fail even when the animation bypass remains call-site-only.

### Suggestions

- Restrict the hidden-bypass scan to the new guard and animation call sites, or make the broader repository policy explicit.
- In the refusal test, assert `_zones_changed()` is not called for both matrix component subclasses, not only through a generic matrix case.

### Risk Assessment

**LOW.** The plan follows the actual construction paths closely and has strong positive and negative coverage.

## 18-03

### Summary

The typed builder and golden-packet strategy are well designed. The principal gap is that the plan knowingly substitutes packet capture for one literal locked acceptance criterion without formally reconciling the specification.

### Strengths

- The builder naturally funnels through the existing dataclass validation rather than duplicating the raw construction path ([multizone.py:44](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:44), [multizone.py:49](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:49)).
- The eight-slot protocol position is confirmed by the current sender: direction is serialised from `parameters[1]` ([multizone.py:875](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:875)).
- Widening the setter through one `_coerce_direction()` rule prevents the builder and mutation paths from drifting ([multizone.py:117](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:117)).
- The golden comparison is stronger than object equality alone because it tests the actual packed `MultiZone.SetEffect` payload.

### Concerns

- **MEDIUM:** The plan explicitly cannot satisfy the specification’s literal “`get_effect()` reports direction” criterion because emulator 3.10.0 zeroes those parameters. Packet capture is a valid backstop, but it is a changed acceptance mechanism rather than the locked criterion.
- **LOW:** `_seconds_to_units()` validates finite, negative and overflow values, but non-numeric values would generally raise `TypeError` from `math.isfinite`, not the documented `ValueError`. Static typing makes this low risk, but the runtime contract should be deliberate.
- **LOW:** The setter annotation may differ from the property getter annotation. The plan says to decide only after a Pyright failure, which is less implementation-ready than the rest of the plan.

### Suggestions

- Amend the specification before execution to state that direction is verified on the received SetEffect packet until the emulator round-trips Move parameters.
- Add explicit non-numeric speed/duration tests, then either document `TypeError` or normalise them to `ValueError`.
- Decide the property annotation shape during planning rather than delegating that API decision to a possible type-checker diagnostic.

### Risk Assessment

**MEDIUM.** The code design is sound, but acceptance evidence and the locked specification are not fully aligned.

## 18-04

### Summary

The Morph palette plan is cohesive and preserves unaffected wire paths through pre-change goldens. It correctly places validation before the new device read and uses existing wire-granularity equality.

### Strengths

- `HSBK.__eq__` already compares protocol tuples, exactly matching D-17’s required granularity ([color.py:282](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/color.py:282)).
- The new derivation fits beside existing wire-aware helpers such as `is_dark()` and `hsk_matches()` ([component_state.py:110](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/component_state.py:110)).
- Constructing `MatrixEffect` before the colour read preserves existing argument validation ordering ([matrix.py:1246](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/matrix.py:1246)).
- The timeout fallback mirrors an established SKY pattern that logs and continues ([matrix.py:1222](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/matrix.py:1222)).
- The emulator does round-trip matrix effect palettes, making the proposed integration assertion meaningful ([tile_handlers.py:356](/Volumes/External/Developer/Djelibeybi/lifx-emulator/packages/lifx-emulator-core/src/lifx_emulator/handlers/tile_handlers.py:356), [tile_handlers.py:453](/Volumes/External/Developer/Djelibeybi/lifx-emulator/packages/lifx-emulator-core/src/lifx_emulator/handlers/tile_handlers.py:453)).

### Concerns

- **MEDIUM:** Assigning `effect.palette` after `MatrixEffect` construction bypasses its palette validator. The generated palette is currently fixed at three valid `HSBK` objects, so this is safe, but the invariant is implicit.
- **LOW:** The goldens are manually captured constants. Their evidentiary value depends on the summary recording the pre-change green run exactly as required.
- **LOW:** The new read adds one request sequence before every palette-less Morph start. This is intended, but it should be called out as an API latency change.

### Suggestions

- Validate the derived palette through `validate_effect_palette()` or construct a second validated `MatrixEffect`; either makes the invariant explicit.
- Record the five pre-change payloads and the exact capture commit in the summary.
- Add a test asserting that an empty device colour result falls back to `palette_count=0`.

### Risk Assessment

**MEDIUM.** Behaviour is well specified and well tested, with manageable network and validation risks.

## 18-05

### Summary

The intended Conductor exclusion and ordering are good, but the plan does not fully achieve its own “dropped means dropped” and locked no-packet claims. It explicitly masks the problematic path by pre-opening the emulator devices.

### Strengths

- Exclusion after capability filtering and before the lock would prevent capture, Animator creation, registration and restoration for devices already identified as Thread ([conductor.py:140](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/effects/conductor.py:140), [conductor.py:160](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/effects/conductor.py:160)).
- Rebinding the filtered list preserves ordering through capture, Animator construction and registry insertion ([conductor.py:168](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/effects/conductor.py:168), [conductor.py:228](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/effects/conductor.py:228)).
- Passing `enable_thread` through all three factories closes the library-owned bypass ([conductor.py:680](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/effects/conductor.py:680)).
- The structured warning avoids IP and hostname disclosure.

### Concerns

- **HIGH:** `_filter_compatible_lights()` calls each effect’s compatibility method before the proposed exclusion ([conductor.py:629](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/effects/conductor.py:629)). Most frame effects query capabilities when unknown; for example, Flame calls `ensure_capabilities()` ([flame.py:188](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/effects/flame.py:188)). Therefore a fresh Thread participant can receive packets before exclusion.
- **HIGH:** A bare `Light` defaults to WiFi until it receives evidence ([base.py:653](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/base.py:653)). As the plan itself notes, such a device can pass exclusion, have its prestate captured, and only then be refused by the Animator factory. That directly conflicts with “exclusion before any prestate capture”.
- **HIGH:** The emulator tracer opens both devices before measuring packet counts ([18-05-PLAN.md:196](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-05-PLAN.md:196)), so it does not exercise either failure mode above.

### Suggestions

- Add a two-pass design:
  1. exclude devices already evidenced as Thread before compatibility checks;
  2. run compatibility checks on survivors;
  3. exclude again after queries, before capture.
- Add tests for a metadata-known Thread device with unloaded capabilities and a fresh reply-first-observed Thread device.
- Reconcile the strict “no packet” prohibition: zero packets is achievable for metadata/previously evidenced Thread devices, but not for a genuinely unknown direct-constructor device without changing connectivity discovery semantics.
- Do not execute this plan until the specification states the intended unknown-connectivity behaviour.

### Risk Assessment

**HIGH.** The normal known-Thread path is covered, but the proposed test setup hides a real ordering gap and one path violates the locked capture boundary.

## 18-06

### Summary

The typed device method and raw-path isolation are strong. However, the plan knowingly weakens two locked palette acceptance statements because `apply_theme()` shuffles and blends colours.

### Strengths

- Building `MultiZoneEffect.move()` first ensures invalid typed arguments fail before any device I/O.
- Keeping palette derivation exclusively in `set_move_effect()` preserves the raw path, whose current sender emits only the SetEffect request ([multizone.py:834](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:834)).
- Timeout fallback and explicit-palette validation are well separated.
- The packet-order assertion proves painting completes before Move is started.

### Concerns

- **HIGH:** `apply_theme()` does not paint a palette “as given”. It passes the theme to `MultiZoneGenerator` ([multizone.py:1168](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/multizone.py:1168)), which calls `theme.shuffled()` ([generators.py:100](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/generators.py:100)); `Theme.shuffled()` invokes `random.shuffle()` ([theme.py:157](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/theme.py:157)).
- **HIGH:** The generator recursively creates blended intermediate colours ([generators.py:51](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/generators.py:51)). An 80-zone strip therefore will not end with “three distinct colours”. The plan acknowledges this and changes the test to accept any permutation and merely “more than one” colour ([18-06-PLAN.md:69](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-06-PLAN.md:69)).
- **MEDIUM:** The StateUnhandled integration case may fail during the preliminary zone read rather than the final `set_effect()`. That proves propagation from `set_move_effect()`, but not the stated “every error `set_effect()` raises” delegation path.

### Suggestions

- Resolve the specification conflict before execution:
  - either redefine R9 as “apply through the existing shuffled/blended theme mechanism”; or
  - paint a deterministic repeated palette directly with `set_all_color_zones()` so order and exact colours are preserved.
- Do not silently replace “exactly three distinct colours” with “more than one”; update the locked acceptance criterion if blending is the chosen behaviour.
- Make the StateUnhandled test pass an explicit valid palette and arrange successful painting so the failure is demonstrably from SetEffect.

### Risk Assessment

**HIGH.** The implementation can work, but the proposed tests intentionally validate weaker behaviour than the locked requirement.

## 18-07

### Summary

The documentation plan is broad, well targeted and correctly finds several currently invalid examples. It should remain blocked until the Conductor and Move palette semantics are resolved, otherwise it may publish claims the implementation does not consistently meet.

### Strengths

- The stale API examples are real: current docs call a nonexistent keyword-form multizone `set_effect()` and an invalid OFF form ([docs/api/devices.md:646](/Volumes/External/Developer/Djelibeybi/lifx-async/docs/api/devices.md:646)).
- The migration guide contains multiple obsolete Move examples and an incorrect replacement recommendation ([effect-api-changes.md:40](/Volumes/External/Developer/Djelibeybi/lifx-async/docs/migration/effect-api-changes.md:40), [effect-api-changes.md:227](/Volumes/External/Developer/Djelibeybi/lifx-async/docs/migration/effect-api-changes.md:227)).
- Executing every fenced example in the new Move section is a strong anti-drift mechanism.
- Updating the exception tree is necessary because it currently ends at `LifxUnsupportedCommandError` ([docs/api/exceptions.md:6](/Volumes/External/Developer/Djelibeybi/lifx-async/docs/api/exceptions.md:6)).
- The strict docs build, llms.txt validation and phase-wide patch coverage are appropriate final gates.

### Concerns

- **MEDIUM:** Documentation of “excluded before capture” and explicit palette behaviour depends on unresolved HIGH findings in 18-05 and 18-06.
- **LOW:** The stale-call scan targets Move specifically. It would not itself catch the currently invalid multizone `set_effect(effect_type=FirmwareEffect.OFF)` form at `docs/api/devices.md:660`, although the task separately instructs its replacement.
- **LOW:** The connectivity prose must distinguish guarded factories from direct `Animator(...)`, because direct construction remains intentionally unguarded.

### Suggestions

- Add `18-04` only through the existing transitive dependency on 18-06; the current ordering is otherwise sound.
- Expand the stale scan to cover both MOVE and OFF keyword calls on `MultiZoneLight.set_effect()`.
- Finalise the exact palette wording only after R9 is reconciled.
- State explicitly that direct `Animator(...)` is an advanced escape hatch and does not inspect connectivity.

### Risk Assessment

**MEDIUM.** The documentation mechanics are excellent, but upstream behavioural ambiguity could make the published prose inaccurate.

## 18-08

### Summary

The lint sweep is appropriately isolated and its positive PLC0415 probes are strong. The node-ID preservation gate is currently non-executable as written under the repository’s resolved Pytest version.

### Strengths

- The measured scope is accurate: current Ruff reports 18 PLC0415 sites in `test_animator.py` and two in `test_multizone.py`; examples are visible at [test_animator.py:157](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/test_animation/test_animator.py:157) and [test_multizone.py:832](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/test_devices/test_multizone.py:832).
- The two corresponding ignores exist exactly where the plan expects ([pyproject.toml:90](/Volumes/External/Developer/Djelibeybi/lifx-async/pyproject.toml:90)).
- The stdin positive-control probe is a good defence against a vacuous Ruff gate.
- Running this after plans 02, 03 and 06 preserves their “existing tests unmodified” evidence.

### Concerns

- **HIGH:** The baseline command uses `pytest --collect-only -q | grep "::"` ([18-08-PLAN.md:132](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-08-PLAN.md:132)). With the currently resolved Pytest 9.1.1, `-q` renders a collection tree without node IDs, so the command produces zero lines. I verified this in the current checkout. `-qq` emits the expected node IDs.
- **HIGH:** Task 1 therefore fails its own `test -s` and `>200` gate before any sweep begins. The same broken command is repeated for the after-state comparison ([18-08-PLAN.md:206](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/18-typed-move-and-morph-palette-effects/18-08-PLAN.md:206)).
- **LOW:** The project permits any Pytest version from 8.4.2 upward ([pyproject.toml:48](/Volumes/External/Developer/Djelibeybi/lifx-async/pyproject.toml:48)), so collection-output assumptions need to be tested against the locked environment rather than an older CLI format.

### Suggestions

- Replace both collection commands with `pytest --collect-only -qq ...`.
- Add `set -o pipefail` or capture and assert the Pytest exit status separately.
- Require exact equality of before and after node-ID sets; no new tests should be created by an import-only sweep.

### Risk Assessment

**HIGH as written, LOW after correction.** The implementation work is mechanical, but the mandatory evidence gate currently fails immediately.

## Cross-plan assessment

The wave structure is good:

- 18-01 establishes honest emulator evidence.
- 18-02, 18-03 and 18-04 are genuinely file-disjoint.
- 18-05 and 18-06 integrate the primitives.
- 18-07 and 18-08 close documentation and lint obligations.

Before execution, three blockers should be resolved:

1. Fix 18-08’s Pytest node-ID command.
2. Reconcile 18-05’s unknown/first-observed Thread behaviour with the no-packet and pre-capture requirements.
3. Reconcile 18-06’s shuffled/blended `apply_theme()` behaviour with R9’s “as given” and “three distinct colours” wording.

The 18-03 emulator limitation should also be reflected formally in the acceptance criterion rather than only in plan prose.

## Overall Risk Assessment

**HIGH until replanned.** Most implementation mechanisms are strong, but two plans currently weaken locked behavioural criteria and one plan’s mandatory verification command is demonstrably broken. Once those three issues are resolved, the phase should fall to **MEDIUM** overall, driven mainly by the shared emulator-fixture migration and added device reads.

No files were changed during this review.


---

## OpenCode Review

> **Dropped lane.** OpenCode stopped after its opening sentence. Its first file read targeted the
> sibling `lifx-emulator` checkout, which its permission layer auto-rejected
> (`permission requested: external_directory (.../lifx-emulator/*); auto-rejecting`). It produced
> no plan sections and carries no weight in the consensus below.

> [reviewed-without-source-citations] This reviewer declared source-grounded evidence but cited no file:line source evidence, so it reviewed the pasted plan text only — down-weight its verdict in the Consensus Summary.

I'll verify the plans against the actual repository source before reviewing. Let me examine the key files.

---

## Antigravity Review

# Phase 18: Animator Connectivity Guard and Typed Move Effect - Plan Review

## 18-01
**Summary:**
Plan 18-01 properly pins `lifx-emulator-core` to the needed version `3.10.0` inside `pyproject.toml` and modifies emulator fixture setup (like `thread_emulator`) to mirror proper IPv6 Thread isolation behavior. It correctly avoids modifying internal connection state directly, leaning on the real response bit instead.

**Strengths:**
- Relies on actual emulator headers (`device.connection.thread_connection`) to trigger the Thread state instead of artificial patching, preserving fidelity (verified via `src/lifx/devices/base.py:2617-2641`).
- Appropriately updates `remove_emulated_device` async handling, resolving dangling pending tasks from the older synchronous teardowns (e.g., `ceiling_device` at `tests/conftest.py:825` and `switch_device` at `tests/conftest.py:863`).

**Concerns:**
- None. (Severity: LOW)

**Suggestions:**
- Ensure any future teardown tests created alongside this plan rigorously use the new async-capable `remove_emulated_device`.

**Risk Assessment:** LOW. Standard dependency bump paired with test environment corrections; well-isolated from production code.

## 18-02
**Summary:**
Plan 18-02 introduces the `LifxThreadAnimationError` exception, the `is_thread_refused` guard helper, and integrates them into `Animator`'s factories (`for_matrix`, `for_multizone`, `for_light`) via an explicit `enable_thread` keyword-only argument. It sets up strict exception throwing if Thread is encountered without opt-in.

**Strengths:**
- `LifxThreadAnimationError` intelligently subclasses `LifxUnsupportedCommandError` (which is defined at `src/lifx/exceptions.py:65`), maintaining backward compatibility with existing library consumers (like LedFx) handling `LifxUnsupportedCommandError` or `LifxError`.
- Evaluates the Thread guard *after* factory queries (e.g., placing the check after `FrameBuffer.for_matrix(device)` inside `src/lifx/animation/animator.py:202-212`), ensuring that the guard captures freshly-observed Thread statuses without needing a pre-established connection state.

**Concerns:**
- The guard silently allows empty-effect streams or default behavior if `enable_thread` is `True`, but relies on `refuse_thread_device` doing exact serial string logging. Any formatting error would break the rigid parsing tests. (Severity: LOW)

**Suggestions:**
- Add a specific test case verifying that `for_light` does not make internal network calls unnecessarily when checking Thread connectivity since it's explicitly documented to remain a synchronous factory check.

**Risk Assessment:** LOW. The logic is self-contained and fails safely by refusing Thread meshes from being flooded.

## 18-03
**Summary:**
Plan 18-03 establishes a typed `move()` builder method on `MultiZoneEffect` to allow consumers to construct the 8-slot firmware MOVE effect programmatically rather than manually encoding the raw integers.

**Strengths:**
- Directly aligns with Home Assistant feedback (Issue #191) to abstract away the opaque 8-slot array requirement by introducing a clean classmethod on `MultiZoneEffect` (`src/lifx/devices/multizone.py:34`).
- Centralizes parameter validation for `speed` and `duration` integer conversions within the `MultiZoneEffect` dataclass rather than scattering it across the library.

**Concerns:**
- Coercing strings (`"forward"`, `"reversed"`) via case-insensitive matching in `_coerce_direction` could lead to downstream confusion if not documented strictly, though it widens compatibility safely. (Severity: LOW)

**Suggestions:**
- Ensure the error messages thrown by the internal `_coerce_direction` method explicitly enumerate the accepted enum/string names to aid debugging for library consumers.

**Risk Assessment:** LOW. Additive API enhancement with backwards compatibility preserved for raw `parameters`.

## 18-04
**Summary:**
Plan 18-04 introduces the `derive_effect_palette()` shared helper in `src/lifx/devices/component_state.py` and implements default palette generation for `MatrixLight.set_effect(MORPH)` to mirror the LIFX app's behavior of animating colors already on the device if no palette is provided.

**Strengths:**
- Consolidates color-derivation logic effectively under `src/lifx/devices/component_state.py` alongside other pure state-derivation utilities like `is_dark()`.
- Uses product-specific kelvin constraints safely, falling back to absolute boundaries (1500K-9000K) to avoid unbounded kelvin errors when generating white palettes.

**Concerns:**
- The kelvin boundaries could result in jarring effects if a device reports an unexpectedly small min/max kelvin delta; the plan doesn't mention clamping the +45/-45 degree hue wrapping logic against visual perceptual thresholds. (Severity: LOW)

**Suggestions:**
- When querying `get_all_tile_colors()`, strictly limit the timeout duration (as in the D-23 requirement) to avoid halting the morph animation kickoff due to a single dropped packet.

**Risk Assessment:** LOW. Mostly cosmetic enhancement aligned strictly with application expectations.

## 18-05
**Summary:**
Plan 18-05 bridges the Thread connectivity guard from Plan 18-02 into the high-level `Conductor` orchestrator. It ensures the `Conductor` skips Thread-connected lights *before* attempting expensive state captures during `start()` and `add_lights()`.

**Strengths:**
- Intercepts and excludes Thread devices before the `async with self._lock` prestate capture block (found in `src/lifx/effects/conductor.py:114` for `start()` and `:329` for `add_lights()`), saving unnecessary state-query packets over Thread.
- Logs excluded participants neatly using the existing structured warning pattern without failing the entire group unless the group becomes entirely empty.

**Concerns:**
- State synchronization: If a device drops off WiFi and connects via Thread right as `add_lights()` executes, the cached `connectivity` might briefly mislead the guard until the next request naturally updates it. (Severity: LOW)

**Suggestions:**
- Ensure that `Conductor.remove_lights()` does not inadvertently stumble if asked to remove a Thread light that was silently skipped by `add_lights()` earlier (it should silently ignore/clean it up).

**Risk Assessment:** MEDIUM. `Conductor` is a complex orchestrator; modifying its participant lists dynamically requires ensuring that index-based alignments in the background tasks do not break.

## 18-06
**Summary:**
Plan 18-06 unites the `MultiZoneEffect.move()` builder and the `derive_effect_palette()` helper into the singular `MultiZoneLight.set_move_effect()` caller-facing method, enabling one-call Move animation configurations.

**Strengths:**
- Isolates the `derive/paint` behavior specifically to the new typed `set_move_effect()` path, leaving the raw `set_effect(effect)` (e.g., `src/lifx/devices/matrix.py:1176`) byte-for-byte untouched (as explicitly prohibited by D-21).
- Safely wraps the generated palette inside an `apply_theme` call blended by the existing `MultiZoneGenerator`, reusing robust drawing infrastructure rather than reinventing multi-zone color blending.

**Concerns:**
- Generating a palette and immediately applying it via `apply_theme` introduces a burst of color SET packets right before the Move effect starts, which could cause visible stuttering on lossy networks. (Severity: MEDIUM)

**Suggestions:**
- Ensure the `apply_theme(theme, duration=0)` call utilizes an `ack_required=False` or similar pipelining approach if possible, to minimize the delay before the MOVE command actually hits the wire.

**Risk Assessment:** MEDIUM. Orchestrating sequential UDP operations (paint then effect) can encounter partial failures if the device misses the second packet.

## 18-07
**Summary:**
Plan 18-07 updates user-facing documentation in `docs/user-guide/effects.md`, `animation.md`, `migration/effect-api-changes.md`, and the API references to properly detail the Thread animation refusal and the new `Move` API.

**Strengths:**
- Completely documents the Thread fallback explicitly in the migration guide, reducing support friction for LedFx and Home Assistant maintainers who might otherwise be confused by sudden `LifxThreadAnimationError` exceptions.

**Concerns:**
- None. (Severity: LOW)

**Suggestions:**
- Provide a literal code snippet in `docs/user-guide/effects.md` showing how to explicitly catch `LifxThreadAnimationError` and gracefully degrade to standard non-frame effects.

**Risk Assessment:** LOW. Documentation-only changes.

## 18-08
**Summary:**
Plan 18-08 performs the final stylistic cleanup, hoisting all function-local imports in `tests/test_animation/**` and `tests/test_devices/test_multizone.py` to the module level and resolving the associated `PLC0415` Ruff exceptions in `pyproject.toml`.

**Strengths:**
- Defers this cleanup to the final wave, ensuring that the critical byte-identical untouched suite proofs in Plan 18-02 can be mathematically verified before the files are refactored.
- Modifies `pyproject.toml` accurately, removing only the specific exception lines (`"tests/test_animation/**" = ["PLC0415"]` and `"tests/test_devices/test_multizone.py" = ["PLC0415"]` around `pyproject.toml:100-102`) without stomping on Phase 19's concurrent work.

**Concerns:**
- The removal of inline imports could introduce circular dependencies across fixtures, particularly around complex `Animator` testing mocks. (Severity: LOW)

**Suggestions:**
- Double-check that `uv run --frozen pytest` execution order doesn't break due to module-level import circularities in the tests before pushing the final wave.

**Risk Assessment:** LOW. Mechanized linting refactor guarded tightly by the existing robust test suite.

## Overall Risk Assessment
The overall risk level for Phase 18 is **LOW**. The plans comprehensively cover edge cases related to Thread mesh limitations by instituting a fail-safe default, while carefully maintaining backward compatibility for power users via the `enable_thread` override. The staged execution waves ensure that the base emulator capabilities exist before building the guard, and the guard exists before exposing it via the orchestrators. The isolation of the generated-palette logic from the raw `set_effect` paths ensures no existing integrations are broken.

---

## Consensus Summary

Two lanes produced reviews: Codex, which was source-grounded and cited `file:line` evidence across
both the lifx-async and lifx-emulator checkouts, and Antigravity, which cited some files but was
mostly restating the plans. OpenCode dropped out. So the "agreed" lists below cover only what both
working lanes said, and Codex's grounded findings count for more wherever the two disagree.
Codex's 18-08 blocker has been independently re-verified: under the locked pytest,
`--collect-only -q` prints 0 `::` lines for `tests/test_devices/test_multizone.py`, while `-qq` prints 63.

### Agreed Strengths

- Wave ordering is sound: 18-01's emulator prerequisite comes first, 18-02/03/04 are file-disjoint,
  18-05/06 integrate them, and 18-07/08 close out the docs and lint work.
- 18-02's guard placement after the factory queries (`FrameBuffer.for_matrix()`,
  `get_zone_count()`) catches connectivity first seen in those replies, and making
  `LifxThreadAnimationError` a subclass of `LifxUnsupportedCommandError` keeps existing `except`
  clauses working.
- 18-06 keeps palette derivation out of the raw `set_effect()` path, so its wire bytes stay
  unchanged.
- 18-08 is scheduled after the plans whose evidence depends on the "existing tests unmodified" checks.

### Agreed Concerns

- **18-05 Conductor exclusion (Codex HIGH, Antigravity MEDIUM):** a Thread participant can see
  traffic before exclusion. Codex's grounded reasons: `_filter_compatible_lights()` runs
  compatibility checks, which call `ensure_capabilities()`, before the Thread filter; a bare
  `Light` defaults to WiFi until a reply proves otherwise, so it can be prestate-captured before
  the factory refuses it; and the test pre-opens both emulator devices, which hides both paths.
  Antigravity raised the same stale-connectivity race at LOW.
- **18-06 Move palette painting (Codex HIGH, Antigravity MEDIUM):** `apply_theme()` does not paint
  the palette "as given". `MultiZoneGenerator` calls `theme.shuffled()`, which uses
  `random.shuffle()`, and then blends intermediate colours. The plan quietly relaxes the locked
  "exactly three distinct colours" criterion to "more than one". Antigravity flagged the
  paint-then-effect burst as a separate MEDIUM risk.

### Codex-only blockers (grounded, weighted)

- **18-08 (HIGH, verified):** the node-ID baseline uses `--collect-only -q`, which prints no node
  IDs under pytest 9.1.1. Task 1 fails its own `test -s` / `>200` gate. Switch to `-qq`, add
  `pipefail`, and require the before and after sets to be exactly equal.
- **18-03 (MEDIUM):** the locked criterion that `get_effect()` reports the direction can't be met
  on emulator 3.10.0, and packet capture has been swapped in without amending the SPEC. Separately,
  non-numeric speed or duration raises `TypeError` rather than `ValueError`.
- **18-04 (MEDIUM):** assigning `effect.palette` after construction bypasses
  `validate_effect_palette()`.
- **18-01 (MEDIUM):** `>=3.10.0` is a minimum constraint, not a pin (the lock is what pins it), and
  the V6ONLY check reads the private `_ipv6_transport`.
- **18-06 (MEDIUM):** the StateUnhandled integration case may fail during the preliminary zone
  read rather than during `set_effect()`.

### Divergent Views

- **Overall risk:** Antigravity says LOW. Codex says HIGH until three items are fixed (the 18-08
  command, the 18-05 unknown-connectivity semantics and the 18-06 R9 wording), then MEDIUM.
  Antigravity didn't check the Conductor filter order, the `apply_theme()` shuffle or the pytest
  output, so Codex's verdict should stand.
- **18-06 remedy:** Antigravity suggests pipelining the paint with `ack_required=False`. Codex
  would either redefine R9 around the shuffled/blended mechanism or paint a deterministic palette
  with `set_all_color_zones()`. This needs a user decision before replanning.
- **18-05 remedy:** Codex proposes excluding twice (on known Thread evidence before the
  compatibility check, then again after the queries and before capture), and says the SPEC must
  first state what happens to a device whose connectivity is still unknown.

## Maintainer Adjudication

Recorded 2026-09-23, after the review. These rulings override the findings above wherever the two
conflict. The replanning pass must not redesign either rejected area.

### 18-05: Codex HIGHs rejected

- **Capability probe before exclusion:** accepted by design. The SPEC's MUST NOT list
  (`18-SPEC.md:293`) forbids only capture, power-on, frame and restore packets to an excluded
  participant. The capability query is recorded as accepted threat T-18-17
  (`18-05-PLAN.md:319`).
- **Unknown-connectivity device reaching capture:** not a real path. Thread devices don't answer
  broadcasts, and every construction path records connectivity before the Conductor sees the
  device: discovery metadata, `connect()`, `from_ip()`, or the Thread bit on the first correlated
  reply, which is the capability query itself. R1's Target (`18-SPEC.md:71-74`) already says
  this. A directly constructed object that has never exchanged a packet is out of scope.
- **Emulator test pre-opening devices:** this records the Thread bit the same way the real path
  does, so it hides nothing. No two-pass exclusion and no SPEC change are needed.

### 18-06: Codex HIGHs rejected

- Painting through `apply_theme()` was always meant to shuffle and blend. R9's Target says so
  (`18-SPEC.md:184`). The SPEC's acceptance text used to say "three distinct colours" and "painted
  as given", which contradicted the Target. It has been amended to say that the three R10 colours
  (or an explicit palette) are passed to `apply_theme()` at `duration=0` and that the zones hold
  `MultiZoneGenerator`'s shuffled blend. The plan's test strategy already matches this.
- Antigravity's `ack_required=False` pipelining suggestion is out of scope.

### Items the replanning pass should act on

1. **18-08 (blocker, verified):** replace `--collect-only -q` with `--collect-only -qq` in both
   the baseline and the after-state commands, add `set -o pipefail`, and require the before and
   after node-ID sets to be exactly equal.
2. **18-03 (MEDIUM):** amend the acceptance criterion so that direction is verified on the
   captured `MultiZone.SetEffect` packet while emulator 3.10.0 zeroes Move parameters. Decide
   whether a non-numeric speed or duration raises `TypeError` or `ValueError`, and test it.
3. **18-04 (MEDIUM):** validate the derived palette through `validate_effect_palette()` rather
   than assigning `effect.palette` after construction.
4. **18-01 (MEDIUM):** describe `>=3.10.0` as a minimum, with `uv.lock` as the exact resolution,
   and record the private `_ipv6_transport` dependency.
5. **18-06 (MEDIUM):** make the StateUnhandled integration case pass an explicit palette, so
   that the failure demonstrably comes from `set_effect()` rather than from the zone read.
