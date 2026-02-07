"""LIFX Animation Module.

This module provides efficient animation support for LIFX devices,
optimized for high-frequency frame delivery.

Architecture:
    FrameBuffer (orientation) -> PacketGenerator -> Direct UDP

Key Components:
    - Orientation: Tile orientation remapping with LRU-cached lookup tables
    - FrameBuffer: Orientation mapping for matrix devices
    - PacketGenerator: Device-specific packet generation (matrix, multizone)
    - Animator: High-level class that sends frames via direct UDP

Quick Start:
    ```python
    from lifx import Animator, MatrixLight

    async with await MatrixLight.from_ip("192.168.1.100") as device:
        # Query device once for tile info
        animator = await Animator.for_matrix(device)

    # Device connection closed - animator sends via direct UDP
    while running:
        # Send HSBK frame (protocol-ready uint16 values)
        hsbk_frame = [(65535, 65535, 65535, 3500)] * animator.pixel_count
        stats = animator.send_frame(hsbk_frame)  # Synchronous for speed
        print(f"Sent {stats.packets_sent} packets")
        await asyncio.sleep(1 / 30)  # 30 FPS

    animator.close()
    ```

HSBK Format:
    All color data uses protocol-ready uint16 values:
    - Hue: 0-65535 (maps to 0-360 degrees)
    - Saturation: 0-65535 (maps to 0.0-1.0)
    - Brightness: 0-65535 (maps to 0.0-1.0)
    - Kelvin: 1500-9000
"""

# Animator - High-level API
from lifx.animation.animator import (
    Animator,
    AnimatorStats,
)

# FrameBuffer - Orientation and canvas mapping
from lifx.animation.framebuffer import (
    FrameBuffer,
    TileRegion,
)

# Orientation - Tile remapping
from lifx.animation.orientation import (
    Orientation,
    build_orientation_lut,
)

# Packet generators
from lifx.animation.packets import (
    HEADER_SIZE,
    SEQUENCE_OFFSET,
    LightPacketGenerator,
    MatrixPacketGenerator,
    MultiZonePacketGenerator,
    PacketGenerator,
    PacketTemplate,
)

__all__ = [
    # Animator (high-level API)
    "Animator",
    "AnimatorStats",
    # FrameBuffer
    "FrameBuffer",
    "TileRegion",
    # Orientation
    "Orientation",
    "build_orientation_lut",
    # Packet generators
    "PacketGenerator",
    "PacketTemplate",
    "LightPacketGenerator",
    "MatrixPacketGenerator",
    "MultiZonePacketGenerator",
    "HEADER_SIZE",
    "SEQUENCE_OFFSET",
]
