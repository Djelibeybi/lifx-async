---
status: resolved
phase: 08-hardware-fidelity-validation
source: [08-EXCEPTION-OVERRIDE.json, 08-CEILING-DETERMINATIONS.json, 08-VERIFICATION.md]
started: 2026-08-16T08:32:37Z
updated: 2026-08-16T08:32:37Z
resolution: operator-approved exception
resolution_detail: >-
  Closed by operator decision, not by a clean pass. Theme-fidelity observations
  for both roles were accepted; Tile restoration remains unverified, official
  08-UAT-RESULTS.json is deliberately absent, a synthetic two-role merge is
  prohibited, and no further hardware run is required. Mirrors the override
  already recorded in 08-VERIFICATION.md (overrides_applied: 1, accepted_at
  2026-08-16).
---

# Phase 08 Hardware UAT — Operator-Approved Exception Closeout

**Decision date:** 2026-08-16  
**Classification:** completed with operator-approved exception; official finalisation withheld

The machine-reviewable closeout decision is
[08-EXCEPTION-OVERRIDE.json](08-EXCEPTION-OVERRIDE.json). The independent, privacy-safe
[08-CEILING-DETERMINATIONS.json](08-CEILING-DETERMINATIONS.json) records the 25 per-theme
protocol-ceiling determinations; it is not a UAT result or finalisation substitute.

## Accepted Observations

Two representative shipped themes were observed through both the manually applied app path and
the library MORPH path. The source-Tile role produced twelve stable expected palette matches: six
app observations and six library observations. The non-Tile matrix role independently produced
twelve stable expected matches under the five-second post-app-change settling contract: six app
observations and six library observations.

The operator accepted these theme-fidelity observations as the Phase 8 hardware outcome. Palette
comparison remained unordered and duplicate-sensitive; no mismatch was accepted as a match.

## Exception Retained

The source-Tile role did not verify restoration of its captured device state. That is an unresolved
safety/infrastructure exception. Its role-local record is non-finalisable and must not be resumed
or treated as restored.

The non-Tile matrix role restored successfully, but its role-only record is also permanently
non-finalisable. It cannot be combined with the source-Tile record into a synthetic 24-cycle run.

## Deliberate Withholding of Official Evidence

No authoritative results JSON or derived official evidence rendering was created. The planned
finalisation contract requires one designated run with all 24 observations and verified restoration
of both roles. That condition was not met, so publishing a combined evidence artefact would be
misleading.

The override records accepted observations and the decision not to make a further hardware run; it
does not claim the Tile restored or permit a synthetic merge. The Phase 8 verifier must retain the
restoration exception and determine any requirement-level status separately.
