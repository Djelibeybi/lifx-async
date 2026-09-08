# Roadmap: lifx-async

## Milestones

- ✅ **v1.0 Ceiling Save-on-Exit**: Phase 1, shipped 2026-06-12 ([archive](milestones/v1.0-ROADMAP.md))
- ✅ **Post-v1.0 Discovery unification**: Phase 1, verified 2026-06-13, archived in `milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`
- ✅ **v1.1 Wire Reliability**: Phases 2–5, shipped 2026-07-26 ([archive](milestones/v1.1-ROADMAP.md))
- ✅ **v1.2 Theme Library Update**: Phases 6–9, shipped 2026-08-27 ([archive](milestones/v1.2-ROADMAP.md))
- ✅ **v2.0 Thread/IPv6 Support**: Phases 10–14, shipped 2026-09-05 ([archive](milestones/v2.0-ROADMAP.md))
- 🚧 **v2.1 Spring Cleaning**: Phases 15–20, in progress

## Phases

<details>
<summary>✅ v1.0 Ceiling Save-on-Exit (Phase 1), SHIPPED 2026-06-12</summary>

- [x] Phase 1: Ceiling Save-on-Exit (1/1 plans), completed 2026-06-12

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ Post-v1.0 Phase 1: Unify duplicated discovery loops (verified 2026-06-13)</summary>

Standalone phase from the /simplify review (2026-06-13). Rebuilt `discover_devices()`
on `_discover_with_packet()` with hoisted DoS serial validation and first-wins per-serial
dedup; retired `_parse_device_state_service()`. Review-fix 6/6, security 11/11 closed,
UAT 4/4 including real-hardware validation (regression 0d83deb found and fixed).
5/5 plans complete. Phase directory archived in
`milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`.

</details>

<details>
<summary>✅ v1.1 Wire Reliability (Phases 2–5), SHIPPED 2026-07-26</summary>

Closed the measured reliability gap against the reference clients (Glowup, Photons) using
the spike-validated blueprints, without changing the asyncio core or the public API.

- [x] Phase 2: Discovery Re-broadcast (2/2 plans), completed 2026-07-16
- [x] Phase 3: Retry Schedule Reshape (3/3 plans), completed 2026-07-17
- [x] Phase 4: Animation Flow Control (13/13 plans), completed 2026-07-17
- [x] Phase 5: Reliability Documentation (6/6 plans), completed 2026-07-18

