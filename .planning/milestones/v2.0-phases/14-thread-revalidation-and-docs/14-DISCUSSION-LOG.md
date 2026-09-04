# Phase 14: Thread Revalidation and Docs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-31
**Phase:** 14-thread-revalidation-and-docs
**Areas discussed:** Non-animation sampling protocol, animation ceiling protocol, harness and evidence ownership, consumer guidance structure

---

## Non-animation sampling protocol

| Question | Options considered | Selected |
|----------|--------------------|----------|
| What minimum discovery sampling should close THREAD-01? | Six paired rounds; ten paired rounds; two independent six-round sessions | Six paired rounds |
| How should each `discover()` / `discover_mdns()` pair be ordered and spaced? | Alternating order with pre-generated bounded jitter; fixed order with fixed cadence; back-to-back pairs | Alternating order with pre-generated bounded jitter |
| How many request attempts should each available Thread device receive for THREAD-02? | 100 attempts per device; 50 attempts per device; 200 attempts per device | 100 attempts per device |
| What frozen polling and confirmation rule should THREAD-04 use? | 60-second cadence, three absent pairs, three-hour cap; 30-second cadence, three absent pairs, three-hour cap; adaptive 15-second then 60-second cadence, three absent pairs, three-hour cap | 60-second cadence, three absent pairs, three-hour cap |
| Which packet should define the 100 acknowledgement trials? | No-op `SetPower` using captured current level; paired `EchoRequest` and no-op `SetPower`; no-op `SetColor` using captured colour | No-op `SetPower` using captured current level |
| How should the 100 trials be spaced? | Pre-generated 0.5–1.5 second bounded jitter; fixed one-second cadence; pre-generated 2–5 second bounded jitter | Pre-generated 0.5–1.5 second bounded jitter |
| Which latency should the evidence treat as the primary distribution? | Record and summarise both; logical completion latency only; winning-transmission RTT only | Record and summarise both |
| How should median, p95, maximum, and timeouts be calculated? | Empirical nearest-rank summaries; linearly interpolated percentiles; timeout-capped distribution | Empirical nearest-rank summaries |

**User's choices:** Six paired rounds; alternating API order with a recorded schedule; 100 no-op `SetPower` attempts per available Thread device; 0.5–1.5 second request jitter; both logical and winning-transmission latency distributions; nearest-rank statistics; 60-second dual-path staleness polling with three-pair confirmation and a three-hour cap.

**Notes:** Failed, timed-out, retransmitted, and censored attempts remain evidence. A target still advertised at the staleness cap does not close THREAD-04. The no-op request uses captured state and carries restoration evidence.

---

## Animation ceiling protocol

| Question | Options considered | Selected |
|----------|--------------------|----------|
| Which offered-rate search should each device run? | Coarse sweep plus deterministic refinement; full fixed ladder; sparse fixed ladder | Coarse sweep plus deterministic refinement |
| How long and how often should each offered rate run? | Three 30-second repetitions; three 60-second repetitions; five 30-second repetitions | Three 30-second repetitions |
| What concurrent control-query load should accompany the animation runs? | Single-shot `GetColor` at 2 Hz with bracketing baselines; single-shot `GetColor` at 1 Hz with bracketing baselines; normally retried `GetColor` at 2 Hz with bracketing baselines | Single-shot `GetColor` at 2 Hz with bracketing baselines |
| How should the observed ceiling be declared? | Contiguous 95% frontier with baseline-relative query protection; contiguous 90% frontier; peak achieved delivered FPS | Contiguous 95% frontier with baseline-relative query protection |
| How should rate ordering control for drift and carry-over? | Counterbalanced passes; grouped ascending rates; one seeded shuffle of all trials | Counterbalanced passes |
| What recovery boundary should separate animation trials? | Five-second quiet interval with fresh `Animator` and liveness check; ten-second quiet interval while reusing the `Animator`; restore full state after every trial | Five-second quiet interval with fresh `Animator` and liveness check |
| How should animation acknowledgement timing be summarised? | Per repetition and pooled per rate; pooled per rate only; per repetition only | Per repetition and pooled per rate |
| What should happen if animation-state restoration fails? | Fail closed for the mutable session; continue with other devices; invalidate the whole session | Fail closed for the mutable session |

