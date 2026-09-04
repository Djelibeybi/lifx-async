# Phase 12: IPv6 Discovery Plumbing — Specification

**Created:** 2026-08-29
**Ambiguity score:** 0.08 (gate: ≤ 0.20)
**Requirements:** 3 locked

## Goal

`find_by_ip()` returns a reachable device for every validated IPv6 literal through family-aware targeted discovery, proven end to end on `::1` throughout supported CI and through a bounded Windows compatibility attempt.

## Background

The transport and direct device-control layers already support IPv6. `UdpTransport` derives its socket family from its local bind address, and the existing `emulator_server_ipv6` and `ipv6_light` fixtures prove connection, colour, power, and animation traffic against an emulator bound to `::1`.

The targeted discovery path does not yet select that family. `_discover_with_packet()` constructs `UdpTransport(port=0, broadcast=True)`, which uses the default IPv4 wildcard bind. `UdpTransport.send()` then rejects an IPv6 destination because an `AF_INET` endpoint cannot send to it. `find_by_ip()` validates IPv6 input but delegates to this path, so it cannot return the reachable IPv6 emulator or an IPv6-only device.

The current CI matrix has an IPv6 must-not-skip guard on Ubuntu/Python 3.10. Other emulator-supported Unix cells can use the existing fixture, while `emulator_available` currently excludes Windows before any emulator-backed test runs. Phase 12 extends the existing fixture and CI evidence to targeted discovery, including a real bounded Windows attempt because LedFx supports Windows.

## Requirements

1. **Family-aware targeted discovery**: Targeted `_discover_with_packet()` calls derive their local wildcard bind and socket family from the destination literal while retaining the established discovery contract.
   - Current: `_discover_with_packet()` always opens the default IPv4-bound `UdpTransport`, even when `broadcast_address` is an IPv6 literal; the transport rejects the family mismatch before a usable IPv6 request can be sent.
   - Target: An IPv4 destination uses an `AF_INET` endpoint bound to the IPv4 wildcard, and a valid IPv6 destination uses an `AF_INET6` endpoint bound to the IPv6 wildcard. Existing overall and idle deadlines, retransmission schedule, source and serial validation, UDP-service filtering, first-wins per-serial deduplication, and cleanup behaviour remain unchanged.
   - Acceptance: Focused tests observe real or instrumented local socket families and wildcard binds for IPv4 and IPv6 destinations, prove concurrent IPv6 lookups are independent, prove cancellation closes the lookup endpoint and permits a later successful lookup, and keep the existing discovery invariant suite green.

2. **IPv6 `find_by_ip()`**: `find_by_ip()` returns the device reached at every IPv6 literal accepted by the existing address validator.
   - Current: IPv6 literals pass the public validation gate, including properly zoned link-local forms, but the IPv4-bound targeted discovery path cannot complete the lookup. A bare link-local address without a zone identifier already raises `ValueError` before socket creation.
   - Target: A reachable IPv6 target yields its correctly typed `Device`; compressed, expanded, ULA, GUA, loopback, and zoned link-local representations all select the IPv6 path. Empty or invalid input and a bare link-local address continue to fail before any socket is opened. Existing IPv4 lookup behaviour remains intact.
   - Acceptance: An emulator-backed test calls `find_by_ip("::1", port=<fixture port>)` and receives the fixture's synthetic device through the actual discovery and device-creation path, with evidence that the discovery socket is `AF_INET6`. Representation-focused tests cover compressed and expanded IPv6, ULA/GUA, and zoned link-local forms; negative tests cover empty, invalid, and bare link-local input before socket creation; the existing IPv4 emulator lookup still passes.

3. **Portable IPv6 discovery evidence**: The existing IPv6 emulator fixture is reused or minimally adapted to exercise targeted discovery across supported CI, with a real bounded Windows attempt.
   - Current: The `::1` emulator proves direct transport and animation traffic, but no test sends targeted discovery through it. The IPv6 tests are guaranteed not to skip only on Ubuntu/Python 3.10, and the shared emulator availability gate excludes Windows entirely.
   - Target: The targeted IPv6 discovery test runs in every emulator-supported matrix cell, retains the Ubuntu/Python 3.10 must-not-skip guard, uses an isolated ephemeral port with no cross-runner state, and is actually attempted on Windows. In-scope library or targeted-fixture defects found on Windows are fixed. Only a precisely evidenced blocker in the external emulator or host platform may remain as a named Windows gap.
   - Acceptance: CI evidence shows the targeted `::1` discovery test running rather than skipping in supported Unix cells and an actual Windows job reaching the targeted test. Windows passes after in-scope fixes, or verification records the exact attempted job, failure, ownership boundary, and reason the remaining external blocker cannot be closed in this phase. The pre-existing blanket Windows skip and an allowed-failure job do not count as the attempt.

