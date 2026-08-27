# Phase 8: Hardware Fidelity Validation - Research

**Researched:** 2026-08-15  
**Domain:** Real LIFX-hardware MORPH palette fidelity, Android UI automation, resumable UAT evidence  
**Confidence:** HIGH

## User Constraints (from CONTEXT.md)

### Locked Decisions

<user_constraints>

**D-01:** The app path is fully automated with UIAutomator. Each app cycle starts from the LIFX app home screen and uses semantic controls to select the approved device, open MORPH, select the theme and tap Save. The app is not force-stopped between cycles.

**D-02:** Theme lookup uses the expected category plus one exact display-name match in the semantic picker grid. Recorded grid positions and coordinate-only selection are not authoritative.

**D-03:** Before either light is touched, preflight requires exactly one authorised Android tablet, the installed and signed-in LIFX app, an unlocked screen, both target devices visible, and both fixed themes resolvable. It also records the app version and a fingerprint of the semantic category/theme catalogue; drift during the run fails it.

**D-04:** A missing expected theme or Save control gets two semantic-lookup retries. Exhausting them records the failure, captures local diagnostics, restores device and tablet state, and stops the run.

**D-05:** After Save, bounded stability polling records every LAN read. Two consecutive identical unordered palettes establish the official stable readback. Timeout fails the cycle; a stable palette unequal to the expected shipped theme is retained as mismatch evidence. Transitional reads are never discarded from local evidence. The 2026-08-16 correction supersedes the capture-era reset-palette assumption: it was not a canonical reusable signature and requires no operator input or guessed constant.

**D-06:** For each theme and device, run three app cycles followed by three library cycles. A stable mismatch does not shorten the dataset: all remaining fixed cycles run, every mismatch remains recorded, restoration still runs, and the criterion fails.

**D-07:** The runner temporarily enables Android keep-awake after capturing the prior setting and restores that setting on every exit path.

**D-08:** The runner is a phase-local UAT harness at `.planning/phases/08-hardware-fidelity-validation/uat_theme_fidelity.py`, not permanent Phase 9 capture tooling. It shows detailed redacted progress and mirrors events to a local JSONL trace.

**D-09:** UI and stability waits have documented defaults with explicit CLI overrides; every effective value is recorded. Exit statuses distinguish pass, validation mismatch, incomplete/preflight failure and restoration failure.

**D-10:** Raw screenshots, UI hierarchies and JSONL traces stay outside committed evidence. Delete them after a full pass; retain them locally after failure and print the diagnostic directory for review.

**D-11:** Interrupted runs resume at the next unfinished cycle rather than starting over. Resume requires an exact provenance match for runner revision, app version, catalogue fingerprint, device identities and firmware, themes, ordering and effective timeouts. The interrupted record and all completed cycles remain intact.

**D-12:** Resumable private connection details live in a restrictive local-only checkpoint outside git. Committed evidence identifies targets only as `source-tile` and `non-tile-matrix` plus the permitted product metadata.

**D-13:** Official Phase 8 runs always use `cheerful` followed by `mondrian`, with no theme override. Cheerful is the first theme in the captured UI and has five colours; Mondrian is the first Art Series theme and has 16 colours. This is the earliest qualifying pair and deliberately minimises picker scrolling.

**D-14:** The runner hardcodes only the two shipped slugs. Preflight derives category, display name and expected palette from `data/themes.jsonl`, then freezes a hash of the resolved records into the run provenance.

**D-15:** A private, git-ignored local target file explicitly names one source Tile and one indoor non-Tile matrix device. The runner does not choose targets through unrestricted fleet discovery.

**D-16:** Prefer a Ceiling as the non-Tile product, with Luna as fallback. Both product families must still pass live capability validation as non-Tile matrix devices before mutation.

**D-17:** Preflight must capture a capability-complete restoration snapshot: power, base colour, active effect and settings, full matrix pixels, and Ceiling uplight/downlight state where applicable. Any missing required read aborts before mutation.

