---
phase: 10-land-the-ipv6-thread-branch
plan: 04
subsystem: testing
tags: [ipv6, emulator, fixtures, ci, e2e, animator, pytest]

requires:
  - phase: 10-01
    provides: "the rebased address-family seam in the working tree, so a device, a connection and an animator can all follow an IPv6 target, and the tracer transcript this suite is the permanent form of"
  - phase: 10-02
    provides: "lifx.network.address, so `::1` reaches family_for()/wildcard_for() through the one shared rule rather than three inline heuristics"
  - phase: 10-03
    provides: "the send-time family assertion in UdpTransport.send(), which means a mismatched destination on these sockets fails typed rather than timing out"
provides:
  - "a second session-scoped emulator bound to ::1, with IPV6_V6ONLY set before bind and read back after"
  - "tests/test_api/test_ipv6_e2e.py: connect, get_color, set_color, set_power and an Animator frame run, each asserting the address family of the socket the call actually used"
  - "frame delivery proven by an emulated-device state readback rather than by send-side statistics"
  - "ipv6_available, the single capability gate every ::1 fixture skips through"
  - "LIFX_REQUIRE_IPV6, and the designated must-not-skip CI cell (ubuntu, Python 3.10) that sets it"
affects: [10-05, 10-06, 12, 13, 14]

actuals:
  tokens: 5036
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Capability gate as a session-scoped bool fixture, with the skip-or-fail decision extracted into a pure function so both non-happy arms are testable without arranging the failure"
    - "A test-only server subclass that owns socket creation, used where a socket option is only settable before a bind the library under test performs internally"
    - "Every transport-family test reads the family off the real socket, never off the recorded configuration value"

key-files:
  created:
    - tests/test_api/test_ipv6_e2e.py
  modified:
    - tests/conftest.py
    - .github/workflows/ci.yml
    - CLAUDE.md

key-decisions:
  - "The ::1 emulator hosts a matrix-capable Tile rather than a plain colour light, while the library-side object under test stays a plain Light. The emulator's Set64Handler returns early for a device without matrix capability, so against a plain colour light the animation test could only ever have proven that a datagram was sent"
  - "IPV6_V6ONLY is set inside a test-only EmulatedLifxServer subclass that owns socket creation, and only read back in the fixture. Setting it after a bind raises EINVAL on macOS, and the stock start() binds internally via local_addr"
  - "emulator_server_ipv6 yields (port, server) rather than the port alone, mirroring emulator_server, because proving frame arrival needs server-side state and no observation of arrival is possible from the client"
  - "The must-not-skip CI gate is a conditional env var on the existing pytest step, not a new job: no artefact plumbing, no junit parsing, one cell going red with a message naming the cause"
  - "The delivery assertion was validated as non-vacuous by pointing the animator one port off and observing the test fail, rather than trusting that a passing assertion means the frame landed"

patterns-established:
  - "Write targets are derived from a pre-write reading, never hardcoded, so an assertion cannot pass on state the device already held"
  - "A test that claims an address family asserts it on the socket the call used, so the claim cannot silently become false"
  - "A branch that only ever takes its success path in every environment the suite runs in gets its other arms extracted into a pure function and unit-tested"

requirements-completed: []

