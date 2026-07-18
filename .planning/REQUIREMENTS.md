# Requirements: lifx-async v1.1 Wire Reliability

**Defined:** 2026-07-16
**Source:** Spike series 001–005 (`.planning/spikes/`, blueprints in
`./.claude/skills/spike-findings-lifx-async/`)

## v1.1 Requirements

### Discovery

- [x] **DISC-01**: `discover_devices()` re-broadcasts `GetService` on an escalating
  schedule (Photons-shaped gaps) within the discovery window, preserving existing serial
  validation and first-wins dedup

- [x] **DISC-02**: Duplicate `StateService` responses (devices answer each broadcast ~2×;
  re-broadcasts multiply this) never cause duplicate device yields

- [x] **DISC-03**: Hardware validation over repeated rounds: median per-round coverage of
  the production fleet equals full coverage (baseline: 48/73)

### Animation flow control

- [x] **ANIM-01**: The Animation layer paces frame delivery via ack-gated flow control
  (ack probe per frame, gate on outstanding acks, latest-frame-wins) as internal library
  behaviour — no downstream-facing toggle

- [x] **ANIM-02**: The zero-allocation prebaked-template send path is preserved; the
  ack-capable transport is a proper animator facility (no private-reaching)

- [x] **ANIM-03**: Hardware validation resolved by operator ruling: the cross-device
  paired-sweep criterion ran once per the 7-device healthy-radio matrix roster and
  honestly FAILed its aggregate statistical bar on 2026-07-17 (5/5 valid gate sessions
  FAILed, 2 INCONCLUSIVE — 04-UAT-SWEEP.json), while the gated arm won directionally in
  every session ever measured across the phase (8 devices, 2 radio generations, ~10
  sessions, ratios 1.28x–5.25x). By operator ruling (verbatim reply "2", 2026-07-17) the
  cross-device directional dossier is accepted as satisfying the requirement's intent —
  an acceptance over a recorded FAIL, never a statistical pass. Completed by the
  operator's visual smoothness verdict on My Office Ceiling Capsule (04-13 Task 4).

- [x] **ANIM-04**: Flow control covers the large-matrix framebuffer path (multi-packet
  frames + buffer swap), hardware-validated on the 04-12 sweep's three ceiling-class
  devices: every sent gated frame matched the chain-dims-derived row-aligned
  packets/frame expectation on every round, CopyFrameBuffer ack RTT evidence was
  recorded on every gated round (the D4-04 ack-probe attachment confirmed on all three
  devices). My Office Ceiling Capsule is 16×8 zones (128 zones; 26 in × 13 in physical —
  supersedes the earlier units mix-up, operator correction verbatim, 2026-07-17).
  Completed by the operator's visual geometry verdict on the Capsule (04-13 Task 4).

### Retry schedule

- [x] **RETRY-01**: First-attempt window floored (~200 ms) with escalating retransmit
  gaps replacing the 31 ms-doubling shape — no duplicate packets on healthy networks

- [x] **RETRY-02**: Responses arriving between attempts are consumed immediately (listen
  during backoff — no blind sleeps)

- [x] **RETRY-03**: The caller's `timeout` is honoured as wall time — a 16 s budget can
  never take 29 s

- [x] **RETRY-04**: Shared-queue correlation across all issued sequences is preserved:
  late replies accepted, duplicates silently discarded

### Documentation

- [x] **DOCS-01**: Gen4 power-save wake-tail behaviour documented (sub-250 ms; when apps
  may want periodic polling)

- [x] **DOCS-02**: Streaming-consumer guidance (LedFx pattern): what the animation layer
  now handles, what consumers should not reimplement

## Future Requirements

- **THREAD-01** (seed: SEED-001): When LIFX Thread firmware lands (expected soon),
  revalidate all v1.1 wire-reliability behaviour over Thread/IPv6 — discovery model,
  retry timing, ack-gate tuning, and an `AF_INET6` transport path. WiFi-derived constants
  must not be assumed to transfer.

- **PERS-01** (deferred from v1.0): extract `state_file` save/load into a reusable mixin

- **API-01** (deferred from Phase 5, 2026-07-17): fix three behavioural defects in
  `src/lifx/api.py` that the Phase 5 documentation audit surfaced and confirmed against
  source, but which fall outside that phase's "no code changes" boundary — each needs code,
  tests, and 100% branch patch coverage:
  (a) `_fetch_location_metadata`/`_fetch_group_metadata` docstrings promise graceful
  failure handling that does not exist — no logger, and `asyncio.gather()` without
  `return_exceptions=True`, so one offline device aborts the whole `organize_by_location()`
  / `organize_by_group()` call (the `CollectionInfo | None` branches are dead code);
  (b) `find_by_label(exact_match=True)` promises "at most one device" but yields every
  match, and LIFX labels are not unique;
  (c) `organize_by_location`/`organize_by_group` cache on `is None` only, so a warm cache
  silently ignores `include_unassigned` and drops the "Unassigned" group;
  (d) `DiscoveredDevice.create_device()` (`src/lifx/network/discovery.py:102-122`) — a bare
  `except Exception: return None` swallows every failure, so an out-of-scope device (a LIFX
  Switch, via `LifxUnsupportedDeviceError` from `detection.py:33`) and a transient network
  failure are **indistinguishable to the caller**: both yield `None`. Its docstring's
  `Raises:` promises `LifxDeviceNotFoundError`, `LifxTimeoutError` and `LifxProtocolError`
  — none can escape the catch-all — and `Returns:` omits `None` despite the `Device | None`
  signature. Decide first whether the catch-all is intended; then either narrow it so real
  errors propagate, or correct the docstring to describe what it does. **Do not correct the
  docstring alone** — that would document a swallow-everything catch as intended.
  Decide per defect whether to fix the behaviour or correct the promise.

## Out of Scope

| Exclusion | Reason |
|-----------|--------|
| Switching from asyncio to threading | Disproven (Spike 004): wire-equivalent at idle; collapses under CPU load |
| Keepalive daemon | Disproven (Spike 001): zero idle-related loss; gen4 wake tail is a docs footnote |
| Glowup-style query retries (3× fresh 2 s deadlines) | Disproven (Spike 002): 40% failure at 50% loss |
| Downstream-facing flow-control toggles | Delivery strategy is the animation library's decision (user, 2026-07-16) |
| mDNS discovery changes | Spike 005's finding applies to UDP broadcast discovery |
| Increasing animation FPS | ~20 FPS is a platform ceiling (WiFi/Set64), not a client defect |

## Traceability

<!-- Filled by roadmap creation (2026-07-16). -->

| REQ-ID | Phase | Status |
|--------|-------|--------|
| DISC-01 | Phase 2 | Complete |
| DISC-02 | Phase 2 | Complete |
| DISC-03 | Phase 2 | Complete |
| RETRY-01 | Phase 3 | Complete |
| RETRY-02 | Phase 3 | Complete |
| RETRY-03 | Phase 3 | Complete |
| RETRY-04 | Phase 3 | Complete |
| ANIM-01 | Phase 4 | Complete |
| ANIM-02 | Phase 4 | Complete |
| ANIM-03 | Phase 4 | Complete |
| ANIM-04 | Phase 4 | Complete |
| DOCS-01 | Phase 5 | Complete |
| DOCS-02 | Phase 5 | Complete |
