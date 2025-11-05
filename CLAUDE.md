# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Project Overview

A modern, type-safe, async Python library for controlling LIFX smart devices over the local network.
Built with Python's built-in `asyncio` for async/await patterns and features auto-generated protocol
structures from a YAML specification.

**Python Versions**: 3.11, 3.12, 3.13, 3.14 (tested on all versions via CI)
**Runtime Dependencies**: Zero - completely dependency-free!
**Async Framework**: Python's built-in `asyncio` (no external async library required)
**Test Isolation**: lifx-emulator runs as subprocess, not a dependency

## Essential Commands

### Development Setup

```bash
# Sync all dependencies (including dev)
uv sync

# Install only the core library (zero dependencies)
uv sync --no-dev
```

### Adding a dependency

```bash
# Add a runtime dependency (use sparingly - library is currently dependency-free!)
uv add some-package

# Add a development dependency
uv add --dev pytest-cov
```

### Testing

```bash
# Run all tests
uv run --frozen pytest

# Run specific test file
uv run pytest tests/test_devices/test_light.py -v

# Run with coverage
uv run pytest --cov=lifx --cov-report=html

# Verbose output
uv run --frozen pytest -v

# Run with emulator integration tests (requires lifx-emulator on PATH)
# Tests marked with @pytest.mark.emulator will be skipped if emulator is not available
uv run pytest
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint with auto-fix
uv run ruff check . --fix

# Type check (strict Pyright validation)
uv run pyright
```

### Protocol Update

```bash
# Source: https://github.com/LIFX/public-protocol/blob/main/protocol.yml
# Regenerate Python protocol code
uv run python -m lifx.protocol.generator
```

### Products Registry Update

```bash
# Source: https://github.com/LIFX/products/blob/master/products.json
# Regenerate Python product registry
uv run python -m lifx.products.generator
```

### Documentation

```bash
# Serve documentation locally with hot reload
uv run mkdocs serve

# Build static documentation
uv run mkdocs build

# Deploy to GitHub Pages
uv run mkdocs gh-deploy
```

## Architecture

### Layered Architecture (Bottom-Up)

1. **Protocol Layer** (`src/lifx/protocol/`)

   - Auto-generated from `protocol.yml` using `generator.py`
   - `protocol_types.py`: Enums and field structures (HSBK, TileDevice, etc.)
   - `packets.py`: Packet classes with PKT_TYPE constants
   - `header.py`: LIFX protocol header (36 bytes)
   - `serializer.py`: Binary serialization/deserialization
   - `models.py`: Protocol data models (`Serial` dataclass, HEV types)
   - `base.py`: Base classes for protocol structures
   - **Focus on lighting**: Button and Relay items are automatically filtered during generation (not
     relevant for light control)
   - **Never edit generated files manually** - download updated `protocol.yml` from LIFX official
     repo instead

2. **Network Layer** (`src/lifx/network/`)

   - `transport.py`: UDP transport using asyncio
   - `discovery.py`: Device discovery via broadcast with `DiscoveredDevice` dataclass
   - `connection.py`: Device connection with retry logic and connection pooling
   - `message.py`: Message building and parsing with `MessageBuilder`
   - Connection pooling with LRU cache and metrics tracking (`ConnectionPoolMetrics`)

3. **Device Layer** (`src/lifx/devices/`)

   - `base.py`: Base `Device` class with common operations: `from_ip()`, label, power, version, info
   - `light.py`: `Light` class (color control, effects: pulse, breathe, waveforms)
   - `hev.py`: `HevLight` class (Light with HEV anti-bacterial cleaning cycle control)
   - `infrared.py`: `InfraredLight` class (Light with infrared LED control for night vision)
   - `multizone.py`: `MultiZoneLight` for strips/beams (zone-based color control)
   - `tile.py`: `TileDevice` for tile grids (2D pixel control)
   - State caching with configurable TTL to reduce network traffic

