# Protocol Layer

The protocol layer contains auto-generated structures from the official LIFX protocol specification. These classes handle binary serialization and deserialization of LIFX messages.

!!! warning "Auto-Generated Code" Files in the protocol layer are automatically generated from `protocol.yml`. Never edit these files directly. To update the protocol, download the latest `protocol.yml` from the [LIFX public-protocol repository](https://github.com/LIFX/public-protocol) and run `uv run python -m lifx.protocol.generator`.

## Base Packet

The base class for all protocol packets.

### Packet

```python
Packet()
```

Base class for all LIFX protocol packets.

Each packet subclass defines:

- PKT_TYPE: ClassVar[int] - The packet type number
- \_fields: ClassVar\[list[dict]\] - Field metadata from protocol.yml
- Actual field attributes as dataclass fields

| METHOD   | DESCRIPTION                                    |
| -------- | ---------------------------------------------- |
| `pack`   | Pack packet to bytes using field metadata.     |
| `unpack` | Unpack packet from bytes using field metadata. |

| ATTRIBUTE | DESCRIPTION                                             |
| --------- | ------------------------------------------------------- |
| `as_dict` | Return packet as dictionary. **TYPE:** `dict[str, Any]` |

#### Attributes

##### as_dict

```python
as_dict: dict[str, Any]
```

Return packet as dictionary.

#### Functions

##### pack

```python
pack() -> bytes
```

Pack packet to bytes using field metadata.

| RETURNS | DESCRIPTION                                          |
| ------- | ---------------------------------------------------- |
| `bytes` | Packed bytes ready to send in a LIFX message payload |

Source code in `src/lifx/protocol/base.py`

```python
def pack(self) -> bytes:
    """Pack packet to bytes using field metadata.

    Returns:
        Packed bytes ready to send in a LIFX message payload
    """
    from lifx.protocol import serializer

    result = b""

    for field_item in self._fields:
        # Handle reserved fields (no name)
        if "name" not in field_item:
            size_bytes = field_item.get("size_bytes", 0)
            result += serializer.pack_reserved(size_bytes)
            continue

        # Get field value from instance
        field_name = self._protocol_to_python_name(field_item["name"])
        value = getattr(self, field_name)

        # Pack based on type
        field_type = field_item["type"]
        size_bytes = field_item.get("size_bytes", 0)
        result += self._pack_field_value(value, field_type, size_bytes)

    return result
```

##### unpack

```python
unpack(data: bytes, offset: int = 0) -> Packet
```

Unpack packet from bytes using field metadata.

| PARAMETER | DESCRIPTION                                                         |
| --------- | ------------------------------------------------------------------- |
| `data`    | Bytes to unpack from **TYPE:** `bytes`                              |
| `offset`  | Offset in bytes to start unpacking **TYPE:** `int` **DEFAULT:** `0` |

| RETURNS  | DESCRIPTION                                          |
| -------- | ---------------------------------------------------- |
| `Packet` | Packet instance with label fields decoded to strings |

Source code in `src/lifx/protocol/base.py`

```python
@classmethod
def unpack(cls, data: bytes, offset: int = 0) -> Packet:
    """Unpack packet from bytes using field metadata.

    Args:
        data: Bytes to unpack from
        offset: Offset in bytes to start unpacking

    Returns:
        Packet instance with label fields decoded to strings
    """
    packet, _ = cls._unpack_internal(data, offset)

    # Decode label fields from bytes to string in-place
    # This ensures all State packets have human-readable labels
    cls._decode_labels_inplace(packet)

    # Log packet values after unpacking and decoding labels
    packet_values = asdict(packet)
    _LOGGER.debug(
        {
            "class": "Packet",
            "method": "unpack",
            "packet_type": type(packet).__name__,
            "values": packet_values,
        }
    )

    return packet
```

## Protocol Header

The LIFX protocol header structure (36 bytes).

### LifxHeader

```python
LifxHeader(
    size: int,
    protocol: int,
    source: int,
    target: bytes,
    tagged: bool,
    ack_required: bool,
    res_required: bool,
    sequence: int,
    pkt_type: int,
)
```

LIFX protocol header (36 bytes).

| ATTRIBUTE      | DESCRIPTION                                                                                                                                                                                      |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `size`         | Total packet size in bytes (header + payload) **TYPE:** `int`                                                                                                                                    |
| `protocol`     | Protocol number (must be 1024) **TYPE:** `int`                                                                                                                                                   |
| `source`       | Unique client identifier **TYPE:** `int`                                                                                                                                                         |
| `target`       | Device serial number (6 or 8 bytes, automatically padded to 8 bytes) Note: This is the LIFX serial number, which is often but not always the same as the device's MAC address. **TYPE:** `bytes` |
| `tagged`       | True for broadcast discovery, False for targeted messages **TYPE:** `bool`                                                                                                                       |
| `ack_required` | Request acknowledgement from device **TYPE:** `bool`                                                                                                                                             |
| `res_required` | Request response from device **TYPE:** `bool`                                                                                                                                                    |
| `sequence`     | Sequence number for matching requests/responses **TYPE:** `int`                                                                                                                                  |
| `pkt_type`     | Packet type identifier **TYPE:** `int`                                                                                                                                                           |

| METHOD          | DESCRIPTION                                                  |
| --------------- | ------------------------------------------------------------ |
| `__post_init__` | Validate header fields and auto-pad serial number if needed. |
| `create`        | Create a new LIFX header.                                    |
| `pack`          | Pack header into 36 bytes.                                   |
| `unpack`        | Unpack header from bytes.                                    |
| `__repr__`      | String representation of header.                             |

#### Attributes

##### target_serial

```python
target_serial: bytes
```

Get the 6-byte serial number without padding.

| RETURNS | DESCRIPTION          |
| ------- | -------------------- |
| `bytes` | 6-byte serial number |

#### Functions

##### __post_init__

```python
__post_init__() -> None
```

Validate header fields and auto-pad serial number if needed.

Source code in `src/lifx/protocol/header.py`

```python
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
```

##### create

```python
create(
    pkt_type: int,
    source: int,
    target: bytes = b"\x00" * 6,
    tagged: bool = False,
    ack_required: bool = False,
    res_required: bool = True,
    sequence: int = 0,
    payload_size: int = 0,
) -> LifxHeader
```

Create a new LIFX header.

| PARAMETER      | DESCRIPTION                                                                                             |
| -------------- | ------------------------------------------------------------------------------------------------------- |
| `pkt_type`     | Packet type identifier **TYPE:** `int`                                                                  |
| `source`       | Unique client identifier **TYPE:** `int`                                                                |
| `target`       | Device serial number (6 or 8 bytes, defaults to broadcast) **TYPE:** `bytes` **DEFAULT:** `b'\x00' * 6` |
| `tagged`       | True for broadcast, False for targeted **TYPE:** `bool` **DEFAULT:** `False`                            |
| `ack_required` | Request acknowledgement **TYPE:** `bool` **DEFAULT:** `False`                                           |
| `res_required` | Request response **TYPE:** `bool` **DEFAULT:** `True`                                                   |
| `sequence`     | Sequence number for matching requests/responses **TYPE:** `int` **DEFAULT:** `0`                        |
| `payload_size` | Size of packet payload in bytes **TYPE:** `int` **DEFAULT:** `0`                                        |

| RETURNS      | DESCRIPTION         |
| ------------ | ------------------- |
| `LifxHeader` | LifxHeader instance |

Source code in `src/lifx/protocol/header.py`

```python
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
```

##### pack

```python
pack() -> bytes
```

Pack header into 36 bytes.

| RETURNS | DESCRIPTION         |
| ------- | ------------------- |
| `bytes` | Packed header bytes |

Source code in `src/lifx/protocol/header.py`

```python
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
```

##### unpack

```python
unpack(data: bytes) -> LifxHeader
```

Unpack header from bytes.

| PARAMETER | DESCRIPTION                                        |
| --------- | -------------------------------------------------- |
| `data`    | Header bytes (at least 36 bytes) **TYPE:** `bytes` |

| RETURNS      | DESCRIPTION         |
| ------------ | ------------------- |
| `LifxHeader` | LifxHeader instance |

| RAISES       | DESCRIPTION                     |
| ------------ | ------------------------------- |
| `ValueError` | If data is too short or invalid |

Source code in `src/lifx/protocol/header.py`

```python
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
```

##### __repr__

```python
__repr__() -> str
```

String representation of header.

Source code in `src/lifx/protocol/header.py`

```python
def __repr__(self) -> str:
    """String representation of header."""
    target_serial_str = Serial(value=self.target_serial).to_string()
    return (
        f"LifxHeader(type={self.pkt_type}, size={self.size}, "
        f"source={self.source:#x}, target={target_serial_str}, "
        f"seq={self.sequence}, tagged={self.tagged}, "
        f"ack={self.ack_required}, res={self.res_required})"
    )
```

## Serializer

Binary serialization and deserialization utilities.

### FieldSerializer

```python
FieldSerializer(field_definitions: dict[str, dict[str, str]])
```

Serializer for structured fields with nested types.

| PARAMETER           | DESCRIPTION                                                                             |
| ------------------- | --------------------------------------------------------------------------------------- |
| `field_definitions` | Dict mapping field names to structure definitions **TYPE:** `dict[str, dict[str, str]]` |

| METHOD           | DESCRIPTION                                 |
| ---------------- | ------------------------------------------- |
| `pack_field`     | Pack a structured field.                    |
| `unpack_field`   | Unpack a structured field.                  |
| `get_field_size` | Get the size in bytes of a field structure. |

Source code in `src/lifx/protocol/serializer.py`

```python
def __init__(self, field_definitions: dict[str, dict[str, str]]):
    """Initialize serializer with field definitions.

    Args:
        field_definitions: Dict mapping field names to structure definitions
    """
    self.field_definitions = field_definitions
```

#### Functions

##### pack_field

```python
pack_field(field_data: dict[str, Any], field_name: str) -> bytes
```

Pack a structured field.

| PARAMETER    | DESCRIPTION                                                |
| ------------ | ---------------------------------------------------------- |
| `field_data` | Dictionary of field values **TYPE:** `dict[str, Any]`      |
| `field_name` | Name of the field structure (e.g., "HSBK") **TYPE:** `str` |

| RETURNS | DESCRIPTION  |
| ------- | ------------ |
| `bytes` | Packed bytes |

| RAISES       | DESCRIPTION              |
| ------------ | ------------------------ |
| `ValueError` | If field_name is unknown |

Source code in `src/lifx/protocol/serializer.py`

```python
def pack_field(self, field_data: dict[str, Any], field_name: str) -> bytes:
    """Pack a structured field.

    Args:
        field_data: Dictionary of field values
        field_name: Name of the field structure (e.g., "HSBK")

    Returns:
        Packed bytes

    Raises:
        ValueError: If field_name is unknown
    """
    if field_name not in self.field_definitions:
        raise ValueError(f"Unknown field: {field_name}")

    field_def = self.field_definitions[field_name]
    result = b""

    for attr_name, attr_type in field_def.items():
        if attr_name not in field_data:
            raise ValueError(f"Missing attribute {attr_name} in {field_name}")
        result += pack_value(field_data[attr_name], attr_type)

    return result
```

##### unpack_field

```python
unpack_field(
    data: bytes, field_name: str, offset: int = 0
) -> tuple[dict[str, Any], int]
```

Unpack a structured field.

| PARAMETER    | DESCRIPTION                                                |
| ------------ | ---------------------------------------------------------- |
| `data`       | Bytes to unpack from **TYPE:** `bytes`                     |
| `field_name` | Name of the field structure **TYPE:** `str`                |
| `offset`     | Offset to start unpacking **TYPE:** `int` **DEFAULT:** `0` |

| RETURNS                      | DESCRIPTION                       |
| ---------------------------- | --------------------------------- |
| `tuple[dict[str, Any], int]` | Tuple of (field_dict, new_offset) |

| RAISES       | DESCRIPTION              |
| ------------ | ------------------------ |
| `ValueError` | If field_name is unknown |

Source code in `src/lifx/protocol/serializer.py`

```python
def unpack_field(
    self, data: bytes, field_name: str, offset: int = 0
) -> tuple[dict[str, Any], int]:
    """Unpack a structured field.

    Args:
        data: Bytes to unpack from
        field_name: Name of the field structure
        offset: Offset to start unpacking

    Returns:
        Tuple of (field_dict, new_offset)

    Raises:
        ValueError: If field_name is unknown
    """
    if field_name not in self.field_definitions:
        raise ValueError(f"Unknown field: {field_name}")

    field_def = self.field_definitions[field_name]
    field_data: dict[str, Any] = {}
    current_offset = offset

    for attr_name, attr_type in field_def.items():
        value, current_offset = unpack_value(data, attr_type, current_offset)
        field_data[attr_name] = value

    return field_data, current_offset
```

##### get_field_size

```python
get_field_size(field_name: str) -> int
```

Get the size in bytes of a field structure.

| PARAMETER    | DESCRIPTION                                 |
| ------------ | ------------------------------------------- |
| `field_name` | Name of the field structure **TYPE:** `str` |

| RETURNS | DESCRIPTION   |
| ------- | ------------- |
| `int`   | Size in bytes |

| RAISES       | DESCRIPTION              |
| ------------ | ------------------------ |
| `ValueError` | If field_name is unknown |

Source code in `src/lifx/protocol/serializer.py`

```python
def get_field_size(self, field_name: str) -> int:
    """Get the size in bytes of a field structure.

    Args:
        field_name: Name of the field structure

    Returns:
        Size in bytes

    Raises:
        ValueError: If field_name is unknown
    """
    if field_name not in self.field_definitions:
        raise ValueError(f"Unknown field: {field_name}")

    field_def = self.field_definitions[field_name]
    return sum(TYPE_SIZES[attr_type] for attr_type in field_def.values())
```

## Protocol Types

Common protocol type definitions and enums.

### HSBK Type

#### LightHsbk

```python
LightHsbk(hue: int, saturation: int, brightness: int, kelvin: int)
```

Auto-generated field structure.

| METHOD   | DESCRIPTION        |
| -------- | ------------------ |
| `pack`   | Pack to bytes.     |
| `unpack` | Unpack from bytes. |

##### Functions

###### pack

```python
pack() -> bytes
```

Pack to bytes.

Source code in `src/lifx/protocol/protocol_types.py`

```python
def pack(self) -> bytes:
    """Pack to bytes."""
    from lifx.protocol import serializer

    result = b""

    # hue: uint16
    result += serializer.pack_value(self.hue, "uint16")
    # saturation: uint16
    result += serializer.pack_value(self.saturation, "uint16")
    # brightness: uint16
    result += serializer.pack_value(self.brightness, "uint16")
    # kelvin: uint16
    result += serializer.pack_value(self.kelvin, "uint16")

    return result
```

###### unpack

```python
unpack(data: bytes, offset: int = 0) -> tuple[LightHsbk, int]
```

Unpack from bytes.

Source code in `src/lifx/protocol/protocol_types.py`

```python
@classmethod
def unpack(cls, data: bytes, offset: int = 0) -> tuple[LightHsbk, int]:
    """Unpack from bytes."""
    from lifx.protocol import serializer

    current_offset = offset
    # hue: uint16
    hue, current_offset = serializer.unpack_value(data, "uint16", current_offset)
    # saturation: uint16
    saturation, current_offset = serializer.unpack_value(
        data, "uint16", current_offset
    )
    # brightness: uint16
    brightness, current_offset = serializer.unpack_value(
        data, "uint16", current_offset
    )
    # kelvin: uint16
    kelvin, current_offset = serializer.unpack_value(data, "uint16", current_offset)

    return cls(
        hue=hue, saturation=saturation, brightness=brightness, kelvin=kelvin
    ), current_offset
```

### Light Waveform

#### LightWaveform

Bases: `IntEnum`

Auto-generated enum.

### Device Service

#### DeviceService

Bases: `IntEnum`

Auto-generated enum.

### MultiZone Application Request

#### MultiZoneApplicationRequest

Bases: `IntEnum`

Auto-generated enum.

### MultiZone Effect Type

#### MultiZoneEffectType

Bases: `IntEnum`

Auto-generated enum.

### Tile Effect Type

#### TileEffectType

Bases: `IntEnum`

Auto-generated enum.

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

#### Serial

```python
Serial(value: bytes)
```

LIFX device serial number.

Encapsulates a device serial number with conversion methods for different formats. The LIFX serial number is often the same as the device's MAC address, but can differ (particularly the least significant byte may be off by one).

| ATTRIBUTE | DESCRIPTION                                |
| --------- | ------------------------------------------ |
| `value`   | Serial number as 6 bytes **TYPE:** `bytes` |

Example

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

| METHOD          | DESCRIPTION                                                |
| --------------- | ---------------------------------------------------------- |
| `__post_init__` | Validate serial number after initialization.               |
| `from_string`   | Create Serial from string format.                          |
| `from_protocol` | Create Serial from protocol format (8 bytes with padding). |
| `to_string`     | Convert serial to 12-digit hex string format.              |
| `to_protocol`   | Convert serial to 8-byte protocol format with padding.     |
| `__str__`       | Return string representation.                              |
| `__repr__`      | Return detailed representation.                            |

##### Functions

###### __post_init__

```python
__post_init__() -> None
```

Validate serial number after initialization.

Source code in `src/lifx/protocol/models.py`

```python
def __post_init__(self) -> None:
    """Validate serial number after initialization."""
    self._validate_type(self.value)
    self._validate_length(self.value)
```

###### from_string

```python
from_string(serial: str) -> Serial
```

Create Serial from string format.

Accepts 12-digit hex string (with or without separators).

| PARAMETER | DESCRIPTION                                                                       |
| --------- | --------------------------------------------------------------------------------- |
| `serial`  | 12-digit hex string (e.g., "d073d5123456" or "d0:73:d5:12:34:56") **TYPE:** `str` |

| RETURNS  | DESCRIPTION     |
| -------- | --------------- |
| `Serial` | Serial instance |

| RAISES       | DESCRIPTION                 |
| ------------ | --------------------------- |
| `ValueError` | If serial number is invalid |
| `TypeError`  | If serial is not a string   |

Example

> > > Serial.from_string("d073d5123456") Serial(value=b'\\xd0\\x73\\xd5\\x12\\x34\\x56') Serial.from_string("d0:73:d5:12:34:56") # Also accepts separators Serial(value=b'\\xd0\\x73\\xd5\\x12\\x34\\x56')

Source code in `src/lifx/protocol/models.py`

```python
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
```

###### from_protocol

```python
from_protocol(padded_serial: bytes) -> Serial
```

Create Serial from protocol format (8 bytes with padding).

The LIFX protocol uses 8 bytes for the target field, with the serial number in the first 6 bytes and 2 bytes of padding (zeros) at the end.

| PARAMETER       | DESCRIPTION                                          |
| --------------- | ---------------------------------------------------- |
| `padded_serial` | 8-byte serial number from protocol **TYPE:** `bytes` |

| RETURNS  | DESCRIPTION     |
| -------- | --------------- |
| `Serial` | Serial instance |

| RAISES       | DESCRIPTION                     |
| ------------ | ------------------------------- |
| `ValueError` | If padded serial is not 8 bytes |

Example

> > > Serial.from_protocol(b"\\xd0\\x73\\xd5\\x12\\x34\\x56\\x00\\x00") Serial(value=b'\\xd0\\x73\\xd5\\x12\\x34\\x56')

Source code in `src/lifx/protocol/models.py`

```python
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
```

###### to_string

```python
to_string() -> str
```

Convert serial to 12-digit hex string format.

| RETURNS | DESCRIPTION                                                                  |
| ------- | ---------------------------------------------------------------------------- |
| `str`   | Serial number string in format "xxxxxxxxxxxx" (12 hex digits, no separators) |

Example

> > > serial = Serial.from_string("d073d5123456") serial.to_string() 'd073d5123456'

Source code in `src/lifx/protocol/models.py`

```python
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
```

###### to_protocol

```python
to_protocol() -> bytes
```

Convert serial to 8-byte protocol format with padding.

The LIFX protocol uses 8 bytes for the target field, with the serial number in the first 6 bytes and 2 bytes of padding (zeros) at the end.

| RETURNS | DESCRIPTION                                               |
| ------- | --------------------------------------------------------- |
| `bytes` | 8-byte serial number with padding (suitable for protocol) |

Example

> > > serial = Serial.from_string("d073d5123456") serial.to_protocol() b'\\xd0\\x73\\xd5\\x12\\x34\\x56\\x00\\x00'

Source code in `src/lifx/protocol/models.py`

```python
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
```

###### __str__

```python
__str__() -> str
```

Return string representation.

Source code in `src/lifx/protocol/models.py`

```python
def __str__(self) -> str:
    """Return string representation."""
    return self.to_string()
```

###### __repr__

```python
__repr__() -> str
```

Return detailed representation.

Source code in `src/lifx/protocol/models.py`

```python
def __repr__(self) -> str:
    """Return detailed representation."""
    return f"Serial('{self.to_string()}')"
```

### HEV Cycle State

HEV (High Energy Visible) cleaning cycle state:

#### HevCycleState

```python
HevCycleState(duration_s: int, remaining_s: int, last_power: bool)
```

HEV cleaning cycle state.

Represents the current state of a HEV (High Energy Visible) cleaning cycle, which uses anti-bacterial UV-C light to sanitize the environment.

| ATTRIBUTE     | DESCRIPTION                                                            |
| ------------- | ---------------------------------------------------------------------- |
| `duration_s`  | Total duration of the cycle in seconds **TYPE:** `int`                 |
| `remaining_s` | Remaining time in the current cycle (0 if not running) **TYPE:** `int` |
| `last_power`  | Whether the light was on during the last cycle **TYPE:** `bool`        |

Example

```python
# Check if HEV cycle is running
state = await hev_light.get_hev_cycle()
if state.remaining_s > 0:
    print(f"Cleaning in progress: {state.remaining_s}s remaining")
```

##### Attributes

###### is_running

```python
is_running: bool
```

Check if a HEV cycle is currently running.

### HEV Configuration

HEV cycle configuration:

#### HevConfig

```python
HevConfig(indication: bool, duration_s: int)
```

HEV cycle configuration.

Configuration settings for HEV cleaning cycles.

| ATTRIBUTE    | DESCRIPTION                                                        |
| ------------ | ------------------------------------------------------------------ |
| `indication` | Whether to show visual indication during cleaning **TYPE:** `bool` |
| `duration_s` | Default duration for cleaning cycles in seconds **TYPE:** `int`    |

Example

```python
# Configure HEV cycle with 2-hour duration and visual indication
await hev_light.set_hev_config(indication=True, duration_seconds=7200)
```

## Code Generator

The protocol generator reads `protocol.yml` and generates Python code.

### generator

Code generator for LIFX protocol structures.

Downloads the official protocol.yml from the LIFX GitHub repository and generates Python types and packet classes. The YAML is never stored locally, only parsed and converted into protocol classes.

| CLASS          | DESCRIPTION                                    |
| -------------- | ---------------------------------------------- |
| `TypeRegistry` | Registry of all protocol types for validation. |

| FUNCTION                                 | DESCRIPTION                                                                       |
| ---------------------------------------- | --------------------------------------------------------------------------------- |
| `to_snake_case`                          | Convert PascalCase or camelCase to snake_case.                                    |
| `apply_field_name_quirks`                | Apply quirks to field names to avoid Python built-ins and reserved words.         |
| `apply_extended_multizone_packet_quirks` | Apply quirks to extended multizone packet names to follow LIFX naming convention. |
| `apply_tile_effect_parameter_quirk`      | Apply local quirk to fix TileEffectParameter structure.                           |
| `format_long_import`                     | Format a long import statement across multiple lines.                             |
| `format_long_list`                       | Format a long list across multiple lines.                                         |
| `parse_field_type`                       | Parse a field type string.                                                        |
| `camel_to_snake_upper`                   | Convert CamelCase to UPPER_SNAKE_CASE.                                            |
| `generate_enum_code`                     | Generate Python Enum definitions with shortened names.                            |
| `convert_type_to_python`                 | Convert a protocol field type to Python type annotation.                          |
| `generate_pack_method`                   | Generate pack() method code for a field structure or packet.                      |
| `generate_unpack_method`                 | Generate unpack() classmethod code for a field structure or packet.               |
| `generate_field_code`                    | Generate Python dataclass definitions for field structures.                       |
| `generate_nested_packet_code`            | Generate nested Python packet class definitions.                                  |
| `generate_types_file`                    | Generate complete types.py file.                                                  |
| `generate_packets_file`                  | Generate complete packets.py file.                                                |
| `download_protocol`                      | Download and parse protocol.yml from LIFX GitHub repository.                      |
| `validate_protocol_spec`                 | Validate protocol specification for missing type references.                      |
| `should_skip_button_relay`               | Check if a name should be skipped (Button or Relay related).                      |
| `filter_button_relay_items`              | Filter out Button and Relay items from a dictionary.                              |
| `filter_button_relay_packets`            | Filter out button and relay category packets.                                     |
| `extract_packets_as_fields`              | Extract packets that are used as field types in other structures.                 |
| `main`                                   | Main generator entry point.                                                       |

#### Classes

##### TypeRegistry

```python
TypeRegistry()
```

Registry of all protocol types for validation.

Tracks all defined types (enums, fields, packets, unions) to validate that all type references in the protocol specification are valid.

| METHOD            | DESCRIPTION                      |
| ----------------- | -------------------------------- |
| `register_enum`   | Register an enum type.           |
| `register_field`  | Register a field structure type. |
| `register_packet` | Register a packet type.          |
| `register_union`  | Register a union type.           |
| `is_enum`         | Check if a type is an enum.      |
| `has_type`        | Check if a type is defined.      |
| `get_all_types`   | Get all registered types.        |

Source code in `src/lifx/protocol/generator.py`

```python
def __init__(self) -> None:
    """Initialize empty type registry."""
    self._enums: set[str] = set()
    self._fields: set[str] = set()
    self._packets: set[str] = set()
    self._unions: set[str] = set()
    self._basic_types: set[str] = {
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "int8",
        "int16",
        "int32",
        "int64",
        "float32",
        "bool",
        "byte",
        "reserved",  # Special type for reserved fields
    }
```

###### Functions

###### register_enum

```python
register_enum(name: str) -> None
```

Register an enum type.

| PARAMETER | DESCRIPTION                    |
| --------- | ------------------------------ |
| `name`    | Enum type name **TYPE:** `str` |

Source code in `src/lifx/protocol/generator.py`

```python
def register_enum(self, name: str) -> None:
    """Register an enum type.

    Args:
        name: Enum type name
    """
    self._enums.add(name)
```

###### register_field

```python
register_field(name: str) -> None
```

Register a field structure type.

| PARAMETER | DESCRIPTION                               |
| --------- | ----------------------------------------- |
| `name`    | Field structure type name **TYPE:** `str` |

Source code in `src/lifx/protocol/generator.py`

```python
def register_field(self, name: str) -> None:
    """Register a field structure type.

    Args:
        name: Field structure type name
    """
    self._fields.add(name)
```

###### register_packet

```python
register_packet(name: str) -> None
```

Register a packet type.

| PARAMETER | DESCRIPTION                      |
| --------- | -------------------------------- |
| `name`    | Packet type name **TYPE:** `str` |

Source code in `src/lifx/protocol/generator.py`

```python
def register_packet(self, name: str) -> None:
    """Register a packet type.

    Args:
        name: Packet type name
    """
    self._packets.add(name)
```

###### register_union

```python
register_union(name: str) -> None
```

Register a union type.

| PARAMETER | DESCRIPTION                     |
| --------- | ------------------------------- |
| `name`    | Union type name **TYPE:** `str` |

Source code in `src/lifx/protocol/generator.py`

```python
def register_union(self, name: str) -> None:
    """Register a union type.

    Args:
        name: Union type name
    """
    self._unions.add(name)
```

###### is_enum

```python
is_enum(name: str) -> bool
```

Check if a type is an enum.

| PARAMETER | DESCRIPTION                        |
| --------- | ---------------------------------- |
| `name`    | Type name to check **TYPE:** `str` |

| RETURNS | DESCRIPTION                 |
| ------- | --------------------------- |
| `bool`  | True if the type is an enum |

Source code in `src/lifx/protocol/generator.py`

```python
def is_enum(self, name: str) -> bool:
    """Check if a type is an enum.

    Args:
        name: Type name to check

    Returns:
        True if the type is an enum
    """
    return name in self._enums
```

###### has_type

```python
has_type(name: str) -> bool
```

Check if a type is defined.

| PARAMETER | DESCRIPTION                        |
| --------- | ---------------------------------- |
| `name`    | Type name to check **TYPE:** `str` |

| RETURNS | DESCRIPTION                 |
| ------- | --------------------------- |
| `bool`  | True if the type is defined |

Source code in `src/lifx/protocol/generator.py`

```python
def has_type(self, name: str) -> bool:
    """Check if a type is defined.

    Args:
        name: Type name to check

    Returns:
        True if the type is defined
    """
    return (
        name in self._enums
        or name in self._fields
        or name in self._packets
        or name in self._unions
        or name in self._basic_types
    )
```

###### get_all_types

```python
get_all_types() -> set[str]
```

Get all registered types.

| RETURNS    | DESCRIPTION           |
| ---------- | --------------------- |
| `set[str]` | Set of all type names |

Source code in `src/lifx/protocol/generator.py`

```python
def get_all_types(self) -> set[str]:
    """Get all registered types.

    Returns:
        Set of all type names
    """
    return (
        self._enums
        | self._fields
        | self._packets
        | self._unions
        | self._basic_types
    )
```

#### Functions

##### to_snake_case

```python
to_snake_case(name: str) -> str
```

Convert PascalCase or camelCase to snake_case.

| PARAMETER | DESCRIPTION                                    |
| --------- | ---------------------------------------------- |
| `name`    | PascalCase or camelCase string **TYPE:** `str` |

| RETURNS | DESCRIPTION       |
| ------- | ----------------- |
| `str`   | snake_case string |

Source code in `src/lifx/protocol/generator.py`

```python
def to_snake_case(name: str) -> str:
    """Convert PascalCase or camelCase to snake_case.

    Args:
        name: PascalCase or camelCase string

    Returns:
        snake_case string
    """
    # Insert underscore before uppercase letters (except at start)
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return snake.lower()
```

##### apply_field_name_quirks

```python
apply_field_name_quirks(python_name: str) -> str
```

Apply quirks to field names to avoid Python built-ins and reserved words.

| PARAMETER     | DESCRIPTION                                                        |
| ------------- | ------------------------------------------------------------------ |
| `python_name` | The Python field name (usually from to_snake_case) **TYPE:** `str` |

| RETURNS | DESCRIPTION               |
| ------- | ------------------------- |
| `str`   | Quirk-adjusted field name |

Quirks applied

- "type" -> "effect_type" (avoids Python built-in)

Source code in `src/lifx/protocol/generator.py`

```python
def apply_field_name_quirks(python_name: str) -> str:
    """Apply quirks to field names to avoid Python built-ins and reserved words.

    Args:
        python_name: The Python field name (usually from to_snake_case)

    Returns:
        Quirk-adjusted field name

    Quirks applied:
        - "type" -> "effect_type" (avoids Python built-in)
    """
    if python_name == "type":
        return "effect_type"
    return python_name
```

##### apply_extended_multizone_packet_quirks

```python
apply_extended_multizone_packet_quirks(
    packet_name: str, category_class: str
) -> str
```

Apply quirks to extended multizone packet names to follow LIFX naming convention.

In the LIFX protocol, extended multizone packets should follow the standard naming pattern of {Action}{Object} (e.g., GetExtendedColorZones, SetExtendedColorZones).

| PARAMETER        | DESCRIPTION                                                 |
| ---------------- | ----------------------------------------------------------- |
| `packet_name`    | Packet name (after category prefix removal) **TYPE:** `str` |
| `category_class` | Category class name (e.g., "MultiZone") **TYPE:** `str`     |

| RETURNS | DESCRIPTION                |
| ------- | -------------------------- |
| `str`   | Quirk-adjusted packet name |

Quirks applied

- "ExtendedGetColorZones" -> "GetExtendedColorZones"
- "ExtendedSetColorZones" -> "SetExtendedColorZones"
- "ExtendedStateMultiZone" -> "StateExtendedColorZones"

Source code in `src/lifx/protocol/generator.py`

```python
def apply_extended_multizone_packet_quirks(
    packet_name: str, category_class: str
) -> str:
    """Apply quirks to extended multizone packet names to follow LIFX naming convention.

    In the LIFX protocol, extended multizone packets should follow the standard naming
    pattern of {Action}{Object} (e.g., GetExtendedColorZones, SetExtendedColorZones).

    Args:
        packet_name: Packet name (after category prefix removal)
        category_class: Category class name (e.g., "MultiZone")

    Returns:
        Quirk-adjusted packet name

    Quirks applied:
        - "ExtendedGetColorZones" -> "GetExtendedColorZones"
        - "ExtendedSetColorZones" -> "SetExtendedColorZones"
        - "ExtendedStateMultiZone" -> "StateExtendedColorZones"
    """
    if category_class == "MultiZone":
        if packet_name == "ExtendedGetColorZones":
            return "GetExtendedColorZones"
        elif packet_name == "ExtendedSetColorZones":
            return "SetExtendedColorZones"
        elif packet_name == "ExtendedStateMultiZone":
            return "StateExtendedColorZones"
    return packet_name
```

##### apply_tile_effect_parameter_quirk

```python
apply_tile_effect_parameter_quirk(fields: dict[str, Any]) -> dict[str, Any]
```

Apply local quirk to fix TileEffectParameter structure.

The upstream protocol.yml doesn't provide enough detail for TileEffectParameter. This quirk replaces it with the correct structure:

- TileEffectSkyType (enum, uint8)
- 3 reserved bytes
- cloudSaturationMin (uint8)
- 3 reserved bytes
- cloudSaturationMax (uint8)
- 23 reserved bytes Total: 32 bytes

| PARAMETER | DESCRIPTION                                                |
| --------- | ---------------------------------------------------------- |
| `fields`  | Dictionary of field definitions **TYPE:** `dict[str, Any]` |

| RETURNS          | DESCRIPTION                                       |
| ---------------- | ------------------------------------------------- |
| `dict[str, Any]` | Dictionary with TileEffectParameter quirk applied |

Source code in `src/lifx/protocol/generator.py`

```python
def apply_tile_effect_parameter_quirk(
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Apply local quirk to fix TileEffectParameter structure.

    The upstream protocol.yml doesn't provide enough detail for TileEffectParameter.
    This quirk replaces it with the correct structure:
    - TileEffectSkyType (enum, uint8)
    - 3 reserved bytes
    - cloudSaturationMin (uint8)
    - 3 reserved bytes
    - cloudSaturationMax (uint8)
    - 23 reserved bytes
    Total: 32 bytes

    Args:
        fields: Dictionary of field definitions

    Returns:
        Dictionary with TileEffectParameter quirk applied
    """
    if "TileEffectParameter" in fields:
        fields["TileEffectParameter"] = {
            "size_bytes": 32,
            "fields": [
                {"name": "SkyType", "type": "<TileEffectSkyType>"},
                {"size_bytes": 3},
                {"name": "CloudSaturationMin", "type": "uint8"},
                {"size_bytes": 3},
                {"name": "CloudSaturationMax", "type": "uint8"},
                {"size_bytes": 23},
            ],
        }
    return fields
```

##### format_long_import

```python
format_long_import(
    items: list[str], prefix: str = "from lifx.protocol.protocol_types import "
) -> str
```

Format a long import statement across multiple lines.

| PARAMETER | DESCRIPTION                                                                              |
| --------- | ---------------------------------------------------------------------------------------- |
| `items`   | List of import items (e.g., ["Foo", "Bar as BazAlias"]) **TYPE:** `list[str]`            |
| `prefix`  | Import prefix **TYPE:** `str` **DEFAULT:** `'from lifx.protocol.protocol_types import '` |

| RETURNS | DESCRIPTION                                        |
| ------- | -------------------------------------------------- |
| `str`   | Formatted import string with line breaks if needed |

Source code in `src/lifx/protocol/generator.py`

```python
def format_long_import(
    items: list[str], prefix: str = "from lifx.protocol.protocol_types import "
) -> str:
    """Format a long import statement across multiple lines.

    Args:
        items: List of import items (e.g., ["Foo", "Bar as BazAlias"])
        prefix: Import prefix

    Returns:
        Formatted import string with line breaks if needed
    """
    if not items:
        return ""

    # Try single line first
    single_line = prefix + ", ".join(items)
    if len(single_line) <= 120:
        return single_line + "\n"

    # Multi-line format
    lines = [prefix + "("]
    for i, item in enumerate(items):
        if i < len(items) - 1:
            lines.append(f"    {item},")
        else:
            lines.append(f"    {item},")
    lines.append(")")
    return "\n".join(lines) + "\n"
```

##### format_long_list

```python
format_long_list(
    items: list[dict[str, Any]], max_line_length: int = 120
) -> str
```

Format a long list across multiple lines.

| PARAMETER         | DESCRIPTION                                                            |
| ----------------- | ---------------------------------------------------------------------- |
| `items`           | List of dict items to format **TYPE:** `list[dict[str, Any]]`          |
| `max_line_length` | Maximum line length before wrapping **TYPE:** `int` **DEFAULT:** `120` |

| RETURNS | DESCRIPTION           |
| ------- | --------------------- |
| `str`   | Formatted list string |

Source code in `src/lifx/protocol/generator.py`

```python
def format_long_list(items: list[dict[str, Any]], max_line_length: int = 120) -> str:
    """Format a long list across multiple lines.

    Args:
        items: List of dict items to format
        max_line_length: Maximum line length before wrapping

    Returns:
        Formatted list string
    """
    if not items:
        return "[]"

    # Try single line first
    single_line = repr(items)
    if len(single_line) <= max_line_length:
        return single_line

    # Multi-line format with one item per line
    lines = ["["]
    for i, item in enumerate(items):
        item_str = repr(item)
        if i < len(items) - 1:
            lines.append(f"    {item_str},")
        else:
            lines.append(f"    {item_str},")
    lines.append("]")
    return "\n".join(lines)
```

##### parse_field_type

```python
parse_field_type(field_type: str) -> tuple[str, int | None, bool]
```

Parse a field type string.

| PARAMETER    | DESCRIPTION                                                  |
| ------------ | ------------------------------------------------------------ |
| `field_type` | Field type (e.g., 'uint16', '[32]uint8', '') **TYPE:** `str` |

| RETURNS           | DESCRIPTION                                              |
| ----------------- | -------------------------------------------------------- |
| `str`             | Tuple of (base_type, array_count, is_nested)             |
| \`int             | None\`                                                   |
| `bool`            | array_count: Number of elements if array, None otherwise |
| \`tuple\[str, int | None, bool\]\`                                           |

Source code in `src/lifx/protocol/generator.py`

```python
def parse_field_type(field_type: str) -> tuple[str, int | None, bool]:
    """Parse a field type string.

    Args:
        field_type: Field type (e.g., 'uint16', '[32]uint8', '<HSBK>')

    Returns:
        Tuple of (base_type, array_count, is_nested)
        - base_type: The base type name
        - array_count: Number of elements if array, None otherwise
        - is_nested: True if it's a nested structure (<Type>)
    """
    # Check for array: [N]type
    array_match = re.match(r"\[(\d+)\](.+)", field_type)
    if array_match:
        count = int(array_match.group(1))
        inner_type = array_match.group(2)
        # Check if inner type is nested
        if inner_type.startswith("<") and inner_type.endswith(">"):
            return inner_type[1:-1], count, True
        return inner_type, count, False

    # Check for nested structure: <Type>
    if field_type.startswith("<") and field_type.endswith(">"):
        return field_type[1:-1], None, True

    # Simple type
    return field_type, None, False
```

##### camel_to_snake_upper

```python
camel_to_snake_upper(name: str) -> str
```

Convert CamelCase to UPPER_SNAKE_CASE.

| PARAMETER | DESCRIPTION                      |
| --------- | -------------------------------- |
| `name`    | CamelCase string **TYPE:** `str` |

| RETURNS | DESCRIPTION             |
| ------- | ----------------------- |
| `str`   | UPPER_SNAKE_CASE string |

Source code in `src/lifx/protocol/generator.py`

```python
def camel_to_snake_upper(name: str) -> str:
    """Convert CamelCase to UPPER_SNAKE_CASE.

    Args:
        name: CamelCase string

    Returns:
        UPPER_SNAKE_CASE string
    """
    # Insert underscore before uppercase letters (except at start)
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return snake.upper()
```

##### generate_enum_code

```python
generate_enum_code(enums: dict[str, Any]) -> str
```

Generate Python Enum definitions with shortened names.

| PARAMETER | DESCRIPTION                                               |
| --------- | --------------------------------------------------------- |
| `enums`   | Dictionary of enum definitions **TYPE:** `dict[str, Any]` |

| RETURNS | DESCRIPTION        |
| ------- | ------------------ |
| `str`   | Python code string |

Source code in `src/lifx/protocol/generator.py`

```python
def generate_enum_code(enums: dict[str, Any]) -> str:
    """Generate Python Enum definitions with shortened names.

    Args:
        enums: Dictionary of enum definitions

    Returns:
        Python code string
    """
    code: list[str] = []

    for enum_name, enum_def in sorted(enums.items()):
        code.append(f"class {enum_name}(IntEnum):")
        code.append('    """Auto-generated enum."""')
        code.append("")

        # Handle both old format (dict) and new format (list of dicts)
        if isinstance(enum_def, dict) and "values" in enum_def:
            # New format: {type: "uint16", values: [{name: "X", value: 1}, ...]}
            values = enum_def["values"]
            reserved_counter = 0

            # Check if all values share a common prefix (enum name)
            expected_prefix = camel_to_snake_upper(enum_name) + "_"
            non_reserved = [
                item["name"] for item in values if item["name"].lower() != "reserved"
            ]
            has_common_prefix = non_reserved and all(
                name.startswith(expected_prefix) for name in non_reserved
            )

            for item in sorted(values, key=lambda x: x["value"]):
                protocol_name = item["name"]
                member_value = item["value"]

                # Handle reserved fields by making names unique
                if protocol_name.lower() == "reserved":
                    member_name = f"RESERVED_{reserved_counter}"
                    reserved_counter += 1
                # Remove redundant prefix for cleaner Python names
                elif has_common_prefix and protocol_name.startswith(expected_prefix):
                    member_name = protocol_name[len(expected_prefix) :]
                else:
                    member_name = protocol_name

                code.append(f"    {member_name} = {member_value}")
        else:
            # Old format: {MEMBER: value, ...}
            for member_name, member_value in sorted(
                enum_def.items(), key=lambda x: x[1]
            ):
                code.append(f"    {member_name} = {member_value}")

        code.append("")
        code.append("")

    return "\n".join(code)
```

##### convert_type_to_python

```python
convert_type_to_python(
    field_type: str, type_aliases: dict[str, str] | None = None
) -> str
```

Convert a protocol field type to Python type annotation.

| PARAMETER      | DESCRIPTION                                                    |
| -------------- | -------------------------------------------------------------- |
| `field_type`   | Protocol field type string **TYPE:** `str`                     |
| `type_aliases` | Optional dict for type name aliases **TYPE:** \`dict[str, str] |

| RETURNS | DESCRIPTION                   |
| ------- | ----------------------------- |
| `str`   | Python type annotation string |

Source code in `src/lifx/protocol/generator.py`

```python
def convert_type_to_python(
    field_type: str, type_aliases: dict[str, str] | None = None
) -> str:
    """Convert a protocol field type to Python type annotation.

    Args:
        field_type: Protocol field type string
        type_aliases: Optional dict for type name aliases

    Returns:
        Python type annotation string
    """
    if type_aliases is None:
        type_aliases = {}

    base_type, array_count, is_nested = parse_field_type(field_type)

    if array_count:
        if is_nested:
            # Use alias if one exists
            type_name = type_aliases.get(base_type, base_type)
            return f"list[{type_name}]"
        elif base_type in ("uint8", "byte"):
            # Special case: byte arrays
            return "bytes"
        else:
            return "list[int]"
    elif is_nested:
        # Use alias if one exists
        return type_aliases.get(base_type, base_type)
    elif base_type in ("uint8", "uint16", "uint32", "uint64"):
        return "int"
    elif base_type in ("int8", "int16", "int32", "int64"):
        return "int"
    elif base_type == "float32":
        return "float"
    elif base_type == "bool":
        return "bool"
    else:
        return "Any"
```

##### generate_pack_method

```python
generate_pack_method(
    fields_data: list[dict[str, Any]],
    class_type: str = "field",
    enum_types: set[str] | None = None,
) -> str
```

Generate pack() method code for a field structure or packet.

| PARAMETER     | DESCRIPTION                                                       |
| ------------- | ----------------------------------------------------------------- |
| `fields_data` | List of field definitions **TYPE:** `list[dict[str, Any]]`        |
| `class_type`  | Either "field" or "packet" **TYPE:** `str` **DEFAULT:** `'field'` |
| `enum_types`  | Set of enum type names for detection **TYPE:** \`set[str]         |

| RETURNS | DESCRIPTION               |
| ------- | ------------------------- |
| `str`   | Python method code string |

Source code in `src/lifx/protocol/generator.py`

```python
def generate_pack_method(
    fields_data: list[dict[str, Any]],
    class_type: str = "field",
    enum_types: set[str] | None = None,
) -> str:
    """Generate pack() method code for a field structure or packet.

    Args:
        fields_data: List of field definitions
        class_type: Either "field" or "packet"
        enum_types: Set of enum type names for detection

    Returns:
        Python method code string
    """
    if enum_types is None:
        enum_types = set()

    code = []
    code.append("    def pack(self) -> bytes:")
    code.append('        """Pack to bytes."""')
    code.append("        from lifx.protocol import serializer")
    code.append('        result = b""')
    code.append("")

    for field_item in fields_data:
        # Handle reserved fields (no name)
        if "name" not in field_item:
            size_bytes = field_item.get("size_bytes", 0)
            code.append(f"        # Reserved {size_bytes} bytes")
            code.append(f"        result += serializer.pack_reserved({size_bytes})")
            continue

        protocol_name = field_item["name"]
        field_type = field_item["type"]
        size_bytes = field_item.get("size_bytes", 0)
        python_name = apply_field_name_quirks(to_snake_case(protocol_name))

        base_type, array_count, is_nested = parse_field_type(field_type)

        # Check if this is an enum (nested but in enum_types)
        is_enum = is_nested and base_type in enum_types

        # Handle different field types
        if array_count:
            if is_enum:
                # Array of enums - pack as array of ints
                code.append(f"        # {python_name}: list[{base_type}] (enum array)")
                code.append(f"        for item in self.{python_name}:")
                code.append(
                    "            result += serializer.pack_value(int(item), 'uint8')"
                )
            elif is_nested:
                # Array of nested structures
                code.append(f"        # {python_name}: list[{base_type}]")
                code.append(f"        for item in self.{python_name}:")
                code.append("            result += item.pack()")
            elif base_type in ("uint8", "byte"):
                # Byte array
                code.append(f"        # {python_name}: bytes ({size_bytes} bytes)")
                code.append(
                    f"        result += "
                    f"serializer.pack_bytes(self.{python_name}, {size_bytes})"
                )
            else:
                # Array of primitives
                code.append(f"        # {python_name}: list[{base_type}]")
                code.append(
                    f"        result += "
                    f"serializer.pack_array(self.{python_name}, '{base_type}', {array_count})"
                )
        elif is_enum:
            # Enum - pack as int
            code.append(f"        # {python_name}: {base_type} (enum)")
            code.append(
                f"        result += "
                f"serializer.pack_value(int(self.{python_name}), 'uint8')"
            )
        elif is_nested:
            # Nested structure
            code.append(f"        # {python_name}: {base_type}")
            code.append(f"        result += self.{python_name}.pack()")
        else:
            # Primitive type
            code.append(f"        # {python_name}: {base_type}")
            code.append(
                f"        result += "
                f"serializer.pack_value(self.{python_name}, '{base_type}')"
            )

    code.append("")
    code.append("        return result")

    return "\n".join(code)
```

##### generate_unpack_method

```python
generate_unpack_method(
    class_name: str,
    fields_data: list[dict[str, Any]],
    class_type: str = "field",
    enum_types: set[str] | None = None,
) -> str
```

Generate unpack() classmethod code for a field structure or packet.

| PARAMETER     | DESCRIPTION                                                       |
| ------------- | ----------------------------------------------------------------- |
| `class_name`  | Name of the class **TYPE:** `str`                                 |
| `fields_data` | List of field definitions **TYPE:** `list[dict[str, Any]]`        |
| `class_type`  | Either "field" or "packet" **TYPE:** `str` **DEFAULT:** `'field'` |
| `enum_types`  | Set of enum type names for detection **TYPE:** \`set[str]         |

| RETURNS | DESCRIPTION               |
| ------- | ------------------------- |
| `str`   | Python method code string |

Source code in `src/lifx/protocol/generator.py`

```python
def generate_unpack_method(
    class_name: str,
    fields_data: list[dict[str, Any]],
    class_type: str = "field",
    enum_types: set[str] | None = None,
) -> str:
    """Generate unpack() classmethod code for a field structure or packet.

    Args:
        class_name: Name of the class
        fields_data: List of field definitions
        class_type: Either "field" or "packet"
        enum_types: Set of enum type names for detection

    Returns:
        Python method code string
    """
    if enum_types is None:
        enum_types = set()

    code = []
    code.append("    @classmethod")
    code.append(
        f"    def unpack(cls, data: bytes, offset: int = 0) -> tuple[{class_name}, int]:"
    )
    code.append('        """Unpack from bytes."""')
    code.append("        from lifx.protocol import serializer")
    code.append("        current_offset = offset")

    # Store field values
    field_vars = []

    for field_item in fields_data:
        # Handle reserved fields (no name)
        if "name" not in field_item:
            size_bytes = field_item.get("size_bytes", 0)
            code.append(f"        # Skip reserved {size_bytes} bytes")
            code.append(f"        current_offset += {size_bytes}")
            continue

        protocol_name = field_item["name"]
        field_type = field_item["type"]
        size_bytes = field_item.get("size_bytes", 0)
        python_name = apply_field_name_quirks(to_snake_case(protocol_name))
        field_vars.append(python_name)

        base_type, array_count, is_nested = parse_field_type(field_type)

        # Check if this is an enum (nested but in enum_types)
        is_enum = is_nested and base_type in enum_types

        # Handle different field types
        if array_count:
            if is_enum:
                # Array of enums
                code.append(f"        # {python_name}: list[{base_type}] (enum array)")
                code.append(f"        {python_name} = []")
                code.append(f"        for _ in range({array_count}):")
                code.append(
                    "            item_raw, current_offset = serializer.unpack_value(data, 'uint8', current_offset)"
                )
                code.append(f"            {python_name}.append({base_type}(item_raw))")
            elif is_nested:
                # Array of nested structures
                code.append(f"        # {python_name}: list[{base_type}]")
                code.append(f"        {python_name} = []")
                code.append(f"        for _ in range({array_count}):")
                code.append(
                    f"            item, current_offset = {base_type}.unpack(data, current_offset)"
                )
                code.append(f"            {python_name}.append(item)")
            elif base_type in ("uint8", "byte"):
                # Byte array
                code.append(f"        # {python_name}: bytes ({size_bytes} bytes)")
                code.append(
                    f"        {python_name}, current_offset = serializer.unpack_bytes("
                )
                code.append(f"            data, {size_bytes}, current_offset")
                code.append("        )")
            else:
                # Array of primitives
                code.append(f"        # {python_name}: list[{base_type}]")
                code.append(
                    f"        {python_name}, current_offset = serializer.unpack_array("
                )
                code.append(
                    f"            data, '{base_type}', {array_count}, current_offset"
                )
                code.append("        )")
        elif is_enum:
            # Enum - unpack as int then convert
            code.append(f"        # {python_name}: {base_type} (enum)")
            code.append(
                f"        {python_name}_raw, current_offset = serializer.unpack_value(data, 'uint8', current_offset)"
            )
            code.append(f"        {python_name} = {base_type}({python_name}_raw)")
        elif is_nested:
            # Nested structure
            code.append(f"        # {python_name}: {base_type}")
            code.append(
                f"        {python_name}, current_offset = {base_type}.unpack(data, current_offset)"
            )
        else:
            # Primitive type
            code.append(f"        # {python_name}: {base_type}")
            code.append(
                f"        {python_name}, current_offset = serializer.unpack_value(data, '{base_type}', current_offset)"
            )

    code.append("")
    # Create instance - format long return statements
    field_args = ", ".join([f"{name}={name}" for name in field_vars])
    return_stmt = f"        return cls({field_args}), current_offset"

    # If too long, break across multiple lines
    if len(return_stmt) > 120:
        code.append("        return (")
        code.append("            cls(")
        for i, name in enumerate(field_vars):
            if i < len(field_vars) - 1:
                code.append(f"                {name}={name},")
            else:
                code.append(f"                {name}={name},")
        code.append("            ),")
        code.append("            current_offset,")
        code.append("        )")
    else:
        code.append(return_stmt)

    return "\n".join(code)
```

##### generate_field_code

```python
generate_field_code(
    fields: dict[str, Any],
    compound_fields: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    packets_as_fields: dict[str, Any] | None = None,
    enum_types: set[str] | None = None,
) -> tuple[str, dict[str, dict[str, str]]]
```

Generate Python dataclass definitions for field structures.

| PARAMETER           | DESCRIPTION                                                                        |
| ------------------- | ---------------------------------------------------------------------------------- |
| `fields`            | Dictionary of field definitions **TYPE:** `dict[str, Any]`                         |
| `compound_fields`   | Dictionary of compound field definitions **TYPE:** \`dict[str, Any]                |
| `unions`            | Dictionary of union definitions (treated as fields) **TYPE:** \`dict[str, Any]     |
| `packets_as_fields` | Dictionary of packets that are also used as field types **TYPE:** \`dict[str, Any] |
| `enum_types`        | Set of enum type names **TYPE:** \`set[str]                                        |

| RETURNS                     | DESCRIPTION                                               |
| --------------------------- | --------------------------------------------------------- |
| `str`                       | Tuple of (code string, field mappings dict)               |
| `dict[str, dict[str, str]]` | Field mappings: {ClassName: {python_name: protocol_name}} |

Source code in `src/lifx/protocol/generator.py`

```python
def generate_field_code(
    fields: dict[str, Any],
    compound_fields: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    packets_as_fields: dict[str, Any] | None = None,
    enum_types: set[str] | None = None,
) -> tuple[str, dict[str, dict[str, str]]]:
    """Generate Python dataclass definitions for field structures.

    Args:
        fields: Dictionary of field definitions
        compound_fields: Dictionary of compound field definitions
        unions: Dictionary of union definitions (treated as fields)
        packets_as_fields: Dictionary of packets that are also used as field types
        enum_types: Set of enum type names

    Returns:
        Tuple of (code string, field mappings dict)
        Field mappings: {ClassName: {python_name: protocol_name}}
    """
    if enum_types is None:
        enum_types = set()

    code = []
    field_mappings: dict[str, dict[str, str]] = {}
    all_fields = {**fields}
    if compound_fields:
        all_fields.update(compound_fields)
    if unions:
        all_fields.update(unions)
    if packets_as_fields:
        all_fields.update(packets_as_fields)

    for field_name, field_def in sorted(all_fields.items()):
        code.append("@dataclass")
        code.append(f"class {field_name}:")

        # Check if this is a union (has comment indicating it's a union)
        is_union = isinstance(field_def, dict) and "comment" in field_def
        if is_union:
            code.append(
                f'    """Auto-generated union structure. {field_def.get("comment", "")}"""'
            )
        else:
            code.append('    """Auto-generated field structure."""')
        code.append("")

        field_map: dict[str, str] = {}
        fields_data = []

        # Handle both old format (dict) and new format (list of dicts)
        if isinstance(field_def, dict) and "fields" in field_def:
            # New format: {size_bytes: N, fields: [{name: "X", type: "uint16"}, ...]}
            field_list = field_def["fields"]

            # For unions, treat as a raw bytes field (they overlay, so just store raw data)
            if is_union:
                size_bytes = field_def.get("size_bytes", 16)
                code.append(f"    data: bytes  # Union of {size_bytes} bytes")
                field_map["data"] = "data"
                # For pack/unpack, use bytes field
                fields_data = [
                    {
                        "name": "data",
                        "type": f"[{size_bytes}]byte",
                        "size_bytes": size_bytes,
                    }
                ]
            else:
                # Normal field structure - process all fields
                fields_data = field_list  # Save for pack/unpack generation
                for field_item in field_list:
                    # Skip reserved fields without names (they won't be in dataclass)
                    if "name" not in field_item:
                        continue
                    protocol_name = field_item["name"]
                    attr_type = field_item["type"]
                    python_name = apply_field_name_quirks(to_snake_case(protocol_name))
                    python_type = convert_type_to_python(attr_type)

                    code.append(f"    {python_name}: {python_type}")
                    field_map[python_name] = protocol_name
        else:
            # Old format: {attr_name: type, ...}
            # Convert to new format for pack/unpack generation
            for protocol_name, attr_type in field_def.items():
                python_name = apply_field_name_quirks(to_snake_case(protocol_name))
                python_type = convert_type_to_python(attr_type)
                code.append(f"    {python_name}: {python_type}")
                field_map[python_name] = protocol_name
                # Build fields_data for old format
                fields_data.append({"name": protocol_name, "type": attr_type})

        field_mappings[field_name] = field_map

        # Add pack/unpack methods
        if fields_data:
            code.append("")
            code.append(generate_pack_method(fields_data, "field", enum_types))
            code.append("")
            code.append(
                generate_unpack_method(field_name, fields_data, "field", enum_types)
            )

        code.append("")
        code.append("")

    return "\n".join(code), field_mappings
```

##### generate_nested_packet_code

```python
generate_nested_packet_code(
    packets: dict[str, Any], type_aliases: dict[str, str] | None = None
) -> str
```

Generate nested Python packet class definitions.

| PARAMETER      | DESCRIPTION                                                                                             |
| -------------- | ------------------------------------------------------------------------------------------------------- |
| `packets`      | Dictionary of packet definitions (grouped by category) **TYPE:** `dict[str, Any]`                       |
| `type_aliases` | Optional dict mapping type names to their aliases (for collision resolution) **TYPE:** \`dict[str, str] |

| RETURNS | DESCRIPTION                                   |
| ------- | --------------------------------------------- |
| `str`   | Python code string with nested packet classes |

Source code in `src/lifx/protocol/generator.py`

```python
def generate_nested_packet_code(
    packets: dict[str, Any], type_aliases: dict[str, str] | None = None
) -> str:
    """Generate nested Python packet class definitions.

    Args:
        packets: Dictionary of packet definitions (grouped by category)
        type_aliases: Optional dict mapping type names to their aliases (for collision resolution)

    Returns:
        Python code string with nested packet classes
    """
    if type_aliases is None:
        type_aliases = {}

    code = []

    # Flatten packets if they're grouped by category
    flat_packets: list[tuple[str, str, dict[str, Any]]] = []

    # Check if packets are grouped by category (new format)
    sample_key = next(iter(packets.keys())) if packets else None
    if sample_key and isinstance(packets[sample_key], dict):
        sample_value = packets[sample_key]
        # Check if this is a category grouping (contains nested packet dicts)
        if any(isinstance(v, dict) and "pkt_type" in v for v in sample_value.values()):
            # New format: grouped by category
            for category, category_packets in packets.items():
                for packet_name, packet_def in category_packets.items():
                    flat_packets.append((category, packet_name, packet_def))
        else:
            # Old format: flat packets with category field
            for packet_name, packet_def in packets.items():
                category = packet_def.get("category", "misc")
                flat_packets.append((category, packet_name, packet_def))

    # Group by category
    categories: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for category, packet_name, packet_def in flat_packets:
        if category not in categories:
            categories[category] = []
        categories[category].append((packet_name, packet_def))

    # Build lookup table for request-to-response mapping
    # Maps (category, short_name) -> pkt_type
    packet_lookup: dict[tuple[str, str], int] = {}
    for category, packets_list in categories.items():
        parts = category.split("_")
        category_class = "".join(part.capitalize() for part in parts)
        for packet_name, packet_def in packets_list:
            short_name = packet_name
            if packet_name.lower().startswith(category_class.lower()):
                short_name = packet_name[len(category_class) :]
            if category_class == "Light":
                if short_name == "Get":
                    short_name = "GetColor"
                elif short_name == "State":
                    short_name = "StateColor"
            short_name = apply_extended_multizone_packet_quirks(
                short_name, category_class
            )
            packet_lookup[(category, short_name)] = packet_def["pkt_type"]

    # Generate category classes with nested packet classes
    for category in sorted(categories.keys()):
        # Generate category class
        # Quirk: Convert category names to proper camel case (multi_zone -> MultiZone)
        # Split on underscores, capitalize each part, then join
        parts = category.split("_")
        category_class = "".join(part.capitalize() for part in parts)
        code.append("")
        code.append(f"class {category_class}(Packet):")
        code.append(f'    """{category_class} category packets."""')
        code.append("")

        # Generate nested packet classes
        for packet_name, packet_def in sorted(categories[category]):
            pkt_type = packet_def["pkt_type"]
            fields_data = packet_def.get("fields", [])

            # Remove category prefix from packet name (e.g., DeviceGetLabel -> GetLabel)
            # The packet name format is: CategoryActionTarget (e.g., DeviceGetLabel, LightSetColor)
            # Use case-insensitive matching to handle multi_zone -> Multizone -> MultiZone
            short_name = packet_name
            if packet_name.lower().startswith(category_class.lower()):
                short_name = packet_name[len(category_class) :]

            # Quirk: Rename Light.Get/Set/State to Light.GetColor/SetColor/StateColor
            # for better clarity (Set and SetColor are different packets)
            if category_class == "Light":
                if short_name == "Get":
                    short_name = "GetColor"
                elif short_name == "State":
                    short_name = "StateColor"

            # Quirk: Rename extended multizone packets to follow standard naming convention
            short_name = apply_extended_multizone_packet_quirks(
                short_name, category_class
            )

            code.append("    @dataclass")
            code.append(f"    class {short_name}(Packet):")
            code.append(f'        """Packet type {pkt_type}."""')
            code.append("")
            code.append(f"        PKT_TYPE: ClassVar[int] = {pkt_type}")

            # Add STATE_TYPE for Get*/Request packets (expected response packet type)
            state_pkt_type = None
            if short_name.startswith("Get"):
                # Special case: GetColorZones → StateMultiZone (not StateColorZones)
                if category_class == "MultiZone" and short_name == "GetColorZones":
                    state_pkt_type = packet_lookup.get((category, "StateMultiZone"))
                else:
                    # Standard naming: GetXxx → StateXxx
                    state_name = short_name.replace("Get", "State", 1)
                    state_pkt_type = packet_lookup.get((category, state_name))
            elif short_name.endswith("Request"):
                # XxxRequest → XxxResponse
                response_name = short_name.replace("Request", "Response")
                state_pkt_type = packet_lookup.get((category, response_name))

            if state_pkt_type is not None:
                code.append(f"        STATE_TYPE: ClassVar[int] = {state_pkt_type}")

            # Format fields_data - split long lists across multiple lines
            # Account for the prefix "        _fields: ClassVar[list[dict[str, Any]]] = " which is ~50 chars
            fields_repr = format_long_list(fields_data, max_line_length=70)
            if "\n" in fields_repr:
                # Multi-line format - indent properly
                code.append("        _fields: ClassVar[list[dict[str, Any]]] = (")
                for line in fields_repr.split("\n"):
                    if line.strip():
                        code.append(f"        {line}")
                code.append("        )")
            else:
                code.append(
                    f"        _fields: ClassVar[list[dict[str, Any]]] = {fields_repr}"
                )

            # Add packet metadata for smart request handling
            # Classify packet by name pattern: Get*, Set*, State*, or OTHER
            packet_kind = "OTHER"
            if short_name.startswith("Get"):
                packet_kind = "GET"
            elif short_name.startswith("Set"):
                packet_kind = "SET"
            elif short_name.startswith("State"):
                packet_kind = "STATE"

            # Quirk: CopyFrameBuffer is semantically a SET operation
            # It modifies device state without returning data
            if category_class == "Tile" and short_name == "CopyFrameBuffer":
                packet_kind = "SET"

            code.append("")
            code.append("        # Packet metadata for automatic handling")
            code.append(f"        _packet_kind: ClassVar[str] = {repr(packet_kind)}")

            # Requires acknowledgement/response based on packet kind
            # GET requests: ack_required=False, res_required=False (device responds anyway)
            # SET requests: ack_required=True, res_required=False (need acknowledgement)
            requires_ack = packet_kind == "SET"
            requires_response = False
            code.append(f"        _requires_ack: ClassVar[bool] = {requires_ack}")
            code.append(
                f"        _requires_response: ClassVar[bool] = {requires_response}"
            )
            code.append("")

            # Generate dataclass fields (only non-reserved)
            has_fields = False
            if isinstance(fields_data, list):
                for field_item in fields_data:
                    # Skip reserved fields
                    if "name" not in field_item:
                        continue
                    protocol_name = field_item["name"]
                    field_type = field_item["type"]
                    python_name = apply_field_name_quirks(to_snake_case(protocol_name))
                    python_type = convert_type_to_python(field_type, type_aliases)
                    code.append(f"        {python_name}: {python_type}")
                    has_fields = True

            if not has_fields:
                code.append("        pass")

            code.append("")

        code.append("")

    return "\n".join(code)
```

##### generate_types_file

```python
generate_types_file(
    enums: dict[str, Any],
    fields: dict[str, Any],
    compound_fields: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    packets_as_fields: dict[str, Any] | None = None,
) -> str
```

Generate complete types.py file.

| PARAMETER           | DESCRIPTION                                                          |
| ------------------- | -------------------------------------------------------------------- |
| `enums`             | Enum definitions **TYPE:** `dict[str, Any]`                          |
| `fields`            | Field structure definitions **TYPE:** `dict[str, Any]`               |
| `compound_fields`   | Compound field definitions **TYPE:** \`dict[str, Any]                |
| `unions`            | Union definitions **TYPE:** \`dict[str, Any]                         |
| `packets_as_fields` | Packets that are also used as field types **TYPE:** \`dict[str, Any] |

| RETURNS | DESCRIPTION                  |
| ------- | ---------------------------- |
| `str`   | Complete Python file content |

Source code in `src/lifx/protocol/generator.py`

```python
def generate_types_file(
    enums: dict[str, Any],
    fields: dict[str, Any],
    compound_fields: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    packets_as_fields: dict[str, Any] | None = None,
) -> str:
    """Generate complete types.py file.

    Args:
        enums: Enum definitions
        fields: Field structure definitions
        compound_fields: Compound field definitions
        unions: Union definitions
        packets_as_fields: Packets that are also used as field types

    Returns:
        Complete Python file content
    """
    header = '''"""Auto-generated LIFX protocol types.

DO NOT EDIT THIS FILE MANUALLY.
Generated from https://github.com/LIFX/public-protocol/blob/main/protocol.yml
by protocol/generator.py

Uses Pythonic naming conventions (snake_case fields, shortened enums) while
maintaining compatibility with the official LIFX protocol through mappings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


'''

    code = header
    code += generate_enum_code(enums)
    code += "\n"

    # Extract enum names for pack/unpack generation
    enum_names = set(enums.keys())

    field_code, field_mappings = generate_field_code(
        fields, compound_fields, unions, packets_as_fields, enum_names
    )
    code += field_code
    code += "\n"

    # Add type aliases for common names
    code += "# Type aliases for convenience\n"
    all_field_names = {
        **fields,
        **(compound_fields or {}),
        **(unions or {}),
        **(packets_as_fields or {}),
    }
    if "TileStateDevice" in all_field_names:
        code += "TileDevice = TileStateDevice  # Pythonic alias\n"
    code += "\n"

    # Add field name mappings as module-level constant (formatted for readability)
    code += "# Field name mappings: Python name -> Protocol name\n"
    code += "# Used by serializer to translate between conventions\n"
    code += "FIELD_MAPPINGS: dict[str, dict[str, str]] = {\n"
    for class_name in sorted(field_mappings.keys()):
        mappings = field_mappings[class_name]
        # Format each class mapping - if too long, break it into multiple lines
        mappings_str = repr(mappings)
        line = f"    {repr(class_name)}: {mappings_str},"
        if len(line) > 120:
            # Multi-line format
            code += f"    {repr(class_name)}: {{\n"
            for py_name, proto_name in sorted(mappings.items()):
                code += f"        {repr(py_name)}: {repr(proto_name)},\n"
            code += "    },\n"
        else:
            code += line + "\n"
    code += "}\n"
    code += "\n"

    return code
```

##### generate_packets_file

```python
generate_packets_file(
    packets: dict[str, Any],
    fields: dict[str, Any],
    compound_fields: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    packets_as_fields: dict[str, Any] | None = None,
    enums: dict[str, Any] | None = None,
) -> str
```

Generate complete packets.py file.

| PARAMETER           | DESCRIPTION                                                                        |
| ------------------- | ---------------------------------------------------------------------------------- |
| `packets`           | Packet definitions **TYPE:** `dict[str, Any]`                                      |
| `fields`            | Field definitions (for imports) **TYPE:** `dict[str, Any]`                         |
| `compound_fields`   | Compound field definitions (for imports) **TYPE:** \`dict[str, Any]                |
| `unions`            | Union definitions (for imports) **TYPE:** \`dict[str, Any]                         |
| `packets_as_fields` | Packets that are also used as field types (for imports) **TYPE:** \`dict[str, Any] |
| `enums`             | Enum definitions for detecting enum types **TYPE:** \`dict[str, Any]               |

| RETURNS | DESCRIPTION                  |
| ------- | ---------------------------- |
| `str`   | Complete Python file content |

Source code in `src/lifx/protocol/generator.py`

```python
def generate_packets_file(
    packets: dict[str, Any],
    fields: dict[str, Any],
    compound_fields: dict[str, Any] | None = None,
    unions: dict[str, Any] | None = None,
    packets_as_fields: dict[str, Any] | None = None,
    enums: dict[str, Any] | None = None,
) -> str:
    """Generate complete packets.py file.

    Args:
        packets: Packet definitions
        fields: Field definitions (for imports)
        compound_fields: Compound field definitions (for imports)
        unions: Union definitions (for imports)
        packets_as_fields: Packets that are also used as field types (for imports)
        enums: Enum definitions for detecting enum types

    Returns:
        Complete Python file content
    """
    # Extract enum names for pack/unpack generation
    enum_names = set(enums.keys()) if enums else set()

    # Collect all field types and enum types used in packets
    used_fields = set()
    used_enums = set()
    all_fields = {**fields}
    if compound_fields:
        all_fields.update(compound_fields)
    if unions:
        all_fields.update(unions)
    if packets_as_fields:
        all_fields.update(packets_as_fields)

    # Flatten packets to scan for used field types
    flat_packets: list[dict[str, Any]] = []
    for value in packets.values():
        if isinstance(value, dict):
            # Check if this is a category grouping
            if any(isinstance(v, dict) and "pkt_type" in v for v in value.values()):
                # New format: grouped by category
                for packet_def in value.values():
                    flat_packets.append(packet_def)
            elif "pkt_type" in value:
                # Old format: direct packet
                flat_packets.append(value)

    for packet_def in flat_packets:
        fields_data = packet_def.get("fields", [])
        # Handle both list and dict formats
        if isinstance(fields_data, list):
            for field_item in fields_data:
                if "type" in field_item:
                    field_type = field_item["type"]
                    base_type, _, is_nested = parse_field_type(field_type)
                    if is_nested:
                        if base_type in all_fields:
                            used_fields.add(base_type)
                        elif base_type in enum_names:
                            used_enums.add(base_type)
        elif isinstance(fields_data, dict):
            for field_type in fields_data.values():
                base_type, _, is_nested = parse_field_type(field_type)
                if is_nested:
                    if base_type in all_fields:
                        used_fields.add(base_type)
                    elif base_type in enum_names:
                        used_enums.add(base_type)

    # Generate imports with collision detection
    imports = ""
    all_imports = sorted(used_fields | used_enums)
    if all_imports:
        # Detect name collisions with packet category names
        category_names = set()
        for category in packets.keys():
            if isinstance(packets[category], dict):
                # Convert category name to class name (same as in generate_nested_packet_code)
                parts = category.split("_")
                category_class = "".join(part.capitalize() for part in parts)
                category_names.add(category_class)

        # Generate import list with aliases for collisions
        import_items = []
        type_aliases = {}  # Map original name to aliased name
        for name in all_imports:
            if name in category_names:
                # Use alias to avoid collision
                aliased_name = f"{name}Field"
                import_items.append(f"{name} as {aliased_name}")
                type_aliases[name] = aliased_name
            else:
                import_items.append(name)

        imports = format_long_import(import_items) + "\n"
    else:
        type_aliases = {}
        imports = ""

    header = f'''"""Auto-generated LIFX protocol packets.

DO NOT EDIT THIS FILE MANUALLY.
Generated from https://github.com/LIFX/public-protocol/blob/main/protocol.yml
by protocol/generator.py

Uses nested packet classes organized by category (Device, Light, etc.).
Each packet inherits from base Packet class which provides generic pack/unpack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from lifx.protocol.base import Packet
{imports}
'''

    code = header
    packet_code = generate_nested_packet_code(packets, type_aliases)
    code += packet_code

    # Generate packet registry for nested classes
    code += "\n\n"
    code += "# Packet Registry - maps packet type to nested packet class\n"
    code += "PACKET_REGISTRY: dict[int, type[Packet]] = {\n"

    # Build registry with nested class paths
    registry_items = []
    for category, value in packets.items():
        if isinstance(value, dict):
            # Check if this is a category grouping
            if any(isinstance(v, dict) and "pkt_type" in v for v in value.values()):
                # New format: grouped by category
                # Quirk: Convert category names to proper camel case (multi_zone -> MultiZone)
                parts = category.split("_")
                category_class = "".join(part.capitalize() for part in parts)
                for packet_name, packet_def in value.items():
                    pkt_type = packet_def.get("pkt_type")
                    if pkt_type is not None:
                        # Remove category prefix to get short name
                        # Use case-insensitive matching to handle multi_zone -> Multizone -> MultiZone
                        short_name = packet_name
                        if packet_name.lower().startswith(category_class.lower()):
                            short_name = packet_name[len(category_class) :]

                        # Quirk: Rename Light.Get/Set/State to Light.GetColor/SetColor/StateColor
                        if category_class == "Light":
                            if short_name == "Get":
                                short_name = "GetColor"
                            elif short_name == "State":
                                short_name = "StateColor"

                        # Quirk: Rename extended multizone packets to follow standard naming convention
                        short_name = apply_extended_multizone_packet_quirks(
                            short_name, category_class
                        )

                        # Full path: Category.ShortName
                        full_path = f"{category_class}.{short_name}"
                        registry_items.append((pkt_type, full_path))

    # Sort by packet type for readability
    for pkt_type, full_path in sorted(registry_items):
        code += f"    {pkt_type}: {full_path},\n"

    code += "}\n"
    code += "\n\n"
    code += "def get_packet_class(pkt_type: int) -> type[Packet] | None:\n"
    code += '    """Get packet class for a given packet type.\n'
    code += "\n"
    code += "    Args:\n"
    code += "        pkt_type: Packet type number\n"
    code += "\n"
    code += "    Returns:\n"
    code += "        Nested packet class, or None if unknown\n"
    code += '    """\n'
    code += "    return PACKET_REGISTRY.get(pkt_type)\n"

    return code
```

##### download_protocol

```python
download_protocol() -> dict[str, Any]
```

Download and parse protocol.yml from LIFX GitHub repository.

| RETURNS          | DESCRIPTION                |
| ---------------- | -------------------------- |
| `dict[str, Any]` | Parsed protocol dictionary |

| RAISES      | DESCRIPTION       |
| ----------- | ----------------- |
| `URLError`  | If download fails |
| `YAMLError` | If parsing fails  |

Source code in `src/lifx/protocol/generator.py`

```python
def download_protocol() -> dict[str, Any]:
    """Download and parse protocol.yml from LIFX GitHub repository.

    Returns:
        Parsed protocol dictionary

    Raises:
        URLError: If download fails
        yaml.YAMLError: If parsing fails
    """
    parsed_url = urlparse(PROTOCOL_URL)
    if parsed_url.scheme == "https" and parsed_url.netloc.startswith(
        "raw.githubusercontent.com"
    ):
        print(f"Downloading protocol.yml from {PROTOCOL_URL}...")
        with urlopen(PROTOCOL_URL) as response:  # nosec B310
            protocol_data = response.read()

        print("Parsing protocol specification...")
        protocol = yaml.safe_load(protocol_data)
        return protocol
```

##### validate_protocol_spec

```python
validate_protocol_spec(protocol: dict[str, Any]) -> list[str]
```

Validate protocol specification for missing type references.

| PARAMETER  | DESCRIPTION                                           |
| ---------- | ----------------------------------------------------- |
| `protocol` | Parsed protocol dictionary **TYPE:** `dict[str, Any]` |

| RETURNS     | DESCRIPTION                                         |
| ----------- | --------------------------------------------------- |
| `list[str]` | List of error messages (empty if validation passes) |

Source code in `src/lifx/protocol/generator.py`

```python
def validate_protocol_spec(protocol: dict[str, Any]) -> list[str]:
    """Validate protocol specification for missing type references.

    Args:
        protocol: Parsed protocol dictionary

    Returns:
        List of error messages (empty if validation passes)
    """
    errors: list[str] = []
    registry = TypeRegistry()

    # Register all types
    enums = protocol.get("enums", {})
    fields = protocol.get("fields", {})
    compound_fields = protocol.get("compound_fields", {})
    unions = protocol.get("unions", {})
    packets = protocol.get("packets", {})

    # Register enums
    for enum_name in enums.keys():
        registry.register_enum(enum_name)

    # Register field structures
    for field_name in fields.keys():
        registry.register_field(field_name)

    # Register compound fields
    for field_name in compound_fields.keys():
        registry.register_field(field_name)

    # Register unions
    for union_name in unions.keys():
        registry.register_union(union_name)

    # Register packets (flatten by category)
    for category_packets in packets.values():
        if isinstance(category_packets, dict):
            for packet_name in category_packets.keys():
                registry.register_packet(packet_name)

    # Validate field type references
    def validate_field_types(struct_name: str, struct_def: dict[str, Any]) -> None:
        """Validate all field types in a structure."""
        if isinstance(struct_def, dict) and "fields" in struct_def:
            for field_item in struct_def["fields"]:
                if "type" in field_item:
                    field_type = field_item["type"]
                    field_name = field_item.get("name", "reserved")
                    base_type, _, _ = parse_field_type(field_type)

                    # Check if type is defined
                    if not registry.has_type(base_type):
                        errors.append(
                            f"{struct_name}.{field_name}: Unknown type '{base_type}' in field type '{field_type}'"
                        )

    # Validate fields
    for field_name, field_def in fields.items():
        validate_field_types(f"fields.{field_name}", field_def)

    # Validate compound fields
    for field_name, field_def in compound_fields.items():
        validate_field_types(f"compound_fields.{field_name}", field_def)

    # Validate unions
    for union_name, union_def in unions.items():
        validate_field_types(f"unions.{union_name}", union_def)

    # Validate packets
    for category, category_packets in packets.items():
        if isinstance(category_packets, dict):
            for packet_name, packet_def in category_packets.items():
                if isinstance(packet_def, dict):
                    validate_field_types(
                        f"packets.{category}.{packet_name}", packet_def
                    )

    return errors
```

##### should_skip_button_relay

```python
should_skip_button_relay(name: str) -> bool
```

Check if a name should be skipped (Button or Relay related).

| PARAMETER | DESCRIPTION                                                                  |
| --------- | ---------------------------------------------------------------------------- |
| `name`    | Type name to check (enum, field, union, packet, or category) **TYPE:** `str` |

| RETURNS | DESCRIPTION                                                   |
| ------- | ------------------------------------------------------------- |
| `bool`  | True if the name starts with Button or Relay, False otherwise |

Source code in `src/lifx/protocol/generator.py`

```python
def should_skip_button_relay(name: str) -> bool:
    """Check if a name should be skipped (Button or Relay related).

    Args:
        name: Type name to check (enum, field, union, packet, or category)

    Returns:
        True if the name starts with Button or Relay, False otherwise
    """
    return name.startswith("Button") or name.startswith("Relay")
```

##### filter_button_relay_items

```python
filter_button_relay_items(items: dict[str, Any]) -> dict[str, Any]
```

Filter out Button and Relay items from a dictionary.

| PARAMETER | DESCRIPTION                                              |
| --------- | -------------------------------------------------------- |
| `items`   | Dictionary of items to filter **TYPE:** `dict[str, Any]` |

| RETURNS          | DESCRIPTION                                    |
| ---------------- | ---------------------------------------------- |
| `dict[str, Any]` | Filtered dictionary without Button/Relay items |

Source code in `src/lifx/protocol/generator.py`

```python
def filter_button_relay_items(items: dict[str, Any]) -> dict[str, Any]:
    """Filter out Button and Relay items from a dictionary.

    Args:
        items: Dictionary of items to filter

    Returns:
        Filtered dictionary without Button/Relay items
    """
    return {
        name: value
        for name, value in items.items()
        if not should_skip_button_relay(name)
    }
```

##### filter_button_relay_packets

```python
filter_button_relay_packets(packets: dict[str, Any]) -> dict[str, Any]
```

Filter out button and relay category packets.

| PARAMETER | DESCRIPTION                                                                       |
| --------- | --------------------------------------------------------------------------------- |
| `packets` | Dictionary of packet definitions (grouped by category) **TYPE:** `dict[str, Any]` |

| RETURNS          | DESCRIPTION                                         |
| ---------------- | --------------------------------------------------- |
| `dict[str, Any]` | Filtered dictionary without button/relay categories |

Source code in `src/lifx/protocol/generator.py`

```python
def filter_button_relay_packets(packets: dict[str, Any]) -> dict[str, Any]:
    """Filter out button and relay category packets.

    Args:
        packets: Dictionary of packet definitions (grouped by category)

    Returns:
        Filtered dictionary without button/relay categories
    """
    return {
        category: category_packets
        for category, category_packets in packets.items()
        if category not in ("button", "relay")
    }
```

##### extract_packets_as_fields

```python
extract_packets_as_fields(
    packets: dict[str, Any], fields: dict[str, Any]
) -> dict[str, Any]
```

Extract packets that are used as field types in other structures.

| PARAMETER | DESCRIPTION                                                        |
| --------- | ------------------------------------------------------------------ |
| `packets` | Dictionary of packet definitions **TYPE:** `dict[str, Any]`        |
| `fields`  | Dictionary of field definitions to scan **TYPE:** `dict[str, Any]` |

| RETURNS          | DESCRIPTION                                                         |
| ---------------- | ------------------------------------------------------------------- |
| `dict[str, Any]` | Dictionary of packet definitions that are referenced as field types |

Source code in `src/lifx/protocol/generator.py`

```python
def extract_packets_as_fields(
    packets: dict[str, Any], fields: dict[str, Any]
) -> dict[str, Any]:
    """Extract packets that are used as field types in other structures.

    Args:
        packets: Dictionary of packet definitions
        fields: Dictionary of field definitions to scan

    Returns:
        Dictionary of packet definitions that are referenced as field types
    """
    packets_as_fields = {}

    # Flatten packets first
    flat_packets = {}
    for category, category_packets in packets.items():
        if isinstance(category_packets, dict):
            for packet_name, packet_def in category_packets.items():
                if isinstance(packet_def, dict) and "pkt_type" in packet_def:
                    flat_packets[packet_name] = packet_def

    # Scan all fields for references to packet types
    all_structures = {**fields}

    for struct_def in all_structures.values():
        if isinstance(struct_def, dict) and "fields" in struct_def:
            for field_item in struct_def["fields"]:
                if "type" in field_item:
                    field_type = field_item["type"]
                    base_type, _, is_nested = parse_field_type(field_type)

                    # Check if this references a packet
                    if is_nested and base_type in flat_packets:
                        packets_as_fields[base_type] = flat_packets[base_type]

    return packets_as_fields
```

##### main

```python
main() -> None
```

Main generator entry point.

Source code in `src/lifx/protocol/generator.py`

```python
def main() -> None:
    """Main generator entry point."""
    try:
        # Download and parse protocol from GitHub
        protocol = download_protocol()
    except Exception as e:
        print(f"Error: Failed to download protocol.yml: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract sections
    enums = protocol.get("enums", {})
    fields = protocol.get("fields", {})
    compound_fields = protocol.get("compound_fields", {})
    unions = protocol.get("unions", {})
    packets = protocol.get("packets", {})

    # Filter out Button and Relay items (not relevant for light control)
    print("Filtering out Button and Relay items...")
    enums = filter_button_relay_items(enums)
    fields = filter_button_relay_items(fields)
    compound_fields = filter_button_relay_items(compound_fields)
    unions = filter_button_relay_items(unions)
    packets = filter_button_relay_packets(packets)

    # Apply local quirks to fix protocol issues
    print("Applying local protocol quirks...")
    fields = apply_tile_effect_parameter_quirk(fields)

    # Rebuild protocol dict with filtered items for validation
    filtered_protocol = {
        **protocol,
        "enums": enums,
        "fields": fields,
        "compound_fields": compound_fields,
        "unions": unions,
        "packets": packets,
    }

    # Validate filtered protocol specification
    print("Validating protocol specification...")
    validation_errors = validate_protocol_spec(filtered_protocol)
    if validation_errors:
        print("Validation failed with the following errors:", file=sys.stderr)
        for error in validation_errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)
    print("Validation passed!")

    # Extract packets that are used as field types (e.g., DeviceStateVersion)
    packets_as_fields = extract_packets_as_fields(packets, fields)

    print(f"Found {len(unions)} unions")
    print(
        f"Found {len(packets_as_fields)} packets used as field types: {list(packets_as_fields.keys())}"
    )

    # Determine output directory
    project_root = Path(__file__).parent.parent.parent.parent
    protocol_dir = project_root / "src" / "lifx" / "protocol"

    # Generate protocol_types.py (avoid conflict with Python's types module)
    types_code = generate_types_file(
        enums, fields, compound_fields, unions, packets_as_fields
    )
    types_file = protocol_dir / "protocol_types.py"
    with open(types_file, "w") as f:
        f.write(types_code)
    print(f"Generated {types_file}")

    # Generate packets.py
    packets_code = generate_packets_file(
        packets, fields, compound_fields, unions, packets_as_fields, enums
    )
    packets_file = protocol_dir / "packets.py"
    with open(packets_file, "w") as f:
        f.write(packets_code)
    print(f"Generated {packets_file}")
```

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

## Product Registry

The product registry provides automatic device type detection and capability information:

### ProductInfo

```python
ProductInfo(
    pid: int,
    name: str,
    vendor: int,
    capabilities: int,
    temperature_range: TemperatureRange | None,
    min_ext_mz_firmware: int | None,
)
```

Information about a LIFX product.

| ATTRIBUTE             | DESCRIPTION                                                      |
| --------------------- | ---------------------------------------------------------------- |
| `pid`                 | Product ID **TYPE:** `int`                                       |
| `name`                | Product name **TYPE:** `str`                                     |
| `vendor`              | Vendor ID (always 1 for LIFX) **TYPE:** `int`                    |
| `capabilities`        | Bitfield of ProductCapability flags **TYPE:** `int`              |
| `temperature_range`   | Min/max color temperature in Kelvin **TYPE:** \`TemperatureRange |
| `min_ext_mz_firmware` | Minimum firmware version for extended multizone **TYPE:** \`int  |

| METHOD                        | DESCRIPTION                                                          |
| ----------------------------- | -------------------------------------------------------------------- |
| `has_capability`              | Check if product has a specific capability.                          |
| `supports_extended_multizone` | Check if extended multizone is supported for given firmware version. |

#### Attributes

##### has_color

```python
has_color: bool
```

Check if product supports color.

##### has_infrared

```python
has_infrared: bool
```

Check if product supports infrared.

##### has_multizone

```python
has_multizone: bool
```

Check if product supports multizone.

##### has_chain

```python
has_chain: bool
```

Check if product supports chaining.

##### has_matrix

```python
has_matrix: bool
```

Check if product supports matrix (2D grid).

##### has_relays

```python
has_relays: bool
```

Check if product has relays.

##### has_buttons

```python
has_buttons: bool
```

Check if product has buttons.

##### has_hev

```python
has_hev: bool
```

Check if product supports HEV.

##### has_extended_multizone

```python
has_extended_multizone: bool
```

Check if product supports extended multizone.

#### Functions

##### has_capability

```python
has_capability(capability: ProductCapability) -> bool
```

Check if product has a specific capability.

| PARAMETER    | DESCRIPTION                                       |
| ------------ | ------------------------------------------------- |
| `capability` | Capability to check **TYPE:** `ProductCapability` |

| RETURNS | DESCRIPTION                        |
| ------- | ---------------------------------- |
| `bool`  | True if product has the capability |

Source code in `src/lifx/products/registry.py`

```python
def has_capability(self, capability: ProductCapability) -> bool:
    """Check if product has a specific capability.

    Args:
        capability: Capability to check

    Returns:
        True if product has the capability
    """
    return bool(self.capabilities & capability)
```

##### supports_extended_multizone

```python
supports_extended_multizone(firmware_version: int | None = None) -> bool
```

Check if extended multizone is supported for given firmware version.

| PARAMETER          | DESCRIPTION                                          |
| ------------------ | ---------------------------------------------------- |
| `firmware_version` | Firmware version to check (optional) **TYPE:** \`int |

| RETURNS | DESCRIPTION                             |
| ------- | --------------------------------------- |
| `bool`  | True if extended multizone is supported |

Source code in `src/lifx/products/registry.py`

```python
def supports_extended_multizone(self, firmware_version: int | None = None) -> bool:
    """Check if extended multizone is supported for given firmware version.

    Args:
        firmware_version: Firmware version to check (optional)

    Returns:
        True if extended multizone is supported
    """
    if not self.has_extended_multizone:
        return False
    if self.min_ext_mz_firmware is None:
        return True
    if firmware_version is None:
        return True
    return firmware_version >= self.min_ext_mz_firmware
```

### ProductCapability

Bases: `IntEnum`

Product capability flags.

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

1. Download the latest `protocol.yml` from the [LIFX public-protocol repository](https://github.com/LIFX/public-protocol/blob/main/protocol.yml)
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
