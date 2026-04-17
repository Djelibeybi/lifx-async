# Codebase Structure

**Analysis Date:** 2026-04-16

## Directory Layout

```text
lifx-async/
├── src/lifx/                  # Main library package
│   ├── __init__.py            # Public API re-exports (flat namespace)
│   ├── api.py                 # High-level discovery & batch operations
│   ├── color.py               # HSBK class, RGB conversion, Colors presets
│   ├── const.py               # All constants (network, HSBK ranges, URLs)
│   ├── exceptions.py          # Exception hierarchy (LifxError base)
│   ├── py.typed               # PEP 561 type marker
│   ├── protocol/              # Wire protocol (auto-generated)
│   │   ├── base.py            # Packet base class (pack/unpack)
│   │   ├── header.py          # 36-byte LIFX header
│   │   ├── serializer.py      # Binary field serialisation
│   │   ├── models.py          # Serial dataclass, HEV types
│   │   ├── packets.py         # [GENERATED] All packet classes
│   │   ├── protocol_types.py  # [GENERATED] Enums and field structures
│   │   └── generator.py       # Code generator (downloads protocol.yml)
│   ├── network/               # Transport and discovery
│   │   ├── transport.py       # UdpTransport (asyncio DatagramProtocol)
│   │   ├── connection.py      # DeviceConnection (per-device, lazy, locked)
│   │   ├── discovery.py       # DiscoveredDevice, broadcast discovery
│   │   ├── message.py         # create_message() / parse_message()
│   │   ├── utils.py           # allocate_source() helper
│   │   └── mdns/              # mDNS/DNS-SD discovery (zero-dependency)
│   │       ├── discovery.py   # discover_lifx_services(), discover_devices_mdns()
│   │       ├── dns.py         # DNS wire format parser (PTR, SRV, A, TXT)
│   │       ├── transport.py   # MdnsTransport (multicast UDP)
│   │       └── types.py       # LifxServiceRecord dataclass
│   ├── products/              # Product capability registry
│   │   ├── __init__.py        # Public exports (ProductInfo, ProductRegistry)
│   │   ├── registry.py        # [GENERATED] Product database
│   │   ├── quirks.py          # Product-specific quirks/overrides
│   │   └── generator.py       # Code generator (downloads products.json)
│   ├── devices/               # Device class hierarchy
│   │   ├── __init__.py        # Re-exports all device classes
│   │   ├── base.py            # Device[TState] generic base, DeviceState, factory methods
│   │   ├── detection.py       # get_device_class_for_product() capability routing
│   │   ├── light.py           # Light (colour control, waveforms)
│   │   ├── hev.py             # HevLight (+ HEV cleaning cycles)
│   │   ├── infrared.py        # InfraredLight (+ infrared LED)
│   │   ├── multizone.py       # MultiZoneLight (zone-based strips/beams)
│   │   ├── matrix.py          # MatrixLight (2D tiles, candle, path)
│   │   └── ceiling.py         # CeilingLight (uplight/downlight components)
│   ├── animation/             # High-frequency frame delivery
│   │   ├── __init__.py        # Exports Animator, AnimatorStats
│   │   ├── animator.py        # Animator class (direct UDP, factory methods)
│   │   ├── framebuffer.py     # FrameBuffer (multi-tile canvas, orientation)
│   │   ├── orientation.py     # Tile orientation remapping (LRU-cached)
│   │   └── packets.py         # Prebaked packet templates (Matrix, MultiZone, Light)
│   ├── effects/               # Visual effects framework
│   │   ├── __init__.py        # Re-exports all effects
│   │   ├── base.py            # LIFXEffect abstract base class
│   │   ├── conductor.py       # Conductor orchestrator (lifecycle management)
│   │   ├── state_manager.py   # DeviceStateManager (save/restore state)
│   │   ├── registry.py        # EffectRegistry (discovery, device compatibility)
│   │   ├── models.py          # PreState, RunningEffect dataclasses
│   │   ├── const.py           # Effect constants
│   │   ├── frame_effect.py    # FrameEffect (Animator-based effects)
│   │   ├── aurora.py          # EffectAurora
│   │   ├── colorloop.py       # EffectColorloop
│   │   ├── cylon.py           # EffectCylon
│   │   ├── double_slit.py     # EffectDoubleSlit
│   │   ├── embers.py          # EffectEmbers
│   │   ├── fireworks.py       # EffectFireworks
│   │   ├── flame.py           # EffectFlame
│   │   ├── jacobs_ladder.py   # EffectJacobsLadder
│   │   ├── newtons_cradle.py  # EffectNewtonsCradle
│   │   ├── pendulum_wave.py   # EffectPendulumWave
│   │   ├── plasma.py          # EffectPlasma
│   │   ├── plasma2d.py        # EffectPlasma2D
│   │   ├── progress.py        # EffectProgress
│   │   ├── pulse.py           # EffectPulse
│   │   ├── rainbow.py         # EffectRainbow
│   │   ├── ripple.py          # EffectRipple
│   │   ├── rule30.py          # EffectRule30
│   │   ├── rule_trio.py       # EffectRuleTrio
│   │   ├── sine.py            # EffectSine
│   │   ├── sonar.py           # EffectSonar
│   │   ├── spectrum_sweep.py  # EffectSpectrumSweep
│   │   ├── spin.py            # EffectSpin
│   │   ├── sunrise.py         # EffectSunrise, EffectSunset
│   │   ├── twinkle.py         # EffectTwinkle
│   │   └── wave.py            # EffectWave
│   └── theme/                 # Colour palette system
│       ├── __init__.py        # Exports Theme, ThemeLibrary, generators
│       ├── theme.py           # Theme class (colour palette)
│       ├── library.py         # ThemeLibrary, get_theme()
│       ├── generators.py      # SingleZone/MultiZone/MatrixGenerator
│       └── canvas.py          # Canvas abstraction for theme application
├── tests/                     # Test suite (mirrors src structure)
│   ├── conftest.py            # Shared fixtures, emulator setup
│   ├── test_color.py          # HSBK, RGB conversion, roundtrip tests
│   ├── test_utils.py          # General utility tests
│   ├── benchmarks/            # Performance benchmarks
│   ├── test_protocol/         # Protocol layer tests
│   ├── test_network/          # Network layer tests
│   │   └── test_mdns/         # mDNS subsystem tests
│   ├── test_devices/          # Device layer tests (+ state management)
│   ├── test_api/              # API layer tests
│   ├── test_effects/          # Effects layer tests (30+ effect tests)
│   ├── test_animation/        # Animation layer tests
│   ├── test_theme/            # Theme layer tests
│   └── test_products/         # Product registry tests
├── examples/                  # Usage examples (runnable scripts)
│   ├── discovery_*.py         # Discovery examples (broadcast, mDNS, find)
│   ├── control_*.py           # Device control examples
│   ├── animation_*.py         # Animation examples
│   ├── effects_*.py           # Effect examples
│   └── matrix_*.py            # Matrix device examples
├── docs/                      # MkDocs documentation source
│   ├── api/                   # API reference docs
│   ├── architecture/          # Architecture docs
│   ├── getting-started/       # Getting started guides
│   ├── user-guide/            # User guide
│   ├── migration/             # Migration guides
│   ├── assets/                # Static assets (images, effect previews)
│   └── stylesheets/           # Custom CSS
├── scripts/                   # Development scripts
├── conductor/                 # Development workflow tracking
├── pyproject.toml             # Project config (uv, ruff, pyright, pytest)
├── mkdocs.yml                 # Documentation site config
├── uv.lock                    # Dependency lock file
├── codecov.yml                # Coverage config
├── renovate.json              # Dependency update bot config
└── .pre-commit-config.yaml    # Pre-commit hooks (ruff, pyright)
```

