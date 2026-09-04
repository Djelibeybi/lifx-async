---
phase: 10-land-the-ipv6-thread-branch
plan: 02
subsystem: network
tags: [ipv6, address, validation, socket-family, thread]

requires:
  - phase: 10-01
    provides: "the rebased branch content in the working tree, so the three inline family heuristics and the inline Device.__init__ address block were present to replace, plus 10-COVERAGE-GAPS.md naming this plan's owned debt"
provides:
  - "src/lifx/network/address.py, the one home of address-family selection and address validation: validate_address(), family_for(), wildcard_for()"
  - "tests/test_network/test_address.py, a 31-test full-branch suite over the helper"
  - "family derivation at all three socket-creation sites routed through the shared helper, with the inline colon-membership heuristic gone from src/lifx entirely"
  - "a ValueError gate on all four public address entry points: Device.__init__, Device.from_ip(), Device.connect() and find_by_ip()"
  - "IPv4-mapped IPv6 rejection, a rule that did not exist anywhere before"
affects: [10-03, 10-04, 10-05, 10-06, 11, 12]

actuals:
  tokens: 97772
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Leaf-rule module: one shared implementation with a docstring naming every call site, following the theme/slug.py precedent"
    - "Validate/derive split: the entry-point gate and the family derivation are separate functions, because a local bind literal is legal where a device address is not"

key-files:
  created:
    - src/lifx/network/address.py
    - tests/test_network/test_address.py
  modified:
    - src/lifx/devices/base.py
    - src/lifx/api.py
    - src/lifx/network/transport.py
    - src/lifx/network/connection.py
    - src/lifx/animation/animator.py
    - tests/test_devices/test_base.py
    - tests/test_api/test_api_discovery.py
    - tests/test_network/test_transport.py
    - tests/test_network/test_connection.py
    - tests/test_animation/test_animator.py

key-decisions:
  - "Tasks 1 and 3 each landed as a single commit rather than a RED/GREEN pair. The RED state was established and observed first, but D-19 requires the behaviour change and its tests in one commit, and each plan task's own <done> asks for the same, so splitting them would have left a red commit in a bisectable history"
  - "The IPv6 wildcard bind literal is named _IPV6_WILDCARD inside address.py rather than promoted to const.py, because wildcard_for() is its only consumer"
  - "family_for() narrows with isinstance(addr, ipaddress.IPv6Address) rather than getattr(addr, 'scope_id', None), so Pyright proves the attribute access instead of the code defending against it at runtime"
  - "The plan's assigned coverage gaps (devices/base.py lines 522 and 527 on the rebased head) closed by deletion plus replacement, not by retrofitting a test onto the warning: the lines no longer exist, and the rule they held now lives in address.py at 100% branch coverage with an entry-point test driving it through all four callers"

patterns-established:
  - "Address rules live in exactly one module; a call site that needs a family asks for it rather than deriving it"
  - "Every rejection is evaluated before any warning, so an address on its way to a ValueError never logs on the way out"

requirements-completed: [IPV6-02, IPV6-03]

