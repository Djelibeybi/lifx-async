---
phase: 02-discovery-rebroadcast
verified: 2026-07-17T15:09:40Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 2: Discovery Re-broadcast — Verification Report

**Phase Goal:** A single `discover_devices()` call reliably finds the entire fleet, including on multi-AP networks where any one broadcast is best-effort per AP
**Verified:** 2026-07-17T15:09:40Z
**Status:** passed
**Re-verification:** Yes — refreshed after UAT (see Re-verification Note below)

## Re-verification Note (2026-07-17)

Refreshed during `/gsd-verify-work 02`. Since the initial verification
(2026-07-16), `src/lifx/network/discovery.py` was edited by later phases —
`feat(03-02)` (request-retry reshaping onto the Photons wall-time schedule)
and `fix(05-05)`/`docs(05-06)` (network-layer source-override and docstring
edits) — so the report was flagged stale. Behaviour was re-confirmed against
the current code: `uv run pytest tests/test_network/test_discovery_rebroadcast.py`
→ **10 passed** (the full phase-02 behavioural branch matrix), and the git tree
is clean. The four must-have truths below remain VERIFIED; the specific
`discovery.py` line numbers cited in the evidence may have drifted under the
later edits, but the asserted behaviour (escalating re-broadcast schedule,
first-wins dedup, preserved idle/overall exits, DISC-03 fleet coverage) is
intact. UAT (`02-UAT.md`): 6 passed, 0 issues, 1 skipped-with-reason.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | `GetService` re-broadcast on escalating Photons-shaped schedule (gaps 0.6, 1.2, 1.8, 2.0, 2.0 s), capped by the window, observable in emulator/mock tests at expected gaps | ✓ VERIFIED | `DISCOVERY_REBROADCAST_GAPS = (0.6, 1.2, 1.8, 2.0, 2.0)` at `src/lifx/const.py:39`; due-send loop at `src/lifx/network/discovery.py:277-291` (top-of-loop, after both deadline checks); slice cap at L297-298; runtime read of the constant at L253 (not a def-time default). Behavioural tests ran and passed: `test_two_sends_at_first_gap_within_window` asserts gap ∈ [0.4, 0.9] at real gaps; `test_window_caps_schedule_single_send`, `test_schedule_exhaustion_falls_back_to_remaining`, `test_multiple_sends_due_in_one_loop_pass` cover capping/exhaustion/catch-up. `uv run pytest tests/test_network/ -x` → 234 passed, 0 skipped |
| 2 | Every discovered device yielded exactly once despite ~2× answers per broadcast and multiplied response volume | ✓ VERIFIED | First-wins `seen_serials` dedup preserved at `discovery.py:427-430` (checked AFTER `mark_response()` at L425 so duplicate floods keep the idle window open without duplicate yields). `test_same_serial_across_broadcasts_yields_once` (same serial answers across a re-broadcast boundary → 1 yield, 2 sends) and `test_emulator_dedup_across_rebroadcast_window` (real emulator, 2.0 s window spanning 3 sends, asserts no serial yielded twice) both passed |
| 3 | Existing callers work unmodified — serial validation, first-wins dedup, idle-deadline early exit preserved | ✓ VERIFIED | Phase diff touches only `src/lifx/const.py` (+5) and `src/lifx/network/discovery.py` (+57/−6); no signature lines changed for `_discover_with_packet`/`discover_devices`; `src/lifx/api.py` (`discover`, `find_by_serial`, `find_by_ip`, `find_by_label`) untouched this phase. Serial-validation guards intact (`discovery.py:324, 328, 349-353`). `except LifxTimeoutError: continue` at L303-304 makes the deadline checks the sole exit authority. `test_send_does_not_reset_idle_window` proves sends never reset the idle deadline (elapsed upper bound excludes the reset case); `test_quiet_slice_rebroadcast_then_idle_exit` / `..._then_overall_exit` prove both exits still function. All 27 pre-existing tests in `test_discovery_errors.py` + `test_discovery_devices.py` pass unmodified |
| 4 | Hardware UAT: ≥6 rounds against 73-device fleet, median per-round coverage = 73/73 (baseline 48/73) | ✓ VERIFIED | `02-UAT-RESULTS.json` on disk: rounds `[73, 73, 30, 73, 73, 73]`, roster 73, median 73.0, `pass: true`. Independently recomputed: `statistics.median([73,73,30,73,73,73]) = 73.0`; `missed_by_round[2]` has 43 serials = 73 − 30 (internally consistent); all other rounds missed nothing. Harness drives the real `discover_devices()` (`uat_rounds.py:36,63`), has the 0/1/2 exit contract with `ROSTER_SANITY_FLOOR = 60` (L143-156), and `--help` exits 0. Round-2 dip analysed below — the median criterion is genuinely met |

**Score:** 4/4 truths verified (0 present-but-behaviour-unverified — every behaviour-dependent truth has a passing behavioural test executed during this verification)

### Locked Decisions (02-CONTEXT.md)

