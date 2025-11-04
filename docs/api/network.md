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

## Message Building

Utilities for building and parsing LIFX protocol messages.

::: lifx.network.message.MessageBuilder
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

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
        print(f"  Service: {device.service}")
```


## Concurrency

### Concurrent Requests on Single Connection

Each `DeviceConnection` supports true concurrent requests using a background response dispatcher:

```python
import asyncio
from lifx.network.connection import DeviceConnection
from lifx.protocol.packets import LightGet, LightGetPower, DeviceGetLabel


async def main():
    async with DeviceConnection(serial, ip) as conn:
        # Multiple requests execute concurrently
        state, power, label = await asyncio.gather(
            conn.request_response(LightGet(), LightState),
            conn.request_response(LightGetPower(), LightStatePower),
            conn.request_response(DeviceGetLabel(), DeviceStateLabel),
        )
```

### Concurrent Requests on Different Devices

```python
import asyncio
from lifx.network.connection import DeviceConnection


async def main():
    async with DeviceConnection(serial1, ip1) as conn1, DeviceConnection(
        serial2, ip2
    ) as conn2:
        # Fully parallel - different UDP sockets
        result1, result2 = await asyncio.gather(
            conn1.request_response(...), conn2.request_response(...)
        )
```

## Connection Management

::: lifx.network.connection.DeviceConnection
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Performance Considerations

### Connection Pooling

- Connections are cached with LRU eviction
- Default pool size: 100 connections
- Idle connections are automatically closed after timeout
- Pool metrics available via `get_pool_metrics()`

### Response Handling

- Background receiver task runs continuously
- Responses matched by sequence number
- Minimal overhead per concurrent request (~100 bytes)
- Clean shutdown on connection close

### Rate Limiting

The library **intentionally does not implement rate limiting** to keep the core library simple.
Applications should implement their own rate limiting if needed. According to the LIFX protocol
specification, devices can handle approximately 20 messages per second.
