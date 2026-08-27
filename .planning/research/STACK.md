# Stack Research

**Domain:** Thread/IPv6 device support in a zero-dependency async Python LIFX library
**Researched:** 2026-08-27
**Confidence:** HIGH (core claims verified empirically this session on macOS Darwin 25 / CPython 3.14.2 and Linux / CPython 3.10.21 in a `python:3.10-slim` container, and against local CPython 3.14 asyncio source)

The stack for this milestone is the Python standard library and nothing else. This document
therefore recommends *stdlib APIs*, not packages, states where the stdlib fails and hand-rolling
is required, and assesses whether the existing branch (`feat/ipv6-thread-support`, commits
`b49400b`, `b88cdb9`, `2f884f5`) uses the right primitives. Verdict up front: **the branch uses
the correct stdlib primitives everywhere it matters.** The findings below fill in the
version/platform caveats the roadmap needs, plus a small number of hardening opportunities.

## Recommended Stack

### Core stdlib APIs

| Problem | API | Why it is the right one |
|---------|-----|-------------------------|
| IPv6 datagram endpoints | `loop.create_datagram_endpoint(family=AF_INET6, local_addr=("::", 0))` | Family pinned explicitly; asyncio resolves numeric literals without DNS via its `_ipaddr_info` fast path (CPython `asyncio/base_events.py`) |
| Family selection from a literal | `ipaddress.ip_address()` at validation boundaries; `":" in host` in hot paths | `ipaddress` accepts zone IDs on every platform since 3.9; `socket.inet_pton` does not (glibc rejects `%zone`, Apple libc accepts it, verified) |
| Link-local classification | `IPv6Address.is_link_local`, `.scope_id` | fe80::/10 test and zone extraction in one parse; unaffected by the CVE-2024-4032 reclassification |
| ULA classification | `addr in ipaddress.ip_network("fc00::/7")` | There is no `is_unique_local` property; the containment test is exact per RFC 4193 |
| IPv6 multicast join | `setsockopt(IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)` with `mreq = inet_pton(AF_INET6, group) + struct.pack("@I", ifindex)` | `IPV6_JOIN_GROUP` is the only constant CPython exposes on both macOS and Linux (`IPV6_ADD_MEMBERSHIP` is absent on both, verified) |
| Interface index resolution | `socket.if_nametoindex()`, `socket.if_nameindex()` | Available on all POSIX platforms across 3.10 to 3.14, no change in range |
| mDNS reply capture | Ephemeral-port bind `sock.bind(("", 0))`, no group membership | RFC 6762 §6.7 requires responders to unicast replies to a non-5353 source port, so the reply arrives on a socket no daemon shares |
| IPv6 loopback testing | `create_datagram_endpoint(local_addr=("::1", 0))` + direct `datagram_received()` injection | Works on macOS, Linux, GitHub Actions runners, and inside Docker containers with no IPv6 networking (verified: `::1` binds in `python:3.10-slim`) |

### Development tools (already present, no additions)

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest + pytest-asyncio (dev deps) | async test harness | Dev dependencies are outside the zero-dependency constraint; nothing new needed |
| lifx-emulator-core (dev dep) | in-process protocol emulator | IPv4-only today; IPv6 paths are tested with the loopback/injection techniques in §5 below |

## 1. Dual-stack and address-family selection

### `create_datagram_endpoint()` semantics

- With `local_addr`/`remote_addr` and no `family`, asyncio infers the family by resolving the
  address through `BaseEventLoop._ensure_resolved()`. For numeric literals this hits the
  `_ipaddr_info()` fast path in `asyncio/base_events.py`, which parses with `inet_pton` and
  **never performs DNS**. Passing `family=` explicitly (as `UdpTransport.open()` does) pins the
  family and skips ambiguity entirely. Verified against the local 3.14 source.
