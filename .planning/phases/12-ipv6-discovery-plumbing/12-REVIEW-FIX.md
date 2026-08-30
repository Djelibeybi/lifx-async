---
phase: 12-ipv6-discovery-plumbing
fixed_at: 2026-08-30T05:18:33Z
review_path: .planning/phases/12-ipv6-discovery-plumbing/12-REVIEW.md
iteration: 3
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 12: Code Review Fix Report

**Fixed at:** 2026-08-30T05:18:33Z
**Source review:** `.planning/phases/12-ipv6-discovery-plumbing/12-REVIEW.md`
**Iteration:** 3

**Summary:**

- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-06: Non-service discovery lets an unusable source port suppress the valid responder

**Files modified:** `src/lifx/network/discovery.py`, `tests/test_network/test_discovery_errors.py`
**Commit:** `f357490`
**Status:** fixed: requires human verification
**Applied fix:** Select and validate the endpoint port before constructing a discovery response or mutating first-wins serial deduplication. `StateService` validates its advertised UDP port; all other State responses validate the datagram source port that callers receive. The adversarial `StateLabel` regression supplies an invalid-first and valid-second response for one synthetic serial and proves only the valid endpoint is yielded.

### CR-07: Closing a connection leaves requests alive to retransmit on the next session

**Files modified:** `src/lifx/network/connection.py`, `tests/test_network/test_connection.py`
**Commit:** `908d171`
**Status:** fixed: requires human verification
**Applied fix:** Close now increments the loop-agnostic session generation, deduplicates and drains each logical request queue, wakes it with a close sentinel, and detaches all old correlation mappings before teardown awaits. Request loops reject a stale generation before registration, transmission, retransmission, and response handling; cleanup removes only mappings still owned by that request. Parametrised GET and SET regressions prove both finish promptly with `LifxConnectionError` and cannot send through a subsequently reopened transport, while the existing cross-loop reopen and cancellation-cleanup tests remain green.

### CR-08: Animator send failures escape the typed boundary and poison ACK state

**Files modified:** `src/lifx/animation/animator.py`, `tests/test_animation/test_animator.py`
**Commit:** `0bda980`
**Status:** fixed: requires human verification
**Applied fix:** Each frame datagram is now sent inside an `OSError` conversion boundary before ACK tracking or sequence advancement. Repeated probe failures raise `LifxNetworkError` without consuming a sequence or creating phantom outstanding ACKs. A multi-packet large-tile regression proves successful earlier packets keep their sequence progression when the later probe fails, while the failed probe remains untracked.

## Verification

All verification ran in the isolated review-fix worktree at `.claude/worktrees/rf-12-23361-1788066618`, using the repository's existing uv environment and a writable temporary uv cache.

- Combined focused tests: `uv run --frozen pytest tests/test_network/test_discovery_errors.py tests/test_network/test_connection.py tests/test_animation/test_animator.py -q` — 143 passed.
- CR-06 module verification: 28 discovery-error tests passed.
- CR-07 module verification: 58 connection tests passed.
- CR-08 module verification: 57 animator tests passed.
- Ruff lint: `uv run --frozen ruff check .` passed.
- Ruff formatting: `uv run --frozen ruff format --check .` passed; 262 files were already formatted.
- Pyright: `uv run --frozen pyright` passed with 0 errors, 0 warnings, and 0 information messages.
- All three commits are GPG-signed with the configured project key and contain developer sign-off trailers.
- The full test suite was not run between fixes; the phase verifier remains responsible for full-suite verification.

---

_Fixed: 2026-08-30T05:18:33Z_
_Fixer: Codex (gsd-code-fixer)_
_Iteration: 3_
