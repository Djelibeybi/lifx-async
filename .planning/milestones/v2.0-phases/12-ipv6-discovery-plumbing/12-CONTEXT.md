# Phase 12: IPv6 Discovery Plumbing - Context

**Gathered:** 2026-08-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 12 makes the targeted lookup path family-aware so public `find_by_ip()` can
reach an IPv6 literal. It proves the real path against the existing `::1` emulator,
preserves every established discovery invariant, and makes one bounded Windows CI
attempt without broadening the phase into general Windows emulator support.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**3 requirements are locked.** See `12-SPEC.md` for full requirements, boundaries,
and acceptance criteria.

Downstream agents MUST read `12-SPEC.md` before planning or implementing. Requirements
are not duplicated here.

**In scope (from SPEC.md):**

- Family-aware local wildcard binding for `_discover_with_packet()` when its destination
  is an IPv4 or IPv6 literal.
- IPv6-literal support through the existing public `find_by_ip()` contract.
- Emulator-backed `find_by_ip("::1")` coverage through the real targeted discovery and
  device-creation path.
- Reuse or minimal adaptation of the existing `emulator_server_ipv6` fixture for
  discovery.
- Supported-matrix CI execution and a bounded real Windows compatibility attempt for the
  targeted IPv6 discovery test.
- Focused regression coverage for address representation, validation-before-open,
  concurrency, cancellation cleanup, IPv4 compatibility, and existing discovery
  invariants.

**Out of scope (from SPEC.md):**

- Merging broadcast and mDNS discovery or changing `discover()` — Phase 13 owns merged
  discovery.
- Racing broadcast and mDNS in `find_by_serial()` — Phase 13 owns that concurrency
  contract.
- Adding an mDNS path to `find_by_label()` — the milestone explicitly retains its
  existing addressing model.
- Retuning discovery, retry, bandwidth, or animation constants — Phase 14 measures
  Thread behaviour before any WiFi-derived constant changes.
- Thread hardware validation or fleet measurements — Phase 14 owns hardware-gated
  revalidation.
- Making the complete emulator suite Windows-clean — the Windows effort is bounded to
  the targeted IPv6 discovery fixture and its direct prerequisites.
- Adding runtime dependencies or replacing the asyncio transport architecture — the
  library remains zero-dependency and supports Python 3.10.

</spec_lock>

<decisions>
## Implementation Decisions

### Windows execution breadth

- **D-01:** Use the existing `windows-latest` / Python 3.10 matrix cell for the bounded
  Windows attempt. Run it on source/test pull requests only, matching the existing
  three-OS matrix policy. Do not add a separate job and do not expand the attempt across
  every Windows/Python cell.
- **D-02:** Add a clearly named focused targeted-IPv6-discovery step in that cell before
  the normal full-suite step. The normal suite remains unchanged; the focused step makes
  the required attempt explicit in the job log.
- **D-03:** Apply the repository's existing Windows pytest retry policy to the focused
  test. A final pass after an allowed retry is simply passing CI and needs no additional
  note.

### IPv6 proof split

- **D-04:** Use one real end-to-end `find_by_ip("::1", port=<fixture port>)` test through
  the existing emulator and actual device-creation path. Wrap or spy on the real
  `UdpTransport` in the test so network traffic remains real while the test records the
  discovery endpoint's actual socket family and local wildcard bind.
- **D-05:** Exercise compressed, expanded, ULA, GUA, loopback, and zoned link-local
  representations through public `find_by_ip()`. Instrument only the transport boundary
  for representations that cannot be routed portably on an ordinary CI runner; do not
  create runner-specific routes or interfaces.
- **D-06:** For empty, malformed, and bare link-local inputs, install a fail-on-use
  transport sentinel and call public `find_by_ip()`. Any transport construction or open
  attempt is a test failure, pinning validation-before-open at the public entry point.

### Cancellation, cleanup, and concurrency proof

- **D-07:** Make cancellation deterministic: the transport spy signals that its real
  endpoint is open and receive is blocked, and only then does the test cancel the lookup.
  Do not use fixed sleeps or pre-start cancellation as lifecycle evidence.
- **D-08:** Record the real underlying endpoint and assert that transport close completes
  and the endpoint reports closing or closed. After cancellation, perform a fresh real
  `::1` lookup successfully.
- **D-09:** Keep concurrent-independence and cancellation-recovery coverage in separate
  tests. The concurrency test proves two IPv6 lookups receive distinct endpoints and
  complete independently; the cancellation test isolates post-open cancellation, endpoint
  closure, and later real success.

### CI evidence and Windows escape hatch

- **D-10:** A passing, clearly named, required Windows CI step is sufficient evidence.
  Do not add a separate JUnit artefact or committed success attestation; ordinary CI logs
  and status are enough.
- **D-11:** The existing AC9 escape hatch is operator-controlled. Windows remains required
  while work continues. If it remains red, only the user's explicit decision to drop
  Windows can exercise the escape hatch. That decision is the complete justification;
  it does not require an external-cause proof or a SPEC amendment. Failed or allowed-
  failure CI without that explicit decision does not exercise the escape hatch.
- **D-12:** If D-11 is exercised, record the explicit operator decision in whichever
  durable project record is most convenient and efficient at that time. Do not predesign
  a special exception artefact.

### Planner's Discretion

- Exact test module placement and the concrete test-only spy/sentinel classes.
- Exact CI step name and environment-variable name, provided the Windows/Python 3.10
  attempt is conspicuous and required.
