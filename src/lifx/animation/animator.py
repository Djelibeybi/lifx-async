"""High-level Animator class for LIFX device animation.

This module provides the Animator class, which sends animation frames
directly via UDP for maximum throughput - no connection layer overhead.

The factory methods query the device once for configuration (tile info,
zone count), then the Animator sends frames via raw UDP packets with
prebaked packet templates for zero-allocation performance.

Example:
    ```python
    from lifx.animation import Animator

    async with await MatrixLight.from_ip("192.168.1.100") as device:
        # Query device once for tile info
        animator = await Animator.for_matrix(device)

    # Device connection no longer needed - animator sends via direct UDP
    while running:
        stats = animator.send_frame(frame)
        await asyncio.sleep(1 / 30)  # 30 FPS

    animator.close()
    ```
"""

from __future__ import annotations

import random
import socket
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.animation.framebuffer import FrameBuffer
from lifx.animation.packets import (
    SEQUENCE_OFFSET,
    MatrixPacketGenerator,
    MultiZonePacketGenerator,
    PacketGenerator,
    PacketTemplate,
)
from lifx.const import LIFX_UDP_PORT
from lifx.protocol.models import Serial

if TYPE_CHECKING:
    from lifx.devices.matrix import MatrixLight
    from lifx.devices.multizone import MultiZoneLight


@dataclass(frozen=True)
class AnimatorStats:
    """Statistics about a frame send operation.

    Attributes:
        packets_sent: Number of packets sent
        total_time_ms: Total time for the operation in milliseconds
    """

    packets_sent: int
    total_time_ms: float


