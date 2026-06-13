---
phase: 01-unify-duplicated-discovery-loops
fixed_at: 2026-06-13T13:56:02Z
review_path: .planning/phases/01-unify-duplicated-discovery-loops/01-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-06-13T13:56:02Z
**Source review:** .planning/phases/01-unify-duplicated-discovery-loops/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (fix_scope: Critical + Warnings — 1 Critical, 5 Warning; the 7 Info findings IN-01..IN-07 were out of scope)
- Fixed: 6 (CR-01, WR-01, WR-02 in the prior session; WR-03, WR-04, WR-05 in this session)
- Skipped: 0

> Resumed via `/gsd-resume-work` after the prior session died mid-fix. The
> background `gsd-code-fixer` had committed CR-01/WR-01/WR-02 and left the
> WR-03 docstring edit uncommitted in the working tree. This session
> reconciled git state, finished WR-03/WR-04/WR-05, and ran the full gates.

## Fixed Issues

### CR-01: Uncaught LifxProtocolError from transport.receive() aborts all discovery — DoS vector

**Files modified:** `src/lifx/network/discovery.py`
**Commit:** f6cb654
**Applied fix:** The `transport.receive()` call in `_discover_with_packet` now
catches `LifxProtocolError` alongside `LifxTimeoutError` and `continue`s
(drop-and-continue) instead of letting it propagate out of the generator. A
single size-invalid datagram (< `MIN_PACKET_SIZE` or > `MAX_PACKET_SIZE`) from a
hostile or broken sender can no longer terminate discovery for the whole
library, restoring the documented "Discovery DoS Protection" contract on the now
single discovery path. Per locked decision D-01, rejected datagrams are logged at
DEBUG (not WARNING) to avoid log-flooding as its own DoS surface.

### WR-01: Serial guard accepts the all-zeros broadcast target

**Files modified:** `src/lifx/network/discovery.py`
**Commit:** 560699a
**Applied fix:** The hoisted serial guard now rejects the all-zeros target
(`header.target == b"\x00" * 8`) in addition to the multicast bit
(`header.target[0] & 0x01`, which already covers the all-0xff broadcast). A
spoofed response echoing the zero broadcast target can no longer yield a phantom
`DiscoveredDevice` with serial `"000000000000"`. The unreachable distinct
all-0xff clause was collapsed into the multicast-bit check.

### WR-02: Idle-reset semantics still diverge between the two "unified" loops

**Files modified:** `src/lifx/network/mdns/discovery.py`
**Commit:** 77a3f38
**Applied fix:** `discover_lifx_services` now calls `deadline.mark_response()`
on every valid LIFX response *before* the `seen_serials` dedup check, mirroring
`_discover_with_packet` (discovery.py line ~352) and the D-04 rationale. Duplicate
mDNS re-announcements now extend the idle window instead of being ignored, so a
chatty device can no longer cause premature idle expiry while a slower device has
not yet answered. A comment matching the D-04 rationale was added.

### WR-03: `_discover_with_packet` docstring describes a different function

**Files modified:** `src/lifx/network/discovery.py`
**Commit:** 53767ad → finalised this session
**Applied fix:** The docstring's `Returns:` section (claiming a `List`) was
rewritten as `Yields:`, documenting the `AsyncGenerator` contract, the
first-response-wins per-serial dedup, snake_case `response_payload` keys, and the
skip-not-yield behaviour for non-matching State packets. The misleading example
(`responses = await _discover_with_packet(...)` + synchronous `for`, reading
`response_payload["Label"]`) was replaced with a correct
`async for resp in _discover_with_packet(...)` form using the snake_case
`response_payload["label"]` key. Future callers copying the example now write code
that runs.

### WR-04: `DiscoveryResponse.port` documented as "Device UDP port" but held the broadcast parameter

**Files modified:** `src/lifx/network/discovery.py`
**Commit:** _(this session)_
**Applied fix:** `_discover_with_packet` now sets `port=addr[1]` (the device's
actual source port) when constructing `DiscoveryResponse`, instead of `port=port`
(the broadcast destination parameter). This makes the field truthful and fixes
`find_by_label` (api.py), which uses `GetLabel()` — whose `StateLabel` response
carries no service-port field, so `addr[1]` is the only truthful port available
for devices on non-default ports. `discover_devices` is unaffected: it continues
to use the authoritative `response_payload["port"]` from `StateService` per
locked decision D-05; its "Pitfall 2" comment was updated to reflect that
`resp.port` is now the source port, not the broadcast parameter. The
`DiscoveryResponse.port` attribute docstring was corrected accordingly.

> **Reviewer offered two options** (set `port=addr[1]`, or docstring-only). Chose
> the behavioural fix because the docstring-only option leaves the flagged
> `find_by_label` bug (devices on non-default ports get the wrong port) unfixed,
> contravening the project rule "don't ignore a problem: if you see it, fix it."
> Verified test-safe: in the emulator integration tests the device replies from
> its bound port, so `addr[1] == port`, no assertion changes.

### WR-05: Deprecation guidance points users at a private API; `deprecated` directive missing version

**Files modified:** `src/lifx/network/transport.py`, `tests/test_network/test_transport.py`
**Commit:** _(this session)_
**Applied fix:** The `receive_many` deprecation now (1) supplies the version in
the Sphinx directive — `.. deprecated:: 5.5.0` — which previously rendered
incorrectly with no argument; (2) points users at the **public** API only
("`receive()` in a loop, or the public discovery API in `lifx.api`") in both the
docstring and the `DeprecationWarning` message, instead of the underscore-private
`_discover_with_packet()`; and (3) corrects the removal target from `v2.0` (a
release already in the past — the package is at 5.4.9) to `v6.0` (the next
major). The D-12 test `test_receive_many_emits_deprecation_warning` was updated to
`match="v6.0"`.

> **Version judgement (flagged for maintainer):** A deprecation is a non-breaking
> addition, so it was attributed to the next minor (`5.5.0`) with removal in the
> next major (`6.0`). Adjust if the release plan differs.

## Skipped Issues

None in scope. The 7 Info findings (IN-01..IN-07) were outside the
Critical + Warnings fix scope and remain as documented improvement candidates in
`01-REVIEW.md`.

## Verification

Final state (all 6 in-scope findings applied):
- `uv run ruff format --check` (modified files) — already formatted
- `uv run ruff check src/lifx/network/ tests/test_network/` — all checks passed
- `uv run pyright src/lifx/network/` — 0 errors, 0 warnings, 0 info
- `uv run --frozen pytest tests/test_network/ tests/test_api/test_api_discovery.py` — 231 passed
- `uv run --frozen pytest` — **2508 passed, 12 deselected** (full suite)

The 7 `DeprecationWarning`s emitted by the legacy `receive_many` tests are the
expected IN-07 behaviour (out of scope) — only the dedicated D-12 test asserts the
warning.

---

_Fixed: 2026-06-13T13:56:02Z_
_Fixer: Claude (gsd-resume-work → manual fix pass)_
_Iteration: 1_
