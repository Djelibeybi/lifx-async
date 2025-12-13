# High-Level API

The high-level API provides simplified functions for common LIFX operations. These are the
recommended entry points for most users.

## Discovery Functions

::: lifx.api.discover
    options:
      show_root_heading: true
      heading_level: 3

::: lifx.api.find_by_serial
    options:
      show_root_heading: true
      heading_level: 3

::: lifx.api.find_by_label
    options:
      show_root_heading: true
      heading_level: 3

::: lifx.api.find_by_ip
    options:
      show_root_heading: true
      heading_level: 3

## Device Group

::: lifx.api.DeviceGroup
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Organizational Groupings

Dataclasses for organizing devices by location or group. Returned by `DeviceGroup.organize_by_location()` and `DeviceGroup.organize_by_group()`.

### LocationGrouping

Location-based device grouping returned by `DeviceGroup.organize_by_location()`.

::: lifx.api.LocationGrouping
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### GroupGrouping

Group-based device grouping returned by `DeviceGroup.organize_by_group()`.

::: lifx.api.GroupGrouping
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Examples

### Simple Discovery

```python
from lifx import discover, DeviceGroup, Colors


async def main():
    count: int = 0
    async for device in discover():
        count += 1
        await device.set_power(True)
        await device.set_color(Colors.BLUE)

    print(f"Found {count} devices")

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

### Find by Label

```python
from lifx import find_by_label, Colors


async def main():
    # Find all devices with "Living" in the label (substring match)
    async for device in find_by_label("Living"):  # May match "Living Room", "Living Area", etc.

        await device.set_power(True)

    # Find device with exact label match
    async for device in find_by_label("Living Room", exact_match=True):
        await device.set_color(Colors.WARM_WHITE)
        break  # exact_match returns at most one device
```

### Find by IP Address

```python
from lifx import find_by_ip


async def main():
    # Find device at specific IP address
    device = await find_by_ip("192.168.1.100")
    if device:
        async with device:
            await device.set_power(True)
```
