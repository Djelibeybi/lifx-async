# Phase 10: Land the IPv6/Thread Branch, Specification

**Created:** 2026-08-27
**Ambiguity score:** 0.11 (gate: ≤ 0.20)
**Requirements:** 9 locked

## Goal

The three commits of `feat/ipv6-thread-support` (`b49400b`, `b88cdb9`, `2f884f5`) are rebased
onto `main` and merged with branch-audit findings B1, B2, B4 and B9 fixed, so a caller can
connect to, control and stream animation frames to a device whose only address is IPv6.

## Background

`main` is IPv4-only at every socket-creation site. `UdpTransport.open()` passes
`family=socket.AF_INET` unconditionally, `DeviceConnection._open()` constructs
`UdpTransport(port=0, ...)` with the default IPv4 bind, `Animator` creates its direct-UDP frame
socket as `socket.socket(socket.AF_INET, socket.SOCK_DGRAM)`, and `Device.__init__` raises
`ValueError("Only IPv4 addresses are supported")` for anything else. The fleet has two Thread
`MatrixLight` devices on ULA prefix `fd00:1::` that the library cannot reach at all.

**Corrected 2026-08-28 by plan 10-06.** The prefix above is stale. Plan 10-06's discovery
sweep found nothing on `fd00:1::`; the live Thread OMR prefix is
`fd00:2::/64`, and the mesh now carries six IPv6-only devices rather than two (the
two `MatrixLight`s plus a `CeilingLight`, a `MultiZoneLight` and two single-zone `Light`s).
A Thread OMR prefix is an auto-generated ULA that re-derives whenever the border router
re-forms the mesh, so the durable identifier is the serial, not the address. The SPEC is
locked, so this is recorded as a correction rather than an edit to the prose above, matching
how review finding 4's `codecov.yml` imprecision was handled. No requirement or acceptance
criterion depends on the prefix: R9 and AC 19 identify the UAT target by serial.

`feat/ipv6-thread-support` fixes this across 11 files (+1131/-330). Its stdlib primitives and
address-family seam were judged correct by the v2.0 research pass, so this phase is a rebase
plus a reconciled fix list, not a rewrite. The branch diverged at `42c9ad2` (6.5.1); `main` has
16 commits since, none of them touching `network/`, `animation/` or `devices/base.py`, so the
rebase is expected to be clean.

Four defects the branch introduced or left standing are in scope here:

- **B2**: the branch downgraded the zone-less IPv6 link-local rejection in `Device.__init__`
  from `ValueError` to a `WARNING` log. Because `UdpTransport` routes every send-time `OSError`
  to `error_received` and deliberately never raises, this turns a permanent configuration error
  into a silent 16 second timeout.
- **B9**: the `":" in ip` family heuristic is written out three times, in
  `network/transport.py:295`, `network/connection.py:234` and `animation/animator.py:399`.
- **B1**: no send-time family assertion exists, so a destination whose family does not match the
  socket's is swallowed as a `gaierror` and surfaces as a timeout.
- **B4**: `network/mdns/transport.py`'s module and class docstrings still describe joining the
  mDNS multicast group, which `IP_ADD_MEMBERSHIP` removal made false.
- **IPV6-04**: `MdnsTransport.open()` creates and configures `sock` before
  `create_datagram_endpoint()`; an `OSError` at any point after `socket.socket()` raises
  `LifxNetworkError` without closing the descriptor.

The `::1` test fixture is newly in scope for this phase (see Boundaries). `lifx-emulator-core`
3.7.0 already accepts `bind_address` and calls `create_datagram_endpoint(local_addr=...)` with
no explicit `family`, so asyncio infers `AF_INET6` from `"::1"`. This was verified on the
development machine: `local_addr=("::1", 0)` yields family 30. No emulator-side change is
required.

## Requirements

