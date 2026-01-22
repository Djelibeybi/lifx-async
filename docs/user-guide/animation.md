# Animation Guide

This guide covers how to use the animation module for high-frequency frame delivery to LIFX devices.
The animation system is designed for real-time effects and applications that need to push color data at 30+ FPS.

## When to Use Animation

Use the animation module when you need:

- **High frame rates** (20+ FPS)
- **Real-time effects** from external sources
- **Integration with music visualizers**
- **Continuous animations** that run for extended periods

For simple, one-time color changes, use the device methods directly (`set_color()`, `set_tile_colors()`, etc.) instead.

## Basic Usage

### Matrix Devices (Tiles, Candle, Path)

```python
import asyncio
from lifx import Animator, MatrixLight

async def main():
    async with await MatrixLight.from_ip("192.168.1.100") as device:
        # Create animator (queries device for tile info)
        animator = await Animator.for_matrix(device)

    # Device connection closed - animator sends via direct UDP
    print(f"Canvas: {animator.canvas_width}x{animator.canvas_height}")
    print(f"Total pixels: {animator.pixel_count}")

    try:
        # Animation loop
        for _ in range(100):
            # Generate frame (H, S, B, K as uint16)
            frame = [(65535, 65535, 65535, 3500)] * animator.pixel_count

            # send_frame() is synchronous for speed
            stats = animator.send_frame(frame)
            print(f"Sent {stats.packets_sent} packets")

            await asyncio.sleep(1 / 30)  # 30 FPS
    finally:
        animator.close()

asyncio.run(main())
```

### MultiZone Devices (Strips, Beams)

```python
import asyncio
from lifx import Animator, MultiZoneLight

async def main():
    async with await MultiZoneLight.from_ip("192.168.1.100") as device:
        # Create animator
        animator = await Animator.for_multizone(device)

    print(f"Device has {animator.pixel_count} zones")

    try:
        # Animation loop
        for _ in range(100):
            # Generate frame
            frame = [(0, 65535, 65535, 3500)] * animator.pixel_count

            stats = animator.send_frame(frame)
            await asyncio.sleep(1 / 30)
    finally:
        animator.close()

asyncio.run(main())
```

## Multi-Tile Canvas

For devices with multiple tiles (like the original 5-tile LIFX Tile), the animator automatically
creates a unified canvas based on tile positions. This allows animations to span across all tiles
as one continuous image, rather than each tile showing a mirrored copy.

### How It Works

1. The animator reads each tile's position (`user_x`, `user_y`) from the device
2. Positions are in "tile-width units" (1.0 = one tile width)
3. A canvas is created that encompasses all tiles
4. Your input frame is interpreted as a 2D row-major image
5. Each tile extracts its region from the canvas based on its position

### Example: 5 Horizontal Tiles

```python
async with await MatrixLight.from_ip("192.168.1.100") as device:
    animator = await Animator.for_matrix(device)

# For 5 tiles arranged horizontally:
# - canvas_width = 40 (5 tiles x 8 pixels)
# - canvas_height = 8
# - pixel_count = 320 (40 x 8)

print(f"Canvas: {animator.canvas_width}x{animator.canvas_height}")

# Generate a gradient that flows across ALL tiles
frame = []
for y in range(animator.canvas_height):
    for x in range(animator.canvas_width):
        # Hue varies from 0 to 65535 across the full width
        hue = int(x / animator.canvas_width * 65535)
        frame.append((hue, 65535, 65535, 3500))

animator.send_frame(frame)  # Rainbow spans all 5 tiles!
```

### Canvas Coordinate System

The canvas uses row-major ordering:

```
For a 40x8 canvas (5 horizontal tiles):

Index:  0  1  2  3  4  ...  39   (row 0)
       40 41 42 43 44  ...  79   (row 1)
       ...
      280 281 ...         319   (row 7)

Tile positions:
Tile 0: x=0-7,   y=0-7
Tile 1: x=8-15,  y=0-7
Tile 2: x=16-23, y=0-7
Tile 3: x=24-31, y=0-7
Tile 4: x=32-39, y=0-7
```

## Understanding HSBK Format

The animation module uses protocol-ready HSBK values for performance:

```python
# HSBK tuple: (hue, saturation, brightness, kelvin)
# - Hue: 0-65535 (maps to 0-360 degrees)
# - Saturation: 0-65535 (maps to 0.0-1.0)
# - Brightness: 0-65535 (maps to 0.0-1.0)
# - Kelvin: 1500-9000

# Examples
red = (0, 65535, 65535, 3500)           # Full red
blue = (43690, 65535, 65535, 3500)      # Full blue (240/360 * 65535)
white = (0, 0, 65535, 5500)             # Daylight white
dim_warm = (0, 0, 16384, 2700)          # 25% warm white
off = (0, 0, 0, 3500)                   # Off (black)
```

### Converting from User-Friendly Values

```python
def to_protocol_hsbk(
    hue: float,        # 0-360 degrees
    saturation: float, # 0.0-1.0
    brightness: float, # 0.0-1.0
    kelvin: int,       # 1500-9000
) -> tuple[int, int, int, int]:
    """Convert user-friendly values to protocol format."""
    return (
        int(hue / 360 * 65535),
        int(saturation * 65535),
        int(brightness * 65535),
        kelvin,
    )

# Usage
red = to_protocol_hsbk(0, 1.0, 1.0, 3500)
blue = to_protocol_hsbk(240, 1.0, 1.0, 3500)
```

