# Device Classes

Device classes provide direct control over LIFX devices. All device classes support async context
managers for automatic resource cleanup.

## Base Device

The `Device` class provides common operations available on all LIFX devices.

::: lifx.devices.base.Device
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## Light

The `Light` class provides color control and effects for standard LIFX lights.

::: lifx.devices.light.Light
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## HEV Light

The `HevLight` class extends `Light` with anti-bacterial cleaning cycle control for LIFX HEV devices.

::: lifx.devices.hev.HevLight
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## Infrared Light

The `InfraredLight` class extends `Light` with infrared LED control for night vision on LIFX A19 + Night Vision devices.

::: lifx.devices.infrared.InfraredLight
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## MultiZone Light

The `MultiZoneLight` class controls LIFX strips and beams with multiple color zones.

::: lifx.devices.multizone.MultiZoneLight
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## Matrix Light

The `MatrixLight` class controls LIFX matrix devices (tiles, candle, path) with 2D zone control.

::: lifx.devices.matrix.MatrixLight
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## Device Properties

### MAC Address

The `mac_address` property provides the device's MAC address, calculated from the serial number
and host firmware version. The calculation is performed automatically when the device is used
as a context manager or when `get_host_firmware()` is called.

**Calculation Logic** (based on host firmware major version):

- **Version 2 or 4**: MAC address matches the serial number
- **Version 3**: MAC address is the serial number with the least significant byte incremented by 1 (with wraparound from 0xFF to 0x00)
- **Unknown versions**: Defaults to the serial number

The MAC address is returned in colon-separated lowercase hexadecimal format (e.g., `d0:73:d5:01:02:03`)
to visually distinguish it from the serial number format.

```python
from lifx import Device

async def main():
    async with await Device.from_ip("192.168.1.100") as device:
        # MAC address is automatically calculated during setup
        if device.mac_address:
            print(f"Serial: {device.serial}")
            print(f"MAC:    {device.mac_address}")

        # Returns None before host_firmware is fetched
        assert device.mac_address is not None
```

## Examples

### Basic Light Control

```python
from lifx import Light, Colors


async def main():
    async with await Light.from_ip("192.168.1.100") as light:
        # Turn on and set color
        await light.set_power(True)
        await light.set_color(Colors.BLUE, duration=1.0)

        # Get device info
        label = await light.get_label()
        print(f"Controlling: {label}")
```

### Light Effects

```python
from lifx import Light, Colors


async def main():
    async with await Light.from_ip("192.168.1.100") as light:
        # Pulse effect
        await light.pulse(Colors.RED, period=1.0, cycles=5)

        # Breathe effect
        await light.breathe(Colors.BLUE, period=2.0, cycles=3)
```

### HEV Light Control (Anti-Bacterial Cleaning)

```python
from lifx import HevLight


async def main():
    async with await HevLight.from_ip("192.168.1.100") as light:
        # Start a 2-hour cleaning cycle
        await light.set_hev_cycle(enable=True, duration_seconds=7200)

        # Check cycle status
        state = await light.get_hev_cycle()
        if state.is_running:
            print(f"Cleaning: {state.remaining_s}s remaining")

        # Configure default settings
        await light.set_hev_config(indication=True, duration_seconds=7200)
```

### Infrared Light Control (Night Vision)

```python
from lifx import InfraredLight


async def main():
    async with await InfraredLight.from_ip("192.168.1.100") as light:
        # Set infrared brightness to 50%
        await light.set_infrared(0.5)

        # Get current infrared brightness
        brightness = await light.get_infrared()
        print(f"IR brightness: {brightness * 100}%")
```

### MultiZone Control

```python
from lifx import find_lights, Colors


async def main():
    async with find_lights() as lights:
        for light in lights:
            # Get all zones - automatically uses best method
            colors = await light.get_all_color_zones()
            print(f"Device has {len(colors)} zones")

```

### Tile Control

```python
from lifx import find_lights, HSBK


async def main():
    async with find_lights() as lights:
        for light in lights:
            if light.has_matrix:
                # Set a gradient across the tile
                colors = [
                    HSBK(hue=h, saturation=1.0, brightness=0.5, kelvin=3500)
                    for h in range(0, 360, 10)
                ]
                await light.set_tile_colors(colors)
```
