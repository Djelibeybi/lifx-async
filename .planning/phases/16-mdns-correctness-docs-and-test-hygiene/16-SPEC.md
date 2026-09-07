# Phase 16 Specification: mDNS Correctness, Docs and Test Hygiene

**Created:** 2026-09-07
**Ambiguity score:** 0.13 (gate: ≤ 0.20)
**Requirements:** 4 locked

## Goal

`selected_address_for()` stops accepting a trailing-dot owner name that bypasses its
fail-closed unusable-address guards, the mDNS and connectivity documentation describes
caller-visible behaviour instead of internal validation language, and every function-local
import under `tests/` outside Phase 18 and Phase 19 territory moves to module scope.

## Background

Four PR #211 review findings were deferred to issues #213, #215, #216 and #217. All four
are live in the working tree today.

`_LifxRecordCache` keys every cached owner set through `_normalise_dns_name()`
(`src/lifx/network/discovery/mdns/discovery.py:144`), which strips one trailing dot and
casefolds. `selected_address_for()` (`discovery.py:349`) instead calls `owner.lower()`.
An owner supplied as `host.local.` therefore misses all five fail-closed guards, which are
keyed by the normalised form: retained-payload-budget exhaustion, address-budget
exhaustion, `_address_overflowed_owners`, and byte-incomplete A and AAAA owner types.
It still reaches `_addresses_in_order()`, which routes through `records_for()` and does
normalise, so the call returns an address that the guards were written to refuse. The
bypass is reachable, not theoretical.

`docs/user-guide/advanced-usage.md:143` lists `Device.connectivity` under the state-backed
`#### Device Properties` list, immediately above the `##### Non-State Properties` heading
where `Device.model` already sits. The property is derived from `connection.thread_connection`
on every read (`src/lifx/devices/base.py:2304`) and caches nothing. `AGENTS.md:349-350`
models caching as exactly two lists, cached semi-static and never-cached volatile, and
`connectivity` appears in neither, so the repository guidance offers no correct home for it.

The sentence `Mesh scale is proven synthetically.` appears in the `discover_mdns()` docstring
(`src/lifx/api.py:1287`) and in `docs/user-guide/discovery.md:120`. It is also load-bearing
in the test suite twice: `test_public_guidance_uses_the_approved_limitation_phrases`
(`tests/test_network/test_mdns/test_phase_contract.py:132`) requires it in `discovery.md`,
and `_MOVED_MDNS_LIMITATION_PHRASES` (line 394) asserts it is absent from
`advanced-usage.md`. Deleting the prose without moving both contract sites fails the suite.
Proxy behaviour, where a Thread border router advertises every device on its mesh, exists
only in internal code comments (`discovery.py:277`, `699`, `726`, `782`, `814`) and is never
stated to a caller.

Ruff's `PLC0415` rule reports 322 function-local imports repository-wide: 189 under `tests/`,
82 under `src/`, 49 under `.planning/` and 2 elsewhere. 58 of the `tests/` ones are in
`tests/test_network/test_mdns/`. `test_discovery.py` already imports
`_discover_lifx_services_sweep` and `_LifxRecordCache` from the same module at module scope,
so no circular-import barrier exists for the 50 local imports of `_discover_lifx_services`
and `discover_devices_mdns` in that file.

## Requirements

1. **Owner-name normalisation**: `selected_address_for()` normalises its owner argument
   through the same helper that keys the cached owner sets.
   - Current: `selected_address_for()` calls `owner.lower()` while every cached owner set is
     keyed by `_normalise_dns_name()`, so a trailing-dot owner misses all five fail-closed
     guards yet still receives an address through the normalising `records_for()` path
   - Target: `selected_address_for()` routes its owner argument through
     `_normalise_dns_name()`, so `host.local.` and `host.local` reach the identical guard
     set and the identical selection result
   - Acceptance: a named regression test asserts that for an owner in the
     `_address_overflowed_owners` set, both the bare and the trailing-dot form return `None`;
     a parametrised invariant test asserts `records_for()`, `addresses_for()` and
     `selected_address_for()` return identical results across bare, trailing-dot, uppercase
     and mixed-case forms of the same owner

