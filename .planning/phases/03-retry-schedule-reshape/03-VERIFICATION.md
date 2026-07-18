---
phase: 03-retry-schedule-reshape
verified: 2026-07-17T15:19:30Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "docs/api/network.md:132 and docs/architecture/overview.md:136 still describe 'exponential backoff and jitter' retry logic"
    addressed_in: "Phase 5"
    evidence: "Phase 5 goal: 'Users can find accurate guidance on the wire behaviour the library now guarantees'; 03-02-SUMMARY.md Phase 5 handoff notes explicitly assign these two files"
human_verification:
  - test: "Review the run-1 FAIL / run-2 PASS sequence of the optional zero-loss hardware measurement (03-03): run 1 mean 1.083 packets/trial (trials 52/53 at 5 and 2 transmissions, trial 52 latency 1848.9 ms), run 2 mean 1.017 / median 1.0 (canonical 03-UAT-RESULTS.json)"
    expected: "Agreement that run 1's elevated mean was a genuine transient WiFi-loss event (high-latency multi-tx trials = schedule working under real loss) rather than a duplicate-storm regression (which would show extra transmissions on fast, already-answered requests)"
    why_human: "Real-hardware network behaviour on a specific physical device; 03-03-SUMMARY.md itself sets human_judgment: true and asks for exactly this sanity-check before RETRY-02 real-world evidence is treated as settled"
---

# Phase 3: Retry Schedule Reshape — Verification Report

**Phase Goal:** Request retries stop firing duplicates on healthy networks, consume responses the moment they arrive, and never exceed the caller's timeout
**Verified:** 2026-07-17T15:19:30Z
**Status:** passed (all automated criteria pass; the one human-judgement item is now resolved)
**Re-verification:** Yes — resolved after human UAT (see Re-verification Note below)

## Re-verification Note (2026-07-17)

Resolved during `/gsd-verify-work 03`. The report's single `human_verification`
item — sanity-checking the run-1 FAIL / run-2 PASS zero-loss hardware sequence
(03-03) as a genuine transient WiFi-loss event rather than a duplicate-storm
regression — was **confirmed PASS by the operator** in UAT (`03-UAT.md` test 1).
All eight UAT checks passed (7 automated coverage entries + this human
checkpoint), 0 issues. Status advances `human_needed` → `passed`.

Additionally, since initial verification (2026-07-17T01:35Z), `connection.py`
was edited by later phase-05 commits (`fix(05-05)` source overrides,
`docs(05-06)` docstring de-jargoning). Behaviour was re-confirmed against the
current code: `uv run pytest tests/test_network/test_connection_retry.py
tests/test_network/test_concurrent_requests.py` → **27 passed**; git tree clean.
The specific `connection.py` line numbers cited in the evidence below may have
drifted under those edits, but the asserted behaviour (floored first window,
listen-during-backoff, wall-time deadline, shared-queue correlation) is intact.

## Gates Run by the Verifier (not taken from SUMMARYs)

| Gate | Command | Result |
|------|---------|--------|
| Full suite | `uv run --frozen pytest` | **2563 passed, 12 deselected, 112.29 s** — exit 0 |
| Branch coverage (network suite) | `uv run pytest tests/test_network/ --cov=lifx --cov-branch --cov-report=term-missing` | 252 passed; connection.py missing entries all outside the phase edit range (see below) |
| Type check | `uv run pyright` | 0 errors, 0 warnings |
| Lint | `uv run ruff check .` / `ruff format --check .` | All checks passed / 221 files already formatted |

**Coverage edit-range audit:** connection.py's Missing column (both full-suite and network-only runs): `223->227, 227->240, 232-237, 245-246, 250->253` (`close()`), `298, 368, 377, 386-399, 415-426` (`send_packet`/`_background_receiver`), `876->exit, 909->exit` (`request_stream()` SET/EchoRequest loop arcs). Every entry is a pre-existing gap OUTSIDE the phase's edited ranges (`_transmit_and_listen` L428–665, wrappers L667–749, docstrings, const import). 100% line + branch coverage on the phase's edits, independently confirmed.

## Goal Achievement

