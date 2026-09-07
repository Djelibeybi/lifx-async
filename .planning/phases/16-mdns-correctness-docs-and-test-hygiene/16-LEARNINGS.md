---
phase: 16
phase_name: "mDNS Correctness, Docs and Test Hygiene"
project: "lifx-async"
generated: "2026-09-07"
counts:
  decisions: 12
  lessons: 9
  patterns: 8
  surprises: 7
missing_artifacts:
  - "16-UAT.md"
---

# Phase 16 Learnings: mDNS Correctness, Docs and Test Hygiene

## Decisions

### Split the public entry point rather than normalising in place

`selected_address_for()` became a thin public wrapper that normalises its owner through
`_normalise_dns_name()` and delegates to a private `_selected_address_for_normalised()` that
applies no normalisation of its own. Both internal callers invoke the private delegate directly
on a target already normalised once.

**Rationale:** the obvious one-line fix, `owner = _normalise_dns_name(owner)` at the top of the
public method, would have been actively worse than the bug. `_normalise_dns_name()` strips
exactly one trailing dot, so it is not idempotent, and both internal callers already pass a
normalised target. Double-normalising on the internal path would turn a currently-resolving
multi-trailing-dot name into a permanent pending-target miss, re-queried forever. The split
puts the normalisation contract at the signature instead of relying on every caller knowing it.
**Source:** 16-CONTEXT.md (D-01), 16-01-PLAN.md

### Left `_normalise_dns_name()` non-idempotent on purpose

Making the helper strip all trailing dots was considered and rejected.

**Rationale:** it is called on the ingest path and on every SRV target, so widening it changes
cache keying for every caller in order to fix a problem D-01 confines to one method. The cost
is a permanent residual, accepted knowingly: an owner with two or more trailing dots keys the
guard on one value while the lookup resolves another, so that target stays pending forever.
**Source:** 16-CONTEXT.md (D-02), recorded in `_normalise_dns_name()`'s own docstring

### Extracted one guard predicate instead of fixing the guard twice

The four fail-closed checks duplicated between `selected_address_for()` and `pending_targets()`
became a single `_owner_is_unusable()` predicate used by both.

**Rationale:** the duplication was the structural cause of the defect. Both methods assert the
same unusable-owner condition, and only one was updated when normalisation was introduced. One
predicate means the next guard added lands in both places without anyone remembering to.
**Source:** 16-CONTEXT.md (D-03), 16-01-SUMMARY.md

### Sweep first, enable the rule second, in two commits

The 166-import hoist across 27 files is one commit; enabling ruff `PLC0415` is a separate,
later commit.

**Rationale:** sweeping first means no commit in history has the rule enabled with violations
outstanding, so `ruff check .` is green at every commit and a bisect never lands on a red lint
state. Reversing the order would have produced a window of self-inflicted red.
**Source:** 16-CONTEXT.md (D-08), 16-04-PLAN.md

### Per-file-ignores over a narrower `select`, so each exclusion is a deletable handoff

`PLC0415` is enabled repository-wide with per-file-ignore entries, rather than selected on
`tests/` alone.

**Rationale:** every excluded path becomes a visible line with a named owning phase. Phase 18
deletes `tests/test_animation/**` and `tests/test_devices/test_multizone.py` when it sweeps its
files; Phase 19 deletes `tests/test_theme/**`. A narrower `select` would have made the same
exclusions invisible and unowned.
**Source:** 16-CONTEXT.md (D-05), 16-04-SUMMARY.md

### Dropped the offending sentence rather than rewording it

`Mesh scale is proven synthetically.` was removed outright from both `src/lifx/api.py` and
`docs/user-guide/discovery.md`, not replaced with a softer scale claim.

**Rationale:** the existing bounded-discovery paragraph already tells the caller what to
conclude. A replacement claim would be one more sentence to keep true.
**Source:** 16-CONTEXT.md (D-13), 16-02-SUMMARY.md

### Attributed request verification to `discover()`'s mDNS leg, not its UDP leg

The proxy-response prose names `discover()`'s mDNS candidates as the ones that must answer a
correlated device request before being yielded.

**Rationale:** D-14 as originally recorded said the UDP leg was unicast-verified, which is false
against the implementation. The UDP leg consumes `discover_devices_shared()` directly and
verifies nothing; only `_discover_verified_devices_mdns()` opens a connection and requires an
answer to a correlated `Light.GetColor` or `Device.EchoRequest`. The error was not a phrasing
detail: a caller told the UDP leg is verified would trust an unverified broadcast reply for
exactly the reachability judgement the prohibition exists to protect.
**Source:** 16-CONTEXT.md (D-14 amendment), 16-REVIEWS.md, 16-02-SUMMARY.md

