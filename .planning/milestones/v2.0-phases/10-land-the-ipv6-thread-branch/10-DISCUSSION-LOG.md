# Phase 10: Land the IPv6/Thread Branch - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md, this log preserves the alternatives considered.

**Date:** 2026-08-27
**Phase:** 10-land-the-ipv6-thread-branch
**Areas discussed:** Address helper home and surface; `::1` fixture and Windows gate;
Universal-skip CI assertion; Rebase and PR shape

---

## Address helper home and surface

### Q1: Where should the single address-family implementation live?

| Option | Description | Selected |
|--------|-------------|----------|
| New leaf `src/lifx/address.py` | Mirrors `geometry.py` / `theme/slug.py`; avoids `devices` and `animation` importing from `network` | |
| `src/lifx/network/utils.py` | Already holds `allocate_source()` and `IdleDeadline`; no new file | |
| New `src/lifx/network/address.py` | Inside the layer owning sockets, dedicated module rather than a grab-bag | ✓ |

**User's choice:** New `src/lifx/network/address.py`

### Q2: What surface should it expose?

| Option | Description | Selected |
|--------|-------------|----------|
| Two functions: validate + family | `validate_address()` raises, `family_for()` returns; smallest surface | ✓ |
| One parse function returning a record | `parse_address() -> ParsedAddress` with family, normalised literal, zone, wildcard | |
| One function returning family, raising inline | Fewest names; reads badly at entry points | |

**User's choice:** Two functions: validate + family
**Notes:** A third function, `wildcard_for()`, was added in Q5, so the module ships three.

### Q3: How much of `Device.__init__`'s address validation moves in?

| Option | Description | Selected |
|--------|-------------|----------|
| Only the new rules | Empty/None, malformed, zone-less link-local, IPv4-mapped; smallest diff | |
| All address rules move | Loopback, unspecified and non-private too; truest to "one implementation" | ✓ |
| New rules now, note the rest as follow-up | Same as first, with the remainder recorded as deferred | |

**User's choice:** All address rules move to the helper
**Notes:** Chose the fuller consolidation despite the larger patch diff. This is what made
Q4 necessary.

### Q4: What happens to the moved `# pragma: no cover` branches?

| Option | Description | Selected |
|--------|-------------|----------|
| Drop them and test every branch | Pure functions are trivially testable; consistent with the SPEC prohibition | ✓ |
| Carry the pragmas across unchanged | Smallest work; reads as the weakening the SPEC forbids | |
| Drop them, and accept a scope increase | Same as first, with the cost flagged in the plan estimate | |

**User's choice:** Drop them and test every branch

### Q5: Where does `DeviceConnection`'s wildcard bind-literal mapping live?

| Option | Description | Selected |
|--------|-------------|----------|
| Third helper: `wildcard_for(ip)` | `connection.py` contains no family test at all | ✓ |
| `DeviceConnection` maps from `family_for()` | No new name, but the rule reappears in `connection.py` | |
| `UdpTransport` takes a family instead | Changes a constructor used by discovery and broadcast paths too | |

**User's choice:** Third helper: `wildcard_for(ip)`

### Q6: Do the serial checks move as well?

| Option | Description | Selected |
|--------|-------------|----------|
| No, serial stays in `Device.__init__` | `network/address.py` owns addresses only | ✓ |
| Yes, move them and test them too | Consolidates all construction-time validation; not IPv6 work | |
| No, but drop their pragmas in place | Cleans the debt without moving code | |

**User's choice:** No, serial stays in `Device.__init__`
**Notes:** The user corrected the question's first phrasing, which wrote the broadcast
serial MAC-style. Serials are handled as 12-digit hex strings, so it is `ffffffffffff`.
The question was reissued with the correction.

### Q7: Where does `find_by_ip()` validate?

| Option | Description | Selected |
|--------|-------------|----------|
| First statement, before any socket | Raises well inside 100 ms; valid IPv6 still returns `None` until Phase 12 | ✓ |
| Same, plus a docstring note about the Phase 12 gap | Costs a docs line Phase 12 then deletes | |
| Same, and raise `LifxUnsupportedCommandError` for valid IPv6 | Contradicts the SPEC boundary | |

**User's choice:** First statement, before any socket

### Q8: How should the moved warnings identify themselves in logs?

| Option | Description | Selected |
|--------|-------------|----------|
| Log as the helper, drop the Device context | Honest about where the check runs; low-risk break | ✓ |
| Pass a caller context argument | Preserves today's log shape; a parameter that only shapes a log line | |
| Return the warnings, let callers log | Most flexible; a caller that forgets silently drops the warning | |