- The `reuse_address` parameter existed but raised in 3.10 and was **removed in 3.11**
  (signature verified: present in 3.10.21, absent in 3.14.2; see the 3.11 changelog for
  `loop.create_datagram_endpoint`). No new code may pass it. The existing code passes only
  `reuse_port`, which is fine, and `reuse_port=True` raises `ValueError` on platforms without
  `SO_REUSEPORT` (Windows); the current `bool(hasattr(socket, "SO_REUSEPORT"))` guard is the
  right pattern.
- **asyncio never touches `IPV6_V6ONLY` for datagram endpoints.** The 3.14
  `create_datagram_endpoint` implementation sets only `SO_REUSEPORT` (if asked) and
  `SO_BROADCAST` (if asked); dual-stack behaviour is whatever the OS default is. Verified by
  reading the full implementation. (Contrast `loop.create_server`, which does manage
  `IPV6_V6ONLY` for wildcard TCP binds; that logic does not apply here.)
- No other behavioural change to datagram endpoints or `DatagramProtocol` callbacks between
  3.10 and 3.14 is relevant to this work: **no change** in family inference, `error_received`
  routing, or sockaddr tuple shapes across the range.

### OS defaults and the dual-stack trap

- Default `IPV6_V6ONLY` is **0 (dual-stack) on both macOS and Linux** (verified via
  `getsockopt` on both). An AF_INET6 socket bound to `"::"` therefore also receives IPv4
  datagrams, and it reports their senders as **IPv4-mapped addresses**: verified on both
  platforms, a 127.0.0.1 sender appears as `('::ffff:127.0.0.1', port, 0, 0)`.
- This makes a single dual-stack socket a trap for this codebase specifically:
  - Any string comparison of `addr[0]` against a stored IPv4 `PeerInfo.ip` fails
    (`"192.168.1.5" != "::ffff:192.168.1.5"`).
  - IPv4 **broadcast** (255.255.255.255, which discovery depends on) cannot be sent from an
    AF_INET6 socket; `SO_BROADCAST` semantics do not carry over via mapped addresses.
  - IPv6 sockaddrs are 4-tuples `(host, port, flowinfo, scope_id)`, so any code that compares
    whole address tuples, rather than indexing `addr[0]`/`addr[1]`, breaks.
- **Recommendation (and what the branch already does): per-family sockets, with the family
  following the target address.** `DeviceConnection` binds `"::"` for IPv6 targets and
  `0.0.0.0` otherwise; discovery keeps its IPv4 broadcast socket. Optional hardening: set
  `IPV6_V6ONLY=1` on the per-device IPv6 socket so mapped-IPv4 strays can never arrive; it is
  hygiene, not correctness, because request correlation is by (source, sequence, serial), not
  by peer address.

### Deciding the family without DNS

- `ipaddress.ip_address(text)` is the authoritative classifier: raises `ValueError` for
  non-literals, returns `IPv4Address`/`IPv6Address`, and has accepted zone-qualified IPv6
  (`"fe80::1%en0"`) since Python 3.9 (bpo-34788); no change across 3.10 to 3.14.
  `Device.__init__` already uses it.
- `socket.inet_pton(AF_INET6, text)` is a **portability trap** for this job: Apple's libc
  accepts `"fe80::1%en0"`, glibc rejects it (both verified this session). CPython's own
  asyncio knows this: `_ipaddr_info()` bails out on `'%' in host` with the comment "Linux's
  inet_pton doesn't accept an IPv6 zone index" (`asyncio/base_events.py`, line ~139 in 3.14).
  Do not use `inet_pton` for family sniffing.
- The branch's `":" in host` heuristic (in `UdpTransport.open()`, `DeviceConnection.open()`,
  `Animator`) is sound **after** validation: every IPv6 literal contains a colon, no IPv4
  literal can, and the inputs at those seams are literals that already passed
  `ipaddress.ip_address()` in `Device.__init__`. Keep `ipaddress` at the boundary and the
  cheap heuristic in the hot paths.