class Animator:
    """High-level animator for LIFX devices.

    Sends animation frames directly via UDP for maximum throughput.
    No connection layer, no ACKs, no waiting - just fire packets as
    fast as possible.

    All packets are prebaked at initialization time. Per-frame, only
    color data and sequence numbers are updated in place before sending.

    Attributes:
        pixel_count: Total number of pixels/zones

    Example:
        ```python
        async with await MatrixLight.from_ip("192.168.1.100") as device:
            animator = await Animator.for_matrix(device)

        # No connection needed after this - direct UDP
        while running:
            stats = animator.send_frame(frame)
            await asyncio.sleep(1 / 30)  # 30 FPS

        animator.close()
        ```
    """

    def __init__(
        self,
        ip: str,
        serial: Serial,
        framebuffer: FrameBuffer,
        packet_generator: PacketGenerator,
        port: int = LIFX_UDP_PORT,
    ) -> None:
        """Initialize animator for direct UDP sending.

        Use the `for_matrix()` or `for_multizone()` class methods for
        automatic configuration from a device.

        Args:
            ip: Device IP address
            serial: Device serial number
            framebuffer: Configured FrameBuffer for orientation mapping
            packet_generator: Configured PacketGenerator for the device
            port: UDP port (default: 56700)
        """
        self._ip = ip
        self._port = port
        self._serial = serial
        self._framebuffer = framebuffer
        self._packet_generator = packet_generator

        # Protocol source ID (random, identifies this client)
        self._source = random.randint(1, 0xFFFFFFFF)  # nosec B311

        # Sequence number (0-255, wraps around)
        self._sequence = 0

        # Create prebaked packet templates
        self._templates: list[PacketTemplate] = packet_generator.create_templates(
            source=self._source,
            target=serial.value,
        )

        # UDP socket (created lazily)
        self._socket: socket.socket | None = None

    @classmethod
    async def for_matrix(
        cls,
        device: MatrixLight,
    ) -> Animator:
        """Create an Animator configured for a MatrixLight device.

        Queries the device for tile information, then returns an animator
        that sends frames via direct UDP (no device connection needed
        after creation).

        Args:
            device: MatrixLight device (must be connected)

        Returns:
            Configured Animator instance

        Example:
            ```python
            async with await MatrixLight.from_ip("192.168.1.100") as device:
                animator = await Animator.for_matrix(device)

            # Device connection closed, animator still works via UDP
            while running:
                stats = animator.send_frame(frame)
                await asyncio.sleep(1 / 30)  # 30 FPS
            ```
        """
        # Get device info
        ip = device.ip
        serial = Serial.from_string(device.serial)

        # Ensure we have tile chain
        if device.device_chain is None:
            await device.get_device_chain()

        tiles = device.device_chain
        if not tiles:
            raise ValueError("Device has no tiles")

        # Create framebuffer with orientation correction
        framebuffer = await FrameBuffer.for_matrix(device)

        # Create packet generator
        packet_generator = MatrixPacketGenerator(
            tile_count=len(tiles),
            tile_width=tiles[0].width,
            tile_height=tiles[0].height,
        )

        return cls(ip, serial, framebuffer, packet_generator)

    @classmethod
    async def for_multizone(
        cls,
        device: MultiZoneLight,
    ) -> Animator:
        """Create an Animator configured for a MultiZoneLight device.

        Only devices with extended multizone capability are supported.
        Queries the device for zone count, then returns an animator
        that sends frames via direct UDP.

        Args:
            device: MultiZoneLight device (must be connected and support
                   extended multizone protocol)

        Returns:
            Configured Animator instance

        Raises:
            ValueError: If device doesn't support extended multizone

        Example:
            ```python
            async with await MultiZoneLight.from_ip("192.168.1.100") as device:
                animator = await Animator.for_multizone(device)

            # Device connection closed, animator still works via UDP
            while running:
                stats = animator.send_frame(frame)
                await asyncio.sleep(1 / 30)  # 30 FPS
            ```
        """
        # Check extended multizone capability
        has_extended = bool(
            device.capabilities and device.capabilities.has_extended_multizone
        )
        if not has_extended:
            raise ValueError(
                "Device does not support extended multizone protocol. "
                "Only extended multizone devices are supported for animation."
            )

        # Get device info
        ip = device.ip
        serial = Serial.from_string(device.serial)

        # Create framebuffer (no orientation for multizone)
        framebuffer = await FrameBuffer.for_multizone(device)

        # Get zone count
        zone_count = await device.get_zone_count()

        # Create packet generator
        packet_generator = MultiZonePacketGenerator(zone_count=zone_count)

        return cls(ip, serial, framebuffer, packet_generator)

    @property
    def pixel_count(self) -> int:
        """Get total number of input pixels (canvas size for multi-tile)."""
        # For multi-tile devices, this returns the canvas size
        # For single-tile/multizone, this returns device pixel count
        return self._framebuffer.canvas_size

    @property
    def canvas_width(self) -> int:
        """Get width of the logical canvas in pixels."""
        return self._framebuffer.canvas_width

    @property
    def canvas_height(self) -> int:
        """Get height of the logical canvas in pixels."""
        return self._framebuffer.canvas_height

    def send_frame(
        self,
        hsbk: list[tuple[int, int, int, int]],
    ) -> AnimatorStats:
        """Send a frame to the device via direct UDP.

        Applies orientation mapping (for matrix devices), updates colors
        in prebaked packets, and sends them directly via UDP. No ACKs,
        no waiting - maximum throughput.

        This is a synchronous method for minimum overhead. UDP sendto()
        is non-blocking for datagrams.

        Args:
            hsbk: Protocol-ready HSBK data for all pixels.
                  Each tuple is (hue, sat, brightness, kelvin) where
                  H/S/B are 0-65535 and K is 1500-9000.

        Returns:
            AnimatorStats with operation statistics

        Raises:
            ValueError: If hsbk length doesn't match pixel_count
        """
        start_time = time.perf_counter()

        # Apply orientation mapping
        device_data = self._framebuffer.apply(hsbk)

        # Update colors in prebaked templates
        self._packet_generator.update_colors(self._templates, device_data)

        # Ensure socket exists
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setblocking(False)

        # Send each packet, updating sequence number
        for tmpl in self._templates:
            tmpl.data[SEQUENCE_OFFSET] = self._sequence
            self._sequence = (self._sequence + 1) % 256
            self._socket.sendto(tmpl.data, (self._ip, self._port))

        end_time = time.perf_counter()

        return AnimatorStats(
            packets_sent=len(self._templates),
            total_time_ms=(end_time - start_time) * 1000,
        )

    def close(self) -> None:
        """Close the UDP socket.

        Call this when done with the animator to free resources.
        """
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def __del__(self) -> None:
        """Clean up socket on garbage collection."""
        self.close()
