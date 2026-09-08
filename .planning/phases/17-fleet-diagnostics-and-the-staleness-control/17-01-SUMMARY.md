---
phase: 17-fleet-diagnostics-and-the-staleness-control
plan: 01
subsystem: diagnostics
tags: [mdns, ipv6, thread, dataclass, pyright, tooling]

requires:
  - phase: 16-mdns-correctness-docs-and-test-hygiene
    provides: "_owner_is_unusable() shared fail-closed guard and idempotent _normalise_dns_name(), both preconditions this plan's owner-normalisation and refused-state logic build on"
provides:
  - "Typed _InstanceView dataclass replacing the probe's untyped list[tuple[str, dict[str, object]]] return"
  - "Five explicit address-selection states (selected, fallback, refused, absent, no-target), with refused and absent rendered as two distinct CHOSEN messages instead of one collapsed 'pending address records' line"
  - "The refused message names the record count and classifies each record"
  - "Owner normalisation moved to a single _normalise_dns_name() call site in _instance_view(), replacing the probe's own .lower()"
  - "An unused packet-source fallback is named on a refused or absent instance instead of silently discarded"
  - "The dead linklocal_chosen counter, its WHY branch, its summary line and the unreachable is_reachable_choice() warning are deleted; the predicate is renamed to _has_routable_scope with both live call sites preserved"
  - "A malformed TXT payload marks one field and lets the run complete over the remaining instances instead of raising"
  - "The non-list AAAA runtime check is eliminated by construction (aaaa: tuple[str, ...]) and the elimination is recorded rather than re-armed as a branch"
affects: [17-02-fleet-diagnostics-and-the-staleness-control]

actuals:
  tokens: 6415
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Typed dataclass replacing an untyped dict/tuple return to eliminate isinstance-narrowing asserts by construction, following the existing TargetNotFound/TargetOutcome precedent in the same file"
    - "Pure rendering function (_non_resolving_lines) separated from report_records() so distinct output states are assertable without capturing stdout"

key-files:
  created: []
  modified:
    - .planning/scripts/ipv6_thread_probe.py
    - .planning/scripts/tests/test_ipv6_thread_probe.py

key-decisions:
  - "Module-level string constants (_REFUSED_ADDRESS_TAIL, _FALLBACK_MSG, _MALFORMED_TXT_MSG) hold each new fixed message tail on one physical source line, so the grep-checkable phrases the plan's acceptance criteria require stay contiguous under ruff's 88-character line limit rather than being split by an f-string line wrap"
  - "The dead link-local WHY branch, its counter and the connectivity warning were removed together in Task 3 as the plan specified, rather than folding them into Task 1 or 2, keeping each task's commit scoped to what its own tests exercise"

requirements-completed: [MDNS-10]

