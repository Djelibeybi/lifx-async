---
phase: 11-mdns-hardening
fixed_at: 2026-08-29T01:41:07Z
review_path: .planning/phases/11-mdns-hardening/11-REVIEW.md
iteration: 3
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 11: Code Review Fix Report

**Fixed at:** 2026-08-29T01:41:07Z
**Source review:** `.planning/phases/11-mdns-hardening/11-REVIEW.md`
**Iteration:** 3

**Summary:**

- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### CR-04: The schema consumer accepts the raw serial as `library_head`

**Status:** fixed: requires human verification
**Files modified:** `scripts/ipv6_thread_probe.py`, `tests/test_scripts/test_ipv6_thread_probe.py`
**Commit:** ea452ff
**Applied fix:** The Phase 11 schema-v2 consumer now normalises the transient selected serial and recursively rejects it in every string anywhere in the record tree, including dictionary keys, nested dictionary values, lists, aliases, and `library_head`. This privacy scan runs before field validation and therefore protects `_write_uat_record()` before it creates the output path. Focused regressions prove both direct validation and writing reject exact, mixed-case, and separator-formatted serial content outside `device_alias`, while a separate malformed non-sensitive `library_head` regression proves field-specific structural validation remains active.

## Cumulative Phase 11 Review Fixes

- **CR-01:** usable-address-aware bounded mDNS follow-up — `a03db50`
- **CR-02:** full multizone capture/restoration, corrected to the capability-aware public setter — `c4b4b22`, `f3632e0`
- **CR-03:** unsuccessful restoration forces a non-zero process status — `a0ec114`
- **CR-04:** sanitised evidence schema, hardened aliases, and complete-record raw-serial rejection — `3126269`, `3243d02`, `ea452ff`
- **CR-05:** separate Phase 11 schema-v2 producer/consumer contract — `6ec5bae`
- **WR-01:** DNS query packets rejected before counters and cache mutation — `f9af104`

## Verification

Verification ran in the isolated worktree at `.claude/worktrees/gsd-reviewfix-11-iter2`.

- Focused probe regressions: `115 passed`
- Combined mDNS/probe regressions: `333 passed`
- Full pytest suite: `3985 passed, 12 deselected` with seven existing `receive_many` deprecation warnings
- Ruff format check: passed for all four owned files
- Ruff check: passed for all four owned files
- Project-wide Pyright: `0 errors, 0 warnings, 0 information messages`
- GPG verification: the iteration-3 commit has a good signature from the configured project key
- Signed pre-commit hooks: passed for the atomic fix commit

## Skipped Issues

None — the sole current finding was fixed.

---

_Fixed: 2026-08-29T01:41:07Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 3_
