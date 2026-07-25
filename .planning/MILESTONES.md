# Milestones

## v1.1 Wire Reliability (Shipped: 2026-07-26)

**Phases completed:** 4 phases, 24 plans, 52 tasks

**Key accomplishments:**

- 6-round `discover_devices()` measurement against the 73-device production fleet: median coverage 73/73 (full roster), up from the recorded 48/73 single-broadcast baseline.
- 17-test branch-matrix RED suite in test_connection_retry.py plus a rewritten TestRetryTimeoutBudget, both confirmed RED against the current exponential/jitter retry implementation with the exact fail/pass breakdown 03-RESEARCH.md predicted.
- Reshaped both `DeviceConnection` request paths onto a single shared `_transmit_and_listen()` engine — one monotonic wall deadline, Photons-shaped escalating retransmits, retransmit-while-listening, and shared-queue correlation on both GET and ACK — turning all 20 Wave-0 tests green and closing RETRY-01 through RETRY-04.
- Built and ran a headless zero-loss packets/trial harness against the gen4 test downlight: first attempt measured mean 1.083 packets/trial (FAIL, driven by a genuine two-trial WiFi retransmit event), a mandatory single re-run measured mean 1.017 / median 1.0 (PASS) with 12.6ms median latency — both far below the pre-reshape spike 002 baselines of 1.37 packets/trial and 62ms median.
- RED test suite pinning the row-aligned 13x26 Ceiling chunking fix and the ack-probe attachment seam (`probe_template_index` + header flag constants) that plan 04-03 must turn GREEN.
- RED test suite pinning the AckGate facility contract (test_flow.py) and the animator's gate-before-frame/probe-baking/additive-stats contract (test_animator.py), including deterministic emulator gating against a genuine 13x26 large-tile device, that plan 04-04 must turn GREEN.
- Fixed the latent large-tile chunking bug (raw 64-pixel colour slicing vs row-aligned rect offsets) that garbled frames on any tile width not dividing 64, and added the FLAGS_OFFSET/ACK_REQUIRED_FLAG/probe_template_index seam that plan 04-04's Animator wiring consumes — closing the full 04-01 RED suite (21 tests) with zero test edits.
- Implemented the internal `AckGate` flow-control facility and wired sweep-then-gate ordering into `Animator.send_frame`, turning the full 04-02 RED suite green while fixing a pre-existing port-routing bug that the new ack-receive path exposed.
- Built `uat_ack_stream.py`, a standalone phase-dir harness that drives the shipped `Animator.for_matrix()`/`send_frame()` ack-gated flow control at 20 FPS against real matrix/ceiling devices, with a concurrent single-shot `GetColor` prober and a fixed 0/1/2 exit-code contract, ready for plans 04-06/04-07 to run against real hardware.
- ANIM-03 Tiles UAT: Task 1 ran twice and honestly FAILed at the original 0% gate; its measurement ownership then moved to 04-11, and its operator visual checkpoint (Task 2) never ran — visual ownership landed on 04-13 Task 4. ANIM-03 was ultimately resolved by operator ruling, not by this plan.
- ANIM-04 Ceiling Capsule UAT: superseded in full before dispatch. Its headless measurement was covered by the Capsule's own 04-12 sweep session, and its operator visual checkpoint landed on 04-13 Task 4. ANIM-04 was ultimately resolved by operator ruling, not by this plan.
- 1. [Rule 3 - Blocking] Large-file pre-commit hook rejected the events evidence
- H2
- Operator-approved cross-device paired sweep (7 healthy-radio matrix devices + Tiles II reference) ran once per device; aggregate outcome FAIL (5/5 valid gate sessions FAILed) under unusually high ambient network loss -- ANIM-03/ANIM-04 remain unchecked pending fresh operator routing.
- ANIM-03/ANIM-04 resolved by operator ruling (verbatim "2") over the 04-12 sweep's honest statistical FAIL — an acceptance of the eight-device directional dossier, never a statistical pass — with the Capsule dims corrected (16×8 zones, 128 zones, 26 in × 13 in physical) and closed out by an approved dual visual verdict (geometry PASS, smoothness = documented 20 FPS latest-frame-wins stutter, not freeze/crawl); Phase 4 plans complete.
- 1. [Rule 1 - Bug] Discovery-timeout example value raised from the plan's 10.0 to 30.0
- Removed pre-v1.1 workaround recipes (two-pass discovery, fast=True streaming loops) and inflated 30+ FPS claims from advanced-usage.md, architecture/overview.md and CLAUDE.md, so no published page or repo instruction contradicts the v1.1 wire behaviour.
- 1. [Plan-literal imprecision] Acceptance grep named the wrong exception class
- Closed the last open 05-VERIFICATION.md gap (async-for vs await on `discover_devices()` in three troubleshooting.md examples) plus the full operator-opted residual set across eight docs pages and three narrow source-docstring overrides, with the docs build holding at its pre-existing 8-issue baseline and the full test suite green.
- Closed all six operator-diagnosed documentation gaps: honest direct-connection guidance, de-jargoned rendered docstrings with IDs demoted to traceability comments, zero run-on paragraphs, rendered mDNS API reference, and a permanent zero-warning `--strict` docs build gate in CI.

---

## v1.0 Ceiling Save-on-Exit (Shipped: 2026-06-12)

**Phases completed:** 1 phases, 1 plans, 3 tasks

**Key accomplishments:**

- `CeilingLight.__aexit__` override that persists in-memory state to `state_file` before `close()`, proven by three emulator-backed TDD tests covering happy-path write, no-op without state_file, and exception-propagation-with-save-failure.

---
