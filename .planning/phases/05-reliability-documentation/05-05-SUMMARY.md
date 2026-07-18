---
phase: 05-reliability-documentation
plan: 05
subsystem: docs
tags: [docs, discovery, concurrency, animation, ceiling, faq, mkdocs, docstrings]

# Dependency graph
requires:
  - phase: 05-reliability-documentation
    provides: "05-01..05-04 documentation accuracy pass (discovery, streaming, correlation, CR-01 version-neutrality); 05-VERIFICATION.md truth #23 as the only open gap"
provides:
  - "Truth #23 closed: every discover_devices() discovery example in troubleshooting.md consumes the async generator via async-for, not await"
  - "Full D5-17 residual set closed: dead matrix API examples, false lock-serialisation claims, backoff wording, missing imports, fire-and-forget wave effect, CeilingLight/flow.py/tile_orientations omissions, healthy-networks qualifier, Australian English spelling"
  - "Three narrow, operator-authorised source docstring overrides (D5-18/D5-20/D5-21): connection.py Features bullet, api.py preset name, discovery.py create_device() Example async-for + None guard"
  - "docs/api/animation.md and docs/api/network.md hand-written prose corrected to the shipped ack-paced/correlation model, with every ::: mkdocstrings block byte-identical"
affects: [documentation, api-reference]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hand-written-prose-only editing inside mkdocstrings-fed API reference pages, with ::: directive blocks left absolutely fenced and verified via a diff-scope gate"
    - "Docstring Example blocks treated as narrowly overridable when they render into the published site and directly contradict source behaviour, while Returns:/Raises: sections stay fenced pending a separate behavioural-defect decision (API-01(d))"

key-files:
  created: []
  modified:
    - docs/user-guide/troubleshooting.md
    - docs/user-guide/ceiling-lights.md
    - docs/faq.md
    - docs/user-guide/advanced-usage.md
    - docs/architecture/overview.md
    - docs/user-guide/animation.md
    - docs/api/animation.md
    - docs/api/network.md
    - CLAUDE.md
    - src/lifx/network/connection.py
    - src/lifx/network/discovery.py
    - src/lifx/api.py

key-decisions:
  - "D5-16/D5-17/D5-18/D5-20/D5-21 all implemented exactly as pinned in 05-CONTEXT.md; no new decisions required during execution"
  - "connection.py:64's Features bullet wraps across two lines instead of the plan's literal single line — ruff's E501 line-length gate rejected the 116-character single-line form; the required grep-matched substring stays intact on one line"

requirements-completed: [DOCS-01, DOCS-02]

coverage:
  - id: D1
    description: "Truth #23 closed — troubleshooting.md's three discover_devices() examples (network-connectivity check, diagnose_discovery, partial-discovery recipe) collect via async-for instead of awaiting the async generator"
    requirement: "DOCS-01"
    verification:
      - kind: other
        ref: "grep -cF 'async for device in discover_devices(' docs/user-guide/troubleshooting.md == 3; grep -cF 'await discover_devices(' == 0; uv run zensical build exit 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "D5-17 residual set closed across ceiling-lights.md, faq.md, advanced-usage.md, overview.md — dead matrix APIs replaced with get_device_chain()/set_effect(FirmwareEffect.MORPH, speed=5.0), lock-serialisation claims replaced with the correlation model, escalating-schedule retry wording, missing Colors imports, wave_effect now awaits asyncio.gather, CeilingLight/tile_orientations additions, AU spelling"
    requirement: "DOCS-02"
    verification:
      - kind: other
        ref: "full grep gate set in 05-05-PLAN.md Task 2 acceptance_criteria (22 checks) — all pass; uv run zensical build exit 0 at 8-issue baseline"
        status: pass
    human_judgment: false
  - id: D3
    description: "D5-18/D5-20/D5-21 source overrides and docs/api hand-written prose closed — connection.py, api.py, discovery.py docstrings corrected; docs/api/animation.md and docs/api/network.md prose matches the shipped ack-paced/correlation model with ::: blocks byte-identical"
    requirement: "DOCS-02"
    verification:
      - kind: other
        ref: "full grep gate set in 05-05-PLAN.md Task 3 acceptance_criteria (28 checks) — all pass; git diff 7baf7dd..HEAD --stat -- src/ shows exactly 3 files with the documented shapes"
        status: pass
      - kind: unit
        ref: "uv run --frozen pytest -q"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-07-17
