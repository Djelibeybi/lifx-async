---
phase: 12-ipv6-discovery-plumbing
verified: 2026-08-29T13:32:58Z
status: passed
score: 28/28 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 27/28
  gaps_closed:
    - "Positive numeric and named IPv6 zones now reach the real send boundary with their scope preserved."
    - "Unknown named zones and numeric zones above the 32-bit range now fail before sendto()."
    - "An explicit zero numeric zone now fails at both public validation and the transport send boundary."
  gaps_remaining: []
  regressions: []
gaps: []
review_findings:
  - id: CR-01
    disposition: resolved
    phase_impact: "Closed by the public and transport zero-scope guards plus regressions in revision 655ee8a."
  - id: CR-02
    disposition: confirmed_out_of_scope_follow_up
    phase_impact: "Real receive-scope loss outside find_by_ip(), but Phase 12's targeted find_by_ip() path restores the validated literal; Phase 13 owns discover()/find_by_serial(), while find_by_label() needs separate follow-up."
  - id: CR-03
    disposition: confirmed_out_of_scope_follow_up
    phase_impact: "Real ownership gaps remain in discover(), find_by_serial(), and find_by_label(), but find_by_ip() and discover_devices() have the two required aclosing owners and passing lifecycle tests."
  - id: CR-04
    disposition: confirmed_out_of_scope_follow_up
    phase_impact: "find_by_label(exact_match=True) can yield more than one match, but this is outside FIND-06 and the locked Phase 12 targeted-IP boundary."
  - id: WR-01
    disposition: warning_current_evidence_passes
    phase_impact: "The gate is not intrinsically fail-closed against future opt-in/import drift, but the current implementation-equivalent revision actually collected and passed the named Windows test, so AC9 is met for this revision."
---

# Phase 12: IPv6 Discovery Plumbing Verification Report

**Phase Goal:** The targeted-lookup leg works over IPv6: `_discover_with_packet` binds by family, `find_by_ip()` accepts an IPv6 literal, and real IPv6 end-to-end tests run on every CI runner.
**Verified:** 2026-08-29T13:32:58Z
**Status:** passed
**Re-verification:** Yes — after the direct zero-scope correction

## Goal Achievement

The complete targeted IPv6 contract is achieved. The `::1` path is behaviourally exercised through the public API, real IPv6 UDP transport, in-process emulator, product detection, lifecycle cleanup, and current CI. Positive numeric and named zones reach the native send scope, while unknown, oversized, and explicit zero zones now fail immediately at the appropriate public and transport boundaries.

### Observable Truths

Roadmap success criteria replace clearly duplicated PLAN wording below; every additional PLAN truth remains represented.

