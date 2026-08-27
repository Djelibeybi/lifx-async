"""End-to-end IPv6 tests against an emulator bound to ``::1``.

Scope is deliberately exactly the control path on a single ``Light``:
connect, ``get_color()``, ``set_color()``, ``set_power()``, plus one
``Animator`` frame-delivery run. Every other device class reaches the
network through the same connection, so re-running them over IPv6 would
test the same code a second time.

Every emulator-backed test in this module asserts the address family of the
socket the call actually used. Without that, a regression that quietly sent
these tests back over IPv4 would leave them green, and the suite would go on
reporting IPv6 coverage it no longer had.

The loopback warning fires on every ``::1`` request, exactly as it already
does for the ``127.0.0.1`` emulator suite. That is left alone: it is genuinely
useful in production, where a LIFX device is never on loopback.
"""

from __future__ import annotations

import asyncio
import socket

import pytest
from lifx_emulator import EmulatedLifxServer

from lifx.animation.animator import Animator
from lifx.animation.framebuffer import FrameBuffer
from lifx.animation.packets import MatrixPacketGenerator
from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.protocol.models import Serial
from tests.conftest import IPV6_DEVICE_SERIAL, ipv6_probe_outcome

# The emulated Tile is 8x8, so one Set64 packet carries a whole frame.
_TILE_WIDTH = 8
_TILE_HEIGHT = 8
_PIXEL_COUNT = _TILE_WIDTH * _TILE_HEIGHT

# Bounded poll for the frame readback. UDP may drop a datagram on loopback,
# so the same frame is offered repeatedly rather than asserted once.
_FRAME_ATTEMPTS = 40
_FRAME_INTERVAL = 0.05


def connection_socket_family(light: Light) -> socket.AddressFamily:
    """Return the address family of the socket a device connection opened.

    Read off the real socket rather than off ``UdpTransport._family``. The
    recorded family is what ``open()`` asked for; the socket is what it got,
    and only the second can prove which family the request actually went out
    over.
    """
    udp_transport = light.connection._transport
    assert udp_transport is not None, "the device connection has no transport"

    endpoint = udp_transport._transport
    assert endpoint is not None, "the transport has no asyncio endpoint"

    sock = endpoint.get_extra_info("socket")
    assert sock is not None, "the asyncio endpoint exposes no socket"

    return sock.family


