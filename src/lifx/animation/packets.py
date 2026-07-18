"""Device-specific packet generators for animation.

This module provides packet generators that create prebaked packet templates
for high-performance animation. All packets (header + payload) are prebaked
at initialization time, and only color data and sequence numbers are updated
per frame.

**Performance Optimization:**
- Complete packets (header + payload) are prebaked as bytearrays
- Per-frame updates only touch color bytes and sequence number
- Zero object allocation in the hot path
- Direct struct.pack_into for color updates

Supported Devices:
    - MatrixLight: Uses Set64 packets (64 pixels per packet per tile)
    - MultiZoneLight: Uses SetExtendedColorZones (82 zones per packet)

Example:
    ```python
    from lifx.animation.packets import MatrixPacketGenerator

    # Create generator and prebake packets
    gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
    templates = gen.create_templates(source=12345, target=b"\\xd0\\x73...")

    # Per-frame: update colors and send
    gen.update_colors(templates, hsbk_data)
    for tmpl in templates:
        tmpl.data[23] = sequence  # Update sequence byte
        socket.sendto(tmpl.data, (ip, port))
    ```
"""

from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import chain
from typing import ClassVar

# Header constants
HEADER_SIZE = 36
FLAGS_OFFSET = 22  # Offset of flags byte in header (Frame Address: 8-byte
# target + 6-byte reserved = offset 8+8+6=22)
ACK_REQUIRED_FLAG = 0x02  # Bit 1 of the flags byte, matching the
# (ACK_REQUIRED & 0b1) << 1 packing in _build_header
SEQUENCE_OFFSET = 23  # Offset of sequence byte in header

# Header field values for animation packets
PROTOCOL_NUMBER = 1024
ORIGIN = 0
ADDRESSABLE = 1
TAGGED = 0
ACK_REQUIRED = 0
RES_REQUIRED = 0


@dataclass(slots=True)
class PacketTemplate:
    """Prebaked packet template for zero-allocation animation.

    Contains a complete packet (header + payload) as a mutable bytearray.
    Only the sequence byte and color data need to be updated per frame.

    Attributes:
        data: Complete packet bytes (header + payload)
        color_offset: Byte offset where color data starts
        color_count: Number of HSBK colors in this packet
        hsbk_start: Starting index in the input HSBK array
        fmt: Pre-computed struct format string for bulk color packing
    """

    data: bytearray
    color_offset: int
    color_count: int
    hsbk_start: int
    fmt: str


def _build_header(
    pkt_type: int,
    source: int,
    target: bytes,
    payload_size: int,
) -> bytearray:
    """Build a LIFX header as a bytearray.

    Args:
        pkt_type: Packet type identifier
        source: Client source ID
        target: 6-byte device serial
        payload_size: Size of payload in bytes

    Returns:
        36-byte header as bytearray
    """
    header = bytearray(HEADER_SIZE)

    # Frame (8 bytes)
    size = HEADER_SIZE + payload_size
    protocol_field = (
        (ORIGIN & 0b11) << 14
        | (TAGGED & 0b1) << 13
        | (ADDRESSABLE & 0b1) << 12
        | (PROTOCOL_NUMBER & 0xFFF)
    )
    struct.pack_into("<HHI", header, 0, size, protocol_field, source)

    # Frame Address (16 bytes)
    # target (8 bytes) + reserved (6 bytes) + flags (1 byte) + sequence (1 byte)
    target_padded = target + b"\x00\x00" if len(target) == 6 else target
    flags = (RES_REQUIRED & 0b1) | ((ACK_REQUIRED & 0b1) << 1)
    struct.pack_into("<8s6sBB", header, 8, target_padded, b"\x00" * 6, flags, 0)

    # Protocol Header (12 bytes)
    struct.pack_into("<QHH", header, 24, 0, pkt_type, 0)

    return header


