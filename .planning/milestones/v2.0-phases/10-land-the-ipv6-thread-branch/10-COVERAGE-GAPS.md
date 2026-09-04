# Phase 10: Branch Patch-Coverage Gaps

**Measured:** 2026-08-27, on the rebased `feat/ipv6-thread-support` head
**Measured against:** `git diff main HEAD` restricted to `src/lifx/*` and `scripts/*`
**Coverage source:** `coverage.xml` from `uv run --frozen pytest` (3526 passed).
`pyproject.toml` `addopts` already carries `--cov-branch`, so no flag or configuration
was changed to produce this.

## Why this file exists

`codecov.yml` sets `coverage.status.patch.default.target: 100%`, and the gate scores
**partial branches as well as uncovered lines** (auto-memory `project_codecov_branch_patch`).
Review finding 3 moved this measurement from plan 10-06 into Wave 1, so plans 10-02 and
10-03 schedule the work instead of improvising it against the merge deadline
(threat T-10-19).

Every path returned by `git diff main HEAD --name-only -- 'src/lifx/*' 'scripts/*'` has a
heading below, including the ones with no gaps. `src/lifx/api.py` has **no** heading because
the rebased branch does not touch it; it enters the patch diff only in plan 10-02, when
`find_by_ip()` gains its `validate_address()` call, and that plan carries the test in the
same commit (D-19).

A line is listed only if the patch gate scores it, meaning it is an added or changed line in
the branch diff. Where a nearby uncovered line is a diff *context* line it is called out
explicitly, so plan 10-06 does not read its absence as an oversight.

---

## `src/lifx/network/mdns/discovery.py`

**Owner: plan 10-03** (10 uncovered lines, 9 partial branches)

The branch rewrote this file (+328/-, `_LifxRecordCache`, `_pick_address()`, PTR
retransmission, follow-up A/AAAA queries). The gaps cluster in the three behaviours the
rewrite added and no existing test drives.

### Uncovered lines

- **226** in `pending_targets()`. The `continue` taken when a cached TXT instance has no
  matching SRV record. No test presents a TXT record without its SRV partner.
- **229** in `pending_targets()`. The `continue` taken when the SRV target's address is
  already cached, so no follow-up query is needed. Every test fixture supplies address
  records alongside the SRV, so this skip never fires.
- **387, 388, 396** in `discover_lifx_services()`. The PTR retransmission body: popping the
  elapsed delay, logging `retransmitting_query`, and re-sending the query. No test runs long
  enough to cross a retransmission slot.
- **449, 451, 452, 460** in `discover_lifx_services()`. The follow-up A/AAAA query loop over
  `pending_targets()`: the dedupe and 64-target cap guard, adding to `queried_targets`, the
  `querying_addresses` debug log, and the `build_address_query()` send. The loop body never
  executes because `pending_targets()` always returns empty (see lines 226 and 229 above).
  *Note:* line 450 (the `continue` inside that guard) is also uncovered but is a diff
  **context** line, so the patch gate does not score it.
- **475** in `discover_lifx_services()`. The serial-dedupe `continue`. No test presents the
  same serial in two response packets.

### Partial branches

- **101**, `_LifxRecordCache._add()`, `50% (1/2)`, missing `exit`. The drop arm taken when
  the table is at `_MAX_ENTRIES` (1024) and the key is new. This is the T-10-01 unbounded
  growth mitigation, so it is the arm that most needs a test.
- **137**, `add_packet()`, `50% (1/2)`, missing `117`. The false arm of
  `record.parsed_data not in addrs and len(addrs) < 16`, meaning a duplicate AAAA or a
  seventeenth AAAA for one host is skipped. Also a T-10-01 bound.
- **225**, `50% (1/2)`, missing `226`. Companion to uncovered line 226.
- **228**, `50% (1/2)`, missing `229`. Companion to uncovered line 229.
- **386**, `50% (1/2)`, missing `387`. The retransmission slot test never evaluates true.
- **397**, `50% (1/2)`, missing `400`. The false arm of `if retransmit_delays:`, where the
  receive timeout is not clamped to the next retransmission.
- **403**, `50% (1/2)`, missing `408`. On `LifxTimeoutError`, the true arm that loops to
  re-send rather than breaking. *Note:* line 408, the clean-break arm, is a diff context
  line and is out of patch-gate scope.
- **448**, `50% (1/2)`, missing `449`. The follow-up query `for` loop never enters its body.
- **474**, `50% (1/2)`, missing `475`. Companion to uncovered line 475.

---

## `src/lifx/network/mdns/dns.py`

**Owner: plan 10-03** (5 uncovered lines, 0 partial branches)

### Uncovered lines

- **378, 380, 381, 382, 384**, the entire body of `build_address_query()`. The function is
  never called by any test, and its only production caller (`discovery.py:460`) is itself
  uncovered. A direct unit test on the returned bytes closes all five at once: two questions
  in the header, one A and one AAAA question for the encoded name.

