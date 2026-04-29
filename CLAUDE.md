# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Project Overview

A modern, type-safe, async Python library for controlling LIFX smart devices over the local network.
Built with Python's built-in `asyncio` for async/await patterns and features auto-generated protocol
structures from a YAML specification. Published on PyPI as `lifx-async` (`pip install lifx-async`).

**Python Versions**: 3.10, 3.11, 3.12, 3.13, 3.14 (tested on all versions via CI)
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
uv run zensical serve

# Build static documentation
uv run zensical build
uv run llmstxt-standalone build

# Deploy to GitHub Pages via the Documentation workflow
gh workflow run docs.yml
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
   - `ceiling.py`: `CeilingLight` class (extends `MatrixLight` with independent uplight/downlight component control for LIFX Ceiling products)
   - State caching with configurable TTL to reduce network traffic

4. **High-Level API** (`src/lifx/api.py`)

   - `discover()`: Async generator yielding devices via UDP broadcast
   - `discover_mdns()`: Async generator yielding devices via mDNS (faster, single query)
   - `find_by_serial()`: Find specific device by serial number
   - `find_by_label()`: Async generator yielding devices matching label (exact or substring)
   - `find_by_ip()`: Find device by IP address using targeted broadcast
   - `DeviceGroup`: Batch operations (set_power, set_color, etc.)
   - `LocationGrouping` / `GroupGrouping`: Organizational structures for location/group-based grouping

5. **Animation Layer** (`src/lifx/animation/`)

   - `animator.py`: High-level `Animator` class with direct UDP sending
   - `framebuffer.py`: Multi-tile canvas mapping and orientation correction
   - `packets.py`: Prebaked packet templates (`MatrixPacketGenerator`, `MultiZonePacketGenerator`)
   - `orientation.py`: Tile orientation remapping with LRU-cached lookup tables
   - Optimized for high-frequency frame delivery (30+ FPS) for real-time effects
   - Uses protocol-ready uint16 HSBK values (no conversion overhead)
   - Multi-tile canvas support using `user_x`/`user_y` tile positions

6. **Effects Layer** (`src/lifx/effects/`)

   - 30+ built-in effects (aurora, flame, plasma, rainbow, twinkle, etc.)
   - `base.py`: Base effect class with frame generation interface
   - `registry.py`: Effect registry for discovering available effects by name
   - `state_manager.py`: Effect state management for running effects on devices
   - `models.py`: Shared effect models and configuration types
   - Effects generate HSBK frames consumed by the Animation Layer

7. **Theme Layer** (`src/lifx/theme/`)

   - `theme.py`: Theme definitions (named color palettes)
   - `library.py`: Built-in theme library
   - `generators.py`: Theme-based color generators for effects
   - `canvas.py`: Canvas abstraction for applying themes to device layouts

8. **Utilities**

   - `color.py`: `HSBK` class with RGB conversion, `Colors` presets
   - `const.py`: Critical constants (network settings, UUIDs, official URLs)
   - `exceptions.py`: Exception hierarchy (see Exception Hierarchy section below)
   - `products/`: Product registry module
     - `products/__init__.py`: Public API exports
     - `products/registry.py`: Auto-generated product database (from products.json)
     - `products/generator.py`: Generator to download and parse products.json

### Device Capabilities Matrix

Different LIFX device types support different features:

| Device Type | Color | Multizone | Matrix | Infrared | HEV | Variable Temperature | Ceiling Components |
|-------------|-------|-----------|--------|----------|-----|----------------------|--------------------|
| Device      | ❌    | ❌        | ❌     | ❌       | ❌  | ❌                   | ❌                 |
| Light       | ✅    | ❌        | ❌     | ❌       | ❌  | ✅                   | ❌                 |
| InfraredLight | ✅  | ❌        | ❌     | ✅       | ❌  | ✅                   | ❌                 |
| HevLight    | ✅    | ❌        | ❌     | ❌       | ✅  | ✅                   | ❌                 |
| MultiZoneLight | ✅ | ✅        | ❌     | ❌       | ❌  | ✅                   | ❌                 |
| MatrixLight | ✅    | ❌        | ✅     | ❌       | ❌  | ✅                   | ❌                 |
| CeilingLight | ✅   | ❌        | ✅     | ❌       | ❌  | ✅                   | ✅                 |

**Device Detection**: The `products` registry automatically detects device capabilities based on
product ID and instantiates the appropriate device class.

### Exception Hierarchy

All exceptions inherit from `LifxError` (`src/lifx/exceptions.py`): `LifxDeviceNotFoundError`, `LifxTimeoutError`, `LifxProtocolError`, `LifxConnectionError`, `LifxNetworkError`, `LifxUnsupportedCommandError`.

### Key Design Patterns

- **Async Context Managers**: All devices and connections use `async with` for automatic cleanup
- **Type Safety**: Full type hints with strict Pyright validation
- **Auto-Generation**: Protocol structures generated from YAML specification
- **State Caching**: Device properties cache values to reduce network requests
- **Lazy Connections**: Connections open automatically on first request
- **Async Generator Streaming**: Request/response communication via async generators

### State Caching

