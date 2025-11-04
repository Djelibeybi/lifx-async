"""LIFX protocol header implementation.

The LIFX header is 36 bytes total, consisting of:
- Frame (8 bytes)
- Frame Address (16 bytes)
- Protocol Header (12 bytes)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import ClassVar

from lifx.protocol.models import Serial


@dataclass
class LifxHeader:
    """LIFX protocol header (36 bytes).

    Attributes:
        size: Total packet size in bytes (header + payload)
        protocol: Protocol number (must be 1024)
        source: Unique client identifier
        target: Device serial number (6 or 8 bytes, automatically padded to 8 bytes)
                Note: This is the LIFX serial number, which is often but not always
                the same as the device's MAC address.
        tagged: True for broadcast discovery, False for targeted messages
        ack_required: Request acknowledgement from device
        res_required: Request response from device
        sequence: Sequence number for matching requests/responses
        pkt_type: Packet type identifier
    """

    HEADER_SIZE: ClassVar[int] = 36
    PROTOCOL_NUMBER: ClassVar[int] = 1024
    ORIGIN: ClassVar[int] = 0  # Always 0
    ADDRESSABLE: ClassVar[int] = 1  # Always 1

    size: int
    protocol: int
    source: int
    target: bytes  # Stored as 8 bytes internally (6-byte serial + 2-byte padding)
    tagged: bool
    ack_required: bool
    res_required: bool
    sequence: int
    pkt_type: int

    def __post_init__(self) -> None:
        """Validate header fields and auto-pad serial number if needed."""
        # Auto-pad serial number if 6 bytes
        if len(self.target) == 6:
            self.target = self.target + b"\x00\x00"
        elif len(self.target) != 8:
            raise ValueError(f"Target must be 6 or 8 bytes, got {len(self.target)}")

        if self.protocol != self.PROTOCOL_NUMBER:
            raise ValueError(
                f"Protocol must be {self.PROTOCOL_NUMBER}, got {self.protocol}"
            )
        if self.sequence > 255:
            raise ValueError(f"Sequence must be 0-255, got {self.sequence}")

    @property
    def target_serial(self) -> bytes:
        """Get the 6-byte serial number without padding.

        Returns:
            6-byte serial number
        """
        return Serial.from_protocol(self.target).value

    @classmethod
    def create(
        cls,
        pkt_type: int,
        source: int,
        target: bytes = b"\x00" * 6,
        tagged: bool = False,
        ack_required: bool = False,
        res_required: bool = True,
        sequence: int = 0,
        payload_size: int = 0,
    ) -> LifxHeader:
        """Create a new LIFX header.

        Args:
            pkt_type: Packet type identifier
            source: Unique client identifier
            target: Device serial number (6 or 8 bytes, defaults to broadcast)
            tagged: True for broadcast, False for targeted
            ack_required: Request acknowledgement
            res_required: Request response
            sequence: Sequence number for matching requests/responses
            payload_size: Size of packet payload in bytes

        Returns:
            LifxHeader instance
        """
        return cls(
            size=cls.HEADER_SIZE + payload_size,
            protocol=cls.PROTOCOL_NUMBER,
            source=source,
            target=target,  # __post_init__ will auto-pad if needed
            tagged=tagged,
            ack_required=ack_required,
            res_required=res_required,
            sequence=sequence,
            pkt_type=pkt_type,
        )

    def pack(self) -> bytes:
        """Pack header into 36 bytes.

        Returns:
            Packed header bytes
        """
        # Frame (8 bytes)
        # Byte 0-1: size (uint16)
        # Byte 2-3: origin + tagged + addressable + protocol bits
        # Byte 4-7: source (uint32)

        # Pack protocol field with flags
        protocol_field = (
            (self.ORIGIN & 0b11) << 14
            | (int(self.tagged) & 0b1) << 13
            | (self.ADDRESSABLE & 0b1) << 12
            | (self.protocol & 0xFFF)
        )

        frame = struct.pack("<HHI", self.size, protocol_field, self.source)

        # Frame Address (16 bytes)
        # Byte 0-7: target (uint64)
        # Byte 8-13: reserved (6 bytes)
        # Byte 14: res_required (bit 0) + ack_required (bit 1) + reserved (6 bits)
        # Byte 15: sequence (uint8)

        flags = (int(self.res_required) & 0b1) | ((int(self.ack_required) & 0b1) << 1)

        frame_addr = struct.pack(
            "<Q6sBB",
            int.from_bytes(self.target, byteorder="little"),
            b"\x00" * 6,  # reserved
            flags,
            self.sequence,
        )

        # Protocol Header (12 bytes)
        # Byte 0-7: reserved (uint64)
        # Byte 8-9: type (uint16)
        # Byte 10-11: reserved (uint16)

        protocol_header = struct.pack("<QHH", 0, self.pkt_type, 0)

        return frame + frame_addr + protocol_header

    @classmethod
    def unpack(cls, data: bytes) -> LifxHeader:
        """Unpack header from bytes.

        Args:
            data: Header bytes (at least 36 bytes)

        Returns:
            LifxHeader instance

        Raises:
            ValueError: If data is too short or invalid
        """
        if len(data) < cls.HEADER_SIZE:
            raise ValueError(f"Header data must be at least {cls.HEADER_SIZE} bytes")

        # Unpack Frame (8 bytes)
        size, protocol_field, source = struct.unpack("<HHI", data[0:8])

        # Extract protocol field components
        origin = (protocol_field >> 14) & 0b11
        tagged = bool((protocol_field >> 13) & 0b1)
        addressable = bool((protocol_field >> 12) & 0b1)
        protocol = protocol_field & 0xFFF

        # Validate origin and addressable
        if origin != cls.ORIGIN:
            raise ValueError(f"Invalid origin: {origin}")
        if not addressable:
            raise ValueError("Addressable bit must be set")

        # Unpack Frame Address (16 bytes)
        target_int, _reserved, flags, sequence = struct.unpack("<Q6sBB", data[8:24])
        target = target_int.to_bytes(8, byteorder="little")

        res_required = bool(flags & 0b1)
        ack_required = bool((flags >> 1) & 0b1)

        # Unpack Protocol Header (12 bytes)
        _reserved1, pkt_type, _reserved2 = struct.unpack("<QHH", data[24:36])

        return cls(
            size=size,
            protocol=protocol,
            source=source,
            target=target,
            tagged=tagged,
            ack_required=ack_required,
            res_required=res_required,
            sequence=sequence,
            pkt_type=pkt_type,
        )

    def __repr__(self) -> str:
        """String representation of header."""
        target_serial_str = Serial(value=self.target_serial).to_string()
        return (
            f"LifxHeader(type={self.pkt_type}, size={self.size}, "
            f"source={self.source:#x}, target={target_serial_str}, "
            f"seq={self.sequence}, tagged={self.tagged}, "
            f"ack={self.ack_required}, res={self.res_required})"
        )
