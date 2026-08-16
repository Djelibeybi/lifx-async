# Phase 8: Hardware Fidelity Validation — Specification

**Created:** 2026-08-15
**Ambiguity score:** 0.12 (gate: ≤ 0.20)
**Requirements:** 4 locked

## Goal

The 25 shipped themes captured at the 16-colour protocol ceiling carry an evidenced
length determination, and two representative themes produce capture-exact MORPH palette
readbacks over three repeated applications on both the source Tile and one real indoor
non-Tile matrix product.

## Background

Phase 6 generated the shipped theme library from a 2026-08-14 hardware capture and
verified every non-sport palette as an unordered uint16 HSBK multiset. The capture was
made by applying an app theme as MORPH to a LIFX Tile (product 55), saving it in the app,
then reading `StateTileEffect`. This proves what the Tile received, but not that the same
palette reaches another matrix product.

The source material currently disagrees about the 16-colour boundary:

- `.claude/theme-capture/themes.jsonl` contains 26 exactly-16-colour records, one of
  which belongs to an excluded sport category.
- `data/themes.jsonl`, the shipped non-sport source of truth, contains 25 such records.
- `PROJECT.md`, `REQUIREMENTS.md` and `ROADMAP.md` say 26; the capture README says 21.

The correct Phase 8 set is therefore the **25 shipped non-sport themes**. The wire format
cannot reveal whether any of them was clipped: 16 is the maximum palette length in both
`SetTileEffect` and `SetMultiZoneEffect`. A per-theme finding that its true length cannot
be determined from a device is a successful result, not a recovery failure.

`MatrixLight.get_effect()` already returns only the reported `palette_count` entries,
and `Theme.palette_equals()` already compares unordered multisets at uint16 precision
with duplicate counts preserved. `MatrixLight.apply_theme()` is a different static-pixel
canvas path that interpolates colours; its pixel readback is not comparable to the app's
MORPH palette and is deliberately excluded from this phase.

## Requirements

1. **FIDELITY-01 — Ceiling determinations**: A committed evidence table contains exactly
   one row for each of the 25 shipped `lifx-app` themes whose palette length is exactly 16.
   - Current: the 25 themes are identifiable in `data/themes.jsonl`, but no committed
     per-theme determination exists and adjacent project documents carry stale counts of
     26 or 21.
   - Target: every row is keyed by the shipped ASCII slug and records either a true source
     length established from a cited non-device source or the evidenced determination that
     no device readback can establish a length above the 16-slot protocol ceiling; all
     stale 26/21 references are corrected to distinguish 26 raw records from 25 shipped
     records.
   - Acceptance: a mechanical comparison against `data/themes.jsonl` finds exactly the
     same 25 sorted slugs with no missing or extra rows, every row has one permitted
     determination and its evidence, and repository search finds no remaining claim that
     26 or 21 shipped non-sport themes sit at the ceiling.

2. **FIDELITY-02 — App/library MORPH equivalence on Tile**: One named theme with fewer
   than 16 colours and one named exactly-16-colour Art Series theme produce identical
   app-driven and library-driven MORPH palette readbacks on the source Tile.
   - Current: the app capture exists, and shipped palettes match it offline, but no
     committed same-device run compares the app path with a `ThemeLibrary` palette sent
     back through MORPH.
   - Target: the same two slugs are fixed before testing; for each slug, three app
     Save-and-read cycles and three library MORPH-and-read cycles are executed
     sequentially on the Tile.
   - Acceptance: all 12 readbacks (two themes × two sources × three cycles) equal the
     corresponding shipped palette as unordered uint16 HSBK multisets with duplicate
     counts preserved; no cycle may be discarded or replaced after a mismatch.

