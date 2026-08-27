---
phase: 8
reviewers: [opencode, claude]
reviewed_at: 2026-08-15T08:46:47.501Z
plans_reviewed: [08-01-PLAN.md, 08-02-PLAN.md, 08-03-PLAN.md, 08-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 8

## OpenCode Review

# Cross-AI Plan Review — Phase 8: Hardware Fidelity Validation

## Summary

Four well-structured plans that faithfully implement the locked SPEC/CONTEXT decisions (D-01..D-21) and the 25/26/Carlton count correction. Repository checks confirm every load-bearing claim I traced: the 25-row ceiling set is mechanically derivable from `data/themes.jsonl` (`disposition=="lifx-app" & len(colors)==16`), Carlton 🔵 is the sole raw sport record among the 26, `cheerful` (Moods/5) and `mondrian` (Art Series/16) qualify as the earliest pair, `MAX_PALETTE_COLORS=16` exists at `src/lifx/const.py:128`, `MatrixLight.get_effect()` slices `palette[:palette_count]` (`matrix.py:1082-1087`), `set_effect()` is the MORPH path (`matrix.py:1169-1278`), `Theme.palette_equals()` does duplicate-sensitive `Counter` equality (`theme.py:287`), and `HSBK.__eq__` compares at uint16 granularity (`color.py:282-291`). The principal risks are an `autonomous: true` flag on a hardware-dependent plan, an unstated fire-and-forget caveat on `set_effect`, and an ambitious 100%-branch-coverage gate.

## Strengths

- **Count correction is data-pinned.** `08-03-PLAN.md` derives 25/26/Carlton from both JSONL sources and adds a regression test rather than a parallel hand list — matches D-20 and SPEC R1 (`08-SPEC.md:42-55`). Verified: 25 shipped slugs and 26 raw records including `Carlton 🔵` reproduce from the committed files.
- **Correct reuse of existing seams.** Plans call `MatrixLight.set_effect(FirmwareEffect.MORPH, palette=...)` and `get_effect()` rather than hand-rolling packets (`08-02-PLAN.md` Task 1 key_links). Verified the setter pads to 16 while preserving `palette_count` (`matrix.py:1256-1275`) and the readback slices to `palette_count` (`matrix.py:1084-1086`), so a 5-colour `cheerful` readback is not falsely inflated to 16.
- **Fail-closed evidence boundary.** The private/public projection split (D-08..D-12, D-19..D-21), allowlist schema, atomic pair write, and `human_needed` exit-2 path for missing non-Tile hardware are all backed by SPEC acceptance criteria (`08-SPEC.md:162-165`) and the existing capture privacy contract.
- **Restoration is capability-complete.** `08-02` Task 2 snapshots power/base/effect/pixels and Ceiling uplight/downlight before mutation and verifies after — maps to real APIs (`ceiling.py:675-752`, `matrix.py:610,954`). The `restoration_failure` exit-3 distinct from pass/mismatch is a strong tampering control.
- **Provenance-gated resume (D-11).** `08-02` Task 1 enumerates every provenance dimension and refuses resume on any mismatch; `08-04` Task 2 refuses to rerun under a mixed dataset. This addresses the "resuming a different experiment" pitfall directly.

## Concerns

### HIGH — `autonomous: true` on `08-04-PLAN.md` contradicts its `user_setup`

`08-04-PLAN.md` front matter sets `autonomous: true`, yet the plan body and `user_setup` block declare operator-supplied private targets, a signed-in tablet, quiesced pollers, and a `human_needed` classification when the non-Tile fixture is absent. An autonomous executor will either block forever or falsely fail. The plan *content* is correct (it never claims emulator substitution), but the flag is wrong. Set `autonomous: false` (or `manual: true` if the workflow supports it) for 08-04; the 24-cycle hardware run is inherently human-gated per SPEC (`08-SPEC.md:128-129`) and STATE.md:161.

### MEDIUM — `set_effect()` is fire-and-forget; plans don't state the implication

`MatrixLight.set_effect()` uses `self.connection.send_packet(...)` (`matrix.py:1278`), not `request()` — it is unacked. The library cycle's stability rule ("two consecutive identical unordered palettes") absorbs this, but neither `08-01` nor `08-02` calls out that the first post-`set_effect` poll may still return the *previous* effect and that the two-identical-reads rule is what makes this safe. Add a one-line note in `08-01` Task 1 action so the implementer doesn't add a fixed sleep or treat a single transitional read as failure. (The app Save path has the same shape, so the same rule covers both — worth stating once.)

### MEDIUM — `HSBK` objects vs raw uint16 tuples: comparison helper is ambiguous

`08-01`'s research example defines `palette_key(colours: list[tuple[int,int,int,int]]) -> Counter[tuple[...]]`, implying the runner converts `HSBK` to uint16 tuples. But `Theme.palette_equals()` (`theme.py:287`) already compares `HSBK` objects whose `__eq__` is uint16-granular (`color.py:282-291`). The plan should pick one: reuse `Theme.palette_equals()` (preferred — it's the existing domain rule) or convert to tuples via `HSBK.as_tuple()` and document why a second equality path exists. Duplicating equality logic risks divergence from the shipped `Theme` semantics.

