---
phase: 1
slug: ceiling-save-on-exit
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-12
---

# Phase 1 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| application code → local filesystem | `__aexit__` triggers `_save_state_to_file()`, which writes the device's own in-memory state as JSON to the caller-supplied `state_file` path. The state is not externally-supplied input; the path is caller-controlled. | Device state (uplight/downlight colours) — low sensitivity, device-owned |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-01-01 | Information Disclosure / Tampering | state-file write at caller-supplied path in `_save_state_to_file()` | accept | See Accepted Risks Log | closed |
| T-01-02 | Denial of Service | `__aexit__` could raise from the save attempt and skip connection cleanup | mitigate | `src/lifx/devices/ceiling.py:226-233` — `try/except Exception` wraps `await asyncio.to_thread(self._save_state_to_file)` (line 228); `_LOGGER.warning` on failure (lines 230-232); `await super().__aexit__()` unconditional at line 233 (outside the try block); no `return True`; proven by `TestCeilingLightSaveOnExit.test_save_on_exit_body_exception_propagates` | closed |
| T-01-SC | Tampering (supply chain) | npm/pip/cargo installs | accept | See Accepted Risks Log | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-01-01 | Path handling is unchanged from the pre-existing `_save_state_to_file()` helper (`Path(...).expanduser()`). No new path-parsing logic was introduced by this phase. The data written is the device's own in-memory state, not externally-supplied input. Path choice is the application developer's responsibility, consistent with the library's local-network trust model. Out of scope per REQUIREMENTS (no schema or path changes in this phase). | Avi Miller (plan-time disposition) | 2026-06-12 |
| AR-02 | T-01-SC | No new runtime or development packages were added in this phase. The library remains zero-dependency. `01-01-SUMMARY.md` `tech-stack.added: []` confirms no installs occurred. | Avi Miller (plan-time disposition) | 2026-06-12 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Flags

None — `01-01-SUMMARY.md` contains no `## Threat Flags` section; no new unregistered attack surface was identified during implementation.

---

## Audit Notes

`01-01-SUMMARY.md` `key-decisions` records "Call `_save_state_to_file()` synchronously (no `asyncio.to_thread`)" reflecting the original plan decision (D-01). D-01 was revised post-review (user-approved, commit `71142ff`): the call is now `await asyncio.to_thread(self._save_state_to_file)`, confirmed at `ceiling.py:228`. This is a security improvement (non-blocking I/O; I/O errors still propagate through the awaitable and are caught by the same `except Exception` guard). No security regression.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-12 | 3 | 3 | 0 | gsd-security-auditor (ASVS L1) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-12