### Named the derivation "the most recent correlated response", not "request outcome"

The new `AGENTS.md` caching category scopes `connectivity`'s derivation narrowly.

**Rationale:** `_thread_connection` is assigned only after correlation validation
(`connection.py:1075`), so a timeout, a connection failure and an uncorrelated reply are all
request outcomes that leave the value unchanged. The broader phrasing would have overstated
what a read tells you.
**Source:** 16-CONTEXT.md, 16-03-SUMMARY.md

### Split the DOCS-07 contract by the file each half asserts on

The `AGENTS.md` half joined `tests/test_repository_guidance.py`; the `advanced-usage.md` half
joined `tests/test_network/test_mdns/test_phase_contract.py`.

**Rationale:** each destination already owned assertions over its file. Putting both halves in
one place would have given one module a second file's concerns.
**Source:** 16-CONTEXT.md (D-09), 16-03-SUMMARY.md

### Gave the repository-wide prose contract its own module, in the default suite

`tests/test_docs_language.py` is new, walks every `.py` under `src/` and every `.md` under
`docs/`, and carries no opt-in marker.

**Rationale:** the file set is wider than any existing contract test's, and widening the
mDNS-scoped `test_phase_contract.py` into a repository walk would misplace it. It runs by
default because it guards published documentation that any pull request can regress;
deselecting it would let a docs regression reach `main` unchallenged. It also gives Phase 20's
em-dash sweep somewhere to land.
**Source:** 16-CONTEXT.md (D-10, D-11), 16-02-SUMMARY.md

### Locked approved phrases as short fragments, not full sentences

New entries in the approved-phrase list are short distinctive fragments.

**Rationale:** Phase 20 will recast em dashes across these same pages. Full-sentence locks would
all break; topic-keyword-only locks would be too weak to guarantee meaning.
**Source:** 16-CONTEXT.md (D-16)

### Removed a version skip rather than adding a suppression

`tests/test_packaging.py`'s `sys.version_info < (3, 11)` skip and its function-local
`import tomllib` were replaced by a module-scope `try: import tomllib / except
ModuleNotFoundError: import tomli as tomllib`.

**Rationale:** the sweep needed the import at module scope, and the two available moves were a
`noqa` or a compatibility import. `tomli` was already a dev dependency gated on
`python_full_version < '3.11'`, so the compatibility import cost nothing and moved in the
strengthening direction: the test now runs on Python 3.10 instead of skipping.
**Source:** 16-04-PLAN.md (Step 3a), 16-04-SUMMARY.md

---

## Lessons

### The bypass was reachable through public ingestion, not theoretical

`selected_address_for("")` and `selected_address_for(".")` both returned a cached address. The
root name and the empty string both normalise to the empty string, ingest keys a root-owner
address record under it, and no guard rejected it. A responder advertising a root-owner address
record could hand a caller a socket destination under a name identifying nothing.

**Context:** this was found during the cross-AI plan review, not during planning. It became
T-16-01b and the `not owner` first term of the shared predicate, and the test proves it
fail-closed by asserting the record is present in the cache while selection still returns
`None`.
**Source:** 16-REVIEWS.md, 16-01-PLAN.md

### A test asserting an empty result can pass for the wrong reason

A `pending_targets()` assertion that the list comes back empty proves nothing on its own,
because an earlier method exit produces the same empty list. Each new guard assertion needed a
paired control: the identical construction without the guard trigger must return the target.

**Context:** the plan review flagged control-probe vacuity across every lane. The fix was
branch-pinning with `rejection_counts` evidence alongside the paired control.
**Source:** 16-REVIEWS.md, 16-01-SUMMARY.md

### A gate that captures output without checking exit status reports success when its tool never ran

Reproduced live against this phase's own decisive sweep gate: with an unwritable `uv` cache,
ruff exits 2, prints nothing to stdout, and a gate reading only its output concludes zero
violations.

**Context:** found by the cross-AI plan review before execution, then re-proven by the security
auditor after it. Two rules now bind every gate in these plans: every ruff invocation asserts an
exact expected exit status, and no `test` deciding a gate sits mid-chain where a trailing
command discards its status.
**Source:** 16-REVIEWS.md, 16-04-PLAN.md (T-16-21), 16-SECURITY.md

### A floor is not a set comparison

An earlier draft of the "tests were not silently weakened" gate used a 2400-test floor. The tree
collects over 4200, so the gate would have accepted losing more than 1800 tests.

**Context:** replaced with a node-ID set comparison taken before and after the sweep, failing on
the first ID that disappears, and failing closed when the baseline is missing so skipping the
baseline is not a way past it. Measured: 4256 at the base, 4272 at HEAD, zero lost.
**Source:** 16-04-PLAN.md (T-16-16), 16-SECURITY.md