4. **High-Level API** (`src/lifx/api.py`)

   - `discover()`: Simplified discovery returning `DeviceGroup` with context manager
   - `find_lights()`: Find Light devices with optional label filtering
   - `find_by_serial()`: Find specific device by serial number
   - `DeviceGroup`: Batch operations (set_power, set_color, etc.)
   - `DiscoveryContext`: Async context manager for device discovery
   - `LocationGrouping` / `GroupGrouping`: Organizational structures for location/group-based grouping

5. **Utilities**

   - `color.py`: `HSBK` class with RGB conversion, `Colors` presets
   - `const.py`: Critical constants (network settings, UUIDs, official URLs)
   - `exceptions.py`: Exception hierarchy (see Exception Hierarchy section below)
   - `products/`: Product registry module
     - `products/__init__.py`: Public API exports
     - `products/registry.py`: Auto-generated product database (from products.json)
     - `products/generator.py`: Generator to download and parse products.json

### Device Capabilities Matrix

Different LIFX device types support different features:

| Device Type | Color | Multizone | Tiles | Infrared | HEV | Variable Temperature |
|-------------|-------|-----------|-------|----------|-----|----------------------|
| Device      | ❌    | ❌        | ❌    | ❌       | ❌  | ❌                   |
| Light       | ✅    | ❌        | ❌    | ❌       | ❌  | ✅                   |
| InfraredLight | ✅  | ❌        | ❌    | ✅       | ❌  | ✅                   |
| HevLight    | ✅    | ❌        | ❌    | ❌       | ✅  | ✅                   |
| MultiZoneLight | ✅ | ✅        | ❌    | ❌       | ❌  | ✅                   |
| TileDevice  | ✅    | ❌        | ✅    | ❌       | ❌  | ✅                   |

**Device Detection**: The `products` registry automatically detects device capabilities based on
product ID and instantiates the appropriate device class.

### Exception Hierarchy

All exceptions inherit from `LifxError` (src/lifx/exceptions.py):

```
LifxError (base exception)
├── LifxDeviceNotFoundError     # Device cannot be found or reached
├── LifxTimeoutError             # Operation timed out
├── LifxProtocolError            # Protocol parsing/validation error
├── LifxConnectionError          # Connection error
├── LifxNetworkError             # Network-level error
└── LifxUnsupportedCommandError  # Device doesn't support the command (StateUnhandled response)
```

**Usage**:
```python
from lifx.exceptions import LifxTimeoutError, LifxDeviceNotFoundError

try:
    await light.set_color(color)
except LifxTimeoutError:
    print("Device did not respond in time")
except LifxDeviceNotFoundError:
    print("Device is offline or unreachable")
```

### Key Design Patterns

- **Async Context Managers**: All devices and connections use `async with` for automatic cleanup
- **Type Safety**: Full type hints with strict Pyright validation
- **Auto-Generation**: Protocol structures generated from YAML specification
- **State Storage**: Device state stored with TTL to minimize network requests
- **Connection Pooling**: LRU cache for connection reuse across operations
- **Background Response Dispatcher**: Concurrent request handling via asyncio tasks

## Common Patterns

### Device Serial Number Handling

Devices accept serial numbers as 12-digit hex strings:

- Preferred format: `'d073d5123456'` (12 hex digits, no separators)
- Also accepts (for compatibility): `'d0:73:d5:12:34:56'` (hex with colons)

**Important**: The LIFX serial number is often the same as the device's MAC address, but can differ
(particularly the least significant byte may be off by one).

Serial handling (`src/lifx/protocol/models.py`):

The `Serial` dataclass provides a type-safe way to work with LIFX serial numbers:

```python
from lifx.protocol.models import Serial

# Create from string (accepts hex with or without separators)
serial = Serial.from_string("d073d5123456")
serial = Serial.from_string("d0:73:d5:12:34:56")  # Also works

# Convert between formats
protocol_bytes = serial.to_protocol()  # 8 bytes with padding
serial_string = serial.to_string()     # "d073d5123456"
serial_bytes = serial.value            # 6 bytes

# Create from protocol format (8 bytes)
serial = Serial.from_protocol(protocol_bytes)
```