coverage:
  - id: D1
    description: "lifx.network.address exists as the single home of the address rules, exposing validate_address(), family_for() and wildcard_for() and nothing else public, at 100% line and branch coverage with no coverage-exemption markers"
    requirement: IPV6-03
    verification:
      - kind: unit
        ref: "tests/test_network/test_address.py (31 tests)"
        status: pass
      - kind: other
        ref: "uv run pytest tests/test_network/test_address.py -o addopts='' --cov=lifx.network.address --cov-branch --cov-fail-under=100 (30 stmts, 14 branches, 0 miss, 0 partial)"
        status: pass
      - kind: other
        ref: "grep -c 'pragma: no cover' src/lifx/network/address.py prints 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "All three socket-creation sites derive family or bind literal through the shared helper, and the inline colon-membership heuristic is absent from src/lifx"
    requirement: IPV6-03
    verification:
      - kind: other
        ref: "grep -rn '\":\" in ' src/lifx/ produces no output (SPEC AC 8)"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_transport.py::TestSocketFamilySelection (3 tests, both families plus a zoned literal)"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_connection.py::TestWildcardBindSelection (3 tests)"
        status: pass
      - kind: unit
        ref: "tests/test_animation/test_animator.py::test_send_frame_uses_ipv4_socket_family, ::test_send_frame_uses_ipv6_socket_family (unmodified, still pass), ::test_send_frame_uses_ipv6_socket_family_for_zoned_address"
        status: pass
    human_judgment: false
  - id: D3
    description: "All four public address entry points reject a zone-less IPv6 link-local address with ValueError in under 100 ms and before any socket exists, and accept the zoned form"
    requirement: IPV6-02
    verification:
      - kind: unit
        ref: "tests/test_devices/test_base.py::TestAddressEntryPointGate (13 tests, elapsed-time assertion on each of the three base.py entry points, DeviceConnection patched and asserted not called)"
        status: pass
      - kind: unit
        ref: "tests/test_api/test_api_discovery.py::TestFindByIpAddressGate (3 tests, including the D-07 fall-through)"
        status: pass
      - kind: other
        ref: "grep -c 'is_loopback\\|non_private_ip\\|link_local' src/lifx/devices/base.py prints 0"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every coverage gap 10-COVERAGE-GAPS.md assigns to plan 10-02 is closed, with no coverage-exemption marker added and no check weakened"
    requirement: IPV6-03
    verification:
      - kind: other
        ref: "coverage.xml from uv run --frozen pytest, intersected with git diff -U0 main HEAD line ranges: 0 missing lines and 0 partial branches across all six touched source files"
        status: pass
      - kind: other
        ref: "git diff <plan base> HEAD | grep '^+' | grep -c 'pragma: no cover' prints 0 (3 removed, 0 added)"
        status: pass
      - kind: other
        ref: "git diff main HEAD --name-only -- pyproject.toml codecov.yml is empty; --diff-filter=DR over tests/ is empty; 0 added pytest.skip/xfail"
        status: pass
    human_judgment: false
  - id: D5
    description: "The full local gate is green with nothing weakened"
    verification:
      - kind: unit
        ref: "uv run --frozen pytest (3580 passed, 12 deselected)"
        status: pass
      - kind: other
        ref: "uv run pyright (0 errors); uv run ruff check . ; uv run ruff format --check ."
        status: pass
    human_judgment: false

duration: 35 min
completed: 2026-08-27
status: complete
---

# Phase 10 Plan 02: One Home for the Address Rules Summary

**`lifx.network.address` created as the single implementation of address-family selection and address validation, adopted at all three socket-creation sites and gating all four public entry points, so a zone-less IPv6 link-local address now raises a named `ValueError` in microseconds instead of costing a silent 16 second timeout, with the helper at 100% line and branch coverage and three coverage-exemption markers removed rather than carried across.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-08-27T11:40:00Z (approximate)
- **Completed:** 2026-08-27T12:15:41Z
- **Tasks:** 3
- **Files modified:** 12 (2 created, 10 modified)

## Accomplishments

- `src/lifx/network/address.py` is the one home of every address rule. `validate_address()` rejects empty/`None`, malformed literals, IPv4-mapped IPv6, the unspecified address and zone-less IPv6 link-local, then warns on loopback and non-private. `family_for()` and `wildcard_for()` derive without judging, so a local bind literal stays legal where a device address would not be.
- The colon-membership heuristic is gone from `src/lifx` entirely. `UdpTransport.open()`, `DeviceConnection._open()` and `Animator.send_frame` each ask the shared rule, and `_open()` now performs no family test at all.
- All four public entry points are gated, including `Device.connect()`, whose serial-less leg builds a `DeviceConnection` directly and never reaches `__init__`. That was the hole the cross-AI review found (finding 9) and the SPEC was amended to close.
- IPv4-mapped IPv6 rejection is new behaviour that existed nowhere before, closing threat T-10-05.
- The helper reports 100% line and branch coverage over 30 statements and 14 branches, with zero coverage-exemption markers, and three markers came off `devices/base.py` on the way.
- Zero missing lines and zero partial branches remain anywhere inside this plan's diff, measured against both the plan base and `main` (the codecov patch scope).

