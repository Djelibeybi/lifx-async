# Phase 18: Typed Move and Morph Palette Effects Specification

**Created:** 2026-09-09
**Ambiguity score:** 0.11 (gate: ≤ 0.20)
**Requirements:** 6 locked for Phase 18: R4 to R7, R9 and R10 (R9 and R10 folded in from the
former Phase 17.1 on 2026-09-23). R1 to R3 and R8 (ANIM-05, the Animator Thread guard) moved
to Phase 20 on 2026-09-23; their numbers are kept so references stay stable. What moved is
listed in `../20-animator-thread-guard/prior-plans/README.md`. The full pre-split text was last
carried by this file at commit 976b22a; after any rebase, `git log -p` on this file finds the
last version before the "moved to Phase 20" stubs.

## Goal

A caller starts the firmware Move effect with `MultiZoneEffect.move(direction, speed, duration)`
or `MultiZoneLight.set_move_effect(direction, speed, duration)` instead of an eight-slot
`parameters` list. When a caller starts Move through `set_move_effect()` or Morph through
`MatrixLight.set_effect()` without a palette, the library behaves as the LIFX app does: it
animates the colours already on the device and synthesises a small palette only when the
device shows a single colour. (The Animator and Conductor Thread guard this goal also named
moved to Phase 20 with ANIM-05 on 2026-09-23.)

## Background

**ANIM-05.** Moved to Phase 20 (ANIM-05) on 2026-09-23; see
`../20-animator-thread-guard/prior-plans/README.md`. The background on `Device.connectivity`,
the `Animator` factories, the effects `Conductor`, LedFx and SEED-003 moved with it.

**EFFECT-01.** `MultiZoneLight.set_effect()` (`src/lifx/devices/multizone.py`) accepts only a
`MultiZoneEffect`, whose `speed` is an integer in milliseconds, whose `duration` is passed raw to
the wire (`MultiZoneEffectSettings.duration`, nanoseconds, 0 for indefinite), and whose direction
lives in `parameters[1]`. The dataclass exposes a `direction` property that rewrites the whole
list. Home Assistant hand-encodes `parameters=[0, int(direction), 0, 0, 0, 0, 0, 0]` exactly as
issue #191 describes. `MatrixLight.set_effect()` is the typed precedent: keyword arguments with
`speed` in float seconds. Two published examples already describe a typed Move API that does not
exist: the `MultiZoneLight` class docstring shows
`set_move_effect(speed=5.0, direction="forward")` and `docs/migration/effect-api-changes.md`
shows `set_effect(effect_type=FirmwareEffect.MOVE, speed=5.0, direction=Direction.FORWARD)`.

## Requirements

1. **R1 Factories refuse Thread by default**: Moved to Phase 20 (ANIM-05) on 2026-09-23; see
   `../20-animator-thread-guard/prior-plans/README.md`.

2. **R2 WiFi behaviour unchanged**: Moved to Phase 20 (ANIM-05) on 2026-09-23; see
   `../20-animator-thread-guard/prior-plans/README.md`.

3. **R3 Conductor excludes Thread participants before capture**: Moved to Phase 20 (ANIM-05)
   on 2026-09-23; see `../20-animator-thread-guard/prior-plans/README.md`.

4. **R4 Typed Move builder**: `MultiZoneEffect.move(direction, speed, duration=0)` is a
   classmethod that returns a MOVE `MultiZoneEffect` with the eight-slot `parameters` list
   encoded internally.
   - Current: a caller writes `parameters=[0, int(direction), 0, 0, 0, 0, 0, 0]` by hand
   - Target: `direction` accepts a `Direction` member or its case-insensitive name
     (`"forward"`, `"reversed"`); any other value raises `ValueError`. `speed` is a float
     number of seconds converted to integer milliseconds with `round()`; `duration` is a float
     number of seconds converted to integer nanoseconds with `round()`, and `0` means the
     effect runs indefinitely. `0` is accepted for both; a negative value, or a converted value
     outside `uint32` (speed) or `uint64` (duration), raises `ValueError`
   - Acceptance: `MultiZoneEffect.move(Direction.REVERSED, 5.0)` equals
     `MultiZoneEffect(FirmwareEffect.MOVE, 5000, 0, [0, 0, 0, 0, 0, 0, 0, 0])`;
     `move("Forward", 0.0)` yields `parameters[1] == 1` and `speed == 0`;
     `move("sideways", 1.0)`, `move(Direction.FORWARD, -1.0)` and
     `move(Direction.FORWARD, 1.0, duration=2**64 / 1e9 + 1)` raise `ValueError`;
     `move(Direction.FORWARD, 0.0015).speed == 2`

