---
phase: 10-land-the-ipv6-thread-branch
verified: 2026-08-27T23:31:00Z
status: passed
score: 13/13 must-haves verified
behavior_unverified: 0
overrides_applied: 0
next_action: "Phase 10 is verified on its phase branch and ready for the post-phase shipment workflow."
next_command: "/gsd-ship 10"
re_verification:
  previous_status: gaps_found
  previous_score: 14/19
  gaps_closed:
    - "D-26 corrected the SPEC failure: the branch must remain off main until Phase 10 ships."
    - "D-27 classifies patch coverage as advisory, with no fabricated override recorded."
    - "mDNS and UDP endpoints publish atomically and a racing close invalidates late completion."
    - "DeviceConnection open waiters retry after opener failure and failed transports are cleaned up."
    - "D-29 makes UAT restoration best-effort rather than a control or phase gate."
  gaps_remaining: []
  regressions: []
---

# Phase 10: Land the IPv6/Thread Branch Verification Report

**Status:** PASSED

**Verified goal:** The reconciled IPv6/Thread tree can connect, control and animate an IPv6-only
device and is ready to ship from its phase branch. It remains off `main` until shipment, as D-26
requires.

## Must-have verification

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | IPv6-only connect, read, control and Animator delivery work | Verified | `tests/test_api/test_ipv6_e2e.py` passed in the 3,731-test frozen suite |
| 2 | Every target-derived socket uses the shared family rule | Verified | `family_for()` and `wildcard_for()` consumers plus address and IPv6 end-to-end tests passed |
| 3 | Zone-less link-local input fails immediately at all public entry points | Verified | Address, device and API regression tests passed |
| 4 | mDNS failed/cancelled opens release owned sockets and remain reusable | Verified | 33 strict mDNS transport tests passed with resource warnings treated as errors |
| 5 | mDNS concurrent opens create one endpoint | Verified | Event-controlled concurrent-open ledger test passed |
| 6 | mDNS close wins against a late successful open | Verified | New successful open/close race test passed; endpoint closed and later reopen succeeded |
| 7 | UDP endpoint state is published only when protocol, transport and family are complete | Verified | `is_open` complete-state invariant and focused transport tests passed |
| 8 | UDP close wins against a late successful open | Verified | New successful open/close race test passed; late endpoint closed and later reopen succeeded |
| 9 | A DeviceConnection waiter cannot return success after opener failure | Verified | New failed-opener waiter test observed first failure, second attempt and an open connection |
| 10 | Full regression suite remains green | Verified | `uv run --frozen pytest -q`: 3,731 passed, 12 deselected |
| 11 | Static quality gates remain green | Verified | Ruff passed; Pyright reported 0 errors and 0 warnings |
| 12 | Hardware control evidence remains intact without rewriting UAT history | Verified | Existing `10-UAT-RESULTS.json` still records passed connect/control; Plan 10-09 did not modify it |
| 13 | The accepted tree remains off main before shipment | Verified | `git merge-base --is-ancestor HEAD main` exited 1 |

## Operator dispositions

- **Coverage:** the fail-open checker finding remains recorded. D-27 makes it advisory because it
  does not change functionality. No formal override was created; the operator can supply one if
  the release workflow actually requires it.
- **UAT restoration:** the multizone restoration limitation remains recorded. D-29 makes
  restoration best-effort and non-gating; connect/control evidence remains the UAT contract.
- **Transport lifecycle:** CR-02, CR-03 and WR-01 were functional blockers and are fixed by Plan
  10-09.

## Scope and deferred work

The deeper mDNS cache/provenance warnings remain visible in `10-REVIEW.md` and belong to the mDNS
hardening work rather than this transport-landing phase. Phase 11 owns mDNS hardening, Phase 12
owns valid IPv6 targeted discovery, Phase 13 owns merged discovery, and Phase 14 owns Thread
streaming measurements.

## Verdict

Phase 10 meets the rewritten SPEC with no functional gap and no applied override. It is verified
and ready for `/gsd-ship 10`. That shipment workflow, not execute-phase, owns the merge to `main`.
