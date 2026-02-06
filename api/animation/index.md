# Animation Module

The animation module provides efficient high-frequency frame delivery for LIFX devices, optimized for real-time effects and applications that need to push color data at 30+ FPS.

## Overview

The animation system uses a streamlined architecture optimized for speed:

```text
Application Frame -> FrameBuffer -> PacketGenerator -> Direct UDP
                     (canvas map)   (prebaked packets)  (fire-and-forget)
```

Key features:

- **Direct UDP**: Bypasses connection layer for maximum throughput
- **Prebaked packets**: Templates created once, only colors updated per frame
- **Multi-tile canvas**: Unified coordinate space for multi-tile devices
- **Tile orientation**: Automatic pixel remapping for rotated tiles
- **Synchronous sending**: `send_frame()` is synchronous for minimum overhead

## Quick Start

```python
import asyncio
from lifx import Animator, MatrixLight

async def main():
    async with await MatrixLight.from_ip("192.168.1.100") as device:
        # Create animator for matrix device
        animator = await Animator.for_matrix(device)

    # Device connection closed - animator sends via direct UDP
    try:
        while True:
            # Generate HSBK frame (protocol-ready uint16 values)
            # H/S/B: 0-65535, K: 1500-9000
            hsbk_frame = [(65535, 65535, 65535, 3500)] * animator.pixel_count

            # send_frame() is synchronous for speed
            stats = animator.send_frame(hsbk_frame)
            print(f"Sent {stats.packets_sent} packets in {stats.total_time_ms:.2f}ms")

            await asyncio.sleep(1 / 30)  # 30 FPS
    finally:
        animator.close()
```

## Multi-Tile Canvas

For devices with multiple tiles (like the original 5-tile LIFX Tile), the animator creates a unified canvas based on tile positions (`user_x`, `user_y`). Animations span all tiles as one continuous image.

```python
async with await MatrixLight.from_ip("192.168.1.100") as device:
    animator = await Animator.for_matrix(device)

# Check canvas dimensions
print(f"Canvas: {animator.canvas_width}x{animator.canvas_height}")
# For 5 horizontal tiles: "Canvas: 40x8"

# Generate frame for entire canvas (row-major order)
frame = []
for y in range(animator.canvas_height):
    for x in range(animator.canvas_width):
        hue = int(x / animator.canvas_width * 65535)  # Gradient across all tiles
        frame.append((hue, 65535, 65535, 3500))

animator.send_frame(frame)
```

## HSBK Format

All color data uses protocol-ready uint16 values:

| Component  | Range     | Description           |
| ---------- | --------- | --------------------- |
| Hue        | 0-65535   | Maps to 0-360 degrees |
| Saturation | 0-65535   | Maps to 0.0-1.0       |
| Brightness | 0-65535   | Maps to 0.0-1.0       |
| Kelvin     | 1500-9000 | Color temperature     |

This design pushes conversion work to the caller (e.g. using NumPy) for better performance. The `lifx-async` library remains dependency-free.

```python
# Red at full brightness
red = (0, 65535, 65535, 3500)

# 50% brightness warm white
warm_white = (0, 0, 32768, 2700)

# Convert from user-friendly values
def to_protocol_hsbk(
    hue: float, sat: float, bright: float, kelvin: int
) -> tuple[int, int, int, int]:
    """Convert user-friendly values to protocol format."""
    return (
        int(hue / 360 * 65535),
        int(sat * 65535),
        int(bright * 65535),
        kelvin,
    )
```

## Animator

High-level class integrating all animation components.

### Animator

```python
Animator(
    ip: str,
    serial: Serial,
    framebuffer: FrameBuffer,
    packet_generator: PacketGenerator,
    port: int = LIFX_UDP_PORT,
)
```

High-level animator for LIFX devices.

Sends animation frames directly via UDP for maximum throughput. No connection layer, no ACKs, no waiting - just fire packets as fast as possible.

All packets are prebaked at initialization time. Per-frame, only color data and sequence numbers are updated in place before sending.

| ATTRIBUTE     | DESCRIPTION                                  |
| ------------- | -------------------------------------------- |
| `pixel_count` | Total number of pixels/zones **TYPE:** `int` |

Example

```python
async with await MatrixLight.from_ip("192.168.1.100") as device:
    animator = await Animator.for_matrix(device)

# No connection needed after this - direct UDP
while running:
    stats = animator.send_frame(frame)
    await asyncio.sleep(1 / 30)  # 30 FPS

animator.close()
```

Use the `for_matrix()` or `for_multizone()` class methods for automatic configuration from a device.

| PARAMETER          | DESCRIPTION                                                            |
| ------------------ | ---------------------------------------------------------------------- |
| `ip`               | Device IP address **TYPE:** `str`                                      |
| `serial`           | Device serial number **TYPE:** `Serial`                                |
| `framebuffer`      | Configured FrameBuffer for orientation mapping **TYPE:** `FrameBuffer` |
| `packet_generator` | Configured PacketGenerator for the device **TYPE:** `PacketGenerator`  |
| `port`             | UDP port (default: 56700) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT` |

| METHOD          | DESCRIPTION                                                |
| --------------- | ---------------------------------------------------------- |
| `for_matrix`    | Create an Animator configured for a MatrixLight device.    |
| `for_multizone` | Create an Animator configured for a MultiZoneLight device. |
| `send_frame`    | Send a frame to the device via direct UDP.                 |
| `close`         | Close the UDP socket.                                      |

Source code in `src/lifx/animation/animator.py`

```python
def __init__(
    self,
    ip: str,
    serial: Serial,
    framebuffer: FrameBuffer,
    packet_generator: PacketGenerator,
    port: int = LIFX_UDP_PORT,
) -> None:
    """Initialize animator for direct UDP sending.

    Use the `for_matrix()` or `for_multizone()` class methods for
    automatic configuration from a device.

    Args:
        ip: Device IP address
        serial: Device serial number
        framebuffer: Configured FrameBuffer for orientation mapping
        packet_generator: Configured PacketGenerator for the device
        port: UDP port (default: 56700)
    """
    self._ip = ip
    self._port = port
    self._serial = serial
    self._framebuffer = framebuffer
    self._packet_generator = packet_generator

    # Protocol source ID (random, identifies this client)
    self._source = random.randint(1, 0xFFFFFFFF)  # nosec B311

    # Sequence number (0-255, wraps around)
    self._sequence = 0

    # Create prebaked packet templates
    self._templates: list[PacketTemplate] = packet_generator.create_templates(
        source=self._source,
        target=serial.value,
    )

    # UDP socket (created lazily)
    self._socket: socket.socket | None = None