## Task Commits

1. **Task 1: create `lifx.network.address` with full-branch tests** - `0cacfa8` (feat)
2. **Task 2: adopt the helper at the three socket-creation sites** - `fc85be1` (refactor)
3. **Task 3: gate the four entry points with `validate_address`** - `9ab687a` (fix)

All three carry a good GPG signature under key `66D6066620F03B05` and a `Signed-off-by: Avi Miller <me@dje.li>` trailer. Nothing was pushed (D-24).

Tasks 1 and 3 are marked `tdd="true"`. Both followed the RED/GREEN discipline (see the RED evidence below) but landed as one commit each rather than a `test(...)`/`feat(...)` pair, because D-19 and each task's own `<done>` both require the behaviour change and its tests in the same commit. `workflow.tdd_mode` is `false` in `.planning/config.json`, so the gate-sequence enforcement that would have demanded separate commits does not apply.

### RED evidence

Task 1, before `address.py` existed:

```
tests/test_network/test_address.py:25: in <module>
    from lifx.network.address import family_for, validate_address, wildcard_for
E   ModuleNotFoundError: No module named 'lifx.network.address'
```

Task 3, before the entry-point gates were added (7 failed, 6 passed):

```
FAILED ...::test_init_rejects_zone_less_link_local
FAILED ...::test_from_ip_rejects_zone_less_link_local
FAILED ...::test_connect_rejects_zone_less_link_local
FAILED ...::test_init_delegates_the_whole_rule_set[::ffff:192.0.2.1-IPv4-mapped]
FAILED ...::test_init_delegates_the_whole_rule_set[FE80::1-zone identifier]
FAILED ...::test_init_delegates_the_whole_rule_set[fe80:0:0:0:0:0:0:1-zone identifier]
FAILED ...::test_init_delegates_the_whole_rule_set[-No IP address]
```

The 6 that passed at RED are the rules that already existed and were only being relocated (`0.0.0.0`, `fe80::1%`, the serial checks, the port check) plus the two acceptance-side cases. That split is itself informative: it shows exactly which behaviour this plan added and which it merely moved.

## Files Created/Modified

- `src/lifx/network/address.py` - the shared rule module, 174 lines, near-leaf (its one `lifx` import is `DEFAULT_IP_ADDRESS`)
- `tests/test_network/test_address.py` - 31 tests, every branch from both sides
- `src/lifx/devices/base.py` - address block deleted and replaced with `validate_address(ip)` in `__init__`; new gates in `from_ip()` and `connect()`; `ipaddress` import removed
- `src/lifx/api.py` - `find_by_ip()` validates first, then falls through unchanged
- `src/lifx/network/transport.py` - `family = family_for(self._ip_address)`
- `src/lifx/network/connection.py` - `local_ip = wildcard_for(self.ip)`; `DEFAULT_IP_ADDRESS` import removed as it became unused
- `src/lifx/animation/animator.py` - `family = family_for(self._addr[0])`, cache-on-first-frame shape unchanged, no per-frame check (D-08)
- `tests/test_devices/test_base.py` - `TestAddressEntryPointGate`, 13 tests
- `tests/test_api/test_api_discovery.py` - `TestFindByIpAddressGate`, 3 tests
- `tests/test_network/test_transport.py` - `TestSocketFamilySelection`, 3 tests
- `tests/test_network/test_connection.py` - `TestWildcardBindSelection`, 3 tests
- `tests/test_animation/test_animator.py` - one added zoned-literal family test; the branch's two existing family tests are untouched and still pass

## Coverage outcome

The gaps `10-COVERAGE-GAPS.md` assigned to this plan were `devices/base.py` line 527 (the `link_local_without_scope` warning) and the 50% partial branch at line 522 that guards it. Both are closed by deletion plus replacement rather than by retrofitting a test onto a warning this plan was about to remove:

- The warning and its guard no longer exist in `base.py`. The rule moved into `validate_address()`, where it is a raise, and both arms are driven by `test_address.py` as well as by `TestAddressEntryPointGate` through all four callers.
- `grep -c "is_loopback\|non_private_ip\|link_local" src/lifx/devices/base.py` prints 0.

The three files the gap list recorded as having no gaps but as gaining new patch lines (`network/transport.py`, `network/connection.py`, `animation/animator.py`) each gained a call into the helper. The note in the gap list was that only the IPv4 arm ran in the suite, so the new tests drive the IPv6 arm at each site as well.

Measured intersection of `coverage.xml` against the diff line ranges:

| File | Patch lines vs `main` | Missing | Partial branches |
|---|---|---|---|
| `src/lifx/network/address.py` | 175 | none | none |
| `src/lifx/devices/base.py` | 13 | none | none |
| `src/lifx/api.py` | 6 | none | none |
| `src/lifx/network/transport.py` | 7 | none | none |
| `src/lifx/network/connection.py` | 9 | none | none |
| `src/lifx/animation/animator.py` | 7 | none | none |

No gap was declared unreachable, so no unreachability annotation is owed. No coverage-exemption marker was added anywhere; three were removed from `base.py`. `pyproject.toml` and `codecov.yml` are untouched.

## Decisions Made

- **One commit per task, not a RED/GREEN pair.** Covered under Task Commits above. The RED state was observed for both TDD tasks before any implementation was written.
- **`_IPV6_WILDCARD` stays module-private in `address.py`.** It is the counterpart to `DEFAULT_IP_ADDRESS`, but `wildcard_for()` is its only consumer, so promoting it to `const.py` would widen the public constant surface for no caller.
- **`isinstance` narrowing rather than `getattr` probing.** The branch used `getattr(addr, "scope_id", None)` because `IPv4Address` has no such attribute. Narrowing with `isinstance(addr, ipaddress.IPv6Address)` lets Pyright prove the access, groups the two IPv6-only rules under one guard, and keeps the module free of runtime defensiveness the type checker already covers. This is consistent with the review's rejection of the Antigravity suggestion to add an `isinstance(ip, str)` guard: type-level facts stay at the type level.
- **`family_for()` is asserted to disagree with `validate_address()` on `"::"`.** `test_bind_literals_are_not_rejected` asserts both halves in one test, so the validate/derive split cannot be quietly collapsed later without a failing test naming the reason.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `DEFAULT_IP_ADDRESS` became an unused import in `connection.py`**

- **Found during:** Task 2
- **Issue:** Moving the wildcard choice into `wildcard_for()` left `connection.py` importing `DEFAULT_IP_ADDRESS` with no remaining use, which ruff `F401` blocks.
- **Fix:** Removed the import.
- **Files modified:** `src/lifx/network/connection.py`
- **Verification:** `uv run ruff check .` exits 0
- **Committed in:** `fc85be1`

**2. [Rule 3 - Blocking] `codespell` pre-commit hook rejected "unparsable"**

- **Found during:** Task 1, first commit attempt
- **Issue:** The `validate_address` docstring used "unparsable"; the project's `codespell` hook requires "unparsable".
- **Fix:** Corrected the spelling and re-committed. The hook was not bypassed.
- **Files modified:** `src/lifx/network/address.py`
- **Verification:** `codespell` hook passes
- **Committed in:** `0cacfa8`

**3. [Rule 2 - Missing Critical] Em dashes removed from the new module docstring before commit**

- **Found during:** Task 1
- **Issue:** The first draft of `address.py`'s module docstring carried 7 em dashes. The project convention (recorded in the operator's project memory) is that no em dash may be written into any lifx-async doc, docstring or user-visible string, and that the sentence should be recast rather than the character substituted.
- **Fix:** Recast each construction, using a colon for the call-site list entries, a full stop for the opening claim, and "because" for the rejection rationale. No spaced hyphens were substituted.
- **Files modified:** `src/lifx/network/address.py`
- **Verification:** the file contains zero em dashes; this summary and the new tests contain none either
- **Committed in:** `0cacfa8`