1. **IPv6 device control** (IPV6-01): A caller can connect to, control and stream animation
   frames to a device whose only address is IPv6.
   - Current: `UdpTransport.open()` hard-codes `family=socket.AF_INET`; `Animator` hard-codes
     `socket.AF_INET`; `Device.__init__` rejects every non-IPv4 address outright
   - Target: every socket-creation site (`UdpTransport`, `DeviceConnection`, the `Animator`
     frame socket) derives its socket family from the target address via the R3 helper
   - Acceptance: against an emulator bound to `::1`, a `Light` connects, reads state, sets
     colour and power, and an `Animator` delivers frames; the frame socket's family is asserted
     to be `AF_INET6`

2. **Fast, typed rejection of zone-less link-local** (IPV6-02): An IPv6 link-local address with
   no zone identifier raises `ValueError` immediately.
   - Current: the branch logs a `WARNING` and proceeds, costing a silent 16 second timeout
   - Target: `Device.__init__`, `Device.from_ip()`, `find_by_ip()` and `Device.connect()` each
     raise `ValueError` naming the missing zone identifier, before any socket is created
   - Acceptance: each of the four entry points raises `ValueError` for `fe80::1` in under
     100 ms and never reaches a socket; `fe80::1%en0` is accepted at all four
   - **Amended 2026-08-27** (post cross-AI review, finding 9): `Device.connect()` was added as a
     fourth entry point. It bypasses `Device.__init__` when no serial is supplied
     (`feat/ipv6-thread-support:src/lifx/devices/base.py:739-750`), so the serial-less leg
     reproduced the exact 16 second silent timeout this requirement exists to eliminate. This
     reconciles the enumeration with the intent already recorded in the Interview Log — "every
     public entry point taking an address" — rather than widening scope

3. **One address-family implementation** (IPV6-03): Address-family selection has exactly one
   implementation.
   - Current: the `":" in ip` heuristic appears three times, in `network/transport.py:295`,
     `network/connection.py:234` and `animation/animator.py:399`
   - Target: a shared helper owns family derivation and address validation, mirroring the way
     `theme/slug.py` owns the slug rule; all three sites call it and none contains a family test
   - Acceptance: a repository grep for `":" in ` under `src/lifx/` returns no family-selection
     use; unit tests cover IPv4, IPv6, `"::"`/`"0:0:0:0:0:0:0:0"` equivalence, zone-less
     link-local rejection, IPv4-mapped rejection, and empty/`None` rejection

4. **No socket leak on mDNS open failure** (IPV6-04): `MdnsTransport.open()` that fails partway
   through leaves no socket behind.
   - Current: `sock` is created, bound and configured before `create_datagram_endpoint()`; any
     `OSError` after `socket.socket()` raises `LifxNetworkError` with the descriptor still open
   - Target: the failure path closes any socket it created before raising
   - Acceptance: a test that forces `OSError` at each of `bind()`, `setsockopt()` and
     `create_datagram_endpoint()` asserts the socket is closed in every case and that no
     `ResourceWarning` is emitted

5. **Send-time family assertion** (B1): `UdpTransport.send()` fails loudly on a family mismatch.
   - Current: sending an IPv6 literal from an `AF_INET` socket raises `socket.gaierror`, an
     `OSError` subclass, which asyncio routes to `error_received` and the transport swallows;
     the caller waits out the full retry schedule
   - Target: `send()` raises `LifxNetworkError` immediately when the destination family does not
     match the socket family
   - Acceptance: sending an IPv6 destination on an `AF_INET` transport raises `LifxNetworkError`
     in under 100 ms; a separate test asserts `EHOSTUNREACH`, `EHOSTDOWN` and `ENETUNREACH` from
     a real peer still route to `error_received` and still do not tear the endpoint down

6. **Honest mDNS transport docstrings** (B4): `network/mdns/transport.py` no longer claims
   multicast group membership.
   - Current: the module docstring says "with multicast group joining" and `MdnsTransport`'s
     class docstring says "with support for multicast group membership", after
     `IP_ADD_MEMBERSHIP` was removed
   - Target: both describe the actual behaviour, an ephemeral-port RFC 6762 section 6.7 legacy
     unicast query socket, with no membership claim
   - Acceptance: neither docstring contains "multicast group", "membership" or
     "IP_ADD_MEMBERSHIP"; the RFC 6762 section 6.7 rationale already in `open()` is reflected in
     the class docstring

