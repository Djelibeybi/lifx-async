"""High-level Animator class for LIFX device animation.

This module provides the Animator class, which sends animation frames
directly via UDP for maximum throughput - no connection layer overhead.
Frame delivery is paced internally by ack-gated flow control (ANIM-01):
one packet per frame carries the `ack_required` flag, and `send_frame()`
non-blockingly sweeps the animator's own socket for arrived acks each call,
dropping (never queuing) a frame while too many probes are outstanding.
See `lifx.animation.flow` for the `AckGate` facility itself.

Every light owns one Animator, `device.animator`. Library effects and
direct frame senders such as LedFx borrow it, so each light has one writer
and one ack gate. Preparing the Animator queries the device once for its
geometry (tile info, zone count), then the Animator sends frames via raw UDP
packets with prebaked packet templates for zero-allocation performance. The
`for_matrix()`, `for_multizone()` and `for_light()` factories are deprecated
and return the device's Animator.

Example:
    ```python
    async with await Device.connect("192.168.1.100") as device:
        # Query device once for tile info
        animator = await device.animator.prepare()

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
import warnings
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.animation.flow import AckGate
from lifx.animation.framebuffer import FrameBuffer
from lifx.animation.packets import (
    ACK_REQUIRED_FLAG,
    FLAGS_OFFSET,
    SEQUENCE_OFFSET,
    PacketGenerator,
    PacketTemplate,
)
from lifx.animation.slots import ComponentSlot, HeldTile
from lifx.color import HSBK
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
from lifx.protocol.protocol_types import LightHsbk

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


@dataclass(frozen=True)
class _Geometry:
    """The device's own canvas and the generator for its full set of pixels."""

    framebuffer: FrameBuffer
    packet_generator: PacketGenerator
    wraps: bool


def _check_length(canvas: FrameBuffer, hsbk: list[tuple[int, int, int, int]]) -> None:
    """Reject a frame that does not cover a writer's canvas.

    This runs even when the ack gate is closed: a full gate must never
    suppress input validation.
    """
    if len(hsbk) != canvas.canvas_size:
        raise ValueError(
            f"HSBK length ({len(hsbk)}) must match pixel_count ({canvas.canvas_size})"
        )


def _warn_deprecated(factory: str) -> None:
    warnings.warn(
        f"Animator.{factory}() is deprecated; use device.animator instead",
        DeprecationWarning,
        stacklevel=3,
    )