3. **FIDELITY-03 — Non-Tile product invariance**: The same two themes pass the same
   MORPH comparison on one responding indoor matrix product other than the Tile.
   - Current: product invariance is expected because the palette is effect configuration,
     but every capture record came from product 55 and no other product is evidenced.
   - Target: one real indoor Candle, Ceiling or other non-Tile matrix product is selected;
     its model, product ID and host firmware are recorded, then three app and three library
     MORPH cycles per theme are compared with the original Tile capture.
   - Acceptance: all 12 non-Tile readbacks equal the corresponding Tile-captured/shipped
     palette as unordered uint16 HSBK multisets. If no indoor non-Tile matrix product
     responds, this requirement remains `human_needed` and Phase 8 cannot pass; Tile-only
     or emulator evidence is not a substitute.

4. **Replayable, sanitised validation evidence**: The phase commits enough evidence for
   an independent verifier to reproduce every determination and comparison without
   trusting a summary.
   - Current: raw app capture files exist, but there is no Phase 8 record joining the
     selected slugs, source path, device class, per-cycle readbacks, comparison result,
     state restoration and 25-row ceiling table.
   - Target: a tracked Phase 8 validation artefact records the exact commands or probe
     entry points, selected slugs, product metadata, all cycle outcomes, failures and final
     device-state restoration result while omitting private network/device identifiers.
   - Acceptance: the artefact contains six app/library cycle results per theme per tested
     product, the 25-row FIDELITY-01 table, model/product/firmware metadata, a final
     restoration result for every selected device and no local IP address, serial/MAC or
     household device label.

## Boundaries

**In scope:**

- A 25-row, slug-keyed determination table for the shipped exactly-16-colour themes
- Correction of the stale 26/21 counts in active planning and capture documentation
- Two fixed sample themes: one palette below the ceiling and one exactly-16-colour Art
  Series palette
- Three sequential app MORPH and three sequential library MORPH readbacks per sample on
  the source Tile
- The same repeated comparison on one real indoor non-Tile matrix product
- A committed, replayable and sanitised Phase 8 validation record
- Focused probe/support code and automated tests when required to produce reliable evidence

**Out of scope:**

- Static `MatrixLight.apply_theme()` canvas/pixel fidelity — it interpolates output and is
  not comparable to the app's MORPH palette
- Visual or photographic comparison — protocol readback is the authority for this phase
- Testing every category, theme or matrix product — the locked scope is two themes and one
  non-Tile product
- Exterior devices — validation must remain on explicitly selected indoor hardware
- Recovering a palette longer than 16 from any device — the protocol makes that impossible
- Calling undocumented LIFX theme endpoints or spending identifiable credentials to seek a
  non-device source
- Capture/resync tooling and end-user theme documentation — Phase 9 owns TOOL-01..03 and
  DOCS-03
- Changing shipped theme palettes in response to a mismatch — a mismatch creates a failed
  criterion and gap plan, not an in-phase data rewrite

## Constraints

- Real hardware is mandatory for FIDELITY-02 and FIDELITY-03; emulator-backed tests may
  test support code but cannot satisfy either hardware criterion.
- Palette equality is an unordered **multiset** of protocol uint16 HSBK tuples; order is
  ignored and duplicate counts are significant.
- Every app path includes the app's Save action before readback; selection alone does not
  update the running effect.
- The 24-key schedule is role-local: app Saves alternate `mondrian` 1, `cheerful` 1,
  `mondrian` 2, `cheerful` 2, `mondrian` 3, `cheerful` 3, then library cycles remain
  grouped `cheerful` 1–3 followed by `mondrian` 1–3. Before each invocation that reaches
  an app key, the operator explicitly attests that the manually positioned Morph
  configuration is set to Cheerful; the hidden current picker theme is not a UI observation.
- All application/readback cycles run sequentially. An interrupted or incomplete cycle set
  cannot be reported as passing.
- Tests may touch only explicitly selected indoor devices. Each device's prior power,
  colour/pixel and effect state must be captured and restored after success, failure or
  interruption.
- Committed evidence records model, product ID and firmware but no IP address, serial/MAC
  value or identifiable household label.
- No undocumented LIFX endpoint or identifiable cloud credential may be used.
- Any new Python tooling uses `uv`, adds no runtime dependency and keeps Python 3.10–3.14,
  ruff and strict pyright compatibility. Automated code changes require 100% branch patch
  coverage independently of the hardware evidence.
