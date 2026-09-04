---
phase: 13-merged-discovery
verified: 2026-08-31T07:07:35Z
status: passed
score: 20/20 must-haves verified
behavior_unverified: 0
overrides_applied: 0
decision_coverage:
  honored: 16
  total: 16
  not_honored: []
human_verification: []
---

# Phase 13: Merged Discovery Verification Report

**Phase Goal:** Thread devices are found by default without making dual discovery mandatory: `discover()` runs broadcast and mDNS legs concurrently merged by serial, `discover_udp()` and `discover_mdns()` expose explicit source-specific enumeration, overlapping UDP callers share one active sweep, `find_by_serial()` races both legs, and the existing discovery contract survives measurably intact.
**Verified:** 2026-08-31T07:07:35Z
**Status:** passed
**Re-verification:** Yes — post-verification mDNS interface-binding security repair and signed PR-history consolidation
**Production implementation revision:** `39bad58c42627ac3612868503bb5fb9305b04cc3`

## Goal Achievement

### Roadmap Success Criteria

| # | Roadmap truth | Status | Evidence |
|---|---|---|---|
| 1 | Pre-merge invariants and measurement entry gate existed before merge code | ✓ VERIFIED | `13-ENTRY-GATE.md` retains the frozen original base and no-diff result; the Plan 13-01 tests and direct-UDP measurement path remain present. The later PR-history consolidation preserves the artefact while replacing the original execution commit sequence with signed consolidated commits. |
| 2 | Default discovery concurrently merges UDP and mDNS, streams first-valid devices, and isolates expected mDNS failure | ✓ VERIFIED | `src/lifx/api.py:1058-1206` creates both pumps, merges by canonical serial, streams winners, absorbs typed mDNS failures and reaps both tasks. Named merge/failure tests passed during this verification. |
| 3 | mDNS candidates are directly verified before yield | ✓ VERIFIED | `src/lifx/network/discovery/mdns/discovery.py:1314-1453` classifies the product, sends correlated `GetColor`/`EchoRequest`, validates the response and closes the connection before returning a device. Candidate/lifecycle tests passed. |
| 4 | `find_by_serial()` races both sources and reaps the loser | ✓ VERIFIED | `src/lifx/api.py:1333-1515` owns one dual-source race and executes `_cancel_and_reap()` before returning or constructing the UDP winner. Both source-winner variants passed. |
| 5 | Timing/result change and FIND-08 disposition are recorded | ✓ VERIFIED | The canonical validator accepted one emulator pair and six fleet pairs at the production revision. The summary records raw timings/counts, confounds and the non-gating `no_eligible_find08_population` disposition. |
| 6 | Explicit UDP/mDNS APIs remain available and compatible overlapping UDP callers share only one active sweep | ✓ VERIFIED | Public exports are present in `lifx.api` and `lifx`; the coordinator key contains only wire/timing settings, retains active-only state and replays the accepted prefix. Named sharing/replay tests passed. |

### Observable Truths — Consolidated SPEC Acceptance Contract

The twenty SPEC acceptance criteria consolidate every roadmap success criterion and every Plan 13-01 through 13-07 truth group. Plan-specific edge assertions are covered by the referenced behavioural suites rather than counted again as duplicate truths.