- Alternative if a stricter probe is ever wanted:
  `socket.getaddrinfo(host, port, flags=socket.AI_NUMERICHOST)` fails fast for anything that
  would need DNS. Not needed given the above.

### Silent failure mode that motivated the animator fix

`_SelectorDatagramTransport.sendto()` catches `OSError` (which includes `socket.gaierror`)
and routes it to `protocol.error_received()` instead of raising
(`asyncio/selector_events.py`, verified in the 3.14 source). An AF_INET socket asked to send
to an IPv6 literal therefore **drops the datagram silently** from the caller's perspective.
The raw-socket path in `Animator` raises instead, but the same class of bug applies: this is
why commit `2f884f5` (frame-socket family follows the device address) is required, and why
any new send path must pick its family before first send.

## 2. Link-local versus routable IPv6

### Zone/scope IDs (RFC 4007)

- `getaddrinfo` moves the zone out of the text and into the sockaddr:
  `getaddrinfo("fe80::1%lo0", 56700, AF_INET6, SOCK_DGRAM, flags=AI_NUMERICHOST)` returns
  sockaddr `('fe80::1', 56700, 0, 1)` on both platforms (verified). The 4th element is the
  interface index.
- `sendto` with a zone-qualified 2-tuple `("fe80::1%en0", port)` is valid syntax on both
  platforms: CPython's C layer resolves the string per call via numeric `getaddrinfo`
  (`socketmodule.c` `setipaddr`), which handles the zone on both libcs. Verified: the send
  attempt proceeds to routing on both platforms. A 4-tuple with an explicit `scope_id` is
  equally valid and skips the per-call parse.
- **Missing or wrong scope is undefined-by-platform, not a clean error:**
  - macOS: `sendto` to an unscoped `fe80::` target fails immediately with
    `errno 65 EHOSTUNREACH` ("No route to host"). Verified.
  - Linux: the same send **succeeded** in a single-interface container (the kernel picked the
    only candidate interface); on a multi-homed host it typically fails `EINVAL` or egresses
    an arbitrary interface. Verified (the success case), which is the worse failure mode:
    it works in CI and on simple networks, then breaks on the multi-homed networks Thread
    devices actually live on.
  - Because the transport routes send-time `OSError` to `error_received`, a missing scope on
    macOS looks like packet loss, not an exception.
