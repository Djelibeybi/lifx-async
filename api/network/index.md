# Network Layer

The network layer provides low-level operations for communicating with LIFX devices over UDP.

## Discovery

Functions for discovering LIFX devices on the local network.

### discover_devices

```python
discover_devices(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[DiscoveredDevice, None]
```

Discover LIFX devices on the local network.

Sends a broadcast DeviceGetService packet and yields devices as they respond. Implements DoS protection via timeout, source validation, and serial validation.

| PARAMETER                 | DESCRIPTION                                                                                          |
| ------------------------- | ---------------------------------------------------------------------------------------------------- |
| `timeout`                 | Discovery timeout in seconds **TYPE:** `float` **DEFAULT:** `DISCOVERY_TIMEOUT`                      |
| `broadcast_address`       | Broadcast address to use **TYPE:** `str` **DEFAULT:** `'255.255.255.255'`                            |
| `port`                    | UDP port to use (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                 |
| `max_response_time`       | Max time to wait for responses **TYPE:** `float` **DEFAULT:** `MAX_RESPONSE_TIME`                    |
| `idle_timeout_multiplier` | Idle timeout multiplier **TYPE:** `float` **DEFAULT:** `IDLE_TIMEOUT_MULTIPLIER`                     |
| `device_timeout`          | request timeout set on discovered devices **TYPE:** `float` **DEFAULT:** `DEFAULT_REQUEST_TIMEOUT`   |
| `max_retries`             | max retries per request set on discovered devices **TYPE:** `int` **DEFAULT:** `DEFAULT_MAX_RETRIES` |

| YIELDS                                   | DESCRIPTION                                       |
| ---------------------------------------- | ------------------------------------------------- |
| `AsyncGenerator[DiscoveredDevice, None]` | DiscoveredDevice instances as they are discovered |
| `AsyncGenerator[DiscoveredDevice, None]` | (deduplicated by serial number)                   |

Example

```python
# Process devices as they're discovered
async for device in discover_devices(timeout=5.0):
    print(f"Found device: {device.serial} at {device.ip}:{device.port}")

# Or collect all devices first
devices = []
async for device in discover_devices():
    devices.append(device)
```

Source code in `src/lifx/network/discovery.py`

````python
async def discover_devices(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[DiscoveredDevice, None]:
    """Discover LIFX devices on the local network.

    Sends a broadcast DeviceGetService packet and yields devices as they respond.
    Implements DoS protection via timeout, source validation, and serial validation.

    Args:
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: UDP port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered devices
        max_retries: max retries per request set on discovered devices

    Yields:
        DiscoveredDevice instances as they are discovered
        (deduplicated by serial number)

    Example:
        ```python
        # Process devices as they're discovered
        async for device in discover_devices(timeout=5.0):
            print(f"Found device: {device.serial} at {device.ip}:{device.port}")

        # Or collect all devices first
        devices = []
        async for device in discover_devices():
            devices.append(device)
        ```
    """
    seen_serials: set[str] = set()
    packet_count = 0
    start_time = time.time()

    # Create transport with broadcast enabled
    async with UdpTransport(port=0, broadcast=True) as transport:
        # Allocate unique source for this discovery session
        discovery_source = allocate_source()

        # Create discovery message
        discovery_packet = DevicePackets.GetService()
        message = create_message(
            packet=discovery_packet,
            source=discovery_source,
            sequence=_DEFAULT_SEQUENCE_START,
            target=b"\x00" * 8,  # Broadcast
            res_required=True,
            ack_required=False,
        )

        # Send broadcast
        request_time = time.time()
        _LOGGER.debug(
            {
                "class": "discover_devices",
                "method": "discover",
                "action": "broadcast_sent",
                "broadcast_address": broadcast_address,
                "port": port,
                "max_timeout": timeout,
                "request_time": request_time,
            }
        )
        await transport.send(message, (broadcast_address, port))

        # Calculate idle timeout
        idle_timeout = max_response_time * idle_timeout_multiplier
        last_response_time = request_time

        # Collect responses with dynamic timeout
        while True:
            # Calculate elapsed time since last response
            elapsed_since_last = time.time() - last_response_time

            # Stop if we've been idle too long
            if elapsed_since_last >= idle_timeout:
                _LOGGER.debug(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "idle_timeout",
                        "idle_time": elapsed_since_last,
                        "idle_timeout": idle_timeout,
                    }
                )
                break

            # Stop if we've exceeded the overall timeout
            if time.time() - request_time >= timeout:
                _LOGGER.debug(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "overall_timeout",
                        "elapsed": time.time() - request_time,
                        "timeout": timeout,
                    }
                )
                break

            # Calculate remaining timeout (use the shorter of idle or overall timeout)
            remaining_idle = idle_timeout - elapsed_since_last
            remaining_overall = timeout - (time.time() - request_time)
            remaining = min(remaining_idle, remaining_overall)

            # Try to receive a packet
            try:
                data, addr = await transport.receive(timeout=remaining)
                response_timestamp = time.time()

            except LifxTimeoutError:
                # Timeout means no more responses within the idle period
                _LOGGER.debug(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "no_responses",
                    }
                )
                break

            # Increment packet counter for logging
            packet_count += 1

            try:
                # Parse message
                header, payload = parse_message(data)

                # Validate source matches expected source
                if header.source != discovery_source:
                    _LOGGER.debug(
                        {
                            "class": "discover_devices",
                            "method": "discover",
                            "action": "source_mismatch",
                            "expected_source": discovery_source,
                            "received_source": header.source,
                            "source_ip": addr[0],
                        }
                    )
                    continue

                # Check if this is a DeviceStateService response
                if header.pkt_type != DevicePackets.StateService.PKT_TYPE:
                    _LOGGER.debug(
                        {
                            "class": "discover_devices",
                            "method": "discover",
                            "action": "unexpected_packet_type",
                            "pkt_type": header.pkt_type,
                            "expected_type": DevicePackets.StateService.PKT_TYPE,
                            "source_ip": addr[0],
                        }
                    )
                    continue

                # Validate serial is not multicast/broadcast
                if header.target[0] & 0x01 or header.target == b"\xff" * 8:
                    _LOGGER.warning(
                        {
                            "warning": "Invalid serial number in discovery response",
                            "serial": header.target.hex(),
                            "source_ip": addr[0],
                        }
                    )
                    continue

                # Parse service info
                _service, device_port = _parse_device_state_service(payload)

                # Calculate accurate response time from this specific response
                response_time = response_timestamp - request_time

                # Convert 8-byte protocol serial to string
                device_serial = Serial.from_protocol(header.target).to_string()

                # Deduplicate by serial number and yield new devices immediately
                if device_serial not in seen_serials:
                    seen_serials.add(device_serial)

                    # Create device info
                    device = DiscoveredDevice(
                        serial=device_serial,
                        ip=addr[0],
                        port=device_port,
                        response_time=response_time,
                        timeout=device_timeout,
                        max_retries=max_retries,
                    )

                    _LOGGER.debug(
                        {
                            "class": "discover_devices",
                            "method": "discover",
                            "action": "device_found",
                            "serial": device.serial,
                            "ip": device.ip,
                            "port": device.port,
                            "response_time": response_time,
                        }
                    )

                    yield device

                # Update last response time for idle timeout calculation
                last_response_time = response_timestamp

            except LifxProtocolError as e:
                # Log malformed responses
                _LOGGER.warning(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "malformed_response",
                        "reason": str(e),
                        "source_ip": addr[0],
                        "packet_size": len(data),
                    },
                    exc_info=True,
                )
                continue
            except Exception as e:
                # Log unexpected errors
                _LOGGER.error(
                    {
                        "class": "discover_devices",
                        "method": "discover",
                        "action": "unexpected_error",
                        "error_details": str(e),
                        "source_ip": addr[0],
                    },
                    exc_info=True,
                )
                continue

        _LOGGER.debug(
            {
                "class": "discover_devices",
                "method": "discover",
                "action": "complete",
                "devices_found": len(seen_serials),
                "packets_processed": packet_count,
                "elapsed": time.time() - start_time,
            }
        )
