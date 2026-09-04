---
phase: 14-thread-revalidation-and-docs
verified: 2026-09-04T23:05:00Z
status: passed
score: 8/8 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 7/8
  gaps_closed:
    - "The generated evidence report records Thread animation as an out-of-scope scope boundary and states what the Candle observation is not evidence of (AC-04, AC-05)"
  gaps_remaining: []
  regressions: []
  human_items_closed:
    - "_cli_validate ship/no-ship decision — fixed in 7041717, independently re-verified"
gaps: []
deferred: []
---

# Phase 14: Thread Revalidation and Docs Verification Report

**Phase Goal:** Revalidate discovery, request timing, and advertisement expiry on the currently available Thread lighting classes; record Thread animation as an explicit, non-gating scope boundary rather than a measurement to complete; preserve privacy-safe and explicitly qualified evidence for every public device class; and publish accurate consumer and architecture guidance without treating the operator's currently interference-affected mesh as an authoritative performance benchmark.

**Verified:** 2026-09-04 (re-verification after commit `7041717`)
**Status:** passed
**Re-verification:** Yes — after gap closure. Previous: gaps_found, 7/8.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Discovery coverage over Thread is measured across repeated rounds, never a single round (SC-1, THREAD-01) | ✓ VERIFIED | `14-DISCOVERY.jsonl` holds 12 rows: 6 rounds × `discover` + 6 × `discover_mdns`, rounds 1-6 on both legs, all `outcome: success`, all 8 roster aliases in every round. `14-MANIFEST.json` freezes 6 rounds and 5 inter-round gaps (6.19-13.64 s) before collection. Coverage keyed per session/source/round/alias, so duplicate packets cannot inflate it |
| 2 | The WiFi-tuned retry constants are measured against Thread ack RTT, and no constant changes from this observation (SC-2, THREAD-02) | ✓ VERIFIED | `14-REQUESTS.jsonl` holds 800 rows: exactly 100 unique trials (1-100) for each of 8 aliases, all `provenance: physical`. Both D-07 latencies per trial. Recomputed medians/p95/max match `14-SUMMARY.json`. `REQUEST_RETRANSMIT_GAPS` in `src/lifx/const.py` untouched — `git log -L` shows last change was v1.1 commit `2255bb8`. Only 7 of 800 acks exceeded 200 ms |
| 3 | Border-router advertisement staleness is measured directly by unplugging a Thread device (SC-3, THREAD-04) | ✓ VERIFIED | `14-STALENESS.jsonl`: `LIFX-Ceiling-13x26-1`, `disconnect_ns` recorded, all 72 polls retained at the frozen 60 s cadence with both legs logged separately, `first_absence_poll: 70` (t+4200 s), `confirmed_expiry_poll: 72` after three consecutive both-absent pairs, `disposition: confirmed_expiry` (not censored; well inside the 10800 s cap), `restored_available_ns` and `restoration_duration_s: 69.36` prove restored availability |
| 4 | Every public lighting class carries exactly one disposition — evidence or a dated named gap, with gaps only for InfraredLight and HevLight (SC-4, THREAD-05) | ✓ VERIFIED | Re-derived independently: `complete: true`, `missing_classes: []`. Six classes, one disposition each. `Light` (4), `MultiZoneLight` (1), `MatrixLight` (2 distinct), `CeilingLight` (1) `evidence_backed`; `InfraredLight` and `HevLight` `named_gap` dated 2026-09-04. Gap legality re-proved empirically: removing one MatrixLight alias's trials yields `missing: ['MatrixLight']`, never a named gap |
| 5 | Class closure never depends on an animation attempt; the rescope is coherent across every authority (THREAD-03) | ✓ VERIFIED | `derive_class_ledger_from_roster()` takes only `inventory`, `discovery_rows`, `request_rows`, `closure_rows`. `_alias_has_physical_animation_attempt()` deleted, not unwired. `test_thread_revalidation.py:3932` pins the absence by reflection; line 3879 closes a class with deliberately zero animation evidence. REQUIREMENTS.md, 14-SPEC.md, 14-CONTEXT.md (D-15 superseded) and 14-06-PLAN.md Task 2 all agree; nothing requires an animation measurement |
| 6 | Tracked evidence contains no raw serials, MAC addresses, IP addresses, hostnames or private alias mappings (AC-13) | ✓ VERIFIED | Verified from file bytes, not summaries. Regex sweep for colon-MACs, `d073d5*`, bare 12-hex, IPv4 quads, IPv6 colon groups and `.local/.lan/.home/.arpa`: zero hits. Full enumeration of every JSON key and distinct string value across all 9 files: the complete string vocabulary is aliases, exact class names, event kinds, outcomes, `seed-001`, one 40-char git revision and two gap-reason sentences. The `_RequestObserver` signature `(str, int\|None, int, bool\|None)` is structurally incapable of carrying identity |
| 7 | Consumer and architecture guidance ships accurately: merged/explicit discovery APIs, four named limitations, no false TaskGroup claim (SC-5, DOCS-04/05/06) | ✓ VERIFIED | `docs/user-guide/discovery.md` covers `discover()`, `discover_udp()`, `discover_mdns()`, `find_by_ip()`/IPv6 and troubleshooting, with 4 snippet regions from the single executable `examples/discovery_progressive.py` (RFC 5737/3849 addresses only). Nav-wired in `mkdocs.yml` (lines 128, 207) with `check_paths: true`. All four DOCS-05 limitations present. `CLAUDE.md` is 12 lines: literal `@AGENTS.md` import plus one Claude-specific note. Zero `TaskGroup` in `src/`; the only mentions in `AGENTS.md` and `troubleshooting.md` are the corrections themselves. 31 targeted tests pass |
| 8 | The report and animation evidence record Thread animation as an out-of-scope boundary and state what the observation is not evidence of (AC-04, AC-05) | ✓ VERIFIED (closed by `7041717`) | `14-REPORT.md` now heads the section "Animation (THREAD-03, out of scope)" and states: the recorded scope boundary and why; that `Animator` is intended to be WiFi-locked; that "Class closure does not consult animation at all"; that the observation "shows only that Thread carried the frames without failing"; that it is "NOT evidence that Thread animation is usable" and "not a throughput, pacing, ACK-delivery, smoothness, parity or performance result"; and — beyond what AC-05 asked — that the payload sends one identical brightness-0 frame per call, so the counters cannot be read as rendering behaviour |

