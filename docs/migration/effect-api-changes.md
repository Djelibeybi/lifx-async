# Effect API Changes (v4.3.0)

This document describes changes to the effect handling API introduced in version 4.3.0.

## Overview

The effect handling API has been simplified and unified to provide a cleaner, more consistent interface:

1. **Unified Effect Enum**: `MultiZoneEffectType` and `TileEffectType` merged into `FirmwareEffect`
2. **Direction Enum**: New `Direction` enum for MOVE effect direction control
3. **Simplified Methods**: Effect methods renamed for clarity (`set_effect`, `get_effect`)
4. **Unified Application Request**: `MultiZoneExtendedApplicationRequest` removed in favor of single `MultiZoneApplicationRequest`

## Changes

### 1. Effect Type Enums Consolidated

**Before:**
```python
from lifx import MultiZoneEffectType, TileEffectType

# MultiZone effects
effect = MultiZoneEffectType.MOVE

# Tile effects
effect = TileEffectType.MORPH
```

**After:**
```python
from lifx import FirmwareEffect

# All firmware effects (multizone and matrix)
effect = FirmwareEffect.MOVE   # MultiZone
effect = FirmwareEffect.MORPH  # Matrix/Tile
effect = FirmwareEffect.FLAME  # Matrix/Tile
effect = FirmwareEffect.SKY    # Matrix/Tile
```

### 2. Direction Control for MOVE Effects

**Before:**
```python
# Direction was embedded in specialized methods
await light.set_move_effect(speed=5.0, direction=1)  # 0=reversed, 1=forward
```

**After:**
```python
from lifx import FirmwareEffect, Direction

# Direction is a proper enum with named values
await light.set_effect(
    effect_type=FirmwareEffect.MOVE,
    speed=5.0,
    direction=Direction.FORWARD,  # or Direction.REVERSED
)

# Direction can also be accessed as a property on MultiZoneEffect
effect = await light.get_effect()
if effect.effect_type == FirmwareEffect.MOVE:
    print(f"Direction: {effect.direction.name}")  # FORWARD or REVERSED
```

### 3. Method Naming Simplified

**Before:**
```python
# MultiZone devices
await multizone_light.set_multizone_effect(...)
effect = await multizone_light.get_multizone_effect()

# Tile/Matrix devices
await matrix_light.set_tile_effect(...)
effect = await matrix_light.get_tile_effect()

# Specialized MOVE method
await multizone_light.set_move_effect(speed=5.0, direction=1)
```

**After:**
```python
# Unified naming across all device types
await multizone_light.set_effect(effect_type=FirmwareEffect.MOVE, ...)
effect = await multizone_light.get_effect()

await matrix_light.set_effect(effect_type=FirmwareEffect.FLAME, ...)
effect = await matrix_light.get_effect()

# No more specialized methods - use set_effect with Direction enum
```

### 4. Application Request Enum Unified

**Before:**
```python
from lifx import MultiZoneApplicationRequest, MultiZoneExtendedApplicationRequest

# Different enums for different packet types
await light.set_color_zones(..., apply=MultiZoneApplicationRequest.APPLY)
await light.set_extended_color_zones(..., apply=MultiZoneExtendedApplicationRequest.APPLY)
```

**After:**
```python
from lifx import MultiZoneApplicationRequest

# Single enum for all multizone application control
await light.set_color_zones(..., apply=MultiZoneApplicationRequest.APPLY)
await light.set_extended_color_zones(..., apply=MultiZoneApplicationRequest.APPLY)
```

## Migration Guide

### Updating MultiZone Effect Code

**Old Code:**
```python
from lifx import MultiZoneLight, MultiZoneEffectType

async with await MultiZoneLight.from_ip("192.168.1.100") as light:
    # Old API
    await light.set_multizone_effect(
        effect_type=MultiZoneEffectType.MOVE,
        speed=5.0,
    )

    # Or using specialized method
    await light.set_move_effect(speed=5.0, direction=1)

    effect = await light.get_multizone_effect()
```

**New Code:**
```python
from lifx import MultiZoneLight, FirmwareEffect, Direction

async with await MultiZoneLight.from_ip("192.168.1.100") as light:
    # New unified API
    await light.set_effect(
        effect_type=FirmwareEffect.MOVE,
        speed=5.0,
        direction=Direction.FORWARD,
    )

    effect = await light.get_effect()
    if effect.effect_type == FirmwareEffect.MOVE:
        print(f"Direction: {effect.direction.name}")
```

### Updating Matrix/Tile Effect Code

**Old Code:**
```python
from lifx import MatrixLight, TileEffectType

async with await MatrixLight.from_ip("192.168.1.100") as light:
    # Old API
    await light.set_tile_effect(
        effect_type=TileEffectType.FLAME,
        speed=5.0,
    )

    effect = await light.get_tile_effect()
```

**New Code:**
```python
from lifx import MatrixLight, FirmwareEffect

async with await MatrixLight.from_ip("192.168.1.100") as light:
    # New unified API
    await light.set_effect(
        effect_type=FirmwareEffect.FLAME,
        speed=5.0,
    )

    effect = await light.get_effect()
```

### Updating Application Request Code

**Old Code:**
```python
from lifx import MultiZoneApplicationRequest, MultiZoneExtendedApplicationRequest

# Standard zones
await light.set_color_zones(
    start=0,
    end=9,
    color=color,
    apply=MultiZoneApplicationRequest.APPLY,
)

# Extended zones
await light.set_extended_color_zones(
    zone_index=0,
    colors=colors,
    apply=MultiZoneExtendedApplicationRequest.APPLY,
)
```

**New Code:**
```python
from lifx import MultiZoneApplicationRequest

# Standard zones
await light.set_color_zones(
    start=0,
    end=9,
    color=color,
    apply=MultiZoneApplicationRequest.APPLY,
)

# Extended zones
await light.set_extended_color_zones(
    zone_index=0,
    colors=colors,
    apply=MultiZoneApplicationRequest.APPLY,  # Same enum
)
```

## Summary of Removals

The following have been **removed** in v4.3.0:

- `lifx.protocol.protocol_types.MultiZoneEffectType` → use `FirmwareEffect`
- `lifx.protocol.protocol_types.TileEffectType` → use `FirmwareEffect`
- `lifx.protocol.protocol_types.MultiZoneExtendedApplicationRequest` → use `MultiZoneApplicationRequest`
- `MultiZoneLight.set_multizone_effect()` → use `set_effect()`
- `MultiZoneLight.get_multizone_effect()` → use `get_effect()`
- `MultiZoneLight.set_move_effect()` → use `set_effect(effect_type=FirmwareEffect.MOVE, direction=Direction.FORWARD)`
- `MultiZoneLight.get_move_effect()` → use `get_effect()` and access `effect.direction`
- `MatrixLight.set_tile_effect()` → use `set_effect()`
- `MatrixLight.get_tile_effect()` → use `get_effect()`

## Benefits

These changes provide several improvements:

1. **Consistency**: All firmware effects use the same enum and method names
2. **Type Safety**: Direction is now a proper enum instead of integer values (0/1)
3. **Discoverability**: Cleaner API with fewer specialized methods
4. **Simplicity**: One enum for application requests instead of two identical ones
5. **Maintainability**: Easier to extend with new effect types in the future
