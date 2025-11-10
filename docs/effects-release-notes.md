# Light Effects Framework - Release Notes

## Version 1.3.0 - Light Effects Framework (MVP)

**Release Date:** TBD

We're excited to announce the Light Effects Framework, a comprehensive system for creating and managing visual effects on LIFX devices. This release adds powerful effect orchestration while maintaining lifx-async's commitment to zero dependencies and type safety.

### What's New

#### Core Framework

The Light Effects Framework provides a production-ready effects system built directly into lifx-async:

- **Conductor**: Central orchestrator managing effect lifecycle and automatic state management
- **Effect Base Class**: Abstract base class (`LIFXEffect`) for creating custom effects
- **Built-in Effects**: Two production-ready effect implementations
- **State Preservation**: Automatic capture and restoration of device state (power, color, zones)

#### Built-In Effects

##### EffectPulse

Pulse/blink/breathe effects with five distinct modes:

- **blink**: Standard on/off toggle (1.0s period, 1 cycle default)
- **strobe**: Rapid flashing (0.1s period, 10 cycles default)
- **breathe**: Smooth breathing using SINE waveform (1.0s period, 1 cycle default)
- **ping**: Single pulse with asymmetric duty cycle (quick flash, longer off)
- **solid**: Minimal brightness variation (subtle ambient effect)

All modes support:
- Configurable period and cycle count
- Optional color override with HSBK parameter
- Intelligent color selection based on device capabilities
- Automatic completion and state restoration

##### EffectColorloop

Continuous color rotation effect cycling through the hue spectrum:

- Configurable rotation speed (period, change amount)
- Device spread for rainbow effects across multiple lights
- Optional brightness locking and saturation constraints
- Random elements (direction, device order, transition time) for visual variety
- Runs indefinitely until manually stopped
- State inheritance optimization for seamless transitions

#### Device Support

Full support for all LIFX device types:

- **Color Lights**: Full effect support with HSBK color control
- **Multizone Lights**: Automatic zone color capture and restoration (both extended and standard messages)
- **Tile Devices**: Effects apply to entire tile chain
- **HEV Lights**: Effects don't interfere with HEV cycle functionality
- **Infrared Lights**: Effects control visible light only
- **Monochrome/White Lights**: Brightness-based effects supported (color changes ignored)

#### State Management

Sophisticated automatic state management:

- **Pre-Effect Capture**: Power state, current color, multizone zone colors
- **Smart Power-On**: Configurable automatic power-on with intelligent startup colors
- **Post-Effect Restoration**: All state restored with proper timing delays (0.3s between operations)
- **Multizone Handling**: Extended multizone messages when supported, standard messages as fallback
- **State Inheritance**: Optional optimization skips reset between compatible effects

#### Concurrency & Performance

Built on lifx-async's existing concurrency model:

- **Concurrent Device Operations**: All devices updated in parallel using `asyncio.gather()`
- **Multiple Effects**: Different effects can run simultaneously on different devices
- **Thread-Safe**: Conductor uses `asyncio.Lock()` for safe concurrent access
- **Efficient**: Leverages connection pooling and background response dispatcher

Expected performance:
- Effect startup: <100ms
- State capture: <1 second per device (concurrent for multiple devices)
- State restoration: 0.6-1.0 seconds per device
- Scales linearly with device count

### API Overview

#### Basic Usage

```python
from lifx import discover
from lifx.effects import Conductor, EffectPulse, EffectColorloop

async with discover() as group:
    conductor = Conductor()

    # Pulse effect
    effect = EffectPulse(mode='blink', cycles=5)
    await conductor.start(effect, group.lights)
    await asyncio.sleep(6)

    # ColorLoop effect
    effect = EffectColorloop(period=30, change=20, spread=60)
    await conductor.start(effect, group.lights)
    await asyncio.sleep(120)
    await conductor.stop(group.lights)
```

#### Custom Effects

