# Phase 12: IPv6 Discovery Plumbing - Research

**Researched:** 2026-08-29
**Domain:** family-aware asyncio UDP discovery, emulator-backed IPv6 integration testing, and matrix-scoped CI execution
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Windows execution breadth

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

#### IPv6 proof split

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

#### Cancellation, cleanup, and concurrency proof

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

#### CI evidence and Windows escape hatch

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

### the agent's Discretion

- Exact test module placement and the concrete test-only spy/sentinel classes.
- Exact CI step name and environment-variable name, provided the Windows/Python 3.10
  attempt is conspicuous and required.
- The durable record used for an operator decision under D-12, if that decision is ever
  made.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within the locked Phase 12 boundary.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIND-06 | Verbatim requirement: **"`find_by_ip()` resolves a device from an IPv6 literal instead of returning `None`"**. [VERIFIED: .planning/REQUIREMENTS.md:132-133] | Reuse `validate_address()`, `family_for()`, and `wildcard_for()`; bind `_discover_with_packet()` to the destination family; prove the public path with the existing `::1` emulator and an observation-only real-transport spy; keep IPv4 and discovery invariants green. [VERIFIED: src/lifx/network/address.py:76-175; src/lifx/api.py:919-973; tests/conftest.py:409-503] |
</phase_requirements>

## Summary

Phase 12 is a narrow production change with a comparatively large proof surface. The public API already validates the target before discovery, and the transport already derives its socket family from its local bind. The family defect is the unqualified construction `"UdpTransport(port=0, broadcast=True)"` inside `_discover_with_packet()`, which leaves every targeted lookup on the IPv4 wildcard. The successful-return cleanup proof also requires `find_by_ip()` to own the `discover_devices()` async generator with the already imported `contextlib.aclosing`, because its current direct `async for` return does not guarantee synchronous finalisation before the Device reaches the caller. [VERIFIED: src/lifx/api.py:15,851-864,955-973; src/lifx/network/discovery.py:232-266; src/lifx/network/transport.py:302-312]