**D-18:** The private target file binds LAN address, serial and app-visible label. LAN metadata and the app-selected label must prove both paths address the same physical light. None of those private identifiers may enter committed evidence.

**D-19:** Structured JSON is the machine-checkable authority and rendered Markdown is the human review surface. The stable official pair is `08-UAT-RESULTS.json` and `08-UAT.md`, finalised from the designated complete or definitively failed run. Interrupted checkpoints remain local and are referenced only by opaque run ID.

**D-20:** Generate the 25-row ceiling table mechanically from the sorted records in `data/themes.jsonl` whose disposition is `lifx-app` and whose colour count is 16. Attach the applicable cited length determination to every row; do not maintain a parallel slug list or CSV.

**D-21:** Official evidence finalisation is fail closed. An allowlist schema rejects private fields and address/identifier patterns, then verifies the exact 25-slug set, required cycle counts, palette comparisons and restoration verdicts before either official file is written.

### the agent's Discretion

None — every implementation question discussed was answered directly.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIDELITY-01 | Determine every shipped 16-colour palette’s true length or record the protocol-limited finding. | Mechanical data inventory, protocol ceiling, stale-count correction, and fail-closed table validation. |
| FIDELITY-02 | Prove app and library MORPH readbacks agree on the source Tile. | Existing MORPH setter/readback seams, exact multiset comparison, app Save workflow, sequential cycles. |
| FIDELITY-03 | Prove the same pair agrees on one indoor non-Tile matrix product. | Explicit target binding, live matrix/capability validation, Ceiling-first restoration path, and human-needed failure state. |

## Summary

Phase 8 should add one phase-local, dependency-free Python UAT runner and a tightly coupled evidence finaliser. It must not change palette data or the normal theme-application API. The runner drives the existing signed-in Android app to apply `cheerful` then `mondrian` as MORPH, reads the selected hardware through the existing local-network `MatrixLight.get_effect()` API, and compares each readback against the frozen shipped palette as an unordered uint16 HSBK multiset. [VERIFIED: src/lifx/devices/matrix.py:1059-1108; src/lifx/theme/theme.py:242-284; 08-CONTEXT.md:D-01..D-14]

The hardware phase needs two separate records. A restrictive, git-ignored checkpoint contains private target bindings, restoration snapshots, resume provenance, local JSONL events, screenshots and hierarchy dumps. A finaliser produces the committed `08-UAT-RESULTS.json` and `08-UAT.md` only after allowlist/redaction and completeness validation. This separation is mandatory: raw diagnostics are useful to repair a failed run but violate the privacy contract if committed. [VERIFIED: 08-CONTEXT.md:D-08..D-12, D-15, D-18..D-21]

The source-of-truth count is 25, not 26 or 21. The exact shipped selection is: “`baubles, bijutsukai, candy_cane, clouds, deck_the_halls, disco, earth, festive, gauguin, hokusai, independence, kandinsky, klimt, mars, matisse, memorial_day, mistletoe, mondrian, monet, moon, oktoberfest, old_glory, rousseau, sun, van_gogh`”. The raw capture has 26 length-16 records because it includes the excluded sport record “`Carlton 🔵`” in “`🏆 AUSSIE RULES`”. [VERIFIED: data/themes.jsonl parsed in this session; .claude/theme-capture/themes.jsonl parsed in this session]

**Primary recommendation:** Plan the runner, its pure support functions/tests, and stale-document/evidence finalisation together; make the real-hardware run a named UAT checkpoint that cannot be replaced by emulator output.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| App-driven MORPH selection and Save | Android client / ADB | Local runner | The app is the only authorised source path; the runner orchestrates it but does not reimplement app theme lookup. |
| MORPH palette setting and readback | API / local UDP device layer | Device firmware | `MatrixLight.set_effect()` writes the MORPH configuration and `get_effect()` reads reported palette slots. [VERIFIED: src/lifx/devices/matrix.py:1059-1108, 1169-1279] |
| Palette equality | Theme domain model | UAT runner | `Theme.palette_equals()` already owns unordered uint16 multiset equality including duplicate counts. [VERIFIED: src/lifx/theme/theme.py:242-284] |
| Hardware target identity and restoration | Local runner | Device firmware | Private explicit bindings prevent fleet-wide mutation; runner snapshots and restores before finalisation. |
| Final evidence and privacy validation | Local runner | Git-tracked phase artefacts | The finaliser must reject fields/patterns outside the published schema before writing authoritative artefacts. |
| 16-colour determinations | Committed theme data + finaliser | Protocol layer | The source data selects rows; protocol's 16-slot limit establishes what a device cannot prove. [VERIFIED: data/themes.jsonl parsed in this session; src/lifx/const.py:123-128] |