**Score:** 8/8 truths verified

### Gap Closure Verification (commit `7041717`)

Both items were re-verified independently against the codebase, not from the fix description.

**Gap 1 — AC-04 / AC-05 report wording: CLOSED.**

Checked clause by clause against the regenerated `14-EVIDENCE/14-REPORT.md`:

| AC clause | Status | Report text |
|-----------|--------|-------------|
| AC-04 out-of-scope | ✓ | Heading "out of scope"; "a recorded scope boundary, not a measurement this phase completes" |
| AC-04 non-gating | ✓ | "Class closure does not consult animation at all." |
| AC-04 cited only as "carries the frames without failing" | ✓ | "shows only that Thread carried the frames without failing" |
| AC-04 no further alias | ✓ | `LIFX-Candle-C-1` is the only alias present |
| AC-05 not usability evidence | ✓ | "It is NOT evidence that Thread animation is usable" |
| AC-05 not parity / smoothness / ACK / throughput | ✓ | "not a throughput, pacing, ACK-delivery, smoothness, parity or performance result" |
| AC-05 cannot gate closure | ✓ | "Class closure does not consult animation at all." |

The report also now discloses the brightness-0 identical-frame payload defect that `14-INTERIM-RESULTS.md` identified, which is a stronger caveat than AC-05 required: it tells a reader the counters cannot be interpreted as rendering behaviour at all.

**Gap 2 — `_cli_validate`: CLOSED, and verified stronger than described.**

Read the new implementation, then tested it on scratch copies (never against the real evidence directory):