The production plan should derive the local wildcard from `broadcast_address` using `wildcard_for()`, preserve broadcast mode for IPv4, disable broadcast mode for IPv6, and wrap the exact discovery generator consumed by `find_by_ip()` with `aclosing()` so a first-result return awaits endpoint cleanup. The broadcast condition matters on Windows: Microsoft documents that `SO_BROADCAST` does not apply to IPv6 because IPv6 has no broadcast, while the current transport applies `SO_BROADCAST` whenever its `broadcast` flag is true. [VERIFIED: src/lifx/api.py:15,851-864,955-973; src/lifx/network/address.py:136-175; src/lifx/network/transport.py:326-340] [CITED: https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options] [CITED: https://docs.python.org/3.10/library/contextlib.html#contextlib.aclosing]

Most phase work belongs in tests and CI: one real `find_by_ip("::1")` test, representation tests at the transport boundary, fail-before-open sentinels, distinct-endpoint concurrency, post-open cancellation cleanup, a narrowly gated Windows fixture path, and a required focused step in the existing Windows/Python 3.10 matrix cell. The existing fixture, actual-socket inspection helper, retry marker, and matrix all provide the necessary patterns. [VERIFIED: tests/conftest.py:90-105,148-182,185-265,409-503; tests/test_api/test_ipv6_e2e.py:46-78; tests/test_network/test_discovery_rebroadcast.py:490-512; .github/workflows/ci.yml:150-192]

**Primary recommendation:** make the family decision once at `_discover_with_packet()` transport construction, preserve the receive loop byte-for-byte, and organise implementation as production seam first, deterministic tests second, narrowly gated Windows fixture/CI third. [VERIFIED: .planning/phases/12-ipv6-discovery-plumbing/12-CONTEXT.md D-01 through D-10]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Public address validation and early-return generator ownership | API / Backend | Network utility | `find_by_ip()` calls `validate_address()` before constructing discovery; the plan then applies the file's existing `aclosing()` pattern to the exact generator so successful return awaits finalisation. [VERIFIED: src/lifx/api.py:15,851-864,955-973] |
| Destination-family and wildcard selection | API / Backend network layer | OS socket layer | `family_for()` and `wildcard_for()` are the single address-family rule; `_discover_with_packet()` is the missing call site. [VERIFIED: src/lifx/network/address.py:136-175; .planning/phases/12-ipv6-discovery-plumbing/12-CONTEXT.md:182-189] |
| UDP endpoint creation and cleanup | API / Backend network layer | OS socket layer | `UdpTransport.open()` passes the chosen local address and family to `create_datagram_endpoint()`; its async context manager closes the endpoint. [VERIFIED: src/lifx/network/transport.py:254-369,546-577] |
| Device identification and typed construction | API / Backend device layer | Emulator | The targeted response becomes `DiscoveredDevice`, then `find_by_ip()` calls its real `create_device()` path. [VERIFIED: src/lifx/network/discovery.py:523-603; src/lifx/api.py:960-973] |
| Portable IPv6 proof | Test / CI | OS socket layer | The session fixture owns an AF_INET6/V6ONLY emulator on `::1`, while the test must inspect the discovery socket rather than trust recorded intent. [VERIFIED: tests/conftest.py:148-182,409-503; tests/test_api/test_ipv6_e2e.py:46-63] |
| Bounded Windows execution | Test / CI | Test fixture | One conditional step selects the existing Windows/Python 3.10 cell; an opt-in fixture gate bypasses only the blanket Windows emulator skip for that focused invocation. [VERIFIED: .github/workflows/ci.yml:150-192; tests/conftest.py:185-211; .planning/phases/12-ipv6-discovery-plumbing/12-CONTEXT.md D-01 through D-03] |

## Project Constraints (from AGENTS.md)

- Keep the runtime dependency list empty and retain the built-in asyncio architecture. [VERIFIED: AGENTS.md:8-15; pyproject.toml:1-7]
- Use `uv` for dependency synchronisation and test/tool execution; the full test command is verbatim `"uv run --frozen pytest"`. [VERIFIED: AGENTS.md:48-100]
- Never put real device serials, MAC addresses, IP addresses, hostnames, account names, or raw discovery output into tracked tests, documentation, evidence, prompts, reports, or memory. Use synthetic identifiers and loopback/documentation-range addresses. [VERIFIED: AGENTS.md:17-38]
- Do not edit generated protocol or product-registry files; Phase 12 does not require either generator. [VERIFIED: AGENTS.md:103-116,371-407]
- Use Conventional Commits without GSD bookkeeping scopes, and commit with `git commit -S -s`. [VERIFIED: AGENTS.md:40-46]
- Do not edit `docs/changelog.md` manually. [VERIFIED: AGENTS.md:424-428]
- Apply the repository spike constraint: retain asyncio and do not retune the established discovery schedule in this phase. [VERIFIED: .agents/skills/spike-findings-lifx-async/SKILL.md Requirements; .agents/skills/spike-findings-lifx-async/references/discovery.md Requirements and Constraints]

## Standard Stack

### Core

| Library / facility | Version | Purpose | Why Standard |
|--------------------|---------|---------|--------------|
| Python stdlib `asyncio`, `socket`, `ipaddress` | Python `>=3.10`; CI exercises `"3.10", "3.11", "3.12", "3.13", "3.14"` | Parse address literals, choose AF_INET/AF_INET6, create datagram endpoints, coordinate cancellation | This is the existing zero-runtime-dependency architecture. Verbatim project values: `"requires-python = \">=3.10\""` and `"python-version: ['3.10', '3.11', '3.12', '3.13', '3.14']"`. [VERIFIED: pyproject.toml:1-7; .github/workflows/ci.yml:150-175] |
| `UdpTransport` | in-repository | Own real UDP endpoints and receive queues | It already computes `family = family_for(self._ip_address)`, passes `local_addr=(self._ip_address, self._port)`, and records the underlying endpoint. [VERIFIED: src/lifx/network/transport.py:219-248,302-312,347-369] |
| `pytest` + `pytest-asyncio` | locked `9.1.1` + `1.4.0` | Async unit and emulator integration tests | These are already configured with automatic asyncio mode, coverage, and timeout handling. Verbatim locked versions: `"version = \"9.1.1\""` and `"version = \"1.4.0\""`. [VERIFIED: uv.lock:821-847; pyproject.toml:107-133] |
| `lifx-emulator-core` | locked `3.7.0`, published 2026-06-13 | Real LIFX UDP discovery and typed-device construction on loopback | The current `emulator_server_ipv6` fixture already hosts a synthetic matrix-capable device on an isolated IPv6 port. Verbatim locked version: `"version = \"3.7.0\""`. [VERIFIED: uv.lock:297-307; tests/conftest.py:409-503] |

### Supporting

| Library / facility | Version | Purpose | When to Use |
|--------------------|---------|---------|-------------|
| `pytest-retry` | locked `1.7.0`, published 2025-01-19 | Existing Windows-only retry policy | Mark the focused emulator-backed test with the repository's exact pattern: `"@pytest.mark.flaky(retries=2, delay=1, condition=sys.platform.startswith(\"win32\"))"`. [VERIFIED: uv.lock:879-889; tests/test_network/test_discovery_errors.py:17-19] |
| `asyncio.Event` | Python stdlib | Deterministic open/blocked/closed handshakes | Use in the transport spy and cancellation test; do not infer lifecycle state from sleeps. [VERIFIED: .planning/phases/12-ipv6-discovery-plumbing/12-CONTEXT.md D-07 through D-09] |
| GitHub Actions matrix and step `if` | repository workflow | Select exactly Windows/Python 3.10 | GitHub supports step-level conditions using matrix context, and an omitted `continue-on-error` keeps the step required. [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsif] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing family helpers | New colon checks or a second `ipaddress` parser | Rejected: it recreates the drift Phase 10 removed and violates the locked single-rule constraint. [VERIFIED: src/lifx/network/address.py:1-31; 12-SPEC.md:57-64] |
| Existing `UdpTransport` | A raw test or production socket | Rejected: it would bypass the exact endpoint ownership, family check, queue, and cleanup path this phase must prove. [VERIFIED: src/lifx/network/transport.py:212-369,420-577; 12-CONTEXT.md D-04] |
| Existing IPv6 emulator fixture | A second dedicated emulator architecture | Rejected: the fixture already owns a V6ONLY socket, isolated ephemeral port, failure cleanup, and synthetic device. [VERIFIED: tests/conftest.py:90-105,148-182,409-503] |
| Conditional step in existing matrix job | Separate Windows job | Rejected by D-01 and unnecessary because the existing matrix already carries OS and Python values. [VERIFIED: 12-CONTEXT.md D-01; .github/workflows/ci.yml:150-192] |

**Installation:** none. Phase 12 adds no dependency and must not change `pyproject.toml` or `uv.lock`. [VERIFIED: 12-SPEC.md:47-64; pyproject.toml:1-7]

## Package Legitimacy Audit

Not applicable. No external package is introduced, so the package-legitimacy gate has no candidate package to evaluate. Existing development dependencies remain locked by `uv.lock`. [VERIFIED: 12-SPEC.md:47-64; pyproject.toml:40-59; uv.lock:249-295]

## Architecture Patterns

### System Architecture Diagram

```text
caller: find_by_ip(ip, port)
        |
        v
validate_address(ip) ---------------- invalid / bare link-local --> ValueError, no transport
        |
        v
discover_devices(broadcast_address=ip)
        |
        v
_discover_with_packet(GetService)
        |
        +--> family_for(ip) --> AF_INET  --> wildcard_for(ip) --> 0.0.0.0 + broadcast enabled
        |                  \
        |                   --> AF_INET6 --> wildcard_for(ip) --> ::      + broadcast disabled
        |
        v
UdpTransport async context --> asyncio UDP endpoint --> target emulator/device
        |                                                   |
        |<-- validated StateService: source, packet, serial, UDP service --+
        v
DiscoveredDevice --> create_device() --> correctly typed Device --> caller

cancel/error/return --> async context exit --> UdpTransport.close() --> endpoint closing/closed
```

The flow preserves the existing validation, retransmission, timeout, UDP-service, deduplication, and typed-construction stages; only transport configuration branches by destination family. [VERIFIED: src/lifx/network/discovery.py:232-266,268-520,523-603; src/lifx/network/address.py:136-175]

### Component Responsibilities

| Component | Responsibility in Phase 12 | Must Not Absorb |
|-----------|----------------------------|-----------------|
| `src/lifx/network/address.py` | Remain the unchanged source of address validation, family, and wildcard rules. [VERIFIED: src/lifx/network/address.py:1-31,76-175] | A Phase 12-specific parser or representation allow-list. |
| `src/lifx/network/discovery.py` | Apply the existing helpers when constructing the discovery transport; preserve the receive loop. [VERIFIED: src/lifx/network/discovery.py:165-520] | mDNS merging, timing changes, or device-construction policy. |
| `src/lifx/api.py` | Keep public validation-first delegation and return contract while owning the `discover_devices()` generator with the existing `aclosing()` pattern. [VERIFIED: src/lifx/api.py:15,851-864,919-973] | A second family test or transport parameter. |
| `tests/conftest.py` | Provide the real IPv6 emulator and a focused Windows opt-in that does not unlock the rest of the emulator suite. [VERIFIED: tests/conftest.py:185-211,409-503; 12-CONTEXT.md D-01] | General Windows emulator enablement. |
| API/network tests | Prove public representations, real endpoint family/bind, lifecycle, independence, and IPv4 regression. [VERIFIED: 12-SPEC.md AC1-AC7] | Runner-specific link-local routes or mocked end-to-end delivery. |
| `.github/workflows/ci.yml` | Add one required focused step before the unchanged full-suite step in the selected cell. [VERIFIED: .github/workflows/ci.yml:150-192; 12-CONTEXT.md D-01 through D-03] | A separate job, allowed failure, or committed success artefact. |

### Recommended Project Structure

```text
src/lifx/network/
└── discovery.py                 # family-aware discovery transport construction
src/lifx/
└── api.py                       # deterministic successful-return generator finalisation

tests/
├── conftest.py                  # narrowly gated reuse of IPv6 emulator fixture
├── test_api/
│   ├── test_api_discovery.py    # public validation/sentinel and IPv4 regression
│   └── test_ipv6_e2e.py         # real lookup, family/bind, concurrency, cancellation
└── test_network/
    └── test_discovery_*.py      # transport-construction and invariant regression seam

.github/workflows/
└── ci.yml                       # focused Windows/Python 3.10 step before full suite
```

This placement follows the repository's test-to-source mirroring convention; exact module placement remains planner discretion. [VERIFIED: AGENTS.md:351-368; 12-CONTEXT.md Planner's Discretion]