```

#### Attributes

##### pixel_count

```python
pixel_count: int
```

Get total number of input pixels (canvas size for multi-tile).

##### canvas_width

```python
canvas_width: int
```

Get width of the logical canvas in pixels.

##### canvas_height

```python
canvas_height: int
```

Get height of the logical canvas in pixels.

#### Functions

##### for_matrix

```python
for_matrix(device: MatrixLight) -> Animator
```

Create an Animator configured for a MatrixLight device.

Queries the device for tile information, then returns an animator that sends frames via direct UDP (no device connection needed after creation).

| PARAMETER | DESCRIPTION                                                    |
| --------- | -------------------------------------------------------------- |
| `device`  | MatrixLight device (must be connected) **TYPE:** `MatrixLight` |

| RETURNS    | DESCRIPTION                  |
| ---------- | ---------------------------- |
| `Animator` | Configured Animator instance |

Example

```python
async with await MatrixLight.from_ip("192.168.1.100") as device:
    animator = await Animator.for_matrix(device)

# Device connection closed, animator still works via UDP
while running:
    stats = animator.send_frame(frame)
    await asyncio.sleep(1 / 30)  # 30 FPS
```

Source code in `src/lifx/animation/animator.py`

````python
@classmethod
async def for_matrix(
    cls,
    device: MatrixLight,
) -> Animator:
    """Create an Animator configured for a MatrixLight device.

    Queries the device for tile information, then returns an animator
    that sends frames via direct UDP (no device connection needed
    after creation).

    Args:
        device: MatrixLight device (must be connected)

    Returns:
        Configured Animator instance

    Example:
        ```python
        async with await MatrixLight.from_ip("192.168.1.100") as device:
            animator = await Animator.for_matrix(device)

        # Device connection closed, animator still works via UDP
        while running:
            stats = animator.send_frame(frame)
            await asyncio.sleep(1 / 30)  # 30 FPS
        ```
    """
    # Get device info
    ip = device.ip
    serial = Serial.from_string(device.serial)

    # Ensure we have tile chain
    if device.device_chain is None:
        await device.get_device_chain()

    tiles = device.device_chain
    if not tiles:
        raise ValueError("Device has no tiles")

    # Create framebuffer with orientation correction
    framebuffer = await FrameBuffer.for_matrix(device)

    # Create packet generator
    packet_generator = MatrixPacketGenerator(
        tile_count=len(tiles),
        tile_width=tiles[0].width,
        tile_height=tiles[0].height,
    )

    return cls(ip, serial, framebuffer, packet_generator)
````

##### for_multizone

```python
for_multizone(device: MultiZoneLight) -> Animator
```

Create an Animator configured for a MultiZoneLight device.

Only devices with extended multizone capability are supported. Queries the device for zone count, then returns an animator that sends frames via direct UDP.

| PARAMETER | DESCRIPTION                                                                                                  |
| --------- | ------------------------------------------------------------------------------------------------------------ |
| `device`  | MultiZoneLight device (must be connected and support extended multizone protocol) **TYPE:** `MultiZoneLight` |

| RETURNS    | DESCRIPTION                  |
| ---------- | ---------------------------- |
| `Animator` | Configured Animator instance |

| RAISES       | DESCRIPTION                                  |
| ------------ | -------------------------------------------- |
| `ValueError` | If device doesn't support extended multizone |

Example

```python
async with await MultiZoneLight.from_ip("192.168.1.100") as device:
    animator = await Animator.for_multizone(device)

# Device connection closed, animator still works via UDP
while running:
    stats = animator.send_frame(frame)
    await asyncio.sleep(1 / 30)  # 30 FPS
```

Source code in `src/lifx/animation/animator.py`

````python
@classmethod
async def for_multizone(
    cls,
    device: MultiZoneLight,
) -> Animator:
    """Create an Animator configured for a MultiZoneLight device.

    Only devices with extended multizone capability are supported.
    Queries the device for zone count, then returns an animator
    that sends frames via direct UDP.

    Args:
        device: MultiZoneLight device (must be connected and support
               extended multizone protocol)

    Returns:
        Configured Animator instance

    Raises:
        ValueError: If device doesn't support extended multizone

    Example:
        ```python
        async with await MultiZoneLight.from_ip("192.168.1.100") as device:
            animator = await Animator.for_multizone(device)

        # Device connection closed, animator still works via UDP
        while running:
            stats = animator.send_frame(frame)
            await asyncio.sleep(1 / 30)  # 30 FPS
        ```
    """
    # Ensure capabilities are loaded
    if device.capabilities is None:
        await device._ensure_capabilities()

    # Check extended multizone capability
    has_extended = bool(
        device.capabilities and device.capabilities.has_extended_multizone
    )
    if not has_extended:
        raise ValueError(
            "Device does not support extended multizone protocol. "
            "Only extended multizone devices are supported for animation."
        )

    # Get device info
    ip = device.ip
    serial = Serial.from_string(device.serial)

    # Create framebuffer (no orientation for multizone)
    framebuffer = await FrameBuffer.for_multizone(device)

    # Get zone count
    zone_count = await device.get_zone_count()

    # Create packet generator
    packet_generator = MultiZonePacketGenerator(zone_count=zone_count)

    return cls(ip, serial, framebuffer, packet_generator)
````

##### send_frame

```python
send_frame(hsbk: list[tuple[int, int, int, int]]) -> AnimatorStats
```

Send a frame to the device via direct UDP.

Applies orientation mapping (for matrix devices), updates colors in prebaked packets, and sends them directly via UDP. No ACKs, no waiting - maximum throughput.

This is a synchronous method for minimum overhead. UDP sendto() is non-blocking for datagrams.

| PARAMETER | DESCRIPTION                                                                                                                                                                   |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hsbk`    | Protocol-ready HSBK data for all pixels. Each tuple is (hue, sat, brightness, kelvin) where H/S/B are 0-65535 and K is 1500-9000. **TYPE:** `list[tuple[int, int, int, int]]` |

| RETURNS         | DESCRIPTION                             |
| --------------- | --------------------------------------- |
| `AnimatorStats` | AnimatorStats with operation statistics |

| RAISES       | DESCRIPTION                              |
| ------------ | ---------------------------------------- |
| `ValueError` | If hsbk length doesn't match pixel_count |

Source code in `src/lifx/animation/animator.py`