coverage:
  - id: D1
    description: "The probe distinguishes the refused state (cached-but-unusable address records) from the absent state (nothing cached) with two different CHOSEN messages, the refused message naming the record count and classifying each record"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestSyntheticCacheReporting::test_instance_view_reports_refused_when_cached_addresses_yield_no_selection"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestSyntheticCacheReporting::test_instance_view_reports_absent_when_no_address_record_is_cached"
        status: pass
    human_judgment: false
  - id: D2
    description: "The view's target field carries the single normalised owner (_normalise_dns_name()) rather than a .lower()ed near-miss, so the probe no longer depends on downstream lookups normalising on its behalf"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestSyntheticCacheReporting::test_instance_view_keys_addresses_and_selection_on_the_same_normalised_owner"
        status: pass
    human_judgment: false
  - id: D3
    description: "A refused or absent instance with a usable packet-source fallback states that the fallback exists and was not used, instead of silently discarding it"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestSyntheticCacheReporting::test_instance_view_names_an_unused_fallback_when_cached_addresses_are_refused"
        status: pass
    human_judgment: false
  - id: D4
    description: "The unreachable linklocal_chosen counter, its WHY branch, its summary line and the unreachable is_reachable_choice() warning are deleted; the predicate is renamed to _has_routable_scope with its two live call sites (stage_connect, _select_target) preserved and their existing test unedited and green"
    requirement: "MDNS-10"
    verification:
      - kind: other
        ref: "grep -n 'linklocal_chosen\\|is_reachable_choice' .planning/scripts/ipv6_thread_probe.py (returns nothing)"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestSelectTarget::test_returns_not_found_for_a_zoneless_link_local_address"
        status: pass
    human_judgment: false
  - id: D5
    description: "A malformed TXT payload marks the TXT field once, prints the instance's remaining well-formed fields, and lets report_records() continue to the next instance instead of raising; a resolved selection state with no usable chosen address renders through the non-resolving states rather than asserting"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestSyntheticCacheReporting::test_instance_view_marks_a_malformed_txt_and_keeps_the_remaining_instances"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestSyntheticCacheReporting::test_non_resolving_lines_marks_a_missing_chosen_address"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestSyntheticCacheReporting::test_report_records_completes_over_a_malformed_middle_instance"
        status: pass
    human_judgment: false
  - id: D6
    description: "The non-list AAAA runtime check is eliminated by construction (_InstanceView.aaaa: tuple[str, ...], built only inside _instance_view()) rather than re-armed as a runtime branch, and the elimination is recorded in this SUMMARY's Eliminated by construction section"
    requirement: "MDNS-10"
    verification:
      - kind: other
        ref: "grep -c 'aaaa: tuple\\[str, \\.\\.\\.\\]' .planning/scripts/ipv6_thread_probe.py (returns 1) plus ## Eliminated by construction section below"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 1: Refused-vs-absent probe reporting, owner normalisation, and a survivable malformed instance Summary

**`_instance_view()` now returns a typed `_InstanceView` with five explicit address-selection states, the refused and absent cases render as two distinct CHOSEN messages instead of one collapsed line, and a malformed TXT payload no longer ends the whole diagnostic run.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-08T14:03:00+10:00
- **Completed:** 2026-09-08T14:17:25+10:00
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Replaced `_instance_view()`'s untyped `list[tuple[str, dict[str, object]]]` return with a typed, frozen `_InstanceView` dataclass carrying a `Literal["selected", "fallback", "refused", "absent", "no-target"]` `selection` field, following the existing `TargetNotFound`/`TargetOutcome` precedent in the same file
- Added `_non_resolving_lines()`, a pure renderer that produces distinct CHOSEN text for the refused, absent and no-target states, and marks a `chosen`-missing resolved state instead of raising, so `report_records()` narrows through a bound local rather than a removed `assert isinstance(chosen, str)`
- Moved owner normalisation to the single `_normalise_dns_name()` call inside `_instance_view()`, replacing the probe's own `.lower()`, so `view.target` carries the exact key the cache computes rather than a near-miss of it
- Named an unused packet-source fallback on a refused or absent instance, and split the summary block's counts into `cached but no usable address` and `awaiting address records`, replacing the `pending_targets()` dump
- Deleted the unreachable `linklocal_chosen` counter, its WHY branch, its summary line and the unreachable `is_reachable_choice()` connectivity warning; renamed the predicate to `_has_routable_scope()` and preserved its two live call sites in `stage_connect()` and `_select_target()`
- Replaced the bare `assert isinstance(txt, TxtData)` with a rendered marker for a TXT owner whose payload did not parse, so `report_records()` survives a malformed middle instance and completes over the remaining ones
- Added seven new tooling tests to `TestSyntheticCacheReporting`, all passing, with the four red-phase failures recorded below before each corresponding source change landed

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end typed instance view carrying five explicit selection states** - `66e9765` (feat)
2. **Task 2: Single owner-normalisation site, the unused-fallback statement, and the split summary counts** - `b64f157` (fix)
3. **Task 3: Remove the unreachable link-local counter and warning, rename the zone-scope predicate, and make a malformed instance survivable** - `1d58629` (fix)