2. **Connectivity classification**: `Device.connectivity` is documented as a derived
   non-state property and the repository caching guidance gains a category that fits it.
   - Current: `advanced-usage.md:143` lists it under state-backed `#### Device Properties`;
     `AGENTS.md:349-350` offers only cached-semi-static and never-cached-volatile, and names
     it in neither
   - Target: the bullet moves under the existing `##### Non-State Properties` heading in
     `advanced-usage.md`, and `AGENTS.md` gains an explicit third derived-not-cached
     category naming `connectivity`, so the two-list model stops implying every property is
     one or the other
   - Acceptance: a contract assertion proves `connectivity` appears in exactly one of the
     three `AGENTS.md` caching categories and is absent from the state-backed property list
     in `advanced-usage.md`

3. **Caller-facing mDNS prose**: the mDNS discovery documentation states bounded discovery,
   proxy responses and testing limitations in terms a caller can act on.
   - Current: `api.py:1287` and `discovery.md:120` both carry `mesh scale is proven
     synthetically`; the phrase is simultaneously required by
     `test_public_guidance_uses_the_approved_limitation_phrases` and forbidden by
     `_MOVED_MDNS_LIMITATION_PHRASES`; proxy behaviour appears only in internal code comments
   - Target: `docs/user-guide/discovery.md` names all three topics in caller terms;
     the `discover_mdns()` docstring, `docs/migration/mdns-low-level-api-7.0.0.md` and
     `docs/getting-started/quickstart.md` carry no internal validation language and do not
     contradict the guide; both `test_phase_contract.py` phrase lists move to the replacement
     wording; a repo-wide negative assertion proves the removed jargon appears nowhere under
     `src/` or `docs/`
   - Acceptance: the full test suite passes with the updated approved-phrase and
     forbidden-phrase lists; a grep-equivalent assertion for `proven synthetically` and
     `mesh scale` over `src/` and `docs/` returns zero matches; `discovery.md` names bounded
     discovery, proxy responses and testing limitations

4. **Module-scope test imports**: function-local imports move to module scope across `tests/`,
   excluding Phase 18 and Phase 19 territory.
   - Current: 189 `PLC0415` violations across `tests/`, 58 of them in
     `tests/test_network/test_mdns/`, with no circular-import barrier demonstrated for any
     of the mDNS ones. `PLC0415` is not in ruff's `select` list, so nothing enforces the rule
   - Target: 166 violations across 27 files move to module scope. Exactly three paths are
     excluded and left untouched: `tests/test_animation/`,
     `tests/test_devices/test_multizone.py` and `tests/test_theme/`. A function-local import
     is retained only where a circular-import or patching constraint is demonstrated, and
     each retained one carries a comment naming that reason
   - Acceptance: `uv run ruff check .` and `uv run ruff format --check .` pass;
     `uv run --frozen pytest` passes; `git diff --name-only` lists no file under the three
     excluded paths; every function-local import remaining under `tests/` outside those three
     paths has an adjacent comment naming a circular-import or patching reason

## Boundaries

**In scope:**
- `selected_address_for()` owner normalisation in
  `src/lifx/network/discovery/mdns/discovery.py`
- A regression test and a parametrised owner-form invariant test over `_LifxRecordCache`'s
  three owner-keyed public lookups
- Moving the `Device.connectivity` bullet in `docs/user-guide/advanced-usage.md`
- A third derived-not-cached category in `AGENTS.md`
- Caller-facing prose in the `discover_mdns()` docstring, `docs/user-guide/discovery.md`,
  `docs/migration/mdns-low-level-api-7.0.0.md` and `docs/getting-started/quickstart.md`
- Updating both phrase lists in `tests/test_network/test_mdns/test_phase_contract.py` and
  adding a repo-wide negative assertion