````

### DiscoveredDevice

```python
DiscoveredDevice(
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    first_seen: float = time(),
    response_time: float = 0.0,
)
```

Information about a discovered LIFX device.

| ATTRIBUTE       | DESCRIPTION                                                                        |
| --------------- | ---------------------------------------------------------------------------------- |
| `serial`        | Device serial number as 12-digit hex string (e.g., "d073d5123456") **TYPE:** `str` |
| `ip`            | Device IP address **TYPE:** `str`                                                  |
| `port`          | Device UDP port **TYPE:** `int`                                                    |
| `first_seen`    | Timestamp when device was first discovered **TYPE:** `float`                       |
| `response_time` | Response time in seconds **TYPE:** `float`                                         |

| METHOD          | DESCRIPTION                                                       |
| --------------- | ----------------------------------------------------------------- |
| `create_device` | Create appropriate device instance based on product capabilities. |
| `__hash__`      | Hash based on serial number for deduplication.                    |
| `__eq__`        | Equality based on serial number.                                  |

#### Functions

##### create_device

```python
create_device() -> Device | None
```

Create appropriate device instance based on product capabilities.

Queries the device for its product ID and uses the product registry to instantiate the appropriate device class (Device, Light, HevLight, InfraredLight, MultiZoneLight, MatrixLight, or CeilingLight) based on the product capabilities.

This is the single source of truth for device type detection and instantiation across the library.

| RETURNS  | DESCRIPTION |
| -------- | ----------- |
| \`Device | None\`      |

| RAISES                    | DESCRIPTION                    |
| ------------------------- | ------------------------------ |
| `LifxDeviceNotFoundError` | If device doesn't respond      |
| `LifxTimeoutError`        | If device query times out      |
| `LifxProtocolError`       | If device returns invalid data |

Example

```python
devices = await discover_devices()
for discovered in devices:
    device = await discovered.create_device()
    print(f"Created {type(device).__name__}: {await device.get_label()}")
