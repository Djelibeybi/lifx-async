<!-- refreshed: 2026-06-11 -->
# Architecture

**Analysis Date:** 2026-06-11

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           High-Level API                                     │
│  discover() / discover_mdns() / find_by_* / DeviceGroup / Batch Ops        │
│  `src/lifx/api.py`                                                          │
└───────────────────────────────┬─────────────────────────────────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Device Layer                                            │
│  Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight  │
│  CeilingLight | State classes                                               │
│  `src/lifx/devices/`                                                        │
│  Also: Theme (apply_theme), Animation (Animator), Effects (run effects)    │
└───────────────────────────────┬─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Network Layer                                             │
│  DeviceConnection | Discovery | mDNS | Transport | Message Builder         │
│  `src/lifx/network/`                                                        │
│  Features: Lazy connection opening, request serialization, retry logic      │
└───────────────────────────────┬─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Protocol Layer                                            │
│  Header | Serializer | Packets | Protocol Types | Models                   │
│  `src/lifx/protocol/` - Auto-generated from YAML specification             │
└───────────────────────────────┬─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      UDP Transport                                           │
│  Async UDP socket communication via asyncio                                 │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LIFX Devices on Network                                  │
│  Color Lights | Multizone Strips | Matrix Tiles | HEV Lights | etc.        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| **High-Level API** | Discovery with context managers, batch operations, find/filter operations | `src/lifx/api.py` |
| **Device Base** | Common operations (power, label, version, info), state caching, MAC address calculation | `src/lifx/devices/base.py` |
| **Light** | Color control, brightness, temperature, waveforms | `src/lifx/devices/light.py` |
| **HevLight** | Light + HEV (anti-bacterial cleaning) cycle control | `src/lifx/devices/hev.py` |
| **InfraredLight** | Light + infrared LED control | `src/lifx/devices/infrared.py` |
| **MultiZoneLight** | Strip/beam devices with zone-based color control | `src/lifx/devices/multizone.py` |
| **MatrixLight** | 2D tile devices with pixel-level control | `src/lifx/devices/matrix.py` |
| **CeilingLight** | Matrix device with independent uplight/downlight control | `src/lifx/devices/ceiling.py` |
| **DeviceConnection** | Request/response lifecycle, sequence management, retry logic, connection pooling | `src/lifx/network/connection.py` |
| **Discovery** | UDP broadcast device discovery with DoS protection | `src/lifx/network/discovery.py` |
| **mDNS** | DNS-SD service discovery (faster single-query alternative) | `src/lifx/network/mdns/` |
| **Transport** | Async UDP socket management | `src/lifx/network/transport.py` |
| **Protocol Header** | 36-byte LIFX header serialization/deserialization | `src/lifx/protocol/header.py` |
| **Packets** | Packet structures auto-generated from protocol.yml | `src/lifx/protocol/packets.py` |
| **Serializer** | Binary encoding/decoding of protocol values | `src/lifx/protocol/serializer.py` |
| **Effects** | 30+ built-in effects (aurora, flame, plasma, rainbow, etc.) | `src/lifx/effects/` |
| **Animator** | High-level frame delivery for tile/multizone devices | `src/lifx/animation/animator.py` |
| **FrameBuffer** | Multi-tile canvas with orientation remapping | `src/lifx/animation/framebuffer.py` |
| **Theme** | Named color palettes with generators for device types | `src/lifx/theme/` |
| **Color** | HSBK class with RGB conversion and presets | `src/lifx/color.py` |
| **Products** | Device capability registry from official products.json | `src/lifx/products/` |

## Pattern Overview

**Overall:** Layered async architecture with clear separation of concerns

**Key Characteristics:**
- **Async-first design**: Built on Python's `asyncio`, no external async dependency
- **Type-safe**: Full type hints with strict Pyright validation
- **Zero runtime dependencies**: Protocol layer is completely self-contained
- **Auto-generated protocol**: Packet structures generated from YAML, never edited manually
- **Lazy connection opening**: Connections open on first request, not on initialization
- **Request/response streaming**: Async generators for flexible multi-response handling
- **State caching**: Reduced network traffic via semi-persistent device state
- **Device capability detection**: Automatic instantiation of correct device class based on product ID

## Layers

**Protocol Layer:**
- Purpose: Encode/decode LIFX protocol binary format
- Location: `src/lifx/protocol/`
- Contains: Headers, packet definitions, types, serializers
- Depends on: Python stdlib only (zero dependencies)
- Used by: Network layer
- Key insight: `packets.py` is auto-generated from YAML — never edit manually