| # | Truth | Status | Evidence |
|---|---|---|---|
| AC1 | Broadcast-only invariant and measurement entry gate preceded merged implementation | ✓ VERIFIED | Immutable entry-gate artefact records the original base and no-diff result; the unchanged public/lower-level invariant tests remain collected and green. The post-execution squash intentionally consolidates the original chronological commits. |
| AC2 | `discover()` runs both legs, yields source-only devices and yields nothing on an empty network | ✓ VERIFIED | Two task pumps at `api.py:1139-1156`; merge/empty behavioural tests in `TestDiscoverMerged`. |
| AC3 | Canonical serial dedup is first-valid with no fixed source priority | ✓ VERIFIED | `api.py:1187-1204`; both parametrisations of `test_first_fully_valid_duplicate_wins_without_source_priority` passed. |
| AC4 | Expected mDNS open/receive/partial failures leave UDP productive | ✓ VERIFIED | Typed failure handling at `api.py:142-197`; open and receive parametrisations of the live-sweep degradation test passed. |
| AC5 | Later default calls start fresh mDNS work | ✓ VERIFIED | mDNS source factory and state are created inside every `discover()` invocation; active tests cover success, empty and prior-failure repetition. |
| AC6 | Only currently answering, valid mDNS candidates can yield | ✓ VERIFIED | Direct request/response validation at `discovery/mdns/discovery.py:1314-1453`; cancellation reaping and unsupported-candidate continuation tests passed. |
| AC7 | Serial lookup handles both winner orders, no-match/failure/concurrency/cancellation and reaps work | ✓ VERIFIED | `_race_serial_sources()` plus active `TestFindBySerialRace` and lifecycle matrix; both winner variants passed in this verification. |
| AC8 | `discover`, `discover_udp` and `discover_mdns` are exported with exact source participation and no selector | ✓ VERIFIED | `src/lifx/__init__.py:14-18,157-159`, `src/lifx/api.py:1058,1209,1268`; public-signature test passed. |
| AC9 | `find_by_serial()` remains dual-source; IP and label lookup retain their source contracts | ✓ VERIFIED | Serial race starts both sources; `find_by_ip()` still calls direct `discover_devices()` and `find_by_label()` retains packet-targeted UDP behaviour. No source-selector parameter exists. |
| AC10 | Compatible overlapping callers generate one UDP schedule | ✓ VERIFIED | `_UdpSweepKey` and active registry in `discovery/coordinator.py`; `test_compatible_subscribers_share_one_active_producer` passed. |
| AC11 | Late subscribers receive prefix then suffix once and in order | ✓ VERIFIED | Append-before-fan-out coordinator log and `test_late_subscriber_receives_prefix_then_suffix_once`, which passed. |
| AC12 | Non-last close preserves the producer; last close cancels and reaps it | ✓ VERIFIED | Coordinator detach/shutdown ownership is substantive and wired; focused Phase 13 lifecycle gate and independent code review cover final detach/resource closure. |
| AC13 | Wire/timing differences split sweeps while device settings remain caller-local | ✓ VERIFIED | Compatibility key includes address, port, timeout, response time and idle multiplier only; construction applies per-subscriber timeout/retries after fan-out. Active compatibility tests cover both directions. |
| AC14 | Completed positive, empty and failed sweeps are never retained | ✓ VERIFIED | Coordinator removes terminal active entries; repetition/no-cache tests cover all terminal classes. There is no TTL or completed-result cache. |
| AC15 | At least six fleet pairs and one final-revision emulator pair retain comparable raw measurements | ✓ VERIFIED | Independent aggregation found 14 rows at `39bad58…`: seven baseline and seven merged arms, comprising one emulator and six fleet pairs. `--validate-only --final-revision 39bad58…` exited 0. |
| AC16 | Harness preserves raw values, rejects incomparable evidence, reports deltas without a ceiling and does not retune | ✓ VERIFIED | Schema/summary logic is substantive; validator passed. `src/lifx/const.py`, `pyproject.toml` and `uv.lock` are unchanged from the phase base to production revision, and no Phase-specific CI measurement remains. |
| AC17 | FIND-08 uses integer 3.70–3.99 boundaries and records an empty eligible population honestly | ✓ VERIFIED | Integer-boundary and normalisation tests exist; row-order/dedup and empty-population behavioural tests passed. Final evidence records `no_eligible_find08_population`. |
| AC18 | Source entry point changes discovery participation only | ✓ VERIFIED | Every source path passes the same caller device timeout/retry values and constructs the same device classes/connectivity metadata. Public-surface tests and source inspection show no routing/tuning selector. |
| AC19 | Tracked Phase 13 material contains no live/private identifiers or mappings | ✓ VERIFIED | Canonical validator passed; privacy rejection tests passed; security audit reports no raw identity/address/mapping leakage. The private handoff is ignored and mode `0600`. |
| AC20 | Discovery/lifecycle tests and repository quality gates pass with 100% changed-code coverage | ✓ VERIFIED | Fresh post-squash gates: 4,401 passed/12 deselected; Ruff and Pyright clean; 1,990 changed executable lines and 676 changed branches at 100%. The mDNS bind regression suite passed 53 tests, independent review is clean, GitHub alert 18 is fixed, and security is `SECURED` 32/32. |