- *Writes nothing.* Seeded sentinel bytes into all three products of a full copy of the real session, ran `validate`, and hashed the whole directory before and after: **entire directory byte-unchanged**, sentinels intact. `_cli_validate` no longer contains any write call.
- *Verdict now agrees with the other verbs.* On the real (complete) session copy, `validate` reports `complete: true, missing_classes: []` — previously it reported and wrote `complete: false` with all four available classes missing.
- *Agreement holds in the failing direction too.* Constructed a genuinely incomplete session by deleting `LIFX-Luna-1`'s 100 request trials (800 → 700 rows). `validate` reports `complete: false, missing: ['MatrixLight']`; `generate` reports `ok: false, reason: class_ledger_incomplete, missing: ['MatrixLight']`; neither wrote anything. The two verbs and the roster derivation cannot disagree, and a single missing alias still keeps its whole class incomplete rather than converting to a named gap.
- *`generate` remains the sole, correct producer.* Running `generate` on an untouched scratch copy reproduced the committed products **byte-identically**.
- *Test entrenchment removed.* `test_init_then_validate_round_trip` was inverted from asserting the three products exist to asserting they do not. A new `test_validate_never_overwrites_a_complete_session_s_products` seeds sentinels, runs `validate`, and requires the bytes to survive. Suite went 358 → 359, all passing.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `14-EVIDENCE/14-MANIFEST.json` | Immutable session identity, roster, schedules | ✓ VERIFIED | Passes `_validate_manifest()` and `validate_expected_roster()`; 8-alias roster with two distinct MatrixLight aliases; 99 request gaps inside the D-06 0.5-1.5 s band |
| `14-EVIDENCE/14-DISCOVERY.jsonl` | Six paired physical rounds | ✓ VERIFIED | 12 arms, complete |
| `14-EVIDENCE/14-REQUESTS.jsonl` | Per-device 100-trial request evidence | ✓ VERIFIED | 800 rows; `thread_connection: true` on all 800 — first hardware validation of the frame-address bit added in `b4ae1b8` |
| `14-EVIDENCE/14-STALENESS.jsonl` | One expiry experiment with restoration | ✓ VERIFIED | 72 polls retained, confirmed expiry, restored |
| `14-EVIDENCE/14-ANIMATION.jsonl` | One pre-existing non-gating Candle observation | ✓ VERIFIED | Data honest (`restoration_verified: false` recorded, not glossed); the required qualification now lives in the report, which is the artefact a reader opens |
| `14-EVIDENCE/14-CLOSURE.jsonl` | Per-class dispositions | ✓ VERIFIED | Exactly two `named_gap` rows |
| `14-EVIDENCE/14-SUMMARY.json` | Deterministic summary | ✓ VERIFIED | Byte-identical to independent regeneration |
| `14-EVIDENCE/14-CLASS-LEDGER.json` | Six-class ledger | ✓ VERIFIED | Byte-identical to independent regeneration |
| `14-EVIDENCE/14-REPORT.md` | Human-readable qualified report | ✓ VERIFIED | Regenerates byte-identically; animation section now satisfies AC-04/AC-05 |
| `docs/user-guide/discovery.md` | Canonical discovery guide | ✓ VERIFIED | Present, substantive, nav-wired, snippet-linked |
| `examples/discovery_progressive.py` | Single executable snippet source | ✓ VERIFIED | 4 named regions, documentation-range addresses only |
| `CLAUDE.md` / `AGENTS.md` | Import-only + canonical | ✓ VERIFIED | 12 / 466 lines, contract enforced by 8 tests |
| `scripts/thread_revalidation.py` | Orchestrator | ✓ VERIFIED | 359 tests pass; `validate` is now read-only and verdict-consistent |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `14-MANIFEST.json` | `14-CLASS-LEDGER.json` | roster + journals → `derive_class_ledger_from_roster()` | ✓ WIRED | Independently re-derived; matches committed bytes |
| `14-CLOSURE.jsonl` | `14-CLASS-LEDGER.json` | deterministic journal-only generation | ✓ WIRED | Named gaps flow through; available classes close from the roster, never from a closure claim |
| `_cli_validate` / `_cli_generate` / `validate_staged_evidence` | `derive_class_ledger_from_roster()` | single shared ledger source | ✓ WIRED (new) | Previously `_cli_validate` bypassed it; the three verbs now provably agree in both directions |
| `scripts/measurement_support.py` | `src/lifx/network/connection.py` | task-attribute observer passed explicitly into `_transmit_and_listen()` | ✓ WIRED | Selector at line 63, parameter at 807, 8 event call sites |
| `connection.py` | `14-REQUESTS.jsonl` | value-only observer events → privacy-gated JSONL | ✓ WIRED | `thread_connection` reaches the journal on all 800 rows |
| `docs/user-guide/discovery.md` | `examples/discovery_progressive.py` | `pymdownx.snippets` `--8<--` | ✓ WIRED | 4 regions matched; `check_paths: true` |
| `CLAUDE.md` | `AGENTS.md` | literal `@AGENTS.md` import | ✓ WIRED | Present and test-enforced |

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
|-----------|---------|--------|--------|
| `validate` never writes, even over sentinel products | `validate --session-dir <scratch full copy>` after seeding sentinels | Whole directory byte-unchanged; sentinels intact | ✓ PASS |
| `validate` verdict is correct on a complete session | same | `complete: true, missing: []` | ✓ PASS |
| `validate` and `generate` agree on an incomplete session | Deleted Luna's 100 trials, ran both | Both `missing: ['MatrixLight']`; `generate` `ok: false`; nothing written | ✓ PASS |
| A missing alias never becomes a named gap | same | Class stays incomplete | ✓ PASS |
| `generate` reproduces committed products | `generate --session-dir <scratch copy>` | Byte-identical to committed | ✓ PASS |
| Report satisfies AC-04/AC-05 | Read regenerated `14-REPORT.md` | All clauses present | ✓ PASS |
| Orchestrator suite | `pytest tests/test_scripts/test_thread_revalidation.py` | 359 passed (was 358) | ✓ PASS |
| Guidance/doc contracts | `pytest tests/test_repository_guidance.py tests/test_network/test_mdns/test_phase_contract.py` | 31 passed | ✓ PASS |
| Full suite | `uv run --frozen pytest` | 4834 passed pre-fix; 359/31 targeted suites pass post-fix | ✓ PASS |
| Type check | `uv run pyright` | 0 errors, 0 warnings | ✓ PASS |
| Lint / format | `uv run ruff check . --exclude .claude` / `format --check` | All checks passed; 275 files formatted | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| THREAD-01 | 14-02, 14-03, 14-04, 14-06 | Repeated paired discovery evidence | ✓ SATISFIED | Truth 1 |
| THREAD-02 | 14-01, 14-02, 14-03, 14-04, 14-06 | Request timing and retransmission evidence | ✓ SATISFIED | Truth 2 |
| THREAD-03 | 14-02, 14-03, 14-04, 14-06 | Animation is a recorded scope boundary | ✓ SATISFIED | Truths 5 and 8 |
| THREAD-04 | 14-02, 14-03, 14-04, 14-06 | Observed advertisement staleness | ✓ SATISFIED | Truth 3 |
| THREAD-05 | 14-02, 14-03, 14-04, 14-06 | Per-class evidence or named gap | ✓ SATISFIED | Truth 4 |
| DOCS-04 | 14-05 | Broadcast-first consumer guidance | ✓ SATISFIED | Truth 7 |
| DOCS-05 | 14-05 | Known limitations documented | ✓ SATISFIED | Truth 7 |
| DOCS-06 | 14-05 | Accurate concurrency architecture | ✓ SATISFIED | Truth 7 |

