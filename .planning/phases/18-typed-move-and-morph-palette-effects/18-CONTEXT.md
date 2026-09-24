# Phase 18: Typed Move and Morph Palette Effects - Context

**Gathered:** 2026-09-09
**Status:** Ready for planning
**Amended:** 2026-09-24 after UAT gap G-18-1 (D-14 superseded for Morph, D-23 amended, D-24 to
D-28 added)

<domain>
## Phase Boundary

A typed firmware Move builder (`MultiZoneEffect.move()`) and device method
(`MultiZoneLight.set_move_effect()`) on the multizone surface. When Move (through
`set_move_effect()`) or Morph (through `MatrixLight.set_effect()`) starts without a palette,
the library follows the LIFX app and derives colours from the device (folded in from the
former Phase 17.1 on 2026-09-23). The phase also closes its Phase 16 `PLC0415` handoff (D-12).
Files: `src/lifx/devices/multizone.py`, `src/lifx/devices/matrix.py`, the shared palette helper
in `src/lifx/devices/component_state.py`, their tests and docs, and the import hoist in
`tests/test_animation/` and `tests/test_devices/test_multizone.py`.

The default-on Thread guard with a code-level opt-in across the `Animator` factories and the
effects `Conductor` (ANIM-05), and with it `src/lifx/animation/`,
`src/lifx/effects/conductor.py` and `src/lifx/exceptions.py`, moved to Phase 20 on
2026-09-23; see `../20-animator-thread-guard/prior-plans/README.md`.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**6 requirements are locked for Phase 18**: R4 to R7, R9 and R10 (R9 and R10 added 2026-09-23 when Phase 17.1 was folded in). R1 to R3 and R8 moved to Phase 20 (ANIM-05) on 2026-09-23. See `18-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `18-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- Moved to Phase 20 (ANIM-05) on 2026-09-23: the Thread guard in the three `Animator`
  factories with the `enable_thread` keyword
- Moved to Phase 20 (ANIM-05) on 2026-09-23: Thread exclusion in the `Conductor` with
  `enable_thread` on `Conductor.__init__()`
- `MultiZoneEffect.move()` classmethod and `MultiZoneLight.set_move_effect()`
  (`src/lifx/devices/multizone.py`)
- Docstrings, `docs/api/devices.md` context if needed, `docs/migration/effect-api-changes.md`
  Move section, and the effects user guide's Move section (the Thread-default docs moved to
  Phase 20)
- The R9 palette rule in `set_move_effect()` and the R10 Morph default palette in
  `MatrixLight.set_effect()`, sharing one palette helper
- Emulator tests for every acceptance criterion, including the golden-packet equivalence
  backstop and the executed documentation example

**Out of scope (from SPEC.md):**
- The R9 palette rule on the raw `set_effect(effect)` path, or a `palette` field on the
  `MultiZoneEffect` dataclass (both would break R6)
- FLAME or SKY palette handling, and software effects under `src/lifx/effects/`
- Everything ANIM-05 covers, moved to Phase 20 on 2026-09-23: the Animator factory guard, the
  Conductor exclusion, `enable_thread`, and their own boundaries (guarding
  `Animator.__init__()`, `EffectPulse` and non-frame effects, the Conductor's silent return
  when capability filtering empties the list, and a warning, rate clamp or duty-cycle mode
  for Thread)
- Typed builders for MORPH, FLAME or SKY
- Accepting `speed` or `duration` in raw wire units on the typed API
- Deprecating the raw `parameters` path
- Any change to how `Device.connectivity` is derived
- Gating `get_wifi_info()` and `get_wifi_firmware()` on Thread, or Thread RSSI, pending
  LIFX's replacement packets
- Downstream changes in LedFx or Home Assistant

</spec_lock>

<decisions>
## Implementation Decisions

D-01 to D-08 and the Thread half of D-11 belong to ANIM-05, which moved to Phase 20 on
2026-09-23. They are tagged `[deferred]` so Phase 18's plans are not measured against them.
D-06 and D-07 (the emulator as the Thread fixture) no longer hold: Phase 20 uses synthetic
connectivity in CI and real hardware for integration evidence.

### Exception for the refusal