- Moving 166 function-local imports to module scope across 27 files under `tests/`
- Closing issues #213, #215, #216 and #217 through `Closes` lines in the merge commit

**Out of scope:**
- Em dash recasting in any file this phase touches. Phase 20 owns DOCS-09 as a single
  repository-wide pass of roughly 200 occurrences, and a partial recast here would collide
  textually with it
- `.planning/scripts/ipv6_thread_probe.py`. It calls `selected_address_for()`, so
  requirement 1 changes what it observes, but its own `linklocal_chosen` counter, unscoped
  link-local handling and TXT assertion belong to MDNS-10 in Phase 17
- Retuning any mDNS timing constant. The bounded initial-PTR schedule, the one-second and
  three-second retransmissions, and the address, owner and payload budgets stay exactly as
  they are. No WiFi-measured constant is retuned before Phase 17 measures it
- `tests/test_animation/`, `tests/test_devices/test_multizone.py` and `tests/test_theme/`.
  These are Phase 18 and Phase 19 territory, and touching them would break the locked v2.1
  property that Phases 16, 18 and 19 are file-disjoint and can run in parallel
- `docs/changelog.md`. It is generated by the release workflow and is never hand-edited
- Any change to the `Connectivity` enum, the `thread_connection` frame-address read, or the
  `connectivity` property implementation. Requirement 2 is a documentation and classification
  change only

## Constraints

- Python 3.10 through 3.14. `asyncio.TaskGroup` remains unavailable and unused
- Zero runtime dependencies. No new runtime dependency may be introduced
- The complete test suite, `uv run pyright` and `uv run ruff check .` must pass
- CI requires 100% branch patch coverage on changed measured lines. The measured tree is
  `--cov=lifx` and `--cov=generate_theme_data` only
- `test_phase_contract.py` must stay green throughout. The removed sentence is currently a
  required phrase in one assertion and a forbidden phrase in another, so both sites move
  together with the prose
- Australian English spelling, no em dashes in new or edited prose. Recast the sentence
  rather than substituting a spaced hyphen
- Conventional Commit messages with no GSD phase or plan metadata as scope; every commit
  signed with `git commit -S -s`
- Requirement 1 must not change the public API surface of `_LifxRecordCache` or the return
  type of `selected_address_for()`

## Acceptance Criteria

- [ ] `selected_address_for()` routes its owner argument through `_normalise_dns_name()`
- [ ] A named regression test asserts that a trailing-dot owner and its bare form return the
      identical result from `selected_address_for()`, including `None` when a guard fires
- [ ] `selected_address_for("")` and `selected_address_for(".")` both return `None` and match
      no cached owner entry
- [ ] A test covers an owner name whose `.lower()` and `.casefold()` forms differ, proving
      the guard set and the lookup agree on the casefolded form
- [ ] For an owner with multiple advertised addresses, the trailing-dot form returns the
      byte-identical address string the bare form returns, not merely a non-`None` value
- [ ] The parametrised invariant test covers `records_for()`, `addresses_for()` and
      `selected_address_for()` across bare, trailing-dot, uppercase and mixed-case owners
- [ ] `Device.connectivity` appears under `##### Non-State Properties` in
      `docs/user-guide/advanced-usage.md` and not in the state-backed list above it
- [ ] `AGENTS.md` carries a third derived-not-cached caching category naming `connectivity`
- [ ] A contract assertion proves `connectivity` appears in exactly one of the three
      `AGENTS.md` caching categories
- [ ] `docs/user-guide/discovery.md` names bounded discovery, proxy responses and testing
      limitations in caller terms
- [ ] The `discover_mdns()` docstring, `docs/migration/mdns-low-level-api-7.0.0.md` and
      `docs/getting-started/quickstart.md` contain no internal validation language and do not
      contradict `discovery.md`
- [ ] Both phrase lists in `test_phase_contract.py` carry the replacement wording and the
      suite passes
- [ ] A repo-wide negative assertion proves `proven synthetically` and `mesh scale` appear
      nowhere under `src/` or `docs/`, and that assertion's file set is satisfiable alongside
      the new approved phrases
