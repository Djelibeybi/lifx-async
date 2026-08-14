---
phase: 06
phase_name: "generated-theme-library"
project: "lifx-async — Theme Library Update"
generated: "2026-08-15"
counts:
  decisions: 7
  lessons: 5
  patterns: 7
  surprises: 5
missing_artifacts: []
---

# Phase 06 Learnings: generated-theme-library

## Decisions

### Canonical palette order, not captured order (D-24)
The generator sorts every palette by its stored uint16 `(hue, saturation, brightness, kelvin)`
tuple — stable, duplicates preserved — before emission, and the sort is applied at generation
time rather than at read time.

**Rationale:** The LIFX app shuffles palette order on every application, so captured order is an
accident rather than data. Two positional consumers (`EffectRuleTrio`, `EffectSpin`) read
palettes by index, so an arbitrary order would have made their behaviour depend on capture
timing. Sorting canonically makes the order deterministic and reproducible, and the two
consumers' leading trio (`0/7282/10923` for `exciting`) is pinned by a literal test.
**Source:** 06-01-PLAN.md, 06-02-SUMMARY.md

### COMPAT-02 retired — the app is the source of truth, no legacy aliases
No `*_legacy` keys and no Legacy category. Pre-v1.2 palettes for resynced slugs live in git
history only.

**Rationale:** Measurement showed 10 of the 19 redefined themes shift by only one or two
colours. The operator ruled that carrying two palettes per name for that delta was not worth the
permanent API surface. The replacement criterion — no legacy-suffixed key exists anywhere in the
library — is pinned by a runtime sweep.
**Source:** ROADMAP.md amendment 2026-08-14, 06-CONTEXT.md, 06-02-PLAN.md must_haves

### Flat dict with alias keys binding the same record object (D-13, D-14)
`THEMES` is a single flat dict; rename aliases are bound as `THEMES["forest"] = THEMES["forrest"]`
rather than duplicated records, so an alias carries the target's identity triple.

**Rationale:** Identity binding makes the alias relationship provable (`THEMES[alias] is
THEMES[target]`) rather than merely equal, and removes any possibility of the two drifting on a
future regeneration.
**Source:** 06-01-PLAN.md, verified in 06-VERIFICATION.md truth 5

### Palette-only multiset equality, deliberately unhashable (D-19, D-20)
`Theme.__eq__` compares palettes as unordered `Counter` multisets over uint16-hashable HSBK;
identity fields and order are excluded. `Theme.__hash__` is `None`.

**Rationale:** Order is meaningless (see D-24), so equality must not depend on it. Unhashability
is deliberate: a mutable palette container with value equality would be unsafe as a dict key.
**Source:** 06-01-SUMMARY.md Task 2

### No drift gate between the data file and the generated module (D-23)
Nothing in CI verifies that `src/lifx/theme/data.py` matches the current `data/themes.jsonl`.

**Rationale:** Operator decision, taken knowingly. Idempotence is verified by hand at phase close
instead. Accepted consequence: a stale or partial regeneration would ship silently. Mitigating
factor recorded during the security review — the generator writes atomically, so a partial file
cannot land.
**Source:** 06-01-PLAN.md threat model T-06-04, 06-SECURITY.md R-06-01

### The 28 pre-v1.2 orphans ship unchanged under category `Library` (D-12)
Orphaned keys with no app counterpart are carried across at their exact pre-v1.2 palettes and
given the synthetic category `Library`.

**Rationale:** Keeps COMPAT-01 (no pre-v1.2 name breaks) satisfiable without inventing app data
for names the app does not have. Their disposition is Phase 7's problem, not this phase's.
**Source:** 06-02-SUMMARY.md Task 1, 06-VERIFICATION.md truth 8

### Fix code-review warnings inside the phase rather than deferring them
WR-01 (split-brain `_THEMES` lookup) and WR-03 (`mkstemp` 0600 permissions leaking onto the
shipped module) were fixed after verification passed, before the phase was marked complete.

**Rationale:** Both were introduced by this phase's own code, and `_THEMES` is the documented
Phase 7 extension point — leaving a half-migrated lookup for the phase that is about to build on
it would have handed Phase 7 a latent bug rather than a clean seam.
**Source:** 06-REVIEW.md WR-01/WR-03, commit `931796f`

---

## Lessons

### "Identical" is precision-dependent — say at which precision
The SPEC recorded 2 shared slugs as already-identical to pre-v1.2. At strict uint16 only
`kwanzaa` is; `exciting` drifts exactly 1 unit on three hues. The original classification came
from `analyse_themes.py::palette_key`, which rounds hue to 0.1 degree, and reproduces exactly at
that precision.