## Project Constraints (from AGENTS.md)

- Use Australian English spelling.
- Use `uv` exclusively for Python dependencies and execution; do not use pip, Poetry or Conda.
- If a dependency becomes necessary, add its current version through `uv`, synchronise and lock it; this phase should add none because the library has zero runtime dependencies.
- Keep imports at the top of Python files.
- Do not manually edit generated protocol or products registry files.
- Run relevant tests with `uv run`, then ruff and strict Pyright; investigate and fix every failure rather than ignoring it.
- Generated theme data is regenerated from `data/themes.jsonl` with `uv run scripts/generate_theme_data.py`, not edited directly. [VERIFIED: AGENTS.md; CLAUDE.md]
- Do not ignore uncommitted files: include them or ask the operator. The worktree was clean before this research file was created. [VERIFIED: local `git status --short` audit]
- Commits normally require `git commit -s` and the configured GPG signature; this assignment additionally prohibits branch changes and commits.

## Standard Stack

### Core

| Library / tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Python standard library | Python 3.10–3.14 compatible | CLI, JSON/JSONL, hashing, subprocess, XML parsing, async cleanup | The repository is deliberately runtime-dependency-free and the existing capture tool already uses this shape. [VERIFIED: AGENTS.md; .claude/theme-capture/tools/sweep_themes.py:1-35] |
| Existing `lifx-async` source checkout | current checkout | Targeted device connection, Matrix MORPH commands/readbacks, theme records | Reuses shipped APIs; no public API expansion or third-party package is necessary. [VERIFIED: src/lifx/devices/matrix.py:1059-1279; src/lifx/theme/theme.py:242-284] |
| Android Debug Bridge and `uiautomator dump` | ADB 1.0.41 available | Semantic app navigation, diagnostics and temporary keep-awake control | The prior authorised capture already uses fixed-argument `adb` calls and hierarchy XML. [VERIFIED: .claude/theme-capture/tools/sweep_themes.py:76-89; local environment audit] |

### Supporting

| Library / tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `collections.Counter` | stdlib | Exact unordered multiset equality | For every expected-versus-readback comparison; never use `set` because it drops duplicate counts. [VERIFIED: src/lifx/theme/theme.py:242-284] |
| `hashlib` / canonical JSON | stdlib | Resume/provenance and catalogue-record fingerprints | Hash canonicalised public fields plus private target fingerprints; compare exact stored values before resuming. [ASSUMED] |
| `xml.etree.ElementTree` | stdlib | Parse local UIAutomator hierarchy XML | Reuse the capture tool's pattern only for output from the authorised connected tablet. [VERIFIED: .claude/theme-capture/tools/sweep_themes.py:27-35, 84-89] |

### Alternatives Considered

| Instead of | Could Use | Trade-off |
|------------|-----------|-----------|
| Phase-local UAT runner | Extending Phase 9 capture/resync tooling | Contradicts D-08 and expands permanent tooling before its owning phase. |
| Semantic hierarchy selection | Coordinate-only picker selection | Coordinates are device/layout-specific and explicitly non-authoritative under D-02. |
| Explicit two-device target file | Fleet discovery | Discovery can touch unrelated devices and contradicts D-15. |
| Protocol MORPH comparison | Static canvas/pixel or visual comparison | Neither proves the app's MORPH palette; static interpolation is explicitly excluded. |

**Installation:** None. This phase installs no package.

## Package Legitimacy Audit

