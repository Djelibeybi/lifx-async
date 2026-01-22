# Animation Module

The animation module provides efficient high-frequency frame delivery for LIFX devices, optimized
for real-time effects and applications that need to push color data at 30+ FPS.

## Overview

The animation system uses a streamlined architecture optimized for speed:

```
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

For devices with multiple tiles (like the original 5-tile LIFX Tile), the animator creates
a unified canvas based on tile positions (`user_x`, `user_y`). Animations span all tiles
as one continuous image.

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

| Component | Range | Description |
|-----------|-------|-------------|
| Hue | 0-65535 | Maps to 0-360 degrees |
| Saturation | 0-65535 | Maps to 0.0-1.0 |
| Brightness | 0-65535 | Maps to 0.0-1.0 |
| Kelvin | 1500-9000 | Color temperature |

This design pushes conversion work to the caller (e.g. using NumPy) for better performance.
The `lifx-async` library remains dependency-free.

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

::: lifx.animation.animator.Animator
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

### AnimatorStats

Statistics returned by `Animator.send_frame()`.

::: lifx.animation.animator.AnimatorStats
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## FrameBuffer

Canvas mapping and orientation handling for matrix devices.

::: lifx.animation.framebuffer.FrameBuffer
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

### TileRegion

Represents a tile's region within the canvas.

::: lifx.animation.framebuffer.TileRegion
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Packet Generators

Device-specific packet generation with prebaked templates.

### PacketGenerator (Base)

::: lifx.animation.packets.PacketGenerator
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### PacketTemplate

Prebaked packet template for zero-allocation frame updates.

::: lifx.animation.packets.PacketTemplate
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### MatrixPacketGenerator

Generates Set64 packets for MatrixLight devices.

::: lifx.animation.packets.MatrixPacketGenerator
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

### MultiZonePacketGenerator

Generates SetExtendedColorZones packets for MultiZoneLight devices.

::: lifx.animation.packets.MultiZonePacketGenerator
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## Tile Orientation

Pixel remapping for rotated tiles.

### Orientation Enum

::: lifx.animation.orientation.Orientation
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### build_orientation_lut

::: lifx.animation.orientation.build_orientation_lut
    options:
      show_root_heading: true
      heading_level: 4

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

| Device Type | Pixels | Packets/Frame | Send Time |
|-------------|--------|---------------|-----------|
| Single tile (8x8) | 64 | 1 | <0.5ms |
| 5-tile chain | 320 | 5 | <1ms |
| Large Ceiling (16x8) | 128 | 3 | <1ms |
| MultiZone (82 zones) | 82 | 1 | <0.5ms |
