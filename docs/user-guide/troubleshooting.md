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

   devices = await discover_devices(timeout=5.0)
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
    devices = await discover_devices(
        timeout=10.0,
        broadcast_address="255.255.255.255"
    )

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

```python
async def thorough_discovery():
    # Multiple discovery passes with different timeouts
    all_devices = set()

    for timeout in [3.0, 5.0, 10.0]:
        devices = await discover_devices(timeout=timeout)
        for device in devices:
            all_devices.add((device.serial, device.ip))

    print(f"Total devices found: {len(all_devices)}")
    return all_devices
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

# Increase discovery timeout
async with discover(timeout=10.0) as group:  # Default is 3.0
    print(f"Found {len(group.devices)} devices")
```

## Performance Issues

### Slow Operations

**Symptom:** Operations take longer than expected

**Diagnosis:**

```python
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
           await light.set_color(HSBK(hue=(360/10)*i), saturation=1.0, brightness=1.0, kelvin=3500)
   ```

   Efficient (reuses connection):
   ```python
   async with await Light.from_ip(ip) as light:
       for i in range(10):
           await light.set_color(HSBK(hue=(360/10)*i), saturation=1.0, brightness=1.0, kelvin=3500)
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

# List all known products
registry = get_registry()
for product_id, product in registry.items():
    print(f"{product_id}: {product.name}")

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

- [Advanced Usage](advanced-usage.md) - Optimization patterns
- [API Reference](../api/index.md) - Complete API documentation
- [FAQ](../faq.md) - Frequently asked questions
