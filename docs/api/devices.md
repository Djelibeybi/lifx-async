# Device Classes

Device classes provide direct control over LIFX devices. All device classes support async context
managers for automatic resource cleanup.

## State and Info Classes

Device state and information dataclasses returned by device methods.

### DeviceState

Base device state dataclass returned by `Device.state`.

::: lifx.devices.base.DeviceState
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### DeviceVersion

Device version information returned by `Device.get_version()`.

::: lifx.devices.base.DeviceVersion
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### DeviceInfo

Device runtime information returned by `Device.get_info()`.

::: lifx.devices.base.DeviceInfo
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### WifiInfo

WiFi module information returned by `Device.get_wifi_info()`, including the
firmware-aware `rssi_unit` (`dB` through firmware 2.77, otherwise `dBm`).

Also available as `device.state.wifi_info`. Neither state initialisation nor
`refresh_state()` queries the device for WiFi signal strength unless the device
was created with `fetch_wifi_info=True`, so `signal` and `rssi` are `None` by
default while `rssi_unit` is always populated from the host firmware version:

```python
device = await Device.connect(ip="192.168.1.100", fetch_wifi_info=True)
async with device:
    print(f"{device.state.wifi_info.rssi} {device.state.wifi_info.rssi_unit}")
```

When enabled, the query joins the same parallel batch as the other state
requests, so it costs no extra round trip.

`fetch_wifi_info` is also a settable property, so a device can start or stop
collecting readings at any point. It takes effect from the next state
initialisation or refresh:

```python
async with await Device.connect(ip="192.168.1.100") as device:
    device.fetch_wifi_info = True
    await device.refresh_state()
    print(device.state.wifi_info.rssi)

    device.fetch_wifi_info = False  # stop collecting
```

Turning it off is equally immediate: the next refresh stores `None` for
`signal` and `rssi` rather than leaving the last reading behind a freshly
stamped `last_updated`.

For a one-off reading, call `get_wifi_info()` directly — it is a single
request, where a refresh also re-fetches colour, power, label and every zone or
tile:

```python
async with await Device.connect(ip="192.168.1.100") as device:
    wifi_info = await device.get_wifi_info()
    print(f"{wifi_info.rssi} {wifi_info.rssi_unit}")
```

::: lifx.devices.base.WifiInfo
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### FirmwareInfo

Firmware version information returned by `Device.get_host_firmware()` and `Device.get_wifi_firmware()`.

::: lifx.devices.base.FirmwareInfo
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### CollectionInfo

Location and group collection information returned by `Device.get_location()` and `Device.get_group()`.

::: lifx.devices.base.CollectionInfo
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### DeviceCapabilities

Device capabilities from product registry, available via `Device.capabilities`.

::: lifx.devices.base.DeviceCapabilities
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

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

### LightState

Light device state dataclass returned by `Light.state`.

`ambient_light` holds the most recent lux reading, `-1.0` when that reading was
taken while the light was on (the sensor measures the light's own output, not
the room), or `None` when the sensor was not queried. Like `wifi_info`, it is
only fetched when the device was created with `fetch_ambient_light=True`, or
once the `fetch_ambient_light` property is set on the device:

```python
light = await Device.connect(ip="192.168.1.100", fetch_ambient_light=True)
async with light:
    print(f"Ambient light: {light.state.ambient_light} lux")

    light.fetch_ambient_light = False  # stop collecting
```

::: lifx.devices.light.LightState
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

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

### HevLightState

HEV light device state dataclass returned by `HevLight.state`.

::: lifx.devices.hev.HevLightState
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

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

### InfraredLightState

Infrared light device state dataclass returned by `InfraredLight.state`.

::: lifx.devices.infrared.InfraredLightState
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

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

### MultiZoneLightState

MultiZone light device state dataclass returned by `MultiZoneLight.state`.

::: lifx.devices.multizone.MultiZoneLightState
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### MultiZoneEffect

Configuration dataclass for multizone effects (MOVE). Used with `MultiZoneLight.set_effect()` and returned by `MultiZoneLight.get_effect()`.

::: lifx.devices.multizone.MultiZoneEffect
    options:
      show_root_heading: true
      heading_level: 4
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

### MatrixLightState

Matrix light device state dataclass returned by `MatrixLight.state`.

::: lifx.devices.matrix.MatrixLightState
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### TileInfo

Information dataclass for a single tile in the device chain. Returned as part of `MatrixLightState.chain`.

