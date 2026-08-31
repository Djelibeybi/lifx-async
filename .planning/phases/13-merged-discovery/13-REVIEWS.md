---
phase: 13
reviewers: [claude, opencode, antigravity]
reviewed_at: 2026-08-30T13:36:51Z
plans_reviewed: [13-01-PLAN.md, 13-02-PLAN.md, 13-03-PLAN.md, 13-04-PLAN.md, 13-05-PLAN.md, 13-06-PLAN.md, 13-07-PLAN.md]
models:
  claude: "claude-opus-5 (reasoning=high)"
  opencode: "openrouter/z-ai/glm-5.3 (reasoning=high)"
  antigravity: "gemini-3.1-pro-high"
model_sources:
  claude: "pinned"
  opencode: "pinned"
  antigravity: "pinned"
---

# Cross-AI Plan Review — Phase 13

> **Path amendment (Plan 13-07):** Source paths in these historical review
> findings remain unchanged. See
> [`13-PATH-AMENDMENT.md`](13-PATH-AMENDMENT.md) for current canonical paths and
> the removal of the production observation module.

## Claude Review

I verified the load-bearing claims against source. Here's the review.

---

# Cross-AI Plan Review — Phase 13: Merged Discovery

## 1. Summary

This is a revised plan set, and the revision did its job: every HIGH finding from the prior round has a concrete disposition in the plan text, and I confirmed each fix against source. The emulator port re-stamp is now mandated (`.venv/lib/python3.10/site-packages/lifx_emulator/server.py:132` really does stamp `device.state.port = self.port` at construction, and `start()` at `:515-520` never re-reads the bound port, so the fix was necessary). The mDNS hermeticity fixture is now specified. The sole UDP `accepted` observation has moved down into `_discover_with_packet()`. The Echo branch is correctly demoted to synthetic-only coverage, since `get_device_class_for_product()` (`src/lifx/devices/detection.py:47-64`) returns a `Light` subclass or raises — there is no third outcome. The invalid-serial contract is preserved. The three missing mDNS catch sites are correctly described as *additions* (I confirmed `async with MdnsTransport()` at `mdns/discovery.py:881`, and the sends at `:895` and `:949`, have no surrounding catch, while receive at `:978-1000` and address follow-up at `:1069-1082` do).

Two problems survive, and both are the kind that surface late. The first is that moving the UDP observation into `_discover_with_packet()` puts it *behind the coordinator thread boundary*, where the measurement script's `ContextVar` scope does not reliably reach it — I demonstrated this empirically below. The second is that 13-06 Task 2 makes a valid GPG signature a hard blocking gate on a branch whose last eight commits are all unsigned. Everything else is refinement.

---

## 2. Strengths

- **The entry gate is genuinely production-neutral.** `discover()` at `src/lifx/api.py:822-835` is a thin `discover_devices()` delegate wrapped in `aclosing()`; extracting it to `discover_udp()` changes no behaviour. `discover` and `discover_mdns` are exported from `src/lifx/__init__.py:13-14,155-156` and `api.py:1141`, so the two-`__all__` claim is accurate.
- **Raw-response sharing remains the correct seam, and the plan's reasoning is verified.** `discover_devices()` embeds `timeout=device_timeout, max_retries=max_retries` into each `DiscoveredDevice` at `src/lifx/network/discovery.py:706-711`, while the locked compatibility key excludes both. Sharing constructed devices would leak the first subscriber's settings.
- **The observation's placement *within* `_discover_with_packet()` is correctly ordered.** The plan requires emission after validation and first-wins dedup and immediately before the yield. That lands at `discovery.py:544-547`, after source (`:414`), packet-type (`:418`), serial (`:437-451`), service-port (`:503-514`), and responder-address (`:517-527`) checks. The seam is right even though its reachability is not (see HIGH-1).
- **The port re-stamp requirement is load-bearing and correctly derived.** `validate_port(endpoint_port)` at `discovery.py:503` drops a StateService advertising port 0, so without the re-stamp the entry-gate baseline row could not exist. The plan's added assertion that the advertised port equals the bound endpoint is exactly the right guard.
- **CI reuse claims check out.** Pinned `actions/checkout@3d3c42e5` (`ci.yml:165`), pinned `actions/upload-artifact@043fb46d` (`:315`), the `ubuntu-latest`/`3.10` cell present in both the full 3-OS and reduced matrix paths (`:162-163`), and precedent for a conditional matrix-cell step at `:197-201`. The immutable-head checkout/assert/stamp/validate/upload chain is well specified.
- **The emulator timeout gap is closed.** Global timeout is 60 s (`pyproject.toml:127`) and the 120 s override applies only via the `emulator` marker or `_EMULATOR_FIXTURES` (`tests/conftest.py:100-104`); 13-01 Task 2 now mandates the marker.
- **Privacy discipline is enforceable, not aspirational.** Validate-before-append, external alias map, forbidden-key scanning, and value-suppressed `caplog` assertions all mirror the audited pattern already in `scripts/ipv6_thread_probe.py`.

---

## 3. Concerns

### HIGH — The UDP `accepted` observation cannot deterministically reach the coordinator-thread producer, so the merged arm's `udp` source contribution is not reliably producible

13-01 places the sole UDP emission inside `_discover_with_packet()` and backs it with a `ContextVar` scope entered by the measurement script around the exact `discover()` call. After 13-02, that generator is iterated by the **sweep task on the coordinator thread's event loop** (13-02 Task 1: the coordinator "supplies a factory for the existing `_discover_with_packet()` generator"). `ContextVar` values do not cross that boundary by default.

I tested both cases against this repo's interpreter:

```
# sweep task created inside the registration coroutine submitted via run_coroutine_threadsafe
{'producer_ctx': 'caller-scope', 'register_ctx': 'caller-scope'}

# realistic coordinator: sweep started once by the first subscriber, later subscribers attach
{'first': 'caller-A-no-scope'}     # the measurement subscriber's scope never appears
```

So propagation works **only** when (a) the measured call is the sweep-*starting* subscriber, and (b) the executor happens to create the sweep task inside the coroutine submitted by that subscriber rather than from coordinator-owned bookkeeping. Neither condition is stated, required, or tested by any plan. It is an implementation accident that a reasonable executor could break while satisfying every written acceptance criterion in 13-02.