### MEDIUM — `08-02` Task 3 mandates 100% branch coverage on a hardware-orchestrating file

`coverage report --fail-under=100 --branch` on `uat_theme_fidelity.py` is ambitious: the file contains `finally`/cancellation/`KeyboardInterrupt` paths, ADB subprocess branches, and async cleanup. Achieving 100% branch coverage requires thorough injection seams (which the plans do specify) and negative fixtures for every terminal status. The plan lists the negative fixtures, but the coverage gate could become a time sink or tempt branch-pruning. Consider scoping the 100% gate to the *pure* validation/finalisation functions (D-21 logic) and requiring *line* coverage + key-path branch coverage for the async orchestration, matching how the repo tests other hardware harnesses.

### LOW — `D-16` narrows SPEC's FIDELITY-03 candidate set, dropping Candle

SPEC target (`08-SPEC.md:74`) lists "Candle, Ceiling or other non-Tile matrix product". CONTEXT D-16 and the plans restrict to Ceiling-preferred/Luna-fallback, omitting Candle. This is a locked refinement, so it's authoritative, but if the operator has only a Candle available, the plan forces `human_needed`. Confirm with the operator that a Ceiling or Luna is actually reachable before 08-04 runs; otherwise relax D-16 to re-admit Candle.

### LOW — `08-03` scanner excludes SPEC/PATTERNS by convention, not by mechanism

`08-03` Task 2 scopes the stale-claim regression to four active docs and excludes SPEC/PATTERNS because they "quote the defect to be corrected." This is a manual enumeration (`('PROJECT','REQUIREMENTS','ROADMAP','README')`), not a path/label mechanism — a future doc added under `.planning/phases/08-...` carrying a stale count would be silently unscanned. Acceptable for now (the phase owns those four), but note the brittleness.

### LOW — No explicit handling of `get_effect()` returning `palette=None`

`get_effect()` returns `MatrixEffect` with `palette if palette else None` (`matrix.py:1093`). If a device reports `palette_count=0` (e.g., effect OFF), the runner's comparison helper receives `None`, not `[]`. The plans don't show how the runner normalises `None` to an empty list before `Counter` comparison. A cheap guard, but unspecified — add it to `08-01` Task 1's normalisation step.

## Suggestions

