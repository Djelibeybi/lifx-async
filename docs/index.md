# lifx-async

A modern, type-safe, async Python library for controlling LIFX lights over the local network.

## Features

- **📦 No Runtime Dependencies**: only Python standard libraries required
- **🎯 Type-Safe**: Full type hints with strict Pyright validation
- **🔌 Async Generators**: Provides `async for` usage pattern
- **⚡ Async Context Managers**: Provides `async with` and `await` usage patterns
- **🔌 Lazy Connections**: Auto-open on first request, explicit cleanup
- **🏗️ Layered Architecture**: Protocol → Network → Device → API
- **🔄 Protocol Generator**: generates LIFX protocol `Packets`, `Fields` and `Enum` classes from LIFX public protocol definition
- **🌈 Comprehensive Support**: supports all LIFX smart lighting products including Color, White, Warm to White, Filament, Clean, Night Vision, Z, Beam, String, Neon, Permanent Outdoor, Tile, Candle, Ceiling, Path, Spot, and Luna.

## Examples

=== "Discovery"

    ```python
    import asyncio
    from lifx import discover, Colors

    async def main():
        # Discover devices asynchronously:
        async for device in discover():
            # Control each device as it is discovered
            await device.set_power(True)
            await device.set_color(Colors.BLUE, duration=1.0)

    asyncio.run(main())
    ```

=== "Direct Connection"

    ```python
    import asyncio
    from lifx import Light, HSBK

    async def main():
        # Connect most efficiently without discovery using serial and IP
        async with Light(serial="d073d5010203", ip="192.168.1.100") as light:
            # Using Light as a context manager auto-populates non-volatile state information
            print(f"{light.label} is a {light.model} at {light.location} in the {light.group} group.")

            await light.set_color(HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500), duration=2.0)

    asyncio.run(main())
    ```

=== "Color Control"

    ```python
    import asyncio
    from lifx import Light, HSBK, Colors

    async def main():
        async with Light(serial="d073d5010203", ip="192.168.1.100") as light:
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

- **Async For** and **Async With**: extensive use of asynchronous generators and context managers
- **Async/Await**: Native asyncio support for concurrent operations
- **Type Hints**: Full type annotations for better IDE support
- **Python 3.11+**: Modern language features and performance

### Reliable

- **Comprehensive Tests**: over 700 tests covering over 90% of the source code
- **Lazy Connections**: Auto-open on first request
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