```python
def send_frame(
    self,
    hsbk: list[tuple[int, int, int, int]],
) -> AnimatorStats:
    """Send a frame to the device via direct UDP.

    Applies orientation mapping (for matrix devices), updates colors
    in prebaked packets, and sends them directly via UDP. No ACKs,
    no waiting - maximum throughput.

    This is a synchronous method for minimum overhead. UDP sendto()
    is non-blocking for datagrams.

    Args:
        hsbk: Protocol-ready HSBK data for all pixels.
              Each tuple is (hue, sat, brightness, kelvin) where
              H/S/B are 0-65535 and K is 1500-9000.

    Returns:
        AnimatorStats with operation statistics

    Raises:
        ValueError: If hsbk length doesn't match pixel_count
    """
    start_time = time.perf_counter()

    # Apply orientation mapping
    device_data = self._framebuffer.apply(hsbk)

    # Update colors in prebaked templates
    self._packet_generator.update_colors(self._templates, device_data)

    # Ensure socket exists
    if self._socket is None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(False)

    # Send each packet, updating sequence number
    for tmpl in self._templates:
        tmpl.data[SEQUENCE_OFFSET] = self._sequence
        self._sequence = (self._sequence + 1) % 256
        self._socket.sendto(tmpl.data, (self._ip, self._port))

    end_time = time.perf_counter()

    return AnimatorStats(
        packets_sent=len(self._templates),
        total_time_ms=(end_time - start_time) * 1000,
    )
```

##### close

```python
close() -> None
```

Close the UDP socket.

Call this when done with the animator to free resources.

Source code in `src/lifx/animation/animator.py`

```python
def close(self) -> None:
    """Close the UDP socket.

    Call this when done with the animator to free resources.
    """
    if self._socket is not None:
        self._socket.close()
        self._socket = None
```

### AnimatorStats

Statistics returned by `Animator.send_frame()`.

#### AnimatorStats

```python
AnimatorStats(packets_sent: int, total_time_ms: float)
```

Statistics about a frame send operation.

| ATTRIBUTE       | DESCRIPTION                                                    |
| --------------- | -------------------------------------------------------------- |
| `packets_sent`  | Number of packets sent **TYPE:** `int`                         |
| `total_time_ms` | Total time for the operation in milliseconds **TYPE:** `float` |

## FrameBuffer

Canvas mapping and orientation handling for matrix devices.

### FrameBuffer

```python
FrameBuffer(
    pixel_count: int,
    canvas_width: int = 0,
    canvas_height: int = 0,
    tile_regions: list[TileRegion] | None = None,
)
```

Orientation mapping for matrix device animations.

For matrix devices with tile orientation (like the original LIFX Tile), this class remaps pixel coordinates from user-space (logical layout) to device-space (physical tile order accounting for rotation).

For multi-tile devices, the FrameBuffer creates a unified canvas where each tile's position (user_x, user_y) determines which region of the canvas it displays. This allows animations to span across all tiles instead of being mirrored.

For multizone devices and matrix devices without orientation, this is essentially a passthrough.

| ATTRIBUTE       | DESCRIPTION                                                                       |
| --------------- | --------------------------------------------------------------------------------- |
| `pixel_count`   | Total number of device pixels **TYPE:** `int`                                     |
| `canvas_width`  | Width of the logical canvas in pixels **TYPE:** `int`                             |
| `canvas_height` | Height of the logical canvas in pixels **TYPE:** `int`                            |
| `tile_regions`  | List of tile regions with positions and orientations **TYPE:** \`list[TileRegion] |

Example

```python
# Create for a device
fb = await FrameBuffer.for_matrix(matrix_device)

# Check canvas dimensions
print(f"Canvas: {fb.canvas_width}x{fb.canvas_height}")

# Provide canvas-sized input
canvas = [(0, 0, 65535, 3500)] * (fb.canvas_width * fb.canvas_height)
device_data = fb.apply(canvas)
```

| PARAMETER       | DESCRIPTION                                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `pixel_count`   | Total number of device pixels **TYPE:** `int`                                                                                        |
| `canvas_width`  | Width of the logical canvas (0 = same as pixel_count) **TYPE:** `int` **DEFAULT:** `0`                                               |
| `canvas_height` | Height of the logical canvas (0 = 1 for linear) **TYPE:** `int` **DEFAULT:** `0`                                                     |
| `tile_regions`  | List of tile regions with positions and orientations. If provided, input is interpreted as a 2D canvas. **TYPE:** \`list[TileRegion] |

| METHOD          | DESCRIPTION                                                  |
| --------------- | ------------------------------------------------------------ |
| `for_matrix`    | Create a FrameBuffer configured for a MatrixLight device.    |
| `for_multizone` | Create a FrameBuffer configured for a MultiZoneLight device. |
| `apply`         | Apply orientation mapping to frame data.                     |

Source code in `src/lifx/animation/framebuffer.py`

```python
def __init__(
    self,
    pixel_count: int,
    canvas_width: int = 0,
    canvas_height: int = 0,
    tile_regions: list[TileRegion] | None = None,
) -> None:
    """Initialize framebuffer.

    Args:
        pixel_count: Total number of device pixels
        canvas_width: Width of the logical canvas (0 = same as pixel_count)
        canvas_height: Height of the logical canvas (0 = 1 for linear)
        tile_regions: List of tile regions with positions and orientations.
                     If provided, input is interpreted as a 2D canvas.
    """
    if pixel_count < 0:
        raise ValueError(f"pixel_count must be non-negative, got {pixel_count}")

    self._pixel_count = pixel_count
    self._tile_regions = tile_regions

    # Canvas dimensions
    if tile_regions:
        # Calculate from tile regions
        self._canvas_width = canvas_width
        self._canvas_height = canvas_height
    else:
        # Linear (multizone) or single tile
        self._canvas_width = canvas_width if canvas_width > 0 else pixel_count
        self._canvas_height = canvas_height if canvas_height > 0 else 1