coverage:
  - id: D1
    description: "An emulator bound to ::1 serves connect, a state read, set_color and set_power to a Light, and each of those calls asserts the family of the socket it actually used is AF_INET6"
    requirement: IPV6-01
    verification:
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py::TestIpv6EndToEnd::test_connect_over_ipv6"
        status: pass
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py::TestIpv6EndToEnd::test_get_color_over_ipv6"
        status: pass
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py::TestIpv6EndToEnd::test_set_color_over_ipv6"
        status: pass
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py::TestIpv6EndToEnd::test_set_power_over_ipv6"
        status: pass
    human_judgment: false
  - id: D2
    description: "Animator delivers frames over IPv6 and the emulated device applies them, proven by a device-state readback rather than by send-side packet statistics; the frame socket's family is asserted AF_INET6"
    requirement: IPV6-01
    verification:
      - kind: e2e
        ref: "tests/test_api/test_ipv6_e2e.py::TestIpv6EndToEnd::test_animator_delivers_frames_over_ipv6"
        status: pass
      - kind: other
        ref: "negative control: the same test with port=port + 1 fails with 'At index 0 diff: 0 != 12345', so the readback assertion is not vacuous"
        status: pass
    human_judgment: false
  - id: D3
    description: "The Animator frame socket's family is AF_INET for an IPv4 target, still pinned by the branch's own unit tests, which were not modified"
    requirement: IPV6-01
    verification:
      - kind: unit
        ref: "tests/test_animation/test_animator.py::TestAnimatorSendFrame::test_send_frame_uses_ipv4_socket_family"
        status: pass
      - kind: unit
        ref: "tests/test_animation/test_animator.py (48 passed; git diff shows no change to the file in this plan)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The ::1 fixture starts and serves, with IPV6_V6ONLY set before the bind and read back as 1 on the running server socket"
    requirement: IPV6-01
    verification:
      - kind: integration
        ref: "tests/conftest.py::emulator_server_ipv6 asserts family AF_INET6 and getsockopt(IPPROTO_IPV6, IPV6_V6ONLY) == 1 after start; all five emulator-backed tests pass through it"
        status: pass
      - kind: other
        ref: "awk ordering check on tests/conftest.py: setsockopt at line 172 precedes bind at line 173 inside _Ipv6EmulatedLifxServer.start()"
        status: pass
    human_judgment: false
  - id: D5
    description: "The capability probe skips cleanly where ::1 cannot be bound, and fails instead when LIFX_REQUIRE_IPV6=1; both non-happy arms are unit-tested against a synthetic bind failure"
    requirement: IPV6-01
    verification:
      - kind: unit
        ref: "tests/test_api/test_ipv6_e2e.py::TestIpv6ProbeOutcome::test_bind_failure_defers_to_a_skip_by_default (parameterised over None, '', '0', 'true')"
        status: pass
      - kind: unit
        ref: "tests/test_api/test_ipv6_e2e.py::TestIpv6ProbeOutcome::test_bind_failure_names_the_cause_when_ipv6_is_required"
        status: pass
      - kind: other
        ref: "uv run --frozen pytest tests/test_api/test_ipv6_e2e.py --disable-emulator -q (5 passed, 5 skipped: the probe tests run where the emulator does not)"
        status: pass
    human_judgment: false
  - id: D6
    description: "CI fails rather than skips when the designated must-not-skip cell (ubuntu, Python 3.10) cannot run the IPv6 tests"
    requirement: IPV6-01
    verification:
      - kind: other
        ref: "LIFX_REQUIRE_IPV6=1 uv run --frozen pytest tests/test_api/test_ipv6_e2e.py -q (10 passed); .github/workflows/ci.yml carries exactly one LIFX_REQUIRE_IPV6 line, in an env block on the 'Run unit tests' step, and both fromJSON os lists contain 'ubuntu-latest'"
        status: pass
    human_judgment: true
    rationale: "The gate's failure behaviour on a host without ::1 cannot be observed locally, because every development and CI host this suite runs on can bind IPv6 loopback. The decision function that produces the failure is unit-tested (D5) and the wiring is three lines, but the end-to-end 'CI goes red' path is only ever exercised by the situation it exists to catch. A human should confirm the env expression on the first CI run of this branch."

duration: 30 min
completed: 2026-08-27
status: complete
---

# Phase 10 Plan 04: IPv6 Emulator Fixture, End-to-End Tests and the CI Gate Summary

**A second emulator on `::1` with `IPV6_V6ONLY` set before bind, an end-to-end suite that asserts the socket family every call actually used and proves frame arrival by reading the device's state back, and one CI cell that fails rather than skips when IPv6 is missing**

## Performance

