# lifx-async constants

import uuid
from typing import Final

# ============================================================================
# Network Constants
# ============================================================================

# Default IP address to bind
DEFAULT_IP_ADDRESS: Final[str] = "0.0.0.0"  # nosec B104

# LIFX UDP port for device communication
LIFX_UDP_PORT: Final[int] = 56700

# Maximum packet size for LIFX protocol (prevents DoS attacks)
MAX_PACKET_SIZE: Final[int] = 1024  # LIFX packets should be < 1KB

# Minimum size is the header (36 bytes)
MIN_PACKET_SIZE: Final[int] = 36

# LIFX vendor serial prefix (d0:73:d5) for device fingerprinting
LIFX_VENDOR_PREFIX: Final[bytes] = bytes([0xD0, 0x73, 0xD5])

# Overall discovery timeout for local network devices in seconds
DISCOVERY_TIMEOUT: Final[float] = 5.0  # Max response time * idle timeout

# Maximum response time for local network devices in seconds
MAX_RESPONSE_TIME: Final[float] = 0.5  # 500ms

# Idle timeout multiplier - wait this many times MAX_RESPONSE_TIME after last response
IDLE_TIMEOUT_MULTIPLIER: Final[float] = 4.0  # Wait 2s (4 × 500ms) after last response

# Maximum number of connections in a ConnectionPool
MAX_CONNECTIONS: Final[int] = 100

# ============================================================================
# UUID Namespaces
# ============================================================================

# Namespace UUIDs for generating consistent location/group UUIDs
# These are LIFX-specific namespaces to avoid collisions
LIFX_LOCATION_NAMESPACE: Final[uuid.UUID] = uuid.UUID(
    "b4cfb9c8-7d8a-4b5e-9c3f-1a2b3c4d5e6f"
)
LIFX_GROUP_NAMESPACE: Final[uuid.UUID] = uuid.UUID(
    "a3bea8b7-6c9a-4a4d-8b2e-0a1b2c3d4e5f"
)

# ============================================================================
# Official LIFX Repository URLs
# ============================================================================

# Official LIFX protocol specification URL
PROTOCOL_URL: Final[str] = (
    "https://raw.githubusercontent.com/LIFX/public-protocol/refs/heads/main/protocol.yml"
)

# Official LIFX products specification URL
PRODUCTS_URL: Final[str] = (
    "https://raw.githubusercontent.com/LIFX/products/refs/heads/master/products.json"
)
