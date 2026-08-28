---
phase: 10
slug: land-the-ipv6-thread-branch
status: verified
threats_open: 0
asvs_level: 1
created: 2026-08-28
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Caller → public API | User-supplied addresses enter device construction and lookup paths | IP literals and scope identifiers |
| LAN → mDNS parser/cache | Untrusted multicast and legacy-unicast records enter discovery state | DNS records, serials, addresses and service metadata |
| Library → operating system | Async transports acquire, publish and release UDP sockets | File descriptors, endpoint state and cancellation |
| CI runner → verification evidence | Platform capability and test results become merge evidence | IPv6 availability, test and coverage results |
| Operator → Thread hardware | The local probe selects and temporarily controls a physical device | Private hardware identifiers and device state |
| Hardware evidence → repository | A real run becomes a tracked shipment artefact | Pseudonymised identifiers, stage results and Git revision |
| Git branch → shipment | Local commits become the signed release history | Commit signatures, DCO trailers and reviewed source |
| Package supply chain → project | Dependency operations could alter executable inputs | Runtime and development dependencies |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| 10-01/T-10-01 | Tampering/DoS | mDNS record cache | medium | mitigate | Every persistent cache structure is directly capped; host, fallback and resolved-set boundaries have regressions | closed |
| 10-01/T-10-02 | Spoofing | mDNS TXT `id` | medium | accept | Deferred to Phase 11 MDNS-06 while mDNS is not in the default discovery flow | closed |
| 10-01/T-10-03 | Information disclosure | Hardware probe output | low | accept | Operator-local diagnostic; committed evidence is pseudonymised under `AGENTS.md` | closed |
| 10-01/T-10-19 | Repudiation | Patch-coverage evidence | high | mitigate | Fail-closed changed-line and branch checker with anti-weakening tests; result is advisory by operator decision | closed |
| 10-01/T-10-SC | Tampering | Package supply chain | low | accept | No dependency operation; zero-runtime-dependency contract unchanged | closed |
| 10-02/T-10-04 | DoS | Public address entry points | medium | mitigate | Shared validation rejects zone-less link-local addresses at all four entry points | closed |
| 10-02/T-10-05 | Spoofing | IPv4-mapped IPv6 input | medium | mitigate | Shared validator rejects mapped addresses | closed |
| 10-02/T-10-06 | Information disclosure | Address warning logs | low | accept | Operator-facing local debug logging; exposure shape is unchanged | closed |
| 10-02/T-10-SC | Tampering | Package supply chain | low | accept | No dependency operation; zero-runtime-dependency contract unchanged | closed |
| 10-03/T-10-07 | DoS | UDP send family | medium | mitigate | Send-time family mismatch raises `LifxNetworkError` before `sendto` | closed |
| 10-03/T-10-08 | DoS | mDNS failed open | medium | mitigate | Failure closes the owned endpoint/socket and clears all state | closed |
| 10-03/T-10-20 | DoS | mDNS phantom-open state | medium | mitigate | `is_open` requires all state fields and failed opens remain reopenable | closed |
| 10-03/T-10-09 | DoS | Peer-unreachable errors | high | mitigate | Peer errors remain non-fatal and are pinned by parameterised regressions | closed |
| 10-03/T-10-SC | Tampering | Package supply chain | low | accept | No dependency operation; zero-runtime-dependency contract unchanged | closed |
| 10-04/T-10-10 | Repudiation | IPv6 CI capability | high | mitigate | Mandatory CI cell turns missing IPv6 support into a failure | closed |
| 10-04/T-10-11 | Spoofing | IPv6 end-to-end proof | medium | mitigate | V6-only socket is asserted and delivery is proven by device-state readback | closed |
| 10-04/T-10-21 | DoS | IPv6 fixture setup | high | mitigate | `IPV6_V6ONLY` is set before bind; unsupported environments use the capability gate | closed |
| 10-04/T-10-12 | DoS | Emulator test cost | low | mitigate | One device, one server and an independent port bound the added work | closed |
| 10-04/T-10-SC | Tampering | Package supply chain | low | accept | Existing emulator development dependency only; no package operation | closed |
| 10-05/T-10-13 | Tampering | Hardware state restoration | high | mitigate | Full matrix/light state is captured and restoration runs in `finally`; current UAT restored successfully | closed |
| 10-05/T-10-14 | Repudiation | UAT record integrity | high | mitigate | Results derive from observed stages and record a timestamp and exact Git revision | closed |
| 10-05/T-10-15 | DoS | Optional streaming stage | low | mitigate | Streaming is opt-in, sequential and bounded | closed |
| 10-05/T-10-22 | DoS | Animator socket lifetime | low | mitigate | `Animator.close()` runs in `finally` | closed |
| 10-05/T-10-SC | Tampering | Package supply chain | low | accept | Standard-library implementation; no package operation | closed |
| 10-06/T-10-16 | Repudiation | Hardware evidence | high | mitigate | Fresh pseudonymised UAT passed connect/control and names its immediately preceding reviewed revision | closed |
| 10-06/T-10-17 | Tampering | Shipment history | high | mitigate | Branch remains off `main`; every Phase 10 commit is GPG-signed and DCO-certified | closed |
| 10-06/T-10-18 | Elevation of privilege | CI and patch gate | high | mitigate | Frozen suite and coverage checks remain intact; fail-closed checker was not weakened | closed |
| 10-06/T-10-23 | Repudiation | Gate artefact selection | medium | mitigate | Passing UAT artefact exists and no exception-override artefact exists | closed |
| 10-06/T-10-SC | Tampering | Package supply chain | low | accept | No dependency operation anywhere in the phase | closed |
| 10-07/T-10-21 | DoS | Invalid mDNS address | high | mitigate | Per-record validation failure is isolated and later valid records still yield | closed |
| 10-07/T-10-22 | DoS/Repudiation | Follow-up address queries | high | mitigate | Results yield before auxiliary sends; failures and retry state are isolated and bounded | closed |
| 10-07/T-10-23 | Spoofing | mDNS device construction | medium | mitigate | Construction retains the shared address validator | closed |
| 10-07/T-10-SC | Tampering | Package supply chain | low | accept | No dependency operation; zero-runtime-dependency contract unchanged | closed |
| 10-08/T-10-24 | DoS | mDNS cancellation | high | mitigate | Open is serialised; cancellation closes resources, clears state and permits reopen | closed |
| 10-08/T-10-25 | DoS | UDP cancellation | high | mitigate | Every unsuccessful open clears endpoint, protocol and family state and permits reuse | closed |
| 10-08/T-10-26 | Repudiation | Descriptor cleanup evidence | medium | mitigate | Real-socket ledger and ResourceWarning-as-error assertions prove cleanup | closed |
| 10-08/T-10-SC | Tampering | Package supply chain | low | accept | No dependency operation; zero-runtime-dependency contract unchanged | closed |

