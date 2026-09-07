---
phase: 16-mdns-correctness-docs-and-test-hygiene
plan: 02
subsystem: mdns-discovery-docs
tags: [mdns, docs, discovery, pytest, contract-test]

requires:
  - phase: 16-01
    provides: "Post-fix _LifxRecordCache (public/private normalisation split, shared _owner_is_unusable() predicate), the changed src/ range the codecov patch gate scores against"
provides:
  - "The mDNS discovery documentation states bounded discovery, proxy responses and testing limitations in terms a caller can act on, with the internal validation language removed from src/ and docs/"
  - "A corrected proxy-verification attribution: discover()'s mDNS candidates, not its UDP leg, must answer a correlated device request before being yielded"
  - "tests/test_docs_language.py, a repository-wide default-suite negative assertion guarding both the removed jargon and the false verification attribution"
affects: [20]

actuals:
  tokens: 2400
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Repository-wide prose contract as a plain default-suite test module (no opt-in marker), mirroring test_phase_contract.py's structural walk-and-assert shape but scanning raw file text instead of the .md-shaped _normalised_prose() helper, so Python comments and Markdown headings are also caught"
    - "Forbidden-phrase concatenation with a structural coverage test (test_forbidden_phrase_set_covers_both_concerns) proving neither of two independently-motivated phrase tuples can be silently dropped from the combined walk"

key-files:
  modified:
    - src/lifx/api.py
    - docs/user-guide/discovery.md
    - tests/test_network/test_mdns/test_phase_contract.py
  created:
    - tests/test_docs_language.py

key-decisions:
  - "Attributed proxy-response verification to discover()'s mDNS candidates (via _discover_verified_devices_mdns(), which requires a correlated Light.GetColor or Device.EchoRequest answer before yielding), not to discover()'s UDP leg. The original D-14 wording named the UDP leg as unicast-verified, which is false against src/lifx/api.py:1112 (the UDP leg consumes discover_devices_shared() results directly and verifies nothing); the plan's pre-incorporated cross-AI review correction was implemented as written."
  - "Dropped the 'Mesh scale is proven synthetically' sentence outright in both src/lifx/api.py and docs/user-guide/discovery.md rather than replacing it with a reworded scale claim (D-13), since the existing bounded-discovery paragraph already tells the caller what to conclude."
  - "The discover_mdns() docstring names the verification mechanism as belonging to discover() explicitly, not to discover_mdns() itself: discover_mdns() calls the unverified discover_devices_mdns() path (src/lifx/network/discovery/mdns/discovery.py:1609), while only discover()'s mDNS leg uses the verified _discover_verified_devices_mdns() path. Attributing the mechanism to the wrong function would have been a second false claim of the same shape the plan corrects."
  - "tests/test_docs_language.py scans raw file text (casefolded) rather than reusing test_phase_contract.py's _normalised_prose() helper, because that helper strips lines starting with '#' -- which would silently exempt Python comments under src/ and Markdown headings under docs/ from a contract meant to catch the phrase wherever it appears."
  - "docs/migration/mdns-low-level-api-7.0.0.md and docs/getting-started/quickstart.md were audited in full and left unchanged: neither carries 'proven synthetically'/'mesh scale' internal validation language, and neither contradicts the recast docs/user-guide/discovery.md on proxy responses or bounded-sweep claims. quickstart.md's query-model assertions (initial PTR, one-second/three-second retransmissions, bounded follow-ups) were unaffected since no edit was made."

requirements-completed: [DOCS-08]

