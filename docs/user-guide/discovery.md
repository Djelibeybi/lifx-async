# Discovery

This is the canonical guide to finding LIFX devices with lifx-async. It covers the
unchanged `discover()` migration path, explicit source control with `discover_udp()`
and `discover_mdns()`, targeted lookup by address (including IPv6), how to choose
between them, their limitations, and troubleshooting.

Every code sample below is included directly from
[`examples/discovery_progressive.py`](https://github.com/Djelibeybi/lifx-async/blob/main/examples/discovery_progressive.py) —
one executable file, so the guide and the code can never drift apart.

## An unchanged `discover()` migration

`discover()` still works exactly as before: it broadcasts a discovery request over
UDP and yields devices as they respond. Existing callers need to change nothing.

```python
--8<-- "examples/discovery_progressive.py:merged"
```

What changed under the hood is that `discover()` now also merges verified mDNS
results into the same stream under one caller deadline, so a device that answers
only over mDNS (for example, a Thread device reachable through a border router)
can still be found without any code change. Both legs share one caller-origin
deadline, so `timeout` still bounds the whole call.

The underlying UDP leg sends one initial broadcast, then schedules re-broadcasts
0.6, 1.8, 3.6, 5.6 and 7.6 seconds later; the five-second default schedules the
first three. These offsets are fixed constants, so they are not scaled to the
requested discovery timeout. A due re-broadcast is sent only while discovery
remains active — later sends do not occur after the overall or idle deadline,
when the caller closes or cancels the generator, or when a transport failure
aborts the sweep. A valid response resets the four-second idle window; it does
not extend the overall timeout.

Every yielded device exposes `connectivity` as a `Connectivity` enum member
(`Connectivity.WIFI` or `Connectivity.THREAD`), describing how the device
currently reaches the network. It does not authenticate the device or change
routing or retry behaviour.

## Taking explicit control: `discover_udp()` and `discover_mdns()`

When a caller wants only one source instead of the merged stream, both legs are
available explicitly. `discover_udp()` is the explicit name for the same UDP
broadcast leg `discover()` shares — compatible overlapping calls to `discover()`
and `discover_udp()` share one active validated wire sweep process-wide, so
running both concurrently does not duplicate broadcast traffic.

```python
--8<-- "examples/discovery_progressive.py:explicit-udp"
```

`discover_mdns()` is an explicit, bounded legacy-unicast DNS-SD alternative.
Device type metadata arrives in the DNS-SD response itself, avoiding a separate
LIFX product query for every device. It sends an initial DNS-SD PTR service
query and may retransmit that PTR query once at one second and once at three
seconds within the caller's deadline, assembling valid legacy-unicast replies
during the quiet window. When a valid SRV target still lacks a usable address,
it conditionally sends bounded A/AAAA follow-ups: one successful send, or no
more than two failed attempts, for each of at most 64 targets.

```python
--8<-- "examples/discovery_progressive.py:explicit-mdns"
```

An empty `discover_mdns()` result does not prove a device is offline — it only
proves that device did not answer this specific DNS-SD query during the call.
Use `discover()` as the compatibility fallback whenever a caller needs a
stronger liveness signal than mDNS alone can give.

## Targeted lookup and IPv6

When the device address is already known, skip discovery entirely with
`find_by_ip()`. It sends the discovery request directly to that IPv4 or IPv6
literal and returns the responding device — more efficient than broadcasting to
every device and filtering the result.

```python
--8<-- "examples/discovery_progressive.py:targeted"
```

A link-local IPv6 address needs a zone ID identifying its network interface
(for example `"fe80::1%en0"`), but a DNS AAAA record cannot carry that ID. An
mDNS response containing only an unscoped link-local AAAA address therefore
cannot produce a usable device route; targeted `find_by_ip()` with an explicit
zone, or `discover()`, are the working alternatives on such networks.

The address is validated before a socket is opened. Invalid literals,
IPv4-mapped IPv6 literals, wildcard addresses and link-local IPv6 addresses
without a zone ID raise `ValueError` immediately. A named zone the host cannot
resolve, or a transport failure, raises `LifxNetworkError`.

If the address is not known either, `find_by_serial()` and `find_by_label()`
provide the other two targeted lookups — by serial number and by device
label/name respectively. See the [High-Level API reference](../api/high-level.md)
for their full signatures.

## When a device moves

A device can come back on a different IP address or port after a router
restart, a DHCP change or a move between access points. Its serial does not
change, so the library follows the serial: the device object you already hold
keeps working and nothing you cached on it is thrown away.

Pass the objects you hold to discovery with `known_devices` (or `device` for
`find_by_serial()`). When a result reports one of those serials at a different
address, that object is moved to the new address and yielded in place of a new
object:

```python
from lifx import Light, discover_udp

lights: list[Light] = [...]  # objects you created or discovered earlier

async for device in discover_udp(known_devices=lights):
    print(device.serial, device.ip, device.port)  # same objects, current address
```

`discover()`, `discover_udp()`, `discover_mdns()` and `find_by_serial()` all
accept it. If you learn the new address some other way, apply it yourself:

```python
light.update_address("192.0.2.40", 56700)
```

What a move does:

- `device.ip` and `device.port` report the new address.
- A request that was in flight is not failed. Its next retransmission goes to
  the new address, so it completes there.
- A late reply from an address the connection has left is ignored (logged at
  debug level), so it cannot be mistaken for an answer from the device. Only
  endpoints the connection has moved away from are filtered: a connection that
  never moved still accepts a reply by source, sequence and serial alone, as
  before.
- The cached label, firmware, group, location, product capabilities and the
  device's own `connectivity` report are kept. Nothing is re-read.
- No color, power or restore write is ever sent. A move only changes where
  packets go.
- The light's Animator, and any software effect running through it, sends its
  next frame to the new address. Probes still awaiting an ack from the old
  address no longer gate it.
- Announcing the address a device already has changes nothing. A change of IPv6
  zone counts as a move.

`Device.update_address()` returns `True` when the address changed and `False`
when it was already current. It raises `ValueError` for an address or port the
library cannot use, and leaves the device unchanged.

Discovery is unauthenticated UDP, so the library does not arbitrate between
conflicting announcements: a second host that claims a serial can move the
object. Use `device.connection.address_epoch`, which counts moves, if you need
to tell that one happened.

## Watching devices continuously

`discover()` answers "what is on the network now". To keep an application in
step with the network over hours, open a `DeviceWatcher`. It hands you one
device object per serial, keeps those objects current, and tells you when a
device appears, changes or goes quiet.

```python
from lifx import DeviceEventType, DeviceWatcher

async with DeviceWatcher() as watcher:
    # The initial discovery has finished; watcher.devices is populated.
    async for event in watcher:
        if event.type is DeviceEventType.UPDATED:
            print(event.serial, dict(event.changes))
```

On entry the watcher runs one discovery. After that it sweeps every
`sweep_interval` seconds (default 30) through the same process-wide sweep
coordinator `discover()` uses, so several consumers do not multiply broadcast
traffic. Pass `mdns=True` to add an mDNS leg for Thread and IPv6 devices.
`await watcher.sweep()` forces a sweep now.

### Events

| Event | Meaning |
|-------|---------|
| `ADDED` | A serial was seen for the first time, or answered again after `REMOVED` |
| `UPDATED` | A tracked field changed |
| `REMOVED` | The device has been silent for longer than the threshold |

`event.device` is always the same object for a serial, and `watcher.get(serial)`
and `watcher.devices` return it too. `UPDATED` carries `event.changes`, a
mapping from each changed field (`address`, `label`, `group`, `location`,
`host_firmware`, `wifi_firmware`) to its `(old, new)` values. A device that
restarts on a new address produces one `UPDATED` with an `address` change,
through [endpoint migration](#when-a-device-moves), not a `REMOVED` followed by
an `ADDED`. Label, group, location and firmware are reported when the cached
values on the device object change, for example after you call `get_label()`.

Read events with `async for event in watcher`, or register callbacks:

```python
remove = watcher.add_listener(lambda event: print(event.type, event.serial))
```

Callbacks run inside the sweep, see every event in order, and a callback that
raises is logged without affecting the others. The iterator reads from a queue
of `max_queue_size` events (default 256). When it is full the oldest event is
dropped and `watcher.dropped_events` increases; a slow consumer never delays a
sweep.

### Liveness

A device is silent when it has answered nothing, neither a discovery reply nor
any request on its connection, for longer than `silence_threshold`. The default
is the larger of 30 seconds and five sweep intervals. Silence is measured from
the connection's `last_response_at`, so a device you are talking to is never
removed while it answers, even if sweeps miss it. A silent device's object is
kept. When it answers again `ADDED` is emitted for the same object.

Only a correlated response counts as an answer. A UDP discovery reply is one. An
mDNS advertisement is not: a Thread border router keeps advertising a device
after it stops responding (see [Limitations](#limitations)), so the watcher's
mDNS leg sends each advertised endpoint one bounded read-only request and
treats the device as seen only when it answers. An advertisement that never
answers is never added, and a tracked device whose advertisements continue but
whose requests all fail is removed at the silence threshold like any other.

### State polling

By default the watcher sends nothing but discovery traffic. Two optional polls
keep device state fresh without a loop of your own. Each has its own flag and
interval, and both are off by default.

```python
async with DeviceWatcher(
    high_frequency_polling=True,    # color and power, plus zones or tiles
    high_frequency_interval=10.0,   # seconds, the default
    low_frequency_polling=True,     # label, firmware, group, location
    low_frequency_interval=300.0,   # seconds, the default
) as watcher:
    async for event in watcher:
        ...
```

| Flag | Reads | Reported field names |
|------|-------|----------------------|
| `high_frequency_polling` | color and power; zones on a multizone light; tiles on a matrix light | `color`, `power`, `zones`, `tiles` |
| `low_frequency_polling` | label, host firmware, wifi firmware, group, location | `label`, `host_firmware`, `wifi_firmware`, `group`, `location` |

A poll refreshes the device's cached state and any difference from the previous
reading is an `UPDATED` event whose `changes` names the fields. The first
reading of a field is a baseline and is not reported. Polls run on their own
timers, so an interval shorter than `sweep_interval` is honored. A device that
is silent is not polled.

A device evidenced as Thread gets no high-frequency polling, because a Thread
mesh is not built for that traffic. Pass `enable_thread=True`, the same opt-in
the software effect path uses, to poll it anyway. Low-frequency polling still
reads a Thread device, except for wifi firmware, which Thread firmware cannot
answer.

A poll that fails is logged. It does not stop the polls of other devices and
does not by itself mark the device silent; only the silence threshold does
that. Polling only reads.

The watcher listens, discovers and, when asked, polls. It never writes color or
power, and it closes no device object: leaving the `async with` block stops the
sweeps and polls and leaves the devices you hold open for you.

## Choosing a discovery method

| Scenario | Recommended method |
|----------|---------------------|
| General use, existing code | `discover()` (unchanged) |
| Only the UDP broadcast leg, no mDNS | `discover_udp()` |
| Device type metadata without an extra query | `discover_mdns()`, with `discover()` fallback |
| Known device address (fastest) | `find_by_ip()` |
| Known label or serial | `find_by_label()` or `find_by_serial()` |
| Cross-subnet, with an mDNS reflector | `discover_mdns()`, with `discover()` fallback |
| Maximum compatibility | `discover()` |

## Limitations

`discover_mdns()` uses DNS-SD to find devices with an IPv4 multicast query,
sent from an **ephemeral source port**, and accepts **legacy-unicast replies**
addressed directly to that socket. The socket **does not join the multicast
group** and **does not receive unsolicited announcements**, so each call
observes only direct traffic delivered to its per-call socket during the sweep
and does not reuse DNS cache state from an earlier call. Discovery **does not
authenticate or correlate responders** with its outstanding queries.

These properties combine into one practical rule: merged `discover()`
visibility and single-source `discover_mdns()` visibility are not the same
fact. A device absent from a `discover_mdns()` result may still answer
`discover()` (or `discover_udp()`) a moment later, because the two legs observe
different traffic. A bounded discovery timeout that finds nothing is evidence
of silence during that window, not proof of absence — treat a short or
censored discovery call as inconclusive, not as a negative result, especially
under load or on a congested network.

A Thread border router advertises every device on its mesh over mDNS,
whether or not each advertised device is currently reachable. An mDNS
result therefore proves an advertisement exists, not that the advertised
device is currently reachable. The next action is to confirm it with a
request, or to use `discover()`, whose mDNS candidates must answer a
correlated device request before they are yielded.

Because a border router keeps advertising a device whose power is gone,
`discover_mdns()` may yield a device whose advertisement has outlived it,
for as long as that advertisement lingers. On the fleet measured for this
project, a Thread advertisement outlived its device's power by between 4140
and 4200 seconds, an interval bounded by a sixty-second measurement cadence
rather than a point value. On the same fleet, a WiFi advertisement, which
has no border router sustaining it, was confirmed gone at most 80.8548
seconds after power loss, the measured completion time of the first poll
rather than a point observed inside that window.

Both `discover()` and `find_by_serial()` instead verify an mDNS candidate
with a correlated request before yielding it, so neither can hand back a
device built from a stale advertisement; but that verification is a
point-in-time observation and not a continuing reachability guarantee,
because the device may go away immediately afterwards.

A device can remain undiscoverable for tens of seconds after power returns,
by any discovery method. On the fleet measured for this project, a Thread
device took 69.4 seconds from the power-on edge to answering both discovery
legs again, and a WiFi device took 14.6 seconds. These are single-trial
observations of this fleet, one trial per link type, and are not a
guarantee, a lease value, a universal limit, or a value to size a timeout
from.

Behaviour on a large or congested network is not characterised by this
documentation. Any physical observations of Thread/mDNS behaviour, where
referenced in this documentation set, describe the specific fleet measured
at that time, not a universal benchmark or a performance guarantee for
every network or every LIFX firmware revision. Do not size timeouts or
retry policy from this documentation; measure them against your own
network instead.

## Troubleshooting

**No devices found with `discover()` or `discover_udp()`:** confirm the device
is powered on and on the same network, check that UDP port 56700 is not
blocked by a firewall, and try a network-specific `broadcast_address` if the
default `255.255.255.255` does not reach the target subnet.

**No devices found with `discover_mdns()`:** the network or device may not
expose the required DNS-SD service records — use `discover()` as the
compatibility fallback rather than retrying `discover_mdns()` repeatedly.

**`ValueError` from `find_by_ip()` with a link-local IPv6 address:** add the
interface zone ID, for example `"fe80::1%en0"` on macOS or `"fe80::1%eth0"` on
Linux.

**`LifxNetworkError` from a named IPv6 zone:** the host could not resolve that
zone name to an interface index — check the interface name with your OS's
network tooling.

See the full [Troubleshooting Guide](troubleshooting.md) for connection,
timeout and performance issues beyond discovery.

## Next Steps

- [Advanced Usage](advanced-usage.md) — state caching, connection management and concurrency patterns
- [Network Layer API](../api/network.md) — low-level discovery, connection and transport reference
- [High-Level API](../api/high-level.md) — `discover()`, `discover_udp()`, `discover_mdns()` and targeted lookup reference
- [Troubleshooting Guide](troubleshooting.md) — common issues and solutions