- **D-01 [deferred]:** A new `LifxThreadAnimationError(LifxUnsupportedCommandError)` in
  `src/lifx/exceptions.py`, exported from `lifx` and `lifx.exceptions` alongside its siblings.
  Consumers can catch the specific class, while existing handlers for
  `LifxUnsupportedCommandError` or `LifxError` (LedFx catches `LifxError` around Animator
  creation) keep working unchanged. `LifxUnsupportedDeviceError` was rejected: its contract is
  about unsupported product types raised by `Device.connect()`, and discovery filters it to
  `None`; here the device is supported and the transport is not.
  **Reversibility:** one-way once released. The class name becomes part of the published
  exception hierarchy that consumers write `except` clauses against.
- **D-02 [deferred]:** The message carries the serial, the reason and the override, in this shape:
  `Animator refuses Thread device d073d5xxxxxx: a Thread mesh cannot sustain animation frame
  traffic. Pass enable_thread=True to override.` The Conductor's all-Thread raise uses the
  same class and names every excluded serial.

### Guard placement and Conductor exclusion

- **D-03 [deferred]:** One helper in the animation package owns the rule. It takes `(device,
  enable_thread)` and either returns or raises `LifxThreadAnimationError`; a predicate form
  (or the same helper called with the exception caught) serves the Conductor's exclusion
  decision. The three factories call it after their own device queries complete, so the
  freshest observed connectivity is used. The Conductor imports it lazily inside the method
  that needs it, the same way `_create_animators()` already imports `Animator`, keeping the
  existing import direction from effects to animation.
  **Reversibility:** reversible. A private helper; the placement can move without touching
  the public surface.
- **D-04 [deferred]:** The Conductor applies exclusion in a **separate step** after
  `_filter_compatible_lights()`, only when the effect is a `FrameEffect`, in both `start()` and
  `add_lights()`, and before any prestate capture. Because it is its own step it knows exactly
  whether Thread exclusion emptied an otherwise non-empty list, which is the spec's raise
  condition; the existing capability-empty silent return with its warning stays untouched.
  `Conductor.__init__(enable_thread=False)` stores the flag and passes it to every
  `Animator.for_*()` call it makes.
- **D-05 [deferred]:** Each excluded participant is logged at **WARNING** using the existing structured
  dict style (`class`, `method`, `action: "exclude"`, `values: {serial, reason}`). The consumer
  asked for a device and lost it; that belongs in default log output, matching the existing
  warning when `start()` finds no compatible participants. No IP, MAC or hostname in the entry.

### Thread test fixture strategy

- **D-06 [deferred]:** A Thread device in tests comes from **lifx-emulator-core**, not from patching. The
  emulator gains a per-device option that sets `thread_connection` in every reply header, so
  the real receive path in `DeviceConnection` observes the bit exactly as hardware would.
  Flipping `connection._thread_connection` was rejected for the factory tests: every
  correlated reply overwrites the observed bit, so the emulator's clear-bit replies to the
  factories' own queries would undo the flag and the "first observed during construction"
  criterion could never be exercised honestly.
  **Reversibility:** costly. The fixture shape is shared by every Thread test written from
  here on; swapping it later rewrites all of them.
- **D-07 [deferred]:** The emulator change is a **blocking prerequisite**: it lands in lifx-emulator-core,
  is released, and the dev-dependency pin in `pyproject.toml` (`lifx-emulator-core>=3.1.0`
  today) is bumped to the version carrying the flag before any phase test is written. The plan
  records this as its first wave with the required version named. The local checkout is
  `/Volumes/External/Developer/Djelibeybi/lifx-emulator`.
- **D-08 [deferred]:** Conductor exclusion tests use the existing `MagicMock` `light1` / `light2` fixtures
  in `tests/test_effects/test_conductor.py`, given a `connectivity` attribute, for ordering,
  logging and the raise condition. One emulator-backed test proves an excluded Thread
  participant receives no capture, power-on, frame or restore packet from the Conductor.

### Move API internals

