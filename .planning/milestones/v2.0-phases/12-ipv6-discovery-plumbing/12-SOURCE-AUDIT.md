# Phase 12 Multi-Source Coverage Audit

| SOURCE | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | - | Family-aware targeted lookup, public IPv6 literal support, and real cross-runner IPv6 E2E evidence | 12-01..12-04 | COVERED | Tracer proves the public real-socket/emulator path; expansions cover boundaries/lifecycle and the required CI evidence. |
| REQ | FIND-06 | `find_by_ip()` accepts an IPv6 literal and returns the targeted Device | 12-01..12-04 | COVERED | FIND-06 appears in every plan; the tracer returns the product-derived synthetic `MatrixLight`. |
| RESEARCH | Family bind | Reuse `family_for()` and `wildcard_for()` at `_discover_with_packet()` transport construction | 12-01 | COVERED | No duplicate parser or family rule is introduced. |
| RESEARCH | Successful-return cleanup | Own the exact `discover_devices()` generator with the existing `aclosing()` pattern so `find_by_ip()` awaits finalisation before returning its first Device | 12-01 | COVERED | The tracer asserts the retained discovery endpoint is already closing/closed immediately after the public call returns. |
| RESEARCH | Shared reliability seam | Preserve source/serial/type validation, first-wins dedup, timing, rebroadcast, cancellation, and cleanup | 12-01, 12-03 | COVERED | Behaviour edits are confined to API generator ownership and discovery transport construction; `transport.py` is comment-only, while focused invariant suites and lifecycle tests guard the rest. |
| RESEARCH | Real tracer | Observe the actual socket and product construction through `find_by_ip("::1")` | 12-01 | COVERED | Test wrapper delegates to real `UdpTransport`; constructor intent alone is insufficient. |
| RESEARCH | Deterministic boundaries | Instrument representation at the transport seam and cancellation with events | 12-02, 12-03 | COVERED | Cooperative short-timeout fake, per-test observation queues/events, no route/interface dependency, sleeps, polling, or pre-start cancellation. |
| RESEARCH | Narrow Windows attempt | Use the existing matrix cell and fixture-only opt-in | 12-04 | COVERED | No separate job, all-Windows emulator support, or workflow retry. |
| RESEARCH | Scope exclusions | No mDNS, dependency, hardware-fleet, tuning, or generated-protocol work | 12-01..12-04 | COVERED | Plans modify only `find_by_ip()` generator ownership, shared UDP discovery, one transport comment, tests/fixtures, and the existing CI matrix. |
| CONTEXT | D-01 | Existing Windows/Python 3.10 source/test PR cell only | 12-04 | COVERED | Narrow fixture opt-in; general Windows emulator suite remains disabled. |
| CONTEXT | D-02 | Focused targeted IPv6 step immediately before unchanged full suite | 12-04 | COVERED | Exact node ID in the existing matrix; following full-suite command/environment retained. |
| CONTEXT | D-03 | Exact Windows `flaky(retries=2, delay=1, condition=...)` policy | 12-04 | COVERED | Applied only to the real public tracer; pass after retry counts as pass. |
| CONTEXT | D-04 | Real `find_by_ip("::1")`, emulator/device construction, and actual socket observation | 12-01 | COVERED | Leading tracer proves family, wildcard, destination, cleanup, and `MatrixLight`. |
| CONTEXT | D-05 | Complete IPv6 representation matrix without runner routes/interfaces | 12-02 | COVERED | Accepted forms reach the real discovery transport boundary via a cooperative no-response transport; a synthetic split host/scope response additionally proves the validated zoned literal reaches Device construction intact. |
| CONTEXT | D-06 | Empty/malformed/bare-link-local fail-on-use sentinel | 12-02 | COVERED | Sentinel fails at construction; public validation must occur first. |
| CONTEXT | D-07 | Deterministic cancellation after real open and blocked receive | 12-03 | COVERED | Test-local queued observation records and event handshakes wrap real `open()`/`receive()`; no sleep or polling. |
| CONTEXT | D-08 | Retain endpoint, prove close, then fresh success | 12-03 | COVERED | Cancellation assertion precedes a new real emulator-backed lookup. |
| CONTEXT | D-09 | Separate concurrency and cancellation tests | 12-03 | COVERED | Two distinct test methods and endpoint assertions. |
| CONTEXT | D-10 | Passing named Windows step is evidence; no JUnit/committed success attestation | 12-04 | COVERED | Blocking current-PR log inspection owns the evidence boundary. |
| CONTEXT | D-11 | Windows remains required unless user explicitly drops after a precise blocker | 12-04 | COVERED | Required step has no failure allowance; persistent blocker pauses for user direction. |
| CONTEXT | D-12 | Record an exercised D-11 decision in a convenient durable record | 12-04 | COVERED | No exception artefact is designed before the decision exists. |
| SPEC | AC1 | IPv4 remains `AF_INET` / `0.0.0.0` and real lookup succeeds | 12-01 | COVERED | Real IPv4 emulator regression. |
| SPEC | AC2 | IPv6 is `AF_INET6` / `::` and sends supplied destination | 12-01, 12-02 | COVERED | Real tracer plus representation-boundary matrix. |
| SPEC | AC3 | Real public `find_by_ip("::1")` returns typed synthetic Device | 12-01 | COVERED | No direct `Light` or mocked factory. |
| SPEC | AC4 | Representation and invalid/bare-link-local boundaries | 12-02 | COVERED | Complete D-05/D-06 matrix plus scoped caller-literal preservation across the inbound sockaddr-to-Device return path. |
| SPEC | AC5 | Independent concurrency, cancellation close, later success | 12-03 | COVERED | Separate event-driven real-endpoint tests. |
| SPEC | AC6 | Existing discovery invariants remain green | 12-01, 12-03, 12-04 | COVERED | Focused invariant tests plus full frozen suite. |
| SPEC | AC7 | Ephemeral `::1` fixture with owned teardown/no cross-runner state | 12-01, 12-03, 12-04 | COVERED | Existing fixture retained and narrow eligibility tested. |
| SPEC | AC8 | Real targeted test runs on supported Unix and designated Windows cell | 12-04 | COVERED | Both new emulator-backed classes carry the emulator marker; full suites retain Unix execution and the focused required Windows/Python 3.10 step selects the exact tracer node. |
| SPEC | AC9 | Windows reaches the test; no skip/allowed-failure evidence | 12-04 | COVERED | Required step plus blocking current-PR log inspection and D-11 boundary. |
| SPEC | AC10 | No discovery constant changes | 12-01, 12-02 | COVERED | Actions explicitly prohibit retuning and focused suites pin behaviour. |
| SPEC | AC11 | Privacy-safe fixtures/evidence only | 12-01..12-04 | COVERED | Loopback/documentation-range/synthetic data and value-suppressed inspection. |
| SPEC | AC12 | Focused/full/Ruff/Pyright gates and only explicit D-11 allowance | 12-04 | COVERED | Local automated gate plus blocking external CI checkpoint. |
| SPEC EDGE | R1 idempotency/repetition | Observational per-call discovery has no persistent mutation or repeat-order/timing promise | 12-01 | COVERED (dismissed) | Resolution is lifted verbatim into `must_haves.truths`. |
| SPEC EDGE | R1 concurrency | Independent calls, cancellation cleanup, and reuse | 12-03 | COVERED | Resolution is lifted verbatim into `must_haves.truths`. |
| SPEC EDGE | R2 empty/degenerate | Empty/invalid rejected before socket | 12-02 | COVERED | Resolution is lifted verbatim into `must_haves.truths`. |
| SPEC EDGE | R2 encoding/representation | All six accepted classes and bare/zoned boundary | 12-02 | COVERED | Resolution is lifted verbatim into `must_haves.truths`. |
| SPEC EDGE | R2 concurrency | Delegated to R1 lifecycle coverage | 12-02, 12-03 | COVERED (dismissed) | Resolution is lifted verbatim into `must_haves.truths`. |
| SPEC EDGE | R3 idempotency | Ordinary CI rerun hygiene, no new product repeat contract | 12-04 | COVERED (dismissed) | Resolution is lifted verbatim into `must_haves.truths`. |
| SPEC EDGE | R3 concurrency | Ephemeral fixture, teardown, no cross-runner state, independent matrix jobs | 12-04 | COVERED | Resolution is lifted verbatim into `must_haves.truths`. |
| SPEC PROHIBITION | P1 | No live serials/IPs/hostnames/account IDs/raw discovery output | 12-01..12-04 | COVERED | Present in each plan's `must_haves.prohibitions`; synthetic data and suppressed audit. |
| SPEC PROHIBITION | P2 | No Windows skip or allowed failure counted as attempt | 12-01..12-04 | COVERED | Present in each plan's `must_haves.prohibitions`; required named step and checkpoint. |
| REVIEW | Emulator timeout marker | New tracer and lifecycle classes must inherit the 120-second emulator timeout policy | 12-01, 12-03, 12-04 | COVERED | Both classes are explicitly marked `@pytest.mark.emulator`; Plan 12-04 preserves the markers while adding the focused retry policy. |
| REVIEW | Cooperative no-response fake | Representation fake must not busy-spin and tests must pin short deadlines | 12-02 | COVERED | `receive(timeout)` awaits the supplied timeout before raising; every row passes explicit 0.05/0.01/1.0 timing arguments without changing production constants. |
| REVIEW | Test-local observation state | Endpoint records and cancellation events must not live in shared class state | 12-01, 12-03 | COVERED | `_make_observed_discovery_transport()` receives a fresh test-local queue; each `_DiscoveryObservation` owns its events. |
| REVIEW | Cancellation discrimination | Endpoint close on cancellation does not by itself prove outer `aclosing` ownership | 12-01, 12-03 | COVERED | Plan 12-03 attributes closure to the innermost transport context; the successful-return tracer and explicit generator-ownership class are the discriminating tests. |
| REVIEW | Ownership class declaration | Verify node `TestDiscoveryGeneratorOwnership` must be explicitly created | 12-01 | COVERED | The class is named in artifacts, action, acceptance criteria, and verify command. |
| REVIEW | Fixture dependency and wording | Retain `ipv6_available`; acknowledge all direct fixture consumers; keep Windows scope narrow at node selection | 12-04 | COVERED | The server fixture keeps the probe dependency, the plan names `ipv6_light`, and CI selects one exact node. |
| REVIEW | Inbound zoned-link-local return path | A split IPv6 sockaddr scope must not be lost before Device construction | 12-02 | COVERED | Targeted `find_by_ip()` restores the validated caller literal before `create_device()`; a synthetic response regression covers the swallowed-`None` failure mode. |
| REVIEW | Public and module docstrings | Describe IPv4/IPv6 targeted literals and extend the IPv6 module scope text | 12-01 | COVERED | Task 1 updates both docstrings without adding hostname or routing claims and records the actual pre-fix `LifxNetworkError`. |
| REVIEW | Broad `aclosing` claim | Disposition Antigravity's requested edits to unrelated discovery/device callers | 12-01 | REJECTED FOR PHASE | The executable plan reproduces the cited callers and rejects expansion: Phase 13 owns merged/serial work, label discovery is locked unchanged, and metadata setters are unrelated to FIND-06. |
| DETECTOR | API coverage | Internal dependency-free LAN protocol, not an external API/SDK/service | Planning gate | SKIPPED (`detected:false`) | The deterministic final plan/roadmap scan returned no signals, so no `COVERAGE.md` is required. |
| DETECTOR | Assumption delta | Detector returned `detected:false` | - | EXCLUDED | No assumption-delta decision is fabricated. |
| DETECTOR | Schema push | No supported ORM/schema file in scope | - | EXCLUDED | No schema work planned. |
| DETECTOR | API surface intel | Zero-symbol report is stale/non-authoritative | 12-01..12-04 | EXCLUDED AS AUTHORITY | Current source symbols and explicit phase-produced test symbols are listed in every plan. |

No GOAL, REQ, RESEARCH, CONTEXT, SPEC acceptance criterion, resolved edge, prohibition, or current
actionable review finding is missing or silently dropped. Deferred and other-phase items—mDNS,
general Windows emulator support, hardware-fleet validation, discovery constant tuning,
dependencies, and generated protocol changes—remain excluded.