### Pattern 1: Derive Bind and Broadcast Capability Together

**What:** compute the destination family through the shared helper, bind through `wildcard_for()`, and enable IPv4 broadcast only for AF_INET. [VERIFIED: src/lifx/network/address.py:136-175] [CITED: https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options]

**When to use:** at the single `UdpTransport` construction in `_discover_with_packet()`, before any send or receive-loop work. [VERIFIED: src/lifx/network/discovery.py:232-266]

**Verbatim anchors:** `"return socket.AF_INET6 if addr.version == 6 else socket.AF_INET"`, `"return _IPV6_WILDCARD if family_for(ip) == socket.AF_INET6 else DEFAULT_IP_ADDRESS"`, and the current call `"async with UdpTransport(port=0, broadcast=True) as transport:"`. [VERIFIED: src/lifx/network/address.py:154-175; src/lifx/network/discovery.py:241]

```python
# Source pattern: src/lifx/network/address.py:136-175 and discovery.py:241
destination_family = family_for(broadcast_address)
async with UdpTransport(
    ip_address=wildcard_for(broadcast_address),
    port=0,
    broadcast=destination_family == socket.AF_INET,
) as transport:
    ...
```

The broadcast condition is not optional Windows polish. The current transport sets `SO_BROADCAST` whenever `broadcast` is true, while Microsoft states that IPv6 has no broadcast and excludes `SO_BROADCAST` from the socket options that apply equally to IPv4 and IPv6. [VERIFIED: src/lifx/network/transport.py:326-340] [CITED: https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options]

