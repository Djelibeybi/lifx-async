---
phase: 12-ipv6-discovery-plumbing
reviewed: 2026-08-29T13:02:56Z
depth: deep
files_reviewed: 9
files_reviewed_list:
  - .github/workflows/ci.yml
  - src/lifx/api.py
  - src/lifx/network/discovery.py
  - src/lifx/network/transport.py
  - tests/conftest.py
  - tests/test_api/test_api_discovery.py
  - tests/test_api/test_ipv6_e2e.py
  - tests/test_network/test_discovery_devices.py
  - tests/test_network/test_transport.py
findings:
  critical: 4
  warning: 1
  info: 0
  total: 5
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-08-29T13:02:56Z
**Depth:** deep
**Files Reviewed:** 9
**Status:** issues_found

## Summary

The full Phase 12 diff was traced from the public discovery APIs through validation, family/wildcard selection, IPv6 sockaddr construction, response handling, generator ownership, emulator eligibility, and CI execution. The ordinary numeric and named scope-loss defect from the previous review is fixed, but a degenerate numeric scope still crosses the real send boundary as an unscoped link-local destination. Four correctness/lifecycle blockers and one CI robustness warning remain.

The four reviewed test modules pass (126 tests with `ResourceWarning` promoted to an error), Ruff passes for all reviewed Python files, and Pyright reports no errors. Those gates do not exercise the failing zero-scope case or the other contract failures below. No hard-coded secret or committed live infrastructure identifier was found.

## Narrative Findings (AI reviewer)

No structural-analysis findings were supplied. The findings below come from direct code and call-chain review.

## Critical Issues

### CR-01: A zero numeric IPv6 zone is silently converted to an unscoped link-local send

**Classification:** BLOCKER

**File:** `src/lifx/network/transport.py:478-495`

**Also affects:** `tests/test_network/test_transport.py:806-872`

**Issue:** The repaired zone parser accepts `scope_id == 0` because its range check is `0 <= scope_id`. For a zoned link-local destination, zero is not a usable interface scope; after the code strips the textual zone from the host, the resulting sockaddr is indistinguishable from an unzoned link-local destination. The public validator accepts a zero zone because it checks only that a zone is present, so this path reaches the socket instead of failing as a permanent configuration error. A direct probe against the reviewed implementation recorded a send to `("fe80::1", 56700, 0, 0)` for `fe80::1%0`. The current tests cover positive numeric, named, unknown named, and greater-than-32-bit zones, but omit zero.

**Fix:** Require a positive scope whenever a textual zone is present, and keep zero only for genuinely unzoned non-link-local IPv6 destinations. Align the public validator with the same rule so invalid input fails before socket creation.

```python
if separator:
    scope_id = int(zone) if zone.isdecimal() else socket.if_nametoindex(zone)
    if not 1 <= scope_id <= 0xFFFFFFFF:
        raise LifxNetworkError(
            "Invalid IPv6 zone identifier: scope ID is out of range"
        )
else:
    host = address[0]
    scope_id = 0
```

Add a regression requiring `fe80::1%0` to fail without calling `sendto()`.

### CR-02: Discovery still discards IPv6 receive scope outside `find_by_ip()`

**Classification:** BLOCKER

**File:** `src/lifx/network/transport.py:115-116,132,512`

**Also affects:** `src/lifx/network/discovery.py:440-450`; `src/lifx/api.py:787-798,903-914,1032-1065`

**Issue:** IPv6 datagram callbacks provide a four-field sender sockaddr containing `scope_id`, but the protocol queue and receive API declare a two-field tuple and `_discover_with_packet()` retains only `addr[0]` and `addr[1]`. A link-local response therefore loses its interface scope. `find_by_ip()` repairs its own result by restoring the caller's validated literal, but `discover_devices()`, `discover()`, `find_by_serial()`, and `find_by_label()` receive an unscoped link-local host and then cannot construct a reachable device. Phase 12 made the shared packet-discovery transport IPv6-capable, so this is now a reachable broken path rather than merely an annotation mismatch.

**Fix:** Model both sockaddr shapes and preserve a non-zero received scope at the shared discovery boundary.

```python
UdpAddress = tuple[str, int] | tuple[str, int, int, int]

response_ip = addr[0]
if len(addr) == 4 and addr[3] and "%" not in response_ip:
    response_ip = f"{response_ip}%{addr[3]}"
```

Use `response_ip` in `DiscoveryResponse`, update the queue/callback/receive annotations, and add a split-scope test through `discover_devices()` plus a non-`find_by_ip()` public wrapper.

### CR-03: Public discovery wrappers leak their owned generators on early exit

**Classification:** BLOCKER

**File:** `src/lifx/api.py:787-798,903-914,1032-1065`

**Issue:** Phase 12 added explicit `aclosing()` ownership to `find_by_ip()` and `discover_devices()`, but the other public owners still iterate delegates directly. `find_by_serial()` returns on its first match without closing `discover_devices()`. Closing `discover()` or `find_by_label()` while they are suspended at a yield also does not synchronously close the inner generator. `async for` does not guarantee `aclose()` on `return`, `break`, or closure of an outer async generator, so the inner `_discover_with_packet()` and its UDP endpoint can remain alive until async-generator finalisation or event-loop shutdown.

**Fix:** Give each wrapper a named delegate and an `aclosing()` scope, matching the repaired `find_by_ip()` pattern.

```python
devices = discover_devices(...)
async with aclosing(devices):
    async for discovered in devices:
        ...
```

Apply the same ownership to `find_by_label()`'s `_discover_with_packet()` delegate. Add finalisation sentinels for an early `find_by_serial()` return and for `discover().aclose()` / `find_by_label().aclose()`.

### CR-04: `exact_match=True` can yield multiple devices despite its at-most-one contract

**Classification:** BLOCKER

**File:** `src/lifx/api.py:1043-1065`

**Also affects:** `tests/test_api/test_api_discovery.py:365-409`

**Issue:** The public documentation says exact matching yields at most one device, but the implementation continues scanning after each successful exact match. Device labels are not unique, so two devices with the same label are both yielded. The positive test does not collect or count results and passes even if no device is yielded, so it cannot detect either the multiple-result bug or a total regression of exact matching.

**Fix:** Return after the first successfully constructed exact match and test against a controlled stream containing at least two matching devices.

```python
if device is not None:
    yield device
    if exact_match:
        return
```

The regression should assert that exactly one device is yielded and that the underlying discovery generator is closed.

## Warnings

### WR-01: The required Windows IPv6 step is not intrinsically fail-closed against a skip

**Classification:** WARNING

**File:** `.github/workflows/ci.yml:181-187`

**Also affects:** `tests/conftest.py:214-243,446-483`

**Issue:** `LIFX_REQUIRE_IPV6=1` makes only the loopback bind probe fail rather than skip. The separate targeted-emulator eligibility fixture returns `False` for a missing/mistyped opt-in or an emulator import failure, after which `emulator_server_ipv6` calls `pytest.skip()`. Pytest exits successfully when its only selected test skips, so this step can report green without exercising the required Windows path. The checked-in YAML currently supplies the opt-in, but the test gate itself does not enforce that the selected node actually ran.

**Fix:** Add a dedicated mandatory-targeted flag for this step and call `pytest.fail()` when eligibility is false under that flag, or add an equivalent post-test assertion that rejects a skipped selected node. Unit-test the mandatory-but-ineligible branch.

---

_Reviewed: 2026-08-29T13:02:56Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