```

Source code in `src/lifx/network/discovery.py`

````python
async def create_device(self) -> Device | None:
    """Create appropriate device instance based on product capabilities.

    Queries the device for its product ID and uses the product registry
    to instantiate the appropriate device class (Device, Light, HevLight,
    InfraredLight, MultiZoneLight, MatrixLight, or CeilingLight) based on
    the product capabilities.

    This is the single source of truth for device type detection and
    instantiation across the library.

    Returns:
        Device instance of the appropriate type

    Raises:
        LifxDeviceNotFoundError: If device doesn't respond
        LifxTimeoutError: If device query times out
        LifxProtocolError: If device returns invalid data

    Example:
        ```python
        devices = await discover_devices()
        for discovered in devices:
            device = await discovered.create_device()
            print(f"Created {type(device).__name__}: {await device.get_label()}")
        ```
    """
    from lifx.devices.base import Device
    from lifx.devices.ceiling import CeilingLight
    from lifx.devices.hev import HevLight
    from lifx.devices.infrared import InfraredLight
    from lifx.devices.light import Light
    from lifx.devices.matrix import MatrixLight
    from lifx.devices.multizone import MultiZoneLight
    from lifx.products import is_ceiling_product

    kwargs = {
        "serial": self.serial,
        "ip": self.ip,
        "port": self.port,
        "timeout": self.timeout,
        "max_retries": self.max_retries,
    }

    # Create temporary device to query version
    temp_device = Device(**kwargs)

    try:
        await temp_device._ensure_capabilities()

        if temp_device.capabilities:
            # Check for Ceiling products first (before generic MatrixLight)
            if temp_device.version and is_ceiling_product(
                temp_device.version.product
            ):
                return CeilingLight(**kwargs)

            if temp_device.capabilities.has_matrix:
                return MatrixLight(**kwargs)
            if temp_device.capabilities.has_multizone:
                return MultiZoneLight(**kwargs)
            if temp_device.capabilities.has_infrared:
                return InfraredLight(**kwargs)
            if temp_device.capabilities.has_hev:
                return HevLight(**kwargs)
            if temp_device.capabilities.has_relays or (
                temp_device.capabilities.has_buttons
                and not temp_device.capabilities.has_color
            ):
                return None

            return Light(**kwargs)

    except Exception:
        return None

    finally:
        # Always close the temporary device connection to prevent resource leaks
        await temp_device.connection.close()

    return None
````

##### __hash__

```python
__hash__() -> int
```

Hash based on serial number for deduplication.

Source code in `src/lifx/network/discovery.py`

```python
def __hash__(self) -> int:
    """Hash based on serial number for deduplication."""
    return hash(self.serial)
```

##### __eq__

```python
__eq__(other: object) -> bool
```

Equality based on serial number.

Source code in `src/lifx/network/discovery.py`

```python
def __eq__(self, other: object) -> bool:
    """Equality based on serial number."""
    if not isinstance(other, DiscoveredDevice):
        return False
    return self.serial == other.serial
```

### DiscoveryResponse

Response dataclass from custom discovery broadcasts (using packets other than GetService).

#### DiscoveryResponse

```python
DiscoveryResponse(
    serial: str,
    ip: str,
    port: int,
    response_time: float,
    response_payload: dict[str, Any],
)
```

Response from a discovery broadcast using a custom packet.

| ATTRIBUTE          | DESCRIPTION                                                               |
| ------------------ | ------------------------------------------------------------------------- |
| `serial`           | Device serial number **TYPE:** `str`                                      |
| `ip`               | Device IP address **TYPE:** `str`                                         |
| `port`             | Device UDP port **TYPE:** `int`                                           |
| `response_time`    | Response time in seconds **TYPE:** `float`                                |
| `response_payload` | Unpacked State packet fields as key/value dict **TYPE:** `dict[str, Any]` |

## UDP Transport

Low-level UDP transport for sending and receiving LIFX protocol messages.

### UdpTransport

```python
UdpTransport(
    ip_address: str = DEFAULT_IP_ADDRESS, port: int = 0, broadcast: bool = False
)
```

UDP transport for sending and receiving LIFX packets.

This class provides a simple interface for UDP communication with LIFX devices. It uses asyncio for async I/O operations.

| PARAMETER   | DESCRIPTION                                                                         |
| ----------- | ----------------------------------------------------------------------------------- |
| `port`      | Local port to bind to (0 for automatic assignment) **TYPE:** `int` **DEFAULT:** `0` |
| `broadcast` | Enable broadcast mode for device discovery **TYPE:** `bool` **DEFAULT:** `False`    |

| METHOD         | DESCRIPTION                                     |
| -------------- | ----------------------------------------------- |
| `open`         | Open the UDP socket.                            |
| `send`         | Send data to a specific address.                |
| `receive`      | Receive data from socket with size validation.  |
| `receive_many` | Receive multiple packets within timeout period. |
| `close`        | Close the UDP socket.                           |

| ATTRIBUTE | DESCRIPTION                               |
| --------- | ----------------------------------------- |
| `is_open` | Check if socket is open. **TYPE:** `bool` |

Source code in `src/lifx/network/transport.py`

```python
def __init__(
    self,
    ip_address: str = DEFAULT_IP_ADDRESS,
    port: int = 0,
    broadcast: bool = False,
) -> None:
    """Initialize UDP transport.

    Args:
        port: Local port to bind to (0 for automatic assignment)
        broadcast: Enable broadcast mode for device discovery
    """
    self._ip_address = ip_address
    self._port = port
    self._broadcast = broadcast
    self._protocol: _UdpProtocol | None = None
    self._transport: DatagramTransport | None = None
```

#### Attributes

##### is_open

```python
is_open: bool
```

Check if socket is open.

#### Functions

##### open

```python
open() -> None
```

Open the UDP socket.

Source code in `src/lifx/network/transport.py`

```python
async def open(self) -> None:
    """Open the UDP socket."""
    if self._protocol is not None:
        _LOGGER.debug(
            {
                "class": "UdpTransport",
                "method": "open",
                "action": "already_open",
                "ip_address": self._ip_address,
                "port": self._port,
            }
        )
        return

    try:
        import socket as stdlib_socket

        loop = asyncio.get_running_loop()

        _LOGGER.debug(
            {
                "class": "UdpTransport",
                "method": "open",
                "action": "opening_socket",
                "ip_address": self._ip_address,
                "port": self._port,
                "broadcast": self._broadcast,
            }
        )

        # Create protocol
        protocol = _UdpProtocol()
        self._protocol = protocol

        # Create datagram endpoint
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol,
            local_addr=(self._ip_address, self._port),
            reuse_port=bool(hasattr(stdlib_socket, "SO_REUSEPORT")),
            family=stdlib_socket.AF_INET,
        )

        # Get actual port assigned
        actual_port = self._transport.get_extra_info("sockname")[1]
        _LOGGER.debug(
            {
                "class": "UdpTransport",
                "method": "open",
                "action": "socket_opened",
                "assigned_port": actual_port,
                "broadcast": self._broadcast,
            }
        )

        # Enable broadcast if requested
        if self._broadcast:
            sock = self._transport.get_extra_info("socket")
            if sock:
                sock.setsockopt(
                    stdlib_socket.SOL_SOCKET,
                    stdlib_socket.SO_BROADCAST,
                    1,
                )
                _LOGGER.debug(
                    {
                        "class": "UdpTransport",
                        "method": "open",
                        "action": "broadcast_enabled",
                    }
                )

    except OSError as e:
        _LOGGER.debug(
            {
                "class": "UdpTransport",
                "method": "open",
                "action": "failed",
                "ip_address": self._ip_address,
                "port": self._port,
                "reason": str(e),
            }
        )
        raise LifxNetworkError(f"Failed to open UDP socket: {e}") from e