- The branch's `Device.__init__` warning for link-local-without-scope is therefore correct
  placement (warn at validation, don't crash). One cleanup: `getattr(addr, "scope_id", None)`
  is unnecessary; `IPv6Address.scope_id` exists unconditionally since 3.9 and returns `None`
  when absent. Plain `addr.scope_id is None` is exact.
- **Received datagrams from link-local peers arrive zone-qualified.** CPython converts an
  incoming `sockaddr_in6` to a tuple using numeric `getnameinfo`, and both glibc and Apple's
  libc append `%<ifname>` for link-local sources with a scope. So `addr[0]` may be
  `'fe80::abc%eth0'`. Two consequences: (a) the reply address can be fed straight back to
  `sendto`, which is convenient; (b) any comparison of `addr[0]` against an unscoped stored
  IP needs normalisation (`ipaddress.ip_address(addr[0].split("%")[0])` or compare
  `IPv6Address` objects with zones stripped). Confidence MEDIUM-HIGH (libc-documented
  behaviour; not re-verified live this session because loopback has no link-local peer).

### Classification with `ipaddress`

| Class | Test | Notes |
|-------|------|-------|
| Link-local (fe80::/10) | `addr.is_link_local` | Needs a zone to be usable; lowest preference |
| ULA (fc00::/7, RFC 4193) | `addr in ipaddress.ip_network("fc00::/7")` | No `is_unique_local` property exists; `is_private` is True for ULA but also for other ranges, so the containment test is the precise one. The fleet's Thread prefixes (`fdc6:...`, `fd5a:...`) are ULA |
| GUA (2000::/3) | `addr.is_global` | Preferred equally with ULA for this purpose: both are routable without a zone |

- **CVE-2024-4032 caveat:** `is_private`/`is_global` were realigned with the IANA
  Special-Purpose registries in 3.13.0, backported to 3.12.4 and the 3.11/3.10 security
  branches (3.11.10, 3.10.15). Within the CI matrix (current patch releases via
  `setup-python`) all versions have the fix, but a user on an old 3.10/3.11/3.12 patch
  release sees the old table. **The ranges this milestone classifies are unaffected**:
  fe80::/10, fc00::/7 and ff02::/16 answered identically on 3.10.21 and 3.14.2 (verified).
  The affected ranges were things like `64:ff9b:1::/48` and `2002::/16`. Conclusion: prefer
  `is_link_local` and the fc00::/7 containment test (stable across the fix) over `is_global`
  where possible; the branch's `_pick_address()` uses only `is_link_local`, which is fully
  stable. No change needed.

## 3. IPv6 multicast for mDNS (`ff02::fb`)

Recorded for completeness and for a possible future IPv6 query leg. **The branch's current
design does not require any of this** (see §4): a one-shot querier on an ephemeral port needs
no group membership to receive its unicast replies, and the existing IPv4 multicast query
already reaches Thread devices because the border router's advertising proxy answers on the
IPv4 side with AAAA records (this is how the two live Thread devices were found).

- **Constant name:** use `socket.IPV6_JOIN_GROUP` / `socket.IPV6_LEAVE_GROUP`. CPython does
  **not** expose `IPV6_ADD_MEMBERSHIP` on either macOS or Linux (verified on both; it is a
  glibc C macro alias that never made it into the socket module). Code written against the
  `*_MEMBERSHIP` names fails with `AttributeError` everywhere.
- **mreq layout** (`struct ipv6_mreq`): 16-byte group address then a native unsigned int
  interface index:
  `mreq = socket.inet_pton(socket.AF_INET6, "ff02::fb") + struct.pack("@I", ifindex)`.
  Verified to join successfully on both platforms (lo/lo0 and ifindex 0). Contrast the IPv4
  path in `MdnsTransport` history: `struct.pack("4sl", inet_aton(group), INADDR_ANY)` at
  level `IPPROTO_IP`; the IPv6 version is level `IPPROTO_IPV6` and index-based rather than
  address-based.
- **Interface index:** `socket.if_nametoindex("en0")` and `socket.if_nameindex()` (full
  enumeration) are the stdlib tools; both available and unchanged across 3.10 to 3.14 on
  POSIX. Index 0 means "kernel default", which is accepted on both platforms but is wrong on
  multi-homed hosts: ff02::/16 is link scope, so membership is inherently per-interface, and
  complete coverage means iterating `if_nameindex()` and joining per interface (skipping
  failures; loopback and down interfaces reject or are useless).
- **Sending to ff02::fb differs by platform (verified):**
  - Linux: `sendto(("ff02::fb", port))` unscoped works (default multicast route), and a
    scoped destination `"ff02::fb%eth0"` also works.
  - macOS: **both** the unscoped and the zone-scoped destination fail with
    `errno 65 EHOSTUNREACH`; the send only succeeds after
    `setsockopt(IPPROTO_IPV6, IPV6_MULTICAST_IF, ifindex)`. So the portable send pattern is:
    set `IPV6_MULTICAST_IF` per interface, then send to the plain group address, per
    interface.
- **Other options:** hop limit is `IPV6_MULTICAST_HOPS` (mDNS wants 255 per RFC 6762 §11;
  the IPv4 code sets `IP_MULTICAST_TTL`), loopback suppression is `IPV6_MULTICAST_LOOP`.
  All constants present on both platforms (verified).
- **Stdlib gap:** there is no `getifaddrs()` equivalent, so you cannot ask "which interfaces
  currently hold an IPv6 address" without external tools. `if_nameindex()` gives names and
  indices only. Workarounds that stay in-stdlib: join/send per interface and tolerate
  `OSError` per interface, or discover the default route's source address with the
  connected-UDP trick (`connect()` a datagram socket to the target, read `getsockname()`;
  no packet is sent by `connect` on UDP).

## 4. Port binding and SO_REUSEPORT (the ephemeral-port defect)

### What RFC 6762 says

- §5.1 "One-Shot Multicast DNS Queries": a simple querier may send from an ephemeral port,
  and such queries are distinguishable *by source port*.
- §6.7 "Legacy Unicast Responses": "If the source UDP port in a received Multicast DNS query
  is not port 5353 ... the responder MUST send a UDP response directly back to the sender,
  via unicast, to the query packet's source IP address and port." (Responders also cap
  record TTLs at 10 seconds in such replies, which is why discovery results should be treated
  as a snapshot, not a cache.)
