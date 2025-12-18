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
**Test Isolation**: lifx-emulator-core runs embedded in-process for fast, cross-platform testing

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
   - `protocol_types.py`: Enums and field structures (HSBK, TileStateDevice, etc.)
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
   - `connection.py`: Device connection with retry logic and lazy opening
   - `message.py`: Message building and parsing with `MessageBuilder`
   - `mdns/`: mDNS/DNS-SD discovery module (zero-dependency, stdlib only)
     - `discovery.py`: `discover_lifx_services()` and `discover_devices_mdns()`
     - `dns.py`: DNS wire format parser for PTR, SRV, A, TXT records
     - `transport.py`: `MdnsTransport` class for multicast UDP
     - `types.py`: `LifxServiceRecord` dataclass
   - Lazy connection opening (auto-opens on first request)

3. **Device Layer** (`src/lifx/devices/`)

   - `base.py`: Base `Device` class with common operations: `from_ip()`, label, power, version, info
   - `light.py`: `Light` class (color control, effects: pulse, breathe, waveforms)
   - `hev.py`: `HevLight` class (Light with HEV anti-bacterial cleaning cycle control)
   - `infrared.py`: `InfraredLight` class (Light with infrared LED control for night vision)
   - `multizone.py`: `MultiZoneLight` for strips/beams (zone-based color control)
   - `matrix.py`: `MatrixLight` for matrix devices (2D pixel control: tiles, candle, path)
   - State caching with configurable TTL to reduce network traffic

4. **High-Level API** (`src/lifx/api.py`)

   - `discover()`: Async generator yielding devices via UDP broadcast
   - `discover_mdns()`: Async generator yielding devices via mDNS (faster, single query)
   - `find_by_serial()`: Find specific device by serial number
   - `find_by_label()`: Async generator yielding devices matching label (exact or substring)
   - `find_by_ip()`: Find device by IP address using targeted broadcast
   - `DeviceGroup`: Batch operations (set_power, set_color, etc.)
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

| Device Type | Color | Multizone | Matrix | Infrared | HEV | Variable Temperature |
|-------------|-------|-----------|--------|----------|-----|----------------------|
| Device      | ❌    | ❌        | ❌     | ❌       | ❌  | ❌                   |
| Light       | ✅    | ❌        | ❌     | ❌       | ❌  | ✅                   |
| InfraredLight | ✅  | ❌        | ❌     | ✅       | ❌  | ✅                   |
| HevLight    | ✅    | ❌        | ❌     | ❌       | ✅  | ✅                   |
| MultiZoneLight | ✅ | ✅        | ❌     | ❌       | ❌  | ✅                   |
| MatrixLight | ✅    | ❌        | ✅     | ❌       | ❌  | ✅                   |

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
- **State Caching**: Device properties cache values to reduce network requests
- **Lazy Connections**: Connections open automatically on first request
- **Async Generator Streaming**: Request/response communication via async generators

### State Caching

**Current Behavior**:
- Selected properties cache static/semi-static values to reduce network requests
- Cached properties: `label`, `version`, `host_firmware`, `wifi_firmware`, `location`, `group`, `hev_config`, `hev_result`, `zone_count`, `multizone_effect`, `tile_chain`, `tile_count`, `tile_effect`
- Volatile state (power, color, hev_cycle, zones, tile_colors, ambient_light_level) is **not** cached - always use `get_*()` methods to fetch fresh data
- Use `get_*()` methods to fetch fresh data from devices for any property
- No automatic expiration - application controls when to refresh
- Use `get_color()` to retrieve color, power, and label values as two of the three are volatile and it returns all three in a single request/response pair.

**Example**:
```python
async with device:
    # get_color() is the most efficient way of getting color and power in a single request/response pair
    color, power, label = await device.get_color()

    # Access cached label (semi-static)
    cached_label = device.label  # Returns str | None

    # For volatile state like power/color, always call get_*() methods
    power_level = await device.get_power()  # Returns int (0 or 65535)
    is_on = power_level > 0
```

**Note**: Volatile state properties (`power`, `color`, `hev_cycle`, `zones`, `tile_colors`, `ambient_light_level`) were removed as they change too frequently to benefit from caching. Always fetch these values using `get_*()` methods.

## Common Patterns

### Targeted Device Discovery

The high-level API provides efficient methods to find specific devices without discovering all devices on the network:

#### Find by Label

