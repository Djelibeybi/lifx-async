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
Large-mesh packet assembly and follow-up behaviour are covered by deterministic
multi-packet tests: **mesh scale is proven synthetically**, not against a
current physical fleet at that scale.

These four properties combine into one practical rule: merged `discover()`
visibility and single-source `discover_mdns()` visibility are not the same
fact. A device absent from a `discover_mdns()` result may still answer
`discover()` (or `discover_udp()`) a moment later, because the two legs observe
different traffic. A bounded discovery timeout that finds nothing is evidence
of silence during that window, not proof of absence — treat a short or
censored discovery call as inconclusive, not as a negative result, especially
under load or on a congested network.

Phase 14 physical observations of Thread/mDNS behaviour, where referenced in
this documentation set, describe the specific fleet measured at that time.
They are fleet-specific findings, not universal benchmarks that generalise to
every network or every LIFX firmware revision — treat them as one data point,
not a performance guarantee.

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