- Australian English is required in prose and comments.

## Acceptance Criteria

- [ ] The ceiling table contains exactly the 25 sorted shipped slugs selected by
  `disposition == "lifx-app"` and palette length 16 in `data/themes.jsonl`.
- [ ] Every ceiling-table row records either a cited true non-device length or the explicit
  evidenced finding that no device-based method can determine a longer length.
- [ ] Active planning/capture documentation distinguishes 26 raw exactly-16-colour records
  from the 25 shipped non-sport records; the stale count of 21 is removed.
- [ ] One below-ceiling theme and one exactly-16-colour Art Series theme are named before
  the first run and used unchanged for every Tile and non-Tile cycle.
- [ ] On the source Tile, all three app MORPH and all three library MORPH readbacks for each
  sample match the shipped palette as unordered uint16 HSBK multisets.
- [ ] On one real indoor non-Tile matrix product, all three app MORPH and all three library
  MORPH readbacks for each sample match the original Tile capture as unordered uint16 HSBK
  multisets.
- [ ] The non-Tile device's model, product ID and firmware are recorded; no emulator or Tile
  result is represented as the FIDELITY-03 product.
- [ ] A missing/unresponsive indoor non-Tile product leaves verification `human_needed` and
  does not produce a passing Phase 8 report.
- [ ] Every required cycle is recorded, including failures; no mismatch is discarded,
  retried away or normalised.
- [ ] A mismatch leaves shipped/captured palette data unchanged and produces a failed
  criterion for gap planning.
- [ ] Only explicitly selected indoor devices are touched, and each selected device's prior
  power, colour/pixel and effect state is restored after success, failure or interruption.
- [ ] Committed evidence contains no IP address, serial/MAC value or identifiable household
  label.
- [ ] Any support-code changes pass focused tests, ruff, strict pyright and 100% branch patch
  coverage; hardware evidence remains an independent gate.

## Edge Coverage

**Coverage:** 20/20 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| boundary | R1 | ✅ covered | The committed source has 25 shipped ceiling themes; the 26th raw record is an excluded sport theme and the README's 21 is stale |
| adjacency | R1 | ⛔ dismissed | Rows are keyed by the 25 unique shipped ASCII slugs; no collision or merge is permitted |
| empty | R1 | ✅ covered | Exact set equality with the 25 source slugs fails on any missing or extra row |
| encoding | R1 | ✅ covered | Identity is the shipped ASCII slug, not the emoji-bearing raw display name |
| ordering | R1 | ✅ covered | The evidence table is sorted by slug for deterministic comparison |
| precision | R1 | ✅ covered | Ceiling membership is literal palette length 16 in committed uint16-normalised data; no rounding is involved |
| boundary | R2 | ✅ covered | Samples straddle the wire boundary: one palette below 16 and one exactly 16 |
| adjacency | R2 | ✅ covered | Equality is a multiset; equal colours remain separate occurrences and duplicate counts must match |
| empty | R2 | ⛔ dismissed | Both fixed samples must resolve to non-empty shipped palettes; an empty theme is not a valid sample |
| ordering | R2 | ✅ covered | App shuffling is expected; comparison is order-independent |
| precision | R2 | ✅ covered | Comparison uses exact protocol uint16 HSBK tuples, not source floats or visual tolerance |
| idempotency | R2 | ✅ covered | Three app and three library cycles must all pass; repetition cannot change the verdict |
| concurrency | R2 | ✅ covered | Cycles are sequential; interruption leaves the evidence incomplete and cannot pass |
| boundary | R3 | ✅ covered | Product 55 is excluded from the non-Tile slot; one real indoor matrix product must answer |
| adjacency | R3 | ✅ covered | Equality remains multiset-exact with duplicate counts preserved across products |
| empty | R3 | ✅ covered | No responding non-Tile device yields `human_needed`, never an empty successful sample |
| ordering | R3 | ✅ covered | Product/app shuffling does not affect unordered comparison |
| precision | R3 | ✅ covered | Cross-product comparison is exact at uint16 HSBK precision |
| idempotency | R3 | ✅ covered | All three cycles for both sources and themes must pass on the same recorded product |
| concurrency | R3 | ✅ covered | The selected device is tested sequentially and restored on interruption; unrelated devices remain untouched |

