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

## Milestone: v1.2 — Theme Library Update

**Shipped:** 2026-08-27
**Phases:** 4 (6–9) | **Plans:** 11 | **Tasks:** 28 | **Commits:** 87 over 13 days

### What Was Built
- A generated theme library: 166 committed JSONL records drive a validating generator into `src/lifx/theme/data.py`, replacing a 366-line hand-transcribed table that had drifted from the app for years. 169 names resolve, regeneration is byte-idempotent, and CI regenerates and diffs on every change to `data/**`
- A machine-readable fate for every key: 138 `lifx-app` / 19 library-only / 9 deprecated with a resolving `replaced_by`, plus `renamed` added post-ship once the closed three-value set proved unable to express an alias
- Category navigation over the app's own nine-category taxonomy, with slug derivation collapsed into one leaf module shared by library and generator, and the six pre-6.4.0 names failing loudly rather than mapping onto a category none of them matched
- A fail-closed, resumable hardware fidelity runner with full restoration and privacy-safe artefacts, closed under an explicit operator exception rather than a manufactured pass
- The record contract as an importable, independently tested `lifx.theme.schema`, and a catalogue page bound to the library by a drift test that fails when the two disagree

### What Worked
- Making the drift class structurally impossible. The milestone existed because a hand-written table silently diverged from its source for years with nothing to detect it. Generated data plus a CI regen-and-diff gate means that specific failure cannot recur silently.
- Binding prose to code. `test_docs_catalogue.py` fails when the catalogue page and the library disagree, so the published counts cannot quietly become false. The same instinct produced the supersession guard at the close.
- Reversing locked decisions when measurement contradicted them, and recording the reversal rather than the outcome alone. COMPAT-02's `*_legacy` aliases were retired once the 19 redefined palettes were actually measured, and the device-readback rule was dropped once it was clear no device could answer the question.
- Refusing to synthesise evidence. Phase 8's two roles could not be honestly merged into one 24-cycle record, and no combined artefact was published. The exception is written down in a machine-reviewable form that states plainly what was not verified.

### What Was Inefficient
- **A whole phase was spent proving a question unanswerable under a constraint that was dropped one phase later.** Phase 8 established that no device-based method can recover a palette longer than 16 colours, which was true. Phase 9 then obtained the true lengths from an internal HTTP API. The constraint was never wrong about devices; it was wrong about being sufficient, and nobody tested that until after the phase built around it had shipped.
- Phase 8's harness became unrunnable within days. It depends on an untracked capture directory that was removed shortly afterwards, so roughly 1,900 covered statements of carefully fail-closed tooling cannot be executed in this repository again.
- The resync silently invalidated Phase 8's determinations on 2026-08-19 and nothing noticed until the close-out audit on 2026-08-27. The regression test that would have caught it lived outside `testpaths`, so it had never run in CI.
- Phase 9 was executed entirely outside the GSD loop as two commits on two branches with no plan preceding either. Its plans and summaries are post-hoc reconstructions, and its verification is the phase's first and only goal-backward check.

### Patterns Established
- Anything transcribed from an external source ships as generated data plus a CI regen-and-diff gate, never as a hand-maintained literal
- A published page that makes counted claims about the library gets a drift test binding it to the library
- A shared derivation rule lives in a leaf module both consumers import, so a generator and its library cannot drift apart
- Superseded evidence is pinned, not regenerated or deleted: stamp it `historical` with a `source@commit` provenance, explain what superseded it, and add a live guard for whatever invariant still matters

### Key Lessons
1. **Challenge the constraint before building around it.** The most expensive thing in this milestone was a phase scoped by a rule that went unquestioned for three phases and was discarded in the fourth.
2. **A test outside `testpaths` is documentation, not a guard.** It will not run, it will rot, and it will be cited as coverage that does not exist.
3. **Evidence pinned to an untracked input has a short shelf life.** If a harness reads something git does not track, its results outlive its ability to reproduce them.
4. **Reconstructing plans after execution produces a record, not a verification.** Phase 9 labelled its reconstructions honestly and verified goal-backward against the shipped tree instead, which is the right handling, but it is recovery rather than process.
5. **Audit findings are wrong in both directions.** This close-out called FIDELITY-01 broken when the resync had satisfied it more strongly, and called Phase 7 unsigned when the sign-off had been recorded all along and only a stale line suggested otherwise. Verify the finding before acting on it, and withdraw it visibly when it does not hold.

### Cost Observations
- Model mix: not tracked precisely; planning and verification on the stronger tier, routine execution on Sonnet-class
- Notable: the close-out integration check returned a confident BLOCKER that was, on verification, a supersession the milestone should have celebrated. Independent verification of the subagent's headline claim took minutes and changed the milestone's recorded status from `gaps_found` to `tech_debt`

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~4 | 1 | First GSD milestone on this repo; full pipeline (map → discuss → plan → execute → review → audit) exercised end-to-end |
| v1.1 | many | 4 | Spike-first planning (5 hardware experiments before any phase); hardware UAT checkpoints as blocking gates; close-out audit with cross-phase integration checking against source |
| v1.2 | many | 4 | Generated data with a CI regen-and-diff gate; docs bound to code by drift tests; two locked decisions reversed in flight and recorded; one phase executed outside the loop and reconstructed afterwards |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 2500 (suite green) | — | 0 (still zero runtime deps) |
| v1.1 | 2629 (suite green) | 96% overall, 100% branch patch in CI | 0 (still zero runtime deps) |
| v1.2 | 3520 (suite green) | 97% overall, 100% branch patch in CI | 0 (still zero runtime deps) |

### Top Lessons (Verified Across Milestones)

1. **A plan's decision is a hypothesis, not a fact.** v1.0's D-01 (synchronous state save) was reversed by review; v1.1's ANIM-03 threshold was amended twice and the D5-09 docs rule is still disputed. Decisions that were never measured get re-litigated at the gate.
2. **Review catches what planning decided wrongly.** Both milestones' most valuable defects — blocking I/O on the event loop, whole-file clobbering, the large-tile chunking bug, the discovery idle-window hazard — came from review or audit, not from execution.
3. **Planning artefacts outweigh code on small changes.** True for v1.0 (25 docs commits vs 2 files) and for v1.1's quick tasks. Match the track to the change size.
4. **Unexamined constraints cost whole phases.** v1.1 calibrated a gate from one measurement round and paid for it in re-runs; v1.2 scoped a phase around a capture rule nobody tested until the phase after it. In both cases the expensive part was an assumption that was never cheap to check.
