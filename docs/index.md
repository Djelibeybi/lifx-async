# lifx-async

A modern, type-safe, async Python library for controlling LIFX lights over the local network.

## Features

- **📦 No Runtime Dependencies**: only Python standard libraries required
- **🎯 Type-Safe**: Full type hints with strict Pyright validation
- **⚡ Async Context Managers**: Provides `async with` and `await` usage patterns
- **🔌 Connection Pooling**: Efficient reuse with LRU cache
- **🏗️ Layered Architecture**: Protocol → Network → Device → API
- **🔄 Protocol Generator**: generates LIFX protocol `Packets`, `Fields` and `Enum` classes from LIFX public protocol definition
- **🌈 Comprehensive Support**: supports all LIFX smart lighting products including Color, White, Warm to White, Filament, Clean, Night Vision, Z, Beam, String, Neon, Permanent Outdoor, Tile, Candle, Ceiling, Path, Spot, and Luna.

## Examples

=== "Discovery"

    ```python
    import asyncio
    from lifx import discover, Colors

    async def main():
        # Discover all devices with automatic connection management
        async with discover(timeout=3.0) as group:
            if not group:
                print("No LIFX devices found!")
                return

            # Control all devices at once
            await group.set_power(True)
            await group.set_color(Colors.BLUE, duration=1.0)
            await group.set_brightness(0.5)

            # Or control individual devices
            for device in group:
                label = await device.get_label()
                print(f"Controlling: {label}")

    asyncio.run(main())
    ```

=== "Direct Connection"

    ```python
    import asyncio
    from lifx import Light, Colors

    async def main():
        # Connect directly without discovery
        async with await Light.from_ip(ip="192.168.1.100") as light:
            await light.set_color(Colors.RED)
            await light.set_brightness(0.8, duration=2.0)

    asyncio.run(main())
    ```

=== "Color Control"

    ```python
    import asyncio
    from lifx import Light, HSBK, Colors

    async def main():
        async with await Light.from_ip(ip="192.168.1.100") as light:
            # Use RGB
            red = HSBK.from_rgb(255, 0, 0)
            await light.set_color(red)

            # Use presets
            await light.set_color(Colors.WARM_WHITE)

            # Custom HSBK
            custom = HSBK(
                hue=180,         # 0-360 degrees
                saturation=0.7,  # 0.0-1.0
                brightness=0.8,  # 0.0-1.0
                kelvin=3500,     # 1500-9000
            )
            await light.set_color(custom)

    asyncio.run(main())
    ```

## Installation

```bash
# Using uv (recommended)
uv pip install lifx-async

# Or using pip
pip install lifx-async
```

For development:

```bash
git clone https://github.com/Djelibeybi/lifx-async.git
cd lifx
uv sync
```

## Why lifx-async?

### Modern Python

- **Async With**: extensive use of async context managers
- **Async/Await**: Native asyncio support for concurrent operations
- **Type Hints**: Full type annotations for better IDE support
- **Python 3.11+**: Modern language features and performance

### Reliable

- **Comprehensive Tests**: over 500 tests covering over 80% of the source code
- **Connection Pooling**: Efficient connection reuse
- **Stores State**: Reduces network traffic

### Developer Friendly

- **Clear API**: Intuitive, Pythonic interface
- **Rich Documentation**: Extensive guides and examples
- **Code Generation**: Protocol updates are automatic
- **No External Dependencies**: Only Python standard libraries required

## Support

- **Documentation**: [https://lifx.readthedocs.io](https://lifx.readthedocs.io)
- **Issues**: [GitHub Issues](https://github.com/Djelibeybi/lifx-async/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Djelibeybi/lifx-async/discussions)

## License

Universal Permissive License 1.0 - see [LICENSE](https://github.com/Djelibeybi/lifx-async/blob/main/LICENSE) for details.
