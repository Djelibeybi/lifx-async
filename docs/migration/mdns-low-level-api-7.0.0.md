# mDNS Low-Level API Removal (7.0.0)

Version 7.0.0 removes the public low-level mDNS record API. The supported mDNS
entry point now yields fully constructed devices and exposes connectivity through
`Device.connectivity`.

## Removed API

The following names are no longer public:

- `lifx.LifxServiceRecord`
- `lifx.discover_lifx_services()`
- `lifx.network.mdns.create_device_from_record()`

Their replacements inside the mDNS implementation are private and are not
compatibility APIs. Code should not import their underscore-prefixed equivalents.
The canonical implementation now lives below `lifx.network.discovery.mdns`;
`lifx.network.mdns` retains only the supported public compatibility re-exports.

## Migration

Replace raw service-record iteration and manual conversion with `discover_mdns()`:

```python
from lifx import discover_mdns


async def discover_devices():
    async for device in discover_mdns(timeout=5.0):
        async with device:
            print(device.serial, device.ip, device.connectivity)
```

`Device.connectivity` returns a `Connectivity` enum member. Discovery reports
`Connectivity.THREAD` only on an exact positive Thread report and
`Connectivity.WIFI` otherwise; the device's own frame address report supersedes
that once it has answered a request. Alternative advertised addresses, raw DNS
records and the private connectivity field are intentionally not exposed.

An IPv6 link-local address also needs a zone ID identifying its network interface,
which a DNS AAAA record cannot carry. If an mDNS responder supplies no usable IPv4,
ULA or GUA address, use `discover()` as the compatibility fallback.