**4. [Rule 1 - Bug] A coverage-exemption marker slipped into a new test helper**

- **Found during:** Task 3, acceptance verification
- **Issue:** The `find_by_ip` acceptance tests needed an async generator yielding nothing. The first version used `return` followed by an unreachable `yield` carrying a `pragma: no cover` marker. That marker would have shown up in the plan's diff, and prohibition 3 forbids adding one. Test files are not measured by `--cov` in any case, so the marker was both forbidden and pointless.
- **Fix:** Replaced with `for _ in (): yield`, which is an async generator with no unreachable statement and needs no marker.
- **Files modified:** `tests/test_api/test_api_discovery.py`
- **Verification:** `git diff | grep '^+' | grep -c 'pragma: no cover'` prints 0
- **Committed in:** `9ab687a`

---

**Total deviations:** 4 auto-fixed (2 blocking, 1 missing critical, 1 bug)
**Impact on plan:** No scope creep. Three are mechanical consequences of the moves the plan specified. The fourth is the plan's own prohibition catching a marker before it reached a commit, which is the gate working as designed.

## Issues Encountered

- **`--cov-fail-under=100` cannot be scoped by `--cov` alone.** The repository's `addopts` already declares `--cov=lifx`, so adding `--cov=lifx.network.address` on the command line widens rather than narrows the measured set, and the run failed at 26.70% total. The helper's 100% figure needs `-o addopts=""` to clear the inherited flags first. This is a property of the plan's stated verification command, not of the code, and it is recorded here so plan 10-03 does not rediscover it.

## Note for plan 10-03

Plan 10-03's send-time family assertion in `UdpTransport.send()` consumes `family_for()`, which is now available at `lifx.network.address`. Two details worth knowing before writing it:

- `family_for()` raises `ValueError` on a malformed literal, propagated unchanged from the standard library. A send-time assertion that calls it on a caller-supplied destination therefore has two failure modes to convert, not one.
- `10-COVERAGE-GAPS.md` states under `network/transport.py` that "plan 10-02 also adds the B1 send-time family assertion". That sentence names the wrong plan: the B1 assertion is plan 10-03's Task, per `10-SPEC.md` requirement 5 and this plan's own artefact list. Plan 10-02 added only the `family_for()` adoption. No action is needed beyond not reading that line as evidence the work is already done.

## User Setup Required

None. No external service configuration was required.

## Next Phase Readiness

- `lifx.network.address` is stable and fully covered, so plan 10-03 can build the send-time assertion on top of `family_for()` without touching the helper.
- Plan 10-04's `::1` fixture will trip the loopback warning on every IPv6 test, now logged in the D-06 helper shape (`module`/`function`/`action`/`ip`) rather than the old `class`/`method` shape. Any fixture or test asserting on that dict must use the new keys. D-13 confirms the warning itself is left alone.
- Plan 10-04 should note that `validate_address()` accepts `::1` (loopback is a warning, not a rejection), so the emulator fixture needs no exemption.
- The remaining patch-coverage debt is entirely plan 10-03's: 15 uncovered lines and 9 partial branches across `mdns/discovery.py` and `mdns/dns.py`.
- **No blockers.** Nothing was pushed to any remote.

## Self-Check: PASSED

Both claimed created files exist on disk (`src/lifx/network/address.py`,
`tests/test_network/test_address.py`), as do all ten claimed modified files. All three
task commits resolve in `git log` (`0cacfa8`, `fc85be1`, `9ab687a`), each with `%G?` of
`G` under key `66D6066620F03B05` and a `Signed-off-by: Avi Miller <me@dje.li>` trailer.
No commit in this plan deleted a tracked file. The working tree was clean after each
commit. `feat/ipv6-thread-support` is the checked-out branch and no `git push`,
`git stash`, `git clean` or rebase was run. The full suite passes at 3580 tests, up from
3526 at the start of this plan, with no test deleted, skipped or weakened.

---
*Phase: 10-land-the-ipv6-thread-branch*
*Completed: 2026-08-27*