`find_by_label()` uses a protocol trick by broadcasting `GetLabel` instead of `GetService`, returning all device labels in one pass. This is more efficient than querying each device individually.

```python
from lifx import find_by_label

# Find all devices with "Living" in the label (substring match, default)
async for device in find_by_label("Living"):  # May match "Living Room", "Living Area", etc.
    await device.set_power(True)

# Find device by exact label match (returns at most one device)
async for device in find_by_label("Living Room", exact_match=True):
    await device.set_power(True)
    break  # exact_match returns at most one device
```

**Parameters:**
- `label`: Device label to search for (case-insensitive)
- `exact_match`: If `True`, match label exactly and yield at most one device; if `False` (default), match substring and yield all matching devices
- Returns: `AsyncGenerator[Device, None]`

#### Find by IP Address

`find_by_ip()` uses a protocol trick by sending `GetService` directly to a specific IP address instead of broadcasting, making it faster and more targeted.

```python
from lifx import find_by_ip

# Find device at specific IP address
device = await find_by_ip("192.168.1.100")
if device:
    async with device:
        await device.set_power(True)
```

**Parameters:**
- `ip`: IP address to search
- Returns: `Device | None`

#### Find by Serial Number

`find_by_serial()` discovers devices and filters by serial number.

```python
from lifx import find_by_serial

# Find device by serial (accepts with or without colons)
device = await find_by_serial("d073d5123456")
# or
device = await find_by_serial("d0:73:d5:12:34:56")

if device:
    async with device:
        await device.set_power(True)
```

**Parameters:**
- `serial`: 12-digit hex serial number (with or without colons, case-insensitive)
- Returns: `Device | None`

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

### MAC Address Calculation

The `mac_address` property on `Device` provides the device's MAC address, calculated from the serial
number and host firmware version. The calculation is automatically performed when `get_host_firmware()`
is called or when using the device as a context manager.

**Calculation Logic** (based on host firmware major version):
- **Version 2 or 4**: MAC address matches the serial
- **Version 3**: MAC address is serial with LSB + 1 (with wraparound from 0xFF to 0x00)
- **Unknown versions**: Defaults to serial

**Format**: MAC address is returned in colon-separated lowercase hex format (e.g., `d0:73:d5:01:02:03`)
to visually distinguish it from the serial number format.

```python
from lifx.devices import Device

async with await Device.from_ip("192.168.1.100") as device:
    # MAC address is automatically calculated during device setup
    if device.mac_address:
        print(f"MAC: {device.mac_address}")  # e.g., "d0:73:d5:01:02:04"

    # Returns None before host_firmware is fetched
    assert device.mac_address is not None
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

### Ambient Light Sensor (Light Level Detection)

Light devices with ambient light sensors can measure the current ambient light level in lux:

```python
from lifx.devices import Light

async with await Light.from_ip("192.168.1.100") as light:
    # Turn light off for accurate reading
    await light.set_power(False)

    # Get ambient light level in lux
    lux = await light.get_ambient_light_level()
    if lux > 0:
        print(f"Ambient light: {lux} lux")
    else:
        print("No ambient light sensor or completely dark")
```

**Notes:**
- This is a volatile property and is never cached - always fetched fresh from the device
- Devices without ambient light sensors return 0.0 (not an error)
- For accurate readings, the light should be off - otherwise the light's own illumination interferes with the sensor
- A reading of 0.0 could mean either no sensor or complete darkness

### MultiZone Light Control (Strips and Beams)

MultiZoneLight devices support zone-based color control:

```python
from lifx.devices import MultiZoneLight
from lifx.color import HSBK

async with await MultiZoneLight.from_ip("192.168.1.100") as light:
    # Get all zone colors using the convenience method
    # Automatically uses the best method based on device capabilities
    colors = await light.get_all_color_zones()
    print(f"Device has {len(colors)} zones")

    # Get specific zone range using extended method (requires extended capability)
    first_ten = await light.get_extended_color_zones(start=0, end=9)

    # Get specific zone range using standard method
    first_ten = await light.get_color_zones(start=0, end=9)

    # Set all zones to red
    zone_count = await light.get_zone_count()
    await light.set_color_zones(0, zone_count - 1, HSBK.from_rgb(255, 0, 0))