| Decision | Status | Evidence |
| -------- | ------ | -------- |
| D2-01: Photons gaps 0.6/1.2/1.8/2.0/2.0 inside `_discover_with_packet()`'s loop, capped by the window | ✓ HONOURED | Constant values match exactly; due-send loop placed after both expiry checks so no send fires past either deadline |
| D2-02: Phase 1 rework preserved (serial validation, first-wins dedup, IdleDeadline, thin wrapper); no `mark_response()` on send | ✓ HONOURED | Send path (`discovery.py:277-291`) contains no `mark_response()` call; every existing `mark_response()` call site preserved (L393, L425); proven behaviourally by `test_send_does_not_reset_idle_window` |
| D2-03: Public API unchanged — schedule is a `const.py` module constant, no new kwargs | ✓ HONOURED | No signature changes in the phase diff; no new parameters on `discover_devices` or `_discover_with_packet`; `DISCOVERY_REBROADCAST_GAPS` follows the existing `Final[...]` + comment convention |
| D2-04: mDNS path untouched | ✓ HONOURED | `git status --porcelain src/lifx/network/mdns/` → empty; `git log ec35187^..HEAD -- src/lifx/network/mdns/` → no commits |

### Message/Source Reuse (plan must-have)

`test_rebroadcast_reuses_identical_message` passed: every `send.call_args_list` entry identical to the first — the same `message` object (`discovery.py:289` reuses the object built at L223-230, same source, same sequence), so the source-validation guard at L324 accepts responses to any broadcast in the session.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/lifx/const.py` | `DISCOVERY_REBROADCAST_GAPS` schedule constant | ✓ VERIFIED | L39, with cumulative-offsets comment; imported and read at runtime by discovery.py |
| `src/lifx/network/discovery.py` | Send/receive interleave with continue-on-timeout and `rebroadcast_sent` debug logging | ✓ VERIFIED | Due-send loop L277-291 with `rebroadcast_sent` dict log; slice cap L297-298; `continue` L303-304; substantive, wired, exercised by tests |
| `tests/test_network/test_discovery_rebroadcast.py` | Branch-matrix tests (min 150 lines) | ✓ VERIFIED | 336 lines, 10 tests in 3 classes (`TestRebroadcastSchedule` ×8, `TestRebroadcastDedup` ×1, `TestRebroadcastEmulator` ×1); all pass; emulator test ran (not skipped) |
| `.planning/phases/02-discovery-rebroadcast/uat_rounds.py` | DISC-03 harness driving real `discover_devices()` | ✓ VERIFIED | Imports `from lifx.network.discovery import discover_devices`; exit contract 0/1/2 with roster sanity floor 60; `--help` exits 0; not imported from src/ or tests/ |
| `.planning/phases/02-discovery-rebroadcast/02-UAT-RESULTS.json` | Recorded 6-round measurement with pass flag | ✓ VERIFIED | Present, machine-readable, internally consistent (median/missed sets recomputed and confirmed) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `discovery.py` | `const.py` | Runtime read of `DISCOVERY_REBROADCAST_GAPS` inside generator body | ✓ WIRED | Import L15; `accumulate(DISCOVERY_REBROADCAST_GAPS)` at L253 inside the generator (not a def-time default) |
| `test_discovery_rebroadcast.py` | `discovery.py` | `patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", ...)` | ✓ WIRED | Used in 7 tests; patching works, proving the runtime read |
| `test_discovery_rebroadcast.py` | `test_discovery_errors.py` | Shared `_build_state_service_packet` import | ✓ WIRED | Import at L21; helper file unmodified |
| `uat_rounds.py` | `discovery.py` | Calls real `discover_devices()` generator | ✓ WIRED | L36 import, L63 call — measures the shipped code path, not a hand-rolled schedule |
| `uat_rounds.py` | spike 005 baseline JSON | Loads `summary-20260716-211339.json` for comparison | ✓ WIRED | `BASELINE_PATH` L39-41; graceful fallback if missing |

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
| --------- | ------- | ------ | ------ |
| Rebroadcast schedule + dedup + idle semantics | `uv run pytest tests/test_network/ -x` | 234 passed, 0 skipped, 30.5 s | ✓ PASS |
| Full-suite regression | `uv run --frozen pytest` | 2545 passed, 12 deselected (benchmark), 0 failed, 109.2 s | ✓ PASS |
| Edit-range branch coverage | `uv run pytest tests/test_network/ --cov-report=term-missing` | `discovery.py` Missing column: `105->120, 115-116, 122, 126, 130-132, 211, 329-337, 371-378, 445-454` — all pre-existing paths (create_device error handling, STATE_TYPE guard, unexpected/unknown-packet and malformed-response branches) outside the L249-304 edit range; no new line or branch partial missing | ✓ PASS |
| Lint | `uv run ruff check .` | All checks passed | ✓ PASS |
| Type check | `uv run pyright` | 0 errors, 0 warnings | ✓ PASS |
| UAT harness runnable | `uv run python .planning/.../uat_rounds.py --help` | Exit 0, no packets sent | ✓ PASS |
| UAT JSON integrity | Recompute median + missed sets from raw JSON | median 73.0 confirmed; missed_by_round[2] = 43 = 73 − 30; other rounds empty; `pass: true` consistent with the harness's own contract | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| DISC-01 | 02-01 | Escalating re-broadcast schedule preserving validation + dedup | ✓ SATISFIED | Truths 1 and 3 above |
| DISC-02 | 02-01 | Duplicate responses never cause duplicate yields | ✓ SATISFIED | Truth 2 above |
| DISC-03 | 02-02 | Repeated-round hardware validation: median = full coverage | ✓ SATISFIED | Truth 4 above (with dip analysis below) |