```

#### Attributes

##### pixel_count

```python
pixel_count: int
```

Get total number of device pixels.

##### canvas_width

```python
canvas_width: int
```

Get width of the logical canvas in pixels.

##### canvas_height

```python
canvas_height: int
```

Get height of the logical canvas in pixels.

##### canvas_size

```python
canvas_size: int
```

Get total number of canvas pixels (width * height).

##### tile_regions

```python
tile_regions: list[TileRegion] | None
```

Get tile regions if configured.

#### Functions

##### for_matrix

```python
for_matrix(device: MatrixLight) -> FrameBuffer
```

Create a FrameBuffer configured for a MatrixLight device.

Automatically determines pixel count from device chain and creates appropriate mapping for tile orientations and positions.

For multi-tile devices (has_chain capability), creates a unified canvas based on tile positions (user_x, user_y). Each tile's position determines which region of the canvas it displays, allowing animations to span across all tiles.

| PARAMETER | DESCRIPTION                                                    |
| --------- | -------------------------------------------------------------- |
| `device`  | MatrixLight device (must be connected) **TYPE:** `MatrixLight` |

| RETURNS       | DESCRIPTION                     |
| ------------- | ------------------------------- |
| `FrameBuffer` | Configured FrameBuffer instance |

Example

```python
async with await MatrixLight.from_ip("192.168.1.100") as matrix:
    fb = await FrameBuffer.for_matrix(matrix)
    print(f"Canvas: {fb.canvas_width}x{fb.canvas_height}")
```

Source code in `src/lifx/animation/framebuffer.py`

````python
@classmethod
async def for_matrix(
    cls,
    device: MatrixLight,
) -> FrameBuffer:
    """Create a FrameBuffer configured for a MatrixLight device.

    Automatically determines pixel count from device chain and creates
    appropriate mapping for tile orientations and positions.

    For multi-tile devices (has_chain capability), creates a unified canvas
    based on tile positions (user_x, user_y). Each tile's position determines
    which region of the canvas it displays, allowing animations to span
    across all tiles.

    Args:
        device: MatrixLight device (must be connected)

    Returns:
        Configured FrameBuffer instance

    Example:
        ```python
        async with await MatrixLight.from_ip("192.168.1.100") as matrix:
            fb = await FrameBuffer.for_matrix(matrix)
            print(f"Canvas: {fb.canvas_width}x{fb.canvas_height}")
        ```
    """
    # Ensure device chain is loaded
    if device.device_chain is None:
        await device.get_device_chain()

    tiles = device.device_chain
    if not tiles:
        raise ValueError("Device has no tiles")

    # Calculate total device pixels
    pixel_count = sum(t.width * t.height for t in tiles)

    # Ensure capabilities are loaded
    if device.capabilities is None:
        await device._ensure_capabilities()

    # Only build canvas mapping for devices with chain capability.
    # The original LIFX Tile is the only matrix device with accelerometer-based
    # orientation detection and multi-tile positioning. Other matrix devices
    # (Ceiling, Luna, Candle, Path, etc.) have fixed positions.
    if device.capabilities and device.capabilities.has_chain:
        return cls._for_multi_tile(tiles, pixel_count)
    else:
        # Single tile device - simple passthrough
        first_tile = tiles[0]
        return cls(
            pixel_count=pixel_count,
            canvas_width=first_tile.width,
            canvas_height=first_tile.height,
        )
````

##### for_multizone

```python
for_multizone(device: MultiZoneLight) -> FrameBuffer
```

Create a FrameBuffer configured for a MultiZoneLight device.

Automatically determines pixel count from zone count. Multizone devices don't need permutation (zones are linear).

| PARAMETER | DESCRIPTION                                                          |
| --------- | -------------------------------------------------------------------- |
| `device`  | MultiZoneLight device (must be connected) **TYPE:** `MultiZoneLight` |

| RETURNS       | DESCRIPTION                     |
| ------------- | ------------------------------- |
| `FrameBuffer` | Configured FrameBuffer instance |

Example

```python
async with await MultiZoneLight.from_ip("192.168.1.100") as strip:
    fb = await FrameBuffer.for_multizone(strip)
```

Source code in `src/lifx/animation/framebuffer.py`

````python
@classmethod
async def for_multizone(
    cls,
    device: MultiZoneLight,
) -> FrameBuffer:
    """Create a FrameBuffer configured for a MultiZoneLight device.

    Automatically determines pixel count from zone count.
    Multizone devices don't need permutation (zones are linear).

    Args:
        device: MultiZoneLight device (must be connected)

    Returns:
        Configured FrameBuffer instance

    Example:
        ```python
        async with await MultiZoneLight.from_ip("192.168.1.100") as strip:
            fb = await FrameBuffer.for_multizone(strip)
        ```
    """
    # Get zone count (fetches from device if not cached)
    zone_count = await device.get_zone_count()

    return cls(pixel_count=zone_count)
````

##### apply

```python
apply(hsbk: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]
```

Apply orientation mapping to frame data.

For multi-tile devices, the input is interpreted as a row-major 2D canvas of size (canvas_width x canvas_height). Each tile extracts its region from the canvas based on its position.

For single-tile or multizone devices, this is a passthrough.

| PARAMETER | DESCRIPTION                                                                                                                                                                                                                                                                         |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hsbk`    | List of protocol-ready HSBK tuples. - For multi-tile: length must match canvas_size - For single-tile/multizone: length must match pixel_count Each tuple is (hue, sat, brightness, kelvin) where H/S/B are 0-65535 and K is 1500-9000. **TYPE:** `list[tuple[int, int, int, int]]` |

| RETURNS                           | DESCRIPTION                        |
| --------------------------------- | ---------------------------------- |
| `list[tuple[int, int, int, int]]` | Remapped HSBK data in device order |

| RAISES       | DESCRIPTION                                |
| ------------ | ------------------------------------------ |
| `ValueError` | If hsbk length doesn't match expected size |

Source code in `src/lifx/animation/framebuffer.py`

```python
def apply(
    self, hsbk: list[tuple[int, int, int, int]]
) -> list[tuple[int, int, int, int]]:
    """Apply orientation mapping to frame data.

    For multi-tile devices, the input is interpreted as a row-major 2D
    canvas of size (canvas_width x canvas_height). Each tile extracts
    its region from the canvas based on its position.

    For single-tile or multizone devices, this is a passthrough.

    Args:
        hsbk: List of protocol-ready HSBK tuples.
              - For multi-tile: length must match canvas_size
              - For single-tile/multizone: length must match pixel_count
              Each tuple is (hue, sat, brightness, kelvin) where
              H/S/B are 0-65535 and K is 1500-9000.

    Returns:
        Remapped HSBK data in device order

    Raises:
        ValueError: If hsbk length doesn't match expected size
    """
    # Multi-tile canvas mode
    if self._tile_regions:
        expected_size = self._canvas_width * self._canvas_height
        if len(hsbk) != expected_size:
            raise ValueError(
                f"HSBK length ({len(hsbk)}) must match "
                f"canvas_size ({expected_size})"
            )
        return self._apply_canvas(hsbk)

    # Single-tile or multizone mode (passthrough)
    if len(hsbk) != self._pixel_count:
        raise ValueError(
            f"HSBK length ({len(hsbk)}) must match "
            f"pixel_count ({self._pixel_count})"
        )

    return list(hsbk)
```