```python
from lifx.effects import LIFXEffect

class MyEffect(LIFXEffect):
    async def async_play(self) -> None:
        # Custom effect logic
        for light in self.participants:
            await light.set_color(my_color)

        # Restore state when done
        if self.conductor:
            await self.conductor.stop(self.participants)
```

### Documentation

Comprehensive documentation included:

- **Getting Started Guide** (`docs/getting-started/effects.md`): Installation, basic usage, common patterns
- **Effects Reference** (`docs/api/effects.md`): Detailed API documentation for all effects
- **Architecture Guide** (`docs/architecture/effects-architecture.md`): System design, lifecycle, concurrency model
- **Custom Effects Guide** (`docs/user-guide/effects-custom.md`): Creating your own effects
- **Troubleshooting Guide** (`docs/user-guide/effects-troubleshooting.md`): Common issues, device compatibility, debugging

### Examples

Three new example scripts demonstrating effects:

- `examples/06_pulse_effect.py`: All five pulse modes with various configurations
- `examples/07_colorloop_effect.py`: Rainbow effects with different parameters
- `examples/08_custom_effect.py`: Custom `FlashEffect` and `WaveEffect` implementations

### Testing

Comprehensive test coverage for effects framework:

- State capture and restoration tests
- All pulse modes tested
- ColorLoop behavior validated
- Multizone device special handling verified
- Concurrent effect execution tested
- State inheritance optimization validated

### Breaking Changes

**None** - This is purely additive functionality. All existing APIs remain unchanged.

### Dependencies

**Zero new dependencies** - The effects framework uses only:
- Python 3.11+ standard library
- Existing lifx-async modules

### Migration

No migration needed - this is new functionality. Existing code continues to work exactly as before.

For users of the standalone `aiolifx_effects` library:

- The API is similar but not identical
- Main difference: Conductor is required (previously optional)
- State management is automatic (no manual PreState handling)
- See documentation for specific API differences

## What's Not Included (Phase 1 MVP)

The following features are planned for future releases:

### Additional Effect Types (Phase 2)

- **Flicker**: Simulated candle/fire flicker effect
- **Pastels**: Slowly cycle through light pastel colors
- **Random**: Random color changes with configurable randomness factor
- **Twinkle**: Intermittent flashing using themes

### Advanced Features (Phase 2+)

- **Effect Parameters API**: Unified parameter specification and validation
- **Effect Presets**: Pre-configured effect collections
- **Performance Monitoring**: Timing statistics and metrics
- **Tile-Specific Effects**: Per-tile effect control for tile devices
- **Multizone-Specific Effects**: Per-zone effects for multizone devices

### Out of Scope

- **Audio Reactive Effects**: Requires external audio input (different feature)
- **Button/Relay/Switch Support**: Effects are for lighting devices only
- **Rate Limiting**: Application responsibility (consistent with lifx-async philosophy)

## Known Limitations

1. **No Automatic Rate Limiting**: Applications should implement their own rate limiting for rapid-fire effects (LIFX devices handle ~20 messages/second)

2. **Tile Devices**: Currently treated as single units. Per-tile effects not yet implemented (similar to theme support would be needed)

3. **Multizone Devices**: Currently treated as single units for effects. Per-zone effects require custom implementation