- **Duration:** 30 min
- **Started:** 2026-08-27T12:51:00Z (approximate; first commit 13:10:05Z)
- **Completed:** 2026-08-27T13:22:00Z
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- **SPEC AC 1 and AC 13 (as amended).** An emulator bound to `::1` serves connect, `get_color()`, `set_color()` and `set_power()` to a `Light`, and an `Animator` delivers frames to it. All five emulator-backed tests pass on macOS; Windows continues to skip every emulator test through the pre-existing `tests/conftest.py:148` gate, which was left exactly as it was.
- **SPEC AC 16 (as amended), the anti-false-green requirement.** Every emulator-backed test asserts the address family of the socket the call actually used, read off the real socket rather than off `UdpTransport._family`. A regression that quietly sent this suite back over IPv4 fails it rather than leaving it green.
- **Frame delivery is observed, not inferred.** `send_frame()` increments its packet statistics immediately after `sendto()`, so a send-side count proves only that a datagram reached the kernel. The animation test reads the emulated device's own tile state back instead. The assertion was then validated as non-vacuous by pointing the animator one port off, which failed it with `At index 0 diff: 0 != 12345`.
- **SPEC AC 14 and AC 15.** `ipv6_available` is the single capability gate; `LIFX_REQUIRE_IPV6=1` turns its skip into a failure naming the cause, and CI sets it on the ubuntu/Python 3.10 cell, which is present in every matrix configuration including the reduced ubuntu-only path. Both of the probe's non-happy arms are unit-tested against a synthetic bind failure, so neither is trusted purely on the basis of never having fired.
- **The fixture starts on macOS, which the previous plan revision could not have.** `IPV6_V6ONLY` is set before the bind inside a test-only server subclass. Setting it afterwards raises `EINVAL`, and the stock `EmulatedLifxServer.start()` binds internally via `local_addr=`, so owning socket creation is the only place the option can be set explicitly.
- **Nothing pre-existing was disturbed.** `git diff` on `tests/conftest.py` for this plan shows no removed line at all: the change is a pure addition, and `emulator_server` with its seven devices is untouched.

## Task Commits

Each task was committed atomically, GPG-signed with key `27B3A9EA...20F03B05` and DCO signed off:

1. **Task 1: conftest fixtures for the `::1` emulator** - `f545c5e` (test)
2. **Task 2: IPv6 end-to-end suite** - `47b6597` (test)
3. **Task 3: the designated must-not-skip CI cell and its documentation** - `d1b2f69` (ci)

Nothing was pushed. Operator directive D-24 is not implicated: no `git push` was run at all.

## Files Created/Modified

- `tests/test_api/test_ipv6_e2e.py` - New. Five emulator-backed tests scoped to SPEC R1 on one `Light`, plus a fixture-free class covering the capability probe's two non-happy arms
- `tests/conftest.py` - New only: `get_free_port6()`, `_Ipv6EmulatedLifxServer`, `ipv6_probe_outcome()`, `ipv6_available`, `IPV6_DEVICE_SERIAL`, `emulator_server_ipv6`, `ipv6_light`
- `.github/workflows/ci.yml` - An `env:` block on the existing "Run unit tests" step setting `LIFX_REQUIRE_IPV6` for the ubuntu/Python 3.10 cell only
- `CLAUDE.md` - A short subsection documenting `LIFX_REQUIRE_IPV6` beside `LIFX_EMULATOR_EXTERNAL`

## Decisions Made

See `key-decisions` in the frontmatter. The two that most affect later plans:

**The `::1` emulator's single device is a matrix-capable Tile, not a plain colour light.** The plan asked for the colour-light factory call and, separately, for the animation test to prove delivery by reading device state back. Those two are mutually unsatisfiable: the emulator's `Set64Handler` returns `[]` when `not device_state.has_matrix`, so a plain colour light receives the frames and discards them, and no state readback can ever show anything. The Tile answers the Light commands the control tests use exactly as a plain light would, so D-14's "R1's list on a single `Light`" holds on the library side: `ipv6_light` is still a plain `Light`. The alternative, weakening the delivery proof to a packet counter, would have kept the letter of the fixture instruction and lost the thing the review added it for.