### TileRegion

Represents a tile's region within the canvas.

#### TileRegion

```python
TileRegion(
    x: int,
    y: int,
    width: int,
    height: int,
    orientation_lut: tuple[int, ...] | None = None,
)
```

Region of a tile within the canvas.

| ATTRIBUTE         | DESCRIPTION                                                                   |
| ----------------- | ----------------------------------------------------------------------------- |
| `x`               | X offset in canvas coordinates **TYPE:** `int`                                |
| `y`               | Y offset in canvas coordinates **TYPE:** `int`                                |
| `width`           | Tile width in pixels **TYPE:** `int`                                          |
| `height`          | Tile height in pixels **TYPE:** `int`                                         |
| `orientation_lut` | Lookup table for orientation remapping (optional) **TYPE:** \`tuple[int, ...] |

## Packet Generators

Device-specific packet generation with prebaked templates.

### PacketGenerator (Base)

#### PacketGenerator

Bases: `ABC`

Abstract base class for packet generators.

Packet generators prebake complete packets (header + payload) at initialization time. Per-frame, only color data and sequence numbers are updated in place.

| METHOD             | DESCRIPTION                                       |
| ------------------ | ------------------------------------------------- |
| `create_templates` | Create prebaked packet templates.                 |
| `update_colors`    | Update color data in prebaked templates.          |
| `pixel_count`      | Get the total pixel count this generator expects. |

##### Functions

###### create_templates

```python
create_templates(source: int, target: bytes) -> list[PacketTemplate]
```

Create prebaked packet templates.

| PARAMETER | DESCRIPTION                                       |
| --------- | ------------------------------------------------- |
| `source`  | Client source ID for header **TYPE:** `int`       |
| `target`  | 6-byte device serial for header **TYPE:** `bytes` |

| RETURNS                | DESCRIPTION                                  |
| ---------------------- | -------------------------------------------- |
| `list[PacketTemplate]` | List of PacketTemplate with prebaked packets |

Source code in `src/lifx/animation/packets.py`

```python
@abstractmethod
def create_templates(self, source: int, target: bytes) -> list[PacketTemplate]:
    """Create prebaked packet templates.

    Args:
        source: Client source ID for header
        target: 6-byte device serial for header

    Returns:
        List of PacketTemplate with prebaked packets
    """
```

###### update_colors

```python
update_colors(
    templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
) -> None
```

Update color data in prebaked templates.

| PARAMETER   | DESCRIPTION                                                                         |
| ----------- | ----------------------------------------------------------------------------------- |
| `templates` | Prebaked packet templates **TYPE:** `list[PacketTemplate]`                          |
| `hsbk`      | Protocol-ready HSBK data for all pixels **TYPE:** `list[tuple[int, int, int, int]]` |

Source code in `src/lifx/animation/packets.py`

```python
@abstractmethod
def update_colors(
    self, templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
) -> None:
    """Update color data in prebaked templates.

    Args:
        templates: Prebaked packet templates
        hsbk: Protocol-ready HSBK data for all pixels
    """
```

###### pixel_count

```python
pixel_count() -> int
```

Get the total pixel count this generator expects.

Source code in `src/lifx/animation/packets.py`

```python
@abstractmethod
def pixel_count(self) -> int:
    """Get the total pixel count this generator expects."""
```

### PacketTemplate

Prebaked packet template for zero-allocation frame updates.

#### PacketTemplate

```python
PacketTemplate(
    data: bytearray,
    color_offset: int,
    color_count: int,
    hsbk_start: int,
    fmt: str,
)
```

Prebaked packet template for zero-allocation animation.

Contains a complete packet (header + payload) as a mutable bytearray. Only the sequence byte and color data need to be updated per frame.

| ATTRIBUTE      | DESCRIPTION                                                              |
| -------------- | ------------------------------------------------------------------------ |
| `data`         | Complete packet bytes (header + payload) **TYPE:** `bytearray`           |
| `color_offset` | Byte offset where color data starts **TYPE:** `int`                      |
| `color_count`  | Number of HSBK colors in this packet **TYPE:** `int`                     |
| `hsbk_start`   | Starting index in the input HSBK array **TYPE:** `int`                   |
| `fmt`          | Pre-computed struct format string for bulk color packing **TYPE:** `str` |

### MatrixPacketGenerator

Generates Set64 packets for MatrixLight devices.

#### MatrixPacketGenerator

```python
MatrixPacketGenerator(tile_count: int, tile_width: int, tile_height: int)
```

Bases: `PacketGenerator`

Packet generator for MatrixLight devices.

Generates Set64 packets for all tiles. Uses prebaked packet templates with complete headers for maximum performance.

For standard tiles (≤64 pixels):

- Single Set64 packet directly to display buffer (fb_index=0)

For large tiles (>64 pixels, e.g., Ceiling 16x8=128):

- Multiple Set64 packets to temp buffer (fb_index=1)
- CopyFrameBuffer packet to copy fb_index=1 → fb_index=0

Set64 Payload Layout (522 bytes):

- Offset 0: tile_index (uint8)
- Offset 1: length (uint8, always 1)
- Offset 2-5: TileBufferRect (fb_index, x, y, width - 4 x uint8)
- Offset 6-9: duration (uint32)
- Offset 10-521: colors (64 x HSBK, each 8 bytes)

CopyFrameBuffer Payload Layout (15 bytes):

- Offset 0: tile_index (uint8)
- Offset 1: length (uint8, always 1)
- Offset 2: src_fb_index (uint8, 1 = temp buffer)
- Offset 3: dst_fb_index (uint8, 0 = display)
- Offset 4-7: src_x, src_y, dst_x, dst_y (uint8 each)
- Offset 8-9: width, height (uint8 each)
- Offset 10-13: duration (uint32)
- Offset 14: reserved (uint8)

| PARAMETER     | DESCRIPTION                                         |
| ------------- | --------------------------------------------------- |
| `tile_count`  | Number of tiles in the device chain **TYPE:** `int` |
| `tile_width`  | Width of each tile in pixels **TYPE:** `int`        |
| `tile_height` | Height of each tile in pixels **TYPE:** `int`       |

| METHOD             | DESCRIPTION                                     |
| ------------------ | ----------------------------------------------- |
| `pixel_count`      | Get total pixel count.                          |
| `create_templates` | Create prebaked packet templates for all tiles. |
| `update_colors`    | Update color data in prebaked templates.        |

| ATTRIBUTE          | DESCRIPTION                                                                       |
| ------------------ | --------------------------------------------------------------------------------- |
| `is_large_tile`    | Check if tiles have >64 pixels (requires multi-packet strategy). **TYPE:** `bool` |
| `packets_per_tile` | Get number of Set64 packets needed per tile. **TYPE:** `int`                      |

Source code in `src/lifx/animation/packets.py`

```python
def __init__(
    self,
    tile_count: int,
    tile_width: int,
    tile_height: int,
) -> None:
    """Initialize matrix packet generator.

    Args:
        tile_count: Number of tiles in the device chain
        tile_width: Width of each tile in pixels
        tile_height: Height of each tile in pixels
    """
    self._tile_count = tile_count
    self._tile_width = tile_width
    self._tile_height = tile_height
    self._pixels_per_tile = tile_width * tile_height
    self._total_pixels = tile_count * self._pixels_per_tile

    # Determine if we need large tile mode (>64 pixels per tile)
    self._is_large_tile = self._pixels_per_tile > self._MAX_COLORS_PER_PACKET

    # Calculate packets needed per tile
    self._rows_per_packet = self._MAX_COLORS_PER_PACKET // tile_width
    self._packets_per_tile = (
        self._pixels_per_tile + self._MAX_COLORS_PER_PACKET - 1
    ) // self._MAX_COLORS_PER_PACKET
