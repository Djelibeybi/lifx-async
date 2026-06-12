---
phase: 1
slug: ceiling-save-on-exit
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-12
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode = "auto") |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_devices/test_state_ceiling.py -k SaveOnExit -v` |
| **Full suite command** | `uv run --frozen pytest` |
| **Estimated runtime** | ~3s (quick) / ~60-90s (full suite, 2425+ tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_devices/test_state_ceiling.py -k SaveOnExit -v`
- **After every plan wave:** Run `uv run --frozen pytest`
- **Before `/gsd-verify-work`:** Full suite green + `uv run pyright` clean + `uv run ruff check .` clean
- **Max feedback latency:** ~3 seconds (quick command)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | TEST-01, TEST-02, TEST-03 | — | N/A | integration (emulator) | `uv run pytest tests/test_devices/test_state_ceiling.py -k SaveOnExit -v` | ✅ (created by 01-01-01) | ✅ green |
| 01-01-02 | 01 | 1 | CEIL-01, CEIL-02, CEIL-03, CEIL-04 | T-01-02 | save errors swallowed + close() always runs | integration (emulator) | `uv run pytest tests/test_devices/test_state_ceiling.py -k SaveOnExit -v` | ✅ (created by 01-01-01) | ✅ green |
| 01-01-03 | 01 | 1 | CEIL-04 | T-01-02 | full suite unaffected; types + lint clean | regression | `uv run ruff format . && uv run ruff check . && uv run pyright && uv run --frozen pytest` | ✅ (existing suite) | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_devices/test_state_ceiling.py` — add `TestCeilingLightSaveOnExit` class covering TEST-01, TEST-02, TEST-03 (created by Task 01-01-01)

*No framework install needed — pytest + emulator (`lifx-emulator-core` dev dep) infrastructure already in place.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

*All phase behaviours have automated verification (emulator-backed integration tests + full regression suite).*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (TestCeilingLightSaveOnExit created in Task 1)
- [x] No watch-mode flags
- [x] Feedback latency < 5s (quick command)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-12
