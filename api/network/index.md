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
) -> list[DiscoveredDevice]
```

Discover LIFX devices on the local network.

Sends a broadcast DeviceGetService packet and collects responses. Implements DoS protection via timeout, source validation, and serial validation.

| PARAMETER           | DESCRIPTION                                                                          |
| ------------------- | ------------------------------------------------------------------------------------ |
| `timeout`           | Discovery timeout in seconds **TYPE:** `float` **DEFAULT:** `DISCOVERY_TIMEOUT`      |
| `broadcast_address` | Broadcast address to use **TYPE:** `str` **DEFAULT:** `'255.255.255.255'`            |
| `port`              | UDP port to use (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT` |

| RETURNS                  | DESCRIPTION                                                |
| ------------------------ | ---------------------------------------------------------- |
| `list[DiscoveredDevice]` | List of discovered devices (deduplicated by serial number) |

Example

```python
devices = await discover_devices(timeout=5.0)
for device in devices:
    print(f"Found device: {device.serial} at {device.ip}:{device.port}")
```

Source code in `src/lifx/network/discovery.py`

````python
async def discover_devices(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> list[DiscoveredDevice]:
    """Discover LIFX devices on the local network.

    Sends a broadcast DeviceGetService packet and collects responses.
    Implements DoS protection via timeout, source validation, and serial validation.

    Args:
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: UDP port to use (default LIFX_UDP_PORT)

    Returns:
        List of discovered devices (deduplicated by serial number)

    Example:
        ```python
        devices = await discover_devices(timeout=5.0)
        for device in devices:
            print(f"Found device: {device.serial} at {device.ip}:{device.port}")
        ```
    """
    devices: dict[str, DiscoveredDevice] = {}
    packet_count = 0
    start_time = time.time()

    # Create transport with broadcast enabled
    async with UdpTransport(port=0, broadcast=True) as transport:
        # Create discovery message
        builder = MessageBuilder()
        discovery_packet = DevicePackets.GetService()
        message = builder.create_message(
            packet=discovery_packet,
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
                if header.source != builder.source:
                    _LOGGER.debug(
                        {
                            "class": "discover_devices",
                            "method": "discover",
                            "action": "source_mismatch",
                            "expected_source": builder.source,
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
                service, device_port = _parse_device_state_service(payload)

                # Calculate accurate response time from this specific response
                response_time = response_timestamp - request_time

                # Convert 8-byte protocol serial to string
                device_serial = Serial.from_protocol(header.target).to_string()

                # Create device info
                device = DiscoveredDevice(
                    serial=device_serial,
                    ip=addr[0],
                    port=device_port,
                    service=service,
                    response_time=response_time,
                )

                # Deduplicate by serial number
                devices[device.serial] = device

                # Update last response time for idle timeout calculation
                last_response_time = response_timestamp

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
                "devices_found": len(devices),
                "packets_processed": packet_count,
                "elapsed": time.time() - start_time,
            }
        )

    return list(devices.values())
````

### DiscoveredDevice

```python
DiscoveredDevice(
    serial: str,
    ip: str,
    port: int,
    service: int,
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
| `service`       | Service type (typically UDP=1) **TYPE:** `int`                                     |
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
create_device() -> Device
```

Create appropriate device instance based on product capabilities.

Queries the device for its product ID and firmware version, then instantiates the appropriate device class (Device, Light, MultiZoneLight, or TileDevice) based on the product capabilities.

| RETURNS  | DESCRIPTION                             |
| -------- | --------------------------------------- |
| `Device` | Device instance of the appropriate type |

| RAISES                | DESCRIPTION               |
| --------------------- | ------------------------- |
| `DeviceNotFoundError` | If device doesn't respond |
| `TimeoutError`        | If device query times out |

Example

```python
devices = await discover_devices()
for discovered in devices:
    device = await discovered.create_device()
    print(f"Created {type(device).__name__}: {await device.get_label()}")
```

Source code in `src/lifx/network/discovery.py`

````python
async def create_device(self) -> Device:
    """Create appropriate device instance based on product capabilities.

    Queries the device for its product ID and firmware version, then
    instantiates the appropriate device class (Device, Light, MultiZoneLight,
    or TileDevice) based on the product capabilities.

    Returns:
        Device instance of the appropriate type

    Raises:
        DeviceNotFoundError: If device doesn't respond
        TimeoutError: If device query times out

    Example:
        ```python
        devices = await discover_devices()
        for discovered in devices:
            device = await discovered.create_device()
            print(f"Created {type(device).__name__}: {await device.get_label()}")
        ```
    """
    from lifx.devices.base import Device
    from lifx.devices.hev import HevLight
    from lifx.devices.infrared import InfraredLight
    from lifx.devices.light import Light
    from lifx.devices.multizone import MultiZoneLight
    from lifx.devices.tile import TileDevice
    from lifx.products import get_device_class_name

    # Create temporary device to query version (registry is always pre-loaded)
    temp_device = Device(serial=self.serial, ip=self.ip, port=self.port)

    try:
        version = await temp_device.get_version()
        pid = version.product

        # Get appropriate class name
        class_name = get_device_class_name(pid)

        # Instantiate the correct class
        if class_name == "TileDevice":
            device = TileDevice(serial=self.serial, ip=self.ip, port=self.port)
        elif class_name == "MultiZoneLight":
            device = MultiZoneLight(serial=self.serial, ip=self.ip, port=self.port)
        elif class_name == "HevLight":
            device = HevLight(serial=self.serial, ip=self.ip, port=self.port)
        elif class_name == "InfraredLight":
            device = InfraredLight(serial=self.serial, ip=self.ip, port=self.port)
        elif class_name == "Light":
            device = Light(serial=self.serial, ip=self.ip, port=self.port)
        else:
            device = temp_device

        return device

    except Exception:
        # If version query fails, default to Light
        device = Light(serial=self.serial, ip=self.ip, port=self.port)
        return device
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
        async with asyncio.timeout(timeout):
            data, addr = await self._protocol.queue.get()

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
    except TimeoutError as e:
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

    packets: list[tuple[bytes, tuple[str, int]]] = []

    try:
        async with asyncio.timeout(timeout):
            while True:
                if max_packets is not None and len(packets) >= max_packets:
                    break

                try:
                    data, addr = await self._protocol.queue.get()

                    # Validate packet size
                    if len(data) > MAX_PACKET_SIZE:
                        # Drop oversized packet to prevent memory exhaustion DoS
                        continue

                    if len(data) < MIN_PACKET_SIZE:
                        # Drop undersized packet (header is 36 bytes)
                        continue

                    packets.append((data, addr))
                except OSError:
                    # Ignore individual receive errors
                    break

    except TimeoutError:
        # Timeout is expected - return what we collected
        pass

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

## Message Building

Utilities for building and parsing LIFX protocol messages.

### MessageBuilder

```python
MessageBuilder(source: int | None = None)
```

Builder for creating LIFX messages with consistent source and sequence.

This class maintains state for source ID and sequence numbers, making it easier to create multiple messages from the same client.

| PARAMETER | DESCRIPTION                                        |
| --------- | -------------------------------------------------- |
| `source`  | Client identifier (random if None) **TYPE:** \`int |

| METHOD           | DESCRIPTION                                        |
| ---------------- | -------------------------------------------------- |
| `create_message` | Create a message with auto-incrementing sequence.  |
| `next_sequence`  | Get the next sequence number without incrementing. |

Source code in `src/lifx/network/message.py`

```python
def __init__(self, source: int | None = None) -> None:
    """Initialize message builder.

    Args:
        source: Client identifier (random if None)
    """
    self.source = (
        source if source is not None else secrets.randbelow(0xFFFFFFFF) + 1
    )
    self._sequence = 0
```

#### Functions

##### create_message

```python
create_message(
    packet: Any,
    target: bytes = b"\x00" * 8,
    ack_required: bool = False,
    res_required: bool = True,
) -> bytes
```

Create a message with auto-incrementing sequence.

| PARAMETER      | DESCRIPTION                                                                |
| -------------- | -------------------------------------------------------------------------- |
| `packet`       | Packet dataclass instance **TYPE:** `Any`                                  |
| `target`       | Device serial number in bytes **TYPE:** `bytes` **DEFAULT:** `b'\x00' * 8` |
| `ack_required` | Request acknowledgement **TYPE:** `bool` **DEFAULT:** `False`              |
| `res_required` | Request response **TYPE:** `bool` **DEFAULT:** `True`                      |

| RETURNS | DESCRIPTION            |
| ------- | ---------------------- |
| `bytes` | Complete message bytes |

Source code in `src/lifx/network/message.py`

```python
def create_message(
    self,
    packet: Any,
    target: bytes = b"\x00" * 8,
    ack_required: bool = False,
    res_required: bool = True,
) -> bytes:
    """Create a message with auto-incrementing sequence.

    Args:
        packet: Packet dataclass instance
        target: Device serial number in bytes
        ack_required: Request acknowledgement
        res_required: Request response

    Returns:
        Complete message bytes
    """
    msg = create_message(
        packet=packet,
        source=self.source,
        target=target,
        sequence=self._sequence,
        ack_required=ack_required,
        res_required=res_required,
    )
    self._sequence = (self._sequence + 1) % 256
    return msg
```

##### next_sequence

```python
next_sequence() -> int
```

Get the next sequence number without incrementing.

| RETURNS | DESCRIPTION          |
| ------- | -------------------- |
| `int`   | Next sequence number |

Source code in `src/lifx/network/message.py`

```python
def next_sequence(self) -> int:
    """Get the next sequence number without incrementing.

    Returns:
        Next sequence number
    """
    return self._sequence
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

### DeviceConnection

```python
DeviceConnection(
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    source: int | None = None,
    max_retries: int = 3,
    timeout: float = 1.0,
)
```

Handle to a device connection (lightweight, user-facing).

This is a lightweight handle that internally uses a class-level connection pool. Multiple DeviceConnection instances with the same serial/ip/port will share the same underlying connection.

All connection management (pooling, opening, closing) is internal and completely hidden from Device classes.

Device classes just call

await self.connection.request(packet)

Example

```python
conn = DeviceConnection(serial="d073d5123456", ip="192.168.1.100")
state = await conn.request(packets.Light.GetColor())
# state.label is already decoded to string
# state.color is LightHsbk instance
```

This is lightweight - doesn't actually create a connection. Connection is created/retrieved from pool on first request().

| PARAMETER     | DESCRIPTION                                                                          |
| ------------- | ------------------------------------------------------------------------------------ |
| `serial`      | Device serial number as 12-digit hex string **TYPE:** `str`                          |
| `ip`          | Device IP address **TYPE:** `str`                                                    |
| `port`        | Device UDP port (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT` |
| `source`      | Client source identifier (random if None) **TYPE:** \`int                            |
| `max_retries` | Maximum retry attempts **TYPE:** `int` **DEFAULT:** `3`                              |
| `timeout`     | Overall timeout for requests in seconds **TYPE:** `float` **DEFAULT:** `1.0`         |

| METHOD                  | DESCRIPTION                                   |
| ----------------------- | --------------------------------------------- |
| `close_all_connections` | Close all connections in the shared pool.     |
| `get_pool_metrics`      | Get connection pool metrics.                  |
| `request`               | Send request and return unpacked response(s). |

Source code in `src/lifx/network/connection.py`

```python
def __init__(
    self,
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    source: int | None = None,
    max_retries: int = 3,
    timeout: float = 1.0,
) -> None:
    """Initialize connection handle.

    This is lightweight - doesn't actually create a connection.
    Connection is created/retrieved from pool on first request().

    Args:
        serial: Device serial number as 12-digit hex string
        ip: Device IP address
        port: Device UDP port (default LIFX_UDP_PORT)
        source: Client source identifier (random if None)
        max_retries: Maximum retry attempts
        timeout: Overall timeout for requests in seconds
    """
    self.serial = serial
    self.ip = ip
    self.port = port
    self.source = source
    self.max_retries = max_retries
    self.timeout = timeout
```

#### Functions

##### close_all_connections

```python
close_all_connections() -> None
```

Close all connections in the shared pool.

Call this at application shutdown for clean teardown.

Source code in `src/lifx/network/connection.py`

```python
@classmethod
async def close_all_connections(cls) -> None:
    """Close all connections in the shared pool.

    Call this at application shutdown for clean teardown.
    """
    async with cls._pool_lock:
        if cls._pool is not None:
            await cls._pool.close_all()
            cls._pool = None
```

##### get_pool_metrics

```python
get_pool_metrics() -> ConnectionPoolMetrics | None
```

Get connection pool metrics.

| RETURNS                 | DESCRIPTION |
| ----------------------- | ----------- |
| \`ConnectionPoolMetrics | None\`      |

Source code in `src/lifx/network/connection.py`

```python
@classmethod
def get_pool_metrics(cls) -> ConnectionPoolMetrics | None:
    """Get connection pool metrics.

    Returns:
        ConnectionPoolMetrics if pool exists, None otherwise
    """
    return cls._pool.metrics if cls._pool is not None else None
```

##### request

```python
request(
    packet: Any, timeout: float = 2.0, collect_multiple: bool = False
) -> Any
```

Send request and return unpacked response(s).

This method handles everything internally:

- Getting connection from pool (creates if needed)
- Opening connection if needed
- Sending request with proper ack/response flags
- Optionally collecting multiple responses if requested
- Unpacking response(s)
- Decoding label fields

Device classes just call this and get back the result.

By default, GET requests return immediately after the first response. Set collect_multiple=True for multi-response commands to wait 200ms.

| PARAMETER          | DESCRIPTION                                                                                   |
| ------------------ | --------------------------------------------------------------------------------------------- |
| `packet`           | Packet instance to send **TYPE:** `Any`                                                       |
| `timeout`          | Request timeout in seconds **TYPE:** `float` **DEFAULT:** `2.0`                               |
| `collect_multiple` | Whether to wait for multiple responses (default: False) **TYPE:** `bool` **DEFAULT:** `False` |

| RETURNS | DESCRIPTION                                                         |
| ------- | ------------------------------------------------------------------- |
| `Any`   | Single or multiple response packets (list if collect_multiple=True) |
| `Any`   | True for SET acknowledgement                                        |

| RAISES                        | DESCRIPTION                   |
| ----------------------------- | ----------------------------- |
| `LifxTimeoutError`            | If request times out          |
| `LifxProtocolError`           | If response invalid           |
| `LifxConnectionError`         | If connection fails           |
| `LifxUnsupportedCommandError` | If packet kind is unsupported |

Example

```python
# GET request returns unpacked packet
state = await conn.request(packets.Light.GetColor())
color = HSBK.from_protocol(state.color)
label = state.label  # Already decoded to string

# SET request returns True
success = await conn.request(
    packets.Light.SetColor(color=hsbk, duration=1000)
)

# Multi-response GET - collect multiple responses
states = await conn.request(
    packets.MultiZone.GetColorZones(...), collect_multiple=True
)
if isinstance(states, list):
    for state in states:
        # process each zone state
        pass
else:
    # single response
    pass
```

Source code in `src/lifx/network/connection.py`

````python
async def request(
    self, packet: Any, timeout: float = 2.0, collect_multiple: bool = False
) -> Any:
    """Send request and return unpacked response(s).

    This method handles everything internally:
    - Getting connection from pool (creates if needed)
    - Opening connection if needed
    - Sending request with proper ack/response flags
    - Optionally collecting multiple responses if requested
    - Unpacking response(s)
    - Decoding label fields

    Device classes just call this and get back the result.

    By default, GET requests return immediately after the first response.
    Set collect_multiple=True for multi-response commands to wait 200ms.

    Args:
        packet: Packet instance to send
        timeout: Request timeout in seconds
        collect_multiple: Whether to wait for multiple responses (default: False)

    Returns:
        Single or multiple response packets (list if collect_multiple=True)
        True for SET acknowledgement

    Raises:
        LifxTimeoutError: If request times out
        LifxProtocolError: If response invalid
        LifxConnectionError: If connection fails
        LifxUnsupportedCommandError: If packet kind is unsupported

    Example:
        ```python
        # GET request returns unpacked packet
        state = await conn.request(packets.Light.GetColor())
        color = HSBK.from_protocol(state.color)
        label = state.label  # Already decoded to string

        # SET request returns True
        success = await conn.request(
            packets.Light.SetColor(color=hsbk, duration=1000)
        )

        # Multi-response GET - collect multiple responses
        states = await conn.request(
            packets.MultiZone.GetColorZones(...), collect_multiple=True
        )
        if isinstance(states, list):
            for state in states:
                # process each zone state
                pass
        else:
            # single response
            pass
        ```
    """

    # Get pool and retrieve actual connection
    pool = await self._get_pool()
    actual_conn = await pool.get_connection(
        serial=self.serial,
        ip=self.ip,
        port=self.port,
        source=self.source,
        max_retries=self.max_retries,
        timeout=self.timeout,
    )

    # Get packet metadata
    packet_kind = getattr(packet, "_packet_kind", "OTHER")

    if packet_kind == "GET":
        # Request response(s) - with optional multi-response collection
        response = await actual_conn.request_response(
            packet, timeout=timeout, collect_multiple=collect_multiple
        )

        # Use PACKET_REGISTRY to find the appropriate packet class
        from lifx.protocol.packets import get_packet_class

        # Check if we got multiple responses or a single response
        if isinstance(response, list):
            # Multiple responses - unpack each one
            unpacked_responses = []
            for header, payload in response:
                packet_class = get_packet_class(header.pkt_type)
                if packet_class is None:
                    raise LifxProtocolError(
                        f"Unknown packet type {header.pkt_type} in response"
                    )

                # Unpack (labels are automatically decoded by Packet.unpack())
                response_packet = packet_class.unpack(payload)
                unpacked_responses.append(response_packet)

            # Log the full request/reply cycle (multiple responses)
            request_values = packet.as_dict
            reply_values_by_seq: dict[int, dict[str, Any]] = {}
            for i, (header, _) in enumerate(response, 1):
                resp_pkt = unpacked_responses[i - 1]
                reply_values_by_seq[header.sequence] = resp_pkt.as_dict

            _LOGGER.debug(
                {
                    "class": "DeviceConnection",
                    "method": "request",
                    "request": {
                        "packet": type(packet).__name__,
                        "values": request_values,
                    },
                    "reply": {
                        "packet": type(unpacked_responses[0]).__name__
                        if unpacked_responses
                        else "Unknown",
                        "expected": len(response),
                        "received": len(unpacked_responses),
                        "values": reply_values_by_seq,
                    },
                    "serial": self.serial,
                    "ip": self.ip,
                }
            )

            return unpacked_responses
        else:
            # Single response - response is tuple[LifxHeader, bytes]
            header, payload = response
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

            # Log the full request/reply cycle (single response)
            request_values = packet.as_dict
            reply_values = response_packet.as_dict
            _LOGGER.debug(
                {
                    "class": "DeviceConnection",
                    "method": "request",
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

            return response_packet

    elif packet_kind == "SET":
        # Request acknowledgement
        await actual_conn.request_ack(packet, timeout=timeout)

        # Log the full request/ack cycle
        request_values = packet.as_dict
        _LOGGER.debug(
            {
                "class": "DeviceConnection",
                "method": "request",
                "request": {
                    "packet": type(packet).__name__,
                    "values": request_values,
                },
                "reply": {
                    "packet": "Acknowledgement",
                    "values": {},
                },
                "serial": self.serial,
                "ip": self.ip,
            }
        )

        return True

    else:
        # Handle special cases
        if hasattr(packet, "PKT_TYPE"):
            pkt_type = packet.PKT_TYPE
            # EchoRequest/EchoResponse (58/59)
            if pkt_type == 58:  # EchoRequest
                from lifx.protocol.packets import Device

                response = await actual_conn.request_response(
                    packet, timeout=timeout, collect_multiple=False
                )
                if not isinstance(response, tuple):
                    raise LifxProtocolError(
                        "Expected single response tuple for EchoRequest"
                    )

                header, payload = response
                response_packet = Device.EchoResponse.unpack(payload)

                # Log the full request/reply cycle
                request_values = packet.as_dict
                reply_values = response_packet.as_dict
                _LOGGER.debug(
                    {
                        "class": "DeviceConnection",
                        "method": "request",
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

                return response_packet
            else:
                raise LifxUnsupportedCommandError(
                    f"Cannot auto-handle packet kind: {packet_kind}"
                )
        else:
            raise LifxProtocolError(
                f"Packet missing PKT_TYPE: {type(packet).__name__}"
            )
````

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

The library **intentionally does not implement rate limiting** to keep the core library simple. Applications should implement their own rate limiting if needed. According to the LIFX protocol specification, devices can handle approximately 20 messages per second.
