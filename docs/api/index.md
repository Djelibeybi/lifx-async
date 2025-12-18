# API Reference

Complete reference documentation for lifx-async.

## Module Structure

```
lifx/
├── __init__.py               # High-level API exports
├── api.py                    # Simplified discovery and device group functions
├── color.py                  # Color utilities (HSBK, Colors)
├── const.py                  # Network constants and URLs
├── exceptions.py             # Exception hierarchy
├── devices/                  # Device classes
│   ├── base.py              # Base Device class
│   ├── light.py             # Light device (color control)
│   ├── hev.py               # HevLight device (anti-bacterial cleaning)
│   ├── infrared.py          # InfraredLight device (night vision)
│   ├── multizone.py         # MultiZoneLight (strips/beams)
│   └── matrix.py            # MatrixLight (2D matrix devices: tiles, candle, path)
├── network/                  # Network layer
│   ├── connection.py        # Device connections with lazy opening
│   ├── discovery.py         # Network device discovery (UDP broadcast)
│   ├── message.py           # Message building and parsing
│   ├── transport.py         # UDP transport
│   └── mdns/                # mDNS/DNS-SD discovery
│       ├── discovery.py     # mDNS discovery functions
│       ├── dns.py           # DNS wire format parser
│       ├── transport.py     # Multicast UDP transport
│       └── types.py         # LifxServiceRecord dataclass
├── products/                 # Product registry
│   ├── registry.py          # Auto-generated product database
│   ├── generator.py         # Generator to download/parse products.json
│   └── __init__.py          # Public API exports
└── protocol/                 # Protocol layer (auto-generated)
    ├── base.py              # Base packet class
    ├── generator.py         # Code generator from protocol.yml
    ├── header.py            # Protocol header (36 bytes)
    ├── models.py            # Protocol models (Serial, HEV types)
    ├── packets.py           # Packet definitions
    ├── protocol_types.py    # Type definitions and enums
    └── serializer.py        # Binary serialization/deserialization
```

## Quick Reference

### High-Level API

Main entry points for most users:

