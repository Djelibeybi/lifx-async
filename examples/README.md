# Examples

Each example can be run with `uv run python examples/<script>`. All scripts require LIFX devices
on your local network unless otherwise noted.

## Discovery

### discovery_broadcast

Discovers all LIFX devices on the network via UDP broadcast and prints serial, IP, label, power
state, and color for each device found.

```bash
uv run python examples/discovery_broadcast.py
```

No parameters.

### discovery_logging

Discovers lights and logs their state using Python's `logging` module. Useful for understanding
the library's internal request/response flow.

```bash
uv run python examples/discovery_logging.py
```

No parameters.

### discovery_find_device

Finds a single device by label, serial number, or IP address. More efficient than full discovery
when you know which device you want.

```bash
uv run python examples/discovery_find_device.py --label "Living Room"
uv run python examples/discovery_find_device.py --serial d073d5123456
uv run python examples/discovery_find_device.py --ip 192.168.1.100
```

| Parameter | Short | Required | Description |
|-----------|-------|----------|-------------|
| `--label` | `-l` | one of three | Find by label (case-insensitive substring match) |
| `--exact` | `-e` | no | Use exact match for label search |
| `--serial` | `-s` | one of three | Find by serial number (12 hex digits, with or without colons) |
| `--ip` | `-i` | one of three | Find by IP address |

`--label`, `--serial`, and `--ip` are mutually exclusive; exactly one is required.

### discovery_mdns

Discovers devices using mDNS/DNS-SD instead of UDP broadcast. Demonstrates both the high-level
API (yields device instances) and low-level API (yields raw service records).

```bash
uv run python examples/discovery_mdns.py
```

No parameters.

## Control

### control_basic

Connects to a single light and demonstrates basic operations: power on/off, setting color,
adjusting hue, saturation, brightness, and kelvin individually. Restores original state when done.

```bash
uv run python examples/control_basic.py --ip 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--ip` | yes | IP address of the light |

### control_waveforms

Demonstrates the five built-in waveform types: PULSE, SINE (breathe), SAW, TRIANGLE, and
HALF_SINE. Each waveform transitions between two colors for two cycles.

```bash
uv run python examples/control_waveforms.py --ip 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--ip` | yes | IP address of the light |

### control_device_groups

Discovers all devices and demonstrates DeviceGroup features: type filtering (lights, HEV,
infrared, multizone, matrix), batch operations, organization by location/group, and iteration.

```bash
uv run python examples/control_device_groups.py
uv run python examples/control_device_groups.py --demo
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--demo` | no | Run batch color/brightness operations (changes light states) |

Without `--demo`, the script is read-only and only displays device information.

## Effects

### effects_pulse

Demonstrates pulse effect variations: blink, strobe, breathe, and ping. Each mode uses the LIFX
protocol's built-in waveform engine for smooth transitions.

```bash
uv run python examples/effects_pulse.py
uv run python examples/effects_pulse.py 192.168.1.100 d073d5123456
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| positional args | no | IP addresses and/or serial numbers of target devices |

Without arguments, discovers all lights on the network.

### effects_colorloop

Continuously rotates through the hue spectrum. All pixels on a device display the same color.
Demonstrates basic, fast, and synchronized colorloop modes.

```bash
uv run python examples/effects_colorloop.py
uv run python examples/effects_colorloop.py 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| positional args | no | IP addresses and/or serial numbers of target devices |

### effects_custom

Shows how to create custom effects by subclassing `LIFXEffect`. Includes two examples:
`FlashEffect` (synchronized flashing) and `WaveEffect` (sequential color wave across devices).

```bash
uv run python examples/effects_custom.py
```

No parameters. Discovers all lights on the network.

### effects_background

Demonstrates that `conductor.start()` returns immediately, allowing effects to run in the
background while you do other work. Starts a colorloop, does work for 10 seconds, then stops it.

```bash
uv run python examples/effects_background.py
```

No parameters. Discovers all lights on the network.

### effects_rainbow

Spreads a full 360-degree rainbow across all pixels and scrolls it over time. On multizone strips
and matrix lights this produces a moving per-pixel rainbow. Demonstrates speed, brightness, and
device spread options.

```bash
uv run python examples/effects_rainbow.py
uv run python examples/effects_rainbow.py 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| positional args | no | IP addresses and/or serial numbers of target devices |

### effects_flame

Simulates fire and candle flicker using layered sine waves. On single bulbs it flickers like a
candle; on strips it looks like fire along a wall; on matrix lights a 2D fire with vertical
gradient appears. Demonstrates default, intense, and ember glow modes.

```bash
uv run python examples/effects_flame.py
uv run python examples/effects_flame.py 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| positional args | no | IP addresses and/or serial numbers of target devices |

### effects_aurora

Simulates the northern lights with flowing colored bands. Best on multizone strips and matrix
lights. Demonstrates default palette, warm palette, and fast mode with device spread.

