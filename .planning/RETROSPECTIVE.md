# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Ceiling Save-on-Exit

**Shipped:** 2026-06-12
**Phases:** 1 | **Plans:** 1 | **Sessions:** ~4 (map → plan → execute → review/audit)

### What Was Built
- `CeilingLight.__aexit__` override that persists in-memory state to `state_file` before `close()`, with a belt-and-braces guard so save failures never raise and never mask a body exception
- Three emulator-backed TDD tests (`TestCeilingLightSaveOnExit`): happy-path write, `state_file=None` no-op, and exception-propagation-with-save-failure
- Review-driven hardening: atomic state-file writes (temp file + `os.replace`), per-serial entry merge instead of whole-file replace, exit-save moved off the event loop via `asyncio.to_thread`

### What Worked
- RED→GREEN TDD with atomic commits made the 6-minute execution clean — failing tests committed first, implementation second, quality gate third
- The embedded lifx-emulator gave real protocol-level coverage without hardware
- Code review caught three genuine issues (blocking I/O on the event loop, non-atomic writes, whole-file clobbering) that the original plan had explicitly decided the other way

### What Was Inefficient
- D-01 ("call `_save_state_to_file()` synchronously, matching the 8 existing call sites") was reversed by review fix IN-02 — researching the blocking-I/O question up front would have avoided a decide-then-revise cycle
- Planning artifacts (~25 docs commits) heavily outweighed the code change (2 files, +156/−8) for a single-phase milestone; a lighter-weight track may suit changes this small

### Patterns Established
- `CeilingLight` async context-manager lifecycle: `__aenter__` loads state, `__aexit__` saves state, both chain to `super()`
- Belt-and-braces `__aexit__` guards: outer try/except at the boundary, separate from the helper's own error handling, so the never-raise invariant survives future helper edits
- State-file writes are atomic (temp file + `os.replace`) and merge per-serial entries

### Key Lessons
1. "Match the existing call sites" is not always right — the exit path had different constraints (event-loop blocking matters more at lifecycle boundaries) than the per-operation save points.
2. Multiple devices sharing one `state_file` is a real usage pattern; any whole-file write must merge, not replace.
3. The outer exception guard in `__aexit__` is intentionally unreachable in production today (the helper catches I/O errors first) — documented as deliberate design, not dead code.

### Cost Observations
- Model mix: not tracked this milestone
- Sessions: ~4
- Notable: execution itself took 6 minutes; the bulk of effort went to planning, review and audit artifacts

---

## Milestone: v1.1 — Wire Reliability

**Shipped:** 2026-07-26
**Phases:** 4 (2–5) | **Plans:** 24 | **Tasks:** 52

### What Was Built
- Escalating Photons-shaped `GetService` re-broadcast inside the discovery window: one call went from a median 48/73 devices to 73/73 across a 6-round measurement on the production fleet
- A single shared `_transmit_and_listen()` engine behind both `DeviceConnection` request paths — one monotonic wall deadline, retransmit-while-listening, shared-queue correlation on GET and ACK alike: 1.37 → 1.017 packets/request, 62 ms → 12.6 ms median latency, no 29 s overruns of a 16 s budget
- Ack-gated frame pacing owned inside the animation layer, invisible to consumers, plus a latent large-tile chunking fix (raw 64-pixel slicing → row-aligned rect offsets) that had been garbling any tile width not dividing 64
- Reliability documentation with a zero-warning `--strict` docs build gated in CI, replacing an 8-warning "baseline" that turned out to be a defect set

### What Worked
- Spiking before planning. Five hardware experiments disproved the "port to threading" hypothesis outright and located the real levers; the milestone's whole shape came from evidence rather than intuition.
- Honest FAIL reporting. Phase 4's gate failed repeatedly and the thresholds were never quietly moved to make it pass — the eventual acceptance is recorded as an operator ruling over a statistical FAIL (`04-RULING.md`), not dressed up as a pass.
- Adversarial review at the close. The integration check read source rather than trusting the plans, and the serial/MAC work's max-effort review found 14 real defects across a script that had already passed a coordinator review.

### What Was Inefficient
- Phase 4 took 13 plans against 2–6 for every other phase, with several measurement re-runs and two threshold amendments, because the acceptance criterion was calibrated from a single 50-query spike round. Calibrating a gate from one sample cost the milestone its longest tail.
- `04-VALIDATION.md` sat at `status: draft` from planning until the close-out audit caught it, so a phase with full automated coverage read as unvalidated for weeks.
- Real LAN addresses reached planning artefacts and a test fixture and had to be scrubbed later; capturing sanitised data at the point of capture would have been free.

### Patterns Established
- Idle-deadline discipline for async generators: reset before the yield *and* on consumer resume, so consumer work never eats the window, with the overall deadline left as the real bound
- Diagnostics as PEP 723 single-file scripts pinned to the local checkout via `[tool.uv.sources]`, so an audit provably measures the working tree rather than the published release
- Deliberately separate schedules where a shared engine would violate a requirement — documented on both sides with traceability comments so the duplication is not "fixed" later by mistake

### Key Lessons
1. A gate calibrated from a single measurement round will be re-litigated. Spend the rounds up front or expect the tail.
2. Documents that record their own status (`status: draft`) need something that reconciles them; otherwise the record drifts from reality silently and only an audit catches it.
3. Audit findings are not automatically true. The close-out review's headline claim about MAC-address staleness rested on a false premise — the MAC is a derived convenience that never appears on the wire — and the operator's correction, not the reviewer's confidence, settled it.
4. Verify a regression test by breaking the fix. The idle-window test was only trustworthy once the patch was temporarily stripped and the test was watched to fail.

### Cost Observations
- Model mix: not tracked precisely; planning/verification agents on the stronger tier, routine execution on Sonnet-class
- Notable: one max-effort review spawned 44 agents over ~30 minutes and produced 15 distinct findings from 49 candidates — expensive, and it caught defects two earlier review passes had missed

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~4 | 1 | First GSD milestone on this repo; full pipeline (map → discuss → plan → execute → review → audit) exercised end-to-end |
| v1.1 | many | 4 | Spike-first planning (5 hardware experiments before any phase); hardware UAT checkpoints as blocking gates; close-out audit with cross-phase integration checking against source |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 2500 (suite green) | — | 0 (still zero runtime deps) |
| v1.1 | 2629 (suite green) | 96% overall, 100% branch patch in CI | 0 (still zero runtime deps) |

### Top Lessons (Verified Across Milestones)

1. **A plan's decision is a hypothesis, not a fact.** v1.0's D-01 (synchronous state save) was reversed by review; v1.1's ANIM-03 threshold was amended twice and the D5-09 docs rule is still disputed. Decisions that were never measured get re-litigated at the gate.
2. **Review catches what planning decided wrongly.** Both milestones' most valuable defects — blocking I/O on the event loop, whole-file clobbering, the large-tile chunking bug, the discovery idle-window hazard — came from review or audit, not from execution.
3. **Planning artefacts outweigh code on small changes.** True for v1.0 (25 docs commits vs 2 files) and for v1.1's quick tasks. Match the track to the change size.
