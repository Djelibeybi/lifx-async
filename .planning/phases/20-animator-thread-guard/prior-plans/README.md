# Superseded Phase 18 plans (reference only)

These three plans were written for ANIM-05 when it was part of Phase 18. ANIM-05 moved to
Phase 20 on 2026-09-23 because the lifx-emulator-core release that models Thread devices is
not ready.

Do not execute them as written. They assume the emulator answers Thread requests with one
reply per device. It will instead answer the way the Thread standard does, packing replies
into as few packets as possible.

Phase 20 is now verified without the emulator:

- CI covers every guard branch with synthetic Thread connectivity, following the existing
  `_refuse_on_connectivity()` tests in `tests/test_devices/test_base.py`.
- An operator-run check on real Thread devices provides the integration evidence. It is
  pseudonymised before commit, like Phase 17's hardware evidence. "No frame sent" is
  counted on the sending side through the request-observation seam in
  `.planning/scripts/measurement_support.py`.
- Emulator integration tests are a deferred follow-up once the emulator ships packed Thread
  replies.

So the `thread_emulator` fixture and the per-device packet-count assertions in these plans
are dropped, not redesigned. The guard design itself (`LifxThreadAnimationError`,
`animation/guard.py`, `enable_thread` on the three factories and on `Conductor`) still
applies.

- `18-01-PLAN.superseded.md`: emulator bump and the shared `thread_emulator` fixture
- `18-02-PLAN.superseded.md`: `LifxThreadAnimationError`, `animation/guard.py` and
  `enable_thread` on the three `Animator` factories
- `18-05-PLAN.superseded.md`: Conductor Thread exclusion and `Conductor(enable_thread=...)`

The ANIM-05 requirements, decisions and cross-AI review adjudication came from
`../../18-typed-move-and-morph-palette-effects/`. `18-SPEC.md` now holds only "moved" stubs
for R1 to R3 and R8, so read the full pre-split text at commit `976b22a`
(`git show 976b22a:.planning/phases/18-typed-move-and-morph-palette-effects/18-SPEC.md`).
D-01 to D-08 are still in `18-CONTEXT.md`, tagged `[deferred]`, and the round 1 adjudication
is in `18-REVIEWS-ROUND1.md`. Carry the ANIM-05 parts forward into this phase's own SPEC and
CONTEXT when it is planned.

## Carried out of the Phase 18 replan (2026-09-23)

The surviving Phase 18 plans were revised to drop ANIM-05. Phase 20's SPEC, CONTEXT and plans
must pick up the following, which no Phase 18 plan now covers:

- **Docs removed from 18-07:** the "Thread devices" note under "When to Use Animation" in
  `docs/user-guide/animation.md` (including the wording that direct `Animator(...)` is an
  escape hatch that does not inspect connectivity); the Conductor Thread note in
  `docs/user-guide/effects.md`; `LifxThreadAnimationError` in the `docs/api/exceptions.md`
  tree and its `:::` entry, and in AGENTS.md's exception list; the AGENTS.md Animation Layer
  `guard.py` entry; the connectivity sentences in `docs/api/devices.md`,
  `docs/user-guide/advanced-usage.md` and the `Device.connectivity` docstring in
  `src/lifx/devices/base.py`; coverage of `guard.py`, `animator.py`, `exceptions.py` and
  `conductor.py`.
- **Hygiene:** `LifxUnsupportedDeviceError` is missing from both AGENTS.md's exception list
  and `docs/api/exceptions.md`. Fix both alongside the `LifxThreadAnimationError` edits.
- **Review items:** L227 (escape-hatch wording), L419 (catch-and-degrade snippet) and the
  Conductor half of L225, all `@92a657d` in `18-REVIEWS.md`.
- **18-SPEC edges:** R1 empty (dismissed), encoding, concurrency; R2 concurrency (dismissed);
  R3 adjacency (dismissed), empty, ordering; R8 boundary, empty, idempotency (dismissed).
- **18-SPEC prohibitions:** no IP, MAC or hostname in messages or logs (R1, R3); no packet to
  an excluded participant (R3); the guard sends no packet (R1); no refusal because an address
  is IPv6 (R1, R2); opt-in only through the call-site argument (R8); no Thread-dependent
  behaviour outside the factories and the Conductor (R2, R8).
- **18-SPEC wording to replace, not copy:** the Constraints line saying a Thread device comes
  from the emulator and "never by real hardware", "Emulator tests for every acceptance
  criterion", and the emulator Thread wording in R1, R2, R3, R8 and the Thread prohibition
  rows.
- **18-CONTEXT:** D-01 to D-08 (tagged `[deferred]`) and the Thread half of D-11.
- **Sequencing:** Phase 20 R2's "tests/test_animation unmodified" check must be measured
  against the tree after 18-08's PLC0415 import hoist lands.
