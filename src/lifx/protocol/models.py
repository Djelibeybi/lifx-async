"""Protocol data models and utilities.

Contains dataclasses and utilities for working with LIFX protocol types,
including serial number handling and HEV (High Energy Visible) cycle types.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Serial:
    """LIFX device serial number.

    Encapsulates a device serial number with conversion methods for different formats.
    The LIFX serial number is often the same as the device's MAC address, but can differ
    (particularly the least significant byte may be off by one).

    Attributes:
        value: Serial number as 6 bytes

    Example:
        ```python
        # Create from string
        serial = Serial.from_string("d073d5123456")

        # Convert to protocol format (8 bytes with padding)
        protocol_bytes = serial.to_protocol()

        # Convert to string
        serial_str = serial.to_string()  # "d073d5123456"

        # Create from protocol format
        serial2 = Serial.from_protocol(protocol_bytes)
        ```
    """

    value: bytes

    def __post_init__(self) -> None:
        """Validate serial number after initialization."""
        self._validate_type(self.value)
        self._validate_length(self.value)

    @staticmethod
    def _validate_type(value: bytes) -> None:
        """Validate value is bytes type.

        Args:
            value: Value to validate

        Raises:
            TypeError: If value is not bytes
        """
        if not isinstance(value, bytes):  # type: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"Serial value must be bytes, got {type(value).__name__}")

    @staticmethod
    def _validate_length(value: bytes) -> None:
        """Validate serial number is 6 bytes.

        Args:
            value: Serial number bytes to validate

        Raises:
            ValueError: If length is not 6 bytes
        """
        if len(value) != 6:
            raise ValueError(f"Serial number must be 6 bytes, got {len(value)}")

    @classmethod
    def from_string(cls, serial: str) -> Serial:
        """Create Serial from string format.

        Accepts 12-digit hex string (with or without separators).

        Args:
            serial: 12-digit hex string (e.g., "d073d5123456" or "d0:73:d5:12:34:56")

        Returns:
            Serial instance

        Raises:
            ValueError: If serial number is invalid
            TypeError: If serial is not a string

        Example:
            >>> Serial.from_string("d073d5123456")
            Serial(value=b'\\xd0\\x73\\xd5\\x12\\x34\\x56')
            >>> Serial.from_string("d0:73:d5:12:34:56")  # Also accepts separators
            Serial(value=b'\\xd0\\x73\\xd5\\x12\\x34\\x56')
        """
        cls._validate_string_type(serial)
        serial_clean = cls._remove_separators(serial)
        cls._validate_hex_length(serial_clean)
        serial_bytes = cls._parse_hex(serial_clean)

        return cls(value=serial_bytes)

    @staticmethod
    def _validate_string_type(value: str) -> None:
        """Validate value is string type.

        Args:
            value: Value to validate

        Raises:
            TypeError: If value is not a string
        """
        if not isinstance(value, str):  # type: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"Serial must be a string, got {type(value).__name__}")

    @staticmethod
    def _remove_separators(serial: str) -> str:
        """Remove common separators from serial number string.

        Args:
            serial: Serial string possibly containing separators

        Returns:
            Serial string with all separators removed
        """
        return serial.replace(":", "").replace("-", "").replace(" ", "")

    @staticmethod
    def _validate_hex_length(value: str) -> None:
        """Validate hex string is 12 characters (6 bytes).

        Args:
            value: Hex string to validate

        Raises:
            ValueError: If length is not 12 hex characters
        """
        if len(value) != 12:  # 6 bytes = 12 hex chars
            raise ValueError(
                f"Serial number must be 12 hex characters, got {len(value)}"
            )

    @staticmethod
    def _parse_hex(value: str) -> bytes:
        """Parse hex string to bytes.

        Args:
            value: Hex string to parse

        Returns:
            Parsed bytes

        Raises:
            ValueError: If hex string is invalid
        """
        try:
            return bytes.fromhex(value)
        except ValueError as e:
            raise ValueError(f"Invalid serial number format: {e}") from e

    @classmethod
    def from_protocol(cls, padded_serial: bytes) -> Serial:
        """Create Serial from protocol format (8 bytes with padding).

        The LIFX protocol uses 8 bytes for the target field, with the serial number
        in the first 6 bytes and 2 bytes of padding (zeros) at the end.

        Args:
            padded_serial: 8-byte serial number from protocol

        Returns:
            Serial instance

        Raises:
            ValueError: If padded serial is not 8 bytes

        Example:
            >>> Serial.from_protocol(b"\\xd0\\x73\\xd5\\x12\\x34\\x56\\x00\\x00")
            Serial(value=b'\\xd0\\x73\\xd5\\x12\\x34\\x56')
        """
        if len(padded_serial) != 8:
            raise ValueError(
                f"Padded serial number must be 8 bytes, got {len(padded_serial)}"
            )

        # Extract first 6 bytes
        return cls(value=padded_serial[:6])

    def to_string(self) -> str:
        """Convert serial to 12-digit hex string format.

        Returns:
            Serial number string in format "xxxxxxxxxxxx" (12 hex digits, no separators)

        Example:
            >>> serial = Serial.from_string("d073d5123456")
            >>> serial.to_string()
            'd073d5123456'
        """
        return self.value.hex()

    def to_protocol(self) -> bytes:
        """Convert serial to 8-byte protocol format with padding.

        The LIFX protocol uses 8 bytes for the target field, with the serial number
        in the first 6 bytes and 2 bytes of padding (zeros) at the end.

        Returns:
            8-byte serial number with padding (suitable for protocol)

        Example:
            >>> serial = Serial.from_string("d073d5123456")
            >>> serial.to_protocol()
            b'\\xd0\\x73\\xd5\\x12\\x34\\x56\\x00\\x00'
        """
        return self.value + b"\x00\x00"

    def __str__(self) -> str:
        """Return string representation."""
        return self.to_string()

    def __repr__(self) -> str:
        """Return detailed representation."""
        return f"Serial('{self.to_string()}')"


# HEV protocol types


@dataclass
class HevCycleState:
    """HEV cleaning cycle state.

    Represents the current state of a HEV (High Energy Visible) cleaning cycle,
    which uses anti-bacterial UV-C light to sanitize the environment.

    Attributes:
        duration_s: Total duration of the cycle in seconds
        remaining_s: Remaining time in the current cycle (0 if not running)
        last_power: Whether the light was on during the last cycle

    Example:
        ```python
        # Check if HEV cycle is running
        state = await hev_light.get_hev_cycle()
        if state.remaining_s > 0:
            print(f"Cleaning in progress: {state.remaining_s}s remaining")
        ```
    """

    duration_s: int
    remaining_s: int
    last_power: bool

    @property
    def is_running(self) -> bool:
        """Check if a HEV cycle is currently running."""
        return self.remaining_s > 0


@dataclass
class HevConfig:
    """HEV cycle configuration.

    Configuration settings for HEV cleaning cycles.

    Attributes:
        indication: Whether to show visual indication during cleaning
        duration_s: Default duration for cleaning cycles in seconds

    Example:
        ```python
        # Configure HEV cycle with 2-hour duration and visual indication
        await hev_light.set_hev_config(indication=True, duration_seconds=7200)
        ```
    """

    indication: bool
    duration_s: int
