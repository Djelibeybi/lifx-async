# Phase 10: Land the IPv6/Thread Branch - Context

**Gathered:** 2026-08-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Rebase the three `feat/ipv6-thread-support` commits (`b49400b`, `b88cdb9`, `2f884f5`) onto
`main` and merge them with branch-audit findings B1, B2, B4 and B9 fixed, plus the
`MdnsTransport.open()` socket-leak fix (IPV6-04), so a caller can connect to, control and
stream animation frames to a device whose only address is IPv6.

This phase decides **how** that lands. The **what** is locked by `10-SPEC.md`.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**9 requirements are locked.** See `10-SPEC.md` for full requirements, boundaries, and
acceptance criteria.

Downstream agents MUST read `10-SPEC.md` before planning or implementing. Requirements are
not duplicated here.

**In scope (from SPEC.md):**

- Rebasing all three branch commits onto `main` whole, including the
  `network/mdns/discovery.py` and `network/mdns/dns.py` rewrite and
  `scripts/ipv6_thread_probe.py`
- Branch-audit fixes B1, B2, B4 and B9
- The `MdnsTransport.open()` socket-leak fix (IPV6-04)
- IPv4-mapped IPv6 addresses (`::ffff:192.0.2.1`) rejected with `ValueError` by the shared
  helper
- A `bind_address="::1"` emulator fixture and IPv6 end-to-end tests, skip-guarded across the
  full Python matrix, with a universal-skip CI assertion
- Zone-less link-local `ValueError` at `Device.__init__`, `Device.from_ip()` and
  `find_by_ip()`
- A recorded Thread hardware UAT gating the merge on the control path, waivable only by an
  operator-approved exception recorded as `10-EXCEPTION-OVERRIDE.json`

**Out of scope (from SPEC.md):**

- **B3**, address selection ordering. Phase 11
- **B5**, mDNS TTL, cache-flush and goodbye handling. Phase 11
- **B6**, TXT `id` serial validation. Phase 11
- **B7**, the duplicated device-class ladder in `create_device_from_record`. Phase 12/13
- **B8**, no `ff02::fb` IPv6 mDNS leg. Phase 11 owns the mDNS documentation pass (MDNS-08)
- **`find_by_ip()` returning a device for a valid IPv6 literal.** Phase 12 (FIND-06). This
  phase adds only the zone-less rejection to that entry point
- **The family-aware `_discover_with_packet` bind.** Phase 12 (FIND-06)
- **Merged `discover()` and racing `find_by_serial()`.** Phase 13
- **Any Thread measurement or constant retuning.** Phase 14 (THREAD-01..05)
- **mDNS `tm` transport field.** Phase 11 (MDNS-02)

</spec_lock>

<spec_amendments>
## SPEC.md Amendments Made During This Discussion

Three acceptance criteria in `10-SPEC.md` were amended in place during this discussion,
because scouting the codebase found them resting on facts that do not hold. The amendments
are already written into `10-SPEC.md` and marked there, so the two documents cannot
disagree. They are restated here so the change is visible in the phase record.

