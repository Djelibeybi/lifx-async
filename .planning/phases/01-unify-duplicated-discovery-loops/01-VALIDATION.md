---
phase: 1
slug: unify-duplicated-discovery-loops
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| *(filled by planner from PLAN.md tasks)* | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (pytest + pytest-asyncio + embedded
emulator already configured; `tests/test_network/` fixtures in place).

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 95s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