- **D-09:** A single private `_coerce_direction()` in `src/lifx/devices/multizone.py` accepts a
  `Direction` member or a case-insensitive member name and raises `ValueError` otherwise. It is
  used by `MultiZoneEffect.move()`, `MultiZoneLight.set_move_effect()` **and the existing
  `MultiZoneEffect.direction` setter**, which widens from enum-only to enum-or-name. One parsing
  rule for the field; the widening is backward compatible. (Clarified 2026-09-23 after cross-AI
  review round 2: backward compatible for the annotated `Direction` type. A bare `int`, which
  the old setter stored unchecked through `int(value)`, now raises `ValueError` because the one
  rule rejects it, as R4 requires of `move()`. The migration guide records this and shows
  `Direction(value)` as the fix. The decision itself is unchanged.)
- **D-10:** `MultiZoneLight.set_move_effect(direction, speed, duration=0, palette=None)` builds
  the effect first with `MultiZoneEffect.move(direction, speed, duration)` (so bad arguments
  raise before any packet is sent), then applies the D-13 palette rule, then
  `await self.set_effect(effect)`. Validation, conversion and every `set_effect()` error path
  still live in one place. (Amended 2026-09-23: originally "a thin delegate and nothing else";
  the palette step was added when Phase 17.1 was folded in.) Its docstring carries the
  runnable example the spec's R7 requires, mirroring the keyword style of
  `MatrixLight.set_effect()`.
- **D-11:** User-guide prose is added this phase, not left to docstrings alone: a short "Thread
  devices" note under "When to Use Animation" in `docs/user-guide/animation.md`, a matching
  note under "Conductor" in `docs/user-guide/effects.md`, and a "Firmware Move effect" example
  in `docs/user-guide/effects.md`. The `MultiZoneLight` class docstring and the migration
  guide's Move section are rewritten to the shipped API per the spec.

### Carried forward from Phase 16

- **D-12:** Phase 16 D-05 assigned this phase the `PLC0415` sweep of its own test files. This
  phase hoists every inline import in `tests/test_animation/**` and
  `tests/test_devices/test_multizone.py` to module scope and deletes those two lines from
  `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml`. `uv run ruff check .` must stay
  clean afterwards.

### Default palette handling (folded in from Phase 17.1, 2026-09-23)

- **D-13:** Follow the LIFX app. When Morph (via `MatrixLight.set_effect(MORPH, palette=None)`)
  or Move (via `set_move_effect(..., palette=None)`) starts with no palette, read the device's
  current colours first: `get_all_tile_colors()` for a matrix, `get_all_color_zones()` for a
  strip.
- **D-14:** If the device already shows more than one distinct colour, send no palette at all:
  Morph keeps `palette_count=0` as today, and Move leaves the zones untouched. There is no
  reduction, sampling or truncation to 16 colours.
  **[Superseded for Morph on 2026-09-24 by D-24 and D-25; still holds for Move.]** Real
  hardware disproved the Morph half (UAT gap G-18-1): a Luna does not start MORPH at all when
  `Tile.SetEffect` carries `palette_count=0`, and `get_effect()` reports OFF. Move on a real
  strip behaves as D-14 says, so the Move half is unchanged.
- **D-15:** If every pixel or zone is the same colour, generate three colours:
  - **White** (saturation == 0): the current white, plus whites at the device's minimum and
    maximum kelvin.
  - **Colour** (saturation > 0): the current colour, plus hue +45° and hue -45° (wrapping
    modulo 360), keeping the current saturation.
- **D-16:** The min/max kelvin for the white case come from `Light.min_kelvin` /
  `Light.max_kelvin` (products registry), falling back to 1500 K and 9000 K only when the range
  is unknown.
- **D-17:** "Single colour" means equal under the existing `HSBK.__eq__` (uint16 protocol
  semantics), with no perceptual tolerance.
- **D-18:** Generated colours copy the current colour's brightness; the ±45° hue variants also
  copy its kelvin. Generated whites keep the current brightness with saturation 0.
- **D-19:** For Morph, the generated palette is sent in `Tile.SetEffect`. Only MORPH changes:
  FLAME and SKY with no palette keep sending `palette_count=0`, and an explicitly supplied
  palette is always sent as given.