### Pattern 2: Observe the Real Transport Without Replacing Delivery

**What:** subclass or wrap the production `UdpTransport`, call the real implementation, then record its requested bind, underlying endpoint, actual socket, and open/close events. [VERIFIED: 12-CONTEXT.md D-04, D-07, D-08]

**When to use:** the end-to-end lookup, concurrency, and cancellation tests. Patch the name consumed by `lifx.network.discovery`, not the transport used later by the typed device's separate connection. This keeps discovery traffic real while making only the discovery endpoint observable. [VERIFIED: src/lifx/network/discovery.py:23,241; src/lifx/network/connection.py:237-245]

```python
# Source pattern: tests/test_api/test_ipv6_e2e.py:46-63
class RecordingDiscoveryTransport(UdpTransport):
    async def open(self) -> None:
        await super().open()
        self.endpoint = self._transport
        self.opened.set()

    async def close(self) -> None:
        await super().close()
        self.closed.set()
```

The test must read `endpoint.get_extra_info("socket").family` and `getsockname()` from the actual endpoint. The repository's existing helper explicitly rejects treating the transport's recorded `_family` as proof of what the OS created. [VERIFIED: tests/test_api/test_ipv6_e2e.py:46-63]

### Pattern 3: Split Portable Representation Tests from Routable Proof

**What:** drive compressed, expanded, ULA, documentation-range global-unicast-form, loopback, and zoned link-local strings through public `find_by_ip()`, but substitute only a recording transport for addresses CI cannot route. Use the real `::1` fixture for the one delivery proof. [VERIFIED: 12-CONTEXT.md D-04 through D-06; 12-SPEC.md AC3-AC4]

**When to use:** all representation classes except the loopback end-to-end case. The fake transport should record constructor arguments and destination sends, then end the generator without synthesising a device. [VERIFIED: src/lifx/network/discovery.py:241-266,315-326]

Python 3.10's `ipaddress` accepts compressed, expanded, and scoped IPv6 literals; `IPv6Address.version` and `scope_id` expose the family and zone. [CITED: https://docs.python.org/3.10/library/ipaddress.html#ipaddress.IPv6Address]

### Pattern 4: Cancel Only After the Endpoint Is Open and Receive Is Blocked

**What:** the spy owns an `opened` event and a `closed` event. The test starts `find_by_ip()` against an unused IPv6 loopback port, awaits `opened`, verifies receive is waiting, cancels the task, awaits cancellation, awaits `closed`, asserts the recorded endpoint is closing/closed, then performs a new real emulator lookup. [VERIFIED: 12-CONTEXT.md D-07 through D-09]

**When to use:** only the cancellation-recovery test. Keep the two-successful-lookups concurrency proof separate. [VERIFIED: 12-CONTEXT.md D-09]

Python's async context-manager semantics await `__aexit__` on exceptional exit, and `aclosing()` is the standard deterministic mechanism where an async generator may be exited early. [CITED: https://docs.python.org/3.10/reference/compound_stmts.html#the-async-with-statement] [CITED: https://docs.python.org/3.10/library/contextlib.html#contextlib.aclosing]

A local macOS/Python 3.10 research probe that injected only the intended IPv6 bind into the existing discovery path observed the endpoint become closing after post-open task cancellation. This supports the plan but does not replace the required cross-platform regression test. [VERIFIED: local asyncio probe, 2026-08-29]

### Pattern 5: Opt In Only the Focused Windows Invocation

**What:** add a dedicated IPv6-emulator availability decision that preserves `--disable-emulator`, keeps normal Windows full-suite behaviour skipped, and permits the existing IPv6 fixture only when the focused CI step sets its test-only opt-in. [VERIFIED: tests/conftest.py:185-211,242-265,409-503; 12-CONTEXT.md D-01 through D-03]

**When to use:** the selected Windows/Python 3.10 step only. Unix matrix cells continue using the existing IPv6 fixture normally; the subsequent Windows full-suite step runs without the opt-in and retains the blanket skip. [VERIFIED: .github/workflows/ci.yml:150-192; 12-SPEC.md AC8-AC9]

The focused test uses the existing exact Windows retry shape, remains required, and runs before the unchanged `"uv run --frozen pytest"` full suite. GitHub documents that step-level `if` can use matrix contexts and that `continue-on-error: true` is what would prevent a failing step from failing the job, so it must not be added here. [VERIFIED: tests/test_network/test_discovery_errors.py:17-19; .github/workflows/ci.yml:181-192] [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsif] [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepscontinue-on-error]

### Anti-Patterns to Avoid

