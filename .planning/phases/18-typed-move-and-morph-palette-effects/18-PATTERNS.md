# Phase 18: Typed Move and Morph Palette Effects - Pattern Map

> Mapped before the 2026-09-23 split. The analogues for the Thread guard (`animation/guard.py`,
> `LifxThreadAnimationError`, the Conductor exclusion and the Thread emulator fixture) now
> belong to Phase 20 (ANIM-05). Phase 18 plans use only the Move, Morph, palette and PLC0415
> analogues.

**Mapped:** 2026-09-23
**Files analyzed:** 14 (7 source, 7 test/docs groups)
**Analogs found:** 12 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `src/lifx/exceptions.py` (add `LifxThreadAnimationError`) | model (exception hierarchy) | request-response | `src/lifx/exceptions.py` `LifxUnsupportedCommandError` (same file, sibling class) | exact |
| `src/lifx/__init__.py` (export new exception) | config (public API surface) | request-response | `src/lifx/__init__.py` existing exception export block | exact |
| `src/lifx/animation/guard.py` (new helper module, name at discretion) | utility | request-response | `src/lifx/devices/base.py` `_refuse_on_connectivity()` / `_evidenced_connectivity()` | role-match (refusal-by-connectivity pattern, different package) |
| `src/lifx/animation/animator.py` (`for_light`, `for_multizone`, `for_matrix`) | controller (factory) | request-response | same file, pre-existing factory bodies | exact (modifying itself) |
| `src/lifx/effects/conductor.py` (`__init__`, `start`, `add_lights`) | service (orchestrator) | event-driven | same file, `_filter_compatible_lights()` step | exact (modifying itself) |
| `src/lifx/devices/multizone.py` (`MultiZoneEffect.move()`, `_coerce_direction()`, `direction` setter widening) | model + utility | transform | same file, `MultiZoneEffect._validate_speed/_validate_duration/_validate_parameters` and `direction` property/setter | exact |
| `src/lifx/devices/multizone.py` (`MultiZoneLight.set_move_effect()`) | controller (device method) | request-response | `src/lifx/devices/matrix.py` `MatrixLight.set_effect()` (keyword-style typed wrapper precedent) | exact |
| `src/lifx/devices/matrix.py` (`MatrixLight.set_effect()` default-palette branch) | controller (device method) | request-response | same file, existing SKY best-effort probe block (lines 1222-1238) | exact |
| `src/lifx/devices/component_state.py` (shared palette-derivation helper) | utility | transform | same file, `is_dark()` / `hsk_matches()` | exact |
| `tests/test_animation/test_animator.py` (guard unit tests) | test | request-response | same file, `TestAnimatorForMultizoneFactory` / `TestAnimatorForLightFactory` classes | exact |
| `tests/test_effects/test_conductor.py` (exclusion tests) | test | event-driven | same file, `_make_color_light()` + `light1`/`light2` fixtures | exact |
| `tests/test_devices/test_multizone.py` (`move()`, `set_move_effect()`, golden-packet tests) | test | transform | same file, `TestMultiZoneEffect` class (`test_set_effect_with_direction`, `test_direction_property_set_for_move_effect`) | exact |
| New emulator-backed Thread tests (`tests/test_animation/`, `tests/test_effects/`) | test | event-driven | `tests/test_animation/test_animator.py` `TestAnimatorForMatrixIntegration` (`@pytest.mark.emulator`, `emulator_devices` fixture) | role-match (blocked on emulator prerequisite, see No Analog Found) |
| `docs/migration/effect-api-changes.md`, `docs/user-guide/animation.md`, `docs/user-guide/effects.md`, `MultiZoneLight` class docstring | docs | transform | same files, existing Move sections | exact |

## Pattern Assignments

### `src/lifx/exceptions.py` (add `LifxThreadAnimationError`)

**Analog:** `src/lifx/exceptions.py` (same file — follow the sibling-class shape)

**Core pattern** (lines 65-88, `LifxUnsupportedCommandError` and `LifxUnsupportedDeviceError`):
```python
class LifxUnsupportedCommandError(LifxError):
    """Raised when a device doesn't support the requested command.

    Raised when a device returns a ``StateUnhandled`` response indicating
    the packet type is not supported, or when calling a method that requires
    a capability the device does not have.
    """

    pass
```
D-01 locks `LifxThreadAnimationError(LifxUnsupportedCommandError)` — subclass the existing command-unsupported class, not `LifxError` directly, following this exact docstring shape (one-line summary, "Raised when/by" body, trailing `pass`). Message shape per D-02: `f"Animator refuses Thread device {serial}: a Thread mesh cannot sustain animation frame traffic. Pass enable_thread=True to override."`