- Conversely, queries sourced *from* 5353 mark the sender as a fully compliant multicast
  responder (§5.2, §6), and answers to them are typically sent **to the multicast group**,
  relying on group membership and shared-port delivery.

### Why 5353 + SO_REUSEPORT loses replies

When the library binds 5353 with `SO_REUSEPORT` alongside mDNSResponder (macOS, always
running) or Avahi (Linux), two delivery regimes mix:

1. **Multicast** datagrams to the group are delivered to every socket that joined the group
   on that port; both the daemon and the library see them. This part works.
2. **Unicast** datagrams to port 5353 (QU-bit answers, direct responses, and any
   implementation that unicasts) are delivered to exactly **one** of the sockets sharing the
   port, and the app cannot influence which:
   - Linux: since kernel 3.9, `SO_REUSEPORT` distributes UDP datagrams across the sharing
     sockets by a 4-tuple hash (socket(7)); the daemon wins a fraction of flows, effectively
     at random per source.
   - macOS: classic BSD semantics; a unicast UDP datagram goes to one socket (in practice
     the daemon), not to all members.

   Either way, replies vanish into the system daemon. The project measured exactly this:
   **9 of 25 devices found bound to 5353, 25 of 25 bound ephemeral** (PROJECT.md, HIGH
   confidence, own field evidence).

An ephemeral port sidesteps the entire problem: RFC 6762 §6.7 obliges responders to unicast
to that port, no other process shares it, and no group membership is needed to receive the
replies. The branch's rewrite of `MdnsTransport.open()` (bind `("", 0)`, drop the group
join, drop the 5353 attempt) is the correct stdlib expression of this. It also stops the
library from impersonating a full responder it isn't.

One consequence to document for the phase that tests this: an ephemeral-port querier
**cannot receive unsolicited multicast announcements**, only answers to its own queries.
That is the correct trade for a discovery sweep, and it is why the RFC 6762 §5.2-style query
retransmit added in `discover_lifx_services()` matters (re-asking catches responders whose
first answer was lost).

## 5. Testing IPv6 and multi-packet mDNS without hardware

Three layers, all stdlib, ordered from most to least deterministic. The synthetic
multi-packet requirements (cross-packet accumulation, follow-up A/AAAA) belong at layers 1
and 2; layer 3 proves the socket plumbing.

1. **Pure codec tests (no sockets, no loop).** Craft response packets with `struct` and the
   module's own `_encode_name()`; parse with `parse_dns_response()`. Include DNS name
   compression pointers (`0xC0 | offset`) in crafted packets, because real responders
   compress and the hand-rolled parser must keep handling it. Multi-packet scenarios are
   just lists of crafted payloads.
