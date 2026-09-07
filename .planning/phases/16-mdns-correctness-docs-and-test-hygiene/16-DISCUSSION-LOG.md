# Phase 16: mDNS Correctness, Docs and Test Hygiene - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-09-07
**Phase:** 16-mdns-correctness-docs-and-test-hygiene
**Areas discussed:** Import-sweep enforcement, Normalisation placement, Contract-test
placement, Replacement prose

---

## Import-sweep enforcement

### Q1: How should module-scope imports be enforced after the sweep?

| Option | Description | Selected |
|--------|-------------|----------|
| PLC0415 + per-file-ignores | Add PLC0415 to ruff's select, per-file-ignores for `src/**`, `.planning/**` and the three Phase 18/19 paths. Phases 18 and 19 delete their own entry when they sweep. | ✓ |
| Contract test, no ruff config | A test in the `test_phase_contract.py` idiom asserting zero PLC0415 violations under the swept paths. | |
| Manual sweep only | Fix the 166 and rely on review. | |
| PLC0415 on tests/ only | Scope the rule to `tests/` with `src/` and `.planning/` outside the select entirely. | |

**Notes:** Grounded in measured data. Ruff reports 322 violations repository-wide: 82 in
`src/` (mostly legitimate circular-import breakers), 49 in `.planning/`, 23 in Phase 18/19
files this phase must not edit. A repository-wide enable was therefore not available.

### Q2: What marks the demonstrated reason for a retained function-local import?

| Option | Description | Selected |
|--------|-------------|----------|
| noqa with inline reason | `# noqa: PLC0415` plus a named circular-import or patching reason. Machine-checkable and greppable. | ✓ |
| Plain comment above | A comment naming the constraint, no noqa. | |
| None retained | Prove all 166 can move, so no exemption mechanism is needed. | |

### Q3: How should the SPEC P6 boundary be stated for verify-phase?

| Option | Description | Selected |
|--------|-------------|----------|
| Reason-bearing noqa is legitimate | P6 forbids a bare noqa or an ignore covering an in-scope file. A reason-bearing noqa and an ignore covering a forbidden-to-edit path are permitted and enumerable. | ✓ |
| Cap the count | Same distinction plus a hard numeric cap, exceeding it becomes a checkpoint. | |
| Enumerate at plan time | Planner must list every intended noqa and ignore before execution. | |

**Notes:** Raised because the Q1 and Q2 answers both use mechanisms P6 forbids on a literal
reading. The distinction is purpose: scoping a rule and documenting a proven constraint,
versus hiding a violation in a file that is in scope.

### Q4: How should the 27-file sweep be committed?

| Option | Description | Selected |
|--------|-------------|----------|
| One commit per test directory | Six or seven commits, bisect lands on a directory. | |
| Two commits: mdns, then rest | Splits along the requirement boundary: 58 for #217's literal wording, 108 for the widened scope. | |
| One commit for the sweep | Single mechanical change plus a separate config commit. | ✓ |
| You decide | Leave granularity to the planner. | |

---

## Normalisation placement

### Q1: Where should owner normalisation live, given the internal callers already normalise?

| Option | Description | Selected |
|--------|-------------|----------|
| Public normalises, private does not | Public wrapper normalises and delegates to a private method taking a normalised owner; the two internal call sites use the private one. | ✓ |
| Make the helper idempotent | Change `_normalise_dns_name` to strip all trailing dots so double normalisation is safe. | |
| One-line fix, document the gap | Add the call and record that multi-trailing-dot names differ on the internal path. | |

**Notes:** The option set was rewritten mid-discussion after finding that
`_normalise_dns_name()` strips exactly one trailing dot and is therefore not idempotent,
and that both internal callers pass a target already normalised at `discovery.py:659`. The
naive one-line fix would have introduced a permanent pending-target miss for a
multi-trailing-dot name.

### Q2: Should the duplicated guard checks be deduplicated?

| Option | Description | Selected |
|--------|-------------|----------|
| Extract a shared predicate | One private predicate used by `selected_address_for()` and `pending_targets()`. | ✓ |
| Leave the duplication | Fix normalisation only, let the invariant test catch future drift. | |
| Extract, and cover with the invariant test | Both, with the owner-form matrix also driving `pending_targets()`. | |

### Q3: Does the invariant test reach the private helpers?

| Option | Description | Selected |
|--------|-------------|----------|
| Public lookups only | Drive the three public lookups across the four owner forms. Refactor-tolerant. | ✓ |
| Public plus pending_targets | Also drive `pending_targets()` across the owner forms. | |
| Include the private predicate | Test `_owner_is_unusable` directly. | |

**Notes:** Combined with the Q2 answer this leaves a residual: the extraction's equivalence
for `pending_targets()` rests on existing coverage rather than a new assertion. Recorded in
CONTEXT.md as a planner check, and in Deferred Ideas as the cheap close.

### Q4: How is the Phase 17 handoff recorded?

| Option | Description | Selected |
|--------|-------------|----------|
| Note in CONTEXT.md for Phase 17 | Record the behavioural change without touching the probe. | ✓ |
| Note plus a MDNS-10 requirement check | Also flag that MDNS-10 verifies against the fixed cache. | |
| No note needed | The probe passes already-normalised targets, so nothing changes. | |

