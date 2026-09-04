---
phase: 14-thread-revalidation-and-docs
plan: 06
subsystem: evidence
tags: [thread, physical-evidence, srp, mdns, staleness, class-ledger, seed-001]

# Dependency graph
requires:
  - phase: 14-thread-revalidation-and-docs (plan 04)
    provides: hermetically proven physical protocol mode drivers
provides:
  - SEED-001 physical evidence for the available Thread lighting classes
  - Observed advertisement staleness and rediscovery figures for this fleet
  - First hardware validation of the frame-address thread_connection bit
  - Closed six-class ledger with two dated named gaps
affects: [.planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE]

# Actuals
actuals:
  tokens: 0
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Operator-supplied power scripts driving both edges of a physical disconnect experiment, so no human sits in the timing path"
    - "Unbounded restoration polling with live stderr progress, rather than a deadline that converts a slow device into a spurious null"

key-files:
  created:
    - .planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-MANIFEST.json
    - .planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-DISCOVERY.jsonl
    - .planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-REQUESTS.jsonl
    - .planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-STALENESS.jsonl
    - .planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-ANIMATION.jsonl
    - .planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-CLOSURE.jsonl
    - .planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-SUMMARY.json
    - .planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-CLASS-LEDGER.json
    - .planning/phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-REPORT.md
    - .planning/phases/14-thread-revalidation-and-docs/14-INTERIM-RESULTS.md
  modified: []
---

# Plan 14-06: Collect SEED-001 physical evidence

Session `seed-001`, collected 2026-09-04 between 18:36 and 21:23 AEST against a
roster of eight Thread devices spanning `Light`, `MultiZoneLight`, `MatrixLight`
(two distinct devices) and `CeilingLight`. Evidence rows were produced at
revision `687c8d8`, which the manifest pins.

## What was measured

**THREAD-01, discovery.** Six paired rounds across `discover()` and
`discover_mdns()`, twelve arms in total. Every round found all eight devices on
both legs. No partial round, no source disagreement, no missing alias.

**THREAD-02, request timing.** 800 trials, 100 per device, all `completed`. No
timeout, failure, retransmission or `power_out_of_range`. Acknowledgement
round-trip was 31.5 ms minimum, 43.9 ms median, 94.3 ms at p95 and 326.8 ms
maximum.

Two consequences worth carrying. The median sits below the roughly 100 ms the
v1.1 WiFi spike series measured under streaming load, so Thread is not the
latency penalty those assumptions implied. The maximum exceeds the 200 ms "an
acked bulb has answered by now" constant, so that constant is not a safe upper
bound on this transport even though the median is comfortably inside it. Per
THREAD-02's acceptance, the constants remain unchanged: this is one confounded
fleet's observation, not replicated evidence of a defect.

`thread_connection` was true on all 800 trials. That is the first validation of
the frame-address bit parsing added in `b4ae1b8` against real hardware, rather
than against constructed headers.

**THREAD-04, observed staleness.** One trial, `confirmed_expiry`. The UDP leg
lost the device at the first poll, t+60s, which is what makes the result clean:
the bulb answers broadcast itself and was unpowered, so everything lingering past
that point is the border router alone. The mDNS leg held the device until poll
70 (t+4200s), confirmed at poll 72, placing true disappearance between t+4140s
and t+4200s. Restoration took 69.4 seconds from the power-on edge.

The 4200s figure is remaining lease at the instant of disconnection, not a lease
value, because SRP clients renew before expiry. It is statistically
indistinguishable from OpenThread's 7200s default sampled mid-cycle.
`.planning/seeds/SEED-002-wifi-advertisement-staleness-control.md` records the
WiFi control that would isolate it.

**THREAD-05, class closure.** All six public lighting classes hold exactly one
disposition. `Light` (4 aliases), `MultiZoneLight` (1), `MatrixLight` (2) and
`CeilingLight` (1) are `evidence_backed`. `InfraredLight` and `HevLight` are
`named_gap` dated 2026-09-04, their fleet hardware predating Thread.

## Deviations

**Animation left scope mid-plan.** Task 2 originally ran `animation --all` across
the fleet before closure derivation. One attempt was recorded for
`LIFX-Candle-C-1`, which completed all three rate observations with
`restored: true` and `restoration_verified: false`. The stage was then stopped by
decision rather than by that failure: Thread lacks the bandwidth to sustain
animation at usable frame rates, and pushing that data volume onto a mesh is poor
practice regardless of what a measurement would show. THREAD-03 became a recorded
scope boundary (`6a13e99`), closure stopped consulting animation (`80c77ea`), and
`Animator` is intended to be locked to WiFi devices in a future milestone
(SEED-003). The Candle observation is preserved and cited only as evidence that
Thread carries frames without failing.

**The animation payload is unfit for its stated purpose**, recorded rather than
fixed. `_make_animation_send_frame` binds a single brightness-0 frame and sends
it identically on every call, so firmware that short-circuits an unchanged frame
does almost no work and the transport figures flatter themselves.

**D-16 was disproportionate** and was rewritten in `6a13e99`. It had required
restarting the complete physical protocol under a new session identity on any
restoration failure, which would have discarded the 70-minute staleness
experiment over a latent tile-buffer difference on a switched-off bulb. Halt
immediately and operator-confirmed recovery survive; the session-restart clause
does not.

**The plan's CLI contract did not match the shipped CLI.** Every verify command
named flags that plan 14-04 never built (`--expected-roster`, `--through-stage`,
`--require-complete`, `--check-tracked-paths`), and `LIFX_PHASE14_EXPECTED_ROSTER`
had no consumer. The plan was amended to the CLI as built (`e8179cc`), with each
gate expressed as an explicit assertion over the JSON envelope rather than an
exit code.

**Tooling defects found and fixed during the run**: the measurement scripts could
not be invoked as files after plan 14-03's consolidation (`f25a299`); `init`
froze incomplete rosters without complaint (`5a290f9`); `generate` wrote products
on failure (`ebeaf0c`); verdicts were inferable only from `$?` (`4f1bc37`,
`8042723`); `--all` did not exist, forcing hand-written shell loops (`b3770ed`);
and the staleness experiment required a hand-pasted timestamp and gave up on
restoration after 15 seconds (`687c8d8`).

## Known defect, not fixed

`_cli_validate` writes the summary, ledger and report unconditionally, including
for an incomplete session, so inspecting a session mutates it. This wrote stale
products into the evidence directory mid-run; they were removed in `36bea08`.
The defect undercuts the atomicity `ebeaf0c` gave `generate` and is left for a
follow-up.

## Self-Check: PASSED

- Six-class ledger complete, `generate` returns `ok: true` with no missing classes
- Products regenerate byte-identically
- No serial, address or hostname shapes in any tracked evidence path
- Full suite 4834 passing, ruff and pyright clean
