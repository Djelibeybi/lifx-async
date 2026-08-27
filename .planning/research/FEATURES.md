# Feature Research

**Domain:** Thread/IPv6 device discovery and control in a local-network smart-lighting library
**Researched:** 2026-08-27
**Confidence:** MEDIUM overall — ecosystem claims verified against actual source and specs; Thread
performance numbers come from published measurements, not from this fleet, and are flagged where
only local measurement can settle them

Scope note: this is milestone research for v2.0 Thread/IPv6 Support. Existing capabilities
(broadcast discovery, mDNS discovery, targeted lookups, device classes, effects, animation,
protocol codec) are treated as the baseline and are not re-researched.

## How the Ecosystem Works (Question-by-Question Findings)

### 1. Discovery: how a Thread border router advertises mesh devices

**Mechanism (verified against OpenThread documentation and the ot-br-posix architecture):**
A Thread device cannot speak mDNS itself — multicast does not cross the mesh economically.
Instead it registers its services with the border router over unicast SRP (Service Registration
Protocol), and the border router's **advertising proxy** republishes those registrations as
ordinary mDNS/DNS-SD on the infrastructure (WiFi/Ethernet) link. The AAAA records point at the
device's own mesh address on the OMR prefix, normally a ULA. The border router answers mDNS
*on behalf of every device on its mesh* from a single responder socket.