---

### `src/lifx/__init__.py` (export the new exception)

**Analog:** `src/lifx/__init__.py` lines 75-79 (import block) and 196-198 (`__all__` block)

**Import pattern** (lines 75-79):
```python
    LifxNetworkError,
    ...
    LifxUnsupportedCommandError,
    LifxUnsupportedDeviceError,
```

**Export pattern** (lines 196-198):
```python
    "LifxNetworkError",
    "LifxUnsupportedCommandError",
    "LifxUnsupportedDeviceError",
```
Insert `LifxThreadAnimationError` alphabetically in both the `from lifx.exceptions import (...)` block and `__all__`. Note `lifx.exceptions` itself needs no `__all__` edit — it exports every public class by module contents; only `lifx/__init__.py`'s explicit re-export list needs the addition. Per D-01, it must also be importable directly from `lifx.exceptions` (already true — no `__all__` restricts that module).

---

### `src/lifx/animation/guard.py` (new shared helper, D-03)

**Analog:** `src/lifx/devices/base.py` `_evidenced_connectivity()` (lines 1624-1635) and `_refuse_on_connectivity()` (lines 1636-1655)

**Imports pattern** — the guard needs `Connectivity` from `lifx.devices.base` and `LifxThreadAnimationError` from `lifx.exceptions`:
```python
from lifx.devices.base import Connectivity, Device
from lifx.exceptions import LifxThreadAnimationError
```

**Core refusal pattern** (base.py lines 1636-1655), the shape to mirror for the new helper — note this method already implements "read `device.connectivity` (or the lower-level evidence), raise a typed exception naming the reason" and is the library's only existing precedent for a connectivity-gated refusal:
```python
def _refuse_on_connectivity(self, refused: Connectivity, method: str) -> None:
    """Refuse a radio-specific query the device's firmware cannot answer.
    ...
    """
    if self._evidenced_connectivity() is refused:
        radio = "Thread" if refused is Connectivity.THREAD else "WiFi"
        raise LifxUnsupportedCommandError(
            f"{method}() is not supported on a {radio} device: "
            f"{radio} firmware cannot answer this query"
        )
```
The new helper takes `(device, enable_thread)` instead of using `self`/`method`, reads the public `device.connectivity` property (not the private `_evidenced_connectivity()`, since the guard lives outside `Device`), and raises `LifxThreadAnimationError` with the D-02 message shape when `device.connectivity is Connectivity.THREAD and not enable_thread`. Provide a predicate form (or a second thin wrapper) for the Conductor's exclusion check per D-03's "predicate form ... serves the Conductor's exclusion decision."

**`connectivity` property being read** (`src/lifx/devices/base.py` lines 2617-2641) — this is the read-only, no-extra-query source of truth the guard consumes; nothing new is added to it:
```python
@property
def connectivity(self) -> Connectivity:
    observed = self.connection.thread_connection
    if observed is not None:
        return Connectivity.THREAD if observed else Connectivity.WIFI
    return self._connectivity
```

---

### `src/lifx/animation/animator.py` (`for_light`, `for_multizone`, `for_matrix`)

**Analog:** same file — the three existing factories are their own closest analog; add the `enable_thread: bool = False` keyword-only parameter and a guard call after each factory's own queries.

**Imports pattern** (lines 33-66) — the module already gates imports behind `TYPE_CHECKING` for device types; add the guard import at module scope (not lazy — animation package owns the helper, so this is an intra-package import, not the effects-to-animation lazy-import case):
```python
from lifx.animation.flow import AckGate
from lifx.animation.framebuffer import FrameBuffer
from lifx.animation.packets import (...)
from lifx.const import LIFX_UDP_PORT
from lifx.exceptions import LifxNetworkError
```

**Guard placement — `for_matrix`** (after tile query, lines 224-253, before `return cls(...)`): call the guard after `tiles = device.device_chain` is resolved and before `framebuffer = await FrameBuffer.for_matrix(device)` (or immediately before the final `return cls(...)`), so a Thread report first observed by `get_device_chain()` is caught (R1 Target, D-03: "after their own device queries complete").

