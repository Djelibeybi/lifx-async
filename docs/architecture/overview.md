# Architecture Overview

lifx-async is built as a layered architecture with clear separation of concerns.

## System Architecture

```mermaid
graph TB
    subgraph "Layer 4: High-Level API"
        API[api.py<br/>discover, find_lights, etc.]
        DeviceGroup[DeviceGroup<br/>Batch operations]
    end

    subgraph "Layer 3: Device Layer"
        Device[Device<br/>Base class]
        Light[Light<br/>Color control]
        Hev[HevLight<br />HEV support]
        Infrared[InfraredLight<br />Infrared support]
        MultiZone[MultiZoneLight<br/>Linear/1D zones]
        Matrix[MatrixLight<br/>Matrix/2D zones]
    end

    subgraph "Layer 2: Network Layer"
        Discovery[Discovery<br/>UDP broadcast]
        Connection[Connection<br/>Lazy opening]
        Transport[Transport<br/>UDP sockets]
    end

    subgraph "Layer 1: Protocol Layer"
        Generator[Generator<br/>YAML → Python]
        Types[Protocol Types<br/>Enums, HSBK, etc.]
        Packets[Packets<br/>Message classes]
    end

    subgraph "External"
        YAML[protocol.yml<br/>LIFX specification]
        Network[UDP Network<br/>Port 56700]
    end

    API --> DeviceGroup
    DeviceGroup --> Light
    DeviceGroup --> Hev
    DeviceGroup --> Infrared
    DeviceGroup --> MultiZone
    DeviceGroup --> Matrix
    API --> Discovery
    Device --> Connection
    Light --> Device
    Hev --> Light
    Infrared --> Light
    MultiZone --> Light
    Matrix --> Light
    Connection --> Transport
    Connection --> Packets
    Discovery --> Transport
    Packets --> Types
    Transport --> Network
    Generator --> YAML
    Generator -.generates.-> Types
    Generator -.generates.-> Packets

    style API fill:#e1f5e1
    style Device fill:#e1f0ff
    style Connection fill:#fff4e1
    style Generator fill:#ffe1f0
```

## Layer Responsibilities

### Layer 1: Protocol Layer

**Purpose**: Handle LIFX binary protocol

- **Auto-Generated**: All code generated from `protocol.yml`
- **Type-Safe**: Full type hints for all structures
- **Binary Serialization**: Pack/unpack protocol messages
- **No Business Logic**: Pure data structures

**Key Files**:

- `protocol_types.py` - Enums, HSBK, field structures
- `packets.py` - Packet class definitions
- `generator.py` - Code generation from YAML

**Example**:

```python
from lifx.protocol.packets import Light
from lifx import HSBK

# Create a packet
packet = Light.SetColor(
    color=HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500), duration=1.0
)

# Serialize to bytes
data = packet.pack()
```

### Layer 2: Network Layer

**Purpose**: Handle network communication

- **UDP Transport**: Async socket operations
- **Discovery**: Broadcast-based device discovery
- **Lazy Connections**: Auto-open on first request
- **Retry Logic**: Automatic retry with exponential backoff

**Key Files**:

- `transport.py` - UDP socket wrapper
- `discovery.py` - Device discovery
- `connection.py` - Connection management
- `message.py` - Message building

**Example**:

```python
from lifx.network.connection import DeviceConnection

conn = DeviceConnection(serial="d073d5123456", ip="192.168.1.100")
# Connection opens lazily on first request
response = await conn.request(packet)
```

### Layer 3: Device Layer

**Purpose**: Device abstractions with high-level operations

- **Device Types**: Base, Light, HevLight, InfraredLight, MultiZoneLight, MatrixLight
- **State Caching**: Cached state properties for efficient access
- **Type Detection**: Automatic capability detection
- **Async Context Managers**: Automatic resource cleanup

**Key Files**:

- `base.py` - Base Device class
- `light.py` - Light class
- `hev.py` - HevLight class
- `infrared.py` - InfraredLight class
- `multizone.py` - MultiZoneLight class
- `matrix.py` - MatrixLight class

**Example**:

```python
from lifx import Light

async with Light(serial, ip) as light:
    # High-level operations
    await light.set_color(Colors.BLUE)
    await light.pulse(Colors.RED, period=1.0, cycles=5)
```

