# Effects Troubleshooting

This guide helps you diagnose and resolve common issues when using the Light Effects Framework.

## Table of Contents

- [Common Issues](#common-issues)
- [Device Compatibility](#device-compatibility)
- [Performance Issues](#performance-issues)
- [State Management](#state-management)
- [Debugging Techniques](#debugging-techniques)
- [Known Limitations](#known-limitations)

## Common Issues

### Effects Don't Start

**Symptom:** Calling `conductor.start()` doesn't appear to do anything.

**Possible Causes:**

1. **No await keyword**

```python
# Wrong - missing await
conductor.start(effect, lights)  # Returns immediately, nothing happens

# Correct
await conductor.start(effect, lights)
```

1. **Devices not reachable**

```python
# Check device connectivity first
from lifx import discover, DeviceGroup

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

if not group.lights:
    print("No devices found!")
    return

# Now safe to use effects
conductor = Conductor()
await conductor.start(effect, group.lights)
```

1. **Empty participants list**

```python
# Check you have lights
if not lights:
    print("No lights to apply effect to")
    return

await conductor.start(effect, lights)
```

**Solution:** Always use `await` and verify devices are discovered before starting effects.

______________________________________________________________________

### Lights Don't Restore to Original State

**Symptom:** After effect completes, lights stay in effect state instead of returning to original.

**Possible Causes:**

1. **Missing conductor.stop() call**

```python
# ColorLoop requires manual stop
effect = EffectColorloop(period=30)
await conductor.start(effect, lights)
await asyncio.sleep(60)
# MISSING: await conductor.stop(lights)
```

**Solution:** Always call `conductor.stop()` for continuous effects:

```python
await conductor.stop(lights)
```

1. **Effect doesn't call conductor.stop() internally**

Custom effects must restore state:

```python
async def async_play(self) -> None:
    # Effect logic
    ...

    # Required for auto-restore
    if self.conductor:
        await self.conductor.stop(self.participants)
```

1. **Network timeout during restoration**

If restoration fails due to network issues, lights may be in inconsistent state.

**Solution:** Check logs for timeout errors, verify network connectivity.

______________________________________________________________________

### Effect Appears to Freeze

**Symptom:** Effect starts but never completes, script hangs.

**Possible Causes:**

1. **ColorLoop running indefinitely**

ColorLoop is designed to run forever:

```python
# This will hang forever
effect = EffectColorloop(period=30)
await conductor.start(effect, lights)
# Script hangs here - ColorLoop never completes
```

**Solution:** Call `conductor.stop()` explicitly:

```python
effect = EffectColorloop(period=30)
await conductor.start(effect, lights)
await asyncio.sleep(60)  # Let it run
await conductor.stop(lights)  # Stop it
```

1. **Custom effect with infinite loop**

```python
async def async_play(self) -> None:
    while True:  # Infinite loop!
        await self._do_something()
```

**Solution:** Add stop condition:

```python
async def async_play(self) -> None:
    self._running = True
    while self._running:
        await self._do_something()
```

1. **Missing await in effect logic**

```python
async def async_play(self) -> None:
    # Missing await - blocks event loop
    light.set_color(color)  # Should be: await light.set_color(color)
```

**Solution:** Always use `await` on async operations.

______________________________________________________________________

### Lights Flash/Reset Between Effects

**Symptom:** When starting second effect, lights briefly return to original state before new effect starts.

**Cause:** State inheritance not enabled.

```python
# Each effect resets to original state
effect1 = EffectColorloop(period=30)
await conductor.start(effect1, lights)
await asyncio.sleep(10)

effect2 = EffectColorloop(period=20)  # Lights briefly reset here
await conductor.start(effect2, lights)
```

**Solution:** Effects must implement `inherit_prestate()` to prevent reset:

```python
class EffectColorloop(LIFXEffect):
    def inherit_prestate(self, other: LIFXEffect) -> bool:
        return isinstance(other, EffectColorloop)
```

This is already implemented for `EffectColorloop`, but custom effects may need it.

**Note:** For different effect types, the reset is intentional behavior.

______________________________________________________________________

### Pulse Effect Too Fast/Slow

**Symptom:** Pulse timing doesn't match expectations.

**Cause:** Misunderstanding period vs. total duration.

```python
# This runs for 1 second total (period=1.0, cycles=1)
effect = EffectPulse(mode='blink', period=1.0, cycles=1)

# This runs for 5 seconds total (period=1.0, cycles=5)
effect = EffectPulse(mode='blink', period=1.0, cycles=5)

# This runs for 2 seconds total (period=2.0, cycles=1)
effect = EffectPulse(mode='blink', period=2.0, cycles=1)
```

**Solution:** Total duration = `period * cycles`

```python
# Want 10-second effect?
effect = EffectPulse(mode='breathe', period=2.0, cycles=5)  # 2.0 * 5 = 10s
```

______________________________________________________________________

### ColorLoop Colors Look Wrong

**Symptom:** ColorLoop shows unexpected colors or is too dim/bright.

**Possible Causes:**

1. **Saturation constraints too restrictive**

```python
# Very low saturation = washed out colors
effect = EffectColorloop(saturation_min=0.1, saturation_max=0.3)  # Pastels
```

**Solution:** Use higher saturation for vibrant colors:

```python
effect = EffectColorloop(saturation_min=0.8, saturation_max=1.0)
```

1. **Brightness locked to low value**

```python
# Locked to 30% brightness
effect = EffectColorloop(brightness=0.3)  # Dim!
```

**Solution:** Use higher brightness or `None` to preserve original:

```python
effect = EffectColorloop(brightness=None)  # Preserve original
# or
effect = EffectColorloop(brightness=0.8)  # 80% brightness
```

1. **Monochrome device**

ColorLoop doesn't work on monochrome/white-only lights.

**Solution:** Only use ColorLoop on color-capable devices.

______________________________________________________________________

### Multizone Lights Don't Restore Zones Correctly

**Symptom:** After effect, multizone light zones are wrong color or all same color.

**Possible Causes:**

1. **Device was powered off before effect**

Some older multizone devices report all zones as the same color when powered off.

**Workaround:** Ensure lights are powered on before starting effects:

```python
# Power on first
for light in lights:
    await light.set_power(True)
await asyncio.sleep(0.5)

# Now start effect
await conductor.start(effect, lights)
```

1. **Extended multizone messages not supported**

Older devices may not support efficient extended multizone messages.

**Solution:** Framework automatically falls back to standard messages. No action needed.

1. **Network timeouts during zone restoration**

If restoring many zones times out, state may be incomplete.

**Solution:** Check network stability, reduce concurrent operations.

______________________________________________________________________

## Device Compatibility

### Color Lights

**Full Support:** All effects work as expected.

**Models:** LIFX Color, LIFX+, LIFX Mini Color, LIFX Candle Color

______________________________________________________________________

### Monochrome/White Lights

**Limited Support:** Only brightness-based effects work.

**What Works:**

- EffectPulse: Brightness pulsing (hue/saturation ignored)
- Custom effects using only brightness

**What Doesn't Work:**

- EffectColorloop: No visible effect (can't change hue)
- Color-based custom effects: Only brightness changes visible

**Recommendation:** Avoid ColorLoop on monochrome devices.

**Models:** LIFX White, LIFX Mini White, LIFX Downlight

______________________________________________________________________

### Multizone Lights

**Full Support** via animation module.

**Works Well:**

- EffectPulse: All zones pulse together (firmware waveform)
- EffectColorloop: Entire device cycles color (via `MultiZonePacketGenerator`)
- Custom `FrameEffect`: Per-zone control via `generate_frame()` with `pixel_count = zone_count`

**Special Considerations:**

- EffectPulse applies uniformly (not per-zone)
- `FrameEffect` subclasses can generate individual zone colors
- Zones are properly restored after effect

**Models:** LIFX Z, LIFX Beam

______________________________________________________________________

### Matrix Lights (Tile/Candle/Path)

**Full Support** via animation module.

**Works Well:**

- EffectPulse: All tiles pulse together (firmware waveform)
- EffectColorloop: All pixels cycle color together (via `MatrixPacketGenerator`)
- Custom `FrameEffect`: Per-pixel control via `generate_frame()` with `pixel_count = W * H`

**Special Considerations:**

- `FrameContext` provides `canvas_width` and `canvas_height` for 2D-aware effects
- Multi-tile canvas mapping is automatic (tile orientation correction included)
- EffectPulse applies uniformly (not per-pixel)

**Models:** LIFX Tile, LIFX Candle, LIFX Path

______________________________________________________________________

### HEV Lights

**Full Support** (treated like standard color lights).

**Note:** Effects don't interfere with HEV cycle functionality.

**Models:** LIFX Clean

______________________________________________________________________

### Infrared Lights

**Full Support** (treated like standard color lights).

**Note:** Effects control visible light only, infrared LED not affected.

**Models:** LIFX+, LIFX Night Vision

______________________________________________________________________

## Performance Issues

### Slow Effect Startup

**Symptom:** Noticeable delay before effect starts.

**Cause:** State capture requires network round trips.

**Expected Timing:**

- Single device: \<1 second
- 10 devices: \<1 second (concurrent)
- 50 devices: 1-2 seconds

**If Slower:**

- Check network latency (ping devices)
- Verify devices are on local network (not remote)
- Reduce concurrent discovery operations

______________________________________________________________________

### Choppy/Stuttering Effects

**Symptom:** Effects don't run smoothly, visible stuttering.

**Possible Causes:**

1. **Too many concurrent effects**

```python
# 50 devices all running independent effects
for light in lights:
    await conductor.start(effect, [light])  # Too many!
```

**Solution:** Group devices:

```python
# All devices in one effect
await conductor.start(effect, lights)
```

1. **Network congestion**

Too many packets sent too quickly can overwhelm network or devices.

**Solution:** Add rate limiting:

```python
# In custom effect
for iteration in range(self.iterations):
    await self._update_colors()
    await asyncio.sleep(0.05)  # Rate limit: max 20/sec
```

1. **Blocking operations in effect**

```python
# Bad - blocking sleep
import time
time.sleep(1)  # Blocks entire event loop!

# Good - async sleep
await asyncio.sleep(1)
```

**Solution:** Always use async operations.

______________________________________________________________________

### Effects on Many Devices Are Slow

**Symptom:** Effects take much longer with many devices.

**Expected Behavior:** Effects should scale linearly (not exponentially).

**If Slower Than Expected:**

1. Verify concurrent operations are used:

```python
# Good - concurrent
await asyncio.gather(*[
    light.set_color(color) for light in lights
])

# Bad - sequential
for light in lights:
    await light.set_color(color)
```

1. Check for sequential operations in custom effects
1. Verify network capacity isn't saturated

**Recommendation:** For 50+ devices, consider:

- Staggering effect starts
- Using fewer concurrent effects
- Implementing application-level rate limiting

______________________________________________________________________

## State Management

### State Captured Incorrectly

**Symptom:** Restored state doesn't match original state.

**Possible Causes:**

1. **State changed between capture and effect**

```python
# State captured here
await conductor.start(effect, lights)

# Meanwhile, user changes light with app
# Effect completes, restores OLD state (not current state)
```

**Solution:** Effects framework works correctly - this is expected behavior. State is captured at effect start.

1. **Multizone device powered off during capture**

Older devices report inaccurate zone colors when off.

**Workaround:** Power on before effect:

```python
for light in lights:
    await light.set_power(True)
await asyncio.sleep(0.5)
await conductor.start(effect, lights)
```

______________________________________________________________________

### State Restoration Fails Silently

**Symptom:** State restoration errors not visible.

**Cause:** Errors are logged but don't raise exceptions (by design - one failed device shouldn't stop others).

**Solution:** Enable debug logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('lifx.effects')
logger.setLevel(logging.DEBUG)
```

Check logs for warnings like:

```text
WARNING:lifx.effects.conductor:Failed to restore color for d073d5123456: TimeoutError
```

______________________________________________________________________

## Debugging Techniques

### Enable Debug Logging

See detailed information about effect execution:

```python
import logging

# Enable debug logging for effects
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Just effects module
logger = logging.getLogger('lifx.effects')
logger.setLevel(logging.DEBUG)
```

**Output shows:**

- State capture details
- Prestate inheritance decisions
- State restoration steps
- Error messages

______________________________________________________________________

### Check Current Effect Status

See what's currently running on each device:

```python
conductor = Conductor()

# After starting effects
for light in lights:
    current = conductor.effect(light)
    if current:
        print(f"{light.label}: {type(current).__name__}")
    else:
        print(f"{light.label}: idle")
```

______________________________________________________________________

### Verify Device Connectivity

Before effects, verify all devices are reachable:

```python
async def check_connectivity(lights):
    """Verify all lights respond."""
    for light in lights:
        try:
            label = await light.get_label()
            print(f"✓ {label} reachable")
        except Exception as e:
            print(f"✗ {light.serial} unreachable: {e}")

# Use before effects
from lifx import discover, DeviceGroup

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

await check_connectivity(group.lights)
```

______________________________________________________________________

### Test with Single Device First

Isolate issues by testing with one device:

```python
# Test with single device first
from lifx import discover, DeviceGroup

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

if group.lights:
    test_light = group.lights[0]

    conductor = Conductor()
    effect = EffectPulse(mode='blink', cycles=3)

    print(f"Testing with {await test_light.get_label()}")
    await conductor.start(effect, [test_light])
    await asyncio.sleep(4)

    print("Test complete - check if light restored correctly")
```

______________________________________________________________________

### Validate Effect Parameters

Check that effect parameters are valid:

```python
# Add parameter validation
class MyEffect(LIFXEffect):
    def __init__(self, count: int, period: float, power_on: bool = True):
        super().__init__(power_on=power_on)

        if count < 1:
            raise ValueError(f"count must be positive, got {count}")
        if period <= 0:
            raise ValueError(f"period must be positive, got {period}")

        self.count = count
        self.period = period
```

______________________________________________________________________

### Measure Effect Timing

Verify effect runs for expected duration:

```python
import time

start = time.time()

effect = EffectPulse(mode='blink', period=1.0, cycles=5)
await conductor.start(effect, lights)

# Expected: 5 seconds
await asyncio.sleep(6)

elapsed = time.time() - start
print(f"Effect took {elapsed:.1f}s (expected ~5s)")
```

______________________________________________________________________

## Known Limitations

### Rate Limiting

The effects framework **does not** implement automatic rate limiting.

**Impact:** Sending too many concurrent commands may overwhelm devices or network.

**LIFX Limit:** ~20 messages per second per device

**Recommendation:** For rapid-fire effects, add your own rate limiting:

```python
async def async_play(self) -> None:
    for i in range(100):
        await self._update_lights()
        await asyncio.sleep(0.05)  # 20/sec max
```

______________________________________________________________________

### Per-Pixel Effects on Matrix and Multizone Devices

`FrameEffect` subclasses have full per-pixel control via the animation module. The `FrameContext` provides `pixel_count`, `canvas_width`, and `canvas_height`, and `generate_frame()` returns individual colors for each pixel.

**Matrix devices:** `generate_frame()` receives `pixel_count = W * H` (e.g., 64 for a single 8x8 tile, 320 for 5 tiles). Pixels are in row-major order across the canvas.

**Multizone devices:** `generate_frame()` receives `pixel_count = N` (number of zones). Each color maps to one zone.

**Example: Per-pixel rainbow using FrameEffect:**

```python
from lifx import FrameEffect, FrameContext, HSBK

class PixelRainbow(FrameEffect):
    """Rainbow across all pixels on any device type."""

    @property
    def name(self) -> str:
        return "pixel_rainbow"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        colors = []
        for i in range(ctx.pixel_count):
            hue = (ctx.elapsed_s * 30 + i * 360 / ctx.pixel_count) % 360
            colors.append(HSBK(hue=hue, saturation=1.0, brightness=0.8, kelvin=3500))
        return colors
```

**Note:** `EffectPulse` still treats all device types as single units (applies firmware waveforms uniformly). For per-pixel pulse effects, use a `FrameEffect` instead.

______________________________________________________________________

### Button/Relay/Switch Devices

The effects framework **only supports lighting devices**.

**Not Supported:**

- LIFX Switch
- LIFX Relay
- Button devices

**Reason:** Effects are designed for visual output (lights), not control devices.

______________________________________________________________________

### Network Timeouts with Many Devices

With 50+ devices, state capture/restoration may timeout.

**Symptoms:**

- Some devices don't restore state
- Timeout errors in logs

**Solutions:**

- Increase timeout values (requires lifx-async modification)
- Reduce number of concurrent effects
- Group devices and stagger effect starts
- Verify network infrastructure can handle traffic

______________________________________________________________________

### Prestate Inheritance Limitations

State inheritance is conservative to prevent artifacts.

**Current Behavior:**

- Only `EffectColorloop` supports inheritance (from other `EffectColorloop`)
- Other effect types always reset state

**Enhancement Opportunity:** More effect types could support inheritance with careful design.

______________________________________________________________________

## Still Having Issues?

If you're experiencing issues not covered here:

1. **Check the logs** with debug logging enabled
1. **Test with single device** to isolate the problem
1. **Verify device firmware** is up to date
1. **Check network** connectivity and stability
1. **Review examples** in the `examples/` directory
1. **Report issues** on [GitHub Issues](https://github.com/Djelibeybi/lifx-async/issues)

When reporting issues, include:

- lifx-async version
- Python version
- Device model(s) affected
- Minimal reproduction code
- Full error message and traceback
- Debug logs if applicable

## See Also

- [Getting Started](https://djelibeybi.github.io/lifx-async/getting-started/effects/index.md) - Basic usage patterns
- [Effects Reference](https://djelibeybi.github.io/lifx-async/api/effects/index.md) - Detailed API documentation
- [Custom Effects](https://djelibeybi.github.io/lifx-async/user-guide/effects-custom/index.md) - Creating your own effects
- [Architecture](https://djelibeybi.github.io/lifx-async/architecture/effects-architecture/index.md) - How the system works