1. Flip `08-04` `autonomous` to false; keep 08-01/08-02 autonomous.
2. In `08-01` Task 1, add: "`set_effect()` is unacked (`send_packet`); stability is established solely by two consecutive identical `get_effect()` readbacks — never by a fixed sleep or a single read."
3. Standardise on `Theme.palette_equals()` for the comparison; drop the bespoke `palette_key`/`palettes_match` helpers unless the runner must compare pre-`HSBK` uint16 tuples (and if so, derive them via `HSBK.as_tuple()` and assert parity with `palette_equals` in a test).
4. In `08-02` Task 3, scope `--fail-under=100 --branch` to pure validation/finalisation functions via `--include` of named functions or a separate module split (pure helpers in a `_pure.py`, orchestration in the runner). Keeps the strict gate where it's cheap and honest.
5. Add a `None`-to-`[]` normalisation assertion for `get_effect()` readback in `08-01` tests.
6. In `08-04` Task 2, before `--run`, have the runner print the resolved non-Tile product class; if only a Candle is available, surface the D-16 restriction and stop rather than silently failing preflight.

## Risk Assessment

**MEDIUM.** The plans are thorough, map cleanly to verified repository seams, and the 25/26/Carlton and HSBK-equality claims all check out against actual data and code. The HIGH concern is a metadata flag (`autonomous: true` on 08-04), not a plan-logic defect — easily fixed and the body already behaves correctly. The MEDIUM concerns (unacked `set_effect` documentation, comparison-helper duplication, 100%-branch-coverage scope) are implementation-quality risks, not correctness blockers, and the plans' injection/fixture design gives the implementer room to resolve them. No evidence of scope creep, missing error handling for the core flows, dependency-ordering errors (waves 1→2→3 are correctly blocked), or security gaps — the privacy allowlist, restrictive file modes, and no-fleet-discovery rules are consistently enforced. Once the `autonomous` flag and the `set_effect`/comparison notes are corrected, this is a LOW-risk execution.

---

## Claude Review

# Cross-AI Plan Review — Phase 8: Hardware Fidelity Validation

Repository read and verified at `main` (`6dd6e5d`). All findings below cite source I opened.

## 1. Summary