7. **IPv6 emulator fixture and end-to-end tests** (new in this phase): CI exercises the IPv6
   path for real, without hardware.
   - Current: every emulator fixture binds `127.0.0.1`; no test exercises an `AF_INET6` socket
   - Target: a pytest fixture starts `lifx-emulator-core` with `bind_address="::1"` and explicit
     `IPV6_V6ONLY`; IPv6 end-to-end tests run on all of Python 3.10 to 3.14 behind a capability
     probe that skips when `::1` cannot be bound; a CI step fails the build if every job skipped
   - Acceptance: the `::1` fixture starts and serves requests on Linux and macOS; the
     capability probe skips cleanly on a host with IPv6 loopback disabled; the CI step goes red
     when the designated must-not-skip job cannot run the IPv6 tests
   - **Amended 2026-08-27 (discuss-phase).** Windows was struck from this criterion:
     `tests/conftest.py:148` already returns `emulator_available = False` on `win32`, so every
     emulator test skips there today. That exclusion predates this phase and is unrelated to
     IPv6. The universal-skip assertion was also narrowed from cross-job aggregation to a single
     designated job, `LIFX_REQUIRE_IPV6=1` on ubuntu with Python 3.10

8. **Rebased, merged, CI green** (IPV6-01..04 delivery): The branch is on `main`.
   - Current: three commits on `feat/ipv6-thread-support`, unmerged, diverged at `42c9ad2`
   - Target: rebased onto `main` and squashed to two commits (D-25, 2026-08-28) — `79a5ce0`,
     redding1's original replayed byte-identically, plus one authored commit carrying the rest
     of the series — both GPG-signed with DCO sign-off intact and redding1 credited by
     `Co-Authored-By` on the squashed commit, merged via PR with CI green
   - Acceptance: `main` contains the rebased commits; the CI run is green including quality,
     generated-files and the full 3-OS by 5-version matrix; Codecov reports 100% *branch* patch
     coverage on the merged report, with zero partial branches, not merely 100% line coverage

9. **Thread hardware UAT** (new in this phase): The IPv6 path is proven on real Thread hardware
   before merge, or its absence is recorded as an operator-approved exception.
   - Current: no Thread device has ever been reached by this library
   - Target: a recorded UAT run proves connect and control against a Thread `MatrixLight` over
     IPv6, and gates the merge. The animation frame-streaming run is recorded as an artefact but
     does not gate, because Thread frame-rate ceilings are Phase 14's measurement. If no Thread
     device is reachable when the branch is otherwise ready, the operator may waive the control
     gate by recording a `10-EXCEPTION-OVERRIDE.json` on the v1.2 Phase 8 schema, naming why the
     hardware was unavailable and deferring the evidence to THREAD-05 in Phase 14. CI green is
     never waivable
   - Acceptance: either `10-UAT-RESULTS.json` exists, carries the device serial of one of the two
     known Thread MatrixLights and a timestamp inside the phase window, and records the control
     run as passed; or `10-EXCEPTION-OVERRIDE.json` exists with `kind`
     `operator-approved-exception`, `decision` `accepted_exception`, `authority` `operator`, a
     non-empty reason for hardware unavailability, and a THREAD-05 deferral reference. The
     streaming run is recorded with whatever result it produced, or noted as not run

## Boundaries

**In scope:**

- Rebasing all three branch commits onto `main` whole, including the `network/mdns/discovery.py`
  and `network/mdns/dns.py` rewrite and `scripts/ipv6_thread_probe.py`
- Branch-audit fixes B1, B2, B4 and B9
- The `MdnsTransport.open()` socket-leak fix (IPV6-04)
- IPv4-mapped IPv6 addresses (`::ffff:192.0.2.1`) rejected with `ValueError` by the shared helper
- A `bind_address="::1"` emulator fixture and IPv6 end-to-end tests, skip-guarded across the
  full Python matrix, with a universal-skip CI assertion