**Context:** The old hand-written table stored integer degrees that *round* to 43509/49334/53521;
the app itself sends 43508/49333/53520 — it truncates. Any future comparison against pre-v1.2
values is 1-ulp-sensitive for the same reason. Phase 8's fidelity work needs to know this before
it treats a 1-ulp delta as a hardware finding.
**Source:** 06-02-SUMMARY.md Finding 3, 06-VERIFICATION.md frontmatter override

### A mechanically-derived string can trip a spell-check hook
Stripping the non-ASCII curly apostrophe from the app's "What's the craic?" theme yields "Whats
the craic?", which codespell flags as a typo and which blocks the commit.

**Context:** The string reaches both `data/themes.jsonl` and the generated `data.py`, so
exempting only the data file would not have been enough. Resolved by adding `whats` to the
codespell ignore list. The general shape: a normalisation rule that is correct for the data can
produce output that a lint hook considers wrong, and the fix belongs in the hook config, not in
the data.
**Source:** 06-02-SUMMARY.md deviation 1

### A test can pin a coincidence rather than a behaviour
`test_love_equals_romance` passed for years because `love` and `romance` happened to share a
palette pre-v1.2. Resyncing `romance` to its app palette broke it, even though the behaviour
under test (palette-only equality) was unchanged.

**Context:** The replacement uses the app's measured genuinely-identical trio
(`memorial_day`/`independence`/`old_glory`) and asserts the same behaviour without pinning any
particular palette. A test whose premise is a data coincidence will break on any data resync and
tell you nothing when it does.
**Source:** 06-02-SUMMARY.md deviation 2

### TDD's RED gate does not apply to characterisation tasks
Task 3 of plan 06-02 pins behaviour that Task 2 of the same plan delivered. A failing-first run
was impossible without deleting Task 2's work.

**Context:** The task was declared `tdd="true"` in the plan, which was the wrong classification —
pinning/characterisation tasks are test-only by nature and exempt from the RED→GREEN sequence.
Worth catching at plan time rather than discovering at execution time.
**Source:** 06-02-SUMMARY.md deviation 4

### Migrating a lookup means migrating every reader
The cutover changed `get()` and `get_available_themes()` to read the module-global `THEMES` but
left `get_by_category()` reading `cls._THEMES`. All three worked, because `_THEMES is THEMES` —
the defect is invisible until someone rebinds the class attribute.

**Context:** `_THEMES` is documented as the Phase 7 extension point, so the split would have
surfaced as a `KeyError` from two of three methods precisely when it was first used as intended.
Found by the deep code review, not by any test, because no test subclasses the library.
**Source:** 06-REVIEW.md WR-01

---

## Patterns

### Tracer plan with a human feedback gate before expansion
Plan 06-01 built the full pipeline production-quality on four seed records and stopped at a
`type="tracer"` gate; plan 06-02 only expanded the record count and removed the fallback.

**When to use:** Any bulk data import or code-generation pipeline. A wrong record schema or a
broken emission format is caught after one commit rather than after the 166-record import, and
the gate gives a human a cheap look at the shape before volume hides it.
**Source:** 06-01-PLAN.md objective, 06-01-SUMMARY.md

### Every generated string reaches source only through `repr()`, after validation
Strings are validated first (non-empty, ASCII, `str`), then emitted exclusively via `!r`;
emit-time assertions back the validator so a hostile record cannot inject statements.

**When to use:** Any generator that turns data into executable code. The emitted module was
confirmed to contain zero backslash escapes, which is the observable signal that validation ran
before emission rather than `repr()` papering over bad input.
**Source:** 06-01-PLAN.md threat model T-06-01, 06-SECURITY.md, 06-REVIEW.md

### Cross-assert two independent derivations instead of trusting one
The conversion script derived each slug with `analyse_themes.py::slug()` (imported, not
re-implemented) and asserted per record that `generator.derive_slug(stored_name)` produced the
same key. All 138 agreed, including the eight punctuated names.

**When to use:** Whenever a rule is implemented in two places for two purposes. Agreement across
independent implementations is real evidence; re-implementing the rule inside the check is not.
**Source:** 06-02-SUMMARY.md Task 1

### Discriminate with multisets, never with lengths
The tracer's precedence check compares `Counter(as_tuple)` multisets — equal to the seed record
*and* unequal to the old table — rather than checking palette length.