```

##### send

```python
send(data: bytes, address: tuple[str, int]) -> None
```

Send data to a specific address.

| PARAMETER | DESCRIPTION                                       |
| --------- | ------------------------------------------------- |
| `data`    | Bytes to send **TYPE:** `bytes`                   |
| `address` | Tuple of (host, port) **TYPE:** `tuple[str, int]` |

| RAISES         | DESCRIPTION                         |
| -------------- | ----------------------------------- |
| `NetworkError` | If socket is not open or send fails |

Source code in `src/lifx/network/transport.py`

```python
async def send(self, data: bytes, address: tuple[str, int]) -> None:
    """Send data to a specific address.

    Args:
        data: Bytes to send
        address: Tuple of (host, port)

    Raises:
        NetworkError: If socket is not open or send fails
    """
    if self._transport is None or self._protocol is None:
        raise LifxNetworkError("Socket not open")

    try:
        self._transport.sendto(data, address)
    except OSError as e:
        _LOGGER.debug(
            {
                "class": "UdpTransport",
                "method": "send",
                "action": "failed",
                "destination": address,
                "packet_size": len(data),
                "reason": str(e),
            }
        )
        raise LifxNetworkError(f"Failed to send data: {e}") from e
```

##### receive

```python
receive(timeout: float = 2.0) -> tuple[bytes, tuple[str, int]]
```

Receive data from socket with size validation.

| PARAMETER | DESCRIPTION                                             |
| --------- | ------------------------------------------------------- |
| `timeout` | Timeout in seconds **TYPE:** `float` **DEFAULT:** `2.0` |

| RETURNS                         | DESCRIPTION                                            |
| ------------------------------- | ------------------------------------------------------ |
| `tuple[bytes, tuple[str, int]]` | Tuple of (data, address) where address is (host, port) |

| RAISES             | DESCRIPTION                            |
| ------------------ | -------------------------------------- |
| `LifxTimeoutError` | If no data received within timeout     |
| `NetworkError`     | If socket is not open or receive fails |
| `ProtocolError`    | If packet size is invalid              |

Source code in `src/lifx/network/transport.py`

```python
async def receive(self, timeout: float = 2.0) -> tuple[bytes, tuple[str, int]]:
    """Receive data from socket with size validation.

    Args:
        timeout: Timeout in seconds

    Returns:
        Tuple of (data, address) where address is (host, port)

    Raises:
        LifxTimeoutError: If no data received within timeout
        NetworkError: If socket is not open or receive fails
        ProtocolError: If packet size is invalid
    """
    if self._protocol is None:
        raise LifxNetworkError("Socket not open")

    try:
        data, addr = await asyncio.wait_for(
            self._protocol.queue.get(), timeout=timeout
        )
    except TIMEOUT_ERRORS as e:
        raise LifxTimeoutError(f"No data received within {timeout}s") from e
    except OSError as e:
        _LOGGER.error(
            {
                "class": "UdpTransport",
                "method": "receive",
                "action": "failed",
                "reason": str(e),
            }
        )
        raise LifxNetworkError(f"Failed to receive data: {e}") from e

    # Validate packet size
    if len(data) > MAX_PACKET_SIZE:
        from lifx.exceptions import LifxProtocolError

        _LOGGER.error(
            {
                "class": "UdpTransport",
                "method": "receive",
                "action": "packet_too_large",
                "packet_size": len(data),
                "max_size": MAX_PACKET_SIZE,
            }
        )
        raise LifxProtocolError(
            f"Packet too big: {len(data)} bytes > {MAX_PACKET_SIZE} bytes"
        )

    if len(data) < MIN_PACKET_SIZE:
        from lifx.exceptions import LifxProtocolError

        _LOGGER.error(
            {
                "class": "UdpTransport",
                "method": "receive",
                "action": "packet_too_small",
                "packet_size": len(data),
                "min_size": MIN_PACKET_SIZE,
            }
        )
        raise LifxProtocolError(
            f"Packet too small: {len(data)} bytes < {MIN_PACKET_SIZE} bytes"
        )

    return data, addr
