---
phase: 12
slug: ipv6-discovery-plumbing
status: verified
threats_open: 0
asvs_level: 1
created: 2026-08-29
verified_revision: 655ee8a43852f39e7a5f1c4e183a6e944f48ae2e
---

# Phase 12 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Public caller to targeted discovery | Caller-supplied address selects validation, socket family, bind address, and destination | IP literal and optional IPv6 zone |
| Local UDP socket to discovery parser | Untrusted LAN responses enter existing source, packet-type, service, serial, and deduplication gates | Binary discovery datagrams |
| Operating-system scope resolution to UDP send | A numeric or named zone becomes a native interface scope | Local interface scope identifier |
| Concurrent tasks to per-call state | Each lookup owns its source, endpoint, seen set, and deadlines | Ephemeral discovery state |
| Cancellation to transport ownership | Task cancellation must close the owned datagram endpoint | Async lifecycle state |
| CI configuration to runner evidence | Narrow opt-ins select the required IPv6 tracer without broadening unrelated tests | Workflow flags and test conclusions |
| Test and runner output to tracked evidence | Verification must establish execution without copying infrastructure details | Sanitised categories, counts, and conclusions |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-12-01 | Spoofing | Discovery response path | high | mitigate | Existing source-ID, response-type, service, serial, and deduplication gates remain intact and covered by regressions | closed |
| T-12-02 | Tampering | Address-family selection | medium | mitigate | Family and wildcard derive from the validated destination through shared helpers | closed |
| T-12-03 | Denial of Service | Discovery timing loop | high | mitigate | Retransmission, idle, overall-deadline, deduplication, and cleanup invariants remain covered | closed |
| T-12-04 | Information Disclosure | Test and evidence fixtures | high | mitigate | Only synthetic, loopback, and documentation-range representations are tracked; raw infrastructure output is excluded | closed |
| T-12-05 | Tampering | Address representation | medium | mitigate | Public representation and production send-boundary tests cover accepted IPv6 forms | closed |
| T-12-06 | Denial of Service | Invalid target validation | high | mitigate | Empty, malformed, unscoped link-local, and zero-scope input fail before transport construction | closed |
| T-12-07 | Information Disclosure | Test literals and failures | high | mitigate | Tests and reports omit live routes, interface names, addresses, and discovery output | closed |
| T-12-08 | Tampering | Concurrent per-call state | high | mitigate | Real-endpoint concurrency tests prove independent transports and results | closed |
| T-12-09 | Denial of Service | Cancellation cleanup | high | mitigate | Event-synchronised cancellation tests prove endpoint closure and later reuse | closed |
| T-12-10 | Repudiation | Lifecycle evidence | medium | mitigate | Assertions use actual endpoint state and ResourceWarning-clean execution | closed |
| T-12-11 | Information Disclosure | Endpoint observations | high | mitigate | Evidence is restricted to synthetic address categories, family, wildcard, and lifecycle state | closed |
| T-12-12 | Elevation of Privilege | Windows emulator opt-in | high | mitigate | Dedicated fixture and exact CI selection keep the opt-in narrow | closed |
| T-12-13 | Repudiation | CI success claim | high | mitigate | The required current-revision Windows and Ubuntu jobs executed and passed | closed |
| T-12-14 | Denial of Service | Windows UDP scheduling | medium | mitigate | Retry and timeout policy remains narrowly bounded to the tracer | closed |
| T-12-15 | Information Disclosure | CI evidence | high | mitigate | Logs were inspected in place and only sanitised conclusions and counts were recorded | closed |
| T-12-16 | Tampering | Required branch gate | high | mitigate | The required tracer has no failure allowance and current evidence confirms execution | closed |
| T-12-17 | Tampering | Zoned link-local identity | high | mitigate | The validated caller literal is preserved through targeted device construction | closed |
| T-12-05-01 | Tampering / Denial of Service | IPv6 sockaddr conversion | high | mitigate | Positive scopes are preserved; explicit zero and oversized scopes are rejected before send | closed |
| T-12-05-02 | Denial of Service | Zone resolution failure | high | mitigate | Invalid names and numeric scopes fail immediately without calling send or closing the endpoint | closed |
| T-12-05-03 | Repudiation | Closure evidence | high | mitigate | Focused and frozen local gates plus current-revision cross-platform CI passed | closed |
| T-12-05-04 | Information Disclosure | Tests, diffs, and logs | high | mitigate | Synthetic representations and value-suppressed evidence preserve the privacy boundary | closed |
| T-12-05-05 | Spoofing / Tampering | UDP discovery responses | medium | mitigate | Existing response-validation and deadline invariant suites passed unchanged | closed |
| T-12-SC | Tampering | Package supply chain | low | accept | Phase 12 adds no dependency or lock-file change and uses the frozen uv environment | closed |
| T-12-05-SC | Tampering | Existing dependency set | low | accept | The direct zero-scope correction adds no dependency or package-management change | closed |

*Status: open · closed · open — below high threshold (non-blocking)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-12-01 | T-12-SC, T-12-05-SC | No supply-chain surface changed; the existing frozen dependency set is outside this phase's implementation delta | Phase plan | 2026-08-29 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-29 | 24 | 24 | 0 | Codex security gate |

The register was authored across all five Phase 12 plans. At ASVS level 1,
implementation, regression, privacy, and current-revision CI evidence confirms
that every critical/high mitigation is present. No unplanned endpoint,
authentication path, persistence field, file access, schema, dependency, or
trust boundary was introduced.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-29