- Zone-less link-local `ValueError` at `Device.__init__`, `Device.from_ip()`, `find_by_ip()` and
  `Device.connect()` (the fourth added by the 2026-08-27 amendment above)
- A recorded Thread hardware UAT gating the merge on the control path, waivable only by an
  operator-approved exception recorded as `10-EXCEPTION-OVERRIDE.json`

**Out of scope:**

- **B3, address selection ordering** (`_pick_address` returning `routable[0]`, single retained
  address). Phase 11 owns ULA/GUA/link-local ordering and the multi-address record
- **B5, mDNS TTL, cache-flush and goodbye handling**. Phase 11
- **B6, TXT `id` serial validation**. Phase 11
- **B7, the duplicated device-class ladder in `create_device_from_record`**. Phase 12/13, where
  the two legs meet
- **B8, no `ff02::fb` IPv6 mDNS leg**. Deliberately not recorded as a limitation here; Phase 11
  owns the mDNS documentation pass (MDNS-08) and it belongs with the rest of that text
- **`find_by_ip()` returning a device for a valid IPv6 literal**. Phase 12 (FIND-06). This phase
  adds only the zone-less rejection to that entry point; a valid IPv6 address still returns
  `None` until Phase 12 wires the family-aware lookup
- **The family-aware `_discover_with_packet` bind**. Phase 12 (FIND-06)
- **Merged `discover()` and racing `find_by_serial()`**. Phase 13
- **Any Thread measurement or constant retuning**. Phase 14 (THREAD-01..05)
- **mDNS `tm` transport field**. Phase 11 (MDNS-02)

## Constraints

- **Python 3.10 floor.** The library ships 3.10 for LedFx; `asyncio.TaskGroup` is unavailable.
- **Zero runtime dependencies.** `pyproject.toml` declares `dependencies = []`.
- **100% branch patch coverage.** `codecov.yml` sets `patch.default.target: 100%` with no
  `flags:` key, so the status is computed against the merged report across all five Python flags.
  Branch partials count against it, not only uncovered lines.
- **CI matrix.** `os × python-version`: three OSes on a source-changing PR, ubuntu only
  otherwise; Python 3.10 to 3.14. Coverage uploads come from the ubuntu jobs only.
- **Windows `IPV6_V6ONLY` defaults on**, so per-family sockets are required and dual-stack tricks
  are not available.
- **Commit signing.** GPG key `27B3A9EA...20F03B05` and DCO sign-off must survive the rebase.
- **No WiFi-measured constant may be retuned before Phase 14 measures it over Thread.**

## Acceptance Criteria

- [ ] An emulator bound to `::1` serves connect, state read, `set_color` and `set_power` to a
      `Light`, and `Animator` delivers frames to it
- [ ] The `Animator` frame socket's family is asserted `AF_INET6` for an IPv6 target and
      `AF_INET` for an IPv4 target
- [ ] `Device.__init__`, `Device.from_ip()`, `find_by_ip()` and `Device.connect()` each raise
      `ValueError` for `fe80::1` in under 100 ms, and each accepts `fe80::1%en0`
- [ ] `fe80::1%` (empty zone) raises; `FE80::1` and the fully expanded form raise identically
- [ ] `::ffff:192.0.2.1` raises `ValueError` from the shared helper
- [ ] `""` and `None` raise `ValueError` from the shared helper
- [ ] `"::"` and `"0:0:0:0:0:0:0:0"` resolve to the same family
- [ ] A grep for `":" in ` under `src/lifx/` returns no family-selection use
- [ ] `MdnsTransport.open()` closes its socket when `bind()`, `setsockopt()` or
      `create_datagram_endpoint()` raises, with no `ResourceWarning`
- [ ] `UdpTransport.send()` raises `LifxNetworkError` in under 100 ms on a destination/socket
      family mismatch
