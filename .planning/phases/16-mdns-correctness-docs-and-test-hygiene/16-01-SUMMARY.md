---
phase: 16-mdns-correctness-docs-and-test-hygiene
plan: 01
subsystem: mdns-discovery
tags: [mdns, dns-normalisation, fail-closed, pytest]

requires:
  - phase: none
    provides: n/a (first plan in phase, no dependencies)
provides:
  - "selected_address_for() normalises its owner argument through _normalise_dns_name(), closing the trailing-dot guard bypass"
  - "_owner_is_unusable() shared fail-closed predicate used by selected_address_for() and pending_targets()"
  - "A parametrised owner-form invariant test over records_for(), addresses_for() and selected_address_for()"
  - "pending_targets() guard-branch closure for the whole-sweep address-budget and byte-incomplete-AAAA-on-target terms"
affects: [16-02, 17]

actuals:
  tokens: 3900
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Public/private normalisation split: a public wrapper normalises once and delegates to a private method that must not renormalise, avoiding double-normalisation on a non-idempotent helper"
    - "Shared fail-closed guard predicate as a single branch-free `return (...)` boolean expression, so an added term contributes no new branch to the coverage-measured range"
    - "Branch-pinning a guard test with `rejection_counts` evidence alongside a paired control, so an empty-list assertion cannot be mistaken for a different early exit"

key-files:
  modified:
    - src/lifx/network/discovery/mdns/discovery.py
    - tests/test_network/test_mdns/test_discovery.py

key-decisions:
  - "D-01/D-03 implemented as planned: _owner_is_unusable() extracted as a six-term single-return predicate (adding a leading `not owner` term), and _selected_address_for_normalised() as the private delegate both internal callers now invoke directly"
  - "T-16-04 residual accepted as documented in the plan: a two-or-more-trailing-dot owner still diverges between guard key and lookup key, recorded in _normalise_dns_name()'s docstring and in this plan rather than fixed, per D-02"
  - "pending_targets()'s whole-sweep address-budget control required one extra address record beyond exactly filling the sweep budget, since the exhaustion check runs before the per-record counter increments and the loop alone only reaches the cap, never exceeds it"

requirements-completed: [MDNS-09]

coverage:
  - id: D1
    description: "selected_address_for() routes its owner argument through _normalise_dns_name(); a trailing-dot owner and its bare form reach the identical guard set and result"
    requirement: MDNS-09
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py::TestLifxRecordCacheOwnerNormalisation::test_trailing_dot_owner_is_refused_when_the_overflow_guard_fires"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py::TestLifxRecordCacheOwnerNormalisation::test_owner_forms_agree_across_the_three_public_lookups (parametrised x4)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Empty and DNS-root owner names are refused fail-closed even when an address record is genuinely cached under that key"
    requirement: MDNS-09
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py::TestLifxRecordCacheOwnerNormalisation::test_empty_and_bare_dot_owners_match_no_cached_entry"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py::TestLifxRecordCacheOwnerNormalisation::test_empty_and_root_owners_are_refused_even_when_an_address_is_cached"
        status: pass
    human_judgment: false
  - id: D3
    description: "An owner whose .lower() and .casefold() forms differ is driven into an owner-keyed guard on the casefolded form, not merely producing a successful lookup"
    requirement: MDNS-09
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py::TestLifxRecordCacheOwnerNormalisation::test_owner_whose_lower_and_casefold_differ_agrees_on_the_casefolded_form"
        status: pass
    human_judgment: false
  - id: D4
    description: "pending_targets() refuses a target the sweep-budget guard and the byte-incomplete-AAAA guard reject, each proven against a paired control"
    requirement: MDNS-09
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py::TestLifxRecordCachePendingTargets::test_pending_targets_refuses_a_target_the_address_guards_reject"
        status: pass
    human_judgment: false
  - id: D5
    description: "No fail-closed guard became fail-open and no public API surface changed; whole mDNS suite, default suite, pyright and ruff all pass"
    requirement: MDNS-09
    verification:
      - kind: integration
        ref: "shell: uv run --frozen pytest tests/test_network/test_mdns -q (391 passed)"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen pytest -q (4265 passed, 631 deselected)"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen pyright (0 errors)"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen ruff check . && uv run --frozen ruff format --check . (both clean)"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-09-07
status: complete
---

# Phase 16 Plan 01: mDNS owner-name normalisation Summary

**Closed MDNS-09 by routing `selected_address_for()`'s owner argument through `_normalise_dns_name()` via a public/private split, extracting a shared six-term fail-closed guard predicate used by both the selection path and `pending_targets()`.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-07T06:52:44Z
- **Completed:** 2026-09-07T07:04:59Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `selected_address_for()` is now a thin public wrapper that normalises its owner argument
  through `_normalise_dns_name()` and delegates to a new private
  `_selected_address_for_normalised()`, which applies no normalisation of its own. Both
  internal callers (the resolution loop and `pending_targets()`) call the private delegate
  directly on a target already normalised once, avoiding the double-normalisation trap a
  naive one-line fix would have introduced against `_normalise_dns_name()`'s non-idempotence.
