# Roadmap: lifx-async

## Milestones

- ✅ **v1.0 Ceiling Save-on-Exit** — Phase 1 (shipped 2026-06-12) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **Post-v1.0: Discovery unification** — Phase 1 (verified 2026-06-13) — archived in `milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`
- 🚧 **v1.1 Wire Reliability** — Phases 2–5 (in progress)

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

### 🚧 v1.1 Wire Reliability (In Progress)

**Milestone Goal:** Close the empirically-measured reliability gap between lifx-async and
the reference clients (Glowup, Photons) using the spike-validated blueprints
(`.claude/skills/spike-findings-lifx-async/`), without changing the asyncio core or
public API.

**Hardware validation note:** DISC-03, ANIM-03, and ANIM-04 are validated against real
hardware (7 quiesced test devices + 73-device production fleet) as UAT-style steps —
the emulator cannot model per-AP broadcast delivery, WiFi loss, or power-save. These runs
complement the emulator-backed automated suite; they cannot run in CI. The automated
tests must independently satisfy CI's 100% branch patch coverage gate. Repeated rounds
are mandatory for discovery/loss claims — single rounds mislead.

- [x] **Phase 2: Discovery Re-broadcast** - Re-send `GetService` on an escalating Photons-shaped schedule inside the discovery window so one call finds the whole fleet
- [x] **Phase 3: Retry Schedule Reshape** - Floor the first-attempt window, listen during backoff, and honour the caller's timeout as wall time
- [x] **Phase 4: Animation Flow Control** - Ack-gated frame pacing owned by the animation layer, covering both the direct and large-matrix framebuffer send paths (completed 2026-07-17)
- [x] **Phase 5: Reliability Documentation** - Gen4 wake-tail footnote and streaming-consumer guidance for the new wire behaviour (completed 2026-07-18)

## Phase Details

### Phase 2: Discovery Re-broadcast

**Goal**: A single `discover_devices()` call reliably finds the entire fleet, including on multi-AP networks where any one broadcast is best-effort per AP
**Depends on**: Nothing (first phase of milestone; builds on the shipped `_discover_with_packet()` unification)
**Requirements**: DISC-01, DISC-02, DISC-03
**Success Criteria** (what must be TRUE):

  1. Within one discovery window, `GetService` is re-broadcast on an escalating Photons-shaped schedule (gaps ≈ 0.6, 1.2, 1.8, 2.0, 2.0 s), capped by the discovery window — observable in emulator tests as multiple broadcasts at the expected gaps
  2. Every discovered device is yielded exactly once, even though devices answer each broadcast ~2× and re-broadcasts multiply response volume (~600–850 responses on a 73-device fleet)
  3. Existing callers of `discover_devices()` work unmodified — serial validation and first-wins dedup behaviour are preserved, and the idle-deadline early exit still functions with responses arriving across the whole window
  4. Hardware UAT: over repeated rounds (≥6) against the 73-device production fleet, median per-round coverage equals full coverage — 73/73 (baseline: 48/73 from a single broadcast)

**Plans**: 2/2 plans executed

Plans:

- [x] 02-01-PLAN.md — Photons-shaped re-broadcast interleave in `_discover_with_packet()`, tests-first with branch-matrix coverage (DISC-01, DISC-02)
- [x] 02-02-PLAN.md — DISC-03 UAT harness (`uat_rounds.py`) + 6-round production-fleet measurement vs the 48/73 baseline

### Phase 3: Retry Schedule Reshape

**Goal**: Request retries stop firing duplicates on healthy networks, consume responses the moment they arrive, and never exceed the caller's timeout
**Depends on**: Nothing (independent of Phase 2 — touches `connection.py` request paths only)
**Requirements**: RETRY-01, RETRY-02, RETRY-03, RETRY-04
**Success Criteria** (what must be TRUE):

  1. On a healthy network a request sends exactly one packet: the first-attempt window is floored at ~200 ms with escalating retransmit gaps replacing the 31 ms-doubling shape (baseline: 1.37 packets/trial at zero loss)
  2. A response arriving between retransmits completes the request immediately — no blind sleeps stall arrived responses (observable as request latency ≈ RTT on slow-responding devices, not RTT plus a jitter sleep)
  3. A request honours its `timeout` as wall time — a 16 s budget can never take 29 s, even under heavy loss with retransmits and backoff (all waiting counts against the budget)
  4. Shared-queue correlation across all sequences issued for a logical request is preserved: late replies from earlier retransmits are accepted, duplicates are silently discarded, never surfaced as protocol errors
  5. Existing callers of `DeviceConnection.request()` (including `timeout`/`max_retries` arguments) work unmodified

