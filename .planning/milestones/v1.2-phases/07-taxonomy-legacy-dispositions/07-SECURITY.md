---
phase: 07
slug: taxonomy-legacy-dispositions
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-15
---

# Phase 07 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| `data/themes.jsonl` → generator | Committed data file is the sole input; a tampered line is the attack surface | Theme records: slug, name, category, disposition, replaced_by, colours |
| generator → `src/lifx/theme/data.py` | Emitted source is imported by the package; injected text would execute at import | Python source text produced by `repr()` of validated values |
| caller → `get_by_category()` / `get_categories()` | Caller-supplied category string crosses into library code | Arbitrary user string, normalised by `derive_slug()` |
| docs → reader | Published documentation is trusted by users as a description of API behaviour | Category counts, legacy-name fates, deprecation replacements |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-07-01 | Tampering | `data/themes.jsonl` disposition/replaced_by fields | medium | mitigate | Verified in `scripts/generate_theme_data.py`: allowed-set check (`:289`, `_DISPOSITIONS` at `:54`), deprecated requires non-empty `replaced_by` (`:300`), `replaced_by` must be a canonical key (`:309`), cross-record resolution pass (`:359`), plus emit-time backstops re-asserting both invariants before any value reaches emitted source text (`:491`, `:497`) | closed |
| T-07-02 | Tampering (supply chain) | regeneration inputs | medium | mitigate | Verified: generator imports are `json`, `os`, `subprocess`, `sys`, `tempfile`, `pathlib`, `typing` and `lifx.*` only — no `urllib`, `requests`, `socket` or `http`. The single `subprocess.run` (`:549`) invokes `sys.executable -m ruff format/check` on local paths with a fixed argv and no shell. Zero packages installed by this phase | closed |
| T-07-03 | Information disclosure | `Theme.replaced_by` | low | accept | Field carries only public theme keys already listable via `get_available_themes()` | closed |
| T-07-04 | Denial of service | `derive_slug()` on caller input | low | accept | Verified `src/lifx/theme/slug.py:34` — a single `re.sub(r"[^a-z0-9]+", "_", …)`: negated character class, one quantifier, no alternation or nesting, so no catastrophic-backtracking structure. Linear in input length; no recursion | closed |
| T-07-05 | Information disclosure | `ValueError` messages | low | accept | Verified `src/lifx/theme/library.py:209` and `:214` — messages echo the caller's own input plus `get_categories()` output, both already public. Re-checked after the 6.4.0 rename (`db1ae95` + follow-up) changed the message text; no new data is disclosed | closed |
| T-07-06 | Tampering (supply chain) | taxonomy source | medium | mitigate | Verified: every import across the seven `src/lifx/theme/*.py` modules is stdlib (`collections`, `dataclasses`, `random`, `re`) or intra-`lifx`. No network capability anywhere in the theme layer; categories derive solely from the committed generated record set | closed |
| T-07-07 | Repudiation / integrity of claims | migration page tables | low | mitigate | Verified by execution against the shipped library: the nine category counts on the page match `data/themes.jsonl` exactly (Archives 60, Art Series 10, Holidays 15, Library 28, Moods 13, Music 14, Nature 8, Play 7, Space 11); `ThemeLibrary.get("fire")` returns `disposition="deprecated"`, `replaced_by="warm_ember"`; `holiday`→15 and `mood`→13 still resolve; all four retired names raise naming the documented replacement. Page is scoped in time by its "As of the 6.4.0 migration (2026-08-15)" note (D-10) | closed |
| T-07-08 | Spoofing (misattribution) | Library category description | low | mitigate | Verified at `docs/migration/theme-taxonomy-6.4.0.md:30-31` (prose plus the table's `Defined by` column), `src/lifx/theme/library.py:14` ("not app captures") and `:182` (`get_by_category()` docstring). Independently confirmed by the phase UAT test 1 (`07-UAT.md`) after the 6.4.0 rename | closed |
| T-07-09 | Tampering (supply chain) | docs toolchain | low | accept | Zero packages installed by this phase; `zensical` is a pre-existing dev dependency | closed |
| T-07-10 | Tampering | `replaced_by` on a non-deprecated record | low | accept | Acknowledged enforcement gap (R2-05, D-08 — deliberate user decision). Compensating control verified: `tests/test_theme/test_library.py:617` `test_replaced_by_only_on_deprecated_records` sweeps every shipped record and asserts `replaced_by is None` for any non-deprecated disposition, with a docstring naming the generator gap. CI runs it before ship | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-07-01 | T-07-03 | `replaced_by` exposes only public theme keys already enumerable through the public API | Planned disposition, 07-01-PLAN.md | 2026-08-15 |
| R-07-02 | T-07-04 | Slug normalisation is one bounded, non-backtracking regex pass; input is bounded by the caller's own string | Planned disposition, 07-02-PLAN.md | 2026-08-15 |
| R-07-03 | T-07-05 | Error messages echo caller input plus public category names; nothing sensitive to leak | Planned disposition, 07-02-PLAN.md | 2026-08-15 |
| R-07-04 | T-07-09 | No packages installed by this phase; docs toolchain unchanged | Planned disposition, 07-03-PLAN.md | 2026-08-15 |
| R-07-05 | T-07-10 | Generation-time enforcement of SPEC R5 deliberately deferred (D-08); caught at test time by a library-side shape sweep that CI runs before ship. Reversible: a one-line addition inside the existing replacement validation plus one failing-record test | Avi Miller (D-08) | 2026-08-15 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-15 | 10 | 10 | 0 | `/gsd-secure-phase 7` — orchestrator, ASVS L1 grep-depth verification against the implementation |

Register origin: `register_authored_at_plan_time: true` — all three PLAN files carry a
`<threat_model>` block, so this run verified planned mitigations rather than building a
retroactive STRIDE register. With `threats_open: 0` at ASVS L1 the workflow short-circuit
applies and no separate auditor pass was required.

Re-verification note: this audit ran **after** commit `a97796d`, which renamed the migration
page and rewrote the `get_by_category()` `ValueError` text. T-07-05, T-07-07 and T-07-08 all
touch surfaces that commit changed, so each was re-checked against the current tree rather
than against the state the plans described.

### Discrepancy found (documentation, not a threat)

`07-02-SUMMARY.md` states that "the Phase 6 no-network AST assertion still passes with
`slug.py` as the eighth theme-layer file". No such automated assertion exists in the test
suite — the Phase 6 no-network finding was a review-time inspection recorded in
`06-SECURITY.md:71`, not a test. The underlying control is real and was verified directly
here (T-07-02, T-07-06), so no threat is open; the summary's wording overstates the
mechanism. The theme layer also contains seven `.py` files, not eight.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-15