```

##### Attributes

###### is_large_tile

```python
is_large_tile: bool
```

Check if tiles have >64 pixels (requires multi-packet strategy).

###### packets_per_tile

```python
packets_per_tile: int
```

Get number of Set64 packets needed per tile.

##### Functions

###### pixel_count

```python
pixel_count() -> int
```

Get total pixel count.

Source code in `src/lifx/animation/packets.py`

```python
def pixel_count(self) -> int:
    """Get total pixel count."""
    return self._total_pixels
```

###### create_templates

```python
create_templates(source: int, target: bytes) -> list[PacketTemplate]
```

Create prebaked packet templates for all tiles.

| PARAMETER | DESCRIPTION                            |
| --------- | -------------------------------------- |
| `source`  | Client source ID **TYPE:** `int`       |
| `target`  | 6-byte device serial **TYPE:** `bytes` |

| RETURNS                | DESCRIPTION                                           |
| ---------------------- | ----------------------------------------------------- |
| `list[PacketTemplate]` | List of PacketTemplate with complete prebaked packets |

Source code in `src/lifx/animation/packets.py`

```python
def create_templates(self, source: int, target: bytes) -> list[PacketTemplate]:
    """Create prebaked packet templates for all tiles.

    Args:
        source: Client source ID
        target: 6-byte device serial

    Returns:
        List of PacketTemplate with complete prebaked packets
    """
    if self._is_large_tile:
        return self._create_large_tile_templates(source, target)
    else:
        return self._create_standard_templates(source, target)
```

###### update_colors

```python
update_colors(
    templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
) -> None
```

Update color data in prebaked templates.

| PARAMETER   | DESCRIPTION                                                                         |
| ----------- | ----------------------------------------------------------------------------------- |
| `templates` | Prebaked packet templates **TYPE:** `list[PacketTemplate]`                          |
| `hsbk`      | Protocol-ready HSBK data for all pixels **TYPE:** `list[tuple[int, int, int, int]]` |

Source code in `src/lifx/animation/packets.py`

```python
def update_colors(
    self, templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
) -> None:
    """Update color data in prebaked templates.

    Args:
        templates: Prebaked packet templates
        hsbk: Protocol-ready HSBK data for all pixels
    """
    for tmpl in templates:
        if tmpl.color_count == 0:
            continue  # Skip CopyFrameBuffer packets

        # Flatten HSBK tuples and pack in one bulk call
        start = tmpl.hsbk_start
        end = start + tmpl.color_count
        flat: list[int] = []
        for h, s, b, k in hsbk[start:end]:
            flat.extend((h, s, b, k))
        struct.pack_into(tmpl.fmt, tmpl.data, tmpl.color_offset, *flat)
```

### MultiZonePacketGenerator

Generates SetExtendedColorZones packets for MultiZoneLight devices.

#### MultiZonePacketGenerator

```python
MultiZonePacketGenerator(zone_count: int)
```

Bases: `PacketGenerator`

Packet generator for MultiZoneLight devices with extended multizone.

Uses SetExtendedColorZones packets (up to 82 zones each). For devices with >82 zones, multiple packets are generated.

SetExtendedColorZones Payload Layout (664 bytes):

- Offset 0-3: duration (uint32)
- Offset 4: apply (uint8, 1 = APPLY)
- Offset 5-6: zone_index (uint16)
- Offset 7: colors_count (uint8)
- Offset 8-663: colors (82 x HSBK, each 8 bytes)

| PARAMETER    | DESCRIPTION                                         |
| ------------ | --------------------------------------------------- |
| `zone_count` | Total number of zones on the device **TYPE:** `int` |

| METHOD             | DESCRIPTION                                     |
| ------------------ | ----------------------------------------------- |
| `pixel_count`      | Get total zone count.                           |
| `create_templates` | Create prebaked packet templates for all zones. |
| `update_colors`    | Update color data in prebaked templates.        |

Source code in `src/lifx/animation/packets.py`

```python
def __init__(self, zone_count: int) -> None:
    """Initialize multizone packet generator.

    Args:
        zone_count: Total number of zones on the device
    """
    self._zone_count = zone_count
    self._packets_needed = (
        zone_count + self._MAX_ZONES_PER_PACKET - 1
    ) // self._MAX_ZONES_PER_PACKET
```

##### Functions

###### pixel_count

```python
pixel_count() -> int
```

Get total zone count.

Source code in `src/lifx/animation/packets.py`

```python
def pixel_count(self) -> int:
    """Get total zone count."""
    return self._zone_count
