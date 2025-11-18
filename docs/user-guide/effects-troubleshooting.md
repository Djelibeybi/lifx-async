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

2. **Devices not reachable**

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

3. **Empty participants list**

```python
# Check you have lights
if not lights:
    print("No lights to apply effect to")
    return

await conductor.start(effect, lights)
```

**Solution:** Always use `await` and verify devices are discovered before starting effects.

---

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

2. **Effect doesn't call conductor.stop() internally**

Custom effects must restore state:

```python
async def async_play(self) -> None:
    # Effect logic
    ...

    # Required for auto-restore
    if self.conductor:
        await self.conductor.stop(self.participants)
```

3. **Network timeout during restoration**

If restoration fails due to network issues, lights may be in inconsistent state.

**Solution:** Check logs for timeout errors, verify network connectivity.

---

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

2. **Custom effect with infinite loop**

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

3. **Missing await in effect logic**

```python
async def async_play(self) -> None:
    # Missing await - blocks event loop
    light.set_color(color)  # Should be: await light.set_color(color)
```

**Solution:** Always use `await` on async operations.

---

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

---

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

---

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

2. **Brightness locked to low value**

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

3. **Monochrome device**

ColorLoop doesn't work on monochrome/white-only lights.

**Solution:** Only use ColorLoop on color-capable devices.

---

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

2. **Extended multizone messages not supported**

Older devices may not support efficient extended multizone messages.

**Solution:** Framework automatically falls back to standard messages. No action needed.

3. **Network timeouts during zone restoration**

If restoring many zones times out, state may be incomplete.

**Solution:** Check network stability, reduce concurrent operations.

---

## Device Compatibility

### Color Lights

**Full Support:** All effects work as expected.

**Models:** LIFX Color, LIFX+, LIFX Mini Color, LIFX Candle Color

---

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

---

### Multizone Lights

**Full Support** with some considerations.

**Works Well:**

- EffectPulse: All zones pulse together
- EffectColorloop: Entire device cycles color

**Special Considerations:**

- Effects apply to entire device, not individual zones
- Zone colors properly restored after effect
- Extended multizone messages used when available

**Potential Enhancement:** Future versions could support per-zone effects.

**Models:** LIFX Z, LIFX Beam

---

### Matrix Lights (Tile/Candle/Path)

**Full Support** (treated as single unit).

**Works Well:**

- EffectPulse: All tiles/zones pulse together
- EffectColorloop: All tiles/zones cycle color together

**Limitation:** Current implementation doesn't use per-tile control. All tiles show same color.

**Potential Enhancement:** Future versions could support per-tile effects (similar to theme support).

**Models:** LIFX Tile, LIFX Candle, LIFX Path

---

### HEV Lights

**Full Support** (treated like standard color lights).

**Note:** Effects don't interfere with HEV cycle functionality.

**Models:** LIFX Clean

---

### Infrared Lights

**Full Support** (treated like standard color lights).

**Note:** Effects control visible light only, infrared LED not affected.

**Models:** LIFX+, LIFX Night Vision

---

## Performance Issues

### Slow Effect Startup

**Symptom:** Noticeable delay before effect starts.

**Cause:** State capture requires network round trips.

**Expected Timing:**

- Single device: <1 second
- 10 devices: <1 second (concurrent)
- 50 devices: 1-2 seconds

**If Slower:**

- Check network latency (ping devices)
- Verify devices are on local network (not remote)
- Reduce concurrent discovery operations

---

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

2. **Network congestion**

Too many packets sent too quickly can overwhelm network or devices.

**Solution:** Add rate limiting:

```python
# In custom effect
for iteration in range(self.iterations):
    await self._update_colors()
    await asyncio.sleep(0.05)  # Rate limit: max 20/sec
```

3. **Blocking operations in effect**

```python
# Bad - blocking sleep
import time
time.sleep(1)  # Blocks entire event loop!

# Good - async sleep
await asyncio.sleep(1)
```

**Solution:** Always use async operations.

---

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

2. Check for sequential operations in custom effects

3. Verify network capacity isn't saturated

**Recommendation:** For 50+ devices, consider:

- Staggering effect starts
- Using fewer concurrent effects
- Implementing application-level rate limiting

---

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

2. **Multizone device powered off during capture**

Older devices report inaccurate zone colors when off.

**Workaround:** Power on before effect:

```python
for light in lights:
    await light.set_power(True)
await asyncio.sleep(0.5)
await conductor.start(effect, lights)
```

---

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

```
WARNING:lifx.effects.conductor:Failed to restore color for d073d5123456: TimeoutError
```

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

### Tile Per-Tile Effects

Current implementation treats tiles as a single unit.

**Limitation:** Can't apply different effects to individual tiles within a tile chain.

**Workaround:** Use theme support for per-tile colors, or wait for future enhancement.

**Potential Future:** Per-tile effect logic could be added using `MatrixLight.set_matrix_colors()`.

---

### Multizone Per-Zone Effects

Current implementation treats multizone device as a single unit.

**Limitation:** Can't pulse individual zones or create zone-specific effects.

**Workaround:** Manually use `set_color_zones()` in custom effects.

**Example:**

```python
from lifx import MultiZoneLight

async def async_play(self) -> None:
    for light in self.participants:
        if isinstance(light, MultiZoneLight):
            # Control individual zones
            zone_count = await light.get_zone_count()
            for i in range(zone_count):
                color = self._get_zone_color(i)
                await light.set_color_zones(i, i, color)
```

---

### Button/Relay/Switch Devices

The effects framework **only supports lighting devices**.

**Not Supported:**

- LIFX Switch
- LIFX Relay
- Button devices

**Reason:** Effects are designed for visual output (lights), not control devices.

---

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

---

### Prestate Inheritance Limitations

State inheritance is conservative to prevent artifacts.

**Current Behavior:**

- Only `EffectColorloop` supports inheritance (from other `EffectColorloop`)
- Other effect types always reset state

**Enhancement Opportunity:** More effect types could support inheritance with careful design.

---

## Still Having Issues?

If you're experiencing issues not covered here:

1. **Check the logs** with debug logging enabled
2. **Test with single device** to isolate the problem
3. **Verify device firmware** is up to date
4. **Check network** connectivity and stability
5. **Review examples** in the `examples/` directory
6. **Report issues** on [GitHub Issues](https://github.com/Djelibeybi/lifx-async/issues)

When reporting issues, include:

- lifx-async version
- Python version
- Device model(s) affected
- Minimal reproduction code
- Full error message and traceback
- Debug logs if applicable

## See Also

- [Getting Started](../getting-started/effects.md) - Basic usage patterns
- [Effects Reference](../api/effects.md) - Detailed API documentation
- [Custom Effects](effects-custom.md) - Creating your own effects
- [Architecture](../architecture/effects-architecture.md) - How the system works