No orphaned requirements: REQUIREMENTS.md maps exactly DISC-01/02/03 to Phase 2, all claimed by the two plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | None (no TBD/FIXME/XXX/TODO/HACK/placeholder in any phase-modified file) | — | — |

### Round-2 Dip Analysis (30/73)

**What the evidence shows.** Round 2 found 30 of 73 devices; the 43 missed serials were found in every other round (all other `missed_by_round` entries are empty). The rounds immediately before and after (same process, same event loop, same code) hit 73/73.

**Can the recorded evidence discriminate environmental suppression from an intermittent schedule failure?** **No.** The harness records only per-round serial sets. It does not record per-round wall time, per-round `rebroadcast_sent` counts, raw datagram counts, or response-time distributions. 30/73 lies inside the single-broadcast baseline band (min 27, median 48, max 73), so the raw count alone is consistent with both hypotheses.

**Why the balance of evidence still favours an environmental event:**

1. *No mechanism identified for intermittent send failure.* The due-send loop runs at the top of every loop iteration against monotonic time, and the catch-up branch (multiple offsets elapsed in one pass, e.g. after a slow receive) is directly unit-tested (`test_multiple_sends_due_in_one_loop_pass`). Loop starvation severe enough to skip sends would require the event loop to be blocked, which the adjacent 73/73 rounds in the same process contradict.
2. *43 devices vanishing as a block is the per-AP loss signature* the spike 005 baseline already characterised as bimodal (per-AP broadcast delivery suspected).
3. *A designed interaction can amplify an environmental event:* the idle window is 4.0 s (`MAX_RESPONSE_TIME 1.0 × IDLE_TIMEOUT_MULTIPLIER 4.0`) while re-broadcast gaps are ≤ 2.0 s. If ALL responses are suppressed for > 4 s mid-round (e.g. AP backhaul hiccup), the idle deadline legitimately ends the round before the t = 5.6/7.6 s sends fire. That is the preserved D2-02 idle semantics behaving as designed, not a schedule defect — and the median criterion was explicitly framed to tolerate occasional per-round misses.

**Recommended follow-up measurement (non-blocking).** Extend `uat_rounds.py` to record, per round: (a) elapsed wall time, (b) a count of `rebroadcast_sent` debug entries via a logging handler on `lifx.network.discovery`, (c) total raw datagrams received, and (d) max per-device `response_time`. A future dip round showing all scheduled sends fired with a short wall time (idle exit) would definitively confirm environmental suppression; missing sends would indicate a schedule bug. This is instrumentation on a phase-dir tool, not shipped code.

**Classification:** DISC-03's criterion — median per-round coverage equals the full roster over ≥ 6 rounds — is genuinely and verifiably met (73.0 = 73). The dip's root cause is UNCERTAIN but does not violate the criterion, no threshold was altered in response to it, and the honest-reporting rules in the plan were followed. Non-blocking observation, not a gap.

### Minor Discrepancies (informational)

- `02-02-SUMMARY.md` says "42 serials missed this round only"; the JSON records **43** (= 73 − 30). Off-by-one in the SUMMARY narrative only; the evidence artefact is correct. No action required.

### VALIDATION.md Sign-Off Readiness

All five automated verification rows in `02-VALIDATION.md`'s per-task map are green as independently re-run during this verification (test collection, GREEN suite, branch coverage, harness `--help` + ruff, UAT JSON pass flag). The sign-off state (`status: draft`, `nyquist_compliant: false`, approval pending) **can be updated** — every gate it depends on passes. Left unmodified per verifier scope (orchestrator/validate-phase owns that file).

### Human Verification Required

None. The hardware UAT (the only manual-only verification listed in 02-VALIDATION.md) has already been executed and its evidence artefact independently validated.

### Gaps Summary

No gaps. The phase goal is achieved in the codebase: the Photons-shaped re-broadcast interleave is real, wired, behaviourally tested at every branch of the matrix, preserves all Phase 1 semantics and the public API, leaves mDNS untouched, and the 6-round hardware measurement records median full-fleet coverage (73/73) against a 48/73 baseline.

---

_Verified: 2026-07-16T12:52:40Z_
_Verifier: Claude (gsd-verifier)_
