"""High-level Animator class for LIFX device animation.

This module provides the Animator class, which sends animation frames
directly via UDP for maximum throughput - no connection layer overhead.
Frame delivery is paced internally by ack-gated flow control (ANIM-01):
one packet per frame carries the `ack_required` flag, and `send_frame()`
non-blockingly sweeps the animator's own socket for arrived acks each call,
dropping (never queuing) a frame while too many probes are outstanding.
See `lifx.animation.flow` for the `AckGate` facility itself.

The factory methods query the device once for configuration (tile info,
zone count), then the Animator sends frames via raw UDP packets with
prebaked packet templates for zero-allocation performance.

Example:
    ```python
    from lifx.animation import Animator

    async with await Device.connect("192.168.1.100") as device:
        assert isinstance(device, MatrixLight)
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

import socket
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.animation.flow import AckGate
from lifx.animation.framebuffer import FrameBuffer
from lifx.animation.packets import (
    ACK_REQUIRED_FLAG,
    FLAGS_OFFSET,
    SEQUENCE_OFFSET,
    LightPacketGenerator,
    MatrixPacketGenerator,
    MultiZonePacketGenerator,
    PacketGenerator,
    PacketTemplate,
)
from lifx.const import LIFX_UDP_PORT
from lifx.exceptions import LifxNetworkError
from lifx.network.address import (
    SocketAddress,
    family_for_sockaddr,
    sockaddr_for,
    validate_address,
)
from lifx.network.utils import allocate_source
from lifx.protocol.models import Serial

if TYPE_CHECKING:
    from lifx.devices.light import Light
    from lifx.devices.matrix import MatrixLight
    from lifx.devices.multizone import MultiZoneLight


@dataclass(frozen=True)
class AnimatorStats:
    """Statistics about a frame send operation.

    Attributes:
        packets_sent: Number of packets sent
        total_time_ms: Total time for the operation in milliseconds
        gated: Whether this frame was dropped by ack-gated flow control.
            A gated frame sends nothing, consumes no sequence
            numbers, and skips framebuffer work entirely -- latest-frame-wins
            means the caller should simply send its next frame rather than
            queue or retry this one.
        acks_outstanding: The number of probe acks outstanding immediately
            after this call (for a gated frame, the count that caused the
            gate; for a sent frame, the count including this frame's own
            probe). Purely for observability -- consumers cannot configure
            flow control.
    """

    packets_sent: int
    total_time_ms: float
    gated: bool = False
    acks_outstanding: int = 0


class Animator:
    """High-level animator for LIFX devices.

    Sends animation frames directly via UDP for maximum throughput. No
    connection layer overhead -- frames are paced internally by ack-gated
    flow control rather than fired blind: delivery is paced against device
    acknowledgements, and when a device falls behind, new frames are
    dropped, never queued (latest-frame-wins). If a device stops
    acknowledging entirely, throughput degrades to a slow floor rather
    than stalling forever. This is entirely internal behaviour -- there is
    no flow-control toggle; consumers keep calling `send_frame()` exactly
    as before.

    All packets are prebaked at initialization time. Per-frame, only
    color data, the sequence number, and (for the probe template) the
    `AckGate`'s tracked-probe bookkeeping are updated -- the hot path
    remains a non-blocking `recvfrom_into` sweep on the animator's own
    socket plus one dict write, so `send_frame()` stays synchronous with no
    event-loop coupling.

    Attributes:
        pixel_count: Total number of pixels/zones

    Example:
        ```python
        async with await Device.connect("192.168.1.100") as device:
            assert isinstance(device, MatrixLight)
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

        Raises:
            ValueError: If ``ip`` is not a valid IPv4 or IPv6 literal, including
                a link-local IPv6 address without a syntactically valid zone.
        """
        self._ip = ip
        self._port = port
        # Finalisation state exists before validation or packet-generator work
        # that could raise, so cleanup is safe for a partly built instance.
        self._addr: SocketAddress | None = None
        self._socket: socket.socket | None = None
        self._ack_gate = AckGate()

        # Scope resolution is deliberately deferred until the first send so
        # a named IPv6 interface is re-resolved for each new socket session.
        # The literal itself is still gated here so permanent configuration
        # errors never reach the render loop.
        validate_address(ip)
        self._serial = serial
        self._framebuffer = framebuffer
        self._packet_generator = packet_generator

        # Protocol source ID (unique per-session, identifies this client)
        self._source = allocate_source()

        # Sequence number (0-255, wraps around)
        self._sequence = 0

        # Create prebaked packet templates
        self._templates: list[PacketTemplate] = packet_generator.create_templates(
            source=self._source,
            target=serial.value,
        )

        # Ack-gated flow control (ANIM-01/ANIM-02, D4-03): bake the
        # ack_required flag once into the template that carries the probe
        # (default: first packet; large-tile matrix: final CopyFrameBuffer,
        # D4-04). The hot send loop never touches the flags byte again.
        self._probe_index = packet_generator.probe_template_index
        self._templates[self._probe_index].data[FLAGS_OFFSET] |= ACK_REQUIRED_FLAG

    @classmethod
    async def for_matrix(
        cls,
        device: MatrixLight,
        duration_ms: int = 0,
    ) -> Animator:
        """Create an Animator configured for a MatrixLight device.

        Queries the device for tile information, then returns an animator
        that sends frames via direct UDP (no device connection needed
        after creation).

        Args:
            device: MatrixLight device (must be connected)
            duration_ms: Transition duration in milliseconds (default 0 for instant).
                        When non-zero, device smoothly interpolates between frames.

        Returns:
            Configured Animator instance

        Example:
            ```python
            async with await Device.connect("192.168.1.100") as device:
                assert isinstance(device, MatrixLight)
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
            duration_ms=duration_ms,
        )

        return cls(ip, serial, framebuffer, packet_generator, port=device.port)

    @classmethod
    async def for_multizone(
        cls,
        device: MultiZoneLight,
        duration_ms: int = 0,
    ) -> Animator:
        """Create an Animator configured for a MultiZoneLight device.

        Only devices with extended multizone capability are supported.
        Queries the device for zone count, then returns an animator
        that sends frames via direct UDP.

        Args:
            device: MultiZoneLight device (must be connected and support
                   extended multizone protocol)
            duration_ms: Transition duration in milliseconds (default 0 for instant).
                        When non-zero, device smoothly interpolates between frames.

        Returns:
            Configured Animator instance

        Raises:
            ValueError: If device doesn't support extended multizone

        Example:
            ```python
            async with await Device.connect("192.168.1.100") as device:
                assert isinstance(device, MultiZoneLight)
                animator = await Animator.for_multizone(device)

            # Device connection closed, animator still works via UDP
            while running:
                stats = animator.send_frame(frame)
                await asyncio.sleep(1 / 30)  # 30 FPS
            ```
        """
        # Ensure capabilities are loaded
        if device.capabilities is None:
            await device.ensure_capabilities()

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
        packet_generator = MultiZonePacketGenerator(
            zone_count=zone_count, duration_ms=duration_ms
        )

        return cls(ip, serial, framebuffer, packet_generator, port=device.port)

    @classmethod
    def for_light(
        cls,
        device: Light,
        duration_ms: int = 0,
    ) -> Animator:
        """Create an Animator configured for a single Light device.

        Unlike the matrix/multizone factories, this does not need to be async
        because single lights don't require any device queries for configuration.

        Args:
            device: Light device (must have ip and serial set)
            duration_ms: Transition duration in milliseconds (default 0 for instant).
                        When non-zero, device smoothly interpolates between frames.

        Returns:
            Configured Animator instance

        Example:
            ```python
            async with await Device.connect("192.168.1.100") as device:
                animator = Animator.for_light(device)

            # Device connection closed, animator still works via UDP
            while running:
                stats = animator.send_frame([(65535, 65535, 65535, 3500)])
                await asyncio.sleep(1 / 30)  # 30 FPS
            ```
        """
        ip = device.ip
        serial = Serial.from_string(device.serial)
        framebuffer = FrameBuffer.for_light(device)
        packet_generator = LightPacketGenerator(duration_ms=duration_ms)

        return cls(ip, serial, framebuffer, packet_generator, port=device.port)

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
        in prebaked packets, and sends them directly via UDP -- unless
        ack-gated flow control drops the frame first. Each call first
        sweeps the animator's own socket for arrived acks; if the device
        is still behind on acknowledgements after the sweep, the frame is
        dropped entirely (no framebuffer work, no packets sent, no
        sequence numbers consumed) and the caller should simply send its
        next frame rather than retry or queue this one (latest-frame-wins).

        This is a synchronous method for minimum overhead. UDP sendto()
        is non-blocking for datagrams, and the ack sweep is a non-blocking
        `recvfrom_into` loop on the same socket -- no event loop is
        required.

        Args:
            hsbk: Protocol-ready HSBK data for all pixels.
                  Each tuple is (hue, sat, brightness, kelvin) where
                  H/S/B are 0-65535 and K is 1500-9000.

        Returns:
            AnimatorStats with operation statistics. `gated=True` means the
            frame was dropped by flow control.

        Raises:
            ValueError: If hsbk length doesn't match pixel_count. This
                validation always runs, even when the gate is saturated --
                a full gate must never suppress input validation.
            LifxNetworkError: If the destination is invalid or the UDP socket
                cannot be created, or a frame datagram cannot be sent.
        """
        start_time = time.perf_counter()

        if len(hsbk) != self._framebuffer.canvas_size:
            raise ValueError(
                f"HSBK length ({len(hsbk)}) must match "
                f"pixel_count ({self._framebuffer.canvas_size})"
            )

        # Ensure socket exists. The socket family follows the device
        # address, derived by the one shared rule: Thread devices are
        # IPv6-only, and an AF_INET socket raises gaierror when asked to
        # send to an IPv6 address.
        sock = self._socket
        if sock is None:
            try:
                addr = sockaddr_for((self._ip, self._port))
                family = family_for_sockaddr(addr)
                sock = socket.socket(family, socket.SOCK_DGRAM)
                sock.setblocking(False)
            except (OSError, ValueError) as error:
                if sock is not None:
                    sock.close()
                raise LifxNetworkError(
                    f"Failed to open UDP socket for {self._ip!r}: {error}"
                ) from error
            self._addr = addr
            self._socket = sock

        send_address = self._addr
        if send_address is None:
            raise LifxNetworkError("Animator UDP session is incomplete")
        now = time.monotonic()
        self._ack_gate.sweep(sock, self._source, now)
        if self._ack_gate.gated:
            return AnimatorStats(
                packets_sent=0,
                total_time_ms=(time.perf_counter() - start_time) * 1000,
                gated=True,
                acks_outstanding=self._ack_gate.outstanding_count,
            )

        # Apply orientation mapping
        device_data = self._framebuffer.apply(hsbk)

        # Update colors in prebaked templates
        self._packet_generator.update_colors(self._templates, device_data)

        # Send each packet, updating sequence number
        for i, tmpl in enumerate(self._templates):
            sequence = self._sequence
            tmpl.data[SEQUENCE_OFFSET] = sequence
            try:
                sock.sendto(tmpl.data, send_address)
            except OSError as error:
                raise LifxNetworkError(
                    f"Failed to send animation frame to {self._ip!r}: {error}"
                ) from error

            if i == self._probe_index:
                self._ack_gate.track(sequence, now)
            self._sequence = (sequence + 1) % 256

        end_time = time.perf_counter()

        return AnimatorStats(
            packets_sent=len(self._templates),
            total_time_ms=(end_time - start_time) * 1000,
            acks_outstanding=self._ack_gate.outstanding_count,
        )

    def close(self) -> None:
        """Close the UDP socket.

        Call this when done with the animator to free resources. Also
        resets the ack gate, so a fresh animator session (new socket, new
        gate) starts ungated.
        """
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._addr = None
        self._ack_gate.reset()

    def __del__(self) -> None:
        """Clean up socket on garbage collection."""
        self.close()