status: complete
---

# Phase 05 Plan 05: Second Gap Closure — Truth #23 and the Full D5-16..D5-21 Residual Set Summary

**Closed the last open 05-VERIFICATION.md gap (async-for vs await on `discover_devices()` in three troubleshooting.md examples) plus the full operator-opted residual set across eight docs pages and three narrow source-docstring overrides, with the docs build holding at its pre-existing 8-issue baseline and the full test suite green.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-07-17T07:12:55Z
- **Completed:** 2026-07-17T07:23:45Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Truth #23 closed: all three `discover_devices()` examples in troubleshooting.md (the network-connectivity check, `diagnose_discovery`, and the partial-discovery recipe) now collect via `async for ... in discover_devices(...): devices.append(device)`, matching the page's own correct pattern — the recommended partial-discovery recipe no longer raises `TypeError`
- Full D5-17 residual set closed: `ceiling-lights.md`'s MatrixLight Compatibility example now calls real APIs (`get_device_chain()`, `set_effect(effect_type=FirmwareEffect.MORPH, speed=5.0)`) instead of removed names, with speed correctly in seconds; the false lock-based request-serialisation claim is gone from `faq.md`, `advanced-usage.md`, and `CLAUDE.md`, replaced everywhere with the shipped receiver/correlation model; `overview.md`'s retry wording now says "escalating schedule" instead of "exponential backoff"; three `advanced-usage.md` examples gained missing `Colors` imports; `wave_effect` now awaits its colour-change tasks via `asyncio.gather` instead of discarding fire-and-forget tasks; `overview.md`'s Device layer prose gained `CeilingLight`/`ceiling.py` to match its own diagram; Australian English spelling corrected on every pinned line
- Three narrow, operator-authorised source docstring overrides (D5-18, D5-20/D5-21 — the only permitted `src/` edits): `connection.py:64`'s Features bullet, `api.py:620`'s preset name (`Colors.WARM` replacing the nonexistent `Colors.WARM_WHITE`), and `discovery.py`'s `create_device()` docstring Example (async-for collapse + `Device | None` guard) — the same docstring's `Returns:`/`Raises:` sections stay byte-identical, routed to `API-01(d)`
- `docs/api/animation.md`'s Direct UDP Delivery bullets now state the shipped ack-paced, latest-frame-wins, never-retried contract instead of the pre-flow-control claims; `docs/api/network.md`'s Device Discovery example and Concurrency section corrected to consume the async generator properly and state the correlation model — every `:::` mkdocstrings block in both files stays byte-identical

## Task Commits

1. **Task 1: Close truth #23 — rewrite the three awaited-generator discovery examples as async-for collection (D5-16) + troubleshooting.md companions (D5-17)** - `68ac301` (fix)
2. **Task 2: D5-17 residual closure across the four prose pages** - `c11da0e` (fix)
3. **Task 3: D5-18/D5-20 source overrides + docs/api hand-written prose + CLAUDE.md concurrency model** - `a32d234` (fix)

**Plan metadata:** (this commit, following)

## Files Created/Modified

