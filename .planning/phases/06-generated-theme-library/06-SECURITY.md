---
phase: 06
slug: generated-theme-library
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-15
---

# Phase 06 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Phase 06 replaced a hand-written Python palette table with one generated from a committed
data file. The security-relevant change is that `data/themes.jsonl` — trusted-but-validated
input — now crosses into shipped, importable Python via `src/lifx/theme/generator.py`.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| raw capture → `data/themes.jsonl` | Hardware-captured JSONL is mechanically converted into the committed data file; the conversion is the integrity-critical step | Theme display names, categories, uint16 HSBK palettes — all public LIFX app data |
| `data/themes.jsonl` → `src/lifx/theme/data.py` | The committed data file becomes executable Python via the generator | Same, promoted to module-level Python literals |
| generator → `ruff` subprocess | The generator shells out to ruff to format the temp file before the atomic rename | Generated source text, on a path derived from `Path`, never from record content |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-06-01 | Tampering | `emit_data_module()` string fields | medium | mitigate | Every string reaches generated source only through `repr()` (`generator.py:414-422`). Every key — slug **and** alias — passes `_is_canonical_key()`: `type(key) is str`, non-empty, `isascii()`, `key == key.lower()`, `isidentifier()` (96-101), enforced at 278 (alias) and 286 (slug). Colour fields validated with `type(value) is not int`, which rejects bools as well as string numerics (187-193), then range-checked. Name and category validated as non-empty ASCII `str` (416-418). Failures raise a controlled `RuntimeError` naming the record and line — 8 `RuntimeError` sites, **0 bare asserts**. Emit-time checks back the validator (414, 418). | closed |
| T-06-02 | Tampering | `format_generated_files()` subprocess | low | mitigate | Fixed argv `[sys.executable, "-m", "ruff", *command, *targets]` (465-466). No `shell=True` anywhere in the module. Targets are `Path`-derived, never record-derived. Pattern copied from the previously audited products generator. | closed |
| T-06-03 | Tampering (supply chain) | regeneration inputs | medium | mitigate | Sole input is `DATA_FILE` (`generator.py:33`), the committed local `data/themes.jsonl`. A grep for `urlopen\|urllib\|requests\|http://\|https://\|socket.\|aiohttp` across `src/lifx/theme/` returns nothing outside the generated data module. No device access. Zero packages installed by this phase, so no package-legitimacy audit applies. | closed |
| T-06-04 | Repudiation | `data.py` vs data file drift | low | accept | D-23: the operator knowingly declined a drift gate. Regeneration idempotence was verified by hand (double-run byte-identical, `git status` clean); drift after a stale regeneration would ship silently. See Accepted Risks. | closed |
| T-06-05 | Tampering | conversion script output | medium | mitigate | Every palette mechanically derived and verified multiset-equal at uint16 precision against its source (capture for app records, the pre-v1.2 `_THEMES` table for orphans) before commit; no hand-typed values; collision guard fails loudly. Independently re-confirmed during verification: all 138 non-sport slugs re-derived from the raw 179-record capture and compared as uint16 `Counter` multisets — 0 missing, 0 mismatched. | closed |
| T-06-06 | Tampering (supply chain) | regeneration inputs | medium | mitigate | Same control and same evidence as T-06-03: local committed data file only, no network, no device, no undocumented LIFX endpoints. | closed |
| T-06-07 | Repudiation | `data.py` vs data file drift | low | accept | D-23, as T-06-04 — no drift gate by operator decision; idempotence verified once by hand and recorded in `06-02-SUMMARY.md`. See Accepted Risks. | closed |
| T-06-08 | Information disclosure | committed data file | low | accept | The data file carries only public theme names and colour values already shipped in the LIFX app. Raw app strings with emoji stay in `.claude/theme-capture/`, which is neither packaged nor published. See Accepted Risks. | closed |
| T-06-09 | Information disclosure | generated module file permissions | low | mitigate | Added after the phase, closing code-review finding WR-03. `tempfile.mkstemp()` creates the temp file `0600` and the atomic rename carried that mode onto `data.py`, so a regenerated module shipped owner-only. The fix widens the mode before the replace, but does so as `0o666 & ~umask` (`generator.py`, `_current_umask()`), so the process umask still governs: a restrictive `0077` umask still yields `0600`. The widening exposes nothing beyond T-06-08's already-public content, and world-readability is required for the module to be importable once installed from a wheel. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (`high`) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-06-01 | T-06-04, T-06-07 | A drift gate between `data/themes.jsonl` and the generated `data.py` was declined knowingly (D-23). A stale or interrupted regeneration would ship silently rather than failing CI. Mitigating factors: the generator writes atomically (temp file, format, rename) so a partial file cannot land, and idempotence was verified by hand at phase close. Severity is low — drift produces wrong colours, not a compromise. | Operator (D-23, `06-SPEC.md`) | 2026-08-14 |
| R-06-02 | T-06-08 | The committed data file exposes only theme names, categories and colour values that the LIFX app already ships publicly. The raw capture, which contains the original emoji-bearing app strings, stays in `.claude/theme-capture/` and is excluded from the package. | Operator (Phase 6 discussion, `06-CONTEXT.md`) | 2026-08-14 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-15 | 9 | 9 | 0 | `/gsd-secure-phase 6` — orchestrator, ASVS L1 grep-depth verification against the implementation |

Corroborating evidence from the same phase, gathered independently of this audit:

- `06-REVIEW.md` (deep code review, 0 critical): proved by execution that all strings reach
  `data.py` via `repr()` post-validation, that the emitted module contains zero backslash
  escapes, that `type(v) is int` / `type(key) is str` close the bool and subclass holes, and
  that the generator has no network imports.
- `06-VERIFICATION.md` (16/16 must-haves): re-derived every slug and palette from the raw
  capture rather than trusting the summaries, and confirmed regeneration is byte-identical.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-15