- A new `_owner_is_unusable()` predicate is a single branch-free `return (...)` boolean
  expression carrying six terms (a new leading `not owner` plus the five pre-existing
  conditions), shared by `_selected_address_for_normalised()` and `pending_targets()`, so the
  next guard added lands in both places automatically.
- `_normalise_dns_name()`'s docstring now records that it strips exactly one trailing dot and
  is therefore not idempotent, without changing its body (D-02).
- A named regression test proves a trailing-dot owner and its bare form both return `None`
  when the per-owner overflow guard fires. A parametrised invariant test (4 forms: bare,
  trailing-dot, uppercase, mixed-case) proves `records_for()`, `addresses_for()` and
  `selected_address_for()` agree across all owner forms, with the trailing-dot selection
  compared by string equality against the bare form.
- Two additional tests close a real, previously-reachable bypass: an owner supplied as `""`
  or `"."` is refused fail-closed even when an address record genuinely sits under that key
  (proven by asserting the record is cached before asserting the refusal), and an owner whose
  `.lower()` and `.casefold()` forms differ is driven into an owner-keyed guard on the
  casefolded form, not merely proven by a lookup that would succeed regardless.
- `pending_targets()`'s remaining D-04 residual is closed: a targeted test drives the
  whole-sweep address-budget term and the byte-incomplete-AAAA-keyed-on-target term through
  `pending_targets()`, each paired with a control returning the pending target so an empty
  result cannot be mistaken for an earlier method exit.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end owner-name normalisation through the fail-closed boundary** -
   `c0d495d` (fix)
2. **Task 2: Owner-form invariant matrix and the pending_targets guard-branch close** -
   `a080f6a` (test)

## Files Created/Modified

- `src/lifx/network/discovery/mdns/discovery.py` - `_owner_is_unusable()` and
  `_selected_address_for_normalised()` added; `selected_address_for()` rewritten as a
  normalising public wrapper; both internal callers rewired to the private delegate;
  `pending_targets()`'s duplicated four-condition guard replaced with a call to the shared
  predicate; `_normalise_dns_name()` docstring gained a non-idempotence note (body unchanged)
- `tests/test_network/test_mdns/test_discovery.py` - new `TestLifxRecordCacheOwnerNormalisation`
  class with five test methods (one parametrised x4); new
  `test_pending_targets_refuses_a_target_the_address_guards_reject` added to
  `TestLifxRecordCachePendingTargets`; `DNS_TYPE_A`/`DNS_TYPE_AAAA` imports added

## Decisions Made

- Implemented D-01, D-02, D-03 and D-04 exactly as recorded in `16-CONTEXT.md` and refined by
  the cross-AI plan review incorporated into `16-01-PLAN.md`: the `not owner` term, the
  corrected T-16-04 wording (the delegate's own body applies no normalisation, but its lookup
  chain re-applies a no-op for every SPEC-covered form), and the branch-pinned
  `pending_targets()` test with `rejection_counts` evidence.
- The whole-sweep address-budget control in Task 2 needed one extra filler address record
  beyond exactly filling `_MAX_ADDRESS_RRS_PER_SWEEP`, mirroring the existing
  `test_sweep_address_budget_cannot_be_bypassed_across_owners` recipe: the exhaustion check
  runs before the per-record counter increments, so filling to the cap exactly never trips it.

## Deviations from Plan

None - plan executed exactly as written, including the plan's own pre-incorporated
cross-AI-review corrections (the `not owner` term, the corrected threat-model wording, and
the branch-pinned pending_targets test).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The post-fix `_LifxRecordCache` (public/private split, shared `_owner_is_unusable()`
  predicate) is ready for Phase 17's MDNS-10 work, which calls `selected_address_for()` from
  `.planning/scripts/ipv6_thread_probe.py` and must plan against this fixed cache, not the
  prior one.
- Plan 16-02 depends on this plan landing first: the codecov patch gate needs a changed `src/`
  range to score against, which only this plan supplies in the phase.
- The permanent multi-trailing-dot residual (D-02) remains documented in
  `_normalise_dns_name()`'s docstring and in `16-01-PLAN.md`; no SPEC acceptance criterion or
  edge-coverage row requires it closed, and no artefact of this plan claims the owner-form
  invariant holds for every dot form.
- No blockers.

## Self-Check: PASSED

- `test -e src/lifx/network/discovery/mdns/discovery.py` -> FOUND
- `test -e tests/test_network/test_mdns/test_discovery.py` -> FOUND
- `git log --oneline --all | grep -q c0d495d` -> FOUND
- `git log --oneline --all | grep -q a080f6a` -> FOUND
- `uv run --frozen pytest tests/test_network/test_mdns -q` -> 391 passed
- `uv run --frozen pytest -q` -> 4265 passed, 631 deselected
- `uv run --frozen pyright` -> 0 errors, 0 warnings
- `uv run --frozen ruff check .` -> All checks passed
- `uv run --frozen ruff format --check .` -> 284 files already formatted
- `git diff --name-only dedf699 HEAD` -> only `src/lifx/network/discovery/mdns/discovery.py`
  and `tests/test_network/test_mdns/test_discovery.py`

---
*Phase: 16-mdns-correctness-docs-and-test-hygiene*
*Completed: 2026-09-07*
