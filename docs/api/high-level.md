# High-Level API

The high-level API provides simplified functions for common LIFX operations. These are the
recommended entry points for most users.

## Discovery Functions

::: lifx.api.discover
    options:
      show_root_heading: true
      heading_level: 3

::: lifx.api.find_lights
    options:
      show_root_heading: true
      heading_level: 3

::: lifx.api.find_by_serial
    options:
      show_root_heading: true
      heading_level: 3

## Discovery Context

::: lifx.api.DiscoveryContext
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Device Group

::: lifx.api.DeviceGroup
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Examples

### Simple Discovery

```python
from lifx import discover, Colors


async def main():
    async with discover() as group:
        print(f"Found {len(group.devices)} devices")
        await group.set_power(True)
        await group.set_color(Colors.BLUE)
```

### Find Specific Lights

```python
from lifx import find_lights


async def main():
    # Find all lights with "Kitchen" in the label
    async with find_lights(label_filter="Kitchen") as lights:
        for light in lights:
            await light.set_brightness(0.8)
```

### Find by Serial Number

```python
from lifx import find_by_serial


async def main():
    # Find specific device by serial number
    device = await find_by_serial("d073d5123456")
    if device:
        async with device:
            await device.set_power(True)
```
