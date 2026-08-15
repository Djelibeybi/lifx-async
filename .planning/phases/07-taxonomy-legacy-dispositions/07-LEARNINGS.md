---
phase: 7
phase_name: "Taxonomy & Legacy Dispositions"
project: "lifx-async — Theme Library Update"
generated: "2026-08-15"
counts:
  decisions: 8
  lessons: 7
  patterns: 6
  surprises: 5
missing_artifacts: []
---

# Phase 7 Learnings: Taxonomy & Legacy Dispositions

## Decisions

### Legacy category names live as a private tagged-tuple shim, not as taxonomy
The 6 pre-migration category names ship as `_LEGACY_CATEGORIES`, a module-level dict mapping
each name to `(replacement_category, resolves)`. `holiday` and `mood` carry `True` and return
the replacement's themes; `seasonal`, `ambient`, `functional` and `atmosphere` carry `False`
and raise, using the stored replacement only to name it in the error.

**Rationale:** A `False` entry still needs a replacement so the raising branch can point
somewhere useful — one dict serves both fates without a second structure. Underscore-prefixed
and unexported so it reads as a migration shim rather than part of the taxonomy.
**Source:** 07-CONTEXT.md D-01/D-02/D-03, 07-02-SUMMARY.md

---

### `derive_slug()` moved into the package as a leaf module
Category matching normalises both sides through one shared rule at `src/lifx/theme/slug.py`,
imported by both the library and the out-of-wheel generator. The tests assert the two are the
same object, not merely equivalent.

**Rationale:** Two implementations of a normalisation rule drift silently. The identity
assertion makes divergence a test failure rather than a support ticket. Kept as a leaf (only
import: `re`) so it cannot participate in an import cycle.
**Source:** 07-CONTEXT.md D-04, 07-02-SUMMARY.md

---

### `derive_slug()` placement survived a review challenge on corrected premises
Cross-AI review flagged the placement as creating a regeneration bootstrap cycle. Investigation
showed the cycle predates this phase — `src/lifx/__init__.py` eagerly imports `lifx.theme`, so
the generator's `lifx.color` import already loads `data.py`. Placement stands; recovery for a
broken `data.py` is git.

**Rationale:** The finding described a real property of the codebase but misattributed its
cause to this phase. Correcting the premise mattered more than acting on the recommendation.
**Source:** 07-02-SUMMARY.md (review F2), 07-REVIEWS.md

---

### `disposition` is required on all records; `replaced_by` is `str | None`
Every one of the 166 records carries a disposition from a closed three-value set. `replaced_by`
is `None` unless the disposition is `deprecated` — never an empty string, so "absent" has one
representation.

**Rationale:** A required field with a closed value set makes an omission a generation failure
rather than a silent default. One representation of absence removes a class of comparison bug.
**Source:** 07-CONTEXT.md D-05/D-06, 07-01-SUMMARY.md

---

### R2-05 deferral held — the generator does not enforce SPEC R5
The generator does not reject a `replaced_by` on a non-deprecated record. Enforcement is the
library-side shape sweep at test time, which CI runs before ship.

**Rationale:** Deliberate scope decision with the trade-off understood, taken by the operator.
Reversible as a one-line addition inside the existing replacement validation plus one
failing-record test. Recorded as accepted risk R-07-05 with its compensating control named.
**Source:** 07-01-SUMMARY.md, 07-REVIEWS.md R2-05, 07-SECURITY.md

---

### Emit-time backstops check canonical form, not resolution
The emit-time backstop re-asserts that `replaced_by` is a canonical key, but not that it
resolves to a real record. Resolution is the cross-record pass's job.

**Rationale:** Resolution needs whole-set knowledge the per-record backstops deliberately do
not rebuild. Duplicating it at emit time would mean maintaining a second copy of `seen_keys`.
**Source:** 07-01-SUMMARY.md (F3)

---

### The migration page is a dated record, never resynced
The page is stamped with an "As of the … migration" admonition stating outright that it is not
maintained. `get_categories()` is the answer for current data.

**Rationale:** A migration page that tries to stay current becomes wrong silently. One that
declares its own staleness stays useful indefinitely.
**Source:** 07-CONTEXT.md D-10, 07-03-SUMMARY.md

---

### User-facing docs identify releases by release version, never by milestone number
The migration page, its filename, the prose and the `get_by_category()` `ValueError` all name
the lifx-async release. The internal `.planning/` milestone number never appears in shipped
output.

**Rationale:** `v1.2` is this repository's planning vocabulary. To a reader on PyPI it names
nothing. Raised by the operator during UAT as gap G-07-1.
**Source:** 07-UAT.md G-07-1, STATE.md Decisions

---

## Lessons

### Deriving a release version from an unfetched checkout produces a confident wrong answer
The fix for G-07-1 first labelled the work 6.3.0, computed from `git tag` (latest: v6.2.0) and
`pyproject.toml` (6.2.0). Both were stale. `origin/main` already carried `ca52da5` "6.3.0" and
tag `v6.3.0` — Phase 6's own release from PR #196 — so the corrected label pointed at a release
that predated the work. The same defect the gap was raised to fix, with a different number.

