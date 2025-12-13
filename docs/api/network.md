# Network Layer

The network layer provides low-level operations for communicating with LIFX devices over UDP.

## Discovery

Functions for discovering LIFX devices on the local network.

::: lifx.network.discovery.discover_devices
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

::: lifx.network.discovery.DiscoveredDevice
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

### DiscoveryResponse

Response dataclass from custom discovery broadcasts (using packets other than GetService).

::: lifx.network.discovery.DiscoveryResponse
    options:
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## UDP Transport

Low-level UDP transport for sending and receiving LIFX protocol messages.

::: lifx.network.transport.UdpTransport
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      filters:
        - "!^_"

## Examples

### Device Discovery

```python
from lifx.network.discovery import discover_devices


async def main():
    # Discover all devices on the network
    devices = await discover_devices(timeout=3.0)

    for device in devices:
        print(f"Found: {device.label} at {device.ip}")
        print(f"  Serial: {device.serial}")
```


## Concurrency

### Request Serialization on Single Connection

Each `DeviceConnection` serializes requests using a lock to prevent response mixing:

```python
import asyncio
from lifx.network.connection import DeviceConnection
from lifx.protocol.packets import Light, Device


async def main():
    conn = DeviceConnection(serial="d073d5123456", ip="192.168.1.100")

    # Sequential requests (serialized by internal lock)
    state = await conn.request(Light.GetColor())
    power = await conn.request(Light.GetPower())
    label = await conn.request(Device.GetLabel())

    # Connection automatically closes when done
    await conn.close()
```

### Concurrent Requests on Different Devices

```python
import asyncio
from lifx.network.connection import DeviceConnection


async def main():
    conn1 = DeviceConnection(serial="d073d5000001", ip="192.168.1.100")
    conn2 = DeviceConnection(serial="d073d5000002", ip="192.168.1.101")

    # Fully parallel - different UDP sockets
    result1, result2 = await asyncio.gather(
        conn1.request(Light.GetColor()),
        conn2.request(Light.GetColor())
    )

    # Clean up connections
    await conn1.close()
    await conn2.close()
```

## Connection Management

::: lifx.network.connection.DeviceConnection
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Performance Considerations

### Connection Lifecycle

- Connections open lazily on first request
- Each device owns its own connection (no shared pool)
- Connections close explicitly via `close()` or context manager exit
- Low memory overhead (one UDP socket per device)

### Response Handling

- Responses matched by sequence number
- Async generator-based streaming for efficient multi-response protocols
- Immediate exit for single-response requests (no wasted timeout)
- Retry logic with exponential backoff and jitter

### Rate Limiting

The library **intentionally does not implement rate limiting** to keep the core library simple.
Applications should implement their own rate limiting if needed. According to the LIFX protocol
specification, devices can handle approximately 20 messages per second.