- Cached (semi-static): `label`, `version`, `host_firmware`, `wifi_firmware`, `location`, `group`, `hev_config`, `hev_result`, `zone_count`, `multizone_effect`, `tile_chain`, `tile_count`, `tile_effect`
- **Never cached** (volatile): `power`, `color`, `hev_cycle`, `zones`, `tile_colors`, `ambient_light_level` — always use `get_*()` methods
- `get_color()` returns `(color, power, label)` in a single request/response pair — most efficient way to get color + power
- No automatic expiration — application controls when to refresh

## Common Patterns

> **Full API docs, usage examples, and device-specific guides are available at
> https://djelibeybi.github.io/lifx-async/ and via context7 (`/djelibeybi/lifx-async`, 549 snippets).**
> The following covers only non-obvious gotchas not in the docs.

### Key Gotchas

- **Serial vs MAC**: Serial number often matches MAC address but can differ (LSB may be off by one depending on firmware version). MAC calculation logic is in `devices/base.py`.
- **HSBK dual formats**: User-facing `HSBK` uses float (hue 0-360, sat/bright 0.0-1.0, kelvin 1500-9000). Protocol/animation layer uses raw uint16 (0-65535 for H/S/B). Don't mix them.
- **`get_color()` returns a triple**: `(color, power, label)` — most efficient single-request way to get color + power state
- **Ambient light sensor**: Returns 0.0 for both "no sensor" and "complete darkness". Light must be off for accurate readings.
- **High-frequency updates**: Use the Animation Layer (`src/lifx/animation/`) for performance-critical frame delivery rather than calling device methods directly.
- **Packet flow**: Create packet → `DeviceConnection.request()` → response auto-unpacked

### Concurrency Considerations

- Requests on a single connection are serialized via `_request_lock` (asyncio.Lock) to prevent response mixing on the same UDP socket
- Different devices have different connections, so operations on multiple devices execute in parallel via `asyncio.TaskGroup`
- Request/response uses async generators: single-response requests break after first response, multi-response requests stream until timeout or early exit
- Sequence numbers (0-255, uint8) are atomically allocated per request for response correlation
- **No rate limiting** built in — devices handle ~20 msg/sec; application developers should implement their own if needed

**Discovery DoS Protection:**

The `discover_devices()` function implements DoS protection through:
- **Source ID validation** - Rejects responses with mismatched source IDs
- **Serial validation** - Rejects invalid/broadcast serial numbers
- **Overall timeout** - Discovery stops after timeout seconds (default: 5.0)
- **Idle timeout** - Discovery stops when no responses received for 2 seconds

## Testing Strategy

- **2425+ tests total** (comprehensive coverage across all layers)
- **Protocol Layer**: 159 tests (serialization, header, packets, generator validation)
- **Network Layer**: 183 tests (transport, discovery, connection, message, mDNS, async generator requests)
- **Device Layer**: 375 tests (base, light, ceiling, hev, infrared, multizone, matrix, state management, MAC address)
- **API Layer**: 63 tests (discovery, batch operations, organization, themes, error handling)
- **Effects Layer**: 1249 tests (30+ built-in effects, registry, state manager, integration, capability filtering)
- **Theme Layer**: 146 tests (themes, canvas, generators, library, apply_theme)
- **Animation Layer**: 123 tests (animator, framebuffer, packets, orientation)
- **Utilities**: 127 tests (color conversion, product registry, RGB roundtrip)

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
- **Works on all supported Python versions (3.10+)**

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

**Key Test Directories:**

Test files mirror source structure: `tests/test_devices/test_light.py` tests `src/lifx/devices/light.py`

```
tests/
├── test_protocol/          # Protocol header, serializer, generated packets, generator
├── test_network/           # Transport, discovery, connection, message, concurrent requests
│   └── test_mdns/          # mDNS DNS parser, transport, discovery
├── test_devices/           # Base, light, ceiling, hev, infrared, multizone, matrix
│   └── test_state_*.py     # State management tests per device type
├── test_api/               # Discovery, batch operations, errors, organization, themes
├── test_effects/           # Individual effect tests + registry, integration, capability filtering
├── test_theme/             # Theme, canvas, generators, library
├── test_animation/         # Animator, framebuffer, packets, orientation
├── test_color.py           # Color utilities and RGB roundtrip
├── test_products/          # Product registry
└── test_utils.py           # General utilities
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

- **Source**: https://github.com/LIFX/products/blob/master/products.json
- **Auto-generated**: `src/lifx/products/registry.py` — update with `uv run python -m lifx.products.generator`
- **Key functions**: `get_product(product_id)` → `ProductInfo`, `get_device_class_name(product_id)` → class name string

**Device Type Detection** (`DiscoveredDevice.create_device()` is the single source of truth):
1. Ceiling product ID → `CeilingLight`
2. Matrix capability → `MatrixLight`
3. Multizone → `MultiZoneLight`
4. Infrared → `InfraredLight`
5. HEV → `HevLight`
6. Color → `Light`
7. Relay/Button-only → `None` (filtered out)

## Known Limitations

- Button/Relay/Switch devices are explicitly out of scope (library focuses on lighting devices)
- Never update docs/changelog.md manually as it is auto-generated during the release process by the CI/CD workflow.
- If a field is user-visible, it must never be bytes. This means things like serial, label, location and group must always be converted to a string prior to storing it anywhere a user would be able to access it. Conversion to and from bytes should happen either as close to sending or receiving the packet as possible.