class AnimatorWriter:
    """One writer's canvas on a device's Animator.

    The Conductor borrows a light's Animator through a writer, so an effect
    can draw on a canvas of its own (a Mirror's ring, say) at its own
    transition duration, while every frame still goes out through the
    Animator's one socket and one ack gate. It has the frame-loop surface of
    an Animator: `pixel_count`, `canvas_width`, `canvas_height`, `wraps`,
    `send_frame()` and `close()`.
    """

    def __init__(
        self,
        animator: Animator,
        canvas: FrameBuffer,
        *,
        duration_ms: int,
        wraps: bool,
        slot: ComponentSlot | None = None,
        whole_light: bool = False,
    ) -> None:
        self._animator = animator
        self._canvas = canvas
        self._duration_ms = duration_ms
        self._wraps = wraps
        self._slot = slot
        self._whole_light = whole_light
        self._streaming = True

    @property
    def animator(self) -> Animator:
        """The device's Animator this writer borrows."""
        return self._animator

    @property
    def component(self) -> str | None:
        """The light component this writer draws on, or None for the whole light."""
        return self._slot.component if self._slot is not None else None

    @property
    def canvas(self) -> FrameBuffer:
        """The canvas this writer's frames are drawn on."""
        return self._canvas

    @property
    def duration_ms(self) -> int:
        """Transition duration, in milliseconds, of this writer's frames."""
        return self._duration_ms

    @property
    def whole_light(self) -> bool:
        """True if this writer draws one light component's share of a whole light.

        A whole-light effect on a Mirror draws through one writer per ring, so
        each ring is a canvas of its own while the effect still runs on the
        whole light.
        """
        return self._whole_light

    def leave_whole_light(self) -> None:
        """Go on drawing this light component as an effect of its own.

        A whole-light effect moves onto one light component when an effect
        starts on, or a caller changes, the other. The ring this writer draws
        then belongs to that light component alone.
        """
        self._whole_light = False

    @property
    def pixel_count(self) -> int:
        """Number of pixels in this writer's canvas."""
        return self._canvas.canvas_size

    @property
    def canvas_width(self) -> int:
        """Width of this writer's canvas in pixels."""
        return self._canvas.canvas_width

    @property
    def canvas_height(self) -> int:
        """Height of this writer's canvas in pixels."""
        return self._canvas.canvas_height

    @property
    def wraps(self) -> bool:
        """True if the canvas is a ring: its last pixel sits next to its first."""
        return self._wraps

    def send_frame(
        self,
        hsbk: list[tuple[int, int, int, int]],
        duration_ms: int | None = None,
        *,
        settled: bool = False,
    ) -> AnimatorStats:
        """Send a frame drawn on this writer's canvas through the Animator.

        A light component's writer stores the frame in its slot and sends the
        tile composed from every slot.

        Args:
            hsbk: The frame, one protocol-ready colour per canvas pixel
            duration_ms: Transition duration for this frame alone, or None
                for the writer's own
            settled: For a light component's writer, the frame is the
                colours the firmware fades this slot towards: it is kept as
                the slot's target, and the tile composes every slot's target
                and the held tile's final colours rather than colours
                part-way through a fade
        """
        duration = self._duration_ms if duration_ms is None else duration_ms
        if self._slot is not None:
            return self._animator._send_slot(
                self, self._slot, hsbk, duration, settled=settled
            )
        return self._animator._send(self._canvas, hsbk, duration)

    @property
    def streaming(self) -> bool:
        """Whether this writer's effect sends a frame of the tile every frame.

        A writer that sends the tile only now and then, as a colour loop
        does between steps, clears it, so another effect on the tile does
        not wait for this writer's frames to carry its own slot.
        """
        return self._streaming

    @streaming.setter
    def streaming(self, value: bool) -> None:
        self._streaming = value

    @property
    def draws_slot(self) -> bool:
        """True if this writer draws on a light component's slot."""
        return self._slot is not None

    def tile_shared(self, own: Collection[AnimatorWriter]) -> bool:
        """Whether a streaming writer outside ``own`` draws on this tile.

        That writer's frames carry this writer's slot, so this writer need
        only keep its slot current.

        Args:
            own: Writers that belong to the same effect as this one
        """
        return any(
            writer not in own and writer._streaming
            for writer in self._animator._slot_writers
        )

    @property
    def hold_remaining(self) -> float:
        """Seconds left of a fade asked of the tile's held colours, or 0."""
        hold = self._animator._hold
        return hold.remaining(time.monotonic()) if hold is not None else 0.0

    @property
    def hold_version(self) -> int:
        """A count that changes whenever the tile's held colours change."""
        hold = self._animator._hold
        return hold.version if hold is not None else 0

    def shares_tile_with(self, other: object) -> bool:
        """True if both writers draw on slots of the same Animator's tile."""
        return (
            isinstance(other, AnimatorWriter)
            and self._slot is not None
            and other._slot is not None
            and other._animator is self._animator
        )

    def stage(
        self, hsbk: list[tuple[int, int, int, int]], *, settled: bool = False
    ) -> None:
        """Keep a light component's frame for the next tile, sending nothing.

        An effect drawing on both light components of one light stages the
        first light component's frame, then sends the second, so each frame
        of the effect is one tile. Only a light component's writer stages.

        Args:
            hsbk: The frame, one protocol-ready colour per canvas pixel
            settled: Keep the frame as the slot's target, the colours the
                firmware fades it towards, as ``send_frame()`` does
        """
        slot = self._slot
        assert slot is not None
        self._animator._store_slot(self, slot, hsbk, settled=settled)

    def close(self) -> None:
        """Stop writing. The device's Animator stays open for other writers.

        A light component's writer gives its slot back. Once no other writer
        draws on the light component, its last frame becomes that part of the
        held tile, so it keeps showing until a restore or a caller's write.
        """
        if self._slot is not None:
            self._animator._release_slot(self, self._slot)


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
            animator = await device.animator.prepare()

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
        *,
        wraps: bool = False,
    ) -> None:
        """Initialize animator for direct UDP sending.

        Prefer `device.animator`, which every light owns. Constructing an
        Animator directly gives a second writer for the same device, with its
        own ack gate.

        Args:
            ip: Device IP address
            serial: Device serial number
            framebuffer: Configured FrameBuffer for orientation mapping
            packet_generator: Configured PacketGenerator for the device
            port: UDP port (default: 56700)
            wraps: True if the canvas is a ring whose last pixel sits next
                to its first (default: False)

        Raises:
            ValueError: If ``ip`` is not a valid IPv4 or IPv6 literal, including
                a link-local IPv6 address without a syntactically valid zone.
        """
        self._open_session(ip, serial, port)
        self._duration_ms = packet_generator.duration_ms
        self._install(framebuffer, packet_generator, wraps=wraps)

    def _open_session(self, ip: str, serial: Serial, port: int) -> None:
        """Set up the writer identity: address, source, sequence and ack gate."""
        self._ip = ip
        self._port = port
        # Finalisation state exists before validation or packet-generator work
        # that could raise, so cleanup is safe for a partly built instance.
        self._addr: SocketAddress | None = None
        self._socket: socket.socket | None = None
        self._ack_gate = AckGate()
        self._geometry: _Geometry | None = None
        self._device: Light | None = None
        # Light component slots: the open writers, each slot's latest frame,
        # and the held tile shown where no slot has a frame.
        self._slot_writers: dict[AnimatorWriter, ComponentSlot] = {}
        self._slot_frames: dict[
            str,
            tuple[ComponentSlot, FrameBuffer, list[tuple[int, int, int, int]]],
        ] = {}
        # A slot written with a transition the firmware runs, such as a
        # colour loop's step, also keeps the colours it is fading towards.
        self._slot_targets: dict[
            str,
            tuple[ComponentSlot, FrameBuffer, list[tuple[int, int, int, int]]],
        ] = {}
        self._hold: HeldTile | None = None

        # Scope resolution is deliberately deferred until the first send so
        # a named IPv6 interface is re-resolved for each new socket session.
        # The literal itself is still gated here so permanent configuration
        # errors never reach the render loop.
        validate_address(ip)
        self._serial = serial

        # Protocol source ID (unique per-session, identifies this client)
        self._source = allocate_source()

        # Sequence number (0-255, wraps around)
        self._sequence = 0

    def _install(
        self,
        framebuffer: FrameBuffer,
        packet_generator: PacketGenerator,
        *,
        wraps: bool = False,
    ) -> None:
        """Install the device's geometry and prebake its packet templates."""
        packet_generator.duration_ms = self._duration_ms
        self._geometry = _Geometry(framebuffer, packet_generator, wraps)
        self._bake(packet_generator)

    def _bake(self, packet_generator: PacketGenerator) -> None:
        """Prebake the packet templates at the generator's current duration."""
        self._templates: list[PacketTemplate] = packet_generator.create_templates(
            source=self._source,
            target=self._serial.value,
        )

        # Ack-gated flow control (ANIM-01/ANIM-02, D4-03): bake the
        # ack_required flag once into the template that carries the probe
        # (default: first packet; large-tile matrix: final CopyFrameBuffer,
        # D4-04). The hot send loop never touches the flags byte again.
        self._probe_index = packet_generator.probe_template_index
        self._templates[self._probe_index].data[FLAGS_OFFSET] |= ACK_REQUIRED_FLAG

    @classmethod
    def _for_device(cls, device: Light) -> Animator:
        """Create the Animator a light owns; see `Light.animator`.

        A single light's geometry needs no query, so its Animator is ready at
        once. A matrix or multizone light's geometry is resolved by the first
        `prepare()`. The light describes its own geometry, so the Animator
        never needs to know the device classes.
        """
        serial = Serial.from_string(device.serial)
        animator = cls.__new__(cls)
        animator._open_session(device.ip, serial, device.port)
        animator._device = device
        animator._duration_ms = 0
        geometry = device._animation_geometry()
        if geometry is not None:
            animator._install(*geometry)
        return animator

    async def prepare(self, *, enable_thread: bool = False) -> Animator:
        """Query the device for its geometry, once, and get ready to draw.

        A light's Animator learns its tile layout or zone count from the
        device the first time it is prepared; later calls make no query.
        Every call also tells the device that frames are about to bypass its
        own colour methods, so a Ceiling or Mirror component call reads the
        device instead of undoing the animation. A single light's Animator is
        ready without this, but preparing it is harmless.

        A light evidenced as Thread, by its own replies or an mDNS record, is
        refused unless the caller passes ``enable_thread=True``: a Thread mesh
        is not built for a steady stream of frames. A light not yet heard
        from is not refused.

        Args:
            enable_thread: Stream to a light evidenced as Thread anyway.
                Off by default.

        Returns:
            This Animator, so `animator = await device.animator.prepare()`
            reads naturally.

        Raises:
            ValueError: If a matrix light reports no tiles, or a multizone
                light does not support the extended multizone protocol.
            LifxUnsupportedCommandError: If the light is evidenced as Thread
                and ``enable_thread`` is False

        Example:
            ```python
            async with await Device.connect("192.168.1.100") as device:
                animator = await device.animator.prepare()

            while running:
                animator.send_frame(frame)
                await asyncio.sleep(1 / 30)
            ```
        """
        device = self._device
        if device is None:
            return self
        device._refuse_thread_frames("Animator.prepare()", enable_thread=enable_thread)
        if self._geometry is None:
            framebuffer, packet_generator = await device._query_animation_geometry()
            # A concurrent prepare() may have finished first; keep its templates.
            if self._geometry is None:
                self._install(framebuffer, packet_generator)

        # Frames go straight out over UDP rather than through set64(), so the
        # device never hears about them. Tell it now: a component light
        # (Ceiling, Mirror) forgets the tile it last wrote, so its next
        # component call reads the device instead of undoing the animation.
        device._zones_changed()
        return self

    @classmethod
    async def for_matrix(
        cls,
        device: MatrixLight,
        duration_ms: int = 0,
        *,
        enable_thread: bool = False,
    ) -> Animator:
        """Return the device's Animator, prepared for a MatrixLight.

        Deprecated: use `device.animator` and `await device.animator.prepare()`.
        Every call returns the same Animator, the one the device owns, so a
        library effect and this caller share one writer and one ack gate.

        Args:
            device: MatrixLight device (must be connected)
            duration_ms: Transition duration in milliseconds (default 0 for
                instant), applied to frames sent through `send_frame()`.
            enable_thread: Stream to a light evidenced as Thread anyway;
                see `prepare()`. Off by default.

        Returns:
            The device's Animator

        Raises:
            LifxUnsupportedCommandError: If the device is evidenced as Thread
                and ``enable_thread`` is False
            ValueError: If the device reports no tiles
        """
        _warn_deprecated("for_matrix")
        return await cls._borrow(device, duration_ms, enable_thread)

    @classmethod
    async def for_multizone(
        cls,
        device: MultiZoneLight,
        duration_ms: int = 0,
        *,
        enable_thread: bool = False,
    ) -> Animator:
        """Return the device's Animator, prepared for a MultiZoneLight.

        Deprecated: use `device.animator` and `await device.animator.prepare()`.
        Every call returns the same Animator, the one the device owns. Only
        devices with extended multizone capability are supported.

        Args:
            device: MultiZoneLight device (must be connected and support
                   extended multizone protocol)
            duration_ms: Transition duration in milliseconds (default 0 for
                instant), applied to frames sent through `send_frame()`.
            enable_thread: Stream to a light evidenced as Thread anyway;
                see `prepare()`. Off by default.

        Returns:
            The device's Animator

        Raises:
            LifxUnsupportedCommandError: If the device is evidenced as Thread
                and ``enable_thread`` is False
            ValueError: If device doesn't support extended multizone
        """
        _warn_deprecated("for_multizone")
        return await cls._borrow(device, duration_ms, enable_thread)

    @classmethod
    async def _borrow(
        cls, device: Light, duration_ms: int, enable_thread: bool
    ) -> Animator:
        """Prepare the device's Animator and set its transition duration."""
        animator = await device.animator.prepare(enable_thread=enable_thread)
        animator.duration_ms = duration_ms
        return animator

    @classmethod
    def for_light(
        cls,
        device: Light,
        duration_ms: int = 0,
        *,
        enable_thread: bool = False,
    ) -> Animator:
        """Return the device's Animator for a single Light device.

        Deprecated: use `device.animator`. Every call returns the same
        Animator, the one the device owns. A single light's Animator needs no
        device query, so this stays synchronous.

        Args:
            device: Light device (must have ip and serial set)
            duration_ms: Transition duration in milliseconds (default 0 for
                instant), applied to frames sent through `send_frame()`.
            enable_thread: Stream to a light evidenced as Thread anyway;
                see `prepare()`. Off by default.

        Returns:
            The device's Animator

        Raises:
            LifxUnsupportedCommandError: If the device is evidenced as Thread
                and ``enable_thread`` is False
            RuntimeError: If the device is a matrix or multizone light whose
                Animator has not been prepared yet; await
                `device.animator.prepare()` instead.
        """
        _warn_deprecated("for_light")
        device._refuse_thread_frames(
            "Animator.for_light()", enable_thread=enable_thread
        )
        animator = device.animator
        animator._require_geometry()
        animator.duration_ms = duration_ms
        return animator

    def _writer(self, *, duration_ms: int = 0) -> AnimatorWriter:
        """Borrow this Animator to draw on the device's own canvas.

        Args:
            duration_ms: Transition duration for this writer's frames

        Returns:
            A writer that sends through this Animator's socket and ack gate

        Raises:
            RuntimeError: If the Animator has not been prepared yet
        """
        geometry = self._require_geometry()
        return AnimatorWriter(
            self, geometry.framebuffer, duration_ms=duration_ms, wraps=geometry.wraps
        )

    def _require_geometry(self) -> _Geometry:
        """Return the device's geometry, or explain how to resolve it."""
        geometry = self._geometry
        if geometry is None:
            raise RuntimeError(
                "The Animator does not know the device's geometry yet: "
                "await device.animator.prepare() first"
            )
        return geometry

    @property
    def duration_ms(self) -> int:
        """Transition duration, in milliseconds, of frames sent by `send_frame()`.

        When non-zero, the device smoothly interpolates between frames.
        """
        return self._duration_ms

    @duration_ms.setter
    def duration_ms(self, value: int) -> None:
        if value < 0:
            raise ValueError(f"duration_ms must be non-negative, got {value}")
        self._duration_ms = value

    @property
    def pixel_count(self) -> int:
        """Get total number of input pixels (canvas size for multi-tile)."""
        # For multi-tile devices, this returns the canvas size
        # For single-tile/multizone, this returns device pixel count
        return self._require_geometry().framebuffer.canvas_size

    @property
    def canvas_width(self) -> int:
        """Get width of the logical canvas in pixels."""
        return self._require_geometry().framebuffer.canvas_width

    @property
    def canvas_height(self) -> int:
        """Get height of the logical canvas in pixels."""
        return self._require_geometry().framebuffer.canvas_height

    @property
    def wraps(self) -> bool:
        """True if the canvas is a ring: its last pixel sits next to its first."""
        return self._require_geometry().wraps

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
            RuntimeError: If the Animator has not been prepared yet.
        """
        geometry = self._require_geometry()
        return self._send(geometry.framebuffer, hsbk, self._duration_ms)

    def _send(
        self,
        canvas: FrameBuffer,
        hsbk: list[tuple[int, int, int, int]],
        duration_ms: int,
    ) -> AnimatorStats:
        """Send one writer's frame, mapped by its canvas, at its duration."""
        start_time = time.perf_counter()
        _check_length(canvas, hsbk)
        if not self._slot_writers:
            # A whole-tile frame replaces a tile left over from slots.
            self._hold = None
        return self._transmit(lambda: canvas.apply(hsbk), duration_ms, start_time)

    def _slot_writer(
        self,
        slot: ComponentSlot,
        canvas: FrameBuffer,
        tile: list[HSBK],
        *,
        duration_ms: int = 0,
        wraps: bool = False,
        whole_light: bool = False,
    ) -> AnimatorWriter:
        """Borrow this Animator to draw on one light component's slot.

        The first slot holds ``tile``, the light component colours in buffer
        order, so a light component with no effect keeps showing them. Later
        slots share that held tile.

        Args:
            slot: The light component's buffer positions
            canvas: The canvas the light component's effect draws on
            tile: Current colours of the whole tile, in buffer order
            duration_ms: Transition duration for this writer's frames
            wraps: True if the canvas is a ring, such as a Mirror ring
            whole_light: True if the writer draws this light component's
                share of a whole-light effect

        Returns:
            A writer whose frames land on the light component's slot

        Raises:
            RuntimeError: If the Animator has not been prepared yet
        """
        self._require_geometry()
        if not self._slot_writers:
            self._hold = HeldTile(tile)
        writer = AnimatorWriter(
            self,
            canvas,
            duration_ms=duration_ms,
            wraps=wraps,
            slot=slot,
            whole_light=whole_light,
        )
        self._slot_writers[writer] = slot
        return writer

    def _animating(self) -> frozenset[str]:
        """Names of the light components that writers are drawing on."""
        return frozenset(slot.component for slot in self._slot_writers.values())

    def _held_tile(self) -> list[HSBK] | None:
        """Colours the held tile shows, or None if nothing is held.

        A tile stays held after the last slot is released, until something
        else writes the tile, so the light components keep the colours their
        callers gave them while effects ran.
        """
        return self._hold.target if self._hold is not None else None

    def _retarget_hold(self, tile: list[HSBK], duration: float) -> None:
        """Fade the held tile towards new colours; the next frame shows them.

        Only called while a slot is open, and an open slot always has a held
        tile beneath it.
        """
        hold = self._hold
        assert hold is not None
        hold.retarget(tile, duration)

    def _forget_hold(self) -> None:
        """Forget a held tile no slot is using, after the tile was rewritten."""
        if not self._slot_writers:
            self._hold = None

    def _release_slot(self, writer: AnimatorWriter, slot: ComponentSlot) -> None:
        """Stop composing a writer's frames into its light component's slot.

        Once no writer draws on the light component, its last frame is what
        the device shows there, so it becomes that part of the held tile. A
        later change to the light component then starts from those colours,
        and darkening it keeps the frame's hue, saturation and kelvin rather
        than switching the firmware to white.
        """
        if writer not in self._slot_writers:
            return
        del self._slot_writers[writer]
        if slot.component in self._animating():
            return
        current = self._slot_frames.pop(slot.component, None)
        # A slot fading towards a target ends up showing it.
        last = self._slot_targets.pop(slot.component, None) or current
        hold = self._hold
        if last is None or hold is None:
            return
        _, canvas, frame = last
        mapped = canvas.apply(frame)
        # Only this light component's cells change; the other light
        # component keeps any fade its caller started.
        hold.set_cells(
            {
                position: HSBK.from_protocol(LightHsbk(*mapped[source]))
                for position, source in zip(slot.positions, slot.sources)
            }
        )

    def _store_slot(
        self,
        writer: AnimatorWriter,
        slot: ComponentSlot,
        hsbk: list[tuple[int, int, int, int]],
        *,
        settled: bool = False,
    ) -> bool:
        """Keep a light component's latest frame for the next composed tile.

        A frame is kept even when the ack gate drops the tile it was sent
        with, so the next tile any slot sends carries it.

        Args:
            writer: The writer drawing the frame
            slot: The writer's light component slot
            hsbk: The frame
            settled: Keep the frame as the slot's target rather than as the
                colours of the moment

        Returns:
            False if the writer was released and no longer draws on the light
        """
        _check_length(writer._canvas, hsbk)
        if writer not in self._slot_writers:
            return False
        entry = (slot, writer._canvas, hsbk)
        if settled:
            self._slot_targets[slot.component] = entry
            return True
        self._slot_frames[slot.component] = entry
        if writer._streaming:
            # A streamed frame is what the slot shows; no fade runs there.
            self._slot_targets.pop(slot.component, None)
        return True

    def _send_slot(
        self,
        writer: AnimatorWriter,
        slot: ComponentSlot,
        hsbk: list[tuple[int, int, int, int]],
        duration_ms: int,
        *,
        settled: bool = False,
    ) -> AnimatorStats:
        """Keep a light component's frame and send the tile of every slot."""
        start_time = time.perf_counter()
        if not self._store_slot(writer, slot, hsbk, settled=settled):
            # A released writer no longer draws on the light.
            return AnimatorStats(packets_sent=0, total_time_ms=0.0)
        hold = self._hold
        # An open slot writer always has a held tile beneath it.
        assert hold is not None
        return self._transmit(
            lambda: self._compose(hold, settled=settled), duration_ms, start_time
        )

    def _compose(
        self, hold: HeldTile, *, settled: bool = False
    ) -> list[tuple[int, int, int, int]]:
        """Build the whole tile: the held tile, overlaid with each slot's frame.

        Args:
            hold: The held tile beneath the slots
            settled: Use the held tile's final colours and each slot's target,
                not colours part-way through a fade
        """
        tile = hold.target_tuples() if settled else hold.tuples_at(time.monotonic())
        frames = dict(self._slot_frames)
        if settled:
            frames.update(self._slot_targets)
        for slot, canvas, frame in frames.values():
            mapped = canvas.apply(frame)
            for position, source in zip(slot.positions, slot.sources):
                tile[position] = mapped[source]
        return tile

    def _transmit(
        self,
        build: Callable[[], list[tuple[int, int, int, int]]],
        duration_ms: int,
        start_time: float,
    ) -> AnimatorStats:
        """Send the tile ``build`` produces, unless the ack gate is closed."""

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

        # Apply the writer's canvas mapping (orientation, ring scatter, slots)
        device_data = build()

        # Writers sharing this Animator may use different durations; rebake
        # the templates only when the duration changes.
        packet_generator = self._require_geometry().packet_generator
        if packet_generator.duration_ms != duration_ms:
            packet_generator.duration_ms = duration_ms
            self._bake(packet_generator)

        # Update colors in prebaked templates
        packet_generator.update_colors(self._templates, device_data)

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
