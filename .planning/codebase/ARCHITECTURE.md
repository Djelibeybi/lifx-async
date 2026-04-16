# Architecture

**Analysis Date:** 2026-04-16

## Pattern Overview

**Overall:** Layered Architecture with Async-First Design

**Key Characteristics:**
- Seven distinct layers with strict dependency direction (lower layers never import higher layers)
- Zero runtime dependencies - uses only Python stdlib (`asyncio`, `struct`, `socket`, `dataclasses`)
- Async context managers (`async with`) for resource lifecycle management throughout
- Auto-generated protocol and product layers from external YAML/JSON specifications
- Device class hierarchy with capability-based polymorphism
- Dual HSBK value spaces: user-facing floats vs protocol uint16

## Layers

**Layer 1 - Protocol (lowest):**
- Purpose: Binary serialisation/deserialisation of LIFX wire protocol
- Location: `src/lifx/protocol/`
- Contains: Packet dataclasses, header parsing, field type definitions, code generator
- Depends on: Nothing (self-contained)
- Used by: Network layer, Device layer, Animation layer
- Key abstraction: `Packet` base class (`src/lifx/protocol/base.py`) with `PKT_TYPE`, `pack()`, `unpack()` class methods
- Auto-generated files: `packets.py`, `protocol_types.py` (from `protocol.yml` via `generator.py`)

**Layer 2 - Network:**
- Purpose: UDP transport, device discovery, connection management, message framing
- Location: `src/lifx/network/`
- Contains: UDP transport, broadcast/mDNS discovery, per-device connections, message create/parse
- Depends on: Protocol layer
- Used by: Device layer, API layer, Animation layer
- Key abstraction: `DeviceConnection` (`src/lifx/network/connection.py`) - lazy-opening, request-serialised UDP connection with async generator response streaming

**Layer 3 - Products:**
- Purpose: Device capability detection from LIFX product registry
- Location: `src/lifx/products/`
- Contains: Auto-generated product database, capability lookup, device class mapping
- Depends on: Nothing (self-contained data)
- Used by: Device layer (for class instantiation), API layer
- Auto-generated: `registry.py` (from `products.json` via `generator.py`)

**Layer 4 - Devices:**
- Purpose: High-level device abstractions with typed state, caching, and capability-specific methods
- Location: `src/lifx/devices/`
- Contains: Device class hierarchy, state dataclasses, detection logic
- Depends on: Protocol, Network, Products layers
- Used by: API layer, Effects layer, Animation layer
- Key abstraction: `Device[TState]` generic base class (`src/lifx/devices/base.py`) parameterised by state type

**Layer 5 - API (highest application layer):**
- Purpose: Simplified discovery, batch operations, organisational grouping
- Location: `src/lifx/api.py`
- Contains: `discover()`, `find_by_*()` async generators, `DeviceGroup` batch operations, `LocationGrouping`/`GroupGrouping`
- Depends on: Devices, Network, Protocol layers
- Used by: End-user application code

**Layer 6 - Animation (performance path):**
- Purpose: High-frequency frame delivery bypassing connection layer for 30+ FPS
- Location: `src/lifx/animation/`
- Contains: `Animator` with direct UDP socket, `FrameBuffer` for multi-tile canvas mapping, prebaked packet templates
- Depends on: Protocol layer (packet structure), Network utils (source allocation)
- Used by: Effects layer (FrameEffect subclasses)
- Key design: Queries device once via connection layer, then sends frames via raw `socket.sendto()` for zero-overhead delivery

**Layer 7 - Effects & Themes (application extensions):**
- Purpose: Visual effects orchestration and colour palette management
- Location: `src/lifx/effects/`, `src/lifx/theme/`
- Contains: 30+ built-in effects, `Conductor` orchestrator, `EffectRegistry`, theme library
- Depends on: Devices, Animation, Colour utilities
- Used by: End-user application code

## Data Flow

**Device Command Flow (e.g. set_color):**