**Context:** Caught at ship preflight, when `git fetch` ran for the first time in the session.
The check that produced the wrong answer looked authoritative: two independent sources agreeing.
They were the same stale source read twice. **Fetch before deriving anything from tags or
`pyproject.toml`; rebase so the version is readable from the tree rather than remembered.**
**Source:** 07-UAT.md (version_correction), 07-VERIFICATION.md addendum

---

### A config toggle absent from config.json is not a disabled toggle
Both `workflow.security_enforcement` and `workflow.api_coverage_gate` are absent from
`.planning/config.json`, and both resolve `true` — they default on. Reading the file and seeing
nothing led to the wrong conclusion that the gates were off.

**Context:** The security gate was genuinely active, meaning verify-work should have dispatched
`/gsd-secure-phase` before offering transition. Nothing advanced on the bad reading because the
transition was still waiting on operator approval, but the margin was luck. **Resolve a toggle
with `config-get`, never by grepping the config file.**
**Source:** verify-work and secure-phase runs, 2026-08-15

---

### `render-hooks` lists registered hooks, not enabled ones
The `activeHooks` array includes entries whose `when` condition has not been evaluated against
config. Treating membership in that array as "this gate is on" is wrong in both directions.

**Context:** Surfaced when the `api-coverage.verify-pre` gate appeared in `activeHooks` and
returned `block: true` on a phase with no external API. **Read the hook's `when` key and resolve
it separately.**
**Source:** verify-work run, 2026-08-15

---

### The staleness resolver punishes correcting a summary after verification
Editing two SUMMARY files during the transition made them newer than `07-VERIFICATION.md`,
flipping the phase from `passed` to `stale` and blocking the completion predicate — despite
nothing about the verified behaviour changing.

**Context:** This is open-gsd/gsd-core#2348, already documented in STATE.md Blockers from the
v1.1 close, and it bit again in the same way. The remedy on record is to refresh the
VERIFICATION file *after* the last summary edit, with real content, never by touching mtimes.
**Source:** STATE.md Blockers, 07-VERIFICATION.md addendum

---

### A UAT test can pass while the thing being read is defective
Test 1 asked whether the `Library` category is correctly attributed. It was, at every site. The
operator's response was nonetheless an issue — the same files carried an unrelated defect, the
`v1.2` label, visible while reading for the attribution check.

**Context:** Recording the response as a plain failure of test 1 would have lost the fact that
the attribution wording verified clean. The test kept a `history:` of both verdicts and the gap
carried its own truth statement rather than inheriting the test's. **A tester reading a file
sees everything in it, not only what the test asked about.**
**Source:** 07-UAT.md test 1

---

### A summary can describe a control accurately and its mechanism wrongly
`07-02-SUMMARY.md` claimed "the Phase 6 no-network AST assertion still passes". No such
assertion exists in the test suite — Phase 6's no-network finding was a review-time inspection
recorded at `06-SECURITY.md:71`.

**Context:** Found during the Phase 7 security audit, which verified the underlying control
directly (every theme-layer import is stdlib or intra-`lifx`) rather than trusting the summary's
description of it. The control was real; only the named mechanism was invented. **Verify the
control, not the sentence describing it.**
**Source:** 07-SECURITY.md (Discrepancy found), 07-02-SUMMARY.md

---

### Two review findings were acceptance criteria that could not pass as written
Round 2 of cross-AI review found the no-network criterion (07-01-PLAN.md:231) would fail on a
correct tree — its grep exclusion missed the `pkivolowitz/lifx` attribution URL — and that the
idempotence check compared against git rather than against the previous generation.

**Context:** Both were reproduced against the live tree before being accepted. An acceptance
criterion that fails on correct work is worse than a missing one: it trains the executor to
override the gate.
**Source:** 07-REVIEWS.md R2-01, R2-02

---

## Patterns

### Cross-record validation as a second pass after `seen_keys` is complete
Validate per-record invariants in the main loop; validate anything needing whole-set knowledge
(does this `replaced_by` resolve?) in a second iteration once every slug and alias is known.

**When to use:** Any generator validating references between records in a single input file.
Attempting resolution in the first pass forces either ordering constraints on the data or a
partial-knowledge check that misses forward references.
**Source:** 07-01-SUMMARY.md

---

### Shape sweeps, never count pins
`TestDispositionSurfacing` asserts invariants over every record — every disposition is in the
allowed set, every non-deprecated record has `replaced_by is None`, every `replaced_by` resolves
— without pinning the 138/19/9 split.

**When to use:** Whenever the data is expected to change on resync but its shape is not. A count
pin turns every legitimate data update into a spurious test failure; a shape sweep survives the
update and still catches a corrupt one.
**Source:** 07-01-SUMMARY.md, 07-CONTEXT.md D-08/D-23

---