**Plans**: 3/3 plans executed

Plans:

- [x] 03-01-PLAN.md — RED: branch-matrix retry tests (test_connection_retry.py) + TestRetryTimeoutBudget wall-time rewrite (RETRY-01..04, Wave 0)
- [x] 03-02-PLAN.md — GREEN: REQUEST_RETRANSMIT_GAPS + shared `_transmit_and_listen` engine in connection.py, branch-coverage audit (RETRY-01..04)
- [x] 03-03-PLAN.md — Optional zero-loss packets/trial hardware measurement on the gen4 downlight vs the 1.37 spike baseline (RETRY-01/02 evidence)

### Phase 4: Animation Flow Control

**Goal**: Streaming animations pace themselves via ack-gated flow control decided inside the animation layer, so frame delivery never starves other traffic to the device — invisible to downstream consumers
**Depends on**: Nothing (independent subsystem — animation layer; ordered after the smaller self-contained wins; hardware loss measurements use single-shot probes so Phase 3 is not a prerequisite)
**Requirements**: ANIM-01, ANIM-02, ANIM-03, ANIM-04
**Success Criteria** (what must be TRUE):

  1. The animator gates frame delivery on outstanding ack probes (ack flag on the first packet of each frame, gate at 2 outstanding, ~1 s expiry, latest-frame-wins — dropped frames are skipped, never queued) as internal behaviour: consumers call the same Animator API with no flow-control toggle
  2. The zero-allocation prebaked-template send path is preserved, and ack collection runs through an ack-capable transport that is a proper animator facility — no reaching into private transport internals
  3. Hardware UAT (cross-device paired sweep — resolved by operator ruling): the operator-approved cross-device paired-sweep criterion (`04-SWEEP-DESIGN.md`) ran once per device over the 7-device healthy-radio matrix roster and honestly FAILed its aggregate statistical bar on 2026-07-17 — 5 of 5 valid gate sessions FAILed, 2 INCONCLUSIVE, in the lossiest ambient network window measured anywhere in this phase (`04-UAT-SWEEP.json`: gated pooled loss 13.7%–38.9% vs blind 25.9%–94.7%). The gated arm nonetheless won directionally in every one of the 8 sessions (ratios 1.28x–3.38x), consistent with every prior session measured across the phase (~10 sessions, 2 radio generations, ratios 1.28x–5.25x: 04-GAP-INVESTIGATION.json, 04-UAT-TILES.json, 04-UAT-TILES-paired-run1-FAIL.json, 04-UAT-SWEEP.json). **Resolution is BY OPERATOR RULING** (verbatim reply "2", 2026-07-17) accepting this cross-device directional dossier as satisfying the requirement's intent — an acceptance over a recorded FAIL, never a statistical pass; the FAIL evidence stands unmodified. The operator's visual smoothness verdict on the Capsule (04-13 Task 4) completes ANIM-03.
  4. Hardware UAT (large-matrix framebuffer path): the framebuffer-path evidence captured in the 04-12 sweep sessions of the three ceiling-class devices (Makerspace Ceiling, Playroom Ceiling, My Office Ceiling Capsule) stands — every sent gated frame matched the chain-dims-derived row-aligned packets/frame expectation on every round (`packet_shape_ok: true` in all per-device JSONs), every gated round recorded ≥ 1 CopyFrameBuffer ack RTT sample (medians 50.1–50.2 ms on the two 8×8 ceilings, 150.0–150.2 ms on the Capsule's 16×8 chain — the D4-04 ack-probe attachment confirmed on all three). My Office Ceiling Capsule is **16×8 zones (128 zones, 8 rows of 16; 26 in × 13 in physical)** — supersedes the earlier units mix-up that attributed physical inches to the zone grid (operator correction verbatim, 2026-07-17). The operator's visual geometry verdict on the Capsule (04-13 Task 4) completes ANIM-04.

**Plans**: 11/13 plans executed (04-06, 04-07 superseded — never execute)

Plans:
**Wave 1**

- [x] 04-01-PLAN.md — RED: row-aligned large-tile chunking (13×26) + probe-seam branch-matrix tests in test_packets.py (ANIM-02, ANIM-04, Wave 0)
- [x] 04-02-PLAN.md — RED: AckGate branch matrix (test_flow.py), mock-socket/ack-injection fixtures, animator gating + deterministic emulator tests (ANIM-01, ANIM-02, Wave 0)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-03-PLAN.md — GREEN: row-aligned chunking fix + FLAGS_OFFSET/ACK_REQUIRED_FLAG + probe_template_index seam in packets.py (ANIM-02, ANIM-04)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 04-04-PLAN.md — GREEN: flow.py AckGate + ack-gated send_frame + additive AnimatorStats fields, branch-coverage audit + full-suite regression (ANIM-01, ANIM-02)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 04-05-PLAN.md — UAT harness uat_ack_stream.py: shipped-Animator streaming + single-shot query prober, fixed exit-code contract (ANIM-03, ANIM-04)

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 04-06-PLAN.md — ANIM-03 Tiles UAT: operator visual-smoothness checkpoint (human gate) — Task 1 (headless measurement, superseded twice: 0% gate then 04-10's amended absolute gate, which FAILed twice) now owned by 04-11's paired headless run; Task 2 SUPERSEDED — 04-12 Task 5 (its intended owner) was skipped on the sweep's aggregate FAIL, and visual ownership passed to 04-13 Task 4, approved by the operator's dual verdict; do not execute this plan

**Wave 6** *(blocked on Wave 5 completion)*

- [ ] 04-07-PLAN.md — ANIM-04 Ceiling Capsule UAT: power-on, 13×26 [corrected 2026-07-17: the Capsule is 16×8 zones, 128 zones, 26 in × 13 in physical] framebuffer-path measurement with CopyFB ack RTTs + operator visual checkpoint (human gate) — SUPERSEDED IN FULL: Task 1 covered by the Capsule's 04-12 sweep session; Task 2's intended owner, 04-12 Task 5, was skipped on the sweep's aggregate FAIL, and visual ownership passed to 04-13 Task 4, approved by the operator's dual verdict; do not execute this plan
- [x] 04-08-PLAN.md — Gap closure (ANIM-03): spike 003 sample-size forensics + threshold-free 5-arm hardware investigation (control/shipped/replica/FPS-sweep/fallback) with per-event evidence

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 04-09-PLAN.md — Gap closure (ANIM-03): pre-declared statistical analysis (04-GAP-ANALYSIS.md) + blocking operator routing decision (fix / recalibrate / rerun / investigate)

**Wave 8** *(blocked on Wave 7 completion)*

- [x] 04-10-PLAN.md — Gap closure (ANIM-03): apply the operator-approved recalibration (ROADMAP criterion 3, REQUIREMENTS ANIM-03, harness gate 9.0%/round + 5.0% pooled) + fresh 3-round Tiles evidence under the amended gate

**Wave 9** *(blocked on Wave 8 completion)*

- [x] 04-11-PLAN.md — Gap closure (ANIM-03): paired-relative criterion redesign (operator routing "2") — evidence-derived design brief + reproducible stats runner, blocking operator approval of the complete final wording, paired ambient/gated/blind harness rework, fresh paired Tiles evidence with honest PASS/FAIL/ENV-ERROR/INCONCLUSIVE routing

**Wave 10** *(blocked on Wave 9 completion)*

- [x] 04-12-PLAN.md — Gap closure (ANIM-03 + ANIM-04): operator-directed cross-device retarget — Tiles flaky-radio ruling recorded verbatim, cross-device paired sweep over 7 healthy-radio matrix devices (Tiles II reference-only), blocking operator approval of the complete criteria 3+4 / ANIM-03+04 wording, harness sweep generalisation (serial-first resolution, profile auto-selection, chain-dims-derived packet expectation, as-found restoration), honest per-device + aggregate evidence, and the single consolidated visual checkpoint (Capsule, smoothness + geometry — supersedes 04-06 Task 2 and 04-07). Aggregate outcome FAILed (5/5 valid gate sessions FAIL); Task 5 (the consolidated visual checkpoint) was SKIPPED per its own routing. Visual ownership moved to 04-13 Task 4 by operator ruling (verbatim "2", 2026-07-17).

**Wave 11** *(blocked on Wave 10 completion)*

- [x] 04-13-PLAN.md — Gap closure (ANIM-03 + ANIM-04, phase-closing): record the operator ruling (verbatim "2", 2026-07-17 — accept the eight-device directional dossier over the honestly-FAILed sweep bar), blocking operator approval of the complete final wording, verbatim application with the Capsule dims correction (16×8 zones / 26 in × 13 in physical), the single Capsule visual round with dual smoothness + geometry verdict (inherits the skipped 04-12 Task 5). Outcome: operator approved with the observation recorded (geometry PASS, smoothness = documented latest-frame-wins stutter under 20 FPS saturation, not freeze/crawl) — ANIM-03/ANIM-04 flipped complete; Phase 4 plans done, ready for phase-level verification

### Phase 5: Reliability Documentation

**Goal**: Users can find accurate guidance on the wire behaviour the library now guarantees and the device quirks it deliberately does not paper over
**Depends on**: Phase 4 (DOCS-02 documents the shipped animation-layer behaviour; also draws on Phases 2–3 outcomes)
**Requirements**: DOCS-01, DOCS-02
**Success Criteria** (what must be TRUE):

  1. A reader can find documented gen4 power-save wake-tail behaviour (sub-250 ms) including when an application may want periodic state polling for minimal first-command latency — and that the library itself deliberately ships no keepalive daemon
  2. A streaming consumer (LedFx pattern) can find guidance stating what the animation layer now handles (ack-gated pacing, latest-frame-wins) and what consumers must not reimplement (their own acks, keepalives, or frame retry wrappers)
  3. The documentation builds cleanly (`uv run zensical build`) with the new content included and linked from the relevant device/animation pages

**Plans**: 6/6 plans executed

Plans:
**Wave 1**

- [x] 05-01-PLAN.md — DOCS-01 wake-tail section in troubleshooting.md (pinned anchor) + FAQ entry + stale discovery/retry fixes (audit #5–#8)
- [x] 05-03-PLAN.md — Stale-content fixes: advanced-usage.md (#9–#11), architecture/overview.md (#12–#13), CLAUDE.md hygiene (F2); surface F1/F3 as findings

**Wave 2** *(blocked on 05-01 — links to its wake-tail anchor)*

- [x] 05-02-PLAN.md — DOCS-02 streaming-consumer section in animation.md + own stale fixes (#1–#4) + animation/ceiling-lights cross-links (D5-02)

**Wave 3** *(gap closure — 05-VERIFICATION.md blocker CR-01 + operator-opted residuals D5-12..D5-15)*

- [x] 05-04-PLAN.md — Version-neutral wire-behaviour claims (CR-01/D5-12) + residual accuracy closure (WR-01..WR-08, IN-01..IN-03, F1 per D5-13/D5-14/D5-15)

**Wave 4** *(second gap closure — 05-VERIFICATION.md truth #23 + operator-opted residuals D5-16..D5-18, D5-20; D5-19 deferred as API-01)*

- [x] 05-05-PLAN.md — Async-for discovery examples (truth #23/D5-16) + full doc-side residual closure (D5-17) + the three narrow source-docstring overrides (connection.py:64, api.py:620 per D5-18; discovery.py create_device Example per D5-20/D5-21 incl. None guard) + docs/api/network.md hand-written prose (D5-20)

**Wave 5** *(third gap closure — 05-UAT.md gaps G-05-2..G-05-7 under D5-22/D5-23)*

- [x] 05-06-PLAN.md — UAT gap closure: honest direct-connection docs (G-05-2), agreed animation lead-in verbatim (G-05-3), rendered-docstring blank lines across 13 files (G-05-4 + audit), de-jargoned retransmit prose per proposed_text (G-05-5), planning-ID demotion to comments + spike-figure removal + mandatory D5-22 audit (G-05-6), 8-warning baseline eliminated — effects.md backticks, mDNS ::: render targets, CI `zensical build --strict` (G-05-7/D5-23)

## Progress

**Execution Order:**
Phases execute in numeric order: 2 → 3 → 4 → 5 (Phases 2–4 are mutually independent; 5 requires 4)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Ceiling Save-on-Exit | v1.0 | 1/1 | Complete | 2026-06-12 |
| 1. Unify duplicated discovery loops | post-v1.0 | 5/5 | Complete | 2026-06-13 |
| 2. Discovery Re-broadcast | v1.1 | 2/2 | Complete | 2026-07-16 |
| 3. Retry Schedule Reshape | v1.1 | 3/3 | Complete | 2026-07-17 |
| 4. Animation Flow Control | v1.1 | 11/13 | Complete    | 2026-07-17 |
| 5. Reliability Documentation | v1.1 | 6/6 | Complete    | 2026-07-18 |