- **A-01: AC 13 narrowed from "Linux, macOS and Windows" to "Linux and macOS."**
  `tests/conftest.py:148` already returns `emulator_available = False` on `win32` ("too
  flaky on Windows: timing-sensitive UDP"), so every emulator test skips there today. That
  exclusion predates this phase and has nothing to do with IPv6. Reopening it would be a
  large unrelated scope increase on the milestone's critical path. Windows still runs the
  address helper's unit tests, which are pure and platform-independent.

- **A-02: AC 16 rewritten from same-port emulator coexistence to a socket-family
  assertion.** AC 16 existed to prevent a false green, an "IPv6 end-to-end test" actually
  served over IPv4. The mechanism it guarded against is dual-stack capture, which requires
  a wildcard (`::`) bind: on Linux `net.ipv6.bindv6only` defaults to 0, so a `::` socket
  also accepts IPv4-mapped traffic. This fixture binds `::1` specifically, and a
  `::1` socket cannot receive IPv4-mapped traffic, whose loopback form is
  `::ffff:127.0.0.1`, a different address. Asserting the socket family directly proves what
  AC 16 wanted, without the fixture complexity. `IPV6_V6ONLY` is still set explicitly as
  hygiene against a future wildcard bind.

- **A-03: the R1 concurrency backstop row moved from `backstop` to `dismissed`.** It held
  out a test that an `Animator` with a stale-family cached socket does not silently serve a
  differently-family target. `Animator._addr` is assigned once at `animator.py:147` and
  never reassigned anywhere in the module; `close()` clears `self._socket` but not the
  address. An `Animator`'s family is therefore fixed for its lifetime, and the scenario is
  reachable only by mutating a private attribute. It collapses into AC 2, the
  construction-time family assertion. Edge coverage is now 16 covered, 1 backstop,
  14 dismissed.

</spec_amendments>

<decisions>
## Implementation Decisions

### Address helper (IPV6-03)

- **D-01:** The single address-family implementation lives in a new
  `src/lifx/network/address.py`. Callers span layers, so `devices/base.py`, `api.py` and
  `animation/animator.py` will each import from `lifx.network.address`; that follows the
  existing `devices -> network` direction and does not invert it.
  **Reversibility:** costly, rationale: moving it later touches every call site plus its
  test module, though nothing outside the package imports it.

- **D-02:** The module exposes three small functions, each owning one rule:
  - `validate_address(ip) -> None`, raising `ValueError` for empty/`None`, malformed
    literals, zone-less IPv6 link-local, and IPv4-mapped IPv6
  - `family_for(ip) -> socket.AddressFamily`
  - `wildcard_for(ip) -> str`, returning `"::"` or `DEFAULT_IP_ADDRESS`, so
    `DeviceConnection._open()` contains no family test at all
  The three-function surface was chosen over a single `parse_address()` returning a record,
  and over one function that both raises and returns a family. Accepted cost: an address is
  parsed twice when a caller needs both validation and a family.

- **D-03:** **All** address rules move into `validate_address()`, not only the new ones.
  The loopback warning, the `is_unspecified` raise and the non-private warning currently
  inline in `Device.__init__` move too, so `Device.__init__` calls the validator and
  contains no address logic of its own. This is the fullest reading of IPV6-03's "exactly
  one implementation."
  **Reversibility:** costly, rationale: undoing it means re-inlining the checks and
  re-deriving the tests written for them.

- **D-04:** The `# pragma: no cover` markers on the moved validation branches come **off**,
  and every branch gets a unit test. They exist because the branches were awkward to reach
  through a `Device` constructor, not because they are unreachable; as pure functions they
  are trivially testable. Carrying them into a brand-new file would read as exactly the
  weakening `10-SPEC.md`'s third prohibition forbids. Planning must budget for this test
  writing, which is real work beyond the IPv6 change itself.

- **D-05:** The serial checks (all-zeros `000000000000`, broadcast `ffffffffffff`) do
  **not** move. `network/address.py` owns addresses only, matching its name. They stay in
  `Device.__init__` with their existing pragmas, and stay out of the patch diff.

- **D-06:** The moved loopback and non-private warnings log as the helper
  (`module: lifx.network.address, function: validate_address`) and drop today's
  `class: Device, method: __init__` context. These are operator-facing debug warnings, not
  API. Note that the `::1` fixture will trip the loopback warning on every IPv6 test, just
  as the existing `127.0.0.1` suite does today.

- **D-07:** `find_by_ip()` calls `validate_address(ip)` as its first statement, before any
  socket exists, so `fe80::1` raises well inside the 100 ms the SPEC asks for. A
  syntactically valid IPv6 literal still falls through to today's behaviour and returns
  `None` until Phase 12 wires the family-aware lookup. No `LifxUnsupportedCommandError`
  and no interim docstring note; the gap is Phase 12's.

- **D-08:** `Animator` derives its family with `family_for(self._addr[0])` and keeps its
  cache-on-first-frame behaviour. No per-frame family check is added; the hot path Phase 4
  tuned stays lean. The R5 send-time family assertion in `UdpTransport.send()` is the
  safety net. See A-03.

### `::1` emulator fixture (R7)

- **D-09:** Windows is out. See A-01.

- **D-10:** Prove IPv6 by asserting socket families, not by same-port coexistence. See
  A-02. A `get_free_port6()` helper (binding `("::1", 0)`) gives the IPv6 emulator its own
  port; `get_free_port()` binds `AF_INET` on `127.0.0.1` and cannot speak for an IPv6 port.

- **D-11:** The fixture is a second session-scoped emulator, `emulator_server_ipv6`,
  running its own `EmulatorRunner` on `::1`, mirroring `tile_chain_server`
  (`tests/conftest.py:241`). The existing `emulator_server` and its seven devices are
  untouched, so nothing that iterates that device list changes. Parameterising
  `emulator_server` over both families was rejected: it would roughly double the emulator
  suite's runtime on every CI job.

- **D-12:** The capability probe is a session-scoped `ipv6_available` bool fixture
  attempting `socket.socket(AF_INET6).bind(("::1", 0))` once and caching the result,
  mirroring `emulator_available` (`tests/conftest.py:130`). The `::1` emulator fixture
  calls `pytest.skip()` when it is False, so all dependent tests skip through one gate.

- **D-13:** The loopback warning firing on every `::1` test is left alone. It already fires
  for `127.0.0.1` across the whole existing emulator suite, it is genuinely useful in
  production where a LIFX device is never on loopback, and suppressing it would stop the
  tests exercising the code path the helper now owns.

- **D-14:** The IPv6 end-to-end tests cover exactly SPEC R1's list, on a single `Light`:
  connect, `get_color()`, `set_color()`, `set_power()`, plus an `Animator` frame delivery
  run with the `AF_INET6` family assertion. Every other device class shares the same
  connection path, so re-running them over IPv6 would test the same code twice.

### Universal-skip CI assertion (R7)

- **D-15:** The gate is a designated must-not-skip job, not cross-job aggregation. One CI
  job sets `LIFX_REQUIRE_IPV6=1`; the `ipv6_available` fixture reads it and raises instead
  of skipping when `::1` will not bind. Every other job stays skip-guarded. No artefact
  plumbing, no junit-xml parsing, no gate job. The failure is a single job going red with a
  message naming the cause.

- **D-16:** That job is **ubuntu with Python 3.10**. 3.10 is the LedFx floor and the
  version most exposed to stdlib differences in `ipaddress` scope-id handling and
  `create_datagram_endpoint` family inference. It is present in every matrix
  configuration, including the ubuntu-only path taken when no source file changed, so the
  gate is never absent. GitHub-hosted ubuntu runners have `::1`.

- **D-17:** `LIFX_REQUIRE_IPV6=1` guards the IPv6 probe **only**, not `emulator_available`.
  The variable means what its name says. A missing `lifx-emulator-core` is a declared dev
  dependency failure that breaks `uv sync` long before pytest runs.

### Rebase and PR shape (R8)

- **D-18:** One PR. Rebase the three commits onto `main`, then stack the audit fixes, the
  `network/address.py` consolidation, the `::1` fixture and the CI gate as further commits
  on the same branch. Codecov's patch status is computed over the whole PR diff, so the
  fixes' tests cover the rebased lines they touch, which a rebase-only PR could not manage
  alone. One CI cycle on the milestone's critical path.
  **Reversibility:** one-way, rationale: once merged, the commit series on `main` cannot be
  reshaped without a force-push to a published default branch.

- **D-19:** The branch's own tests are corrected **in the fix commits that change the
  behaviour**, not in a reconciliation commit after the rebase. The rebased commits land
  with their tests exactly as written, so the rebase is verifiably a pure replay. B2's
  WARNING-to-raise flip and B9's removal of the `":" in ip` heuristic each carry their test
  updates in the same commit. The rebase commits alone would fail if run in isolation,
  which no CI job does since only the PR head is tested.

- **D-20:** `backup/ipv6-thread-pre-rebase` is **not** refreshed. It currently sits at
  `af17071`, a single commit holding an older version of the branch's first commit, so it
  is not a backup of today's three-commit head at `2f884f5`. The reflog and the PR are
  sufficient recovery, and no commit on `main` since the `42c9ad2` divergence touches
  `src/lifx/network`, `src/lifx/animation` or `src/lifx/devices/base.py` (verified), so the
  rebase is expected to be clean. Note that `.planning/PROJECT.md:302` claims this ref
  "holds the pre-rebase state", which was true of an earlier state only.

- **D-21:** The Thread hardware UAT is produced by **extending
  `scripts/ipv6_thread_probe.py`**, which already drives the library's own primitives
  through records, ports and connect against real hardware. It gains control
  (`set_color`/`set_power`) and an optional streaming stage, and emits
  `10-UAT-RESULTS.json` with the device serial and timestamp. The script lands in this PR
  anyway; a second purpose-built harness would overlap it heavily.

- **D-22:** The UAT runs **against the PR head, after CI is green, before merge**, so it
  exercises the code actually about to land, including the consolidated helper and the B2
  raise. `10-UAT-RESULTS.json` is committed to the phase directory as the last commit
  before merge. Both Thread `MatrixLight`s (Test Candle, Test Tube, ULA prefix
  `fd00:1::`) are reachable, so `10-EXCEPTION-OVERRIDE.json` is not expected to be
  needed.

  *Corrected 2026-08-28 by plan 10-06.* The prefix in this decision is stale. The live
  Thread OMR prefix is `fd00:2::/64`; nothing answers on `fd00:1::`. The
  decision itself holds: both `MatrixLight`s are reachable and were reached, so the
  exception path was not taken. OMR prefixes are auto-generated and re-derive when the
  border router re-forms the mesh, so match on serial, never on prefix.

- **D-23:** The phase splits into four plans on the dependency chain:
  1. Rebase onto `main`, no behaviour change
  2. `network/address.py` plus the three socket-creation call sites and the three
     entry-point validations, covering B9, B2 and the D-03 consolidation with its tests
  3. The remaining fixes: B1 send-time family assertion, IPV6-04 socket-leak close,
     B4 docstrings
  4. `::1` fixture, IPv6 end-to-end tests, `LIFX_REQUIRE_IPV6` CI gate
  The UAT run and the merge close the phase outside the plans. The helper-before-fixes
  ordering is the part that would be expensive to get wrong.

### Claude's Discretion

- Whether the B1 family assertion is raised before or after the existing
  `is_open` / transport-liveness check in `UdpTransport.send()`, provided the SPEC's
  `error_received` contract for `EHOSTUNREACH` / `EHOSTDOWN` / `ENETUNREACH` stays intact
- Whether the `MdnsTransport.open()` leak fix uses `try/except` with an explicit
  `sock.close()` or a `contextlib.ExitStack`
- The exact wording of the corrected `network/mdns/transport.py` docstrings, subject to the
  AC that they contain none of "multicast group", "membership" or `IP_ADD_MEMBERSHIP`
- Whether `LIFX_REQUIRE_IPV6` is documented in `CLAUDE.md` alongside
  `LIFX_EMULATOR_EXTERNAL`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements

- `.planning/phases/10-land-the-ipv6-thread-branch/10-SPEC.md` — locked requirements,
  boundaries, acceptance criteria, edge coverage and prohibitions. MUST read before
  planning. Carries the three amendments recorded above, already applied in place

### Milestone context

- `.planning/PROJECT.md` — v2.0 milestone scope, constraints, and the Key Decisions table.
  Note `PROJECT.md:299-302` on the three branch commits and the stale backup ref
- `.planning/REQUIREMENTS.md` — authoritative REQ-IDs; IPV6-01..04 are this phase's
- `.planning/ROADMAP.md` — Phase 10 goal, success criteria, and the execution notes
  establishing Phase 10 as the milestone's critical path

### Research inputs

- `.planning/research/PITFALLS.md` — the B1..B9 branch-audit findings this phase reconciles
- `.planning/research/ARCHITECTURE.md` — the address-family seam judged correct by the v2.0
  research pass
- `.planning/research/STACK.md` — Python 3.10 floor, `asyncio.TaskGroup` unavailability
- `.claude/skills/spike-findings-lifx-async/SKILL.md` — v1.1 reliability blueprints; the
  constants this phase must not retune

### Repository conventions

- `CLAUDE.md` — architecture, testing strategy, the UDP endpoint-death versus peer-error
  rule in `network/transport.py`, and the emulator fixture conventions
- `codecov.yml` — `patch.default.target: 100%` with no `flags:` key, so the status is
  computed against the merged report across all five Python flags; branch partials count
- `.github/workflows/ci.yml` — the `os x python-version` matrix the `LIFX_REQUIRE_IPV6`
  job is added to

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/lifx/geometry.py` and `src/lifx/theme/slug.py` — the project's established pattern
  for a leaf module owning exactly one rule so two call sites cannot drift apart. The
  precedent the address helper follows, though it lands under `network/` rather than at top
  level (D-01)
- `src/lifx/network/utils.py` — existing cross-cutting network helpers (`allocate_source()`,
  `IdleDeadline`). Considered as the helper's home and not chosen
- `tests/conftest.py:241` `tile_chain_server` — a second session-scoped emulator on its own
  port, the exact shape `emulator_server_ipv6` copies (D-11)
- `tests/conftest.py:130` `emulator_available` — the session-scoped bool probe fixture
  `ipv6_available` mirrors (D-12)
- `tests/conftest.py:83` `get_free_port()` — binds `AF_INET` on `127.0.0.1`; needs an IPv6
  sibling (D-10)
- `scripts/ipv6_thread_probe.py` (on the branch, commit `b88cdb9`) — a three-stage
  records/ports/connect hardware probe already driving the library's own primitives, which
  becomes the UAT harness (D-21)

### Established Patterns

- **Structured dict logging.** Every warning in `devices/base.py` logs a dict with `class`
  and `method` keys. The moved warnings change that shape (D-06)
- **`# pragma: no cover` on construction-time validation.** `devices/base.py` carries these
  on the serial and address checks; D-04 removes them from the address ones and D-05 leaves
  the serial ones alone
- **100% branch patch coverage.** `codecov.yml` sets `patch.default.target: 100%` with no
  `flags:` key, so it is computed on the merged report. Branch partials count, not only
  uncovered lines. This is what makes D-18's single-PR shape the right one
- **Emulator tests skip on `win32`** (`tests/conftest.py:148`), which is what forced A-01

### Integration Points

Three socket-creation sites lose their inline `":" in ip` heuristic:

- `src/lifx/network/transport.py:295` (on the branch) — `UdpTransport.open()` derives
  `family` from the **bind** address; calls `family_for()`
- `src/lifx/network/connection.py:234` (on the branch) — `DeviceConnection._open()` derives
  a **bind literal** from the device's target address; calls `wildcard_for()`
- `src/lifx/animation/animator.py:399` (on the branch) — the direct-UDP frame socket
  derives `family` from the **target**; calls `family_for()`

Three entry points gain `validate_address()`:

- `src/lifx/devices/base.py` `Device.__init__` — replaces the whole inline address
  validation block, roughly lines 485 to 535 on the branch
- `src/lifx/devices/base.py:596` `Device.from_ip()`
- `src/lifx/api.py:906` `find_by_ip()` — first statement (D-07)

Rebase surface: 11 files, +1131/-330, diverged at `42c9ad2` (6.5.1). No commit on `main`
since that point touches `src/lifx/network`, `src/lifx/animation` or
`src/lifx/devices/base.py`, so the rebase is expected to be clean (verified 2026-08-27).

</code_context>

<specifics>
## Specific Ideas

- The user corrected a serial written MAC-style during the discussion: serials are handled
  as 12-digit hex strings, so the broadcast serial is `ffffffffffff`, not colon-separated
- Two questions during the discussion challenged SPEC criteria that turned out to rest on
  facts that do not hold ("How could a family change on an existing cached socket?" and
  "Why does it want this?" of AC 16). Both produced amendments A-02 and A-03. Downstream
  agents should treat the remaining SPEC criteria as verified against the code, since these
  two were the ones that failed that check

</specifics>

<deferred>
## Deferred Ideas

- **`.planning/PROJECT.md:302` is stale** about `backup/ipv6-thread-pre-rebase` holding the
  pre-rebase state. Worth correcting at the next phase transition or milestone update, not
  in this phase's diff
- **Reopening the `win32` emulator gate** (`tests/conftest.py:148`). Considered and
  rejected for this phase as an unrelated scope increase on the critical path. If Windows
  emulator coverage is wanted, it belongs in its own task with its own flakiness
  measurement
- **Consolidating the serial validation** in `Device.__init__` and removing its
  `# pragma: no cover` markers. Explicitly left out by D-05; no phase claims it

</deferred>

---

*Phase: 10-land-the-ipv6-thread-branch*
*Context gathered: 2026-08-27*

---

## D-24: Never push to the `redding1` remote (operator directive, 2026-08-27)

**Locked by the operator during Phase 10 execution, after plan 10-01 landed.**

`feat/ipv6-thread-support` was originally fetched from `redding1`
(`git@github.com:redding1/lifx-async`), the fork that authored `b49400b`. Its branch config
still tracked that fork:

```
branch.feat/ipv6-thread-support.remote      redding1
branch.feat/ipv6-thread-support.pushremote  git@github.com:redding1/lifx-async.git
```

so a bare `git push` would have targeted redding1. The orchestrator set
`branch.feat/ipv6-thread-support.pushRemote = origin` and removed the redding1 pushremote.
Fetch-tracking is deliberately left pointing at redding1; only pushes are redirected.

**Rule for every remaining plan, 10-06 in particular:**

- Push ONLY to `origin` (`git@github.com:Djelibeybi/lifx-async.git`), and always name the
  remote explicitly: `git push --force-with-lease origin feat/ipv6-thread-support`,
  `git push origin main`.
- NEVER run `git push redding1 ...`, never re-point `pushRemote` back at redding1, and never
  run a bare `git push` that relies on tracking config to choose a remote.
- If any step appears to require a redding1 push, STOP and report it as a
  `checkpoint:decision` with gate `blocking-human`. Do not improvise.

This does not change the rebase-derived force-push requirement itself: the series is
SHA-rewritten, so `origin/feat/ipv6-thread-support` still needs `--force-with-lease`
(D-20 remains the recovery path). Only the destination is constrained.

## D-25: The series was squashed to two commits (operator directive, 2026-08-28)

**Locked by the operator after CI went green on the PR head, before the merge gate was lifted.**

`feat/ipv6-thread-support` carried 50 commits: redding1's `79a5ce0`, the two other replayed
code commits, and 47 planning, fix and hygiene commits stacked above them by plans 10-01 to
10-05. The operator directed that everything above redding1's commit be squashed into a single
feature commit describing only the delivered behaviour.

Result, verified before and after:

| Property | State |
|---|---|
| `git diff backup/pre-squash HEAD` | empty — trees identical, only history collapsed |
| `79a5ce09b71ea076d1065953aee72609e154fa0a` | byte-identical, unmodified, still the base |
| Signatures | both commits `git verify-commit` exit 0 under key `66D6066620F03B05` |
| DCO | `Signed-off-by: redding1` on `79a5ce0`, `Signed-off-by: Avi Miller <me@dje.li>` on the squashed commit |
| Authorship | redding1 additionally credited by `Co-Authored-By` on the squashed commit |
| Recovery ref | `backup/pre-squash` = `619bf6d` |

**Consequence for the acceptance criteria.** SPEC AC 17 and the matching 10-06 checks were
written as "all three replayed commits", which the squash makes unsatisfiable as literal text:
only one of the three survives as a distinct commit. The *intent* behind that criterion was
never the commit count — it was that the merge preserve signatures, DCO sign-off and redding1's
authorship, none of which the squash weakened. AC 17 and 10-06's Task 1 and Task 4 checks are
therefore amended to assert that intent directly:

- every commit the merge adds to `main` verifies and carries a `Signed-off-by` trailer;
- `79a5ce0` is present unmodified and is the oldest commit in `main..HEAD`;
- redding1 is credited by `Co-Authored-By` on the squashed commit.

This is not a weakened check. The former criterion could pass with a signature-preserving
rebase that silently dropped a trailer on a stacked commit; the amended one cannot.

**Plan 10-01's "three oldest commits" criterion is deliberately NOT amended.** It was true when
10-01 executed and its SUMMARY records the proof. Rewriting a completed plan's acceptance
record to match a later decision would falsify the history the record exists to preserve.

**Consequence for the UAT gate.** `10-UAT-RESULTS.json` pinned `library_head: 1903c775...`, a SHA
the squash removed from the branch. **Resolved 2026-08-28:** the hardware UAT was re-run against
the squashed commit on Thread Tube `d073d5e00002` (product 217, firmware 4.200, IPv6-only, no A record) and
passed: connect and control both `passed`, `restored: true`, streaming `not_run`. The 10-06 Task 2
validator passes against the fresh record, `library_head` included.

## D-26: Phase 10 remains off main until shipment (operator directive, 2026-08-28)

The former SPEC made ancestry on `main` an in-phase acceptance gate. That reverses the required
order: Phase 10 must first pass and ship from its phase branch, after which the shipment workflow
may merge the exact accepted tree to `main`. Verification MUST treat premature `main` ancestry as
a SPEC violation, not treat branch-only delivery as a gap.

## D-27: Patch coverage is non-functional evidence (operator directive, 2026-08-28)

Patch coverage remains recorded and `codecov.yml` remains unchanged, but coverage does not alter
runtime functionality. It is advisory for Phase 10 and may be explicitly overridden by the
operator if the release workflow would otherwise block. No override is fabricated merely because
the checker is imperfect.

## D-28: Transport lifecycle races are blocking defects (operator directive, 2026-08-28)

The successful-open/close race, partial-state publication and `DeviceConnection.open()` waiter
failure path MUST be fixed with deterministic regressions before Phase 10 can pass.

## D-29: UAT restoration is best-effort (operator directive, 2026-08-28)

Restoring device state after UAT is nice-to-have operator hygiene. Capture and restoration results
may remain in the artefact, but restoration success is not a functional, UAT or phase-completion
gate. The recorded hardware result is not rewritten.
