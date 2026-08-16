---
phase: 08
slug: hardware-fidelity-validation
status: secured
threats_open: 0
asvs_level: 1
block_on: high
audited: 2026-08-16
---

# Phase 08 — Security

## Verdict: SECURED

All 24 declared threats are closed at their production boundaries. In particular, the
private-path authority, live-resume provenance, and exact full-lifecycle product identity
checks that were previously open now fail closed before private access or light mutation.

The operator-approved Tile-restoration exception remains an operational/safety exception,
not a security waiver: no official 24-cycle evidence was created, the role-local runs remain
non-finalisable, and a synthetic merge is prohibited.

## Threat Register

| Threat ID | Category | Severity | Disposition | Status | Evidence |
|---|---|---:|---|---|---|
| T-08-01 | Information disclosure — target/checkpoint/diagnostics | high | mitigate | closed | Production derives the sole repository-anchored private root; `--targets` may name only its exact relative `targets.json`. Canonical boundary resolution rejects absolute/path escapes, non-direct roots and target/root symlinks before any mkdir, chmod, read or write ([uat_theme_fidelity.py](uat_theme_fidelity.py:108), [uat_theme_fidelity.py](uat_theme_fidelity.py:139), [uat_theme_fidelity.py](uat_theme_fidelity.py:4282)). Run IDs are canonical and resolved as direct children before resume/finalise access. |
| T-08-02 | Spoofing — semantic device/theme selection | high | mitigate | closed | Bound host/serial/label contact, current Morph-surface attestation, two equal current hierarchy fingerprints, and fresh stable MORPH readback bind each guided observation ([uat_theme_fidelity.py](uat_theme_fidelity.py:3543), [uat_theme_fidelity.py](uat_theme_fidelity.py:3817), [uat_theme_fidelity.py](uat_theme_fidelity.py:4040)). |
| T-08-03 | Tampering — LAN target selection | high | mitigate | closed | The strict loader permits exactly the two confirmed/quiesced role records and no discovery path; lifecycle preflight rechecks their live matrix/product properties before a snapshot or callback ([uat_theme_fidelity.py](uat_theme_fidelity.py:826), [uat_theme_fidelity.py](uat_theme_fidelity.py:3175)). |
| T-08-04 | Tampering — Android global setting | medium | mitigate | closed | Keep-awake captures the exact prior value, restores it in `finally`, and rereads it; failed restoration raises the restoration exit ([uat_theme_fidelity.py](uat_theme_fidelity.py:3486)). |
| T-08-05 | Elevation of privilege — ADB subprocess | medium | mitigate | closed | The sole subprocess wrapper uses a fixed argv list, no shell, bounded timeout, captured output and redacted failures ([uat_theme_fidelity.py](uat_theme_fidelity.py:2372)). |
| T-08-06 | Repudiation — tracer event ordering | medium | mitigate | closed | Private JSONL records are mode 0600; checkpoint cycles retain ordered monotonic observations and reject malformed/out-of-order prefixes ([uat_theme_fidelity.py](uat_theme_fidelity.py:618), [uat_theme_fidelity.py](uat_theme_fidelity.py:746), [uat_theme_fidelity.py](uat_theme_fidelity.py:3315)). |
| T-08-07 | Tampering — resume checkpoint | high | mitigate | closed | Production and role-only paths derive provenance from the read-only current app version, current two-read Morph surface digest, binding digests, exact live firmware and frozen theme records. Resume recaptures it and requires exact equality before entering the lifecycle ([uat_theme_fidelity.py](uat_theme_fidelity.py:504), [uat_theme_fidelity.py](uat_theme_fidelity.py:3543), [uat_theme_fidelity.py](uat_theme_fidelity.py:4590)). |
| T-08-08 | Tampering — device restoration | high | mitigate | closed | Two equal static-OFF snapshots precede the mutation boundary; restoration writes effect, base colour, pixels and power once, then performs bounded read-only verification. Any failure exits as restoration failure and cannot finalise ([uat_theme_fidelity.py](uat_theme_fidelity.py:1015), [uat_theme_fidelity.py](uat_theme_fidelity.py:1105), [uat_theme_fidelity.py](uat_theme_fidelity.py:1852)). |
| T-08-09 | Information disclosure — public projection | high | mitigate | closed | Public evidence is constructed from an allowlist, recursively rejects private identifiers and validates the resulting semantic schema before staging ([uat_theme_fidelity.py](uat_theme_fidelity.py:1200), [uat_theme_fidelity.py](uat_theme_fidelity.py:1257), [uat_theme_fidelity.py](uat_theme_fidelity.py:1504)). |
| T-08-10 | Repudiation — mismatch/cycle record | high | mitigate | closed | Checkpoint decoding permits only the ordered locked schedule prefix; public validation requires all 24 exact keys and recomputes each palette verdict from committed records ([uat_theme_fidelity.py](uat_theme_fidelity.py:706), [uat_theme_fidelity.py](uat_theme_fidelity.py:1397)). |
| T-08-11 | Spoofing — non-Tile evidence | high | mitigate | closed | Generic live checks require a non-55 indoor non-emulator matrix and reject Candle; the exact full-run allowlist further permits only Ceiling or Luna with the required resolved class ([uat_theme_fidelity.py](uat_theme_fidelity.py:891), [uat_theme_fidelity.py](uat_theme_fidelity.py:917)). |
| T-08-12 | Information disclosure — Android app identity/session | medium | mitigate | closed | Only the constrained app-version token is retained. Raw hierarchy output is written only beneath the controlled private run directory and is excluded from the public schema ([uat_theme_fidelity.py](uat_theme_fidelity.py:944), [uat_theme_fidelity.py](uat_theme_fidelity.py:1200), [uat_theme_fidelity.py](uat_theme_fidelity.py:2399)). |
| T-08-13 | Denial of service — bounded polls/UI retries | medium | mitigate | closed | Finite configured action/stability windows and poll intervals bound guided app observation; library readback uses the same bounded stability contract ([uat_theme_fidelity.py](uat_theme_fidelity.py:3882), [uat_theme_fidelity.py](uat_theme_fidelity.py:4152)). |
| T-08-14 | Tampering — count correction | medium | mitigate | closed | Ceiling determinations are mechanically derived and constrained to the shipped set; the separate documentation regression verifies the 25/26/Carlton distinction ([uat_theme_fidelity.py](uat_theme_fidelity.py:1257), [test_documentation_counts.py](tests/test_documentation_counts.py:26)). |
| T-08-15 | Repudiation — FIDELITY-01 wording | medium | mitigate | closed | The committed determination records source predicate, literal palette length and Carlton exclusion; the active-document test guards the wording ([08-CEILING-DETERMINATIONS.json](08-CEILING-DETERMINATIONS.json:1), [test_documentation_counts.py](tests/test_documentation_counts.py:47)). |
| T-08-16 | Information disclosure — capture README | low | accept | closed — accepted risk | The capture/documentation material contains public theme and category facts only. The accepted rationale remains recorded as R-08-01 below. |
| T-08-17 | Denial of service — stale scanner false positive | low | mitigate | closed | The documentation check intentionally scans only active documents, excluding historical problem quotations ([test_documentation_counts.py](tests/test_documentation_counts.py:12)). |
| T-08-18 | Spoofing — physical target/app label | high | mitigate | closed | Production connects only to the bound host/serial, rejects a non-matrix, mismatched label or wrong source product, and binds the manual-role claim to the current run and opaque binding digest ([uat_theme_fidelity.py](uat_theme_fidelity.py:2733), [uat_theme_fidelity.py](uat_theme_fidelity.py:3817)). |
| T-08-19 | Tampering — real light state | high | mitigate | closed | The durable initial checkpoint follows both complete snapshots and is the mutation boundary. Every post-boundary terminal path attempts verified restoration; restoration/close faults override outcome and block finalisation ([uat_theme_fidelity.py](uat_theme_fidelity.py:1852)). |
| T-08-20 | Information disclosure — official JSON/Markdown | high | mitigate | closed | Finalisation accepts only a designated `finalisable` private result with a validated public projection; the evidence writer revalidates before output ([uat_theme_fidelity.py](uat_theme_fidelity.py:4184), [uat_theme_fidelity.py](uat_theme_fidelity.py:4198)). |
| T-08-21 | Repudiation — UAT cycle outcomes | high | mitigate | closed | Full runs require the exact 24-key schedule and verified restorations. Luna-only sessions cannot resume or finalise, and their result contains no public projection ([uat_theme_fidelity.py](uat_theme_fidelity.py:1852), [uat_theme_fidelity.py](uat_theme_fidelity.py:2098), [uat_theme_fidelity.py](uat_theme_fidelity.py:4221)). |
| T-08-22 | Spoofing — secondary product | high | mitigate | closed | Full lifecycle acquires both metadata records, applies generic validation and then the exact Tile plus Ceiling/Luna allowlist before any snapshot, checkpoint, callback or device write. Role-only lifecycle performs its exact Luna check before its snapshot/checkpoint/callback ([uat_theme_fidelity.py](uat_theme_fidelity.py:917), [uat_theme_fidelity.py](uat_theme_fidelity.py:1852), [uat_theme_fidelity.py](uat_theme_fidelity.py:2098)). |
| T-08-23 | Denial of service — missing app/hardware | medium | mitigate | closed | App, lock-state, contact, metadata and snapshot checks occur in non-mutating preflight with finite settings; failures are classified before lifecycle mutation and no fleet discovery is attempted ([uat_theme_fidelity.py](uat_theme_fidelity.py:3543), [uat_theme_fidelity.py](uat_theme_fidelity.py:4282)). |
| T-08-24 | Information disclosure — app/tablet session | medium | mitigate | closed | The public root has an exact allowlist and rejects account, token, cookie, host, serial, MAC and ADB patterns recursively; private Android/UI material has no public field ([uat_theme_fidelity.py](uat_theme_fidelity.py:1200), [uat_theme_fidelity.py](uat_theme_fidelity.py:1326)). |

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted by |
|---|---|---|---|
| R-08-01 | T-08-16 | The capture README exposes public theme/category facts only; no device, tablet, LAN or account identity is present. | Planned disposition, [08-03-PLAN.md](08-03-PLAN.md:193) |