- The durable record used for an operator decision under D-12, if that decision is ever
  made.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked phase and milestone authority

- `.planning/phases/12-ipv6-discovery-plumbing/12-SPEC.md` — locked requirements,
  boundaries, acceptance criteria, edge coverage, privacy constraints, and the AC9
  Windows escape hatch. MUST read before planning.
- `.planning/PROJECT.md` — v2.0 scope and the locked decision that `find_by_ip()` accepts
  IPv6 while `find_by_label()` does not change.
- `.planning/REQUIREMENTS.md` — authoritative FIND-06 requirement and phase traceability.
- `.planning/ROADMAP.md` — Phase 12 goal, dependency ordering, success criteria, and its
  file-disjoint relationship with Phase 11.

### Inherited decisions and measured constraints

- `.planning/phases/10-land-the-ipv6-thread-branch/10-CONTEXT.md` — shared address helper,
  `::1` emulator, IPv6 must-not-skip gate, lifecycle, and privacy decisions inherited by
  this phase.
- `.planning/phases/11-mdns-hardening/11-CONTEXT.md` — current private/public discovery
  boundaries and privacy-safe network evidence patterns.
- `.agents/skills/spike-findings-lifx-async/SKILL.md` — validated reliability constraints;
  retain asyncio and do not retune WiFi-derived constants in this phase.
- `.agents/skills/spike-findings-lifx-async/references/discovery.md` — established
  `_discover_with_packet()` architecture, re-broadcast schedule, deduplication, and the
  rule that this phase must preserve rather than retune.
- `AGENTS.md` — repository coding, testing, privacy, dependency, and commit rules.

### Live implementation and test surfaces

- `src/lifx/network/address.py` — the single `validate_address()`, `family_for()`, and
  `wildcard_for()` rules Phase 12 must reuse.
- `src/lifx/network/discovery.py` — `_discover_with_packet()` transport ownership,
  deadlines, re-broadcast schedule, validation, deduplication, and cleanup boundary.
- `src/lifx/api.py` — public `find_by_ip()` validation and targeted-discovery delegation.
- `src/lifx/network/transport.py` — `UdpTransport` local-bind family derivation and the
  real endpoint state observed by the tests.
- `tests/conftest.py` — existing IPv6 probe, `emulator_server_ipv6`, synthetic device,
  ephemeral-port, and blanket Windows emulator gate.
- `tests/test_api/test_ipv6_e2e.py` — existing real `::1` control and animation proof plus
  actual-socket inspection pattern.
- `tests/test_api/test_api_discovery.py` — existing public IPv4 `find_by_ip()` emulator
  coverage and generator-cleanup patterns.
- `tests/test_network/test_discovery_rebroadcast.py` and
  `tests/test_network/test_discovery_errors.py` — existing discovery timing, send,
  validation, error, and invariant seams that must not be weakened.
- `.github/workflows/ci.yml` — current OS/Python matrix, source-change scoping, full pytest
  step, and Ubuntu/Python 3.10 IPv6 must-not-skip environment.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `wildcard_for()` already maps a destination literal to the correct IPv4 or IPv6 local
  wildcard; `_discover_with_packet()` needs to use that established rule when constructing
  its transport.
- `UdpTransport` already derives the socket family from its local bind address, owns its
  asyncio endpoint through an async context manager, and exposes enough private test state
  to observe the actual socket without adding production diagnostics.
- `emulator_server_ipv6`, `get_free_port6()`, `ipv6_available`, and the synthetic IPv6
  device already provide isolated real `::1` traffic and teardown.
- The existing IPv6 E2E helper demonstrates how to inspect an actual device-connection
  socket rather than trusting a recorded family value.

### Established Patterns

- Public input validation occurs before socket creation and belongs to
  `validate_address()`; Phase 12 adds no second parsing rule.
- `_discover_with_packet()` owns source validation, serial validation, UDP-service
  filtering, first-wins deduplication, re-broadcast timing, idle/overall deadlines, and
  deterministic transport cleanup. Family awareness must not alter these invariants.
- Emulator-backed tests use isolated ephemeral ports and synthetic identifiers. Raw
  hardware or network evidence never enters tracked artefacts.
- Windows emulator tests currently skip through `emulator_available`; the Phase 12
  focused path must bypass that blanket only for its direct fixture/test prerequisites,
  not enable the complete emulator suite.

### Integration Points

- `_discover_with_packet()` constructs `UdpTransport(port=0, broadcast=True)` today. Its
  local bind literal is the family-selection seam.
- `find_by_ip()` already validates first and delegates through `discover_devices()` using
  the target literal as the destination; its public signature and behaviour remain intact.
- The focused Windows invocation fits inside the existing `test` matrix job before the
  unchanged `uv run --frozen pytest` step.
- The new tests extend the existing API/discovery suites and reuse the current fixture
  rather than constructing a parallel emulator architecture.

</code_context>

<specifics>
## Specific Ideas

- Prefer a real-transport spy that changes observation only, not delivery.
- Use explicit events to synchronise lifecycle tests; fixed sleeps are not accepted as
  cancellation-state evidence.
- Passing after the chosen existing Windows retry policy is simply a pass.
- Do not create evidence artefacts preemptively; green CI is the successful-path proof.
- The AC9 escape hatch belongs to the operator alone and is not verifier discretion.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within the locked Phase 12 boundary.

</deferred>

---

*Phase: 12-ipv6-discovery-plumbing*
*Context gathered: 2026-08-29*
