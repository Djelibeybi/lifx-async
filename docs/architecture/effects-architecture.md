# Effects Architecture

This document provides a comprehensive overview of the Light Effects Framework architecture, including design decisions, implementation details, and lifecycle management.

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Component Architecture](#component-architecture)
- [Effect Lifecycle](#effect-lifecycle)
- [State Management](#state-management)
- [Concurrency Model](#concurrency-model)
- [Device Type Handling](#device-type-handling)
- [Design Decisions](#design-decisions)

## High-Level Overview

The Light Effects Framework is built on a layered architecture that separates concerns and provides a clean abstraction for effect management:

```
┌─────────────────────────────────────────────────────┐
│              Application Layer                       │
│  (User code, business logic, effect selection)      │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│              Effects API Layer                       │
│   • Conductor (orchestration)                       │
│   • EffectPulse, EffectColorloop (implementations)  │
│   • LIFXEffect (base class)                         │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│            Device Layer (lifx.devices)               │
│   • Light, MultiZoneLight, MatrixLight              │
│   • Device state methods (get_color, set_color)     │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│           Network Layer (lifx.network)               │
│   • DeviceConnection (UDP transport)                │
│   • Message building and parsing                    │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│          Protocol Layer (lifx.protocol)              │
│   • Binary serialization/deserialization            │
│   • Packet definitions (auto-generated)             │
└─────────────────────────────────────────────────────┘
```

### Key Principles

1. **Zero Dependencies**: Uses only Python stdlib and existing lifx-async components
2. **State Preservation**: Automatically captures and restores device state
3. **Type Safety**: Full type hints with strict Pyright validation
4. **Async/Await**: Native asyncio for concurrent operations
5. **Extensibility**: Abstract base class for custom effects

## Component Architecture

### Module Structure

```
src/lifx/effects/
├── __init__.py              # Public API exports
├── base.py                  # LIFXEffect abstract base class
├── conductor.py             # Conductor orchestrator
├── pulse.py                 # EffectPulse implementation
├── colorloop.py             # EffectColorloop implementation
├── models.py                # PreState, RunningEffect dataclasses
└── utils.py                 # Shared utilities (future)
```

### Component Responsibilities

#### Conductor (`conductor.py`)

**Purpose:** Central orchestrator managing effect lifecycle across multiple devices.

**Responsibilities:**

- Track running effects per device (serial → RunningEffect mapping)
- Capture device state before effects
- Power on devices if needed
- Execute effects via `effect.async_perform()`
- Restore device state after effects complete
- Handle concurrent effects on different devices
- Provide thread-safe state management with `asyncio.Lock()`

**Key Data Structures:**

```python
class Conductor:
    _running: dict[str, RunningEffect]  # serial → RunningEffect
    _lock: asyncio.Lock                 # Thread-safe access
```

#### LIFXEffect Base Class (`base.py`)

**Purpose:** Abstract base for all effect implementations.

**Responsibilities:**

- Define effect interface (abstract `async_play()` method)
- Handle power-on logic in `async_perform()`
- Provide startup color via `from_poweroff_hsbk()`
- Enable state inheritance optimization via `inherit_prestate()`
- Store conductor reference and participants

**Key Methods:**

```python
class LIFXEffect(ABC):
    async def async_perform(participants):  # Setup + call async_play()
        ...

    @abstractmethod
    async def async_play():                 # Effect logic (override)
        ...

    async def from_poweroff_hsbk(light):    # Startup color (override)
        ...

    def inherit_prestate(other):            # State inheritance (override)
        ...
```

#### Effect Implementations

**EffectPulse (`pulse.py`):**

- Implements pulse/blink/breathe effects
- Five modes with different timing and waveforms
- Intelligent color selection based on mode
- Auto-completion after configured cycles

**EffectColorloop (`colorloop.py`):**

- Implements continuous hue rotation
- Randomized direction, device order, saturation
- Runs indefinitely until stopped
- Supports state inheritance for seamless transitions

#### Data Models (`models.py`)

**PreState:**

Stores device state before effect:

```python
@dataclass
class PreState:
    power: bool                     # Power state (on/off)
    color: HSBK                     # Current color
    zone_colors: list[HSBK] | None  # Multizone colors (if applicable)
```

**RunningEffect:**

Associates effect with its pre-state:

```python
@dataclass
class RunningEffect:
    effect: LIFXEffect    # Effect instance
    prestate: PreState    # Captured state
```

## Effect Lifecycle

The effect lifecycle consists of five distinct phases:

### 1. Initialization

User creates effect instance with desired parameters:

```python
effect = EffectPulse(mode='blink', cycles=5)
```

**What happens:**

- Effect object created with parameters stored
- No network activity yet
- No conductor association yet

### 2. State Capture

Conductor starts effect and captures current device state:

```python
await conductor.start(effect, [light1, light2])
```

**What happens:**

```
For each light:
  1. Check if prestate can be inherited from running effect
  2. If not, capture new prestate:
     a. Get power state (get_power)
     b. Get current color (get_color)
     c. Get zone colors if multizone (get_color_zones or get_extended_color_zones)
  3. Store in RunningEffect and register in conductor._running
```

**Timing:** <1 second per device (mostly network I/O)

**Special Cases:**

- **Prestate Inheritance:** If `effect.inherit_prestate(current_effect)` returns `True`, reuses existing PreState
- **Multizone Devices:** Uses extended messages if supported, falls back to standard messages
- **Powered-off Devices:** All state is still captured (including zone colors that may be inaccurate)

### 3. Power-On (Optional)

If `effect.power_on == True`, devices are powered on:

```python
async def async_perform(self, participants):
    if self.power_on:
        for light in self.participants:
            power_level = await light.get_power()
            if power_level == 0:
                startup_color = await self.from_poweroff_hsbk(light)
                await light.set_color(startup_color, duration=0)
                await light.set_power(True, duration=0.3)
```

**What happens:**

```
For each powered-off light:
  1. Get startup color from from_poweroff_hsbk()
  2. Set color immediately (duration=0)
  3. Power on with 0.3s fade (duration=0.3)
```

**Timing:** 0.3 seconds per powered-off device

### 4. Effect Execution

Effect logic runs via `async_play()`:

```python
await effect.async_play()
```

**What happens:**

- Subclass-specific effect logic executes
- Can access `self.participants` and `self.conductor`
- Can issue commands to devices
- Pulse effects: Send waveform, wait for completion
- ColorLoop effects: Continuous loop until stopped

**Timing:**

- EffectPulse: `period * cycles` seconds
- EffectColorloop: Runs indefinitely

### 5. State Restoration

Conductor restores devices to pre-effect state:

```python
await conductor.stop([light1, light2])
```

**What happens:**

```
For each light:
  1. Restore multizone colors (if applicable):
     - Use extended messages if supported
     - Use standard messages with apply=NO_APPLY, then apply=APPLY
     - Wait 0.3s for device processing
  2. Restore color:
     - set_color(prestate.color, duration=0)
     - Wait 0.3s
  3. Restore power:
     - set_power(prestate.power, duration=0)
```

**Timing:** 0.6-1.0 seconds per device (includes delays)

**Special Cases:**

- Multizone devices get zones restored first
- 0.3s delays ensure device processing completes
- Errors are logged but don't stop other devices

## State Management

### State Storage

The conductor maintains a registry of running effects:

```python
_running: dict[str, RunningEffect]
```

**Key:** Device serial number (12-digit hex string)
**Value:** `RunningEffect` containing effect instance and captured `PreState`

### State Capture Details

#### Power State

Integer power level captured via `get_power()`:

```python
power_level = await light.get_power()  # Returns int (0 or 65535)
is_on = power_level > 0
```

#### Color State

HSBK color captured via `get_color()`:

```python
color, power, _ = await light.get_color()  # power is int (0 or 65535)
```

Returns:

- `color`: HSBK (hue, saturation, brightness, kelvin)
- `power`: Power level as integer (0 for off, 65535 for on)
- `label`: Device label

#### Multizone State

For `MultiZoneLight` devices, zone colors are captured:

```python
if isinstance(light, MultiZoneLight):
    # Get all zones using the convenience method
    # Automatically uses the best method based on capabilities
    zone_colors = await light.get_all_color_zones()
```

**Extended Multizone:**

- Single message retrieves all zones
- Returns `list[HSBK]` with all zone colors
- More efficient, used when available

**Standard Multizone:**

- Retrieves zones in batches of 8
- Multiple messages required for >8 zones
- Used as fallback for older devices

### State Restoration Details

#### Multizone Restoration

Zones are restored **before** color and power:

**Extended Multizone:**

```python
await light.set_extended_color_zones(
    zone_index=0,
    colors=zone_colors,
    duration=0.0,
    apply=MultiZoneExtendedApplicationRequest.APPLY
)
```

Single message restores all zones.

**Standard Multizone:**

```python
for i, color in enumerate(zone_colors):
    is_last = (i == len(zone_colors) - 1)
    apply = APPLY if is_last else NO_APPLY

    await light.set_color_zones(
        start=i, end=i,
        color=color,
        duration=0.0,
        apply=apply
    )
```

Multiple messages with `apply` logic:

- `NO_APPLY` (0): Update buffer, don't display
- `APPLY` (1): Update buffer and display (used on last zone)

This ensures atomic update visible only when all zones are set.

#### Timing Delays

Critical 0.3-second delays ensure device processing:

```python
# After multizone restoration
await asyncio.sleep(0.3)

# After color restoration
await asyncio.sleep(0.3)

# No delay after power (last operation)
```

Without these delays, subsequent operations may arrive before device finishes processing, causing state corruption.

### Prestate Inheritance

Optimization that skips state capture/restore for compatible consecutive effects:

```python
def inherit_prestate(self, other: LIFXEffect) -> bool:
    """Return True if can skip restoration."""
    return isinstance(other, EffectColorloop)  # Example
```

**When used:**

```python
current_running = self._running.get(serial)
if current_running and effect.inherit_prestate(current_running.effect):
    # Reuse existing prestate
    prestate = current_running.prestate
else:
    # Capture new prestate
    prestate = await self._capture_prestate(light)
```

**Benefits:**

- Eliminates flash/reset between compatible effects
- Reduces network traffic
- Faster effect transitions

**Used by:**

- `EffectColorloop.inherit_prestate()` → Returns `True` for other `EffectColorloop` instances
- `EffectPulse` doesn't use it (returns `False`)

## Concurrency Model

### Thread Safety

The conductor uses an `asyncio.Lock()` for thread-safe state management:

```python
async def start(self, effect, participants):
    async with self._lock:
        # Critical section: state capture and registration
        for light in participants:
            prestate = await self._capture_prestate(light)
            self._running[light.serial] = RunningEffect(effect, prestate)

    # Effect execution happens outside lock (concurrent)
    await effect.async_perform(participants)
```

**Why lock is needed:**

- Prevents race conditions when starting/stopping effects concurrently
- Protects `_running` dictionary modifications
- Ensures atomic state capture and registration

**Why effect execution is outside lock:**

- Allows multiple effects to run concurrently on different devices
- Effect logic doesn't modify conductor state
- Prevents blocking other operations during long-running effects

### Concurrent Device Operations

Effects use `asyncio.gather()` for concurrent device operations:

```python
# Apply waveform to all devices concurrently
tasks = [
    light.set_waveform(color, period, cycles, waveform)
    for light in self.participants
]
await asyncio.gather(*tasks)
```

**Benefits:**

- Multiple devices updated in parallel
- Network latency overlaps
- Total time ≈ single device time (not N × device time)

### Background Response Dispatcher

Each `DeviceConnection` has a background receiver task that routes responses:

```python
# In DeviceConnection
async def _response_receiver(self):
    while self._running:
        packet = await self._receive_packet()
        # Route by sequence number to waiting coroutine
        self._pending[seq_num].set_result(packet)
```

**Implications for effects:**

- Multiple concurrent requests on same device are supported
- Responses are correctly matched even with concurrent operations
- No additional coordination needed in effect code

### Effect Concurrency Patterns

#### Pattern 1: Sequential Effects on Same Devices

```python
# Effect 1 completes before Effect 2 starts
await conductor.start(effect1, lights)
await asyncio.sleep(duration1)
await conductor.start(effect2, lights)  # Captures new state
```

State is automatically restored between effects.

#### Pattern 2: Concurrent Effects on Different Devices

```python
# Different devices, completely independent
await conductor.start(effect1, group1)
await conductor.start(effect2, group2)
# Both run concurrently
```

No locking needed - different devices, different state.

#### Pattern 3: Replacing Running Effect

```python
# Start effect1
await conductor.start(effect1, lights)
await asyncio.sleep(5)

# Replace with effect2
await conductor.start(effect2, lights)  # Prestate may be inherited
```

If `effect2.inherit_prestate(effect1)` returns `True`, no restoration happens.

## Device Type Handling

### Device Capabilities Detection

The effects framework adapts to device capabilities automatically:

```python
# Check if multizone
if isinstance(light, MultiZoneLight):
    # Capture zone colors
    zone_colors = await light.get_color_zones(...)

# Check if extended multizone supported
if light.capabilities and light.capabilities.has_extended_multizone:
    # Use efficient extended messages
    await light.set_extended_color_zones(...)
```

### Device-Specific Behavior

#### Color Lights (`Light`)

- Full HSBK color support
- All effect parameters apply
- No special handling needed

#### Multizone Lights (`MultiZoneLight`)

- **State Capture:** Zone colors captured using extended or standard messages
- **State Restoration:** All zones restored with proper `apply` logic
- **Effect Behavior:** Entire device pulses/cycles together (zones not individually controlled)
- **Timing:** 0.3s delay after zone restoration

#### Matrix Lights (`MatrixLight`)

- **Current Implementation:** Treated like color lights (no matrix-specific logic yet)
- **Future Enhancement:** Could apply effects to individual tiles using device chain

#### HEV Lights (`HevLight`)

- Treated like standard color lights
- HEV cycle not affected by effects
- Effects don't interfere with HEV functionality

#### Infrared Lights (`InfraredLight`)

- Treated like standard color lights
- Infrared LED not affected by color effects
- Effects only control visible light

#### Monochrome/White Lights

- **Color parameters ignored:** Hue and saturation have no effect
- **Brightness works:** Effects can still toggle/fade brightness
- **Kelvin preserved:** Temperature setting maintained
- **Recommendation:** Limited usefulness (only brightness changes visible)

## Design Decisions

### Why Conductor Pattern?

**Decision:** Central conductor manages all effect lifecycle instead of effects managing themselves.

**Rationale:**

1. **Centralized State:** Single source of truth for what's running where
2. **Consistent State Management:** All effects get same capture/restore logic
3. **Concurrency Control:** Single lock protects all state modifications
4. **User Simplicity:** Users don't manage state manually

**Alternative Considered:** Effects self-manage state

**Rejected because:** Would require each effect to duplicate state logic, higher chance of bugs

### Why Abstract Base Class?

**Decision:** `LIFXEffect` is abstract with required `async_play()` override.

**Rationale:**

1. **Type Safety:** Enforces effect interface at type-check time
2. **Code Reuse:** Common setup logic in `async_perform()`
3. **Extensibility:** Users can create custom effects easily
4. **Consistency:** All effects follow same pattern

### Why Two-Phase Effect Execution?

**Decision:** `async_perform()` calls `async_play()` instead of single method.

**Rationale:**

1. **Separation of Concerns:** Setup logic separate from effect logic
2. **User Simplicity:** Users only override `async_play()`, setup is automatic
3. **Consistency:** All effects get same power-on behavior
4. **Flexibility:** Base class can add more setup steps without breaking subclasses

### Why No Rate Limiting?

**Decision:** Effects don't implement rate limiting.

**Rationale:**

1. **Simplicity:** Keeps core library simple and focused
2. **Flexibility:** Applications have different rate limit needs
3. **Transparency:** Users see actual device behavior
4. **Consistency:** Matches lifx-async philosophy (no hidden rate limiting)

**Recommendation:** Applications should implement rate limiting if sending many concurrent requests.

### Why 0.3-Second Delays?

**Decision:** Fixed 0.3-second delays between state restoration operations.

**Rationale:**

1. **Device Processing Time:** LIFX devices need time to process commands
2. **Empirical Testing:** 0.3s works reliably across all device types
3. **State Integrity:** Prevents race conditions and state corruption
4. **Trade-off:** Slightly slower restoration but guaranteed correctness

**Alternative Considered:** No delays, faster restoration

**Rejected because:** Causes state corruption and unpredictable behavior

### Why Prestate Inheritance?

**Decision:** Optional optimization via `inherit_prestate()` method.

**Rationale:**

1. **Performance:** Eliminates unnecessary state reset
2. **User Experience:** No visible flash between compatible effects
3. **Opt-in:** Only used when effect explicitly enables it
4. **Safe Default:** Returns `False` unless overridden

**Use Cases:**

- ColorLoop → ColorLoop: Seamless transition
- Pulse → Pulse: Could enable but currently disabled
- Different types: Should not inherit (different visual intent)

### Why No Tile-Specific Logic (Yet)?

**Decision:** Tiles treated like single-color lights for now.

**Rationale:**

1. **MVP Scope:** Phase 1 focuses on core framework
2. **Complexity:** Tile effects require 2D coordinate system
3. **Future Enhancement:** Architecture supports adding tile-specific effects later
4. **Current Usefulness:** Effects still work on tiles (just not tile-aware)

**Future Work:** Tile-specific effects would use `MatrixLight.set_matrix_colors()` and apply per-tile logic similar to theme support.

## Integration Points

### With Device Layer

Effects use standard device methods:

- `get_power()`, `set_power()`
- `get_color()`, `set_color()`
- `set_waveform()` (EffectPulse)
- `get_color_zones()`, `set_color_zones()` (MultiZoneLight)
- `get_extended_color_zones()`, `set_extended_color_zones()` (MultiZoneLight)

No special device modifications needed.

### With Network Layer

Effects rely on existing lazy connection and concurrent request support:

- Lazy connections open on first request and are reused
- Requests are serialized via lock to prevent response mixing
- No effect-specific network code needed

### With Protocol Layer

Effects use existing protocol structures:

- `HSBK` for color representation
- `LightWaveform` enum for waveform types
- `MultiZoneApplicationRequest` for zone apply logic
- Auto-generated packet classes

## Performance Characteristics

### Memory Usage

- **Conductor:** ~10KB base + running effects
- **Per Effect:** ~1KB per device + effect-specific state
- **PreState:** ~200 bytes per device (~100 bytes + zone colors)

### CPU Usage

- **Minimal:** Async I/O bound, not CPU bound
- **Concurrency:** Multiple devices don't increase CPU significantly
- **Background Tasks:** Requests serialized per connection, concurrent across devices

### Network Traffic

#### State Capture

- Power: 1 request per device
- Color: 1 request per device
- Multizone: 1 request (extended) or N/8 requests (standard)
- **Total:** 3-4 packets per device

#### Effect Execution

- Pulse: 1 waveform packet per device
- ColorLoop: 1 color packet per device per iteration

#### State Restoration

- Multizone: 1 request (extended) or N requests (standard)
- Color: 1 request per device
- Power: 1 request per device
- **Total:** 2-3 packets per device (or N+2 for standard multizone)

### Scalability

- **Tested:** 10+ devices
- **Expected:** 50+ devices in production
- **Limitation:** Network capacity and device response time
- **Recommendation:** For 50+ devices, consider grouping effects or staggering start times

## See Also

- [Getting Started](../getting-started/effects.md) - Basic usage
- [Effects Reference](../api/effects.md) - Detailed API documentation
- [Custom Effects](../user-guide/effects-custom.md) - Creating your own effects
- [Troubleshooting](../user-guide/effects-troubleshooting.md) - Common issues