The four plans are unusually rigorous on the parts that are cheap to be rigorous about — mechanical data derivation, privacy allowlisting, evidence cardinality, resume provenance — and thinnest on the part that actually decides whether Phase 8 produces evidence at all: driving the Android app. The FIDELITY-01 half (08-03 plus the finaliser's `derive_ceiling_determinations()`) is correct and verifiable: I reproduced the 25/26/Carlton split from the two JSONL files exactly as specified. The FIDELITY-02/03 half rests on a stated-but-false premise — that `sweep_themes.py` already supplies semantic device/theme/Save selection — and on a restoration contract that, read literally against `matrix.py`, will classify a passing run as `restoration_failure`. Two of the defects below (`speed` units, picker scrolling) are hard blockers that no amount of test coverage will surface, because both live in the injected-adapter seam the tests define.

## 2. Strengths

- **The ceiling count is right and mechanically derivable.** `data/themes.jsonl` filtered on `disposition == "lifx-app"` and `len(colors) == 16` yields exactly the 25 sorted slugs quoted in 08-RESEARCH.md:79; `.claude/theme-capture/themes.jsonl` yields 26, the extra being `Carlton 🔵` in `🏆 AUSSIE RULES`. 08-03's inline verify command and 08-02 Task 3's `derive_ceiling_determinations()` both derive rather than hardcode, and 08-03's acceptance criterion explicitly forbids a parallel slug list. This is the strongest part of the phase.
- **Multiset comparison is not ceremonial — it is load-bearing for the chosen sample.** `mondrian`'s shipped palette contains four repeated HSBK tuples (e.g. `(0,0,65535,6500)` and `(43690,65535,65535,3500)` each appear more than once). A `set()` comparison would silently pass a 12-colour readback. The plans' insistence on `Counter` (matching `src/lifx/theme/theme.py:249` `palette_equals()`) is correct and the chosen sample proves it.
- **The theme pair is genuinely the earliest qualifying one.** `.claude/theme-capture/picker-order.txt:1-16` confirms `Cheerful` is picker entry 1 and `Mondrian` is the first `🎨 ART SERIES` entry at line 16; `data/themes.jsonl` confirms 5 and 16 colours respectively, straddling `MAX_PALETTE_COLORS` (`src/lifx/const.py:128`).
- **`human_needed` is wired as a first-class outcome, not an escape hatch.** 08-02 Task 1 and 08-04 Task 1 both require exit 2 with no official file written when the non-Tile target is absent, and 08-02's negative tests reject product 55 / emulator / Exterior explicitly. This correctly implements SPEC.md:164-165.
- **Two-projection privacy model.** Building the public record from an allowlist rather than redacting in place (08-02 Task 3) is the right shape, and the negative fixtures are enumerated concretely rather than gestured at.

## 3. Concerns

### HIGH — `EffectSnapshot.speed` round-trip is unit-mismatched; restoration will fail a passing run

`MatrixLight.get_effect()` returns `speed=response.settings.speed` — raw protocol **milliseconds** (`src/lifx/devices/matrix.py:1091`, and `MatrixEffect.speed` is documented as milliseconds at `matrix.py:178`). `MatrixLight.set_effect()` takes `speed: float` in **seconds** and converts: `speed_ms = round(speed * 1000) if speed else 3000` (`matrix.py:1239`).

08-02 Task 2 says to snapshot `EffectSnapshot.speed` from `get_effect()` and "restore complete effect settings with `set_effect()`", then "re-read and compare every required snapshot field at protocol precision." A pre-state MORPH at 3000 ms restores as 3,000,000 ms, verification mismatches, and the plan's own rule fires: outcome `restoration_failure`, exit 3, `finalisable == false`. A fully successful 24-cycle run is thereby reported as a restoration failure. The `else 3000` branch is a second trap: a snapshot with `speed == 0` (a device with the effect OFF) restores as 3000, not 0.

The injected tests cannot catch this — the fake device is written to whatever contract the implementer assumed, so the test agrees with the bug.

### HIGH — No scroll step exists, and `mondrian` is not on-screen

D-02 and both runner plans resolve the theme by "one exact display-name match in the current hierarchy", with absence after two retries meaning fail-closed stop. A `uiautomator dump` contains only rendered nodes. `picker-order.txt:16` puts `Mondrian` 15 entries down the list, and the existing tool's visible window is `LIST_TOP = 1830` to `LIST_BOTTOM = 2580` (`sweep_themes.py:49-50`) — roughly three or four cells. The existing tool solves this with `find_and_tap()`'s swipe loop (`sweep_themes.py:151-184`).

Neither plan lists a scroll/swipe function. 08-01's artefact list is `load_theme_specs`, `palette_key`, `adb`, `dump_ui_hierarchy`, `find_semantic_control`, `poll_stable_palette`, `run_tracer_cycle`, `build_parser`, `main` — no traversal. 08-02 adds no UI function at all. As specified, every `mondrian` cycle (12 of the 24) fails its semantic lookup and halts the run at exit 2. The tracer in 08-01 only runs `cheerful`, which *is* the first visible cell — so the tracer passes and the gap surfaces only in Wave 2, on hardware, at 08-04.

### HIGH — Category matching cannot be an exact match against the shipped record

D-02 and 08-02 Task 1 say to resolve "the category and exact display name derived from the fixed theme record (`Moods`/`Cheerful`, then `Art Series`/`Mondrian`)". The shipped records carry emoji-stripped, title-case categories (META-01/META-02) — I read `Moods` and `Art Series` from `data/themes.jsonl`. The app's own headings are `'🙂 MOODS'` and `'🎨 ART SERIES'` (raw capture records, and `sweep_themes.py:60-72` `HEADINGS`). An exact string match of the derived category against the picker heading matches nothing, ever.

The display names happen to survive (`'Cheerful'`, `'Mondrian'` carry no emoji in the raw capture), so the *name* half of D-02 is safe for this fixed pair — but only by luck, and the plans do not say so.

### HIGH — "Reusable semantic selectors already exist" is false; scope and estimates follow from it

08-CONTEXT.md:203 and 08-RESEARCH.md both assert `sweep_themes.py` "already contains semantic `theme_button` and `save_button` lookup". It does not. `theme_button` appears nowhere in the tool — only in `README.md:27` as prose. The tool has `THEME_BUTTON = (1099, 524)` and `SAVE_BUTTON = (900, 2682)` as hardcoded coordinates (`sweep_themes.py:44-45`), tapped blind (`:130`, `:186`). The only semantic use of a resource-id is `sheet_is_open()`, a boolean predicate (`:120-125`). There is no home-screen navigation, no device-tile selection, and no MORPH-surface navigation anywhere in the file — the tool assumes the operator has already parked the app on a light running MORPH (`README.md:41`).

So D-01's full chain (home → unique device tile → device-surface verification → MORPH control → MORPH-surface verification → category → theme → Save) is entirely new UI automation against an app whose hierarchy nobody has inspected for those surfaces. 08-01 estimates 24k tokens across 2 tasks and 08-02 35k across 3. Those numbers look like they were costed against the "reuse existing patterns" premise.

### HIGH — Pixel-restoration verification cannot converge when the pre-state is a running effect

08-02 Task 2 requires snapshotting "every colour of every tile" and then: "If an active effect makes a pixel observation transitional, retain every restore poll privately and require the same bounded two-consecutive snapshot semantics; do not waive pixel verification."

A running MORPH mutates pixels continuously. Two consecutive identical full-matrix reads will effectively never occur, so the bounded deadline expires and the run terminates at exit 3. This is not hypothetical for these targets: the documented capture method (`README.md:41`) presumes the light is already running MORPH, and the operator's fixture lights plausibly are. Worse, the pixel snapshot is not meaningful state in that case — restoring the *effect* regenerates pixels regardless, making the pixel write both redundant and unverifiable. The plan restores pixels, then effect, then power, which guarantees the effect overwrites what was just restored.

### MEDIUM — The tests cannot import the runner

`.planning/phases/08-hardware-fidelity-validation/uat_theme_fidelity.py` is not importable from `.../tests/test_uat_theme_fidelity.py`. `pyproject.toml:109` sets `pythonpath = ["src", "scripts"]` only, and pytest's default `prepend` import mode inserts the *test file's* directory (`tests/`), not its parent. Neither plan lists a `conftest.py` in `files_modified` or in its artefact section. Adding a `sys.path` insertion at the top of the test module collides with the project rule that all imports go at the top of the file (CLAUDE.md). A `conftest.py` in the phase directory is the clean fix and should be a named artefact.

### MEDIUM — Focused pytest commands inherit repo-wide `addopts` and pollute the worktree

`pyproject.toml:113-125` sets `addopts` including `--cov=lifx --cov-branch --cov-report=xml --junitxml=junit.xml --timeout=30`. 08-01's two verify commands and 08-02's Tasks 1–2 run `uv run --frozen pytest <path> -q -k ...` without `-o addopts=''`, so each writes `coverage.xml` and `junit.xml` into the tree. The project rule is explicit that untracked files must not be ignored. 08-02 Task 3 gets this right (`-o addopts=''`); the others should match. The 30 s per-test timeout also silently bounds any injected orchestration test.

### MEDIUM — 100% branch coverage on the whole runner is a demanding, unstated design constraint

08-02 Task 3's gate is `coverage run --branch --include='.../uat_theme_fidelity.py' … --fail-under=100`, scoped to the *entire* file — including ADB subprocess wrappers, `Device.connect` orchestration, signal/cancellation paths and the keep-awake lifecycle. That is achievable only if literally every I/O call sits behind an injected adapter, which the plans mention ("narrow injected ADB/device/checkpoint adapters") but never specify as a hard architectural requirement. As written, the coverage gate is what will force the design, discovered late. `[tool.coverage.report] exclude_lines` (pyproject.toml:147-155) does cover `if __name__ == "__main__":`, which helps.

### MEDIUM — 08-03 edits `.planning/ROADMAP.md` in Wave 1 alongside 08-01

Both are Wave 1. If the phase runs with worktrees, 08-03 mutates `ROADMAP.md` while the orchestrator also owns post-merge ROADMAP sync (execute-plan.md `update_roadmap` §, single-writer contract). This is a known merge-conflict shape in this workflow. Low blast radius, but worth sequencing 08-03 outside a parallel wave or excluding ROADMAP from the worktree commit.

### LOW — "strict pyright" is claimed but the repo runs standard mode

08-RESEARCH.md and both runner plans repeatedly say "strict pyright". `pyproject.toml:91` sets `typeCheckingMode = "standard"`, and CLAUDE.md agrees. `include = ["src", "scripts/generate_theme_data.py"]` (`:95`) does not cover the phase directory; passing the file explicitly on the CLI does check it (it is not in `exclude`), so the verify command works — but it verifies a weaker gate than the plans claim.

### LOW — The plans say "display name" where the data says `name`

`data/themes.jsonl` records carry keys `category, colors, disposition, name, slug` — there is no `display_name` field. The plans' `ThemeSpec.display_name` and the public JSON's `display_name` are fine as output names, but `load_theme_specs()` must read `name`. Trivially resolvable, worth stating so an executor does not go hunting.

## 4. Suggestions

1. **Normalise the effect snapshot at the boundary.** Store `EffectSnapshot.speed` in milliseconds (as read) and restore with `set_effect(speed=snapshot.speed / 1000)`, with an explicit test asserting the round-trip `get → restore → get` is identity for both a MORPH pre-state and a `speed == 0` OFF pre-state. Better still: add a named helper in the runner with the unit conversion documented in one place, since `matrix.py` is asymmetric here.
2. **Add a bounded semantic scroll to 08-01's tracer, not 08-02.** Name it in the artefact list (`scroll_to_semantic_control()`), give it its own retry budget separate from the two lookup retries, and make the tracer exercise `mondrian` — not just `cheerful` — so the traversal gap fails in Wave 1 on a fake hierarchy rather than in Wave 3 on hardware. This is exactly what a tracer is for.
3. **Define category matching as normalised, not exact.** Reuse the emoji-strip + case-fold rule that already exists for `get_by_category()` in `src/lifx/theme/library.py`, and add a test asserting `'🎨 ART SERIES'` resolves from the record's `Art Series`. Keep display-name matching exact, and add an assertion that both fixed slugs' `name` values are emoji-free so the exactness assumption is pinned rather than lucky.
4. **Narrow pixel restoration to the case where it is meaningful.** If the snapshot effect is not `OFF`, restore the effect and verify effect settings + power + base colour; record pixels as diagnostic-only with an explicit `pixels_verified: false` and a stated reason. If the snapshot effect is `OFF`, restore and verify pixels with the two-consecutive rule. Also restore the effect *before* pixels, or the effect write invalidates the pixel write.
5. **Correct the reusable-asset claim in CONTEXT/RESEARCH** so the executor is not told semantic selectors exist, and re-cost 08-01/08-02. A realistic first step is an operator-run hierarchy dump of the home screen, device surface and MORPH surface, committed nowhere but used to write the selectors — otherwise the tracer is being written blind.
6. **Name `conftest.py` as a Plan 08-01 artefact** with a single `sys.path` insertion for the phase directory, and add `-o addopts=''` to every focused pytest command in 08-01 and 08-02.
7. **Note in 08-01's `sh`/`adb` helper contract that the existing analogue swallows failures.** `sweep_themes.py:76-83` returns `.stdout` only and never checks `returncode`, so a failed `adb` call returns `""` and reads as "control absent". The new `adb()` must raise on non-zero and surface stderr, or every ADB fault will be misclassified as a semantic-lookup miss and consume the two retries.

## 5. Risk Assessment

**Overall: HIGH.**

08-03 alone is LOW risk and independently valuable — it is data-derived, mechanically tested and correct. 08-02's finaliser and evidence schema are MEDIUM: demanding but well-specified. The risk concentrates in 08-01/08-02's app-automation path and restoration lifecycle, where three verified defects (speed units, missing traversal, exact category match) each independently prevent a passing 24-cycle run, and where the phase's own automated tests are structurally incapable of catching any of them — the injected adapters encode the same assumptions as the production code. Compounding this, the plans' cost and reuse assumptions rest on a `sweep_themes.py` capability that does not exist, so the executor discovers the true scope mid-Wave-1. The failure mode is not silent-wrong evidence — the fail-closed design is genuinely good, and a mis-restored or halted run cannot masquerade as a pass — it is repeated hardware runs that terminate at exit 2 or 3 with the operator's lights mutated and no evidence produced.

Fixing suggestions 1–4 before execution moves this to MEDIUM. Fixing 1–4 and re-scoping 08-01 to include real hierarchy reconnaissance moves it to LOW-MEDIUM.

---

## Consensus Summary

Both reviewers independently verified the mechanical 25-shipped/26-raw/Carlton distinction, the suitability of `cheerful` and `mondrian`, the need for duplicate-sensitive palette comparison, and the strength of the fail-closed private/public evidence boundary. Both also regard the whole-runner 100% branch-coverage gate as an execution risk unless the implementation is deliberately decomposed around injectable or pure seams.

The reviews disagree materially on overall readiness. OpenCode rates the plans MEDIUM risk and sees the restoration contract as capability-complete. Claude rates them HIGH risk after tracing concrete source behaviour that the plans do not currently account for: effect-speed milliseconds versus seconds, missing picker scrolling for `mondrian`, category normalisation, absent reusable semantic selectors, and non-convergent pixel verification for a running effect. These source-cited findings are actionable even though only one reviewer raised them; they can independently prevent a successful hardware run and should be resolved through `$gsd-plan-phase 8 --reviews` before execution.

### Agreed Strengths

- The 25 shipped exactly-16-colour target set and 26 raw-record explanation are mechanically correct and avoid a second hand-maintained list.
- Exact unordered multiset comparison is necessary, especially for duplicate-bearing `mondrian`.
- Privacy allowlisting, provenance-gated resume, distinct terminal outcomes, and `human_needed` handling make false-positive evidence unlikely.
- Wave dependencies broadly separate runner construction, documentation correction, and final hardware evidence.

### Agreed Concerns

- Requiring 100% branch coverage across the entire hardware-orchestrating runner may drive late architecture churn or brittle tests unless pure logic and injected I/O boundaries are explicit.
- The hardware plan needs a deliberate human boundary; OpenCode specifically flags `08-04` as incorrectly marked `autonomous: true` despite mandatory operator setup.

### Divergent Views

- **Overall risk:** OpenCode says MEDIUM and expects small plan corrections; Claude says HIGH because several source-verified defects can block every real run.
- **Restoration:** OpenCode praises the complete snapshot surface; Claude shows that speed-unit asymmetry and active-effect pixel transitions make the literal restore/verify sequence fail.
- **Android automation:** OpenCode accepts the semantic-selection direction; Claude finds that the cited capture tool uses hard-coded coordinates, lacks home/device/MORPH navigation, and requires bounded scrolling that the plans omit.
- **Comparison implementation:** OpenCode prefers direct reuse of `Theme.palette_equals()`; Claude accepts a `Counter`-based helper but requires the uint16 conversion contract to remain explicit.
