# Phase 10: Deferred Items

Out-of-scope discoveries logged during execution. Each names why it was not fixed
where it was found.

## `src/lifx/network/mdns/dns.py` — em dash in `build_address_query()` docstring

**Found during:** plan 10-03, Task 4
**Line:** 367, `"...included in the service response — e.g. when a Thread border router's..."`

The project's standing prose rule is no em dashes (recast the sentence instead). This one
arrived with the rebased branch commits, not with any Phase 10 fix.

**Why it was not fixed here.** Plan 10-03 Task 4 is explicitly a test-only commit
("Change no source file in this task... that is a finding, not a licence"), and its
acceptance criteria require `git diff HEAD~1 --name-only` to list only files under
`tests/`. B4's docstring scope is `network/mdns/transport.py` alone, so this line is not
in any Task 1 to 3 commit either.

**Suggested owner:** Phase 11, which owns the mDNS documentation pass (MDNS-08).

## Flaky: `test_api_apply_theme.py::TestDeviceGroupApplyTheme` times out against the in-process emulator

**Found:** 2026-08-28, on the `6.6.0` release commit `ac221d7` (CI run 33113095979,
Python 3.12 / ubuntu). `1 failed, 3668 passed`.

```
FAILED tests/test_api/test_api_apply_theme.py::TestDeviceGroupApplyTheme::test_apply_theme_with_power_on
  lifx.exceptions.LifxTimeoutError: No response from 127.0.0.1 after 3 attempts
```

**Not a Phase 10 regression.** Evidence:

1. The identical failure mode hit a *sibling* test in the same class — `test_apply_theme_to_tiles`,
   same `No response from 127.0.0.1 after 3 attempts` — on `b4ef1ee` on 2026-08-16, eleven days
   before this phase existed (CI run 31946070836).
2. Phase 10 touched neither `apply_theme` nor `light.py`. Its only `api.py` change is a
   `validate_address(ip)` call inside `find_by_ip()`, which this test never reaches. Its
   `connection.py` change replaces `"::" if ":" in self.ip else DEFAULT_IP_ADDRESS` with
   `wildcard_for(self.ip)` — the same `0.0.0.0` for any IPv4 address, so a behavioural no-op on
   this path.
3. `a56bd2c` and `d68d36a` both went green across all 15 matrix cells. The failure appeared only
   on `ac221d7`, whose entire diff is `pyproject.toml`, `uv.lock` and the generated changelog.
4. The test passes 5/5 locally.

**Likely cause.** `DeviceGroup.apply_theme()` fans out over seven emulated devices concurrently
through `asyncio.gather`, and the emulator runs in-process on the same event loop. On a loaded
runner the emulator's own coroutine can be starved past three consecutive 2.0 s request deadlines.
This is the same shape as the streaming-starves-control-traffic behaviour seen with the Animator.

**Suggested treatment (out of Phase 10 scope).** Either give the group fan-out tests a longer
request timeout, or bound the concurrency of `apply_theme`'s gather in the emulator-backed tests.
Do not paper over it with a bare retry marker: the starvation is the thing worth measuring.