## Directory Purposes

**`src/lifx/protocol/`:**
- Purpose: LIFX binary wire protocol implementation
- Contains: Auto-generated packet classes, header parsing, serialisation
- Key files: `packets.py` (generated, ~1100 lines), `generator.py` (downloads + generates)
- Rule: Never edit `packets.py` or `protocol_types.py` manually

**`src/lifx/network/`:**
- Purpose: All network I/O - UDP transport, discovery, per-device connections
- Contains: Transport, connection management, message framing, mDNS subsystem
- Key files: `connection.py` (~1000 lines, core request/response), `discovery.py` (broadcast discovery)

**`src/lifx/devices/`:**
- Purpose: Device class hierarchy with typed state and capability-specific methods
- Contains: Base device, 6 device subclasses, detection logic
- Key files: `base.py` (~1600 lines, Device generic base), `detection.py` (class routing)

**`src/lifx/effects/`:**
- Purpose: Visual effects framework with 30+ built-in effects
- Contains: Abstract base, conductor orchestrator, registry, individual effect implementations
- Key files: `base.py` (LIFXEffect ABC), `conductor.py` (lifecycle management), `registry.py` (effect discovery)

**`src/lifx/animation/`:**
- Purpose: High-frequency frame delivery for real-time animations (30+ FPS)
- Contains: Animator, framebuffer, prebaked packet templates, orientation mapping
- Key files: `animator.py` (direct UDP sender), `framebuffer.py` (multi-tile canvas)

