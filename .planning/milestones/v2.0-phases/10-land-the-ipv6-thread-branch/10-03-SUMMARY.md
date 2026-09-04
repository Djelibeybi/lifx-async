---
phase: 10-land-the-ipv6-thread-branch
plan: 03
subsystem: network
tags: [ipv6, transport, mdns, error-handling, coverage, thread]

requires:
  - phase: 10-01
    provides: "the rebased mDNS rewrite (_LifxRecordCache, _pick_address, PTR retransmission, follow-up A/AAAA queries, build_address_query) whose coverage debt this plan pays, and 10-COVERAGE-GAPS.md naming the gaps"
  - phase: 10-02
    provides: "lifx.network.address.family_for(), the shared rule the B1 send-time assertion consumes rather than re-deriving"
provides:
  - "a send-time address-family assertion in UdpTransport.send(), so a family mismatch fails typed in microseconds instead of being swallowed as a gaierror and surfacing as a 16 second timeout"
  - "a socket family recorded at open() time on UdpTransport, cleared alongside _transport and _protocol"
  - "a leak-safe and state-clearing MdnsTransport.open() failure path, so a partway-failed open strands no descriptor and leaves a transport that can still be opened"
  - "the SPEC R4 held-out concurrency backstop: concurrent open() calls and close() racing a failing open(), both deterministic and both counting descriptors"
  - "mdns/transport.py docstrings that describe the ephemeral-port RFC 6762 section 6.7 behaviour the code actually has"
  - "lifx.network.mdns at 100% line and 100% branch coverage with zero partial branches"
affects: [10-04, 10-05, 10-06, 11, 12, 14]

actuals:
  tokens: 39911
  tasks: 4
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Pre-send guard, not error reclassification: an address-shaped error is caught before the datagram is handed to asyncio, leaving the swallow-all error_received contract untouched"
    - "Failure paths reset the same field set their close() does, so is_open never lies after a partway-failed open"
    - "Leak tests instrument a real socket rather than a MagicMock, because a mock owns no descriptor and so can never emit the ResourceWarning that proves one was released"

key-files:
  created:
    - .planning/phases/10-land-the-ipv6-thread-branch/deferred-items.md
  modified:
    - src/lifx/network/transport.py
    - src/lifx/network/mdns/transport.py
    - tests/test_network/test_transport.py
    - tests/test_network/test_mdns/test_transport.py
    - tests/test_network/test_mdns/test_discovery.py
    - tests/test_network/test_mdns/test_dns.py
    - .planning/phases/10-land-the-ipv6-thread-branch/10-COVERAGE-GAPS.md

key-decisions:
  - "The family assertion is placed after the existing transport-liveness check, not before it, so a dead endpoint still reports 'Socket not open' rather than being described by its stale family. CONTEXT lists the placement as Claude's discretion; this ordering is what makes the R5 concurrency edge (send after _endpoint_lost) raise the typed error instead of dereferencing what open() left behind"
  - "The socket family is recorded at open() time as self._family rather than read back per datagram via get_extra_info('socket'). Cheaper on the hot path, and None-safe: close() and _endpoint_lost() clear it with _transport and _protocol so the three fields never disagree"
  - "family_for()'s ValueError is allowed to propagate unchanged from send() rather than being wrapped as LifxNetworkError. Both call sites reach send() through a validated device address or an internal broadcast literal, so an unparsable destination is a programming error, not a network condition"
  - "The MdnsTransport failure path clears _socket, _protocol and _transport together rather than only closing the descriptor (review finding 7). Closing alone would have left is_open reporting True and open()'s early return refusing to rebuild, producing a transport that was descriptor-clean and permanently unusable"
  - "No _is_opening guard was added to MdnsTransport.open(). The concurrency backstop was written first and passed against the unfixed code: there is no await between the already-open check and the _protocol assignment, so the early return is atomic in practice. The test is kept as a regression pin against a future refactor that moves the assignment past the await, per the plan's 'fix it minimally' instruction"
  - "The B1 misattribution correction was committed separately from Task 4, whose acceptance criteria require its diff to list only files under tests/"
  - "10-COVERAGE-GAPS.md was corrected but NOT annotated as closed. It is the independent checklist plan 10-06 verifies against, and marking it done here would invite a rubber-stamp; the closure evidence lives in this summary instead"