## Reverification of Previously Open Threats

- `b94b680` closes T-08-01. The CLI no longer has a private-root override; its optional target spelling is constrained to the fixed Phase 8 path, and canonical checks reject root/target escapes and symlinks before private access. Focused negative tests cover path escape and symlink cases.
- `98e41c5` closes T-08-07. `build_live_provenance()` consumes current preflight facts rather than placeholders. Full and role-only production paths run that preflight before lifecycle; a resume compares the refreshed provenance before invoking the lifecycle.
- `51d56e0` closes T-08-22. `run_designated_lifecycle()` calls `validate_live_preflight_metadata()` after both metadata reads and before snapshots/checkpoint/callbacks; role-only Luna has its own exact pre-snapshot guard. Tests poison snapshot/checkpoint/callback seams and prove disallowed devices stop before each.

## Exception Boundary

The operator-approved exception records accepted role-local fidelity observations, verified Luna
restoration and unverified Tile restoration. It deliberately withholds `08-UAT-RESULTS.json`,
prohibits synthetic merging, and does not make either private result finalisable
([08-EXCEPTION-OVERRIDE.json](08-EXCEPTION-OVERRIDE.json:1), [08-UAT.md](08-UAT.md:20)). This
does not reopen T-08-08: its mitigation is the fail-closed outcome and finalisation block, both
of which remain active.

## Audit Evidence

- Fake-only Phase 8 gate: `252 passed`.
- Ruff check and format check: passed.
- Pyright: `0 errors, 0 warnings, 0 information messages`.
- `git diff --check` was clean before this documentation update; no implementation file was changed.
- No hardware, ADB, UI, LAN or private runtime target/run artefact was accessed during this audit.
- No `## Threat Flags` section was present in the Phase 08 summaries; no unregistered implementation flag was found.

**threats_open:** 0
