# lifx-async compared with Alessio Palumbo's Go LIFX libraries

Date: 2026-10-17. Alessio Palumbo is a LIFX staff engineer; his personal Go libraries are treated
as the "official unofficial" reference implementations. This note compares them with lifx-async
and, in particular, works out what it would take to provide lifx-onboard's SoftAP onboarding from
lifx-async or a sibling repository.

Every claim below is cited to a file. Go paths are relative to the repo named in the heading;
lifx-async paths are relative to this repository. The clones were read, never executed. Anything
not confirmed in code is marked unverified.

## Summary

- **Protocol and registry layers are at parity.** Both generators consume the same upstream
  `protocol.yml` and `products.json`. lifx-async's generator is the more careful one (bit-run
  packing, open enums, firmware-resolved capabilities); lifxprotocol-go mis-sizes
  `ThreadStateInfo` and lifxregistry-go never consumes `upgrades`. One registry field lifx-async
  ignores and should adopt: `uplight_coords`.
- **At the LAN client layer lifx-async is ahead on transport reliability** (correlation, acks,
  retransmission, ack-gated animation) and device coverage (IPv6, Thread, mDNS, HEV, IR, Mirror).
  lifxlan-go is ahead on **long-running session management**: continuous discovery, endpoint
  migration by serial, liveness, state polling, and device-change events. It also carries
  hardware observations lifx-async lacks: hidden-cell maps for Candle, Ceiling and Luna, a Luna
  orientation map, and sunset soft-off.
- **lifx-maestro** is an application (music analysis, timeline, audio-clocked scheduler). Its wire
  layer is fire-and-forget and weaker than lifx-async's. Two small timing rules are worth
  borrowing; everything else belongs in a sibling app.
- **lifx-onboard** is one 98-byte packet (type 305, not in the official protocol) sent over TLS to
  `172.16.0.1:56700`, wrapped in a seven-phase state machine, wrapped in a lot of host WiFi
  management. The packet, TLS client, helpers, state machine and LAN verification can live in
  lifx-async with no dependencies. The WiFi scan/join backends and the CLI cannot, and should be
  the sibling repo.
- **Two project documents are stale**: AGENTS.md says sensor packets 401/402 are a local quirk;
  upstream `protocol.yml` now defines them and the generator has no injection code. The same is
  true of Thread packets 1200/1201. See "Corrections".

## Sources and versions

| Repo | Head | Date | Notes |
|---|---|---|---|
| lifxprotocol-go | `b173d057` (v0.5.0) | 2026-09-13 | pins LIFX/public-protocol `9289015784bd…` (`cmd/protocol-gen/src/protocol_commit.txt`) |
| lifxregistry-go | `d3c97201` (v0.5.1) | 2026-10-08 | pins LIFX/products `58b8dfa85c86…` (`cmd/registry-gen/src/products_commit.txt`) |
| lifxlan-go | `cf20b81b` (v0.16.0) | 2026-10-11 | requires lifxprotocol-go v0.4.0, lifxregistry-go v0.5.1 (`go.mod`) |
| lifx-maestro | `67ee579` (v0.8.0) | 2026-10-15 | requires lifxlan-go v0.16.0 |
| lifx-onboard | `60b82594` | 2026-10-16 | requires lifxlan-go v0.14.4; pre-1.0 |
| lifx-async | `eb53ca76` (7.11.3) | | this worktree, no local changes |

Other LIFX repos Alessio owns, from `gh api users/alessio-palumbo/repos`: `lifx-emulator` (Go +
Wails virtual lights, develops against sibling checkouts of the three libraries), `hikari` and
`hikari-desktop` (TUI and desktop controllers), `lifx-dash`, `lifx-force`, `lifx-remote`
(Raspberry Pi Zero W remote), and `lifx-command-engine` (a stdin/stdout JSON sidecar that turns
text into command plans, built on `lifxlan-go/pkg/command`). All are applications on top of the
three libraries; none adds protocol capability beyond what is covered below, so they were skimmed
only.

## 1. Protocol layer: lifxprotocol-go vs `src/lifx/protocol/generator.py`

### 1.1 Source of truth

| | lifxprotocol-go | lifx-async |
|---|---|---|
| protocol.yml | Verbatim upstream copy committed at `cmd/protocol-gen/src/protocol.yml` and embedded (`cmd/protocol-gen/main.go:17-21`). `scripts/fetch-latest-protocol.sh` clones depth-1 and records the HEAD; `Makefile` regenerates only when the commit changes. | Downloaded at generation time from `PROTOCOL_URL` (`src/lifx/const.py:182-184`), parsed in memory, never committed (`generator.py:1591-1614`). |
| Provenance in output | `// Source: https://github.com/LIFX/public-protocol@<commit>` plus timestamp (`cmd/protocol-gen/generate/protocol.go:16-20`). | URL only, no commit (`packets.py:1-7`). |

