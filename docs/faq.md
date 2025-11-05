# Frequently Asked Questions

## General

### What is lifx-async?

lifx-async is a modern, async Python library for controlling LIFX smart lighting devices over your local
network. It provides a type-safe, high-performance interface for device discovery, color control,
effects, and more.

### Which devices are supported?

lifx-async supports all LIFX lighting products:

- **Light**: A19, BR30, Downlight, etc.
- **HEV**: Clean
- **Infrared**: Nightvision
- **Multizone**: LIFX Z, Beam, Neon, String
- **Matrix**: LIFX Tile, Candle, Ceiling, Path, Spot

Button and Relay devices are not currently supported (they are out of scope for this
lighting-focused library).

### Do I need cloud access?

No! lifx-async communicates directly with devices over your local network. No cloud connection or LIFX
account required.

### What Python versions are supported?

Python 3.11 or higher is required.

## Installation & Setup

### How do I install lifx-async?

```bash
# Using uv (recommended)
uv pip install lifx-async

# Or using pip
pip install lifx-async
```

See the [Installation Guide](getting-started/installation.md) for more options.

### Why can't discovery find my devices?

Common issues:

1. **Same Network**: Ensure your computer and LIFX devices are on the same network
1. **Firewall**: Check firewall settings allow UDP broadcasts
1. **Timeout**: Try increasing timeout: `discover(timeout=10.0)`
1. **Router**: Some routers block broadcast packets - try direct connection

**Workaround** - Connect directly by IP:

```python
async with await Light.from_ip("192.168.1.100") as light:
    await light.set_color(Colors.BLUE)
```

### Do I need to know my device's IP address?

No! Discovery finds devices automatically:

```python
async with discover() as group:
    # All devices found automatically
    await group.set_color(Colors.BLUE)
```

If you do know the IP, you can connect directly for faster connection.

## Usage

### How do I control multiple lights at once?

Use the `DeviceGroup` returned by `discover()` for batch operations:

```python
from lifx import discover, Colors

async with discover() as group:
    # All lights at once
    await group.set_power(True)
    await group.set_color(Colors.BLUE)
    await group.set_brightness(0.5)
```

### How do I set a specific RGB color?

Use `HSBK.from_rgb()`:

```python
from lifx import HSBK

# Create color from RGB (0-255)
purple = HSBK.from_rgb(128, 0, 128)
await light.set_color(purple)

# Or use hex
color = HSBK.from_rgb(0xFF, 0x00, 0xFF)
```

### Can I control lights concurrently?

Yes! Use `asyncio.gather()`:

```python
import asyncio

# Control multiple lights in parallel
await asyncio.gather(
    light1.set_color(Colors.RED),
    light2.set_color(Colors.GREEN),
    light3.set_color(Colors.BLUE),
)
```

### How do I find a specific device?

By label:

```python
lights = await find_lights(label_contains="Bedroom")
```

By serial number:

```python
device = await find_by_serial("d073d5123456")
```

### What are the available color presets?

