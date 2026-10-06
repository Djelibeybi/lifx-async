"""Two separate colour loops on one Ceiling share its tile without stalling.

Neither loop streams, so neither may wait for the other's frames to carry
its slot: each sends the tile at its own steps, carrying the other's target.
"""

from __future__ import annotations

import struct

import pytest

from lifx.animation.animator import AnimatorWriter
from lifx.animation.flow import AckGate
from lifx.animation.packets import HEADER_SIZE
from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.devices.component.effect_support import component_writer
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.frame_effect import FrameContext
from tests.test_animation.conftest import MockUdpSocket
from tests.test_animation.test_component_slots import _ceiling


def _loop(change: float = 10) -> EffectColorloop:
    """A colour loop turning 10 degrees a second, in steps of ``change``."""
    effect = EffectColorloop(period=36, change=change)
    effect._initial_colors = [
        HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
    ]
    effect._direction = 1
    return effect


def _hue_at(elapsed: float) -> int:
    """The protocol hue _loop() shows at a moment."""
    return HSBK(round(120 + elapsed * 10) % 360, 0.9, 0.8, 3500).as_tuple()[0]


class TestTwoColourLoopsOnOneTile:
    """Two separate colour loops on a Ceiling's two light components."""

    @staticmethod
    async def _loops(
        ceiling: CeilingLight,
    ) -> tuple[EffectColorloop, AnimatorWriter, EffectColorloop, AnimatorWriter]:
        up_writer = await component_writer(ceiling, "uplight", 75)
        down_writer = await component_writer(ceiling, "downlight", 75)
        up, down = _loop(), _loop()
        for effect, writer in ((up, up_writer), (down, down_writer)):
            effect.participants = [ceiling]
            effect._animators = [writer]
        return up, up_writer, down, down_writer

    @staticmethod
    def _frame(
        effect: EffectColorloop, writer: AnimatorWriter, elapsed: float
    ) -> tuple[list[tuple[int, int, int, int]], FrameContext]:
        ctx = FrameContext(
            elapsed_s=elapsed,
            device_index=0,
            pixel_count=writer.pixel_count,
            canvas_width=writer.canvas_width,
            canvas_height=writer.canvas_height,
        )
        return [c.as_tuple() for c in effect.generate_frame(ctx)], ctx

    def _tick(self, loops: tuple, elapsed: float) -> None:  # type: ignore[type-arg]
        up, up_writer, down, down_writer = loops
        for effect, writer in ((up, up_writer), (down, down_writer)):
            frame, ctx = self._frame(effect, writer, elapsed)
            effect._deliver(0, writer, frame, ctx, False)

    @staticmethod
    def _sent_durations(udp: MockUdpSocket) -> list[int]:
        return [
            struct.unpack_from("<I", bytes(c.args[0]), HEADER_SIZE + 6)[0]
            for c in udp.sock.sendto.call_args_list
        ]

    async def test_each_loop_sends_its_own_steps(
        self, mock_udp_socket: MockUdpSocket, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(AckGate, "gated", property(lambda _self: False))
        ceiling = _ceiling()
        loops = await self._loops(ceiling)

        for elapsed in (0.0, 0.05, 0.5, 1.0):
            self._tick(loops, elapsed)

        durations = self._sent_durations(mock_udp_socket)
        assert len(durations) == 4
        assert all(duration > 75 for duration in durations)
        tile = struct.unpack_from(
            "<256H",
            bytes(mock_udp_socket.sock.sendto.call_args.args[0]),
            HEADER_SIZE + 10,
        )
        assert tile[63 * 4] == _hue_at(2.0)
        assert tile[0] == _hue_at(2.0)

    async def test_neither_loop_streams_a_held_fade_on_thread(
        self, mock_udp_socket: MockUdpSocket, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(AckGate, "gated", property(lambda _self: False))
        ceiling = _ceiling()
        ceiling.connection._adopt_thread_connection(True)
        loops = await self._loops(ceiling)
        hold = ceiling.animator._held_tile()
        assert hold is not None
        ceiling.animator._retarget_hold(hold, 2.0)

        for elapsed in (0.0, 0.05, 0.1, 0.5):
            self._tick(loops, elapsed)

        durations = self._sent_durations(mock_udp_socket)
        assert durations
        assert all(duration > 75 for duration in durations)

    async def test_unequal_steps_carry_each_others_fade_as_of_the_tiles_end(
        self, mock_udp_socket: MockUdpSocket, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 1 s uplight step carries a 4 s downlight step only part-way.

        The downlight fades 120 to 160 degrees over 4 s. The uplight's write
        at 1 s ends at 2 s, so it carries the downlight at 140 degrees, not at
        the 160 it is heading for.
        """
        monkeypatch.setattr(AckGate, "gated", property(lambda _self: False))
        clock = [1000.0]
        monkeypatch.setattr("lifx.animation.slots.time.monotonic", lambda: clock[0])
        monkeypatch.setattr("lifx.animation.animator.time.monotonic", lambda: clock[0])
        ceiling = _ceiling()
        up_writer = await component_writer(ceiling, "uplight", 75)
        down_writer = await component_writer(ceiling, "downlight", 75)
        up, down = _loop(change=10), _loop(change=40)
        for effect, writer in ((up, up_writer), (down, down_writer)):
            effect.participants = [ceiling]
            effect._animators = [writer]
        loops = (up, up_writer, down, down_writer)

        for elapsed in (0.0, 0.05, 1.0):
            clock[0] = 1000.0 + elapsed
            self._tick(loops, elapsed)

        tile = struct.unpack_from(
            "<256H",
            bytes(mock_udp_socket.sock.sendto.call_args.args[0]),
            HEADER_SIZE + 10,
        )
        expected = HSBK(140, 0.9, 0.8, 3500).as_tuple()[0]
        assert abs(tile[0] - expected) <= 1
        assert tile[63 * 4] == _hue_at(2.0)