```

##### receive_many

```python
receive_many(
    timeout: float = 5.0, max_packets: int | None = None
) -> list[tuple[bytes, tuple[str, int]]]
```

Receive multiple packets within timeout period.

| PARAMETER     | DESCRIPTION                                                               |
| ------------- | ------------------------------------------------------------------------- |
| `timeout`     | Total timeout in seconds **TYPE:** `float` **DEFAULT:** `5.0`             |
| `max_packets` | Maximum number of packets to receive (None for unlimited) **TYPE:** \`int |

| RETURNS                               | DESCRIPTION                    |
| ------------------------------------- | ------------------------------ |
| `list[tuple[bytes, tuple[str, int]]]` | List of (data, address) tuples |

| RAISES         | DESCRIPTION           |
| -------------- | --------------------- |
| `NetworkError` | If socket is not open |

Source code in `src/lifx/network/transport.py`

```python
async def receive_many(
    self, timeout: float = 5.0, max_packets: int | None = None
) -> list[tuple[bytes, tuple[str, int]]]:
    """Receive multiple packets within timeout period.

    Args:
        timeout: Total timeout in seconds
        max_packets: Maximum number of packets to receive (None for unlimited)

    Returns:
        List of (data, address) tuples

    Raises:
        NetworkError: If socket is not open
    """
    if self._protocol is None:
        raise LifxNetworkError("Socket not open")

    import time

    packets: list[tuple[bytes, tuple[str, int]]] = []
    deadline = time.monotonic() + timeout

    while True:
        if max_packets is not None and len(packets) >= max_packets:
            break

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        try:
            data, addr = await asyncio.wait_for(
                self._protocol.queue.get(), timeout=remaining
            )

            # Validate packet size
            if len(data) > MAX_PACKET_SIZE:
                # Drop oversized packet to prevent memory exhaustion DoS
                continue

            if len(data) < MIN_PACKET_SIZE:
                # Drop undersized packet (header is 36 bytes)
                continue

            packets.append((data, addr))
        except TIMEOUT_ERRORS:
            # Timeout is expected - return what we collected
            break
        except OSError:
            # Ignore individual receive errors
            break

    return packets
```

##### close

```python
close() -> None
```

Close the UDP socket.

Source code in `src/lifx/network/transport.py`

```python
async def close(self) -> None:
    """Close the UDP socket."""
    if self._transport is not None:
        _LOGGER.debug(
            {
                "class": "UdpTransport",
                "method": "close",
                "action": "closing",
            }
        )
        self._transport.close()
        self._transport = None
        self._protocol = None
        _LOGGER.debug(
            {
                "class": "UdpTransport",
                "method": "close",
                "action": "closed",
            }
        )
```

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

### DeviceConnection

```python
DeviceConnection(
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
)
```

Connection to a LIFX device.

This class manages the UDP transport and request/response lifecycle for a single device. Connections are opened lazily on first request and remain open until explicitly closed.

Features:

- Lazy connection opening (no context manager required)
- Async generator-based request/response streaming
- Retry logic with exponential backoff and jitter
- Request serialization to prevent response mixing
- Automatic sequence number management

Example

```python
conn = DeviceConnection(serial="d073d5123456", ip="192.168.1.100")

# Connection opens automatically on first request
state = await conn.request(packets.Light.GetColor())
# state.label is already decoded to string
# state.color is LightHsbk instance

# Optionally close when done
await conn.close()
```

With context manager (recommended for cleanup):

```python
async with DeviceConnection(...) as conn:
    state = await conn.request(packets.Light.GetColor())
# Connection automatically closed on exit
```

This is lightweight - doesn't actually create a connection. Connection is opened lazily on first request.

| PARAMETER     | DESCRIPTION                                                                                                     |
| ------------- | --------------------------------------------------------------------------------------------------------------- |
| `serial`      | Device serial number as 12-digit hex string (e.g., 'd073d5123456') **TYPE:** `str`                              |
| `ip`          | Device IP address **TYPE:** `str`                                                                               |
| `port`        | Device UDP port (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                            |
| `max_retries` | Maximum number of retry attempts (default: 8) **TYPE:** `int` **DEFAULT:** `DEFAULT_MAX_RETRIES`                |
| `timeout`     | Default timeout for requests in seconds (default: 8.0) **TYPE:** `float` **DEFAULT:** `DEFAULT_REQUEST_TIMEOUT` |

| METHOD           | DESCRIPTION                                                 |
| ---------------- | ----------------------------------------------------------- |
| `__aenter__`     | Enter async context manager.                                |
| `__aexit__`      | Exit async context manager and close connection.            |
| `open`           | Open connection to device.                                  |
| `close`          | Close connection to device.                                 |
| `send_packet`    | Send a packet to the device.                                |
| `receive_packet` | Receive a packet from the device.                           |
| `request_stream` | Send request and yield unpacked responses.                  |
| `request`        | Send request and get single response (convenience wrapper). |

| ATTRIBUTE | DESCRIPTION                                   |
| --------- | --------------------------------------------- |
| `is_open` | Check if connection is open. **TYPE:** `bool` |

Source code in `src/lifx/network/connection.py`

```python
def __init__(
    self,
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
) -> None:
    """Initialize device connection.

    This is lightweight - doesn't actually create a connection.
    Connection is opened lazily on first request.

    Args:
        serial: Device serial number as 12-digit hex string (e.g., 'd073d5123456')
        ip: Device IP address
        port: Device UDP port (default LIFX_UDP_PORT)
        max_retries: Maximum number of retry attempts (default: 8)
        timeout: Default timeout for requests in seconds (default: 8.0)
    """
    self.serial = serial
    self.ip = ip
    self.port = port
    self.max_retries = max_retries
    self.timeout = timeout

    self._transport: UdpTransport | None = None
    self._is_open = False
    self._is_opening = False  # Flag to prevent concurrent open() calls

    # Background receiver task infrastructure
    # Key: (source, sequence, serial) → Queue of (header, payload) tuples
    self._pending_requests: dict[
        tuple[int, int, str], asyncio.Queue[tuple[LifxHeader, bytes]]
    ] = {}
    self._receiver_task: asyncio.Task[None] | None = None
    self._receiver_shutdown: asyncio.Event | None = None
