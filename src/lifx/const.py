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
DISCOVERY_TIMEOUT: Final[float] = 15.0

# Maximum response time for local network devices in seconds
MAX_RESPONSE_TIME: Final[float] = 1.0  # 1 second

# Idle timeout multiplier - wait this many times MAX_RESPONSE_TIME after last response
IDLE_TIMEOUT_MULTIPLIER: Final[float] = 4.0  # 4 seconds (1.0 x 4.0)

# Default timeout for device requests in seconds
DEFAULT_REQUEST_TIMEOUT: Final[float] = 16.0
STATE_REFRESH_DEBOUNCE_MS: Final[int] = 300

# Default maximum number of retry attempts for failed requests
DEFAULT_MAX_RETRIES: Final[int] = 8

# ============================================================================
# mDNS Constants
# ============================================================================

# mDNS multicast address (IPv4)
MDNS_ADDRESS: Final[str] = "224.0.0.251"

# mDNS port
MDNS_PORT: Final[int] = 5353

# LIFX mDNS service type
LIFX_MDNS_SERVICE: Final[str] = "_lifx._udp.local"

# ============================================================================
# HSBK Min/Max Values
# ============================================================================

KELVIN_CANDLELIGHT: Final[int] = 1500
KELVIN_SUNSET: Final[int] = 2000
KELVIN_AMBER: Final[int] = 2200
KELVIN_ULTRA_WARM: Final[int] = 2500
KELVIN_INCANDESCENT: Final[int] = 2700
KELVIN_WARM: Final[int] = 3000
KELVIN_NEUTRAL_WARM: Final[int] = 3200
KELVIN_NEUTRAL: Final[int] = 3500
KELVIN_COOL: Final[int] = 4000
KELVIN_COOL_DAYLIGHT: Final[int] = 4500
KELVIN_SOFT_DAYLIGHT: Final[int] = 5000
KELVIN_DAYLIGHT: Final[int] = 5600
KELVIN_NOON_DAYLIGHT: Final[int] = 6000
KELVIN_BRIGHT_DAYLIGHT: Final[int] = 6500
KELVIN_CLOUDY_DAYLIGHT: Final[int] = 7000
KELVIN_BLUE_DAYLIGHT: Final[int] = 7500
KELVIN_BLUE_OVERCAST: Final[int] = 8000
KELVIN_BLUE_ICE: Final[int] = 9000

MIN_HUE: Final[float] = 0.0
MAX_HUE: Final[float] = 360.0
MIN_SATURATION: Final[float] = 0.0
MAX_SATURATION: Final[float] = 1.0
MIN_BRIGHTNESS: Final[float] = 0.0
MAX_BRIGHTNESS: Final[float] = 1.0
MIN_KELVIN: Final[int] = 1500
MAX_KELVIN: Final[int] = 9000

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