**User's choices:** Coarse rates of 1, 2, 5, 10, 15, and 20 FPS followed by integer refinement; three 30-second repetitions; 2 Hz single-shot `GetColor` with 30-second bracketing baselines; a contiguous 95% delivery frontier; ascending, descending, and seeded-shuffle passes; five-second quiet recovery with a fresh `Animator`; per-repetition and pooled-per-rate acknowledgement summaries; fail closed after restoration failure.

**Notes:** Every lower tested rate must pass the ceiling rule, and non-monotonic results remain visible. A restoration failure stops the session before another device and requires operator-confirmed recovery plus a new session identity; valid earlier records remain usable.

---

## Harness and evidence ownership

| Question | Options considered | Selected |
|----------|--------------------|----------|
| Which tool should own Phase 14? | New Phase 14 orchestrator reusing extracted helpers; expand `ipv6_thread_probe.py`; expand `measure_merged_discovery.py` | New Phase 14 orchestrator reusing extracted helpers |
| How should its long-running hardware sessions resume? | One session manifest with independently resumable stages; one monolithic invocation; independent session per stage | One session manifest with independently resumable stages |
| Where should identifier sanitisation occur? | Sanitise at the write boundary; private raw journal plus generated sanitised journal; collect first and redact later | Sanitise at the write boundary |
| How should a completed session's evidence be organised? | Manifest plus per-stage append-only JSONL; manifest plus one heterogeneous event journal; one nested session JSON document | Manifest plus per-stage append-only JSONL |

**User's choices:** A new Phase 14 orchestrator; one immutable session manifest; independently resumable append-only stages; identity resolution in memory and sanitisation at the write boundary; separate discovery, request, animation, staleness, and closure journals; deterministic generated outputs.

**Notes:** Optional diagnostic captures remain private and cannot feed tracked summaries directly. Journals are authoritative; summaries, the six-class ledger, and the human report are generated and never hand-edited.

---

## Consumer guidance structure

| Question | Options considered | Selected |
|----------|--------------------|----------|
| Where should the canonical broadcast-first Thread story live? | Dedicated discovery user guide; expand advanced usage; versioned migration page only | Dedicated discovery user guide |
| How should the new guide be organised? | Consumer journey; API-by-API; transport concepts first | Consumer journey |
| How should the runnable migration example be maintained? | One progressive tested example; separate executable examples per API; guide-only code block | One progressive tested example |
| How should `AGENTS.md` and `CLAUDE.md` be protected from concurrency-description drift? | Marker-delimited identical blocks; independent semantic assertions; generate both blocks from one canonical snippet; `AGENTS.md` canonical with `CLAUDE.md` import after checking GSD ownership | `AGENTS.md` canonical with `CLAUDE.md` import after checking GSD ownership |

**User's choices:** Create `docs/user-guide/discovery.md`; move the UDP material into it; use a consumer-journey structure and one executable progressive example; keep shared and GSD-facing guidance in `AGENTS.md`; reduce `CLAUDE.md` to an `@AGENTS.md` import plus genuinely Claude-specific instructions.

**Notes:** The user conditionally asked to reverse the guide ownership if GSD updated only `CLAUDE.md`. The installed GSD policy was checked: the configured Codex runtime maps project instructions to `AGENTS.md`, GSD updates preserve project `AGENTS.md`, and the current hand-written guides are not silently regenerated. The condition was therefore false and the selected direction was retained. Tests will protect the import, prohibit shared duplication, require the actual Python 3.10-compatible `asyncio.gather()` behaviour in `AGENTS.md`, and forbid the false `TaskGroup` claim.

---

## The agent's Discretion

- Orchestrator CLI names, extracted-helper placement, schema field names, and evidence filenames or directory layout.
- Exact seeded schedule encoding and the bounded discovery inter-round jitter range.
- Deterministic arithmetic for the baseline-relative query-failure comparison.
- The private target alias used for the staleness experiment.
- Supporting documentation layout and copy within the selected consumer journey.
- Test doubles, fake clocks, schedulers, and fixtures used for mechanical validation.

## Deferred Ideas

None — discussion stayed within phase scope.
