# Roadmap: lifx-async

## Milestones

- ✅ **v1.0 Ceiling Save-on-Exit** — Phase 1 (shipped 2026-06-12) — [archive](milestones/v1.0-ROADMAP.md)

## Phases

<details>
<summary>✅ v1.0 Ceiling Save-on-Exit (Phase 1) — SHIPPED 2026-06-12</summary>

- [x] Phase 1: Ceiling Save-on-Exit (1/1 plans) — completed 2026-06-12

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Ceiling Save-on-Exit | v1.0 | 2/5 | In Progress|  |

### Phase 1: Unify duplicated discovery loops

**Goal:** Rebuild `discover_devices()` on top of `_discover_with_packet()` in `src/lifx/network/discovery.py`, removing ~150 near-identical lines that have already drifted. Move the documented DoS protections (serial/broadcast-bit validation, currently only in `discover_devices`) into the shared generator so every discovery caller gets them, and retire the hand-rolled `_parse_device_state_service()` in favour of the protocol layer's `StateService.unpack()`. Identified during the /simplify review of UDP transport mechanics (2026-06-13); the duplicated retry-budget arithmetic in `connection.py` (`_request_stream_impl` vs `_request_ack_stream_impl`) is a candidate follow-up but out of scope for this phase.
**Requirements**: D-01..D-12 (CONTEXT.md decisions); no separate REQUIREMENTS.md IDs for this milestone
**Depends on:** Nothing (first phase of milestone)
**Plans:** 2/5 plans executed
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Extract IdleDeadline timeout helper into network/utils.py + unit tests (D-06)
- [x] 01-04-PLAN.md — Deprecate UdpTransport.receive_many + DeprecationWarning test (D-09, D-12)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-02-PLAN.md — Hoist serial validation + dedup into _discover_with_packet, thin discover_devices, delete _parse_device_state_service (D-01..D-05)
- [ ] 01-03-PLAN.md — Adopt IdleDeadline in mDNS discover_lifx_services + tighten receive() exception routing (D-07, D-08)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 01-05-PLAN.md — Rewrite discovery error tests: retire _parse_device_state_service tests, add generator-level validation/dedup tests (D-10, D-11)

---
*Next milestone: run `/gsd-new-milestone` to define requirements and roadmap.*