The consequence is precisely 13-06 Task 1's acceptance criterion — "merged sources contain both `udp` and `mdns` from the one exact call" — and it fails at the Wave 5 CI step or, worse, silently produces a merged row with `sources: ["mdns"]` that the validator accepts because no rule requires `udp` presence on the merged arm. This is the same defect class the previous review found in 13-04's contradictory emission point; the fix relocated it rather than removing it.

Note the baseline arm is unaffected: `implementation_path: direct_udp` runs `discover_devices()` in the caller's own task, where the ContextVar is visible. That asymmetry is what makes the failure easy to miss.

### HIGH — 13-06 Task 2 hard-blocks on `git verify-commit`, but every commit on this branch is unsigned

13-06 Task 2's automated verification opens with:

```
EXPECTED_SHA=$(git rev-parse HEAD) && git verify-commit "$EXPECTED_SHA" && ...
```

and its acceptance requires Task 1's commit to "verify with `git verify-commit`". On the current branch:

```
6f21dfa N docs: plan merged discovery execution
332465a N docs: cross-AI review for phase 13
16021fe N docs: create merged discovery plans
68b7e85 N docs: research merged discovery
...
```

All eight commits report `%G?` = `N`, i.e. **no signature at all** (not an untrusted or expired one, which would report `U`/`E`). This is despite `commit.gpgsign=true` and `user.signingkey=66D6066620F03B05` being configured — so signing is being silently skipped in whatever context these commits are produced, which is the same context the executor will run in.

If Task 1's commit lands unsigned like its eight predecessors, Task 2's first gate fails, Wave 5 halts, and 13-07 (and therefore the entire fleet-evidence and closure path) is blocked behind a git configuration problem rather than anything to do with discovery. The plan should verify signing capability *before* Wave 5 — ideally as an early check in 13-01 — rather than discovering it at the one point where a human checkpoint is already queued behind it.