- `docs/user-guide/troubleshooting.md` - Three discovery examples collect via async-for; measure_latency gains `import asyncio`; Optimisation-patterns link spelling
- `docs/user-guide/ceiling-lights.md` - MatrixLight Compatibility example uses real get_device_chain()/set_effect() API; tile_orientations added to inherited-state list
- `docs/faq.md` - Response Correlation bullet replaces the false lock claim; wake-tail entry gains the on-healthy-networks qualifier
- `docs/user-guide/advanced-usage.md` - Correlation-model claim; three missing Colors imports; wave_effect awaits asyncio.gather; AU headings (Performance Optimisation, Synchronised Multi-Device Effects)
- `docs/architecture/overview.md` - Escalating-schedule retry wording; CeilingLight/ceiling.py added to Device layer; AU spelling (Serialisation/Serialise/acknowledgement/Deserialise)
- `docs/user-guide/animation.md` - AU spelling (Normalise, vectorised)
- `docs/api/animation.md` - Direct UDP Delivery bullets state the shipped ack-paced contract; AU spelling (initialisation)
- `docs/api/network.md` - Device Discovery example and Concurrency section corrected; heading renamed to "Requests on a Single Connection"
- `CLAUDE.md` - Concurrency bullet matches shipped correlation model; flow.py added to Animation Layer list; AU spelling (Optimised)
- `src/lifx/network/connection.py` - DeviceConnection Features bullet describes the receiver/correlation model (one docstring line, wrapped across two for line length)
- `src/lifx/network/discovery.py` - create_device() docstring Example consumes the generator via async-for with a None guard; Returns:/Raises: byte-identical
- `src/lifx/api.py` - filter_by_group docstring example uses Colors.WARM (existing preset)

## Decisions Made

- D5-16/D5-17/D5-18/D5-20/D5-21 all implemented exactly as pinned in `05-CONTEXT.md` — no new decisions required during execution; every target value had been re-verified against shipped source at planning time and matched the codebase as found
- The create_device() docstring's `Returns:`/`Raises:` sections were left byte-identical as directed (routed to `API-01(d)`) — confirmed via `git diff 7baf7dd -- src/lifx/network/discovery.py` showing no touched lines matching `Returns:`, `Raises:`, or the three exception names

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Wrapped connection.py:64's Features bullet across two lines to satisfy ruff's line-length gate**
- **Found during:** Task 3 (source docstring overrides), first commit attempt
- **Issue:** The plan's literal single-line replacement for `connection.py:64` ("- Response correlation: a background receiver routes each reply to its request, so concurrent requests never mix") is 116 characters, exceeding the project's 88-character ruff `E501` limit — the pre-commit hook rejected the commit
- **Fix:** Wrapped the bullet across two lines, matching the sibling bullet's existing wrap style (`    - Response correlation: a background receiver routes each reply to its request,` / `      so concurrent requests never mix`), keeping the plan's must-have substring `"routes each reply to its request"` intact on a single line so the verification grep still matches
- **Files modified:** `src/lifx/network/connection.py`
- **Verification:** `uv run ruff check src/lifx/network/connection.py` passes; `grep -qF 'routes each reply to its request' src/lifx/network/connection.py` passes; `uv run pyright src/lifx/network/connection.py` clean; full pytest suite green
- **Committed in:** `a32d234` (Task 3 commit)
- **Note:** This makes `connection.py`'s diff shape 2 insertions/1 deletion (then 3+/2- after the fix) rather than the plan's literal 1 insertion/1 deletion. The plan's acceptance-criteria gate `git show --stat HEAD -- src/` expecting "connection.py (1 insertion, 1 deletion)" does not hold verbatim; every other src/ diff-shape gate (api.py 1+/1-, discovery.py 3+/2-) and every content-based gate (grep substrings, byte-identical Returns:/Raises:, the D5-19 fence) hold exactly as specified.

---

**Total deviations:** 1 auto-fixed (1 blocking — lint compliance)
**Impact on plan:** No scope creep; the single required content substring and every other verification gate hold. The deviation only widened one file's line-count diff by one line to satisfy a pre-existing project lint rule the plan's literal text did not account for.

## Issues Encountered

None beyond the line-length deviation above.

## Fence Compliance (D5-18/D5-20/D5-21 and widened D5-14)