```

**Note on methods:**
- `get_all_color_zones()`: Convenience method with no parameters that automatically uses the best method (extended or standard) based on device capabilities
- `get_extended_color_zones(start, end)`: Direct access to extended multizone protocol (requires extended capability)
- `get_color_zones(start, end)`: Direct access to standard multizone protocol (works on all multizone devices)

**Fire-and-forget mode for animations:**

For high-frequency animations (>20 updates/second), use the `fast=True` parameter to skip waiting for device acknowledgement:

```python
# Standard mode (waits for response)
await light.set_extended_color_zones(0, colors)

# Fast mode for animations (fire-and-forget, no response waiting)
for frame in animation_frames:
    await light.set_extended_color_zones(0, frame, fast=True)
    await asyncio.sleep(0.033)  # ~30 FPS
```

**Note:** `MatrixLight.set64()` is already fire-and-forget by default.

### Packet Flow

1. Create packet instance (e.g., `LightSetColor`)
2. Send via `DeviceConnection.request()`
3. Response is automatically unpacked

### Concurrency Considerations

**Request/Response Pattern:**

The library uses async generators for all request/response communication:

**Single Response (Most Common):**
```python
# Get single response with convenience wrapper
label_state = await device.connection.request(GetLabel())

# Or explicitly with generator
async for state in device.connection.request_stream(GetLabel()):
    process(state)
    break  # Exit after first response
```

**Multiple Responses:**
```python
# Stream responses until timeout
async for zone_state in device.connection.request_stream(
    GetExtendedColorZones(), timeout=2.0
):
    colors.extend(zone_state.colors)
    if len(colors) >= expected:
        break  # Early exit when done
```

**Benefits:**
- Immediate exit for single-response requests (no wasted timeout)
- Natural streaming for multi-response protocols
- Memory efficient (no buffering all responses)
- Consistent with discovery pattern

**Concurrent request patterns:**

1. **Sequential operations on a single connection** (default):

   ```python
   async with DeviceConnection(serial, ip) as conn:
       # Requests are serialized via _request_lock to prevent response mixing
       await conn.request(packet1)
       await conn.request(packet2)
   ```

2. **Concurrent operations on different devices** (fully parallel):

   ```python
   # Different devices = different connections = maximum parallelism
   async with asyncio.TaskGroup() as tg:
       tg.create_task(device1.set_power(True))
       tg.create_task(device2.set_power(True))
   ```

**How it works:**

- Each connection has one UDP socket with a unique local port
- Requests are serialized via `_request_lock` to prevent response mixing on the same connection
- Each request uses `request_stream()` async generator to yield responses as they arrive
- Single-response requests break immediately after first response
- Multi-response requests stream until timeout or early exit condition

**Request Serialization:**

The library uses an asyncio.Lock (`_request_lock`) to serialize requests on the same connection:

1. **Why serialization?** Without a background receiver task, concurrent requests on the same UDP socket could receive each other's responses. The lock ensures only one request is active per connection.

2. **How it works:**
   ```python
   async with self._request_lock:
       # Send request
       await self.send_packet(request)
       # Receive and yield responses
       async for header, payload in self._receive_responses(timeout):
           yield header, payload
   ```

3. **Concurrent device operations:** Different devices have different connections with their own locks, so operations on multiple devices execute in parallel.

**Sequence Number Allocation:**

The library uses atomic sequence number allocation for robust request handling:

- Each request atomically allocates a unique sequence number (0-255)
- The sequence counter wraps around at 256 (uint8 protocol limit)
- Ensures response correlation with the request

```python
# In MessageBuilder
def next_sequence(self) -> int:
    """Atomically allocate and return the next sequence number."""
    seq = self._sequence
    self._sequence = (self._sequence + 1) % 256
    return seq
```

**Performance characteristics:**

- Single-response requests exit immediately (no wasted timeout)
- Multi-response requests stream efficiently with early exit
- Concurrent requests to different devices benefit from full parallelism
- Minimal memory overhead (no buffering responses)

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

- **1075+ tests total** (comprehensive coverage across all layers)
- **Protocol Layer**: 136 tests (serialization, header, packets, generator validation)
- **Network Layer**: 149 tests (transport, discovery, connection, message, mDNS, async generator requests)
- **Device Layer**: 157 tests (base, light, hev, infrared, multizone, tile)
- **API Layer**: 60 tests (discovery, batch operations, organization, themes, error handling)
- **Utilities**: 329 tests (color conversion, product registry, RGB roundtrip, effects, themes)

Test files mirror source structure: `tests/test_devices/test_light.py` tests
`src/lifx/devices/light.py`

### Integration Tests with lifx-emulator-core

Some tests require `lifx-emulator-core` to run integration tests against real protocol implementations.
The emulator runs **embedded in-process** as a dev dependency, providing:
- Fast startup (~5-10ms vs 500ms+ for subprocess)
- Cross-platform support (Windows, macOS, Linux)
- Direct access to emulator internals for scenario testing

**Setup**: The emulator is automatically installed as a dev dependency:
```bash
uv sync  # Installs lifx-emulator-core automatically
```

**Running Integration Tests**:
- Tests marked with `@pytest.mark.emulator` use the embedded emulator
- If emulator is not available, these tests are automatically skipped
- **Works on all Python versions (3.11+)**

**External Emulator Management**:

For cases where you want to manage the emulator separately (or test against actual hardware):

```bash
# Use an externally managed emulator instance
LIFX_EMULATOR_EXTERNAL=1 LIFX_EMULATOR_PORT=56700 pytest

