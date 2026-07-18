---
phase: 5
slug: reliability-documentation
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-17
validated: 2026-07-18
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Revision 2 (2026-07-18) — scope correction.** Revision 1 was seeded at planning
> time from plans 05-01..05-03 only and described this as a docs-only phase where
> "no code changes occur; pytest is untouched". That stopped being true: the three
> gap-closure plans (05-04, 05-05, 05-06) edit **rendered docstrings in `src/`**, so
> the Python gates (pytest / ruff / pyright) are load-bearing here and are recorded
> below. The prose is still the deliverable — but some of it now lives in source.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | zensical (docs build) **+** pytest / ruff / pyright — the gap plans edit `src/` docstrings, so the Python gates apply |
| **Config file** | `mkdocs.yml`, `pyproject.toml` |
| **Quick run command** | `uv run zensical build --strict` |
| **Full suite command** | `uv run --frozen pytest && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run zensical build --clean --strict` |
| **Estimated runtime** | ~8 s docs build (clean); ~112 s pytest (2618 tests) |

**Baseline — SUPERSEDED (this is the substantive change in revision 2).** Revision 1
recorded a baseline of *"exactly 8 pre-existing anchor warnings"* in `docs/api/effects.md`
(5) and `docs/api/index.md` (3), and defined "green" as *exit 0 AND no warning naming an
edited page* — explicitly excusing those 8 as *"not this phase's failure"*.

**Plan 05-06 (G-05-7 / D5-23) disproved that framing.** The 8 warnings were a *defect set*,
not a constant: 5 were type annotations markdown was parsing as link references (fixed by
backticking), and 3 were anchors pointing at mDNS API symbols that were linked from
`api/index.md` but had never been rendered (fixed by adding the three `:::` targets). The
current, permanent baseline is:

> **`uv run zensical build --clean --strict` exits 0 with ZERO warnings** — and both CI
> invocations in `.github/workflows/docs.yml` (lines 56, 114) carry `--strict`, so the
> warning class cannot silently drift back.

The intermediate `'8 issues found'` (05-04, 05-05) and `'3 issues found'` (05-06 Task 1)
assertions in those plans' `<automated>` blocks were **point-in-time rungs of a deliberate
8 → 3 → 0 descent**. They are correct as of the commit that carried them and are
superseded by the zero-warning end state. Re-running them verbatim today goes red *because
the phase finished the job* — that is not a regression, and future audits must not read it
as one.

---

## Sampling Rate

- **After every task commit:** the task's `<automated>` gate (content greps) + `uv run zensical build --strict`; add `uv run --frozen pytest` for any task touching `src/`
- **After every plan wave:** full build green at zero warnings under `--strict`
- **Before `/gsd-verify-work`:** full suite green + the manual accuracy read-through (see Manual-Only Verifications)
- **Max feedback latency:** ~8 s for docs-only tasks; ~2 min when the Python gates apply

---

## Per-Task Verification Map

All statuses below were **re-run and observed** during the revision-2 audit (2026-07-18),
not inherited from the plans' self-reports.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | DOCS-01 | content+build | `grep -q '^### Gen4 Power-Save Wake Tail' docs/user-guide/troubleshooting.md && grep -q 'version_major >= 4' … && grep -q 'asyncio.sleep(15)' …` | ✅ | ✅ green |
| 05-01-02 | 01 | 1 | DOCS-01 | content+build | `! grep -q 'async with discover(' … && ! grep -q 'Default is 3.0' … && grep -qi 're-broadcast' …` | ✅ | ✅ green |
| 05-01-03 | 01 | 1 | DOCS-01 | content+build | `grep -q 'user-guide/troubleshooting.md#gen4-power-save-wake-tail' docs/faq.md` | ✅ | ✅ green |
| 05-02-01 | 02 | 2 | DOCS-02 | content+build | `! grep -q '1 / 30' … && ! grep -qE '30\+ FPS' … && ! grep -q 'packet loss is normal' …` | ✅ | ✅ green |
| 05-02-02 | 02 | 2 | DOCS-02 | content+build | `grep -q '^## Streaming and Flow Control' … && grep -q 'latest-frame-wins' … && grep -q '10 FPS' …` | ✅ | ✅ green |
| 05-03-01 | 03 | 1 | DOCS-02 | content+build | `! grep -q 'Batched Discovery' … && grep -q 'Low-Latency One-Shots' …` | ✅ | ✅ green |
| 05-03-02 | 03 | 1 | DOCS-02 | content+build | `! grep -q '30+ FPS' docs/architecture/overview.md && grep -q 'animation/flow.py' … && grep -q 'default: 15.0' CLAUDE.md` | ✅ | ✅ green |
| 05-04 (gap) | 04 | 3 | DOCS-01, DOCS-02 | content+build+pytest | `! grep -rq 'Since v1.1' docs/ CLAUDE.md src/ && grep -q 'paces frame delivery against device acknowledgements' … && test "$(grep -cF '(default 15.0)' src/lifx/api.py)" = "2" && [Layer 1..8 renumber] && uv run --frozen pytest tests/test_api -q` | ✅ | ✅ green |
| 05-05 (gap) | 05 | 4 | DOCS-01, DOCS-02 | content+build+pytest | `! grep -qF 'await discover_devices(' … && test "$(grep -cF 'async for device in discover_devices(' …)" = "3" && ! grep -qF '_request_lock' CLAUDE.md && grep -qF '(source, sequence, serial)' CLAUDE.md && grep -qF 'escalating schedule' docs/architecture/overview.md` | ✅ | ✅ green |
| 05-06 (gap) | 06 | 5 | DOCS-01, DOCS-02 | content+build+pytest+lint+types | See **05-06 durable gate** below | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### 05-06 durable gate (corrected — see Audit Findings)