_Note: each task's commit bundles its production edit and its tests together, following D-08's TDD structure rather than separate test/feat commits._

## Files Created/Modified

- `.planning/scripts/ipv6_thread_probe.py` - Typed `_InstanceView`, `_non_resolving_lines()`, single-site owner normalisation, split summary counts, dead-code removal, `_has_routable_scope()` rename, malformed-TXT marker
- `.planning/scripts/tests/test_ipv6_thread_probe.py` - Seven new `TestSyntheticCacheReporting` tests plus migration of the one pre-existing dict-subscript consumer test to attribute access

## Decisions Made

- Held each new fixed message tail (the refused-record tail, the unused-fallback statement, the malformed-TXT marker) in its own module-level string constant, so the exact grep-checkable phrase stays on one physical source line rather than being wrapped across lines by ruff's 88-character limit, which would have broken every acceptance criterion phrased as a literal contiguous substring
- Kept the dead-code removal (Task 3) separate from the typed-view migration (Task 1) and the normalisation/summary changes (Task 2), exactly as the plan specified, so each commit's tests exercise only what that commit changed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `.planning/scripts/ipv6_thread_probe.py` and its test suite are ready for `17-02-PLAN.md`, which adds the opt-in `--alias-map` redaction flag to the same file
- MDNS-10 is not yet fully satisfied at the requirement level: `17-02-PLAN.md` and `17-03-PLAN.md` also declare it, and `requirements.mark-complete` will hold the checkbox open until all three plans in this phase have a `*-SUMMARY.md`
- No blockers. All verification gates (pytest, pyright, ruff check, ruff format, the protected-path grep) pass on the current tree

## Red phase

Both tests were written before `_instance_view()` was changed, then run against the
pre-change source with:

```
uv run --frozen pytest ".planning/scripts/tests/test_ipv6_thread_probe.py::TestSyntheticCacheReporting" -q --no-cov -p no:cacheprovider
```

Summary line: `2 failed, 1 passed, 2 retried in 0.22s`

`test_instance_view_reports_refused_when_cached_addresses_yield_no_selection` failed with:

```
AttributeError: 'tuple' object has no attribute 'selection'
```

`test_instance_view_reports_absent_when_no_address_record_is_cached` failed with:

```
AttributeError: 'tuple' object has no attribute 'selection'
```

Both fail on the `view.selection` read because the pre-change `_instance_view()` still
returns `list[tuple[str, dict[str, object]]]`, so `view` is a plain tuple with no
`selection` attribute at all. This is the recorded pre-change failure AC-01 and AC-02
require.

### Task 2's red phase (normalised-owner and unused-fallback tests)

Task 1 was already committed by the time Task 2's two new tests were run, so
`_instance_view()` already returned the typed `_InstanceView` dataclass Task 1 introduced;
what Task 2 changes is `_instance_view()`'s `srv.target.lower()` call and
`_non_resolving_lines()`'s refused/absent arms, not the dataclass shape itself. Both tests
were run before those two changes with the same command as above (scoped to
`TestSyntheticCacheReporting`), summary line: `2 failed, 3 passed, 2 retried in 0.21s`.

`test_instance_view_keys_addresses_and_selection_on_the_same_normalised_owner` failed on
its first assertion, the `view.target` read specifically, not on the `addresses` or
`chosen` assertions that follow it (AC-04):

```
AssertionError: assert 'synthetic-host.local.' == 'synthetic-host.local'

- synthetic-host.local
+ synthetic-host.local.
?                     +
```

`test_instance_view_names_an_unused_fallback_when_cached_addresses_are_refused` failed on
its final assertion, that `_non_resolving_lines()` names an unused fallback:

```
AssertionError: assert False
 +  where False = any(<generator object ...>)
```

Neither test's failure originates from an `AttributeError` on `view.target`, because by
this point in the plan `_InstanceView` already exists as a dataclass (Task 1 landed
first); the pre-change state Task 2 tests against is "dataclass in place, but the target
is still `.lower()`ed and the refused/absent renderer is still silent about an unused
fallback", not "view is still a dict". Recorded here as what actually happened, per the
same principle Task 1's red phase states explicitly.

### Task 3's red phase (malformed-instance smoke test)

`test_report_records_completes_over_a_malformed_middle_instance` was written and run
before the bare `assert isinstance(txt, TxtData)` was removed from `report_records()`:

```
uv run --frozen pytest ".planning/scripts/tests/test_ipv6_thread_probe.py::TestSyntheticCacheReporting" -q --no-cov -p no:cacheprovider
```

Summary line: `1 failed, 7 passed, 1 retried in 0.11s`

`test_report_records_completes_over_a_malformed_middle_instance` failed with:

```
AssertionError
```

raised from inside `report_records()` at the bare `assert isinstance(txt, TxtData)`, after
printing the first (well-formed) instance's block and reaching the second (malformed)
instance — exactly the "run ends at the first malformed instance" defect R3 exists to fix.
This is the recorded pre-change failure AC-08 requires.

The plan's other two Task 3 tests,
`test_instance_view_marks_a_malformed_txt_and_keeps_the_remaining_instances` and
`test_non_resolving_lines_marks_a_missing_chosen_address`, both passed in this same run
against the pre-change source. `_instance_view()`'s TXT filter and `_non_resolving_lines()`'s
missing-chosen marker were already in place from Task 1; only `report_records()`'s bare
assert still terminated the run at a malformed instance, which is exactly what the smoke
test isolates.

## Eliminated by construction

SPEC amendment A6 splits R3's three original bare assertions by whether they can still
occur once `_InstanceView` is typed. Two remain reachable and are handled at run time (the
TXT-payload marker and the missing-chosen marker documented above). The third, the bare
`assert isinstance(aaaa_ips, list)` that used to sit inside `report_records()`'s
per-instance loop, is eliminated by construction rather than re-armed as a runtime branch.

`_InstanceView.aaaa` is declared `tuple[str, ...]`, never `list[str] | None` or any other
optional/union shape that would need a runtime `isinstance` check before use. It is built
inside `_instance_view()`, and only there: `tuple(aaaa_values)`, where `aaaa_values` is
itself constructed inside the same function from `cache.records_for(target or "", DNS_TYPE_AAAA)`
filtered through `isinstance(record.parsed_data, str)`. No other code path constructs an
`_InstanceView`, and a frozen dataclass gives every field exactly the type its annotation
declares, so no runtime value reaching `report_records()` through `view.aaaa` can ever be a
non-list (or any other non-`tuple[str, ...]`) shape. There is nothing left to narrow.

No runtime branch replaces the deleted assert, and none should be added later. Re-adding an
`isinstance` check for a value the type system already forbids from ever taking the wrong
shape would recreate exactly the class of dead code R2 deletes three lines away in this
same plan (the unreachable `linklocal_chosen` counter and its warning): a branch that can
never execute, uncovered by the tooling coverage this file deliberately sits outside of,
and indistinguishable from real defensive code to a later reader. `17-CONTEXT.md` D-05
records that converting an unreachable guard into a branch was already rejected on that
same ground, for the same reason.

---
*Phase: 17-fleet-diagnostics-and-the-staleness-control*
*Completed: 2026-09-08*

## Self-Check: PASSED

- `.planning/scripts/ipv6_thread_probe.py` — FOUND
- `.planning/scripts/tests/test_ipv6_thread_probe.py` — FOUND
- Commit `66e9765` — FOUND
- Commit `b64f157` — FOUND
- Commit `1d58629` — FOUND