patterns-established:
  - "A guard that could be mistaken for error-handling states in its own docstring which error paths it does not touch, and ships a parameterised regression test pinning them"
  - "Descriptor-leak tests assert created equals closed plus still-live, from a ledger that drops its reference on close, so a leaked socket is both counted and collectable"

requirements-completed: [IPV6-01, IPV6-04]

coverage:
  - id: D1
    description: "UdpTransport.send() raises LifxNetworkError in under 100 ms when the destination's address family does not match the socket's, in both directions of the mismatch, naming both families"
    requirement: IPV6-01
    verification:
      - kind: unit
        ref: "tests/test_network/test_transport.py::TestSendFamilyAssertion::test_ipv6_destination_on_an_ipv4_socket_raises_immediately"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_transport.py::TestSendFamilyAssertion::test_ipv4_destination_on_an_ipv6_socket_raises_immediately"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_transport.py::TestSendFamilyAssertion (matching IPv4, matching IPv6 and IPv4-broadcast happy paths still reach sendto)"
        status: pass
    human_judgment: false
  - id: D2
    description: "EHOSTUNREACH, EHOSTDOWN and ENETUNREACH from a peer still route to error_received, still do not raise from send(), and still leave the endpoint open; send() after endpoint death raises the typed error rather than an AttributeError"
    requirement: IPV6-01
    verification:
      - kind: unit
        ref: "tests/test_network/test_transport.py::TestSendFamilyAssertion::test_peer_errors_are_still_swallowed_after_a_send (parameterised over all three errnos)"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_transport.py::TestSendFamilyAssertion::test_send_on_a_dead_endpoint_raises_the_typed_error"
        status: pass
      - kind: other
        ref: "git diff shows no change to error_received, _FATAL_SOCKET_ERRNOS or _endpoint_lost beyond a docstring cross-reference"
        status: pass
    human_judgment: false
  - id: D3
    description: "MdnsTransport.open() closes its socket and clears _socket, _protocol and _transport when bind(), the post-bind setsockopt() or create_datagram_endpoint() raises, emits no ResourceWarning, and leaves a transport a caller's retry loop can still open"
    requirement: IPV6-04
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_transport.py::TestMdnsTransportOpenFailureIsClean::test_failed_open_closes_its_socket_and_resets_state (parameterised over bind, setsockopt, endpoint)"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_mdns/test_transport.py::TestMdnsTransportOpenFailureIsClean::test_transport_is_reusable_after_a_failed_open (parameterised over the same three)"
        status: pass
      - kind: other
        ref: "uv run --frozen pytest tests/test_network/test_mdns/test_transport.py -q -W error::ResourceWarning (28 passed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The SPEC R4 held-out concurrency backstop: concurrent open() calls build exactly one endpoint, and close() racing a failing open() strands no descriptor, both interleavings made deterministic with an asyncio.Event and asserted by counting descriptors"
    requirement: IPV6-04
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_transport.py::TestMdnsTransportOpenConcurrency::test_concurrent_opens_build_exactly_one_endpoint"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_mdns/test_transport.py::TestMdnsTransportOpenConcurrency::test_close_racing_a_failing_open_strands_nothing"
        status: pass
    human_judgment: false
  - id: D5
    description: "network/mdns/transport.py's module, class and open() docstrings describe the actual ephemeral-port RFC 6762 section 6.7 legacy-unicast behaviour and contain none of 'multicast group', 'membership' or 'IP_ADD_MEMBERSHIP'"
    requirement: IPV6-04
    verification:
      - kind: other
        ref: "uv run python -c \"import lifx.network.mdns.transport as m; d=(m.__doc__ or '')+(m.MdnsTransport.__doc__ or ''); assert not [b for b in ['multicast group','membership','IP_ADD_MEMBERSHIP'] if b in d]; assert '6.7' in d and 'ephemeral' in d.lower()\""
        status: pass
      - kind: other
        ref: "grep -n 'multicast group\\|membership\\|IP_ADD_MEMBERSHIP' src/lifx/network/mdns/transport.py returns nothing (whole file, not just the two docstrings)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every gap 10-COVERAGE-GAPS.md assigns to plan 10-03 is closed by a test: lifx.network.mdns reports 100% line and 100% branch coverage with zero partial branches, with no pragma marker added, no test skipped and no coverage target changed"
    requirement: IPV6-04
    verification:
      - kind: other
        ref: "uv run --frozen pytest tests/test_network -o addopts='' --cov=lifx.network.mdns --cov-branch --cov-report=term-missing (441 stmts, 140 branches, 0 miss, 0 partial, 100%)"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py::TestLifxRecordCacheBounds, ::TestLifxRecordCachePendingTargets, ::TestMdnsQueryRetransmission, ::TestMdnsFollowUpAddressQueries, ::TestMdnsSerialDeduplication"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_mdns/test_dns.py::TestBuildAddressQuery"
        status: pass
      - kind: other
        ref: "git diff main HEAD --name-only -- pyproject.toml codecov.yml is empty; git diff carries no added 'pragma: no cover'"
        status: pass
    human_judgment: false
  - id: D7
    description: "10-COVERAGE-GAPS.md no longer attributes the B1 send-time family assertion to plan 10-02, so plan 10-06 does not read it as already delivered"
    verification:
      - kind: other
        ref: "grep -n 'plan 10-02 also adds the B1' .planning/phases/10-land-the-ipv6-thread-branch/10-COVERAGE-GAPS.md returns nothing; the paragraph now names plan 10-03 and carries a dated correction note"
        status: pass
    human_judgment: false

