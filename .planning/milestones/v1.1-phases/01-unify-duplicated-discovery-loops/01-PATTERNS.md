# Phase 1: Unify Duplicated Discovery Loops - Pattern Map

**Mapped:** 2026-06-13
**Files analysed:** 6 (4 source, 2 test)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/lifx/network/utils.py` | utility | — | `src/lifx/network/utils.py` (existing `allocate_source`) | exact (same file, new class) |
| `src/lifx/network/discovery.py` | service | streaming / event-driven | self (rebuild internal structure) | exact |
| `src/lifx/network/mdns/discovery.py` | service | streaming / event-driven | `src/lifx/network/discovery.py` `_discover_with_packet` loop | role-match |
| `src/lifx/network/transport.py` | transport | request-response | self (add `warnings.warn` to existing method) | exact |
| `tests/test_network/test_utils.py` | test | — | `tests/test_network/test_discovery_errors.py` unit tests | role-match |
| `tests/test_network/test_discovery_errors.py` | test | — | self (rewrite/extend existing tests) | exact |

---

## Pattern Assignments

### `src/lifx/network/utils.py` — add `IdleDeadline` class

**Analog:** existing `allocate_source` function in the same file (lines 1–15)

**Existing file structure** (`src/lifx/network/utils.py`, lines 1–15):
```python
"""Network utilities for LIFX protocol communication."""

import secrets


def allocate_source() -> int:
    """Allocate unique source identifier for a LIFX protocol request.

    LIFX protocol defines source as Uint32, with 0 and 1 reserved.
    We generate values in range [2, 0xFFFFFFFF].

    Returns:
        Unique source identifier (range: 2 to 4294967295)
    """
    return secrets.randbelow(0xFFFFFFFF - 1) + 2
```

**Pattern to follow — module header and import style:**
- Module docstring on line 1.
- Stdlib imports only (this file must stay zero-dependency).
- `import time` is the only new import needed.

**Pattern to follow — timeout arithmetic from `_discover_with_packet`** (`src/lifx/network/discovery.py`, lines 231–259):
```python
idle_timeout = max_response_time * idle_timeout_multiplier
last_response_time = request_time

while True:
    elapsed_since_last = time.monotonic() - last_response_time

    if elapsed_since_last >= idle_timeout:
        break   # idle timeout

    if time.monotonic() - request_time >= timeout:
        break   # overall timeout

    remaining_idle = idle_timeout - elapsed_since_last
    remaining_overall = timeout - (time.monotonic() - request_time)
    remaining = min(remaining_idle, remaining_overall)
```

`IdleDeadline` encapsulates exactly this pattern. Use `time.monotonic()` throughout (never `time.time()`). Expose `remaining() -> float`, `mark_response()`, and optionally `idle_expired` / `overall_expired` boolean properties for distinct timeout-type log messages (mirrors existing per-type log entries at lines 238–255).

---

### `src/lifx/network/discovery.py` — hoist validation/dedup, thin `discover_devices`, delete `_parse_device_state_service`

**Analog:** self — the file is being restructured. Both surviving functions are in the same file.

**Imports pattern to preserve** (lines 1–32):
```python
"""Device discovery for LIFX network."""

from __future__ import annotations

import logging
import struct          # DELETE when _parse_device_state_service is removed (Pitfall 6)
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_TIMEOUT,
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_UDP_PORT,
    MAX_RESPONSE_TIME,
)
from lifx.exceptions import LifxProtocolError, LifxTimeoutError
from lifx.network.message import create_message, parse_message
from lifx.network.transport import UdpTransport
from lifx.network.utils import allocate_source
from lifx.protocol.base import Packet
from lifx.protocol.models import Serial
from lifx.protocol.packets import Device as DevicePackets
from lifx.protocol.packets import get_packet_class
```
Add `from lifx.network.utils import IdleDeadline` alongside `allocate_source`. Remove `import struct`.

**Serial validation pattern to hoist into `_discover_with_packet`** (currently at `discover_devices`, lines 558–566):
```python
# Validate serial is not multicast/broadcast (D-01, change WARNING → DEBUG per D-02)
if header.target[0] & 0x01 or header.target == b"\xff" * 8:
    _LOGGER.debug(
        {
            "class": "_discover_with_packet",
            "action": "invalid_serial",
            "serial": header.target.hex(),
            "source_ip": addr[0],
        }
    )
    continue
