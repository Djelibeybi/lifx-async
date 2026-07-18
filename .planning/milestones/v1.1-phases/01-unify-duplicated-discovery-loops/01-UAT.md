---
status: complete
phase: 01-unify-duplicated-discovery-loops
source:
  - 01-01-SUMMARY.md
  - 01-02-SUMMARY.md
  - 01-03-SUMMARY.md
  - 01-04-SUMMARY.md
  - 01-05-SUMMARY.md
started: 2026-06-13T14:02:40Z
updated: 2026-06-13T14:18:00Z
---

## Current Test

[testing complete]

## Tests

<!--
This phase is a pure internal refactor with NO user-facing API change.
The user-observable contract is that discovery behaves identically while
the documented DoS protections now apply on the single unified path.
Tests 1-3 were verified automatically against the in-process emulator
(tests/test_network/test_uat_phase01_smoke.py, since removed) plus the
full regression suite (2508 passed).
-->

### 1. Discovery still works through the unified path
expected: `discover_devices()` / `discover()` finds devices and reports each device's authoritative service port from the StateService payload (D-05), unchanged from before the refactor.
result: pass
evidence: "Emulator: discover_devices() -> 7 devices, service_ports=[64646]. Full suite test_api_discovery.py 231 passed."

### 2. find_by_label returns a device on the correct port (WR-04)
expected: `find_by_label()` matches by label and the returned device carries a truthful port (the device's actual source port), so devices on non-default ports are reachable.
result: pass
evidence: "Emulator: find_by_label('LIFX Color 000001') -> 1 match, port=64646 == device source port. WR-04 fix verified."

### 3. receive_many emits a corrected DeprecationWarning (WR-05 / D-09 / D-12)
expected: Calling the deprecated `UdpTransport.receive_many()` emits a `DeprecationWarning` that names the v6.0 removal target and points at the public `lifx.api` discovery API — not the private `_discover_with_packet`.
result: pass
evidence: "Emulator: warning fired=True, names v6.0=True, public-api=True, no private leak=True. D-12 test asserts match='v6.0'."

### 4. Validate discovery against real LIFX hardware
expected: Running discovery against the user's real LIFX network finds the expected devices, with correct serials/IPs/ports and no regression from the unified discovery path.
result: pass
evidence: "User re-ran examples/discovery_broadcast.py against real hardware after the fix (0d83deb) — 'it works just fine now'. The DeviceService(5) regression is confirmed closed on hardware."
history: |
  Initially failed: examples/discovery_broadcast.py raised
  'ValueError: 5 is not a valid DeviceService' on real hardware (severity:
  major). Root cause: D-05 retired the raw struct parser for
  StateService.unpack, which coerced the service byte to DeviceService(5) and
  raised; real devices advertise services the bundled enum does not define;
  the emulator only sends service=UDP(1) so no test caught it. Fixed in
  0d83deb (base.py enum tolerance via _coerce_enum + discovery non-UDP filter;
  3 regression tests). Confirmed on hardware by the user.

## Summary

total: 4
passed: 4
issues: 0
pending: 0
blocked: 0
skipped: 0

## Gaps

- truth: "Discovery against real hardware finds devices without raising"
  status: closed
  reason: "ValueError on unknown DeviceService(5) — regression from D-05; fixed in 0d83deb (enum tolerance + non-UDP service filter) and confirmed on real hardware by the user."
  severity: major
  test: 4
  artifacts:
    - src/lifx/protocol/base.py
    - src/lifx/network/discovery.py
    - tests/test_network/test_discovery_errors.py
  missing: []