## Prohibitions (must-NOT)

**Coverage:** 7/7 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT call undocumented LIFX theme endpoints or use identifiable cloud credentials to obtain a source palette | R1 | resolved | verification: judgment — device readback remains the only authorised capture source; a cited non-device source must already be legitimately accessible |
| MUST NOT claim a true source length from a 16-entry device readback or claim fidelity beyond the products, firmware and cycles actually evidenced | R1, R2, R3 | resolved | verification: judgment — the report must distinguish measured facts from protocol-limited unknowns |
| MUST NOT commit a local IP address, device serial/MAC value or identifiable household label in validation evidence | R4 | resolved | verification: test — evidence is mechanically scanned before commit; no wired descriptor exists yet, so plan-phase must supply the check |
| MUST NOT normalise away a mismatch or modify captured/shipped theme data during validation | R2, R3 | resolved | verification: test — a mismatch must remain in the evidence and leave `data/themes.jsonl` and generated theme data unchanged; no wired descriptor exists yet |
| MUST NOT address, power or alter an unrelated fleet device or any Exterior device | R2, R3 | resolved | verification: test — the probe uses an explicit indoor-device allowlist; no wired descriptor exists yet |
| MUST NOT leave a selected device in the test state after success, failure or interruption | R2, R3 | resolved | verification: test — captured pre-state and final readback must match; no wired descriptor exists yet |
| MUST NOT substitute emulator or Tile evidence for the required real non-Tile product | R3 | resolved | verification: test — recorded product ID and device class must prove a real non-Tile matrix product; no wired descriptor exists yet |

## Ambiguity Report

| Dimension | Score | Min | Status | Notes |
|-----------|-------|-----|--------|-------|
| Goal Clarity | 0.92 | 0.75 | ✓ | Three fidelity outcomes and their evidence are measurable |
| Boundary Clarity | 0.82 | 0.70 | ✓ | Static rendering, broad fleet coverage, endpoints and Phase 9 tooling are excluded |
| Constraint Clarity | 0.90 | 0.65 | ✓ | Exact comparison, repetitions, hardware class, privacy and restoration are locked |
| Acceptance Criteria | 0.88 | 0.70 | ✓ | 13 pass/fail criteria cover data, both products, evidence and failure states |
| **Ambiguity** | **0.12** | **≤0.20** | **✓** | No unresolved edge or prohibition remains |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | What proves app/library equivalence? | Exact protocol palette readback only; no visual judgement |
| 1 | Researcher | What carries the ceiling determination? | A committed evidence table with one row per affected shipped theme |
| 1 | Researcher | How broad is the theme sample? | Two themes: one short palette and one exactly-16-colour Art Series palette |
| 2 | Researcher | Which library paths are validated? | Initially both MORPH and static `apply_theme()`; edge probe later excluded static pixels as non-comparable |
| 2 | Simplifier | How many repetitions and products? | Three cycles per source/theme; one responding indoor non-Tile matrix product |
| Edge probe | Boundary Keeper | Is the ceiling set 21, 25 or 26? | 25 shipped non-sport themes; correct stale 26/21 references |
| Edge probe | Failure Analyst | How can static pixels equal an app MORPH palette? | They cannot; remove `MatrixLight.apply_theme()` from Phase 8 |
| Edge probe | Failure Analyst | What if non-Tile hardware is unavailable? | Phase remains `human_needed`; no Tile/emulator substitute |
| Prohibition probe | Failure Analyst | What must evidence and hardware validation never do? | No private identifiers, no data rewrite on mismatch, no unrelated-device changes, and restore selected device state |

---

*Phase: 08-hardware-fidelity-validation*
*Spec created: 2026-08-15*
*Next step: $gsd-discuss-phase 8 — implementation decisions (how to build what's specified above)*