*Status: open · closed · open — below high threshold (non-blocking)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-10-01 | 10-01/T-10-02 | TXT serial validation belongs to Phase 11 MDNS-06 and mDNS is not yet the default discovery path | Operator via approved plan | 2026-08-28 |
| AR-10-02 | 10-01/T-10-03 | Raw hardware diagnostics remain private and transient; committed evidence is pseudonymised | Operator via approved plan | 2026-08-28 |
| AR-10-03 | 10-02/T-10-06 | Caller-supplied addresses may appear in local operator debug logs, matching existing behaviour | Operator via approved plan | 2026-08-28 |
| AR-10-04 | 10-01/T-10-SC | No dependency change occurred in plan 10-01 | Operator via approved plan | 2026-08-28 |
| AR-10-05 | 10-02/T-10-SC | No dependency change occurred in plan 10-02 | Operator via approved plan | 2026-08-28 |
| AR-10-06 | 10-03/T-10-SC | No dependency change occurred in plan 10-03 | Operator via approved plan | 2026-08-28 |
| AR-10-07 | 10-04/T-10-SC | No dependency change occurred in plan 10-04 | Operator via approved plan | 2026-08-28 |
| AR-10-08 | 10-05/T-10-SC | No dependency change occurred in plan 10-05 | Operator via approved plan | 2026-08-28 |
| AR-10-09 | 10-06/T-10-SC | No dependency change occurred in plan 10-06 | Operator via approved plan | 2026-08-28 |
| AR-10-10 | 10-07/T-10-SC | No dependency change occurred in plan 10-07 | Operator via approved plan | 2026-08-28 |
| AR-10-11 | 10-08/T-10-SC | No dependency change occurred in plan 10-08 | Operator via approved plan | 2026-08-28 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-28 | 37 | 37 | 0 | GSD security auditor and Codex orchestrator |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-28