| # | Truth | Status | Evidence |
|---:|---|---|---|
| 1 | `find_by_ip()` returns a device for an IPv6 literal instead of `None`. | ✓ VERIFIED | Real `::1` tracer passes and returns the product-derived synthetic matrix device; local named module: 25/25 passed. |
| 2 | `_discover_with_packet()` derives socket family and wildcard bind from the target. | ✓ VERIFIED | `family_for(broadcast_address)` and `wildcard_for(broadcast_address)` drive `UdpTransport` at `discovery.py:244-249`; real IPv4/IPv6 observation tests pass. |
| 3 | A real `::1` emulator fixture supplies IPv6 E2E coverage on required CI runners. | ✓ VERIFIED | Ubuntu full-suite log executes all IPv6 E2E nodes; designated Windows/Python 3.10 step collected and passed the exact targeted node. |
| 4 | Targeted IPv4 remains `AF_INET`, `0.0.0.0`, broadcast-enabled, and returns a device. | ✓ VERIFIED | Real IPv4 regression in `TestIpv6TargetedDiscovery` passed. |
| 5 | Successful return closes both owned generators synchronously with Python 3.10-compatible `aclosing`. | ✓ VERIFIED | `api.py:962-980` and `discovery.py:592-613`; named ownership and real endpoint-close tests passed. |
| 6 | Existing discovery validation, deduplication, timing, cancellation, and cleanup invariants remain unchanged. | ✓ VERIFIED | Source path is unchanged apart from transport selection/ownership; rebroadcast/error suites 33/33 passed and final suite is green. |
| 7 | R1 repetition/idempotency introduces no persistent mutation or new timing promise. | ✓ VERIFIED | Targeted discovery constructs per-call generators/endpoints and writes no persistent state. |
| 8 | Every validator-accepted IPv6 form, including zoned link-local, arrives usable at the real send boundary with IPv6 wildcard bind. | ✓ VERIFIED | Positive numeric and named zones are canonicalised with a non-zero scope; explicit zero is rejected before transport construction and independently at send time. |
| 9 | Empty, malformed, and bare link-local literals fail before transport construction/open. | ✓ VERIFIED | Fail-on-use sentinel tests passed; `validate_address()` runs at `api.py:957-960`. |
| 10 | Representation checks avoid runner-specific routes, interface names, scopes, and external networks. | ✓ VERIFIED | Matrix uses loopback/documentation/synthetic literals and a cooperative no-response double. This isolation does not prove the production zoned-send boundary (truth 8). |
| 11 | A zoned target remains zoned at device construction when receive sockaddr splits host and scope. | ✓ VERIFIED | `api.py:975-980` restores the validated caller literal; split-scope return-path test passed. |
| 12 | R2 empty/degenerate boundary is exercised. | ✓ VERIFIED | Empty and invalid cases are present and passed in `TestFindByIpAddressGate`. |
| 13 | R2 representation boundary exercises compressed, expanded, ULA, GUA, loopback, zoned, and bare-link-local cases. | ✓ VERIFIED | The complete declared matrix exists and passed; its production-boundary weakness is separately classified under truth 8. |
| 14 | R2 concurrency is delegated to R1 lifecycle coverage rather than duplicated. | ✓ VERIFIED | Plan boundary is honoured; concurrency is exercised by the separate real lifecycle class. |
| 15 | Two concurrent public IPv6 lookups use distinct real endpoints and complete independently. | ✓ VERIFIED | Named real-emulator lifecycle test passed locally and in Ubuntu CI. |
| 16 | Cancellation occurs only after real endpoint open and blocked receive are observed. | ✓ VERIFIED | Event-driven observation wrapper delegates to real receive; cancellation lifecycle test passed without polling/sleep. |
| 17 | Cancellation closes the retained endpoint and a fresh public lookup then succeeds. | ✓ VERIFIED | Named cancellation/cleanup/reuse transition test passed. |
| 18 | Concurrency and cancellation remain separate discriminating tests. | ✓ VERIFIED | Separate test methods exist and both passed. |
| 19 | R1 concurrency edge is covered: independence, cancellation release, and later reuse. | ✓ VERIFIED | Behavioural lifecycle tests passed against real endpoints and emulator. |
| 20 | The existing Windows/Python 3.10 matrix cell runs the focused test immediately before the unchanged full suite. | ✓ VERIFIED | `.github/workflows/ci.yml:181-190`; current PR run confirms ordering and execution. |
| 21 | Exact Windows retry policy is applied to the real tracer. | ✓ VERIFIED | Source uses `retries=2`, `delay=1`, and `sys.platform.startswith("win32")`; selected test is the public tracer. |
| 22 | Narrow Windows opt-in enables the IPv6 emulator path while preserving the IPv6 availability dependency and general-suite exclusion. | ✓ VERIFIED | `conftest.py:214-243,446-483`; decision tests and exact CI node pass. |
| 23 | Both new emulator-backed classes inherit the emulator timeout policy. | ✓ VERIFIED | Both classes carry `@pytest.mark.emulator`; collection and tests pass. |
| 24 | The focused Windows step is required, guarded against IPv6 skip, and actually runs. | ✓ VERIFIED | No `continue-on-error`; both opt-ins set. Current log shows one item collected and one passed. |
| 25 | Windows remains mandatory unless the operator explicitly drops it after an in-scope attempt. | ✓ VERIFIED | No escape was exercised; current required attempt passed. |
| 26 | A D-11 exception is durably recorded if and only if exercised. | ✓ VERIFIED | Conditional path was not exercised, so no exception artefact is correctly present. |
| 27 | Focused/full tests, Ruff, Pyright, privacy review, and source-audit gates complete. | ✓ VERIFIED | Local focused suites, Ruff, Pyright, `git diff --check`, privacy inspection, and current CI passed; live verification supersedes the source audit's mistaken D-05 coverage claim. |
| 28 | R3 rerun/concurrency edge is covered by ephemeral fixture ownership and isolated CI jobs. | ✓ VERIFIED | Fixture uses an ephemeral port, owns runner teardown, and tests keep observation state local; matrix jobs are independent. |