- [`discover()`](high-level.md#lifx.api.discover) - Device discovery via UDP broadcast
- [`discover_mdns()`](high-level.md#lifx.api.discover_mdns) - Device discovery via mDNS (faster)
- [`find_by_serial()`](high-level.md#lifx.api.find_by_serial) - Find device by serial number
- [`find_by_label()`](high-level.md#lifx.api.find_by_label) - Find devices by label (exact or substring)
- [`find_by_ip()`](high-level.md#lifx.api.find_by_ip) - Find device by IP address
- [`DeviceGroup`](high-level.md#lifx.api.DeviceGroup) - Batch operations

### Device Classes

Control your LIFX devices:

- [`Device`](devices.md#lifx.devices.base.Device) - Base device operations
- [`Light`](devices.md#lifx.devices.light.Light) - Color control
- [`HevLight`](devices.md#lifx.devices.hev.HevLight) - Anti-bacterial cleaning cycles
- [`InfraredLight`](devices.md#lifx.devices.infrared.InfraredLight) - Night vision infrared LED
- [`MultiZoneLight`](devices.md#lifx.devices.multizone.MultiZoneLight) - Strips/beams
- [`MatrixLight`](devices.md#lifx.devices.matrix.MatrixLight) - 2D matrix devices (tiles, candle, path)

### Color Utilities

Work with colors:

- [`HSBK`](colors.md#lifx.color.HSBK) - Color representation
- [`Colors`](colors.md#lifx.color.Colors) - Built-in presets

### Network Layer

Low-level network operations:

- [`discover_devices()`](network.md#lifx.network.discovery.discover_devices) - Low-level UDP discovery
- [`discover_lifx_services()`](network.md#lifx.network.mdns.discover_lifx_services) - Low-level mDNS discovery
- [`LifxServiceRecord`](network.md#lifx.network.mdns.LifxServiceRecord) - mDNS service record
- [`DeviceConnection`](network.md#lifx.network.connection.DeviceConnection) - Device connections

### Products Registry

Device capabilities and automatic type detection:

- [`ProductInfo`](protocol.md#lifx.products.ProductInfo) - Product information
- [`ProductCapability`](protocol.md#lifx.products.ProductCapability) - Device capabilities

### Exceptions

Error handling:

- [`LifxError`](exceptions.md#lifx.exceptions.LifxError) - Base exception
- [`LifxTimeoutError`](exceptions.md#lifx.exceptions.LifxTimeoutError) - Timeout errors
- [`LifxConnectionError`](exceptions.md#lifx.exceptions.LifxConnectionError) - Connection errors

## Usage Patterns

### Async Context Managers

All device classes support async context managers for automatic resource cleanup:

```python
async with await Light.from_ip("192.168.1.100") as light:
    await light.set_color(Colors.BLUE)
# Connection automatically closed
```

### Batch Operations

Use `DeviceGroup` for efficient batch operations:

```python
from lifx import discover, DeviceGroup, Colors

devices = []
async for device in discover():
    devices.append(device)

group = DeviceGroup(devices)
await group.set_power(True)
await group.set_color(Colors.BLUE)
```

### Connection Lifecycle

Connections open lazily on first request and reuse the same socket:

```python
# Multiple operations reuse the same connection
async with await Light.from_ip("192.168.1.100") as light:
    await light.set_color(Colors.RED)
    await light.set_brightness(0.5)
    await light.get_label()
# Connection automatically closed on exit
```

### Concurrent Requests

Devices support concurrent requests via asyncio.gather:

```python
# Execute multiple operations concurrently
async with await Light.from_ip("192.168.1.100") as light:
    # Note: get_color() returns (color, power, label) tuple
    (color, power, label), version = await asyncio.gather(
        light.get_color(),
        light.get_version()
    )
    brightness = color.brightness
    print(f"{label}: Brightness={brightness}, Firmware={version.firmware}")
```

## Type Hints

lifx-async is fully type-hinted. Use a type checker like Pyright or mypy:

```python
from lifx import Light, HSBK


async def set_custom_color(light: Light, hue: float) -> None:
    color: HSBK = HSBK(hue=hue, saturation=1.0, brightness=0.8, kelvin=3500)
    await light.set_color(color)
```

## API Sections

<div class="grid cards" markdown>

- :material-api:{ .lg .middle } __High-Level API__

  ______________________________________________________________________

  Simple, batteries-included API for common tasks

  [:octicons-arrow-right-24: High-Level API](high-level.md)

- :material-lightbulb:{ .lg .middle } __Device Classes__

  ______________________________________________________________________

  Control LIFX lights, strips, tiles, and matrix devices

  [:octicons-arrow-right-24: Devices](devices.md)

- :material-palette:{ .lg .middle } __Color Utilities__

  ______________________________________________________________________

  Work with colors, RGB, and HSBK

  [:octicons-arrow-right-24: Colors](colors.md)

- :material-network:{ .lg .middle } __Network Layer__

  ______________________________________________________________________

  Low-level network operations

  [:octicons-arrow-right-24: Network](network.md)

- :material-code-braces:{ .lg .middle } __Protocol Layer__

  ______________________________________________________________________

  Auto-generated protocol structures

  [:octicons-arrow-right-24: Protocol](protocol.md)

- :material-alert:{ .lg .middle } __Exceptions__

  ______________________________________________________________________

  Error handling and exception hierarchy

  [:octicons-arrow-right-24: Exceptions](exceptions.md)

</div>

## Best Practices

### Always Use Context Managers

```python
# ✅ Good - automatic cleanup
async with await Light.from_ip("192.168.1.100") as light:
    await light.set_color(Colors.BLUE)

# ❌ Bad - manual cleanup required
light = Light("d073d5123456", "192.168.1.100")
await light.connect()
await light.set_color(Colors.BLUE)
await light.disconnect()
```

### Handle Exceptions

```python
from lifx import discover, Colors, LifxError

try:
    async for device in discover():
        await device.set_color(Colors.GREEN)
except LifxError as e:
    print(f"LIFX error: {e}")
```

### Use Type Hints

```python
from lifx import Light, HSBK


async def control_light(light: Light) -> str:
    label: str = await light.get_label()
    return label
```

## Further Reading

- [Architecture](../architecture/overview.md) - How lifx-async works
- [FAQ](../faq.md) - Frequently asked questions