- [ ] `EHOSTUNREACH`, `EHOSTDOWN` and `ENETUNREACH` from a peer still route to `error_received`
      and still do not tear the endpoint down
- [ ] `network/mdns/transport.py` docstrings contain no "multicast group", "membership" or
      "IP_ADD_MEMBERSHIP"
- [ ] The `::1` fixture starts and serves on Linux and macOS (amended: Windows skips all
      emulator tests today, `tests/conftest.py:148`)
- [ ] The capability probe skips cleanly where `::1` cannot be bound
- [ ] CI fails when the designated must-not-skip job (ubuntu, Python 3.10, `LIFX_REQUIRE_IPV6=1`)
      cannot run the IPv6 tests
- [ ] Each IPv6 end-to-end test asserts the socket family it used is `AF_INET6`, so a test cannot
      pass while silently running over IPv4; the fixture sets `IPV6_V6ONLY` explicitly
      (amended: this replaces same-port coexistence, which a `::1`-specific bind cannot suffer
      the dual-stack capture that criterion guarded against)
- [ ] Every commit the merge adds to `main` carries a good GPG signature (`git verify-commit`
      exits 0 on each) and a `Signed-off-by` trailer; `79a5ce0` is present unmodified with
      redding1's original sign-off, and redding1 is credited by `Co-Authored-By` on the squashed
      commit (amended 2026-08-28 for the D-25 squash; previously "all three commits", which the
      squash made unsatisfiable without losing the authorship it was written to protect)
- [ ] Codecov reports 100% branch patch coverage on the merged report, zero partial branches
- [ ] Either `10-UAT-RESULTS.json` records a passed control run against a Thread MatrixLight,
      carrying that device's serial and a timestamp inside the phase window, or
      `10-EXCEPTION-OVERRIDE.json` records an operator-approved exception with a non-empty reason
      for hardware unavailability and a THREAD-05 deferral reference
- [ ] Exactly one of `10-UAT-RESULTS.json` and `10-EXCEPTION-OVERRIDE.json` is present, never
      both, so the phase record cannot claim a pass and a waiver at once
- [ ] CI green is required in both cases; the exception waives only the hardware gate
- [ ] The streaming UAT run is recorded with its actual result, pass or fail, and does not gate
- [ ] NEGATIVE: no value of `REQUEST_RETRANSMIT_GAPS`, `ACK_INFLIGHT_LIMIT`,
      `ACK_EXPIRY_SECONDS` or `DISCOVERY_REBROADCAST_GAPS` changes in this phase
- [ ] NEGATIVE: `pyproject.toml` `dependencies` is still `[]`
- [ ] NEGATIVE: no new `# pragma: no cover` on IPv6 code, no existing test deleted or skipped to
      make the rebase pass, and `codecov.yml`'s patch target is unchanged
- [ ] NEGATIVE: the UAT record is not marked passed without an actual hardware run

## Edge Coverage