::: lifx.devices.matrix.TileInfo
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

### MatrixEffect

Configuration dataclass for matrix effects (MORPH, FLAME, SKY). Used with `MatrixLight.set_effect()` and returned by `MatrixLight.get_effect()`.

SKY requires the matrix capability plus host firmware 4.x or later — confirmed on Ceiling, Luna, Tube, Path and the E26 Candle. Check with `await matrix.supports_sky_effect()`; `set_effect()` raises `LifxUnsupportedCommandError` when either requirement is unmet.

::: lifx.devices.matrix.MatrixEffect
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## Ceiling Light

The `CeilingLight` class extends `MatrixLight` with independent control over uplight and downlight components for LIFX Ceiling fixtures.

::: lifx.devices.ceiling.CeilingLight
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

### CeilingLightState

The `CeilingLightState` dataclass extends `MatrixLightState` with ceiling-specific component information. It is returned by `CeilingLight.state` after connecting to a device.

::: lifx.devices.ceiling.CeilingLightState
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## Device Properties

### MAC Address

The `mac_address` property provides the device's MAC address, calculated from the serial number
and host firmware version. The calculation is performed automatically when the device is used
as a context manager or when `get_host_firmware()` is called.

**Calculation Logic** (based on the host firmware major *and* minor version):

- **Firmware 3.70 and above, below 4.0**: MAC address is the serial number with the least significant byte incremented by 1 (with wraparound from 0xFF to 0x00)
- **Every other firmware** — including earlier 3.x builds such as 3.50, verified against LIFX Tiles whose real MAC matched their serial — MAC address matches the serial number

Both version components are compared as integers, so firmware 3.9 is *below* the 3.70
boundary, not above it: reading the version as a decimal misclassifies it.

Devices never report their MAC on the wire and are always addressed by serial, so this value is
a convenience derivation only. It is recalculated whenever `get_host_firmware()` reports a
different firmware version, so it stays consistent with the rule above after an update.

The MAC address is returned in colon-separated lowercase hexadecimal format (e.g., `d0:73:d5:01:02:03`)
to visually distinguish it from the serial number format.

```python
from lifx import Device

async def main():
    async with await Device.connect("192.168.1.100") as device:
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
from lifx import Colors, Device


async def main():
    async with await Device.connect("192.168.1.100") as light:
        # Turn on and set color
        await light.set_power(True)
        await light.set_color(Colors.BLUE, duration=1.0)

        # Get device info
        label = await light.get_label()
        print(f"Controlling: {label}")
```

### Light Effects

```python
from lifx import Colors, Device


async def main():
    async with await Device.connect("192.168.1.100") as light:
        # Pulse effect
        await light.pulse(Colors.RED, period=1.0, cycles=5)

        # Breathe effect
        await light.breathe(Colors.BLUE, period=2.0, cycles=3)
```

### HEV Light Control (Anti-Bacterial Cleaning)

```python
from lifx import Device, HevLight


async def main():
    async with await Device.connect("192.168.1.100") as light:
        assert isinstance(light, HevLight)
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
from lifx import Device, InfraredLight


async def main():
    async with await Device.connect("192.168.1.100") as light:
        assert isinstance(light, InfraredLight)
        # Set infrared brightness to 50%
        await light.set_infrared(0.5)

        # Get current infrared brightness
        brightness = await light.get_infrared()
        print(f"IR brightness: {brightness * 100}%")
```

### Ambient Light Sensor

Light devices with ambient light sensors can measure the current ambient light level in lux:

```python
from lifx import Device


async def main():
    async with await Device.connect("192.168.1.100") as light:
        # Ensure light is off for accurate reading
        await light.set_power(False)

        # Get ambient light level in lux
        lux = await light.get_ambient_light_level()
        if lux > 0:
            print(f"Ambient light: {lux} lux")
        else:
            print("No ambient light sensor or completely dark")
```

The sensor can also be read as part of state instead of on demand. A light
created with `fetch_ambient_light=True` — or one that has the property set later
— queries it during state initialisation and on every `refresh_state()`, storing
the result in `state.ambient_light`:

```python
async with await Device.connect(ip="192.168.1.100") as light:
    light.fetch_ambient_light = True

    await light.refresh_state()
    print(f"Ambient light: {light.state.ambient_light} lux")

    light.fetch_ambient_light = False  # stop collecting
```

