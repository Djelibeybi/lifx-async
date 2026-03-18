# Animation API Reference

> **Looking for usage examples?** See the [Animation Guide](../user-guide/animation.md) for tutorials, multi-tile canvas usage, HSBK format details, and troubleshooting. This page covers the API surface only.

The animation module provides efficient high-frequency frame delivery for LIFX devices, optimized for real-time effects at 30+ FPS.

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

### Typical Performance

| Device Type | Pixels | Packets/Frame | Send Time |
|-------------|--------|---------------|-----------|
| Single tile (8x8) | 64 | 1 | <0.5ms |
| 5-tile chain | 320 | 5 | <1ms |
| Large Ceiling (16x8) | 128 | 3 | <1ms |
| MultiZone (82 zones) | 82 | 1 | <0.5ms |

## See Also

- [Animation Guide](../user-guide/animation.md) — Usage guide with examples, multi-tile canvas, and troubleshooting
