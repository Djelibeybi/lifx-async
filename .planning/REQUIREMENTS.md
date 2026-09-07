# Requirements: lifx-async v2.1 Spring Cleaning

**Defined:** 2026-09-05
**Core Value:** Commands stick, devices are found (over WiFi or Thread, transparently),
streaming never starves control traffic, and a theme by name looks like the theme of that
name in the LIFX app.

**Milestone goal:** Clear every accumulated small item so nothing carried forward is left
unaddressed: all 11 open GitHub issues, both dormant seeds, the repo-wide em dash style
debt, and the one unclosed deferred item from v2.0 Phase 13.

REQ-IDs continue from the existing numbering (`MDNS-08`, `DISC-03`, `ANIM-04`, `THEME-04`,
`DOCS-06` were the previous high-water marks). `EFFECT`, `TEST` and `CI` are new
categories.

## v2.1 Requirements

### mDNS Correctness

- [x] **MDNS-09**: `selected_address_for()` normalises owner names through the same
      DNS-name normalisation helper used to build the cached owner sets, so an owner
      supplied with a trailing dot cannot bypass the fail-closed unusable-address check.
      Covered by a regression test.
      ([#213](https://github.com/Djelibeybi/lifx-async/issues/213), PR #211 finding 11)
- [ ] **MDNS-10**: The IPv6 Thread probe distinguishes an instance with no address data
      from one holding a cached but unusable unscoped link-local AAAA record; the
      `linklocal_chosen` summary counter and its warning are made truthful and reachable
      or removed; the TXT assertion is replaced with defensive diagnostic handling so a
      partially assembled instance cannot terminate diagnostics. Synthetic identifiers and
      non-live addresses only.
      ([#212](https://github.com/Djelibeybi/lifx-async/issues/212), PR #211 finding 10)

### Discovery

- [ ] **DISC-04**: Advertisement staleness is measured against a WiFi bulb using the same
      protocol THREAD-04 used on Thread, so the 69s Thread disappearance-to-expiry figure
      has a control and the library can say whether that number is Thread-specific or a
      general mDNS TTL/goodbye artefact.
      (SEED-002, planted 2026-09-04)

### Animation

- [ ] **ANIM-05**: `Animator` refuses, or clearly degrades, when asked to drive a Thread
      device. `Animator.for_light()` / `for_multizone()` / `for_matrix()` currently build
      against any device reaching the required protocol surface with no connectivity check
      anywhere in the construction path, so a caller can silently push frame traffic onto
      a mesh that lacks the bandwidth to carry it.
      (SEED-003, planted 2026-09-04; recorded as a scope boundary in v2.0 Phase 14,
      THREAD-03)

### Effects API

- [ ] **EFFECT-01**: A caller constructs the firmware Move effect through a typed API
      instead of hand-encoding the eight-slot `parameters` list and needing to know the
      protocol layout.
      ([#191](https://github.com/Djelibeybi/lifx-async/issues/191))

### Theme Library

- [ ] **THEME-05**: A caller can enumerate primary themes separately from rename aliases,
      and can resolve any accepted name back to its canonical slug. `get_available_themes()`
      currently returns 168 names for 166 themes with nothing marking the two rename
      aliases as aliases.
      ([#201](https://github.com/Djelibeybi/lifx-async/issues/201), PR #196 review)
- [ ] **THEME-06**: A digit-leading display name is representable as a slug, so a future
      app theme such as `80s Neon` cannot abort the generator. `validate_key()`'s
      `str.isidentifier()` rule and the `slug == derive_slug(name)` rule currently conflict
      for this class of name with no escape hatch.
      ([#199](https://github.com/Djelibeybi/lifx-async/issues/199), PR #196 review)
- [ ] **THEME-07**: The changelog enumerates every pre-v1.2 key whose palette changed
      value, `earth` and `coral_reef` included. The substitution is intentional under the
      locked "overwrite redefined themes, keep legacy aliases" decision, but a caller
      upgrading to v1.2 currently gets different colours with no entry naming the affected
      keys.
      ([#198](https://github.com/Djelibeybi/lifx-async/issues/198), PR #196 review)

### Documentation

- [x] **DOCS-07**: `Device.connectivity` is documented as a non-state property rather than
      listed among the state-backed cached properties, with repository guidance about state
      caching aligned. It is derived from request outcomes, not stored device state, so the
      current classification misleads callers about caching and refresh behaviour.
      ([#216](https://github.com/Djelibeybi/lifx-async/issues/216), PR #211 finding 14)
- [x] **DOCS-08**: mDNS discovery docstrings and related documentation state caller-facing
      behaviour and limitations (bounded discovery, proxy responses, testing limitations)
      instead of internal validation language such as mesh scale being "proven
      synthetically".
      ([#215](https://github.com/Djelibeybi/lifx-async/issues/215), PR #211 finding 13)
- [ ] **DOCS-09**: `docs/` carries no em dashes. Each affected sentence is recast rather
      than having the character swapped for a spaced hyphen. Roughly 200 occurrences,
      deferred by the user during v1.2 Phase 7 UAT.

### Tests and CI

- [x] **TEST-01**: mDNS discovery test imports sit at module scope, with function-local
      imports retained only where a demonstrated circular-import or patching constraint
      requires them. Ruff and the complete mDNS discovery suite pass afterwards.
      ([#217](https://github.com/Djelibeybi/lifx-async/issues/217), PR #211 finding 15)
- [x] **TEST-02**: The v2.0 Phase 13 deferred item is resolved either way.
      `test_non_last_detach_preserves_producer_and_last_detach_reaps_it` in
      `tests/test_network/test_discovery_coordinator.py` is verified to leave no blocked
      executor worker, fixed if it does, and `deferred-items.md` is updated to record the
      outcome. The v2.0 close assumed a later commit had already fixed it; `fc61b98` in
      fact fixed a different test
      (`test_forked_child_lazily_starts_a_fresh_coordinator`), so the assumption is
      unverified.
- [x] **CI-01 (reversed)**: `.planning/scripts/ipv6_thread_probe.py` does not contribute
      lines to coverage collection. Phase 15 stated the measured-tree rule in `AGENTS.md`:
      coverage measures the shipped library plus any code a CI job executes, never
      operator or maintainer tooling. The probe is operator tooling, an operator runs it
      by hand against real Thread hardware, so it is out of scope for coverage regardless
      of what it measures. It has relocated there, outside the measured tree entirely,
      and the 225 missed statements and 12 partial branches it carried at 66% coverage
      stop being a coverage question. Issue #214 is closed on this reasoning rather than
      met as originally worded.
      ([#214](https://github.com/Djelibeybi/lifx-async/issues/214), PR #211 finding 12)
- [x] **CI-02**: The `codecov/patch` gate cannot pass without scoring a pull request's full
      changed range. On PR #208 a documentation-only head commit caused the gate to report
      success against zero scored lines, leaving 184 added executable source lines
      unmeasured against the 100% target. Delivered as `.github/patch_coverage_guard.py`, a
      CI guard that computes the changed-measured and scored counts from the repository's
      own data (a merge-base diff intersected with `coverage.py`'s own source analysis) and
      fails the build when the changed measured set is non-empty and none of it was scored.
      The gathered evidence does not support the documentation-only-head-commit
      explanation originally recorded against #209, so the guard is cause-agnostic by
      design rather than a fix aimed at that theory; #209 carries the corrected evidence.
      ([#209](https://github.com/Djelibeybi/lifx-async/issues/209))

## Future Requirements

Tracked, deliberately not in this milestone's roadmap.

### Persistence

- **PERS-01**: Generalise `state_file` save/load out of `CeilingLight` into a reusable
  mixin. Deferred since 2026-06-11. No longer speculative generality: Mirror Light on
  `feat/mirror-light` is the second consumer, so this waits on that branch landing and on
  the hardware arriving.

### Fleet Validation

- **FLEET-01**: Cross-packet mDNS accumulation and follow-up A/AAAA queries confirmed on
  real hardware, once the fleet is large enough to overflow one legacy-unicast reply.
  Proven synthetically in the test suite in the meantime.
- **FLEET-02**: Multi-address and multi-border-router topologies revalidated on hardware.

### Measurement

- **SPIKE-006**: Race the shipped retry config (`timeout=16.0`, `max_retries=8`) against
  spike 002's winning `regime_photons` envelope and an uncapped 16s arm on a lossy path,
  to settle the disputed D5-09 decision ("publish behaviour, not tuning constants"), which
  remains OPEN. Unscheduled; a stretch only if v2.1 finishes early.

## Out of Scope

| Feature | Reason |
|---------|--------|
| PERS-01 `state_file` mixin | Deferred, waiting on `feat/mirror-light` to land as the second consumer (user decision, 2026-09-05) |
| Spike 006 retry-cap-vs-photons-envelope | Unscheduled hardware measurement, not cleanup. D5-09 stays OPEN. Stretch only if v2.1 finishes early (user decision, 2026-09-05) |
| Issue [#1](https://github.com/Djelibeybi/lifx-async/issues/1) Dependency Dashboard | Renovate-owned bot artefact that never closes; not a real issue |
| FLEET-01 / FLEET-02 | Waiting on a fleet large enough to overflow one legacy-unicast reply |
| MirrorLight (PR #194) | Lands on its own schedule, not folded into this milestone (user decision, 2026-08-14) |
| Thread coverage for `HevLight` / `InfraredLight` | No Thread-capable hardware of either class exists in the fleet (v2.0 decision) |
| Live device serials, MAC addresses, IP addresses or hostnames in any committed artefact | Repository privacy rule. MDNS-10 and DISC-04 both produce hardware evidence, so both use format-preserving pseudonyms from the operator's private mapping |

## Traceability

Populated during roadmap creation (2026-09-05). Phase numbering continues from
v2.0, which ended at Phase 14.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MDNS-09 | Phase 16 | Complete |
| MDNS-10 | Phase 17 | Pending |
| DISC-04 | Phase 17 | Pending |
| ANIM-05 | Phase 18 | Pending |
| EFFECT-01 | Phase 18 | Pending |
| THEME-05 | Phase 19 | Pending |
| THEME-06 | Phase 19 | Pending |
| THEME-07 | Phase 19 | Pending |
| DOCS-07 | Phase 16 | Complete |
| DOCS-08 | Phase 16 | Complete |
| DOCS-09 | Phase 20 | Pending |
| TEST-01 | Phase 16 | Complete |
| TEST-02 | Phase 15 | Complete |
| CI-01 | Phase 15 | Reversed |
| CI-02 | Phase 15 | Complete |

**Coverage:**

- v2.1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0
- Orphaned (no phase): 0
- Duplicated (more than one phase): 0

Per-phase distribution: Phase 15 (3), Phase 16 (4), Phase 17 (2), Phase 18 (2),
Phase 19 (3), Phase 20 (1).

---
*Requirements defined: 2026-09-05*
*Last updated: 2026-09-05 after v2.1 roadmap creation*