### Color Representation

The `HSBK` class (in `color.py`) provides user-friendly color handling:

- Hue: 0-360 degrees (float)
- Saturation: 0.0-1.0 (float)
- Brightness: 0.0-1.0 (float)
- Kelvin: 1500-9000 (int)

Conversion methods:

- `HSBK.from_rgb(r, g, b, kelvin)`: Create from RGB (0-255)
- `hsbk.to_rgb()`: Convert to RGB tuple
- Protocol uses uint16 (0-65535) internally

### HEV Light Control (Anti-Bacterial Cleaning)

HevLight devices support HEV (High Energy Visible) cleaning cycles:

```python
from lifx.devices import HevLight

async with await HevLight.from_ip("192.168.1.100") as light:
    # Start a 2-hour cleaning cycle
    await light.set_hev_cycle(enable=True, duration_seconds=7200)

    # Check cycle status
    state = await light.get_hev_cycle()
    if state.is_running:
        print(f"Cleaning: {state.remaining_s}s remaining")

    # Configure default settings
    await light.set_hev_config(indication=True, duration_seconds=7200)
```

### Infrared Light Control (Night Vision)

InfraredLight devices support infrared LED control:

```python
from lifx.devices import InfraredLight

async with await InfraredLight.from_ip("192.168.1.100") as light:
    # Set infrared brightness to 50%
    await light.set_infrared(0.5)

    # Get current infrared brightness
    brightness = await light.get_infrared()
    print(f"IR brightness: {brightness * 100}%")
```

### Packet Flow

1. Create packet instance (e.g., `LightSetColor`)
2. Send via `DeviceConnection.request()`
3. Response is automatically unpacked

### Concurrency Considerations

**Device Connection Concurrency (Implemented):**

Each `DeviceConnection` supports **true concurrent requests** using a background response
dispatcher:

- Background receiver task runs continuously while connection is open
- Responses are routed to waiting coroutines by sequence number
- Multiple concurrent requests on the same connection are fully supported
- Backward compatible with existing sequential code

**Concurrent request patterns:**

1. **Concurrent requests on a single connection** (optimal):

   ```python
   async with DeviceConnection(serial, ip) as conn:
       # Multiple requests execute concurrently
       result1, result2, result3 = await asyncio.gather(
           conn.request_response(packet1, type1),
           conn.request_response(packet2, type2),
           conn.request_response(packet3, type3),
       )
   ```

2. **Sequential operations on a single connection** (still works):

   ```python
   async with DeviceConnection(serial, ip) as conn:
       # These execute sequentially (no gather)
       await conn.request_response(packet1, type1)
       await conn.request_response(packet2, type2)
   ```

3. **Concurrent operations on different devices** (fully parallel):

   ```python
   # Different devices = different connections = maximum parallelism
   async with DeviceConnection(serial1, ip1) as conn1, DeviceConnection(
       serial2, ip2
   ) as conn2:
       result1, result2 = await asyncio.gather(
           conn1.request_response(...), conn2.request_response(...)
       )
   ```

**How it works:**

- Each connection has one UDP socket with a unique local port
- Background task (`_response_receiver()`) continuously receives UDP packets
- Incoming packets are matched to pending requests by sequence number
- Each request waits on an `asyncio.Event` that's signaled when response arrives
- Sequence number ensures correct response routing even with concurrent requests

**Performance characteristics:**

- Multiple concurrent requests on a single connection execute with maximum parallelism
- Concurrent requests to different devices benefit from full parallelism
- No additional UDP sockets needed for concurrency
- Minimal memory overhead (~100 bytes per pending request)

**Rate Limiting:**

The library **intentionally does not implement rate limiting** to keep the core library simple and
flexible. According to the LIFX protocol specification, devices can handle approximately 20 messages
per second. Application developers should implement their own rate limiting if needed, especially when:
- Sending many concurrent requests to a single device
- Broadcasting commands to many devices
- Implementing high-frequency polling or monitoring

