# Phase 2: Discovery Re-broadcast — Context

**Source:** Spike 005 (`.planning/spikes/005-discovery-regimes/`) and the
`spike-findings-lifx-async` skill (`references/discovery.md`). This context distils the
already-held discussion (spike series review + v1.1 milestone scoping, 2026-07-16) —
no separate discuss-phase interview was run.

## Decisions (settled)

- **D2-01**: Re-broadcast `GetService` inside `_discover_with_packet()`'s receive loop on
  a Photons-shaped escalating schedule; gaps ≈ 0.6, 1.2, 1.8, 2.0, 2.0 s from first send,
  capped by the discovery window. Working interleave pattern:
  `spike-findings-lifx-async/sources/005-discovery-regimes/sweep.py` (`run_round()`).
- **D2-02**: Preserve everything from the Phase 1 rework unchanged: serial validation,
  first-wins per-serial dedup (D-04), IdleDeadline semantics, thin `discover_devices()`
  wrapper. The dedup already absorbs duplicate responses to later broadcasts.
- **D2-03**: Public API unchanged — no new parameters required for the default behaviour;
  existing callers benefit transparently. (If the planner finds a schedule constant worth
  exposing, module-level constants in `const.py` are the pattern, not new kwargs.)
- **D2-04**: Applies to UDP broadcast discovery only; mDNS path untouched (Out of Scope).

## Measured baselines (success targets)

- Single broadcast today: median 48/73 devices per round, min 27, bimodal (per-AP
  broadcast delivery suspected). Photons schedule in the same harness: 72–73/73 at ~615
  responses/round.
- Devices answer each broadcast ~2× (two StateService packets) — response volume scales
  as ≈ 2 × devices × broadcasts; must not destabilise the receive loop or dedup.
- DISC-03 hardware UAT: ≥6-round median coverage of the production fleet = full roster
  (union across rounds), using repeated rounds — single rounds mislead.

## Constraints

- Emulator cannot model per-AP broadcast loss — automated tests cover schedule mechanics
  (send times, dedup, idle/overall deadline interaction); hardware UAT covers coverage.
- CI: 100% branch patch coverage on automated tests; pyright strict; ruff clean.
- Spike harness `sweep.py` is reusable as the UAT measurement tool (compare against its
  `lifx-async` regime arm as the baseline).

## Requirements in scope

DISC-01 (re-broadcast schedule), DISC-02 (no duplicate yields), DISC-03 (hardware UAT).
