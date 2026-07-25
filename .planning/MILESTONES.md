# Milestones

## v1.1 Wire Reliability (Shipped: 2026-07-26)

**Phases completed:** 4 phases (2–5), 24 plans, 52 tasks
**Closeout:** override_closeout — 13/13 requirements satisfied, 25/25 must-have truths
verified, 7/7 cross-phase connections wired, all four phases Nyquist-compliant. Known
verification overrides: 3 (see STATE.md Deferred Items).

**Delivered:** the library's wire behaviour — discovery coverage, request retries and
animation frame delivery — is now measurably as reliable as the reference clients, with
the asyncio core and public API untouched.

**Key accomplishments:**

- **Discovery re-broadcast (DISC-01..03):** `GetService` re-sent on an escalating
  Photons-shaped schedule inside the discovery window. A 6-round measurement against the
  73-device production fleet moved median single-call coverage from 48/73 to 73/73.
- **Retry schedule reshape (RETRY-01..04):** both `DeviceConnection` request paths
  collapsed onto one shared `_transmit_and_listen()` engine — a single monotonic wall
  deadline, retransmit-while-listening, and shared-queue correlation across GET and ACK.
  Hardware harness: 1.37 → 1.017 packets/request, 62 ms → 12.6 ms median latency, and no
  29 s overruns of a 16 s budget.
- **Animation flow control (ANIM-01..04):** ack-gated frame pacing owned inside the
  animation layer with no consumer-facing toggle. The gated arm won directionally in
  every session ever measured (1.28×–5.25×); certified by operator ruling over a recorded
  statistical FAIL, never presented as a statistical pass (`04-RULING.md`).
- **Latent large-tile bug fixed:** raw 64-pixel colour slicing replaced with row-aligned
  rect offsets, which had garbled frames on any tile width not dividing 64 (Ceiling
  13×26).
- **Reliability documentation (DOCS-01..02):** workaround recipes and inflated 30+ FPS
  claims removed, gen4 wake-tail and streaming-consumer guidance added, and the docs
  build taken from an 8-warning "baseline" to zero warnings under `--strict`, gated in CI.
- **Close-out fixes:** phase 4's validation strategy reconciled (`049902b`) and
  `api.discover()` stopped letting a slow or dead device expire the discovery idle window
  (`3d16822`), both found by the milestone audit's cross-phase integration check.

**Deferred:** SEED-001 Thread/IPv6 revalidation (dormant), PERS-01 persistence mixin,
02-01-SUMMARY.md's missing requirements frontmatter (cross-checked manually), and the
disputed D5-09 docs rule.

---

## v1.0 Ceiling Save-on-Exit (Shipped: 2026-06-12)

**Phases completed:** 1 phases, 1 plans, 3 tasks

**Key accomplishments:**

- `CeilingLight.__aexit__` override that persists in-memory state to `state_file` before `close()`, proven by three emulator-backed TDD tests covering happy-path write, no-op without state_file, and exception-propagation-with-save-failure.

---
