# Codebase Structure

**Analysis Date:** 2026-06-11

## Directory Layout

```
lifx-async/
├── .planning/                  # GSD planning artifacts (generated)
├── .claude/                    # Project-specific instructions and skills
├── src/lifx/                   # Main source code
│   ├── __init__.py            # Public API exports
│   ├── api.py                 # High-level discovery and batch operations
│   ├── color.py               # HSBK color class with RGB conversion
│   ├── const.py               # Constants (ports, defaults, UUIDs, timeouts)
│   ├── exceptions.py          # Exception hierarchy (LifxError, LifxTimeoutError, etc.)
│   │
│   ├── protocol/              # LIFX protocol implementation
│   │   ├── __init__.py
│   │   ├── header.py          # 36-byte LIFX header serialization
│   │   ├── packets.py         # Auto-generated packet definitions (NEVER edit manually)
│   │   ├── protocol_types.py  # Auto-generated enums and types
│   │   ├── serializer.py      # Binary encoding/decoding
│   │   ├── models.py          # Protocol data models (Serial, HEV types)
│   │   ├── base.py            # Base classes for protocol structures
│   │   └── generator.py       # Code generator for protocol.yml → packets.py
│   │
│   ├── network/               # Network communication layer
│   │   ├── __init__.py
│   │   ├── connection.py      # Device connection with request/response, retry logic
│   │   ├── discovery.py       # UDP broadcast device discovery (DoS-protected)
│   │   ├── transport.py       # Async UDP socket management
│   │   ├── message.py         # Message serialization (header + packet → binary)
│   │   ├── utils.py           # Source ID allocation
│   │   └── mdns/              # mDNS/DNS-SD discovery (faster single-query alternative)
│   │       ├── __init__.py
│   │       ├── discovery.py   # discover_lifx_services(), discover_devices_mdns()
│   │       ├── dns.py         # DNS wire format parser (PTR, SRV, A, TXT records)
│   │       ├── transport.py   # MdnsTransport for multicast UDP
│   │       └── types.py       # LifxServiceRecord dataclass
│   │
│   ├── devices/               # Device types and state classes
│   │   ├── __init__.py
│   │   ├── base.py            # Device base class, state caching, MAC address logic
│   │   ├── detection.py       # Device type detection from product ID
│   │   ├── light.py           # Light with color control (HSBK)
│   │   ├── hev.py             # Light + HEV (anti-bacterial cleaning)
│   │   ├── infrared.py        # Light + infrared LED
│   │   ├── multizone.py       # MultiZoneLight for strips/beams (zone-based control)
│   │   ├── matrix.py          # MatrixLight for tiles (2D pixel control)
│   │   └── ceiling.py         # CeilingLight (tiles + uplight/downlight components)
│   │
│   ├── effects/               # Visual effect generators (30+ built-in effects)
│   │   ├── __init__.py
│   │   ├── base.py            # Base effect class with frame generator interface
│   │   ├── frame_effect.py    # FrameEffect for custom frame-based effects
│   │   ├── registry.py        # Effect registry for discovering/instantiating by name
│   │   ├── state_manager.py   # EffectStateManager for running effects on devices
│   │   ├── conductor.py       # Conductor for orchestrating multiple effects
│   │   ├── models.py          # Shared effect models
│   │   ├── const.py           # Effect constants
│   │   ├── aurora.py          # Aurora effect (animated gradient with randomness)
│   │   ├── colorloop.py       # Colour loop effect
│   │   ├── flame.py           # Flame effect
│   │   ├── plasma.py          # Plasma effect
│   │   ├── plasma2d.py        # 2D plasma for matrix devices
│   │   ├── rainbow.py         # Rainbow effect
│   │   ├── pulse.py           # Pulse effect
│   │   ├── progress.py        # Progress bar effect
│   │   ├── sunrise.py         # Sunrise effect with configurable origin
│   │   ├── (20+ more effects) # Aurora, Cylon, Double Slit, Embers, Fireworks, etc.
│   │
│   ├── animation/             # High-frequency frame delivery for tiles/multizone
│   │   ├── __init__.py
│   │   ├── animator.py        # Animator class (high-level API, direct UDP sending)
│   │   ├── framebuffer.py     # FrameBuffer with multi-tile canvas mapping
│   │   ├── packets.py         # Packet templates and generators (Matrix, MultiZone, Light)
│   │   └── orientation.py     # Tile orientation remapping with LRU cache
│   │
│   ├── theme/                 # Theme support (named color palettes)
│   │   ├── __init__.py
│   │   ├── theme.py           # Theme definition (list of HSBK colors)
│   │   ├── library.py         # Built-in theme library
│   │   ├── canvas.py          # Canvas abstraction for applying themes
│   │   └── generators.py      # Generators for single/multi/matrix zones
│   │
│   └── products/              # Device capability registry
│       ├── __init__.py
│       ├── registry.py        # Auto-generated product database
│       ├── generator.py       # Generator to download products.json
│       └── quirks.py          # Device-specific quirks/workarounds
│
├── tests/                     # Test suite (2425+ tests, mirrors src structure)
│   ├── conftest.py           # Pytest fixtures (emulator setup, async helpers)
│   ├── test_protocol/        # Protocol layer tests (159 tests)
│   │   ├── test_header.py
│   │   ├── test_packets.py
│   │   ├── test_serializer.py
│   │   └── test_generator.py
│   │
│   ├── test_network/         # Network layer tests (183 tests)
│   │   ├── test_transport.py
│   │   ├── test_discovery.py
│   │   ├── test_connection.py
│   │   ├── test_message.py
│   │   └── test_mdns/
│   │
│   ├── test_devices/         # Device layer tests (375 tests)
│   │   ├── test_base.py
│   │   ├── test_light.py
│   │   ├── test_ceiling.py
│   │   ├── test_matrix.py
│   │   ├── test_multizone.py
│   │   ├── test_hev.py
│   │   └── test_state_*.py   # State management per device type
│   │
│   ├── test_api/             # High-level API tests (63 tests)
│   │   ├── test_discovery.py
│   │   ├── test_batch_operations.py
│   │   └── test_device_group.py
│   │
│   ├── test_effects/         # Effects tests (1249 tests)
│   │   ├── test_aurora.py
│   │   ├── test_registry.py
│   │   ├── test_integration.py
│   │   └── (per-effect test files)
│   │
│   ├── test_theme/           # Theme tests (146 tests)
│   │   ├── test_theme.py
│   │   ├── test_canvas.py
│   │   └── test_library.py
│   │
│   ├── test_animation/       # Animation tests (123 tests)
│   │   ├── test_animator.py
│   │   ├── test_framebuffer.py
│   │   └── test_orientation.py
│   │
│   ├── test_products/        # Product registry tests
│   │   └── test_registry.py
│   │
│   └── test_utils.py         # Utilities tests (color, products, etc.)
│
├── examples/                 # Usage examples (25+ examples)
│   ├── discovery_broadcast.py        # UDP broadcast discovery
│   ├── discovery_mdns.py             # mDNS discovery
│   ├── discovery_find_device.py      # Find specific device
│   ├── discovery_logging.py          # Discovery with logging
│   ├── control_basic.py              # Basic on/off control
│   ├── control_device_groups.py      # Batch operations
│   ├── control_waveforms.py          # Waveform effects
│   ├── effects_aurora.py             # Aurora effect example
│   ├── effects_demo.py               # Multiple effects demo
│   ├── effects_custom.py             # Custom effect creation
│   ├── matrix_basic.py               # Basic tile control
│   ├── matrix_large_tiles.py         # Multi-tile effects
│   ├── matrix_effects.py             # Tile-specific effects
│   ├── animation_basic.py            # Animator usage
│   ├── animation_numpy.py            # Numpy integration
│   └── (more examples)
│
├── docs/                    # Documentation (MkDocs)
│   ├── index.md            # Landing page
│   ├── getting-started.md  # Quick start guide
│   ├── api/                # API documentation
│   └── guides/             # Guides for different device types
│
├── scripts/                # Development scripts
│   ├── mdns_probe.py       # mDNS debugging tool
│   └── test_multiversion.py # Multi-Python version testing
│
├── pyproject.toml         # Project metadata, dependencies, tool config
├── uv.lock                # Locked dependency versions
├── mkdocs.yml             # Documentation site configuration
├── README.md              # Project overview
├── CLAUDE.md              # Project-specific coding instructions
└── LICENSE                # MIT license

```