**Score:** 20/20 truths verified (0 present-but-behaviour-unverified)

## Unsupported Product Boundary

Unsupported relay/button-only products such as LIFX Switches are automatically excluded before `discover()` yields a device:

1. UDP: `DiscoveredDevice.create_device()` calls `get_device_class_for_product()`; relay/button-only products raise `LifxUnsupportedDeviceError`, which is converted to `None` (`discovery/udp.py:209-215`). `_pump_udp_discovery()` enqueues only non-`None` devices (`api.py:116-126`).
2. mDNS: `_verify_mdns_candidate()` runs the same classifier and returns `None` for an unsupported candidate (`discovery/mdns/discovery.py:1346-1359`), so it cannot enter the merge queue.
3. Public boundary: `discover()` yields only `device` events from those two filtered pumps (`api.py:1187-1204`).
4. Evidence boundary: measurement source and FIND-08 observations are intersected with identities actually yielded by the public call (`scripts/measure_merged_discovery.py:960-1023,1045-1104`). Therefore unsupported Switch serials need no alias-map entries.

The public-boundary test alone mocks `create_device()` returning `None`, so it is not sufficient in isolation. It is paired with real product-classification tests for a synthetic LIFX Switch on UDP and mDNS. All four named filtering tests passed (`4 passed`).

## Required Artifacts