### Layer 4: High-Level API

**Purpose**: Simple, batteries-included API

- **Simplified Discovery**: One-line device discovery
- **Batch Operations**: Control multiple devices
- **Direct Connection**: Connect by IP without discovery
- **Filtered Discovery**: Find devices by label or serial

**Key Files**:

- `api.py` - High-level functions
- `color.py` - Color utilities

**Example**:

```python
from lifx import discover, DeviceGroup, Colors

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

await group.set_color(Colors.BLUE)
```

## Data Flow

### Sending a Command

```mermaid
sequenceDiagram
    participant User
    participant Light
    participant Connection
    participant Transport
    participant Device

    User->>Light: set_color(Colors.BLUE)
    Light->>Light: Convert to HSBK
    Light->>Connection: send_packet(SetColor)
    Connection->>Connection: Serialize packet
    Connection->>Transport: send_message(bytes)
    Transport->>Device: UDP packet
    Device-->>Transport: UDP acknowledgment
    Transport-->>Connection: Response
    Connection-->>Connection: Deserialize packet
    Connection-->>Light: Reply
    Light-->>User: Success
```

### Discovery Process

```mermaid
sequenceDiagram
    participant User
    participant Discovery
    participant Transport
    participant Network
    participant Devices

    User->>Discovery: discover_devices(timeout=3.0)
    Discovery->>Transport: Open UDP socket
    Discovery->>Transport: Send broadcast (GetService)
    Transport->>Network: Broadcast on 255.255.255.255
    Network->>Devices: Broadcast packet
    Devices-->>Network: StateService responses
    Network-->>Transport: Multiple responses
    Transport-->>Discovery: Parse responses
    Discovery->>Discovery: Collect device info
    Discovery-->>User: List[DiscoveredDevice]
```

## Key Design Decisions

### Async-First

**Why**: LIFX operations involve network I/O which benefits from async

```python
# Multiple devices controlled concurrently
await asyncio.gather(
    light1.set_color(Colors.RED),
    light2.set_color(Colors.BLUE),
    light3.set_color(Colors.GREEN),
)
```

### Lazy Connections

**Why**: Simple lifecycle management with automatic cleanup

```python
# Connection opens lazily on first request
async with await Light.from_ip("192.168.1.100") as light:
    await light.set_color(Colors.RED)  # Opens connection here
    await light.set_brightness(0.5)  # Reuses same connection
    await light.get_label()  # Reuses same connection
# Connection automatically closed on exit
```

### State Caching

**Why**: Reduces network traffic and provides fast access to semi-static device state

```python
# Semi-static properties return cached values:
label = light.label
if label:
    # Use cached label
    print(f"Label: {label}")
else:
    # No cached data yet, fetch from device
    label = await light.get_label()
    print(f"Fetched label: {label}")

# Volatile state (power, color) always requires fresh fetch
# get_color() will cache the label value only
color, power, label = await light.get_color()
print(f"Current state of {light.label} - Power: {power}, Color: {color}")
```

### Code Generation

**Why**: Protocol updates are automatic, reduces errors

```bash
# Regenerate code
uv run python -m lifx.protocol.generator
```

## Performance Characteristics

### Connection Lifecycle

- **Lazy Opening**: Opens on first request, not on creation
- **Explicit Cleanup**: Closes via `close()` or context manager exit
- **Low Overhead**: One UDP socket per device

### State Caching as Properties

- **Format**: Cached values or `None` if not yet fetched
- **Properties**: All device state available as properties
- **Getting Fresh Data**: Use `get_*()` methods to always fetch from device

## Concurrency Model

Each connection serializes requests to prevent response mixing:

```python
conn = DeviceConnection(serial="d073d5123456", ip="192.168.1.100")
# Requests are serialized on the same connection
result1 = await conn.request(packet1)
result2 = await conn.request(packet2)
await conn.close()
```

**How it works**:

- Requests are serialized via `_request_lock` on same connection
- Responses matched to requests by sequence number
- Async generator streaming for efficient multi-response protocols
- Single UDP socket per connection

## Next Steps

- [API Reference](../api/index.md) - Detailed API documentation
- [FAQ](../faq.md) - Frequently asked questions