## Directory Purposes

**`src/lifx/`**
- Purpose: Main library source code
- Contains: All public API, device classes, protocol, network, effects
- Key files: `__init__.py` (public exports), `api.py` (high-level API), `color.py` (color utilities)

**`src/lifx/protocol/`**
- Purpose: LIFX binary protocol implementation
- Contains: Header format, packet definitions, serialization, type definitions
- Generated: `packets.py` and `protocol_types.py` are auto-generated from YAML
- Never edit: `packets.py`, `protocol_types.py` — edit generator.py instead
- Key files: `generator.py` (regenerate all), `header.py` (36-byte header structure)

**`src/lifx/network/`**
- Purpose: UDP communication and device discovery
- Contains: Connection pooling, transport, discovery (UDP + mDNS), message building
- Key patterns: Lazy connection opening, async generator streaming, DoS protection
- Key files: `connection.py` (request/response), `discovery.py` (broadcast), `mdns/` (DNS-SD)

**`src/lifx/devices/`**
- Purpose: Device-type-specific control APIs
- Contains: Device class hierarchy, state dataclasses, capability-specific methods
- Detection: `detection.py` maps product ID → device class name
- Key patterns: Inheritance from Device[StateT], state caching per device
- Key files: `base.py` (Device base class), device-specific files (light.py, matrix.py, etc.)

