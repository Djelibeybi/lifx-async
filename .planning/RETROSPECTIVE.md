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

## Milestone: v2.0 — Thread/IPv6 Support

**Shipped:** 2026-09-05
**Phases:** 5 (10–14) | **Plans:** 41 | **Tasks:** 93 | **Commits:** ~40 over 9 days (2026-08-27 → 2026-09-04)

### What Was Built
- IPv6/Thread transport landed onto `main` (Phase 10, PR #210): socket family follows the target address everywhere, including the animator's direct-UDP frame socket; a zone-less link-local address raises an immediate `ValueError` instead of a silent 16s timeout
- mDNS hardened to broadcast-grade quality (Phase 11): ephemeral-port bind fixed a plain IPv4 defect (25 devices found vs. 9 with `SO_REUSEPORT` contention), `Device.connectivity` exposes WiFi/Thread with the low-level record made private, cross-packet record accumulation and follow-up A/AAAA queries proven synthetically, bounded fail-closed address admission against attacker-controlled payloads
- IPv6 targeted lookup (Phase 12): `find_by_ip()` resolves an IPv6 literal, family-aware bind at every socket-creation site, concurrent/cancellation-safe on both Windows and Ubuntu CI
- Merged discovery (Phase 13): `discover()` runs UDP and unicast-verified mDNS concurrently merged by serial with the pre-existing contract proven intact by an entry-gate invariant suite; `discover_udp()`/`discover_mdns()` stay explicit; overlapping UDP callers share one active sweep; `find_by_serial()` races both legs
- Thread revalidation (Phase 14): every v1.1 wire-reliability finding measured against a real 8-device Thread fleet — discovery coverage held across repeated rounds, retry constants held against measured ack RTT, staleness measured directly by unplugging a device, every device class closed evidence-backed or as a named gap. Animation throughput recorded as a scope boundary rather than measured, seeding SEED-003 (lock `Animator` to WiFi) for a future milestone

### What Worked
- **Entry-gate invariants before merge code.** Phase 13 wrote the pre-merge invariant and before/after measurement harness first, as its own plan, so the existing `discover()` contract had a proof it survived the merge rather than a hope.
- **Spike-first discipline held for a full milestone.** No WiFi-tuned constant was retuned before Phase 14 measured it on Thread — a rule stated at the milestone's opening in 2026-07-16 and honoured through four phases that touched the exact code the constants live in.
- **Named gaps instead of open-ended blocking.** THREAD-05's six-class ledger closed on schedule because `HevLight`/`InfraredLight` recorded "no Thread-capable hardware exists" as a terminal disposition rather than leaving the phase waiting on hardware that doesn't exist yet — the same lesson v1.2's FIDELITY pattern established, reapplied deliberately.
- **Gap-closure waves stayed disciplined.** Phase 10 and Phase 11 both absorbed post-ship review findings as numbered waves (10-07..09, 11-07..14) rather than reopening earlier plans, keeping each wave's diff reviewable on its own.

### What Was Inefficient
- **Phase 11 took 14 plans against an 8-plan original estimate**, largely from a privacy/history-rewrite decision point (11-07..09) that needed its own operator sign-off cycle mid-phase — a security-sensitive call that couldn't be pre-planned away.
- **The Phase 13 coordinator teardown test hang was deferred rather than fixed inline**, and its `deferred-items.md` entry was never reconciled against a later commit that appears to fix the same symptom under a different test name — acknowledged at this milestone's close rather than resolved, see Key Lessons.
- **Two seeds (SEED-002, SEED-003) fired conceptually during Phase 14 but were not implemented in v2.0** — the animation-lock decision and the WiFi-control staleness experiment were both identified as necessary follow-ups but scoped out to keep Phase 14 hardware-gated work from expanding further.

### Patterns Established
- A milestone-opening spike-first rule (SEED-001 style) can hold across multiple phases and multiple authors when it's restated in each phase's SPEC rather than assumed from context
- Cross-cutting infra work (address-family selection, mDNS record admission) gets its own leaf module (`lifx.network.address`) the first time it's needed at more than one call site, rather than after the second duplication is noticed
- A revalidation phase against real hardware produces its evidence as append-only JSONL journals with a generated report, never hand-edited prose, so the report can't drift from what was actually observed

### Key Lessons
1. **A deferred item needs a closing check, not just an acknowledgement.** The Phase 13 coordinator-teardown hang was deferred with full root-cause detail, but nothing re-verified it before milestone close even though a plausible fix commit (`fc61b98`, a different test name, same symptom class) had already landed. Acknowledging at close is not the same as confirming closed.
2. **Security/privacy decision points inside a phase cost more than planned for.** Phase 11's history-rewrite disposition (11-07..09) nearly doubled its plan count over the original estimate; a decision this consequential deserves its own planning slot rather than riding inside a phase sized for feature work.
3. **"Proven synthetically, validated on hardware later" is a real phase boundary, not a hedge.** Phase 11's mesh-scale claims and Phase 14's hardware revalidation were planned as separate, sequenced concerns from the start, and neither blocked the other — the discipline that let Phase 14 be hardware-gated without blocking CI or any other phase.

### Cost Observations
- Model mix: planner/executor on `gpt-5.6-sol` (per `.planning/config.json`); review and gap-closure checkpoints on the stronger tier
- Notable: Phase 10 was the correct critical-path call — nothing else in the milestone was testable on real Thread hardware until it merged, and Phases 11/12 ran genuinely in parallel once it did (file-disjoint: `network/mdns/` vs `network/discovery.py`+`api.py`)

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~4 | 1 | First GSD milestone on this repo; full pipeline (map → discuss → plan → execute → review → audit) exercised end-to-end |
| v1.1 | many | 4 | Spike-first planning (5 hardware experiments before any phase); hardware UAT checkpoints as blocking gates; close-out audit with cross-phase integration checking against source |
| v1.2 | many | 4 | Generated data with a CI regen-and-diff gate; docs bound to code by drift tests; two locked decisions reversed in flight and recorded; one phase executed outside the loop and reconstructed afterwards |
| v2.0 | many | 5 | Entry-gate invariant suites written before merge code, not after; named-gap closure pattern reused deliberately from v1.2's FIDELITY precedent; hardware revalidation phase evidenced via append-only JSONL journals with a generated (never hand-edited) report; milestone close acknowledged known-open items via a structured audit rather than silently absorbing them |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 2500 (suite green) | — | 0 (still zero runtime deps) |
| v1.1 | 2629 (suite green) | 96% overall, 100% branch patch in CI | 0 (still zero runtime deps) |
| v1.2 | 3520 (suite green) | 97% overall, 100% branch patch in CI | 0 (still zero runtime deps) |
| v2.0 | 4856 collected (4844 run, 12 deselected benchmark) | 100% branch patch in CI per phase | 0 (still zero runtime deps) |

### Top Lessons (Verified Across Milestones)

1. **A plan's decision is a hypothesis, not a fact.** v1.0's D-01 (synchronous state save) was reversed by review; v1.1's ANIM-03 threshold was amended twice and the D5-09 docs rule is still disputed. Decisions that were never measured get re-litigated at the gate.
2. **Review catches what planning decided wrongly.** Both milestones' most valuable defects — blocking I/O on the event loop, whole-file clobbering, the large-tile chunking bug, the discovery idle-window hazard — came from review or audit, not from execution.
3. **Planning artefacts outweigh code on small changes.** True for v1.0 (25 docs commits vs 2 files) and for v1.1's quick tasks. Match the track to the change size.
4. **Unexamined constraints cost whole phases.** v1.1 calibrated a gate from one measurement round and paid for it in re-runs; v1.2 scoped a phase around a capture rule nobody tested until the phase after it. In both cases the expensive part was an assumption that was never cheap to check.
5. **Acknowledging a deferred item at close is not the same as confirming it's actually closed.** v2.0 acknowledged a known test-hang defect at milestone close without re-checking whether a later, differently-named commit had already fixed the same symptom. A close-out acknowledgement should trigger one verification pass, not just a disclosure entry.