duration: 36min
completed: 2026-08-27
status: complete
---

# Phase 10 Plan 03: Remaining Branch-Audit Fixes Summary

**A send-time address-family assertion that turns a swallowed `gaierror` timeout into a typed sub-millisecond failure, a leak-safe and reopenable `MdnsTransport.open()`, honest mDNS docstrings, and `lifx.network.mdns` taken to 100% branch coverage with zero partials**

## Performance

- **Duration:** 36 min
- **Started:** 2026-08-27T12:14:00Z (approximate; first commit 12:33:11Z)
- **Completed:** 2026-08-27T12:50:35Z
- **Tasks:** 4
- **Files modified:** 7 (2 source, 4 test, 1 planning doc) plus 1 planning doc created

## Accomplishments

- **B1 (SPEC R5, AC 10).** `UdpTransport.send()` now compares the destination's address family against the socket's before handing the datagram to asyncio, and raises `LifxNetworkError` naming both. Previously an IPv6 literal on an `AF_INET` socket raised `socket.gaierror`, an `OSError` subclass that `_UdpProtocol.error_received` swallows by design, so a permanent configuration error was indistinguishable from a sleeping device and cost the caller the full retry schedule.
- **AC 11 pinned, not broken.** The guard is a pre-send check only. `error_received`, `_FATAL_SOCKET_ERRNOS` and `_endpoint_lost` are untouched, and a new parameterised test asserts `EHOSTUNREACH`, `EHOSTDOWN` and `ENETUNREACH` are still swallowed after a real send with the endpoint left open. This was the highest-severity threat in the plan's register (T-10-09).
- **IPV6-04 (AC 9), both halves.** A partway-failed `MdnsTransport.open()` now closes its socket *and* clears `_socket`, `_protocol` and `_transport` together. The state reset is what review finding 7 caught: closing the descriptor alone would have left `is_open` reporting True and `open()`'s early return refusing to rebuild, giving a transport that was descriptor-clean and permanently dead.
- **SPEC R4 backstop landed.** Concurrent `open()` calls build exactly one endpoint, and `close()` racing a failing `open()` strands nothing. Both interleavings are driven by an `asyncio.Event` rather than by timing, and both assert created sockets equal closed plus still-live rather than merely asserting no exception.
- **B4 (AC 12).** All three stale claims about joining the mDNS group are gone, from the module, class and `open()` docstrings, replaced by the ephemeral-port RFC 6762 section 6.7 rationale that was previously visible only in an inline comment.
- **Coverage debt paid in Wave 3, not against the merge deadline.** `lifx.network.mdns` is at 100% line and 100% branch coverage, zero partial branches, across all four modules. Plan 10-06 Task 1 now verifies a closed list rather than discovering an open one (review finding 3).