The query joins the same parallel batch as the other state requests, so it costs
no extra round trip. Toggling the property takes effect from the next state
initialisation or refresh: turning it off stores `None` rather than leaving the
last reading behind a freshly stamped `last_updated`.

**Notes:**

- Every product answers packet 401, so the query never fails on an unsupported device — it returns 0.0
- **A reading of 0.0 is ambiguous**: no sensor, a sensor the device cannot read, and complete darkness all report 0.0, and nothing in the response or the product registry distinguishes them
- `state.ambient_light` is captured whenever state refreshes, including the debounced refresh that follows `set_power()`/`set_color()`. A reading taken while the light is on measures the light's own output, so it is stored as `-1.0` (`lifx.INVALID_AMBIENT_LIGHT_RESPONSE`) rather than as a plausible-looking lux value
- For accurate readings, the light should be turned off (otherwise the light's own illumination interferes with the sensor)
- `get_ambient_light_level()` always fetches fresh from the device; `state.ambient_light` is as fresh as the last state refresh, and is `None` until the sensor is queried at least once
- If a request does fail outright, `state.ambient_light` is left `None` and a warning is logged — state initialisation and refresh still succeed
- Returns ambient light level in lux (higher values indicate brighter ambient light)

### MultiZone Control

```python
from lifx import Colors, Device, Direction, FirmwareEffect, MultiZoneLight


async def main():
    async with await Device.connect("192.168.1.100") as light:
        assert isinstance(light, MultiZoneLight)
        # Get all zones - automatically uses best method
        colors = await light.get_all_color_zones()
        print(f"Device has {len(colors)} zones")

        # Write zones back the same way. set_all_color_zones picks the
        # extended or legacy packet based on device capabilities, chunks
        # past the 82-colour extended packet limit, and run-length encodes
        # legacy writes, so it works on any strip or beam.
        colors[0] = Colors.RED
        await light.set_all_color_zones(colors, duration=1.0)

        # Only write part of the strip: zones outside start..end keep
        # whatever they were showing.
        await light.set_all_color_zones(colors, start=10, end=19)

        # Set a MOVE effect
        await light.set_effect(
            effect_type=FirmwareEffect.MOVE,
            speed=5.0,  # seconds per cycle
            direction=Direction.FORWARD,
        )

        # Get current effect
        effect = await light.get_effect()
        print(f"Effect: {effect.effect_type.name}")
        if effect.effect_type == FirmwareEffect.MOVE:
            print(f"Direction: {effect.direction.name}")

        # Stop the effect
        await light.set_effect(effect_type=FirmwareEffect.OFF)
```

### Tile Control

```python
from lifx import HSBK, Device, FirmwareEffect, MatrixLight


async def main():
    async with await Device.connect("192.168.1.100") as light:
        assert isinstance(light, MatrixLight)
        # Set a gradient across the tile
        colors = [
            HSBK(hue=h, saturation=1.0, brightness=0.5, kelvin=3500)
            for h in range(0, 360, 10)
        ]
        await light.set_tile_colors(colors)

        # Set a tile effect (MORPH, FLAME, or SKY)
        await light.set_effect(
            effect_type=FirmwareEffect.FLAME,
            speed=5.0,  # seconds per cycle
        )

        # Get current effect
        effect = await light.get_effect()
        print(f"Tile effect: {effect.effect_type.name}")

        # Stop the effect
        await light.set_effect(effect_type=FirmwareEffect.OFF)
```

### Ceiling Light Control

```python
from lifx import HSBK, CeilingLight, Device


async def main():
    async with await Device.connect("192.168.1.100") as ceiling:
        assert isinstance(ceiling, CeilingLight)
        # Set downlight to warm white
        await ceiling.set_downlight_colors(
            HSBK(hue=0, saturation=0, brightness=0.8, kelvin=3000)
        )

        # Set uplight to a dim ambient glow
        await ceiling.set_uplight_color(
            HSBK(hue=30, saturation=0.2, brightness=0.3, kelvin=2700)
        )

        # Turn uplight off (stores color for later restoration)
        await ceiling.turn_uplight_off()

        # Turn uplight back on (restores previous color)
        await ceiling.turn_uplight_on()

        # Check component state
        if ceiling.downlight_is_on:
            print("Downlight is currently on")
```

For detailed CeilingLight usage, see the [Ceiling Lights User Guide](../user-guide/ceiling-lights.md).
