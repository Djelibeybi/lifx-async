---
phase: 16-mdns-correctness-docs-and-test-hygiene
plan: 03
subsystem: docs-and-test-contracts
tags: [documentation, agents-md, connectivity, pytest, contract-test]

requires:
  - phase: 16-02
    provides: "test_phase_contract.py post-DOCS-08 state (TestPhase14DiscoveryLinkingContract, _ADVANCED_USAGE_PATH, _MOVED_MDNS_LIMITATION_PHRASES already carrying the five replacement fragments)"
provides:
  - "Device.connectivity documented as a derived non-state property in docs/user-guide/advanced-usage.md, no longer listed among the state-backed Device Properties"
  - "A third Derived, not cached caching category in AGENTS.md's State Caching section, scoped to a correlated response only"
  - "Two file-split contract assertions (D-09) proving connectivity appears in exactly one of AGENTS.md's three caching categories, and is absent from the state-backed property list in advanced-usage.md"
  - "Two judged, gated dispositions recorded for ROADMAP criterion 2's wider 'repository or published guidance' wording: docs/api/devices.md's Connectivity section and AGENTS.md's Key Design Patterns index bullet"
affects: []

actuals:
  tokens: 1600
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Positional raw-text region assertion (index of one heading, then the next, then the following same-or-higher heading) in test_phase_contract.py, used instead of _normalised_prose() because that helper strips the heading lines the assertion's positions depend on"
    - "Marker-tuple-plus-loop assertion extended to a count-based exactly-one check (not membership) in tests/test_repository_guidance.py, so both the zero case and the duplicated case fail"

key-files:
  modified:
    - docs/user-guide/advanced-usage.md
    - AGENTS.md
    - tests/test_repository_guidance.py
    - tests/test_network/test_mdns/test_phase_contract.py

key-decisions:
  - "Chosen category label 'Derived, not cached', placed third (after never-cached-volatile, before the get_color() bullet), per 16-03-PLAN.md's exercised discretion — reads as the natural third member of the existing pair with a one-line diff."
  - "Scoped the new AGENTS.md bullet to 'the most recent correlated response' rather than 'the connection's most recent request outcome', per the plan's cross-AI-review-informed wording: src/lifx/network/connection.py:1075 assigns _thread_connection only after correlation validation, so a timeout, connection failure, or uncorrelated reply are all request outcomes that leave the value unchanged. Matches the property's own docstring at src/lifx/devices/base.py:2305-2318."
  - "docs/api/devices.md left unmodified. Verified it contains zero case-insensitive occurrences of cache/cached/caching in its Connectivity section, so there is no caching claim there for connectivity to be listed among (SPEC scopes requirement 2 to advanced-usage.md plus AGENTS.md only)."
  - "AGENTS.md's 'Key Design Patterns > State Caching: Device properties cache values...' index bullet left unmodified. It names no individual property and cannot list connectivity among anything; a reader following the pointer reaches the corrected three-category model at the section it points to."
  - "tests/test_network/test_mdns/test_phase_contract.py's new assertion reads raw file text (not _normalised_prose()), because that helper strips heading lines, and the assertion is positional (index of #### Device Properties, then the first ##### Non-State Properties after it, then the next #### heading) — exactly the pattern the file's own read_first-noted structure requires."
  - "Fixed an orphaned assertion line introduced by my own Edit during Task 2 (a pre-existing test_troubleshooting_never_recommends_taskgroup line got separated from its method when I inserted the new test after an incomplete old_string match). Restored it to its original method before the pre-existing suite was re-run green. Auto-fixed under deviation Rule 1 (self-introduced bug, caught and corrected within the same task, before any commit)."

requirements-completed: [DOCS-07]