**`src/lifx/effects/`**
- Purpose: Visual effect generators
- Contains: 30+ built-in effects, effect registry, state manager, conductor
- Key patterns: Frame generators, registry for name-based lookup
- Key files: `registry.py` (discover effects), `conductor.py` (orchestrate multiple effects)

**`src/lifx/animation/`**
- Purpose: High-frequency frame delivery for matrix/multizone devices
- Contains: Animator (direct UDP), FrameBuffer (canvas), packet pre-generation, orientation
- Key patterns: Synchronous frame sending for performance
- Key files: `animator.py` (high-level API), `framebuffer.py` (canvas), `packets.py` (templates)

**`src/lifx/theme/`**
- Purpose: Coordinated color schemes for device groups
- Contains: Theme definitions, generators for different device types
- Key files: `library.py` (built-in themes), `generators.py` (device-specific)

**`src/lifx/products/`**
- Purpose: Device capability registry from LIFX products.json
- Contains: Product database, device type detection
- Generated: `registry.py` auto-generated from products.json
- Key files: `generator.py` (download + regenerate), `registry.py` (lookup capabilities)

**`tests/`**
- Purpose: Test suite (2425+ tests)
- Organization: Mirrors `src/` structure exactly
- Coverage: Protocol (159), Network (183), Devices (375), API (63), Effects (1249), Theme (146), Animation (123), Utilities (127)
- Key files: `conftest.py` (fixtures, emulator setup)

**`examples/`**
- Purpose: Usage examples for different patterns
- Contains: Discovery, control, effects, animation, matrix, grouping examples
- Executable: All examples can be run directly: `python examples/discovery_broadcast.py`

**`docs/`**
- Purpose: User-facing documentation (MkDocs)
- Contains: API reference, guides for different device types, examples
- Generated: Some sections auto-generated during release

**`scripts/`**
- Purpose: Development and debugging utilities
- Contains: mDNS probe, multi-version testing

## Key File Locations

**Entry Points:**
- `src/lifx/__init__.py`: Public API exports (Device classes, discovery functions, Color, Exceptions)
- `src/lifx/api.py`: High-level discovery and batch operations (discover, find_by_*, DeviceGroup)

**Configuration:**
- `src/lifx/const.py`: Constants (LIFX_UDP_PORT, timeouts, default values, official URLs)
- `pyproject.toml`: Project metadata, dependencies, tool configuration

**Core Logic:**
- `src/lifx/devices/base.py`: Base Device class, state management, common operations
- `src/lifx/network/connection.py`: Request/response, retry logic, connection pooling
- `src/lifx/protocol/header.py`: 36-byte LIFX header format
- `src/lifx/protocol/serializer.py`: Binary encoding/decoding

**Device Types:**
- `src/lifx/devices/light.py`: Color lights (HSBK control)
- `src/lifx/devices/multizone.py`: Strips/beams (zone-based control)
- `src/lifx/devices/matrix.py`: Tiles (2D pixel control)
- `src/lifx/devices/ceiling.py`: Ceiling lights (tiles + components)
- `src/lifx/devices/hev.py`: HEV lights (color + anti-bacterial)
- `src/lifx/devices/infrared.py`: Infrared lights (color + IR LED)