## Task Commits

Each task was committed atomically, GPG-signed with key `27B3A9EA...20F03B05` and DCO signed off:

1. **Task 1: B1 send-time family assertion** - `5dc49ae` (feat)
2. **Task 2: IPV6-04 leak fix plus the R4 backstop** - `c3a843b` (fix)
3. **Task 3: B4 honest docstrings** - `4b77b9f` (docs)
4. **Task 4: mDNS branch-coverage debt** - `451ea89` (test)
5. **Gap-list misattribution correction** - `e691ba0` (docs)

Nothing was pushed. Operator directive D-24 is not implicated: no `git push` was run at all.

## Files Created/Modified

- `src/lifx/network/transport.py` - Records the socket family at `open()`; `send()` rejects a mismatched destination; `close()` and `_endpoint_lost()` clear the family with the other two references
- `src/lifx/network/mdns/transport.py` - `open()`'s failure path closes its socket and performs `close()`'s three-field reset; module, class and `open()` docstrings rewritten to match the code
- `tests/test_network/test_transport.py` - `TestSendFamilyAssertion`: both mismatch directions with sub-100 ms timing bounds, three happy paths, the parameterised peer-error regression, and the dead-endpoint typed raise
- `tests/test_network/test_mdns/test_transport.py` - `_SocketLedger` and `_RecordingSocket` instrumentation over a real socket, the three forced-failure cases and their reopen assertions, and the two concurrency interleavings
- `tests/test_network/test_mdns/test_discovery.py` - Cache bounds from both sides, all four `pending_targets()` outcomes, the PTR retransmission slots on a faked clock, the follow-up query loop and its 64-target cap, and the serial dedupe
- `tests/test_network/test_mdns/test_dns.py` - `TestBuildAddressQuery`, round-tripped through `parse_name` including a 63-byte label
- `.planning/phases/10-land-the-ipv6-thread-branch/10-COVERAGE-GAPS.md` - B1 attribution corrected from plan 10-02 to plan 10-03
- `.planning/phases/10-land-the-ipv6-thread-branch/deferred-items.md` - New; records the one out-of-scope defect found

## Decisions Made

See `key-decisions` in the frontmatter. The two that most affect later plans:

**The family assertion sits after the liveness check.** CONTEXT lists the placement as Claude's discretion. Putting it second is what makes the R5 concurrency edge behave: a `send()` after `_endpoint_lost` reports `"Socket not open"` rather than being described in terms of a family that no longer has a socket. `self._family` is cleared alongside `_transport` and `_protocol` for the same reason, so the three can never disagree about whether the transport is alive.

**No `_is_opening` guard was added to `MdnsTransport`.** The plan allowed one if the backstop exposed a real interleaving. Written first, the concurrent-open test passed against the unfixed code: there is no `await` between the already-open check and the `_protocol` assignment, so the early return is atomic in practice. Adding a poll-loop guard would have been unjustified restructuring. The test stays as a regression pin against any future refactor that moves that assignment past the await, which is exactly the change that would reintroduce the race.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] An existing test hand-assembled a transport state the new guard rejects**