coverage:
  - id: D1
    description: "Device.connectivity moved under the first ##### Non-State Properties heading in docs/user-guide/advanced-usage.md, absent from the state-backed #### Device Properties list above it"
    requirement: DOCS-07
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_phase_contract.py::TestPhase14DiscoveryLinkingContract::test_connectivity_is_not_listed_among_the_state_backed_device_properties"
        status: pass
      - kind: other
        ref: "shell: positional python3 region check over docs/user-guide/advanced-usage.md (CONNECTIVITY-RECLASSIFIED)"
        status: pass
    human_judgment: false
  - id: D2
    description: "AGENTS.md carries a third Derived, not cached caching category naming exactly connectivity, with no em dash and derivation scoped to a correlated response, matching src/lifx/network/connection.py:1075"
    requirement: DOCS-07
    verification:
      - kind: other
        ref: "shell: grep-based category count, em-dash and overbroad-derivation-claim checks over AGENTS.md (DERIVED-CATEGORY-OK, DERIVATION-WORDING-MATCHES-THE-IMPLEMENTATION, CATEGORY-COUNTS-OK)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A contract assertion proves connectivity appears in exactly one of the three AGENTS.md state-caching categories (count, not membership, so zero and duplicate both fail)"
    requirement: DOCS-07
    verification:
      - kind: unit
        ref: "tests/test_repository_guidance.py::TestStateCachingCategories::test_connectivity_appears_in_exactly_one_caching_category"
        status: pass
      - kind: unit
        ref: "tests/test_repository_guidance.py::TestStateCachingCategories::test_agents_md_declares_three_state_caching_categories"
        status: pass
    human_judgment: false
  - id: D4
    description: "docs/api/devices.md is unmodified and its Connectivity section still carries no caching claim; AGENTS.md retains ### State Caching and CLAUDE.md does not duplicate it"
    requirement: DOCS-07
    verification:
      - kind: other
        ref: "shell: python3 casefold scan of docs/api/devices.md's Connectivity section (API-REFERENCE-MAKES-NO-CACHING-CLAIM) and git diff emptiness check (API-REFERENCE-UNTOUCHED)"
        status: pass
      - kind: unit
        ref: "tests/test_repository_guidance.py::TestClaudeImportsAgents::test_claude_md_does_not_duplicate_shared_architecture_guidance"
        status: pass
    human_judgment: false
  - id: D5
    description: "The whole default suite, ruff, ruff format and pyright stay green; the plan's four declared files are the only ones changed"
    requirement: DOCS-07
    verification:
      - kind: integration
        ref: "shell: uv run --frozen pytest -q (4272 passed, 631 deselected)"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen ruff check . && uv run --frozen ruff format --check . && uv run --frozen pyright (all clean, 0 errors)"
        status: pass
      - kind: other
        ref: "shell: git diff --name-only 5f6285d HEAD lists exactly AGENTS.md, docs/user-guide/advanced-usage.md, tests/test_repository_guidance.py, tests/test_network/test_mdns/test_phase_contract.py"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-09-07
status: complete
---

# Phase 16 Plan 03: Connectivity reclassified as derived, not cached Summary

**Closed DOCS-07 by moving `Device.connectivity` out of the state-backed property list into `advanced-usage.md`'s Non-State Properties section, adding a third `Derived, not cached` caching category to `AGENTS.md` scoped precisely to a correlated response, and splitting the two proving contract assertions across `tests/test_repository_guidance.py` and `tests/test_network/test_mdns/test_phase_contract.py` per D-09.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-07T17:21:00+10:00 (approximate)
- **Completed:** 2026-09-07T17:33:00+10:00 (approximate)
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Moved the `Device.connectivity` bullet in `docs/user-guide/advanced-usage.md` from the
  state-backed `#### Device Properties` list to the first `##### Non-State Properties`
  heading, placed before the pre-existing `Device.model` bullet so the section reads in the
  same relative order.
