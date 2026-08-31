# Phase 13: Merged Discovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-30
**Phase:** 13-merged-discovery
**Areas discussed:** mDNS failure boundary, live-response proof, shared-sweep fan-out,
measurement workflow

---

## mDNS Failure Boundary

### Escaping failure boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit availability allowlist | Absorb known availability failures and surface defects | ✓ |
| All library exceptions | Absorb every `LifxError` | |
| All ordinary exceptions | Degrade for every `Exception` | |

**User's choice:** Explicit availability allowlist.
**Notes:** Candidate validation remains local; invariant and programming defects propagate after
cleanup.

### Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| One privacy-safe DEBUG event | Stable stage/reason and exception type only | ✓ |
| One privacy-safe WARNING | Make leg failure conspicuous | |
| No event | Degrade silently | |

**User's choice:** One privacy-safe `DEBUG` event per call.
**Notes:** No identifiers, addresses, raw packets, TXT values, or exception text.

### Unexpected defects

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast after deterministic cleanup | Cancel/reap all work, then propagate | ✓ |
| Let UDP finish, then raise | Delay propagation until the UDP deadline | |
| Treat it as unavailable | Suppress like an availability failure | |

**User's choice:** Fail fast after deterministic cleanup.
**Notes:** Do not wait out the ordinary discovery window.

### Failure stage

| Option | Description | Selected |
|--------|-------------|----------|
| Stage-aware policy | Sweep failures end the leg; candidate failures drop the candidate | ✓ |
| Single global allowlist | Any allowed type ends the whole mDNS leg | |
| Candidate failure ends the leg | One failed verification invalidates the source | |

**User's choice:** Stage-aware policy.
**Notes:** Cancellation and invariant failures remain non-recoverable control/defect paths.

---

## Live-Response Proof

### Probe packet

| Option | Description | Selected |
|--------|-------------|----------|
| Echo challenge | Purpose-built liveness proof | |
| `GetService` | Reuse discovery response validation | |
| `GetVersion` | Obtain and cross-check product identity | Initially |
| Product-directed `GetColor`/Echo | Use `GetColor` for lights and Echo for non-lights | ✓ |

**User's choice:** Inspect mDNS TXT `p`; use `GetColor` for lights and Echo for non-lights.
**Notes:** The user initially selected `GetVersion` because product type would soon be needed. After
confirming that mDNS already carries product ID in `p`, they chose `GetColor` for its immediately
useful label/colour/power response. A purported light returning `StateUnhandled` is rejected.

### State reuse

| Option | Description | Selected |
|--------|-------------|----------|
| Seed existing state only | Retain snapshot without changing fresh getters | ✓ |
| One-shot discovery cache | First getter consumes discovery response | |
| Discard after validation | Use response only for liveness | |

**User's choice:** Seed existing state only.
**Notes:** Later colour and power getters still query the device.

### Verification concurrency

| Option | Description | Selected |
|--------|-------------|----------|
| Bounded concurrency | Parallel probes behind an internal cap | ✓ |
| Fully concurrent | Start every candidate immediately | |
| Sequential | Verify one candidate at a time | |

**User's choice:** Bounded concurrency.
**Notes:** Queued candidates receive no deadline extension; exact cap is planner discretion.

### Retry and deadline

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse normal settings within remaining deadline | Honour caller request settings, capped globally | ✓ |
| One attempt only | Drop after one silence | |
| Dedicated discovery retry | Add a new fixed liveness schedule | |

**User's choice:** Reuse normal request settings within the remaining discovery deadline.
**Notes:** Add no new retry constant.

---

## Shared-Sweep Fan-Out

### Slow and late subscribers

| Option | Description | Selected |
|--------|-------------|----------|
| Shared active log with per-subscriber cursor | Append once, read independently | ✓ |
| Unbounded queue per subscriber | Copy each record reference per caller | |
| Bounded subscriber queues | Disconnect callers that cannot keep up | |

**User's choice:** Shared active record log with per-subscriber cursors.
**Notes:** The producer never awaits consumers; the log exists only for the active sweep.

### Sharing scope

| Option | Description | Selected |
|--------|-------------|----------|
| True process-wide sharing | Share across event loops and threads | ✓ |
| Per-event-loop sharing | Different loops may start different sweeps | |
| Serialise cross-loop callers | Prevent overlap without sharing records | |

**User's choice:** True process-wide sharing.
**Notes:** The narrow bridge must be thread-safe; UDP discovery remains asyncio-based.

### Sweep ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy coordinator event-loop thread | Internal loop owns active sweeps | ✓ |
| First caller's loop | Other loops depend on that loop remaining alive | |
| Application-designated loop | Add public lifecycle/configuration | |

**User's choice:** Lazy coordinator event-loop thread.
**Notes:** Start on demand and stop when no active sweep or subscriber remains.

### Subscriber close

| Option | Description | Selected |
|--------|-------------|----------|
| Synchronous detachment acknowledgement | Last subscriber also awaits sweep/socket close | ✓ |
| Fire-and-forget detachment | Cleanup may still be pending | |
| Wait for whole sweep | Non-last callers are coupled to sweep completion | |

**User's choice:** Synchronous detachment acknowledgement.
**Notes:** Non-last close does not stop or wait for the sweep.

---

## Measurement Workflow

### Raw format

| Option | Description | Selected |
|--------|-------------|----------|
| Append-only JSONL plus derived summary | Immutable raw rows; regenerate summary | ✓ |
| One versioned JSON document | Rewrite the document when adding rounds | |
| pytest-benchmark JSON | Reuse benchmark comparison tooling | |

**User's choice:** Append-only JSONL plus derived summary.
**Notes:** Keep raw nanosecond timings and integer counts linked by scenario/pair identifiers.

### Invocation

| Option | Description | Selected |
|--------|-------------|----------|
| One script with explicit modes | `baseline-only`, `merged-only`, and `paired` | ✓ |
| Paired mode only | Cannot establish the pre-merge harness gate | |
| Pytest-only interface | CI-friendly but awkward for fleet operation | |

**User's choice:** One script with explicit modes.
**Notes:** Paired mode runs baseline then merged sequentially.

### Confounds

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit declaration and labelled result | Structured state; continue but mark confounded | ✓ |
| Refuse unless quiesced | Clean evidence only | |
| Optional free-text notes | No structured validation | |

**User's choice:** Require an explicit declaration and label the result.
**Notes:** Values are `quiesced`, `not_quiesced`, or `unknown`, plus categorical confounds.

### Per-device evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Stable privacy-safe aliases | Reconstruct overlap and source contribution | ✓ |
| Aggregate counts only | No independently reconstructable overlap | |
| Counts plus optional alias sidecar | Split correlation into a second artefact | |

**User's choice:** Stable privacy-safe aliases.
**Notes:** Resolve raw identifiers against the operator's external mapping; never write live values
or the mapping to the repository.

---

## Planner's Discretion

- Exact bounded liveness concurrency cap.
- Concrete stable diagnostic reason names.
- Internal coordinator and thread-safe bridge implementation details.
- Measurement filenames, JSONL field names, summary layout, and test placement.

## Deferred Ideas

None.