**Score:** 28/28 truths verified (0 present-but-behaviour-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/lifx/api.py` | Public targeted lookup, caller-literal preservation, outer ownership | ✓ VERIFIED | Substantive, imported, used, and behaviourally exercised through public `find_by_ip()`. |
| `src/lifx/network/discovery.py` | Family-aware transport construction and inner ownership | ✓ VERIFIED | Substantive and wired; real IPv4/IPv6 and lifecycle tests pass. Receive-scope loss for other public callers is a confirmed out-of-scope review finding. |
| `src/lifx/network/address.py` | Public fail-fast address validation | ✓ VERIFIED | Explicit numeric zero, empty, malformed, and unscoped link-local input fail before transport construction. |
| `src/lifx/network/transport.py` | Family-appropriate transport and canonical IPv6 send | ✓ VERIFIED | Positive numeric and named scopes are preserved; invalid names, zero, and oversized scopes fail before send. |
| `tests/test_api/test_ipv6_e2e.py` | Real public E2E, lifecycle, fixture/CI policy | ✓ VERIFIED | 25/25 passed locally; corresponding Ubuntu and Windows nodes executed in current CI. |
| `tests/test_network/test_discovery_devices.py` | Inner-generator ownership regression | ✓ VERIFIED | Named synchronous-finalisation test passed. |
| `tests/test_api/test_api_discovery.py` | Representation, invalid-input, and split-scope return regressions | ✓ VERIFIED | The invalid matrix includes explicit zero and proves failure before transport construction. |
| `tests/test_network/test_transport.py` | Production send-boundary family and zone regressions | ✓ VERIFIED | Positive numeric/named and invalid name, zero, and range cases are covered through the real send boundary. |
| `tests/conftest.py` | Narrow IPv6 emulator eligibility and owned `::1` fixture | ✓ VERIFIED | Substantive and wired; eligibility tests and actual CI execution confirm the current path. |
| `.github/workflows/ci.yml` | Required focused Windows test before full suite | ✓ VERIFIED | Exact node, opt-ins, timeout, and ordering exist; current revision log confirms execution. |

`gsd-tools verify.artifacts` reported 13/13 declared artefact entries present/substantive across all five PLANs. Manual wiring, behavioural tests, and current-revision CI now clear the final zero-scope defect.

### Key Link Verification

The generic key-link query could not interpret symbol-qualified `path::symbol` PLAN entries and returned “Source file not found”; each link was therefore traced manually.

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `find_by_ip` | `discover_devices` | exact literal plus outer `aclosing` | ✓ WIRED | `api.py:962-980`. |
| `discover_devices` | `_discover_with_packet` | exact inner generator plus `aclosing` | ✓ WIRED | `discovery.py:592-601`. |
| `_discover_with_packet` | `UdpTransport` | `family_for` / `wildcard_for` | ✓ WIRED | `discovery.py:244-249`; real family tests pass. |
| `TestIpv6TargetedDiscovery` | `emulator_server_ipv6` | public `::1` lookup and synthetic Tile | ✓ WIRED | Real test and current CI pass. |
| Representation matrix | `find_by_ip` | public validation entry | ✓ WIRED | All declared rows execute. |
| `find_by_ip` | real discovery send | validated literal → zone resolution → canonical sockaddr | ⚠ BROKEN FOR ZERO SCOPE | Positive numeric/named zones are correct; explicit `%0` is accepted and forwarded as an unscoped link-local destination. |
| Fail-on-use sentinel | `validate_address` | pre-transport rejection | ✓ WIRED | Named tests pass. |
| `find_by_ip` | `DiscoveredDevice.create_device` | restored caller literal | ✓ WIRED | `discovered.ip = ip` precedes product construction. |
| Observed receive | real `UdpTransport.receive` | event handshake around delegated receive | ✓ WIRED | Lifecycle transition test passes. |
| Discovery generator | transport `__aexit__` | cancellation unwinds async context | ✓ WIRED | Cancellation close is behaviourally proven. |
| Lifecycle tests | public `find_by_ip` | concurrent/cancelled/reuse calls | ✓ WIRED | Named tests pass. |
| Windows named step | exact tracer node | node ID plus two opt-ins | ✓ WIRED | Current log collected and passed one test. |
| Eligibility fixture | `emulator_server_ipv6` | fixture dependency | ✓ WIRED | `conftest.py:446-450`. |
| Required CI step | D-10/D-11 evidence | required conclusion/log | ✓ WIRED | Current implementation-equivalent evidence collected and passed the exact node. |

### Data-Flow Trace (Level 4)

| Path | Data source | Result | Status |
|---|---|---|---|
| `find_by_ip("::1")` → validation → discovery → real IPv6 UDP → emulator `StateService` → `DiscoveredDevice` → product-derived Device | Real in-process emulator response | Non-empty, typed device returned | ✓ FLOWING |
| IPv4 targeted lookup through the same public path | Real in-process emulator response | Device returned with IPv4 endpoint | ✓ FLOWING |
| Positive numeric/named zoned literal → `UdpTransport.send()` | Caller literal plus numeric parse or `if_nametoindex()` | Canonical sockaddr carries a non-zero scope | ✓ FLOWING |
| Zero-scoped link-local literal → validation and transport guard | Caller literal with an explicit zero zone | Public validation fails before transport construction; the send boundary independently refuses scope zero | ✓ FAILS CLOSED |

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
|---|---|---|---|
| Phase-linked public API, E2E, ownership, discovery, and transport regressions | Focused frozen pytest selection with `ResourceWarning` promoted to error | 138 passed | ✓ PASS |
| Positive numeric and named send scopes | Named real-boundary transport tests | Both canonical four-field sockaddr assertions passed | ✓ PASS |
| Zero-scoped production send boundary | Public fail-on-construction sentinel plus real `UdpTransport.send()` regression | Both layers reject immediately; `sendto()` is not called and the endpoint remains reusable | ✓ PASS |
| Format, lint, typing, diff hygiene | Ruff format/check, Pyright, `git diff --check` | clean; Pyright 0 errors | ✓ PASS |
| Final full suite | Orchestrator-observed local run and current required CI workflow | 4,033 passed, 12 deselected locally; current matrix passed | ✓ PASS |

### Probe Execution

No standalone `scripts/**/tests/probe-*.sh` probe is declared for this phase. The PLAN's “probe” terminology refers to the in-test IPv6 availability fixture, which was independently exercised by the focused tests and current CI above.

### Current-Revision CI Evidence

The current local `src/`, `tests/`, and workflow content is byte-identical to the implementation revision exercised by the live PR evidence. Infrastructure identifiers are intentionally omitted.

- Designated Windows focused step: one item collected and one passed.
- Required emulator-supported Unix matrix cells show the targeted IPv6 tracer as passed rather than skipped.
- Required Linux full-suite cell and the complete current-revision matrix passed after the zero-scope correction.
- No merge, rerun, comment, or other external state mutation was performed during verification.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| FIND-06 | 12-01 through 12-05 | `find_by_ip()` resolves a device from an IPv6 literal instead of returning `None`. | ✓ VERIFIED | The real `::1` path, positive zoned paths, invalid-address gates, lifecycle coverage, and current cross-platform CI all pass. |

No additional Phase 12 requirements are mapped in `REQUIREMENTS.md`; no orphaned requirement was found.

### Prohibitions

| Prohibition | Verification | Status | Evidence |
|---|---|---|---|
| No live identifiers or raw discovery output in tests, documentation, commits, or evidence | Judgement plus value-suppressed scan | ✓ VERIFIED | Phase files use loopback, documentation-range, ULA, and synthetic identifiers; no live infrastructure value is reproduced here. |
| Do not count a Windows skip/allowed failure as the required attempt | Current CI log inspection | ✓ VERIFIED | Required step has no failure allowance and actually collected/passed the named node. |

### Decision and Test-Quality Coverage

- The decision-coverage query reports all 12 Phase 12 decisions honoured.
- Phase-linked tests are active, exercise public or production boundaries, and use value assertions; no disabled Phase 12 test or circular generated expectation was found.
- The focused independent selection passed 138 tests with `ResourceWarning` promoted to an error.
- The existing exact-label test is not discriminating because it neither collects nor counts exact matches. That weakness corroborates CR-04 but does not alter the FIND-06 phase score.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|---|---|---|---|
| `.github/workflows/ci.yml` / `tests/conftest.py` | Focused step could skip after future opt-in or emulator-import drift | ⚠ Warning | Current revision is proven green with one executed test, but the step is not intrinsically fail-closed for future revisions. |

No unreferenced `TBD`, `FIXME`, or `XXX` debt marker, placeholder implementation, hardcoded user-visible empty value, or privacy leak was found in Phase 12-modified files.

### Review Finding Adjudication

| Finding | Verified disposition | Blocks Phase 12? | Rationale |
|---|---|---:|---|
| CR-01 — zero numeric IPv6 zone becomes unscoped | Resolved in `655ee8a` | No | Public validation and the transport boundary now reject zero; both regressions pass locally and in current CI. |
| CR-02 — receive scope lost outside `find_by_ip()` | Confirmed, out-of-scope follow-up | No | Targeted `find_by_ip()` restores its validated literal. Phase 13 clearly owns merged discovery/serial work; label discovery still needs separate tracking. |
| CR-03 — generator ownership incomplete in other public helpers | Confirmed, out-of-scope follow-up | No | `find_by_ip()` and `discover_devices()` have the required owners and passing transition tests. The other wrappers were explicitly excluded; Phase 13 covers only part of that debt. |
| CR-04 — `find_by_label(exact_match=True)` yields multiple exact matches | Confirmed, out-of-scope follow-up | No | A controlled duplicate-label stream yielded two devices, proving the API-contract defect; it is unrelated to FIND-06 and excluded from Phase 12's locked boundary. |
| WR-01 — Windows node can green-skip | Warning retained; current evidence passes | No for this revision | The configured current run collected and passed the test. A fail-closed future guard would harden the workflow. |

The source audit and SUMMARYs are not treated as proof. In particular, the source audit's D-05 “COVERED” statement is contradicted by the live `UdpTransport.send()` trace and is not accepted.

### Human Verification Required

None. This is an infrastructure phase; every behaviour-dependent Phase 12 truth has a named automated transition/E2E test.

### Gaps Summary

No Phase 12 gap remains. The implementation selects `AF_INET6`/`::`, supports real `::1` targeted lookup, closes both Phase-owned generators, preserves positive numeric and named scopes, rejects invalid and zero scopes without sending, and passes current Unix and Windows CI.

## Canonical Next Action

**Next action:** Phase 12 may advance after planning-state completion.

---

_Verified: 2026-08-29T13:32:58Z_
_Verifier: Codex direct re-verification after current-revision CI_