**User's choice:** Log as the helper, drop the Device context

### Q9: The SPEC's R1 concurrency backstop row

| Option | Description | Selected |
|--------|-------------|----------|
| Reframe as a construction-time assertion | Collapses into AC 2; `_addr` is immutable | ✓ |
| Keep it, testing private mutation explicitly | Would fail as written without a per-frame check | |
| Keep the row, mark it dismissed with reason | Leaves the row visible in the edge table | |

**User's choice:** Reframe it as a construction-time assertion
**Notes:** The user challenged the premise: "How could a family change on an existing
cached socket? That seems impossible." Verified in the code: `Animator._addr` is assigned
once at `animator.py:147` and never reassigned; `close()` clears `self._socket` but not the
address. The SPEC row overstated the risk and was amended in place (A-03). In the resolution
the row was moved to `dismissed` with the reasoning recorded, which also satisfies the third
option.

---

## `::1` fixture and Windows gate

### Q1: The Windows conflict

| Option | Description | Selected |
|--------|-------------|----------|
| Amend AC 13 to Linux + macOS | Records the win32 exclusion as pre-existing and unrelated to IPv6 | ✓ |
| Reopen the win32 gate for the IPv6 fixture only | Unproven; flakiness would land on the critical-path PR | |
| Reopen the win32 gate entirely | Large unrelated scope increase | |

**User's choice:** Amend AC 13 to Linux + macOS
**Notes:** Raised by Claude during scouting, not by the SPEC. `tests/conftest.py:148`
already disables all emulator tests on `win32`.

### Q2: Proving the IPv6 tests are not silently running over IPv4

| Option | Description | Selected |
|--------|-------------|----------|
| Assert socket families, drop same-port coexistence | Proves the exchange directly rather than inferring it | ✓ |
| Keep same-port coexistence as well | Belt and braces; adds fixture coupling and a port probe | |
| Keep AC 16 as written | Treats the SPEC as locked | |

**User's choice:** Assert socket families, drop the same-port coexistence
**Notes:** The user asked "Why does it want this?" of AC 16. The answer is that it guards
against a false green via dual-stack capture, which requires a wildcard `::` bind. This
fixture binds `::1` specifically, which cannot receive IPv4-mapped traffic. AC 16 was
amended in place (A-02).

### Q3: Fixture shape

| Option | Description | Selected |
|--------|-------------|----------|
| Second session fixture, mirroring `tile_chain_server` | Existing `emulator_server` untouched | ✓ |
| Parameterise `emulator_server` over both families | Doubles the emulator suite's runtime on every job | |
| Second fixture, minimal device set | Faster startup, second roster to maintain | |

**User's choice:** Second session fixture, mirroring `tile_chain_server`

### Q4: Capability probe

| Option | Description | Selected |
|--------|-------------|----------|
| Session-scoped bool fixture, like `emulator_available` | One probe per session, one skip gate | ✓ |
| `@pytest.mark.ipv6` with an autouse skip hook | Makes the IPv6 set enumerable by marker | |
| Both: probe fixture plus marker | Marker exists only for CI counting | |

**User's choice:** Session-scoped bool fixture

### Q5: The loopback warning on every `::1` test

| Option | Description | Selected |
|--------|-------------|----------|
| Leave it, unchanged from today | Already fires for `127.0.0.1` across the whole suite | ✓ |
| Downgrade loopback to debug level | Changes behaviour unrelated to IPv6 | |
| Filter it in the test fixtures | Could mask a genuine regression | |

**User's choice:** Leave it, unchanged from today

### Q6: End-to-end scope

| Option | Description | Selected |
|--------|-------------|----------|
| Exactly SPEC R1's list, on a `Light` | Connect, `get_color`, `set_color`, `set_power`, animator frames | ✓ |
| Add a `MatrixLight` animator path | Matches the Thread hardware, duplicates existing coverage | |
| Broader sweep across device classes | Substantial runtime for repeated coverage of the same code | |

**User's choice:** Exactly SPEC R1's list, on a `Light`

---

## Universal-skip CI assertion

### Q1: Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Designated must-not-skip job via env var | One job red, no aggregation or artefact plumbing | ✓ |
| Per-job skip-count artefacts collated by a gate job | Literal reading of "across all jobs"; breaks silently | |
| Parse junit-xml in a final gate job | Needs junit output and a marker to identify IPv6 tests | |

