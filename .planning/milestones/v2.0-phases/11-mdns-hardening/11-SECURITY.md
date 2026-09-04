---
phase: 11
slug: mdns-hardening
status: verified
threats_total: 68
threats_open: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: 2026-08-29
verified: 2026-08-29
---

# Phase 11 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| LAN DNS packet → parser/cache | Untrusted names, classes, TTLs, RDATA and source addresses attempt to influence retained discovery state. | Attacker-controlled network data |
| Cache → private service record | Live TXT, SRV and address records become a candidate device identity and endpoint only after provenance and consensus checks. | Unauthenticated discovery metadata |
| Private record → public device | Internal connectivity and endpoint data can construct a user-visible `Device`. | Validated serial, product, address and diagnostic connectivity |
| Cache → outbound follow-up | Untrusted SRV targets can cause bounded A/AAAA multicast queries. | Hostname and query-attempt state |
| Cache → diagnostics | Rejection state must remain useful without exposing LAN identifiers or values. | Reason, record type and aggregate count only |
| Probe → operator evidence | A hardware-oriented diagnostic must not persist raw device or network identifiers. | Privacy-safe schema-v2 result |
| Private implementation → public API/docs | Internal record, generator and converter symbols must not become supported public contracts. | API surface and behavioural claims |
| Working tree/history → evidence | Planning, coverage and provenance evidence must not leak live identifiers or misstate a stale result. | Repository metadata and value-suppressed audit results |
| Operator disposition → history mutation | Privacy classification does not itself authorise rewriting shared or local history. | Explicit no-rewrite decision and reachability evidence |
| Locked environment → build/test | Security verification must not introduce dependency or coverage-policy drift. | Existing frozen dependencies and immutable-base gates |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-11-01 | Spoofing | Connectivity metadata | medium | mitigate | Exact `tm=2` mapping is diagnostic only; every other value falls back to WiFi. | closed |
| T-11-02 | Tampering | Device factory | high | mitigate | Literal connectivity validation and tests prove routing, retry and address state are unchanged. | closed |
| T-11-03 | Denial of service | mDNS socket bind | high | mitigate | Production binds an ephemeral port, avoids multicast membership, and has a direct-receipt regression. | closed |
| T-11-04 | Information disclosure | Synthetic tests | medium | mitigate | Fixtures use synthetic identifiers, loopback and documentation-only network data. | closed |
| T-11-05 | Tampering | TXT/SRV effective values | high | mitigate | Full live-set consensus rejects conflicting construction metadata and endpoints until expiry resolves ambiguity. | closed |
| T-11-06 | Spoofing | TXT serial | high | mitigate | TXT identity must be one valid unicast serial and conflicting identities fail closed. | closed |
| T-11-07 | Denial of service | Owner and TXT/SRV admission | high | mitigate | Owner, TXT and SRV identity ceilings exact-deduplicate refreshes and never evict admitted state. | closed |
| T-11-07R | Denial of service | Address cardinality | medium | accept | Superseded by D-15's stricter 256-per-owner and 1,024-per-sweep fail-closed caps. | closed |
| T-11-08 | Information disclosure | Discovery fixtures | high | mitigate | Phase fixtures and committed evidence contain no live identifiers. | closed |
| T-11-09 | Spoofing | Structural validation | medium | accept | Connectivity remains explicitly unauthenticated diagnostic metadata; no authenticity claim is made. | closed |
| T-11-10 | Tampering | Goodbye/cache-flush semantics | high | mitigate | Exact-RR grace/rescue and count-only unexpected cache-flush handling are covered by fake-clock tests. | closed |
| T-11-11 | Denial of service | Expiry scheduler | high | mitigate | Per-call goodbye indexing, bounded retained state and deadline-clamped processing prevent unbounded expiry work. | closed |
| T-11-12 | Information disclosure | Aggregate diagnostics | high | mitigate | Diagnostics expose stable reasons, types and counts only; identifier-bearing fields are prohibited. | closed |
| T-11-13 | Denial of service | Follow-up amplification | high | mitigate | Follow-up is capped at 64 case-folded targets and two failed attempts, with successful sends deduplicated. | closed |
| T-11-14 | Repudiation | Cross-call state | medium | mitigate | Cache, deadlines and query ledgers are owned by one discovery generator and concurrent calls are isolated. | closed |
| T-11-15 | Information disclosure | Public docs/examples | high | mitigate | Public prose omits private records and raw metadata; examples remain synthetic. | closed |
| T-11-16 | Spoofing | Documentation claims | high | mitigate | Documentation identifies connectivity as diagnostic and records legacy-unicast limitations. | closed |
| T-11-17 | Repudiation | Multicast-membership claims | medium | mitigate | Source, private docstrings and public documentation consistently describe unicast-only receipt. | closed |
| T-11-18 | Information disclosure | Public exports | high | mitigate | D-16 private record, generator and converter names have no public or compatibility aliases. | closed |
| T-11-19 | Tampering | API cutover scope | high | mitigate | Superseding D-16 removes the earlier public-factory expectation and contract tests enforce the final private boundary. | closed |
| T-11-20 | Information disclosure | Probe/test evidence | high | mitigate | Hardware discovery was not executed; probe behaviour is tested entirely with synthetic fixtures. | closed |
| T-11-21 | Denial of service | Migration regression | high | mitigate | Focused and frozen full suites pass without deleted, skipped or weakened tests. | closed |
| T-11-22 | Tampering | Public/private surface audit | high | mitigate | Runtime, AST and exact-token checks enforce private symbols and supported exports. | closed |
| T-11-23 | Information disclosure | Complete phase diff | high | mitigate | Immutable-base and value-suppressed audits cover tracked, intended-untracked and staged evidence. | closed |
| T-11-24 | Tampering | Patch-coverage source set | high | mitigate | Changed production sources are derived from the immutable diff and empty, excluded or weakened inputs fail closed. | closed |
| T-11-25 | Repudiation | Edge/prohibition evidence | medium | mitigate | Final verification accounts for every requirement, edge, prohibition and review finding. | closed |
| T-11-31 | Information disclosure | Planning state candidate | high | mitigate | The candidate was removed without echoing its value; reports retain location/category/disposition only. | closed |
| T-11-32 | Tampering | Preserved draft patches | high | mitigate | Dirty-set and per-file digest checks preserved executor-owned work before structured completion. | closed |
| T-11-33 | Repudiation | Partial execution | medium | mitigate | Signed authority commits, replacement-plan summary and fresh evidence distinguish historical from current results. | closed |
| T-11-34 | Information disclosure | External mapping | high | mitigate | The private mapping remained external and was not copied into repository, report, prompt or memory artefacts. | closed |
| T-11-35 | Tampering | Range/ref classification | high | mitigate | Value-suppressed reachability audit pinned merge base, refs, tags, upstream, worktrees and remote containment. | closed |
| T-11-36 | Information disclosure | Historical patches | high | mitigate | Historical candidate scans suppressed values and commit identity details. | closed |
| T-11-37 | Repudiation | Rewrite authority | high | mitigate | The operator explicitly selected no-rewrite against the committed privacy audit. | closed |
| T-11-38 | Denial of service | Accidental broad rewrite | medium | mitigate | No-rewrite avoided history mutation; the audited range and boundaries remain recorded. | closed |
| T-11-39 | Tampering | Rebase/rewrite range | high | mitigate | Not applicable after no-rewrite; the complete pre-disposition commit sequence remained unchanged. | closed |
| T-11-40 | Repudiation | Rewritten commits | high | mitigate | Not applicable after no-rewrite; existing signatures and DCO trailers were verified instead. | closed |
| T-11-41 | Information disclosure | Historical candidate | high | mitigate | Operator classification established an approved pseudonym; value-suppressed scans found no live or unresolved phase-owned candidate. | closed |
| T-11-42 | Tampering | Other refs/worktrees/remotes | high | mitigate | No branch, tag, worktree, remote, reflog or object-store mutation occurred. | closed |
| T-11-43 | Repudiation | Fresh verification evidence | medium | mitigate | Post-disposition focused, full, privacy, signature and DCO gates were rerun and recorded. | closed |
| T-11-10-01 | Spoofing | Cache admission | high | mitigate | Exact case-insensitive LIFX service ownership and SRV linkage gate all construction state. | closed |
| T-11-10-02 | Tampering | TXT consensus | high | mitigate | One-pass effective-value consensus rejects the second distinct construction value. | closed |
| T-11-10-03 | Elevation of privilege | Public discovery generator | high | mitigate | Exact service provenance is revalidated immediately before device construction. | closed |
| T-11-10-04 | Denial of service | Repeated TXT values | high | mitigate | Linear consensus operates under the independent 16-TXT identity ceiling. | closed |
| T-11-10-05 | Information disclosure | Rejection diagnostics | medium | mitigate | Service/TXT rejection diagnostics retain only reason and numeric counts. | closed |
| T-11-11-01 | Denial of service | Retained payload | high | mitigate | Retention is limited to 4,096 bytes per record and 262,144 bytes per sweep before storage. | closed |
| T-11-11-02 | Tampering | Byte accounting | high | mitigate | Exact costs survive goodbye grace/rescue and release only on actual expiry, with underflow tests. | closed |
| T-11-11-03 | Denial of service | Address ceilings | high | mitigate | Independent 256-per-owner and 1,024-per-sweep limits permanently fail affected state closed. | closed |
| T-11-11-04 | Spoofing | Address selection | high | mitigate | Unusable addresses are filtered before ranking and the selected address is revalidated at construction. | closed |
| T-11-11-05 | Information disclosure | Capacity diagnostics | medium | mitigate | Capacity events expose stable reasons and counts without names, addresses or TXT values. | closed |
| T-11-12-01 | Denial of service | Probe receive loop | high | mitigate | Overall, idle, expiry and retransmission clocks clamp every wait and re-evaluate simultaneous causes. | closed |
| T-11-12-02 | Denial of service | Probe follow-up | high | mitigate | Separate attempted/success ledgers enforce 64 targets, two failed attempts and no repeated success. | closed |
| T-11-12-03 | Tampering | Probe cache lifetime | medium | mitigate | Positive TTL, goodbye grace, rescue and final expiry match production fake-clock semantics. | closed |
| T-11-12-04 | Information disclosure | Probe evidence | high | mitigate | Schema-v2 validation recursively rejects raw identifiers before creating an output path. | closed |
| T-11-13-01 | Repudiation | Query-model docs | medium | mitigate | Contract tests require the initial PTR, one- and three-second retransmissions and conditional bounded follow-up. | closed |
| T-11-13-02 | Information disclosure | Public documentation | medium | mitigate | Contract tests prohibit private symbols and live/raw evidence in public prose. | closed |
| T-11-13-03 | Tampering | Documentation drift | medium | mitigate | Per-surface semantic tests reject omitted retransmissions and known false formulations. | closed |
| T-11-13-04 | Spoofing | Default integration claim | low | mitigate | Documentation preserves explicit-alternative and fallback wording rather than claiming default integration. | closed |
| T-11-14-01 | Repudiation | Conditional API tests | high | mitigate | Supported-device construction uses unskippable non-None assertions. | closed |
| T-11-14-02 | Information disclosure | Evidence/history | high | mitigate | Location-only current/staged/history scans prohibit raw mapping, identifiers and signer identity. | closed |
| T-11-14-03 | Tampering | Coverage gates | high | mitigate | Immutable-base branch coverage passes both production-source checkers without policy weakening. | closed |
| T-11-14-04 | Repudiation | Commit provenance | high | mitigate | Phase evidence verifies cryptographic signatures and DCO trailers with identities suppressed. | closed |
| T-11-14-05 | Elevation of privilege | Phase completion | high | mitigate | Completion occurred only after source audit, tests, coverage, privacy and provenance gates passed. | closed |
| T-11-SC | Tampering | Package supply chain | low | accept | No package installation, runtime dependency or lockfile change occurred across Plans 11-01 through 11-09. | closed |
| T-11-10-SC | Tampering | Package supply chain | low | accept | Plan 11-10 used the frozen existing environment and changed no dependency. | closed |
| T-11-11-SC | Tampering | Package supply chain | low | accept | Plan 11-11 used the frozen existing environment and changed no dependency. | closed |
| T-11-12-SC | Tampering | Package supply chain | low | accept | Plan 11-12 used the frozen existing environment and changed no dependency. | closed |
| T-11-13-SC | Tampering | Package supply chain | low | accept | Plan 11-13 used the frozen existing environment and changed no dependency. | closed |
| T-11-14-SC | Tampering | Package supply chain | low | accept | Plan 11-14 used the frozen existing environment and changed no dependency or coverage configuration. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*