coverage:
  - id: D1
    description: "docs/user-guide/discovery.md names bounded discovery, proxy responses and testing limitations in caller terms, with the five locked approved-phrase fragments present"
    requirement: DOCS-08
    verification:
      - kind: other
        ref: "shell: grep fragment checks over docs/user-guide/discovery.md (all five present)"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_mdns/test_phase_contract.py::TestPhase11SurfaceContract::test_public_guidance_uses_the_approved_limitation_phrases"
        status: pass
    human_judgment: false
  - id: D2
    description: "discover_mdns() docstring, docs/migration/mdns-low-level-api-7.0.0.md and docs/getting-started/quickstart.md carry no internal validation language and do not contradict discovery.md"
    requirement: DOCS-08
    verification:
      - kind: other
        ref: "shell: grep -ciE 'mesh scale|proven synthetically' over src/lifx/api.py (0 matches)"
        status: pass
      - kind: unit
        ref: "tests/test_docs_language.py::test_src_carries_no_internal_validation_language"
        status: pass
      - kind: unit
        ref: "tests/test_docs_language.py::test_docs_carry_no_internal_validation_language"
        status: pass
    human_judgment: false
  - id: D3
    description: "The proxy paragraph attributes correlated-device-request verification to discover()'s mDNS candidates, never to its UDP leg, and a repository-wide negative assertion enforces this"
    requirement: DOCS-08
    verification:
      - kind: other
        ref: "shell: grep -inE 'udp leg is (unicast-)?verified|unicast-verified udp' over src/, docs/, and test_phase_contract.py (0 matches)"
        status: pass
      - kind: unit
        ref: "tests/test_docs_language.py::test_src_carries_no_internal_validation_language (covers _FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES)"
        status: pass
      - kind: unit
        ref: "tests/test_docs_language.py::test_docs_carry_no_internal_validation_language (covers _FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both test_phase_contract.py phrase lists (approved_phrases and _MOVED_MDNS_LIMITATION_PHRASES) move to the replacement wording in the same commit as the prose, and the mDNS contract suite stays green"
    requirement: DOCS-08
    verification:
      - kind: integration
        ref: "shell: uv run --frozen pytest tests/test_network/test_mdns/test_phase_contract.py -q (23 passed)"
        status: pass
      - kind: other
        ref: "shell: git show --name-only HEAD~1 lists src/lifx/api.py, docs/user-guide/discovery.md and test_phase_contract.py together (SIMULTANEITY-HELD)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A repository-wide assertion proves the removed internal validation language and the false verification attribution appear nowhere under src/ or docs/, docs/changelog.md excluded by name and existing on disk, and this new module runs in the default suite alongside the mDNS contract suite"
    requirement: DOCS-08
    verification:
      - kind: unit
        ref: "tests/test_docs_language.py::test_generated_changelog_is_excluded_by_name"
        status: pass
      - kind: unit
        ref: "tests/test_docs_language.py::test_forbidden_phrase_set_covers_both_concerns"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen pytest -q (4269 passed, 631 deselected)"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen ruff check . && uv run --frozen ruff format --check . && uv run --frozen pyright (all clean, 0 errors)"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-09-07
status: complete
---

# Phase 16 Plan 02: mDNS discovery docs recast Summary

**Closed DOCS-08 by dropping the "mesh scale is proven synthetically" internal validation jargon from `discover_mdns()`'s docstring and `docs/user-guide/discovery.md`, adding caller-facing proxy-response prose correctly attributed to `discover()`'s verified mDNS leg, and adding a repository-wide `tests/test_docs_language.py` negative that also forbids the false UDP-leg verification claim the plan review found.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-07T17:01:00+10:00 (approximate)
- **Completed:** 2026-09-07T17:19:08+10:00
- **Tasks:** 2
- **Files modified:** 4 (3 modified, 1 created)

## Accomplishments

- Removed `Mesh scale is proven synthetically.` from both `src/lifx/api.py:1287` (the
  `discover_mdns()` docstring) and `docs/user-guide/discovery.md`'s `## Limitations` section,
  without replacing it with a reworded scale claim (D-13).