2. **Protocol injection (no real sockets, real asyncio).** `_UdpProtocol` is a plain object:
   tests can call `protocol.datagram_received(payload, ("fe80::1%eth0", 5353, 0, 3))`
   directly, or feed `MdnsTransport._protocol.queue`, sequencing packets across iterations
   of the discovery loop. This is the technique for: cross-packet record accumulation, the
   follow-up A/AAAA query path (assert on a captured `transport.send`), zone-qualified
   source addresses, and border-router multi-instance packets. To capture sends, monkeypatch
   the `DatagramTransport` or hand `create_datagram_endpoint(sock=...)` a pre-made socket.
   Note the `sock=` seam is **mutually exclusive** with `local_addr`/`family`/`reuse_port`
   (raises `ValueError`, verified in the 3.14 source), which is exactly why
   `MdnsTransport` configures its socket manually before handing it over.
3. **Real loopback IPv6 endpoints.** Two `create_datagram_endpoint(local_addr=("::1", 0))`
   endpoints exchanging real datagrams exercise the AF_INET6 send/receive path end to end,
   including 4-tuple addresses. Verified working constraints:
   - `::1` is available on macOS and Linux dev machines, GitHub Actions `ubuntu-*` and
     `macos-*` runners, and **inside Docker containers even without IPv6 networking**
     (verified: `("::", 0)` binds in `python:3.10-slim` with default Docker networking).
   - `socket.has_ipv6` is a compile-time constant and is True even when the kernel has IPv6
     disabled (`ipv6.disable=1`). The authoritative guard is a fixture that try-binds
     `("::1", 0)` and skips on `OSError`. Model it on the existing emulator-availability
     skip.
   - `::1` has no zone and is not link-local, so scope-handling tests stay at layer 2; there
     is no portable way to manufacture a real link-local peer in CI.
   - Do **not** join `ff02::fb` or bind 5353 in tests: multicast on runner networks is
     flaky, macOS runners share tenancy, and 5353 collides with the runners' own daemons,
     which is the very defect under test.

No behavioural changes across 3.10 to 3.14 affect these techniques ( `DatagramProtocol`
callback signatures, `Queue`, `wait_for` semantics for this use: no change).

## What NOT to add

| Avoid | Why | Use instead |
|-------|-----|-------------|
| `zeroconf` / `aiozeroconf` | Runtime dependency; binds 5353 as a full responder, importing the exact reply-stealing coexistence problem | Existing hand-rolled `mdns/` one-shot querier on an ephemeral port |
| `netifaces` / `psutil` for interface enumeration | Runtime dependency; unmaintained (`netifaces`) | `socket.if_nameindex()` plus per-interface try/except; connected-UDP `getsockname()` trick for source addresses |
| `aiodns` / `dnspython` | Runtime dependency; general DNS is not the problem, mDNS wire format is, and it is already implemented | `mdns/dns.py` |
| `socket.inet_pton` for family/zone sniffing | Platform-divergent: Apple libc accepts `%zone`, glibc rejects it (verified) | `ipaddress.ip_address()` |
| One dual-stack `"::"` socket for everything | Mapped-address peer strings, no IPv4 broadcast, 4-tuple/2-tuple mixing | Per-family sockets, family follows the target (branch already does this) |
| `reuse_address=` on `create_datagram_endpoint` | Removed in Python 3.11; raises `TypeError` there and was already forbidden in 3.10 | Nothing; `reuse_port` only where genuinely needed (and it no longer is, post ephemeral-bind) |
| `IPV6_ADD_MEMBERSHIP` constant | Not exposed by CPython on macOS **or** Linux (verified) | `socket.IPV6_JOIN_GROUP` / `IPV6_LEAVE_GROUP` |
| Binding UDP 5353 (with or without `SO_REUSEPORT`) | System daemons steal unicast replies; measured 9/25 vs 25/25 devices | Ephemeral port; RFC 6762 §6.7 guarantees unicast replies to it |

## Where the stdlib does not solve it (hand-rolling required)