5. **R5 Typed device method**: `MultiZoneLight.set_move_effect(direction, speed, duration=0,
   palette=None)` starts the firmware Move effect in one call.
   - Current: the name appears in the class docstring but no such method exists
   - Target: builds the effect through `MultiZoneEffect.move()` and sends it through
     `set_effect()`, so argument units, validation and every error `set_effect()` raises
     (`LifxUnsupportedCommandError`, `LifxTimeoutError`, `LifxDeviceNotFoundError`) are
     identical to the builder-plus-`set_effect()` path. Before sending, it applies the R9
     palette rule; `palette` is keyword-usable and defaults to `None`
   - Acceptance: against an emulator multizone device, `set_move_effect(Direction.FORWARD,
     5.0)` results in `get_effect()` reporting `FirmwareEffect.MOVE` and `speed == 5000`, and
     the `MultiZone.SetEffect` the device received carries `Direction.FORWARD` (emulator 3.7.0
     reports every Move parameter as 0 through `get_effect()`, so direction is read from the
     received packet until the emulator round-trips it); a device that answers
     `StateUnhandled` raises `LifxUnsupportedCommandError` through `set_move_effect()`

6. **R6 Raw construction path preserved**: `MultiZoneEffect(effect_type, speed, duration,
   parameters)` and `MultiZoneLight.set_effect(effect)` keep working unchanged.
   - Current: this is the only construction path; Home Assistant uses it
   - Target: the dataclass fields, `__post_init__` validation (eight uint32 slots, non-negative
     speed and duration) and the `direction` getter are unchanged; no deprecation warning or
     log message is added to the raw path. The `direction` setter follows CONTEXT D-09: it
     parses its value with the same rule as `move()` (a `Direction` member or a
     case-insensitive name), so a bare integer, which it used to store unchecked, now raises
     `ValueError`; the migration guide records this (amended 2026-09-23 after cross-AI review
     round 2)
   - Acceptance: the existing `MultiZoneEffect` tests in `tests/test_devices/test_multizone.py`
     pass with their assertions, fixtures and node IDs unchanged. The only permitted edit to
     that file is the import-only `PLC0415` hoist that CONTEXT D-12 assigns to this phase,
     proven by a diff gate that rejects any change outside an import statement (amended
     2026-09-23 after cross-AI review round 2; the file was previously required to stay
     unmodified). A golden-packet test shows the hand-encoded Home Assistant construction
     and `MultiZoneEffect.move()` produce byte-identical `MultiZone.SetEffect` payloads;
     `warnings.catch_warnings(record=True)` around the raw path records nothing

7. **R7 Documentation**: the typed Move API is in the published API reference with an example
   that runs, and the two stale examples are corrected.
   - Current: `docs/api/devices.md` renders `MultiZoneEffect` and `MultiZoneLight` through
     mkdocstrings, so new members appear automatically but carry no example; the class
     docstring and the migration guide show APIs that do not exist
   - Target: the `set_move_effect()` and `MultiZoneEffect.move()` docstrings carry a runnable
     example; the `MultiZoneLight` class docstring example and the migration guide's Move
     section are rewritten to the shipped typed API. (The clause requiring the `Animator`
     factory and `Conductor` docstrings to describe the Thread default and `enable_thread`
     moved to Phase 20 with ANIM-05 on 2026-09-23.)
   - Acceptance: `uv run zensical build` succeeds; grepping `src/lifx` and `docs/` finds no
     `set_move_effect(speed=` and no `set_effect(effect_type=FirmwareEffect.MOVE`; the
     documented Move example is exercised verbatim by an emulator test

8. **R8 Thread opt-in**: Moved to Phase 20 (ANIM-05) on 2026-09-23; see
   `../20-animator-thread-guard/prior-plans/README.md`.