See [`Colors`](api/colors.md#lifx.color.Colors) for the complete list:

```python
from lifx import Colors

# Primary colors
Colors.RED, Colors.GREEN, Colors.BLUE

# White variants
Colors.WARM_WHITE, Colors.COOL_WHITE, Colors.DAYLIGHT

# Pastels
Colors.PASTEL_BLUE, Colors.PASTEL_PINK
```

### How do I create smooth transitions?

Use the `duration` parameter (in seconds):

```python
# Fade to blue over 2 seconds
await light.set_color(Colors.BLUE, duration=2.0)

# Fade brightness over 3 seconds
await light.set_brightness(0.5, duration=3.0)
```

### Can I create pulsing effects?

Yes! Use the `pulse()` or `breathe()` methods:

```python
# Pulse red 5 times
await light.pulse(Colors.RED, period=1.0, cycles=5)

# Breathe blue infinitely
await light.breathe(Colors.BLUE, period=2.0, cycles=0)
```

## Performance

### Is lifx-async fast?

Yes! Key performance features:

- **Async I/O**: Non-blocking operations
- **Connection Pooling**: Reuses connections (LRU cache)
- **Rate Limiting**: Prevents overwhelming devices (20 msg/sec)
- **State Caching**: Reduces redundant network requests
- **Concurrent Requests**: Multiple requests per connection

### How is state stored?

Device properties return `(value, timestamp)` tuples with the timestamp reflecting
when the value was last retrieved from the device. This gives you explicit
control over data freshness:

```python
import time

# Check current stored state
state = light.color
if state:
    color, timestamp = state
    age = time.time() - timestamp
    if age < 5.0:  # Use stored value if less than 5 seconds old
        # Use state color
    else:
        # Data is stale, fetch fresh
        color, _, _ = await light.get_color()
else:
    # Ignore state, fetch from device
    color, _, _ = await light.get_color()
```

To always get fresh data:

```python
# Use get_* methods to always fetch from device
# get_color() returns all three values in one call
color, power, label = await light.get_color()  # Returns (color, power, label)

# Or fetch specific info separately
version = await light.get_version()  # Get firmware and hardware version
```

### Can I control devices from multiple computers?

Yes! lifx-async doesn't require exclusive access. Multiple instances (even on different computers) can
control the same devices.

## Troubleshooting

### I get `LifxTimeoutError`

Common causes:

1. **Device offline**: Check device is powered and connected
1. **Network issues**: Verify network connectivity
1. **Firewall**: Ensure UDP port 56700 is open
1. **Timeout too short**: Increase timeout value

### Connection fails with `LifxConnectionError`

Try:

1. **Restart device**: Power cycle the LIFX device
1. **Check IP**: Verify IP address is correct
1. **Firewall**: Check firewall allows UDP 56700
1. **Network**: Ensure same subnet

### Effects don't work as expected

Make sure you're using the correct duration/period values:

```python
# Period is in seconds
await light.pulse(Colors.RED, period=1.0, cycles=5)

# Duration is in seconds (milliseconds * 1000)
await light.set_color(Colors.BLUE, duration=2.0)
```

### Type checker errors

lifx-async is fully type-hinted. If you get type errors:

1. Ensure you're using Python 3.11+
1. Update your type checker (Pyright, mypy)
1. Check you're using correct types

## Development

### How do I contribute?

Quick start:

1. Fork the repository
1. Create a feature branch
1. Make your changes with tests
1. Submit a pull request

### How do I run tests?

```bash
uv run --frozen pytest
```

### How do I generate protocol code?

```bash
uv run python -m lifx.protocol.generator
```

This downloads the latest `protocol.yml` from LIFX and regenerates Python code.

### Where is the protocol specification?

The official LIFX protocol specification is at:
https://github.com/LIFX/public-protocol/blob/main/protocol.yml

lifx-async automatically downloads and generates Python code from this specification.

## Advanced

### Can I use lifx-async without async?

No.

### How do I access low-level protocol?

```python
from lifx.protocol.packets import Light
from lifx.protocol.protocol_types import HSBK

# Create a packet directly
packet = Light.SetColor(
    color=HSBK(hue=180, saturation=1.0, brightness=0.8, kelvin=3500), duration=1.0
)

# Send via connection
async with DeviceConnection(serial, ip) as conn:
    reply = await conn.request(packet)
```

### How does connection pooling work?

lifx-async maintains an LRU cache of connections. When you open a connection to a device, it's
automatically pooled and reused for subsequent operations. Connections are evicted when the cache is
full (default maximum: 100 connections).

## Still have questions?

- **Documentation**: Browse the [API Reference](api/index.md)
- **Issues**: Report bugs on [GitHub Issues](https://github.com/Djelibeybi/lifx-async/issues)
- **Discussions**: Ask questions in
  [GitHub Discussions](https://github.com/Djelibeybi/lifx-async/discussions)