- **Interface address enumeration.** No `getifaddrs()`. `if_nameindex()` yields names and
  indices but not addresses. Any "which interfaces should I multicast on" logic must
  iterate-and-tolerate-errors or use the connected-UDP source-address trick. Accept this;
  the ephemeral-port unicast design mostly avoids needing it.
- **mDNS/DNS-SD itself.** Already hand-rolled (`mdns/dns.py`, `mdns/discovery.py`); the
  branch extends it (AAAA parsing via `socket.inet_ntop(AF_INET6, rdata)`, `_encode_name`,
  `build_address_query`, `_LifxRecordCache`). Correct primitives; keep.
- **SO_REUSEPORT delivery arbitration.** No API can steer unicast datagrams between sockets
  sharing a port. Unfixable at application level; the ephemeral port is the fix.
- **Link-local peers in CI.** No portable way to create one; scope-ID paths are covered by
  injection tests with zone-qualified 4-tuples.

## Version compatibility (3.10 → 3.14)

| Facility | 3.10 | 3.11 | 3.12 | 3.13 | 3.14 | Notes |
|----------|------|------|------|------|------|-------|
| `create_datagram_endpoint` family/`reuse_port` | ✓ | ✓ | ✓ | ✓ | ✓ | No behavioural change in range |
| `create_datagram_endpoint(reuse_address=...)` | present, raises if True | **removed** | removed | removed | removed | Never pass it |
| `ipaddress` scoped IPv6 + `.scope_id` | ✓ | ✓ | ✓ | ✓ | ✓ | Since 3.9; no change in range |
| `is_private`/`is_global` IANA realignment | 3.10.15+ | 3.11.10+ | 3.12.4+ | ✓ | ✓ | fe80::/10, fc00::/7, ff02::/16 unaffected (verified); avoid relying on `is_global` for exotic ranges |
| `socket.if_nametoindex` / `if_nameindex` | ✓ | ✓ | ✓ | ✓ | ✓ | POSIX; no change |
| `IPV6_JOIN_GROUP`, `IPV6_MULTICAST_IF/HOPS/LOOP`, `IPV6_V6ONLY` | ✓ | ✓ | ✓ | ✓ | ✓ | Presence verified 3.10 (Linux) and 3.14 (macOS) |
| `DatagramProtocol.error_received` routing of send-time `OSError`/`gaierror` | ✓ | ✓ | ✓ | ✓ | ✓ | Verified in 3.14 source; matches existing `_FATAL_SOCKET_ERRNOS` design notes |

## Platform differences (macOS dev machine vs Linux CI)

| Behaviour | macOS (Darwin 25) | Linux (glibc) | Consequence |
|-----------|-------------------|---------------|-------------|
| `inet_pton(AF_INET6, "fe80::1%en0")` | accepted | **rejected** | Never use `inet_pton` for parsing user input; a macOS-developed path would break in CI |
| `sendto` unscoped `fe80::` | fails `EHOSTUNREACH` (65) | may silently succeed on single-homed hosts | Linux CI can pass while real multi-homed networks fail; keep the validation-time warning |
| `sendto` to `ff02::fb` | fails even with `%zone`; needs `IPV6_MULTICAST_IF` | works unscoped or scoped | Any future IPv6 multicast send loop must set `IPV6_MULTICAST_IF` per interface |
| `IPV6_V6ONLY` default | 0 | 0 | Same trap both sides; per-family sockets regardless |
| Unicast delivery among `SO_REUSEPORT` sharers | one socket (BSD semantics) | 4-tuple hash distribution (kernel ≥3.9, socket(7)) | Different mechanisms, same defect: the daemon can take the reply. Ephemeral bind fixes both |
| System mDNS daemon on 5353 | mDNSResponder, always | Avahi, usually on desktop/server images incl. GH runners | The 5353 collision exists in CI too; regression test must not bind 5353 |

## Integration points with existing code