9. **R9 Move palette on the typed path**: `set_move_effect()` gives Move visible colours the
   way the LIFX app does. Move carries no palette on the wire; it rotates the zone colours
   already shown.
   - Current: a single-colour strip shows no visible movement, and there is no way to supply
     colours with the effect
   - Target: with `palette` supplied (a non-empty `list[HSBK]`, at most `MAX_PALETTE_COLORS`),
     the zones are painted with it through `apply_theme()` at `duration=0` and Move then
     starts. With `palette=None`, the zones are read with `get_all_color_zones()`: if more
     than one distinct colour is present the zones are left untouched and Move starts; if
     every zone is equal under `HSBK.__eq__`, the R10 single-colour palette is generated,
     painted the same way, and Move starts. The raw `set_effect(effect)` path does none of
     this (R6)
   - Acceptance: against an emulator multizone device set to one hued colour,
     `set_move_effect(Direction.FORWARD, 5.0)` passes the three R10 colours to `apply_theme()`
     at `duration=0`, leaves `get_all_color_zones()` holding `MultiZoneGenerator`'s shuffled
     blend of those colours, and `get_effect()` reports MOVE; on a strip already showing
     several colours the zones are unchanged; an explicit palette is passed to `apply_theme()`
     unchanged, with no zone read; `set_effect(MultiZoneEffect.move(...))` on a single-colour
     strip sends no `SetColorZones` or `SetExtendedColorZones` packet

10. **R10 Morph default palette**: `MatrixLight.set_effect(FirmwareEffect.MORPH,
    palette=None)` derives its palette from the device instead of sending zeroed slots.
    (Amended 2026-09-24 after UAT gap G-18-1: real firmware never starts MORPH with
    `palette_count=0`, so MORPH now always sends a non-empty palette; CONTEXT D-24 to D-28.
    The superseded text said a multi-colour device sends no palette and a read timeout falls
    back to sending no palette.)
    - Current: `palette_count=0` and 16 zeroed slots are sent, and the firmware decides
    - Target: the tiles are read with `get_all_tile_colors()` and flattened in tile order. A
      single colour sends a three-colour palette generated by one shared helper (also used by
      R9): for a white (saturation 0), the current colour plus whites at the device's
      `min_kelvin` and `max_kelvin`, falling back to 1500 K and 9000 K when the range is
      unknown; for a hued colour, the current colour plus hue +45° and -45° wrapped modulo
      360, at the same saturation, brightness and kelvin. Generated whites keep the current
      brightness. More than one distinct colour sends the device's own colours: all of them in
      first-seen pixel order when there are 16 or fewer, otherwise the colours of 16 pixels
      spaced evenly across the flattened device (pixel `i * n // 16` for `i` in 0 to 15),
      de-duplicated in sample order. An empty colour result raises `LifxProtocolError`, and a
      read timeout or malformed reply propagates as `LifxTimeoutError` or
      `LifxProtocolError`; no `Tile.SetEffect` is sent in any of these cases. FLAME and SKY
      with no palette keep sending `palette_count=0`; an explicit palette is always sent as
      given
    - Acceptance: a single-colour emulator matrix produces a `Tile.SetEffect` with
      `palette_count == 3` and the expected colours; a multi-colour one (use the
      `tile_chain_light` fixture) produces the chain's own colours in first-seen order, with
      `palette_count` between 2 and 16; a matrix showing more than 16 distinct colours sends
      the colours of the 16 evenly spaced pixels; hue 350 yields 35 and 305; an unknown
      kelvin range yields 1500 and 9000; FLAME and SKY are byte-identical to today; a read
      timeout raises and no effect is sent

## Boundaries

**In scope:**
- Moved to Phase 20 (ANIM-05) on 2026-09-23: the Thread guard in the three `Animator`
  factories with the `enable_thread` keyword
- Moved to Phase 20 (ANIM-05) on 2026-09-23: Thread exclusion in `Conductor.start()` and
  `add_lights()` with `enable_thread` on `Conductor.__init__()`
- `MultiZoneEffect.move()` classmethod and `MultiZoneLight.set_move_effect()`
  (`src/lifx/devices/multizone.py`)