```

###### create_templates

```python
create_templates(source: int, target: bytes) -> list[PacketTemplate]
```

Create prebaked packet templates for all zones.

| PARAMETER | DESCRIPTION                            |
| --------- | -------------------------------------- |
| `source`  | Client source ID **TYPE:** `int`       |
| `target`  | 6-byte device serial **TYPE:** `bytes` |

| RETURNS                | DESCRIPTION                                           |
| ---------------------- | ----------------------------------------------------- |
| `list[PacketTemplate]` | List of PacketTemplate with complete prebaked packets |

Source code in `src/lifx/animation/packets.py`

```python
def create_templates(self, source: int, target: bytes) -> list[PacketTemplate]:
    """Create prebaked packet templates for all zones.

    Args:
        source: Client source ID
        target: 6-byte device serial

    Returns:
        List of PacketTemplate with complete prebaked packets
    """
    templates: list[PacketTemplate] = []

    for pkt_idx in range(self._packets_needed):
        zone_start = pkt_idx * self._MAX_ZONES_PER_PACKET
        zone_end = min(zone_start + self._MAX_ZONES_PER_PACKET, self._zone_count)
        zone_count = zone_end - zone_start

        # Build header
        header = _build_header(
            self.SET_EXTENDED_COLOR_ZONES_PKT_TYPE,
            source,
            target,
            self._PAYLOAD_SIZE,
        )

        # Build payload
        payload = bytearray(self._PAYLOAD_SIZE)
        # duration = 0
        struct.pack_into("<I", payload, 0, 0)
        # apply = 1 (APPLY)
        payload[4] = 1
        # zone_index
        struct.pack_into("<H", payload, 5, zone_start)
        # colors_count
        payload[7] = zone_count
        # colors filled with black as default
        for i in range(82):
            offset = self._COLORS_OFFSET_IN_PAYLOAD + i * 8
            struct.pack_into("<HHHH", payload, offset, 0, 0, 0, 3500)

        packet = header + payload

        templates.append(
            PacketTemplate(
                data=packet,
                color_offset=HEADER_SIZE + self._COLORS_OFFSET_IN_PAYLOAD,
                color_count=zone_count,
                hsbk_start=zone_start,
                fmt=f"<{'HHHH' * zone_count}",
            )
        )

    return templates
```

###### update_colors

```python
update_colors(
    templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
) -> None
```

Update color data in prebaked templates.

| PARAMETER   | DESCRIPTION                                                                        |
| ----------- | ---------------------------------------------------------------------------------- |
| `templates` | Prebaked packet templates **TYPE:** `list[PacketTemplate]`                         |
| `hsbk`      | Protocol-ready HSBK data for all zones **TYPE:** `list[tuple[int, int, int, int]]` |

Source code in `src/lifx/animation/packets.py`

```python
def update_colors(
    self, templates: list[PacketTemplate], hsbk: list[tuple[int, int, int, int]]
) -> None:
    """Update color data in prebaked templates.

    Args:
        templates: Prebaked packet templates
        hsbk: Protocol-ready HSBK data for all zones
    """
    for tmpl in templates:
        # Flatten HSBK tuples and pack in one bulk call
        start = tmpl.hsbk_start
        end = start + tmpl.color_count
        flat: list[int] = []
        for h, s, b, k in hsbk[start:end]:
            flat.extend((h, s, b, k))
        struct.pack_into(tmpl.fmt, tmpl.data, tmpl.color_offset, *flat)
```

## Tile Orientation

Pixel remapping for rotated tiles.

### Orientation Enum

#### Orientation

Bases: `IntEnum`

Tile orientation based on accelerometer data.

These values match the orientation detection in TileInfo.nearest_orientation but use integer enum for efficient comparison and caching.

Physical mounting positions

- RIGHT_SIDE_UP: Normal position, no rotation needed
- ROTATED_90: Rotated 90 degrees clockwise (RotatedRight)
- ROTATED_180: Upside down (UpsideDown)
- ROTATED_270: Rotated 90 degrees counter-clockwise (RotatedLeft)
- FACE_UP: Tile facing ceiling
- FACE_DOWN: Tile facing floor

| METHOD        | DESCRIPTION                                                      |
| ------------- | ---------------------------------------------------------------- |
| `from_string` | Convert TileInfo.nearest_orientation string to Orientation enum. |

##### Functions

###### from_string

```python
from_string(orientation_str: str) -> Orientation
```

Convert TileInfo.nearest_orientation string to Orientation enum.

| PARAMETER         | DESCRIPTION                                              |
| ----------------- | -------------------------------------------------------- |
| `orientation_str` | String from TileInfo.nearest_orientation **TYPE:** `str` |

| RETURNS       | DESCRIPTION                          |
| ------------- | ------------------------------------ |
| `Orientation` | Corresponding Orientation enum value |

| RAISES       | DESCRIPTION                             |
| ------------ | --------------------------------------- |
| `ValueError` | If orientation string is not recognized |

Source code in `src/lifx/animation/orientation.py`

```python
@classmethod
def from_string(cls, orientation_str: str) -> Orientation:
    """Convert TileInfo.nearest_orientation string to Orientation enum.

    Args:
        orientation_str: String from TileInfo.nearest_orientation

    Returns:
        Corresponding Orientation enum value

    Raises:
        ValueError: If orientation string is not recognized
    """
    mapping = {
        "Upright": cls.RIGHT_SIDE_UP,
        "RotatedRight": cls.ROTATED_90,
        "UpsideDown": cls.ROTATED_180,
        "RotatedLeft": cls.ROTATED_270,
        "FaceUp": cls.FACE_UP,
        "FaceDown": cls.FACE_DOWN,
    }
    if orientation_str not in mapping:
        raise ValueError(f"Unknown orientation: {orientation_str}")
    return mapping[orientation_str]