### Shared-rule leaf module inside the package, imported by an out-of-wheel generator
Put the shared rule in the package as a module with minimal imports; have the generator import
it rather than reimplement it; assert identity in the tests.

**When to use:** Whenever a build-time tool and the shipped library must agree on a rule.
Precedent in this codebase: `lifx/geometry.py` for the tile-position constants.
**Source:** 07-02-SUMMARY.md

---

### Verify doc claims by executing them, not by reading them
Every statement class in the migration page's After block runs against the shipped library:
`get_categories()`, `get_by_category('Holidays')` non-empty, `get('fire').disposition ==
'deprecated'` and `.replaced_by == 'warm_ember'`, and all four retired names raising with the
documented replacement.

**When to use:** Any documentation page whose body is code. Cheap to run, and it converts a
class of doc rot into a failing check. It caught nothing here — and re-ran clean after the
version rename, which is exactly its value.
**Source:** 07-03-SUMMARY.md DOC2, 07-SECURITY.md T-07-07

---

### Attribution in the table, not only in the prose
The migration page's category table carries a third `Defined by` column (LIFX app / This
library) so the `Library` attribution is structural, not a sentence someone has to reach.

**When to use:** When a prohibition is about how something is presented. Prose can be skimmed
past; a column cannot. The name and count cells stayed adjacent so the row-level verify regex
still matched.
**Source:** 07-03-SUMMARY.md

---

### Fix the small gap inline; reserve gap-closure planning for real work
G-07-1 was diagnosed fully during UAT (root cause, artifact list, fix set, operator decision),
so it was fixed directly rather than routed through planner + plan-checker + `--gaps-only`
execution.

**When to use:** When the diagnosis is complete and the fix is mechanical. The workflow's
default is a formal plan; that overhead earns its keep on ambiguous defects, not on a rename
with a locked decision. Record the deviation and the reason.
**Source:** 07-UAT.md G-07-1 (`resolved_by`)

---

## Surprises

### The version fix was wrong twice, for the same underlying reason
The defect was an internal label in shipped docs. The first correction substituted a version
that had already shipped. Both errors trace to deriving a version without fetching.

**Impact:** Two correction commits (`db1ae95`, `811cfcb`) where one should have sufficed, and a
ship halted at preflight. Caught before anything was pushed. The lesson is now recorded in
STATE.md Decisions so it outlives this phase.
**Source:** 07-UAT.md version_correction, 07-VERIFICATION.md addendum

---

### Every plan estimate overshot by an order of magnitude
| Plan | Estimated | Actual | Ratio |
|---|---:|---:|---:|
| 07-01 | 62,000 | 74,000 | 1.19× |
| 07-02 | 48,000 | 5,100 | 0.11× |
| 07-03 | 30,000 | 3,500 | 0.12× |

**Impact:** 07-01 ran slightly over; the other two came in at roughly a tenth of estimate. All
three were logged `confidence: low`, which was honest. The taxonomy rewrite and the docs page
were both largely mechanical once the disposition schema existed — the dependency did the work
the estimates were pricing.
**Source:** 07-0{1,2,3}-PLAN.md `estimate`, 07-0{1,2,3}-SUMMARY.md `actuals`

---

### "30 orphaned library keys" was never 30
ROADMAP SC3 and REQUIREMENTS COMPAT-04 both say 30. The measured, SPEC-locked count is 28 —
166 records minus 138 app records. The extra 2 were the rename aliases Phase 6 had already
wired.

**Impact:** No functional consequence; verification checked against 28 per SPEC/CONTEXT and
recorded the drift as informational. A count in a requirement that nobody re-derives ages into
a wrong number.
**Source:** 07-VERIFICATION.md Gaps Summary

---

### Half of a success criterion's example list named things that were never categories
ROADMAP SC2 illustrated legacy category names as `(seasonal, hygge, tranquil, sports, …)`.
Extracted from `main:library.py`, the accepted set was exactly six: `seasonal`, `holiday`,
`mood`, `ambient`, `functional`, `atmosphere`. `hygge`, `tranquil` and `sports` are theme
*keys*, and all three still resolve.

**Impact:** None to the work — all six real names got verified fates and all three keys still
resolve — but a criterion listing non-existent inputs could have sent an executor hunting for
category handling that never existed.
**Source:** 07-VERIFICATION.md Gaps Summary

---

### `Archives` is the app's largest category by a factor of four
60 of the 166 themes sit in `Archives` — more than Holidays (15), Music (14) and Moods (13)
combined. The contents are almost entirely date-pegged: roughly 20 Halloween themes, 10
Christmas, 6 St Patrick's, plus Thanksgiving, Hanukkah, Independence Day and remembrance sets.

**Impact:** None on the implementation, which copies the app's grouping verbatim. Worth knowing
for Phase 9 resync: `Archives` is where the app parks past seasonal drops, so it grows every
year while `Holidays` holds only what is currently featured. A resync that assumes stable
category sizes will be surprised.
**Source:** data/themes.jsonl, operator question during UAT