Historical Plan 13-01 through 13-06 paths were intentionally consolidated by Plan 13-07. `13-PATH-AMENDMENT.md` is the authoritative mapping; raw artefact-query “missing” results for former module paths are not missing implementation.

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/lifx/api.py` | Public dual/source-specific discovery and serial race | ✓ VERIFIED | Substantive implementation, exported and used by public callers/tests. |
| `src/lifx/network/discovery/udp.py` | UDP validation, raw/shared discovery and device construction | ✓ VERIFIED | Canonical replacement for former `network/discovery.py`; public compatibility umbrella remains. |
| `src/lifx/network/discovery/coordinator.py` | Process-wide active UDP single-flight | ✓ VERIFIED | Canonical replacement for former `discovery_coordinator.py`; wired from `discover_devices_shared()`. |
| `src/lifx/network/discovery/mdns/discovery.py` | Record assembly, direct liveness and supported-device construction | ✓ VERIFIED | Canonical implementation; former `lifx.network.mdns` modules are thin compatibility re-exports. |
| `src/lifx/devices/light.py` | StateColor adoption without volatile getter caching | ✓ VERIFIED | Private adoption helper is called only after a valid direct response. |
| `tests/test_discovery_observation.py` | Repository-only observation model/capture | ✓ VERIFIED | Intentionally absent from installed source. Production imports neither this test module nor observation context state. |
| `scripts/measure_merged_discovery.py` | Paired measurement, privacy validation and deterministic summary | ✓ VERIFIED | Calls direct UDP for baseline and public `discover()` for merged; filters raw observations by yielded identities. |
| `13-MEASUREMENTS.jsonl` / `13-MEASUREMENT-SUMMARY.md` | Append-only paired evidence and derived summary | ✓ VERIFIED | Final-revision validator exited 0; the 282,350-byte pre-restamp prefix is unchanged with SHA-256 `db10fa2387b858a55a8e06c0cafed49a667b9d7e07dacbcd3d007e84653eb59d`, and the regenerated summary SHA-256 is `d0aa02d57348ad65b6b4a9148cd74477d81c265efc259b14fff044bccadea9e2`. |
| `13-ENTRY-GATE.md` | Pre-merge invariant evidence | ✓ VERIFIED | Exists, substantive and earlier than merge implementation. |
| `13-REVIEW.md` / `13-SECURITY.md` | Independent review gates | ✓ VERIFIED | Clean review; `SECURED`, 32 closed and 0 open threats. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Public `discover()` | shared UDP | `discover_devices_shared()` | ✓ WIRED | Caller deadline and observer are passed explicitly. |
| Public `discover()` | verified mDNS | `_discover_verified_devices_mdns()` | ✓ WIRED | Same caller deadline; typed failure sink and verified devices only. |
| Shared UDP facade | coordinator | `subscribe_udp_sweep()` | ✓ WIRED | Raw accepted records are fanned out before caller-specific construction. |
| mDNS verifier | network connection | `DeviceConnection.request()` | ✓ WIRED | Correlated request is bounded by remaining caller deadline and always closed. |
| mDNS verifier | device state | `_adopt_state_color()` | ✓ WIRED | A valid `StateColor` seeds construction state before eligibility. |
| Public packages | source-specific APIs | imports and `__all__` | ✓ WIRED | Exact top-level and `lifx.api` exports are active. |
| Measurement harness | public discovery/evidence | `_measure_arm()` → `discover()` → yielded-identity intersection | ✓ WIRED | Only supported public results require aliases or contribute to evidence. |

## Data-Flow Trace (Level 4)

| Artifact | Data | Source | Produces real data | Status |
|---|---|---|---|---|
| `discover()` | yielded `Device` | validated UDP response or directly verified mDNS response | Yes | ✓ FLOWING |
| UDP coordinator | replayed discovery records | one active `_discover_with_packet()` producer | Yes; no completed/static cache | ✓ FLOWING |
| Measurement row | device aliases/source contribution | identities actually yielded by direct UDP/public merged calls | Yes; raw observations not yielded are discarded | ✓ FLOWING |
| Measurement summary | timing/count/source deltas | validated JSONL keyed by revision/scenario/pair/round/arm | Yes; deterministic and row-order independent | ✓ FLOWING |

## Behavioural Spot-Checks

| Behaviour | Result | Status |
|---|---|---|
| UDP/mDNS/public unsupported-product filtering | Four named tests, including a synthetic LIFX Switch product, passed | ✓ PASS |
| First-valid merge, mDNS failure isolation, serial race, sharing, replay and mDNS cancellation | Ten named tests passed in 0.05 s | ✓ PASS |
| Privacy, finite confounds, deterministic row order, final revision and unsupported evidence filtering | Eight named tests passed in 0.05 s | ✓ PASS |
| FIND-08 normalisation/dedup row-order invariant | Named test passed | ✓ PASS |
| Canonical evidence validation at production revision | `--validate-only --final-revision 39bad58…` exited 0 | ✓ PASS |

The complete repository suite was rerun during post-fix goal verification: 4,401
tests passed and 12 were deselected. One deterministic cancellation test replaced
timing-dependent coverage of the coordinator's final-detach cleanup branch.

## Probe Execution

N/A — no Phase 13 probe script is declared and no conventional `scripts/*/tests/probe-*.sh` exists.

## Requirements Coverage

| Requirement | Source plans | Status | Evidence |
|---|---|---|---|
| FIND-01 | 03, 04, 06, 07 | ✓ SATISFIED | Default dual-source discovery and final fleet evidence. |
| FIND-02 | 01, 02, 06, 07 | ✓ SATISFIED | Pre/post invariants, exact deadlines, validation and final coverage gates. |
| FIND-03 | 04, 06, 07 | ✓ SATISFIED | Typed mDNS failure isolation with fresh later calls. |
| FIND-04 | 03, 04, 06, 07 | ✓ SATISFIED | Direct correlated candidate liveness before yield. |
| FIND-05 | 05, 06, 07 | ✓ SATISFIED | Dual-source first-hit serial race and complete teardown. |
| FIND-07 | 01, 06, 07 | ✓ SATISFIED | Current-revision paired emulator and six-round fleet comparison. |
| FIND-08 | 01, 03, 06, 07 | ✓ SATISFIED | Integer eligibility rules and truthful non-gating empty-population disposition. |
| FIND-09 | 01, 02, 04, 05, 06, 07 | ✓ SATISFIED | Exact public exports/source modes and no selector. |
| FIND-10 | 02, 04, 06, 07 | ✓ SATISFIED | Active-only compatible UDP single-flight, ordered replay and cleanup. |

No Phase 13 requirement is orphaned: all nine roadmap-mapped IDs appear in at least one plan.

## Prohibition Verification

| Prohibition | Tier | Status | Evidence |
|---|---|---|---|
| No live/private infrastructure or hardware identifiers in tracked Phase 13 material | test | ✓ VERIFIED | Validator and privacy tests pass; security audit clean. |
| Do not make dual-source the only enumeration mode or add a source selector | test | ✓ VERIFIED | Public exports/signatures and source-participation tests pass. |
| Do not alter WiFi-measured discovery, retry, bandwidth or animation constants | historical judgment; objectively checkable final diff | ✓ VERIFIED | `src/lifx/const.py`, `pyproject.toml` and `uv.lock` are unchanged from phase base to production revision; no tuning assignment changed. |
| Do not claim FIND-08 from emulator/Thread/ineligible evidence | test | ✓ VERIFIED | Final evidence uses the named non-gating population gap; boundary tests pass. |
| Do not multiply UDP schedules for compatible overlapping callers | test | ✓ VERIFIED | Active-producer sharing test passes and coordinator key/wiring are substantive. |

## Test Quality Audit

| Test surface | Linked requirements | Disabled-only coverage | Circular | Strongest assertion | Verdict |
|---|---|---|---|---|---|
| `tests/test_api/test_api_discovery.py` | FIND-01/02/03/05/09 | No | No | Behavioural ordering, results, deadlines and cleanup | ✓ STRONG |
| `tests/test_network/test_discovery_coordinator.py` | FIND-02/10 | No | No | Cross-loop schedule count, replay order and lifecycle | ✓ STRONG |
| `tests/test_network/test_mdns/test_liveness.py` | FIND-01/04 | No | No | Correlated response values, rejection and resource teardown | ✓ STRONG |
| `tests/test_scripts/test_measure_merged_discovery.py` | FIND-07/08 | No | No | Value/schema/provenance/determinism and owned emulator lifecycle | ✓ STRONG |
| `tests/test_network/test_discovery_devices.py` | FIND-02/08 | No | No | Concrete product classification and connection ownership | ✓ STRONG |

Conditional fixture skips concern unavailable platforms/external-emulator capabilities; no Phase 13 requirement is proved only by a disabled test. Test file writes create synthetic input alias maps in temporary directories and do not generate expected values from the system under test.

## Decision Coverage

All 16 trackable `13-CONTEXT.md` decisions are honoured by shipped artefacts. The GSD decision-coverage verifier returned 16/16 with no unhonoured decisions.

## Anti-Patterns Found

No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK` or implementation-placeholder debt marker was found in Phase 13 changed Python files. Matches for “placeholder” describe the established synthetic connection correlation identity and are not stubs. No empty production implementation, hollow static data path or new runtime dependency was found.

## Human Verification Required

N/A — this is a core-library/infrastructure phase with no user-facing visual flow. Every behaviour-dependent state, cancellation, cleanup and ordering truth has executable behavioural coverage; `behavior_unverified` is zero. The sole operator checkpoint (private mode-0600 fleet handoff) was completed before collection and is independently evidenced as ignored, mode `0600`, and successfully consumed by the validated final-revision fleet rows.

## Adversarial Disconfirmation

- **Potential partial requirement:** FIND-08 did not observe an eligible 3.70–3.99 WiFi light. This is not hidden or promoted to confirmation: the locked SPEC makes it non-gating and requires the exact `no_eligible_find08_population` disposition, which the evidence contains.
- **Potential misleading test:** `test_discover_skips_unsupported_device` mocks the lower classification result. It is supported by concrete UDP and mDNS LIFX Switch classification tests, so the public filter is proven across the full wiring chain.
- **Potential uncovered error path:** no uncovered changed executable line/branch remains in the final patch gate; focused tests additionally exercise repeated cancellation, force-close, late registration and failed-source cleanup.

## Gaps Summary

No blocking or deferred Phase 13 gap remains. Phase 14 owns Thread performance/device-class revalidation and is not needed to make the merged discovery goal true.

---

_Verified: 2026-08-31T04:31:57Z_
_Verifier: the agent (gsd-verifier)_
