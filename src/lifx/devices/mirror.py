"""LIFX Mirror Light Device.

This module provides the MirrorLight class for controlling LIFX Mirror lights
with independent front and back component control.

Terminology:
- Zone: Individual HSBK pixel in the matrix (indexed 0-49)
- Component: Logical grouping of zones, each a closed ring around the
  capsule-shaped perimeter:
  - Front Component: Zones 0-24, facing the room, for task lighting
  - Back Component: Zones 25-49, facing the wall, for indirect backwash

Unlike Ceiling lights, whose uplight is a single zone, both Mirror components
span multiple zones, so each one can carry its own gradient, theme or effect.

The fixture is driven as a 4x13 matrix: 52 Set64 buffer positions holding the
50 addressable zones, with two positions unused. Zone numbering does not match
buffer order, so component colours are gathered from and scattered to the
buffer positions recorded in the product layout. The whole buffer fits in a
single Set64 packet.

Product IDs:
- 267: Mirror (US)
- 268: Mirror (Intl)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from lifx.animation.framebuffer import FrameBuffer
from lifx.color import HSBK
from lifx.const import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT, LIFX_UDP_PORT
from lifx.devices.component.light import ComponentMatrixLight, _ComponentFields
from lifx.devices.component.participant import LightComponent
from lifx.devices.component.state import (
    colors_as_dict,
    decode_color,
    encode_color,
    read_state_file,
    write_state_file,
)
from lifx.devices.matrix import MatrixLightState
from lifx.exceptions import LifxError
from lifx.products import (
    MirrorComponentLayout,
    get_mirror_layout,
    is_mirror_product,
)

if TYPE_CHECKING:
    from lifx.theme import Theme

_LOGGER = logging.getLogger(__name__)

#: Brightness used when neither stored nor inferred brightness is available.


@dataclass
class MirrorLightState(MatrixLightState):
    """Mirror light device state with front/back component control.

    Extends MatrixLightState with mirror-specific component information.

    Attributes:
        front_colors: List of HSBK colors for each front zone
        back_colors: List of HSBK colors for each back zone
        front_is_on: Whether front component is on (any zone brightness > 0)
        back_is_on: Whether back component is on (any zone brightness > 0)
        front_positions: Set64 buffer positions of the front zones
        back_positions: Set64 buffer positions of the back zones
        stored_front_colors: Stored front colors for restoration after
            turning off
        stored_back_colors: Stored back colors for restoration after
            turning off
        last_front_colors: Last known front colors, updated after every
            operation
        last_back_colors: Last known back colors, updated after every
            operation
    """

    front_colors: list[HSBK]
    back_colors: list[HSBK]
    front_is_on: bool
    back_is_on: bool
    front_positions: tuple[int, ...]
    back_positions: tuple[int, ...]
    stored_front_colors: list[HSBK] | None = field(default=None)
    stored_back_colors: list[HSBK] | None = field(default=None)
    last_front_colors: list[HSBK] | None = field(default=None)
    last_back_colors: list[HSBK] | None = field(default=None)

    @property
    def as_dict(self) -> Any:
        """Return MirrorLightState as dict.

        The buffer position tuples are expanded into lists so the result is
        serialisable. The component colors are expanded via
        :attr:`HSBK.as_dict`; the stored and last-known fields stay None when
        unset.
        """
        state = super().as_dict
        state["front_positions"] = list(self.front_positions)
        state["back_positions"] = list(self.back_positions)
        state["front_is_on"] = self.front_is_on
        state["back_is_on"] = self.back_is_on
        state["front_colors"] = colors_as_dict(self.front_colors)
        state["back_colors"] = colors_as_dict(self.back_colors)
        state["stored_front_colors"] = colors_as_dict(self.stored_front_colors)
        state["stored_back_colors"] = colors_as_dict(self.stored_back_colors)
        state["last_front_colors"] = colors_as_dict(self.last_front_colors)
        state["last_back_colors"] = colors_as_dict(self.last_back_colors)
        return state

    @classmethod
    def from_matrix_state(
        cls,
        matrix_state: MatrixLightState,
        front_colors: list[HSBK],
        back_colors: list[HSBK],
        front_positions: tuple[int, ...],
        back_positions: tuple[int, ...],
        *,
        stored_front_colors: list[HSBK] | None = None,
        stored_back_colors: list[HSBK] | None = None,
    ) -> MirrorLightState:
        """Create MirrorLightState from MatrixLightState.

        Args:
            matrix_state: Base MatrixLightState to extend
            front_colors: Current front zone colors
            back_colors: Current back zone colors
            front_positions: Set64 buffer positions of the front zones
            back_positions: Set64 buffer positions of the back zones
            stored_front_colors: Stored front colors for restoration
            stored_back_colors: Stored back colors for restoration

        Returns:
            MirrorLightState with all matrix state plus mirror components
        """
        return cls(
            model=matrix_state.model,
            label=matrix_state.label,
            serial=matrix_state.serial,
            mac_address=matrix_state.mac_address,
            power=matrix_state.power,
            capabilities=matrix_state.capabilities,
            host_firmware=matrix_state.host_firmware,
            wifi_firmware=matrix_state.wifi_firmware,
            wifi_info=matrix_state.wifi_info,
            thread_info=matrix_state.thread_info,
            location=matrix_state.location,
            group=matrix_state.group,
            color=matrix_state.color,
            ambient_light=matrix_state.ambient_light,
            chain=matrix_state.chain,
            tile_orientations=matrix_state.tile_orientations,
            tile_colors=matrix_state.tile_colors,
            tile_count=matrix_state.tile_count,
            effect=matrix_state.effect,
            front_colors=front_colors,
            back_colors=back_colors,
            front_is_on=matrix_state.power > 0
            and any(c.brightness > 0 for c in front_colors),
            back_is_on=matrix_state.power > 0
            and any(c.brightness > 0 for c in back_colors),
            front_positions=front_positions,
            back_positions=back_positions,
            stored_front_colors=stored_front_colors,
            stored_back_colors=stored_back_colors,
            last_front_colors=list(front_colors),
            last_back_colors=list(back_colors),
            last_updated=time.time(),
        )


class MirrorLight(ComponentMatrixLight):
    """LIFX Mirror Light with independent front and back control.

    MirrorLight extends MatrixLight to provide semantic control over the front
    and back components while maintaining full backward compatibility with the
    MatrixLight API.

    Both components are multi-zone rings, so each can hold its own gradient or
    theme.

    Example:
        ```python
        from lifx.devices import MirrorLight
        from lifx.color import HSBK
        from lifx.theme import get_theme

        async with await MirrorLight.from_ip("192.168.1.100") as mirror:
            # Bright task light on the front, warm backwash behind
            await mirror.set_front_colors(
                HSBK(hue=0, saturation=0, brightness=1.0, kelvin=4500)
            )
            await mirror.set_back_colors(
                HSBK(hue=30, saturation=0.4, brightness=0.3, kelvin=2700)
            )

            # Or a different theme on each component
            await mirror.apply_front_theme(get_theme("evening"))
            await mirror.apply_back_theme(get_theme("galaxy"))

            # Turn components on/off
            await mirror.turn_back_off()
        ```
    """

    _component_fields = (
        _ComponentFields("front", "front_colors"),
        _ComponentFields("back", "back_colors"),
    )

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        state_file: str | None = None,
        *,
        fetch_wifi_info: bool = False,
        fetch_thread_info: bool = False,
        fetch_radio_info: bool = False,
        fetch_ambient_light: bool = False,
    ):
        """Initialize MirrorLight.

        ``state_file`` keeps its original position: inserting a parameter ahead
        of it would silently rebind existing positional callers. New options are
        keyword-only for the same reason.

        Args:
            serial: Device serial number
            ip: Device IP address
            port: Device UDP port (default: 56700)
            timeout: Overall timeout for network requests in seconds
            max_retries: Maximum number of retry attempts for network requests
            state_file: Optional path to JSON file for state persistence
            fetch_wifi_info: Query WiFi signal strength during state initialization
            fetch_thread_info: Query Thread mesh information during state
                initialization
            fetch_radio_info: Query whichever radio matches the device's
                evidenced connectivity during state initialization
            fetch_ambient_light: Query the ambient light sensor during state
                initialization
        """
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
        self._state_file = state_file

    async def __aenter__(self) -> MirrorLight:
        """Async context manager entry.

        Raises:
            LifxError: If device is not a supported Mirror product
        """
        await super().__aenter__()

        # Validate product ID after version is fetched
        if self.version and not is_mirror_product(self.version.product):
            raise LifxError(
                f"Product ID {self.version.product} is not a supported Mirror light."
            )

        # Load state from disk if state_file is provided
        if self._state_file:
            await self._load_state_from_file()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager, saving state to file before closing.

        Saves the current in-memory state to ``state_file`` (when set) before
        delegating to the parent ``close()`` via ``super().__aexit__()``. The
        save runs in a worker thread via ``asyncio.to_thread`` so the file I/O
        never blocks the event loop. Ordinary I/O failures are logged as a
        WARNING and swallowed by the inner ``except Exception``. The save is
        wrapped in ``try/finally`` so the parent cleanup always runs — even if
        cancellation (``asyncio.CancelledError``, a ``BaseException`` that the
        inner handler deliberately does not catch) lands while the threaded
        save is pending. The original body exception (if any) is never replaced
        or suppressed.
        """
        try:
            if self._state_file:
                try:
                    await self._save_state_to_file()
                except Exception as e:
                    _LOGGER.warning(
                        "Failed to save state on __aexit__ for %s: %s",
                        self.serial,
                        e,
                    )
        finally:
            await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _initialize_state(self) -> MirrorLightState:
        """Initialize mirror light state transactionally.

        Extends MatrixLight implementation to add mirror component state.

        Returns:
            MirrorLightState instance with all device, light, matrix, and
            mirror component information.

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        matrix_state = await super()._initialize_state()

        # Extract mirror component colors from already-fetched tile_colors
        # (parent _initialize_state already called get_all_tile_colors)
        tile_colors = matrix_state.tile_colors
        front_colors = _gather(tile_colors, self.front_positions)
        back_colors = _gather(tile_colors, self.back_positions)

        mirror_state = MirrorLightState.from_matrix_state(
            matrix_state=matrix_state,
            front_colors=front_colors,
            back_colors=back_colors,
            front_positions=self.front_positions,
            back_positions=self.back_positions,
        )

        self._state = mirror_state

        return mirror_state

    async def refresh_state(self) -> None:
        """Refresh mirror light state from hardware.

        Fetches color, tiles, tile colors, effect, and mirror component state.

        Raises:
            RuntimeError: If state has not been initialized
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        await super().refresh_state()

        # Extract mirror component colors from already-fetched tile_colors
        # (parent refresh_state already called get_all_tile_colors)
        tile_colors = self._state.tile_colors
        front_colors = _gather(tile_colors, self.front_positions)
        back_colors = _gather(tile_colors, self.back_positions)

        state = cast(MirrorLightState, self._state)
        state.front_colors = list(front_colors)
        state.back_colors = list(back_colors)
        state.last_front_colors = list(front_colors)
        state.last_back_colors = list(back_colors)
        state.front_is_on = bool(
            state.power > 0 and any(c.brightness > 0 for c in front_colors)
        )
        state.back_is_on = bool(
            state.power > 0 and any(c.brightness > 0 for c in back_colors)
        )

    @classmethod
    async def from_ip(
        cls,
        ip: str,
        port: int = LIFX_UDP_PORT,
        serial: str | None = None,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        *,
        fetch_wifi_info: bool = False,
        fetch_thread_info: bool = False,
        fetch_radio_info: bool = False,
        fetch_ambient_light: bool = False,
        state_file: str | None = None,
    ) -> MirrorLight:
        """Create MirrorLight from IP address.

        Args:
            ip: Device IP address
            port: Port number (default LIFX_UDP_PORT)
            serial: Serial number as 12-digit hex string
            timeout: Request timeout for this device instance
            max_retries: Maximum number of retries for requests
            fetch_wifi_info: Query WiFi signal strength during state initialization
            fetch_thread_info: Query Thread mesh information during state
                initialization
            fetch_radio_info: Query whichever radio matches the device's
                evidenced connectivity during state initialization
            fetch_ambient_light: Query the ambient light sensor during state
                initialization
            state_file: Optional path to JSON file for state persistence

        Returns:
            MirrorLight instance

        Raises:
            LifxDeviceNotFoundError: Device not found at IP
            LifxTimeoutError: Device did not respond
            LifxError: Device is not a supported Mirror product
        """
        # Parent factory constructs via cls(...), so this is already a fully
        # configured MirrorLight — only state_file needs setting
        device = await super().from_ip(
            ip,
            port,
            serial,
            timeout,
            max_retries,
            fetch_wifi_info=fetch_wifi_info,
            fetch_thread_info=fetch_thread_info,
            fetch_radio_info=fetch_radio_info,
            fetch_ambient_light=fetch_ambient_light,
        )
        device._state_file = state_file
        return device

    @property
    def state(self) -> MirrorLightState:
        """Get Mirror light state.

        Returns:
            MirrorLightState with current state information.

        Raises:
            RuntimeError: If accessed before state initialization.
        """
        if self._state is None:
            raise RuntimeError("State not found.")
        return cast(MirrorLightState, self._state)

    @property
    def layout(self) -> MirrorComponentLayout:
        """Component layout for this Mirror product.

        Returns:
            MirrorComponentLayout describing the matrix and both components

        Raises:
            LifxError: If device version is not available or not a Mirror
        """
        if not self.version:
            raise LifxError("Device version not available. Use async context manager.")

        layout = get_mirror_layout(self.version.product)
        if not layout:
            raise LifxError(f"Product ID {self.version.product} is not a Mirror light")

        return layout

    def _component_positions(self, component: str) -> tuple[int, ...]:
        """Get the Set64 buffer positions for a component, in zone order.

        Args:
            component: Either "front" or "back"

        Returns:
            Buffer positions of the component's zones

        Raises:
            LifxError: If device version is not available or not a Mirror
        """
        layout = self.layout

        return layout.front_positions if component == "front" else layout.back_positions

    def _component_canvas(
        self, component: str, light_canvas: FrameBuffer
    ) -> tuple[FrameBuffer, tuple[int, ...]]:
        """Draw a ring's effect on the ring itself: Nx1 in zone order.

        Frame pixel k lands on the ring's k-th buffer position, so a pattern
        travels round the ring in zone order.
        """
        count = len(self._component_positions(component))
        canvas = FrameBuffer(pixel_count=count, canvas_width=count, canvas_height=1)
        return canvas, tuple(range(count))

    def _component_wraps(self, _component: str) -> bool:
        """Each Mirror light component is a closed ring, so its canvas wraps."""
        return True

    @property
    def front(self) -> LightComponent:
        """The front ring as an effect participant.

        It carries ``start_effect()``, ``stop_effect()`` and ``animator``. A
        software effect started on it draws on the ring: 25 pixels in zone
        order that wrap, so zone 24 sits next to zone 0. The back keeps its
        colours and stays under the existing back methods. Reading it changes
        nothing.

        Example:
            ```python
            await mirror.front.start_effect(EffectRainbow())
            ```
        """
        return self._light_component("front")

    @property
    def back(self) -> LightComponent:
        """The back ring as an effect participant.

        It carries ``start_effect()``, ``stop_effect()`` and ``animator``. A
        software effect started on it draws on the ring: 25 pixels in zone
        order that wrap. The front keeps its colours and stays under the
        existing front methods. Reading it changes nothing.

        Example:
            ```python
            await mirror.back.start_effect(EffectColorloop())
            ```
        """
        return self._light_component("back")

    @property
    def front_positions(self) -> tuple[int, ...]:
        """Set64 buffer positions of the front zones, in zone order.

        Zone numbering does not match buffer order, so component colours are
        gathered from and scattered to these positions.

        Returns:
            Buffer positions of the 25 front zones

        Raises:
            LifxError: If device version is not available or not a Mirror
        """
        return self._component_positions("front")

    @property
    def back_positions(self) -> tuple[int, ...]:
        """Set64 buffer positions of the back zones, in zone order.

        Returns:
            Buffer positions of the 25 back zones

        Raises:
            LifxError: If device version is not available or not a Mirror
        """
        return self._component_positions("back")

    @property
    def front_zone_count(self) -> int:
        """Number of front zones.

        Returns:
            Zone count (25 for both Mirror products)

        Raises:
            LifxError: If device version is not available or not a Mirror
        """
        return len(self.front_positions)

    @property
    def back_zone_count(self) -> int:
        """Number of back zones.

        Returns:
            Zone count (25 for both Mirror products)

        Raises:
            LifxError: If device version is not available or not a Mirror
        """
        return len(self.back_positions)

    @property
    def front_is_on(self) -> bool:
        """True if front component is currently on.

        Calculated as: power_level > 0 AND any front zone brightness > 0

        Note:
            Requires recent data from device. Call refresh_state() to update
            cached values before checking this property.

        Returns:
            True if front component is on, False otherwise
        """
        return self._component_is_on("front")

    @property
    def back_is_on(self) -> bool:
        """True if back component is currently on.

        Calculated as: power_level > 0 AND any back zone brightness > 0

        Note:
            Requires recent data from device. Call refresh_state() to update
            cached values before checking this property.

        Returns:
            True if back component is on, False otherwise
        """
        return self._component_is_on("back")

    def _component_is_on(self, component: str) -> bool:
        """Check whether a component has any lit zone.

        Args:
            component: Either "front" or "back"

        Returns:
            True if the device is powered and any component zone is lit
        """
        if self._state is None or self._state.power == 0:
            return False

        state = cast(MirrorLightState, self._state)
        last_colors = (
            state.last_front_colors if component == "front" else state.last_back_colors
        )
        if last_colors is None:
            return False

        return any(c.brightness > 0 for c in last_colors)

    async def get_front_colors(self) -> list[HSBK]:
        """Get current front component colors from device.

        Returns:
            List of HSBK colors, one per front zone

        Raises:
            LifxTimeoutError: Device did not respond
        """
        return await self._get_component_colors("front")

    async def get_back_colors(self) -> list[HSBK]:
        """Get current back component colors from device.

        Returns:
            List of HSBK colors, one per back zone

        Raises:
            LifxTimeoutError: Device did not respond
        """
        return await self._get_component_colors("back")

    async def _get_component_colors(self, component: str) -> list[HSBK]:
        """Fetch the current colors of one component.

        Args:
            component: Either "front" or "back"

        Returns:
            List of HSBK colors for the component's zones
        """
        all_colors = await self.get_all_tile_colors()
        tile_colors = all_colors[0]

        return _gather(tile_colors, self._component_positions(component))

    async def set_front_colors(
        self, colors: HSBK | list[HSBK], duration: float = 0.0
    ) -> None:
        """Set front component colors.

        Args:
            colors: Either:

                - Single HSBK: sets all front zones to same color
                - List[HSBK]: sets each zone individually (must match zone count)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If every color has brightness == 0 (use
                turn_front_off instead)
            ValueError: If list length doesn't match front zone count
            LifxTimeoutError: Device did not respond

        Note:
            Also updates stored state for future restoration.
        """
        await self._set_component_colors("front", colors, duration)

    async def set_back_colors(
        self, colors: HSBK | list[HSBK], duration: float = 0.0
    ) -> None:
        """Set back component colors.

        Args:
            colors: Either:

                - Single HSBK: sets all back zones to same color
                - List[HSBK]: sets each zone individually (must match zone count)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If every color has brightness == 0 (use
                turn_back_off instead)
            ValueError: If list length doesn't match back zone count
            LifxTimeoutError: Device did not respond

        Note:
            Also updates stored state for future restoration.
        """
        await self._set_component_colors("back", colors, duration)

    async def turn_front_on(
        self, colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
    ) -> None:
        """Turn front component on.

        If the entire light is off, this sets the colors instantly and then
        turns the light on with the requested duration, so it fades to the
        target colors instead of flashing to its previous state.

        Args:
            colors: Optional colors. Can be:

                - None: uses brightness determination logic
                - Single HSBK: sets all front zones to same color
                - List[HSBK]: sets each zone individually (must match zone count)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If every color has brightness == 0
            ValueError: If list length doesn't match front zone count
            LifxTimeoutError: Device did not respond
        """
        await self._turn_component_on("front", colors, duration)

    async def turn_back_on(
        self, colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
    ) -> None:
        """Turn back component on.

        If the entire light is off, this sets the colors instantly and then
        turns the light on with the requested duration, so it fades to the
        target colors instead of flashing to its previous state.

        Args:
            colors: Optional colors. Can be:

                - None: uses brightness determination logic
                - Single HSBK: sets all back zones to same color
                - List[HSBK]: sets each zone individually (must match zone count)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If every color has brightness == 0
            ValueError: If list length doesn't match back zone count
            LifxTimeoutError: Device did not respond
        """
        await self._turn_component_on("back", colors, duration)

    async def turn_front_off(
        self, colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
    ) -> None:
        """Turn front component off.

        Args:
            colors: Optional colors to store for future turn_on. Can be:

                - None: stores current colors from device
                - Single HSBK: stores this color for all zones
                - List[HSBK]: stores individual colors (must match zone count)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If every color has brightness == 0
            ValueError: If list length doesn't match front zone count
            LifxTimeoutError: Device did not respond

        Note:
            Sets front zone brightness to 0 on device while preserving H, S, K.
            If the back component is already off, the entire device is
            powered off instead and the front zones keep their brightness, so
            a later set_power(True) brings the front back rather than turning
            on a light with every zone at zero brightness.
        """
        await self._turn_component_off("front", colors, duration)

    async def turn_back_off(
        self, colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
    ) -> None:
        """Turn back component off.

        Args:
            colors: Optional colors to store for future turn_on. Can be:

                - None: stores current colors from device
                - Single HSBK: stores this color for all zones
                - List[HSBK]: stores individual colors (must match zone count)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If every color has brightness == 0
            ValueError: If list length doesn't match back zone count
            LifxTimeoutError: Device did not respond

        Note:
            Sets back zone brightness to 0 on device while preserving H, S, K.
            If the front component is already off, the entire device is
            powered off instead and the back zones keep their brightness, so
            a later set_power(True) brings the back back rather than turning
            on a light with every zone at zero brightness.
        """
        await self._turn_component_off("back", colors, duration)

    async def apply_front_theme(
        self, theme: Theme, power_on: bool = False, duration: float = 0.0
    ) -> None:
        """Apply a theme across the front component only.

        Args:
            theme: Theme to apply
            power_on: Turn on the light
            duration: Transition duration in seconds

        Raises:
            LifxTimeoutError: Device did not respond

        Example:
            ```python
            from lifx.theme import get_theme

            await mirror.apply_front_theme(get_theme("evening"), power_on=True)
            ```
        """
        await self._apply_component_theme("front", theme, power_on, duration)

    async def apply_back_theme(
        self, theme: Theme, power_on: bool = False, duration: float = 0.0
    ) -> None:
        """Apply a theme across the back component only.

        Args:
            theme: Theme to apply
            power_on: Turn on the light
            duration: Transition duration in seconds

        Raises:
            LifxTimeoutError: Device did not respond

        Example:
            ```python
            from lifx.theme import get_theme

            await mirror.apply_back_theme(get_theme("galaxy"), power_on=True)
            ```
        """
        await self._apply_component_theme("back", theme, power_on, duration)

    async def _apply_component_theme(
        self, component: str, theme: Theme, power_on: bool, duration: float
    ) -> None:
        """Render a theme across the matrix and keep one component's zones.

        The theme is rendered over the whole 4x13 matrix with the matrix
        generator, so the palette is distributed with the same Canvas
        splotches as any other matrix device, then the component's buffer
        positions are picked out of the result. The whole buffer fits in a
        single Set64, so the write is one packet.

        Args:
            component: Either "front" or "back"
            theme: Theme to apply
            power_on: Turn on the light
            duration: Transition duration in seconds
        """
        from lifx.theme.generators import MatrixGenerator

        layout = self.layout
        generator = MatrixGenerator([((0, 0), (layout.width, layout.height))])
        rendered = generator.get_theme_colors(theme)[0]

        colors = _gather(rendered, self._component_positions(component))

        # Turning on goes through the same path as turn_front_on() and
        # turn_back_on(): from off, the theme is loaded while the light is
        # dark, the other component is zeroed so it stays off, and the power
        # fades up
        if power_on:
            await self._turn_component_on(component, colors, duration)
        else:
            await self._set_component_colors(component, colors, duration)

    async def set_power(self, level: bool | int, duration: float = 0.0) -> None:
        """Set light power state, capturing component colors before turning off.

        Overrides Light.set_power() to capture the current front and back
        colors before turning off the entire light. This allows subsequent
        calls to turn_front_on() or turn_back_on() to restore the colors that
        were active just before the light was turned off.

        The captured colors preserve hue, saturation, and kelvin values even if
        a component was already off (brightness=0). The brightness will be
        determined at turn-on time using the standard brightness inference
        logic.

        Args:
            level: True/65535 to turn on, False/0 to turn off
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If integer value is not 0 or 65535
            TypeError: If level is neither bool nor int
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Turn off entire mirror (captures colors for later)
            await mirror.set_power(False)

            # Later, turn on just the back light with its previous colors
            await mirror.turn_back_on()
            ```
        """
        await super().set_power(level, duration)

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Set light color, updating component state tracking.

        Overrides Light.set_color() to track the color change in the mirror
        light's component state. When set_color() is called, all zones (front
        and back) are set to the same color. This override ensures the cached
        component colors stay in sync so subsequent component control methods
        use the correct color values.

        Args:
            color: HSBK color to set for the entire light
            duration: Transition duration in seconds (default 0.0)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            from lifx.color import HSBK

            # Set the whole mirror to warm white
            await mirror.set_color(
                HSBK(hue=0, saturation=0, brightness=1.0, kelvin=2700)
            )
            ```
        """
        await super().set_color(color, duration)

    async def _load_state_from_file(self) -> None:
        """Load state from JSON file.

        The read runs in a worker thread via ``asyncio.to_thread`` so the file
        I/O never blocks the event loop; the parsed data is applied to state
        back on the loop. Handles a missing file, malformed contents and JSON
        errors gracefully.
        """
        if not self._state_file:
            return

        try:
            exists, data = await asyncio.to_thread(read_state_file, self._state_file)

            if not exists:
                _LOGGER.debug("State file does not exist: %s", self._state_file)
                return

            if not isinstance(data, dict):
                # A file that parses but is not an object (``null`` after a
                # truncated write, a bare list) is corruption, not absence
                _LOGGER.warning(
                    "State file %s does not contain a JSON object (found %s)",
                    self._state_file,
                    type(data).__name__,
                )
                return

            device_state = data.get(self.serial)
            if not device_state:
                _LOGGER.debug("No state found for device %s", self.serial)
                return

            for component in ("front", "back"):
                if component not in device_state:
                    continue

                loaded_colors = [decode_color(c) for c in device_state[component]]
                try:
                    expected = (
                        self.front_zone_count
                        if component == "front"
                        else self.back_zone_count
                    )
                except LifxError:
                    # Version not yet available — accept loaded data
                    self._set_stored_colors(component, loaded_colors)
                    continue

                if len(loaded_colors) == expected:
                    self._set_stored_colors(component, loaded_colors)
                else:
                    _LOGGER.warning(
                        "Ignoring stored %s state: expected %d zones, got %d",
                        component,
                        expected,
                        len(loaded_colors),
                    )

            _LOGGER.debug(
                "Loaded state from %s for device %s", self._state_file, self.serial
            )

        except Exception as e:
            _LOGGER.warning("Failed to load state from %s: %s", self._state_file, e)

    async def _save_state_to_file(self) -> None:
        """Save state to JSON file.

        The read-merge-write cycle runs in a worker thread via
        ``asyncio.to_thread`` so the file I/O never blocks the event loop. The
        thread holds the state file's lock for the whole cycle, so devices
        sharing a file within this process cannot drop each other's entries —
        and cancelling this coroutine cannot free the lock mid-write. Handles
        file I/O errors gracefully.
        """
        if not self._state_file:
            return

        try:
            # Build this device's entry; write_state_file merges it into any
            # existing on-disk entry
            device_state: dict[str, Any] = {}
            state = self.state

            if state.stored_front_colors:
                device_state["front"] = [
                    encode_color(c) for c in state.stored_front_colors
                ]

            if state.stored_back_colors:
                device_state["back"] = [
                    encode_color(c) for c in state.stored_back_colors
                ]

            # A stored colour deliberately reset leaves the file too
            device_state.update(self._unset_state_entries())

            await asyncio.to_thread(
                write_state_file, self._state_file, self.serial, device_state
            )
            self._saved_state_entries(device_state)

            _LOGGER.debug(
                "Saved state to %s for device %s", self._state_file, self.serial
            )

        except Exception as e:
            _LOGGER.warning("Failed to save state to %s: %s", self._state_file, e)

    def __repr__(self) -> str:
        """String representation of mirror light."""
        return f"MirrorLight(serial={self.serial}, ip={self.ip}, port={self.port})"


def _gather(buffer: list[HSBK], positions: tuple[int, ...]) -> list[HSBK]:
    """Read a component's colors out of a Set64 buffer.

    Args:
        buffer: Colors for every buffer position on the tile
        positions: Buffer positions to read, in zone order

    Returns:
        One color per position, in the same order

    Raises:
        LifxError: If the buffer is shorter than the layout requires
    """
    if positions and max(positions) >= len(buffer):
        raise LifxError(
            f"Device returned {len(buffer)} zones, too few for the component layout"
        )

    return [buffer[position] for position in positions]