- **Second address parser:** duplicates validation or family logic and reopens the drift Phase 10 closed. Use the existing helpers unchanged. [VERIFIED: src/lifx/network/address.py:1-31]
- **IPv6 endpoint with `broadcast=True`:** attempts to carry an IPv4-only socket option into Winsock's IPv6 path. Derive the flag from AF_INET. [VERIFIED: src/lifx/network/transport.py:326-340] [CITED: https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options]
- **Mocked end-to-end response:** proves orchestration but not a real UDP exchange or typed construction. Only the representation table should fake the transport. [VERIFIED: 12-CONTEXT.md D-04-D-05]
- **Fixed sleep cancellation:** can cancel before open or after timeout and still pass. Synchronise on explicit spy events. [VERIFIED: 12-CONTEXT.md D-07]
- **Unlocking every Windows emulator test:** broadens the phase into general Windows emulator support. Gate the one focused invocation. [VERIFIED: 12-SPEC.md:47-55; 12-CONTEXT.md D-01]
- **New CI job or allowed failure:** violates the selected matrix cell and cannot satisfy AC9. [VERIFIED: 12-CONTEXT.md D-01, D-10-D-11; 12-SPEC.md AC9]
- **Timing-constant edits:** family plumbing must not touch discovery/retry/animation tuning. [VERIFIED: 12-SPEC.md AC10; .agents/skills/spike-findings-lifx-async/references/discovery.md Constraints]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Address validation | A Phase 12 allow-list or colon heuristic | `validate_address()` | It already rejects empty, malformed, mapped, unspecified, and unzoned link-local inputs before networking. [VERIFIED: src/lifx/network/address.py:76-134] |
| Socket family selection | A second AF_INET/AF_INET6 decision | `family_for()` and `wildcard_for()` | These helpers are the repository's single family rule and already serve connection/animation transports. [VERIFIED: src/lifx/network/address.py:11-31,136-175] |
| UDP endpoint ownership | Raw sockets or a Phase 12 transport | `UdpTransport` async context manager | It already owns open, send-family checking, receive, and close state. [VERIFIED: src/lifx/network/transport.py:212-577] |
| IPv6 test server | A second server process or runner-specific daemon | `emulator_server_ipv6` and `_Ipv6EmulatedLifxServer` | They already enforce AF_INET6, V6ONLY, failure cleanup, synthetic identity, and ephemeral port selection. [VERIFIED: tests/conftest.py:90-105,148-182,409-503] |
| Cancellation timing | Poll loops or sleeps | `asyncio.Event` signals from the spy | The locked decisions require observable open, blocked, and closed lifecycle boundaries. [VERIFIED: 12-CONTEXT.md D-07-D-09] |
| Retry orchestration | Shell retry loops or a second plugin | Existing `pytest.mark.flaky` policy | The repository already limits two retries with one-second delay to Windows. [VERIFIED: tests/test_network/test_discovery_errors.py:17-19; uv.lock:879-889] |
| CI evidence storage | JUnit evidence artefact or exception document | Required step log and job result | D-10 declares ordinary required CI evidence sufficient. [VERIFIED: 12-CONTEXT.md D-10-D-12] |

**Key insight:** the implementation should connect existing, already-tested seams. New parsers, transports, emulators, timing policy, or evidence formats would add failure modes without advancing FIND-06. [VERIFIED: 12-SPEC.md Boundaries and AC1-AC12]

## Common Pitfalls

### Pitfall 1: Fixing the Bind but Leaving IPv4 Broadcast Configuration Enabled

**What goes wrong:** an AF_INET6 discovery transport reaches the Windows-only `SO_BROADCAST` call even though IPv6 has no broadcast. [VERIFIED: src/lifx/network/transport.py:326-340] [CITED: https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options]

**Why it happens:** the current constructor combines local-bind selection and broadcast permission in one hard-coded call. [VERIFIED: src/lifx/network/discovery.py:241]

**How to avoid:** derive `broadcast` from `destination_family == socket.AF_INET` at the same point as the wildcard. [VERIFIED: src/lifx/network/address.py:136-175] [CITED: https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options]

**Warning signs:** Unix passes, while the required Windows focused step fails during endpoint open or socket-option setup before any packet is sent. [CITED: https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options]

### Pitfall 2: Testing Intent Instead of the OS Socket

**What goes wrong:** a test asserts constructor arguments or `_family` and reports IPv6 coverage even if the actual endpoint is wrong. [VERIFIED: tests/test_api/test_ipv6_e2e.py:46-63]

**How to avoid:** assert the real socket's `.family` and `getsockname()` wildcard; retain the endpoint reference for close assertions. [VERIFIED: tests/test_api/test_ipv6_e2e.py:46-63; 12-CONTEXT.md D-04, D-08]

### Pitfall 3: Patching Away the End-to-End Path

**What goes wrong:** stubbing `discover_devices()` or returning a prebuilt `Light` skips LIFX discovery parsing and `DiscoveredDevice.create_device()`. [VERIFIED: src/lifx/api.py:960-973; src/lifx/network/discovery.py:60-129,523-603]

**How to avoid:** patch only `lifx.network.discovery.UdpTransport` with an observation-only subclass for the real `::1` test. [VERIFIED: 12-CONTEXT.md D-04]

### Pitfall 4: A Sentinel at the Wrong Boundary

**What goes wrong:** asserting that a mocked delegate was not called does not directly pin the prohibition on transport construction/open. [VERIFIED: tests/test_api/test_api_discovery.py:512-528; 12-CONTEXT.md D-06]

