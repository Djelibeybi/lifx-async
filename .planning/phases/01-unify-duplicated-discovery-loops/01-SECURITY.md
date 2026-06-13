---
phase: 1
slug: unify-duplicated-discovery-loops
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-13
---

# Phase 1 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Phase goal: rebuild `discover_devices()` on the shared `_discover_with_packet()`
> generator, hoisting the documented DoS protections so every discovery caller
> inherits them. Security posture is therefore central to this phase, not incidental.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| external network → `_discover_with_packet` | Untrusted UDP broadcast responses from arbitrary LAN hosts cross into the shared discovery generator | Raw datagrams → parsed LIFX headers + State packet payloads |
| external network → `discover_lifx_services` (mDNS) | Untrusted multicast mDNS/DNS-SD responses from arbitrary hosts cross into the mDNS discovery generator | Raw multicast datagrams → parsed DNS records |
| deprecation signalling (`receive_many`) | No new input handling; maintenance-only `DeprecationWarning` | None |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-01-01 | Denial of Service | `IdleDeadline` as discovery loop terminator | accept | Helper enforces overall + idle deadlines bounding every discovery loop; correctness proven by `test_network/test_utils.py` (`remaining() <= 0` on expiry). No external input reaches the class directly. | closed |
| T-01-02 | Spoofing / DoS | Forged `StateService` with broadcast/multicast/zero serials | mitigate | Hoisted unconditional serial guard in `_discover_with_packet` (`discovery.py:306`): rejects multicast bit (covers all-`0xff`) **and** the all-zeros broadcast target. Strengthened post-plan by **WR-01** (all-zeros rejection added; unreachable `0xff` clause collapsed). Extends DoS protection to `find_by_label`/enrichment paths. Verified by `test_discovery_errors.py` generator-level rejection tests. | closed |
| T-01-03 | Spoofing | Off-session responses with mismatched source ID | mitigate | `header.source != discovery_source → continue` preserved in `_discover_with_packet` (`discovery.py:286`); verified by `TestDiscoverySourceValidation`. | closed |
| T-01-04 | Denial of Service | Hostile host flooding rejected-serial responses to amplify logs | mitigate | Rejected serials logged at DEBUG only (`discovery.py:307`), never WARNING — no log-flooding amplification on hostile networks (D-02). | closed |
| T-01-05 | Denial of Service | Same-serial flood causing premature idle timeout (loss of legitimate discovery) | mitigate | `mark_response()` called on every valid response **before** the dedup check (`discovery.py:357` → dedup `:360`), so a flooding device cannot truncate discovery early; first-wins dedup still yields each serial once (D-04). | closed |
| T-01-06 | DoS / Repudiation | Genuine socket error masquerading as "no responses", hiding network failure | mitigate | Tightened mDNS exception routing (D-08, **WR-02**): `LifxNetworkError` → WARNING + break; unexpected errors → ERROR with `exc_info` + re-raise. Real failures are diagnosable, not swallowed. | closed |
| T-01-07 | Denial of Service | mDNS response flood / idle starvation | accept | `IdleDeadline` enforces the same overall+idle bounds; `mark_response()` preserves idle-reset semantics; `seen_serials` dedup unchanged. No new attack surface. | closed |
| T-01-08 | Maintenance (non-security) | `UdpTransport.receive_many` deprecation | accept | Deprecation is signalling only; the method body — including its existing oversized/undersized packet-drop guards — is untouched, so no protection is removed. `DeprecationWarning` has no security impact. | closed |
| T-01-09 | Spoofing / DoS (verification) | Hoisted serial validation in `_discover_with_packet` | mitigate | Direct generator-level test coverage (`test_discovery_errors.py`) proving T-01-02 (broadcast/multicast/zero rejection) and T-01-05 (first-wins dedup) are enforced at their new boundary, not just transitively via `discover_devices`. | closed |
| T-01-10 | Denial of Service | Size-invalid datagram aborting all discovery (**found in code review — CR-01**) | mitigate | `_discover_with_packet` now catches `LifxProtocolError` from `transport.receive()` and drops-and-continues (`discovery.py`), so a single under/oversized UDP datagram from a hostile host can no longer terminate discovery for the whole library. Regression test in `TestMalformedSizeDatagramHandling`. This closed a real DoS-contract violation the unified path had inherited. | closed |
| T-01-11 | Denial of Service / Availability | Crafted `StateService` with out-of-range enum value triggering ERROR-log amplification, and crash-on-unexpected-input (**found on real hardware**) | mitigate | Enum deserialisation now tolerates values newer than the bundled `protocol.yml` (`base.py` `_coerce_enum` → falls back to raw int, logged at DEBUG) instead of raising `ValueError` that the broad `except` logged at ERROR with full traceback — removing a log-amplification vector and a crash surface. The GetService path also ignores non-UDP `StateService` so crafted non-UDP services cannot claim a serial or supply a bogus port. Regression tests in `TestNonUdpServiceHandling`. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-01-01 | Discovery-loop termination is bounded by `IdleDeadline`; no external input reaches the helper directly. Unit-test-proven. | Avi Miller | 2026-06-13 |
| AR-02 | T-01-07 | mDNS flood/idle starvation is bounded by the same overall+idle deadlines as the broadcast path; no new attack surface added by the refactor. | Avi Miller | 2026-06-13 |
| AR-03 | T-01-08 | `receive_many` deprecation is signalling only; existing DoS packet-size guards in the method body are untouched. | Avi Miller | 2026-06-13 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-13 | 11 | 11 | 0 | Claude (gsd-secure-phase, short-circuit: plan-time register, all mitigations verified in-tree) |

Notes:
- 9 threats (T-01-01..T-01-09) were authored in the plan-time `<threat_model>` blocks across `01-01`..`01-05` PLAN files.
- 2 further DoS threats (T-01-10, T-01-11) were discovered **after** planning — T-01-10 in the code-review fix pass (CR-01), T-01-11 during real-hardware UAT (unknown `DeviceService` value) — and are recorded here as closed with regression coverage.
- All `mitigate` controls were verified present in the implementation by direct inspection of `src/lifx/network/discovery.py`, `src/lifx/network/mdns/discovery.py`, `src/lifx/network/transport.py`, and `src/lifx/protocol/base.py`. Full suite: 2511 passed.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-13