```bash
uv run python examples/effects_aurora.py
uv run python examples/effects_aurora.py 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| positional args | no | IP addresses and/or serial numbers of target devices |

### effects_progress

Displays an animated progress bar on multizone lights (strips and beams). The filled region has a
traveling bright spot, and position can be updated from external code. Demonstrates download
progress and temperature gauge with gradient foreground.

Multizone devices only.

```bash
uv run python examples/effects_progress.py
uv run python examples/effects_progress.py 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| positional args | no | IP addresses and/or serial numbers of target devices |

### effects_sunrise_sunset

Sunrise transitions from night to daylight; sunset transitions from daylight to night and
optionally powers off the light. Both use a radial model that expands or contracts through color
phases: deep navy, purple/magenta, orange/gold, warm white.

Matrix devices only.

```bash
uv run python examples/effects_sunrise_sunset.py
uv run python examples/effects_sunrise_sunset.py --show-hsbk 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--show-hsbk` | no | Print brightness and kelvin values every 2 seconds while animating |
| positional args | no | IP addresses and/or serial numbers of target devices |

## Matrix Devices

### matrix_basic

Connects to a MatrixLight (Tile, Candle, Path) and demonstrates getting device chain info,
reading tile colors, and setting a blue gradient pattern.

```bash
uv run python examples/matrix_basic.py --ip 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--ip` | yes | IP address of the MatrixLight |

### matrix_effects

Demonstrates the built-in firmware tile effects: MORPH, FLAME, SKY (sunrise and clouds), and
custom palette MORPH. These effects run on the device firmware itself.

```bash
uv run python examples/matrix_effects.py --ip 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--ip` | yes | IP address of the MatrixLight |

### matrix_large_tiles

Demonstrates handling matrix devices with more than 64 zones per tile (e.g., 16x8 = 128 zones).
Shows rainbow, vertical stripe, and checkerboard patterns. The library automatically uses the
frame buffer strategy for large tiles.

```bash
uv run python examples/matrix_large_tiles.py --ip 192.168.1.100
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--ip` | yes | IP address of the MatrixLight |

## Animation

### animation_basic

High-frequency frame delivery using direct UDP for maximum throughput. Auto-detects whether the
device is matrix or multizone and runs a rainbow wave animation. Also includes a profiling mode
with synthetic micro-benchmarks.

```bash
# Run animation on a device
uv run python examples/animation_basic.py --serial d073d5123456

# Faster connection with both serial and IP
uv run python examples/animation_basic.py --serial d073d5123456 --ip 192.168.1.100

# Synthetic benchmarks only (no device needed)
uv run python examples/animation_basic.py --profile
```

| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--serial` | `-s` | yes* | | Device serial number (12 hex digits) |
| `--ip` | `-i` | no | | IP address for faster connection |
| `--duration` | `-d` | no | `10` | Animation duration in seconds |
| `--fps` | `-f` | no | `30` | Target frames per second |
| `--profile` | | no | | Run profiling mode (synthetic benchmarks, plus device benchmarks if serial/ip given) |
| `--iterations` | | no | `2000` | Number of profiling iterations |
| `--warmup` | | no | `200` | Warmup iterations excluded from stats |

*`--serial` is required unless using `--profile` alone.

### animation_numpy

Same as `animation_basic` but uses NumPy for vectorized frame generation. Includes four effects:
spiral, wave, plasma, and fire. Requires `numpy` to be installed.

```bash
# Auto-select effect based on device type
uv run python examples/animation_numpy.py --serial d073d5123456

# Run a specific effect
uv run python examples/animation_numpy.py --serial d073d5123456 --effect plasma

# Synthetic benchmarks only (no device needed)
uv run python examples/animation_numpy.py --profile
```

| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--serial` | `-s` | yes* | | Device serial number (12 hex digits) |
| `--ip` | `-i` | no | | IP address for faster connection |
| `--duration` | `-d` | no | `10` | Animation duration in seconds |
| `--fps` | `-f` | no | `30` | Target frames per second |
| `--effect` | `-e` | no | `auto` | Effect to run: `auto`, `spiral`, `wave`, `plasma`, `fire` |
| `--profile` | | no | | Run profiling mode |
| `--iterations` | | no | `2000` | Number of profiling iterations |
| `--warmup` | | no | `200` | Warmup iterations excluded from stats |

*`--serial` is required unless using `--profile` alone.

## Device Targeting

Many effect examples share the same device targeting pattern:

- **No arguments**: discovers all lights on the network
- **IP addresses**: `192.168.1.100 192.168.1.101`
- **Serial numbers**: `d073d5123456 d073d5abcdef`
- **Mixed**: `192.168.1.100 d073d5123456`

The scripts auto-detect whether each argument is an IP address (contains `.`) or a serial number.