*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` count towards `threats_open`.*

*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third party).*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-11-01 | T-11-09 | LAN discovery metadata is unauthenticated and remains diagnostic only; Phase 13 owns live unicast verification and no Phase 11 text claims authenticity. | Phase 11 plan authority | 2026-08-28 |
| AR-11-02 | T-11-SC, T-11-10-SC, T-11-11-SC, T-11-12-SC, T-11-13-SC, T-11-14-SC | Supply-chain work was excluded; the zero-runtime-dependency contract, frozen environment and lockfile remained unchanged. | Phase 11 plan authority | 2026-08-28 |

T-11-07R is not retained as an accepted exposure: D-15 superseded it with stricter finite address ceilings. Threats T-11-39 through T-11-42 are closed as non-applicable because the operator selected no-rewrite.

---

## Verification Evidence

| Evidence | Result |
|----------|--------|
| Current threat-focused synthetic suite | 398 passed; no hardware or live discovery used |
| Final frozen workspace suite | 4,002 passed, 12 planned deselections |
| Discovery immutable-gap-base patch coverage | 132 changed executable lines and 90 changed branches; pass |
| Probe immutable-gap-base patch coverage | 166 changed executable lines and 88 changed branches; pass |
| Static analysis | Ruff and Pyright passed in final Phase 11 verification |
| Privacy/provenance | Value-suppressed audits passed; signatures and DCO trailers verified with identities suppressed |
| Summary threat flags | No unplanned endpoint, authentication, file-access, schema, dependency, public API or trust boundary was introduced |

The plan-authored register and the current source/test anchors were checked at ASVS L1. With all threats closed and `threats_open: 0`, the secure-phase short-circuit applies and no deeper L2/L3 auditor run is required.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-29 | 68 | 68 | 0 | Codex `gsd-secure-phase` |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-29
