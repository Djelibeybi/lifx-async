"""LIFX message protocol - combines header and payload."""

from __future__ import annotations

from typing import Any

from lifx.exceptions import LifxProtocolError
from lifx.protocol.header import LifxHeader


def create_message(
    packet: Any,
    source: int,  # Now required
    target: bytes = b"\x00" * 8,
    sequence: int = 0,
    ack_required: bool = False,
    res_required: bool = True,
) -> bytes:
    """Create a complete LIFX message from a packet.

    Args:
        packet: Packet dataclass instance
        source: Client identifier (required, range [2, 0xFFFFFFFF])
        target: Device serial number in bytes (8 bytes with padding)
        sequence: Sequence number for matching requests/responses
        ack_required: Request acknowledgement
        res_required: Request response

    Returns:
        Complete message bytes (header + payload)

    Raises:
        ProtocolError: If packet is invalid
    """
    if not hasattr(packet, "PKT_TYPE"):
        raise LifxProtocolError(f"Packet must have PKT_TYPE attribute: {type(packet)}")

    # Pack payload using the packet's own pack() method
    # This ensures reserved fields and proper field types are handled correctly
    payload = packet.pack()

    # Determine if this is a broadcast (tagged) message
    tagged = target == b"\x00" * 8

    # Create header
    header = LifxHeader.create(
        pkt_type=packet.PKT_TYPE,
        source=source,
        target=target,
        tagged=tagged,
        ack_required=ack_required,
        res_required=res_required,
        sequence=sequence,
        payload_size=len(payload),
    )

    # Combine header and payload
    return header.pack() + payload


def parse_message(data: bytes) -> tuple[LifxHeader, bytes]:
    """Parse a complete LIFX message into header and payload.

    Args:
        data: Message bytes (at least 36 bytes for header)

    Returns:
        Tuple of (header, payload)

    Raises:
        ProtocolError: If message is invalid
    """
    if len(data) < LifxHeader.HEADER_SIZE:
        raise LifxProtocolError(
            f"Message too short: {len(data)} < {LifxHeader.HEADER_SIZE} bytes"
        )

    # Parse header
    header = LifxHeader.unpack(data[: LifxHeader.HEADER_SIZE])

    # Extract payload
    payload = data[LifxHeader.HEADER_SIZE :]

    # Validate payload size
    expected_payload_size = header.size - LifxHeader.HEADER_SIZE
    if len(payload) != expected_payload_size:
        raise LifxProtocolError(
            f"Payload size mismatch: {len(payload)} != {expected_payload_size}"
        )

    return header, payload