**`src/lifx/theme/`:**
- Purpose: Colour palette system for applying coordinated schemes to devices
- Contains: Theme definitions, built-in library, zone/matrix generators, canvas abstraction

**`src/lifx/products/`:**
- Purpose: LIFX product capability database
- Contains: Auto-generated registry, quirks, generator
- Key files: `registry.py` (generated, all products), `quirks.py` (product-specific overrides)

## Key File Locations

**Entry Points:**
- `src/lifx/__init__.py`: Package public API (all re-exports)
- `src/lifx/api.py`: High-level discovery and batch operations
- `src/lifx/devices/base.py`: `Device.from_ip()`, `Device.connect()` factory methods

**Configuration:**
- `pyproject.toml`: Project metadata, dependencies, tool config (ruff, pyright, pytest)
- `mkdocs.yml`: Documentation site configuration
- `.pre-commit-config.yaml`: Pre-commit hooks
- `codecov.yml`: Coverage thresholds

**Core Logic:**
- `src/lifx/devices/base.py`: Device base class (state caching, connection management)
- `src/lifx/network/connection.py`: DeviceConnection (request/response, retry, locking)
- `src/lifx/network/discovery.py`: DiscoveredDevice and broadcast discovery
- `src/lifx/protocol/base.py`: Packet base class (pack/unpack)
- `src/lifx/color.py`: HSBK colour class with RGB conversion

**Auto-Generated (do not edit):**
- `src/lifx/protocol/packets.py`: Protocol packet classes
- `src/lifx/protocol/protocol_types.py`: Protocol enums and field structures
- `src/lifx/products/registry.py`: Product capability database

**Testing:**
- `tests/conftest.py`: Shared fixtures, emulator configuration
- `tests/test_devices/`: Device layer tests (most coverage)
- `tests/test_effects/`: Effects tests (largest test count: 1249)

## Naming Conventions

**Files:**
- `snake_case.py`: All Python files use snake_case
- `[GENERATED]` files: `packets.py`, `protocol_types.py`, `registry.py` - never edit manually
- Test files: `test_<module>.py` mirroring source file name
- Effect files: `<effect_name>.py` containing `Effect<Name>` class
- State test files: `test_state_<device>.py` for state management tests

**Directories:**
- `snake_case/`: All directories use snake_case
- `test_<layer>/`: Test directories mirror source structure

