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
| 1. Ceiling Save-on-Exit | v1.0 | 1/1 | Complete | 2026-06-12 |

### Phase 1: Unify duplicated discovery loops

**Goal:** Rebuild `discover_devices()` on top of `_discover_with_packet()` in `src/lifx/network/discovery.py`, removing ~150 near-identical lines that have already drifted. Move the documented DoS protections (serial/broadcast-bit validation, currently only in `discover_devices`) into the shared generator so every discovery caller gets them, and retire the hand-rolled `_parse_device_state_service()` in favour of the protocol layer's `StateService.unpack()`. Identified during the /simplify review of UDP transport mechanics (2026-06-13); the duplicated retry-budget arithmetic in `connection.py` (`_request_stream_impl` vs `_request_ack_stream_impl`) is a candidate follow-up but out of scope for this phase.
**Requirements**: TBD
**Depends on:** Nothing (first phase of milestone)
**Plans:** 0 plans

Plans:

- [ ] TBD (run /gsd-plan-phase 1 to break down)

---
*Next milestone: run `/gsd-new-milestone` to define requirements and roadmap.*
