# Implementation Plan: Full Review — Test Coverage Gaps

**Track ID:** review-tests_20260318
**Spec:** [spec.md](./spec.md)
**Created:** 2026-03-18
**Status:** [ ] Not Started

## Overview

Add tests in three phases ordered by severity. Protocol correctness tests first (they also document known bugs), then adversarial network input tests, then network security/resilience tests.

---

## Phase 1: Protocol Correctness Tests

Write tests that document or catch the bugs identified in the code review. These are written alongside (or before) the fixes in review-critical_20260318.

### Tasks

- [ ] Task 1.1: Add test to `tests/test_devices/test_multizone.py` — assert `MultiZoneEffect.direction` setter produces exactly 8 parameters (`len(effect.parameters) == 8`), not 9 (T-C1)
- [ ] Task 1.2: Add test to `tests/test_devices/test_multizone.py` — assert direction value is stored at correct index after setter: `effect.parameters[1] == int(Direction.FORWARD)` (T-M2 — strengthen existing assertion)
- [ ] Task 1.3: Add test to `tests/test_devices/test_multizone.py` — verify `get_color_zones()` results in state updated with correct zones (T-C2); assert `_state.zones` equals expected after single call
- [ ] Task 1.4: Add test to `tests/test_devices/test_multizone.py` — verify `get_extended_color_zones()` same state update correctness
- [ ] Task 1.5: Run benchmarks and save as `review-tests_20260318-Phase1`: `uv run pytest tests/benchmarks/ -m benchmark --no-cov --benchmark-save=review-tests_20260318-Phase1`

### Verification

- [ ] `uv run pytest tests/test_devices/test_multizone.py -v` — new tests run; direction-setter test initially FAILS (red phase) until review-critical_20260318 fixes `multizone.py:130`
- [ ] After review-critical_20260318 fix: all multizone tests pass (green phase)

---

## Phase 2: Adversarial mDNS Parser Tests

Add a comprehensive adversarial test suite for the DNS wire-format parser. These tests verify the parser fails safely on attacker-controlled input.

### Tasks

- [ ] Task 2.1: Create `tests/test_network/test_mdns/test_dns_adversarial.py` with class `TestMdnsParserAdversarial`
- [ ] Task 2.2: Write test — empty packet (0 bytes) raises `ValueError` or `struct.error` (T-H2)
- [ ] Task 2.3: Write test — truncated header (<12 bytes) raises cleanly (T-H2)
- [ ] Task 2.4: Write test — `an_count=65535` but only 12 bytes of data: raises `ValueError` before exhausting memory (SEC-M2)
- [ ] Task 2.5: Write test — resource record with `rdlength=65535` but only 4 bytes of rdata: raises `ValueError` (T-H2)
- [ ] Task 2.6: Write test — compression pointer chain at exactly `max_jumps=10`: successfully resolves name (boundary test) (T-H2)
- [ ] Task 2.7: Write test — compression pointer chain at `max_jumps=11`: raises `ValueError` (T-H2)
- [ ] Task 2.8: Write test — circular compression pointer (pointer points to itself): raises within limit, no infinite loop (T-H2)
- [ ] Task 2.9: Write test — malformed UTF-8 bytes in DNS label: parser does not crash, returns string with replacement characters (T-H2)
- [ ] Task 2.10: Write test — compression pointer pointing forward in packet (beyond current offset): verify handled without crash (SEC-L3)
- [ ] Task 2.11: Run benchmarks and save as `review-tests_20260318-Phase2`: `uv run pytest tests/benchmarks/ -m benchmark --no-cov --benchmark-save=review-tests_20260318-Phase2`

### Verification

- [ ] `uv run pytest tests/test_network/test_mdns/test_dns_adversarial.py -v` — all adversarial tests pass
- [ ] Any test that currently fails (revealing actual parser bugs) is marked `@pytest.mark.xfail` with explanation until the parser is fixed

---

## Phase 3: Network Security and Resilience Tests

Test network-layer security properties: source ID validation, queue bounded behavior.

### Tasks

- [ ] Task 3.1: Add test to `tests/test_network/test_transport.py` — verify `_UdpProtocol` with `maxsize=1000`: sending 1001 packets via `datagram_received` results in queue size of 1000 (drop-on-full behavior after review-critical_20260318 fix) (T-H1, SEC-M1)
- [ ] Task 3.2: Add test to `tests/test_network/test_transport.py` — verify no exception raised when queue is full and additional packet arrives (T-H1)
- [ ] Task 3.3: Add test to `tests/test_network/test_discovery_errors.py` — send discovery request, inject a crafted response with wrong source ID into transport, verify the device with wrong source ID is NOT yielded by `discover_devices()` (T-H3)
- [ ] Task 3.4: Add test to `tests/test_network/test_discovery_errors.py` — send discovery request, inject response with broadcast serial (all zeros / all 0xFF), verify it is rejected (complements T-H3)
- [ ] Task 3.5: Run benchmarks and save as `review-tests_20260318-Phase3`: `uv run pytest tests/benchmarks/ -m benchmark --no-cov --benchmark-save=review-tests_20260318-Phase3`

### Verification

- [ ] `uv run pytest tests/test_network/ -v` — all network tests pass including new security tests
- [ ] `uv run --frozen pytest` — full test suite passes
- [ ] `uv run ruff format . && uv run ruff check .` — clean
- [ ] `uv run pyright` — clean

---

## Final Verification

- [ ] All acceptance criteria in spec.md met
- [ ] `uv run --frozen pytest` — full test suite passes including new tests
- [ ] No `xfail` tests without tracking issues filed
- [ ] `uv run pyright` — clean
- [ ] `uv run ruff format . && uv run ruff check .` — clean
- [ ] Ready for review

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