---

## Contract-test placement

### Q1: Where does DOCS-07's assertion go?

| Option | Description | Selected |
|--------|-------------|----------|
| Split by file owner | AGENTS.md half to `test_repository_guidance.py`, advanced-usage.md half to `test_phase_contract.py`, each joining the file that already owns those assertions. | ✓ |
| Both in test_repository_guidance.py | One class, but that file starts asserting on `docs/` pages. | |
| Both in test_phase_contract.py | Beside DOCS-08, but connectivity is a device property in an mDNS-scoped file. | |

### Q2: Where does DOCS-08's repository-wide negative live?

| Option | Description | Selected |
|--------|-------------|----------|
| test_phase_contract.py | Beside the phrase lists it guards; widens that file's scope to a repository walk. | |
| test_repository_guidance.py | Treat it as a repository-wide guidance rule. | |
| A new tests/test_docs_language.py | Dedicated home for repository-wide prose prohibitions, which Phase 20's em-dash sweep also needs. | ✓ |

### Q3: What does the new module's walk cover?

| Option | Description | Selected |
|--------|-------------|----------|
| All of src/ and docs/, changelog excluded | Every `.py` under `src/` and `.md` under `docs/`, with `docs/changelog.md` excluded by name. Satisfies P7 structurally. | ✓ |
| Prose only, reusing _normalised_prose | Same walk with comments and headings stripped. | |
| docs/ only | Leaves `src/` docstrings to the phrase lists. | |

### Q4: Plain module or opt-in tooling marker?

| Option | Description | Selected |
|--------|-------------|----------|
| Plain module, runs by default | Guards published documentation, which every PR can regress. | ✓ |
| Marked tooling, opt-in | Faster default runs, but a docs regression reaches main unchallenged. | |

---

## Replacement prose

### Q1: What replaces "mesh scale is proven synthetically"?

| Option | Description | Selected |
|--------|-------------|----------|
| State the caller consequence | A partial result within the timeout means treat a short call as inconclusive, not as a device count. | |
| State consequence plus the bound | The same, plus the 64-target follow-up bound and the deadline-limited assembly. | |
| Drop the claim entirely | Remove the sentence; the existing bounded-discovery paragraph already carries the meaning. | ✓ |

**Notes:** Choosing this forced a follow-up, since SPEC R3's acceptance requires
`discovery.md` to name all three topics and dropping the sentence left testing limitations
without an owner.

### Q2: What does the guide say about proxy responses?

| Option | Description | Selected |
|--------|-------------|----------|
| Advertisement is not liveness | A border router advertises every mesh device, so a result proves an advertisement exists, not reachability. | |
| Liveness plus the fallback | The same, plus confirm with a request or with `discover()`, whose UDP leg is unicast-verified. | ✓ |
| Liveness, fallback, and no source attribution | Both, plus why a proxied instance without address records stays pending. | |

**Notes:** The source-attribution reasoning at `discovery.py:782` stays a code comment.

### Q3: What carries the testing-limitations topic?

| Option | Description | Selected |
|--------|-------------|----------|
| The existing fleet-specific paragraph | Designate the Phase 14 fleet-specific paragraph and assert on it. No new prose. | |
| Recast as a caller-facing limitation | Behaviour on a large or congested network is not characterised, so do not size timeouts or retry policy from these docs. | ✓ |
| Reinterpret the requirement | Collapse three topics to two surfaces and amend SPEC R3. | |

### Q4: What granularity for the approved-phrase entries?

| Option | Description | Selected |
|--------|-------------|----------|
| Short distinctive fragments | Matches the existing style and survives Phase 20's recast. | ✓ |
| Full sentences | Stronger meaning guarantee, but Phase 20 would break every entry. | |
| Topic keywords only | Most recast-tolerant, weakest guarantee. | |

---

## Claude's Discretion

- Exact wording of every replacement sentence, bounded by D-13 through D-16 and SPEC
  prohibitions P3, P4 and P5.
- Names of the private delegate method and the extracted guard predicate.
- Name and position of the third `AGENTS.md` caching category.
- Internal structure of `tests/test_docs_language.py`.
- Whether the `api.py` docstring restates the limitations or links to the guide.
- Commit ordering, subject to the one-commit sweep and the simultaneous phrase-list move.

## Deferred Ideas

- Phase 17 handoff: MDNS-10 must be planned against the post-fix cache.
- `src/` import sweep: 82 violations remain per-file-ignored.
- `.planning/` import sweep: 49 violations remain per-file-ignored.
- Phase 20 extends `tests/test_docs_language.py` rather than creating another module.
- `pending_targets()` owner-form coverage: the D-04 residual.
- Refreshing `.planning/codebase/` maps, which are three months stale and contradict
  Phase 15's delivered mechanisms.

## Corrections Made During Discussion

- `16-SPEC.md` import counts were wrong. The spec-phase grep counted docstring prose lines
  as imports. Ruff's `PLC0415` is authoritative: 166 in scope across 27 files, not 183
  across 28. SPEC.md was amended and requirement 4's acceptance criterion is now a ruff
  invocation rather than a hand-counted total.