```

#### Attributes

##### is_open

```python
is_open: bool
```

Check if connection is open.

#### Functions

##### __aenter__

```python
__aenter__() -> Self
```

Enter async context manager.

Source code in `src/lifx/network/connection.py`

```python
async def __aenter__(self) -> Self:
    """Enter async context manager."""
    # Don't open connection here - it will open lazily on first request
    return self
```

##### __aexit__

```python
__aexit__(
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: object,
) -> None
```

Exit async context manager and close connection.

Source code in `src/lifx/network/connection.py`

```python
async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: object,
) -> None:
    """Exit async context manager and close connection."""
    await self.close()
```

##### open

```python
open() -> None
```

Open connection to device.

Opens the UDP transport for sending and receiving packets. Called automatically on first request if not already open.

Source code in `src/lifx/network/connection.py`

```python
async def open(self) -> None:
    """Open connection to device.

    Opens the UDP transport for sending and receiving packets.
    Called automatically on first request if not already open.
    """
    if self._is_open:
        return

    # Prevent concurrent open() calls
    if self._is_opening:
        # Another task is already opening, wait for it
        while self._is_opening:
            await asyncio.sleep(0.001)
        return

    self._is_opening = True
    try:
        # Double-check after setting flag
        if self._is_open:  # pragma: no cover
            return

        # Create shutdown event for receiver task
        self._receiver_shutdown = asyncio.Event()

        # Open transport
        self._transport = UdpTransport(port=0, broadcast=False)
        await self._transport.open()
        self._is_open = True

        # Start background receiver task
        self._receiver_task = asyncio.create_task(self._background_receiver())

        _LOGGER.debug(
            {
                "class": "DeviceConnection",
                "method": "open",
                "serial": self.serial,
                "ip": self.ip,
                "port": self.port,
            }
        )
    finally:
        self._is_opening = False
```

##### close

```python
close() -> None
```

Close connection to device.

Source code in `src/lifx/network/connection.py`

```python
async def close(self) -> None:
    """Close connection to device."""
    if not self._is_open:
        return

    self._is_open = False

    # Signal shutdown to receiver task
    if self._receiver_shutdown:
        self._receiver_shutdown.set()

    # Wait for receiver to stop (with timeout)
    if self._receiver_task:
        try:
            await asyncio.wait_for(
                self._receiver_task, timeout=_RECEIVER_SHUTDOWN_TIMEOUT
            )
        except TIMEOUT_ERRORS:
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass

    # Cancel all pending request queues
    for queue in self._pending_requests.values():
        # Drain queue
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    self._pending_requests.clear()

    # Close transport
    if self._transport is not None:
        await self._transport.close()

    _LOGGER.debug(
        {
            "class": "DeviceConnection",
            "method": "close",
            "serial": self.serial,
            "ip": self.ip,
        }
    )
    self._transport = None
```

##### send_packet

```python
send_packet(
    packet: Any,
    source: int | None = None,
    sequence: int = 0,
    ack_required: bool = False,
    res_required: bool = False,
) -> None
```

Send a packet to the device.

| PARAMETER      | DESCRIPTION                                                            |
| -------------- | ---------------------------------------------------------------------- |
| `packet`       | Packet dataclass instance **TYPE:** `Any`                              |
| `source`       | Client source identifier (optional, allocated if None) **TYPE:** \`int |
| `sequence`     | Sequence number (default: 0) **TYPE:** `int` **DEFAULT:** `0`          |
| `ack_required` | Request acknowledgement **TYPE:** `bool` **DEFAULT:** `False`          |
| `res_required` | Request response **TYPE:** `bool` **DEFAULT:** `False`                 |

| RAISES            | DESCRIPTION                             |
| ----------------- | --------------------------------------- |
| `ConnectionError` | If connection is not open or send fails |

Source code in `src/lifx/network/connection.py`

```python
async def send_packet(
    self,
    packet: Any,
    source: int | None = None,
    sequence: int = 0,
    ack_required: bool = False,
    res_required: bool = False,
) -> None:
    """Send a packet to the device.

    Args:
        packet: Packet dataclass instance
        source: Client source identifier (optional, allocated if None)
        sequence: Sequence number (default: 0)
        ack_required: Request acknowledgement
        res_required: Request response

    Raises:
        ConnectionError: If connection is not open or send fails
    """
    if not self._is_open or self._transport is None:
        raise LifxConnectionError("Connection not open")

    # Allocate source if not provided
    if source is None:
        source = self._allocate_source()

    target = Serial.from_string(self.serial).to_protocol()
    message = create_message(
        packet=packet,
        source=source,
        sequence=sequence,
        target=target,
        ack_required=ack_required,
        res_required=res_required,
    )

    # Send to device
    await self._transport.send(message, (self.ip, self.port))
