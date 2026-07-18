# Troubleshooting Guide

Common issues and solutions when working with lifx.

## Table of Contents

- [Discovery Issues](#discovery-issues)
- [Connection Problems](#connection-problems)
- [Timeout Errors](#timeout-errors)
- [Performance Issues](#performance-issues)
- [Debugging Tips](#debugging-tips)

## Discovery Issues

### No Devices Found

**Symptom:** `discover()` returns an empty group

**Common Causes:**

1. **Devices not on same network**
   ```python
   # Check network connectivity
   import asyncio
   from lifx.network.discovery import discover_devices

   devices = []
   async for device in discover_devices(timeout=5.0):
       devices.append(device)
   print(f"Found {len(devices)} devices")
   ```

2. **Firewall blocking UDP port 56700**
   ```bash
   # Linux: Check if port is open
   sudo netstat -an | grep 56700

   # Allow UDP on port 56700
   sudo ufw allow 56700/udp
   ```

3. **Broadcast address incorrect**

   Try different broadcast addresses:

   ```python
   from lifx import discover, DeviceGroup

   # Default (255.255.255.255)
   devices = []
   async for device in discover():
       devices.append(device)
   group = DeviceGroup(devices)

   # Network-specific (e.g., 192.168.1.255)
   devices = []
   async for device in discover(broadcast_address="192.168.1.255"):
       devices.append(device)
   group = DeviceGroup(devices)
   ```

**Solution:**

```python
import asyncio
from lifx.network.discovery import discover_devices

async def diagnose_discovery():
    print("Attempting discovery...")

    # Try with extended timeout
    devices = []
    async for device in discover_devices(
        timeout=10.0,
        broadcast_address="255.255.255.255"
    ):
        devices.append(device)

    if not devices:
        print("No devices found. Check:")
        print("1. Devices are powered on")
        print("2. Devices are on the same network")
        print("3. Firewall allows UDP port 56700")
        print("4. Try a network-specific broadcast address")
    else:
        print(f"Found {len(devices)} devices:")
        for device in devices:
            print(f"  - {device.serial} at {device.ip}")

asyncio.run(diagnose_discovery())
```

### Partial Device Discovery

**Symptom:** Only some devices discovered

**Causes:**

- Devices on different subnets
- Network congestion
- Devices slow to respond

**Solution:**

A single `discover_devices()` call already re-broadcasts `GetService` on an
escalating schedule within the discovery window, so devices that miss the
first broadcast get several more chances to respond. There is no need to call
discovery multiple times.

If some devices are still missed on a slow or congested network, increase the
`timeout` to widen the discovery window:

```python
devices = []
async for device in discover_devices(timeout=30.0):
    devices.append(device)
```

## Connection Problems

### Connection Refused

**Symptom:** `LifxConnectionError: Connection refused`

**Causes:**

- Incorrect IP address
- Device powered off
- Network unreachable

**Solution:**

```python
from lifx import Light, LifxConnectionError
import asyncio

async def test_connection(ip: str):
    try:
        async with await Light.from_ip(ip) as light:
            label = await light.get_label()
            print(f"Connected to: {label}")
            return True

    except LifxConnectionError as e:
        print(f"Connection failed: {e}")
        print("Check:")
        print("1. Device IP is correct")
        print("2. Device is powered on")
        print("3. Device is reachable (try ping)")
        return False

# Test connectivity
asyncio.run(test_connection("192.168.1.100"))
```

### Connection Drops

**Symptom:** Intermittent `LifxConnectionError` or `LifxNetworkError`

**Causes:**

- WiFi signal weak
- Network congestion
- Device overloaded

**Solution:**

The library itself retransmits within each request's timeout, so transient
packet loss is handled for you. An application-level wrapper like the one
below is for retrying whole operations that failed — not for per-packet
reliability.

```python
import asyncio
from lifx import Light, LifxError

async def resilient_operation(ip: str, max_retries: int = 3):
    """Retry operations with exponential backoff"""
    async with await Light.from_ip(ip) as light:
        for attempt in range(max_retries):
            try:
                await light.set_power(True)
                print("Success!")
                return
            except LifxError as e:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                print(f"Attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    print(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)

    print("All retries exhausted")
```

## Timeout Errors

### Request Timeouts

**Symptom:** `LifxTimeoutError: Request timed out after X seconds`

**Causes:**

- Device slow to respond
- Network latency high
- Device busy processing other requests

**Solution:**

```python
from lifx import Light

# Increase timeout for slow devices
async with await Light.from_ip(ip, timeout=5.0) as light:
    # get_color() returns (color, power, label)
    color, power, label = await light.get_color()
```

### Discovery Timeout Too Short

**Symptom:** Some devices not found

**Solution:**

```python
from lifx import discover

# Increase the discovery timeout (the default is 15.0 seconds)
devices = []
async for device in discover(timeout=30.0):
    devices.append(device)

print(f"Found {len(devices)} devices")
```

## Performance Issues

### Slow Operations

**Symptom:** Operations take longer than expected

**Diagnosis:**

```python
import asyncio
import time
from lifx import Light

async def measure_latency():
    async with await Light.from_ip("192.168.1.100") as light:
        # Measure single request
        start = time.time()
        await light.get_label()
        elapsed = time.time() - start
        print(f"Single request: {elapsed*1000:.2f}ms")

        # Measure sequential requests
        start = time.time()
        for _ in range(10):
            await light.get_label()
        elapsed = time.time() - start
        print(f"10 sequential: {elapsed*1000:.2f}ms ({elapsed*100:.2f}ms avg)")

        # Measure concurrent requests
        start = time.time()
        await asyncio.gather(*[light.get_label() for _ in range(10)])
        elapsed = time.time() - start
        print(f"10 concurrent: {elapsed*1000:.2f}ms")
```

**Common Causes:**

1. **Sequential instead of concurrent operations**

   Slow approach (sequential):
   ```python
   for device in devices:
       await device.set_color(Colors.BLUE)
   ```

   Fast approach (concurrent):
   ```python
   await asyncio.gather(
       *[device.set_color(Colors.BLUE) for device in devices]
   )
   ```

2. **Not reusing connections**

   Inefficient (creates new connection each time):
   ```python
   for i in range(10):
       async with await Light.from_ip(ip) as light:
           await light.set_color(HSBK(hue=(360 / 10) * i, saturation=1.0, brightness=1.0, kelvin=3500))
   ```

   Efficient (reuses connection):
   ```python
   async with await Light.from_ip(ip) as light:
       for i in range(10):
           await light.set_color(HSBK(hue=(360 / 10) * i, saturation=1.0, brightness=1.0, kelvin=3500))
   ```

3. **Need fresh data?**

   Use `get_*()` methods to always fetch from the device:

   ```python
   # Always fetch fresh data
   # get_color() returns all three values in one call
   color, power, label = await light.get_color()

   # Or fetch other device info
   version = await light.get_version()
   ```

### Gen4 Power-Save Wake Tail

**Symptom:** The first command after a device has been idle for roughly a
minute or more is slower than usual — up to ~250 ms instead of the single-digit
milliseconds a busy device answers in. Subsequent commands respond at full
speed.

**Causes:**

- Gen4 devices use WiFi power-save while idle, so the radio takes a moment to
  wake for the first packet
- Affects gen4 devices only — gen2 and gen3 devices show no wake tail

This is a latency effect, not a reliability problem: on healthy networks, an
idle device loses zero packets. Every command still succeeds; the first one
after idle just takes a little longer.

**Identifying gen4 devices:**

Gen4 devices report a host firmware major version of 4 or later:

```python
firmware = await device.get_host_firmware()
if firmware.version_major >= 4:
    print("Gen4 device: expect a sub-250 ms wake tail after idle")
```

Inside `async with`, the cached `device.host_firmware` property is already
populated, so you can check `device.host_firmware.version_major` directly. Do
not try to identify gen4 devices by product ID — the products registry has no
generation field.

**Solution:**

Most applications can ignore the wake tail entirely. If your application is
latency-sensitive and cannot tolerate a slower first command, an optional
periodic poll keeps the device's radio awake:

```python
import asyncio
from lifx import Light

async def keep_awake(light: Light) -> None:
    """Optional: poll periodically so a gen4 device's radio stays awake."""
    while True:
        # Any request works; get_color() returns colour, power and label
        # in a single request/response pair.
        await light.get_color()
        await asyncio.sleep(15)  # 10-15 s keeps the wake tail away
```

Run it alongside your application with `asyncio.create_task()` or
`asyncio.TaskGroup` — no extra coordination is needed, because the library
serialises requests per connection. The poll is read-only, so it is safe to
run continuously, and one request every 15 seconds stays far below the
~20 msg/sec a device can handle.

!!! note "lifx-async deliberately ships no keepalive daemon"
    Measured on real hardware, idle devices lose zero packets on healthy
    networks — the wake tail is a small, bounded latency cost, not a
    reliability problem. Whether to spend a packet every 10–15 seconds to
    avoid it is the application's choice, so the library does not make it
    for you.

Streaming frames to a device? See the [Animation Guide](animation.md) for how
sustained streaming interacts with gen4 power-save.

### Docker / Container Networking

**Symptom:** Discovery doesn't work in Docker container

**Cause:** Container network isolation

**Solution:**

```yaml
# docker-compose.yml
services:
  app:
    network_mode: "host"  # Use host network for UDP broadcast
```

Or use manual device specification:

```python
# Don't rely on discovery
from lifx import Light

async with await Light.from_ip("192.168.1.100") as light:
    await light.set_color(Colors.BLUE)
```

## Debugging Tips

### Enable Debug Logging

```python
import logging

# Enable DEBUG logging for lifx
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Or for specific modules
logging.getLogger('lifx.network').setLevel(logging.DEBUG)
logging.getLogger('lifx.devices').setLevel(logging.DEBUG)
```

### Check Product Registry

```python
from lifx.products import get_product, get_registry

# Check how many products the registry knows
registry = get_registry()
print(f"Registry contains {len(registry)} products")

# Check specific product
product = get_product(27)  # LIFX A19
if product:
    print(f"Name: {product.name}")
    print(f"Capabilities: {product.capabilities}")
```

### Verify Device Reachability

```bash
# Ping device
ping 192.168.1.100

# Check UDP port (requires nmap)
sudo nmap -sU -p 56700 192.168.1.100

# Test with netcat
echo -n "test" | nc -u 192.168.1.100 56700
```

## Getting Help

If you're still experiencing issues:

1. **Check GitHub Issues**: [github.com/Djelibeybi/lifx-async/issues](https://github.com/Djelibeybi/lifx-async/issues)
2. **Enable debug logging**: Capture logs with `logging.DEBUG`
3. **Provide details**:
   - Python version
   - lifx version
   - Device model and firmware version
   - Network configuration
   - Minimal reproduction code
   - Full error traceback

## Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| `LifxTimeoutError` | Device didn't respond | Increase timeout, check network |
| `LifxConnectionError` | Can't connect to device | Check IP, firewall, device power |
| `LifxDeviceNotFoundError` | Device not discovered | Check network, increase timeout |
| `LifxProtocolError` | Invalid response | Update firmware, check device type |
| `LifxUnsupportedCommandError` | Device doesn't support command | Check device capabilities |
| `AttributeError: 'Light' has no attribute 'set_color_zones'` | Wrong device class | Use `MultiZoneLight` |

## Next Steps

- [Effects Troubleshooting](effects-troubleshooting.md) — Issues specific to the effects framework
- [Advanced Usage](advanced-usage.md) — Optimisation patterns
- [API Reference](../api/index.md) — Complete API documentation
- [FAQ](../faq.md) — Frequently asked questions