**Testing:**
- `tests/conftest.py`: Pytest fixtures, emulator setup
- `tests/test_devices/test_light.py`: Light device tests
- `tests/test_network/test_connection.py`: Connection/retry logic tests

## Naming Conventions

**Files:**
- `*.py`: Standard Python module files
- Protocol files: `packets.py` (auto-generated), `protocol_types.py` (auto-generated), `header.py`, `serializer.py`
- Device files: `base.py` (Device base), `light.py`, `multizone.py`, `matrix.py`, `ceiling.py`, `hev.py`, `infrared.py`
- Effect files: `aurora.py`, `flame.py`, `plasma.py` (one file per effect), `registry.py`, `conductor.py`
- Test files: `test_<module>.py` (e.g., `test_connection.py`, `test_light.py`)

**Functions:**
- `async def`: External API (discovery, control, requests)
- `def`: Internal or synchronous operations
- `_private`: Internal helpers (prefixed with `_`)
- Factory methods: `from_*` (e.g., `Device.from_ip()`, `HSBK.from_rgb()`)

**Variables:**
- `CONSTANT`: Module-level constants (LIFX_UDP_PORT, DEFAULT_REQUEST_TIMEOUT)
- `_private`: Private module-level variables
- Device properties: Lowercase (e.g., `device.label`, `device.power`)
- Class names: PascalCase (Device, Light, HSBK, LifxHeader)

**Types:**
- State dataclasses: `[DeviceType]State` (LightState, MatrixLightState, MultiZoneLightState)
- Exceptions: `Lifx[Error]` (LifxDeviceNotFoundError, LifxTimeoutError)
- Enums: PascalCase (Direction, LightWaveform)

## Where to Add New Code

**New Device Type:**
- Implementation: `src/lifx/devices/<device_name>.py` (inherit from Device[StateT])
- State class: In same file as device (e.g., `LightState` in `light.py`)
- Tests: `tests/test_devices/test_<device_name>.py`
- Export: Add to `src/lifx/devices/__init__.py` and `src/lifx/__init__.py`
- Detection: Update `src/lifx/devices/detection.py` to map product ID → device class

**New Effect:**
- Implementation: `src/lifx/effects/<effect_name>.py` (inherit from `FrameEffect`)
- Frame generator: Implement `generate_frame(frame_context)` method
- Tests: `tests/test_effects/test_<effect_name>.py`
- Registry: Auto-discovered via `@registry.register` decorator or `registry.add()` call
- Export: Add to `src/lifx/effects/__init__.py` and main `src/lifx/__init__.py` if public

**New Utility Function:**
- Cross-module utility: `src/lifx/utils.py` (doesn't exist yet, would be appropriate for shared helpers)
- Color-related: `src/lifx/color.py` (HSBK class)
- Constants: `src/lifx/const.py` (module-level constants)

**New Test:**
- Mirror source structure: `tests/test_<module>/test_<feature>.py`
- Use fixtures from `conftest.py` (emulator, async helpers)
- Follow existing patterns (setup, act, assert)
- Mark with `@pytest.mark.emulator` if using emulator

**Protocol Changes:**
1. Update LIFX official `protocol.yml` (not stored in repo)
2. Run `uv run python -m lifx.protocol.generator`
3. Review auto-generated `src/lifx/protocol/packets.py` and `protocol_types.py`
4. For local quirks (field renames), edit `src/lifx/protocol/generator.py`
5. Commit regenerated files

## Special Directories

**`.planning/codebase/`**
- Purpose: GSD codebase analysis documents
- Generated: Created by `/gsd-map-codebase` command
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md
- Committed: Yes, tracked in git

**`.claude/`**
- Purpose: Project-specific instructions
- Contains: CLAUDE.md (this file's sibling), skills/ (project practices)
- Committed: Yes

**`docs/`**
- Purpose: User documentation
- Generated: Some auto-generated during release (never edit changelog.md manually)
- Committed: Yes

**`site/`**
- Purpose: Built documentation (MkDocs output)
- Generated: Yes (from docs/)
- Committed: Yes (for GitHub Pages)

**`.github/workflows/`**
- Purpose: CI/CD pipelines
- Contains: Tests, coverage, release workflows
- Committed: Yes

**`.mypy_cache/`, `.ruff_cache/`, `__pycache__/`**
- Purpose: Tool caches
- Generated: Yes
- Committed: No (in .gitignore)

---

*Structure analysis: 2026-06-11*
