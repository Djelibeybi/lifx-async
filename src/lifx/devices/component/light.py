"""Shared transition and observation rules for Ceiling and Mirror lights.

Both light components share one tile and one hardware transition. Keep the last
written target while the firmware reports intermediate colours, and serialise
read/compose/write operations so concurrent callers cannot lose each other's
changes. Received colours remain observations, separate from pending targets and
colours remembered for the next turn-on.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lifx.color import HSBK
from lifx.const import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT, LIFX_UDP_PORT
from lifx.devices.component.state import Pending, hsk_matches, is_dark
from lifx.devices.matrix import MatrixLight
from lifx.exceptions import LifxError

if TYPE_CHECKING:
    from lifx.theme import Theme

_POWER_ON = 65535


@dataclass(frozen=True)
class _ComponentFields:
    """Map one light component to its existing named state fields."""

    name: str
    colours: str
    scalar: bool = False

    def read(self, state: Any, prefix: str = "") -> list[HSBK] | None:
        """Read scalar and list fields through the same internal representation."""
        value = getattr(state, prefix + self.colours)
        if value is None:
            return None
        return [value] if self.scalar else list(value)

    def write(self, state: Any, colours: list[HSBK], prefix: str = "") -> None:
        """Preserve the public scalar/list representation, copying lists."""
        setattr(
            state, prefix + self.colours, colours[0] if self.scalar else list(colours)
        )


class ComponentMatrixLight(MatrixLight):
    """Matrix light whose two light components share one transition.

    Device adapters supply positions and state-field mappings. This module owns
    the operation sequence, including pending targets and partial-success state.
    """

    _component_fields: tuple[_ComponentFields, _ComponentFields]
    _state_file: str | None

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        *,
        fetch_wifi_info: bool = False,
        fetch_thread_info: bool = False,
        fetch_radio_info: bool = False,
        fetch_ambient_light: bool = False,
    ) -> None:
        """Initialise shared state; see Device for connection parameters."""
        super().__init__(
            serial,
            ip,
            port,
            timeout,
            max_retries,
            fetch_wifi_info=fetch_wifi_info,
            fetch_thread_info=fetch_thread_info,
            fetch_radio_info=fetch_radio_info,
            fetch_ambient_light=fetch_ambient_light,
        )
        self._pending_tile: Pending[list[HSBK]] = Pending()
        self._pending_power: Pending[int] = Pending()
        self._component_lock = asyncio.Lock()
        self._component_owner: asyncio.Task[Any] | None = None
        self._writing_tile = False
        self._writing_power = False
        # Baseline for detecting changes, not a substitute for a hardware read.
        # During our own fade this holds the target, not intermediate reports.
        self._known_tile: dict[int, HSBK] = {}
        # A Ceiling 13x26 downlight spans two responses. Only decide whether an
        # entire component is dark after observing all of its zones.
        self._observed_positions: set[int] = set()
        self._changed_positions: set[int] = set()

    def _component_positions(self, component: str) -> tuple[int, ...]:
        """Return buffer positions in the device's public colour order."""
        raise NotImplementedError

    async def _save_state_to_file(self) -> None:
        """Persist through the device's existing schema and error policy."""
        raise NotImplementedError

    def _fields(self, component: str) -> _ComponentFields:
        """Find the state mapping for a light component."""
        for fields in self._component_fields:
            if fields.name == component:
                return fields
        raise ValueError(f"Unknown light component: {component}")

    def _other_component(self, component: str) -> str:
        """Return the other side of this light."""
        first, second = self._component_fields
        return second.name if component == first.name else first.name

    def _has_component_state(self) -> bool:
        """Initialisation can temporarily hold only a parent state object."""
        return self._state is not None and hasattr(
            self._state, self._component_fields[0].colours
        )

    @asynccontextmanager
    async def _component_operation(self) -> AsyncIterator[None]:
        """Own one state-changing operation, including its nested write paths.

        Ownership is task-local, not inherited by child tasks. In particular the
        uniform-tile SetColor shortcut must not reacquire our non-reentrant lock.
        This lock is specific to the shared state of this device instance; raw
        matrix commands and Animator keep their existing packet behaviour.
        """
        task = asyncio.current_task()
        if task is not None and task is self._component_owner:
            yield
            return
        async with self._component_lock:
            self._component_owner = task
            try:
                yield
            finally:
                self._component_owner = None

    async def _persist_component_state(self) -> None:
        """Use existing best-effort persistence after state handling completes."""
        if self._state_file:
            await self._save_state_to_file()

    def _zones_changed(self) -> None:
        """Forget pending colours after raw writes, effects or Animator startup."""
        self._pending_tile.clear()
        self._known_tile.clear()
        self._observed_positions.clear()
        self._changed_positions.clear()

    def _stored_colors(self, component: str) -> list[HSBK] | None:
        """Return remembered colours only when they fit this component."""
        colours = self._fields(component).read(self.state, "stored_")
        if colours is None or len(colours) != len(self._component_positions(component)):
            return None
        return colours

    def _set_stored_colors(self, component: str, colors: list[HSBK]) -> None:
        """Remember restoration colours in the existing named fields."""
        self._fields(component).write(self.state, colors, "stored_")

    def _stored_colors_snapshot(self) -> dict[str, list[HSBK] | None] | None:
        """Copy both components' stored colours, or None before state exists."""
        if not self._has_component_state():
            return None
        return {
            fields.name: fields.read(self.state, "stored_")
            for fields in self._component_fields
        }

    async def _reinstate_stored_colors(
        self, snapshot: dict[str, list[HSBK] | None]
    ) -> None:
        """Put back stored colours copied before a whole-light software effect.

        Restoring the tile and power after an effect goes through paths that
        remember colours (uniform-tile SetColor, power-off capture), and tile
        reads while frames play adopt frame colours. None of those are colours
        the user chose, so the copy taken before the effect wins.
        """
        async with self._component_operation():
            for fields in self._component_fields:
                colours = snapshot[fields.name]
                if colours is None:
                    setattr(self.state, "stored_" + fields.colours, None)
                else:
                    fields.write(self.state, colours, "stored_")
        await self._persist_component_state()

    def _set_component_state(
        self, component: str, colors: list[HSBK], *, stored: bool = False
    ) -> None:
        """Publish colours and last-known colours, optionally remembering them."""
        fields = self._fields(component)
        fields.write(self.state, colors)
        fields.write(self.state, colors, "last_")
        if stored:
            fields.write(self.state, colors, "stored_")

    def _update_component_flags(self) -> None:
        """Derive on/off flags from known power and the last-known colours."""
        if not self._has_component_state():
            return
        for fields in self._component_fields:
            colours = fields.read(self.state, "last_")
            if colours is not None:
                setattr(
                    self.state,
                    f"{fields.name}_is_on",
                    bool(self.state.power > 0 and not is_dark(colours)),
                )

    def _publish_tile(self, tile: list[HSBK]) -> None:
        """Publish a complete known tile without changing restoration colours."""
        if not self._has_component_state():
            return
        self._state.tile_colors = list(tile)
        for fields in self._component_fields:
            colours = [tile[p] for p in self._component_positions(fields.name)]
            self._set_component_state(fields.name, colours)
        self._update_component_flags()

    async def _tile_colors_for_update(self) -> list[HSBK]:
        """Compose from our pending target, otherwise from a fresh device read."""
        pending = self._pending_tile.get()
        if pending is not None:
            return pending
        tile = (await self.get_all_tile_colors())[0]
        if any(
            position >= len(tile)
            for fields in self._component_fields
            for position in self._component_positions(fields.name)
        ):
            raise LifxError(
                f"Device returned {len(tile)} zones, too few for the component layout"
            )
        return tile

    async def _write_tile(self, tile_colors: list[HSBK], duration: float) -> None:
        """Write and publish a complete tile only after the write succeeds."""
        self._writing_tile = True
        self._observed_positions.clear()
        self._changed_positions.clear()
        try:
            await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))
        except BaseException:
            # A failed/cancelled request may have reached the hardware. Do not
            # continue composing from an earlier target as though it had not.
            self._pending_tile.clear()
            raise
        finally:
            self._writing_tile = False
        self._pending_tile.record(tile_colors, duration)
        self._known_tile = dict(enumerate(tile_colors))
        self._publish_tile(tile_colors)

    async def _power_for_update(self) -> int:
        """Trust recent power writes while GetPower still reports old power."""
        pending = self._pending_power.get()
        power = pending if pending is not None else await self.get_power()
        if self._state is not None:
            self._state.power = power
        return power

    def _record_power(self, on: bool, duration: float) -> None:
        """Record successful power and update both sides even after partial work."""
        self._pending_power.record(
            _POWER_ON if on else 0, duration, trust_for_duration=not on
        )
        self._observed_positions.clear()
        self._changed_positions.clear()
        if self._state is not None:
            self._state.power = _POWER_ON if on else 0
            self._update_component_flags()

    async def _write_power(self, on: bool | int, duration: float) -> None:
        """Send power without re-entering whole-light colour capture."""
        # Retain the last completed power write on failure: firmware may
        # still report the old power level during a pending power-off fade.
        self._writing_power = True
        try:
            await super().set_power(on, duration)
        finally:
            self._writing_power = False
        self._record_power(bool(on), duration)

    def _normalise_colors(
        self,
        component: str,
        colors: HSBK | list[HSBK],
        *,
        zero_message: str,
    ) -> list[HSBK]:
        """Validate and expand one side's colours before doing any I/O."""
        count = len(self._component_positions(component))
        if isinstance(colors, HSBK):
            if is_dark([colors]):
                raise ValueError(zero_message)
            return [colors] * count
        if is_dark(colors):
            raise ValueError(zero_message)
        if len(colors) != count:
            raise ValueError(
                f"Expected {count} colors for {component}, got {len(colors)}"
            )
        return list(colors)

    async def _set_component_colors(
        self, component: str, colors: HSBK | list[HSBK], duration: float
    ) -> None:
        """Set one side, preserving the other side's colours or fade target."""
        targets = self._normalise_colors(
            component,
            colors,
            zero_message=(
                f"Cannot set {component} colors with brightness=0. "
                f"Use turn_{component}_off() instead."
            ),
        )
        async with self._component_operation():
            await self._set_component_colors_owned(component, targets, duration)
        await self._persist_component_state()

    async def _set_component_colors_owned(
        self,
        component: str,
        targets: list[HSBK],
        duration: float,
        tile: list[HSBK] | None = None,
    ) -> None:
        """Compose/write after the caller has acquired operation ownership."""
        if tile is None:
            tile = await self._tile_colors_for_update()
        for position, colour in zip(self._component_positions(component), targets):
            tile[position] = colour
        await self._write_tile(tile, duration)
        self._set_stored_colors(component, targets)

    async def _turn_component_on(
        self,
        component: str,
        colors: HSBK | list[HSBK] | None,
        duration: float,
    ) -> None:
        """Restore one side, preloading colours if device power is off."""
        targets = (
            self._normalise_colors(
                component,
                colors,
                zero_message=f"Cannot turn on {component} with brightness=0",
            )
            if colors is not None
            else None
        )
        async with self._component_operation():
            if await self._power_for_update() == 0:
                tile = await self._tile_colors_for_update()
                if targets is None:
                    targets = await self._determine_component_brightness(
                        component, tile
                    )
                other = self._other_component(component)
                other_positions = self._component_positions(other)
                other_colours = [tile[p] for p in other_positions]
                for position, colour in zip(
                    self._component_positions(component), targets
                ):
                    tile[position] = colour
                for position in other_positions:
                    tile[position] = self._unlit(tile[position])
                preload = duration if self._pending_power.transitioning() else 0.0
                await self._write_tile(tile, preload)
                # The tile is confirmed even if the subsequent power write fails.
                self._set_stored_colors(component, targets)
                if not is_dark(other_colours):
                    self._set_stored_colors(other, other_colours)
                await self._write_power(True, duration)
            else:
                # Adopt a new observation before selecting restoration colours;
                # an external change discovered by this read must win too.
                tile = await self._tile_colors_for_update()
                if targets is None:
                    targets = await self._determine_component_brightness(
                        component, tile
                    )
                await self._set_component_colors_owned(
                    component, targets, duration, tile
                )
        await self._persist_component_state()

    @staticmethod
    def _unlit(colour: HSBK) -> HSBK:
        """Preserve hue, saturation and kelvin while removing brightness."""
        return HSBK(colour.hue, colour.saturation, 0.0, colour.kelvin)

    async def _turn_component_off(
        self,
        component: str,
        colors: HSBK | list[HSBK] | None,
        duration: float,
    ) -> None:
        """Darken one side, or power off if the other side is already dark."""
        stored = (
            self._normalise_colors(
                component,
                colors,
                zero_message=(
                    "Provided colors cannot have brightness=0. "
                    "Omit the parameter to use current colors."
                ),
            )
            if colors is not None
            else None
        )
        async with self._component_operation():
            tile = await self._tile_colors_for_update()
            positions = self._component_positions(component)
            current = [tile[p] for p in positions]
            if stored is None:
                previous = self._stored_colors(component)
                stored = (
                    previous if is_dark(current) and previous is not None else current
                )
            other = self._other_component(component)
            other_dark = is_dark([tile[p] for p in self._component_positions(other)])
            if other_dark:
                await self._write_power(False, duration)
                # Power-off succeeded. Publish that progress before attempting
                # an optional second write; its failure cannot make us 'on'.
                self._known_tile = dict(enumerate(tile))
                self._publish_tile(tile)
                self._set_stored_colors(component, current)
                if colors is not None and duration == 0:
                    for position, colour, old in zip(positions, stored, current):
                        tile[position] = HSBK(
                            colour.hue, colour.saturation, old.brightness, colour.kelvin
                        )
                    await self._write_tile(tile, 0.0)
            else:
                for position, colour in zip(positions, stored):
                    tile[position] = self._unlit(colour)
                await self._write_tile(tile, duration)
            self._set_stored_colors(component, stored)
        await self._persist_component_state()

    async def _determine_component_brightness(
        self, component: str, tile_colors: list[HSBK] | None = None
    ) -> list[HSBK]:
        """Restore, infer from the other side, or use 80% brightness.

        Inference itself updates only last-known tracking. An actual hardware
        read has its own observation adoption, independent of this calculation.
        """
        stored = self._stored_colors(component)
        if stored is not None and any(c.brightness > 0 for c in stored):
            return stored
        tile = (
            tile_colors
            if tile_colors is not None
            else await self._tile_colors_for_update()
        )
        other = self._other_component(component)
        current = [tile[p] for p in self._component_positions(component)]
        other_colours = [tile[p] for p in self._component_positions(other)]
        self._fields(component).write(self.state, current, "last_")
        self._fields(other).write(self.state, other_colours, "last_")
        source = stored if stored is not None else current
        average = sum(c.brightness for c in other_colours) / len(other_colours)
        brightness = average if average > 0 else 0.8
        return [HSBK(c.hue, c.saturation, brightness, c.kelvin) for c in source]

    async def set_power(self, level: bool | int, duration: float = 0.0) -> None:
        """Set whole-light power, capturing restoration colours on power-off."""
        if isinstance(level, bool):
            on = level
        elif isinstance(level, int):
            if level not in (0, _POWER_ON):
                raise ValueError(f"Power level must be 0 or 65535, got {level}")
            on = level != 0
        else:
            raise TypeError(f"Expected bool or int, got {type(level).__name__}")
        async with self._component_operation():
            if self._state is None:
                await self._initialize_state()
            tile = None if on else await self._tile_colors_for_update()
            await self._write_power(level, duration)
            if tile is not None:
                self._known_tile = dict(enumerate(tile))
                self._publish_tile(tile)
                for fields in self._component_fields:
                    self._set_stored_colors(
                        fields.name,
                        [tile[p] for p in self._component_positions(fields.name)],
                    )
        if not on:
            await self._persist_component_state()

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Set all zones, recording the completed write and restoration."""
        async with self._component_operation():
            # set_matrix_colors optimises uniform tiles through self.set_color.
            # The owning tile operation publishes state and restoration itself.
            if self._writing_tile:
                await super().set_color(color, duration)
                return
            self._observed_positions.clear()
            self._changed_positions.clear()
            try:
                await super().set_color(color, duration)
            except BaseException:
                self._pending_tile.clear()
                raise
            if self._device_chain:
                tile = [color] * self._device_chain[0].total_zones
                self._pending_tile.record(tile, duration)
                self._known_tile = dict(enumerate(tile))
            if not self._has_component_state():
                return
            for fields in self._component_fields:
                colours = [color] * len(self._component_positions(fields.name))
                self._set_component_state(fields.name, colours, stored=True)
            self._update_component_flags()
        await self._persist_component_state()

    def _adopt_tile_observation(
        self, tile_index: int, x: int, y: int, width: int, colors: list[HSBK]
    ) -> None:
        """Adopt just the reported rectangle, including partial State64 reads.

        Observations always update last-known and current colours. During our
        own transition they must not overwrite the target or restoration colours.
        Outside it, changed lit colours become restoration colours; when the
        entire side is dark, retain remembered brightness but adopt changed H/S/K.
        """
        if tile_index != 0 or not self._device_chain or not self._has_component_state():
            return
        tile = self._device_chain[0]
        if width <= 0 or x < 0 or y < 0:
            return
        observed = {}
        for offset, colour in enumerate(colors):
            row, column = y + offset // width, x + offset % width
            if row < tile.height and column < tile.width:
                observed[row * tile.width + column] = colour
        if len(self._state.tile_colors) == tile.total_zones:
            updated = list(self._state.tile_colors)
            for position, colour in observed.items():
                updated[position] = colour
            self._state.tile_colors = updated
        # Start a new pass at the origin or when rectangles repeat. A previous
        # read's tail must not complete this read's first half.
        if (x == 0 and y == 0) or self._observed_positions.intersection(observed):
            self._observed_positions.clear()
            self._changed_positions.clear()
        protected = (
            self._writing_tile
            or self._writing_power
            or self._pending_tile.get() is not None
            or self._pending_power.get() is not None
        )
        for fields in self._component_fields:
            positions = self._component_positions(fields.name)
            if not any(position in observed for position in positions):
                continue
            current = fields.read(self.state)
            if current is None or len(current) != len(positions):
                continue
            last = fields.read(self.state, "last_")
            if last is None or len(last) != len(positions):
                last = list(current)
            previous_stored = self._stored_colors(fields.name)
            for index, position in enumerate(positions):
                if position not in observed:
                    continue
                colour = observed[position]
                baseline = self._known_tile.get(position)
                if baseline is None:
                    baseline = (
                        previous_stored[index]
                        if previous_stored is not None
                        else current[index]
                    )
                    differs = not hsk_matches(baseline, colour) or (
                        not is_dark([colour]) and baseline != colour
                    )
                else:
                    differs = baseline != colour
                if not protected:
                    self._observed_positions.add(position)
                    if differs:
                        self._changed_positions.add(position)
                current[index] = colour
                last[index] = colour
            fields.write(self.state, current)
            fields.write(self.state, last, "last_")
            complete = not protected and self._observed_positions.issuperset(positions)
            if complete:
                restored = (
                    list(previous_stored)
                    if previous_stored is not None
                    else list(current)
                )
                dark = is_dark(current)
                changed = False
                for index, position in enumerate(positions):
                    if position not in self._changed_positions:
                        continue
                    changed = True
                    colour = current[index]
                    brightness = (
                        restored[index].brightness if dark else colour.brightness
                    )
                    restored[index] = HSBK(
                        colour.hue, colour.saturation, brightness, colour.kelvin
                    )
                if changed:
                    self._set_stored_colors(fields.name, restored)
                self._known_tile.update(zip(positions, current))
                self._observed_positions.difference_update(positions)
                self._changed_positions.difference_update(positions)
        self._update_component_flags()

    async def apply_theme(
        self, theme: Theme, power_on: bool = False, duration: float = 0.0
    ) -> None:
        """Retain theme behaviour without an activity-wide scheduling lock."""
        if power_on and await self._power_for_update() == 0:
            preload = duration if self._pending_power.transitioning() else 0.0
            await super().apply_theme(theme, power_on=False, duration=preload)
            await self.set_power(True, duration)
        else:
            await super().apply_theme(theme, power_on=False, duration=duration)
