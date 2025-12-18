"""Type definitions for mDNS discovery.

This module defines the data structures used for mDNS service discovery.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LifxServiceRecord:
    """Information about a LIFX device discovered via mDNS.

    Attributes:
        serial: Device serial number as 12-digit hex string (e.g., "d073d5123456")
        ip: Device IP address
        port: Device UDP port (typically 56700)
        product_id: Product ID from TXT record 'p' field
        firmware: Firmware version from TXT record 'fw' field
    """

    serial: str
    ip: str
    port: int
    product_id: int
    firmware: str

    def __hash__(self) -> int:
        """Hash based on serial number for deduplication."""
        return hash(self.serial)

    def __eq__(self, other: object) -> bool:
        """Equality based on serial number."""
        if not isinstance(other, LifxServiceRecord):
            return False
        return self.serial == other.serial
