"""Tests for the high-level Animator class."""

from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.animation.animator import Animator, AnimatorStats
from lifx.animation.framebuffer import FrameBuffer
from lifx.animation.packets import MatrixPacketGenerator
from lifx.protocol.models import Serial


class TestAnimatorStats:
    """Tests for AnimatorStats dataclass."""

    def test_stats_fields(self) -> None:
        """Test AnimatorStats has correct fields."""
        stats = AnimatorStats(
            packets_sent=5,
            total_time_ms=10.5,
        )
        assert stats.packets_sent == 5
        assert stats.total_time_ms == 10.5

    def test_frozen_dataclass(self) -> None:
        """Verify AnimatorStats is immutable."""
        stats = AnimatorStats(packets_sent=5, total_time_ms=10.5)
        with pytest.raises(AttributeError):
            stats.packets_sent = 10  # type: ignore[misc]


class TestAnimatorConstruction:
    """Tests for Animator construction and properties."""

    def test_init_with_components(self) -> None:
        """Test direct constructor works."""
        framebuffer = FrameBuffer(pixel_count=64)
        packet_generator = MatrixPacketGenerator(
            tile_count=1, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        animator = Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

        assert animator.pixel_count == 64

    def test_canvas_width_property(self) -> None:
        """Test canvas_width property delegation."""
        framebuffer = FrameBuffer(pixel_count=64, canvas_width=8, canvas_height=8)
        packet_generator = MatrixPacketGenerator(
            tile_count=1, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        animator = Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

        assert animator.canvas_width == 8
        assert animator.canvas_height == 8

    def test_pixel_count_from_framebuffer(self) -> None:
        """Test pixel_count property delegation."""
        framebuffer = FrameBuffer(pixel_count=128)
        packet_generator = MatrixPacketGenerator(
            tile_count=2, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        animator = Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

        assert animator.pixel_count == 128


class TestAnimatorSendFrame:
    """Tests for Animator.send_frame method."""

    @pytest.fixture
    def animator(self) -> Animator:
        """Create an animator for testing."""
        framebuffer = FrameBuffer(pixel_count=64)
        packet_generator = MatrixPacketGenerator(
            tile_count=1, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        return Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

    def test_send_frame_wrong_length_raises(self, animator: Animator) -> None:
        """Test that wrong Color array length raises ValueError."""
        hsbk: list[tuple[int, int, int, int]] = [
            (100, 100, 100, 3500)
        ] * 32  # Wrong length

        with pytest.raises(ValueError, match="must match pixel_count"):
            animator.send_frame(hsbk)

    def test_send_frame_sends_packets(self, animator: Animator) -> None:
        """Test that send_frame sends packets via UDP."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        # Mock the socket
        with patch.object(socket, "socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock

            stats = animator.send_frame(hsbk)

            assert stats.packets_sent >= 1
            mock_sock.sendto.assert_called()

    def test_send_frame_returns_stats(self, animator: Animator) -> None:
        """Test that send_frame returns AnimatorStats."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with patch.object(socket, "socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock

            stats = animator.send_frame(hsbk)

            assert isinstance(stats, AnimatorStats)
            assert stats.packets_sent >= 1
            assert stats.total_time_ms >= 0

    def test_send_frame_is_synchronous(self, animator: Animator) -> None:
        """Test that send_frame is synchronous (not a coroutine)."""
        import inspect

        assert not inspect.iscoroutinefunction(animator.send_frame)

    def test_send_frame_reuses_socket(self, animator: Animator) -> None:
        """Test that send_frame reuses the same socket."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with patch.object(socket, "socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock

            # Send multiple frames
            animator.send_frame(hsbk)
            animator.send_frame(hsbk)
            animator.send_frame(hsbk)

            # Socket should only be created once
            assert mock_socket_class.call_count == 1

    def test_send_frame_sends_to_correct_address(self, animator: Animator) -> None:
        """Test that packets are sent to correct IP:port."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with patch.object(socket, "socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock

            animator.send_frame(hsbk)

            # Check sendto was called with correct address
            call_args = mock_sock.sendto.call_args
            address = call_args[0][1]
            assert address == ("192.168.1.100", 56700)

    def test_close_closes_socket(self, animator: Animator) -> None:
        """Test that close() closes the socket."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with patch.object(socket, "socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock

            animator.send_frame(hsbk)
            animator.close()

            mock_sock.close.assert_called_once()


class TestAnimatorForMatrixFactory:
    """Tests for Animator.for_matrix factory method."""

    @pytest.mark.asyncio
    async def test_for_matrix_fetches_device_chain_when_none(self) -> None:
        """Test for_matrix fetches device chain if not already loaded."""
        tile = MagicMock()
        tile.width = 8
        tile.height = 8
        tile.user_x = 0.0
        tile.user_y = 0.0
        tile.nearest_orientation = "Upright"

        device = MagicMock()
        device.ip = "192.168.1.100"
        device.serial = "d073d5123456"
        device.device_chain = None  # Not loaded yet
        device.capabilities = MagicMock()
        device.capabilities.has_chain = False

        # get_device_chain should be called and populate device_chain
        async def mock_get_device_chain() -> list:
            device.device_chain = [tile]
            return [tile]

        device.get_device_chain = mock_get_device_chain

        animator = await Animator.for_matrix(device)

        assert animator.pixel_count == 64


class TestAnimatorForMultizoneFactory:
    """Tests for Animator.for_multizone factory method."""

    @pytest.mark.asyncio
    async def test_for_multizone_no_extended_capability_raises(self) -> None:
        """Test for_multizone raises error when device lacks extended multizone."""
        device = MagicMock()
        device.capabilities = MagicMock()
        device.capabilities.has_extended_multizone = False

        with pytest.raises(ValueError, match="extended multizone"):
            await Animator.for_multizone(device)

    @pytest.mark.asyncio
    async def test_for_multizone_loads_capabilities_when_none(self) -> None:
        """Test for_multizone calls _ensure_capabilities when None.

        If capabilities haven't been fetched, we should load them first.
        Then if device doesn't support extended multizone, raise error.
        """
        device = MagicMock()
        device.capabilities = None

        # Mock _ensure_capabilities to set capabilities without extended multizone
        async def set_capabilities() -> None:
            device.capabilities = MagicMock()
            device.capabilities.has_extended_multizone = False

        device._ensure_capabilities = AsyncMock(side_effect=set_capabilities)

        with pytest.raises(ValueError, match="extended multizone"):
            await Animator.for_multizone(device)

        # Verify _ensure_capabilities was called
        device._ensure_capabilities.assert_called_once()


class TestAnimatorForLightFactory:
    """Tests for Animator.for_light factory method."""

    def test_for_light_creates_animator(self) -> None:
        """Test for_light creates an animator with correct pixel count."""
        device = MagicMock()
        device.ip = "192.168.1.100"
        device.serial = "d073d5123456"

        animator = Animator.for_light(device)

        assert animator.pixel_count == 1
        assert animator.canvas_width == 1
        assert animator.canvas_height == 1

    def test_for_light_sends_single_packet(self) -> None:
        """Test for_light sends exactly 1 packet per frame."""
        device = MagicMock()
        device.ip = "192.168.1.100"
        device.serial = "d073d5123456"

        animator = Animator.for_light(device)
        hsbk: list[tuple[int, int, int, int]] = [(65535, 65535, 65535, 3500)]

        with patch.object(socket, "socket") as mock_socket_class:
            mock_sock = MagicMock()
            mock_socket_class.return_value = mock_sock

            stats = animator.send_frame(hsbk)

            assert stats.packets_sent == 1
            mock_sock.sendto.assert_called_once()

    def test_for_light_is_synchronous(self) -> None:
        """Test for_light factory is synchronous (not async)."""
        import inspect

        assert not inspect.iscoroutinefunction(Animator.for_light)

    def test_for_light_with_duration(self) -> None:
        """Test for_light passes duration_ms to packet generator."""
        device = MagicMock()
        device.ip = "192.168.1.100"
        device.serial = "d073d5123456"

        animator = Animator.for_light(device, duration_ms=500)

        # Verify by checking the packet template's duration
        import struct

        from lifx.animation.packets import HEADER_SIZE

        template = animator._templates[0]
        payload = bytes(template.data[HEADER_SIZE:])
        (duration,) = struct.unpack_from("<I", payload, 9)
        assert duration == 500


@pytest.mark.emulator
class TestAnimatorForMatrixIntegration:
    """Integration tests for Animator.for_matrix with emulator."""

    async def test_for_matrix_creates_animator(self, emulator_devices) -> None:
        """Test factory method works with real device."""
        from lifx.devices.matrix import MatrixLight

        # Find the matrix device
        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break

        assert matrix is not None, "No MatrixLight in emulator_devices"

        async with matrix:
            animator = await Animator.for_matrix(matrix)

            assert animator.pixel_count > 0

    async def test_send_frame_sends_packets(self, emulator_devices) -> None:
        """Test send_frame sends packets."""
        from lifx.devices.matrix import MatrixLight

        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break

        assert matrix is not None

        async with matrix:
            animator = await Animator.for_matrix(matrix)

            # Create frame
            hsbk: list[tuple[int, int, int, int]] = [
                (65535, 65535, 32768, 3500)
            ] * animator.pixel_count
            stats = animator.send_frame(hsbk)

            assert stats.packets_sent >= 1

            animator.close()

    async def test_animation_loop_simulation(self, emulator_devices) -> None:
        """Test multiple frames in sequence."""
        from lifx.devices.matrix import MatrixLight

        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break

        assert matrix is not None

        async with matrix:
            animator = await Animator.for_matrix(matrix)

            total_packets = 0
            for frame_num in range(5):
                # Create frame with shifting colors
                hsbk: list[tuple[int, int, int, int]] = []
                for i in range(animator.pixel_count):
                    hue = ((i + frame_num * 10) * 1000) % 65536
                    hsbk.append((hue, 65535, 32768, 3500))

                stats = animator.send_frame(hsbk)
                total_packets += stats.packets_sent

                # Small delay between frames
                await asyncio.sleep(0.01)

            # Should have sent packets for multiple frames
            assert total_packets >= 5

            animator.close()


@pytest.mark.emulator
class TestAnimatorForMultizoneIntegration:
    """Integration tests for Animator.for_multizone with emulator."""

    async def test_for_multizone_creates_animator(self, emulator_devices) -> None:
        """Test factory method works with real device."""
        from lifx.devices.multizone import MultiZoneLight

        multizone = None
        for device in emulator_devices:
            if isinstance(device, MultiZoneLight):
                multizone = device
                break

        assert multizone is not None, "No MultiZoneLight in emulator_devices"

        async with multizone:
            animator = await Animator.for_multizone(multizone)

            assert animator.pixel_count > 0

            animator.close()

    async def test_send_frame_extended_protocol(self, emulator_devices) -> None:
        """Test extended multizone sends packets."""
        from lifx.devices.multizone import MultiZoneLight

        multizone = None
        for device in emulator_devices:
            if isinstance(device, MultiZoneLight):
                multizone = device
                break

        assert multizone is not None

        async with multizone:
            animator = await Animator.for_multizone(multizone)

            hsbk: list[tuple[int, int, int, int]] = [
                (65535, 65535, 32768, 3500)
            ] * animator.pixel_count
            stats = animator.send_frame(hsbk)

            assert stats.packets_sent >= 1

            animator.close()

    async def test_animation_loop_simulation(self, emulator_devices) -> None:
        """Test multiple frames in sequence."""
        from lifx.devices.multizone import MultiZoneLight

        multizone = None
        for device in emulator_devices:
            if isinstance(device, MultiZoneLight):
                multizone = device
                break

        assert multizone is not None

        async with multizone:
            animator = await Animator.for_multizone(multizone)

            total_packets = 0
            for frame_num in range(5):
                # Create frame with shifting colors
                hsbk: list[tuple[int, int, int, int]] = []
                for i in range(animator.pixel_count):
                    hue = ((i + frame_num * 10) * 1000) % 65536
                    hsbk.append((hue, 65535, 32768, 3500))

                stats = animator.send_frame(hsbk)
                total_packets += stats.packets_sent

                # Small delay between frames
                await asyncio.sleep(0.01)

            # Should have sent packets for multiple frames
            assert total_packets >= 5

            animator.close()


@pytest.mark.emulator
class TestAnimatorErrorHandling:
    """Integration tests for Animator error handling."""

    async def test_send_frame_wrong_length_raises(self, emulator_devices) -> None:
        """Test wrong Color array length raises error."""
        from lifx.devices.matrix import MatrixLight

        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break

        assert matrix is not None

        async with matrix:
            animator = await Animator.for_matrix(matrix)

            # Wrong length
            hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * (
                animator.pixel_count // 2
            )

            with pytest.raises(ValueError, match="must match"):
                animator.send_frame(hsbk)

            animator.close()

    async def test_for_matrix_no_tiles_raises(self, emulator_devices) -> None:
        """Test for_matrix raises when device has no tiles."""
        from lifx.devices.matrix import MatrixLight

        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break

        assert matrix is not None

        async with matrix:
            # Temporarily clear device chain to simulate no tiles
            original_chain = matrix._device_chain
            matrix._device_chain = []

            with pytest.raises(ValueError, match="no tiles"):
                await Animator.for_matrix(matrix)

            # Restore
            matrix._device_chain = original_chain
