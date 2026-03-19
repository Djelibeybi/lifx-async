# Implementation Plan: Full Review — Test Coverage Gaps

**Track ID:** review-tests_20260318
**Spec:** [spec.md](./spec.md)
**Created:** 2026-03-18
**Status:** [x] Complete

## Overview

Add tests in three phases ordered by severity. Protocol correctness tests first (they also document known bugs), then adversarial network input tests, then network security/resilience tests.

---

## Phase 1: Protocol Correctness Tests

Write tests that document or catch the bugs identified in the code review. These are written alongside (or before) the fixes in review-critical_20260318.

### Tasks

- [x] Task 1.1: Add test to `tests/test_devices/test_multizone.py` — assert `MultiZoneEffect.direction` setter produces exactly 8 parameters (`len(effect.parameters) == 8`), not 9 (T-C1) — already implemented in review-critical_20260318
- [x] Task 1.2: Add test to `tests/test_devices/test_multizone.py` — assert direction value is stored at correct index after setter: `effect.parameters[1] == int(Direction.FORWARD)` (T-M2 — strengthen existing assertion) — already implemented in review-critical_20260318
- [x] Task 1.3: Add test to `tests/test_devices/test_multizone.py` — verify `get_color_zones()` results in state updated with correct zones (T-C2); assert `_state.zones` equals expected after single call
- [x] Task 1.4: Add test to `tests/test_devices/test_multizone.py` — verify `get_extended_color_zones()` same state update correctness
- [x] Task 1.5: Run benchmarks and save as `review-tests_20260318`: `uv run pytest tests/benchmarks/ -m benchmark --no-cov --benchmark-save=review-tests_20260318`

### Verification

- [x] `uv run pytest tests/test_devices/test_multizone.py -v` — all multizone tests pass
- [x] After review-critical_20260318 fix: all multizone tests pass (green phase)

---

## Phase 2: Adversarial mDNS Parser Tests

Add a comprehensive adversarial test suite for the DNS wire-format parser. These tests verify the parser fails safely on attacker-controlled input.

### Tasks

- [x] Task 2.1: Create `tests/test_network/test_mdns/test_dns_adversarial.py` with class `TestMdnsParserAdversarial`
- [x] Task 2.2: Write test — empty packet (0 bytes) raises `ValueError` or `struct.error` (T-H2)
- [x] Task 2.3: Write test — truncated header (<12 bytes) raises cleanly (T-H2)
- [x] Task 2.4: Write test — `an_count=65535` but only 12 bytes of data: raises `ValueError` before exhausting memory (SEC-M2)
- [x] Task 2.5: Write test — resource record with `rdlength=65535` but only 4 bytes of rdata: raises `ValueError` (T-H2)
- [x] Task 2.6: Write test — compression pointer chain at exactly `max_jumps=10`: successfully resolves name (boundary test) (T-H2)
- [x] Task 2.7: Write test — compression pointer chain at `max_jumps=11`: raises `ValueError` (T-H2)
- [x] Task 2.8: Write test — circular compression pointer (pointer points to itself): raises within limit, no infinite loop (T-H2)
- [x] Task 2.9: Write test — malformed UTF-8 bytes in DNS label: parser does not crash, returns string with replacement characters (T-H2)
- [x] Task 2.10: Write test — compression pointer pointing forward in packet (beyond current offset): verify handled without crash (SEC-L3)
- [x] Task 2.11: Run benchmarks — combined with final benchmark run

### Verification

- [x] `uv run pytest tests/test_network/test_mdns/test_dns_adversarial.py -v` — all 13 adversarial tests pass
- [x] No xfail tests needed — all parser defenses already work correctly

---

## Phase 3: Network Security and Resilience Tests

Test network-layer security properties: source ID validation, queue bounded behavior.

### Tasks

- [x] Task 3.1: Add test to `tests/test_network/test_transport.py` — verify `_UdpProtocol` with `maxsize=1000`: sending 1001 packets via `datagram_received` results in queue size of 1000 (drop-on-full behavior after review-critical_20260318 fix) (T-H1, SEC-M1) — already implemented in review-critical_20260318
- [x] Task 3.2: Add test to `tests/test_network/test_transport.py` — verify no exception raised when queue is full and additional packet arrives (T-H1) — already implemented in review-critical_20260318
- [x] Task 3.3: Add test to `tests/test_network/test_discovery_errors.py` — send discovery request, inject a crafted response with wrong source ID into transport, verify the device with wrong source ID is NOT yielded by `discover_devices()` (T-H3)
- [x] Task 3.4: Add test to `tests/test_network/test_discovery_errors.py` — send discovery request, inject response with broadcast serial (all zeros / all 0xFF), verify it is rejected (complements T-H3)
- [x] Task 3.5: Run benchmarks — combined with final benchmark run

### Verification

- [x] `uv run pytest tests/test_network/ -v` — all network tests pass including new security tests
- [x] `uv run --frozen pytest` — full test suite passes (2465 passed)
- [x] `uv run ruff format . && uv run ruff check .` — clean
- [x] `uv run pyright` — clean (0 errors, 0 warnings)

---

## Final Verification

- [x] All acceptance criteria in spec.md met
- [x] `uv run --frozen pytest` — full test suite passes (2465 tests, 12 deselected)
- [x] No `xfail` tests — all parser defenses work correctly
- [x] `uv run pyright` — clean (0 errors, 0 warnings, 0 information)
- [x] `uv run ruff format . && uv run ruff check .` — clean
- [x] Ready for review

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