- Added a caller-facing proxy-response paragraph to `docs/user-guide/discovery.md`: a Thread
  border router advertises every device on its mesh, so an mDNS result proves an advertisement
  exists rather than that the device is currently reachable, and the next action is to confirm
  with a request or use `discover()`, whose mDNS candidates must answer a correlated device
  request before they are yielded. Verified this attribution against
  `src/lifx/api.py:1112` (UDP leg, unverified), `src/lifx/api.py:1125` and
  `src/lifx/network/discovery/mdns/discovery.py:1361` (mDNS leg, verified via a correlated
  request) before writing it.
- Updated the `discover_mdns()` docstring with a short caller-facing sentence carrying the same
  proxy point and naming the discovery guide as the fuller reference in plain prose (no relative
  markdown link, since the docstring renders into the generated API reference). Confirmed
  `discover_mdns()` itself calls the unverified `discover_devices_mdns()` path
  (`discovery.py:1609`), so the sentence attributes the verified mechanism to `discover()`
  explicitly rather than implying `discover_mdns()` performs it.
- Recast the fleet-specific Phase 14 paragraph into caller advice: behaviour on a large or
  congested network is not characterised by this documentation, so a caller should not size
  timeouts or retry policy from it (D-15).
- Moved both `tests/test_network/test_mdns/test_phase_contract.py` phrase lists
  (`approved_phrases` and `_MOVED_MDNS_LIMITATION_PHRASES`) to the five replacement fragments in
  the same commit as the prose edits, satisfying the D-12 simultaneity constraint.
- Created `tests/test_docs_language.py`, a plain default-suite module (no opt-in marker) that
  walks every `.py` under `src/` and every `.md` under `docs/` (excluding the generated
  `docs/changelog.md` by name) and asserts neither the removed internal validation language nor
  the false UDP-leg verification attribution ever reappears. A structural test proves both
  forbidden-phrase source tuples are non-empty and fully included in the combined walked set.
- Audited `docs/migration/mdns-low-level-api-7.0.0.md` and `docs/getting-started/quickstart.md`
  in full: neither required a change (see Decisions Made).

## Task Commits

Each task was committed atomically:

1. **Task 1: Move the prose and both phrase lists in one commit** - `ee73680` (docs)
2. **Task 2: Repository-wide prose contract and the remaining DOCS-08 surfaces** - `ea00074` (test)

## Files Created/Modified

- `src/lifx/api.py` - `discover_mdns()` docstring: removed the scale-claim sentence, added a
  proxy-response sentence attributing verification to `discover()`'s mDNS leg
- `docs/user-guide/discovery.md` - `## Limitations` section: removed the scale-claim sentence,
  added a new proxy-response paragraph and recast the fleet-specific paragraph into caller advice
- `tests/test_network/test_mdns/test_phase_contract.py` - moved both phrase lists
  (`approved_phrases`, `_MOVED_MDNS_LIMITATION_PHRASES`) from the deleted sentence to the five
  replacement fragments
- `tests/test_docs_language.py` - new module: `_FORBIDDEN_INTERNAL_VALIDATION_PHRASES`,
  `_FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES`, `_FORBIDDEN_PHRASES`, `_GENERATED_DOCS`, and
  four test functions

## Decisions Made

- Implemented D-10 through D-16 exactly as recorded in `16-CONTEXT.md` and refined by the
  cross-AI plan review incorporated into `16-02-PLAN.md`: the corrected D-14 verification
  attribution (proxy paragraph names `discover()`'s mDNS candidates, never the UDP leg), the
  fifth approved-phrase fragment (`answer a correlated device request`) locking that correction,
  and `_FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES` as the negative backstop.
- The `discover_mdns()` docstring's new sentence explicitly names `discover()` (not
  `discover_mdns()` itself) as the function whose mDNS candidates verify with a correlated
  request, since `discover_mdns()`'s own code path (`discover_devices_mdns()`) does not perform
  that verification. Attributing it to the wrong function would have shipped a second false
  claim of exactly the shape the plan corrects, so this distinction was checked against source
  before writing the sentence, rather than assumed from the plan's already-corrected wording.