| File | Change (branch) | Assessment |
|------|-----------------|------------|
| `network/transport.py` | family follows `_ip_address` (`"::"` → AF_INET6) | Correct; asyncio does the rest. `sockname[1]` indexing survives 4-tuples |
| `network/connection.py` | bind `"::"` when peer IP contains `:` | Correct; per-family socket avoids all dual-stack traps. Optional: `IPV6_V6ONLY=1` hygiene |
| `devices/base.py` | accept IPv6, warn on unscoped link-local | Correct placement; simplify `getattr(addr, "scope_id", None)` → `addr.scope_id` (3.9+ guaranteed) |
| `network/mdns/transport.py` | ephemeral bind, group join removed | Correct per RFC 6762 §5.1/§6.7 and the 9/25-vs-25/25 measurement; document the "no unsolicited announcements" trade |
| `network/mdns/dns.py` | AAAA parse (`inet_ntop`), `build_address_query` | Correct primitives; add a compression-pointer response fixture to the test set |
| `network/mdns/discovery.py` | `_LifxRecordCache`, `_pick_address` (routable-over-link-local via `is_link_local`), §5.2 retransmit | `is_link_local`-only preference is stable across the CVE-2024-4032 change; sound. Watch: zone-qualified `addr[0]` from link-local responders flows into `_fallback_ip_by_instance` and out as a device IP, which is actually desirable (it carries its own scope) but should be normalised before comparing against A/AAAA-derived strings |
| `animation/animator.py` | frame-socket family follows `_addr[0]` | Correct; required because wrong-family sends vanish into `error_received`/`gaierror` silently |

## Sources

- CPython 3.14.2 source (local): `asyncio/base_events.py` (`_ipaddr_info` `'%'` bail-out,
  `create_datagram_endpoint` full implementation, no `IPV6_V6ONLY` handling),
  `asyncio/selector_events.py` (`_SelectorDatagramTransport.sendto` → `error_received`) — HIGH
- Empirical verification this session: macOS Darwin 25 / CPython 3.14.2 and
  `python:3.10-slim` (CPython 3.10.21, glibc) — inet_pton zone divergence, `IPV6_JOIN_GROUP`
  presence and `IPV6_ADD_MEMBERSHIP` absence on both, `IPV6_V6ONLY` defaults, mapped-address
  dual-stack receive, scoped `getaddrinfo` sockaddrs, unscoped-fe80 send behaviour,
  ff02::fb egress requirements, `::1` availability in Docker, 3.10-vs-3.14
  `create_datagram_endpoint` signatures — HIGH
- Python docs: `asyncio` event loop (`create_datagram_endpoint`, reuse_address removal noted
  in 3.11 changelog), `socket` (if_nametoindex, constants), `ipaddress` (scoped addresses,
  "Changed in version 3.9") — HIGH
- RFC 6762 (Multicast DNS): §3 (ff02::fb), §5.1 one-shot queries, §5.2 retransmission,
  §6.7 legacy unicast responses, §11 hop limit — HIGH
- RFC 4007 (IPv6 scoped address architecture), RFC 4193 (ULA fc00::/7), RFC 4291
  (addressing architecture) — HIGH
- Linux `socket(7)` — SO_REUSEPORT UDP datagram distribution (kernel ≥3.9) — HIGH
- CVE-2024-4032 (`ipaddress` is_private/is_global realignment; fixed 3.13.0/3.12.4 and
  security backports): [CVE Details](https://www.cvedetails.com/cve/CVE-2024-4032/),
  [Ubuntu security tracker](https://ubuntu.com/security/CVE-2024-4032) — MEDIUM-HIGH for
  exact backport patch levels; the ranges this project classifies are verified unaffected
- Project's own field measurements (PROJECT.md): 9/25 vs 25/25 device discovery bound
  5353 vs ephemeral; Thread devices found via mDNS only — HIGH

---
*Stack research for: Thread/IPv6 support in lifx-async (stdlib-only)*
*Researched: 2026-08-27*