**Coverage:** 31/31 applicable edges resolved · 0 unresolved
(16 covered by acceptance criteria, 1 held-out backstop test, 14 dismissed with reason.
Amended 2026-08-27 in discuss-phase: the R1 concurrency backstop moved to dismissed.
29 rows proposed by the edge-probe engine, 2 added by classification beyond that floor.)

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | `::ffff:192.0.2.1` rejected with `ValueError`; AC 5 |
| empty | R1 | ✅ covered | `""`/`None` rejected at construction; AC 6 |
| ordering | R1 | ⛔ dismissed | Family selection produces no collection; stable order has no meaning |
| concurrency | R1 | ⛔ dismissed | *(amended 2026-08-27, discuss-phase)* Originally a held-out backstop against a stale-family cached socket. `Animator._addr` is assigned once at `animator.py:147` and never reassigned; `close()` clears `self._socket` but not the address, so an `Animator`'s family is fixed for its lifetime and the scenario is reachable only by mutating a private attribute. Collapses into AC 2, the construction-time family assertion |
| adjacency | R2 | ✅ covered | `fe80::1` raises, `fe80::1%en0` does not; AC 3 |
| empty | R2 | ✅ covered | `fe80::1%` (empty zone) raises; AC 4 |
| encoding | R2 | ✅ covered | `FE80::1` and the expanded form raise identically; AC 4 |
| ordering | R2 | ⛔ dismissed | Single scalar input, no ordering semantics |
| adjacency | R3 | ✅ covered | `"::"` and `"0:0:0:0:0:0:0:0"` resolve to the same family; AC 7 |
| empty | R3 | ✅ covered | Shared with R1/empty; AC 6 |
| encoding | R3 | ✅ covered | The helper owns normalisation; shared with R2/encoding; AC 4 |
| ordering | R3 | ⛔ dismissed | Pure function of one string, no collection produced |
| concurrency | R3 | ⛔ dismissed | Pure function, no shared state, nothing to interrupt |
| concurrency | R4 | 🧪 backstop | Held-out test: concurrent `open()` calls, and `close()` racing a failing `open()`, leak no descriptor in either interleaving. The `if self._protocol is not None` early return is not atomic. Carry into plan-phase `must_haves` |
| concurrency | R5 | ✅ covered | `send()` after endpoint death raises the typed error rather than dereferencing a `None` transport; AC 10 |
| error-handling | R5 | ✅ covered | *(added beyond the probe floor)* The family assertion must not convert genuine peer errors into raises; the swallow-all `error_received` contract stays intact; AC 11 |
| adjacency | R6 | ⛔ dismissed | Docstring-only change, no runtime behaviour |
| empty | R6 | ⛔ dismissed | Docstring-only change, no runtime behaviour |
| ordering | R6 | ⛔ dismissed | Docstring-only change, no runtime behaviour |
| concurrency | R6 | ⛔ dismissed | Docstring-only change, nothing to interrupt |
| boundary | R7 | ✅ covered | CI fails when the designated must-not-skip job cannot run the IPv6 tests; AC 15 *(amended: single designated job, not cross-job aggregation)* |
| adjacency | R7 | ✅ covered | Each IPv6 test asserts its socket family is `AF_INET6`; AC 16 *(amended: replaces same-port coexistence)* |
| platform | R7 | ✅ covered | *(added beyond the probe floor)* The fixture sets `IPV6_V6ONLY` explicitly rather than relying on the platform default; AC 16. *(Amended: the Windows motivation no longer applies, since Windows skips all emulator tests, but explicit is still correct hygiene against a future wildcard bind)* |
| empty | R7 | ⛔ dismissed | Fixture device population follows the existing emulator fixture pattern, unchanged here |
| ordering | R7 | ⛔ dismissed | No collection produced |
| precision | R7 | ⛔ dismissed | No numeric semantics in a fixture |
| boundary | R8 | ✅ covered | 100% *branch* patch coverage on the merged report; branch partials count, not just line hits; AC 18 |
| precision | R8 | ⛔ dismissed | Folded into R8/boundary; the target is exact with no threshold, nothing to round |
| adjacency | R9 | ✅ covered | Control passing while streaming fails is an explicit, allowed outcome; AC 19, AC 20 |
| empty | R9 | ✅ covered | No reachable Thread device routes to an operator-approved exception recorded as `10-EXCEPTION-OVERRIDE.json`, not to an indefinite block; AC 19, AC 20, AC 21 |
| ordering | R9 | ⛔ dismissed | Artefact record, no ordering semantics |

## Prohibitions (must-NOT)

**Coverage:** 4/4 applicable prohibitions resolved · 0 unresolved