- `docs/migration/mdns-low-level-api-7.0.0.md` audit outcome: no change. It documents
  `Device.connectivity` semantics and the low-level API removal, carries no
  "proven synthetically"/"mesh scale" language, and makes no claim about bounded-sweep coverage
  or proxy responses that would contradict the recast `discovery.md`.
- `docs/getting-started/quickstart.md` audit outcome: no change. Its mDNS alternative section
  states the initial-PTR/one-second/three-second query model and the bounded follow-up
  behaviour, carries no internal validation language, and makes no reachability or proxy claim.
  Left untouched, so its `_REQUIRED_QUERY_MODEL_PATHS` assertions in `test_phase_contract.py`
  remain satisfied by construction.
- `tests/test_docs_language.py` scans raw file text (casefolded), not `_normalised_prose()`,
  because that helper drops `#`-prefixed lines — which would exempt Python comments under `src/`
  and Markdown headings under `docs/` from a contract meant to catch the phrase everywhere.

## Deviations from Plan

None - plan executed exactly as written, including the plan's own pre-incorporated cross-AI
review corrections (the corrected D-14 attribution, the fifth approved-phrase fragment, and
`_FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES`). The one additional check performed beyond the
plan's literal text — confirming that `discover_mdns()` itself uses the unverified
`discover_devices_mdns()` path before attributing the verified mechanism to `discover()` in its
own docstring — is documented above as a decision, not a deviation: it is the same correctness
bar the plan's Task 1 action already required ("must not attribute unicast verification to
`discover()`'s UDP leg in any wording"), applied one function further to avoid a second
misattribution of the same shape.

## Issues Encountered

None. One implementation note: the first draft of the new proxy paragraph wrapped two of the
five locked fragments (`answer a correlated device request`, `size timeouts or retry policy`)
across a Markdown line break, which the plan's literal-grep verification commands (and this
plan's own line-wrapped-phrase risk) would have failed even though `_normalised_prose()`-based
test assertions would have passed. Rewrapped both sentences so each locked fragment sits on one
line before committing.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DOCS-08 is closed: `docs/user-guide/discovery.md` names bounded discovery, proxy responses and
  testing limitations in caller terms; no internal validation language or false verification
  attribution remains under `src/` or `docs/`, enforced by both the moved phrase lists and the
  new repository-wide negative.
- `tests/test_docs_language.py` is ready for Phase 20's DOCS-09 em-dash sweep to extend, per
  16-CONTEXT.md's deferred note; the module's docstring records this explicitly.
- No blockers. Plan 16-03 (DOCS-07) and 16-04 (TEST-01) are file-disjoint from this plan's
  changes.

## Self-Check: PASSED

- `test -e src/lifx/api.py` -> FOUND
- `test -e docs/user-guide/discovery.md` -> FOUND
- `test -e tests/test_network/test_mdns/test_phase_contract.py` -> FOUND
- `test -e tests/test_docs_language.py` -> FOUND
- `git log --oneline --all | grep -q ee73680` -> FOUND
- `git log --oneline --all | grep -q ea00074` -> FOUND
- `uv run --frozen pytest tests/test_docs_language.py tests/test_network/test_mdns/test_phase_contract.py -q` -> 27 passed
- `uv run --frozen pytest -q` -> 4269 passed, 631 deselected
- `uv run --frozen pyright` -> 0 errors, 0 warnings
- `uv run --frozen ruff check .` -> All checks passed
- `uv run --frozen ruff format --check .` -> 285 files already formatted
- `git diff --name-only dedf699 HEAD` -> no file under `tests/test_animation/`,
  `tests/test_theme/` or `tests/test_devices/test_multizone.py`; `docs/changelog.md` untouched

---
*Phase: 16-mdns-correctness-docs-and-test-hygiene*
*Completed: 2026-09-07*