# Test against actual LIFX hardware on the default port
LIFX_EMULATOR_EXTERNAL=1 pytest
```

This is useful when:
- Testing against actual LIFX hardware on your network
- Running the emulator with custom configuration or device setup
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
│   ├── test_discovery_devices.py    # Device discovery tests
│   ├── test_discovery_errors.py     # Discovery error handling tests
│   ├── test_connection.py       # Connection management tests
│   ├── test_message.py          # Message building/parsing tests
│   ├── test_concurrent_requests.py  # Concurrent request tests
│   └── test_mdns/               # mDNS discovery tests
│       ├── test_dns.py          # DNS parser tests
│       ├── test_transport.py    # mDNS transport tests
│       └── test_discovery.py    # mDNS discovery tests
├── test_devices/
│   ├── test_base.py             # Base device tests
│   ├── test_light.py            # Light device tests
│   ├── test_hev.py              # HEV light tests
│   ├── test_infrared.py         # Infrared light tests
│   ├── test_multizone.py        # MultiZone light tests
│   └── test_matrix.py           # Matrix light tests
├── test_api/
│   ├── test_api_discovery.py    # High-level discovery tests
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
- **compound_fields**: Complex nested structures (TileStateDevice)
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
- **sensor packets**: Adds undocumented ambient light sensor packets:
  - `SensorGetAmbientLight` (401): Request packet with no parameters
  - `SensorStateAmbientLight` (402): Response packet with lux field (float32)
  - These packets are not in the official protocol.yml but are supported by LIFX devices with ambient light sensors

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

The discovery system uses device capabilities to automatically instantiate the correct device class.
Device type detection is performed by `DiscoveredDevice.create_device()`, which is the single source
of truth for device instantiation across the library.

The detection uses capability-based logic in the following priority order:
1. Matrix capability → `MatrixLight`
2. Multizone capability → `MultiZoneLight`
3. Infrared capability → `InfraredLight`
4. HEV capability → `HevLight`
5. Color capability → `Light`
6. Relay/Button-only devices → `None` (filtered out)

```python
# High-level API - automatically creates appropriate device types
async for device in discover():
    # Each device is the correct type based on its capabilities
    print(f"{device.label}: {type(device).__name__}")

# Low-level API - manual device type detection
from lifx.network.discovery import discover_devices

async for disc in discover_devices():
    device = await disc.create_device()  # Returns appropriate device class or None
    if device:
        print(f"Created {type(device).__name__}")
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

**mDNS Constants:**
- `MDNS_ADDRESS`: Multicast address for mDNS (224.0.0.251)
- `MDNS_PORT`: mDNS port (5353)
- `LIFX_MDNS_SERVICE`: LIFX service type (_lifx._udp.local)

**UUID Namespaces:**
- `LIFX_LOCATION_NAMESPACE`: UUID namespace for generating location UUIDs
- `LIFX_GROUP_NAMESPACE`: UUID namespace for generating group UUIDs

**Official Repository URLs:**
- `PROTOCOL_URL`: Official LIFX protocol.yml URL
- `PRODUCTS_URL`: Official LIFX products.json URL

## Known Limitations

- Button/Relay/Switch devices are explicitly out of scope (library focuses on lighting devices)
- Not yet published to PyPI
- Never update docs/changelog.md manually as it is auto-generated during the release process by the CI/CD workflow.
- If a field is user-visible, it must never be bytes. This means things like serial, label, location and group must always be converted to a string prior to storing it anywhere a user would be able to access it. Conversion to and from bytes should happen either as close to sending or receiving the packet as possible.