- **D-20:** For Move, a generated or explicit palette is painted by wrapping it in a `Theme` and
  calling `self.apply_theme(theme, duration=0)` (blended by `MultiZoneGenerator`, written by
  `set_all_color_zones()` with its extended-multizone fallback), then the Move effect is sent.
- **D-21:** The derive/paint behaviour lives only on the typed `set_move_effect()` path. The raw
  `set_effect(effect)` path is byte-for-byte unchanged (R6), and `palette` is never a
  `MultiZoneEffect` dataclass field. **Reversibility:** costly. `palette` is a new public
  parameter on a published API.
- **D-22:** One pure helper derives the palette from `list[HSBK]` plus an optional kelvin range
  and is shared by matrix and multizone. It sits next to the existing `is_dark()` /
  `hsk_matches()` helpers in `src/lifx/devices/component_state.py`, unless the planner finds a
  better-scoped module. (2026-09-24: its code and its contract, None meaning "not a single
  colour", are unchanged; Morph's multi-colour selection is a second pure helper beside it,
  per D-28.)
- **D-23:** If reading the device's colours times out, log at DEBUG and fall back to the
  "no palette" behaviour (Morph sends `palette_count=0`; Move starts without painting). This
  mirrors the SKY support probe in `MatrixLight.set_effect()`.
  **[Morph half superseded on 2026-09-24 by D-26; the Move half still holds.]** Commit
  `5a9d254` widened the catch to `LifxProtocolError` for both paths. For Morph that fallback
  sends the empty palette the firmware ignores, so it is removed; Move's fallback (log at DEBUG,
  send Move without painting) stays exactly as it is.

### Morph palette after UAT gap G-18-1 (2026-09-24)

- **D-24 (maintainer decision, 2026-09-24):** MORPH started through
  `MatrixLight.set_effect(FirmwareEffect.MORPH, palette=None)` always sends a non-empty
  palette. `palette_count=0` is never sent for MORPH again. Evidence: on a real Luna, MORPH with
  `palette_count=0` never started (`get_effect()` reported OFF), while sending the device's own
  distinct colours as the palette started it and it visibly morphed. Photons never sends an
  empty MORPH palette either (`photons_control/tile.py:106`). FLAME and SKY with no palette,
  and every explicit palette, keep their current bytes (D-19 and the plan 04 goldens).
- **D-25 (maintainer decision, 2026-09-24):** When the device shows more than one distinct
  colour, the MORPH palette is built from its own colours, with every tile's colours flattened
  in tile order. With 2 to 16 distinct colours (`MAX_PALETTE_COLORS`), all of them are sent in
  first-seen pixel order. With more than 16 (a blended `apply_theme()` on the Luna showed 35),
  16 pixels spaced evenly across the whole flattened device are sampled and then
  de-duplicated in sample order. The planner fixed "spaced evenly" as pixel index
  `i * n // 16` for `i` in 0 to 15, where `n` is the flattened pixel count. The single-colour
  rule (D-15 to D-18) is unchanged and still takes precedence for a single colour.
- **D-26 (maintainer decision, 2026-09-24):** If reading the device's colours fails when MORPH
  starts with no palette, the error propagates: `LifxTimeoutError` or `LifxProtocolError` from
  `get_all_tile_colors()` reaches the caller and no `Tile.SetEffect` is sent. There is no
  fallback, because a fallback could only send the empty palette the hardware ignores. This
  reverses the Morph half of commit `5a9d254`; the Move read-failure fallback is unchanged
  because Move without a palette works on real hardware.
- **D-27 (planner, implied by D-24 and D-26; flagged for maintainer review):** An empty colour
  result (a device reporting no tiles, or tiles with no pixels) has no colours to build a
  palette from, so `MatrixLight.set_effect()` raises `LifxProtocolError` naming the device
  before any `Tile.SetEffect` is sent, rather than sending an empty palette.
  **Reversibility:** reversible. One private method's error path.