**Network Layer:**
- Purpose: Manage UDP communication, discovery, and connection lifecycle
- Location: `src/lifx/network/`
- Contains: Connection management, transport, discovery (UDP and mDNS), message building
- Depends on: Protocol layer
- Used by: Device layer
- Key insight: Lazy connection opening — `DeviceConnection` doesn't open socket until first request

**Device Layer:**
- Purpose: Provide device-specific control APIs (color, effects, zones, etc.)
- Location: `src/lifx/devices/`
- Contains: Device class hierarchy, state dataclasses, capability-specific methods
- Depends on: Network layer, protocol, color, products
- Used by: High-level API, application code
- Key insight: State caching reduces repeated network requests; TTL is application-controlled

**Animation Layer:**
- Purpose: High-frequency frame delivery for matrix and multizone devices
- Location: `src/lifx/animation/`
- Contains: Animator, FrameBuffer, orientation remapping, packet pre-generation
- Depends on: Protocol layer (sends raw packets via UDP directly, bypassing DeviceConnection)
- Used by: Application code for real-time effects
- Key insight: Synchronous frame sending for performance; operates independently of Device layer

**Effects Layer:**
- Purpose: Generate frames for visual effects
- Location: `src/lifx/effects/`
- Contains: 30+ built-in effects, frame generators, registry
- Depends on: Color, animation
- Used by: Device methods (set_effect) and standalone animation
- Key insight: Effects are stateful frame generators; registry discovers by name

**Theme Layer:**
- Purpose: Apply coordinated color palettes to device groups
- Location: `src/lifx/theme/`
- Contains: Theme definitions, generators for single/multi/matrix zones, library
- Depends on: Color, devices
- Used by: Device.apply_theme() method
- Key insight: Themes generate device-specific commands based on device type

**Utilities:**
- Purpose: Cross-cutting concerns and support functionality
- Location: `src/lifx/` (color.py, const.py, exceptions.py, products/)
- Contains: HSBK color class, constants, exception hierarchy, product registry
- Depends on: Protocol layer (for types)
- Used by: All other layers

## Data Flow

### Primary Request Path (Device → Network → Protocol → UDP → Device)

1. Application calls device method: `await light.set_color(HSBK.from_rgb(1.0, 0.0, 0.0))` (`src/lifx/devices/light.py:190`)
2. Device method creates packet: `packets.Light.SetColor(color=color.to_protocol())`
3. Device calls connection: `await self.connection.request(packet)` (`src/lifx/network/connection.py:180`)
4. Connection allocates sequence number (0-255, atomic) and creates header: `LifxHeader.create(...)` (`src/lifx/protocol/header.py:76`)
5. Message builder serializes: `create_message(header, packet)` → binary frame (`src/lifx/network/message.py`)
6. Transport sends via UDP: `socket.sendto(frame, (ip, port))` (`src/lifx/network/transport.py:112`)
7. Device receives response on same socket (multiplexed by source ID)
8. Message parser deserializes response: `parse_message(frame)` → packet instance (`src/lifx/network/message.py`)
9. Async generator yields response; connection unpacks and returns typed packet (`src/lifx/network/connection.py:240`)
10. Device updates cached state: `self._state.color = color` (`src/lifx/devices/light.py:144`)
11. Application receives result

### Discovery Path (Broadcast → Network Discovery → Device Creation)

1. Application calls: `async for device in discover()` (`src/lifx/api.py:746`)
2. High-level API calls: `discover_devices(...)` (`src/lifx/network/discovery.py:380`)
3. Discovery creates broadcast header: `LifxHeader.create(pkt_type=2, tagged=True, res_required=True)` (GetService)
4. Transport broadcasts packet: `socket.sendto(packet, ("255.255.255.255", LIFX_UDP_PORT))`
5. Devices respond with service info (addresses, ports)
6. Discovery collects responses for `timeout` seconds, applies DoS protection:
   - Validates source ID matches request
   - Validates serial number (rejects broadcast b'\x00\x00\x00\x00\x00\x00')
   - Stops after idle timeout (2 seconds)
7. Discovered device wrapper created: `DiscoveredDevice(serial, ip, port, ...)`
8. High-level API converts to typed device: `await discovered.create_device()` (`src/lifx/devices/detection.py`)
9. Device type determined by product registry: `get_product(product_id)` → device class name
10. Device instantiated with cached info (no extra request needed)
11. Yielded to application

### Animation Path (Frame → Animator → Direct UDP)