### Observable Truths (ROADMAP Phase 3 Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Healthy network sends exactly one packet; first window floored ~200 ms with escalating gaps replacing the 31 ms-doubling shape | ✓ VERIFIED | `REQUEST_RETRANSMIT_GAPS = (0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0, 2.0, 3.0, 4.0, 5.0)` in const.py; behavioural tests run and pass: `test_healthy_network_single_transmission` (emulator, exactly 1 send), `test_no_retransmit_before_first_gap_floor` (1 send under 0.15 s timeout), `test_escalating_gaps_drive_retransmits`, `test_gap_exhaustion_repeats_final_gap`; hardware: 1.017 packets/trial vs 1.37 baseline |
| 2 | Response arriving between retransmits completes the request immediately — no blind sleeps | ✓ VERIFIED | `grep asyncio.sleep connection.py` → only L183 (`open()` concurrency poll, pre-existing, outside request paths); all waiting folds into one `asyncio.wait_for(queue.get(), timeout=wait)` (L603–614); `test_response_between_retransmits_completes_immediately` asserts elapsed < 0.3 s against a 0.5 s gap; hardware median latency 12.6 ms vs 62 ms baseline |
| 3 | `timeout` honoured as wall time — a 16 s budget can never take 29 s | ✓ VERIFIED | Single `deadline = start + timeout` computed once (L521), every wait bounded by `deadline - now`; `TestRetryTimeoutBudget` (3 emulator drop-all tests): `2.0 <= elapsed < 2.3` under total loss, GET and SET both `< timeout + 0.3`, "after N attempts" reports transmissions actually sent |
| 4 | Shared-queue correlation across all issued sequences; late replies accepted, duplicates silently discarded, never protocol errors | ✓ VERIFIED | One source + ONE shared queue + `correlation_keys` per logical request (L502–512); fresh sequence per retransmit registered to the SAME queue (L573–576); `finally` pops all keys → post-cleanup stragglers hit `_background_receiver`'s DEBUG unmatched path; tests: `test_late_reply_to_earlier_sequence_accepted`, `test_late_ack_to_earlier_sequence_accepted` (the D3-04 ACK behaviour change), `test_duplicate_response_discarded_silently` (queue drained, `_pending_requests == {}`), plus wrong-source/out-of-range/serial-mismatch raising `LifxProtocolError` |
| 5 | Existing callers of `DeviceConnection.request()` (incl. `timeout`/`max_retries`) work unmodified | ✓ VERIFIED | `_request_stream_impl`/`_request_ack_stream_impl` names and signatures unchanged (mock seam, L667–749); `request()`/`request_stream()` signatures unchanged; full suite green with only the three enumerated `TestRetryTimeoutBudget` tests changed vs the pre-phase baseline; StateUnhandled semantics preserved in the ACK wrapper |