### `# noqa: PLC0415: <reason>` is silently invalid

The colon form suggested in this phase's own PATTERNS.md is rejected by ruff, which expects the
code to consist of uppercase letters followed by digits only, and leaves the violation
unsuppressed. The working form is `# noqa: PLC0415 - <reason>`.

**Context:** verified against the ruff pinned in this tree before the sweep. In the end no
retained import was needed, so no `noqa` was written, but the wrong form would have looked
correct in review.
**Source:** 16-04-PLAN.md (D-06 key_links)

### A prose helper that strips `#` lines silently exempts half the corpus

`_normalised_prose()` drops lines beginning with `#`. Reusing it for the repository-wide
contract would have exempted every Python comment under `src/` and every Markdown heading under
`docs/` from a contract meant to catch the phrase wherever it appears.

**Context:** `tests/test_docs_language.py` scans raw casefolded file text instead. The same
helper was avoided again in 16-03 for a different reason: its heading-stripping breaks a
positional region assertion.
**Source:** 16-02-SUMMARY.md, 16-03-SUMMARY.md

### Correcting one false attribution can leave a second one of the same shape

The plan corrected `discover()`'s docstring attribution. The executor then checked whether
`discover_mdns()`'s own docstring had the same problem, found that `discover_mdns()` calls the
unverified path, and named `discover()` explicitly rather than letting the sentence imply
`discover_mdns()` performs the verification.

**Context:** applying the correction one function further than the plan's literal text was the
same correctness bar the plan already required, not a scope expansion.
**Source:** 16-02-SUMMARY.md

### An `Edit` whose `old_string` under-matches can orphan a line into the wrong method

Inserting a new test method after an incomplete `old_string` match left a pre-existing assertion
line stranded after the new method, producing `NameError: name 'prose' is not defined`.

**Context:** caught by the immediately-following test run and restored before any commit. The
lesson is that the immediate targeted run after an insert is what catches this, not review.
**Source:** 16-03-SUMMARY.md

### A verify command can be unsatisfiable by the implementation its own plan mandates

`grep -qE "^[[:space:]]+import tomllib"` fires on any indented `import tomllib`, including the
module-scope `try:`/`except:` block the same plan's Step 3a requires, because `ruff format`
always expands a one-line `try:` onto an indented line.

**Context:** a plan-authoring bug rather than an implementation defect. Confirmed by inspection
that the import sits inside a top-level `try:` and by every other criterion in the same block
passing. Indentation alone cannot distinguish module-scope-inside-a-block from function-local.
**Source:** 16-04-SUMMARY.md

---

## Patterns

### Public/private normalisation split

A public wrapper normalises once and delegates to a private method that must not renormalise.

**When to use:** any time a normalisation helper is not idempotent and internal callers already
hold a normalised value. Encodes the contract at the signature instead of in every caller's
head.
**Source:** 16-01-SUMMARY.md (tech-stack.patterns)

### Shared fail-closed guard as one branch-free boolean expression

`_owner_is_unusable()` is a single `return (a or b or c or ...)`, not a chain of `if` statements.

**When to use:** wherever a guard set is asserted from more than one call site. It gives one
place for the next term to land, and an added term contributes no new branch to the
coverage-measured range, which matters under this project's 100% branch patch gate.
**Source:** 16-01-SUMMARY.md (tech-stack.patterns)

### Branch-pinning a guard test with a paired control

Assert the guard fires, and in the same test assert the identical construction without the
trigger returns the value, plus `rejection_counts` evidence naming the branch.

**When to use:** any test whose pass condition is an empty or `None` result, where an earlier
exit would produce the same observation.
**Source:** 16-01-SUMMARY.md (tech-stack.patterns)

### Node-ID set comparison as a test-weakening gate

Collect pytest node IDs before a mechanical change, collect again after, and fail on the first
ID present in the before set and absent from the after set.

**When to use:** any sweep that touches many test files mechanically. It is the only form that
catches a de-collected test; a count, a floor or a green suite all pass while tests vanish.
**Source:** 16-04-PLAN.md, 16-SECURITY.md

### Positive-and-negative control probes for a lint rule

Prove a configured rule fires on a real in-scope file with no `--select` flag on the command
line, and prove it is suppressed on each ignored path.

**When to use:** whenever a rule is added to a `select` list. Without the positive control a
vacuously configured rule satisfies `ruff check .` while enforcing nothing; without the negative
controls an ignore can leak into siblings. Same failure class as Phase 15's vacuous-coverage-gate
guard.
**Source:** 16-04-PLAN.md (T-16-17), 16-SECURITY.md

### Per-file-ignore as a named handoff line