1. Application calls: `animator = await Animator.for_matrix(device)` (`src/lifx/animation/animator.py:45`)
2. Animator queries device once: `await device.get_tile_chain()` to collect geometry
3. Animator creates FrameBuffer with tile positions
4. Device connection closed (animation is independent)
5. Application creates HSBK frame array (uint16 values): `[(65535, 65535, 65535, 3500)] * pixel_count`
6. Animator sends synchronously: `stats = animator.send_frame(hsbk_frame)` (`src/lifx/animation/animator.py:150`)
7. Animator pre-generates packets from template: `MatrixPacketGenerator.generate_packets(hsbk_frame)` (`src/lifx/animation/packets.py:300`)
8. Animator sends packets directly via UDP: `sock.sendto(packet, (ip, port))`
9. No response handling — animation is fire-and-forget
10. Stats returned (packets sent, bytes sent)

**State Management:**
- Request/response serialized per device via `_request_lock` (asyncio.Lock) to prevent mixing on same UDP socket
- Multiple devices execute in parallel via `asyncio.TaskGroup`
- Sequence numbers (0-255) atomically allocated per request for matching responses
- Cached state (color, power, label) updated after responses
- No automatic cache expiration — application controls refresh

## Key Abstractions

**Device Hierarchy:**
- Purpose: Represent different LIFX device types with type-safe APIs
- Pattern: Inheritance from `Device[StateT]` generic base class
- Examples: `Device` (base) → `Light` (color) → `HevLight` (color + HEV), `MultiZoneLight` (color + zones)
- Capability detection: Product registry determines which class to instantiate

**Packet Classes:**
- Purpose: Type-safe protocol message definitions
- Pattern: Auto-generated dataclasses with `to_bytes()` and `from_bytes()` methods
- Examples: `packets.Light.GetColor()`, `packets.Light.SetColor(color=...)`
- Source: `src/lifx/protocol/packets.py` (auto-generated, never manually edited)

**State Dataclasses:**
- Purpose: Immutable snapshots of device state
- Pattern: Subclassed from `DeviceState` base
- Examples: `LightState` (+ color field), `MultiZoneLightState` (+ zones field)
- Cached in device: `self._state` — application accesses via `.state` property

**Connection/Transport Abstraction:**
- Purpose: Isolate UDP socket management from request/response logic
- Pattern: `UdpTransport` (low-level socket) ← `DeviceConnection` (request/response, retry)
- Lazy opening: Transport opens socket only on first send
- Sequence matching: Response multiplexing via source ID and sequence number

**Async Generator Streaming:**
- Purpose: Flexible request/response handling for variable response counts
- Pattern: `async for response in connection.request(packet):`
- Single-response requests break after first yield
- Multi-response requests stream until timeout or early exit
- Enables discovery streaming (yield devices as found)

## Entry Points

**Application Entry Points (typically used):**
- `lifx.discover()` — Async generator yielding Device instances (`src/lifx/api.py:746`)
- `lifx.discover_mdns()` — mDNS-based discovery (`src/lifx/api.py:796`)
- `lifx.find_by_ip(ip)` — Find device at specific IP (`src/lifx/api.py:903`)
- `lifx.find_by_serial(serial)` — Find device by serial number (`src/lifx/api.py:850`)
- `lifx.find_by_label(label)` — Find device by label (substring) (`src/lifx/api.py:955`)
- `Device.from_ip(ip)` — Create device from IP address (`src/lifx/devices/base.py:350`)
- `Device.connect(serial, ip)` — Connect to specific device (`src/lifx/devices/base.py:360`)

**Internal Entry Points (protocol/network):**
- `discover_devices(...)` — Low-level UDP discovery generator (`src/lifx/network/discovery.py:380`)
- `DiscoveredDevice.create_device()` — Convert discovery response to typed Device (`src/lifx/devices/detection.py:25`)
- `DeviceConnection.request(packet)` — Send request, receive response (`src/lifx/network/connection.py:180`)
- `create_message(header, packet)` — Serialize header + packet to binary (`src/lifx/network/message.py:10`)
- `parse_message(frame)` — Deserialize binary frame to (header, packet) (`src/lifx/network/message.py:40`)

## Architectural Constraints

- **Threading:** Single-threaded event loop (asyncio). No worker threads used. Devices are serialized per connection via `_request_lock`.
- **Global state:** Source ID allocated once per import via `allocate_source()` (`src/lifx/network/utils.py`). No mutable module-level singletons.
- **Circular imports:** Type-checking guard used (`if TYPE_CHECKING:`) in device hierarchy to prevent cycles at runtime (`src/lifx/devices/base.py:28`).
- **Protocol immutability:** `packets.py` auto-generated from YAML — modifications are overwritten on regeneration. Never edit manually.
- **Zero dependencies:** Runtime layer has zero external dependencies. All protocol handling is stdlib-only.
- **Lazy connections:** Connections open on first request, not on Device instantiation. No network calls during Device creation.
- **One socket per device:** Each `DeviceConnection` owns one `UdpTransport` (one socket). Multiple requests serialize via `_request_lock`.
- **No automatic rate limiting:** Devices handle ~20 msg/sec; application responsible for throttling if needed.