**Score:** 5/5 truths verified (0 present-but-behaviour-unverified — every truth has a passing behavioural test the verifier ran)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | `docs/api/network.md:132` + `docs/architecture/overview.md:136` still describe exponential backoff/jitter | Phase 5 | Phase 5 goal covers "accurate guidance on the wire behaviour the library now guarantees"; explicitly handed off in 03-02-SUMMARY.md |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lifx/const.py` | `REQUEST_RETRANSMIT_GAPS` Photons-shaped constant | ✓ VERIFIED | Exact spike-002 expansion; Australian-English comment; imported and read at runtime |
| `src/lifx/network/connection.py` | `_transmit_and_listen` shared engine + thin wrappers | ✓ VERIFIED | 238-line engine (L428–665) with full docstring; both wrappers delegate; wired via imports and 20 Wave-0 tests |
| `tests/test_network/test_connection_retry.py` | 16-row branch-matrix suite, ≥250 lines | ✓ VERIFIED | 712 lines, 18 tests (17 planned + 1 coverage-gap test), all pass |
| `tests/test_network/test_concurrent_requests.py` | Rewritten `TestRetryTimeoutBudget` (wall-time contract) | ✓ VERIFIED | 3 tests assert `timeout <= elapsed < timeout + 0.3`; only that class changed (git history confirms b1628e7 touched only this file) |
| `.planning/.../uat_zero_loss.py` | Harness with fixed 0/1/2 exit contract, ≥80 lines | ✓ VERIFIED | Thresholds (`median==1.0`, `mean<=1.05`) match plan; `git diff 0a8d0df..HEAD` on the file is EMPTY — byte-identical since Task 1, thresholds untouched by the runs |
| `.planning/.../03-UAT-RESULTS.json` | Machine-readable measurement evidence | ✓ VERIFIED | 60 per-trial records, mean 1.0167, median 1.0, latency median 12.58 ms, pass true, baseline block present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| connection.py | const.py | runtime read of `REQUEST_RETRANSMIT_GAPS` | ✓ WIRED | Module-level import; `iter(REQUEST_RETRANSMIT_GAPS)` inside the generator body (L517) — call-time read, patchable; `uv run python -c` attribute assertion from the plan passes |
| `_request_stream_impl` | `_transmit_and_listen` | async-for delegation, `res_required=True`, noun "response" | ✓ WIRED | L693–701 |
| `_request_ack_stream_impl` | `_transmit_and_listen` | async-for delegation, `ack_required=True`, noun "acknowledgement"; StateUnhandled stays in wrapper | ✓ WIRED | L736–749 |
| `_transmit_and_listen` | `_background_receiver` | `(source, sequence, serial)` → shared queue in `_pending_requests`; all keys popped in `finally` | ✓ WIRED | L529–531, 573–576, 659–660; routing code unchanged |
| test suite | connection.py | patching `lifx.network.connection.{REQUEST_RETRANSMIT_GAPS,_STREAM_IDLE_TIMEOUT}` + injection via real `_pending_requests` queues | ✓ WIRED | Both patterns present throughout test_connection_retry.py; no `wait_for` mocking |
| uat_zero_loss.py | connection.py | `from lifx.network.connection import DeviceConnection`, send-count spy on the bound method | ✓ WIRED | Drives the shipped `request()`; no hand-rolled schedule |

### Deletions Real (D3-01/02 teardown)

`grep -n '_calculate_retry_sleep_with_jitter\|_RETRY_SLEEP_BASE\|import random\|_DEFAULT_IDLE_TIMEOUT' src/lifx/network/connection.py` → **no code hits** (only docstring prose mentioning "blind asyncio.sleep" as prohibited). Runtime assertion of all six add/delete conditions from the 03-02 acceptance criteria passes.

### D3-01..06 Compliance

| Decision | Status | Evidence |
|----------|--------|----------|
| D3-01 floored window + escalating gaps | ✓ | Constant + truth 1 tests |
| D3-02 listen during backoff, no blind sleeps | ✓ | Truth 2 evidence; jitter machinery deleted |
| D3-03 timeout is wall time | ✓ | Truth 3 evidence |
| D3-04 correlation contract, fresh sequence, shared queue, silent late-discard | ✓ | Truth 4 evidence; late discard reuses `_background_receiver`'s unmatched DEBUG path with zero new code |
| D3-05 public API unchanged, `max_retries` reinterpreted + documented, constants in const.py | ✓ | `__init__` docstring documents cap-vs-budget "whichever binds first"; timeout default corrected to 16.0; class docstring updated |
| D3-06 scope = connection.py request paths only | ✓ | `git log --name-only 25aa1f2~1..a17c4d8`: only const.py, connection.py, the two test files, phase-dir artefacts, and planning docs. discovery.py / mdns/ / animation/ untouched |

### Deviation Verdicts (03-02-SUMMARY.md)

**Deviation (a) — `_STREAM_IDLE_TIMEOUT` patched into `test_discovery_connection_accepts_any_target` (a 03-01 RED test) during the GREEN plan, despite the GREEN gate demanding tests untouched:**

**Verdict: LEGITIMATE CORRECTION — not test-weakening.** Independently reproduced by the verifier: a scratch replica of the test WITHOUT the patch, run against the shipped engine, completes in **2.002 s** — exceeding the test's own `asyncio.wait_for(task, timeout=1.0)` bound (the `_drive()` consumer never breaks early, so it must wait out the full 2.0 s idle window / wall deadline). The test's actual assertions (`len(yields) == 1`, discovery serial-skip acceptance) are byte-for-byte unchanged; only the timing scaffolding was aligned with the exact idiom its three sibling `_drive()` tests already used (0.3/0.4/10.0 s patches). The old pass was a coincidental artefact of the exponential per-attempt windowing (~0.29 s truncation), exactly as claimed. The behaviour under test (B11 False) is orthogonal to the idle window. Properly disclosed as a deviation with empirical verification before the edit.

**Deviation (b) — `# pragma: no branch` on the ACK wrapper's async-for:**

