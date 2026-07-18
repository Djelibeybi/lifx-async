---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Wire Reliability
current_phase: 05
status: completed
stopped_at: Completed 05-06-PLAN.md (UAT gap closure G-05-2..G-05-7)
last_updated: "2026-07-17T14:10:20.090Z"
last_activity: 2026-07-18
last_activity_desc: Phase 05 complete
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 24
  completed_plans: 24
  percent: 100
current_phase_name: reliability-documentation
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-18 after Phase 5)

**Core value:** Commands stick, devices are found, and streaming never starves control traffic — the library is reliable enough that "bulb didn't respond" stops being a lifx-async problem.
**Current focus:** v1.1 milestone close — all four phases complete; see Blockers before running `/gsd-complete-milestone`

## Current Position

Phase: 05
Plan: Not started
Status: All phases complete
Last activity: 2026-07-18 — Phase 05 complete

Progress: [████████████████████] 24/24 plans (100%) — all 4 v1.1 phases complete and verified

## Performance Metrics

**Velocity:**

- Total plans completed: 23 (v1.0: 1; post-v1.0 Phase 1: 5; v1.1: 3)
- Average duration: -
- Total execution time: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 (v1.0 Ceiling Save-on-Exit) | 1 | - | - |
| 1 (post-v1.0 discovery unification) | 5 | - | - |
| 04 | 11 | - | - |
| 05 | 6 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 02 P01 | 7m | 3 tasks | 3 files |
| Phase 02 P02 | 12min | 2 tasks | 2 files |
| Phase 03 P01 | 10min | 2 tasks | 2 files |
| Phase 03 P02 | ~35min | 2 tasks | 3 files |
| Phase 03 P03 | 15min | 2 tasks | 2 files |
| Phase 04 P01 | 25min | 2 tasks | 1 files |
| Phase 04 P03 | 20min | 2 tasks | 2 files |
| Phase 04 P04 | 35min | 3 tasks | 2 files |
| Phase 04-animation-flow-control P05 | 20min | 1 tasks | 1 files |
| Phase 04 P08 | 28min | 3 tasks | 5 files |
| Phase 04 P09 | ~12min | 2 tasks | 2 files |
| Phase 04 P10 | ~18min | 3 tasks | 8 files |
| Phase 04 P11 | ~50min | 4 tasks | 10 files |
| Phase 04 P12 | 50min | 4 tasks | 15 files |
| Phase 04 P13 | ~35min | 5 tasks | 7 files |
| Phase 05 P01 | 6min | 3 tasks | 2 files |
| Phase 05 P03 | 8min | 2 tasks | 3 files |
| Phase 05 P02 | 9min | 2 tasks | 2 files |
| Phase 05 P04 | 8min | 3 tasks | 8 files |
| Phase 05 P05 | 11min | 3 tasks | 12 files |
| Phase 05 P06 | 27min | 3 tasks | 21 files |

## Accumulated Context

### Roadmap Evolution