- **D-28 (planner's structural choice, 2026-09-24):** The Morph-only multi-colour selection is
  a new pure helper, `sample_effect_palette(colors) -> list[HSBK]`, beside
  `derive_effect_palette()` in `src/lifx/devices/component_state.py`.
  `MatrixLight._derive_morph_palette()` composes them: `derive_effect_palette()` first (the
  single-colour rule), then `sample_effect_palette()` when that returns None. Rejected: a flag
  or mode argument on `derive_effect_palette()`, which would change a signature Move shares,
  add a branch Move never takes, and mix two policies in one function. With this split,
  `src/lifx/devices/multizone.py` and `tests/test_devices/test_multizone_move.py` do not
  change at all. **Reversibility:** reversible. The new helper is module-level but not
  exported from `lifx` or `lifx.devices`.

### Claude's Discretion

- Moved to Phase 20 (ANIM-05) on 2026-09-23: the guard helper's name and module, and whether
  the Conductor uses a predicate or catches the exception.
- Where the `uint32` / `uint64` bounds for the converted `speed` and `duration` live.
- Moved to Phase 20 (ANIM-05) on 2026-09-23: the test layout for Thread tests.
- Exact wording of the two user-guide notes and the migration-guide rewrite.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements
- `.planning/phases/18-typed-move-and-morph-palette-effects/18-SPEC.md`: Locked
  requirements, boundaries, 16 acceptance criteria, 15 resolved edges and 3 prohibitions for
  Phase 18 (the R1 to R3 and R8 items, 15 criteria, 10 edges and 6 prohibitions, are marked
  moved to Phase 20). MUST read before planning.

### Default palette handling
- `src/lifx/devices/matrix.py` `MatrixEffect` and `set_effect()`: Morph palette handling today
  (`palette_count=0` and 16 zeroed slots when `palette=None`), and the best-effort SKY probe
  whose timeout pattern D-23 reuses.
- `src/lifx/devices/multizone.py` `apply_theme()` and `get_all_color_zones()`: the paint and
  read paths D-20 and D-13 reuse.
- `src/lifx/devices/light.py` `min_kelvin` / `max_kelvin`: the kelvin range for D-16.
- `src/lifx/devices/component_state.py` `is_dark()` / `hsk_matches()`: the shape and home for
  the D-22 helper.
- Photons `modules/photons_control/tile.py` (local checkout): substitutes a fixed rainbow when
  no Morph palette is given. It is a contrast only; this phase follows the LIFX app instead.
- `.planning/phases/18-typed-move-and-morph-palette-effects/18-UAT.md` gap G-18-1: the
  real-hardware evidence behind D-24 to D-26 (MORPH with `palette_count=0` never starts on a
  Luna; the device's own colours as the palette do; Move behaves as designed).

### Origin of the guard
- Moved to Phase 20 (ANIM-05) on 2026-09-23: `.planning/seeds/SEED-003-lock-animation-to-wifi.md`
  and `.planning/phases/14-thread-revalidation-and-docs/14-CONTEXT.md` D-09 to D-16 (the
  THREAD-03 rescoping) are Phase 20's references now; see
  `../20-animator-thread-guard/prior-plans/README.md`.

### Origin of the typed Move API
- GitHub issue Djelibeybi/lifx-async#191: The Home Assistant core migration review that asked
  for a typed Move API; its `parameters=[0, int(direction), 0, ...]` example is the golden-packet
  baseline for R6.

### Carried-forward obligations
- `.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-CONTEXT.md`: D-05, the
  `PLC0415` per-file-ignore handoff that this phase closes for its two test paths.
- `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`: The two lines to delete. Phase 18
  bumps no dev-dependency: it runs against the locked lifx-emulator-core 3.7.0, and the
  `lifx-emulator-core>=3.1.0` pin bump left with ANIM-05 on 2026-09-23 (Phase 20 now verifies
  without the emulator).

### Prerequisite repository
- Moved to Phase 20 (ANIM-05) on 2026-09-23: the emulator's per-device `thread_connection`
  reply flag is no longer a Phase 18 prerequisite, and Phase 20 no longer waits for it either.

### Project rules
- `AGENTS.md`: Privacy rules (serial-only identifiers, synthetic addresses in tests and
  docs), measured-tree and coverage rules, Conventional Commits, `git commit -S -s`.

</canonical_refs>

<code_context>
## Existing Code Insights

The entries below about `Device.connectivity`, the connection's Thread bit,
`test_connection_connectivity.py`, the Conductor fixtures and lazy imports, the `Animator`
factories, the `Conductor` and `LifxThreadAnimationError` serve ANIM-05, which moved to Phase 20
on 2026-09-23. They are kept for Phase 20's reference and are not Phase 18 work.

### Reusable Assets
- `Device.connectivity` (`src/lifx/devices/base.py`): header-authoritative once any correlated
  response has been observed, else discovery metadata, default WiFi. The guard reads it and
  adds nothing.
- `DeviceConnection` records `header.thread_connection` from every correlated reply,
  including the ACK to a SET (`src/lifx/network/connection.py` around line 1078). This is why
  LedFx's `set_power(True)` before `for_multizone()` is enough for an observed value, and why
  patching the private bit cannot survive the factories' own queries.
- `MultiZoneEffect._validate_speed/_validate_duration/_validate_parameters`: the existing
  validation `move()` must leave unchanged for the raw path.
- `MatrixLight.set_effect(effect_type, speed: float seconds, duration, ...)`: the keyword-style
  precedent for `set_move_effect()`.
- `tests/test_network/test_connection_connectivity.py`: header-injection helpers if a
  unit-level Thread test is ever needed outside the emulator.
- `tests/test_effects/test_conductor.py`: `MagicMock` `light1` / `light2` fixtures and
  `conductor()` fixture to extend for exclusion tests.

### Established Patterns
- Structured dict logging (`class`, `method`, `action`, `values`) throughout devices and
  effects; the exclusion warning follows it.
- Lazy in-method imports from effects into animation (`conductor.py` `_create_animators`),
  which keeps the package import direction; the guard helper import follows the same route.
  Note `src/**` is still under the `PLC0415` per-file-ignore, so this is permitted there.
- Emulator tests are marked `@pytest.mark.emulator` and use session-scoped emulator fixtures in
  `tests/conftest.py`; the suite retries once on the exact network exception types only.
- 100% branch patch coverage on CI: every new `if` (guard true/false, opt-in, enum versus
  name, overflow) needs both partials exercised.

### Integration Points
- `Animator.for_light()` / `for_multizone()` / `for_matrix()` in `src/lifx/animation/animator.py`:
  guard call after the queries, before `cls(...)`; new keyword-only `enable_thread`.
- `Conductor.start()` at the point after `_filter_compatible_lights()` and before the
  `async with self._lock` capture block; `Conductor.add_lights()` at the matching point before
  its capture `gather`; `Conductor.__init__()` for the flag.
- `MultiZoneEffect` dataclass and `MultiZoneLight` in `src/lifx/devices/multizone.py`; exports
  in `src/lifx/devices/__init__.py` and `src/lifx/__init__.py` if a new public name is added.
- `src/lifx/exceptions.py` and the exception exports for `LifxThreadAnimationError`.
- `docs/api/devices.md` renders `MultiZoneEffect` and `MultiZoneLight` through mkdocstrings, so
  the new members appear automatically; `docs/api/animation.md` renders `Animator`.

</code_context>

<specifics>
## Specific Ideas

- [Moved to Phase 20, ANIM-05, 2026-09-23] The refusal message should read as a deliberate
  library boundary with the escape hatch in the same sentence, not as an "unsupported device"
  error.
- [Moved to Phase 20, ANIM-05, 2026-09-23] "Dropped means dropped": an excluded Thread
  participant gets nothing from the Conductor, not a capture, not a power-on, not a restore.
- [Moved to Phase 20, ANIM-05, 2026-09-23] The opt-in is silent by design. The flag is the
  acknowledgement; no warning nag.
- The golden-packet test should use the exact Home Assistant construction from issue #191 as
  the raw side of the comparison.

</specifics>

<deferred>
## Deferred Ideas

- Gate `get_wifi_info()` and `get_wifi_firmware()` on `Connectivity.THREAD` and add Thread
  RSSI reporting once LIFX publishes the replacement packets. Connectivity is not purely
  descriptive by design; this is its next legitimate consumer. Already recorded as out of scope
  in `18-SPEC.md`.

</deferred>

---

*Phase: 18-typed-move-and-morph-palette-effects*
*Context gathered: 2026-09-09*