- **Found during:** Task 1
- **Issue:** `test_send_oserror_raises_network_error` builds `UdpTransport` internals directly (`transport._protocol`, `transport._transport`) without calling `open()`. Once `send()` required a recorded socket family, that fixture's send was rejected as `"Socket not open"` before it could reach `sendto`, so the test no longer exercised the OSError path it exists for.
- **Fix:** The fixture now also records `transport._family = socket.AF_INET`, exactly as `open()` would, with a comment saying why. No assertion was relaxed and the test still proves the same thing.
- **Files modified:** `tests/test_network/test_transport.py`
- **Verification:** The test passes and still fails if the `Failed to send data` wrap is removed
- **Committed in:** `5dc49ae` (Task 1 commit)

**2. [Rule 2 - Missing Critical] A third stale docstring in the B4 file**

- **Found during:** Task 3
- **Issue:** SPEC R6 and the task's verify command name only the module and class docstrings, but `open()`'s docstring also said it "joins the mDNS multicast group" and was headed "Open the mDNS socket with multicast configuration". Leaving it would have satisfied the acceptance check while leaving the file still lying about its behaviour, which is the defect B4 exists to remove.
- **Fix:** Rewritten alongside the other two. The banned-literal sweep now passes over the whole file, not just the two docstrings the AC checks.
- **Files modified:** `src/lifx/network/mdns/transport.py`
- **Verification:** `grep -n 'multicast group\|membership\|IP_ADD_MEMBERSHIP' src/lifx/network/mdns/transport.py` returns nothing
- **Committed in:** `4b77b9f` (Task 3 commit)

**3. [Rule 2 - Missing Critical] Em dash in the same file's comment**

- **Found during:** Task 3
- **Issue:** A pre-existing comment carried an em dash, against the project's standing prose rule. It sat in the file whose prose Task 3 exists to correct.
- **Fix:** Recast rather than substituted, keeping the commit docstring-and-comment-only as the AC requires.
- **Files modified:** `src/lifx/network/mdns/transport.py`
- **Verification:** No em dash remains in the file
- **Committed in:** `4b77b9f` (Task 3 commit)

**4. [Rule 3 - Blocking] The B1 misattribution needed its own commit**

- **Found during:** Task 4
- **Issue:** The dispatch brief required correcting the `10-COVERAGE-GAPS.md` line attributing B1 to plan 10-02, but Task 4's acceptance criteria require its diff to list only files under `tests/`.
- **Fix:** Landed as a separate `docs(10-03)` commit after Task 4, together with the new `deferred-items.md`.
- **Files modified:** `.planning/phases/10-land-the-ipv6-thread-branch/10-COVERAGE-GAPS.md`, `deferred-items.md`
- **Verification:** `git diff 451ea89~1 451ea89 --name-only` lists only `tests/` paths
- **Committed in:** `e691ba0`

---

**Total deviations:** 4 auto-fixed (1 bug, 2 missing critical, 1 blocking)
**Impact on plan:** All four were necessary for correctness or for satisfying two acceptance criteria that pull in opposite directions. No scope creep: every change stayed inside the files the plan already names, and no behaviour beyond Tasks 1 to 3 was added.

## Deferred Issues

One out-of-scope defect was found and deliberately not fixed, recorded in `deferred-items.md`:

- **`src/lifx/network/mdns/dns.py:367`** carries an em dash in `build_address_query()`'s docstring, arriving with the rebased branch. Task 4 is explicitly a test-only commit ("that is a finding, not a licence"), and B4's docstring scope is `network/mdns/transport.py` alone, so it belongs to neither. Suggested owner: Phase 11's mDNS documentation pass (MDNS-08).

## Known Stubs

None. No hardcoded empty value, placeholder or unwired data source was introduced. No `# pragma: no cover` was added, no test was deleted, skipped or weakened, and no coverage target was changed.

## Unreachable Coverage Gaps

None. Every gap `10-COVERAGE-GAPS.md` assigns to plan 10-03 turned out to be reachable from a test, so nothing is recorded here as unreachable and nothing is annotated in the source.

## Threat Flags

None. The plan's register was addressed rather than extended:

| Threat | Disposition | Where mitigated |
|--------|-------------|-----------------|
| T-10-07 (family mismatch stalls the retry schedule) | mitigated | Task 1, `5dc49ae` |
| T-10-08 (descriptor leak on failed mDNS open) | mitigated | Task 2, `c3a843b` |
| T-10-20 (failed open leaves `is_open` lying) | mitigated | Task 2, `c3a843b` |
| T-10-09 (over-eager assertion converting peer storms into raises) | mitigated | Task 1's parameterised regression test, `5dc49ae` |
| T-10-SC (package installs) | accepted | No package installed; `dependencies = []` unchanged |

No new network endpoint, auth path, file-access pattern or schema at a trust boundary was introduced.

## Issues Encountered

**The ResourceWarning assertion nearly could not fire.** A failed `open()` chains its `OSError` into the `LifxNetworkError`, and that traceback pins `open()`'s frame, which holds the socket the frame created. With `pytest.raises` holding the exception, the socket can never be collected and so can never warn, making the check silently vacuous. The tests clear `__traceback__`, `__cause__` and `__context__` and drop the `ExceptionInfo` before collecting. Confirmed genuine by observing the RED run emit `ResourceWarning: unclosed _RecordingSocket` against the unfixed code.

**A MagicMock socket cannot prove a descriptor was released.** The existing leak-adjacent tests use `MagicMock(spec=socket.socket)`, which owns no file descriptor, so any ResourceWarning assertion over it passes regardless. The new failure tests instrument a real `socket.socket` subclass; the reopen half still uses a mock, where the question is about state and a real descriptor would only be litter.

## TDD Notes

Tasks 1 and 2 carry `tdd="true"` and each landed as a single commit rather than a RED/GREEN pair, matching the precedent plan 10-02 set. The RED state was established and observed first in both cases (Task 1: exactly the two mismatch tests failed, with the peer-error and dead-endpoint pins already green, proving they were regression pins and not new behaviour. Task 2: five of the new tests failed, including the ResourceWarning). D-19 requires the behaviour change and its tests in one commit, and each task's own `<done>` asks for the same, so splitting them would have left a red commit in a bisectable history.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for plan 10-04** (the `::1` emulator fixture, IPv6 end-to-end tests and the `LIFX_REQUIRE_IPV6` CI gate).

- The branch is `feat/ipv6-thread-support`, which plan 10-04's precondition requires; `gsd/phase-10-land-the-ipv6-thread-branch` no longer points at the same commit and will need updating if anything depends on that.
- SPEC AC 9, 10, 11 and 12 all pass. AC 8 is not regressed: `grep -rn '":" in ' src/lifx/` still returns nothing.
- All four branch-audit fixes in this phase's scope (B1, B2, B4, B9) plus IPV6-04 are now landed across plans 10-02 and 10-03.
- Full suite: 3613 passed, 12 deselected, under `-W error::ResourceWarning`. `ruff format`, `ruff check` and `pyright` all clean.
- **For plan 10-06:** `10-COVERAGE-GAPS.md` is deliberately left un-annotated so it remains an independent checklist. The gaps it assigns to plan 10-03 are closed; re-verify with `uv run --frozen pytest tests/test_network -o addopts='' --cov=lifx.network.mdns --cov-branch --cov-report=term-missing`, which should report 0 missing and 0 partial. Plan 10-05 still owns the `scripts/ipv6_thread_probe.py` measurement decision, and plan 10-02's `devices/base.py` gaps closed by deletion rather than by a retrofit test.
- **One concern, not a blocker:** the mDNS coverage measured here is scoped to `tests/test_network`. The Codecov patch status is computed against the merged report across all five Python flags, so plan 10-06 should confirm on the merged CI report and not on this local scoped run alone.

---
*Phase: 10-land-the-ipv6-thread-branch*
*Completed: 2026-08-27*

## Self-Check: PASSED

Verified after writing this summary:

- Both created files exist on disk (`deferred-items.md`, `10-03-SUMMARY.md`)
- All seven modified files exist on disk
- All five commit hashes resolve in `git log --oneline --all`
- `git diff 451ea89~1 451ea89 --name-only` lists only the two `tests/` paths, as Task 4's acceptance criteria require