**When to use:** Any "did the new source win?" assertion. A length check is vacuous whenever the
two candidates happen to share a length, which review found was the case here.
**Source:** 06-01-PLAN.md review finding 2, 06-01-SUMMARY.md

### Recover pre-change behaviour by executing git history
Verification recovered the deleted 366-line `_THEMES` table with `git show
3ab50ee~1:src/lifx/theme/library.py` and executed it, then compared live.

**When to use:** Verifying a compatibility guarantee after the old implementation has been
deleted. Comparing against history that you execute is stronger than comparing against a
transcription of it — and the transcription is exactly what drifted (see the 1-ulp lesson).
**Source:** 06-VERIFICATION.md truths 2, 4, 8

### Atomic generated-file write: unique temp → format in place → set mode → replace
`mkstemp` in the target directory (same filesystem), write, run the formatter over the temp file,
set the file mode, then `Path.replace()`. Temp file removed unconditionally on every failure path.

**When to use:** Any generator writing over a committed artifact. Two concurrent runs cannot race
on a shared temp path, an interrupted run leaves the committed file untouched, and the formatter
never sees a half-written target. Note the mode step — it was missing initially and shipped
0600 (see WR-03).
**Source:** 06-01-SUMMARY.md Task 3, 06-REVIEW.md WR-03

### Omit generated modules and their generator from coverage, in both configs
Both `pyproject.toml` `omit` and `codecov.yml` `ignore` list the generator and the generated
module, each exactly once, verified by `grep -c`.

**When to use:** Whenever adding generated code to a project with a coverage gate. The two
configs serve different gates (pytest-cov locally, Codecov's PR patch status in CI) and both must
be updated or the gate fails on code no one wrote.
**Source:** 06-01-SUMMARY.md Task 3

---

## Surprises

### A SPEC-level "verified identical" claim was wrong at wire precision
The SPEC and both plans stated that 2 shared slugs carried across without diff at uint16 multiset
precision. Only one does.

**Impact:** Required a documented override on an otherwise clean 16/16 verification. No code
changed — THEME-02 binds shipped == captured and prohibits inventing values — but it means the
phase shipped with one recorded, accepted deviation from its own written must_have, and Phase 8
inherits a known 1-ulp comparison hazard.
**Source:** 06-02-SUMMARY.md Finding 3, 06-VERIFICATION.md override

### 69 hardening tests exposed zero generator defects
Task 3 wrote 69 tests over `tmp_path` fixtures against every validation abort, ordering rule,
round-trip boundary and the interrupted-write path. `generator.py` needed no changes.

**Impact:** The plan's minimum was 14 tests; 69 were written and all passed first time. Either
the tracer gate had already flushed the defects out, or the validation was over-specified before
it was exercised. Cheap outcome either way, but it means the hardening pass bought regression
protection rather than bug discovery.
**Source:** 06-01-SUMMARY.md Task 3, deviations section ("None")

### The one unavoidable slug collision collapsed cleanly
`christmas` appears twice in the capture — HOLIDAYS (index 78) and ARCHIVES (index 133) — and was
the single collision that dropping the sport categories could not sidestep.

**Impact:** The two palettes proved uint16-multiset identical, so the ARCHIVES twin was simply
dropped after the identity proof. The collision guard, written to fail loudly and let the app
record win, recorded zero live instances. A risk carried through planning that cost nothing to
resolve.
**Source:** 06-02-SUMMARY.md Task 1, PROJECT.md key context

### The phase's own cutover was left half-migrated
Two of three lookup methods moved to the generated dict; the third kept reading the class
attribute.

**Impact:** Harmless today (`_THEMES is THEMES`) and invisible to the full 3326-test suite, but it
sits exactly on the seam Phase 7 was about to extend. Found only by the deep code review. Fixed
in `931796f` before the phase closed.
**Source:** 06-REVIEW.md WR-01

### A generated source file shipped owner-only
`tempfile.mkstemp()` creates `0600`, and `Path.replace()` preserves the temp file's mode, so every
regeneration left `src/lifx/theme/data.py` as `-rw-------`.

**Impact:** Not caught by any test, lint or type check — the file is perfectly importable for the
user who generated it, and git does not track read permissions, so it would never have shown up
in a diff. It would have surfaced as an import failure only for a consumer installing from a
wheel built on that tree. Fixed with a umask-honouring `chmod` before the rename.
**Source:** 06-REVIEW.md WR-03, commit `931796f`