13/13 requirements satisfied, 25/25 must-have truths verified, 7/7 cross-phase
connections wired, all four phases Nyquist-compliant.

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) ·
audit: [milestones/v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.2 Theme Library Update (Phases 6–9), SHIPPED 2026-08-27</summary>

Resynced `lifx.theme.library` with the LIFX app's live theme set without silently changing
colours existing callers depend on. The hand-written palette table is gone: 166 committed
JSONL records drive a validating generator into `src/lifx/theme/data.py`, and 169 names
resolve with app-accurate palettes, names, categories and dispositions.

- [x] Phase 6: Generated Theme Library (2/2 plans), completed 2026-08-15
- [x] Phase 7: Taxonomy & Legacy Dispositions (3/3 plans), completed 2026-08-15
- [x] Phase 8: Hardware Fidelity Validation (4/4 plans), completed 2026-08-16
- [x] Phase 9: Theme Data Contract & Docs (2/2 plans), completed 2026-08-27

16/16 live requirements satisfied, 8 cross-phase seams checked, 3520 tests at 97%
coverage. COMPAT-02 retired 2026-08-14; TOOL-01..03 withdrawn 2026-08-19 to the private
`lifx-theme-resync` repository.

Two locked decisions reversed in flight: the `*_legacy` aliases, and the "device readback
only" capture rule. The latter is what answered the milestone's central question, since
Phase 9's resync from an internal LIFX HTTP API endpoint supplied the true palette lengths
that no device could.

Closed at `tech_debt` with both audit findings remediated before archiving, and one
finding withdrawn as mistaken. Phase 8 retains its operator-approved exception: the
source-Tile restoration is unverified, `08-UAT-RESULTS.json` is deliberately absent, and a
synthetic two-role merge is prohibited.

Full details: [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) ·
audit: [milestones/v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v2.0 Thread/IPv6 Support (Phases 10–14), SHIPPED 2026-09-05</summary>

A Thread device became a first-class device: found by default (`discover()` merges a UDP
broadcast leg and a unicast-verified mDNS leg by serial), addressed by IPv6 literal
(`find_by_ip()`), raced concurrently in `find_by_serial()`, and self-identified via
`Device.connectivity`. The mDNS leg reached broadcast-grade quality (ephemeral-port bind,
RFC 6762-compliant goodbye/cache-flush handling, bounded fail-closed record admission).
Every v1.1 wire-reliability finding was then revalidated against a real 8-device Thread
fleet.

- [x] Phase 10: Land the IPv6/Thread Branch (9/9 plans), completed 2026-08-28 (PR #210)
- [x] Phase 11: mDNS Hardening (14/14 plans), completed 2026-08-29
- [x] Phase 12: IPv6 Discovery Plumbing (5/5 plans), completed 2026-08-29
- [x] Phase 13: Merged Discovery (7/7 plans), completed 2026-08-31
- [x] Phase 14: Thread Revalidation and Docs (6/6 plans), completed 2026-09-04

28/28 requirements satisfied, 41/41 plans complete. Closed at `override_closeout`: two
dormant seeds (SEED-002 WiFi-control staleness, SEED-003 lock `Animator` to WiFi) and one
Phase 13 deferred item (coordinator teardown test hang) acknowledged rather than blocking
close — see `.planning/STATE.md` Deferred Items.

Full details: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

</details>

### 🚧 v2.1 Spring Cleaning (Phases 15–20, In Progress)

**Milestone Goal:** Clear every accumulated small item so nothing carried forward is left
unaddressed: all 11 open GitHub issues, both dormant seeds, the repo-wide em dash style
debt, and the one unclosed deferred item from v2.0 Phase 13.

This is a cleanup round, not a feature milestone. Most requirements are small, independent
fixes; the phases group them by the code and review surface they touch and by what can be
verified together, not by size.

- [x] **Phase 15: Coverage Gate and Test-Suite Health** - Make the project's own verification machinery honest before it measures anything else: the `codecov/patch` gate cannot pass without scoring a pull request's changed range, the `scripts/` tree triage and measured-tree rule state which code coverage measures, and the v2.0 Phase 13 coordinator teardown item is settled either way (completed 2026-09-07)
- [x] **Phase 16: mDNS Correctness, Docs and Test Hygiene** - Close the fail-closed address-check bypass in `selected_address_for()`, and make the mDNS surface describe itself to callers: `Device.connectivity` classified as a derived rather than cached property, caller-facing discovery docstrings, and module-scope test imports (completed 2026-09-07)
- [x] **Phase 17: Fleet Diagnostics and the Staleness Control** - Make the IPv6 Thread probe report what it actually observed, and give v2.0's 4140-4200s Thread disappearance-to-expiry interval a WiFi control measured with the same protocol (completed 2026-09-08)
- [ ] **Phase 18: Animator Connectivity Guard and Typed Move Effect** - The milestone's two public API changes: `Animator` stops silently accepting a Thread device, and a caller builds the firmware Move effect through typed arguments instead of an eight-slot `parameters` list
- [ ] **Phase 19: Theme Library API and Data** - Primary themes distinguishable from rename aliases with canonical-slug resolution, a digit-leading display name representable as a slug, and the v1.2 palette substitutions named in the changelog
- [ ] **Phase 20: Documentation Prose Sweep** - Roughly 200 em dashes across `docs/` recast sentence by sentence rather than substituted, run last so it cannot collide with any other change to `docs/`

**Constraints that bind every phase:**

- CI requires **100% branch patch coverage**, not just line coverage. Branch partials count.
- Zero runtime dependencies, Python 3.10 floor, so no `asyncio.TaskGroup`.
- Generated files (`src/lifx/protocol/*`, `src/lifx/products/registry.py`) are never
  hand-edited.
- `docs/changelog.md` is produced by the release workflow. Nothing in this milestone edits
  it directly; changelog content reaches it through Conventional Commit messages and
  release notes.
- No live device serial, MAC address, IP address or hostname reaches a committed artefact.
  Phase 17 is the only phase producing hardware evidence and uses format-preserving
  pseudonyms from the operator's private mapping.
- Australian English in all prose and comments.

**Execution notes:**

- **Phase 15 runs first because it changes what "verified" means.** Phase 15 reverses CI-01:
  the probe is operator tooling, so it leaves the measured tree entirely rather than being
  added to it, and Phase 17 inherits it at its relocated `.planning/scripts/` path, outside
  coverage collection. CI-02 must land before any phase leans on a green `codecov/patch`
  badge.

- **Phase 17 is serial after Phase 16.** The probe drives the library's own mDNS
  primitives, including `selected_address_for()`, so MDNS-09's owner-name normalisation
  settles before MDNS-10 changes what the probe reports about a cached but unusable
  address.

- **Phases 16, 18 and 19 are file-disjoint and can run in parallel.** Phase 16 lives in
  `src/lifx/network/discovery/mdns/`, `src/lifx/devices/base.py` docstrings and
  `tests/test_network/`; Phase 18 lives in `src/lifx/animation/` and
  `src/lifx/devices/multizone.py`; Phase 19 lives in `src/lifx/theme/` and
  `data/themes.jsonl`.

- **Phase 20 is last on purpose.** A ~200-occurrence prose pass across `docs/` conflicts
  textually with every other phase that adds or edits documentation, so it sweeps what the
  earlier phases have already landed rather than racing them.

- **Phase 17's DISC-04 is hardware-gated** and cannot be verified by the emulator suite: it
  needs a real WiFi bulb and a physical unplug, mirroring v2.0's THREAD-04. It must not
  block CI or any other phase.

- **TEST-02's outcome is unknown by design.** The test may already be correct, in which
  case the deliverable is the recorded verification plus the `deferred-items.md` update,
  not a code change. `fc61b98` fixed a different test, so the v2.0 close assumption does
  not carry.

## Phase Details

### Phase 15: Coverage Gate and Test-Suite Health

**Goal**: The project's own verification machinery tells the truth, so every later phase in
this milestone is measured rather than assumed
**Depends on**: Nothing (first phase of v2.1; v2.0 shipped 2026-09-05)
**Requirements**: CI-01, CI-02, TEST-02
**Success Criteria** (what must be TRUE):

  1. A pull request whose head commit changes only documentation can no longer report a passing `codecov/patch` gate against zero scored lines: the case is either prevented outright or fails loudly with a message naming it, reproducing PR #208's 184 unmeasured executable lines as a failure
  2. Coverage measures the shipped library plus code a CI job executes, and nothing else: `scripts/` holds only `generate_theme_data.py`, the five operator measurement scripts relocate to `.planning/scripts/` outside the measured tree, and CI-01 is recorded as reversed rather than met, since the probe it asked to add is operator tooling
  3. `test_non_last_detach_preserves_producer_and_last_detach_reaps_it` is run under conditions that would expose a blocked executor worker, and the observed outcome is recorded as evidence rather than inferred from a later commit
  4. `deferred-items.md` records the v2.0 Phase 13 item as verified-clean or as fixed, naming the evidence, so no unclosed assumption carries past this milestone

**Plans**: 5/5 plans executed
**Wave 1**

- [x] 15-01-PLAN.md: tracer that relocates `check_patch_coverage.py` and proves the opt-in tooling-test collection mechanism end to end (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 15-02-PLAN.md: relocate the five measurement scripts, delete the two dead ones, flat sibling imports including the two default-suite consumers, PEP 723 headers, and the two-target `--cov` rule (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 15-03-PLAN.md: the vacuous-gate guard, its fixture-driven tests, and the CI step in the designated ubuntu cell (wave 3)
- [x] 15-04-PLAN.md: TEST-02 coordinator teardown evidence in both directions, and reconciliation of `deferred-items.md` with `STATE.md` (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 15-05-PLAN.md: `AGENTS.md` measured-tree rule and corrected invocations, CI-01 reversal on the record including Phase 17's dependency reason, the R2 exclusion boundary amended into the spec, and the #214 and #209 issue corrections (wave 4)

### Phase 16: mDNS Correctness, Docs and Test Hygiene

**Goal**: The mDNS surface behaves correctly at its fail-closed boundary and describes
itself to callers in caller-facing terms
**Depends on**: Phase 15 (the patch gate must score a changed range before later work
relies on it); file-disjoint from Phases 18 and 19 and can run in parallel with them
**Requirements**: MDNS-09, DOCS-07, DOCS-08, TEST-01
**Success Criteria** (what must be TRUE):

  1. An owner name supplied with a trailing dot resolves to the same address decision as the same name without one, so an unusable address is refused in both forms; a regression test fails if the normalisation is removed from `selected_address_for()`
  2. A caller reading `Device.connectivity` learns it is derived from request outcomes rather than stored device state, and no repository or published guidance lists it among the state-backed cached properties
  3. The mDNS discovery docstrings and related pages state bounded discovery behaviour, proxy responses and testing limitations in terms a caller can act on, with no internal validation language such as mesh scale being "proven synthetically" remaining
  4. The mDNS discovery tests import at module scope, ruff and the complete mDNS discovery suite pass, and any retained function-local import carries a named circular-import or patching reason rather than being left unexplained

**Plans**: 4/4 plans executed

Plans:

**Wave 1**

- [x] 16-01-PLAN.md: MDNS-09 tracer, the owner-name normalisation split and the extracted fail-closed guard predicate, with the named regression test and the owner-form invariant matrix (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 16-02-PLAN.md: DOCS-08 caller-facing mDNS prose, both `test_phase_contract.py` phrase lists moved in the same commit, and the new repository-wide `tests/test_docs_language.py` contract (wave 2)

**Wave 3** *(blocked on Wave 2 completion; the two plans are file-disjoint and run in parallel)*

- [x] 16-03-PLAN.md: DOCS-07 `Device.connectivity` reclassified as a derived non-state property, with a third `AGENTS.md` caching category and the two contract assertions split by file (wave 3)
- [x] 16-04-PLAN.md: TEST-01 the 166-import sweep across 27 files as one commit, then the `PLC0415` ruff enablement with per-file-ignores that hand off to Phases 18 and 19 (wave 3)

### Phase 17: Fleet Diagnostics and the Staleness Control

**Goal**: The hardware-facing diagnostics report what they actually observed, and v2.0's
Thread disappearance-to-expiry interval of 4140 to 4200 s (not to be confused with its separate
69.4 s restoration duration) gains a WiFi control instead of standing alone
**Depends on**: Phase 15 (the probe lands at its relocated `.planning/scripts/` path, outside the measured tree) and Phase 16
(the probe drives the library's address selection, so MDNS-09 settles first)
**Requirements**: MDNS-10, DISC-04
**Success Criteria** (what must be TRUE):

  1. The probe distinguishes an instance holding no address data at all from one holding a cached but unusable unscoped link-local AAAA record, and says which it saw instead of reporting "pending address records" for both
  2. The `linklocal_chosen` summary counter and its warning are reachable and truthful, or removed; a partially assembled instance no longer terminates diagnostics through the TXT assertion, and instead produces defensive diagnostic output
  3. Advertisement staleness is measured against a WiFi bulb using the same disappearance-to-expiry protocol THREAD-04 used on Thread, producing a figure directly comparable with the recorded 4140 to 4200 s interval
  4. The recorded result states whether the 4140 to 4200 s disappearance-to-expiry interval is Thread-specific or a general mDNS TTL and goodbye artefact, so the library can answer that question rather than leaving one measurement uncontrolled
  5. Every committed artefact from both runs carries format-preserving pseudonyms from the operator's private mapping, with no live serial, MAC address, IP address or hostname anywhere in the staged diff

**Plans**: 5/5 plans executed

Plans:

**Wave 1**

- [x] 17-01-PLAN.md: MDNS-10 tracer, the typed instance view with five explicit selection states, the refused-versus-absent split, the single owner-normalisation site, the split summary counts, the dead link-local counter and predicate name removed, and defensive TXT handling (wave 1)

**Wave 2** *(blocked on Wave 1 completion; same two files)*

- [x] 17-02-PLAN.md: the opt-in `--alias-map` redaction, its external loader, prefix-reserved address substitution and stdout install seam, as its own commit with its own tooling tests (wave 2)

**Wave 3** *(blocked on Wave 2 completion; hardware-gated, first half of the single operator sitting)*

- [x] 17-03-PLAN.md: R4 one redacted Thread-fleet probe transcript under `17-EVIDENCE/`, with the observed and not-observed statement and a blocking staged-diff inspection (wave 3)

**Wave 4** *(blocked on Wave 3 completion; hardware-gated, second half of the same sitting. Serialised after Wave 3 rather than sharing it: the two hardware plans are file-disjoint in what they write but share one git index and the `17-EVIDENCE/` directory, so concurrent runs could inspect or commit each other's staged artefacts)*

- [x] 17-04-PLAN.md: DISC-04 the WiFi staleness trial through the unmodified tool, its session manifest and staleness JSONL under `17-EVIDENCE/`, the same-alias rerun guarantee and a blocking staged-diff inspection (wave 4)

**Wave 5** *(blocked on Wave 4 completion; gated on real WiFi numbers per D-22)*

- [x] 17-05-PLAN.md: R6 the staleness control finding with all four figures and the 69.4 second correction across ROADMAP and REQUIREMENTS, and R7 the caller-facing liveness prose with its approved-phrase lock (wave 5)

### Phase 18: Animator Connectivity Guard and Typed Move Effect

**Goal**: The milestone's two public API changes land: a caller cannot silently push
animation frames onto a Thread mesh, and a caller builds the firmware Move effect without
knowing the protocol layout
**Depends on**: Phase 15; file-disjoint from Phases 16 and 19 and can run in parallel with
them
**Requirements**: ANIM-05, EFFECT-01
**Success Criteria** (what must be TRUE):

  1. `Animator.for_light()`, `for_multizone()` and `for_matrix()` refuse or clearly degrade when handed a Thread device, naming connectivity as the reason at construction time rather than failing opaquely later during frame delivery
  2. A WiFi device constructs and drives an `Animator` exactly as before, so existing callers including LedFx see no signature or behaviour change
  3. A caller starts the firmware Move effect by naming direction, speed and duration through typed arguments, without constructing the eight-slot `parameters` list or knowing which slot carries direction
  4. The typed Move API appears in the published API documentation with an example that runs, and the existing `MultiZoneEffect` construction path keeps working for callers already using it

**Plans**: TBD

### Phase 19: Theme Library API and Data

**Goal**: A caller can tell a primary theme from a rename alias, a digit-leading app name
cannot abort the generator, and the v1.2 palette substitutions are named where an upgrading
caller will find them
**Depends on**: Phase 15; file-disjoint from Phases 16 and 18 and can run in parallel with
them
**Requirements**: THEME-05, THEME-06, THEME-07
**Success Criteria** (what must be TRUE):

  1. A caller can enumerate the primary themes separately from the rename aliases, instead of receiving 168 flat names for 166 themes with nothing marking the two aliases
  2. Any accepted theme name, primary or alias, resolves back to its canonical slug through a documented call
  3. A display name beginning with a digit, such as `80s Neon`, is representable as a slug and regenerates `src/lifx/theme/data.py` without aborting, so the conflict between `validate_key()`'s identifier rule and the `slug == derive_slug(name)` rule has an escape hatch before the app ships such a name
  4. The changelog enumerates every pre-v1.2 key whose palette changed value, `earth` and `coral_reef` included, reaching `docs/changelog.md` through the release process rather than by editing that generated file

**Plans**: TBD

### Phase 20: Documentation Prose Sweep

**Goal**: The published documentation reads in the project's house style, with every em
dash recast rather than substituted
**Depends on**: Phases 15 to 19 (every other change touching `docs/` lands first, so this
sweep cannot collide with them)
**Requirements**: DOCS-09
**Success Criteria** (what must be TRUE):

  1. A repository-wide search of `docs/` finds no em dash character, covering the roughly 200 occurrences deferred during v1.2 Phase 7 UAT
  2. Each affected sentence is recast so its meaning survives, with no occurrence replaced by a spaced hyphen, an en dash or a comma standing in for the same construction
  3. The documentation still builds clean under `--strict` with zero warnings, and the theme catalogue and discovery guide drift tests stay green, so the sweep changes prose without breaking the bindings between docs and library

**Plans**: TBD

## Progress

**Execution Order:** 15 → (16 → 17) ∥ 18 ∥ 19 → 20

| Milestone | Phases | Status | Shipped |
|-----------|--------|--------|---------|
| v1.0 Ceiling Save-on-Exit | 1 | Complete | 2026-06-12 |
| Post-v1.0 Discovery unification | 1 | Complete | 2026-06-13 |
| v1.1 Wire Reliability | 2–5 | Complete | 2026-07-26 |
| v1.2 Theme Library Update | 6–9 | Complete | 2026-08-27 |
| v2.0 Thread/IPv6 Support | 10–14 | Complete | 2026-09-05 |
| v2.1 Spring Cleaning | 15–20 | In progress | - |

### v2.1 Phases

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 15. Coverage Gate and Test-Suite Health | 5/5 | Not started |  |
| 16. mDNS Correctness, Docs and Test Hygiene | 4/4 | Not started |  |
| 17. Fleet Diagnostics and the Staleness Control | 5/5 | Not started |  |
| 18. Animator Connectivity Guard and Typed Move Effect | 0/? | Not started | - |
| 19. Theme Library API and Data | 0/? | Not started | - |
| 20. Documentation Prose Sweep | 0/? | Not started | - |
