"""Type definitions for mDNS discovery.

This module defines the data structures used for mDNS service discovery.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class _LifxServiceRecord:
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
    connectivity: Literal["wifi", "thread"] = "wifi"
    addresses: frozenset[str] = field(default_factory=frozenset)
    service_instance: str | None = None

    def __hash__(self) -> int:
        """Hash based on serial number for deduplication."""
        return hash(self.serial)

    def __eq__(self, other: object) -> bool:
        """Equality based on serial number."""
        if not isinstance(other, _LifxServiceRecord):
            return False
        return self.serial == other.serial