**Guard placement — `for_multizone`** (after `zone_count = await device.get_zone_count()`, lines 291-320, before `return cls(...)`): same rule — evaluate after the capability/zone-count queries.

**Guard placement — `for_light`** (lines 322-357): `for_light` sends nothing, so the guard runs against whatever `device.connectivity` already reports (metadata default per R1 Target), placed right after `ip = device.ip` / `serial = Serial.from_string(device.serial)` and before `return cls(...)`. `for_light` stays synchronous — the guard function itself must not be a coroutine.

**Signature change pattern** — add `enable_thread: bool = False` as the last keyword-only parameter on all three, after `duration_ms: int = 0`, matching the existing keyword-default style already used for `duration_ms`.

---

### `src/lifx/effects/conductor.py` (`__init__`, `start`, `add_lights`)

**Analog:** same file — `_filter_compatible_lights()` (lines 613-657) is the step to run the new exclusion step after, and `_create_animators()` (lines 659-689) shows the established lazy-import-from-effects-to-animation pattern (D-03 says the guard helper import follows this same route).

**Imports pattern / lazy import precedent** (lines 671-673, inside `_create_animators`):
```python
from lifx.animation.animator import Animator
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
```
The new Thread-exclusion step imports the guard predicate the same way, inside the method that needs it (not at module top), per D-03.

**`__init__` pattern** (lines 55-59) — add `enable_thread: bool = False` parameter and store it:
```python
def __init__(self) -> None:
    """Initialize the Conductor."""
    self._state_manager = DeviceStateManager()
    self._running: dict[str, RunningEffect] = {}
    self._lock = asyncio.Lock()
```

**Exclusion step placement in `start()`** (D-04: separate step, only for `FrameEffect`, after `_filter_compatible_lights()`, before prestate capture) — insert between the existing filter-then-warn-then-return block (lines 140-158) and the `async with self._lock:` capture block (line 160). The `isinstance(effect, FrameEffect)` check already exists later in `start()` at line 226-234 (currently placed after capture); D-04 requires exclusion to run as its own step *before* capture, so the `FrameEffect` check must be duplicated (or hoisted) earlier than that existing check.

**Existing silent-return-with-warning pattern to mirror for the raise condition** (lines 145-158):
```python
if not filtered_participants:
    _LOGGER.warning(
        {
            "class": self.__class__.__name__,
            "method": "start",
            "action": "filter",
            "values": {
                "effect": type(effect).__name__,
                "total_participants": len(participants),
                "compatible_participants": 0,
            },
        }
    )
    return
```
D-05's per-excluded-participant WARNING log follows this exact structured-dict shape, with `"action": "exclude"` and `"values": {"serial": ..., "reason": ...}`. The list-emptied-by-Thread-exclusion raise (distinct from the capability-emptied silent return) is a **new** branch — no existing raise-after-filter precedent in this file; model it on the guard's own `LifxThreadAnimationError`, naming every excluded serial per D-02.

**`add_lights()` placement** (lines 329-349): same exclusion step, inserted between `compatible = await self._filter_compatible_lights(effect, lights)` (line 347) and the `if not compatible: return` / `async with self._lock:` block, gated the same way on `isinstance(effect, FrameEffect)`.

---

### `src/lifx/devices/multizone.py` — `MultiZoneEffect.move()`, `_coerce_direction()`, `direction` setter widening

**Analog:** same file — `_validate_speed`/`_validate_duration`/`_validate_parameters` (lines 60-104) for the validation-staticmethod style, and the existing `direction` property/setter (lines 106-132) for the widening target.

**Imports pattern** (lines 11-25) — already imports `Direction` and `FirmwareEffect`:
```python
from lifx.protocol.protocol_types import (
    Direction,
    FirmwareEffect,
    MultiZoneApplicationRequest,
    MultiZoneEffectParameter,
    MultiZoneEffectSettings,
)
```

**Validation staticmethod pattern** (lines 60-71, `_validate_speed`) — `_coerce_direction()` follows this same `@staticmethod` + docstring-with-Raises shape:
```python
@staticmethod
def _validate_speed(value: int) -> None:
    """Validate effect speed is non-negative.
    ...
    """
    if value < 0:
        raise ValueError(f"Effect speed must be non-negative, got {value}")
```
D-09: `_coerce_direction()` accepts a `Direction` member or case-insensitive name, raises `ValueError` otherwise; used by `move()`, `set_move_effect()` and the widened `direction` setter (currently `direction.setter` at lines 117-132 takes `Direction` only — widen its type hint and body to call `_coerce_direction()`).