## Boundaries

**In scope:**

- Family-aware local wildcard binding for `_discover_with_packet()` when its destination is an IPv4 or IPv6 literal.
- IPv6-literal support through the existing public `find_by_ip()` contract.
- Emulator-backed `find_by_ip("::1")` coverage through the real targeted discovery and device-creation path.
- Reuse or minimal adaptation of the existing `emulator_server_ipv6` fixture for discovery.
- Supported-matrix CI execution and a bounded real Windows compatibility attempt for the targeted IPv6 discovery test.
- Focused regression coverage for address representation, validation-before-open, concurrency, cancellation cleanup, IPv4 compatibility, and existing discovery invariants.

**Out of scope:**

- Merging broadcast and mDNS discovery or changing `discover()` — Phase 13 owns merged discovery.
- Racing broadcast and mDNS in `find_by_serial()` — Phase 13 owns that concurrency contract.
- Adding an mDNS path to `find_by_label()` — the milestone explicitly retains its existing addressing model.
- Retuning discovery, retry, bandwidth, or animation constants — Phase 14 measures Thread behaviour before any WiFi-derived constant changes.
- Thread hardware validation or fleet measurements — Phase 14 owns hardware-gated revalidation.
- Making the complete emulator suite Windows-clean — the Windows effort is bounded to the targeted IPv6 discovery fixture and its direct prerequisites.
- Adding runtime dependencies or replacing the asyncio transport architecture — the library remains zero-dependency and supports Python 3.10.

## Constraints

- Python 3.10 through 3.14 and the existing asyncio-only architecture remain supported.
- Runtime dependencies remain empty; development dependency management and test execution use `uv`.
- IPv4 targeted and broadcast discovery retain their current public behaviour and timing constants.
- Address validity continues to be owned by the existing shared address validator and family-selection helper; Phase 12 does not introduce a second parsing rule.
- The existing synthetic serial and `::1` loopback fixture are reused. Tests, documentation, commits, and evidence contain no live serial, IP address, hostname, account identifier, or raw discovery output.
- A Windows named gap is allowed only after an actual targeted-test attempt and precise evidence that the remaining blocker belongs to the external emulator or host platform rather than the in-scope library path.

## Acceptance Criteria

- [ ] AC1: IPv4 targeted discovery opens an `AF_INET` endpoint on the IPv4 wildcard and the existing IPv4 `find_by_ip()` emulator test still returns a device.
- [ ] AC2: IPv6 targeted discovery opens an `AF_INET6` endpoint on the IPv6 wildcard and sends to the supplied IPv6 destination.
- [ ] AC3: `find_by_ip("::1", port=<IPv6 emulator port>)` returns the fixture's synthetic device through the real targeted discovery and device-creation path, not through a directly constructed `Light` or mocked discovery generator.
- [ ] AC4: Compressed, expanded, ULA, GUA, loopback, and zoned link-local IPv6 literals select the IPv6 family; empty, invalid, and bare link-local input fail before socket creation.
- [ ] AC5: Two concurrent targeted IPv6 lookups operate independently, and cancelling one lookup closes its endpoint without preventing a later lookup from succeeding.
- [ ] AC6: Existing tests for discovery overall timeout, idle timeout, retransmission, source/serial validation, UDP-service filtering, first-wins deduplication, and cleanup remain green without weakened assertions.
- [ ] AC7: The IPv6 emulator discovery fixture binds `::1` on an isolated ephemeral port, leaves no socket after teardown or failed setup, and shares no mutable state across CI runners.
- [ ] AC8: The targeted IPv6 discovery test runs rather than skips in every emulator-supported CI matrix cell; Ubuntu/Python 3.10 remains a must-not-skip cell.
- [ ] AC9: A Windows CI job actually reaches the targeted IPv6 discovery test. In-scope defects are fixed; otherwise verification names the exact attempted job and external blocker. The existing blanket skip or an allowed-failure job is not accepted as evidence of an attempt.
- [ ] AC10: No discovery, retry, bandwidth, or animation timing constant changes in this phase.
- [ ] AC11: Phase 12 tests, documentation, commits, and evidence contain only synthetic, loopback, or documentation-range identifiers and contain no raw live discovery output.
- [ ] AC12: The focused Phase 12 suite, complete frozen pytest suite, Ruff format/lint, and Pyright checks pass on the final tree, subject only to the explicitly evidenced Windows external-blocker allowance in AC9.

