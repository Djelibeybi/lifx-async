---
phase: 5
slug: reliability-documentation
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-18
---

# Phase 5 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Scope note:** Phase 5 (reliability-documentation) edits Markdown prose plus a
handful of source docstring lines. No auth, session, input-validation, crypto,
network endpoint, or file-access artefact is created or modified. All six PLANs
carried a parseable `<threat_model>` block (register authored at plan time), so
this audit verifies the documented mitigations rather than scanning for new
attack surface. ASVS L1, block-on `high`: every threat is `low` severity, so no
threat counts toward the blocking gate.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| published docs → reader behaviour | Guidance shapes what application developers build against real devices (polling cadence, streaming FPS, connection/discovery expectations) | Behavioural guidance, code examples |
| internal planning artefacts → public site | `.planning/` and `.claude/` content (spike narratives, planning IDs, tuning constants) must not leak into published docs | Internal process vocabulary |
| source docstrings → rendered API reference | `connection.py` / `api.py` docstrings feed the published API pages; a wrong default is a site-wide contradiction | Public API contract |
| repo instructions (CLAUDE.md) → agent/contributor behaviour | Stale claims (concurrency model, constants, version) misdirect future automated and human work | Instruction accuracy |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-05-01 | Information Disclosure | troubleshooting.md, faq.md | low | mitigate | D5-03 forbids methodology narrative; prohibition + `grep -ci 'spike'` gate keeps internal spike/planning content out of published pages | closed |
| T-05-02 | Denial of Service | polling recipe (reader-side flooding) | low | mitigate | Recipe pinned to 15 s cadence, far below the ~20 msg/sec device limit; gate asserts `asyncio.sleep(15)` | closed |
| T-05-04 | Information Disclosure | animation.md | low | mitigate | D5-09 prohibition + negative greps keep internal tuning constants (gate threshold, ack expiry, probe placement) out of user-guide prose | closed |
| T-05-05 | Denial of Service | streaming example | low | mitigate | Example pinned at 20 FPS with explicit saturation guidance (~10 FPS Capsule-class), consistent with ~20 msg/sec limit | closed |
| T-05-06a | Information Disclosure | architecture/overview.md Layer 5 bullet | low | mitigate | New bullet uses D4-01/D4-02 behavioural wording only; negative grep asserts no tuning constants | closed |
| T-05-07a | Denial of Service | advanced-usage.md fire-and-forget example | low | mitigate | Example slowed to 20 FPS / one-shot scope; flooding-prone streaming framing removed | closed |
| T-05-06b | Information Disclosure | docs examples (faq, overview, advanced-usage, troubleshooting) | low | mitigate | Broken examples replaced with source-verified API usage — each snippet checked against shipped class/signature; no secrets in any example | closed |
| T-05-07b | Denial of Service | reader-side device flooding | low | mitigate | No FPS/polling figure raised; the D5-14 fix lowers the documented figure | closed |
| T-05-08 | Spoofing | version-attribution claims | low | mitigate | D5-12 removes the false version claim entirely rather than substituting a guess; prohibition blocks reintroduction | closed |
| T-05-09 | Information Disclosure | docs examples (troubleshooting, ceiling-lights, faq, advanced-usage) | low | mitigate | Broken examples replaced with source-verified API usage; every target value re-traced to the shipped signature | closed |
| T-05-10 | Tampering | CLAUDE.md concurrency model | low | mitigate | Bullet now matches connection.py's shipped receiver/correlation model, verified against `_pending_requests` | closed |
| T-05-11 | Denial of Service | reader-side device flooding | low | mitigate | No FPS/polling figure changes; animation.md rewrite states pacing and drops, lowering throughput expectations | closed |
| T-05-12 | Information Disclosure | rendered API reference (planning IDs, spike figures, lineage refs) | low | mitigate | Internal-process vocabulary removed from every published docstring; traceability retained in non-rendered `#` comments only | closed |
| T-05-13 | Tampering | published behavioural contract accuracy | low | mitigate | Every rewrite preserves shipped behavioural claims verbatim-in-substance; gates pin the contract substrings and overview.md wording anchor | closed |
| T-05-14 | Denial of Service | reader-side expectations (connection/discovery timing) | low | mitigate | No FPS/polling/timing figure added; removed constants lower copy-paste risk | closed |
| T-05-15 | Tampering | docs build integrity (silent warning drift) | low | mitigate | Both CI build invocations gain `--strict` (G-05-7c); future unresolved link or missing anchor fails the build | closed |
| T-05-SC | Tampering | npm/pip/cargo installs | low | accept | No package-manager installs occur in this phase (RESEARCH §Package Legitimacy Audit: none) | closed |

*Status: open · closed · open — below `high` threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

*Note: T-05-06/T-05-07 were reused across PLANs 05-03 and 05-04 for distinct components; suffixed `a`/`b` here to keep register rows unambiguous while preserving the plans' own numbering.*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-05-01 | T-05-SC | Supply-chain tampering via package installs is not applicable — this phase runs no npm/pip/cargo installs (RESEARCH §Package Legitimacy Audit confirmed none) | Avi Miller | 2026-07-18 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-18 | 17 | 17 | 0 | gsd-secure-phase (L1 short-circuit — register authored at plan time, all threats low/below block threshold) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-18
