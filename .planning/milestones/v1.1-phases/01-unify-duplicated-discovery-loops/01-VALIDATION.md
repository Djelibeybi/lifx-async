---
phase: 1
slug: unify-duplicated-discovery-loops
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-13
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (via uv, with pytest-asyncio + embedded lifx-emulator-core) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run --frozen pytest tests/test_network/ -q` |
| **Full suite command** | `uv run --frozen pytest -q` |
| **Estimated runtime** | ~35 s (network tests) / ~95 s (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --frozen pytest tests/test_network/ -q`
- **After every plan wave:** Run `uv run --frozen pytest -q` plus `uv run pyright` and `uv run ruff check .`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 95 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| P01-T1 | 01-01 | 1 | D-06 | T-01-01 | IdleDeadline bounds discovery loops (remaining()<=0 on expiry) | unit | `uv run pyright src/lifx/network/utils.py` | will create `src/lifx/network/utils.py` (modify) | ⬜ pending |
| P01-T2 | 01-01 | 1 | D-06 | T-01-01 | IdleDeadline expiry/reset proven deterministically | unit | `uv run --frozen pytest tests/test_network/test_utils.py -v` | will create `tests/test_network/test_utils.py` | ⬜ pending |
| P02-T1 | 01-02 | 2 | D-01, D-02, D-03, D-04 | T-01-02, T-01-03, T-01-04, T-01-05 | Hoisted serial guard (DEBUG) + first-wins dedup + IdleDeadline in _discover_with_packet | unit/emulator | `uv run pyright src/lifx/network/discovery.py && uv run --frozen pytest tests/test_network/test_discovery_devices.py -q` | `src/lifx/network/discovery.py` (modify) | ⬜ pending |
| P02-T2 | 01-02 | 2 | D-05 | T-01-02 | Thin discover_devices wrapper; _parse_device_state_service + struct deleted; port from response_payload["port"] | unit/emulator | `uv run pyright src/lifx/network/discovery.py && uv run --frozen pytest tests/test_network/test_discovery_devices.py -q` | `src/lifx/network/discovery.py` (modify) | ⬜ pending |
| P03-T1 | 01-03 | 2 | D-07, D-08 | T-01-06, T-01-07 | mDNS adopts IdleDeadline; receive() exceptions routed by type (timeout→break, network→WARNING, other→raise) | unit | `uv run pyright src/lifx/network/mdns/discovery.py && uv run --frozen pytest tests/test_network/test_mdns/ -q` | `src/lifx/network/mdns/discovery.py` (modify) | ⬜ pending |
| P04-T1 | 01-04 | 1 | D-09 | T-01-08 | receive_many emits stacklevel=2 DeprecationWarning naming v2.0; body unchanged | unit | `uv run pyright src/lifx/network/transport.py` | `src/lifx/network/transport.py` (modify) | ⬜ pending |
| P04-T2 | 01-04 | 1 | D-12 | T-01-08 | pytest.warns asserts the deprecation fires; existing receive_many tests stay green | unit | `uv run --frozen pytest tests/test_network/test_transport.py -v -k "deprecation or receive_many"` | `tests/test_network/test_transport.py` (modify) | ⬜ pending |
| P05-T1 | 01-05 | 3 | D-10 | T-01-09 | _parse_device_state_service tests retired; malformed-payload re-proven via shared path | unit | `uv run --frozen pytest tests/test_network/test_discovery_errors.py -v` | `tests/test_network/test_discovery_errors.py` (modify) | ⬜ pending |
| P05-T2 | 01-05 | 3 | D-11 | T-01-09 | Generator-level broadcast/multicast + all-0xff rejection + first-wins dedup; emulator dedup retained | unit/emulator | `uv run --frozen pytest tests/test_network/ -q` | `tests/test_network/test_discovery_errors.py` (modify) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (pytest + pytest-asyncio + embedded
emulator already configured; `tests/test_network/` fixtures in place). The three test gaps the
research flagged are scaffolded inline by the plans rather than a separate Wave 0:

- `tests/test_network/test_utils.py` (IdleDeadline) — created in Plan 01-01 Task 2.
- New `_discover_with_packet`-level serial-validation + dedup tests, and malformed-payload
  coverage — created in Plan 01-05.
- `receive_many` `DeprecationWarning` test — created in Plan 01-04 Task 2.

No task's `<verify>` references a MISSING test; every task carries an `<automated>` command.

---

## Manual-Only Verifications

All phase behaviours have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test files scaffolded inline by Plans 01/04/05)
- [x] No watch-mode flags
- [x] Feedback latency < 95s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner — 2026-06-13
