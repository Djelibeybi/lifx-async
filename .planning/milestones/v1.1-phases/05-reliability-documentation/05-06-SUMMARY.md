---
phase: 05-reliability-documentation
plan: 06
subsystem: docs
tags: [mkdocstrings, zensical, docstrings, mdns, ci]

requires:
  - phase: 05-reliability-documentation (plans 01-05)
    provides: user-guide/architecture/API reference prose that this plan corrected
provides:
  - Honest direct-connection guidance (quickstart.md, overview.md) distinguishing the
    unicast-discovery-round-trip IP-only path from the genuine zero-discovery serial+IP path
  - Operator-agreed animation.md Performance Characteristics lead-in (verbatim text)
  - De-jargoned rendered docstrings across connection.py, discovery.py, animator.py,
    packets.py — no Photons/Glowup/wall-time lineage vocabulary, no planning IDs, no
    tuning constants, with every removed ID demoted to a `# Traceability` comment
  - Zero missing-blank-line run-on paragraphs across every mkdocstrings-rendered docstring
    (23 -> 0)
  - Rendered mDNS public API (discover_mdns, discover_lifx_services, LifxServiceRecord) on
    the pages docs/api/index.md always linked
  - `uv run zensical build --strict` exits 0 with zero warnings; CI gates on --strict
affects: [docs, ci]

tech-stack:
  added: []
  patterns:
    - "Traceability demotion: internal planning IDs removed from rendered prose survive as
       `# Traceability:` comments immediately above the affected definition, never deleted"
    - "AST + importlib target-derived docstring sweeps (vocabulary, blank-line, tuning-constant)
       scoped live from `grep -rh '^::: ' docs/api/*.md`, so the audit surface tracks the ::: list
       automatically instead of a hard-coded file set"

key-files:
  created: []
  modified:
    - docs/getting-started/quickstart.md
    - docs/architecture/overview.md
    - docs/api/animation.md
    - docs/api/effects.md
    - docs/api/high-level.md
    - docs/api/network.md
    - .github/workflows/docs.yml
    - src/lifx/network/connection.py
    - src/lifx/network/discovery.py
    - src/lifx/animation/animator.py
    - src/lifx/animation/packets.py
    - src/lifx/animation/orientation.py
    - src/lifx/api.py
    - src/lifx/color.py
    - src/lifx/devices/base.py
    - src/lifx/devices/ceiling.py
    - src/lifx/devices/light.py
    - src/lifx/devices/matrix.py
    - src/lifx/devices/multizone.py
    - src/lifx/effects/pulse.py
    - src/lifx/protocol/base.py
    - src/lifx/protocol/generator.py

key-decisions:
  - "G-05-2 fixed as a doc-page-only change: from_ip()'s docstring in base.py is not a
     falsehood (it never claims 'no discovery') and stays untouched; only quickstart.md and
     overview.md prose changed"
  - "G-05-3 used the operator's agreed_text verbatim ('characteristics', 'expected'), with
     bullets 1-2 left byte-identical"
  - "G-05-5/G-05-6 demoted every planning ID and design-lineage reference from rendered
     docstrings to new `# Traceability` comments rather than deleting them outright"
  - "G-05-7 rendered the three missing mDNS ::: targets (discover_mdns, discover_lifx_services,
     LifxServiceRecord) rather than removing the dead links from api/index.md, which itself
     received zero edits"
  - "D5-23's --strict gate inversion applied to both CI build invocations in docs.yml so the
     zero-warning class cannot silently regress to a new baseline"

requirements-completed: [DOCS-01, DOCS-02]