- [ ] The negative assertion's file set accounts for the generated `docs/changelog.md`
      without requiring an edit to it
- [ ] `uv run ruff check --select PLC0415 tests/` reports zero violations outside the three
      excluded paths, down from 166 across 27 files
- [ ] `git diff --name-only` lists no file under `tests/test_animation/`,
      `tests/test_devices/test_multizone.py` or `tests/test_theme/`
- [ ] No file with zero function-local imports is modified by requirement 4
- [ ] Every function-local import retained under `tests/` outside the three excluded paths
      carries an adjacent comment naming a circular-import or patching reason
- [ ] `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` all pass
- [ ] `uv run --frozen pytest` passes
- [ ] MUST NOT: no fail-closed guard becomes fail-open. Every unusable-address condition
      still returns `None` in bare, trailing-dot, uppercase and mixed-case owner forms
- [ ] MUST NOT: no raw owner name, hostname or address is emitted into any log, exception
      message, diagnostic counter or committed test fixture
- [ ] MUST NOT: no documentation describes `connectivity` as authenticating the device or as
      a security or trust boundary
- [ ] MUST NOT: no documentation states or implies that a bounded sweep enumerates every
      device on the mesh, or that a border-router advertisement proves the advertised device
      is currently reachable
- [ ] MUST NOT: no fleet-specific Phase 14 observation is presented as a universal benchmark
      or a performance guarantee
- [ ] MUST NOT: no test is deleted, skipped, xfailed or weakened, and no `noqa` or
      per-file-ignore is added, to make the import sweep pass
- [ ] MUST NOT: `docs/changelog.md` is not edited

## Edge Coverage

**Coverage:** 12/15 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | AC: trailing-dot and bare forms resolve to one cache identity |
| empty | R1 | ✅ covered | AC: `""` and `"."` both return `None` and match no entry |
| encoding | R1 | ✅ covered | AC: an owner whose `.lower()` and `.casefold()` differ proves guard and lookup agree |
| ordering | R1 | ✅ covered | AC: trailing-dot form returns the byte-identical address, not merely non-`None` |
| adjacency | R2 | ✅ covered | AC: contract assertion proves exactly one `AGENTS.md` category names `connectivity` |
| empty | R2 | ⛔ dismissed | A derived category with one member is well-formed; `Device.model` already sits under Non-State Properties, and no behaviour reads category cardinality |
| ordering | R2 | ⛔ dismissed | The order of the three caching lists is cosmetic; no consumer reads list order |
| adjacency | R3 | ✅ covered | AC: the negative assertion's file set is satisfiable alongside the new approved phrases |
| empty | R3 | ✅ covered | AC: `discovery.md` carries all three topics; the other three surfaces need only remove the jargon and not contradict it |
| ordering | R3 | ⛔ dismissed | The order the three topics appear in prose is cosmetic and no assertion depends on it |
| concurrency | R3 | ✅ covered | AC: the negative assertion accounts for the generated `docs/changelog.md` without editing it |
| adjacency | R4 | ✅ covered | AC: exactly three excluded paths; `tests/conftest.py` and `tests/test_packaging.py` sit at the root and are in scope |
| empty | R4 | ✅ covered | AC: no file with zero function-local imports is modified |
| ordering | R4 | ✅ covered | AC: an import whose relocation changes observable behaviour stays local with a named reason |
| concurrency | R4 | 🧪 backstop | Held-out edge test: a targeted single-file run of a changed file that imports `measurement_support` passes, proving no relocation depends on `tests/conftest.py`'s `sys.path` insert running first. Carry into plan-phase `must_haves` |

## Prohibitions (must-NOT)