```

##### receive_packet

```python
receive_packet(timeout: float = 0.5) -> tuple[LifxHeader, bytes]
```

Receive a packet from the device.

Note

This method does not validate the source IP address. Validation is instead performed using the LIFX protocol's built-in target field (serial number) and sequence number matching in request_stream() and request_ack_stream(). This approach is more reliable in complex network configurations (NAT, multiple interfaces, bridges, etc.) while maintaining security through proper protocol-level validation.

| PARAMETER | DESCRIPTION                                             |
| --------- | ------------------------------------------------------- |
| `timeout` | Timeout in seconds **TYPE:** `float` **DEFAULT:** `0.5` |

| RETURNS                    | DESCRIPTION                |
| -------------------------- | -------------------------- |
| `tuple[LifxHeader, bytes]` | Tuple of (header, payload) |

| RAISES            | DESCRIPTION                   |
| ----------------- | ----------------------------- |
| `ConnectionError` | If connection is not open     |
| `TimeoutError`    | If no response within timeout |

Source code in `src/lifx/network/connection.py`

```python
async def receive_packet(self, timeout: float = 0.5) -> tuple[LifxHeader, bytes]:
    """Receive a packet from the device.

    Note:
        This method does not validate the source IP address. Validation is instead
        performed using the LIFX protocol's built-in target field (serial number)
        and sequence number matching in request_stream() and request_ack_stream().
        This approach is more reliable in complex network configurations (NAT,
        multiple interfaces, bridges, etc.) while maintaining security through
        proper protocol-level validation.

    Args:
        timeout: Timeout in seconds

    Returns:
        Tuple of (header, payload)

    Raises:
        ConnectionError: If connection is not open
        TimeoutError: If no response within timeout
    """
    if not self._is_open or self._transport is None:
        raise LifxConnectionError("Connection not open")

    # Receive message - source address not validated here
    # Validation occurs via target field and sequence number matching
    data, _addr = await self._transport.receive(timeout=timeout)

    # Parse and return message
    return parse_message(data)
```

##### request_stream

```python
request_stream(
    packet: Any, timeout: float | None = None
) -> AsyncGenerator[Any, None]
```

Send request and yield unpacked responses.

This is an async generator that handles the complete request/response cycle including packet type detection, response unpacking, and label decoding. Connection is opened automatically if not already open.

Single response (most common): async for response in conn.request_stream(GetLabel()): process(response) break # Exit immediately

Multiple responses

async for state in conn.request_stream(GetColorZones()): process(state)

# Continues until timeout

| PARAMETER | DESCRIPTION                                  |
| --------- | -------------------------------------------- |
| `packet`  | Packet instance to send **TYPE:** `Any`      |
| `timeout` | Request timeout in seconds **TYPE:** \`float |

| YIELDS                      | DESCRIPTION                                                              |
| --------------------------- | ------------------------------------------------------------------------ |
| `AsyncGenerator[Any, None]` | Unpacked response packet instances (including StateUnhandled if device   |
| `AsyncGenerator[Any, None]` | doesn't support the command)                                             |
| `AsyncGenerator[Any, None]` | For SET packets: yields True (acknowledgement) or False (StateUnhandled) |

| RAISES                | DESCRIPTION          |
| --------------------- | -------------------- |
| `LifxTimeoutError`    | If request times out |
| `LifxProtocolError`   | If response invalid  |
| `LifxConnectionError` | If connection fails  |

Example

```python
# GET request yields unpacked packets
async for state in conn.request_stream(packets.Light.GetColor()):
    color = HSBK.from_protocol(state.color)
    label = state.label  # Already decoded to string
    break

# SET request yields True (acknowledgement) or False (StateUnhandled)
async for result in conn.request_stream(
    packets.Light.SetColor(color=hsbk, duration=1000)
):
    if result:
        # Acknowledgement received
        pass
    else:
        # Device doesn't support this command
        pass
    break

# Multi-response GET - stream all responses
async for state in conn.request_stream(
    packets.MultiZone.GetExtendedColorZones()
):
    # Process each zone state
    pass