coverage:
  - id: D1
    description: "quickstart.md and overview.md no longer claim IP-only connection skips
      discovery; the serial+IP zero-discovery path is documented per the docs/index.md
      precedent (G-05-2)"
    requirement: "DOCS-01"
    verification:
      - kind: unit
        ref: "task 1 automated verify block (grep gates) + uv run zensical build"
        status: pass
    human_judgment: false
  - id: D2
    description: "docs/api/animation.md's Performance Characteristics lead-in matches the
      operator's agreed verbatim text with 'expected' drop framing (G-05-3)"
    requirement: "DOCS-02"
    verification:
      - kind: unit
        ref: "task 1 automated verify block (grep gates)"
        status: pass
    human_judgment: false
  - id: D3
    description: "docs/api/effects.md's five unresolved-link warnings closed by backticking
      type annotations; nothing else on the page changed (G-05-7a)"
    requirement: "DOCS-02"
    verification:
      - kind: unit
        ref: "task 1 automated verify block + uv run zensical build ('3 issues found', no
          effects.md warnings)"
        status: pass
    human_judgment: false
  - id: D4
    description: "connection.py and discovery.py rendered docstrings speak plain reader
      vocabulary matching overview.md:150's wording; every planning ID demoted to a
      Traceability comment (G-05-5, G-05-6 network-layer share)"
    requirement: "DOCS-02"
    verification:
      - kind: unit
        ref: "task 2 automated verify block (grep gates, AST vocabulary scan) + uv run
          pytest tests/test_network/ -q"
        status: pass
    human_judgment: false
  - id: D5
    description: "Animator/AnimatorStats/send_frame/probe_template_index docstrings speak
      reader vocabulary with no planning IDs or tuning constants; blank-line audit closes
      23 run-on paragraphs to 0; mDNS API rendered; CI gates on --strict (G-05-6 animation
      share, G-05-4, G-05-7b/c, D5-22 audit)"
    requirement: "DOCS-02"
    verification:
      - kind: unit
        ref: "task 3 automated verify block (AST vocabulary + blank-line sweeps over 53
          :::-reachable files, post-build run-on detector) + uv run --frozen pytest + uv
          run zensical build --strict"
        status: pass
    human_judgment: false

duration: 27min
completed: 2026-07-17
status: complete
---

# Phase 05 Plan 06: UAT Gap Closure (G-05-2..G-05-7) Summary

**Closed all six operator-diagnosed documentation gaps: honest direct-connection guidance, de-jargoned rendered docstrings with IDs demoted to traceability comments, zero run-on paragraphs, rendered mDNS API reference, and a permanent zero-warning `--strict` docs build gate in CI.**

## Performance

- **Duration:** 27 min
- **Started:** 2026-07-17T12:58:00Z
- **Completed:** 2026-07-17T13:25:00Z
- **Tasks:** 3
- **Files modified:** 21

## Accomplishments

- Closed G-05-2: quickstart.md and overview.md no longer claim IP-only connection skips
  discovery; the honest unicast-discovery-round-trip framing and the genuine serial+IP
  zero-discovery example (matching docs/index.md:41) are both published
- Closed G-05-3: docs/api/animation.md's Direct UDP Delivery lead-in uses the operator's
  agreed verbatim text ("purpose-built network stack with the following characteristics")
  and "expected" drop framing
- Closed G-05-4: every mkdocstrings-published docstring heading followed by a blank line —
  the built-HTML run-on-paragraph detector went from 23 findings at planning time to 0
- Closed G-05-5/G-05-6: stripped "Photons-shaped", "wall-time budget", "no blind sleeps",
  Glowup lineage references and every GSD planning ID (RETRY-xx, D3-xx, ANIM-xx, D4-xx,
  spike numbers, plan references) from rendered docstrings in connection.py, discovery.py,
  animator.py and packets.py — every removed ID demoted to a `# Traceability` comment,
  never deleted
- Closed G-05-7: backticked five type annotations in effects.md so markdown stops parsing
  `[Light]` as an unresolvable link; rendered the three previously-missing mDNS `:::`
  targets (discover_mdns, discover_lifx_services, LifxServiceRecord) beside their UDP
  siblings; gated both CI `zensical build` invocations on `--strict`
- Re-ran the mandatory D5-22 audit (internal vocabulary, missing blank lines, D5-09 tuning
  constants) over all 53 `:::`-reachable modules at execution time — zero findings beyond
  the planning-time pinned allowlist, confirming no drift since planning
- `uv run zensical build --strict` now exits 0 with zero warnings — the former 8-warning
  baseline (5x effects.md, 3x index.md) is eliminated, not re-pinned

## Task Commits

Each task was committed atomically:

1. **Task 1: G-05-2 + G-05-3 + G-05-7a — honest direct-connection docs, the agreed
   animation lead-in, and the effects.md link-reference fixes** - `64aff6e` (docs)
2. **Task 2: G-05-5 + connection/discovery shares of G-05-4/G-05-6 — de-jargon the
   network-layer rendered docstrings** - `6d0280d` (docs)
3. **Task 3: G-05-6 animation docstrings + full G-05-4/audit blank-line set + G-05-7b/c
   mDNS render targets and CI --strict + D5-22 audit re-run + full gates** - `95c60d6`
   (docs)

## Files Created/Modified

- `docs/getting-started/quickstart.md` - Honest Direct Connection section: unicast
  discovery round-trip for IP-only, genuine zero-discovery for serial+IP
- `docs/architecture/overview.md` - Accurate Direct Connection bullet (Layer 8)
- `docs/api/animation.md` - Operator-agreed Direct UDP Delivery lead-in verbatim
- `docs/api/effects.md` - Five type annotations backticked (link-reference fix)
- `docs/api/high-level.md` - `::: lifx.api.discover_mdns` rendered beside `discover`
- `docs/api/network.md` - `::: lifx.network.mdns.discover_lifx_services` and
  `::: lifx.network.mdns.LifxServiceRecord` rendered in the Discovery group
- `.github/workflows/docs.yml` - Both build invocations gain `--strict`
- `src/lifx/network/connection.py` - Features blank line, plain-language retransmit
  bullet, de-jargoned `__init__` Args, de-ID'd engine docstring + traceability comment
- `src/lifx/network/discovery.py` - `discover_devices` docstring without lineage
  vocabulary or internal schedule offsets
- `src/lifx/animation/animator.py` - Behavioural-contract Animator/AnimatorStats/
  send_frame docstrings, no IDs or tuning constants
- `src/lifx/animation/packets.py` - Both `probe_template_index` docstrings de-ID'd with
  two new traceability comments; five class-docstring blank lines
- `src/lifx/animation/orientation.py` - Blank line under 'Physical mounting positions:'
- `src/lifx/api.py` - Single blank-line insertion in `apply_theme` (the only api.py edit)
- `src/lifx/color.py` - Blank line under HSBK.to_protocol heading
- `src/lifx/devices/base.py` - Blank lines: Device class docstring, capabilities property
- `src/lifx/devices/ceiling.py` - Four Args-nested lists rendered as lists
- `src/lifx/devices/light.py` - Blank lines: Light class docstring, get_color
- `src/lifx/devices/matrix.py` - Blank lines: Zone Addressing heading and numbered steps
- `src/lifx/devices/multizone.py` - Blank line under MultiZoneLight class docstring
- `src/lifx/effects/pulse.py` - Blank lines: EffectPulse.__init__ Args (period, cycles)
- `src/lifx/protocol/base.py` - Blank line under Packet class docstring
- `src/lifx/protocol/generator.py` - Blank lines across five public-function docstrings

## Decisions Made

- G-05-2 treated as a doc-page-only fix: `from_ip()`'s docstring in base.py is not a
  falsehood (it never claims "no discovery"), so it stayed untouched per the plan's
  prohibition
- G-05-3/G-05-5 used the operator's `agreed_text`/`proposed_text` verbatim, with no
  paraphrasing
- Every planning ID removed from a rendered docstring (G-05-6) was demoted to a
  `# Traceability` comment rather than deleted, preserving the phase-record chain
- D5-23's `--strict` gate applied to both CI invocations, making the zero-warning class
  permanent rather than a re-pinnable baseline

## Deviations from Plan

None — plan executed exactly as written. All must_haves, prohibitions, and fences held:

- api.py diff vs c139542: exactly one insertion, zero deletions, one hunk (the
  `apply_theme` blank line) — the three D5-19-deferred defect ranges are byte-identical
- `discover_devices`/`create_device` Returns:/Raises:/Example: sections in discovery.py
  are byte-identical to c139542
- No EXISTING `:::` block modified anywhere: `docs/api/animation.md`'s diff has zero
  `:::` lines; `docs/api/high-level.md` and `docs/api/network.md` diffs are
  insertion-only (verified: every file's diff contains zero deletion lines except the
  intentional ones checked by the non-additive-diff gate)