**`emulator_server_ipv6` yields `(port, server)`, not the port alone.** Arrival cannot be observed from the client: whatever the proof, it has to read something server-side, so the fixture has to expose the server. Once exposed, the strongest available proof is the device's own applied state, which is what the test uses. The tuple mirrors `emulator_server`, which yields `(port, server, scenario_manager)` for the same reason.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The specified fixture device made the plan's own delivery assertion unsatisfiable**

- **Found during:** Task 1 (design), confirmed empirically before any fixture was written
- **Issue:** Task 1 specifies "ONE colour-capable Light-class device (reuse the same device-factory call emulator_server uses for its plain Light)". Task 2's acceptance criteria require the animation test to assert "a device-state readback after the frame run, not only `packets_sent` or socket family". `lifx_emulator/handlers/tile_handlers.py:206` returns `[]` from `Set64Handler.handle()` when `not device_state.has_matrix`, so a plain colour light applies no frame and no readback can ever change. Following the fixture instruction literally would have forced the animation test back to a send-side or arrival-count assertion, which is precisely the weakening the review's Codex MEDIUM finding added the readback to prevent.
- **Fix:** The single device is `create_tile_device(tile_count=1)`, another factory call `emulator_server` already uses. The library-side object stays a plain `Light` pointed at it, so D-14's scope is unchanged. The fixture docstring records why.
- **Files modified:** `tests/conftest.py`
- **Verification:** A throwaway probe run before writing the fixture showed the frame applied on the first attempt (`before LightHsbk(hue=0, ...)` to `after LightHsbk(hue=12345, saturation=54321, brightness=40000, kelvin=2750)`), with `server family 30, v6only 1`. The committed test then failed when the animator was pointed one port off.
- **Committed in:** `f545c5e` (Task 1 commit)

**2. [Rule 3 - Blocking] `emulator_server_ipv6` has to yield the server, not just the port**

- **Found during:** Task 1
- **Issue:** The plan says the fixture yields the port. Proving arrival requires reading server-side state, and nothing observable from the client distinguishes a delivered frame from a dropped one, so with only a port the delivery requirement is unreachable.
- **Fix:** Yields `(port, server)`, mirroring `emulator_server`'s existing tuple shape. `ipv6_light` unpacks the port, so its own contract is unchanged.
- **Files modified:** `tests/conftest.py`
- **Verification:** `test_animator_delivers_frames_over_ipv6` reads `server.get_device(IPV6_DEVICE_SERIAL).state.tile_devices[0]["colors"][0]`
- **Committed in:** `f545c5e` (Task 1 commit)

**3. [Rule 2 - Missing Critical] The subclass's `start()` leaked its socket on a partway failure**

- **Found during:** Task 1
- **Issue:** The plan's `start()` sequence creates a socket and then performs `setsockopt`, `bind`, `setblocking` and `create_datagram_endpoint` in turn. Nothing owns the descriptor until the last of those succeeds, so a failure at any earlier step strands it. This is the same defect plan 10-03 spent a task removing from `MdnsTransport.open()`, reintroduced in a fixture.
- **Fix:** The sequence runs inside `try`/`except Exception`, closing the socket before re-raising. Ordering is unaffected: the `setsockopt` still precedes the `bind`.
- **Files modified:** `tests/conftest.py`
- **Verification:** `awk` ordering check still prints `172: set` before `173: bind`; the fixture starts and reads back `V6ONLY == 1`
- **Committed in:** `f545c5e` (Task 1 commit)

**4. [Rule 2 - Missing Critical] The skip-path parameterisation was widened past the two values named**