- Docstrings, `docs/api/devices.md` context if needed, `docs/migration/effect-api-changes.md`
  Move section, and the effects user guide's Move section (the animation and effects docs
  that describe the Thread default moved to Phase 20 with ANIM-05 on 2026-09-23)
- The R9 palette rule in `set_move_effect()` and the R10 Morph default palette in
  `MatrixLight.set_effect()` (`src/lifx/devices/matrix.py`), sharing one palette helper
- Emulator tests for every acceptance criterion above, including the golden-packet
  equivalence backstop and the executed documentation example

**Out of scope:**
- Moved to Phase 20 (ANIM-05) on 2026-09-23: guarding `Animator.__init__()`
- Moved to Phase 20 (ANIM-05) on 2026-09-23: `EffectPulse` and any non-frame effect
- Moved to Phase 20 (ANIM-05) on 2026-09-23: the Conductor's silent return when capability
  filtering empties the list
- Moved to Phase 20 (ANIM-05) on 2026-09-23: a warning, rate clamp or duty-cycle mode for
  Thread
- Everything ANIM-05 covers: the Animator factory guard, the Conductor exclusion,
  `enable_thread` and their documentation now belong to Phase 20
- Typed builders for MORPH, FLAME or SKY. `MatrixLight.set_effect()` already takes typed
  keywords; multizone firmware has only OFF and MOVE
- Accepting `speed` or `duration` in milliseconds or nanoseconds on the typed API. Callers
  wanting raw units use the preserved `MultiZoneEffect(...)` path
- Deprecating the raw `parameters` path. Home Assistant ships it today
- Applying the R9 palette rule to the raw `set_effect(effect)` path, or adding a `palette`
  field to the `MultiZoneEffect` dataclass. Both would break R6
- Changing FLAME or SKY palette handling, or any software effect under `src/lifx/effects/`
- Any change to how `Device.connectivity` is derived
- Gating `get_wifi_info()` and `get_wifi_firmware()` on Thread, or reporting Thread RSSI.
  Those queries return nothing useful on a Thread device, but the replacement packets are
  still awaited from LIFX, so that is a future item rather than part of this phase
- Downstream changes in LedFx or Home Assistant. This phase ships the library surface they
  will adopt

## Constraints

- CI requires 100% branch patch coverage; every new branch (string versus enum direction,
  overflow checks) needs a test partial (the guard and opt-in examples moved to Phase 20 with
  ANIM-05 on 2026-09-23)
- Zero runtime dependencies, Python 3.10 floor, no `asyncio.TaskGroup`
- Generated files under `src/lifx/protocol/` are never hand-edited; `Direction` and
  `FirmwareEffect` are used as generated
- `docs/changelog.md` is not edited; the Conventional Commit messages carry the change
- Tests and docs use synthetic serials and non-live addresses (the clause on how a Thread
  device is produced for tests moved to Phase 20 with ANIM-05 on 2026-09-23, which replaces
  it rather than copying it)
- Australian English in all prose and docstrings
- Moved to Phase 20 (ANIM-05) on 2026-09-23: the `enable_thread` keyword-only and synchronous
  `for_light()` signature constraint
- File-disjoint from Phases 16, 17 and 19 as the roadmap states, with these additions:
  `src/lifx/devices/matrix.py` and the shared palette helper join the phase's file set
  (`src/lifx/effects/conductor.py` left with ANIM-05 on 2026-09-23). `Theme` is consumed,
  not edited, so Phase 19 stays disjoint

## Acceptance Criteria

Items for R1 to R3 and R8 moved to Phase 20 (ANIM-05) on 2026-09-23 and are listed without a
checkbox so they are not measured here.

