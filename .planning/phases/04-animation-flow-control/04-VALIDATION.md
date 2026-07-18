---
phase: 4
slug: animation-flow-control
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-17
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.4.2 + pytest-asyncio (`asyncio_mode = "auto"`), pytest-cov with `--cov-branch` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (markers include `emulator`) |
| **Quick run command** | `uv run pytest tests/test_animation/ -x -q` |
| **Full suite command** | `uv run --frozen pytest` |
| **Estimated runtime** | quick ~15 s; full ~115 s |

---

## Sampling Rate

- **After every task commit:** Run quick command + `uv run ruff format . && uv run ruff check . --fix && uv run pyright`
- **After every plan wave:** Run `uv run --frozen pytest` (intentionally RED between waves 1 and 3 — RED evidence recorded per plan)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~115 seconds

---

## Per-Task Verification Map

| Req ID | Behaviour | Test Type | Automated Command | File Exists | Status |
|--------|-----------|-----------|-------------------|-------------|--------|
| ANIM-01 | AckGate sweep/track/expiry/gated branch matrix; gated frame returns `gated=True`, sends nothing, skips framebuffer work; seq-wrap overwrite | unit | `uv run pytest tests/test_animation/test_flow.py tests/test_animation/test_animator.py -x` | ❌ W0 (test_flow.py; plans 04-02→04-04) | ⬜ pending |
| ANIM-01 | Deterministic gating end-to-end (emulator drops all acks via scenario `{45: 1.0}`; expiry reopens gate) | emulator | `uv run pytest tests/test_animation/test_animator.py -m emulator -x` | ❌ W0 (plan 04-02) | ⬜ pending |
| ANIM-02 | Probe flag baked once on `probe_template_index` (standard→0, large→last CopyFB, multizone/light→0); other templates' flags byte 0; `AnimatorStats` additive fields | unit + static | `uv run pytest tests/test_animation/test_packets.py tests/test_animation/test_animator.py -x && uv run pyright && uv run ruff check .` | partial W0 (plans 04-01/04-03/04-04) | ⬜ pending |
| ANIM-04 | Row-aligned 13×26 templates (7 Set64: 52×6+26 colours, y offsets 0,4,…,24, fb_index=1, row-aligned hsbk_start; + CopyFB); 16×8 shape unchanged | unit | `uv run pytest tests/test_animation/test_packets.py -x` | partial W0 (plans 04-01/04-03) | ⬜ pending |
| ANIM-04 | Large-tile streaming vs emulated 13×26 device (product 201); probe on CopyFB acked; gating engages under ack-drop | emulator | `uv run pytest tests/test_animation/ -m emulator -x` | ❌ W0 fixture (plan 04-02) | ⬜ pending |
| ANIM-03 | 0% concurrent-query loss + ≥85% delivered frames + operator visual verdict, Tiles @ 20 FPS | manual UAT + human checkpoint | `uat_ack_stream.py` (plan 04-05; runs in 04-06) | ❌ W0 | ⬜ pending |
| ANIM-04 | Same flow control on Ceiling Capsule 192.168.19.231; probe-attachment decision validated; power-on before visual runs; CopyFB ack RTT evidence | manual UAT + human checkpoint | `uat_ack_stream.py` (ceiling host; plan 04-07) | ❌ W0 | ⬜ pending |

Enumerated existing-test changes (6 mocked-socket, 3 emulator-loop, per 04-RESEARCH.md
§Validation Architecture) are scheduled in plan 04-02 and must not be weakened.

---

## Wave 0 Requirements

- [ ] `tests/test_animation/test_flow.py` — AckGate branch-matrix stubs (plan 04-02)
- [ ] `test_packets.py` row-aligned 13×26 geometry matrix + probe seam tests (plan 04-01)
- [ ] Shared `mock_udp_socket` fixture with `recvfrom_into` BlockingIOError default + `make_ack_datagram` helper + 13×26 emulator fixture (plan 04-02)
- [ ] `uat_ack_stream.py` harness with fixed 0/1/2 exit contract (plan 04-05)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual smoothness verdict under ack-gated streaming (Tiles) | ANIM-03 | Emulator cannot model real ack RTT under load; smoothness is an operator judgement | Plan 04-06 checkpoint: watch Tiles during the 3-round harness run |
| Geometry + smoothness verdict on Ceiling 13×26; CopyFB ack RTT compatible with limit-2/1 s expiry | ANIM-04 | Hardware-specific RTT + visual geometry check (row-aligned fix) | Plan 04-07 checkpoint: power on Capsule (set_power first), watch during run; verify no garbling |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