- Sources: [OpenThread Border Router guide](https://openthread.io/guides/border-router),
  [OTBR codelab (bidirectional IPv6 + DNS-SD)](https://openthread.io/codelabs/openthread-border-router),
  [Thread 1.3.0 white paper](https://www.threadgroup.org/Portals/0/documents/support/Thread1.3.0WhitePaper_07192022_3990_1.pdf),
  [ot-br-posix SRP advertising proxy](https://deepwiki.com/openthread/ot-br-posix/6.3-srp-advertising-proxy)
- **Local corroboration:** the Thread devices in this fleet answer on an OMR ULA prefix
  distinct from the WiFi fleet's `fd00:3::`, which is exactly the OMR-prefix shape
  the docs describe (PROJECT.md, Context). The prefix itself is auto-generated and re-derives
  when the border router re-forms the mesh: it was `fd00:1::` until 2026-08-28 and is
  `fd00:2::` now, so the serial is the durable identifier, not the address.

**What a real LIFX advertisement looks like:** PTR `_lifx._udp.local` → instance → SRV
(port 56700, target hostname) + TXT + A/AAAA for the target. The
[official LAN docs](https://lan.developer.lifx.com/docs/communicating-with-device) document
exactly three TXT keys: `id` (serial — prefer over the instance name), `fw` (semantic firmware
version, mDNS requires firmware ≥ 4.110), `p` (product ID). **The `tm` key (1 = WiFi,
2 = Thread) is NOT in the public documentation** — it is observed on real hardware in this
fleet. Treat it as undocumented vendor metadata: parse defensively, absent means unknown, and
never make correctness depend on it.

**LIFX vs Matter service conventions:** Matter uses `_matter._tcp` for operational discovery
(instance name = `<compressed-fabric-id>-<node-id>`) and `_matterc._udp` for commissionable
discovery, with TXT keys such as `D` (discriminator), `VP` (vendor/product) — and, critically,
**MRP session parameters `SII`/`SAI`(/`SAT`)** in operational TXT records, so a controller can
retune its retry intervals per device; malformed values are ignored and defaults apply
([matter.js changelog](https://github.com/matter-js/matter.js/blob/main/CHANGELOG.md)).
LIFX's `_lifx._udp` carries identity only — **no timing hints**. The lesson for question 5:
Matter's designers considered per-device timing advertisement necessary precisely because
WiFi-tuned constants do not transfer to Thread; the LIFX LAN protocol offers no equivalent,
so measurement (SEED-001) is the only way lifx-async gets those numbers.
- Sources: [Google Home Matter discovery primer](https://developers.home.google.com/matter/primer/commissionable-and-operational-discovery),
  [CSA Matter handbook — Discovery](https://handbook.buildwithmatter.com/how-it-works/discovery/)

**Reply overflow at mesh scale:** because one responder answers for many devices, the reply
outgrows a single packet quickly. Two distinct regimes:

- *Multicast responses:* RFC 6762 allows the TC bit plus continuation; a responder seeing a
  query with TC set defers 400–500 ms ([RFC 6762](https://www.rfc-editor.org/rfc/rfc6762.html)).
- *Legacy unicast responses* — which is what lifx-async now receives, because the v2.0
  ephemeral-port bind makes its queries legacy-unicast — **cannot span multiple packets**.
  Avahi simply omits the services that do not fit
  ([avahi/avahi#23](https://github.com/avahi/avahi/issues/23)). The querier must notice the
  gap (SRV target with no address record) and issue follow-up A/AAAA queries.

The `feat/ipv6-thread-support` branch (`b49400b`) already implements the three required
behaviours: per-instance record accumulation across packets, PTR retransmit per RFC 6762 §5.2,
and follow-up A/AAAA queries for unresolved SRV targets. The research confirms these are the
right behaviours, and that they cannot be exercised by two Thread devices — the synthetic
multi-packet tests in the milestone scope are the correct substitute until the fleet migrates.

### 2. Transport visibility: what comparable libraries expose

Verified against actual source, not recall:

| Library | Transport exposed? | Evidence |
|---------|--------------------|----------|
| python-matter-server | **Yes, as diagnostics only.** `client.node_diagnostics()` builds `NodeDiagnostics` with `network_type: NetworkType` (THREAD/WIFI/ETHERNET/UNKNOWN), derived from the GeneralDiagnostics `NetworkInterfaces` cluster attribute. Control traffic is identical either way. | [`matter_server/client/client.py`](https://github.com/home-assistant-libs/python-matter-server/blob/main/matter_server/client/client.py) (`node_diagnostics`, ~line 318), [`matter_server/client/models/node.py`](https://github.com/home-assistant-libs/python-matter-server/blob/main/matter_server/client/models/node.py) (`NetworkType`, `NodeDiagnostics`, ~lines 382–408) |
| Home Assistant Matter integration | Surfaces that diagnostics value in the device panel via the `matter/node_diagnostics` websocket command; newer versions add a network-topology API (schema ≥ 13, `NetworkTopology`). Nothing routes differently by transport. | [`homeassistant/components/matter/api.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/matter/api.py) (`TOPOLOGY_SCHEMA_VERSION = 13`, `websocket_node_diagnostics`) |
| aioesphomeapi | **No.** `DeviceInfo` has `mac_address`, `model`, feature flags — no transport/network-type field. The caller supplies the host; discovery is externalised to HA zeroconf (`_esphomelib._tcp.local.`). | [`aioesphomeapi/model.py`](https://github.com/esphome/aioesphomeapi/blob/main/aioesphomeapi/model.py) (`class DeviceInfo`), [`esphome/manifest.json`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/esphome/manifest.json) |
| python-kasa | **No transport concept.** Broadcast-only discovery to ports 9999/20002 (`Discover.discover()`), results returned as a dict keyed by IP. | [`kasa/discover.py`](https://github.com/python-kasa/python-kasa/blob/master/kasa/discover.py) (`class Discover`, ~line 417) |
| zigpy | Not applicable — devices are addressed by IEEE/NWK over a radio; there is no IP transport to expose at all. (Definitional, not source-verified behaviour.) | [zigpy repo](https://github.com/zigpy/zigpy) |
| aiolifx | **No.** IPv4 broadcast discovery; the only IPv6 support is an `ipv6prefix` parameter that *synthesises* a link-local address from the MAC (`mac_to_ipv6_linklocal`). No mDNS, no Thread awareness, no AAAA. | [`aiolifx/aiolifx.py`](https://github.com/aiolifx/aiolifx/blob/master/aiolifx/aiolifx.py) (lines ~69–90, ~2400) |

**What callers realistically do with transport information:** display it (HA's device
diagnostics panel), filter it when debugging ("which of my bulbs migrated?"), and set
expectations for streaming workloads (a LedFx-class consumer choosing frame rates per device).
No surveyed library makes control behaviour *depend* on it from the caller's side. The
ecosystem consensus is exactly the v2.0 plan: expose `tm` as read-only metadata on
`LifxServiceRecord`, keep every control path transport-blind. lifx-async exposing `tm` would
make it the only LIFX LAN library with any Thread awareness at all — aiolifx (HA's current
LIFX provider) has none.

### 3. Merged discovery: established patterns

- **Dedup key is stable device identity, never address.** HA config flows dedup every
  discovery source (DHCP, zeroconf, HomeKit, integration discovery) on `unique_id`; the LIFX
  flow uses the formatted serial and `_abort_if_unique_id_configured(updates={CONF_HOST: host})`
  — a later discovery from any source *updates the address* but never creates a second device
  ([`homeassistant/components/lifx/config_flow.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/lifx/config_flow.py),
  lines 85–88; [`manifest.json`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/lifx/manifest.json)).
  lifx-async already dedups by serial in both legs (`_discover_with_packet` first-wins;
  `discover_lifx_services` `seen_serials`), so the merge is a union of two serial-keyed streams.
- **Multiple legs, one result stream, merge invisible.** python-kasa sends to two discovery
  ports "in order" and returns one dict; HA users never see which source found a device first.
  No surveyed library exposes "which leg" as API surface beyond diagnostics.
- **Partial results stream as found.** Both existing lifx-async generators yield as devices
  answer; the merged `discover()` must preserve that — run both legs concurrently and yield
  first-wins per serial, not gather-then-merge.

**What consumers (and implementers) get wrong:**

1. *Blocking on the slower leg* — gathering both legs before yielding turns a
  stream-as-found API into a batch API and doubles worst-case latency for the first device.
2. *Deduplicating by IP* — fails outright here: a Thread device has no IPv4 address, and the
  same physical device mid WiFi→Thread migration appears with different addresses on
  different legs. Serial is the only stable key (the WiFi fleet's serial≈MAC quirk in
  `devices/base.py` already makes address-derived identity fragile).
3. *Treating "not found by broadcast" as offline* — a Thread device is invisible to broadcast
  by construction. Consumer guidance docs (in scope) need to say this explicitly for
  broadcast-first integrations.
4. *Assuming the mDNS answer proves the device is reachable* — on Thread, the answer comes
  from the border router's cache of an SRP registration, not from the device. An
  advertisement can outlive device reachability until the SRP lease expires (lease durations
  are deployment-configurable; **unverified for LIFX's firmware without measurement**). The
  first actual request to the device is the real liveness check — the existing lazy-connection
  and retry machinery already handles that, but tests should not equate "advertised" with "up".
5. *Idle-window interference between legs* — each leg has its own silence-based idle window.
  A merged generator must not let the chatty leg (WiFi broadcast) keep the sweep alive while
  the mDNS leg has long finished, nor vice versa; per-leg deadlines with a shared overall
  timeout is the shape that matches the existing `IdleDeadline` semantics.

### 5. Reliability: which WiFi-tuned constants Thread invalidates

Published numbers (none measured on this fleet — flagged accordingly):

- **PHY:** 802.15.4 at 250 kbps, shared with the whole mesh. Frames are 127 bytes; 6LoWPAN
  fragments anything bigger, and losing one fragment loses the datagram
  ([Silicon Labs Thread overview](https://docs.silabs.com/openthread/latest/thread-fundamentals/02-thread-technology-overview)).
- **Latency:** local-network ICMPv6 RTT "typically under a few tens of milliseconds"
  single-hop (Silicon Labs, ibid.). Per-hop mesh forwarding adds latency and jitter; one- and
  two-hop topologies measurably outperform deeper meshes
  ([MDPI 2023 Thread performance evaluation](https://www.mdpi.com/2076-3417/13/13/7745)).
- **Goodput:** the same measurement found 0% UDP loss up to ~100 kbps single-hop before the
  bottleneck, with ~40 kbps the optimum for zero-loss/low-jitter operation.
- **Sleepy end devices:** SEDs poll their parent and buffer downstream traffic. LIFX bulbs
  are mains-powered, so they are almost certainly full Thread devices (likely promoted to
  routers), not SEDs — **but whether LIFX's Thread firmware uses any sleepy/CSL mode is
  unknown without measurement.** The gen4 WiFi power-save wake-tail precedent (sub-250 ms,
  documented in v1.1) says LIFX does ship power management that shapes first-packet latency.

Against the four specific WiFi-tuned assumptions:

| WiFi-tuned constant | Thread verdict |
|---------------------|----------------|
| Acked bulb answers within 200 ms (retry first-attempt floor) | Plausibly still fine single-hop idle (tens of ms RTT) but **unproven under load or multi-hop**; a mesh hop plus fragmentation of larger packets can push tails past 200 ms. Revalidate, don't assume. |
| ~100 ms ack RTT under streaming load | **Likely invalid.** Under streaming the radio is the bottleneck; queueing delay grows with offered load in a way WiFi at 10⁴× the bandwidth never showed. Needs measurement on the test devices. |
| 2-outstanding-frame ack gate | The *design* transfers (ack-gating self-paces to whatever the path delivers — this is the strongest argument the v1.1 architecture was right); the *constant* may not. Two outstanding ~560-byte frames is ~9 kbit in flight on a 250 kbps shared PHY. Gate of 2 may still be correct or may need to be 1; measurement decides. |
| 20 FPS streaming | **Likely infeasible sustained for matrix frames.** Arithmetic: a `Set64` packet is ~558 bytes (36-byte header + ~522-byte payload); 20 FPS ≈ 89 kbps application-layer, *before* 6LoWPAN fragmentation (~5–6 radio frames per packet) and UDP/IPv6 overhead — at or above the measured ~100 kbps zero-loss single-hop ceiling, and that ceiling is for the whole mesh, not per device. Extended multizone (`SetExtendedColorZones`, up to 82 zones) is larger still. Expect graceful degradation via the ack gate to some lower effective rate; the honest answer for the achievable FPS is "unknown without measurement" — which is precisely SEED-001's job, and the two Thread `MatrixLight` devices are the instruments. |

One discovery-side reliability note: Thread has no per-AP broadcast/DTIM pathology, so the
v1.1 escalating re-broadcast schedule is solving a WiFi problem; the mDNS leg's equivalents
are the RFC 6762 §5.2 PTR retransmit (already on the branch) and border-router availability.

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `discover()` finds Thread devices without opt-in | A default sweep that silently misses powered-on devices reads as a bug; measured locally: `discover()` found 25 devices and neither Thread serial. Every surveyed consumer-facing stack (HA, python-kasa) merges sources invisibly | MEDIUM | Merge broadcast + mDNS legs by serial, first-wins, stream-as-found. Depends on existing `_discover_with_packet` dedup + branch mDNS IPv6 leg |
| IPv6 device connections (socket family follows target) | A device with only an IPv6 address must be controllable; `Device.from_ip()` already proved the path | LOW | Already on `feat/ipv6-thread-support` (`b49400b`); landing it is the work |
| AAAA parsing with routable-address preference (ULA/GUA over link-local) | Link-local needs zone IDs and breaks portability; border router advertises OMR ULA | LOW | On branch; probe script verifies the classification on hardware |
| Correct mDNS behaviour when one responder advertises many devices | Border router answers for the whole mesh; legacy unicast replies cannot span packets ([avahi#23](https://github.com/avahi/avahi/issues/23)) so records get omitted | MEDIUM-HIGH | Cross-packet accumulation + follow-up A/AAAA + §5.2 retransmit are on branch; synthetic multi-packet tests are the only way to exercise them pre-fleet-migration |
| mDNS ephemeral-port bind | IPv4 defect in its own right: 5353 + `SO_REUSEPORT` let system daemons steal legacy-unicast replies (measured 9 vs 25 devices) | LOW | On branch; milestone correctly gives it its own regression test |
| `find_by_serial()` reaches Thread devices | A targeted lookup that fails for a device `discover()` can find is incoherent | MEDIUM | Both legs concurrent, first hit wins; neither leg alone covers the fleet (decided 2026-08-27) |
| `find_by_ip()` accepts an IPv6 literal | Returning `None` for a valid address reads as "no such device", not "wrong function" | LOW | Targeted-lookup leg only; transport already proven |
| Public API unchanged for existing callers | Constraint: additive only; HA/LedFx integrations must work unmodified | — | Governs everything above; accepted cost is `discover()`'s timing changes |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `tm` transport method exposed on `LifxServiceRecord` | Matches the ecosystem's best practice (python-matter-server's `NodeDiagnostics.network_type`): transport as read-only diagnostics. No other LIFX LAN library has any Thread awareness — aiolifx's entire IPv6 story is synthesising a link-local from the MAC | LOW | Parse defensively: key is undocumented in official LAN docs; absent ⇒ `None`, never required for correctness |
| Thread-revalidated reliability constants (SEED-001) | Every v1.1 number was measured on WiFi; nobody else in the LIFX ecosystem measures at all. Evidenced-per-device-class closure (v1.2 FIDELITY pattern) makes the claims auditable | HIGH | Depends on merged discovery + IPv6 connections + animator family fix landing first; Test Candle/Tube are the instruments; CeilingLight/MultiZoneLight/Light close as hardware migrates, HevLight/InfraredLight close as named gaps |
| Zero-dependency stdlib mDNS with IPv6 | python-kasa, python-matter-server and HA all lean on the `zeroconf` package; lifx-async's in-tree parser keeps the zero-dep constraint while gaining Thread reach | MEDIUM | Cost already largely paid on the branch; the differentiator is *keeping* it correct at mesh scale (synthetic tests) |
| Animation over Thread that degrades gracefully | The ack-gated flow control paces itself to the path; if measurement shows it self-adapts on Thread, lifx-async streams to Thread matrices at whatever rate the mesh supports without consumer configuration | HIGH (measurement, maybe retuning) | Depends on frame-socket family fix (`2f884f5`); 20 FPS full-frame is likely above the single-hop goodput ceiling — the deliverable is knowing the real number |
| Consumer guidance for broadcast-first integrations | "Your broadcast sweep will never see a Thread bulb" is non-obvious and will generate bug reports downstream (LedFx, HA) | LOW | Docs only; pairs with the merged `discover()` so the guidance is mostly "upgrade and it works" |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Transport-specific entry points (`discover_thread()`, `transport=` parameter) | "Let me query just the Thread devices" | Fragments the API; every surveyed library keeps the merge invisible (HA, python-kasa, matter-server). Callers would encode transport assumptions that break on WiFi→Thread migration | Filter on `LifxServiceRecord.tm` / device metadata after a normal discovery |
| Consumer-facing Thread tuning knobs (gate size, frame rate caps) | Streaming consumers will notice lower Thread throughput and ask for control | Directly conflicts with the locked decision (2026-07-16): delivery strategy is the animation library's, not downstream's; D5-09's publish-behaviour-not-constants rule points the same way | Ack-gated flow control adapts internally; publish measured behaviour in docs |
| Routing control traffic differently by `tm` value | "Thread is slow, so treat Thread devices specially" | No surveyed library does it; `tm` is undocumented and a device's transport can change under firmware migration without the record being re-read; correctness must not depend on a vendor hint | Transport-blind control paths; `tm` is display/diagnostics metadata |
| Treating an mDNS advertisement as proof of reachability | Simplifies device state ("advertised ⇒ online") | On Thread the advertisement is the border router's SRP cache, which can outlive device reachability until lease expiry (durations unverified for LIFX firmware) | First request is the liveness check; existing lazy-connect + retry machinery already models this |
| Gather-both-legs-then-merge discovery | Simpler to implement and test than concurrent streaming merge | Turns a streaming API into a batch API; doubles worst-case first-device latency; regresses the v1.1 idle-window semantics | Concurrent legs, yield first-wins per serial as found |
| Thread commissioning / border-router management / NAT64 | "Complete" Thread story | That is the border router's and the LIFX app's job; enormous scope, zero-dependency constraint makes it impractical, and Matter stacks exist for it | Document the assumption: devices are already joined and advertised by an existing border router |

## Feature Dependencies

```
Land feat/ipv6-thread-support (b49400b, b88cdb9, 2f884f5)
    └──enables──> IPv6 connections, AAAA parsing, multi-packet mDNS, ephemeral bind,
                  animator frame-socket family
                        └──required by──> merged discover() (broadcast + mDNS legs)
                        │                     └──required by──> find_by_serial() both legs
                        │                     └──feeds───────> find_by_label() (no change needed)
                        └──required by──> find_by_ip() IPv6 literal
                        └──required by──> tm exposure on LifxServiceRecord
                                              └──enhances──> consumer guidance docs

Synthetic multi-packet mDNS tests ──verify──> cross-packet accumulation + follow-up A/AAAA
    (substitute for unavailable fleet-scale hardware; hardware confirmation deferred by decision)

Merged discovery + IPv6 connections + animator fix
    └──required by──> THREAD-01 / SEED-001 revalidation (per device class)
                          └──may retune──> retry floor (200 ms), ack gate (2), streaming rate (20 FPS)
```

### Dependency Notes

- **Everything downstream of the branch:** nothing in this milestone is testable on Thread
  hardware until `feat/ipv6-thread-support` lands; it is the critical path.
- **`find_by_label()` deliberately unchanged:** it keeps the broadcast `GetLabel` trick and
  picks Thread devices up via `discover()`'s mDNS leg (user decision, 2026-08-27).
- **Revalidation last:** SEED-001 needs the whole transport stack in place, and its animation
  arm needs the frame-socket family fix specifically.
- **Synthetic tests are load-bearing:** the overflow/accumulation paths are the claims most
  likely to break at mesh scale and cannot fire with two devices; fleet-scale hardware
  validation is a recorded gap, not a blocker (user decision, 2026-08-27).

## MVP Definition

### Launch With (v2.0)

- [ ] Land `feat/ipv6-thread-support` — critical path for everything else
- [ ] Ephemeral-port bind regression test — credits the IPv4 defect fix in its own right
- [ ] Merged `discover()` (concurrent legs, serial-keyed first-wins, stream-as-found)
- [ ] `find_by_serial()` both legs; `find_by_ip()` IPv6 literal
- [ ] `tm` parsed defensively and exposed on `LifxServiceRecord`
- [ ] Synthetic multi-packet mDNS tests (accumulation + follow-up A/AAAA)
- [ ] SEED-001 revalidation for `MatrixLight` (hardware in hand); measured verdict on the
      200 ms floor, ack gate, and achievable streaming FPS over Thread
- [ ] Broadcast-first consumer guidance docs

### Add After Validation (v2.x)

- [ ] Per-class revalidation for `CeilingLight`, `MultiZoneLight`, `Light` — trigger: each
      planned hardware migration completes
- [ ] Constant retuning (retry floor, gate) *if* MatrixLight measurement shows the WiFi values
      failing on Thread — trigger: SEED-001 evidence, not speculation
- [ ] Fleet-scale hardware confirmation of the overflow paths — trigger: enough devices
      migrated for a border router to overflow a single legacy-unicast reply

### Future Consideration (v3+)

- [ ] Per-transport adaptive flow-control profiles (only if measurement shows one gate cannot
      serve both transports) — keep internal per the locked decision
- [ ] `HevLight`/`InfraredLight` Thread coverage — currently closed as named gaps; reopens if
      Thread-capable hardware of either class ships

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Land the IPv6/Thread branch | HIGH | LOW (built, needs review + land) | P1 |
| Merged `discover()` | HIGH | MEDIUM | P1 |
| Ephemeral-bind regression test | HIGH (16/25 devices on plain WiFi) | LOW | P1 |
| `find_by_serial()` both legs / `find_by_ip()` IPv6 | HIGH | LOW-MEDIUM | P1 |
| Synthetic multi-packet mDNS tests | HIGH (only proof of mesh-scale claims) | MEDIUM | P1 |
| `tm` exposure | MEDIUM | LOW | P2 |
| SEED-001 MatrixLight revalidation | HIGH | HIGH (hardware measurement) | P1 (milestone-defining) |
| Consumer guidance docs | MEDIUM | LOW | P2 |
| Per-class revalidation beyond MatrixLight | MEDIUM | MEDIUM (blocked on migrations) | P3 |

## Competitor Feature Analysis

| Feature | aiolifx | python-matter-server / HA | Our Approach |
|---------|---------|---------------------------|--------------|
| Thread device reach | None (IPv4 broadcast; `ipv6prefix` synthesises link-local from MAC) | Native — Matter is transport-agnostic by design; Thread via border router | mDNS leg with AAAA/ULA preference inside merged `discover()` |
| Transport visibility | None | `NodeDiagnostics.network_type` (diagnostics only) | `LifxServiceRecord.tm`, read-only, undocumented-key-tolerant |
| Multi-source discovery merge | N/A (single source) | Config-flow dedup on serial `unique_id`; later sources update host | Serial-keyed first-wins union of concurrent legs, invisible to callers |
| Sleepy/timing adaptation | N/A | Matter MRP `SII`/`SAI` TXT hints retune per-device retry intervals | No protocol hints exist for LIFX LAN → measure (SEED-001) and adapt internally |
| mDNS implementation | N/A | `zeroconf` dependency | Zero-dependency stdlib parser (existing), extended for IPv6/multi-packet |

## Sources

- [OpenThread Border Router guide](https://openthread.io/guides/border-router); [OTBR codelab](https://openthread.io/codelabs/openthread-border-router); [Thread 1.3.0 white paper](https://www.threadgroup.org/Portals/0/documents/support/Thread1.3.0WhitePaper_07192022_3990_1.pdf); [ot-br-posix SRP advertising proxy (DeepWiki)](https://deepwiki.com/openthread/ot-br-posix/6.3-srp-advertising-proxy) — border router advertisement mechanism (MEDIUM confidence, cross-checked)
- [RFC 6762](https://www.rfc-editor.org/rfc/rfc6762.html); [avahi/avahi#23](https://github.com/avahi/avahi/issues/23) — legacy-unicast single-packet limit, TC-bit behaviour, §5.2 retransmit (MEDIUM)
- [LIFX LAN docs — communicating with a device](https://lan.developer.lifx.com/docs/communicating-with-device) — official TXT keys `id`/`fw`/`p`; `tm` absent from public docs (MEDIUM; `tm` semantics themselves are local-hardware observation only)
- [HomeKit News, 2026-08-25](https://homekitnews.com/2026/08/25/lifx-opens-thread-beta-for-its-existing-matter-over-wi-fi-devices/); [Matter Alpha](https://www.matteralpha.com/news/lifx-opens-beta-to-upgrade-wi-fi-lights-to-thread) — LIFX Thread firmware beta timing; LIFX LAN protocol remains available over Thread (LOW-MEDIUM, press)
- [Google Home Matter discovery primer](https://developers.home.google.com/matter/primer/commissionable-and-operational-discovery); [CSA Matter handbook — Discovery](https://handbook.buildwithmatter.com/how-it-works/discovery/); [matter.js changelog (SII/SAI handling)](https://github.com/matter-js/matter.js/blob/main/CHANGELOG.md) — Matter service types and MRP TXT parameters (MEDIUM)
- [python-matter-server `client.py` / `models/node.py`](https://github.com/home-assistant-libs/python-matter-server) ; [HA `components/matter/api.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/matter/api.py); [HA `components/lifx/config_flow.py` + manifest](https://github.com/home-assistant/core/tree/dev/homeassistant/components/lifx); [`kasa/discover.py`](https://github.com/python-kasa/python-kasa/blob/master/kasa/discover.py); [`aioesphomeapi/model.py`](https://github.com/esphome/aioesphomeapi/blob/main/aioesphomeapi/model.py); [`aiolifx/aiolifx.py`](https://github.com/aiolifx/aiolifx/blob/master/aiolifx/aiolifx.py) — library behaviour, verified in source (MEDIUM)
- [Silicon Labs Thread technology overview](https://docs.silabs.com/openthread/latest/thread-fundamentals/02-thread-technology-overview); [MDPI 2023 Thread performance evaluation](https://www.mdpi.com/2076-3417/13/13/7745) — 250 kbps PHY, tens-of-ms RTT, ~100 kbps single-hop zero-loss ceiling, multi-hop degradation (MEDIUM; not measured on this fleet)
- Local evidence: `feat/ipv6-thread-support` (`b49400b`, `b88cdb9`, `2f884f5`), `scripts/ipv6_thread_probe.py`, PROJECT.md probe findings (25-vs-9 ephemeral-bind measurement, ULA prefixes, `discover()` missing both Thread serials) — HIGH for this fleet

---
*Feature research for: Thread/Matter discovery and control from a client library's perspective (lifx-async v2.0)*
*Researched: 2026-08-27*