Example rate limiting pattern:
```python
import asyncio

async def rate_limited_requests(requests, rate_limit=20):
    """Send requests with rate limiting."""
    delay = 1.0 / rate_limit  # e.g., 50ms for 20/sec
    for request in requests:
        await request()
        await asyncio.sleep(delay)
```

**Discovery DoS Protection:**

The `discover_devices()` function implements DoS protection through:
- **Source ID validation** - Rejects responses with mismatched source IDs
- **Serial validation** - Rejects invalid/broadcast serial numbers
- **Overall timeout** - Discovery stops after timeout seconds (default: 5.0)
- **Idle timeout** - Discovery stops when no responses received for 2 seconds

## Testing Strategy

- **561 tests total** (comprehensive coverage across all layers)
- **Protocol Layer**: 136 tests (serialization, header, packets, generator validation)
- **Network Layer**: 76 tests (transport, discovery, connection, message, concurrent requests)
- **Device Layer**: 145 tests (base, light, hev, infrared, multizone, tile)
- **API Layer**: 88 tests (discovery, context management, batch operations, organization, error handling)
- **Utilities**: 74 tests (color conversion, product registry, RGB roundtrip)

Test files mirror source structure: `tests/test_devices/test_light.py` tests
`src/lifx/devices/light.py`

### Integration Tests with lifx-emulator

Some tests require the `lifx-emulator` to run integration tests against real protocol implementations.
The emulator runs as a **separate subprocess** and is **not** a dependency of lifx.

**Setup Options**:

1. **Development setup** (recommended): Clone lifx-emulator as a sibling directory
   ```bash
   cd ..
   git clone https://github.com/Djelibeybi/lifx-emulator.git
   cd lifx-emulator
   uv sync
   cd ../lifx
   ```

2. **System install**: Install lifx-emulator globally (requires Python 3.13+)
   ```bash
   uv tool install lifx-emulator
   ```

**Running Integration Tests**:
- If emulator is not available, these tests are automatically skipped
- No code changes needed - pytest plugin handles everything
- **Works on all Python versions (3.11+)** since emulator runs as separate process

**Note**: The emulator itself requires Python 3.13+, but it runs as a subprocess so your
lifx tests can run on any supported Python version (3.11-3.14).

**External Emulator Management**:

For cases where you want to manage the emulator separately (or test against actual hardware), you can skip the automatic emulator subprocess startup:

```bash
# Use an externally managed emulator instance
LIFX_EMULATOR_EXTERNAL=1 LIFX_EMULATOR_PORT=56700 pytest

# Test against actual LIFX hardware on the default port
LIFX_EMULATOR_EXTERNAL=1 pytest
```

This is useful when:
- Testing against actual LIFX hardware on your network
- Running the emulator with custom configuration or device setup
- Using a shared emulator instance across multiple test runs
- Debugging emulator behavior separately from the test suite

**Key Test Files:**
```
tests/
├── test_protocol/
│   ├── test_header.py           # Protocol header tests
│   ├── test_serializer.py       # Binary serialization tests
│   ├── test_generated.py        # Generated packet tests
│   └── test_generator.py        # Generator validation tests
├── test_network/
│   ├── test_transport.py        # UDP transport tests
│   ├── test_discovery.py        # Device discovery tests
│   ├── test_connection.py       # Connection management tests
│   ├── test_message.py          # Message building/parsing tests
│   └── test_concurrent_requests.py  # Concurrent request tests
├── test_devices/
│   ├── test_base.py             # Base device tests
│   ├── test_light.py            # Light device tests
│   ├── test_hev.py              # HEV light tests
│   ├── test_infrared.py         # Infrared light tests
│   ├── test_multizone.py        # MultiZone light tests
│   └── test_tile.py             # Tile device tests
├── test_api/
│   ├── test_api_discovery.py    # High-level discovery tests
│   ├── test_api_context.py      # Context manager tests
│   ├── test_api_batch_operations.py  # Batch operation tests
│   ├── test_api_batch_errors.py      # Error handling tests
│   └── test_api_organization.py      # Location/group organization tests
├── test_color.py                # Color utilities tests
├── test_products.py             # Product registry tests
└── test_utils.py                # General utility tests
```