- Added a third `**Derived, not cached** (computed on every read)` category to `AGENTS.md`'s
  `### State Caching` section, naming exactly `connectivity`. Verified against
  `src/lifx/network/connection.py:1075` and `src/lifx/devices/base.py:2304-2323` before
  writing the wording: the derivation is scoped to "the most recent correlated response," not
  the broader "request outcome," because `_thread_connection` is assigned only after
  correlation validation, so a timeout, connection failure, or uncorrelated reply all leave
  the cached value unchanged.
- Added `TestStateCachingCategories` to `tests/test_repository_guidance.py` (the `AGENTS.md`
  half of D-09): one test asserts all three category bullet markers are present, the other
  asserts `connectivity` appears in exactly one of the three bullet lines by count comparison
  (`== 1`), so both a zero-occurrence regression and a duplicated-category regression fail.
- Added `test_connectivity_is_not_listed_among_the_state_backed_device_properties` to
  `TestPhase14DiscoveryLinkingContract` in `tests/test_network/test_mdns/test_phase_contract.py`
  (the `advanced-usage.md` half of D-09): reads raw file text (not `_normalised_prose()`,
  which strips the heading lines the assertion's positions depend on), locates the region
  between `#### Device Properties` and the first following `##### Non-State Properties`
  heading and the region between that heading and the next `#### ` heading, and asserts
  `Device.connectivity` is absent from the first and present in the second.
- `src/lifx/devices/base.py` (the `connectivity` property implementation) is unmodified, as
  required: this is a documentation and classification change only.
- Recorded both judged dispositions for ROADMAP success criterion 2's wider "repository or
  published guidance" wording (see Decisions Made below), each gated by a Task 1 verify check
  rather than merely asserted.

## Task Commits

Each task was committed atomically:

1. **Task 1: Reclassify connectivity in both guidance surfaces** - `d5dc718` (docs)
2. **Task 2: The two contract assertions, split by the file each asserts on** - `56305b7` (test)

## Files Created/Modified

- `docs/user-guide/advanced-usage.md` - moved the `Device.connectivity` bullet under the
  first `##### Non-State Properties` heading, removed from the state-backed
  `#### Device Properties` list
- `AGENTS.md` - added a third `**Derived, not cached**` state-caching category naming
  `connectivity`, scoped to a correlated response
- `tests/test_repository_guidance.py` - added `_STATE_CACHING_CATEGORY_MARKERS`,
  `_bullet_line_for_marker()`, and `TestStateCachingCategories` with its two methods
- `tests/test_network/test_mdns/test_phase_contract.py` - added
  `test_connectivity_is_not_listed_among_the_state_backed_device_properties` to
  `TestPhase14DiscoveryLinkingContract`

## Decisions Made

- Implemented the plan's already-cross-AI-review-corrected wording exactly: "most recent
  correlated response" rather than "most recent request outcome," matching
  `connection.py:1075`'s correlation-gated assignment of `_thread_connection`.
- **Judged disposition 1 — `docs/api/devices.md:343-364`'s `### Connectivity` section.**
  NOT a caching listing. Verified: the section contains zero case-insensitive occurrences of
  `cache`, `cached` or `caching`, so there is no caching list in it for `connectivity` to be
  listed among. `## Device Properties` there is an API-reference container heading for
  per-property prose (sibling section: `### MAC Address`), not a state-backed property list.
  The section's own text already describes the value as derived. No change made; SPEC scopes
  requirement 2 to `advanced-usage.md` plus `AGENTS.md`, and correcting the heading name would
  collide with Phase 20's `docs/` pass. Gated by this plan's `API-REFERENCE-MAKES-NO-CACHING-CLAIM`
  and `API-REFERENCE-UNTOUCHED` verify checks, both of which pass.
- **Judged disposition 2 — `AGENTS.md:343`'s `**State Caching**: Device properties cache
  values to reduce network requests` bullet under `### Key Design Patterns`.** NOT a listing.
  It is a one-line index entry pointing at the `### State Caching` section, names no
  individual property, and therefore cannot list `connectivity` among anything. No change
  made; a reader following the pointer reaches the corrected three-category model at the
  section the third category was added to.
- Placed the new category third (after never-cached-volatile, before `get_color()`), per the
  plan's exercised discretion: reads as the natural third member of the existing pair, and
  the diff stays one inserted line.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Self-introduced orphaned assertion line during Task 2's Edit**
- **Found during:** Task 2 (adding the `advanced-usage.md` half of the contract)
- **Issue:** My `Edit` tool call's `old_string` match for inserting the new test method
  after `test_troubleshooting_never_recommends_taskgroup` did not capture that method's full
  original body (it had a second assertion line after the one I matched). The replacement
  left that second `assert "or asyncio.taskgroup\` — no extra coordination" not in prose`
  line orphaned after my new method, causing a `NameError: name 'prose' is not defined` when
  the test suite ran.
- **Fix:** Moved the orphaned assertion line back into
  `test_troubleshooting_never_recommends_taskgroup`, its original method, before my new test
  method.
- **Files modified:** `tests/test_network/test_mdns/test_phase_contract.py`
- **Verification:** `uv run --frozen pytest tests/test_repository_guidance.py
  tests/test_network/test_mdns/test_phase_contract.py -q` went from 1 failed/33 passed to 34
  passed after the fix.
- **Committed in:** `56305b7` (part of Task 2's single commit; the fix was applied before
  the commit, so no separate commit exists for it)

---

**Total deviations:** 1 auto-fixed (1 self-introduced bug, caught and corrected within the
same task before committing).
**Impact on plan:** None on the delivered scope or wording — the fix restored a pre-existing,
unrelated assertion to its correct location. No behavioural or documentation change resulted.

## Issues Encountered

None beyond the self-corrected editing mistake documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DOCS-07 is closed: `Device.connectivity` is documented as derived, not cached, in both
  `advanced-usage.md` and `AGENTS.md`, with both halves of the D-09 contract green.
- Both judged dispositions for ROADMAP success criterion 2's wider wording are recorded above
  with their gated verify checks, so verify-phase inherits the judgement rather than
  rediscovering it as an apparent gap.
- `src/lifx/devices/base.py` is untouched; no runtime behaviour changed.
- No blockers. Plan 16-04 (TEST-01) is file-disjoint from this plan's changes (this plan
  touched `tests/test_repository_guidance.py` and
  `tests/test_network/test_mdns/test_phase_contract.py`; 16-04's import sweep does not
  overlap these files' function-local-import surface in a way that would conflict, since
  both files already used module-scope imports throughout and this plan added no new
  function-local imports).

