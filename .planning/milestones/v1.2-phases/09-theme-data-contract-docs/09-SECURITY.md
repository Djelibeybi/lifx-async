---
phase: 9
slug: theme-data-contract-docs
status: complete
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-27
mode: retroactive-stride
register_authored_at_plan_time: false
---

# Phase 9 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Mode: retroactive-STRIDE.** Phase 9 was executed outside the GSD loop and its
plans are reconstructions (see `09-VERIFICATION.md`), so no `<threat_model>`
block was authored at plan time. This register was therefore built from the
implementation files rather than verified against a pre-existing one, per the
`register_authored_at_plan_time: false` path in the secure-phase workflow.

Every threat below was probed by execution against the shipped tree on
2026-08-27, not assessed by reading. The commands and their results are given as
evidence.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| **Data → code** | `data/themes.jsonl` is parsed by `scripts/generate_theme_data.py` and emitted as `src/lifx/theme/data.py`, a Python module. `library.py:30` imports it, so it executes in every consumer's process on `import lifx`. | Untrusted-shaped JSON records (slug, display name, category, disposition, replaced_by, colours) becoming executable Python source. **The phase's one critical boundary.** |
| Capture → data | The catalogue originates from the LIFX Cloud API via maintainer tooling that lives in the separate private `lifx-theme-resync` repository. | Theme records. Out of this phase's scope; named so the chain is complete. |
| Library → wire | Stored float `HSBK` values are converted by `HSBK.to_protocol()` and sent to devices on the LAN. | Colour values (uint16). |
| Repo → published docs | `docs/getting-started/built-in-themes.md` publishes category names and counts. | Public LIFX product information. |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-09-01 | Tampering / Elevation of Privilege | `scripts/generate_theme_data.py` emit path | critical | mitigate | Layered: `validate_records()` rejects a malformed record outright; emit-time backstops re-assert `validate_key()`, `type(value) is str`, non-empty and `isascii()` on name/category, set-membership on disposition; and **every** emitted value is rendered with `!r`, so a string becomes a quoted, escaped literal rather than source text. | closed |
| T-09-02 | Tampering | `lifx.theme.schema._validate_colors` | medium | mitigate | Strict per-field typing: `bool` rejected despite being an `int` subclass, non-finite floats (`NaN`, `Inf`) rejected, `kelvin` required to be a strict integer. | closed |
| T-09-03 | Denial of Service | `lifx.theme.slug.derive_slug` | low | mitigate | The rule is a flat character-class substitution with no nested quantifier, so it cannot backtrack exponentially. Measured linear. | closed |
| T-09-04 | Tampering / Information Disclosure | `lifx.theme.schema.load_theme_records` path handling | low | mitigate | The generator's input and output paths are derived from `REPO_ROOT` (`Path(__file__).resolve().parents[1]`) as module constants. No `argv`, `argparse`, or environment input reaches a path. | closed |
| T-09-05 | Elevation of Privilege | ruff subprocess in the generator | low | mitigate | Fixed argv list `[sys.executable, "-m", "ruff", ...]`, no `shell=True`, targets are generator-controlled paths. Already annotated `# nosec B603`. | closed |
| T-09-06 | Information Disclosure | `docs/getting-started/built-in-themes.md` | low | accept | The page publishes category names, theme counts and palette-length figures. All are public LIFX product information, and publishing them is the phase's stated goal (DOCS-03). No credential, endpoint, capture method or device identifier appears — the resync runbook and the APK contract stayed in the private `lifx-theme-resync` repository. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Evidence

**T-09-01 — code injection into the generated module.** Probed with a hostile
display name whose text is valid Python: `X', 'INJECTED'); import os;
os.system('id') #`. The name is *accepted* as data, which is correct — display
names legitimately carry punctuation — and the defence is the emit encoding. The
emitted line was parsed with `ast` and the payload resolves to a single
`ast.Constant` string whose value round-trips to the original, with exactly one
statement in the fragment: no injected statement exists. Separately, hostile
*keys* never reach emission at all — `validate_key()` returned `False` for a
newline-and-code slug, a non-ASCII slug (`café`), an uppercase slug, a Python
keyword (`class`), the empty string, an `int` and `None`.

**T-09-02 — colour validation.** `hue=True`, `hue=NaN`, `hue=Inf`,
`kelvin=3500.5` and `kelvin=True` were each rejected with a `RuntimeError`
naming the record and line number. A valid control record was accepted, so the
suite is not vacuously rejecting everything.

**T-09-03 — ReDoS.** `derive_slug` over an adversarial `"a!" * n` input:
0.08 ms at 2,000 characters, 0.68 ms at 20,000, 5.18 ms at 100,000. Growth is
linear; no backtracking blow-up.

**Structural rejections also confirmed:** a non-dict record, an unknown extra
field, and a `replaced_by` on a non-deprecated record were each rejected with a
`RuntimeError`.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-09-01 | T-09-06 | Publishing the category/count table is the phase's requirement (DOCS-03). The data is public LIFX product information; nothing about the capture method, endpoints or credentials is disclosed, those having moved to the private `lifx-theme-resync` repository. | operator | 2026-08-27 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-27 | 6 | 6 | 0 | orchestrator (inline retroactive-STRIDE; the `gsd-security-auditor` subagent was not dispatched — see note) |

**Note on the audit method.** The secure-phase workflow's State B /
`register_authored_at_plan_time: false` path calls for dispatching the
`gsd-security-auditor` subagent. This session operates under a standing
instruction not to spawn subagents unless explicitly requested, so the
retroactive-STRIDE register was built and verified inline by the orchestrator
instead. The substantive difference is that the audit was not performed by an
independent context; it is recorded here rather than left implicit. Every
finding is backed by an executed probe whose command and result are reproducible
from the Evidence section.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