**How to avoid:** patch the discovery transport name to a fail-on-construction sentinel, call public `find_by_ip()`, and cover empty, malformed, and bare link-local inputs. [VERIFIED: src/lifx/api.py:955-969; 12-CONTEXT.md D-06]

### Pitfall 5: Non-Deterministic Cancellation Evidence

**What goes wrong:** a fixed delay can cancel before the endpoint exists or after the receive wait already ended. [VERIFIED: 12-CONTEXT.md D-07]

**How to avoid:** require an open event, a blocked-receive event, and a close event from the real spy; then assert the recorded endpoint is closing/closed and run a fresh real lookup. [VERIFIED: 12-CONTEXT.md D-07-D-09]

### Pitfall 6: Conflating Discovery and Device-Connection Endpoints

**What goes wrong:** `create_device()` opens a separate per-device transport for capability detection, so recording every `UdpTransport` globally can make endpoint counts and bind assertions ambiguous. [VERIFIED: src/lifx/network/discovery.py:60-127; src/lifx/network/connection.py:237-245]

**How to avoid:** patch the imported transport name in `lifx.network.discovery` and record only instances created by `_discover_with_packet()`. [VERIFIED: src/lifx/network/discovery.py:23,241]

### Pitfall 7: Expanding the Windows Escape Hatch by Accident

**What goes wrong:** removing the blanket Windows skip globally turns the full emulator suite into Phase 12 scope, or `continue-on-error` converts the required attempt into non-evidence. [VERIFIED: tests/conftest.py:185-211; 12-CONTEXT.md D-01, D-10-D-11]

**How to avoid:** opt in only the focused invocation, keep the normal full suite unchanged, and leave the step required until the operator explicitly exercises D-11. [VERIFIED: 12-CONTEXT.md D-01-D-03, D-10-D-12]

### Pitfall 8: Treating Documentation-Range Representation Tests as Routing Tests

**What goes wrong:** ULA, global-form, or link-local cases fail for runner topology rather than family selection. [VERIFIED: 12-CONTEXT.md D-05]

**How to avoid:** instrument only the transport boundary for non-loopback representations and reserve real routing for `::1`. [VERIFIED: 12-CONTEXT.md D-04-D-05]

### Pitfall 9: Weakening Discovery Invariants While Editing the Loop

**What goes wrong:** a family fix accidentally changes retransmit offsets, idle/overall deadlines, source/serial checks, UDP-only filtering, first-wins deduplication, or cleanup. [VERIFIED: src/lifx/network/discovery.py:268-520; 12-SPEC.md AC6, AC10]

**How to avoid:** constrain the production diff to imports and transport construction, then run the existing discovery error and rebroadcast suites unchanged. [VERIFIED: tests/test_network/test_discovery_rebroadcast.py; tests/test_network/test_discovery_errors.py]

### Pitfall 10: Leaking Identifiers into Tests or CI Evidence

**What goes wrong:** a live address, serial, hostname, or raw discovery log becomes tracked history. [VERIFIED: AGENTS.md:17-38]

**How to avoid:** use `::1`, documentation ranges, and the existing synthetic fixture constant; inspect the staged diff before commit. [VERIFIED: AGENTS.md:32-38; tests/conftest.py:409-503]

## Code Examples

Verified patterns from repository and official sources:

### Actual Socket Inspection

```python
# Source: tests/test_api/test_ipv6_e2e.py:54-63
endpoint = discovery_transport._transport
assert endpoint is not None
sock = endpoint.get_extra_info("socket")
assert sock is not None
assert sock.family == socket.AF_INET6
assert sock.getsockname()[0] == "::"
```

The exact IPv6 family and wildcard values are anchored by the repository quotes `"return socket.AF_INET6 if addr.version == 6 else socket.AF_INET"` and `"_IPV6_WILDCARD = \"::\""`. [VERIFIED: src/lifx/network/address.py:70-73,136-155]

### Validation-Before-Construction Sentinel

```python
# Source pattern: src/lifx/api.py:955-969 and CONTEXT D-06
class FailOnUseTransport:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("transport constructed before validation completed")
```

Install the sentinel at `lifx.network.discovery.UdpTransport`, then parameterise public `find_by_ip()` over the three locked invalid classes. [VERIFIED: 12-CONTEXT.md D-06; src/lifx/network/discovery.py:23,241]

### Existing Windows Retry Policy

```python
# Source: tests/test_network/test_discovery_errors.py:17-19
@pytest.mark.flaky(retries=2, delay=1, condition=sys.platform.startswith("win32"))
```

The values are quoted verbatim from the existing policy and satisfy D-03 without a shell-level retry. [VERIFIED: tests/test_network/test_discovery_errors.py:17-19; 12-CONTEXT.md D-03]

## State of the Art