(The sign-off trailers are present on all eight, so the PR #219 DCO blocker recorded in `STATE.md:139` does not extend to this branch. That part is fine.)

### MEDIUM — The conftest mDNS override fixture must be synchronous, and the plan does not say so

13-04 introduces `_empty_mdns_for_public_discovery` in `tests/conftest.py`, backed by 13-01's `ContextVar`. Whether it works depends entirely on whether the fixture is sync or async. Tested here:

```python
@pytest.fixture(autouse=True)
def sync_override():  ...cv.set("sync-fixture")...

@pytest.fixture(autouse=True)
async def async_override():  ...cv.set("async-fixture")...

async def test_sees_override():
    print("SEEN:", cv.get())
# SEEN: sync-fixture
```

The async fixture's `set()` runs in its own task context and never reaches the test. Given that everything around it in this suite is async, writing this fixture as an async fixture is the natural mistake — and it **fails open**: the override silently does nothing and every public discovery test opens an ambient `MdnsTransport` to `224.0.0.251:5353` on the operator's 73-device network. 13-04's negative spy AC ("Existing empty/not-found public tests fail if any ambient `MdnsTransport` is constructed") does catch it, so this is a debug-time cost rather than a correctness hole — but it is a cheap sentence to add.

### MEDIUM — Re-stamping devices does not fix `server.port`, so any later-added device regresses

The plans require updating "every device from the injected manager so `device.state.port` equals that port". That covers the devices present at bind time. But `EmulatedLifxServer.self.port` remains `0` (`server.py:108`), and `add_device()` at `server.py:432` re-stamps with `device.state.port = self.port` — i.e. back to 0. The script owns one device, so this is latent rather than active, but a future test that adds a second device to the same server would silently reintroduce the exact defect the re-stamp exists to fix. Setting `server.port` to the bound value alongside the device re-stamp closes it permanently for one extra line.

### MEDIUM — The `PHASE13_ALIAS_MAP_PATH` handoff across the 13-06 → 13-07 boundary is unspecified

13-06 Task 3 asks the operator to "Set `PHASE13_ALIAS_MAP_PATH` to the private mapping outside this checkout"; 13-07 Task 1's precondition asserts it "is set [and] resolves to a readable file". But an `export` in the operator's own terminal does not reach the executor's Bash sessions, which are initialised from the user's profile. Unless the operator adds it to a shell profile (which the checkpoint does not say), 13-07 Task 1 fails its precondition immediately after a blocking human checkpoint has already been consumed. The checkpoint should name the durable mechanism — profile entry, `.env` outside the repo read by the script, or a `--alias-map` path passed at the checkpoint instead of an env var.

### MEDIUM — Producer-origin deadlines are documented for `find_by_serial()`, but documenting them does not make them acceptable

13-02 and 13-05 now accept the shared-sweep deadline origin and require tests plus honest docstrings, which is a real improvement over silence. But the accepted behaviour still means a `find_by_serial(serial, timeout=15)` issued 13 s into a compatible active sweep gets replay plus roughly 2 s of live discovery, then `None`. Against DISC-01's own measured premise — a single broadcast finds median 48/73 (`references/discovery.md`) — that is a materially less reliable lookup than today for exactly the overlapping-caller case FIND-05 exists to serve.

13-05's acceptance ("receives the accepted replay prefix and completes at the producer deadline") pins the behaviour rather than bounding the harm. A minimal mitigation consistent with the locked D-09/D-10 contract: exclude `find_by_serial()` from joining sweeps whose remaining window is below one re-broadcast schedule (7.6 s per `discovery.py:296-300`), and let it start its own. That preserves FIND-10's load contract for enumeration, where it was measured, without degrading targeted lookup.

### MEDIUM — "The sole UDP accepted emission" is not scoped to which sweeps it covers

`_discover_with_packet()` also backs `find_by_label()` (`src/lifx/api.py:1098`), which issues a `GetLabel` broadcast. The plans repeatedly say "exactly one lower-level UDP accepted event per accepted raw response" without stating that the invariant is scoped to the measured call's own sweeps. During a measured `discover()` no `find_by_label()` runs, so no row is corrupted today — but a concurrent label lookup inside an observation scope would contribute phantom `udp` observations to a measurement row. One clarifying sentence in 13-01 Task 2 removes the ambiguity.

### MEDIUM — 13-01's estimate remains optimistic despite the scope-sanity defence

13-01 is 10 files / 3 tasks / 18k tokens. Task 2 alone delivers a production `ContextVar` module, an mDNS source override inside `mdns/discovery.py`, and `scripts/measure_merged_discovery.py` with 8 named functions, 12 CLI flags, strict JSONL validation, a deterministic summary renderer, an embedded-emulator async context manager with cancellation-resistant teardown, and FIND-08 boundary helpers — plus a test module whose acceptance enumerates ~14 distinct behaviours including transport spies and three teardown paths. The added "Scope sanity disposition" section argues the ordering is indivisible, and I agree it is; the concern is the token budget, not the decomposition.

### LOW — Nested `uv sync --frozen` doubles dependency install on the measurement cell

13-06's second checkout into `phase13-head` runs its own `uv sync --frozen`. The lockfile is identical so `setup-uv`'s cache should hit, but a second venv is still created on every source PR forever. Worth noting in the plan as accepted cost alongside the existing "permanent CI measurement cost" acceptance.

### LOW — 13-07 Task 1 uses `uv run` rather than `uv run --frozen`

Every other command in the plan set uses `--frozen`. Trivial inconsistency, but the fleet collection is the one command whose environment most needs to match the recorded revision.

### LOW — `discover_devices` remains a public, un-shared bypass

`src/lifx/__init__.py:161` exports `discover_devices`, and 13-02 deliberately keeps it direct. 13-02's acceptance now says so explicitly and scopes T-13-05 accordingly, which is the honest disposition. Flagging only so it reaches the DOCS-04 consumer guidance in Phase 14.

---

## 4. Suggestions

1. **Fix the observation boundary before Wave 2 lands.** Either (a) require the coordinator to carry the subscribing caller's observation context explicitly onto the sweep task — pass the captured `contextvars.Context` (or the observation sink itself) through `subscribe_udp_sweep()` as a parameter rather than relying on ambient propagation — or (b) move the merged path's UDP `accepted` emission back up into `discover_devices_shared()`, on the caller loop, and keep the `_discover_with_packet()` emission for the direct path only, with an explicit rule that exactly one of the two fires per accepted response. Option (a) preserves the single-emitter design; option (b) is simpler. Either way, add a 13-02 acceptance criterion that an observation scope entered on a caller loop records `udp` events from a shared sweep, including when that caller is a *late* subscriber.
2. **Add an early signing-capability check.** Put a one-line `git verify-commit HEAD` assertion into 13-01 Task 3's acceptance, so a signing misconfiguration surfaces in Wave 1 rather than blocking Wave 5. The evidence that this is needed is on the branch right now: eight commits at `%G?` = `N` with `commit.gpgsign=true`.
3. **State that `_empty_mdns_for_public_discovery` must be a synchronous fixture** (or otherwise set the override in the test's own context), and keep the ambient-`MdnsTransport` spy as the backstop.
4. **Set `server.port` alongside the device re-stamp** so `add_device()` cannot regress a later device to port 0.
5. **Replace the env-var handoff at 13-06 Task 3** with a durable mechanism the executor can read — most simply, have the operator reply with the path at the checkpoint and have 13-07 pass it via `--alias-map`, keeping the env var as a fallback.
6. **Add a remaining-window floor for `find_by_serial()` sweep joining** (suggest one re-broadcast schedule, 7.6 s), with an edge-coverage row. Enumeration keeps the full FIND-10 sharing contract; only targeted lookup opts out when the remaining window would materially degrade it.
7. **Scope the "sole UDP accepted emission" invariant** to the measured call's own sweeps, so `find_by_label()` is explicitly outside it.
8. **Raise 13-01's estimate** to reflect Task 2, or split Task 2's script and its private seams into two commits within the same plan (the ordering constraint the plan defends applies to the *plan*, not to the number of commits inside it).

---

## 5. Risk Assessment

**Overall: MEDIUM** (down from the prior round's MEDIUM-HIGH).

The revision closed every previously identified HIGH: the emulator port re-stamp, the test-suite hermeticity fixture, the observation emission point, the FIND-07 baseline path, the unreachable Echo branch and its missing exception, the invalid-serial contract, the coordinator's shutdown/fork/abandonment story, and UDP construction fan-out all now have explicit, source-accurate dispositions. I checked each against the code and the dispositions are correct, not merely asserted.

What remains clusters in two places:

- **Evidence producibility (HIGH, but cheap).** The relocated UDP observation sits behind a thread boundary that `ContextVar` does not reliably cross. I demonstrated both the working and failing cases empirically, so this is not speculative. It costs one parameter to fix now and a Wave 5 halt to discover later — and its worst outcome is not a crash but a merged evidence row that passes validation while silently missing the `udp` contribution FIND-07 exists to measure.
- **Execution mechanics (MEDIUM).** The signing gate, the alias-map handoff, and the sync-fixture requirement are all small, but all three sit on or immediately after the blocking human checkpoint in Wave 5, where a halt is most expensive in operator attention.

The novel-infrastructure risk that dominated the prior assessment is materially reduced: the coordinator now has specified `atexit`, post-fork, and abandoned-subscriber semantics with subprocess and fork-guarded tests, and the producer-origin deadline is documented and tested rather than silently assumed. The residual deadline concern for `find_by_serial()` is a product judgement the plan has consciously made, not an oversight — I disagree with it, but it is disclosed and testable.

Addressing suggestions 1 and 2 alone removes both plausible execution-halting failures and brings this to **LOW-MEDIUM**.

---

## OpenCode Review

# Cross-AI Plan Review: Phase 13 Merged Discovery (Plans 13-01 – 13-07)

Reviewed against live source at `main` (6f21dfa). All file:line citations verified by reading the referenced code, the installed `lifx-emulator-core` 3.7.0 package, and `.github/workflows/ci.yml`.

---

## Overall Phase Assessment

This is an unusually disciplined plan set. The wave structure is correct (entry gate → file-disjoint mechanisms → merge → race → evidence → closure), every locked decision D-01 through D-16 maps to an executable task, and the claims I traced against source code held up in every case I checked — including several non-obvious traps (the emulator `state.port` re-stamp, the uncaught mDNS send paths, the `_state is None` construction gap). The residual risk is concentrated in three places: the sheer size of single tasks against their token estimates, the representativeness of emulator-mode merged timing (the mDNS leg is synthetic there by construction), and the cross-platform fragility of coordinator-thread lifecycle tests. Nothing I found is a blocker.

**Verified source-claim spot checks (all passed):**

| Plan claim | Evidence |
|---|---|
| `discover()` delegates only to `discover_devices()` with `aclosing` | `src/lifx/api.py:822-835` |
| `discover_devices()` embeds subscriber-specific `device_timeout`/`max_retries` into each `DiscoveredDevice` | `src/lifx/network/discovery.py:704-711` |
| Initial PTR send (line 896) and retransmit (line 949) have no `LifxNetworkError` catch; only receive (988) and follow-up (1071) absorb, both logging `str(error)` | `src/lifx/network/mdns/discovery.py:896,949,988-996,1069-1082` |
| `MdnsTransport.send` logs destination and `str(e)` at DEBUG | `src/lifx/network/mdns/transport.py:206-215` |
| A newly constructed `Light` has `_state = None`; `adopt_cached_metadata()` excludes label/live state; `get_color()` updates `_state` only when present | `src/lifx/devices/base.py:546-586`, `src/lifx/devices/light.py:121-186` |
| Classifier order Ceiling→Matrix→MultiZone→Infrared→HEV→unsupported→Light; raises `LifxUnsupportedDeviceError` for relay/button-only | `src/lifx/devices/detection.py:47-64` |
| `DeviceConnection.request(packet, timeout=None)` accepts per-call timeout; Echo 58/59 handled | `src/lifx/network/connection.py:1253,1216-1221` |
| Packet constants GetColor 101 / StateColor 107 / StateUnhandled 223 / Echo 58-59 | `src/lifx/protocol/packets.py:527-531,768-771,448-451,48-68` |
| `Serial.from_string` raises `ValueError` on invalid input; strips `:`/`-`/space | `src/lifx/protocol/models.py:110-176` |
| `EmulatedLifxServer.start()` binds via `create_datagram_endpoint` and never writes the bound port back to `self.port`; devices' `state.port` is set from constructor `self.port` at init and `add_device`; StateService replies use `device_state.port` | `lifx_emulator/server.py:426-436,128-134,429-433`, `lifx_emulator/handlers/device_handlers.py:19-43` |
| CI matrix: 3-OS only for source-changing PRs; Python 3.10 in matrix; `upload-artifact` pinned; `workflow_dispatch` reaches release jobs | `.github/workflows/ci.yml:9-20,161-165,315` |

---

## 13-01-PLAN.md — Entry gate

**Summary:** Correct and well-sequenced: pin the baseline before changing it, and make the evidence harness executable on the broadcast-only tree. The emulator `state.port` re-stamp requirement is a genuine trap the plan handles precisely (verified above: with `port=0`, the emulator stamps `state.port = 0` and never learns the bound port, so `GetService` replies would advertise port 0 without the re-stamp).

**Strengths:**
- Entry-gate-before-merge ordering is enforced by commit ancestry (Task 3), not just by convention — falsifiable per FIND-02.
- Baseline arm pinned to direct `discover_devices()` with `implementation_path` recorded, so the post-13-02 switch of `discover_udp()` to the shared facade cannot contaminate the FIND-07 comparison. Honest delta.
- Observation emission placed solely inside `_discover_with_packet()` after validation/dedup (discovery.py:550-555 is the natural site) means all later consumers inherit exactly one event — verified the wrapper (discovery.py:689-711) and `find_by_label()` (api.py:1098) both flow through that generator.

**Concerns:**
- **MEDIUM — Task 2 is oversized for its estimate.** One "auto" task carries the full D-13/D-14/D-15/D-16 harness, the emulator ownership lifecycle, the `_override_mdns_service_source()` ContextVar seam, FIND-08 eligibility logic, and ~10 acceptance-criteria clusters. The 3-file diff understates the behavioural surface; expect this task to split during execution.
- **MEDIUM — emulator merged-arm timing is structurally unrepresentative.** The synthetic `_LifxServiceRecord` bypasses `MdnsTransport` entirely, so the emulator "merged" arm omits the real mDNS sweep cost (PTR query, 1s/3s retransmits, ~4s idle window — mdns/discovery.py:901-904). On a real network the mDNS leg typically runs the full idle window and dominates merged wall time. Fleet pairs capture the real number, but the summary should label emulator merged timing as a lower bound on the mDNS leg, or FIND-07's "emulator CI wall time" component risks being read as representative.
- **LOW — production hermeticity seam.** `_override_mdns_service_source()` in `src/lifx/network/mdns/discovery.py` is a test/evidence-only hook in runtime code. Private, inert by default, and never bypasses liveness — acceptable, but it is scope creep in the production tree and should be documented as a retained seam (13-01 does say "retained private hermetic-test/evidence seam", good).
- **LOW — Task 1's "consumer-resume idle reset" invariant test will survive 13-02 only if phrased as outcome, not mechanism.** After the coordinator drains eagerly, consumer resume no longer drives the producer at all (discovery.py:557-579's post-yield reset fires on coordinator resume instead). The property "consumer body time never expires the idle window" still holds, more strongly — but a test asserting the sweep *stays alive* because of consumer stalls would fail. Recommend the entry-gate tests pin observable outcomes (no record loss, bounded completion), not pacing internals.

**Suggestions:**
- Split Task 2 into "harness core + JSONL validation" and "emulator ownership + source override" if the executor hits its budget.
- Add one summary sentence in 13-06/13-07 marking emulator merged-arm timing as synthetic-mDNS (see concern above).

**Risk:** MEDIUM — mostly schedule risk on Task 2, not correctness risk.

---

## 13-02-PLAN.md — Process-wide UDP coordinator

**Summary:** The hardest plan, and the design is sound: raw `DiscoveryResponse` fan-out (not `DiscoveredDevice`, correctly avoiding first-subscriber settings leakage — verified at discovery.py:704-711), serialised coordinator-loop append/register ordering, idempotent detach, and honest treatment of the producer-origin deadline. The thread/loop architecture matches the documented Python 3.10 boundaries.

**Strengths:**
- The compatibility key exactly matches the SPEC constraint (verified in 13-SPEC.md "Constraints"), and `_address_is_prevalidated` is correctly kept out of the key with per-caller advisory emission preserved.
- Prefix-then-suffix ordering via coordinator-loop serialisation point (append before fan-out; register schedules prefix before admitting suffix) is the correct race-free construction.
- `atexit`/`register_at_fork`/abandoned-subscriber detachment closes the lifecycle holes reviewers usually miss. No signal handlers — correct.
- The "Review feedback dispositions" section engages the rejected same-loop alternative with the right rationale (D-10 lock).

**Concerns:**
- **MEDIUM — cross-platform test fragility.** Real OS threads, two `asyncio.run()` loops, barriers, subprocess exit tests, and fork-guarded child-reset tests across ubuntu/macos/windows CI (ci.yml:161-165) is historically where suites flake, especially Windows. The plan bans sleeps and fixed interfaces, which helps, but the fork test needs a spawn-safe guard on Windows/macOS (macOS fork is unsafe with threads). Suggest explicitly requiring `pytest.mark.skipif(sys.platform == "win32")`-style guards and a retry-free deterministic design review gate.
- **MEDIUM — the pacing semantics change is real and only partially testable.** Today a stalled consumer can end a sweep early via the overall deadline (discovery.py:570-578 documents this exact hazard); under the coordinator, the wire sweep completes independently and queued records are constructed afterwards, unbounded by the discovery `timeout`. That is arguably better (no device loss) but it is a public behavioural change: `discover()` can now yield devices *after* `timeout` seconds have elapsed since call start, because construction time sits behind the queue. The plan documents producer-origin deadlines for late subscribers but not the post-deadline-yield case for slow constructors. This deserves an explicit docstring line and a test asserting the bound (or acknowledging its absence) on the merged path.
- **LOW — `os.register_at_fork` registration timing.** Register at import (global side effect on import) or lazily (window where a fork before first sweep misses the reset)? Plan is silent. Recommend lazy registration inside coordinator start, before the thread exists.
- **LOW — estimate optimism.** Coordinator + facade + the full deterministic lifecycle test matrix in 18k tokens is tight.

**Suggestions:**
- Add one acceptance criterion: "a device record accepted before the producer deadline is still delivered to a subscriber whose construction loop exceeds the deadline, and the public docstring states this bound change".
- Pin the fork-test platform guard as an explicit artifact.

**Risk:** MEDIUM — highest engineering difficulty in the phase, but the decomposition and cleanup contract are right.

---

## 13-03-PLAN.md — mDNS liveness verification

**Summary:** The strongest plan of the set. Every seam claim traced to source is accurate: the uncaught open/send paths (mdns/discovery.py:896, 949), the receive/follow-up catches that absorb and log raw text (988-996, 1069-1082), the `_state is None` D-06 gap (base.py:562, light.py:160), and the Echo branch being currently unreachable (detection.py:24 returns `type[Light]` only, raising for unsupported). The decision to keep D-05's Echo branch as synthetic-only coverage rather than pretending it is reachable is exactly right.

**Strengths:**
- The conditional sink design (absorb only with a sink; re-raise byte-compatibly without) preserves `discover_mdns()`'s standalone contract while giving the merged path typed, privacy-safe events — verified the current asymmetry is real (receive absorbs at 988, sends propagate at 896/949).
- The `_DiscoveryLightSnapshot` resolution to the D-06 gap is the correct minimal design: no partial `LightState`, no volatile cache, `_label` seeded (mirrors light.py:157), `_state` updated only when present (mirrors light.py:160-168).
- One-deadline-for-everything including queue wait, with `min(device_timeout, remaining)`, correctly reuses connection.py:1253's per-call timeout rather than inventing a probe retry constant.
- `candidate_unsupported` for `LifxUnsupportedDeviceError` matches detection.py:60-62's raise site and keeps it candidate-local.

**Concerns:**
- **LOW — `_MdnsCandidateFailure` allowlist breadth.** The candidate allowlist includes `LifxTimeoutError` at both sweep and candidate level; the plan correctly keeps ordinary receive-timeout as clean completion, but the boundary between "candidate request timed out" and "sweep receive timed out" depends on where the `LifxTimeoutError` surfaces (transport.receive vs connection.request). The tests cover both; just ensure the reason taxonomy documents that the same exception class maps to different stages by catch site, or a future reader will "simplify" it into a bug.
- **LOW — `firmware` is a string on the record** (types.py:26). The observation layer must parse it to an integer tuple for FIND-08; plan says "integer firmware tuple when parseable" — fine, but add an explicit unparseable-firmware test row.
- **LOW — cap 16 rationale is asserted, not measured.** Marked `[RESOLVED by Plan 13-03]` in research but the resolution is a reasoned choice with tests, not a measurement. Acceptable under planner discretion; just don't let 13-07's summary imply the cap was empirically derived.

**Suggestions:** None material. This plan can execute as written.

**Risk:** LOW.

---

## 13-04-PLAN.md — Merged default stream

**Summary:** Correct merge architecture with the two hardest correctness properties (exactly-once diagnostics, fail-fast vs degrade) specified testably. The hermetic-fixture-by-default decision (`_empty_mdns_for_public_discovery` in conftest.py) is the right call — without it, every existing public discovery test would touch the developer LAN's mDNS the moment the default goes dual-source.

**Strengths:**
- Explicit Python 3.10 `create_task()` supervision with manual reap; the rejected-TaskGroup disposition is correct for this codebase (pyproject floor 3.10, and cancel-sibling semantics genuinely wrong for failure-isolated legs).
- Preserving the one-at-a-time `_create_discovered_device()` cadence (verified current behaviour at api.py:831-835) avoids a 73-device construction burst — a subtle regression the plan caught.
- The "exactly one event, cannot take both routes" rule (outer allowlist only for genuinely escaping failures before the typed contract activates) closes the double-report race that the conditional catches in 13-03 would otherwise create.
- AC coverage for `find_by_ip()`/`find_by_label()` signature stability matches FIND-09/SPEC AC9.

**Concerns:**
- **MEDIUM — post-deadline delivery (same issue as 13-02).** "Results stream before the slower leg completes" plus the coordinator's eager drain means devices can be yielded after the caller's nominal `timeout` when per-device construction is slow. Under the pre-merge contract the overall deadline ended the sweep (and truncated late results). This is a real observable contract change to `discover()`; FIND-02's "existing contract survives" is only true if this is either prevented or explicitly re-documented. Neither plan states which.
- **LOW — the verify selector `-k 'discover and not find_by_serial'`** will also select `discover_mdns` tests that 13-03 conditioned on sink behaviour; harmless but broad.
- **LOW — `LifxUnsupportedDeviceError` arrives from `create_device()`-adjacent paths too** (discovery.py:161-162 catches it and returns `None` on the UDP leg). On the mDNS leg it is candidate-local by plan; ensure the merged path does not accidentally let a UDP-leg `None` (silently skipped device) be confused with an absorbed mDNS candidate event in the observer's source-contribution accounting.

**Suggestions:**
- Resolve the post-deadline-yield question explicitly: either bound subscriber-side construction by the caller deadline (skip/drop with a diagnostic) or document the change in `discover()`'s docstring and add it to the 13-01 entry-gate assertions so it is a decision, not an accident.

**Risk:** MEDIUM (solely for the deadline-semantics ambiguity; the rest is LOW).

---

## 13-05-PLAN.md — Dual-source serial race

**Summary:** Clean, correctly scoped, and the invalid-serial disposition is right: current `find_by_serial()` (api.py:949-962) manually strips separators and never raises, so catching `Serial.from_string`'s `ValueError` and returning `None` preserves the public outcome.

**Strengths:**
- Races matches, not leg completion — the core state-machine insight, matching SPEC requirement 5.
- Loser reaped *before* construction/return; repeated/concurrent/cancelled matrix is exhaustive.
- Honest naming of the active-sweep inherited deadline ("may receive less than a fresh full timeout").

**Concerns:**
- **LOW — one marginal normalisation delta:** `Serial._remove_separators` also strips spaces (models.py:161) while the current api.py:949 does not, so a spaced serial like `"d073d5 123456"` previously never matched (returned `None`) and will now match. Arguably a fix; add it to the AC list so it is a tested, intentional change rather than a surprise.
- **LOW — joining an active sweep whose key was created by a `discover()` call with the *same* wire/timing args but a different serial target:** the lookup inherits the sweep mid-flight and has no replay guarantee for the target serial if it was accepted before subscription... actually replay covers the accepted prefix, so the serial is delivered. Correct as designed; no action.

**Suggestions:** Add the space-normalisation delta as an explicit test row.

**Risk:** LOW.

---

## 13-06-PLAN.md — CI evidence path

**Summary:** The most operationally intricate plan, and the verification chain (signed commit → push → PR run whose `headSha` equals that commit → nested checkout asserting `git rev-parse HEAD` equality → revision-stamped rows → validated append) is sound and tamper-resistant. Verified the CI facts it rests on: 3-OS matrix only on source-changing PRs (ci.yml:161-165), Python 3.10 in matrix, `upload-artifact` pinned (ci.yml:315), and `workflow_dispatch` genuinely reaches release jobs — so the "never use workflow_dispatch" rule is correct, not paranoia.

**Strengths:**
- Ordinary merge-ref tests preserved; measurement isolated to a second checkout pinned to the immutable PR head. This is the correct trust boundary.
- The signed/DCO commit boundary as a hard task gate matches AGENTS.md's `git commit -S -s` rule.
- The Task 3 human checkpoint requests exactly the operator-only facts (alias path, quiescence, confounds) and nothing else — privacy model intact.

**Concerns:**
- **MEDIUM — PR targeting.** Task 2 pushes the phase branch and opens a draft PR against the default branch. Verify the repository's branch protection and whether a phase-branch PR this early (before Phase 13 is complete) is acceptable workflow, and that the `pull_request` paths filter (ci.yml:9-20) will fire — it will, since Task 1's commit touches `src/`, `tests/`, `scripts/`, and `ci.yml`, but this dependency should be stated so a later "docs-only" gate commit can't accidentally become the measured head.
- **MEDIUM — the completed-merge focused test doubles as the CI evidence precondition, but emulator merged timing remains synthetic-mDNS** (see 13-01 concern). The plan is internally honest about hermeticity; carry that honesty into the summary's labelling.
- **LOW — `uv sync --frozen` in the nested checkout** creates a second environment; cache mitigates, but the step's `timeout-minutes` should be set explicitly.
- **LOW — PR-head evidence is one pair (one round).** FIND-07 requires "at least one current-revision emulator CI run" — satisfied — but a single CI run is noisy; consider whether the validator should mark single-round emulator evidence as such.

**Suggestions:**
- State explicitly that the measured PR head commit must contain source changes (paths-filter dependency).
- Add `timeout-minutes` to the measurement step.

**Risk:** MEDIUM — operational complexity and external-service dependence, not design flaws.

---

## 13-07-PLAN.md — Fleet evidence and closure

**Summary:** Correct closure plan. The evidence invariants (append-only, byte-prefix preservation, byte-identical summary regeneration, confound labelling, named-gap-only FIND-08 closure) are all testable, and the multi-source coverage audit table is exhaustive — I traced its requirement/decision rows against REQUIREMENTS.md and 13-SPEC.md and found no misattributions.

**Strengths:**
- FIND-08's honest-closure discipline: emulator/Thread/ineligible firmware can never confirm it; only eligible physical WiFi or the exact `no_eligible_find08_population` gap. Integer boundary tests `(3,69)/(3,70)/(3,99)/(4,0)` match the documented MAC quirk rule.
- "No slowdown ceiling" — observed deltas only — resists the temptation to turn evidence into a gate the fleet cannot renegotiate.
- Final gate includes full frozen suite, Ruff, Pyright, and a value-suppressed staged-diff privacy audit per AGENTS.md:17-38.

**Concerns:**
- **MEDIUM — six sequential fleet pairs × (baseline ~15s + merged ~15s+) plus quiescence discipline is a ~5+ minute operator window minimum**, and any mid-collection fleet state change invalidates comparability without necessarily being detectable. D-15's confound labelling handles honesty, but consider adding a within-run stability check (e.g. baseline unique counts across rounds flagged if variance exceeds a categorical threshold — as a *label*, not a gate).
- **LOW — `autonomous: true` on a plan whose Task 1 precondition is the 13-06 human checkpoint.** The precondition field covers it; just ensure the executor halts rather than improvising fleet state.
- **LOW — "all thirty-six SPEC edge rows have exactly one lifted must-have entry"** is asserted in success criteria; I did not independently count the 34 truths + 2 backstops across the seven plans. Worth a mechanical check at execution time.

**Suggestions:** Add the baseline-variance stability label to the summary spec.

**Risk:** LOW.

---

## Cross-Cutting Findings

1. **HIGH (aggregate, MEDIUM individually) — the `discover()` overall-deadline semantics drift across 13-02/13-04.** Pre-merge, the overall timeout bounds the entire observable sweep including consumer-side construction (discovery.py:560-578 documents this explicitly). Post-merge under the shared facade, the wire sweep is bounded but subscriber-side device construction is not, so yields can continue past `timeout`. No plan owns this decision. It should be made explicitly in 13-02/13-04 and pinned in the 13-01 entry-gate suite either way, or FIND-02's "existing contract survives the merge" is only loosely true.

2. **MEDIUM — emulator merged-arm timing is a lower bound on the mDNS leg.** The `_override_mdns_service_source()` design is the right hermeticity mechanism, but the FIND-07 emulator evidence will not include real mDNS sweep cost (query, retransmits, idle window — mdns/discovery.py:901-904). Label it as such in 13-MEASUREMENT-SUMMARY.md so downstream readers do not extrapolate emulator deltas to fleet expectations.

3. **MEDIUM — task-size/estimate mismatch.** 13-01 Task 2 and 13-02 Task 1 each carry roughly a plan's worth of behavioural surface. Both will stress their 18k-token budgets. Neither is incorrectly decomposed — the orderings are genuinely indivisible — but the executor should expect to split commits within tasks.

4. **LOW — test/evidence seams in production modules** (`discovery_observation.py`, `_override_mdns_service_source()`). Both private, inert by default, never bypass liveness. Acceptable; document them as retained seams so a future refactor does not delete them as "dead code".

5. **LOW — normalisation deltas from adopting `Serial.from_string`** in `find_by_serial()` (space stripping). Intentional-test-worthy, not risky.

## Risk Assessment

**Overall: MEDIUM.** The architecture is right, the source claims verify, the privacy model is rigorous, and the evidence workflow is tamper-resistant. The two things that could bite are (a) the unowned deadline-semantics change on the public `discover()` contract, which is cheap to fix now and expensive to discover post-merge, and (b) schedule risk from oversized tasks plus cross-platform coordinator tests. No plan requires rework; items 1 and 2 above should be dispositioned before Wave 3 begins, since both touch plans that are already approved.

---

## Antigravity Review

> [reviewed-without-source-citations] This reviewer declared source-grounded evidence but cited no file:line source evidence, so it reviewed the pasted plan text only — down-weight its verdict in the Consensus Summary.

# Cross-AI Plan Review: Phase 13 Merged Discovery

## 1. Overall Assessment
The provided implementation plans (`13-01-PLAN.md` and `13-02-PLAN.md`) are exceptionally thorough, well-researched, and perfectly aligned with the project's strict constraints. The architectural decisions elegantly balance backward compatibility (FIND-02), network resource conservation (single-flight UDP), and strict privacy boundaries. The choice to orchestrate around existing, proven primitives (`_discover_with_packet`, `DeviceConnection`) rather than rewriting them minimizes regression risk.

## 2. Repository Alignment & Verification
All file paths, line references, and structural assumptions in the prompt were verified against the local repository at `/Volumes/External/Developer/Djelibeybi/lifx-async`:
*   `src/lifx/network/discovery.py`: Confirmed the existence of `_discover_with_packet` and `discover_devices`, validating that established bounds like serial deduplication, socket limits, and validation checks remain isolated as the low-level producer.
*   `src/lifx/api.py`: Confirmed `discover` and `discover_mdns` generators and their `contextlib.aclosing` wrappers.
*   `src/lifx/network/mdns/discovery.py`: Confirmed the `_discover_lifx_services` generator boundary, correctly identifying where mDNS candidates are yielded locally without an ambient cache.
*   `src/lifx/devices/detection.py`: Confirmed `get_device_class_for_product` reliably handles ordered class resolution.
*   `src/lifx/devices/base.py` & `light.py`: Confirmed that `adopt_cached_metadata()` intentionally excludes live state, proving that the `_DiscoveryLightSnapshot` seed strategy outlined in the prompt is exactly the right path forward to resolve D-06.
*   `pyproject.toml`: Confirmed the Python 3.10 minimum requirement, the zero-dependency commitment (`dependencies = []`), and OS matrices that structurally rule out `asyncio.TaskGroup` and justify the custom lifecycle orchestration.

## 3. Plan 13-01: Entry-Gate Telemetry (Quality & Completeness)
**Quality & Completeness:**
*   This plan brilliantly establishes a safe sandbox for measurement before making disruptive architectural changes to the public `discover()`. The migration ordering prevents confounding the baseline.
*   The `ContextVar`-backed `_override_mdns_service_source` mechanism cleanly allows local loopback emulator tests without polluting the CI environment with ambient mDNS traffic.
*   The emphasis on privacy—specifically scrubbing exception text, raw network payloads, and real identifiers from the append-only `.jsonl`—satisfies the stringent privacy rules established in `AGENTS.md`.

**Risks & Mitigations:**
*   **Risk:** `ContextVar` propagation in async code is generally automatic, but if `lifx-emulator-core` or the measurement harness inadvertently utilizes `run_in_executor`, context might be dropped.
    *   *Mitigation:* The plan executes the synthetic emulator context tightly around `_discover_lifx_services()`. This guarantees the scope remains confined safely to the async task that orchestrates the generator, avoiding thread boundary drops.

## 4. Plan 13-02: Process-wide Coordinator (Quality & Completeness)
**Quality & Completeness:**
*   The use of a lazy, internal `threading.Thread` owning a completely separate `asyncio.run()` loop cleanly solves the process-wide, cross-loop sharing requirement (D-10/D-11). It isolates global mutable sweep state from caller loops without making the codebase inherently blocking.
*   The queue backpressure vulnerability (where a slow consumer could stall the UDP producer) is correctly thwarted by relying exclusively on unbounded queues (`maxsize=0`) and pushing state via `call_soon_threadsafe(queue.put_nowait, ...)`.

**Risks & Mitigations:**
*   **Risk (Thread Teardown):** Manually managed Python threads blocking on asynchronous I/O can hang the interpreter at shutdown if sockets are not fully closed.
    *   *Mitigation:* The plan includes a bounded `atexit` teardown phase (`_shutdown_udp_coordinator_at_exit`). The requirement to invoke `shutdown_asyncgens()` ensures generators finalize promptly.
*   **Risk (Fork Safety):** UNIX environments (particularly macOS CI runners) forking processes during test orchestration can break inherited thread locks.
    *   *Mitigation:* Leveraging `os.register_at_fork(after_in_child=...)` to discard corrupted inherited registry state is a highly robust solution, preventing strange cross-talk in test suites.

## 5. Constructive Feedback / Recommendations
To ensure a completely bulletproof delivery across waves 1 and 2, consider the following tactical refinements:

1.  **Strict Shutdown Timeouts:** In `13-02`, when implementing the `atexit` handler (`_shutdown_udp_coordinator_at_exit`), explicitly enforce a tight timeout (e.g., `asyncio.wait_for(..., timeout=2.0)` on the join/cleanup phase). If an unhandled underlying socket block occurs, it's safer for the script to crash immediately than to hang a CI pipeline indefinitely.
2.  **Explicit ContextVar Resets:** Ensure the `_MdnsServiceSourceOverride` context manager employs a strict `try/finally` block where `token = var.set(...)` is paired safely with `var.reset(token)`. A leaked token returning to the main loop could unpredictably corrupt subsequent, unrelated standalone tests.
3.  **Graceful Late-Subscriber Expiry:** The logic limiting late subscribers strictly to the remaining producer window is completely correct. Ensure that if `remaining <= 0` at the exact millisecond of subscription, the coordinator immediately resolves the request by pushing terminal state directly to the caller's queue (after prefix replay) rather than raising a synchronous error, maintaining standard interface consistency.

---

## Consensus Summary

Two prompt-fed reviewers inspected all seven plans against the repository. Claude and OpenCode agree that the revised plan graph is disciplined, source-accurate in its core architecture, privacy-aware, and materially stronger than the prior version. Antigravity is down-weighted because it cited no `file:line` evidence and discussed only Plans 13-01 and 13-02.

Overall risk remains **MEDIUM**. The plan set is executable, but one high-impact evidence-path issue and one public deadline-semantics ambiguity should be dispositioned before execution reaches their affected waves.

### Agreed Strengths

- The entry-gate-first wave ordering protects the direct UDP baseline before merged behaviour lands.
- Sharing validated raw `DiscoveryResponse` values, then constructing fresh devices with subscriber-specific settings, is the correct coordinator boundary.
- The emulator dynamic-port re-stamp, mDNS failure catches, supported-device classification, StateColor adoption, invalid-serial handling, and immutable PR-head CI chain match the current source.
- The evidence design is privacy-safe and auditable: external aliases, validation before append, pseudonymised rows, immutable revision binding, and deterministic summary regeneration.
- The seven-plan dependency graph correctly separates automated CI work, the manual fleet-preparation checkpoint, and automated fleet collection.

### Agreed Concerns

- **Task size and estimate pressure (MEDIUM):** Claude and OpenCode both judge 13-01 Task 2 and the coordinator work in 13-02 large for their estimates. The dependency order is defensible, but execution may require more budget or multiple commits within a task.
- **Coordinator lifecycle and cross-platform proof (MEDIUM):** the process-wide thread/loop design is sound but novel for this repository. Deterministic Windows/macOS/Linux lifecycle tests, explicit platform guards for fork-only cases, and no sleep-based timing remain important.

### Grounded Concern Requiring Disposition

- **Caller observation across the coordinator thread (HIGH, Claude):** Plan 13-01 scopes UDP `accepted` observations with a `ContextVar`, while Plan 13-02 moves the raw sweep onto a coordinator-owned thread and event loop. Ambient context propagation is not guaranteed for a late subscriber or a sweep created from coordinator-owned bookkeeping. If the observation sink is not carried explicitly, the merged measurement can miss its UDP contribution. Add an explicit sink/context transfer contract and a late-subscriber test that proves a caller-scoped measurement receives the shared sweep's UDP observations.
- **Post-deadline delivery semantics (MEDIUM-HIGH, OpenCode):** eager coordinator draining bounds the wire sweep at the producer deadline, but subscriber-side device construction can continue afterwards. The plans document producer-origin deadlines for late subscribers without explicitly deciding whether `discover(timeout=...)` may yield after the caller's nominal wall deadline. Prevent that drift or document and test it as an intentional compatibility change before Wave 3.

### Other Actionable Refinements

- State that the autouse empty-mDNS override fixture must set its `ContextVar` in the test's context (for example, as a synchronous fixture), with the ambient-transport spy retained as a backstop.
- Set the emulator server's own `port` alongside existing device-state re-stamps so later `add_device()` calls cannot advertise port zero.
- Make the 13-06 to 13-07 alias-map handoff durable across executor sessions without copying the mapping into the repository.
- Label emulator merged timing as synthetic-mDNS and therefore not representative of real multicast sweep cost; fleet pairs remain the representative measurement.
- Use `uv run --frozen` for fleet collection and add explicit CI step timeouts where appropriate.
- Make the `Serial.from_string()` space-stripping delta explicit if spaced serial input is intended to begin matching.

### Divergent or Rejected Findings

- **Rejected — recent commits are unsigned:** Claude's sandbox reported `%G? = N`, but host verification shows all eight recent commits as `G`, and `git verify-commit --raw 6f21dfa` reports `GOODSIG` and `VALIDSIG` for `27B3A9EA9D847501F05627B166D6066620F03B05`. Keep the existing signed/DCO gate; no early signing-remediation plan is required.
- **Not consensus — late `find_by_serial()` subscribers should start a fresh sweep below a remaining-window floor:** this is a product-contract suggestion from Claude and would weaken the locked compatible-caller sharing decision. Retain it as a possible future policy change unless the user explicitly revises D-10.
- **Down-weighted — Antigravity's ContextVar mitigation:** it addresses the caller-loop mDNS override, not the UDP observation crossing into the coordinator thread, and contains no source citations.
- **OpenCode-only refinements:** post-deadline delivery, emulator lower-bound labelling, spaced-serial normalisation, and fleet variance labelling are useful but were not independently corroborated by another fully grounded reviewer.