```
Place this check after source validation and pkt_type check (lines 271–284), before serial extraction. The `class` key must match the function name (`_discover_with_packet`).

**Dedup pattern to hoist into `_discover_with_packet`** (currently at `discover_devices`, lines 578–579):
```python
seen_serials: set[str] = set()
# ... inside loop, after serial extraction and BEFORE yield:
if device_serial in seen_serials:
    continue
seen_serials.add(device_serial)
```
The `responses` dict (lines 201, 322) is vestigial — **delete** it when introducing `seen_serials`.

**Idle timer reset semantics (Pitfall 1):** Reset `deadline.mark_response()` on every valid protocol response (valid source, valid pkt_type, valid serial — even duplicates), _before_ the dedup `continue`. This preserves the existing behaviour where a device flooding duplicates does not cause premature idle expiry.

**`LifxProtocolError` handling alignment** (align `discover_devices` pattern at lines 608–620 with `_discover_with_packet` at lines 335–344 — use `exc_info=True`):
```python
except LifxProtocolError as e:
    _LOGGER.warning(
        {
            "class": "_discover_with_packet",
            "action": "malformed_response",
            "reason": str(e),
            "source_ip": addr[0],
        },
        exc_info=True,
    )
    continue
```

**Thin `discover_devices` wrapper pattern** (replaces lines 392–645):
```python
async def discover_devices(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[DiscoveredDevice, None]:
    async for resp in _discover_with_packet(
        DevicePackets.GetService(),
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    ):
        device_port: int = resp.response_payload["port"]  # from StateService, NOT resp.port
        yield DiscoveredDevice(
            serial=resp.serial,
            ip=resp.ip,
            port=device_port,
            response_time=resp.response_time,
            timeout=device_timeout,
            max_retries=max_retries,
        )
```
Note: `resp.port` is the broadcast port parameter; `resp.response_payload["port"]` is the device's actual UDP service port (Pitfall 2). Key is lowercase `"port"` (Pitfall 4).

**Structured log style** (copy from lines 218–228, 325–333):
```python
_LOGGER.debug(
    {
        "class": "_discover_with_packet",
        "method": "discover",
        "action": "broadcast_sent",
        "broadcast_address": broadcast_address,
        "port": port,
        "packet_type": type(packet).__name__,
        "expected_response": expected_response_type,
    }
)
```
All log entries are dicts with `"class"` and `"action"` keys. `"method"` is optional. No f-strings in log calls.

---

### `src/lifx/network/mdns/discovery.py` — adopt `IdleDeadline`, tighten exception handling

**Analog:** `src/lifx/network/discovery.py` `_discover_with_packet` loop (lines 231–265) — identical timeout arithmetic pattern.

**Current mDNS timeout loop** (`src/lifx/network/mdns/discovery.py`, lines 224–277):
```python
idle_timeout = max_response_time * idle_timeout_multiplier
last_response_time = request_time

while True:
    elapsed_since_last = time.monotonic() - last_response_time

    if elapsed_since_last >= idle_timeout:
        _LOGGER.debug({
            "class": "discover_lifx_services",
            "method": "discover",
            "action": "idle_timeout",
            "idle_time": elapsed_since_last,
            "idle_timeout": idle_timeout,
        })
        break

    if time.monotonic() - request_time >= timeout:
        _LOGGER.debug({
            "class": "discover_lifx_services",
            "method": "discover",
            "action": "overall_timeout",
            "elapsed": time.monotonic() - request_time,
            "timeout": timeout,
        })
        break

    remaining_idle = idle_timeout - elapsed_since_last
    remaining_overall = timeout - (time.monotonic() - request_time)
    remaining = min(remaining_idle, remaining_overall)

    try:
        data, addr = await transport.receive(timeout=remaining)
        response_timestamp = time.monotonic()

    except Exception:            # ← bare catch — must be tightened (D-08, Pitfall 5)
        _LOGGER.debug({
            "class": "discover_lifx_services",
            "method": "discover",
            "action": "no_responses",
        })
        break
```

**Tightened exception pattern to use** (D-08):
```python
except LifxTimeoutError:
    break                   # clean idle/overall expiry — stop collecting
except LifxNetworkError as e:
    _LOGGER.warning(
        {
            "class": "discover_lifx_services",
            "action": "network_error",
            "error": str(e),
        }
    )
    break                   # log and stop; callers do not handle LifxNetworkError today
except Exception as e:
    _LOGGER.error(
        {
            "class": "discover_lifx_services",
            "action": "unexpected_error",
            "error": str(e),
        },
        exc_info=True,
    )
    raise                   # unexpected — propagate
```
`LifxNetworkError` and `LifxTimeoutError` are already imported in `src/lifx/exceptions.py`. Add them to the mDNS discovery import block alongside any existing exception imports.

Replace the inline timeout arithmetic with `IdleDeadline` (import from `lifx.network.utils`). Preserve the distinct idle/overall log messages by checking `deadline.idle_expired` / `deadline.overall_expired` properties (if exposed) or by inspecting `remaining()` after the loop.

---

### `src/lifx/network/transport.py` — deprecate `receive_many`

**Analog:** No existing `warnings.warn` usage in the codebase. Pattern comes from stdlib.

**Existing `receive_many` signature and body start** (lines 282–333):
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
    ...
```

**Deprecation pattern to apply** (D-09):
```python
import warnings  # add to top-of-file imports

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

    .. deprecated:: current
        :meth:`receive_many` is deprecated and will be removed in v2.0.
        Use :meth:`receive` in a loop or
        :func:`~lifx.network.discovery._discover_with_packet` for
        multi-response collection.
    """
    warnings.warn(
        "UdpTransport.receive_many is deprecated and will be removed in v2.0. "
        "Use receive() in a loop or _discover_with_packet() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # rest of body unchanged
    if self._protocol is None:
        raise LifxNetworkError("Socket not open")
    ...
```
`stacklevel=2` ensures the warning points to the caller, not to `receive_many` itself. Method body is otherwise untouched.

---

### `tests/test_network/test_utils.py` — new `IdleDeadline` unit tests

**Analog:** `tests/test_network/test_discovery_errors.py` unit test class structure (no emulator, pure unit).

**Test class and fixture pattern** (`tests/test_network/test_discovery_errors.py`, lines 1–17, 83–128):
```python
"""Tests for discovery error paths and DoS protection mechanisms."""

from __future__ import annotations

import pytest


class TestDiscoveryWithEmulatorErrors:
    """Test discovery with various error scenarios."""

    @pytest.mark.asyncio
    async def test_discovery_timeout_scenario(self) -> None:
        """Test discovery with no responding devices."""
        count = 0
        async for disc in discover_devices(
            timeout=0.1,
            broadcast_address="255.255.255.255",
            port=65432,
        ):
            count += 1
        assert count == 0
```

No emulator dependency for `IdleDeadline` tests — these are pure synchronous unit tests. Use `time.sleep()` sparingly (or `unittest.mock.patch("time.monotonic")`) to avoid slow tests. Mock `time.monotonic` for deterministic assertions rather than sleeping.

**File header pattern:**
```python
"""Tests for IdleDeadline utility class."""

from __future__ import annotations

import pytest

from lifx.network.utils import IdleDeadline
```

---

### `tests/test_network/test_discovery_errors.py` — rewrite/extend

**Analog:** self — existing file structure is the pattern. Portions deleted, new tests added in same style.

**Mock transport pattern** (lines 186–199 — the canonical pattern for patching `UdpTransport`):
```python
with (
    patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
    patch("lifx.network.discovery.allocate_source", return_value=known_source),
):
    mock_transport = AsyncMock()
    mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
    mock_transport.__aexit__ = AsyncMock(return_value=False)
    mock_transport.send = AsyncMock()
    mock_transport.receive = mock_receive
    mock_transport_cls.return_value = mock_transport

    devices = []
    async for device in discover_devices(timeout=0.5):
        devices.append(device)
```

**Mock receive helper pattern** (lines 176–184):
```python
async def mock_receive(timeout: float = 2.0):
    nonlocal call_count
    call_count += 1
    if call_count == 1:
        return crafted_packet, ("192.168.1.100", 56700)
    # Subsequent calls timeout to end discovery
    from lifx.exceptions import LifxTimeoutError
    raise LifxTimeoutError("timeout")
```

**Packet builder helper** (lines 131–155 — reusable for new tests):
```python
def _build_state_service_packet(source: int, target: bytes, port: int = 56700) -> bytes:
    payload = struct.pack("<BI", 1, port)
    header = LifxHeader.create(
        pkt_type=3,  # StateService
        source=source,
        target=target,
        tagged=False,
        ack_required=False,
        res_required=False,
        sequence=0,
        payload_size=len(payload),
    )
    return header.pack() + payload
```
This builder is reusable for new `_discover_with_packet`-level serial validation tests (D-11). The new tests patch `UdpTransport` at the `_discover_with_packet` path (same patch target: `"lifx.network.discovery.UdpTransport"`).

**Emulator test pattern** (lines 52–76, 290–305):
```python
@pytest.mark.emulator
@pytest.mark.flaky(retries=2, delay=1, condition=sys.platform.startswith("win32"))
class TestDiscoveryDeduplication:
    @pytest.mark.asyncio
    async def test_devices_deduplicated_by_serial(self, emulator_port: int) -> None:
        seen_serials: set[str] = set()
        async for disc in discover_devices(
            timeout=1.5,
            broadcast_address="127.0.0.1",
            port=emulator_port,
        ):
            assert disc.serial not in seen_serials, f"Duplicate serial: {disc.serial}"
            seen_serials.add(disc.serial)
```
`emulator_port` fixture comes from `tests/conftest.py`. `@pytest.mark.flaky` is applied to `@pytest.mark.emulator` classes on Windows CI.

**`pytest.warns` pattern for D-12** (add to `tests/test_network/test_transport.py`):
```python
async def test_receive_many_emits_deprecation_warning(self) -> None:
    """receive_many must emit DeprecationWarning (D-12)."""
    async with UdpTransport() as transport:
        with pytest.warns(DeprecationWarning, match="v2.0"):
            await transport.receive_many(timeout=0.1)
```

---

## Shared Patterns

### Structured dict-style logging
**Source:** `src/lifx/network/discovery.py` lines 218–228, 325–333, 335–354
**Apply to:** All new/modified log calls in `discovery.py`, `mdns/discovery.py`, `transport.py`
```python
_LOGGER.debug(
    {
        "class": "<function_or_class_name>",
        "action": "<snake_case_action>",
        # optional keys: "serial", "ip", "source_ip", "elapsed", "error", ...
    }
)
_LOGGER.warning(
    {
        "class": "...",
        "action": "...",
        "reason": str(e),
        "source_ip": addr[0],
    },
    exc_info=True,       # always True for WARNING and ERROR
)
```

### `time.monotonic()` for all interval arithmetic
**Source:** `src/lifx/network/discovery.py` lines 202, 217, 235, 247, 263
**Apply to:** `IdleDeadline.__init__`, `IdleDeadline.remaining`, `IdleDeadline.mark_response`
Never use `time.time()` — the mDNS loop previously used it and was corrected in commit `2f6404a`.

### Async-generator type annotation
**Source:** `src/lifx/network/discovery.py` lines 150–157
```python
async def _discover_with_packet(
    packet: Packet,
    timeout: float = DISCOVERY_TIMEOUT,
    ...
) -> AsyncGenerator[DiscoveryResponse]:
```
Return type is `AsyncGenerator[YieldType]` (single type arg, not two). Pyright strict mode requires this annotation.

### `AsyncMock` + `patch` for transport mocking
**Source:** `tests/test_network/test_discovery_errors.py` lines 186–199
**Apply to:** All new unit tests that exercise `_discover_with_packet` with crafted packets.

---

## No Analog Found

None. All files to be created or modified have close analogs in the codebase.

---

## Metadata

**Analog search scope:** `src/lifx/network/`, `tests/test_network/`
**Files read:** 7 (`utils.py`, `discovery.py`, `transport.py`, `mdns/discovery.py` partial, `tests/test_discovery_errors.py`, `tests/test_transport.py` partial, `tests/conftest.py` partial)
**Pattern extraction date:** 2026-06-13
