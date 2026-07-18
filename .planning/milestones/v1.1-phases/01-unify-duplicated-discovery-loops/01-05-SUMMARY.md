---
phase: 01-unify-duplicated-discovery-loops
plan: "05"
subsystem: network/discovery
tags:
  - testing
  - discovery
  - dos-protection
  - serial-validation
dependency_graph:
  requires:
    - 01-02
  provides:
    - D-10 test coverage (malformed-payload handling via shared path)
    - D-11 test coverage (broadcast serial, all-0xff serial, first-wins dedup at _discover_with_packet)
  affects:
    - tests/test_network/test_discovery_errors.py
tech_stack:
  added: []
  patterns:
    - AsyncMock+patch UdpTransport pattern for _discover_with_packet direct testing
    - Truncated-payload test fixture (header + 2-byte payload, StateService expects 5)
key_files:
  modified:
    - tests/test_network/test_discovery_errors.py
decisions:
  - Drove _discover_with_packet directly (not only via discover_devices) for D-11 tests to prove protection at its new location
  - Used ValueError-swallowing Exception branch (not LifxProtocolError) for truncated payload — StateService.unpack raises ValueError; both caught by _discover_with_packet
metrics:
  duration: "~5 minutes"
  completed: "2026-06-12T15:59:50Z"
  tasks_completed: 2
  files_modified: 1
---

# Phase 01 Plan 05: Close D-10/D-11 Test Gaps in Discovery Error Suite — Summary

**One-liner:** Re-prove malformed-payload handling via the unified `_discover_with_packet` path (D-10) and add direct generator-level serial-validation and first-wins dedup tests (D-11).

## What Was Built

Rewrote `tests/test_network/test_discovery_errors.py` to close test gaps left by the Wave 2 discovery refactor (Plan 02). All references to the deleted `_parse_device_state_service` function are gone; the behaviour it covered is now re-proven through the shared generator.

### New test classes

**`TestMalformedPayloadHandling`** (D-10):
- `test_truncated_state_service_payload_yields_no_device` — feeds a StateService packet whose header claims 2-byte payload (too short for the 5-byte `<BI` struct) through `discover_devices` via mocked `UdpTransport`; asserts zero devices yielded and no exception escapes the generator.

**`TestDiscoverWithPacketSerialValidation`** (D-11):
- `test_broadcast_bit_serial_rejected_at_generator` — drives `_discover_with_packet` directly; multicast serial (`\x01\x02\x03…`) yields zero `DiscoveryResponse` objects.
- `test_all_ff_serial_rejected_at_generator` — same pattern with `\xff`×8; zero responses.
- `test_first_wins_dedup_at_generator` — two packets with identical valid serial; exactly one `DiscoveryResponse` yielded.

### Retained classes (unchanged)

- `TestDiscoveryMalformedPackets` (emulator)
- `TestDiscoveryWithEmulatorErrors`
- `TestDiscoverySourceValidation` (existing serial/source validation tests via `discover_devices`)
- `TestDiscoveryDeduplication` (emulator dedup — D-11 emulator-first)

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Retire _parse_device_state_service tests, re-prove malformed-payload handling | dbdf418 | tests/test_network/test_discovery_errors.py |
| 2 | Add generator-level serial-validation and dedup tests (D-11) | dbdf418 | tests/test_network/test_discovery_errors.py |

(Both tasks committed together — single file, completed in one pass.)

## Verification Results

| Check | Result |
|-------|--------|
| `grep -c "_parse_device_state_service" test_discovery_errors.py` | 0 |
| `grep -c "class TestParseDeviceStateServiceErrors" test_discovery_errors.py` | 0 |
| `grep -c "_discover_with_packet" test_discovery_errors.py` | 10 |
| `pytest tests/test_network/test_discovery_errors.py -v` | 12 passed |
| `pytest tests/test_network/ -q` | 207 passed |
| `pyright` | 0 errors |
| `ruff check .` | no errors |

## Deviations from Plan

None — plan executed exactly as written. The `TestParseDeviceStateServiceErrors` class and `_parse_device_state_service` import were already removed by plan 01-02 as noted in the execution context. No structural changes were required.

## Known Stubs

None.

## Threat Flags

None — test-only plan; no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- `tests/test_network/test_discovery_errors.py` exists and is committed at dbdf418
- Commit dbdf418 verified via `git log --oneline`