## Anti-Patterns

### Mixing Protocol and User HSBK Formats

**What happens:** Code uses uint16 HSBK (0-65535) where user-facing HSBK (0-360°, 0.0-1.0) is expected, or vice versa.

**Why it's wrong:** HSBK has two incompatible formats — protocol layer works with uint16, user-facing classes use floats. Mixing causes color distortion.

**Do this instead:**
- Use `HSBK.from_protocol(uint16_hsbk)` to convert from protocol format (`src/lifx/color.py:50`)
- Use `color.to_protocol()` to convert to protocol format (`src/lifx/color.py:90`)
- Animation/Animator work with uint16 directly (that's the performance optimization)
- Device methods work with user-facing HSBK floats

### Holding DeviceConnection Open During Idle Periods

**What happens:** Creating Device from discovery, then holding connection open without sending requests.

**Why it's wrong:** Each connection owns a UDP socket; keeping it open wastes resources. Original request that queried device has enough info to avoid second connection.

**Do this instead:**
- Call `await device.connection.close()` when done (`src/lifx/network/connection.py:100`)
- Use context manager: `async with device: ...` (calls close automatically) (`src/lifx/devices/base.py:400`)
- For discovery: hold device only while in use, or batch operations in DeviceGroup

### Calling Device Methods on StateUnhandled Response

**What happens:** Device returns `StateUnhandled` (packet type 223) indicating unsupported command.

**Why it's wrong:** Some devices don't support all commands (e.g., color-less devices can't set_color). Ignoring the error masks capability mismatches.

**Do this instead:**
- Check device capabilities before calling method: `if device.capabilities.has_color: await device.set_color(...)`
- Catch `LifxUnsupportedCommandError` exception (`src/lifx/exceptions.py:65`)
- Use device-specific classes: `MatrixLight` for matrix, `MultiZoneLight` for zones, etc.

### Directly Editing Generated Protocol Files

**What happens:** Hand-editing `src/lifx/protocol/packets.py` or `protocol_types.py`.

**Why it's wrong:** Generator overwrites these files. Manual changes are lost on next regeneration.

**Do this instead:**
- Update `protocol.yml` in LIFX official repo
- Run `uv run python -m lifx.protocol.generator` to regenerate
- For local quirks (field renames, filtering), modify `src/lifx/protocol/generator.py`

## Error Handling

**Strategy:** Exception-based with specific error types for different failure modes

**Patterns:**
- Device not reachable: `LifxDeviceNotFoundError` — network layer can't send or receive from device
- Operation timeout: `LifxTimeoutError` — no response within timeout period
- Invalid response: `LifxProtocolError` — response packet type mismatch or deserialization failure
- Connection not open: `LifxConnectionError` — attempting request when socket not open
- OS-level network error: `LifxNetworkError` — socket creation/send/receive failed
- Device unsupported command: `LifxUnsupportedCommandError` — device returns StateUnhandled
- Device not supported: `LifxUnsupportedDeviceError` — product type unknown (relay-only, button-only, etc.)

**Retry Logic:** Automatic retry in `DeviceConnection.request()` with exponential backoff and jitter (base 0.1s, max 8 retries) (`src/lifx/network/connection.py:195`)

## Cross-Cutting Concerns

**Logging:** Python stdlib logging with module-level loggers:
- Each module has `_LOGGER = logging.getLogger(__name__)`
- Debug logging at key points: device discovery, request/response, state updates
- No structured logging — plain text messages

**Validation:**
- HSBK color ranges (hue 0-360, sat/bright 0.0-1.0, kelvin 1500-9000) validated in `HSBK` class (`src/lifx/color.py`)
- Packet types validated in `DeviceConnection.request()` against expected response type
- Serial/MAC address format validated (must be valid hex, correct length)
- Sequence numbers (0-255) enforced by uint8 type

**Authentication:** No authentication in protocol layer. LIFX protocol is unauthenticated (assumes local network trust). Device discovery requires network access.

**Concurrency:** All external-facing APIs are async. Concurrency patterns:
- Single connection per device serializes requests via `_request_lock`
- Multiple devices use `asyncio.TaskGroup` for parallel requests
- Discovery uses async generators for streaming results
- No explicit thread spawning; all parallelism is async

---

*Architecture analysis: 2026-06-11*