1. User calls `await light.set_color(HSBK(hue=120, ...))` on `Light` (`src/lifx/devices/light.py`)
2. `Light` converts user-facing HSBK floats to protocol uint16 values
3. Creates protocol packet: `packets.Light.SetColor(color=LightHsbk(...), duration=...)`
4. Passes packet to `DeviceConnection.request()` (`src/lifx/network/connection.py`)
5. `request()` acquires `_request_lock`, calls `create_message()` to build header + payload bytes
6. `UdpTransport.send()` sends bytes via `asyncio.DatagramProtocol`
7. Background receiver task dispatches response to matching pending request queue
8. Response unpacked and returned to caller

**Discovery Flow:**

1. User calls `async for device in discover():` (`src/lifx/api.py`)
2. `discover()` delegates to `discover_devices()` (`src/lifx/network/discovery.py`)
3. Broadcasts `Device.GetService` packet to `255.255.255.255:56700`
4. Collects `StateService` responses → yields `DiscoveredDevice` instances
5. Each `DiscoveredDevice.create_device()` queries product ID → `detection.py` maps to device class
6. Appropriate device subclass instantiated and yielded to caller

**Animation Frame Flow:**

1. User creates `Animator` via factory: `await Animator.for_matrix(device)`
2. Factory queries device for tile chain info (one-time connection use)
3. Creates `FrameBuffer` with tile positions and `MatrixPacketGenerator` with prebaked templates
4. Each frame: user provides HSBK uint16 tuples → `FrameBuffer.apply()` remaps per tile orientation
5. `Animator.send_frame()` patches payload into prebaked templates, sends via raw `socket.sendto()`

**Effect Lifecycle Flow:**

1. User creates `Conductor` and starts effect: `await conductor.start(effect, lights)`
2. `Conductor` captures pre-effect device state via `DeviceStateManager` (`src/lifx/effects/state_manager.py`)
3. Sets `effect.conductor` and `effect.participants`, calls `effect.async_play()`
4. Effect runs until cancelled or completes naturally
5. On stop: `Conductor` restores pre-effect state (if `restore_on_complete` is True)

**State Management:**
- Each `Device` holds a `DeviceConnection` for network I/O
- Semi-static properties (label, version, firmware, location, group) are cached with no automatic expiration
- Volatile properties (power, colour, zones) always fetched fresh via `get_*()` methods
- State refresh controlled by application code, not by timers

## Key Abstractions

**Packet (`src/lifx/protocol/base.py`):**
- Purpose: Typed representation of a LIFX protocol message
- Examples: `packets.Light.GetColor`, `packets.Light.SetColor`, `packets.Device.GetService`
- Pattern: Dataclass with `PKT_TYPE: ClassVar[int]`, `_fields: ClassVar[list[dict]]`, `pack()`/`unpack()` methods

**Device[TState] (`src/lifx/devices/base.py`):**
- Purpose: Generic base for all device types, parameterised by state dataclass
- Examples: `Light` (→ `LightState`), `MultiZoneLight` (→ `MultiZoneLightState`), `CeilingLight` (→ `CeilingLightState`)
- Pattern: Generic class with `async with` context manager, factory methods (`from_ip()`, `connect()`), cached properties, typed state via `get_state()`

**DeviceConnection (`src/lifx/network/connection.py`):**
- Purpose: Per-device UDP connection with request serialisation and retry logic
- Pattern: Lazy-opening connection, `_request_lock` prevents response mixing, async generator streaming for multi-response queries, background receiver task dispatches to pending request queues keyed by `(source, sequence, serial)`

**DiscoveredDevice (`src/lifx/network/discovery.py`):**
- Purpose: Lightweight record from discovery, converts to appropriate Device subclass
- Pattern: Dataclass with `create_device()` factory that queries product ID → `get_device_class_for_product()` (`src/lifx/devices/detection.py`)

**LIFXEffect (`src/lifx/effects/base.py`):**
- Purpose: Abstract base for all visual effects
- Pattern: Subclass implements `async_play()`, `name` property; `Conductor` manages lifecycle