Upstream `protocol.yml` at `main` now defines `sensor` (401, 402) and `thread` (1200, 1201)
categories (lines 1440-1461 of the raw file, fetched 2026-10-17). lifxprotocol-go's
`gen/protocol/packets/sensor.go` and `thread.go` are generated from upstream, not added locally.
lifx-async's `generator.py` likewise has no sensor or thread injection: `grep -nE 'Sensor|Thread'
src/lifx/protocol/generator.py` returns nothing, and `main()` (1786-1873) calls only
`apply_firmware_effect_enum_quirk`, `apply_multizone_application_request_quirk`,
`apply_tile_effect_parameter_quirk`, `apply_tile_state_device_quirk` and the Button/Relay filter.

### 1.2 Generator design

| Aspect | lifxprotocol-go | lifx-async |
|---|---|---|
| Decoder | Reads `enums/fields/unions/packets`; `Field` has `Name/Type/SizeBytes` only, so `size_bits` is ignored (`cmd/protocol-gen/decode/protocol.go:52-56`). | Reads `compound_fields` too (1795-1799); `validate_protocol_spec` rejects bit runs that do not fill whole bytes (1616-1701). |
| Output shape | `gen/protocol/enums/enums.go`, `gen/protocol/packets/{fields,unions,payloads,helpers,<ns>}.go`; field-by-field `encoding/binary` LE (`templates/packets.tmpl`); unions as `[N]byte` with `unsafe.Pointer` accessors (`unions.tmpl`). | `protocol_types.py`, `packets.py`; nested classes per category; `get_packet_class()` (1577). |
| Reserved fields | Public `Reserved1..N` typed by size (`generate/protocol.go:133-158`); reserved enum values dropped (59-77). | Skipped in the dataclass, zero-filled in `pack()` (761-870). |
| Button/Relay | Included (`packets/button.go`, `relay.go`). | Filtered (1703-1745). |
| Enum naming | No prefix stripping: `TileEffectTypeTILEEFFECTTYPEMORPH`, `DeviceServiceDEVICESERVICEUDP` (`enums.go:237-366`). | Prefix stripped (`shared_enum_prefix`, 578-605). |
| Field renames | None beyond camel-casing (`generate/funcs.go`). | `type` to `effect_type` (179-194). |
| Packet renames | Verbatim (`MultiZoneExtendedSetColorZones`, `LightGet`). | Category prefix removed; `ExtendedSetColorZones` to `SetExtendedColorZones`, `LightGet` to `Light.GetColor` (197-225). |
| Effect enums | `MultiZoneEffectType` and `TileEffectType` separate. | Merged `FirmwareEffect` plus synthetic `Direction` (362-435). |
| `TileEffectParameter` | Upstream `Parameter0..7 uint32` (`fields.go:142-152`); sky type in `Parameter0`, cloud saturation and sunset soft-off in `Parameter1` (`lifxlan-go/pkg/messages/matrix.go:118-121,143,165`). | Replaced by `SkyType u8`, `CloudSaturationMin u8`, `CloudSaturationMax u8` with reserved padding (228-265). Byte-compatible with Go's `Parameter1` for values below 256. |
| `TileStateDevice` reserved byte | Kept as `Reserved3` (`fields.go:112-124`). | Replaced by `supported_frame_buffers` (322-359), which drives `TileInfo.requires_frame_buffer` (`devices/matrix.py:155`). |
| Open enums | None; Go enums are plain ints, unknown values pass through and `String()` returns `""`. | `OPEN_ENUMS = {DeviceService, FirmwareEffect, TileEffectSkyType}` with `_missing_` (268-320). |
| Bit fields (`ThreadLinkHealth`) | Mis-generated: 2-bit reserved runs become `[0]byte` and the link-quality fields become full `uint8` (`fields.go:90-102`), so the struct is 9 bytes against a declared 8 and `ThreadStateInfo` would read 33 bytes from a 32-byte payload. Inferred from the struct, not executed. | Packed LSB-first (711-760; `protocol_types.py:450-470`). |

### 1.3 Packet-level diff

Compared `gen/protocol/packets/payloads.go` against the `PKT_TYPE` constants in `packets.py`.

| Packet set | lifxprotocol-go | lifx-async |
|---|---|---|
| Device 2, 3, 14-25, 32-35, 38, 45, 48-53, 58, 59, 223 | yes | yes |
| Light 101-103, 107, 116-122, 142-149 | yes | yes (101/107 renamed) |
| Sensor 401, 402 | yes (upstream) | yes (upstream) |
| MultiZone 501-503, 506-512 | yes | yes |
| Tile 701-703, 707, 711, 715, 716, 718-720 | yes | yes |
| Relay 816-818 | yes | filtered |
| Button 905-907, 909-911 | yes | filtered |
| Thread 1200, 1201 | yes (StateInfo mis-sized) | yes |
| WiFi SoftAP 301-306 | no | no |

Neither library has anything the other lacks apart from the deliberate Button/Relay filter, and
neither defines the undocumented SoftAP family that lifx-onboard needs (section 5).

## 2. Product registry: lifxregistry-go vs `src/lifx/products/`

### 2.1 lifxregistry-go

- Committed `products.json` is embedded (`cmd/registry-gen/main.go:17-21`); only vendor id 1 is
  kept (`decode/registry.go:51-70`). Vendor `defaults` are parsed but never merged into products.
- Output is one `var ProductsByPID = map[int]Product{…}` (`templates/products.tmpl`) with
  `Product{PID, Name, Features, Upgrades}`, `FeatureSet{HEV, Color, Chain, Matrix, Relays, Buttons,
  Infrared, Multizone, TemperatureRange []int, ExtendedMultizone, UplightCoords *UplightCoordinates}`
  and `Upgrade{Major, Minor, Features}` (`gen/registry/products.go:4214-4249`). There are no
  functions in the generated package; capability logic lives in lifxlan-go
  `pkg/device/device.go:358-396`.
- `uplight_coords` is real upstream data. Fetched `products.json` at `master` on 2026-10-17: the
  vendor defaults carry the key, and PIDs 176, 177, 265, 266 have `{x: 7, y: 7}`, PIDs 201, 202
  have `{x: 15, y: 7}`. Go generates `UplightCoords` for exactly those six.
- No hand-maintained product sets.

### 2.2 lifx-async

- `products/generator.py` produces `registry.py` with a `ProductCapability` bitfield,
  `TemperatureRange`, `TemperatureRangeUpgrade`, and `ProductInfo.for_firmware()`, which drops
  `EXTENDED_MULTIZONE` below `min_ext_mz_firmware` and picks the newest reached kelvin upgrade
  (`registry.py:133-181`). `ProductRegistry.load_from_dict()` allows runtime reload (2064-2200).
- The generator reads `defaults.get("features", {})` (`generator.py:136-137, 462-463`), but the
  upstream `defaults` object is flat (keys `hev, color, chain, …, uplight_coords,
  extended_multizone`, confirmed from the fetched file), so the merge is a no-op. It is harmless
  today only because every product spells out every key. Go has the same latent bug.
- `uplight_coords` is not parsed anywhere (`grep -rn uplight_coords src/lifx` is empty). The
  Ceiling uplight zone is a hand table, `CEILING_LAYOUTS` (`products/quirks.py:41-78`, zone 63 on
  8x8 and 127 on 16x8, with a TODO). `x + y * width` reproduces both values from the upstream
  coordinates.
- Hand sets that have no Go equivalent: `CEILING_LAYOUTS`, `MIRROR_LAYOUTS` and `MIRROR_ZONE_MAP`
  (136-249), `VERTICAL_THEME_PRODUCTS` (288), `MOVE_AS_MORPH_PRODUCTS` (308),
  `SKY_EFFECT_MIN_FIRMWARE_MAJOR = 4` with `supports_sky_effect()` (86-104).
- Detection order in `devices/detection.py:22-66`: Ceiling PID, Mirror PID, matrix, multizone,
  infrared, HEV, relay/button-only raises, else `Light`.

### 2.3 Comparison

| Concern | Go (registry plus lifxlan-go consumer) | lifx-async |
|---|---|---|
| Vendor defaults merge | not merged | no-op merge (same latent bug) |
| Firmware `upgrades` | emitted, never consumed; `grep -rn Upgrades pkg internal cmd` finds no reader; `SetProductInfo` uses the base range (`device.go:378-389`) | `for_firmware()` applied at `devices/base.py:1099` |
| Unknown product kelvin | 1500-9000, `HasColor: true` (`device.go:398-406`), also when the range has fewer than two entries | 2500-9000 (`const.py:119-120`) |
| Kelvin validation on write | rejects values outside the base product range with `ErrInvalidState` (`pkg/controller/state.go:156-161`) | `set_kelvin` checks only the global 1000-10000 bounds (`devices/light.py:504-506`); `min_kelvin`/`max_kelvin` are exposed (1086-1113) but not enforced |
| Uplight position | registry `UplightCoords` (`pkg/device/light_parts.go:30-37`) | hand `CEILING_LAYOUTS` |
| Hidden or padding cells | hand tables in `pkg/device/surface.go:197-235`: Candle hides 2, 3, 4 with a row-0 offset of 1; Ceiling 8x8 hides 0, 1, 6, 7, 56, 57, 62, 63; Ceiling 16x8 hides 0, 1, 14, 15, 112, 113, 126, 127; Luna hides 0, 6, 28, 34 | no equivalent; every w×h cell is painted |
| Orientation groups | PID 55 uses Tile axes, PIDs 219/220 (Luna) their own (`orientation.go:36-60`) | orientation applied only when `has_chain` (`devices/matrix.py:1625-1644`) |
| Vertical-theme, move-as-morph | none; `pkg/themes` takes a user-supplied `Axis` (`themes.go:28-33`) | `VERTICAL_THEME_PRODUCTS`, `MOVE_AS_MORPH_PRODUCTS` |
| Mirror zone map | none | `MIRROR_ZONE_MAP` |
| SKY firmware gate | none | `supports_sky_effect` |
| Taxonomy | `DeviceType{Light, Switch, Hybrid}` × `LightType{SingleZone, MultiZone, Matrix}`; multizone checked before matrix (`device.go:391-395`) | class hierarchy; matrix before multizone; switches excluded |

## 3. LAN client: lifxlan-go vs lifx-async network and device layers

### 3.1 Framing

- `internal/protocol.Header` exposes only the `res_required` and `ack_required` bits
  (`header.go:92-115`); the frame-address connection bit lifx-async reads for `connectivity` is
  not modelled.
- `pkg/protocol.Message.NewMessage` sets protocol 1024, addressable, origin 0; `SetTarget` sets
  tagged iff the target is all zero (`message.go:22-74`). `UnmarshalBinary` fails on an unknown
  payload type (line 125) and `Client.Receive` silently drops it (`client.go:170-173`). lifx-async
  routes unknown types through `StateUnhandled` (`network/connection.py:42`).

### 3.2 `pkg/client`

| Feature | lifxlan-go | lifx-async |
|---|---|---|
| Socket | one `ListenUDP` on `0.0.0.0:0` for everything (`client.go:102-105`) | socket per `DeviceConnection` (`connection.py:281`), separate discovery and Animator sockets |
| Source id | fixed per client, default 2, must be greater than 1 (`client.go:42, 86-93`) | random per request in [2, 0xFFFFFFFF] (`network/utils.py:7-16`) |
| Broadcast target | subnet-directed on the first up+broadcast IPv4 interface, or by name/index/exact address (`client.go:271-330`); `RefreshBroadcastTarget()` (203-235) | no interface-pinning API (transport not read in detail) |
| IPv6 | none (`client.go:306`) | IPv4 and IPv6 with zone ids (`api.find_by_ip`) |
| Receive loop | blocking, 1024-byte buffer, malformed skipped (148-178) | background receiver task (`connection.py:614`) |
| mDNS | none | `network/discovery/mdns/`, `discover_mdns` |

### 3.3 `pkg/controller`

| Feature | lifxlan-go | lifx-async |
|---|---|---|
| Lifecycle | `New()` broadcasts GetService and rediscovers every 500 ms (`controller.go:18, 126-131, 233-246`); options `WithDiscoveryPeriod`, `WithHFStateRefreshPeriod` (10 s), `WithLFStateRefreshPeriod` (2 min), `WithPreflightHandshakeTimeout` (5 s) (`option.go`) | one-shot `discover()`; process-wide sweep coordinator (`network/discovery/coordinator.py`); no polling |
| Session | created on first `StateService(UDP)`; endpoint is source IP plus advertised port (`controller.go:311-324`, `endpoint.go:988-995`) | `DeviceConnection` per device, lazy open |
| Endpoint migration | same serial at a new IP/port is updated in place, `DeviceChangeAddress` event fires, state is refreshed, replies from the old epoch are dropped (`endpoint.go:997-1037`, `docs/network-transitions.md`) | none; a device keeps its constructor IP |
| Preflight | GetInfo, Label, Version, LightGet, HostFirmware, Location, Group, WifiInfo resent every 1 s up to 5 s; adds `TileGetDeviceChain` or `MultiZoneExtendedGetColorZones` by type, and probes both when the PID is unknown (`session.go:842-909`) | `connect()`/`ensure_capabilities()` fetch once (`devices/base.py:1099-1140`); unknown products fall back to `Light` |
| Polling | high-frequency 10 s: LightGet, GetPower, plus ExtendedGetColorZones and MZ GetEffect or TileGetEffect and one TileGet64 per 64 px per chain (`device.go:609-642`); low-frequency 2 min: label, firmware, location, group, wifi (648-665); switches poll RelayGetPower (667-681) | none; on demand, semi-static values cached without expiry |
| Liveness | session terminated after `max(30 s, 5 × min(HF, LF))` of silence (`controller.go:72-90`, `session.go:667-679`) | none |
| Ack and correlation | none. `send` stamps target and a wrapping uint8 sequence and returns after the write (`session.go:531-553, 640-642`); inbound is routed by serial only (`controller.go:305-335`); `SetAckRequired` is never called; `SetResponseRequired(true)` only on the SetLabel, SetLocation, SetGroup and SetEffect builders (`messages.go:69, 88, 107`, `multizone.go:83`, `matrix.go:214`). `docs/light-parts.md`: "sends are not ACKs". | `(source, sequence, serial)` correlation with per-request queues, retransmit gaps `0.2, 0.3, 0.4, 0.5, …` (`const.py:54`), 16 s budget (`const.py:42, 48`; `connection.py:860-1000`); writes set `ack_required` (1173-1214) |
| Retry | none for sends; `RestoreOptions.Attempts` blindly repeats whole rounds 120 ms apart (`snapshot.go:216-220, 307-342`) | transport level |
| Rate limiting | none; `minInterval = 1 ms` in the deprecated matrix effects (`pkg/matrix/effects.go:20`) | none; the Animator ack-gates instead |
| Ping | `Controller.Ping` via EchoRequest with a 64-bit counter (`session.go:555-617`) | no helper found in `devices/` (not exhaustive) |
| Events | `SubscribeDevices` channel of Added/Updated/Removed with a `DeviceChange` bitmask (`events.go:646-960`) | none |
| Snapshot and restore | `CaptureStateSnapshot` waits for observation coverage of the light and every zone or pixel block (`snapshot.go`, `snapshot_observations.go`); `RestoreStateSnapshot` restores colours then power, power first when off (`snapshot.go:364-430`) | `effects/conductor.py` prior-state restore for participants only; `DeviceStateManager` in `effects/state_manager.py` |
| SetState | validates hue 0-360, sat/bri 0-100, kelvin against the product range, duration within uint32 ms; colour sent as `LightSetWaveformOptional` SAW with one cycle, then `DeviceSetPower`/`LightSetPower` (`state.go:67-215`, `messages.go:17-57`) | `Light.set_color` and friends; `DeviceGroup` gather fan-out (`api.py:332+`) |
| Light parts | `SetLightPartColor`/`SetLightPartPower`/`GetLightPartState` for main, uplight, all: capture the full physical state, merge, resend the whole frame (`light_parts.go:992-1127`, `light_part_power.go`); uplight soft-off emulated by brightness 0 plus a remembered value (`planPartPower` 1415+) | `CeilingLight.uplight/downlight`, `MirrorLight.front/back`, `ComponentMatrixLight` with `Pending` (`devices/ceiling.py`, `mirror.py`, `component/light.py`) |

### 3.4 `pkg/device`

| Feature | lifxlan-go | lifx-async |
|---|---|---|
| Identity | `Serial [8]byte`, `SerialFromHex` (`device.go:66-95`); `LocationID`/`GroupID [16]byte` as UUID text (97-208) | `Serial` in `protocol/models.py`; user-facing values always `str` |
| MAC | none (header comment only) | `get_mac_address()` with the 3.x minor ≥ 70 rule, memoised per firmware (`devices/base.py:1027-1061`) |
| WiFi signal | `round(10·log10(signal))`, RSSI if negative, SNR if 4..24 (`device.go:210-253`) | same derivation, with dB vs dBm chosen by firmware ≤ 2.77 (`devices/base.py:172-189`) |
| Firmware | `"%d.%d"` string (`session.go:735`), unused for capabilities | ints, drive `for_firmware`, MAC and SKY gate |
| Colour | `Color{Hue 0-360, Sat/Bri 0-100 float64, Kelvin uint16}`, rounded to integer percent on read (`color.go:858-860`) | `color.HSBK` floats 0.0-1.0 |
| Matrix geometry | first tile's width/height applied to every chain member (`device.go:411-462`) | per-tile `TileInfo` with `user_x/user_y` and `supported_frame_buffers` (`matrix.py:60-190`), `geometry.py` |
| Surface | `SurfaceFromDevice` rows with `Offset`/`HiddenCols`, 16x8 capsule reshape for 201/202, chain tiles side by side ignoring `user_x/y` (`surface.go:49-110`); `VisibleZoneCount` | `Canvas`, `tile_position_to_pixels()` |
| Orientation | `NearestOrientation(pid, x, y, z)` with Tile and Luna maps; logical/physical rotations (`orientation.go`) | `nearest_orientation()` and LUTs, only for `has_chain` |
| Selectors | serial, label, group, location, all (`selector.go`) | `find_by_*`, groupings, `DeviceGroup.filter_by_*` |
| Effect state | `MultizoneEffect`/`MatrixEffect` with `Known`, `InstanceID`, `RemainingDuration`, palette; `SkyType` from `Parameter0` (`effect.go`) | `MultiZoneEffect`/`MatrixEffect` with `cloud_saturation_*` |
| Switch, relay, button | full (`device.go:289-292, 524-604`; `messages.go:134-174`) | out of scope |
| HEV, IR, ambient, Thread, reboot, wifi firmware | none in `pkg/` | all present |
| Label | UTF-8, no NUL, ≤ 32 bytes (`messages.go:110-123`) | same (`devices/base.py:1222-1227`) |

### 3.5 `pkg/messages` wire rules

| Rule | lifxlan-go | lifx-async |
|---|---|---|
| Extended multizone chunking | 82 per packet; single chunk `APPLY`; several chunks all `NO_APPLY` followed by an extra empty `APPLY_ONLY` (`multizone.go:13, 26-52`) | 82 per packet, all but the last `NO_APPLY`, the last `APPLY`; `APPLY_ONLY` rejected for writes (`devices/multizone.py:1348-1435`). Different conventions, both consistent with `APPLY_ONLY` discarding carried colours. |
| Writes over 64 pixels | Set64 into buffer 1 with duration 0, then `CopyFrameBuffer` 1→0 with the transition (`matrix.go:28-61, 222-233`); requires `64 % width == 0` (`matrix_sequence.go:49-51`) | identical (`devices/matrix.py:1154-1200`), gated on `requires_frame_buffer` |
| Set64 timing | none; back-to-back, no ack (`session.go:537-552`); `docs/matrix-streaming.md` pushes pacing to the caller | `set64` ack-required and retransmitted (`matrix.py:947-952`); Animator gate of one probe per frame, gate at two outstanding, 1 s expiry (`animation/flow.py:47-59`) |
| Frame-buffer preload | `SetMatrixFrameAnimation` (deprecated) one hidden buffer per frame; `NewMatrixFrameSequence` streams | `copy_frame_buffer()` exposed; no preload helper |
| Firmware effects | Move direction in `Parameter1` (`multizone.go:62-75`); Off, Flame, Morph (≤ 16 colours), Clouds (`Parameter1` min saturation default 50, clamped to 100 although the comment says 0-255), Sunrise, Sunset with `softOff` in `Parameter1` (`matrix.go:63-168`); random `Instanceid` | `set_move_effect`, `set_effect`, `set_morph_effect`; no sunset soft-off (grep finds none) |

### 3.6 Effects, themes, misc packages

- `pkg/effects`: 16 registered effects (comet, sparkle, scanner, solid, gradient, gradient_drift,
  palette_sweep, sweep, waterfall, rockets, snake, worm, wave, concentric_frames, flow, ring;
  `registry.go:40-70`) plus color_cycle and breathe (`temporal.go`). `Runner` sleeps
  `frame.Duration`/`Step` with no ack (`runner.go:36-75`). `AdaptFrameToSurface` (`adapt.go`).
  lifx-async: 27 effects (`effects/registry.py:278-643`), Conductor with overlap and restore,
  ack-gated Animator, prebaked packet generators.
- `pkg/themes`: `Theme{Palette, Layout gradient/steps/solid, Axis}`, `Plan`, `PlanWithOptions`
  with a `BrightnessPolicy`, `PlanParts`, `MaxFrameCells = 65536`, JSON themes, no built-in
  library. lifx-async: 379-row library (`theme/data.py`), `apply_theme`, `apply_mood`,
  `animate_mood`.
- `pkg/matrix`: deprecated blocking effects. `pkg/command`: natural-language command parser with
  no lifx-async equivalent. `pkg/iterator`: range helpers.

### 3.7 Concurrency

Go: one goroutine per session, one controller receive goroutine, `sendMu` keeps multi-packet
batches contiguous (`session.go:482-483, 524-528`), inbound channel of 10 that drops when full
(`session.go:446`, `controller.go:327-334`). lifx-async: asyncio, receiver task per connection,
per-request queues, gather fan-out, no `TaskGroup` for 3.10 compatibility.

## 4. lifx-maestro

A Go desktop app (Wails) and CLI that analyses a song, generates a JSON lighting timeline, and
plays it against LIFX devices on the audio clock, with a microphone-reactive Live mode. The README
states it intentionally has no AI generation; "generation" is rule-based choreography.

### 4.1 What it has that lifx-async does not

- **Offline music analysis** via a Python subprocess with librosa 1.0.0 (`analyzer/analyze.py`,
  `internal/analysis/analysis.go:127-131`): beat tracking, RMS energy, calm/balanced/energetic
  dynamics, intro/build/drop/breakdown/outro sections, low/mid/high streams with onset accents.
- **Realtime analysis** over 500 ms windows at a 100 ms hop (`internal/live/engine.go:13-16`),
  in Python or an experimental pure-Go FFT port (`internal/audiodsp/`).
- **Timeline format** (`internal/timeline/timeline.go:11-60`): `{name, duration_ms,
  events[{time_ms, target, action, params}]}` with five actions (power_on, power_off, set_color,
  set_zone_colors, set_matrix_colors). No cues, lanes, groups, loops or tempo map; targets are
  selector strings resolved to serials at generation time.
- **Audio-clocked scheduler** polling every 2 ms (`internal/scheduler/scheduler.go:33-37,
  71-76`); `perform` uses the decoder position as the clock (`internal/perform/perform.go:107`,
  `internal/audio/player.go:134-139`). No drift model, no per-device offsets.
- **Live mode** with a one-slot latest-wins queue per target (`internal/live/dispatcher.go:94-110`)
  and intensity-driven pacing (`internal/live/generator.go:153-161`).
- A desktop editor, MP3 playback, a master brightness fader.

### 4.2 Wire layer

All writes are fire-and-forget through lifxlan-go `Controller.Send`: no acks, no retry, no rate
limit (`internal/devices/lifx.go:238-253`; lifxlan-go `session.go`, `message.go`). Four
unordered worker goroutines dispatch events (`internal/playback/playback.go:92-120`). Matrix
chains receive the same frame on every tile (`lifx.go:133-134`, admitted in the README). Nothing
in this layer should be imported.

### 4.3 Timing rules worth borrowing

| Rule | Value | Citation |
|---|---|---|
| Fade clipped to the gap before the next write on the same target | yes | `internal/generation/normalize.go:30-49` |
| Writes shorter than this are dropped | 20 ms | `normalize.go:9, 43-46` |
| Beat rise | `min(style, gap/4)`, floor 35 ms | `internal/effects/effects.go:183-208` |
| Restore fade and attempts | 500 ms, 2 tries 120 ms apart | `internal/devices/lifx.go:21-29` |
| Settle window before re-capturing prestate after a restore | 5 s | `lifx.go:24-29, 186-197` |
| Brightness floor | ≤ 0 sent as 1 % | `playback.go:310-315` |

The first two and the settle window are small, pure, and relevant to lifx-async's
`Conductor` and `DeviceStateManager`, especially given the Get64 trailing-write lag recorded in
AGENTS.md. Music analysis, the timeline format, the scheduler and Live mode belong in a sibling
application that drives `Animator.send_frame()` or `AnimatorWriter.stage()`.

Unverified: lifxlan-go `pkg/effects` internals; whether `styles.Style.OffsetMS` is consumed;
the 16 kHz mic capture figures are README-only.

## 5. lifx-onboard (SoftAP onboarding)

Surveyed at commit `60b82594` (2026-10-16), module `go 1.27`, depends on `lifxlan-go v0.14.4` and
`lifxprotocol-go v0.4.0` plus `golang.org/x/sys` and `golang.org/x/term` (`go.mod`). Pre-1.0
(`README.md`).

### 5.1 What it does

A factory-fresh or reset LIFX device advertises an open WiFi network whose SSID starts with `LIFX`
and ends with the last six hex characters of the device serial, for example
`LIFX Candle Color 8274eb` (`scanner/scanner.go` `APFromSSID`, `README.md`). lifx-onboard:

1. scans the host's WiFi for such SSIDs (or takes an SSID or serial from the caller),
2. joins that SoftAP with the host's own WiFi interface,
3. waits until `172.16.0.1:56700` accepts a TCP connection,
4. opens a TLS connection to it and writes one LIFX message, type 305 `WifiSetAccessPoint`,
5. forgets the SoftAP, disconnects from it and returns the host to its original network,
6. optionally polls a LAN discovery client until the device reappears on the home LAN.

Everything except the one packet is host WiFi management. That is why the library is cgo and
platform code heavy: 52 Go files, about 7,300 lines, of which `internal/wire/` (the packet) is
under 100 lines.

### 5.2 The wire protocol (the only LIFX-specific part)

Packet 305 (`0x131`) is not in the official `protocol.yml`. lifx-onboard implements it from the
third-party documentation in lifxjs `Protocol.md` and tserong's `lifx-hacks/onboard.py`
(`internal/wire/doc.go`, `README.md` "Protocol" section). Both sources were fetched and agree
with the Go implementation.

Payload, 98 bytes, little-endian (`internal/wire/wifi.go`, golden-byte test
`internal/wire/wifi_test.go:18`):

| Offset | Size | Field | Values |
|---|---|---|---|
| 0 | 1 | `interface` | 0 unknown, 1 SOFT_AP, 2 STATION. Onboarding sends 2. |
| 1 | 32 | `ssid` | UTF-8, NUL padded, silently truncated at 32 bytes |
| 33 | 64 | `password` | UTF-8, NUL padded, silently truncated at 64 bytes |
| 97 | 1 | `security` | 1 OPEN, 2 WEP_PSK, 3 WPA_TKIP_PSK, 4 WPA_AES_PSK, 5 WPA2_AES_PSK, 6 WPA2_TKIP_PSK, 7 WPA2_MIXED_PSK |

Header: the standard 36-byte LIFX header with protocol 1024, addressable set, origin 0, tagged
unset, and the target set to the device serial derived from the SSID
(`lifxlan-go/pkg/protocol/message.go:24` `NewMessage`, `softap/softap.go` `SendSetAccessPoint`).
Total on-wire message is 134 bytes (`softap/softap_test.go:116`). The target is "largely
advisory" because the device only ever sees its own AP traffic (`softap/softap.go` comment).
Neither `res_required` nor `ack_required` is set and nothing is read back: the library writes the
bytes and closes the socket (`softap/softap.go`). tserong's script behaves the same way and notes
that after onboarding the bulb stops accepting TCP on 56700.

Transport (`softap/softap.go` `Dial`):

- TCP (`tcp4`) to `172.16.0.1:56700` (`DefaultAddr`), 10 s dial timeout.
- TLS with certificate verification disabled (the device presents a self-signed certificate),
  minimum TLS 1.2 by default.
- `LegacyTLS` forces TLS 1.0 only with cipher `TLS_RSA_WITH_AES_256_CBC_SHA` "for devices
  running pre-2020 firmware". The CLI exposes this as `--legacy-tls` (`cmd/lifx-onboard/common.go:55`).

Defaults applied before sending (`options.go` `defaults`): an empty password forces `SecurityOpen`;
a non-empty password with no explicit security becomes `SecurityWpa2AesPsk`; a secured mode with an
empty password is rejected with `ErrMissingCredentials`.

lifxjs also documents the neighbouring undocumented packets in the same family: 301
`GetWifiState`, 302 `SetWifiState`, 303 `StateWifiState`, 304 `GetAccessPoints`, 306
`StateAccessPoint` (interface, ssid[32], security, strength u16, channel u16). lifx-onboard
implements none of them; only 305 is needed for the handoff. Whether current firmware still
answers 304/306 is unverified.

### 5.3 Serial derivation

The SoftAP SSID carries only the last three bytes of the MAC. The library prepends the LIFX OUI
`d0:73:d5` to reconstruct both the BSSID and an 8-byte serial (`scanner/scanner.go` `LIFXOUI`,
`APFromSSID`). `onboard.ParseSerial` accepts a full 12-hex serial with or without separators, or
just the trailing six hex characters, and strips the OUI if present (`onboard_by_ssid.go`
`ParseSerial`). lifx-async's `Serial.from_string` already accepts the separator forms
(`src/lifx/protocol/models.py:116`) but has no suffix-only form and no OUI constant.

### 5.4 Host WiFi management (the bulk of the code)

Abstractions in `scanner/scanner.go`:

- `Scanner.Scan(ctx, ScanOptions{MinRSSI, IncludeNonLIFX}) -> []AP` and `Interface()`.
- `Joiner.Join(ctx, AP)` and `Joiner.RejoinHome(ctx, ssid, password)`.
- Optional capability interfaces discovered by type assertion: `CurrentNetworkReporter.CurrentSSID`,
  `NetworkForgetter.Forget`, `Disassociator.Disassociate`. The Joiner is consulted before the
  Scanner (`rejoin.go` `wifiBackends`, the 2026-10-16 commit).

Platform backends:

| OS | Scan | Join / rejoin | Forget | Current SSID | Disassociate | Source |
|---|---|---|---|---|---|---|
| macOS (default build) | `system_profiler SPAirPortDataType -json` (cached up to ~30 s, no RSSI/BSSID) | `networksetup -setairportnetwork` | `networksetup -removepreferredwirelessnetwork` | not available | not available | `scanner/scanner_darwin.go`, `scanner/joiner_darwin.go`, `scanner/default_darwin_nocorewlan.go` |
| macOS (`-tags corewlan`, cgo) | CoreWLAN `scanForNetworksWithSSID:includeHidden:` (active scan, RSSI, BSSID) | `networksetup` (kept for parity) | `networksetup` | CoreWLAN `CWInterface.ssid` | CoreWLAN `disassociate` | `scanner/scanner_darwin_corewlan.go`, `scanner/default_darwin_corewlan.go` |
| Linux | `nmcli -t -f SSID,BSSID,SIGNAL device wifi list` (an `iw dev <if> scan` scanner exists but is not the default) | `nmcli device wifi connect` / `nmcli connection up` | `nmcli connection delete id` | `nmcli -t -f ACTIVE,SSID device wifi` | not available | `scanner/scanner_nmcli_linux.go`, `scanner/scanner_linux.go`, `scanner/joiner_linux.go` |
| Windows | `wlanapi.dll` `WlanScan` + `WlanGetAvailableNetworkList` (raw struct parsing, no cgo) | `WlanSetProfile` + `WlanConnect` with generated profile XML | `WlanDeleteProfile` | `WlanQueryInterface` | `WlanDisconnect` | `scanner/wlan_windows.go`, `scanner/wlan.go` |
| other | `ErrUnsupportedPlatform` | | | | | `scanner/scanner_other.go` |

macOS specifics that dominate the design:

- macOS redacts SSIDs from any process not launched by LaunchServices as an app with Location
  Services granted. The CLI therefore ships as `LifxOnboard.app` and, when exec'd from a shell,
  re-launches itself through `open -W -n -g`, relaying stdin/stdout/stderr through FIFOs and the
  environment through a 0600 file so the password never appears in `ps`
  (`cmd/lifx-onboard/launch_darwin.go`). The bundle needs `NSLocationWhenInUseUsageDescription`,
  `NSLocalNetworkUsageDescription`, `LSUIElement`, and the
  `com.apple.security.personal-information.location` entitlement; ad-hoc signing suffices
  (`scripts/bundle.sh`, `scripts/entitlements.plist`).
- `onboard.RequestMacOSLocationAccess()` pumps the run loop for up to 15 s waiting for the
  CoreLocation prompt (`location_darwin_corewlan.go`).
- On macOS 26 `networksetup -getairportnetwork` reports "not associated" even when connected, so the
  join is never verified by SSID; TCP reachability of `172.16.0.1:56700` is the ground truth
  (`scanner/joiner_darwin.go` `Join` comment, `onboard_by_ssid.go` `realWait`).
- `networksetup` exits 0 on failure, so output is grepped for "could not find network", "failed to
  join", "error:", "not associated" (`networksetupFailureMessage`).
- Tahoe rejects passwordless joins to WPA networks even with the credential in the keychain
  (`RejoinHome` comment), hence `--rejoin-ssid` and `LIFX_ONBOARD_REJOIN_PASSWORD`.
- Forcing a join races the OS auto-join and fails with `-3900 tmpErr`, so the library prefers to
  wait `AutoJoinWait` (10 s, counted from when the host leaves the SoftAP) for the OS to reconnect
  on its own, and keeps whatever network the OS chose (`rejoin.go` `waitForAutoJoin`,
  `rejoinHome`).

### 5.5 The state machine

Phases, in order, with their event types (`onboard.go`, `events.go`, `onboard_by_ssid.go`):

| Phase | What happens | Retry and timeout defaults (`options.go`) | Events |
|---|---|---|---|
| scan | `Scanner.Scan` until a matching AP appears | `FindTimeout` 30 s, `FindPoll` 2 s | `EventScanning`, `EventDiscovered` |
| join | `Joiner.Join(ap)` | retried for `FindTimeout` because a freshly reset device may not be advertising yet | `EventJoining`, `EventJoined` |
| wait | plain TCP dial of `172.16.0.1:56700` until it accepts; aborts early with `ErrLeftSoftAP` if the host is seen on another network | `WaitTimeout` 30 s, `WaitPoll` 1 s | `EventWaitingForSoftAP`, `EventOnSoftAP` |
| dial | TLS handshake | `DialTimeout` 10 s | `EventDialing` |
| configure | write packet 305, close | none | `EventConfigured` |
| rejoin | forget SoftAP, disassociate, then try targets in order: explicit `RejoinSSID`; the original network (auto-join wait first); the home network handed to the device | `RejoinTimeout` 30 s per target, `RejoinPoll` 2 s, `AutoJoinWait` 10 s | `EventRejoining`, `EventRejoined` |
| verify | poll `LANSender.GetDevices()` until the serial appears at an address other than `172.16.0.1` | `VerifyTimeout` 60 s (0 disables), `VerifyPoll` 1 s | `EventVerifying`, `EventVerified` |

`EventFailed{Serial, Phase, Err}` is emitted on any failure. Events go to a caller-supplied
buffered channel and are dropped, never blocked on, when it is full (`events.go`). `Result` carries
`Serial`, `Verified`, `Took`, `Phase` and `Err` (`onboard.go`).

Recovery: any failure after the join runs `recoverHost`, which forgets the SoftAP, disassociates and
rejoins with a budget of `RejoinTimeout × targets + AutoJoinWait`, and deliberately keeps running
after context cancellation so Ctrl-C never strands the host on the device's SoftAP (`rejoin.go`
`recoverHost`, `context.WithoutCancel`).

Verification pitfall encoded in `onHomeLAN` (`onboard.go`): the LAN client keeps discovering while
the host sits on the SoftAP, so the device can be recorded at `172.16.0.1` before it has joined the
home network. A sighting at the SoftAP address must not count as verified.

Three entry points (`onboard.go`, `onboard_by_ssid.go`, `bulk.go`):

- `Onboard(ctx, Options)`: scan then onboard the first (or `Target`) AP.
- `OnboardBySSID(ctx, OnboardBySSIDOptions)`: caller supplies the SSID, a serial, or its last six
  hex characters. A full SSID skips the scan entirely, which is the only path that works on macOS
  without Location Services.
- `BulkOnboard(ctx, BulkOptions)`: repeated scan loop; onboarding is strictly serial because joining
  changes global host WiFi state, but verification of already-configured devices is interleaved and
  drained after the loop. `Targets` is an allow-list so other people's devices in setup mode nearby
  are ignored; `MaxDevices` caps attempts; `StopWhenIdleFor` ends the loop after a quiet period.
  A never-seen target is reported with `PhaseScan` and `ErrNoDevicesFound`.

The LAN dependency is a one-method interface, `LANSender.GetDevices() []device.Device`
(`sender.go`), so the onboarding module never sends UDP itself.

### 5.6 CLI contract (`cmd/lifx-onboard/`)

Commands `ssid`, `auto`, `bulk`, `scan` (`main.go`). Password sources, in order: `--password-stdin`,
`LIFX_ONBOARD_PASSWORD`, no-echo TTY prompt; never a plain flag so it stays out of shell history
(`common.go` `readPassword`). Shared flags: `--home-ssid`, `--security`, `--iface`, `--legacy-tls`,
`--no-verify`, `--verify-timeout`, `--dial-timeout`, `--rejoin-ssid`, `--find-timeout`,
`--rejoin-timeout`, `--json`, `-v` (`common.go:51-63`). `--json` emits NDJSON records with
`time`, `type`, `serial`, `ssid`, `bssid`, `rssi`, `addr`, `interface`, `timeout_s`, `took_s`,
`phase`, `error`, `verified`, `aps` (`output.go`). Exit codes map to the failing phase: 0 ok, 1
failure, 2 usage, 3 scan, 4 join, 5 wait, 6 dial, 7 configure, 8 rejoin, 9 verify, 130 interrupted
(`main.go`).

### 5.7 Test strategy

61 Go tests. The FSM is tested with fake `Scanner`/`Joiner` implementations and a
`dialFunc`/`waitFunc` seam that bypasses TLS (`onboard.go` `onboardWithDial`,
`onboard_by_ssid.go` `onboardBySSIDWith`). The softap package is tested against an in-process TLS
server with a self-signed certificate that captures the raw bytes (`softap/softap_test.go`
`newFakeAP`). Platform parsers are tested from fixtures (`scanner/testdata/`) and the Windows
struct decoding is build-tag free so it runs everywhere (`scanner/wlan.go`). The CLI "doubles as
the hardware test harness" (`cmd/lifx-onboard/main.go` doc comment).

### 5.8 What lifx-async has today

Nothing. `grep -rniE 'softap|accesspoint|onboard|172\.16\.0\.1' src/lifx` returns no matches,
there is no `ssl` or `SOCK_STREAM` use anywhere under `src/lifx`, and the generated packet table
contains the documented WiFi packets only (16 to 19, `src/lifx/protocol/packets.py:1375-1378`).
`Serial` has no OUI constant and no suffix-only parser.

## 6. Providing lifx-onboard's functionality from Python

### 6.1 Where the seam falls

lifx-onboard already draws the line in the right place: one small protocol module, one TLS
client, a pure state machine, and a set of OS-specific WiFi backends behind two interfaces. The
first three are dependency-free and asyncio-friendly; the backends are not.

| Piece | lifx-onboard source | Belongs in | Why |
|---|---|---|---|
| Packet 305 and the security/interface enums | `internal/wire/wifi.go` | lifx-async, as a generator quirk alongside the existing ones in `src/lifx/protocol/generator.py` | Pure protocol, 98 bytes, same header. |
| SoftAP TLS client | `softap/softap.go` | lifx-async, new `lifx.network.softap` or `lifx.onboard` | `asyncio.open_connection(..., ssl=ctx)` and `ssl.SSLContext` are stdlib. TLS 1.0 with `AES256-SHA:@SECLEVEL=0` loads on this machine (Python 3.14.7, OpenSSL 3.5.8), so a `legacy_tls` option is reproducible. |
| Serial and SSID helpers (`LIFXOUI`, `APFromSSID`, `ParseSerial`) | `scanner/scanner.go`, `onboard_by_ssid.go` | lifx-async, extend `Serial` in `src/lifx/protocol/models.py` | Small, pure, reusable by any front end. |
| State machine, events, results, retry and recovery policy | `onboard.go`, `bulk.go`, `rejoin.go`, `events.go` | lifx-async, `lifx.onboard`, with `Scanner` and `Joiner` as `typing.Protocol`s the caller must supply | No OS calls of its own; every platform touch goes through the two interfaces. Testable exactly as the Go code is, with fake backends and a fake TLS server. |
| LAN verification | `verify` in `onboard.go`, `LANSender` | lifx-async | `discover()` and `find_by_serial()` already exist; the `onHomeLAN` rule (ignore sightings at `172.16.0.1`) must be kept. |
| Host WiFi scan/join/forget/current-SSID backends | `scanner/*_darwin*.go`, `*_linux.go`, `wlan_windows.go` | sibling repo | Needs subprocesses (`networksetup`, `system_profiler`, `nmcli`), `ctypes` against `wlanapi.dll`, and for an unredacted macOS scan either pyobjc's CoreWLAN and CoreLocation bindings (a dependency) or an app bundle launched by LaunchServices. None of that belongs in a zero-dependency library. |
| CLI, NDJSON output, exit codes, macOS relaunch-through-`open` trick, bundle script | `cmd/lifx-onboard/`, `scripts/` | sibling repo | Application concerns. |

Recommendation: put the protocol, TLS client, helpers, state machine and verification into
lifx-async as `lifx.onboard` with the two backend protocols left abstract, and build the sibling
repo as the thing that supplies real backends and the CLI. That mirrors lifx-onboard's own split
(`LANSender` in one direction, `Scanner`/`Joiner` in the other) and keeps lifx-async
installable with no dependencies. A Home Assistant or other integration that already knows the
SoftAP SSID can then onboard with lifx-async alone, because the full-SSID path never scans.

### 6.2 Behaviours worth copying verbatim

These are the hard-won rules in the Go code that a rewrite would otherwise rediscover on hardware:

- Treat TCP reachability of `172.16.0.1:56700` as "joined", never the OS's reported SSID
  (`scanner/joiner_darwin.go`, `onboard_by_ssid.go` wait phase).
- Retry the join itself for `FindTimeout`, not just the scan, because a freshly reset device
  takes a while to raise its SoftAP (`onboard.go` `joinAP`).
- Forget the SoftAP from saved networks and disassociate before rejoining, otherwise the OS
  auto-join waits for the SoftAP to come back (`rejoin.go` `forgetSoftAP`, `leaveSoftAP`).
- Prefer the OS auto-join over a forced join; count the auto-join budget only from when the host
  has actually left the SoftAP; accept whatever network the OS picked (`rejoin.go`
  `waitForAutoJoin`, `rejoinHome`).
- Rejoin targets in order: explicit override, original network, home network handed to the device
  (`rejoin.go` `rejoinTargets`).
- Run host recovery even after cancellation, with a bounded budget (`rejoin.go` `recoverHost`).
- During verification, ignore the device if it is seen at the SoftAP address (`onboard.go`
  `onHomeLAN`).
- Keep the password out of argv and out of `ps`: stdin, env, or no-echo prompt only
  (`cmd/lifx-onboard/common.go`, `launch_darwin.go`).
- Never block on a slow event consumer; drop instead (`events.go`). In asyncio the natural
  equivalent is a bounded `asyncio.Queue` with `put_nowait` and a dropped-event counter, or a
  callback.
- Bulk mode is serial per device but interleaves verification (`bulk.go`).

### 6.3 Open questions to settle on hardware before committing to an API

- Which current products still expose a SoftAP and accept 305 over TLS. tserong's notes are from
  the Original and Color 1000 era; lifx-onboard's README example is a Candle Color. Thread and
  Matter-capable products may commission differently. Unverified either way; the test fleet can
  answer it with a factory reset of one device per generation.
- Whether TLS 1.2 is accepted by every firmware that still SoftAPs, or whether `legacy_tls` is
  needed more often than "pre-2020" suggests (`softap/softap.go` comment).
- Whether packets 304 `GetAccessPoints` and 306 `StateAccessPoint` (lifxjs `Protocol.md`) still
  work. If they do, a Python implementation could let the device scan for the home network and
  report security and signal, removing the guesswork in the `--security` flag.
- What the device does with an SSID or password longer than the field: both Go and tserong
  truncate silently. A Python API should reject instead.

## 7. Consolidated adoption list for lifx-async

Ordered by value to the library. Each item cites the Go source it comes from.

1. **Derive the Ceiling uplight zone from `uplight_coords`** (upstream `products.json`;
   lifxregistry-go `decode/registry.go:12-27`) and retire `CEILING_LAYOUTS`
   (`src/lifx/products/quirks.py:41-78`). `products/generator.py` ignores the key today.
2. **Hidden-cell maps** for Candle (2, 3, 4 with a row-0 offset), Ceiling corners and Luna
   (lifxlan-go `pkg/device/surface.go:197-235`). lifx-async paints every cell. Hardware-verify
   first; these are Alessio's observations.
3. **Luna (219/220) orientation axis map** (`orientation.go:36-60`); lifx-async applies
   orientation only to PID 55.
4. **Enforce the product kelvin range on writes**, as `pkg/controller/state.go:156-161` does.
   `min_kelvin`/`max_kelvin` are already exposed; this worktree's branch name suggests it is in
   progress.
5. **Sunset `softOff`** via `Parameter1 = 1` (`pkg/messages/matrix.go:143-168`). Unverified on
   firmware.
6. **Endpoint migration by serial** with stale-reply rejection (`endpoint.go`,
   `docs/network-transitions.md`). This is the piece of lifxlan-go's session model with the most
   relevance to long-running consumers such as Home Assistant.
7. **Unknown-product shape probing** (`TileGetDeviceChain` plus `ExtendedGetColorZones`;
   `session.go:869-909`) instead of falling back to `Light`.
8. **Fade-to-gap clipping and a sub-20 ms drop rule** (lifx-maestro
   `internal/generation/normalize.go`) as a pure helper for caller-supplied schedules.
9. **Restore settle window** (lifx-maestro `internal/devices/lifx.go:24-29`) on
   `DeviceStateManager.capture_state`.
10. **Echo-based ping** with payload correlation (`session.go:555-617`).
11. **Record the upstream commit hash** in generated headers (`generate/protocol.go:16-20`).
12. **Fix the no-op vendor-defaults merge** (`products/generator.py:136-137, 462-463`).
13. Note the alternative extended-multizone flush convention (empty trailing `APPLY_ONLY`,
    `multizone.go:46-50`) in the `set_extended_color_zones` docstring in case last-chunk-APPLY
    ever misbehaves.

## 8. What lifx-async has that the Go libraries lack

1. Request/response correlation, acks and retransmission (`network/connection.py:860-1000`,
   `const.py:42-58`). lifxlan-go is fire-and-forget with serial-only routing.
2. Ack-gated animation flow control (`animation/flow.py`).
3. Firmware-resolved capabilities (extended-multizone minimum firmware, kelvin upgrades;
   `products/registry.py:133-181`). Go never reads `Upgrades`.
4. MAC derivation rule (`devices/base.py:1027-1061`).
5. IPv6 and Thread (`find_by_ip`, `connectivity`, `get_thread_info`); Go is IPv4-only and
   mis-sizes `ThreadStateInfo`.
6. mDNS discovery.
7. HEV, infrared, ambient light, wifi firmware and reboot methods.
8. Per-tile geometry and `user_x/user_y` chain layout (`geometry.py`).
9. Mirror component model and zone map.
10. `supported_frame_buffers` from `TileStateDevice`.
11. Open-enum discipline (`OPEN_ENUMS`).
12. 379-entry theme library, moods, 27 software effects, Conductor overlap and restore.
13. WiFi RSSI unit chosen by firmware boundary.
14. SKY firmware gate.
15. An embedded emulator test suite (lifx-emulator-core). Alessio's `lifx-emulator` is a desktop
    app, not an in-process test dependency.

## 9. Corrections to project documents

- **AGENTS.md "sensor packets" bullet** (line 476) says packets 401/402 "are not in the official
  protocol.yml" and are added by the generator. Upstream `protocol.yml` at `main` defines a
  `sensor` category with both, and `generator.py` contains no sensor injection. The bullet should
  say they come from upstream.
- **Thread packets** 1200/1201 likewise come from upstream now (`thread` category at line 1454 of
  the raw file); there is no generator quirk left to remove.

## 10. Unverified items

- Go `ThreadStateInfo` unmarshal failure is inferred from struct sizes, not executed.
- Whether lifx-async exposes any `EchoRequest` helper (no hit in `devices/`, not exhaustive).
- Hardware correctness of Go's hidden-cell tables, the Luna map and sunset `softOff`.
- lifx-async transport broadcast address selection (`network/transport.py` not read in detail).
- Which current products still SoftAP, and whether TLS 1.2 is universally accepted (section 6.3).
- lifxlan-go `pkg/effects` internals; `styles.Style.OffsetMS` consumption in lifx-maestro.
