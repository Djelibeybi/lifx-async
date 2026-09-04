# Phase 12: IPv6 Discovery Plumbing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-29
**Phase:** 12-ipv6-discovery-plumbing
**Areas discussed:** Windows execution breadth, IPv6 proof split, cancellation and cleanup
proof, evidence packaging

---

## Windows Execution Breadth

### CI shape

| Option | Description | Selected |
|--------|-------------|----------|
| One Windows/Python 3.10 matrix cell | Use the LedFx/Python floor in the existing matrix | ✓ |
| Every Windows matrix cell | Attempt on Python 3.10 through 3.14 | |
| Separate focused Windows job | Add a distinct job and duplicate setup | |

**User's choice:** One existing `windows-latest` / Python 3.10 matrix cell.

### Attempt visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Named focused step then normal suite | Make the attempt conspicuous without weakening the full job | ✓ |
| Normal full pytest invocation only | Let fixture gating make the test run inside the existing suite | |
| Replace the full suite | Run only the focused test in that cell | |

**User's choice:** Add a named focused step, then run the normal suite unchanged.

### Retry policy

| Option | Description | Selected |
|--------|-------------|----------|
| Strict, no retry | Treat loopback discovery as deterministic | |
| Existing Windows retry policy | Reuse the repository's current Windows flake handling | ✓ |
| Retry emulator start-up only | Keep discovery single-attempt while retrying the external boundary | |

**User's choice:** Use the existing Windows retry policy.

### Trigger policy

| Option | Description | Selected |
|--------|-------------|----------|
| Source/test pull requests only | Match the existing three-OS matrix policy | ✓ |
| Every pull request | Expand Windows to documentation and CI-only changes | |
| Source/test PRs plus manual runs | Add deliberate manual revalidation | |

**User's choice:** Source/test pull requests only.

---

## IPv6 Proof Split

### Real versus instrumented coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Real `::1`, instrument other forms | Keep one portable E2E path and instrument ULA/GUA/scoped forms | ✓ |
| Real IPv4 and `::1`, instrument others | Repeat both routable families at the proof boundary | |
| Real routes for every representation | Configure runner-specific IPv6 interfaces/routes | |

**User's choice:** One real `find_by_ip("::1")` path; instrument every other IPv6
representation.

### Real socket-family evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Spy on real `UdpTransport` | Preserve real traffic while observing actual family and bind | ✓ |
| Infer from `::1` success | Keep socket-family assertions in separate unit tests | |
| Add production diagnostics | Expose a callback or property for the discovery socket | |

**User's choice:** Use a test-only spy around the real transport.

### Representation entry point

| Option | Description | Selected |
|--------|-------------|----------|
| Public `find_by_ip()` | Prove validation, delegation, and family selection together | ✓ |
| `_discover_with_packet()` directly | Test only the private family-selection seam | |
| `wildcard_for()` only | Test the helper without its public consumer | |

**User's choice:** Call public `find_by_ip()` for every representation and instrument only
the transport boundary.

### Invalid-input socket proof

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-on-use transport sentinel | Fail immediately if transport construction/open occurs | ✓ |
| Patch `discover_devices()` | Assert public delegation never begins | |
| Validator tests only | Rely on existing helper coverage | |

**User's choice:** Use a fail-on-use transport sentinel for empty, malformed, and bare
link-local inputs.

---

## Cancellation and Cleanup Proof

### Lifecycle-test shape

| Option | Description | Selected |
|--------|-------------|----------|
| Instrumented cancellation then real success | Stall deterministically, assert close, then use real `::1` | ✓ |
| Real emulator delay/drop | Create and cancel a timing-sensitive real lookup | |
| Entirely instrumented | Keep both cancellation and reuse off the network | |

**User's choice:** Deterministically stall and cancel the first lookup, then perform a
fresh real `::1` lookup.

### Cancellation trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit open-and-blocked signal | Cancel only after endpoint acquisition and blocked receive | ✓ |
| Fixed sleep | Guess when the desired state has been reached | |
| Immediate cancellation | Exercise pre-start cancellation only | |

**User's choice:** Wait for an explicit endpoint-open and receive-blocked signal.

### Closure evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Observe real endpoint state | Assert close completes and endpoint reports closing/closed | ✓ |
| Rebind the ephemeral port | Use an OS-level port-release assertion | |
| Spy call count only | Assert `close()` was called once | |

**User's choice:** Observe the recorded real endpoint after transport close completes.

### Test separation

| Option | Description | Selected |
|--------|-------------|----------|
| Separate concurrency and cancellation tests | Keep failures focused and diagnosable | ✓ |
| One combined test | Cancel one of two lookups, finish another, then run a third | |
| Transport identities only | Omit concurrent successful completion | |

**User's choice:** Separate concurrent-independence and cancellation-recovery tests.

---

## Evidence Packaging

### Successful-path evidence and AC9 interpretation

| Option | Description | Selected |
|--------|-------------|----------|
| Committed verification attestation | Record job/test details in the phase | |
| Verification plus JUnit artefact | Keep a durable note and expiring raw report | |
| JUnit artefact only | Rely on the uploaded report | |
| Passing CI only; operator-controlled escape hatch | Green CI is sufficient; only the operator can drop Windows | ✓ |

**User's choice:** Passing CI is sufficient. The user clarified that AC9's escape hatch is
exercised only if CI remains red and the user explicitly decides to drop Windows. That
decision is the complete justification; no external-cause proof or SPEC amendment is
required.

### Escape-hatch record

| Option | Description | Selected |
|--------|-------------|----------|
| Verification with job link | Predesign a specific phase record | |
| Verification without link | Record only the decision | |
| Context/discussion record | Use this phase's planning artefacts | |
| Most convenient record at decision time | Choose the efficient durable location then | ✓ |

**User's choice:** Use whatever method is most convenient and efficient when the decision
is made; do not predesign a special artefact.

### Focused JUnit artefact

| Option | Description | Selected |
|--------|-------------|----------|
| No extra artefact | Use the named step and ordinary CI logs | ✓ |
| Upload on failure only | Add conditional diagnostic retention | |
| Always upload | Retain a report for every run | |

**User's choice:** No separate JUnit artefact.

### Retry outcome

| Option | Description | Selected |
|--------|-------------|----------|
| Final pass is passing CI | Treat retries as part of the selected policy | ✓ |
| Pass with verification note | Record that a retry occurred | |
| First failure remains unresolved | Reject a later passing attempt | |

**User's choice:** A pass after an existing retry is passing CI with no additional record.

---

## Planner's Discretion

- Exact test file placement and helper class names.
- Exact CI step and environment-variable names.
- The record used if the operator later exercises the AC9 escape hatch.

## Deferred Ideas

None — discussion stayed within the Phase 12 boundary.