All 8 requirement IDs declared in plan frontmatter are accounted for. REQUIREMENTS.md maps exactly these 8 to Phase 14 — no orphaned requirements.

### Anti-Patterns Found

None blocking. No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK` or `PLACEHOLDER` markers exist in any file this phase created or modified.

## Residual observations (none gating)

These do not block the phase. They are recorded so they are not lost.

1. **`14-06-PLAN.md` line 241 is now accurate for animation but still overstates the request side.** The sentence claims `generate_report()` "already qualifies all animation/request measurements as this fleet/session's observations and makes no authoritative benchmark, universal Thread limit, regression gate, render/smoothness claim or tuning recommendation". The second half is now fully true, and the animation half is true. But the "## Request timing (THREAD-02)" section is still eight lines of bare per-device statistics with no fleet/session framing. This is not an acceptance-criterion failure — AC-03's "qualified by the recorded environment" is satisfied by the journals' explicit `confounders` field, and the non-generalisation statement is published where consumers read it (`docs/user-guide/discovery.md`). Either trim the sentence to animation, or add one qualifying line to the request section.

2. **The new regression test's fixture is an empty session, not a complete one.** `test_validate_never_overwrites_a_complete_session_s_products` inits a session and seeds sentinels without journal rows, so its asserted `missing_classes` is all six classes — which both the old buggy closure-rows ledger and the new roster ledger produce. The sentinel half is a genuine pin (any write fails it), but the *verdict-source* half is not pinned against a case where the two ledger sources diverge. I verified that half empirically instead. A fixture with complete journals would close the loop.

3. **AC-05 wording is met in substance, not verbatim.** The report says "not a throughput, pacing, ACK-delivery, smoothness, parity or performance result". The literal tokens "minimum FPS", "ceiling", "universal limit" and "tuning" do not appear, and the WiFi-only spike is not named. All are stated in the locked documents, and "performance result" plus the brightness-0 payload caveat close the misreading risk. Judged met.

4. **Confounders are empty throughout.** The manifest and all 800 request rows carry `confounders: []` while the goal describes an interference-affected mesh. The data supports the empty array — zero timeouts, retransmissions or failures across 800 trials — so recording none is honest for this session, and AC-09 holds (no constant retuned, verified against `src/lifx/const.py` history).

5. **`.claude/hooks/post-tool-call.py` is untracked and is the only source of lint failure.** `ruff check .` reports 5 errors and `ruff format --check` wants to reformat it; excluding `.claude`, both are clean. Not a phase deliverable, but it needs a commit-or-ignore decision.

6. **ROADMAP.md and STATE.md bookkeeping lag.** ROADMAP still shows Phase 14 unchecked, "5/6 plans executed", and `- [ ] 14-06-PLAN.md`; STATE.md's last activity is "Phase 14 execution started" and its plan-duration table stops at P04; REQUIREMENTS.md's footer still reads "Last updated: 2026-08-29" though all 8 IDs are marked Complete.

7. **Two superseded statements survive in dated historical records.** `14-INTERIM-RESULTS.md:129` ("D-16 is disproportionate and remains unfixed", "THREAD-05 blocked by THREAD-03") and `14-DISCUSSION-LOG.md:46` (pre-amendment D-16 wording). The interim file's header self-declares it as a pre-decision snapshot, so both are honest as history rather than errors.

8. **Scope note on what I verified.** I verified the recorded evidence — schema validity, internal consistency, privacy, determinism and plausibility — not the physical acts themselves. That a Ceiling was actually unplugged for 72 minutes rests on the operator's attestation in `14-06-SUMMARY.md`, as it must for any hardware phase.

## Summary

The phase goal is achieved. Real, privacy-safe physical evidence exists for all four available Thread classes across discovery, request timing and advertisement staleness; the six-class ledger closes correctly and was re-derived independently rather than trusted; the WiFi-tuned constants were measured and deliberately left unchanged; the THREAD-03 rescope is coherent across every locked document, enforced in code by a function that structurally cannot consult animation evidence, and now stated plainly in the generated report; and the documentation deliverables hold under targeted tests.

Both findings from the initial verification are genuinely closed. The report gap was fixed at the generator, not by hand-editing the product, and the products were regenerated. The `_cli_validate` defect was fixed at both halves — `validate` now writes nothing at all, and its verdict comes from the same roster derivation `generate` and the staged validator use, which I confirmed empirically in both the complete and incomplete directions. The test that had entrenched the write now asserts its absence.

---

*Verified: 2026-09-04 (initial), re-verified after `7041717`*
*Verifier: Claude (gsd-verifier)*