- **Found during:** Task 2
- **Issue:** The plan asks for a test that the probe returns `False` when `LIFX_REQUIRE_IPV6` is unset. The fixture treats anything other than exactly `"1"` as unset, and the CI expression sets the empty string on every non-designated cell, so `""` is the value that actually reaches production and it was not in the named cases.
- **Fix:** The skip test is parameterised over `None`, `""`, `"0"` and `"true"`. It remains one test function, so the plan's "two probe-decision tests" still describes the file.
- **Files modified:** `tests/test_api/test_ipv6_e2e.py`
- **Verification:** four parameterised cases pass, including under `--disable-emulator`
- **Committed in:** `47b6597` (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (1 bug, 2 missing critical, 1 blocking)
**Impact on plan:** No scope creep. Deviations 1 and 2 are consequences of a single unreachable premise about the fixture device, and both were resolved in the direction the plan's own acceptance criteria and threat register point. Deviations 3 and 4 harden what the plan asked for without changing what it asked for. Every requirement of the plan was met as written.

## Verification Results

| Check | Result |
|---|---|
| `uv run --frozen pytest -q` | 3623 passed, 12 deselected (baseline 3613, +10 new) |
| `uv run --frozen pytest tests/test_api/test_ipv6_e2e.py -v` | 10 passed, 0 skipped |
| `uv run --frozen pytest tests/test_api/test_ipv6_e2e.py --disable-emulator -q` | 5 passed, 5 skipped |
| `LIFX_REQUIRE_IPV6=1 uv run --frozen pytest tests/test_api/test_ipv6_e2e.py -q` | 10 passed |
| `uv run --frozen pytest tests/test_animation/test_animator.py -q` | 48 passed (AC 2's IPv4 side still pinned, file unmodified) |
| `uv run ruff format --check` / `uv run ruff check` | clean |
| `uv run pyright` | clean: 0 errors, 0 warnings |
| AC 8 not regressed: `grep -rn '":" in ' src/lifx/` | no matches |
| `grep -c AF_INET6 tests/test_api/test_ipv6_e2e.py` | 7 (>= 5 required) |
| `grep -c 'pytest.skip\|skipif' tests/test_api/test_ipv6_e2e.py` | 0 (skipping lives in the fixtures) |
| `awk` set-before-bind ordering in `_Ipv6EmulatedLifxServer.start()` | `172: set` then `173: bind` |
| `LIFX_REQUIRE_IPV6` containment | present in `ipv6_available`'s body, absent from `emulator_available`'s |
| `git diff` on `tests/conftest.py` for this plan | pure addition, no removed line |
| YAML parse of the modified `ci.yml` step | `{'name': 'Run unit tests', 'run': ..., 'env': {'LIFX_REQUIRE_IPV6': ...}, 'timeout-minutes': 10}` |
| Both `fromJSON` os lists contain `ubuntu-latest` | confirmed against the file, not assumed |
| `pyproject.toml` `dependencies` | still `[]` |
| `pragma: no cover` added | none |

## Coverage Outcome

`10-COVERAGE-GAPS.md` assigns no gap to plan 10-04, and this plan adds no source line: its diff is `tests/`, `.github/workflows/` and `CLAUDE.md` only, so it carries no patch-coverage exposure of its own. `pyproject.toml` and `codecov.yml` are untouched.

Per plan 10-03's precedent, `10-COVERAGE-GAPS.md` is deliberately left un-annotated so it remains the independent checklist plan 10-06 verifies against. The closure evidence for this plan lives here.

Worth carrying forward for 10-06: the five emulator-backed tests exercise `network/transport.py`, `network/connection.py` and `animation/animator.py` over `AF_INET6` for the first time from an integration path, so the IPv6 arms at those three socket-creation sites now have both unit and end-to-end coverage.

## Known Stubs

None. No hardcoded empty value, placeholder or unwired data source was introduced. No `# pragma: no cover` was added, no test was deleted, skipped or weakened, and no coverage target was changed. The `win32` emulator gate at `tests/conftest.py:148` was neither widened nor narrowed.

## Threat Flags

None. The plan's register was addressed rather than extended:

| Threat | Disposition | Where mitigated |
|--------|-------------|-----------------|
| T-10-10 (a universal skip faking green) | mitigated | Task 3, `d1b2f69`, plus the two probe unit tests in `47b6597` |
| T-10-11 (an "IPv6" test served over IPv4, or a delivery test that only builds a socket) | mitigated | Per-test `AF_INET6` assertion read off the real socket; `IPV6_V6ONLY` set before bind and read back; the animation readback plus its negative control |
| T-10-21 (fixture setup raising instead of skipping) | mitigated | The set moved ahead of the bind where it is legal; capability absence routes through `ipv6_available` to `pytest.skip()`; the flip-to-fail arm is unit-tested |
| T-10-12 (a second emulator doubling CI wall time) | mitigated | One device, one extra server, own port; the whole IPv6 module runs in 0.5 s |
| T-10-SC (package installs) | accepted | No package installed; `dependencies = []` unchanged |

No new network endpoint, auth path, file-access pattern or schema at a trust boundary was introduced. The only sockets bound are on IPv6 loopback, inside the test process.

## Issues Encountered

**The plan's fixture device and its delivery assertion could not both be honoured.** Resolved as deviation 1 above. The decisive detail is `lifx_emulator/handlers/tile_handlers.py:206`, `if not device_state.has_matrix or not packet: return []`, which was read before any fixture was written rather than discovered from a failing test.

**A passing delivery assertion is not evidence that it can fail.** The plan's own history in this phase includes a tracer that would have passed without any write reaching the device. Rather than assume, the committed animation test was run once with the animator pointed at `port + 1`: it failed with `At index 0 diff: 0 != 12345`, so the readback is genuinely load-bearing. The file was restored byte-identically afterwards and the negative control is not committed.

## Residual Gap

One piece of this plan's own machinery is not exercised anywhere: the three lines in `ipv6_available` that call `ipv6_probe_outcome()` and turn a string result into `pytest.fail()`. The decision itself is unit-tested from both arms, but the wiring between the probe and the decision only ever runs on a host that cannot bind `::1`, and no such host exists in this project's development or CI environments. This is recorded as coverage entry D6 with `human_judgment: true` rather than left implicit. It is the same shape of gap the phase accepted for the CI gate as a whole under D-15.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for plan 10-05** (the `scripts/ipv6_thread_probe.py` UAT harness and its tests).

- The branch is still `feat/ipv6-thread-support`; `gsd/phase-10-land-the-ipv6-thread-branch` continues to point at `19e23f7` and now lags by three commits.
- SPEC AC 1, 2, 13, 14, 15 and 16 all pass. AC 8 is not regressed.
- `scripts/ipv6_thread_probe.py` and `tests/test_scripts/` were not touched, so plan 10-05's files are clear.
- **For plan 10-06:** the IPv6 end-to-end suite is the artefact that must be seen *running*, not skipping, on the designated CI cell. The first CI run of this branch is the first time the `LIFX_REQUIRE_IPV6` expression is evaluated by GitHub Actions; if the expression is wrong the cell will silently pass with the variable empty rather than fail, so confirm on that run that the ubuntu/3.10 job reports the five emulator-backed IPv6 tests as passed.
- **Estimate scale note:** `actuals.tokens` here is the template's `chars/4` measure over the realised diff (20146 added characters). Plans 10-01 to 10-03 recorded figures on a different and much larger basis, so the four numbers in this phase are not comparable with each other.
- **No blockers.**

---
*Phase: 10-land-the-ipv6-thread-branch*
*Completed: 2026-08-27*

## Self-Check: PASSED

Verified after writing this summary:

- The created file and all three modified files exist on disk
- All four commit hashes resolve in `git log --oneline --all` (`f545c5e`, `47b6597`, `d1b2f69`, and the metadata commit carrying this file)
- No commit in this plan deleted a tracked file (`git diff --diff-filter=D --name-only f545c5e~1 HEAD` is empty)
- The working tree is clean with no untracked files left behind
- Every commit carries a good signature under key `66D6066620F03B05` and a `Signed-off-by: Avi Miller <me@dje.li>` trailer
- The metadata commit's own hash is not quoted above: a commit cannot name itself, and the self-check ran against the amended commit
