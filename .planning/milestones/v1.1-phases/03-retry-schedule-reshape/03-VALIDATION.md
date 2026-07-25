---
phase: 3
slug: retry-schedule-reshape
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-16
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode=auto, pytest-cov `--cov-branch`, pytest-timeout 30 s) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_network/test_connection.py tests/test_network/test_concurrent_requests.py tests/test_network/test_connection_retry.py -x` |
| **Full suite command** | `uv run --frozen pytest` |
| **Estimated runtime** | quick ~15 s; full ~90 s |

---

## Sampling Rate

- **After every task commit:** Run quick command + `uv run ruff format . && uv run ruff check . --fix && uv run pyright`
- **After every plan wave:** Run `uv run --frozen pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

(Task IDs filled by planner; requirement mapping from 03-RESEARCH.md §Validation Architecture.)

| Req ID | Behaviour | Test Type | Automated Command | File Exists | Status |
|--------|-----------|-----------|-------------------|-------------|--------|
| RETRY-01 | Healthy network: exactly 1 transmission (send spy + emulator); escalating gaps honoured (≥3 sends at patched spacing; no send before 0.2 s on quiet net) | unit + emulator | `uv run pytest tests/test_network/test_connection_retry.py -x` | ✅ | ✅ green |
| RETRY-02 | Injected response between retransmits completes immediately; no further sends after response | unit | same file | ✅ | ✅ green |
| RETRY-03 | Drop-all: `timeout ≤ elapsed < timeout + 0.3` for GET and SET paths | emulator | rewritten `TestRetryTimeoutBudget` (test_concurrent_requests.py) | ✅ | ✅ green |
| RETRY-04 | Late reply to earlier sequence accepted (GET and ACK paths); mismatch injections raise LifxProtocolError; post-cleanup late reply DEBUG-logged + discarded | unit | test_connection_retry.py | ✅ | ✅ green |
| RETRY-01..04 | Regression: existing seam/emulator/device tests pass unmodified (except the 3 enumerated TestRetryTimeoutBudget changes) | all | `uv run --frozen pytest` | ✅ | ✅ green |

Branch matrix: 16 rows enumerated in 03-RESEARCH.md §Branch Matrix — every arm needs a
distinct test for the 100% branch patch coverage gate.

---

## Wave 0 Requirements

- [x] `tests/test_network/test_connection_retry.py` — stubs for RETRY-01/02/04 branches
- [x] `TestRetryTimeoutBudget` rewrite scheduled (assertion inversion — old budget contract is the bug)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Zero-loss packets/trial = 1.0 on gen4 downlight (optional per CONTEXT) | RETRY-01 evidence | Real RTT distribution; headless but network-dependent | N × `request(GetColor())` with send spy against 192.168.18.95; expect 1.0 tx/trial |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-17
