# UDP `receive_many()` Removal (7.0.1)

Version 7.0.1 removes `UdpTransport.receive_many()`. The method was deprecated
in 5.5.0 with a scheduled 6.0 removal, but inadvertently remained available
through 7.0.0.

## Migration

For device discovery, use the public high-level API. It yields devices as they
are found and owns the multi-response collection lifecycle:

```python
from lifx import discover


async def discover_devices():
    async for device in discover(timeout=5.0):
        print(device.serial, device.ip)
```

Code that intentionally uses the low-level UDP transport can call `receive()`
in a loop and decide when collection is complete:

```python
from lifx.exceptions import LifxTimeoutError


async def receive_until_quiet(transport):
    packets = []
    while True:
        try:
            packets.append(await transport.receive(timeout=0.25))
        except LifxTimeoutError:
            return packets
```

Unlike `receive_many()`, `receive()` raises `LifxProtocolError` for an invalid
packet size. Low-level callers should handle that exception according to their
protocol requirements.