4. **Monochrome Devices**: ColorLoop has no visible effect (can't change hue). Pulse effects work but only affect brightness

5. **State Capture Timing**: With 50+ devices, state capture/restoration may take several seconds. Consider staggering effects or grouping devices

6. **Prestate Inheritance**: Only ColorLoop supports state inheritance. Other effect types always reset state (conservative approach to prevent artifacts)

## Upgrade Instructions

### From lifx-async 1.2.x

Simply upgrade to 1.3.0:

```bash
uv pip install --upgrade lifx-async
# or
pip install --upgrade lifx-async
```

Import the new effects API:

```python
from lifx.effects import Conductor, EffectPulse, EffectColorloop, LIFXEffect
```

### From Standalone aiolifx_effects

The lifx-async effects framework is inspired by `aiolifx_effects` but has some differences:

**Key Differences:**

1. **Conductor Required**: Always use `Conductor` (not optional)
2. **Automatic State Management**: No manual `PreState` handling needed
3. **Import Path**: `from lifx.effects import ...` (not `from aiolifx_effects import ...`)
4. **Device Classes**: Use lifx-async device classes (`from lifx import Light`)
5. **No aiolifx Dependency**: Built on lifx-async's native protocol

**Migration Example:**

```python
# Old (aiolifx_effects)
from aiolifx_effects import Conductor, EffectPulse

conductor = Conductor()
effect = EffectPulse(mode='blink', cycles=5)
await conductor.start(effect, lights)

# New (lifx-async)
from lifx.effects import Conductor, EffectPulse

conductor = Conductor()
effect = EffectPulse(mode='blink', cycles=5)
await conductor.start(effect, lights)
# Same API!
```

**Custom Effects:**

```python
# Old (aiolifx_effects)
from aiolifx_effects import Effect

class MyEffect(Effect):
    async def run(self, lights):
        # ...

# New (lifx-async)
from lifx.effects import LIFXEffect

class MyEffect(LIFXEffect):
    async def async_play(self):
        # Access self.participants instead of lights parameter
        # ...
```

See [Custom Effects Guide](user-guide/effects-custom.md) for detailed migration instructions.

## Technical Details

### Module Structure

```
src/lifx/effects/
├── __init__.py              # Public API exports
├── base.py                  # LIFXEffect abstract base class
├── conductor.py             # Conductor orchestrator
├── pulse.py                 # EffectPulse implementation
├── colorloop.py             # EffectColorloop implementation
└── models.py                # PreState, RunningEffect dataclasses
```

### Integration Points

- **Device Layer**: Uses existing `Light`, `MultiZoneLight`, `TileDevice` classes
- **Network Layer**: Leverages connection pooling and concurrent request support
- **Protocol Layer**: Uses existing `HSBK`, `LightWaveform`, packet classes
- **Color Module**: Uses existing `HSBK` color representation

No modifications to core lifx-async modules were required.

### Design Principles

1. **Zero Dependencies**: Only Python stdlib and lifx-async components
2. **State Preservation**: Automatic capture/restore to eliminate user burden
3. **Type Safety**: Full type hints with strict Pyright validation
4. **Async/Await**: Native asyncio throughout, no blocking operations
5. **Extensibility**: Clean abstract base for custom effects
6. **Consistency**: Follows lifx-async patterns and conventions

## Acknowledgments

The Light Effects Framework was inspired by the excellent `aiolifx_effects` project. We've adopted proven patterns while adapting them to lifx-async's architecture and philosophy.

Special thanks to:

- The LIFX protocol team for comprehensive documentation
- The lifx-async community for feedback and testing
- Contributors to aiolifx_effects for pioneering effects orchestration

## Feedback

We'd love to hear your feedback on the Light Effects Framework:

- **GitHub Issues**: [Report bugs or request features](https://github.com/Djelibeybi/lifx-async/issues)
- **GitHub Discussions**: [Share your effects or ask questions](https://github.com/Djelibeybi/lifx-async/discussions)

## What's Next

Future releases will focus on:

1. **Additional Effect Types**: Flicker, Pastels, Random, Twinkle
2. **Per-Tile Effects**: Tile-specific effect control
3. **Per-Zone Effects**: Multizone-specific effects
4. **Effect Presets**: Pre-configured effect collections
5. **Performance Enhancements**: Optimizations for large deployments (50+ devices)

Stay tuned for updates!

## See Also

- [Getting Started with Effects](getting-started/effects.md)
- [Effects API Reference](api/effects.md)
- [Creating Custom Effects](user-guide/effects-custom.md)
- [Effects Architecture](architecture/effects-architecture.md)
- [Troubleshooting Effects](user-guide/effects-troubleshooting.md)
- [Main Changelog](changelog.md)