**FrameEffect (`src/lifx/effects/frame_effect.py`):**
- Purpose: Frame-based effect using Animation layer for high-frequency output
- Pattern: Subclass of `LIFXEffect` that works with `Animator` for direct UDP frame delivery

**Animator (`src/lifx/animation/animator.py`):**
- Purpose: High-throughput frame sender bypassing connection layer
- Pattern: Factory methods (`for_matrix()`, `for_multizone()`, `for_light()`) query device once, then `send_frame()` uses raw socket with prebaked packet templates

## Entry Points

**Public API (`src/lifx/__init__.py`):**
- Location: `src/lifx/__init__.py`
- Triggers: `import lifx` or `from lifx import ...`
- Responsibilities: Re-exports all public symbols from all layers; single flat namespace for consumers

**High-Level API (`src/lifx/api.py`):**
- Location: `src/lifx/api.py`
- Triggers: `discover()`, `find_by_serial()`, `find_by_label()`, `find_by_ip()`, `discover_mdns()`
- Responsibilities: Async generator discovery, device creation, batch operations via `DeviceGroup`

**Device Factory Methods:**
- Location: `src/lifx/devices/base.py` (`Device.from_ip()`, `Device.connect()`)
- Triggers: Direct device creation by IP or serial
- Responsibilities: Query device, detect product, instantiate correct subclass

**Protocol Generator (`src/lifx/protocol/generator.py`):**
- Location: `src/lifx/protocol/generator.py`
- Triggers: `uv run python -m lifx.protocol.generator`
- Responsibilities: Downloads `protocol.yml`, generates `packets.py` and `protocol_types.py`

**Products Generator (`src/lifx/products/generator.py`):**
- Location: `src/lifx/products/generator.py`
- Triggers: `uv run python -m lifx.products.generator`
- Responsibilities: Downloads `products.json`, generates `registry.py`

## Error Handling

**Strategy:** Exception hierarchy rooted at `LifxError` with specific subclasses for each failure domain

**Hierarchy (`src/lifx/exceptions.py`):**
- `LifxError` - Base for all library errors
  - `LifxDeviceNotFoundError` - Device unreachable or unknown product
  - `LifxTimeoutError` - Operation timed out (network or request level)
  - `LifxProtocolError` - Invalid packet, header, or response type mismatch
  - `LifxConnectionError` - Operation on closed connection
  - `LifxNetworkError` - Socket-level failure (UDP/mDNS)
  - `LifxUnsupportedCommandError` - Device returned `StateUnhandled` or lacks capability
  - `LifxUnsupportedDeviceError` - Device is relay/button-only (not a light)

**Patterns:**
- Connection layer retries with exponential backoff and jitter (configurable `max_retries`)
- Python version compatibility: `TIMEOUT_ERRORS` tuple catches both `TimeoutError` and `asyncio.TimeoutError` on Python 3.10
- Discovery has DoS protection: source ID validation, serial validation, overall + idle timeouts
- Device methods raise `LifxUnsupportedCommandError` when calling capability-specific methods on wrong device type

## Cross-Cutting Concerns

**Logging:** Python `logging` module throughout. Each module creates `_LOGGER = logging.getLogger(__name__)`. Structured dict logging in connection layer.

**Validation:** HSBK values validated at construction (ranges enforced). Protocol packets validate via `PKT_TYPE` attribute check. Packet sizes validated on receive.

**Authentication:** None - LIFX local protocol has no authentication. DoS protection in discovery only.

**Concurrency:** Single-device requests serialised via `asyncio.Lock` (`_request_lock`). Multi-device operations parallelised via `asyncio.TaskGroup`. Sequence numbers (uint8, 0-255) allocated atomically per request for response correlation.

**Type Safety:** Full type hints throughout. Strict Pyright validation. `py.typed` marker present (`src/lifx/py.typed`). Generic device base class `Device[TState]`.

---

*Architecture analysis: 2026-04-16*