## Protocol Specification

The `protocol.yml` file is the **source of truth** from the official LIFX repository:

- **Source**: https://github.com/LIFX/public-protocol/blob/main/protocol.yml
- **DO NOT modify locally** - download updates from the official repository
- **NOT stored in repo** - downloaded on-demand by generator and parsed in-memory
- Defines: types, enums, fields, compound_fields, and packets with pkt_type/category
- Local quirks are allowed in generator.py to make the result more Pythonic

The file structure:

- **types**: Basic types (uint8, uint16, etc.)
- **enums**: Protocol enums (LightWaveform, Service, etc.)
- **fields**: Reusable field structures (HSBK, Rect)
- **compound_fields**: Complex nested structures (TileDevice)
- **packets**: Message definitions with pkt_type and category

Local generator quirks:

- **field name quirks**: Rename fields to avoid Python built-ins and improve readability:
  - `type` -> `effect_type` (type is a Python built-in; effect_type is more semantic for effect fields)
  - Field mappings preserve protocol names: `MultiZoneEffectSettings.effect_type` maps to protocol field `Type`
- **underscores**: Remove underscore from category names but maintain camel case so multi_zone
  becomes MultiZone
- **filtering**: Automatically skips Button and Relay items during generation:
  - Enums starting with "Button" or "Relay" are excluded
  - Fields starting with "Button" or "Relay" are excluded
  - Unions starting with "Button" or "Relay" are excluded
  - All packets in "button" and "relay" categories are excluded
  - This keeps the library focused on LIFX lighting devices

Run `uv run python -m lifx.protocol.generator` to regenerate Python code.

## Products Registry

The products registry provides device capability detection and automatic device class selection:

- **Source**: https://github.com/LIFX/products/blob/master/products.json
- **Auto-generated**: `src/lifx/products/registry.py` is generated from products.json
- **Update command**: `uv run python -m lifx.products.generator`
- **Usage**: Import from `lifx.products` module

**Key Functions:**
```python
from lifx.products import get_product, get_device_class_name

# Get product info by product ID
product_info = get_product(product_id=27)  # Returns ProductInfo

# Get appropriate device class name
class_name = get_device_class_name(product_id=27)  # Returns "Light", "MultiZoneLight", etc.
```

**Automatic Device Type Detection:**

The discovery system uses the products registry to automatically instantiate the correct device class:

```python
# Discovery automatically creates HevLight, InfraredLight, MultiZoneLight, etc.
async with discover() as group:
    for device in group:
        # Each device is the correct type based on its product ID
        print(f"{device.label}: {type(device).__name__}")
```

## Constants Module

Critical constants are defined in `src/lifx/const.py`:

**Network Constants:**
- `LIFX_UDP_PORT`: LIFX UDP port (56700)
- `MAX_PACKET_SIZE`: Maximum packet size (1024 bytes) to prevent DoS
- `MIN_PACKET_SIZE`: Minimum packet size (36 bytes = header)
- `LIFX_VENDOR_PREFIX`: LIFX vendor serial prefix (d0:73:d5) for device fingerprinting
- `MAX_RESPONSE_TIME`: Maximum response time for local network devices (0.5s)
- `IDLE_TIMEOUT_MULTIPLIER`: Idle timeout after last response (4.0)

**UUID Namespaces:**
- `LIFX_LOCATION_NAMESPACE`: UUID namespace for generating location UUIDs
- `LIFX_GROUP_NAMESPACE`: UUID namespace for generating group UUIDs

**Official Repository URLs:**
- `PROTOCOL_URL`: Official LIFX protocol.yml URL
- `PRODUCTS_URL`: Official LIFX products.json URL

## Known Limitations

- Button/Relay/Switch devices are explicitly out of scope (library focuses on lighting devices)
- Not yet published to PyPI