**Coverage:** 7/7 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT turn any fail-closed guard into fail-open. Every unusable-address condition still returns `None` in every owner form | R1 | resolved | test (descriptor not captured: the `check_kind` schema offers `node-test` and `lint-rule` only, and this is a pytest repository) |
| MUST NOT emit a raw owner name, hostname or address into any log, exception message, diagnostic counter or committed test fixture | R1 | resolved | test (descriptor not captured, same schema reason) |
| MUST NOT describe `connectivity` as authenticating the device or as a security or trust boundary | R2 | resolved | judgment |
| MUST NOT state or imply that a bounded sweep enumerates every device on the mesh, or that a border-router advertisement proves the advertised device is currently reachable | R3 | resolved | judgment |
| MUST NOT present fleet-specific Phase 14 observations as universal benchmarks or performance guarantees | R3 | resolved | judgment |
| MUST NOT delete, skip, xfail or weaken any test, and MUST NOT add a `noqa` or per-file-ignore, to make the import sweep pass | R4 | resolved | test (descriptor not captured, same schema reason) |
| MUST NOT edit `docs/changelog.md`, which is generated by the release workflow | R3 | resolved | test (descriptor not captured, same schema reason) |

**Canon referrals (recorded, not minted here):** generic PII and GDPR handling is canon and
owned by `/gsd-secure-phase`; the undocumented `tm` TXT key non-disclosure is already owned
by the `tm` assertion in `test_phase_contract.py`; documentation-safe example addresses are
owned by `test_discovery_surfaces_use_only_documentation_safe_addresses`; mDNS speed claims
are owned by `test_public_docs_make_no_mdns_speed_claims`.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                        |
|--------------------|-------|------|--------|----------------------------------------------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Four named defects, each located in code     |
| Boundary Clarity   | 0.90  | 0.70 | ✓      | Six explicit out-of-scope items with reasons |
| Constraint Clarity | 0.78  | 0.65 | ✓      | Contract-test coupling is the binding one    |
| Acceptance Criteria| 0.88  | 0.70 | ✓      | 20 positive plus 7 negative checkboxes       |
| **Ambiguity**      | 0.13  | ≤0.20| ✓      |                                              |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective     | Question summary                                  | Decision locked                                                                 |
|-------|-----------------|---------------------------------------------------|---------------------------------------------------------------------------------|
| 1     | Researcher      | TEST-01 scope: one module or the whole package?   | Whole `test_mdns` package, later widened in round 3                              |
| 1     | Researcher      | MDNS-09 breadth: one call site or the cache?      | Fix `selected_address_for()` plus a cache-wide owner-form invariant test         |
| 1     | Researcher      | Which surfaces carry the DOCS-08 prose?           | Docstring, `discovery.md`, migration page and quickstart                         |
| 2     | Simplifier      | How far does the DOCS-08 contract enforcement go? | Swap both phrase lists and add a repo-wide negative assertion                    |
| 2     | Researcher      | What does aligning caching guidance mean?         | Move the bullet and add a third derived-not-cached category to `AGENTS.md`       |
| 2     | Boundary Keeper | Which adjacent temptations are out of scope?      | Em dashes (Phase 20), the IPv6 probe (Phase 17), and retuning any timing constant |
| 3     | Boundary Keeper | Repo-wide import sweep versus phase parallelism   | Sweep all of `tests/` except Phase 18 and Phase 19 territory: 183 in 28 files    |
| 3     | Failure Analyst | What proof does the MDNS-09 regression owe?       | A named regression test alone, no scratch-tree revert evidence required          |
| 3     | Seed Closer     | When do issues #213, #215, #216, #217 close?      | Closed by the merge commit through `Closes` lines in the PR body                 |
| 4     | Failure Analyst | Edge probe: 15 applicable edges                   | 11 explicit, 1 backstop, 3 dismissed with reasons, 0 unresolved                  |
| 4     | Failure Analyst | Prohibition probe: 7 bespoke must-NOTs            | All 7 resolved: 4 test tier, 3 judgment tier, descriptors deliberately empty     |

---

*Phase: 16-mdns-correctness-docs-and-test-hygiene*
*Spec created: 2026-09-07*
*Next step: /gsd-discuss-phase 16, which covers implementation decisions: how to build what is specified above*