## Self-Check: PASSED

- `test -e docs/user-guide/advanced-usage.md` -> FOUND
- `test -e AGENTS.md` -> FOUND
- `test -e tests/test_repository_guidance.py` -> FOUND
- `test -e tests/test_network/test_mdns/test_phase_contract.py` -> FOUND
- `git log --oneline --all | grep -q d5dc718` -> FOUND
- `git log --oneline --all | grep -q 56305b7` -> FOUND
- `uv run --frozen pytest tests/test_repository_guidance.py tests/test_network/test_mdns/test_phase_contract.py -q` -> 34 passed
- `uv run --frozen pytest -q` -> 4272 passed, 631 deselected
- `uv run --frozen ruff check .` -> All checks passed
- `uv run --frozen ruff format --check .` -> 285 files already formatted
- `uv run --frozen pyright` -> 0 errors, 0 warnings, 0 info items
- `git diff --name-only 5f6285d HEAD` -> exactly AGENTS.md, docs/user-guide/advanced-usage.md,
  tests/test_repository_guidance.py, tests/test_network/test_mdns/test_phase_contract.py;
  `src/lifx/devices/base.py` and `docs/api/devices.md` both unmodified

---
*Phase: 16-mdns-correctness-docs-and-test-hygiene*
*Completed: 2026-09-07*
