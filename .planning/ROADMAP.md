# Roadmap: lifx-async

## Milestones

- ✅ **v1.0 Ceiling Save-on-Exit** — Phase 1 (shipped 2026-06-12) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **Post-v1.0: Discovery unification** — Phase 1 (verified 2026-06-13) — archived in `milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`
- ✅ **v1.1 Wire Reliability** — Phases 2–5 (shipped 2026-07-26) — [archive](milestones/v1.1-ROADMAP.md)
- 📋 **Next milestone** — not yet defined (`/gsd-new-milestone`)

## Phases

<details>
<summary>✅ v1.0 Ceiling Save-on-Exit (Phase 1) — SHIPPED 2026-06-12</summary>

- [x] Phase 1: Ceiling Save-on-Exit (1/1 plans) — completed 2026-06-12

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ Post-v1.0: Phase 1 — Unify duplicated discovery loops (verified 2026-06-13)</summary>

Standalone phase from the /simplify review (2026-06-13). Rebuilt `discover_devices()`
on `_discover_with_packet()` with hoisted DoS serial validation and first-wins per-serial
dedup; retired `_parse_device_state_service()`. Review-fix 6/6, security 11/11 closed,
UAT 4/4 including real-hardware validation (regression 0d83deb found and fixed).
5/5 plans complete. Phase directory archived in
`milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`.

</details>

<details>
<summary>✅ v1.1 Wire Reliability (Phases 2–5) — SHIPPED 2026-07-26</summary>

Closed the measured reliability gap against the reference clients (Glowup, Photons) using
the spike-validated blueprints, without changing the asyncio core or the public API.

- [x] Phase 2: Discovery Re-broadcast (2/2 plans) — completed 2026-07-16
- [x] Phase 3: Retry Schedule Reshape (3/3 plans) — completed 2026-07-17
- [x] Phase 4: Animation Flow Control (13/13 plans) — completed 2026-07-17
- [x] Phase 5: Reliability Documentation (6/6 plans) — completed 2026-07-18

13/13 requirements satisfied · 25/25 must-have truths verified · 7/7 cross-phase
connections wired · all four phases Nyquist-compliant.

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) ·
audit: [milestones/v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md)

</details>

### 📋 Next milestone — not yet defined

Run `/gsd-new-milestone` to define scope, requirements and phases. Carried-forward
candidates live in STATE.md under Deferred Items (PERS-01 persistence mixin, THREAD-01 /
SEED-001 Thread-IPv6 revalidation).

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Ceiling Save-on-Exit | v1.0 | 1/1 | Complete | 2026-06-12 |
| 1. Unify duplicated discovery loops | post-v1.0 | 5/5 | Complete | 2026-06-13 |
| 2. Discovery Re-broadcast | v1.1 | 2/2 | Complete | 2026-07-16 |
| 3. Retry Schedule Reshape | v1.1 | 3/3 | Complete | 2026-07-17 |
| 4. Animation Flow Control | v1.1 | 13/13 | Complete | 2026-07-17 |
| 5. Reliability Documentation | v1.1 | 6/6 | Complete | 2026-07-18 |