| Old / Current Approach | Current Phase 12 Approach | When Changed | Impact |
|------------------------|---------------------------|--------------|--------|
| `_discover_with_packet()` always constructs the default IPv4 transport. [VERIFIED: src/lifx/network/discovery.py:241] | Destination family chooses wildcard and IPv4-only broadcast capability. [VERIFIED: 12-SPEC.md R1; src/lifx/network/address.py:136-175] | Phase 12 | IPv6 literals reach a compatible endpoint without changing public signatures or receive-loop semantics. [VERIFIED: 12-SPEC.md AC1-AC6] |
| IPv6 emulator proves direct connection and animation only. [VERIFIED: tests/test_api/test_ipv6_e2e.py:66-226] | The same fixture proves public targeted discovery and typed construction. [VERIFIED: 12-CONTEXT.md D-04] | Phase 12 | FIND-06 gains real end-to-end evidence rather than family-only unit evidence. [VERIFIED: .planning/REQUIREMENTS.md FIND-06] |
| Windows emulator-backed tests are blanket-skipped. [VERIFIED: tests/conftest.py:185-211] | One required focused invocation opts into the targeted IPv6 fixture in Windows/Python 3.10. [VERIFIED: 12-CONTEXT.md D-01-D-03] | Phase 12 | Windows compatibility becomes observed without making the full emulator suite Phase 12 work. [VERIFIED: 12-SPEC.md AC8-AC9] |

**Deprecated/outdated:**

- The current test `test_routable_ipv6_literal_falls_through` explicitly records the pre-Phase-12 outcome `None`; replace or rewrite it when FIND-06 lands. [VERIFIED: tests/test_api/test_api_discovery.py:540-553]
- The claim in `UdpTransport._endpoint_lost()` that both callers always bind `0.0.0.0` becomes outdated when discovery can bind `::`; update that comment if the production diff makes it false. [VERIFIED: src/lifx/network/transport.py:392-400]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | No `[ASSUMED]` claims remain. | — | — |

All implementation recommendations are grounded in locked decisions, current source, local probes, or official documentation. The only unresolved outcome is whether the real Windows runner and external emulator pass; that is an execution result, not an assumption to lock during planning. [VERIFIED: 12-CONTEXT.md D-11-D-12]

## Open Questions — RESOLVED

1. **RESOLVED for planning: the Windows result is an execution-time required checkpoint governed by D-11 and D-12.**
   - What we know: the blanket gate prevents current evidence, while the fixture already owns and cleans up a V6ONLY AF_INET6 socket. [VERIFIED: tests/conftest.py:148-182,185-211,409-503]
   - Disposition: the required real Windows/Python 3.10 CI attempt has not yet occurred and is not claimed as research evidence. Execution must run the named required step, treat a red result as implementation input, fix every in-scope library or fixture defect, and stop only for the operator-controlled D-11 decision; any explicit drop decision is recorded under D-12. [VERIFIED: current phase state, 2026-08-29; 12-CONTEXT.md D-10-D-12]

2. **RESOLVED: place the IPv6 broadcast guard at the grounded discovery call site.**
   - What we know: only discovery sets `broadcast=True`, and Phase 12 introduces the first IPv6 instance of that call; Windows documents `SO_BROADCAST` as inapplicable to IPv6. [VERIFIED: src/lifx/network/discovery.py:241; src/lifx/network/transport.py:326-340] [CITED: https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options]
   - Disposition: derive the flag from `family_for(broadcast_address) == socket.AF_INET` at `_discover_with_packet()` and keep `UdpTransport` behaviour unchanged. Revise that placement only if actual Windows execution evidence demonstrates the grounded caller-side configuration is insufficient. [VERIFIED: 12-SPEC.md phase boundary; src/lifx/network/discovery.py:241]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | all Python commands | ✓ | `0.11.29` | none; uv is mandatory. [VERIFIED: local environment probe, 2026-08-29; AGENTS.md:48-100] |
| Python | library/test floor | ✓ | local `3.10.11`; CI `3.10` through `3.14` | CI matrix supplies remaining supported versions. [VERIFIED: local environment probe, 2026-08-29; .github/workflows/ci.yml:150-175] |
| IPv6 loopback bind | emulator E2E | ✓ | AF_INET6 `::1` bind succeeded locally | CI fixture skips except where must-not-skip/focused gates require failure. [VERIFIED: local socket probe, 2026-08-29; tests/conftest.py:214-265] |
| `lifx-emulator-core` | real targeted discovery | ✓ | `3.7.0` | no mock fallback for AC3. [VERIFIED: local environment probe, 2026-08-29; uv.lock:297-307; 12-SPEC.md AC3] |
| pytest stack | all focused tests | ✓ | pytest `9.1.1`, pytest-asyncio `1.4.0`, pytest-retry `1.7.0`, pytest-timeout `2.4.0` | none. [VERIFIED: local environment probe, 2026-08-29; uv.lock:821-847,879-913] |
| Windows GitHub-hosted runner | AC9 | not locally available | `windows-latest` / Python `3.10` is configured | Required CI matrix attempt; no local substitute counts. [VERIFIED: .github/workflows/ci.yml:150-175; .planning/phases/12-ipv6-discovery-plumbing/12-CONTEXT.md D-01] |

**Missing dependencies with no fallback:** the actual Windows runner is available only during CI; its result is a required execution gate rather than a local research blocker. [VERIFIED: 12-SPEC.md AC9]