- `docs/api/index.md` diff vs c139542 is empty (0 lines) — untouched, its links now
  resolve because the destinations exist
- `docs/changelog.md` and `mkdocs.yml` diffs vs c139542 are both empty (0 lines)
- `grep -rlE 'Since v[0-9]' docs/ CLAUDE.md src/` matches zero files — no version
  attribution anywhere
- Comments and unrendered docstrings untouched except the three additive
  `# Traceability` comments (connection.py x1, packets.py x2)

## Audit Re-Run Results (D5-22, mandatory)

- **Sweep 1 (internal vocabulary):** AST scan over all 53 `:::`-reachable files
  (target-derived from `grep -rh '^::: ' docs/api/*.md` via importlib resolution)
  printed zero findings and exited 0 — no planning ID, design-lineage reference, or
  measured spike figure remains in any public docstring
- **Sweep 2 (missing blank lines):** AST scan over the entire `src/lifx` tree printed
  zero findings beyond the 15-key pinned out-of-scope allowlist (module docstrings,
  private methods, and untargeted modules) — every `:::`-reachable heading-plus-list
  site now carries its blank line
- **Sweep 3 (D5-09 tuning constants):** Covered by sweep 1's pattern set
  (gate-threshold/expiry/floor/offset patterns); zero findings
- **Sweep 4 (mDNS docstrings, D5-23 inheritance):** `discover_mdns`,
  `discover_lifx_services`, and `LifxServiceRecord` went live as part of the 53-file
  scan in sweeps 1-2; no findings — confirms the planning-time CLEAN result held with
  no drift, and no source edit to those three docstrings was needed
- **Post-build run-on detector:** 0 run-on `<p>` paragraphs across `site/api/` (was 23
  at planning time)

## Demotion Map (final state — where each removed ID now lives)

| Removed from rendered prose | Now lives in |
|---|---|
| RETRY-01/D3-01, RETRY-02/D3-02, RETRY-03/D3-03, RETRY-04/D3-04, D3-05 | `connection.py` new `# Traceability` comment above `_transmit_and_listen`'s body |
| D4-03, D4-01 + spike 003 measured figure, D4-02, D4-04 | `packets.py` new `# Traceability` comment above `PacketGenerator.probe_template_index` |
| D4-04, ANIM-04 UAT (plan 04-07), spike 003 | `packets.py` new `# Traceability` comment above `MatrixPacketGenerator.probe_template_index` |
| ANIM-01, ANIM-02, D4-02, D4-03, D4-04 (Animator/AnimatorStats/send_frame) | Already preserved untouched in `animator.py`'s module docstring (:5) and the in-body comment at :162-165 — no new comment needed |
| Photons-shaped schedule + cumulative offsets (`discover_devices`) | Already preserved untouched in `discovery.py`'s private `_discover_with_packet` docstring and its schedule comment |

## Gate Results

- `uv run --frozen pytest -q`: **2618 passed, 12 deselected** (baseline held)
- `uv run ruff check .`: **All checks passed**
- `uv run ruff format --check .`: **228 files already formatted**
- `uv run pyright`: **0 errors, 0 warnings, 0 info notes**
- `uv run zensical build --strict`: **No issues found — exit 0** (former 8-warning
  baseline eliminated per D5-23)
- Both `.github/workflows/docs.yml` build invocations now read
  `zensical build --clean --strict`

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DOCS-01 and DOCS-02 remain complete — these were accuracy/readability defects inside
  already-satisfied requirements; no REQUIREMENTS.md change needed
- Phase 05 (reliability-documentation) is now fully closed: all 6 plans executed, all
  UAT gaps (G-05-2..G-05-7) resolved, and the docs build is permanently gated on
  `--strict` in CI
- No blockers. The D5-09 dispute (timing/override/diagram documentation) remains
  explicitly open and unscheduled (spike candidate 006) — out of scope for this plan by
  design

---
*Phase: 05-reliability-documentation*
*Completed: 2026-07-17*

## Self-Check: PASSED

All 21 modified files found on disk; all 3 task commits (`64aff6e`, `6d0280d`, `95c60d6`)
found in git history.
