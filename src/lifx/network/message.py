"""LIFX message protocol - combines header and payload."""

from __future__ import annotations

import secrets
from typing import Any

from lifx.exceptions import LifxProtocolError
from lifx.protocol.header import LifxHeader


def create_message(
    packet: Any,
    source: int | None = None,
    target: bytes = b"\x00" * 8,
    sequence: int = 0,
    ack_required: bool = False,
    res_required: bool = True,
) -> bytes:
    """Create a complete LIFX message from a packet.

    Args:
        packet: Packet dataclass instance
        source: Client identifier (random if None)
        target: Device serial number in bytes
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

    # Generate random source if not provided
    if source is None:
        source = secrets.randbelow(0xFFFFFFFF) + 1

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


class MessageBuilder:
    """Builder for creating LIFX messages with consistent source and sequence.

    This class maintains state for source ID and sequence numbers,
    making it easier to create multiple messages from the same client.
    """

    def __init__(self, source: int | None = None) -> None:
        """Initialize message builder.

        Args:
            source: Client identifier (random if None)
        """
        self.source = (
            source if source is not None else secrets.randbelow(0xFFFFFFFF) + 1
        )
        self._sequence = 0

    def create_message(
        self,
        packet: Any,
        target: bytes = b"\x00" * 8,
        ack_required: bool = False,
        res_required: bool = True,
        sequence: int | None = None,
    ) -> bytes:
        """Create a message with specified or auto-incrementing sequence.

        Args:
            packet: Packet dataclass instance
            target: Device serial number in bytes
            ack_required: Request acknowledgement
            res_required: Request response
            sequence: Explicit sequence number (allocates new one if None)

        Returns:
            Complete message bytes
        """
        # If sequence not provided, allocate atomically
        if sequence is None:
            sequence = self.next_sequence()

        msg = create_message(
            packet=packet,
            source=self.source,
            target=target,
            sequence=sequence,
            ack_required=ack_required,
            res_required=res_required,
        )
        return msg

    def next_sequence(self) -> int:
        """Atomically allocate and return the next sequence number.

        This method increments the internal counter immediately to prevent
        race conditions in concurrent request handling.

        Returns:
            Allocated sequence number for this request
        """
        seq = self._sequence
        self._sequence = (self._sequence + 1) % 256
        return seq