### Converting from RGB

```python
def rgb_to_protocol_hsbk(
    r: int, g: int, b: int,  # 0-255
    kelvin: int = 3500,
) -> tuple[int, int, int, int]:
    """Convert RGB to protocol HSBK."""
    # Normalize to 0-1
    r_norm = r / 255
    g_norm = g / 255
    b_norm = b / 255

    max_c = max(r_norm, g_norm, b_norm)
    min_c = min(r_norm, g_norm, b_norm)
    delta = max_c - min_c

    # Brightness
    brightness = max_c

    # Saturation
    if max_c == 0:
        saturation = 0
    else:
        saturation = delta / max_c

    # Hue
    if delta == 0:
        hue = 0
    elif max_c == r_norm:
        hue = 60 * (((g_norm - b_norm) / delta) % 6)
    elif max_c == g_norm:
        hue = 60 * (((b_norm - r_norm) / delta) + 2)
    else:
        hue = 60 * (((r_norm - g_norm) / delta) + 4)

    return (
        int(hue / 360 * 65535),
        int(saturation * 65535),
        int(brightness * 65535),
        kelvin,
    )
```

## Tile Orientation Handling

For matrix devices with the `has_chain` capability (like the original LIFX Tile), tiles may be
physically rotated. The animator automatically handles orientation correction:

```python
async with await MatrixLight.from_ip("192.168.1.100") as device:
    # Orientation is detected from device accelerometer data
    animator = await Animator.for_matrix(device)

# Your frame uses logical canvas coordinates
# The animator remaps to physical tile positions
animator.send_frame(logical_frame)
```

**Supported orientations:**

- `RIGHT_SIDE_UP` - Normal position
- `ROTATED_90` - 90 degrees clockwise
- `ROTATED_180` - Upside down
- `ROTATED_270` - 90 degrees counter-clockwise
- `FACE_UP` - Facing ceiling (treated as right-side-up for 2D mapping)
- `FACE_DOWN` - Facing floor (treated as right-side-up for 2D mapping)

## Performance Tips

### The Animation Loop Pattern

```python
async with await MatrixLight.from_ip("192.168.1.100") as device:
    animator = await Animator.for_matrix(device)

# Device connection closed here - animator works via direct UDP

try:
    while running:
        frame = generate_frame()
        animator.send_frame(frame)  # Synchronous, very fast
        await asyncio.sleep(1 / target_fps)
finally:
    animator.close()  # Clean up UDP socket
```

### Pre-generate Frames

```python
# Generate frames in advance
frames = []
for i in range(100):
    frame = generate_animation_frame(i)
    frames.append(frame)

# Play back at consistent rate
for frame in frames:
    animator.send_frame(frame)
    await asyncio.sleep(1 / 30)
```

### Use NumPy for Large Canvases

For large devices or complex animations, NumPy can speed up frame generation:

```python
import numpy as np

def generate_gradient_numpy(width: int, height: int, hue_offset: int) -> list:
    """Generate rainbow gradient using NumPy."""
    # Create coordinate grids
    x = np.arange(width)
    y = np.arange(height)
    xx, yy = np.meshgrid(x, y)

    # Calculate hues based on position
    hues = ((xx + yy * 0.5 + hue_offset) * 1000) % 65536

    # Build frame array
    frame = np.zeros((height, width, 4), dtype=np.uint16)
    frame[:, :, 0] = hues          # Hue
    frame[:, :, 1] = 65535         # Saturation
    frame[:, :, 2] = 65535         # Brightness
    frame[:, :, 3] = 3500          # Kelvin

    # Convert to list of tuples (row-major)
    return [tuple(p) for p in frame.reshape(-1, 4)]
```

For a complete example including vectorized RGB to HSBK conversion, see
[examples/16_animation_numpy.py](https://github.com/Djelibeybi/lifx-async/blob/main/examples/16_animation_numpy.py).

### Monitor Statistics

```python
total_packets = 0
frame_count = 0
start_time = time.monotonic()

for frame in animation:
    stats = animator.send_frame(frame)
    total_packets += stats.packets_sent
    frame_count += 1

elapsed = time.monotonic() - start_time
fps = frame_count / elapsed
print(f"Average FPS: {fps:.1f}")
print(f"Total packets: {total_packets}")
print(f"Avg packets/frame: {total_packets / frame_count:.1f}")
```

## Troubleshooting

### Flickering or Glitches

**Cause:** Packet loss on the network

**Solutions:**

1. Reduce frame rate (try 20 FPS instead of 30)
2. Ensure good WiFi signal to the device
3. Consider wired connection if possible
4. Accept that some packet loss is normal for UDP

### Animation Appears on Each Tile Separately

**Cause:** Device doesn't have `has_chain` capability, so canvas mode isn't used

**Solutions:**

1. Check device capabilities: only the original LIFX Tile has multi-tile canvas
2. For other matrix devices (Ceiling, Candle, Path), canvas equals tile size

### Wrong Colors on Rotated Tiles

**Cause:** Orientation not detected correctly

**Solutions:**

1. Ensure device chain is loaded before creating animator
2. Check tile accelerometer data via `device.device_chain`
3. Physical tiles must be stable (not moving) for accurate orientation

### Memory Growth

**Cause:** Creating new frame lists each iteration

**Solutions:**

1. Reuse frame lists when possible
2. Use generator patterns for very long animations
3. Clear references after use
