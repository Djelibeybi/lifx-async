---
phase: quick-260726-42c
slug: create-a-script-that-enumerates-mac-addr
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-26
---

# Quick Task 260726-42c — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| LAN → script | Untrusted UDP discovery responses and OS ARP table contents enter here | Device serials, firmware versions, IPs, MACs |
| script → OS | Subprocess invocation of `arp` / `ip neigh` | Fixed argv command lines; raw stdout text |
| PyPI → PEP 723 env | `rich` fetched into the ephemeral script environment | Third-party package code |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-Q42C-01 | Tampering | arp/ip subprocess call | low | mitigate | `_run_snapshot()` (`scripts/serial_mac_audit.py:419`) runs fixed argv lists only — `["arp", "-an"]` (:458) and `["ip", "-4", "neigh", "show"]` (:466) — with no `shell=True` and `timeout=10.0`. Output is matched against strict line regexes (`_ARP_DARWIN_LINE` :149, `_IP_NEIGH_LINE` :293) and every captured MAC additionally passes `_is_valid_mac()` (:152, six one-or-two-digit hex octets) before entering the map. `FileNotFoundError`/`TimeoutExpired` degrade to an empty ARP map. | closed |
| T-Q42C-02 | Spoofing | discovery responses / ARP entries | low | accept | Diagnostic tool on the operator's own L2 segment; `discover_devices()` already validates source ID and serial. Recorded in Accepted Risks Log (R-01). | closed |
| T-Q42C-03 | Information disclosure | CSV/table output (serials, MACs, IPs) | low | accept | Local diagnostic data written only where the operator pipes it; nothing committed or transmitted. Recorded in Accepted Risks Log (R-02). | closed |
| T-Q42C-SC | Tampering | PyPI install of `rich` via PEP 723 | high | mitigate | RESEARCH.md §Package Legitimacy Audit verified rich 15.0.0 against the PyPI JSON API (Textualize, published 2026-04-12) → OK. Pin `rich>=15.0.0` lives only in the inline PEP 723 block (`scripts/serial_mac_audit.py:4`); `lifx-async` resolves to the local checkout via `[tool.uv.sources]`. `git diff main -- pyproject.toml uv.lock` is empty — the zero-dependency runtime surface is untouched. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-01 | T-Q42C-02 | A host spoofing discovery responses or poisoning ARP could plant a false correlation row. The script is an operator-run diagnostic on their own L2 segment, and library discovery already rejects mismatched source IDs and invalid serials. Impact is a wrong row in a throwaway audit, not a privilege or data loss. | Avi Miller | 2026-07-26 |
| R-02 | T-Q42C-03 | Serials, MACs, and IPs from the operator's own fleet appear in the table and `--csv` stream. They go only where the operator redirects them; nothing is committed to the repo or sent off-host. | Avi Miller | 2026-07-26 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-26 | 4 | 4 | 0 | Claude (/gsd-secure-phase, ASVS L1 short-circuit — register authored at plan time) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-26