Each excluded path is its own line, under a comment naming the phase that deletes it.

**When to use:** any staged rollout of a lint rule across a tree that several phases own. The
alternative, a narrower `select`, hides the same exclusions with no owner and no deletion
trigger.
**Source:** 16-04-SUMMARY.md (tech-stack.patterns)

### Count-based exactly-one assertion instead of membership

`len(matching_categories) == 1` rather than `connectivity in category`.

**When to use:** classification contracts where the point is that a thing has exactly one home.
Membership passes when the item is duplicated across two categories, which is the ambiguity the
requirement existed to remove.
**Source:** 16-03-SUMMARY.md (tech-stack.patterns)

### Module-scope try/except stdlib-with-backport import

`try: import tomllib / except ModuleNotFoundError: import tomli as tomllib` at module scope.

**When to use:** when a version skip guards a stdlib module that has a backport already in the
dev dependencies. Removes the skip and gains coverage on the older interpreter rather than
adding a lint suppression.
**Source:** 16-04-SUMMARY.md (tech-stack.patterns)

---

## Surprises

### The pre-sweep inventory matched the spec-locked figure exactly

166 violations across exactly 27 files, with zero delta despite plans 16-01 and 16-02 having
added test code to the tree first. 16-01's new test class and its two added imports introduced
no new `PLC0415` sites at all.

**Impact:** the wave-3 plan's spec-locked count survived two earlier waves editing files in its
own scope, so no renegotiation was needed.
**Source:** 16-04-SUMMARY.md

### Not one function-local import needed retention

The whole design around D-06's reason-bearing `noqa` convention, and D-07's careful bounding of
what a legitimate mark looks like, turned out to be unnecessary. All 166 sites were safely
hoistable; several were outright duplicates of an already-imported name and were deleted rather
than moved. Zero `noqa: PLC0415` marks exist under `tests/` afterwards.

**Impact:** the pattern was habit rather than constraint, exactly as the plan's premise argued
but more completely than it expected. The convention still stands for the phases that inherit
the excluded paths.
**Source:** 16-04-SUMMARY.md

### The wrong verification attribution survived into a locked decision

D-14 was recorded, reviewed and locked with a factually false clause naming `discover()`'s UDP
leg as unicast-verified. It took the cross-AI plan review to catch it, after the discussion
phase had already closed.

**Impact:** the correction added a fifth approved-phrase fragment and a whole negative
phrase-list, because the other four fragments locked the proxy topic without locking which leg
verifies.
**Source:** 16-REVIEWS.md, 16-CONTEXT.md (D-14 amendment)

### D-05's five per-file-ignore entries had to become seven

Measuring the rule rather than reasoning about it found two violations outside all five
enumerated paths, in a git-tracked archived spike harness duplicated under both
`.agents/skills/` and `.claude/skills/`. With five entries the acceptance criterion was
unsatisfiable as written.

**Impact:** two extra entries, on the same ground D-07 already permitted. The alternatives,
sweeping the archived probes into scope or adding a ruff `exclude` that would silence every rule
on those paths, were both declined.
**Source:** 16-CONTEXT.md (D-05 amendment)

### The whole-sweep budget control needed one record beyond the cap

Filling `_MAX_ADDRESS_RRS_PER_SWEEP` exactly never trips the exhaustion check, because the check
runs before the per-record counter increments, so the loop alone reaches the cap but never
exceeds it.

**Impact:** one extra filler record in the test, mirroring an existing recipe in the same file.
Worth knowing before writing any new budget-exhaustion test against this cache.
**Source:** 16-01-SUMMARY.md

### The stated privacy enforcement did not cover the files it was claimed for

Plan 16-01 named `test_discovery_surfaces_use_only_documentation_safe_addresses` as the
enforcement for fixture privacy. That test walks `docs/user-guide/discovery.md` and the
progressive example, not `tests/`. Four new fixture lines use `192.168.1.50` rather than the
`192.0.2.0/24` range the prohibition text names, following the file's own convention, which the
phase inherited at 61 occurrences and left at 65.

**Impact:** closed rather than opened as a threat, since RFC1918 space discloses no live
identifier, but the enforcement claim is the thing that needs correcting, not the fixtures.
Normalising four of sixty-five would leave the file inconsistent.
**Source:** 16-SECURITY.md (auditor note 1)

### `ruff check` exits 0 on a path that does not exist

It prints only a `warning: Failed to lint ...` line. A gate handed a wrong path reports green.

**Impact:** none in this phase, since every gate passes real paths. Recorded because it is the
same failure family as T-16-21 and will bite a future gate author who assumes a non-zero exit
on a bad path.
**Source:** 16-SECURITY.md (auditor note 4)