**Missing dependencies with fallback:** none. [VERIFIED: environment audit, 2026-08-29]

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not set `security_enforcement` to false. The ASVS 4.0.3 category names below match the workflow's required applicability review. [VERIFIED: .planning/config.json, read 2026-08-29] [CITED: https://devguide.owasp.org/en/03-requirements/05-asvs/]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No identity or authentication surface is added by a local UDP address-family change. [VERIFIED: 12-SPEC.md Boundaries] |
| V3 Session Management | no | Discovery calls are per-call async generators and introduce no authenticated session state. [VERIFIED: src/lifx/network/discovery.py:165-520; 12-SPEC.md Boundaries] |
| V4 Access Control | no | Phase 12 adds no authorisation decision or privileged operation. [VERIFIED: 12-SPEC.md Boundaries] |
| V5 Validation, Sanitisation and Encoding | yes | Keep `validate_address()` before transport construction; retain packet-size, source, packet-type, serial, and UDP-service validation. [VERIFIED: src/lifx/network/address.py:76-134; src/lifx/network/discovery.py:322-424] |
| V6 Stored Cryptography | no | The phase stores no credentials or encrypted material and adds no cryptographic operation. [VERIFIED: 12-SPEC.md Boundaries] |

### Known Threat Patterns for asyncio UDP Discovery

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Spoofed or unrelated UDP response | Spoofing | Preserve per-call source-ID matching before accepting a response. [VERIFIED: src/lifx/network/discovery.py:242-252,342-348] |
| Broadcast/multicast/malformed serial claims a device | Spoofing / Tampering | Preserve target multicast, all-zero, and padding validation before serial conversion and first-wins dedup. [VERIFIED: src/lifx/network/discovery.py:361-387,449-452] |
| Oversized or undersized hostile datagram aborts discovery | Denial of Service | Keep transport size validation and discovery's `LifxProtocolError` continue path. [VERIFIED: src/lifx/network/transport.py:486-544; src/lifx/network/discovery.py:322-340] |
| Non-UDP StateService claims the serial first | Tampering | Filter non-UDP service responses before first-wins dedup. [VERIFIED: src/lifx/network/discovery.py:405-424,449-452] |
| Invalid address consumes timeout or opens the wrong family | Denial of Service | Validate at the public entry point, then derive both bind and family from the accepted literal. [VERIFIED: src/lifx/api.py:955-969; src/lifx/network/address.py:76-175] |
| Cancellation leaves an endpoint live | Denial of Service | Keep async-context ownership and add deterministic post-open cancellation/close evidence. [VERIFIED: src/lifx/network/discovery.py:241-520; src/lifx/network/transport.py:254-261,546-568; 12-CONTEXT.md D-07-D-09] |

## Sources

### Primary (HIGH confidence)

- `src/lifx/network/address.py` - validated address rules and exact family/wildcard values.
- `src/lifx/network/discovery.py` - current transport-construction defect and invariant-bearing receive loop.
- `src/lifx/api.py` - public validation-first `find_by_ip()` path.
- `src/lifx/network/transport.py` - family derivation, socket options, real endpoint state, and cleanup.
- `tests/conftest.py` and `tests/test_api/test_ipv6_e2e.py` - existing V6ONLY emulator, synthetic fixture, and actual-socket inspection.
- `.github/workflows/ci.yml` - exact matrix, full-suite step, and must-not-skip gate.
- `.planning/phases/12-ipv6-discovery-plumbing/12-SPEC.md` and `12-CONTEXT.md` - locked scope, acceptance, and implementation decisions.
- `.agents/skills/spike-findings-lifx-async/references/discovery.md` - validated discovery invariants and no-retuning constraint.

### Secondary (MEDIUM confidence)

- [Python 3.10 asyncio event loop documentation](https://docs.python.org/3.10/library/asyncio-eventloop.html#asyncio.loop.create_datagram_endpoint) - datagram family, local address, socket ownership.
- [Python 3.10 ipaddress documentation](https://docs.python.org/3.10/library/ipaddress.html#ipaddress.IPv6Address) - compressed, expanded, version, and scope identifiers.
- [Python 3.10 contextlib documentation](https://docs.python.org/3.10/library/contextlib.html#contextlib.aclosing) - deterministic async-generator finalisation.
- [pytest fixture documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html#teardown-cleanup-aka-fixture-finalization) - yield-fixture teardown.
- [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsif) - matrix-aware step conditions and required-step behaviour.
- [Microsoft Winsock socket options](https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options) - `SO_BROADCAST` does not apply to IPv6.
- [OWASP Developer Guide ASVS](https://devguide.owasp.org/en/03-requirements/05-asvs/) - ASVS 4.0.3 applicability categories.

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - exact repository and lock-file versions were opened and locally imported. [VERIFIED: pyproject.toml:1-59; uv.lock:297-307,821-913; local environment probe, 2026-08-29]
- Architecture: HIGH - the entire public-to-socket path and fixture/CI seams were inspected; the intended bind and cancellation behaviour were also probed locally without editing the repository. [VERIFIED: src/lifx/api.py:919-973; src/lifx/network/discovery.py:165-603; src/lifx/network/transport.py:212-577; local probes, 2026-08-29]
- Pitfalls: HIGH for repository and Windows socket-option issues; MEDIUM for the unexecuted Windows runner outcome. [VERIFIED: current source and tests] [CITED: https://learn.microsoft.com/en-us/windows/win32/winsock/socket-options]

**Validation architecture:** intentionally omitted because the configuration says verbatim `"nyquist_validation": false`. [VERIFIED: .planning/config.json:21-26]

**Research date:** 2026-08-29
**Valid until:** 2026-09-05 for CI/platform details; repository code citations remain valid only for commit `e5b8042c927b` on branch `gsd/phase-12-ipv6-discovery-plumbing`. [VERIFIED: local git inspection, 2026-08-29]
