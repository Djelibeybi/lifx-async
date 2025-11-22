# Protocol Layer

The protocol layer contains auto-generated structures from the official LIFX protocol specification.
These classes handle binary serialization and deserialization of LIFX messages.

!!! warning "Auto-Generated Code" Files in the protocol layer are automatically generated from
`protocol.yml`. Never edit these files directly. To update the protocol, download the latest
`protocol.yml` from the [LIFX public-protocol repository](https://github.com/LIFX/public-protocol)
and run `uv run python -m lifx.protocol.generator`.

## Base Packet

The base class for all protocol packets.

::: lifx.protocol.base.Packet
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Protocol Header

The LIFX protocol header structure (36 bytes).

::: lifx.protocol.header.LifxHeader
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Serializer

Binary serialization and deserialization utilities.

::: lifx.protocol.serializer.FieldSerializer
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## Protocol Types

Common protocol type definitions and enums.

### HSBK Type

::: lifx.protocol.protocol_types.LightHsbk
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source

### Light Waveform

::: lifx.protocol.protocol_types.LightWaveform
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source

### Device Service

::: lifx.protocol.protocol_types.DeviceService
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source

### MultiZone Application Request

::: lifx.protocol.protocol_types.MultiZoneApplicationRequest
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source

### Firmware Effect

Unified enum for all firmware effects (multizone and matrix devices):

::: lifx.protocol.protocol_types.FirmwareEffect
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source

### Direction

Direction enum for MOVE effects:

::: lifx.protocol.protocol_types.Direction
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source

## Packet Definitions

The protocol layer includes packet definitions for all LIFX message types. Major categories include:

### Device Messages

- `DeviceGetService` / `DeviceStateService` - Service discovery
- `DeviceGetLabel` / `DeviceStateLabel` - Device labels
- `DeviceGetPower` / `DeviceSetPower` / `DeviceStatePower` - Power control
- `DeviceGetVersion` / `DeviceStateVersion` - Firmware version
- `DeviceGetLocation` / `DeviceStateLocation` - Location groups
- `DeviceGetGroup` / `DeviceStateGroup` - Device groups
- `DeviceGetInfo` / `DeviceStateInfo` - Runtime info (uptime, downtime)

### Light Messages

- `LightGet` / `LightState` - Get/set light state
- `LightSetColor` - Set color with transition
- `LightSetWaveform` - Waveform effects (pulse, breathe)
- `LightGetPower` / `LightSetPower` / `LightStatePower` - Light power control
- `LightGetInfrared` / `LightSetInfrared` / `LightStateInfrared` - Infrared control

### MultiZone Messages

- `MultiZoneGetColorZones` / `MultiZoneStateZone` / `MultiZoneStateMultiZone` - Zone state
- `MultiZoneSetColorZones` - Set zone colors
- `MultiZoneGetMultiZoneEffect` / `MultiZoneSetMultiZoneEffect` - Zone effects

### Tile Messages

- `TileGetDeviceChain` / `TileStateDeviceChain` - Tile chain info
- `TileGet64` / `TileState64` - Get tile state
- `TileSet64` - Set tile colors
- `TileGetTileEffect` / `TileSetTileEffect` - Tile effects

## Protocol Models

Protocol data models for working with LIFX serial numbers and HEV cycles.

### Serial

Type-safe, immutable serial number handling:

::: lifx.protocol.models.Serial
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### HEV Cycle State

HEV (High Energy Visible) cleaning cycle state:

::: lifx.protocol.models.HevCycleState
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### HEV Configuration

HEV cycle configuration:

::: lifx.protocol.models.HevConfig
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Code Generator

The protocol generator reads `protocol.yml` and generates Python code.

::: lifx.protocol.generator
    options:
      show_root_heading: true
      heading_level: 3

## Examples

### Working with Serial Numbers

The `Serial` dataclass provides type-safe, immutable serial number handling:

```python
from lifx.protocol.models import Serial

# Create from string (accepts hex with or without separators)
serial = Serial.from_string("d073d5123456")
serial = Serial.from_string("d0:73:d5:12:34:56")  # Also works

# Convert between formats
protocol_bytes = serial.to_protocol()  # 8 bytes with padding
serial_string = serial.to_string()     # "d073d5123456"
serial_bytes = serial.value            # 6 bytes (immutable/frozen)

# Create from protocol format (8 bytes)
serial = Serial.from_protocol(b"\xd0\x73\xd5\x12\x34\x56\x00\x00")
print(serial)  # "d073d5123456"

# String representations
print(str(serial))   # "d073d5123456"
print(repr(serial))  # "Serial('d073d5123456')"
```

### Using Protocol Packets Directly

```python
from lifx.network.connection import DeviceConnection
from lifx.protocol.packets import LightSetColor, LightGet, LightState
from lifx.protocol.protocol_types import LightHsbk
from lifx.protocol.models import Serial


async def main():
    serial = Serial.from_string("d073d5123456")

    async with DeviceConnection(serial.to_string(), "192.168.1.100") as conn:
        # Create a packet
        packet = LightSetColor(
            reserved=0,
            color=LightHsbk(
                hue=240 * 182, saturation=65535, brightness=32768, kelvin=3500
            ),
            duration=1000,  # milliseconds
        )

        # Send without waiting for response
        await conn.send_packet(packet)

        # Request with response
        response = await conn.request_response(LightGet(), LightState)
        print(f"Hue: {response.color.hue / 182}°")
```

### Binary Serialization

```python
from lifx.protocol.packets import DeviceSetLabel
from lifx.protocol.serializer import Serializer

# Create packet
packet = DeviceSetLabel(label=b"Kitchen Light\0" + b"\0" * 19)

# Serialize to bytes
data = packet.pack()
print(f"Packet size: {len(data)} bytes")

# Deserialize from bytes
unpacked = DeviceSetLabel.unpack(data)
print(f"Label: {unpacked.label.decode('utf-8').rstrip('\0')}")
```

### Protocol Header

```python
from lifx.protocol.header import LifxHeader
from lifx.protocol.models import Serial

# Create header with Serial
serial = Serial.from_string("d073d5123456")
header = LifxHeader(
    size=36,
    protocol=1024,
    addressable=True,
    tagged=False,
    origin=0,
    source=0x12345678,
    target=serial.to_protocol(),  # 8 bytes with padding
    reserved1=b"\x00" * 6,
    ack_required=False,
    res_required=True,
    sequence=42,
    reserved2=0,
    pkt_type=101,  # LightGet
    reserved3=0,
)

# Serialize
data = header.pack()
print(f"Header: {data.hex()}")

# Deserialize
unpacked_header = LifxHeader.unpack(data)
print(f"Packet type: {unpacked_header.pkt_type}")
print(f"Target serial: {Serial.from_protocol(unpacked_header.target)}")
```

## Protocol Constants

### Message Types

Each packet class has a `PKT_TYPE` constant defining its protocol message type:

```python
from lifx.protocol.packets import LightSetColor, LightGet, DeviceGetLabel

print(f"LightSetColor type: {LightSetColor.PKT_TYPE}")  # 102
print(f"LightGet type: {LightGet.PKT_TYPE}")  # 101
print(f"DeviceGetLabel type: {DeviceGetLabel.PKT_TYPE}")  # 23
```

### Waveform Types

```python
from lifx.protocol.protocol_types import LightWaveform

# Available waveforms
LightWaveform.SAW
LightWaveform.SINE
LightWaveform.HALF_SINE
LightWaveform.TRIANGLE
LightWaveform.PULSE
```

### Firmware Effects

```python
from lifx.protocol.protocol_types import FirmwareEffect, Direction

# Available firmware effects (for multizone and matrix devices)
FirmwareEffect.OFF
FirmwareEffect.MOVE       # MultiZone only
FirmwareEffect.MORPH      # Tile/Matrix only
FirmwareEffect.FLAME      # Tile/Matrix only
FirmwareEffect.SKY        # Tile/Matrix only

# Direction for MOVE effects
Direction.FORWARD   # Move forward through zones
Direction.REVERSED  # Move backward through zones
```

## Product Registry

The product registry provides automatic device type detection and capability information:

::: lifx.products.ProductInfo
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

::: lifx.products.ProductCapability
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

### Using the Product Registry

```python
from lifx.products import get_product, get_device_class_name

# Get product info by product ID
product_info = get_product(product_id=27)

# Get appropriate device class name
class_name = get_device_class_name(product_id=27)  # Returns "Light", "MultiZoneLight", etc.
```

## Protocol Updates

To update to the latest LIFX protocol:

1. Download the latest `protocol.yml` from the
   [LIFX public-protocol repository](https://github.com/LIFX/public-protocol/blob/main/protocol.yml)
1. Save it to the project root
1. Run the generator: `uv run python -m lifx.protocol.generator`
1. Review the generated code changes
1. Run tests: `uv run pytest`

The generator will automatically:

- Parse the YAML specification
- Generate Python dataclasses for all packet types
- Create enums for protocol constants
- Add serialization/deserialization methods
- Filter out Button/Relay messages (out of scope)