Canon referral: GPG/DCO commit signing is project canon, enforced by the commit hook and CI;
not minted here.

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT retune any WiFi-measured reliability constant (`REQUEST_RETRANSMIT_GAPS`, `ACK_INFLIGHT_LIMIT`, `ACK_EXPIRY_SECONDS`, `DISCOVERY_REBROADCAST_GAPS`) in this phase | R1, R5, R8 | resolved | judgment. Phase 14 owns the Thread measurement; the IPv6 work runs past these constants and Thread latency will tempt a nudge |
| MUST NOT add a runtime dependency | R3, R7, R8 | resolved | judgment. `pyproject.toml` declares `dependencies = []`; IPv6/mDNS work is where `zeroconf`, `ifaddr` or `netifaces` get reached for |
| MUST NOT reach the green gate by weakening the checks: no new `# pragma: no cover` on IPv6 code, no existing test deleted or skipped to make the rebase pass, no lowering of the Codecov patch target | R7, R8 | resolved | judgment. The 100% branch gate is exactly the pressure that invites this |
| MUST NOT record the hardware UAT as passed without an actual run against a Thread MatrixLight | R9 | resolved | judgment. Nothing can prove a log came from real hardware, so this routes to judgment review. The recorded exception is the sanctioned route when hardware is unavailable: an honest "not run" is always available, so there is never a reason to fabricate a pass |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                          |
|--------------------|-------|------|--------|------------------------------------------------|
| Goal Clarity       | 0.92  | 0.75 | ✓      | Three named commits, four named audit fixes    |
| Boundary Clarity   | 0.90  | 0.70 | ✓      | B3/B5/B6/B7/B8 and FIND-06 explicitly excluded |
| Constraint Clarity | 0.85  | 0.65 | ✓      | Merged-report patch gate confirmed in codecov.yml |
| Acceptance Criteria| 0.86  | 0.70 | ✓      | 24 pass/fail criteria, 4 of them negative      |
| **Ambiguity**      | 0.11  | ≤0.20| ✓      |                                                |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | Does the branch's mDNS rewrite land in Phase 10 or defer to Phase 11? | Land all three commits whole; Phase 11 hardens what landed |
| 1 | Researcher | How is IPv6-only control proven without the Phase 12 `::1` fixture? | Clarified the emulator is `lifx-emulator-core`; verified `bind_address="::1"` needs no upstream change; fixture pulled into Phase 10 plus hardware UAT |
| 1 | Researcher | Which remaining branch-audit findings join the fix list? | B4 (docstrings) and B1 (send-time family assertion) in; B8 out |
| 2 | Simplifier | Does the Thread hardware UAT gate the merge? | Blocking for control, non-blocking for streaming |
| 2 | Simplifier | What happens on a runner without IPv6 loopback? | Confirmed the merged-report patch gate makes a 3.14-only restriction viable; user chose all versions, skip-guarded |
| 2 | Boundary Keeper | Where is IPV6-02's `ValueError` raised? | Every public entry point taking an address |
| 3 | Boundary Keeper | Confirm the test-matrix trade-off (3.10 is the LedFx floor) | All versions, skip-guarded |
| 3 | Boundary Keeper | Where does `find_by_ip()` split against Phase 12's FIND-06? | Validation in Phase 10, IPv6 lookup stays Phase 12 |
| 4 | Failure Analyst | Edge probe: IPv4-mapped IPv6 addresses | Reject with `ValueError` |
| 4 | Failure Analyst | Edge probe: universal-skip of the IPv6 tests | CI fails if every job skipped |
| 4 | Failure Analyst | Edge probe: no Thread hardware at merge time | Merge blocks; no override |
| 6 | Seed Closer | Reversal: should the hardware gate admit an exception? | Operator-approved exception allowed, recorded as `10-EXCEPTION-OVERRIDE.json` on the v1.2 Phase 8 schema; supersedes the round 4 decision |
| 4 | Failure Analyst | Edge probe: 15 non-material rows | Dismissed as a batch with recorded reasons |
| 5 | Seed Closer | Prohibition probe: 4 kept after precision filter | All 4 kept at judgment tier |

---

*Phase: 10-land-the-ipv6-thread-branch*
*Spec created: 2026-08-27*
*Next step: /gsd-discuss-phase 10, implementation decisions (helper placement and signature, fixture shape, rebase mechanics)*