- v1.1 roadmap created (2026-07-16): Phases 2–5 — Discovery Re-broadcast, Retry Schedule Reshape, Animation Flow Control, Reliability Documentation. Derived from spike series 001–005 blueprints (`.claude/skills/spike-findings-lifx-async/`).

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Adopt Photons-shaped schedules for discovery re-broadcast and request retries (spike-validated: full coverage / 1-in-180 failure at moderate packet cost)
- Animation flow control is owned by the library, not downstream — no consumer-facing toggle (user decision, 2026-07-16)
- Threading port, keepalive daemon, and Glowup-style fresh-deadline retries are disproven and out of scope (Spikes 001/002/004)
- [Phase 1, post-v1.0]: Serial validation is unconditional in `_discover_with_packet`; first-wins per-serial dedup lives in the shared generator — Phase 2 re-broadcast must preserve both
- [Phase 1, post-v1.0]: IdleDeadline governs discovery loop timeouts — re-broadcasts naturally reset the effective idle window as responses keep arriving
- [Phase 2, Plan 01]: Kept response_time anchored at the first broadcast (unchanged semantics); documented the anchor in DiscoveredDevice/DiscoveryResponse docstrings
- [Phase 2, Plan 01]: No mark_response() call added to the send path -- sends never reset the idle deadline, preserving quiet-network exit timing
- [Phase ?]: Harness imports discover_devices directly rather than adapting sweep.py's regime-arm approach, per research finding that the spike harness cannot measure the shipped implementation
- [Phase ?]: ROSTER_SANITY_FLOOR=60 kept as a hard-coded constant, not an argparse flag -- it's a sanity invariant of the measurement contract, not a tunable
- [Phase ?]: Used max_retries=5 in the rewritten wall-time test for a deterministic message-based RED independent of jitter
- [Phase 3, Plan 02]: Single shared `_transmit_and_listen()` engine owns source allocation, the shared queue, the retransmit schedule, the wall deadline, and correlation-key lifecycle; `_request_stream_impl`/`_request_ack_stream_impl` reduced to thin wrappers with unchanged names/signatures (the 12+ test mock seam) — resolves the flagged cross-impl duplication in one pass with the reshape
- [Phase 3, Plan 02]: ACK path moved onto the same shared-queue correlation contract as GET — a late acknowledgement to an earlier retransmit now satisfies the request instead of being discarded (RETRY-04 mandated behaviour change, not a regression)
- [Phase 3, Plan 02]: Patched `_STREAM_IDLE_TIMEOUT` down in one 03-01 RED test (`test_discovery_connection_accepts_any_target`) that lacked the patch its three sibling `_drive()`-based tests already used — it passed coincidentally under the old exponential per-attempt windowing (~0.29 s) but genuinely needs the real 2.0 s idle window under the correct engine; verified empirically against both implementations before touching the test
- [Phase 3, Plan 02]: Marked the ACK wrapper's async-for loop `# pragma: no branch` — its body always exits via `return` or a raised exception, so the natural-exhaustion arc is structurally unreachable; the identical pre-existing pattern in `request_stream()`'s untouched SET/EchoRequest branches already carries the same (unaddressed, out-of-scope) gap
- [Phase ?]: Zero-loss packets/trial hardware harness (uat_zero_loss.py): run 1 FAIL (mean 1.083, transient WiFi retransmits), re-run PASS (mean 1.017, median 1.0) vs spike 002 baseline of 1.37
- [Phase ?]: Used getattr(target, 'attr_name', None) for probe_template_index RED test accesses (not just module constants) to keep pyright strict-clean against a not-yet-existing property
- [Phase ?]: D4-04 encoded: large-tile ack probe attaches to the final CopyFrameBuffer (frame-commit packet), not the first Set64 — matches Glowup's proven >64-zone ceiling behaviour; probe_template_index is a one-line fallback seam to index 0 if hardware disagrees
- [Phase ?]: [Phase 4, Plan 04] AckGate facility (flow.py) implements the spike-003-measured tuning constants and turns the full 04-02 RED suite green
- [Phase ?]: [Phase 4, Plan 04] Fixed a pre-existing bug: Animator factories never passed the device's real port, silently misdirecting all animation traffic for non-default-port devices — surfaced by the new ack-receive path
- [Phase ?]: Ceiling UAT profile powers device on + settles 1s before streaming, confirms via get_power(), and asserts every sent frame is exactly 8 packets (7 row-aligned Set64 + 1 CopyFrameBuffer)
- [Phase ?]: 04-05 deliberately does not mark ANIM-03/ANIM-04 complete in REQUIREMENTS.md -- hardware validation happens in 04-06 (Tiles/ANIM-03) and 04-07 (Ceiling/ANIM-04), not this harness-build plan
- [Phase ?]: [Phase 4, Plan 08] Spike 003's 0% ANIM-03 threshold was calibrated from a single 50-query round (>=6% upper bound; 18% chance of 0/50 even at the UAT's 3.37% rate) — calibration question settled from raw data; fixable-vs-floor deferred to 04-09
- [Phase ?]: [Phase 4, Plan 08] Five-arm hardware evidence recorded verbatim (control 0/227, shipped 2/189, replica 9/185, sweep 1/210, fallback 4/198) with per-event JSONL; no interpretation until 04-09
- [Phase ?]: Verdict H2 (R2 fired): spike 003's 0/50 was a small-sample draw — replica lost 9/185 = 4.86% at power; shipped path significantly outperforms the spike methodology (Fisher p = 0.0342)
- [Phase ?]: ANIM-03 routed by operator (verbatim '1'): recalibrate — operator-authored amendment (pooled <=5.0%/run, <=9.0%/round) via follow-up plan, then 04-06 re-run; 04-06 Task 2 and 04-07 stay gated until it lands
- [Phase ?]: [Phase 4, Plan 10] Operator-approved ANIM-03 recalibration applied verbatim (ROADMAP criterion 3, REQUIREMENTS ANIM-03, harness 9.0%/round + 5.0% pooled); amendment commits strictly precede the evidence commit
- [Phase ?]: [Phase 4, Plan 10] Amended-gate run FAILed twice (pooled 11.21% then 5.74% vs 5.0%; delivered_ratio below 0.85 in two rounds each run — new failure mode); thresholds untouched, routed back to the operator for a fresh decision
- [Phase ?]: [Phase 4, Plan 11] Operator approved the paired-relative ANIM-03 criterion verbatim ('1' = as presented); applied to ROADMAP criterion 3, REQUIREMENTS ANIM-03 and the paired ambient/gated/blind harness with commits strictly before the evidence
- [Phase ?]: [Phase 4, Plan 11] Paired gate FAILed twice with both sessions VALID (gated 2.94% vs blind 7.20%, ratio 2.45, p=0.0973; gated 5.51% vs blind 9.73%, ratio 1.77, p=0.1601) -- thresholds untouched, routed back to the operator for a fresh decision
- [Phase ?]: [Phase 4, Plan 12] Operator approved the cross-device paired-sweep criterion verbatim ('1' = as presented); applied to ROADMAP criteria 3+4, REQUIREMENTS ANIM-03/04, and the sweep-generalised harness with commits strictly before the evidence
- [Phase ?]: [Phase 4, Plan 12] Cross-device sweep ran 8/8 devices, one attempt each: aggregate outcome FAIL (5/5 valid gate sessions FAILed under unusually high ambient network loss, though the gated arm won directionally in every session 1.28-3.38x); thresholds/roster untouched after seeing results; routed back to the operator for a fresh decision (resolved by 04-13's ruling)
- [Phase ?]: [Phase 4, Plan 13] Operator ruled (verbatim "2", 2026-07-17): accept the eight-device directional dossier over the honestly-FAILed 04-12 sweep bar as satisfying ANIM-03/ANIM-04's intent -- an acceptance over a recorded FAIL, never a statistical pass; the final wording was approved verbatim ("1" = as presented) and applied to ROADMAP criteria 3+4, REQUIREMENTS ANIM-03/04, and the 04-06/04-07 final supersession notices, with the Capsule dims corrected (16x8 zones, 128 zones, 26 in x 13 in physical -- an early-planning units mix-up, operator correction verbatim)
- [Phase ?]: [Phase 4, Plan 13] Capsule visual round: headless outcome FAIL (gated pooled loss 51.28% vs the 9.0% ceiling, exit 1) recorded as non-gating context per the ruling. Operator's verbatim dual verdict: "Geometry was fine. It was as smooth as the tiles. No multi-second freezes but it stuttered throughout." Operator approved with the observation recorded (verbatim "1" of 3 options): geometry PASS; smoothness judged as the documented latest-frame-wins degradation under device saturation at 20 FPS (stutter, not freeze/crawl) -- the Capsule's sustainable rate is ~10 FPS at its 16x8/3-packets-per-frame chain shape; recommended as a Phase 5 docs line (choose streaming FPS per device class). ANIM-03/ANIM-04 flipped complete on this approval.
- [Phase ?]: [Phase 5, Plan 01] Wake-tail anchor pinned: heading '### Gen4 Power-Save Wake Tail' -> #gen4-power-save-wake-tail in troubleshooting.md; 05-02 cross-links must use this exact anchor
- [Phase ?]: [Phase 5, Plan 01] Discovery-timeout examples corrected to timeout=30.0 (plan said 10.0, below the actual 15.0 s default) so examples genuinely increase the timeout
- [Phase ?]: [Phase 5, Plan 03] Fire-and-forget docs rescoped to low-latency one-shots; sustained streaming directed to the Animation Guide; example loop bounded at ~20 FPS (T-05-07 flooding framing removed)
- [Phase ?]: [Phase 5, Plan 03] DOCS-02 requirement marking deferred to plan 05-02 completion (05-02 is the primary DOCS-02 plan and still pending); findings F1 (docs/api/animation.md:5 stale FPS prose) and F3 (no wrong docstrings) surfaced in SUMMARY, not fixed, per D5-10/D5-11 scope
- [Phase ?]: [Phase 5, Plan 02] Streaming docs written from the D4-01/D4-02 behavioural summary only — D5-09 boundary held (no gate threshold, ack expiry, or probe placement in user-guide prose)
- [Phase ?]: [Phase 5, Plan 02] Flickering entry references the streaming section by name (no same-page anchor link) so the Task 1 build stayed warning-clean before the section existed
- [Phase ?]: [Phase 5, Plan 04] CR-01 closed with D5-12 version-neutral sentences verbatim at both sites; D5-13 and D5-14 fences each exercised exactly once (api.py one docstring line; docs/api/animation.md one prose line) — verified by git-diff scope gates
- [Phase ?]: [Phase 5, Plan 04] All D5-15 residuals closed against shipped source: protocol examples now use LightHsbk uint16 + integer millisecond durations; capability checks via has_capability() guarded for None; overview.md renumbered 1-8 with a new Layer 1: Utilities section
- [Phase ?]: [Phase 5, Plan 05] Truth #23 closed and full D5-16..D5-21 residual set resolved; connection.py:64's bullet wrapped across two lines (not the plan's literal single line) to satisfy ruff's E501 line-length gate — the required substring stayed intact
- [Phase ?]: [Phase 5, Plan 06] G-05-2 fixed as a doc-page-only change (quickstart.md/overview.md); from_ip()'s docstring is not a falsehood and stayed untouched
- [Phase ?]: [Phase 5, Plan 06] G-05-5/G-05-6: every planning ID and design-lineage reference removed from rendered docstrings (connection.py, discovery.py, animator.py, packets.py) was demoted to a new # Traceability comment, never deleted
- [Phase ?]: [Phase 5, Plan 06] G-05-7/D5-23: rendered the three missing mDNS ::: targets (discover_mdns, discover_lifx_services, LifxServiceRecord) rather than deleting the dead index.md links; both CI docs.yml build invocations now gate on --strict, eliminating the former 8-warning baseline permanently

### Pending Todos

None yet.

### Blockers/Concerns

- **v1.1 milestone-close TODO — verification status (raised 2026-07-17; re-checked 2026-07-18):**
  `complete-milestone` requires `verification_status === 'passed'` for every phase
  (`workflows/complete-milestone.md:94`). **This is now the only thing standing between v1.1 and
  close.** Live resolver output as of 2026-07-18:

  | Phase | Resolver | Verdict |
  |-------|----------|---------|
  | 2 | `stale` | false negative |
  | 3 | `human_needed` | genuine |
  | 4 | `stale` | false negative |
  | 5 | `passed` | ✓ resolved 2026-07-18 |

  **Phase 5 is the worked example of the fix:** its fresh `05-VERIFICATION.md` was written after
  every summary, so the mtime heuristic had nothing to trip on and the status resolved
  legitimately — no mtime touched. Re-running `/gsd-verify-work` on Phases 2 and 4 should do the
  same. Three of four phases were failing at the last review; one remains a real UAT sign-off.

  The two false negatives:

  - **Phase 2** — `02-VERIFICATION.md` declares `status: passed`, but `readVerificationStatus`
    returns **`stale`** because `02-02-SUMMARY.md` is **49 seconds** newer than it. Pre-existing: a
    filesystem-mtime heuristic silently overriding the file's own declared status.

  - **Phase 4** — same shape: the file declares `status: passed`, resolver returns **`stale`**
    because the 04-06/04-07 supersession summaries (commit `2a5d747`) are newer than
    `04-VERIFICATION.md`. Known and accepted when those were written — the alternative was leaving
    Phase 4 permanently `completed=false` on disk (see that commit's message).

  - **Phase 3** — `human_needed`. This one is **genuine**: the file itself says so. It needs the
    manual UAT signed off, not a re-run.

  Decide at close: re-run `/gsd-verify-work` for Phases 2 and 4 (the tool's own advice — writes a
  fresh report newer than the summaries, restoring `passed` legitimately, exactly as Phase 5 just
  demonstrated), sign off Phase 3's UAT, or take `override_closeout` and record these as known
  gaps. **Do not** fix this by touching mtimes.
  Note the heuristic cannot survive a fresh `git clone` — checkout order decides staleness — so a
  passing local run is not evidence of a passing CI run.
  **Reported upstream: open-gsd/gsd-core#2348.**

- **Decision-coverage gate has never run on this project (raised 2026-07-17).** `check.decision-coverage-plan`
  is the *blocking* translation gate at plan-phase step 13a, and it has reported `passed` for every
  phase while parsing **zero** decisions. Cause: `parseDecisions` requires a literal `**D-` prefix, and
  this project's convention is `D5-NN`. The fail-loud guard added upstream for exactly this
  (open-gsd/gsd-core#1365) uses the same `/\bD-[A-Za-z0-9]/` grammar as its evidence test, so it
  cannot fire either. Verified: 05-CONTEXT.md has 23 `D5-*` bullets → 0 parsed → `skipped: "no
  trackable decisions"` → `passed: true`. Swapping `D5-` → `D-` in the same file parses all 23.
  **Reported upstream: open-gsd/gsd-core#2347.**
  Decision for a future milestone: adopt `D-NN` (CONTEXT.md is already per-phase, so the `5` prefix
  was disambiguating something the file scoping already handles) — **not** worth renaming mid-flight;
  D5-01..D5-21 are cited across plans, summaries, verification reports and ~12 commit messages.
  Until then, decision coverage is only ever verified by the plan-checker reading CONTEXT.md by hand.

- **Do not run `roadmap.update-plan-progress` on Phase 4.** It derives status from
  `summaryCount >= planCount && verificationPassed`, so while verification reads `stale` it silently
  rewrites `11/13 | Complete | 2026-07-17` to `In Progress` and drops the completion date. Triggered
  and reverted once on 2026-07-17. The `Complete`-requires-verification rule is deliberate
  (open-gsd/gsd-core#2022); the unreliable input feeding it is open-gsd/gsd-core#2348.

- **Do not run `state sync` unchecked.** `cmdStateSync` does not apply the
  `shouldPreserveExistingProgress` ratchet that `cmdStateJson` does, so the write path can regress
  values the read path protects. It is currently safe (verified 2026-07-17, after the 04-06/04-07
  closure records landed) but is not self-guarding. Not reported upstream — the area is heavily
  trodden (`gsd-build/get-shit-done#3242`'s fix and `#3336`'s "Converge state.sync on shared STATE.md
  transaction projection", both in the *archived* predecessor repo) and the divergence may be
  intended; it would need checking against #3336's commits before claiming a regression.
  **⚠ Note both repos number issues from 1 — a bare `#3242` means different things in each, and
  `open-gsd/gsd-core#3242` does not exist. Always qualify archived refs.**

- **Phase 4's superseded plans (04-06/04-07) carry closure records, not completion records.**
  `plan-scan.cjs` counts a phase complete only when every PLAN has a matching SUMMARY, with no concept
  of a deliberately-unexecuted plan, so without them Phase 4 read `11/13 → completed=false`
  permanently. The two SUMMARYs say `status: superseded` / `executed: partial|false` and claim no
  requirements. **GSD nonetheless infers `completed_plans: 22` when only 20 plans executed** — read the
  frontmatter, not the count. **Reported upstream: open-gsd/gsd-core#2349.**

- Hardware validation (DISC-03, ANIM-03, ANIM-04) cannot run in CI — treat as UAT-style steps against the quiesced test devices / 73-device production fleet; automated emulator-backed tests must independently reach 100% branch patch coverage
- Repeated rounds are mandatory for discovery/loss claims — single rounds mislead (Spike 005: shakedown found 71/73 by luck; 6-round median was 48/73)
- **[RESOLVED — historical, retained for the milestone record] UAT sequencing gate (cleared 2026-07-17):** ANIM-03/ANIM-04 are complete. Resolution: by operator ruling (verbatim reply "2", 2026-07-17, `04-RULING.md`) the cross-device directional dossier from the 04-12 sweep (aggregate statistical FAIL, 5/5 valid sessions FAIL, gated arm winning directionally in every session ever measured, ratios 1.28x–5.25x) was accepted as satisfying the requirements' intent — an acceptance over a recorded FAIL, never a statistical pass — and the operator gave an explicit dual approval verdict (smoothness + geometry) on My Office Ceiling Capsule's gated streaming round at 04-13 Task 4. Verbatim verdict: "Geometry was fine. It was as smooth as the tiles. No multi-second freezes but it stuttered throughout." The operator approved with the observation recorded (verbatim "1" of 3 presented options): geometry PASS; the stutter is the documented latest-frame-wins degradation under device saturation at 20 FPS (not a freeze/crawl failure mode) — the Capsule's sustainable rate is ~10 FPS at its 16×8/3-packets-per-frame chain shape, carried forward as a Phase 5 documentation recommendation (choose streaming FPS per device class). The headless round outcome (FAIL, gated pooled loss 51.28% vs 9.0% ceiling) is recorded as non-gating context per the ruling — certification was resolved by the ruling, not this round's statistics. The Capsule's dims are corrected everywhere they govern (16×8 zones, 128 zones, 26 in × 13 in physical). No gate remains open for Phase 4.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Persistence | PERS-01: extract `state_file` save/load into reusable mixin | Deferred to v2 | 2026-06-11 |
| Thread/IPv6 | THREAD-01 (SEED-001): revalidate wire behaviour over Thread/IPv6 when LIFX Thread firmware lands | Future requirement | 2026-07-16 |

## Session Continuity

Last session: 2026-07-18T14:10:20Z
Stopped at: Phase 5 complete — v1.1 has no phases left; milestone ready to close
Resume file: None

## Operator Next Steps

- **v1.1 is 100% complete (24/24 plans, 4/4 phases, 13/13 requirements).** Next action is
  `/gsd-complete-milestone v1.1` — but read the verification-status blocker below first: it
  requires `verification_status === 'passed'` for **every** phase, and Phases 2/3/4 do not
  currently return it. Phase 5 does (verified 2026-07-18, UAT 6/6, nyquist validated).
- **Unpushed work:** local `main` is several commits ahead of `origin/main`. Phase 5's
  execution, verification, UAT and validation commits are all local only.
- Phase 5 closed the 04-13 Capsule FPS observation as planned — the ~10 FPS per-device-class
  streaming guidance is now published in DOCS-02 (`docs/user-guide/animation.md`), so this
  item needs no further carry-forward.