Not applicable — the phase must use the existing standard-library/checkout/ADB stack and adds no package.

## Architecture Patterns

### System Architecture Diagram

```text
private target file ──► preflight ──► private checkpoint + restoration snapshot
                            │
Android app home ──semantic navigation──► MORPH / exact theme / Save
                            │                         │
                            │                         ▼
shipped data/themes.jsonl ─► frozen expected palette ─► targeted MatrixLight.get_effect()
                                                        │
                                                        ▼
                                                all LAN stability reads
                                                        │
                 ┌───────────── exact Counter multiset comparison ──────────────┐
                 │                                                               │
                 ▼                                                               ▼
       local JSONL + diagnostics                                      continue all cycles
                 │                                                               │
                 └──────────────► restore all selected device state ────────────┘
                                                        │
                                                        ▼
                   allowlist + completeness validator ─► JSON authority + Markdown review
```

### Recommended Project Structure

```text
.planning/phases/08-hardware-fidelity-validation/
├── uat_theme_fidelity.py      # phase-local runner, pure helpers and CLI orchestration
├── 08-UAT-RESULTS.json        # committed authoritative, sanitised complete/failed record
├── 08-UAT.md                  # committed rendered review record
├── 08-RESEARCH.md
└── 08-PLAN.md                 # created by planner

.planning/local/               # git-ignored, restrictive local-only checkpoint root
└── phase-08-theme-fidelity/   # private targets, raw JSONL, diagnostics, resumable state
```

The exact local-only directory name is a planning recommendation, not a locked public path. It must be added to an ignore rule before any private output is created. [ASSUMED]

### Pattern 1: Separate orchestration from pure validation

**What:** Keep ADB/device I/O, checkpoint writes and cleanup in a thin async orchestration layer. Put schema validation, palette canonicalisation/multiset comparison, 25-row derivation, public-record projection, redaction checks and Markdown rendering in deterministic pure functions.

**When to use:** Always. It permits unit tests and branch coverage without live hardware, while reserving FIDELITY-02/03 for real UAT.

**Example:**

```python
from collections import Counter

def palette_key(colours: list[tuple[int, int, int, int]]) -> Counter[tuple[int, int, int, int]]:
    return Counter(colours)

def palettes_match(expected: list[tuple[int, int, int, int]], observed: list[tuple[int, int, int, int]]) -> bool:
    return palette_key(expected) == palette_key(observed)
```

This mirrors the established “`return Counter(self.colors) == Counter(other.colors)`” behaviour, so repeated HSBK tuples in Mondrian remain meaningful. [VERIFIED: src/lifx/theme/theme.py:281-284]

### Pattern 2: Fail-closed state machine with finally restoration

**What:** Model the run as preflight → snapshot → cycles → restoration → finalisation. The only paths that may create committed artefacts are after restoration and complete schema validation. Use `try/finally` plus cancellation-aware handling so an exception, signal or failed UI lookup still attempts restoration and writes private recovery state.

**When to use:** Every mutating hardware run and resume.

**Critical state transitions:**

| State | May mutate lights? | Required persisted material | Permitted next state |
|-------|---------------------|-----------------------------|----------------------|
| Preflight | No | private targets, effective settings, app/catalogue/device provenance | Snapshot or incomplete |
| Snapshot | No, until complete | full restoration snapshot | Cycles or incomplete |
| Cycles | Selected targets only | append-only cycle events, all transient polls | Restoration |
| Restoration | Selected targets only | restoration attempts and final verification | Finalisation or restoration failure |
| Finalisation | No | validated public projection only | Complete/failed official pair |

### Pattern 3: Stable readback without erasing observations

**What:** After each app Save, poll `get_effect()` within a bounded deadline, append every observed readback to private JSONL, and accept only two consecutive identical unordered palettes as that cycle's stable official readback. Treat deadline expiry as cycle failure and a stable unequal palette as retained mismatch evidence; do not delete transitional events.

**When to use:** Every app-driven cycle. Library-driven cycles should use the same bounded readback discipline so both paths are represented consistently. [VERIFIED: 08-CONTEXT.md:D-05]

