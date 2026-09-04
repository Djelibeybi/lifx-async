---
phase: 11-mdns-hardening
plan: 01
subsystem: network-discovery
tags: [mdns, connectivity, legacy-unicast, asyncio, udp]

requires:
  - phase: 10-land-the-ipv6-thread-branch
    provides: cancellation-safe ephemeral IPv4 mDNS transport and cross-packet record cache
provides:
  - Public getter-only Device.connectivity with exact wifi and thread literals
  - Exact private TXT sentinel mapping propagated through mDNS device construction
  - Connectivity-preserving cached metadata adoption
  - Real loopback proof of direct legacy-unicast receipt on an ephemeral non-5353 port
affects: [11-02, 11-03, 11-04, 11-05, 11-06, phase-13-merged-discovery]

actuals:
  tokens: 3966
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - Getter-only public Literal metadata with a validated private hand-off
    - Descriptive connectivity metadata that does not influence routing or tuning
    - Real loopback datagram proof against the transport-owned socket

key-files:
  created:
    - .planning/phases/11-mdns-hardening/11-PHASE-BASE.txt
  modified:
    - src/lifx/devices/base.py
    - src/lifx/network/mdns/types.py
    - src/lifx/network/mdns/discovery.py
    - src/lifx/network/mdns/transport.py
    - tests/test_devices/test_base.py
    - tests/test_network/test_mdns/test_discovery.py
    - tests/test_network/test_mdns/test_transport.py
    - tests/test_api/test_api_discovery.py

key-decisions:
  - "Connectivity remains descriptive: mDNS sets it after normal device construction, and adoption copies it without changing address, routing, retry, or tuning behaviour."
  - "Task 3 used a temporary uncommitted port-5353 mutation because Phase 10 already implemented the behaviour that the new regression proves."

patterns-established:
  - "Exact mapping: only the private ASCII value 2 becomes thread; all other values become wifi without rejection."
  - "Transport proof: obtain the live socket's selected port, send directly from a second loopback socket, and compare payload plus sender tuple."

requirements-completed: [MDNS-01, MDNS-02]

coverage:
  - id: D1
    description: "Exact private connectivity metadata reaches the public Device property without changing device or network configuration."
    requirement: MDNS-02
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_discovery.py#TestCreateDeviceFromRecord"
        status: pass
    human_judgment: false
  - id: D2
    description: "Direct devices default to WiFi, invalid private values are rejected without mutation, and cached metadata adoption preserves Thread connectivity."
    requirement: MDNS-02
    verification:
      - kind: unit
        ref: "tests/test_devices/test_base.py#connectivity and adopt_cached_metadata tests"
        status: pass
      - kind: integration
        ref: "tests/test_api/test_api_discovery.py#TestDiscoverMdns"
        status: pass
    human_judgment: false
  - id: D3
    description: "The real IPv4 mDNS socket owns a non-5353 ephemeral port and receives a synthetic direct legacy-unicast loopback datagram."
    requirement: MDNS-01
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_transport.py#TestMdnsTransportLegacyUnicast"
        status: pass
      - kind: other
        ref: "uv run --frozen pytest tests/test_network/test_mdns/test_transport.py -q -W error::ResourceWarning"
        status: pass
    human_judgment: false
  - id: D4
    description: "The additive record and Device metadata remain compatible with the existing library surface."
    verification:
      - kind: other
        ref: "uv run --frozen pytest -q (3767 passed, 12 deselected)"
        status: pass
      - kind: other
        ref: "uv run pyright (0 errors)"
        status: pass
    human_judgment: false

duration: 18 min
completed: 2026-08-28
status: complete
---

# Phase 11 Plan 01: Connectivity Tracer and Legacy-Unicast Proof Summary

**Device-level WiFi/Thread classification with exact private metadata mapping, adoption-safe propagation, and real ephemeral-socket legacy-unicast receipt proof**

## Performance

- **Duration:** 18 min
- **Started:** 2026-08-28T07:09:49Z
- **Completed:** 2026-08-28T07:27:53Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added getter-only `Device.connectivity: Literal["wifi", "thread"]`, defaulting every non-mDNS construction path to WiFi and mapping only the exact private sentinel to Thread.
- Preserved connectivity through cached metadata adoption and the supported high-level `discover_mdns()` generator without changing device class, address, port, timeout, or retry configuration.
- Proved with real IPv4 loopback sockets that `MdnsTransport` binds an OS-selected non-5353 port and receives a synthetic datagram sent directly to that owned socket.
- Recorded the immutable pre-implementation Phase 11 base and passed the complete compatibility, lint, formatting, typing, and resource-lifecycle gates.