- `git diff 7baf7dd..HEAD --stat -- src/` shows exactly three files: `src/lifx/api.py` (1+/1-), `src/lifx/network/connection.py` (3+/2- — widened by the line-wrap deviation above), `src/lifx/network/discovery.py` (3+/2-)
- `git diff 7baf7dd..HEAD --name-only -- docs/api docs/changelog.md` outputs exactly `docs/api/animation.md` and `docs/api/network.md`; `docs/changelog.md` untouched
- `git diff 7baf7dd..HEAD -- docs/api/network.md | grep -cE '^[+-]:::'` outputs 0 — all five `:::` mkdocstrings blocks byte-identical
- `git diff 7baf7dd -- src/lifx/network/discovery.py` contains no `+`/`-` line matching `Returns:`, `Raises:`, `LifxDeviceNotFoundError`, `LifxTimeoutError`, or `LifxProtocolError` — the create_device() docstring's Returns:/Raises: sections stay byte-identical, routed to `API-01(d)` in REQUIREMENTS.md (not an open finding)
- `git diff 7baf7dd..HEAD -- src/lifx/api.py` shows only the one preset-name line change at 620; lines 260-331, 515-557, 974-1016 (the D5-19-deferred behavioural defects) are untouched
- `git diff 7baf7dd..HEAD --name-only -- mkdocs.yml` is empty — no nav changes (D5-01)
- `grep -rlE 'Since v[0-9]' docs/ CLAUDE.md src/` matches zero files — no version attribution introduced (D5-12 holds)

## Edge-Probe Assumptions Carried Forward to Verification

Per the plan's spec-less edge probe, three flagged assumptions are surfaced (not resolved) for the verifier:

1. **DOCS-01 / idempotency** — every edit was an exact-string replacement gated by an exact-count grep whose target text no longer exists post-edit; re-running this plan is a detectable no-op (each `grep -qF` gate that checks for absence of the old text would now correctly report the edit is already applied).
2. **DOCS-01 / concurrency** — this was the only unexecuted plan in the phase (wave 4, all dependencies complete); tasks ran sequentially with one atomic signed commit per task, and each task independently ended with a green `uv run zensical build`, so no interruption occurred and the final state is clean and buildable.
3. **DOCS-02 / unclassified** — kept live per the plan's instruction that the verifier must independently probe the factual claims in every edited file rather than trust these truths. Low-risk observations noted at planning time and left untouched (cosmetic, no code changes): `overview.md`'s Discovery Process mermaid diagram (lines ~300-318) still shows an explicit `timeout=3.0` argument and a list-shaped outcome (a conceptual diagram, not copy-paste code — out of the truths-pinned scope); `docs/api/network.md`'s single-connection example imports `asyncio` without using it and pairs an "automatically closes" comment with an explicit `close()` call (pre-existing cosmetics, outside the two authorised D5-20 defect classes).

## Final Verification Results

- `uv run zensical build` exits 0, reporting exactly 8 issues (5× `api/effects.md`, 3× `api/index.md`) — the pre-existing baseline. No issue names any page edited by this plan; `docs/api/network.md` in particular is not in the baseline and did not join it.
- `uv run --frozen pytest -q` — **2618 passed, 12 deselected**, 96% coverage. The three docstring-only source edits (`connection.py:64`, `api.py:620`, `discovery.py`'s create_device Example) broke nothing.
- `uv run pyright src/lifx/network/connection.py src/lifx/network/discovery.py src/lifx/api.py` — 0 errors, 0 warnings.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DOCS-01 and DOCS-02 remain marked complete — this plan was an accuracy defect closure inside already-satisfied requirements, not new requirement scope; no REQUIREMENTS.md change is needed
- Phase 05 (reliability-documentation) is now fully executed: all five plans (05-01 through 05-05) have SUMMARY.md files, the truth #23 gap from `05-VERIFICATION.md` is closed, and the docs build/test suite are green
- Operator next step: re-run `/gsd-verify-work` for Phase 5 to produce a fresh verification report capturing this closure, then proceed to the v1.1 milestone-close TODO already logged in STATE.md (Phases 2/3/4 verification-status resolution)

---
*Phase: 05-reliability-documentation*
*Completed: 2026-07-17*

## Self-Check: PASSED

All three task commit hashes (68ac301, c11da0e, a32d234) found in `git log`.
All twelve modified files and this SUMMARY.md verified present on disk.