### Pattern 4: Two projections of the same run

**What:** Write rich private events during the run, then construct a strict public projection. Do not “redact in place”; build public JSON from an allowlisted schema and reject unexpected keys and identifiers before writing either official artefact.

**When to use:** Finalisation only. The finaliser must receive a designated complete or definitively failed run, never an interrupted checkpoint. [VERIFIED: 08-CONTEXT.md:D-10..D-12, D-19..D-21]

### Anti-Patterns to Avoid

- **Calling `MatrixLight.apply_theme()`:** it distributes/interpolates canvas pixels, not an app MORPH palette, so it cannot validate FIDELITY-02/03. [VERIFIED: src/lifx/devices/matrix.py:1281-1315; 08-SPEC.md:34-38]
- **Comparing `set(palette)`:** it destroys multiplicity; Mondrian intentionally contains repeated tuples. [VERIFIED: data/themes.jsonl parsed in this session; src/lifx/theme/theme.py:242-284]
- **Fixed sleeps as the authority:** a sleep may precede a transitional or reset effect; use it only as a polling cadence, with two identical readbacks as the stability rule.
- **Force-stopping the LIFX app:** prohibited by D-01 and can hide navigation/state faults.
- **Writing official evidence during a partial run:** an interrupted run is resumable private state, never a pass.
- **Best-effort restoration:** snapshot failure must abort before mutation; restore verification failure has its own terminal status.

## Don't Hand-Roll

| Problem | Do not build | Use instead | Why |
|---------|-------------|-------------|-----|
| Device palette equality | float tolerance / custom de-duplication | `Theme.palette_equals()` semantics or a matching `Counter` over uint16 tuples | Existing domain rule is order-independent and duplicate-sensitive. [VERIFIED: src/lifx/theme/theme.py:242-284] |
| MORPH packet encoding | hand-written protocol packet | `MatrixLight.set_effect(FirmwareEffect.MORPH, palette=...)` | It pads the protocol palette and supplies the palette count. [VERIFIED: src/lifx/devices/matrix.py:1169-1279] |
| Effect readback parsing | direct `StateEffect` decoder | `MatrixLight.get_effect()` | It reads the reported `palette_count` slice and converts protocol HSBK values. [VERIFIED: src/lifx/devices/matrix.py:1059-1108] |
| Product selection | inferred class/product-name heuristic | private target binding + live capability/product-ID checks | Prevents unrelated-device mutation and verifies the non-Tile condition at run time. |
| Theme metadata lookup | duplicated picker table or slug list | `data/themes.jsonl` | One committed source mechanically produces the exact 25-row table. [VERIFIED: 08-CONTEXT.md:D-14, D-20] |
| Android selector strategy | pre-recorded screen coordinates | UI hierarchy resource-id/text plus category/name semantic predicates | Existing capture extracts semantic cells; coordinates are explicitly non-authoritative. [VERIFIED: .claude/theme-capture/tools/sweep_themes.py:84-184; 08-CONTEXT.md:D-02] |

**Key insight:** the library already owns the protocol mechanics and equality semantics; Phase 8 adds only safe orchestration and durable evidence.

## Common Pitfalls

### Pitfall 1: Treating 16 observed slots as the theme’s true length

**What goes wrong:** The runner claims a source palette is exactly 16 colours from a device readback.

**Why it happens:** The protocol has a 16-slot effect palette ceiling. The source definition is “`MAX_PALETTE_COLORS: Final[int] = 16`”; the raw capture cannot show a 17th value. [VERIFIED: src/lifx/const.py:123-128]

**How to avoid:** Generate every FIDELITY-01 row from the shipped records and record the explicit protocol-limited determination unless a legitimately accessible, cited non-device source establishes the true length. Never call the prohibited undocumented endpoints.

**Warning signs:** Any evidence row calls a device readback a “true length”; a hand-maintained list has 21 or 26 entries; or a raw sport record appears in the shipped set.

### Pitfall 2: Saving is omitted or readback is transitional