```

Source code in `src/lifx/network/connection.py`

````python
async def request_stream(
    self,
    packet: Any,
    timeout: float | None = None,
) -> AsyncGenerator[Any, None]:
    """Send request and yield unpacked responses.

    This is an async generator that handles the complete request/response
    cycle including packet type detection, response unpacking, and label
    decoding. Connection is opened automatically if not already open.

    Single response (most common):
        async for response in conn.request_stream(GetLabel()):
            process(response)
            break  # Exit immediately

    Multiple responses:
        async for state in conn.request_stream(GetColorZones()):
            process(state)
            # Continues until timeout

    Args:
        packet: Packet instance to send
        timeout: Request timeout in seconds

    Yields:
        Unpacked response packet instances (including StateUnhandled if device
        doesn't support the command)
        For SET packets: yields True (acknowledgement) or False (StateUnhandled)

    Raises:
        LifxTimeoutError: If request times out
        LifxProtocolError: If response invalid
        LifxConnectionError: If connection fails

    Example:
        ```python
        # GET request yields unpacked packets
        async for state in conn.request_stream(packets.Light.GetColor()):
            color = HSBK.from_protocol(state.color)
            label = state.label  # Already decoded to string
            break

        # SET request yields True (acknowledgement) or False (StateUnhandled)
        async for result in conn.request_stream(
            packets.Light.SetColor(color=hsbk, duration=1000)
        ):
            if result:
                # Acknowledgement received
                pass
            else:
                # Device doesn't support this command
                pass
            break

        # Multi-response GET - stream all responses
        async for state in conn.request_stream(
            packets.MultiZone.GetExtendedColorZones()
        ):
            # Process each zone state
            pass
        ```
    """
    # Ensure connection is open (lazy opening)
    await self._ensure_open()

    if timeout is None:
        timeout = self.timeout

    # Get packet metadata
    packet_kind = getattr(packet, "_packet_kind", "OTHER")

    if packet_kind == "GET":
        # Use PACKET_REGISTRY to find the appropriate packet class
        from lifx.protocol.packets import get_packet_class

        # Stream responses and unpack each
        async for header, payload in self._request_stream_impl(
            packet, timeout=timeout
        ):
            packet_class = get_packet_class(header.pkt_type)
            if packet_class is None:
                raise LifxProtocolError(
                    f"Unknown packet type {header.pkt_type} in response"
                )

            # Update unknown serial with value from response header
            serial = Serial(value=header.target_serial).to_string()
            if self.serial == "000000000000" and serial != self.serial:
                self.serial = serial

            # Unpack (labels are automatically decoded by Packet.unpack())
            response_packet = packet_class.unpack(payload)

            # Log the request/reply cycle
            request_values = packet.as_dict
            reply_values = response_packet.as_dict
            _LOGGER.debug(
                {
                    "class": "DeviceConnection",
                    "method": "request_stream",
                    "request": {
                        "packet": type(packet).__name__,
                        "values": request_values,
                    },
                    "reply": {
                        "packet": type(response_packet).__name__,
                        "values": reply_values,
                    },
                    "serial": self.serial,
                    "ip": self.ip,
                }
            )

            yield response_packet

    elif packet_kind == "SET":
        # Request acknowledgement
        async for ack_result in self._request_ack_stream_impl(
            packet, timeout=timeout
        ):
            # Log the request/ack cycle
            request_values = packet.as_dict
            reply_packet = "Acknowledgement" if ack_result else "StateUnhandled"
            _LOGGER.debug(
                {
                    "class": "DeviceConnection",
                    "method": "request_stream",
                    "request": {
                        "packet": type(packet).__name__,
                        "values": request_values,
                    },
                    "reply": {
                        "packet": reply_packet,
                        "values": {},
                    },
                    "serial": self.serial,
                    "ip": self.ip,
                }
            )

            yield ack_result
            return

    else:
        # Handle special cases
        if hasattr(packet, "PKT_TYPE"):
            pkt_type = packet.PKT_TYPE
            # EchoRequest/EchoResponse (58/59)
            if pkt_type == 58:  # EchoRequest
                from lifx.protocol.packets import Device

                async for header, payload in self._request_stream_impl(
                    packet, timeout=timeout
                ):
                    response_packet = Device.EchoResponse.unpack(payload)

                    # Log the request/reply cycle
                    request_values = packet.as_dict
                    reply_values = response_packet.as_dict
                    _LOGGER.debug(
                        {
                            "class": "DeviceConnection",
                            "method": "request_stream",
                            "request": {
                                "packet": type(packet).__name__,
                                "values": request_values,
                            },
                            "reply": {
                                "packet": type(response_packet).__name__,
                                "values": reply_values,
                            },
                            "serial": self.serial,
                            "ip": self.ip,
                        }
                    )

                    yield response_packet
                    return
            else:
                raise LifxProtocolError(
                    f"Cannot auto-handle packet kind: {packet_kind}"
                )
        else:
            raise LifxProtocolError(
                f"Packet missing PKT_TYPE: {type(packet).__name__}"
            )
````

##### request

```python
request(packet: Any, timeout: float | None = None) -> Any
```

Send request and get single response (convenience wrapper).

This is a convenience method that returns the first response from request_stream(). It's equivalent to: await anext(conn.request_stream(packet))

Most device operations use this method since they expect a single response. Connection is opened automatically if not already open.

| PARAMETER | DESCRIPTION                                  |
| --------- | -------------------------------------------- |
| `packet`  | Packet instance to send **TYPE:** `Any`      |
| `timeout` | Request timeout in seconds **TYPE:** \`float |

| RETURNS | DESCRIPTION                                                         |
| ------- | ------------------------------------------------------------------- |
| `Any`   | Single unpacked response packet (including StateUnhandled if device |
| `Any`   | doesn't support the command)                                        |
| `Any`   | For SET packets: True (acknowledgement) or False (StateUnhandled)   |

| RAISES                | DESCRIPTION                   |
| --------------------- | ----------------------------- |
| `LifxTimeoutError`    | If no response within timeout |
| `LifxProtocolError`   | If response invalid           |
| `LifxConnectionError` | If connection fails           |

Example

```python
# GET request returns unpacked packet
state = await conn.request(packets.Light.GetColor())
color = HSBK.from_protocol(state.color)
label = state.label  # Already decoded to string

# SET request returns True or False
success = await conn.request(
    packets.Light.SetColor(color=hsbk, duration=1000)
)
if not success:
    # Device doesn't support this command (returned StateUnhandled)
    pass
```

Source code in `src/lifx/network/connection.py`

````python
async def request(self, packet: Any, timeout: float | None = None) -> Any:
    """Send request and get single response (convenience wrapper).

    This is a convenience method that returns the first response from
    request_stream(). It's equivalent to:
        await anext(conn.request_stream(packet))

    Most device operations use this method since they expect a single response.
    Connection is opened automatically if not already open.

    Args:
        packet: Packet instance to send
        timeout: Request timeout in seconds

    Returns:
        Single unpacked response packet (including StateUnhandled if device
        doesn't support the command)
        For SET packets: True (acknowledgement) or False (StateUnhandled)

    Raises:
        LifxTimeoutError: If no response within timeout
        LifxProtocolError: If response invalid
        LifxConnectionError: If connection fails

    Example:
        ```python
        # GET request returns unpacked packet
        state = await conn.request(packets.Light.GetColor())
        color = HSBK.from_protocol(state.color)
        label = state.label  # Already decoded to string

        # SET request returns True or False
        success = await conn.request(
            packets.Light.SetColor(color=hsbk, duration=1000)
        )
        if not success:
            # Device doesn't support this command (returned StateUnhandled)
            pass
        ```
    """
    async for response in self.request_stream(packet, timeout):
        return response
    raise LifxTimeoutError(f"No response from {self.ip}")
````

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

The library **intentionally does not implement rate limiting** to keep the core library simple. Applications should implement their own rate limiting if needed. According to the LIFX protocol specification, devices can handle approximately 20 messages per second.
