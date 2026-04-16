---
updated_at: "2026-04-16T00:00:00Z"
---

## Architecture Overview

Layered async library for LIFX smart light control over local UDP. Zero runtime dependencies. Seven distinct layers from binary protocol up to visual effects, each with clear boundaries. Auto-generated protocol and product registry from upstream LIFX specifications.

## Key Components

| Component | Path | Responsibility |
|-----------|------|---------------|
| Protocol Layer | `src/lifx/protocol/` | Auto-generated binary packet types, header, serialiser from YAML spec |
| Network Layer | `src/lifx/network/` | UDP transport, device discovery (broadcast + mDNS), connections, messages |
| Device Layer | `src/lifx/devices/` | Device hierarchy: Device > Light > HevLight/InfraredLight/MultiZone/Matrix/Ceiling |
| High-Level API | `src/lifx/api.py` | Async generators for discovery, batch DeviceGroup ops, find_by helpers |
| Animation Layer | `src/lifx/animation/` | High-frequency frame delivery (30+ FPS), tile orientation, packet templates |
| Effects Layer | `src/lifx/effects/` | 30+ visual effects with registry, conductor orchestration, state management |
| Theme Layer | `src/lifx/theme/` | Named colour palettes, canvas abstraction, per-device-type generators |
| Products Registry | `src/lifx/products/` | Auto-generated product database with capability detection and ceiling quirks |
| Colour Utilities | `src/lifx/color.py` | HSBK class with RGB conversion, colour presets |
| Constants | `src/lifx/const.py` | Network settings, HSBK bounds, URLs, UUID namespaces |
| Exceptions | `src/lifx/exceptions.py` | LifxError hierarchy (8 exception types) |

## Data Flow

UDP Broadcast/mDNS -> discover_devices() -> DiscoveredDevice -> create_device() (product detection) -> Device subclass -> DeviceConnection.request() -> protocol serialise -> UDP send -> UDP receive -> protocol deserialise -> response

Animation path: Effect.generate_frame() -> FrameBuffer (orientation) -> PacketGenerator -> Direct UDP socket (bypasses connection layer for speed)

## Conventions

- **Naming**: Snake_case for modules/functions, PascalCase for classes. Effect classes prefixed with `Effect` (e.g. `EffectFlame`).
- **File organisation**: Source in `src/lifx/`, tests mirror at `tests/test_<layer>/`. `__init__.py` re-exports public API.
- **Import pattern**: All imports at top of file. Internal imports use `lifx.` prefix. `__all__` defined in every `__init__.py`.
- **Auto-generation**: `protocol/packets.py`, `protocol/protocol_types.py`, `products/registry.py` are generated -- never edit manually.
- **Type safety**: Strict Pyright validation. Full type hints throughout. `from __future__ import annotations` in every file.
- **Async pattern**: `async with` context managers for device lifecycle. Async generators for discovery streaming.
- **Zero dependencies**: No runtime deps. Dev deps managed via `[dependency-groups]` in pyproject.toml.
- **State caching**: Semi-static properties cached with configurable TTL; volatile state (power, colour) always fetched fresh.
