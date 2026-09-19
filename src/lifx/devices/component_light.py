"""Shared base for matrix lights split into independently controlled components.

Ceiling and Mirror lights both drive two logical components from one tile. The
firmware runs one transition per tile, reports in-flight colours while a fade
runs, and keeps reporting the old power level until a power fade finishes, so a
component write built from what the device reports can freeze or undo the
other component's fade. This class keeps track of what it last wrote until the
device catches up; see :class:`~lifx.devices.component_state.Pending`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT, LIFX_UDP_PORT
from lifx.devices.component_state import Pending
from lifx.devices.matrix import MatrixLight

if TYPE_CHECKING:
    from lifx.theme import Theme

_POWER_ON = 65535


class ComponentMatrixLight(MatrixLight):
    """Matrix light whose tile carries two independently controlled components.

    Not used directly: :class:`~lifx.devices.ceiling.CeilingLight` and
    :class:`~lifx.devices.mirror.MirrorLight` build their component API on it.
    """

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
        """Initialize the component light.

        See :class:`~lifx.devices.base.Device` for parameter documentation.
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
        self._pending_tile: Pending[list[HSBK]] = Pending()
        self._pending_power: Pending[int] = Pending()

    def _zones_changed(self) -> None:
        """Forget the remembered tile after an inherited colour write.

        set64(), copy_frame_buffer(), set_effect(), set_color() and the
        waveform methods all call this, so a later component write rebuilds
        from the device rather than undoing their change.
        """
        self._pending_tile.clear()

    async def _tile_colors_for_update(self) -> list[HSBK]:
        """Get the tile as the base for a component write.

        While the last write is still transitioning this is that write's
        target rather than the device's in-flight colours, so the untouched
        component keeps heading where it was going.

        Returns:
            Colors for every zone on the tile
        """
        pending = self._pending_tile.get()
        if pending is not None:
            return pending

        all_colors = await self.get_all_tile_colors()
        return all_colors[0]

    async def _write_tile(self, tile_colors: list[HSBK], duration: float) -> None:
        """Write the whole tile and remember it until the transition settles.

        Args:
            tile_colors: Colors for every zone on the tile
            duration: Transition duration in seconds
        """
        await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))
        self._pending_tile.record(tile_colors, duration)

    async def _power_for_update(self) -> int:
        """Get the power level, trusting this device's own recent change.

        GetPower reports the old level until a power-off fade has finished,
        and for a moment after any SetPower, so a component method that has
        just powered the light off must not ask the device whether it is on.
        A power-off is trusted for its whole fade: if the light was switched
        back on elsewhere meanwhile, the "light is off" path still powers it
        on. A power-on is trusted only for the settle margin, since the
        device reports it straight away. The result is stored in state.power.

        Returns:
            Power level, 0 or 65535
        """
        pending = self._pending_power.get()
        power = pending if pending is not None else await self.get_power()
        if self._state is not None:
            self._state.power = power
        return power

    def _record_power(self, on: bool, duration: float) -> None:
        """Remember a power change until the device reports it.

        Args:
            on: True if the light was powered on
            duration: Transition duration in seconds
        """
        if on:
            self._pending_power.record(_POWER_ON, duration, trust_for_duration=False)
        else:
            self._pending_power.record(0, duration)

    async def _write_power(self, on: bool, duration: float) -> None:
        """Set the power level and remember it until it settles.

        Calls Light.set_power() directly, bypassing the component classes'
        override, which captures component colours on the way down.

        Args:
            on: True to power on, False to power off
            duration: Transition duration in seconds
        """
        await super().set_power(on, duration)
        self._record_power(on, duration)

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Set every zone to one color, remembering it until the fade settles.

        Args:
            color: HSBK color to set for the entire light
            duration: Transition duration in seconds (default 0.0)
        """
        await super().set_color(color, duration)

        # A component call made during this fade must carry the new colour,
        # not the in-flight one, or it would freeze the fade part way
        if self._device_chain:
            tile_size = self._device_chain[0].total_zones
            self._pending_tile.record([color] * tile_size, duration)

    async def apply_theme(
        self,
        theme: Theme,
        power_on: bool = False,
        duration: float = 0.0,
    ) -> None:
        """Apply a theme across the whole matrix, both components included.

        Overrides MatrixLight.apply_theme() only to decide whether the light
        is on using this device's own recent power change, since GetPower
        still reports on while a power-off is fading.

        Args:
            theme: Theme to apply
            power_on: Turn on the light
            duration: Transition duration in seconds
        """
        if power_on and await self._power_for_update() == 0:
            # Load the theme while the light is dark, then fade the power up.
            # If a power-off is still fading the light is visibly lit, so the
            # theme fades in too rather than snapping.
            preload = duration if self._pending_power.transitioning() else 0.0
            await super().apply_theme(theme, power_on=False, duration=preload)
            await self.set_power(True, duration)
        else:
            await super().apply_theme(theme, power_on=False, duration=duration)