**User's choice:** Designated must-not-skip job via env var

### Q2: Which job

| Option | Description | Selected |
|--------|-------------|----------|
| ubuntu + the lowest Python (3.10) | LedFx floor; most exposed to stdlib differences; always in the matrix | ✓ |
| ubuntu + the highest Python (3.14) | Newest asyncio; a 3.10 regression would only skip | |
| ubuntu on every Python version | Strongest signal; five jobs red for one hiccup | |

**User's choice:** ubuntu + the lowest Python (3.10)

### Q3: Gate scope

| Option | Description | Selected |
|--------|-------------|----------|
| IPv6 probe only | The variable means what its name says | ✓ |
| Both probes | Closes the missing-emulator loophole; misnames the variable | |
| A separate `LIFX_REQUIRE_EMULATOR` as well | Precise; a second knob `uv sync` already covers | |

**User's choice:** IPv6 probe only

---

## Rebase and PR shape

### Q1: How the work lands

| Option | Description | Selected |
|--------|-------------|----------|
| One PR: rebase + fixes + fixture | Patch coverage computed over the whole diff; one CI cycle | ✓ |
| Two PRs: rebase first, then fixes | Smaller reviews; rebase-only PR must pass the gate alone | |
| One PR, fixes squashed into the three commits | Cleanest history; violates R8's signature preservation | |

**User's choice:** One PR: rebase + fixes + fixture

### Q2: When the branch's own tests get corrected

| Option | Description | Selected |
|--------|-------------|----------|
| In the fix commits that change the behaviour | Rebase is verifiably a pure replay | ✓ |
| A test-reconciliation commit right after the rebase | Red by construction | |
| Amend the rebased commits' tests during the rebase | Re-signs the commits R8 asks to preserve | |

**User's choice:** In the fix commits that change the behaviour

### Q3: Hardware UAT evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `scripts/ipv6_thread_probe.py` to emit the UAT record | The script already drives the library's primitives against real hardware | ✓ |
| A separate UAT harness on the v1.2 Phase 8 pattern | Consistent with prior evidence records; overlaps the probe | |
| Manual run, hand-written record | Provenance rests entirely on trust | |

**User's choice:** Extend the probe to emit the UAT record

### Q4: UAT timing

| Option | Description | Selected |
|--------|-------------|----------|
| After CI is green, before merge | Exercises the code actually about to land | ✓ |
| Early, against the rebased branch | Proves the branch, not the merged code | |
| Both: early smoke, final gating run | Two hardware sessions, only the second counts | |

**User's choice:** After CI is green, before merge

### Q5: `backup/ipv6-thread-pre-rebase`

| Option | Description | Selected |
|--------|-------------|----------|
| Repoint it at `2f884f5` first | Makes the safety net real | |
| Create a new dated backup ref | Nothing lost; two similarly-named refs | |
| Skip it, the reflog and the PR are enough | Rebase onto a clean merge base is recoverable | ✓ |

**User's choice:** Skip it
**Notes:** Raised by Claude after finding the ref sits at `af17071`, a single commit holding
an older version of the branch's first commit, not at today's `2f884f5` head.

### Q6: Plan split

| Option | Description | Selected |
|--------|-------------|----------|
| Four plans on the dependency chain | Rebase, helper, remaining fixes, fixture and CI gate | ✓ |
| Two plans: rebase, then everything else | Large second plan, hard to review or revert selectively | |
| Let plan-phase decide the split | Helper-before-fixes ordering is expensive to get wrong | |

**User's choice:** Four plans on the dependency chain

---

## Claude's Discretion

- Whether the B1 family assertion is raised before or after the existing transport-liveness
  check in `UdpTransport.send()`
- Whether the `MdnsTransport.open()` leak fix uses `try/except` with an explicit
  `sock.close()` or a `contextlib.ExitStack`
- The exact wording of the corrected `network/mdns/transport.py` docstrings
- Whether `LIFX_REQUIRE_IPV6` is documented in `CLAUDE.md` alongside
  `LIFX_EMULATOR_EXTERNAL`

## Deferred Ideas

- `.planning/PROJECT.md:302` is stale about `backup/ipv6-thread-pre-rebase` holding the
  pre-rebase state; correct at the next phase transition
- Reopening the `win32` emulator gate (`tests/conftest.py:148`), with its own flakiness
  measurement
- Consolidating the serial validation in `Device.__init__` and removing its
  `# pragma: no cover` markers