- Moved to Phase 20 (ANIM-05) on 2026-09-23: each factory refuses a Thread device (R1)
- Moved to Phase 20 (ANIM-05) on 2026-09-23: refusal after the factory's own queries (R1)
- Moved to Phase 20 (ANIM-05) on 2026-09-23: a WiFi device over an IPv6 literal constructs (R2)
- Moved to Phase 20 (ANIM-05) on 2026-09-23: the existing `tests/test_animation/` suite passes unmodified (R2)
- Moved to Phase 20 (ANIM-05) on 2026-09-23: Conductor exclusion of a Thread participant (R3)
- Moved to Phase 20 (ANIM-05) on 2026-09-23: Conductor raise when only Thread participants remain (R3)
- Moved to Phase 20 (ANIM-05) on 2026-09-23: `Conductor.add_lights()` exclusion (R3)
- [ ] `MultiZoneEffect.move(Direction.REVERSED, 5.0)` equals `MultiZoneEffect(FirmwareEffect.MOVE, 5000, 0, [0, 0, 0, 0, 0, 0, 0, 0])`
- [ ] `move()` accepts `"forward"` and `"Reversed"` as direction names; any other string or type raises `ValueError`
- [ ] `move()` accepts `speed=0.0` and `duration=0`; negative values and `uint32`/`uint64` overflow raise `ValueError`; `move(Direction.FORWARD, 0.0015).speed == 2`
- [ ] `set_move_effect(Direction.FORWARD, 5.0)` against the emulator leaves `get_effect()` reporting MOVE and `speed == 5000`, and the received `MultiZone.SetEffect` carries `Direction.FORWARD` (emulator 3.7.0 zeroes Move parameters in `get_effect()`)
- [ ] `set_move_effect()` propagates `LifxUnsupportedCommandError` on a `StateUnhandled` reply
- [ ] The existing `MultiZoneEffect` tests pass with assertions, fixtures and node IDs unchanged; `tests/test_devices/test_multizone.py` differs from the merge-base only by the import-only `PLC0415` hoist (amended 2026-09-23)
- [ ] Golden-packet test: hand-encoded `parameters=[0, int(d), 0, 0, 0, 0, 0, 0]` and `move(d, s)` serialise to byte-identical `MultiZone.SetEffect` payloads
- [ ] `zensical build` succeeds; no `set_move_effect(speed=` and no `set_effect(effect_type=FirmwareEffect.MOVE` remain under `src/lifx` or `docs/`
- [ ] The documented Move example is executed verbatim by an emulator test
- Moved to Phase 20 (ANIM-05) on 2026-09-23: `enable_thread` keyword-only with default `False` (R8)
- Moved to Phase 20 (ANIM-05) on 2026-09-23: `enable_thread=True` constructs and delivers silently (R8)
- Moved to Phase 20 (ANIM-05) on 2026-09-23: MUST NOT put an IP, MAC or hostname in the refusal message or exclusion log
- Moved to Phase 20 (ANIM-05) on 2026-09-23: MUST NOT send an excluded Thread participant any Conductor packet
- Moved to Phase 20 (ANIM-05) on 2026-09-23: MUST NOT send a packet for the guard's own sake
- Moved to Phase 20 (ANIM-05) on 2026-09-23: MUST NOT refuse because an address is IPv6
- Moved to Phase 20 (ANIM-05) on 2026-09-23: MUST NOT enable Thread animation other than by the call-site argument
- [ ] MUST NOT: the raw `MultiZoneEffect(parameters=...)` and `set_effect(effect)` path emits no `DeprecationWarning` and no log message
- Moved to Phase 20 (ANIM-05) on 2026-09-23: MUST NOT add `Connectivity.THREAD`-dependent behaviour outside the factories and the Conductor (Phase 18 now adds none at all; plan 18-07's split-boundary gate enforces that)
- [ ] `set_move_effect()` on a single-colour emulator strip passes the three R10 colours to `apply_theme()`, which paints their shuffled blend, then MOVE runs; on a multi-colour strip the zones are unchanged
- [ ] `set_move_effect(..., palette=[...])` passes the given colours to `apply_theme()` at `duration=0` before MOVE starts
- [ ] Morph with no palette on a single-colour matrix sends `palette_count == 3` with the white or ±45° hue rule; on a multi-colour matrix it sends the device's own colours (all of them in first-seen order up to 16, otherwise 16 evenly sampled pixels, de-duplicated) and never `palette_count == 0` (amended 2026-09-24, G-18-1)
- [ ] Hue wraps modulo 360 (350 yields 35 and 305); an unknown kelvin range falls back to 1500 K and 9000 K; a Morph colour-read timeout, malformed reply or empty result raises and sends no effect (amended 2026-09-24, G-18-1; Move's read-failure fallback is unchanged)
- [ ] MUST NOT: the raw `set_effect(MultiZoneEffect)` path reads zones or paints anything
- [ ] MUST NOT: FLAME and SKY with no palette, and any explicit palette, change on the wire

## Edge Coverage

**Coverage:** 16/16 applicable Phase 18 edges resolved · 0 unresolved (the 10 R1, R2, R3 and
R8 rows moved to Phase 20 with ANIM-05 on 2026-09-23; they stay listed, marked moved, so the
lift is auditable; the R10 boundary row was added on 2026-09-24 after UAT gap G-18-1)

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| empty | R1 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| encoding | R1 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| concurrency | R1 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| concurrency | R2 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| adjacency | R3 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| empty | R3 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| ordering | R3 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| boundary | R4 | ✅ covered (explicit) | 0 accepted for speed and duration; negatives and uint32/uint64 overflow raise `ValueError` |
| adjacency | R4 | ⛔ dismissed | Eight fixed positional slots; no intervals or collections merge |
| empty | R4 | ✅ covered (explicit) | `direction` is required; enum member or case-insensitive name, else `ValueError` |
| ordering | R4 | ⛔ dismissed | Slot positions are protocol constants |
| precision | R4 | ✅ covered (explicit) | Seconds to ms/ns via Python `round()`; `0.0015 s` becomes `2 ms` |
| unclassified | R5 | ✅ covered (explicit) | `set_move_effect()` propagates every error `set_effect()` raises |
| adjacency | R6 | ⛔ dismissed | Fixed positional slots |
| empty | R6 | ✅ covered (explicit) + 🧪 backstop | Existing `__post_init__` validation unchanged; golden-packet equivalence test between raw and typed paths |
| ordering | R6 | ⛔ dismissed | Fixed positional slots |
| concurrency | R7 | ⛔ dismissed | Documentation has no runtime concurrency; the example test runs serially |
| boundary | R8 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| empty | R8 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| idempotency | R8 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| boundary | R9 | ✅ covered (explicit) | Explicit palette must be non-empty and at most `MAX_PALETTE_COLORS`; `None` triggers derivation |
| empty | R9 | ✅ covered (explicit) | Multi-colour strip leaves zones untouched; only a single colour is synthesised |
| boundary | R10 | ✅ covered (explicit) | Hue ±45° wraps modulo 360; kelvin range unknown falls back to 1500/9000 |
| precision | R10 | ✅ covered (explicit) | "Single colour" is `HSBK.__eq__` at uint16 granularity, no perceptual tolerance |
| unclassified | R10 | ✅ covered (explicit) | A colour-read timeout or malformed reply propagates and no effect is sent; an empty colour result raises `LifxProtocolError` (amended 2026-09-24, G-18-1; the superseded resolution logged at DEBUG and sent no palette) |
| boundary | R10 | ✅ covered (explicit) | 16 distinct colours are all sent in first-seen order; 17 or more switch to 16 evenly spaced pixels, de-duplicated (added 2026-09-24, G-18-1) |

R8 was added after the engine run (the bypass decision) and its three rows were classified by
hand against the same taxonomy. R9 and R10 were folded in from the former Phase 17.1 and
classified the same way. The R1, R2, R3 and R8 rows moved to Phase 20 on 2026-09-23.

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable Phase 18 prohibitions resolved · 0 unresolved (6 ANIM-05 rows
moved to Phase 20 on 2026-09-23 and stay listed, marked moved)

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| No IP, MAC or hostname in the refusal message or exclusion log | R1, R3 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| No Conductor packet to an excluded Thread participant | R3 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| No packet for the guard's own sake | R1 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| No refusal because an address is IPv6 | R1, R2 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| Thread animation enabled only by the call-site `enable_thread` argument | R8 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23 |
| MUST NOT emit a `DeprecationWarning` or log message on the raw `parameters` construction path | R6 | resolved | test: `warnings.catch_warnings(record=True)` and `caplog` record nothing |
| No `Connectivity.THREAD`-dependent behaviour outside the factories and the Conductor | R2, R8 | moved to Phase 20 | Moved with ANIM-05 on 2026-09-23; Phase 18 adds no connectivity- or Thread-dependent line at all, enforced by plan 18-07's split-boundary gate |
| MUST NOT read zones or paint colours on the raw `set_effect(MultiZoneEffect)` path | R6, R9 | resolved | test: emulator packet log shows only `MultiZone.SetEffect` for the raw path |
| MUST NOT change the wire payload for FLAME, SKY or any explicitly supplied palette | R10 | resolved | test: golden `Tile.SetEffect` payloads before and after |

Canon breadcrumbs, not minted: generated protocol files stay unedited, `docs/changelog.md` is
release-workflow output, and docs use synthetic identifiers. All are owned by `AGENTS.md` project
rules and `/gsd-secure-phase`.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                          |
|--------------------|-------|------|--------|------------------------------------------------|
| Goal Clarity       | 0.92  | 0.75 | ✓      | Default-refuse with opt-in; builder plus method |
| Boundary Clarity   | 0.90  | 0.70 | ✓      | `__init__`, pulse, capability-empty excluded    |
| Constraint Clarity | 0.85  | 0.65 | ✓      | Units, rounding, keyword-only, sync `for_light` |
| Acceptance Criteria| 0.88  | 0.70 | ✓      | 25 pass/fail criteria, 7 negative               |
| **Ambiguity**      | 0.11  | ≤0.20| ✓      |                                                |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

The Ambiguity Report above and the Interview Log below are the 2026-09-09 record, kept as
written.
Their rows about the Thread guard, the Conductor and `enable_thread` describe decisions that
moved to Phase 20 with ANIM-05 on 2026-09-23.

## Interview Log

| Round | Perspective     | Question summary                                   | Decision locked                                                         |
|-------|-----------------|----------------------------------------------------|-------------------------------------------------------------------------|
| 1     | Researcher      | Refuse or degrade on Thread?                       | Drop Thread devices from a set; raise when only Thread devices remain   |
| 1     | Researcher      | Typed Move API shape?                              | Both `MultiZoneEffect.move()` builder and a device method                |
| 1     | Researcher      | Speed units?                                       | Float seconds, converted to milliseconds                                 |
| 2     | Researcher      | Where does drop-versus-raise apply?                | Conductor drops, single-device factories raise                           |
| 2     | Simplifier      | Guard direct `Animator.__init__()`?                | No; no device object, escape hatch stays                                 |
| 2     | Simplifier      | Fix the two stale doc examples?                    | Yes, rewrite to the shipped API                                          |
| 3     | Boundary Keeper | Device method name?                                | `set_move_effect`                                                        |
| 3     | Failure Analyst | Never-contacted device in `for_light()`?           | Trust `connectivity` as-is; no added query; stays synchronous            |
| 3     | Boundary Keeper | Duration units?                                    | Float seconds, 0 = indefinite, converted to nanoseconds                  |
| 5.5   | Edge probe      | Guard timing in `for_multizone`/`for_matrix`?      | Evaluate after the factory's own queries                                 |
| 5.5   | Edge probe      | Conductor exclusion scope and raise condition?     | Animator paths only; raise only when Thread exclusion empties the list   |
| 5.5   | Edge probe      | Direction input and rounding?                      | Enum or case-insensitive name; `round()`                                 |
| 5.5   | Edge probe      | Remaining 12 edges                                 | Accepted as proposed (explicit, backstop, reasoned dismissals)           |
| 5.6   | User            | Does the Conductor query state before animating?   | Yes; exclusion moves before state capture                                |
| 5.6   | User            | Hard refusal too opinionated for a library?        | Add `enable_thread=False` keyword on factories and `Conductor.__init__`  |
| 5.6   | Seed Closer     | Opt-in behaviour when set?                         | Construct silently, no warning                                           |
| 5.6   | Prohibition     | Which must-NOTs to keep?                           | All six kept, split into seven rows                                      |
| post  | User            | Never-contacted device worth its own criterion?    | No; folded into R1 Target as a note, R1 empty edge dismissed             |

---

*Phase: 18-typed-move-and-morph-palette-effects*
*Spec created: 2026-09-09*
*Next step: /gsd-discuss-phase 18 for implementation decisions (exception class, guard helper placement, string-name parsing, test fixtures for an emulator Thread device)*