class PacketGenerator(ABC):
    """Abstract base class for packet generators.

    Packet generators prebake complete packets (header + payload) at
    initialization time. Per-frame, only color data and sequence numbers
    are updated in place.
    """

    @abstractmethod
    def create_templates(self, source: int, target: bytes) -> list[PacketTemplate]:
        """Create prebaked packet templates.

        Args:
            source: Client source ID for header
            target: 6-byte device serial for header

        Returns:
            List of PacketTemplate with prebaked packets
        """

    @abstractmethod
    def update_colors(
        self, templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
    ) -> None:
        """Update color data in prebaked templates.

        Args:
            templates: Prebaked packet templates
            hsbk: Protocol-ready HSBK data for all pixels
        """

    @abstractmethod
    def pixel_count(self) -> int:
        """Get the total pixel count this generator expects."""

    # Traceability: single baked probe D4-03; first-packet arm D4-01 (spike
    # 003 measured it at 0.0% concurrent-query loss); uniform application
    # D4-02; large-tile override D4-04.
    @property
    def probe_template_index(self) -> int:
        """Template index that carries the ack-required flow-control probe.

        The Animator bakes the `ack_required` flag into exactly one
        prebaked template at initialisation time -- this property names
        which one. Default is the first packet of the frame. Flow control
        applies uniformly to all generator families with no per-family
        carve-outs; `MatrixPacketGenerator` overrides this for large-tile
        mode.
        """
        return 0