**Verdict: JUSTIFIED.** Structural analysis: the loop body unconditionally exits via `raise LifxUnsupportedCommandError` (StateUnhandled) or `yield True; return` on its first item; the delegate either yields (wrapper exits inside the body before a second `__anext__` reaches the delegate's end) or raises `LifxTimeoutError` without yielding (propagates through the async-for). The natural-exhaustion `->exit` arc is therefore unreachable by construction. The precedent claim is **confirmed by the verifier's own coverage run**: `876->exit` and `909->exit` — the identical `async for … yield; return` pattern in `request_stream()`'s untouched SET and EchoRequest branches — appear as unaddressed pre-existing partials in the Missing column. The companion test `test_ack_wrapper_direct_call_completes_naturally` genuinely covers the `return` line (second `__anext__` path) rather than papering over it. The pragma suppresses one uncoverable arc, consistent with the phase's anti-clamp guidance; no control flow was distorted.

### UAT Protocol Verdict (03-03)

**Verdict: SOUND — honest evidence handling, not cherry-picking.** Facts verified:

- The single re-run was **pre-sanctioned in the plan before any run existed** (03-03-PLAN Task 2: on exit 1, "re-run ONCE to rule out a transient network event… if it fails again flag the result prominently"). One re-run happened; it did not fail again.
- The harness is **byte-identical** to its Task 1 commit (`git diff 0a8d0df..HEAD -- uat_zero_loss.py` empty): thresholds, trial count, and pass logic untouched between/after runs.
- **Both runs are reported**: run 1's FAIL numbers (mean 1.083, trials 52/53 at 5 and 2 tx, trial-52 latency 1848.9 ms, median 1.0, latency 17.3 ms) are in the SUMMARY in full; run 2's per-trial data is the canonical JSON.
- The transient interpretation is **diagnostically supported**: 58/60 run-1 trials sent exactly 1 packet; the two multi-tx trials show *high* latency (~1.85 s ≈ the cumulative gap schedule under real loss). The regression the gate targets — duplicate storms — manifests as extra transmissions on *fast, already-answered* requests (the spike-002 defect). Run 1's failure signature is the schedule working under genuine loss, not the defect returning.

**Statistical assessment:** a mean-1.05 gate on n=60 with one sanctioned re-run leaves a non-trivial pass-by-chance window for a marginal regression, but the conjunctive gate (median==1.0 AND zero failures AND mean≤1.05) plus mandatory disclosure of the failing run bounds the cherry-picking room. Acceptable for an *optional, supplementary* measurement whose requirements were already closed by emulator-backed tests.

**Recommended tightening for future hardware gates (non-blocking):**
1. Prefer Phase 2's repeated-rounds design (≥N rounds, median-of-rounds gate) over single-run mean with a one-re-run escape hatch — it makes transients self-averaging instead of protocol-adjudicated.
2. Give the results JSON a multi-run schema so a failing run's per-trial arrays land on disk in the machine-readable artefact, not only in SUMMARY prose.
3. Consider a latency-conditioned duplicate metric (an extra transmission counts against the gate only when the winning response latency < the first gap), which mechanically separates genuine-loss retransmits from duplicate storms.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RETRY-01 | 03-01, 03-02, 03-03 | Floored first window, escalating gaps, no healthy-network duplicates | ✓ SATISFIED | Truth 1 |
| RETRY-02 | 03-01, 03-02, 03-03 | Listen during backoff, immediate consumption | ✓ SATISFIED | Truth 2 (hardware portion → human item) |
| RETRY-03 | 03-01, 03-02 | Wall-time budget | ✓ SATISFIED | Truth 3 |
| RETRY-04 | 03-01, 03-02 | Shared-queue correlation, late replies accepted | ✓ SATISFIED | Truth 4 |

No orphaned requirements: REQUIREMENTS.md maps exactly RETRY-01..04 to Phase 3; all four appear in plan frontmatter; traceability table rows RETRY-01..04 = "Complete" are accurate.

### Traceability Accuracy

- **REQUIREMENTS.md**: RETRY-01..04 checked `[x]`, traceability "Complete" — matches verified evidence. ✓
- **ROADMAP.md**: Phase 3 "Plans: 3/3 plans executed", all plan checkboxes `[x]`; progress table row still "In Progress" with blank Completed date — correct *pending this verification*; should flip to Complete when the phase closes. ✓
- **STATE.md**: `stopped_at: Completed 03-03-PLAN.md` correct; two prose lines stale ("Plan 03-03 … next", `last_activity_desc` referencing Plan 02) and the `progress:` block (total_phases 4, 5/5 plans, 100% bar vs "Phase 3 of 5") is internally inconsistent. ℹ️ Info-level hygiene, not a goal gap.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.planning/.../uat_zero_loss.py` | 211 | word "placeholder" in a `# nosec` comment on the ENV-ERROR path's `"pass": None` | ℹ️ Info | Deliberate JSON null meaning "not evaluated"; the measured path populates a real verdict (JSON on disk has `"pass": true`). Not a stub |
| `.planning/.../03-VALIDATION.md` | frontmatter | `status: draft`, `nyquist_compliant: false`, `wave_0_complete: false`, sign-off pending | ⚠️ Warning | The validation contract was honoured in practice (Wave 0 RED confirmed, sampling gates run, full suite green) but the document was never flipped to `validated`. Process hygiene only — every gate it mandates was independently re-run and passed by this verification |
| `CLAUDE.md` | ~244 | "serialized via `_request_lock`" — no such lock exists | ℹ️ Info | Pre-existing docs-rot, pre-dates the phase, flagged in 03-02-SUMMARY handoff for a documentation pass |

No TBD/FIXME/XXX/TODO markers in any phase-modified source or test file.

### Human Verification Required

#### 1. Run-1 transient-event interpretation (optional hardware measurement)

**Test:** Review 03-03-SUMMARY.md's run-1 numbers (mean 1.083; trials 52/53 at 5 and 2 transmissions; trial-52 latency 1848.9 ms; median 1.0) against the canonical run-2 PASS JSON.
**Expected:** Concur that run 1 shows genuine WiFi loss (high-latency multi-tx trials, schedule behaving as designed) rather than a duplicate-storm regression (extra tx on fast-answered requests) — then RETRY-02's real-world evidence stands.
**Why human:** Physical-device network behaviour; 03-03-SUMMARY itself sets `human_judgment: true` requesting exactly this check. Requirements RETRY-01..04 are already closed by the emulator-backed automated suite regardless of this item's outcome.

### Gaps Summary

None. All five ROADMAP success criteria are observably true in the codebase with behavioural tests the verifier executed directly (2563 passed). Both disclosed deviations were independently investigated and classified as legitimate (one empirically reproduced, one confirmed structurally and by coverage precedent). The UAT re-run protocol was pre-declared, honoured, and honestly reported. The single outstanding item is the executor's own request for human sign-off on the hardware run-1 interpretation — supplementary evidence for already-closed requirements.

---

_Verified: 2026-07-17T01:35:00Z_
_Verifier: Claude (gsd-verifier)_

---

## Addendum: Human item resolved by measurement (2026-07-17)

Operator requested 5 additional harness runs (thresholds untouched, back-to-back,
5 s apart) to settle the run-1 transient question empirically. Seven-run distribution:

| Run | Mean pkts/trial | Median | Gate |
|-----|-----------------|--------|------|
| 1 (original) | 1.083 | 1.0 | fail |
| 2 (original) | 1.017 | 1.0 | pass |
| 3 | 1.000 | 1.0 | pass |
| 4 | 1.100 | 1.0 | fail |
| 5 | 1.000 | 1.0 | pass |
| 6 | 1.017 | 1.0 | pass |
| 7 | 1.000 | 1.0 | pass |

Median = 1.0 in all seven runs; 0 request failures in 420 trials; failing runs contain
only isolated slow multi-tx trials (1.2–1.8 s recovery latency) — the transient-loss
signature, not the duplicate-storm signature (which would show many fast multi-tx
trials). **Human item 1 resolved: run 1 confirmed transient. Overall verdict upgraded
to: passed.** The distribution also confirms the recommendation to prefer
repeated-run median gates for future hardware UATs.