## Edge Coverage

**Coverage:** 7/7 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| Idempotency / repetition | R1 | ⛔ dismissed | Discovery is observational and per-call; it has no persistent mutation, and identical timing or response order across repeated network calls is not promised. |
| Concurrency / effect ordering | R1 | ✅ covered | AC5 specifies independent concurrent lookups, cancellation cleanup, and successful reuse after cancellation. |
| Empty / degenerate | R2 | ✅ covered | AC4 requires empty and invalid input to fail before socket creation. |
| Encoding / representation | R2 | ✅ covered | AC4 fixes the accepted IPv6 representation classes and the bare-versus-zoned link-local boundary. |
| Concurrency / effect ordering | R2 | ⛔ dismissed | `find_by_ip()` delegates its network lifecycle to R1; AC5 covers the shared targeted-discovery concurrency edge without duplicating it. |
| Idempotency / repetition | R3 | ⛔ dismissed | Repeated CI execution is ordinary deterministic-test hygiene rather than product behaviour; the fixture's concrete isolation and teardown obligations are covered separately. |
| Concurrency / effect ordering | R3 | ✅ covered | AC7 and AC8 require ephemeral-port isolation, no cross-runner state, and execution throughout the supported matrix. |

## Prohibitions (must-NOT)

**Coverage:** 2/2 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT place live serials, IP addresses, hostnames, account identifiers, or raw discovery output in Phase 12 tests, documentation, commits, or evidence. | R1-R3 | resolved | verification: test — AC11; use the repository's value-suppressed privacy audit pattern, with the wired-check descriptor located during planning rather than fabricated here. |
| MUST NOT count the pre-existing Windows skip or an allowed-failure job as a Windows compatibility attempt; any named gap requires an actual targeted-test run and precise external-blocker evidence. | R3 | resolved | verification: judgment — AC9; verifier reviews the CI execution and ownership evidence. |

Generic UDP spoofing, injection, and hostile-network security concerns remain canon work for `$gsd-secure-phase` and the existing discovery validation contract; this specification does not mint duplicate prohibitions for them.

## Ambiguity Report

| Dimension | Score | Min | Status | Notes |
|-----------|-------|-----|--------|-------|
| Goal Clarity | 0.96 | 0.75 | ✓ | Public outcome and end-to-end proof are explicit. |
| Boundary Clarity | 0.92 | 0.70 | ✓ | Phase 13 merge work, Phase 14 measurements, whole-suite Windows repair, and dependency changes are excluded. |
| Constraint Clarity | 0.90 | 0.65 | ✓ | Address classes, compatibility, CI population, Windows allowance, privacy, and platform floors are locked. |
| Acceptance Criteria | 0.88 | 0.70 | ✓ | Twelve pass/fail checks cover behaviour, regressions, lifecycle, CI, Windows evidence, and privacy. |
| **Ambiguity** | **0.08** | **≤0.20** | **✓** | Gate passed after the Windows compatibility rule was clarified. |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | Does Phase 12 replace or reuse the existing IPv6 fixture? | Reuse and minimally adapt `emulator_server_ipv6`; prove targeted discovery through it. |
| 1 | Researcher | Which CI population must exercise IPv6 discovery? | Every emulator-supported matrix cell, retaining Ubuntu/Python 3.10 as must-not-skip. |
| 1 | Researcher | Which IPv6 inputs belong to `find_by_ip()`? | Every address accepted by the shared validator; prove `::1`, preserve zoned link-local acceptance and bare link-local rejection. |
| 2 | Researcher + Simplifier | What does Windows support require given LedFx runs there? | Make a real bounded Windows attempt and fix in-scope defects; allow only a precisely evidenced external blocker as a named gap. |
| Edge probe | Completeness | How are seven generated edge candidates resolved? | Four explicit acceptance checks and three reasoned dismissals accepted. |
| Prohibition probe | Must-NOT completeness | Which project-specific privacy and evidence constraints apply? | Keep identifier-free tracked artefacts and require honest Windows-attempt evidence. |

---

*Phase: 12-ipv6-discovery-plumbing*
*Spec created: 2026-08-29*
*Next step: $gsd-discuss-phase 12 — implementation decisions (how to build what is specified above)*