**Classes:**
- `PascalCase`: All classes (`Device`, `Light`, `MultiZoneLight`, `DeviceConnection`)
- Device classes: `<Capability>Light` (e.g., `HevLight`, `InfraredLight`, `CeilingLight`)
- Effect classes: `Effect<Name>` (e.g., `EffectFlame`, `EffectAurora`, `EffectPulse`)
- State dataclasses: `<Device>State` (e.g., `LightState`, `MatrixLightState`)
- Exception classes: `Lifx<Domain>Error` (e.g., `LifxTimeoutError`, `LifxProtocolError`)

**Functions/Methods:**
- `snake_case`: All functions and methods
- Async methods: `async def get_<property>()` for volatile state, `async def set_<property>()` for mutations
- Factory methods: `from_ip()`, `connect()`, `create_device()`
- Generator helpers: `for_matrix()`, `for_multizone()`, `for_light()` on Animator

**Constants:**
- `UPPER_SNAKE_CASE`: All constants in `src/lifx/const.py`
- Module-level loggers: `_LOGGER = logging.getLogger(__name__)`
- Class-level packet types: `PKT_TYPE: ClassVar[int]`

## Where to Add New Code

**New Device Type:**
1. Create device class: `src/lifx/devices/<device_type>.py` extending `Light` or `Device`
2. Create state dataclass: `<DeviceType>State` extending `DeviceState` or `LightState`
3. Add detection logic: Update `src/lifx/devices/detection.py` `get_device_class_for_product()`
4. Export from `src/lifx/devices/__init__.py` and `src/lifx/__init__.py`
5. Tests: `tests/test_devices/test_<device_type>.py`

**New Effect:**
1. Create effect file: `src/lifx/effects/<effect_name>.py`
2. Subclass `LIFXEffect` (or `FrameEffect` for animation-based effects)
3. Implement `name` property and `async_play()` method
4. Register in `src/lifx/effects/registry.py` (add to `_BUILTIN_EFFECTS`)
5. Export from `src/lifx/effects/__init__.py` and `src/lifx/__init__.py`
6. Tests: `tests/test_effects/test_<effect_name>.py`

**New Protocol Packet:**
- Do NOT add manually. Update `protocol.yml` source or add to generator quirks in `src/lifx/protocol/generator.py`
- Run `uv run python -m lifx.protocol.generator` to regenerate

**New Product:**
- Do NOT add manually. Run `uv run python -m lifx.products.generator` to regenerate from upstream
- For quirks/overrides: edit `src/lifx/products/quirks.py`

**New Theme:**
- Add to theme library in `src/lifx/theme/library.py`
- Tests: `tests/test_theme/`

**New Utility:**
- Colour utilities: `src/lifx/color.py`
- Constants: `src/lifx/const.py`
- Exceptions: `src/lifx/exceptions.py`

**New Example:**
- Add to `examples/` with descriptive name following pattern: `<category>_<description>.py`

## Special Directories

**`src/lifx/protocol/`:**
- Purpose: Contains both hand-written base code and auto-generated protocol code
- Generated: `packets.py`, `protocol_types.py` (via `generator.py`)
- Committed: Yes (generated files are committed for zero-dependency installs)

**`src/lifx/products/`:**
- Purpose: Product capability database
- Generated: `registry.py` (via `generator.py`)
- Committed: Yes

**`conductor/`:**
- Purpose: Development workflow tracking (tracks, archives, style guides)
- Generated: No (manual)
- Committed: Yes

**`examples/`:**
- Purpose: Runnable usage examples for documentation and developer reference
- Generated: No
- Committed: Yes

**`.github/`:**
- Purpose: GitHub Actions workflows, issue templates
- Generated: No
- Committed: Yes

**`docs/`:**
- Purpose: MkDocs documentation source (served via `mkdocs serve`)
- Generated: No (but `docs/changelog.md` is auto-generated by CI)
- Committed: Yes

---

*Structure analysis: 2026-04-16*