```bash
# G-05-2 — line-wrap-insensitive (the plan's single-line grep is defective; see finding 2)
test "$(tr '\n' ' ' < docs/getting-started/quickstart.md | tr -s ' ' \
        | grep -o 'unicast discovery round-trip' | wc -l | tr -d ' ')" = "1"
test "$(grep -c 'No Discovery' docs/getting-started/quickstart.md)" = "0"
! grep -qF 'Connect by IP without discovery' docs/architecture/overview.md
# G-05-3 — operator-agreed wording, verbatim
grep -qF 'purpose-built network stack with the following characteristics:' docs/api/animation.md
! grep -qF 'bypasses the connection layer' docs/api/animation.md
test "$(grep -c 'is by design' docs/api/animation.md)" = "0"
# G-05-5/06 — de-jargoned, de-ID'd rendered docstrings
test "$(grep -c 'wall-time' src/lifx/network/connection.py)" = "0"
grep -qF "Automatic retransmits on an escalating schedule within each request's" src/lifx/network/connection.py
# G-05-7 — the permanent end state (supersedes every intermediate warning-count rung)
test "$(grep -cF '(`list[Light]`)' docs/api/effects.md)" = "5"
uv run zensical build --clean --strict 2>&1 | grep -qF 'No issues found'
test "$(grep -c 'zensical build --clean --strict' .github/workflows/docs.yml)" = "2"
```

### G-05-4 structural gate (run-on paragraphs — not expressible as a grep)

```bash
# 0 = every mkdocstrings-published heading is followed by a blank line, so its list
# renders as a list. Was 23 at 05-06 planning time. Requires a built site.
python3 - <<'PY'
import re, pathlib
pat = re.compile(r'<p>[^<]*\w:\s*\n\s*-\s', re.M)
print(sum(len(pat.findall(p.read_text(encoding='utf-8', errors='ignore')))
          for p in pathlib.Path('site/api').rglob('*.html')))
PY
```

---

## Wave 0 Requirements

None — existing infrastructure covers all phase requirements. Every task verifies against
already-present files (`docs/**/*.md`, `CLAUDE.md`, `src/lifx/**/*.py`) and the
already-installed toolchain (zensical, pytest, ruff and pyright are all in the lockfile).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Status |
|----------|-------------|------------|-------------------|--------|
| Accuracy of every figure in the new prose (sub-250 ms, 15 s polling, `version_major >= 4`, ~20 FPS ceiling, ~10 FPS Capsule at 16×8 zones / 3 packets per frame) | DOCS-01 + DOCS-02 | Factual review against sources is not mechanisable — a grep proves a number is *present*, never that it is *correct* | Read the new/changed sections against 05-RESEARCH.md §Verified Numbers; every figure must trace to that table with no invented numbers | ✅ signed off — 05-UAT.md tests 1–5 |
| Judgment-tier prohibition verdicts (8 from plan 05-05, 9 from plan 05-06) | DOCS-01 + DOCS-02 | `category: values` fences carry no test-tier enforcement; in an autonomous run their verdicts are non-authoritative LLM-judge outputs | Operator reviews the verdict tables at the end-of-phase checkpoint | ✅ signed off — 05-UAT.md tests 1 and 6 (2026-07-17/18) |

---

## Audit Findings — revision 2 (2026-07-18)

1. **Stale baseline corrected (material).** Revision 1's "8 warnings are not this phase's
   failure" framing was superseded by 05-06/D5-23, which proved them a fixable defect set.
   Recorded baseline is now zero warnings under `--strict`, gated in CI. Left uncorrected,
   this document would have licensed 8 warnings back in.

2. **Defective gate corrected (would have false-RED'd forever).** Plan 05-06's G-05-2 gate
   is `test "$(grep -c 'unicast discovery round-trip' docs/getting-started/quickstart.md)" = "1"`.
   The phrase is present exactly once and correct, but **wraps across quickstart.md lines
   96–97**, so a line-based `grep -c` returns 0. The content passes; the gate does not. The
   map above records a whitespace-normalised form. Independently flagged by the verifier.
   *No content defect — do not "fix" the prose to satisfy a broken grep.*

3. **Scope corrected.** "Docs-only, pytest untouched" was true of 05-01..05-03 and false of
   05-04..05-06, which edit `src/` docstrings. Python gates are now recorded.

4. **Map completed.** Revision 1 mapped 7 tasks across 3 plans; the phase executed 6 plans.
   The three gap-closure plans are now mapped.

5. **No coverage gaps.** Every requirement (DOCS-01, DOCS-02) has automated verification;
   no MISSING or PARTIAL classifications, so no auditor spawn and no Wave 0 scaffold.

| Metric | Count |
|--------|-------|
| Gaps found (coverage) | 0 |
| Record defects found | 4 (baseline, defective gate, scope, incomplete map) |
| Resolved | 4 |
| Escalated | 0 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (10/10 mapped units)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (vacuous — no MISSING references)
- [x] No watch-mode flags (every command is one-shot; `zensical serve` never appears in a verify)
- [x] Feedback latency < 10 s for docs-only tasks (~8 s build)
- [x] All recorded commands re-run and observed green (2026-07-18), not inherited from self-reports
- [x] `nyquist_compliant: true` set in frontmatter
- [x] `status: validated` set — resolves the NOT-VALIDATED reading at milestone close

**Approval:** approved 2026-07-18 (revision 2 — audited post-execution against all six
executed plans; baseline and one defective gate corrected; all gates observed green).