class MatrixPacketGenerator(PacketGenerator):
    """Packet generator for MatrixLight devices.

    Generates Set64 packets for all tiles. Uses prebaked packet templates
    with complete headers for maximum performance.

    For standard tiles (≤64 pixels):

        - Single Set64 packet directly to display buffer (fb_index=0)

    For large tiles (>64 pixels), colours are chunked row-aligned — each
    Set64 packet covers whole rows of the tile (rows_per_packet = 64 //
    tile_width), matching the device's row-major Set64 fill order from
    (x=0, y=y_offset). The colour slice offset (hsbk_start = y_offset *
    tile_width) therefore always matches the rect's y offset, even on
    widths that do not evenly divide 64:

        - Ceiling 16x8 (128 pixels, divides evenly): 2 Set64 packets of 64
          colours each (rows 0-3, 4-7) + 1 CopyFrameBuffer = 3 packets/tile.
        - Ceiling 13x26 (338 pixels, does not divide evenly): 7 Set64
          packets of 52 colours each for the first 6 (4 rows x 13 width)
          plus a final partial batch of 26 colours (2 rows x 13 width) +
          1 CopyFrameBuffer = 8 packets/tile.
        - Multiple Set64 packets to temp buffer (fb_index=1)
        - CopyFrameBuffer packet to copy fb_index=1 → fb_index=0

    Set64 Payload Layout (522 bytes):

        - Offset 0: tile_index (uint8)
        - Offset 1: length (uint8, always 1)
        - Offset 2-5: TileBufferRect (fb_index, x, y, width - 4 x uint8)
        - Offset 6-9: duration (uint32)
        - Offset 10-521: colors (64 x HSBK, each 8 bytes)

    CopyFrameBuffer Payload Layout (15 bytes):

        - Offset 0: tile_index (uint8)
        - Offset 1: length (uint8, always 1)
        - Offset 2: src_fb_index (uint8, 1 = temp buffer)
        - Offset 3: dst_fb_index (uint8, 0 = display)
        - Offset 4-7: src_x, src_y, dst_x, dst_y (uint8 each)
        - Offset 8-9: width, height (uint8 each)
        - Offset 10-13: duration (uint32)
        - Offset 14: reserved (uint8)
    """

    # Packet types
    SET64_PKT_TYPE: ClassVar[int] = 715
    COPY_FRAME_BUFFER_PKT_TYPE: ClassVar[int] = 716

    # Set64 payload layout
    _SET64_PAYLOAD_SIZE: ClassVar[int] = 522
    _COLORS_OFFSET_IN_PAYLOAD: ClassVar[int] = 10
    _MAX_COLORS_PER_PACKET: ClassVar[int] = 64

    # CopyFrameBuffer payload layout
    _COPY_FB_PAYLOAD_SIZE: ClassVar[int] = 15

    def __init__(
        self,
        tile_count: int,
        tile_width: int,
        tile_height: int,
        duration_ms: int = 0,
    ) -> None:
        """Initialize matrix packet generator.

        Args:
            tile_count: Number of tiles in the device chain
            tile_width: Width of each tile in pixels
            tile_height: Height of each tile in pixels
            duration_ms: Transition duration in milliseconds (default 0 for instant)
        """
        self._tile_count = tile_count
        self._tile_width = tile_width
        self._tile_height = tile_height
        self._duration_ms = duration_ms
        self._pixels_per_tile = tile_width * tile_height
        self._total_pixels = tile_count * self._pixels_per_tile

        # Determine if we need large tile mode (>64 pixels per tile)
        self._is_large_tile = self._pixels_per_tile > self._MAX_COLORS_PER_PACKET

        # Calculate packets needed per tile. Chunking is row-aligned to match
        # the device's row-major Set64 fill order (mirrors the hardware-proven
        # MatrixLight.set_matrix_colors batching in devices/matrix.py): each
        # packet covers whole rows, never a raw 64-pixel slice that could
        # straddle a row boundary on widths that do not divide 64 (D4-05).
        self._rows_per_packet = self._MAX_COLORS_PER_PACKET // tile_width
        self._packets_per_tile = -(-tile_height // self._rows_per_packet)

    @property
    def is_large_tile(self) -> bool:
        """Check if tiles have >64 pixels (requires multi-packet strategy)."""
        return self._is_large_tile

    @property
    def packets_per_tile(self) -> int:
        """Get number of Set64 packets needed per tile."""
        return self._packets_per_tile

    # Traceability: D4-04 (probe on the frame-commit CopyFB, matching
    # Glowup's proven field behaviour on >64-zone ceilings);
    # hardware-validated in the ANIM-04 UAT (plan 04-07); the single-Set64
    # arm is the one spike 003 measured (0.0% loss).
    @property
    def probe_template_index(self) -> int:
        """Template index that carries the ack-required flow-control probe.

        In large-tile mode the probe attaches to the FINAL CopyFrameBuffer
        -- the frame-commit packet, since nothing is visible until the
        buffer swap. The CopyFB's ack RTT includes the device's drain of
        the preceding Set64 burst, a strictly better congestion signal
        than acking the first Set64 of a multi-packet frame. This property
        is the one-line fallback seam to index 0 (first Set64) should
        hardware disagree.

        For standard (≤64px) tiles, the probe sits on the single Set64
        packet.
        """
        if self._is_large_tile:
            return self._tile_count * (self._packets_per_tile + 1) - 1
        return 0

    def pixel_count(self) -> int:
        """Get total pixel count."""
        return self._total_pixels

    def create_templates(self, source: int, target: bytes) -> list[PacketTemplate]:
        """Create prebaked packet templates for all tiles.

        Args:
            source: Client source ID
            target: 6-byte device serial

        Returns:
            List of PacketTemplate with complete prebaked packets
        """
        if self._is_large_tile:
            return self._create_large_tile_templates(source, target)
        else:
            return self._create_standard_templates(source, target)

    def _create_standard_templates(
        self, source: int, target: bytes
    ) -> list[PacketTemplate]:
        """Create templates for standard tiles (≤64 pixels each)."""
        templates: list[PacketTemplate] = []

        for tile_idx in range(self._tile_count):
            # Build header
            header = _build_header(
                self.SET64_PKT_TYPE, source, target, self._SET64_PAYLOAD_SIZE
            )

            # Build payload
            payload = bytearray(self._SET64_PAYLOAD_SIZE)
            payload[0] = tile_idx  # tile_index
            payload[1] = 1  # length
            # TileBufferRect: fb_index=0, x=0, y=0, width=tile_width
            struct.pack_into("<BBBB", payload, 2, 0, 0, 0, self._tile_width)
            # duration
            struct.pack_into("<I", payload, 6, self._duration_ms)
            # colors filled with black as default
            for i in range(64):
                offset = self._COLORS_OFFSET_IN_PAYLOAD + i * 8
                struct.pack_into("<HHHH", payload, offset, 0, 0, 0, 3500)

            # Combine header + payload
            packet = header + payload

            color_count = min(self._pixels_per_tile, 64)
            templates.append(
                PacketTemplate(
                    data=packet,
                    color_offset=HEADER_SIZE + self._COLORS_OFFSET_IN_PAYLOAD,
                    color_count=color_count,
                    hsbk_start=tile_idx * self._pixels_per_tile,
                    fmt=f"<{'HHHH' * color_count}",
                )
            )

        return templates

    def _create_large_tile_templates(
        self, source: int, target: bytes
    ) -> list[PacketTemplate]:
        """Create templates for large tiles (>64 pixels each)."""
        templates: list[PacketTemplate] = []

        for tile_idx in range(self._tile_count):
            tile_pixel_start = tile_idx * self._pixels_per_tile

            # Create Set64 packets for this tile. Row-aligned: each packet
            # covers whole rows of the tile, so the colour slice offset
            # (color_start) and the rect's y offset both advance by
            # rows_per_packet rows per packet — they can never disagree, even
            # when tile_width does not evenly divide 64 (Pitfall 1, D4-04).
            # Ceiling division on packets_per_tile guarantees the final
            # packet always covers at least one row, so no zero-count guard
            # is needed here.
            for pkt_idx in range(self._packets_per_tile):
                y_offset = pkt_idx * self._rows_per_packet
                rows = min(self._rows_per_packet, self._tile_height - y_offset)
                color_count = rows * self._tile_width
                color_start = y_offset * self._tile_width

                # Build header
                header = _build_header(
                    self.SET64_PKT_TYPE, source, target, self._SET64_PAYLOAD_SIZE
                )

                # Build payload
                payload = bytearray(self._SET64_PAYLOAD_SIZE)
                payload[0] = tile_idx  # tile_index
                payload[1] = 1  # length
                # TileBufferRect: fb_index=1 (temp), x=0, y=y_offset, width
                struct.pack_into("<BBBB", payload, 2, 1, 0, y_offset, self._tile_width)
                # duration
                struct.pack_into("<I", payload, 6, self._duration_ms)
                # colors filled with black as default
                for i in range(64):
                    offset = self._COLORS_OFFSET_IN_PAYLOAD + i * 8
                    struct.pack_into("<HHHH", payload, offset, 0, 0, 0, 3500)

                packet = header + payload

                templates.append(
                    PacketTemplate(
                        data=packet,
                        color_offset=HEADER_SIZE + self._COLORS_OFFSET_IN_PAYLOAD,
                        color_count=color_count,
                        hsbk_start=tile_pixel_start + color_start,
                        fmt=f"<{'HHHH' * color_count}",
                    )
                )

            # Create CopyFrameBuffer packet for this tile
            header = _build_header(
                self.COPY_FRAME_BUFFER_PKT_TYPE,
                source,
                target,
                self._COPY_FB_PAYLOAD_SIZE,
            )

            payload = bytearray(self._COPY_FB_PAYLOAD_SIZE)
            payload[0] = tile_idx  # tile_index
            payload[1] = 1  # length
            payload[2] = 1  # src_fb_index (temp buffer)
            payload[3] = 0  # dst_fb_index (display)
            struct.pack_into("<BBBB", payload, 4, 0, 0, 0, 0)  # src/dst x,y
            payload[8] = self._tile_width
            payload[9] = self._tile_height
            struct.pack_into("<I", payload, 10, 0)  # duration = 0
            payload[14] = 0  # reserved

            packet = header + payload

            # CopyFrameBuffer has no colors to update
            templates.append(
                PacketTemplate(
                    data=packet,
                    color_offset=0,  # No colors
                    color_count=0,
                    hsbk_start=0,
                    fmt="",
                )
            )

        return templates

    def update_colors(
        self, templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
    ) -> None:
        """Update color data in prebaked templates.

        Args:
            templates: Prebaked packet templates
            hsbk: Protocol-ready HSBK data for all pixels

        Raises:
            ValueError: If hsbk has fewer values than the total pixel count
        """
        if len(hsbk) < self._total_pixels:
            raise ValueError(
                f"Expected {self._total_pixels} HSBK values, got {len(hsbk)}"
            )

        for tmpl in templates:
            if tmpl.color_count == 0:
                continue  # Skip CopyFrameBuffer packets

            # Write all HSBK tuples into the packet buffer with a single
            # C-level pack using the precomputed bulk format string
            struct.pack_into(
                tmpl.fmt,
                tmpl.data,
                tmpl.color_offset,
                *chain.from_iterable(
                    hsbk[tmpl.hsbk_start : tmpl.hsbk_start + tmpl.color_count]
                ),
            )


class MultiZonePacketGenerator(PacketGenerator):
    """Packet generator for MultiZoneLight devices with extended multizone.

    Uses SetExtendedColorZones packets (up to 82 zones each). For devices
    with >82 zones, multiple packets are generated.

    SetExtendedColorZones Payload Layout (664 bytes):

        - Offset 0-3: duration (uint32)
        - Offset 4: apply (uint8, 1 = APPLY)
        - Offset 5-6: zone_index (uint16)
        - Offset 7: colors_count (uint8)
        - Offset 8-663: colors (82 x HSBK, each 8 bytes)
    """

    SET_EXTENDED_COLOR_ZONES_PKT_TYPE: ClassVar[int] = 510

    _PAYLOAD_SIZE: ClassVar[int] = 664
    _COLORS_OFFSET_IN_PAYLOAD: ClassVar[int] = 8
    _MAX_ZONES_PER_PACKET: ClassVar[int] = 82

    def __init__(self, zone_count: int, duration_ms: int = 0) -> None:
        """Initialize multizone packet generator.

        Args:
            zone_count: Total number of zones on the device
            duration_ms: Transition duration in milliseconds (default 0 for instant)
        """
        self._zone_count = zone_count
        self._duration_ms = duration_ms
        self._packets_needed = (
            zone_count + self._MAX_ZONES_PER_PACKET - 1
        ) // self._MAX_ZONES_PER_PACKET

    def pixel_count(self) -> int:
        """Get total zone count."""
        return self._zone_count

    def create_templates(self, source: int, target: bytes) -> list[PacketTemplate]:
        """Create prebaked packet templates for all zones.

        Args:
            source: Client source ID
            target: 6-byte device serial

        Returns:
            List of PacketTemplate with complete prebaked packets
        """
        templates: list[PacketTemplate] = []

        for pkt_idx in range(self._packets_needed):
            zone_start = pkt_idx * self._MAX_ZONES_PER_PACKET
            zone_end = min(zone_start + self._MAX_ZONES_PER_PACKET, self._zone_count)
            zone_count = zone_end - zone_start

            # Build header
            header = _build_header(
                self.SET_EXTENDED_COLOR_ZONES_PKT_TYPE,
                source,
                target,
                self._PAYLOAD_SIZE,
            )

            # Build payload
            payload = bytearray(self._PAYLOAD_SIZE)
            # duration
            struct.pack_into("<I", payload, 0, self._duration_ms)
            # apply = 1 (APPLY)
            payload[4] = 1
            # zone_index
            struct.pack_into("<H", payload, 5, zone_start)
            # colors_count
            payload[7] = zone_count
            # colors filled with black as default
            for i in range(82):
                offset = self._COLORS_OFFSET_IN_PAYLOAD + i * 8
                struct.pack_into("<HHHH", payload, offset, 0, 0, 0, 3500)

            packet = header + payload

            templates.append(
                PacketTemplate(
                    data=packet,
                    color_offset=HEADER_SIZE + self._COLORS_OFFSET_IN_PAYLOAD,
                    color_count=zone_count,
                    hsbk_start=zone_start,
                    fmt=f"<{'HHHH' * zone_count}",
                )
            )

        return templates

    def update_colors(
        self, templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
    ) -> None:
        """Update color data in prebaked templates.

        Args:
            templates: Prebaked packet templates
            hsbk: Protocol-ready HSBK data for all zones

        Raises:
            ValueError: If hsbk has fewer values than the total zone count
        """
        if len(hsbk) < self._zone_count:
            raise ValueError(
                f"Expected {self._zone_count} HSBK values, got {len(hsbk)}"
            )

        for tmpl in templates:
            # Write all HSBK tuples into the packet buffer with a single
            # C-level pack using the precomputed bulk format string
            struct.pack_into(
                tmpl.fmt,
                tmpl.data,
                tmpl.color_offset,
                *chain.from_iterable(
                    hsbk[tmpl.hsbk_start : tmpl.hsbk_start + tmpl.color_count]
                ),
            )


class LightPacketGenerator(PacketGenerator):
    """Packet generator for single Light devices.

    Uses LightSetColor packets (PKT_TYPE=102) for single-pixel color control.
    Designed for frame-based effects on individual lights.

    LightSetColor Payload Layout (13 bytes):
        - Offset 0: reserved (uint8)
        - Offset 1-8: LightHsbk (H, S, B, K as uint16 = 8 bytes)
        - Offset 9-12: duration (uint32)
    """

    SET_COLOR_PKT_TYPE: ClassVar[int] = 102

    _PAYLOAD_SIZE: ClassVar[int] = 13
    _COLOR_OFFSET_IN_PAYLOAD: ClassVar[int] = 1

    def __init__(self, duration_ms: int = 0) -> None:
        """Initialize light packet generator.

        Args:
            duration_ms: Transition duration in milliseconds (default 0 for instant)
        """
        self._duration_ms = duration_ms

    def pixel_count(self) -> int:
        """Get total pixel count (always 1 for single lights)."""
        return 1

    def create_templates(self, source: int, target: bytes) -> list[PacketTemplate]:
        """Create prebaked packet template for a single light.

        Args:
            source: Client source ID
            target: 6-byte device serial

        Returns:
            List containing a single PacketTemplate
        """
        header = _build_header(
            self.SET_COLOR_PKT_TYPE, source, target, self._PAYLOAD_SIZE
        )

        payload = bytearray(self._PAYLOAD_SIZE)
        payload[0] = 0  # reserved
        # Default color: black
        struct.pack_into("<HHHH", payload, self._COLOR_OFFSET_IN_PAYLOAD, 0, 0, 0, 3500)
        # duration
        struct.pack_into("<I", payload, 9, self._duration_ms)

        packet = header + payload

        return [
            PacketTemplate(
                data=packet,
                color_offset=HEADER_SIZE + self._COLOR_OFFSET_IN_PAYLOAD,
                color_count=1,
                hsbk_start=0,
                fmt="<HHHH",
            )
        ]

    def update_colors(
        self, templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
    ) -> None:
        """Update color data in the prebaked template.

        Args:
            templates: Prebaked packet templates (single template)
            hsbk: Protocol-ready HSBK data (single color)
        """
        tmpl = templates[0]
        h, s, b, k = hsbk[0]
        struct.pack_into(tmpl.fmt, tmpl.data, tmpl.color_offset, h, s, b, k)