```

### build_orientation_lut

#### build_orientation_lut

```python
build_orientation_lut(
    width: int, height: int, orientation: Orientation
) -> tuple[int, ...]
```

Build a lookup table for remapping pixels based on tile orientation.

The LUT maps physical tile positions to row-major framebuffer indices. For a pixel at physical position i, lut[i] gives the framebuffer index.

This is LRU-cached because tiles typically have standard dimensions (8x8) and there are only 6 orientations, so the cache will be highly effective.

| PARAMETER     | DESCRIPTION                              |
| ------------- | ---------------------------------------- |
| `width`       | Tile width in pixels **TYPE:** `int`     |
| `height`      | Tile height in pixels **TYPE:** `int`    |
| `orientation` | Tile orientation **TYPE:** `Orientation` |

| RETURNS | DESCRIPTION                                                         |
| ------- | ------------------------------------------------------------------- |
| `int`   | Tuple of indices mapping physical position to framebuffer position. |
| `...`   | Tuple is used instead of list for hashability in caches.            |

Example

> > > lut = build_orientation_lut(8, 8, Orientation.RIGHT_SIDE_UP) len(lut) 64 lut[0] # First pixel maps to index 0 0 lut = build_orientation_lut(8, 8, Orientation.ROTATED_180) lut[0] # First physical position maps to last framebuffer index 63

Source code in `src/lifx/animation/orientation.py`

```python
@lru_cache(maxsize=64)
def build_orientation_lut(
    width: int,
    height: int,
    orientation: Orientation,
) -> tuple[int, ...]:
    """Build a lookup table for remapping pixels based on tile orientation.

    The LUT maps physical tile positions to row-major framebuffer indices.
    For a pixel at physical position i, lut[i] gives the framebuffer index.

    This is LRU-cached because tiles typically have standard dimensions (8x8)
    and there are only 6 orientations, so the cache will be highly effective.

    Args:
        width: Tile width in pixels
        height: Tile height in pixels
        orientation: Tile orientation

    Returns:
        Tuple of indices mapping physical position to framebuffer position.
        Tuple is used instead of list for hashability in caches.

    Example:
        >>> lut = build_orientation_lut(8, 8, Orientation.RIGHT_SIDE_UP)
        >>> len(lut)
        64
        >>> lut[0]  # First pixel maps to index 0
        0
        >>> lut = build_orientation_lut(8, 8, Orientation.ROTATED_180)
        >>> lut[0]  # First physical position maps to last framebuffer index
        63
    """
    size = width * height
    lut: list[int] = [0] * size

    for y in range(height):
        for x in range(width):
            # Physical position in row-major order
            physical_idx = y * width + x

            # Calculate source position based on orientation
            if orientation == Orientation.RIGHT_SIDE_UP:
                # No transformation
                src_x, src_y = x, y
            elif orientation == Orientation.ROTATED_90:
                # 90 degrees clockwise: (x, y) -> (height - 1 - y, x)
                # Note: Only valid for square tiles. Non-square tiles would require
                # a source buffer with swapped dimensions (e.g., 5x7 for a 7x5 tile).
                # For non-square tiles, fall back to identity transformation.
                if width == height:
                    src_x = height - 1 - y
                    src_y = x
                else:
                    src_x, src_y = x, y
            elif orientation == Orientation.ROTATED_180:
                # 180 degrees: (x, y) -> (width - 1 - x, height - 1 - y)
                # Works for both square and non-square tiles
                src_x = width - 1 - x
                src_y = height - 1 - y
            elif orientation == Orientation.ROTATED_270:
                # 270 degrees (90 counter-clockwise): (x, y) -> (y, width - 1 - x)
                # Note: Only valid for square tiles. For non-square tiles,
                # fall back to identity transformation.
                if width == height:
                    src_x = y
                    src_y = width - 1 - x
                else:
                    src_x, src_y = x, y
            else:
                # FACE_UP and FACE_DOWN: treat as right-side-up (no x/y rotation)
                # The z-axis orientation doesn't affect 2D pixel mapping
                src_x, src_y = x, y

            # Source index in row-major order
            src_idx = src_y * width + src_x
            lut[physical_idx] = src_idx

    return tuple(lut)
```

## Examples

### Matrix Animation (Single Tile)

```python
import asyncio
from lifx import Animator, MatrixLight

async def rainbow_animation():
    async with await MatrixLight.from_ip("192.168.1.100") as device:
        animator = await Animator.for_matrix(device)

    hue_offset = 0
    try:
        while True:
            # Generate rainbow gradient
            frame = []
            for i in range(animator.pixel_count):
                hue = (hue_offset + i * 1000) % 65536
                frame.append((hue, 65535, 32768, 3500))

            stats = animator.send_frame(frame)
            print(f"Sent {stats.packets_sent} packets")

            hue_offset = (hue_offset + 500) % 65536
            await asyncio.sleep(1 / 30)  # 30 FPS
    finally:
        animator.close()
```

### Multi-Tile Animation (LIFX Tile with 5 tiles)

```python
import asyncio
import math
from lifx import Animator, MatrixLight

async def multi_tile_wave():
    async with await MatrixLight.from_ip("192.168.1.100") as device:
        animator = await Animator.for_matrix(device)

    # Canvas spans all tiles (e.g., 40x8 for 5 horizontal tiles)
    width = animator.canvas_width
    height = animator.canvas_height
    print(f"Canvas: {width}x{height}")

    hue_offset = 0
    try:
        while True:
            frame = []
            for y in range(height):
                for x in range(width):
                    # Wave that flows across all tiles
                    pos = x + y * 0.5  # Diagonal wave
                    hue = int((pos / width) * 65535 + hue_offset) % 65536
                    frame.append((hue, 65535, 65535, 3500))

            animator.send_frame(frame)
            hue_offset = (hue_offset + 1000) % 65536
            await asyncio.sleep(1 / 30)
    finally:
        animator.close()
```

### MultiZone Animation

```python
import asyncio
from lifx import Animator, MultiZoneLight

async def chase_animation():
    async with await MultiZoneLight.from_ip("192.168.1.100") as device:
        animator = await Animator.for_multizone(device)

    position = 0
    try:
        while True:
            # Generate chase pattern
            frame = []
            for i in range(animator.pixel_count):
                if i == position:
                    frame.append((0, 65535, 65535, 3500))  # Red
                else:
                    frame.append((0, 0, 0, 3500))  # Off

            animator.send_frame(frame)

            position = (position + 1) % animator.pixel_count
            await asyncio.sleep(1 / 20)  # 20 FPS
    finally:
        animator.close()
```

## Performance Characteristics

### Direct UDP Delivery

The animation module bypasses the connection layer entirely:

- No ACKs, no waiting, no retries
- Packets sent via raw UDP socket
- Maximum throughput for real-time effects
- Some packet loss is acceptable (visual artifacts are brief)

### Prebaked Packet Templates

Packets are constructed once at initialization:

- Header and payload structure prebaked as `bytearray`
- Per-frame: only color data and sequence number updated
- Zero object allocation in the hot path
- Sequence number wraps at 256 (uint8)

### Multi-Tile Canvas Mapping

For devices with multiple tiles:

- Tile positions read from device (`user_x`, `user_y`)
- Canvas bounds calculated from all tile positions
- Input frame interpreted as 2D row-major canvas
- Each tile extracts its region based on position
- Orientation correction applied per-tile

### Typical Performance

| Device Type          | Pixels | Packets/Frame | Send Time |
| -------------------- | ------ | ------------- | --------- |
| Single tile (8x8)    | 64     | 1             | \<0.5ms   |
| 5-tile chain         | 320    | 5             | \<1ms     |
| Large Ceiling (16x8) | 128    | 3             | \<1ms     |
| MultiZone (82 zones) | 82     | 1             | \<0.5ms   |
