---
phase: 2
slug: discovery-rebroadcast
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: true) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-16
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode=auto, pytest-cov `--cov-branch`, pytest-timeout 30 s) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_network/test_discovery_errors.py tests/test_network/test_discovery_devices.py tests/test_network/test_discovery_rebroadcast.py -x` |
| **Full suite command** | `uv run --frozen pytest` |
| **Estimated runtime** | quick ~10 s; full ~90 s |

---

## Sampling Rate

- **After every task commit:** Run quick command + `uv run ruff format . && uv run ruff check . --fix && uv run pyright`
- **After every plan wave:** Run `uv run --frozen pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | DISC-01, DISC-02 | — | RED branch-matrix tests incl. same-source/message reuse and cross-broadcast dedup | unit (TDD RED) | `uv run pytest tests/test_network/test_discovery_rebroadcast.py --collect-only -q` | ✅ | ✅ green |
| 2-01-02 | 01 | 1 | DISC-01, DISC-02 | — | Re-broadcast interleave; serial-validation guard and dedup unchanged | unit (GREEN) | `uv run pytest tests/test_network/test_discovery_rebroadcast.py tests/test_network/ -x` | ✅ | ✅ green |
| 2-01-03 | 01 | 1 | DISC-01 | — | Branch-coverage audit of every new branch | coverage | `uv run pytest --cov=lifx --cov-branch tests/test_network/` | ✅ | ✅ green |
| 2-02-01 | 02 | 2 | DISC-03 | — | UAT harness (exit 2 on roster < 60 guard) | harness build | `uv run python .planning/phases/02-discovery-rebroadcast/uat_rounds.py --help` | ✅ | ✅ green |
| 2-02-02 | 02 | 2 | DISC-03 | — | 6-round fleet measurement vs 48/73 baseline | hardware UAT (headless) | `uv run python .planning/phases/02-discovery-rebroadcast/uat_rounds.py` | ✅ | ✅ green |

Behavioural branch matrix from 02-RESEARCH.md §Validation Architecture (schedule cap,
exhaustion fallback, quiet-slice continue, both exit branches, multi-send loop pass,
no-mark_response-on-send) must each appear as a distinct test for the 100% branch patch
coverage gate.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_network/test_discovery_rebroadcast.py` — stubs for DISC-01/DISC-02 schedule + dedup branches
- [x] `uat_rounds.py` UAT harness (phase dir or scratch; NOT shipped in src/) — 6 × `discover_devices(timeout=10.0)` rounds, compares against baseline `.planning/spikes/005-discovery-regimes/summary-20260716-211339.json`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 6-round median fleet coverage = full roster (baseline 48/73) | DISC-03 | Emulator cannot model per-AP broadcast delivery loss | Run `uv run python .planning/phases/02-discovery-rebroadcast/uat_rounds.py` on the production network; compare median found vs roster union and vs baseline |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-16