class TestIpv6EndToEnd:
    """The SPEC control path, exercised against a real ``AF_INET6`` endpoint."""

    @pytest.mark.emulator
    async def test_connect_over_ipv6(self, ipv6_light: Light) -> None:
        """Entering the context manager opens an AF_INET6 connection.

        ``__aenter__`` runs the full state initialisation, so this is a
        multi-request round trip and not merely a socket construction.
        """
        async with ipv6_light:
            assert ipv6_light.state is not None
            assert connection_socket_family(ipv6_light) == socket.AF_INET6

    @pytest.mark.emulator
    async def test_get_color_over_ipv6(self, ipv6_light: Light) -> None:
        """A state read returns the (color, power, label) triple over IPv6."""
        async with ipv6_light:
            color, power, label = await ipv6_light.get_color()

            assert isinstance(color, HSBK)
            assert power in (0, 65535)
            assert label

            assert connection_socket_family(ipv6_light) == socket.AF_INET6

    @pytest.mark.emulator
    async def test_set_color_over_ipv6(self, ipv6_light: Light) -> None:
        """A colour write reaches the device and the read-back shows it.

        The target is derived from the pre-write reading rather than
        hardcoded. A fixed colour can silently coincide with the emulator's
        default, and then the assertion passes whether or not the write ever
        left this machine.
        """
        async with ipv6_light:
            before, _, _ = await ipv6_light.get_color()

            target = HSBK(
                hue=(before.hue + 137.0) % 360.0,
                saturation=0.75 if before.saturation < 0.5 else 0.25,
                brightness=0.9 if before.brightness < 0.5 else 0.4,
                kelvin=2500 if before.kelvin != 2500 else 4000,
            )
            await ipv6_light.set_color(target)

            after, _, _ = await ipv6_light.get_color()

            # uint16 quantisation on the wire, so compare with tolerance.
            assert after.hue == pytest.approx(target.hue, abs=0.01)
            assert after.saturation == pytest.approx(target.saturation, abs=1e-4)
            assert after.brightness == pytest.approx(target.brightness, abs=1e-4)
            assert after.kelvin == target.kelvin

            # The write changed something, so the read-back is not just the
            # state the device already held.
            assert (after.hue, after.saturation, after.brightness, after.kelvin) != (
                before.hue,
                before.saturation,
                before.brightness,
                before.kelvin,
            )

            assert connection_socket_family(ipv6_light) == socket.AF_INET6

    @pytest.mark.emulator
    async def test_set_power_over_ipv6(self, ipv6_light: Light) -> None:
        """A power write toggles the device and reads back over IPv6.

        The original level is restored so the session-scoped device is left
        as it was found, and the toggle target is derived from the current
        level rather than assumed.
        """
        async with ipv6_light:
            before = await ipv6_light.get_power()
            target = 0 if before else 65535

            await ipv6_light.set_power(target)
            assert await ipv6_light.get_power() == target

            await ipv6_light.set_power(before)
            assert await ipv6_light.get_power() == before

            assert connection_socket_family(ipv6_light) == socket.AF_INET6

    @pytest.mark.emulator
    async def test_animator_delivers_frames_over_ipv6(
        self, emulator_server_ipv6: tuple[int, EmulatedLifxServer]
    ) -> None:
        """Frames reach the device over IPv6 and are applied to its state.

        ``send_frame()`` increments its packet statistics immediately after
        ``sendto()``, so a send-side count proves only that a datagram was
        handed to the kernel. This reads the emulated device's own tile
        state back instead, which can only change if the frame arrived and
        was parsed.
        """
        port, server = emulator_server_ipv6

        emulated = server.get_device(IPV6_DEVICE_SERIAL)
        assert emulated is not None, "the ::1 emulator is not hosting its device"

        before = emulated.state.tile_devices[0]["colors"][0]
        # Derived from the pre-write reading, for the same reason the
        # set_color target is: a fixed colour can coincide with the state
        # already there and prove nothing.
        target = (
            (before.hue + 12345) % 65536,
            (before.saturation + 23456) % 65536,
            (before.brightness + 7777) % 65536,
            2750 if before.kelvin != 2750 else 4250,
        )

        animator = Animator(
            ip="::1",
            serial=Serial.from_string(IPV6_DEVICE_SERIAL),
            framebuffer=FrameBuffer(pixel_count=_PIXEL_COUNT),
            packet_generator=MatrixPacketGenerator(
                tile_count=1, tile_width=_TILE_WIDTH, tile_height=_TILE_HEIGHT
            ),
            port=port,
        )
        frame: list[tuple[int, int, int, int]] = [target] * _PIXEL_COUNT

        try:
            applied: tuple[int, int, int, int] | None = None
            for _ in range(_FRAME_ATTEMPTS):
                animator.send_frame(frame)
                await asyncio.sleep(_FRAME_INTERVAL)

                pixel = emulated.state.tile_devices[0]["colors"][0]
                applied = (
                    pixel.hue,
                    pixel.saturation,
                    pixel.brightness,
                    pixel.kelvin,
                )
                if applied == target:
                    break

            assert applied == target, (
                "the emulated device never applied the streamed frame, so no "
                f"frame arrived over ::1 (last seen {applied}, wanted {target})"
            )
            assert applied != (
                before.hue,
                before.saturation,
                before.brightness,
                before.kelvin,
            )

            # Animator sends through a raw socket.socket it creates in
            # send_frame() and never wraps in an asyncio transport, so there
            # is no get_extra_info("socket") to read: the private attribute
            # is the only place the family of the socket the frames actually
            # went out over can be observed. A refactor that renames
            # _socket, or wraps it in a transport, has to update this.
            assert animator._socket is not None
            assert animator._socket.family == socket.AF_INET6
        finally:
            animator.close()


class TestIpv6ProbeOutcome:
    """The capability probe's two non-happy paths.

    Every host this suite runs on can bind ``::1``, so the probe itself only
    ever takes its success branch. These drive the extracted decision
    function directly, with no bind and no fixtures, so they run everywhere
    including where IPv6 is unavailable and the emulator is disabled.
    """

    @pytest.mark.parametrize("require_ipv6", [None, "", "0", "true"])
    def test_bind_failure_defers_to_a_skip_by_default(
        self, require_ipv6: str | None
    ) -> None:
        """Anything other than exactly "1" leaves the IPv6 tests skippable."""
        error = OSError(99, "Cannot assign requested address")

        assert ipv6_probe_outcome(error, require_ipv6) is False

    def test_bind_failure_names_the_cause_when_ipv6_is_required(self) -> None:
        """LIFX_REQUIRE_IPV6=1 produces a failure message naming the cause."""
        error = OSError(99, "Cannot assign requested address")

        outcome = ipv6_probe_outcome(error, "1")

        assert isinstance(outcome, str)
        assert "LIFX_REQUIRE_IPV6=1" in outcome
        assert "::1" in outcome
        assert "Cannot assign requested address" in outcome