`_encode_name()`, the other symbol the branch added here, is already covered through
`build_service_query()`.

---

## `src/lifx/network/mdns/transport.py`

**Owner: plan 10-03** (no gaps)

All added lines are covered. The branch's change here was largely deletion, removing the
`IP_ADD_MEMBERSHIP` multicast join and the 5353 bind fallback in favour of a plain ephemeral
bind. Plan 10-03 still touches this file for the IPV6-04 socket-leak fix and the B4 docstring
correction, and that work brings its own new lines into the patch diff.

---

## `src/lifx/devices/base.py`

**Owner: plan 10-02** (1 uncovered line, 1 partial branch)

### Uncovered lines

- **527**, the `_LOGGER.warning({... "action": "link_local_without_scope" ...})` call. No
  test constructs a `Device` with a zone-less IPv6 link-local literal such as `fe80::1`.

### Partial branches

- **522**, `50% (1/2)`, missing `527`. The true arm of
  `addr.version == 6 and addr.is_link_local and getattr(addr, "scope_id", None) is None`.

Both gaps close together. Note that plan 10-02 flips this warning into a `ValueError`
(branch-audit finding B2) and moves the check into `lifx.network.address.validate_address()`,
so the test that closes this gap lands in the same commit as that behaviour change (D-19),
not as a retrofit against the warning the branch shipped.

---

## `src/lifx/network/connection.py`

**Owner: plan 10-02** (no gaps)

Both added executable lines are covered. The `local_ip = "::" if ":" in self.ip else
DEFAULT_IP_ADDRESS` wildcard selection is exercised on the IPv4 side by the existing emulator
suite. Plan 10-02 replaces the inline heuristic with `wildcard_for()`, which brings a new
line into the patch diff and needs the IPv6 arm covered at that point.

---

## `src/lifx/network/transport.py`

**Owner: plan 10-02** (no gaps)

The added `family = socket.AF_INET6 if ":" in self._ip_address else socket.AF_INET` line is
covered. As with `connection.py`, only the IPv4 arm actually runs today; the line itself is
not a branch, so the gate does not currently see the gap. Plan 10-02 replaces it with
`family_for()`, and **plan 10-03** adds the B1 send-time family assertion; both bring new
lines into the patch diff that need IPv6 coverage when they land.

*Corrected 2026-08-27 by plan 10-03.* This paragraph originally attributed the B1
send-time family assertion to plan 10-02 as well. That was wrong: plan 10-02 landed only
the `family_for()` adoption, and B1 is SPEC Requirement 5, owned by plan 10-03 Task 1.
The misattribution mattered because plan 10-06 verifies this list before the PR opens and
would have read B1 as already delivered.

---

## `src/lifx/animation/animator.py`

**Owner: plan 10-02** (no gaps)

The added frame-socket family selection is covered by the tests the branch brought with it
(`tests/test_animation/test_animator.py`, +38 lines). Plan 10-02 rewrites the same line to
call `family_for()`.

---

## `scripts/ipv6_thread_probe.py`

**Owner: plan 10-05** (0 measured gaps; 521 added lines carry no coverage data at all)

This file is **not measured**. `pyproject.toml` `addopts` declares `--cov=lifx` and
`--cov=generate_theme_data` only, so the probe script produces no entry in `coverage.xml`
and contributes no scored lines to the patch status, even though `codecov.yml` scopes the
five Python flags to `src/lifx/` and `scripts/`.

This is a reporting gap, not a coverage gap, and it must not be closed by widening
`--cov`. Doing so would drop 521 unmeasured lines into a 100% patch target in the same PR.
Plan 10-05 owns the decision and must record the probe's coverage treatment explicitly,
covering its new pure helpers (`_select_target()`, `_capture_device_state()`,
`_restore_device_state()`, `_stage_result()`, `_build_uat_record()`, `_write_uat_record()`)
via `tests/test_scripts/test_ipv6_thread_probe.py`, which is reachable because
`pythonpath` already includes `scripts`.

---

## Totals

| Owning plan | Files | Uncovered lines | Partial branches |
|-------------|-------|-----------------|------------------|
| 10-02 | `devices/base.py`, `network/connection.py`, `network/transport.py`, `animation/animator.py` | 1 | 1 |
| 10-03 | `network/mdns/discovery.py`, `network/mdns/dns.py`, `network/mdns/transport.py` | 15 | 9 |
| 10-05 | `scripts/ipv6_thread_probe.py` | 0 measured (521 lines unmeasured) | 0 measured |
| **Total** | 8 files | **16** | **10** |

Plan 10-06 Task 1 verifies this list is closed rather than discovering its size.

---

*Phase: 10-land-the-ipv6-thread-branch*
*Produced by: plan 10-01, Task 2*