## Task Commits

Each TDD step was committed atomically:

1. **Task 1: Trace exact private connectivity metadata into a public Device**
   - `fac3429` — `test(mdns): add failing connectivity tracer`
   - `cb1079f` — `feat(mdns): expose device connectivity metadata`
2. **Task 2: Prove defaults, cached-metadata adoption, and high-level propagation**
   - `8177717` — `test(mdns): add connectivity propagation regressions`
   - `4e7ea59` — `feat(mdns): preserve adopted connectivity metadata`
3. **Task 3: Prove the ephemeral socket receives a direct legacy-unicast reply**
   - `562821f` — `test(mdns): prove direct legacy-unicast delivery`
   - `437f812` — `docs(mdns): clarify legacy-unicast transport direction`

## Files Created/Modified

- `.planning/phases/11-mdns-hardening/11-PHASE-BASE.txt` — Immutable 40-character pre-implementation boundary for the Phase 11 diff.
- `src/lifx/devices/base.py` — WiFi default, validated private setter, public property, and adoption propagation.
- `src/lifx/network/mdns/types.py` — Trailing defaulted connectivity field on the service record.
- `src/lifx/network/mdns/discovery.py` — Exact metadata mapping and post-construction propagation to every supported light class.
- `src/lifx/network/mdns/transport.py` — Explicit IPv4 multicast-query and legacy-unicast-reply terminology.
- `tests/test_devices/test_base.py` — Direct default, accepted/rejected setter, and adoption regressions.
- `tests/test_network/test_mdns/test_discovery.py` — Split-record tracer, exact mapping matrix, and routing-neutrality proof.
- `tests/test_network/test_mdns/test_transport.py` — Real ephemeral-port direct loopback receipt regression.
- `tests/test_api/test_api_discovery.py` — High-level `discover_mdns()` connectivity propagation regression.

## Decisions Made

- Connectivity is copied with registry-derived cached metadata so future serial de-duplication cannot silently downgrade a Thread-discovered device to WiFi.
- Connectivity remains observational only; normal product selection and device construction happen first, and no IP-family inference or network tuning was introduced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced an unreachable natural RED with mutation proof**
- **Found during:** Task 3 (Prove the ephemeral socket receives a direct legacy-unicast reply)
- **Issue:** Phase 10 had already implemented the correct ephemeral bind and direct receive path, so the new production-quality regression passed immediately against the baseline.
- **Fix:** Temporarily changed the uncommitted bind to port 5353, confirmed the regression failed at the intended transport boundary, then restored `sock.bind(("", 0))` before committing or running the complete suite.
- **Files modified:** `src/lifx/network/mdns/transport.py` temporarily; no mutation remained in a commit.
- **Verification:** The mutation failed, the restored baseline passed the focused regression, and all 37 transport tests passed with `ResourceWarning` promoted to error.
- **Committed in:** `562821f` contains only the regression; `437f812` contains only the authorised docstring clarification.

---

**Total deviations:** 1 resolved blocking deviation.
**Impact on plan:** No scope expansion or runtime change; mutation testing provided the missing RED evidence for behaviour that pre-dated this plan.

## Issues Encountered

- Restricted sandbox access initially prevented uv cache use and GPG trust-database verification. Approved escalated commands used the existing uv cache and signing key; every commit contains the required GPG signature and DCO trailer.

## Verification

- `217 passed` across the four plan-focused modules with `ResourceWarning` promoted to error.
- `3767 passed, 12 deselected` in the final full frozen suite.
- Ruff check passed; Ruff format reported all targeted files already formatted.
- Pyright passed with `0 errors, 0 warnings, 0 information messages`.
- Added-line privacy audit found no live device serial, MAC address, private infrastructure address, hostname, or raw discovery output.
- Source audit found no port-5353 bind and no multicast membership request in the mDNS transport.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-02 can replace the record cache representation while retaining the exact connectivity mapping and public Device contract established here.
- No blockers; hardware, daemon, multicast routing, and live network state were not used or changed.

## Self-Check: PASSED

- All nine created or modified implementation/test artefacts exist.
- All six task commits exist and the recorded Phase 11 base remains an ancestor of HEAD.
- Coverage metadata classified all four deliverables as automatically covered with passing evidence.

---
*Phase: 11-mdns-hardening*
*Completed: 2026-08-28*
