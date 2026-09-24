---
phase: "18"
slug: "typed-move-and-morph-palette-effects"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-24"
---

# Phase 18: Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Caller to library | Direction strings, float seconds and an optional caller-supplied palette enter the typed Move builder and `set_effect()` | Untrusted numeric and string input |
| Library to device | Converted values are written into fixed-width wire structures; FLAME, SKY and explicit-palette `Tile.SetEffect` payloads must not drift | uint32/uint64 fields, HSBK palettes |
| Device to library | Zone and tile colours read back from the device decide whether Move repaints and become the palette MORPH sends next | Device-reported HSBK |
| Library to caller | A failed MORPH colour read now raises out of `set_effect()` | Exception message naming the device |
| Published docs to callers | Callers copy documented examples into production code | Example code |
| Lint configuration to CI | Per-file ignores decide which files the import rule guards | `pyproject.toml` ruff settings |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-18-08 | Tampering | `move()` numeric conversion | medium | mitigate | TypeError/ValueError before any packet (`multizone.py:172-197`); overflow cases and uint32/uint64 bounds tested at and past the limit (`test_multizone_move.py`, uint64 at-limit test added in d01a862) | closed |
| T-18-09 | Tampering | Raw `MultiZoneEffect` path (Home Assistant) | medium | mitigate | `TestGoldenMovePacket` proves raw and typed packets byte-identical; `test_multizone.py` differs from merge-base only in imports | closed |
| T-18-10 | Denial of service | Direction parsing | low | accept | Single bounded lookup against a two-member enum (`multizone.py:55-65`) | closed |
| T-18-11 | Tampering | FLAME, SKY and explicit-palette payloads | medium | mitigate | Five golden payloads asserted byte-for-byte (`test_effect_palette.py:61-164`) | closed |
| T-18-12 | Denial of service | Colour read before MORPH | low | mitigate (superseded) | Superseded by D-26 in 18-09: MORPH now raises on a failed read; only palette-less MORPH reads; risk carried by T-18-15 | closed |
| T-18-13 | Tampering | Device-reported colours feeding the palette | low | mitigate | Colours built through validating `HSBK()`; `replace()` rebuild reruns `validate_effect_palette()`; oversized derivation raises before send | closed |
| T-18-14 | Tampering | Device colours feeding `sample_effect_palette()` | low | mitigate | Validated `HSBK` input; at most 16 returned; 17-colour sample raises before send (`test_effect_palette.py:694-704`) | closed |
| T-18-15 | Denial of service | MORPH start when the colour read fails | low | accept | D-26: raising is intended; caller retries or passes `palette=`; Move keeps its fallback | closed |
| T-18-16 | Information disclosure | `LifxProtocolError` for an empty colour result | low | mitigate | Message names the device by `self.label or self.serial` only (`matrix.py:1208-1212`) | closed |
| T-18-17 | Tampering | FLAME, SKY and explicit-palette payloads | medium | mitigate | Five `_GOLDEN_` constants AST-identical to capture commit 24c42bc; byte tests pass | closed |
| T-18-18 | Tampering | Raw `set_effect()` path (Home Assistant) | medium | mitigate | Emulator packet log shows exactly one SetEffect (`test_multizone_move.py:713-734`); `test_multizone.py` import-only diff | closed |
| T-18-19 | Tampering | Caller-supplied palette | low | mitigate | `validate_effect_palette()` runs before any paint or send (`multizone.py:1178`); empty and 17-colour palettes tested | closed |
| T-18-20 | Denial of service | Zone read before Move | low | mitigate | Read timeout or malformed reply logs DEBUG (serial only) and Move starts unpainted (D-23, 5a9d254); tested with dropped packets | closed |
| T-18-21 | Tampering | Documented examples drifting from the shipped API | medium | mitigate | Docstring and user-guide Move examples executed verbatim against the emulator; stale-form scan re-run at audit with 0 hits | closed |
| T-18-22 | Information disclosure | Addresses in documentation | low | mitigate | No live IP, serial, MAC or hostname added; test identifiers predate the phase | closed |
| T-18-23 | Tampering | Thread-guard behaviour leaking into Phase 18 | low | mitigate | Only the planned `src/lifx` and docs files changed; no added line mentions connectivity or Thread | closed |
| T-18-24 | Repudiation | Tests silently de-collected by the import sweep | medium | mitigate | Fail-closed baseline gate at plan time; re-collected at audit: 263 = 263, identical node IDs | closed |
| T-18-25 | Tampering | A vacuous lint gate | medium | mitigate | Ruff exit statuses asserted; PLC0415 fires under both swept filenames with the project config | closed |
| T-18-26 | Tampering | Collateral edits to Phase 19's comment and entry | low | mitigate | Only the two Phase 18 per-file-ignore entries removed; Phase 19's preserved | closed |
| T-18-27 | Tampering | Non-import edits riding along with the import sweep | medium | mitigate | Import-only gate reports 0 non-import changes; 2f0be2f and da1597c touch nothing else | closed |

*Status: open · closed · open, below high threshold (non-blocking)*
*Severity: critical > high > medium > low; only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-18-01 | T-18-10 | Direction parsing is one bounded enum lookup with no user-controlled iteration; no meaningful denial-of-service surface | Maintainer (18-03 plan threat register) | 2026-09-23 |
| AR-18-02 | T-18-15 | A MORPH colour-read failure raises instead of falling back, because the only fallback would send the empty palette the firmware ignores (D-26); the caller can retry or pass `palette=` | Maintainer (D-26) | 2026-09-24 |

*Accepted risks do not resurface in future audit runs.*

---

## Audit Notes

- T-18-12 is closed because D-26 superseded it, not by its original mitigation.
- The T-18-21 stale-form scan was a plan-time gate and is not a committed regression test; the executed examples are.
- The T-18-08 uint64 bound had no at-limit test when audited; `test_duration_uint64_boundary` (d01a862) now covers it.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-24 | 20 | 20 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-24