**What goes wrong:** The app selection looks successful but the device remains on its former palette or another unexpected palette.

**Why it happens:** The existing capture establishes that the palette does not reach the device until Save. [VERIFIED: .claude/theme-capture/README.md:22-30]

**How to avoid:** Navigate semantically from home, tap Save, then record all bounded polls and require two consecutive equal multisets. Retry missing semantic controls exactly twice, not the entire cycle.

**Warning signs:** `save_button` missing; a readback equals the prior palette; two stable reads never occur; a stable palette differs from the expected shipped theme.

### Pitfall 3: Coordinate replay passes on one tablet but targets the wrong control

**What goes wrong:** The runner taps a stale location after app/device layout changes.

**Why it happens:** Existing tooling uses coordinate taps after hierarchy inspection, but the phase explicitly rejects coordinate-only authority. UIAutomator exposes hierarchy inspection and object selectors, so use the hierarchy to locate semantic controls. [CITED: https://developer.android.com/reference/androidx/test/uiautomator/UiDevice]

**How to avoid:** Identify the exact category then one exact display-name cell and Save control in the current hierarchy; fingerprint the catalogue and fail on drift. Capture the hierarchy/screenshot locally after exhausted retries.

### Pitfall 4: Restoration ignores pixels or Ceiling components

**What goes wrong:** The test leaves a target in MORPH or restores only base colour/power while changing Tile pixels or Ceiling component state.

**Why it happens:** Matrix state includes separately fetched tile colours/effect; Ceiling expands it with uplight/downlight fields. [VERIFIED: src/lifx/devices/matrix.py:1421-1459; src/lifx/devices/ceiling.py:325-520]

**How to avoid:** Snapshot and verify base colour, power, effect settings, chain/pixels and Ceiling components before mutation. If any required pre-read fails, do not mutate.

### Pitfall 5: Resuming a different experiment

**What goes wrong:** An interrupted run resumes after the app catalogue, firmware, runner, selected targets or timeouts changed, producing a mixed dataset.

**How to avoid:** Store the exact provenance digest and private device bindings before first mutation; refuse resume unless every D-11 dimension matches, and resume at the next unfinished cycle only.

### Pitfall 6: Mistaking emulator or a healthy one-off for UAT evidence

**What goes wrong:** Tests pass but no actual FIDELITY-02/03 evidence exists, or a non-Tile product does not respond.

**How to avoid:** Keep emulator tests for pure support code only. The phase remains `human_needed` without a real responding indoor non-Tile matrix product. Quiesce selected test lights from competing app/Home Assistant pollers, and retain all three sequential cycles. [VERIFIED: 08-SPEC.md:128-139, 160-163; .agents/skills/spike-findings-lifx-async/SKILL.md:23-27]

## Code Examples

### Use the existing MORPH and exact readback seam

```python
from lifx.protocol.protocol_types import FirmwareEffect
from lifx.theme import ThemeLibrary

theme = ThemeLibrary.get("mondrian")
await matrix.set_effect(FirmwareEffect.MORPH, palette=theme.colors)
readback = await matrix.get_effect()
```

The source defines the relevant exact values as “`MAX_PALETTE_COLORS: Final[int] = 16`” and its setter pads its wire palette to 16 while preserving the actual `palette_count`. [VERIFIED: src/lifx/const.py:123-128; src/lifx/devices/matrix.py:1169-1279] The runner must compare `readback.palette` to the frozen `ThemeLibrary` palette with the existing multiset rule, not treat this as static theme application.

### Safe temporary keep-awake lifecycle

```python
prior = adb_global_get("stay_on_while_plugged_in")
try:
    adb_global_put("stay_on_while_plugged_in", enabled_value)
    await run_preflight_and_cycles()
finally:
    adb_global_put("stay_on_while_plugged_in", prior)
```

The Android setting name is “`stay_on_while_plugged_in`”; Android documents supported values as an OR-able set of plugged-in power-source flags. [CITED: https://developer.android.com/reference/android/provider/Settings.Global] The exact temporary value should be chosen and documented by the implementation; it is not locked in Phase 8. [ASSUMED]

## State of the Art

| Old approach | Current approach | Impact |
|--------------|------------------|--------|
| Initial raw capture used picker coordinates and a fixed settle delay. | Phase 8 uses semantic app navigation, retries, catalogue fingerprinting and bounded stable LAN readbacks. [VERIFIED: .claude/theme-capture/tools/sweep_themes.py:37-184; 08-CONTEXT.md:D-01..D-05] | Evidence becomes reproducible and detects UI/catalogue drift rather than silently selecting a nearby control. |
| A single Tile (product 55) capture supplied palette data. | The phase repeats the fixed pair on Tile and a live-validated indoor non-Tile matrix target. [VERIFIED: .claude/theme-capture/README.md:52-67; 08-SPEC.md:70-80] | Evidence is explicitly bounded to observed product/firmware/cycles but no longer Tile-only. |
| Raw JSONL capture stood alone. | Private append-only diagnostic/checkpoint records are projected into an allowlisted JSON authority plus Markdown review record. [VERIFIED: 08-CONTEXT.md:D-08..D-12, D-19..D-21] | Resume and failure diagnosis do not leak household/device identifiers into git. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A private checkpoint root under `.planning/local/phase-08-theme-fidelity/` is the right final path. | Recommended Project Structure | A different ignored path may be required by project conventions; planner should choose/add an explicit ignore rule before writing private data. |
| A2 | `hashlib` plus canonical JSON is the appropriate provenance-digest implementation. | Standard Stack | Non-canonical serialisation could permit an unsafe resume; tests must prove equality/mismatch behaviour. |
| A3 | The exact temporary keep-awake enabled value is left for implementation. | Code Examples | A wrong value might not keep the tablet awake on its charging mode; runner must read/restore and preflight-test the selected value. |

## Open Questions (RESOLVED)

1. **RESOLVED — legitimate non-device sources:** Phase 8 performs no new source search,
   undocumented endpoint call or credential-bearing request. Every ceiling row defaults to
   `device-ceiling-unresolvable`. A row may use `cited-source-length` only when execution is
   supplied an already-authorised, legitimately accessible non-device source with a durable
   citation and an integer length of at least 16; otherwise the default determination remains.
   Absence of such a source is an evidenced result, not a blocker or permission to broaden scope.

2. **RESOLVED — exact real Ceiling/Luna fixture:** No fixture identifier is guessed or
   committed. The mode-0600 private target configuration supplies the one approved
   `non-tile-matrix` binding, and live preflight must prove indoor confirmation, app/LAN identity,
   reachability, firmware and a real non-Tile matrix capability before mutation. Unavailable,
   ambiguous or invalid secondary hardware produces Plan 08-04 outcome `human_needed` and exit 2;
   it can never produce a passing report, and neither Tile nor emulator is a substitute.
   [VERIFIED: 08-CONTEXT.md:D-15..D-18; 08-SPEC.md:FIDELITY-03]

3. **SUPERSEDED 2026-08-16 — reset-palette signature:** The capture-era local reset
   observation has no canonical reusable tuple and is not an input to Phase 8. No signature is
   guessed, hard-coded or supplied by an operator. The runner records every poll, establishes
   stability only through two consecutive exact unordered reads, and retains every stable
   palette unequal to the expected shipped theme as mismatch evidence. [VERIFIED:
   08-CONTEXT.md:D-05; user correction 2026-08-16]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | run harness/tests | ✓ | 0.11.29 | — |
| Python | harness | ✓ | 3.14.5 | supports the project’s 3.10–3.14 range |
| `adb` | Android UI automation | ✓ | 1.0.41 | none; preflight must still verify exactly one authorised tablet |
| Signed-in LIFX Android app | app-side MORPH cycles | unverified | — | none |
| Source Tile and indoor non-Tile matrix hardware | FIDELITY-02/03 | unverified | — | no substitute; FIDELITY-03 becomes `human_needed` |

**Missing dependencies with no fallback:**

- A preflight-approved Android tablet, source Tile, and responding indoor non-Tile matrix target. Their live state must be established by the runner, not inferred from this research.

## Validation Architecture

Skipped — `.planning/config.json` explicitly sets `workflow.nyquist_validation` to `false`.

For support code, retain the project’s ordinary test gates: focused `uv run --frozen pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pyright`. The plan must also add branch-complete tests for pure validation/finalisation code; hardware UAT remains independent. [VERIFIED: AGENTS.md; 08-SPEC.md:136-139]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No | Do not introduce cloud authentication, tokens or undocumented endpoints. |
| V3 Session Management | No | The signed-in app is a preflight condition; the harness must not manage or export its session. |
| V4 Access Control | Yes | Explicit private two-target allowlist; no unrestricted discovery or exterior-device mutation. |
| V5 Input Validation | Yes | Strict schema/provenance validation for private checkpoint and public evidence; reject unexpected fields and identifier patterns. |
| V6 Cryptography | Limited | Use standard-library digesting only for accidental-mismatch detection, not as a secrecy claim. [ASSUMED] |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Private identifiers enter committed evidence | Information disclosure | Generate public records from an allowlist, reject identifier/address patterns, and test negative fixtures. |
| UI drift selects wrong theme/device | Spoofing / tampering | Require one authorised tablet, app version/catalogue fingerprint, semantic category/name selectors and two bounded retries. |
| Wrong LAN target is mutated | Tampering | Bind IP, serial and app label privately; verify LAN/app identity before mutation; never fleet-discover. |
| Interrupted run falsely passes | Integrity | Private append-only checkpoint, exact provenance resume gate, all fixed cycles required, and finalisation only after restoration. |
| Restoration hides a changed state | Tampering | Capability-complete snapshot before mutation and readback verification after restoration; restoration failure is terminal. |
| Device/network behaviour is over-generalised | Repudiation / integrity | Record only sanitised model/product/firmware and measured cycles; make no fidelity claim beyond them. |

## Sources

### Primary (HIGH confidence)

- [`08-SPEC.md`](08-SPEC.md) - locked scope, edge coverage, prohibitions and acceptance criteria.
- [`08-CONTEXT.md`](08-CONTEXT.md) - locked runner, target, restoration and evidence decisions.
- [`data/themes.jsonl`](../../../data/themes.jsonl) - mechanically parsed shipped 25-theme ceiling set and fixed samples.
- [`src/lifx/devices/matrix.py`](../../../src/lifx/devices/matrix.py) - MORPH setter/readback and state methods.
- [`src/lifx/theme/theme.py`](../../../src/lifx/theme/theme.py) - unordered uint16 multiset equality.
- [`src/lifx/const.py`](../../../src/lifx/const.py) - 16-colour protocol ceiling.
- [`src/lifx/devices/ceiling.py`](../../../src/lifx/devices/ceiling.py) - Ceiling component-state restoration seam.
- [`src/lifx/products/registry.py`](../../../src/lifx/products/registry.py) - Tile, Ceiling and Luna product capability metadata.
- [`.claude/theme-capture/README.md`](../../../.claude/theme-capture/README.md) and [`sweep_themes.py`](../../../.claude/theme-capture/tools/sweep_themes.py) - authorised Save-before-readback and existing semantic hierarchy workflow.

### Secondary (MEDIUM confidence)

- [Android UiDevice reference](https://developer.android.com/reference/androidx/test/uiautomator/UiDevice) - hierarchy dumping, semantic object lookup and diagnostics.
- [Android Settings.Global reference](https://developer.android.com/reference/android/provider/Settings.Global) - temporary `stay_on_while_plugged_in` setting semantics.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - uses existing standard library, repository APIs and installed ADB; no new package.
- Architecture: HIGH - all boundaries are locked in CONTEXT/SPEC and map to opened implementation seams.
- Pitfalls: HIGH - derived from locked edge/prohibition coverage, existing capture artefacts and real-hardware spike constraints.

**Research date:** 2026-08-15  
**Valid until:** implementation start; real app/device availability and firmware must be rechecked by preflight.