**`direction` setter being widened** (lines 117-132):
```python
@direction.setter
def direction(self, value: Direction) -> None:
    """Set direction for MOVE effect.
    ...
    """
    if self.effect_type != FirmwareEffect.MOVE:
        raise ValueError(
            f"Direction can only be set for MOVE effects, "
            f"current type is {self.effect_type.name}"
        )
    self.parameters = [0, int(value), 0, 0, 0, 0, 0, 0]
```

**`move()` classmethod** — no direct existing classmethod on `MultiZoneEffect` (it currently has only the dataclass `__init__` via `__post_init__`), so model the eight-slot `parameters` construction on the setter's `[0, int(value), 0, 0, 0, 0, 0, 0]` line above, wrapped in a `@classmethod` that calls `cls(effect_type=FirmwareEffect.MOVE, speed=..., duration=..., parameters=[0, int(direction), 0, 0, 0, 0, 0, 0])`. R4 requires float-seconds-to-ms/ns `round()` conversion with `uint32`/`uint64` bound checks — reuse `_validate_speed`/`_validate_duration`'s "raise ValueError with the value in the message" style for the new bound checks (exact `uint32`/`uint64` bound-check location is Claude's Discretion per CONTEXT.md).

---

### `src/lifx/devices/multizone.py` — `MultiZoneLight.set_move_effect()`

**Analog:** `src/lifx/devices/matrix.py` `MatrixLight.set_effect()` (lines 1176-1287) — explicitly named in CONTEXT.md as "the keyword-style precedent for `set_move_effect()`."

**Keyword-style signature and docstring-example pattern** (matrix.py lines 1176-1221):
```python
async def set_effect(
    self,
    effect_type: FirmwareEffect,
    speed: float = 3.0,
    duration: int = 0,
    palette: list[HSBK] | None = None,
    sky_type: TileEffectSkyType = TileEffectSkyType.SUNRISE,
    cloud_saturation_min: int = 0,
    cloud_saturation_max: int = 0,
) -> None:
    """Set matrix effect with configuration.

    Args:
        effect_type: Type of effect (OFF, MORPH, FLAME, SKY)
        speed: Effect speed in seconds (default: 3)
        ...
    Example:
        >>> # Set MORPH effect with rainbow palette
        >>> rainbow = [...]
        >>> await matrix.set_effect(
        ...     effect_type=FirmwareEffect.MORPH,
        ...     speed=5.0,
        ...     palette=rainbow,
        ... )
    """
```
`set_move_effect(direction, speed, duration=0, palette=None)` (D-10) follows this keyword-example docstring shape exactly, with a runnable example per R7. Internally: `effect = MultiZoneEffect.move(direction, speed, duration)` built first (so bad arguments raise before any packet is sent, D-10), then the D-13 palette rule applied, then `await self.set_effect(effect)` — reusing the existing `set_effect()` at lines 834-914 for the actual send, so `LifxUnsupportedCommandError`/`LifxTimeoutError`/`LifxDeviceNotFoundError` propagate unchanged (R5).

**Existing `set_effect()` docstring's raw-parameters example** (lines 848-868) is the "raw path stays byte-identical" reference the golden-packet test in R6 compares against — do not modify this docstring's raw-`parameters=` example; R7 only requires the **class** docstring and the migration guide be rewritten, not this method's own docstring text (though its Raises list should gain nothing — `set_effect()` itself is unchanged).

---

### `src/lifx/devices/matrix.py` — `MatrixLight.set_effect()` default-palette branch (R10)

**Analog:** same file, the existing SKY best-effort timeout-probe block (lines 1222-1238) — CONTEXT.md's D-23 explicitly says the new timeout fallback "mirrors the SKY support probe."

**Timeout-fallback pattern to mirror** (lines 1222-1238):
```python
if effect_type == FirmwareEffect.SKY:
    try:
        supported, reason = await self._resolve_sky_support()
    except LifxTimeoutError:
        # The support probe is best-effort. A device that fails to
        # answer is not evidence of missing support, and refusing here
        # would turn a fire-and-forget send into a hard failure.
        _LOGGER.debug(
            "SKY support probe timed out for %s, sending the effect anyway",
            self.label or self.serial,
        )
    else:
        if not supported:
            raise LifxUnsupportedCommandError(...)
```
The new MORPH-with-no-palette branch follows the identical `try/except LifxTimeoutError: _LOGGER.debug(...)` shape (D-23: "log at DEBUG and fall back to the 'no palette' behaviour"), gated on `effect_type == FirmwareEffect.MORPH and palette is None` and calling `await self.get_all_tile_colors()` instead of `self._resolve_sky_support()`.

**Palette-to-wire conversion being extended** (lines 1259-1283) — this is where the derived/generated palette slots in, alongside the existing explicit-palette path (D-19: only MORPH changes; FLAME/SKY untouched):
```python
proto_palette = []
palette_count = 0

if effect.palette is not None:
    palette_count = len(effect.palette)
    proto_palette = [color.to_protocol() for color in effect.palette]

while len(proto_palette) < 16:
    proto_palette.append(LightHsbk(0, 0, 0, 3500))
```

**`get_all_tile_colors()`** (line 615, signature) is the read call D-13 requires for Morph; find its exact body via `Read` with `offset=615, limit=30` when implementing — not reproduced here to avoid an unnecessary full-file read.

---

### `src/lifx/devices/component_state.py` — shared palette-derivation helper (D-22)

**Analog:** same file, `is_dark()` (lines 110-122) and `hsk_matches()` (lines 125-144) — D-22 explicitly places the new helper "next to" these.

**Pure-helper style to copy** (lines 110-144):
```python
def is_dark(colors: list[HSBK]) -> bool:
    """Return whether every color is unlit once encoded for the wire.

    Compared at uint16 granularity, matching what the device can express: a
    float brightness small enough to round to 0 is written as 0.

    Args:
        colors: Colours to check

    Returns:
        True if every colour has wire brightness 0
    """
    return all(c.to_protocol().brightness == 0 for c in colors)


def hsk_matches(stored: HSBK, current: HSBK) -> bool:
    """Compare hue/saturation/kelvin at uint16 (wire) granularity.
    ...
    """
    sp = stored.to_protocol()
    cp = current.to_protocol()
    return (
        sp.hue == cp.hue and sp.saturation == cp.saturation and sp.kelvin == cp.kelvin
    )
```
The new helper (e.g. `derive_single_colour_palette(colors: list[HSBK], min_kelvin: int | None, max_kelvin: int | None) -> list[HSBK] | None`) is a pure function taking `list[HSBK]` plus an optional kelvin range (D-22), returns `None` (or an empty list) when the input has more than one distinct colour (compare via `HSBK.__eq__` per D-17 — protocol/uint16 equality, not `hsk_matches()`, since D-17 says "equal under the existing `HSBK.__eq__`", a stricter/different comparison than `hsk_matches()`'s hue/sat/kelvin-only compare — do not reuse `hsk_matches()` here, only its *docstring style*). It applies D-15/D-16/D-18's white-vs-hued generation rule and is imported by both `matrix.py` and `multizone.py`.

**`Colours` (module import) needed:** `from lifx.color import HSBK` (already the file's only import at line 20).

---

### `src/lifx/devices/multizone.py` — `set_move_effect()` palette painting (D-20)

**Analog:** `apply_theme()` (multizone.py, starts line 1142) and `set_all_color_zones()` (lines 989-1140), plus `Theme` construction used by `apply_theme()`.

**Paint-through-theme pattern** (`apply_theme` signature, line 1142-1148):
```python
async def apply_theme(
    self,
    theme: Theme,
    power_on: bool = False,
    duration: float = 0,
    strategy: str | None = None,
) -> None:
```
D-20: wrap the derived/explicit palette in a `Theme` and call `self.apply_theme(theme, duration=0)` before sending the Move effect. `Theme` itself is imported under `TYPE_CHECKING` at line 28 (`from lifx.theme import Theme`) — the runtime construction needs a non-`TYPE_CHECKING` import inside `set_move_effect()` or promoted to module scope; check `Theme`'s constructor signature (`lifx/theme/theme.py`, not read here — out of this phase's file set per Boundaries, "`Theme` is consumed, not edited") before writing the call.

---

## Shared Patterns

### Structured warning/debug logging
**Source:** `src/lifx/effects/conductor.py` lines 146-157 (WARNING) and `src/lifx/devices/multizone.py` lines 902-914 (DEBUG)
**Apply to:** the D-05 per-participant exclusion log in `Conductor`, and any DEBUG logging added around the guard or palette derivation.
```python
_LOGGER.warning(
    {
        "class": self.__class__.__name__,
        "method": "start",
        "action": "filter",
        "values": {
            "effect": type(effect).__name__,
            "total_participants": len(participants),
            "compatible_participants": 0,
        },
    }
)
```
Every new log call uses this `{"class", "method", "action", "values": {...}}` dict shape, never an f-string message (except the two `_LOGGER.debug("...", args)` %-style calls in `matrix.py`'s SKY probe, which D-23 explicitly mirrors for the new timeout fallback — that one block is the sole %-style exception).

### Connectivity-gated refusal
**Source:** `src/lifx/devices/base.py` `_refuse_on_connectivity()` / `_evidenced_connectivity()` (lines 1624-1655) and the public `connectivity` property (lines 2617-2641)
**Apply to:** the new `src/lifx/animation/guard.py` helper (R1/R3), which is a new *variant* of this pattern living outside `Device` because it needs the `enable_thread` opt-in the existing method has no room for.

### Lazy in-method imports (effects → animation, package boundary)
**Source:** `src/lifx/effects/conductor.py` `_create_animators()` lines 671-673 and every other `from lifx.effects.frame_effect import FrameEffect` call scattered through `conductor.py` (e.g. lines 107, 226, 293, 391, 441, 529, 601)
**Apply to:** the Conductor's import of the new animation-package guard helper — same lazy, inside-the-method pattern, preserving the existing "effects imports animation, never the reverse" direction. `src/**` stays under the `PLC0415` per-file ignore (pyproject.toml line 98), so this remains permitted for source files (only the two *test* paths lose the ignore per D-12).

### Keyword-only opt-in flag, default `False`, no environment/global fallback
**Source:** none identical in the codebase today — closest shape is `duration_ms: int = 0` as the existing keyword-with-default on the three `Animator.for_*()` factories (`animator.py` lines 196, 259, 326) and `power_on: bool = False` on `apply_theme()` (`multizone.py` line 1145, `matrix.py` line 1292).
**Apply to:** `enable_thread: bool = False` on all four surfaces (R8). No existing precedent for "read from `os.environ` or a module global" exists anywhere in `src/lifx` (confirmed absent — R8's prohibition needs no removal, only avoidance).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Emulator per-device `thread_connection` reply-flag support (D-06/D-07) | test fixture / external dependency | event-driven | Lives in the separate `lifx-emulator-core` package (local checkout `/Volumes/External/Developer/Djelibeybi/lifx-emulator`), not this repository. It is a **blocking prerequisite** (D-07): the planner's first wave must bump the `lifx-emulator-core>=3.1.0` pin in `pyproject.toml` line 43 to the version carrying the flag before any Thread-emulator test in this phase can be written. No in-repo analog exists because no Thread-capable emulator device has ever been constructed here — today's closest emulator fixtures (`emulator_devices`, `tile_chain_light`, session-scoped in `tests/conftest.py`) all report WiFi implicitly. |
| Golden-packet equivalence test (R6 backstop) | test | transform | No existing test compares two independently-constructed packet payloads byte-for-byte in this codebase; `tests/test_devices/test_multizone.py::test_set_effect_with_direction` (around line 926) is the nearest relative — it asserts on one `MultiZoneEffect`'s serialised fields — but the planner should write the new golden-packet test from `packets.MultiZone.SetEffect(...).to_bytes()` (or equivalent serializer entry point) rather than adapting an existing test, since no prior test performs a raw-vs-typed byte comparison. |

## Metadata

**Analog search scope:** `src/lifx/animation/`, `src/lifx/effects/`, `src/lifx/devices/` (base.py, multizone.py, matrix.py, component_state.py), `src/lifx/exceptions.py`, `src/lifx/__init__.py`, `src/lifx/devices/__init__.py`, `tests/test_animation/`, `tests/test_effects/`, `tests/test_devices/`, `docs/migration/`, `pyproject.toml`
**Files scanned:** 7 source files read in full or by targeted range, 4 test files grep'd/read by range, 2 config/doc files grep'd
**Pattern extraction date:** 2026-09-23
