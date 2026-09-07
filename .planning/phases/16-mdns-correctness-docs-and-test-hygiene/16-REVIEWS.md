---
phase: 16
reviewers: [codex, antigravity, opencode]
reviewed_at: 2026-09-07T15:09:00+10:00
plans_reviewed: [16-01-PLAN.md, 16-02-PLAN.md, 16-03-PLAN.md, 16-04-PLAN.md]
models:
  codex: "gpt-5.6-sol (reasoning=high)"
  antigravity: "gemini-3.1-pro-high"
  opencode: "openrouter/z-ai/glm-5.3 (reasoning=high)"
model_sources:
  codex: "pinned"
  antigravity: "pinned"
  opencode: "pinned"
---

# Cross-AI Plan Review — Phase 16

> **Provenance.** Codex and Antigravity ran in the first pass. OpenCode's lane failed twice —
> it auto-rejects its own `external_directory` permission requests when run non-interactively
> (stdin-piped, `--format json`, no TTY), first for a malformed worktree path and then for its
> own `/tmp/opencode/*` scratch directory. On operator instruction it was re-run with OpenCode's
> `--auto` flag, invoked directly rather than through the GSD lane runner (whose argv template has
> no slot for that flag), using the byte-identical prompt — same SHA, same model, same variant,
> same cwd. Its review below is from that third run and is directly comparable with the other two.

## Codex Review

# Cross-AI Plan Review — Phase 16

## Overall assessment

The phase is well decomposed and the measured Ruff inventory is accurate, but the plans are not ready to execute unchanged. Plan 16-01 has two correctness holes at the exact boundary it is meant to repair, Plan 16-02 would publish an incorrect statement about which discovery leg performs unicast verification, and Plan 16-04 has a Python 3.10 import contradiction plus several false-green verification commands.

**Overall risk: HIGH until those blockers are corrected.**

Repository checks performed:

- Current branch is clean at `f34ede8`.
- Existing documentation contracts: 31 passed.
- Existing repository Ruff check: passed.
- Authoritative `PLC0415` count: 322 total; 189 under `tests/`; 166 in scope across 27 files; 23 in the three deferred paths.
- The seven proposed Ruff ignore patterns match their intended paths.

## Plan 16-01 — MDNS-09

### Summary

The plan correctly identifies the trailing-dot guard bypass and sensibly centralises the fail-closed predicate. However, its private delegate does not actually prevent double-normalisation, and its empty-owner test cannot detect a cached DNS-root owner. Both issues contradict explicit must-haves and the threat model.

### Strengths

- The underlying defect is real: cached owners use `_normalise_dns_name()` while `selected_address_for()` currently uses `.lower()`, allowing guard-key and lookup-key divergence. See [discovery.py:144](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/discovery.py:144>) and [discovery.py:348](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/discovery.py:348>).
- Extracting one unusable-owner predicate for selection and `pending_targets()` is structurally sound. The current duplicate block is visible at [discovery.py:810](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/discovery.py:810>).
- The existing suite already exercises owner overflow through both selection and pending-target paths at [test_discovery.py:3113](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/tests/test_network/test_mdns/test_discovery.py:3113>). Adding address-budget and byte-incomplete cases meaningfully improves equivalence coverage.
- Synthetic identifiers and documentation-safe addresses are used consistently.

### Concerns

- **HIGH — The proposed delegate still double-normalises.** The plan says `_selected_address_for_normalised()` will call `_addresses_in_order(owner)` [16-01-PLAN.md:172](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-01-PLAN.md:172>). But `_addresses_in_order()` calls `records_for()`, which normalises again at [discovery.py:320](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/discovery.py:320>) and [discovery.py:335](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/discovery.py:335>). `_resolve_srv_endpoint()` has already normalised the target at [discovery.py:643](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/discovery.py:643>). Thus the split does not provide the invariant claimed by T-16-04. A `host.local..` target remains permanently pending because the cache key is `host.local.` while the subsequent lookup becomes `host.local`.
- **HIGH — The empty/root acceptance test is insufficient.** DNS parsing represents the root as `"."` [dns.py:200](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/dns.py:200>), while cache ingestion normalises and admits address owners without rejecting the empty result [discovery.py:400](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/discovery.py:400>) and [discovery.py:467](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/discovery.py:467>). I reproduced a cached `"."` A record causing both `selected_address_for("")` and `selected_address_for(".")` to return `192.0.2.42`. The planned test only places an unrelated real owner in the cache [16-01-PLAN.md:322](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-01-PLAN.md:322>), so it passes without enforcing the required fail-closed behaviour.
- **MEDIUM — The casefold test does not explicitly fire a keyed guard.** A successful lookup can pass even if the guard still uses `.lower()`, because `records_for()` independently casefolds. The test must place the casefold-sensitive owner into an overflow or byte-incomplete guard set through public ingestion.
- **MEDIUM — The byte-incomplete AAAA recipe is underspecified.** Parsed AAAA records normally have exactly 16 bytes [dns.py:283](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/dns.py:283>). Exercising an oversized AAAA cache entry therefore requires a deliberately inconsistent defensive `DnsResourceRecord`, not merely adapting `_address_record()`.

### Suggestions

- Introduce normalised-only record/address helpers, for example `_records_for_normalised()` and `_addresses_in_order_normalised()`. Public lookups normalise once and delegate; internal paths call the normalised-only variants.
- Add `not owner` to the shared unusable-owner predicate and test against an actually cached root-owner address record.
- Make the casefold-sensitive test trigger an owner-keyed fail-closed guard.
- Parameterise the byte-incomplete pending-target case across A and AAAA, and document that it exercises a defensive post-parser seam.

### Risk assessment

**HIGH.** The main abstraction does not provide the normalisation property claimed, and an explicit empty-owner acceptance criterion remains false under reachable cache state.

## Plan 16-02 — DOCS-08

### Summary

The atomic prose-and-contract update is carefully designed, and the new repository-wide language contract is appropriately placed. One proposed sentence is nevertheless factually wrong about the discovery architecture and would undermine the caller-facing correctness goal.

### Strengths

- The simultaneity constraint is real and correctly handled. The old phrase is required at [test_phase_contract.py:121](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/tests/test_network/test_mdns/test_phase_contract.py:121>) and forbidden on another surface at [test_phase_contract.py:392](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/tests/test_network/test_mdns/test_phase_contract.py:392>). Plan 16-02 explicitly puts both phrase lists and both prose removals in one commit [16-02-PLAN.md:171](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-02-PLAN.md:171>).
- Dropping the synthetic-scale claim instead of replacing it with another non-actionable claim is appropriate.
- A plain default-suite `tests/test_docs_language.py` is the right home for a `src/` plus `docs/` language contract.
- The migration and quick-start pages currently contain no conflicting synthetic-proof jargon. Their audit-only treatment is therefore reasonable.

### Concerns

- **HIGH — The plan attributes unicast verification to the wrong leg.** It instructs the guide to recommend `discover()`, “whose UDP leg is unicast-verified” [16-02-PLAN.md:184](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-02-PLAN.md:184>). In the implementation, the UDP leg consumes `discover_devices_shared()` results directly [api.py:1112](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/api.py:1112>). It is the mDNS leg that calls `_discover_verified_devices_mdns()` [api.py:1125](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/api.py:1125>), whose candidate path sends a correlated Light/GetColor or Echo request [discovery.py:1361](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/discovery/mdns/discovery.py:1361>). This should say that `discover()` verifies mDNS candidates with a device request, not that its UDP leg is unicast-verified.
- **MEDIUM — The approved fragments would not catch that false clause.** The planned locks cover advertisements and the next action, but not which `discover()` leg performs verification. The contract could remain green while the architectural error is published.

### Suggestions

- Replace the clause with wording such as: “Confirm reachability with a request, or use `discover()`, whose mDNS candidates must answer a correlated device request before they are yielded.”
- Add a distinctive fragment that locks the verified-mDNS mechanism, or add a small negative assertion forbidding “UDP leg is unicast-verified”.
- Keep the current single-commit grouping unchanged.

### Risk assessment

**HIGH as written; LOW after the wording correction.** The implementation work is low risk, but the explicit prose currently misstates a security-relevant reachability mechanism.

## Plan 16-03 — DOCS-07

### Summary

This is the strongest plan. It correctly identifies `connectivity` as derived rather than state-backed, uses suitable contract-test homes, and avoids runtime changes. Only the proposed repository wording needs greater precision.

### Strengths

- The current misplaced bullet is clear at [advanced-usage.md:135](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/docs/user-guide/advanced-usage.md:135>).
- The property performs a fresh read of `connection.thread_connection` on every access and otherwise returns construction metadata [base.py:2304](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/devices/base.py:2304>).
- `AGENTS.md` currently has only cached and never-cached categories [AGENTS.md:347](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/AGENTS.md:347>), so adding a third category resolves a genuine classification gap.
- Splitting tests by asserted file matches the existing ownership: `tests/test_repository_guidance.py` already owns the canonical `AGENTS.md` markers [test_repository_guidance.py:24](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/tests/test_repository_guidance.py:24>).

### Concerns

- **MEDIUM — “Most recent request outcome” is broader than the implementation.** Timeouts, connection failures and uncorrelated replies are request outcomes but do not update the value. `_thread_connection` is written only after correlation validation [connection.py:1075](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/src/lifx/network/connection.py:1075>), and the latest correlated response wins [test_connection_connectivity.py:119](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/tests/test_network/test_connection_connectivity.py:119>).
- **LOW — The planned marker test is not explicitly scoped to the `### State Caching` section.** Searching category markers globally could continue to pass if a bullet drifts outside the section.

### Suggestions

- Describe `connectivity` as recomputed from the latest correlated frame-address observation when present, otherwise from construction/discovery metadata.
- Slice `AGENTS.md` from `### State Caching` to the next same-or-higher-level heading before finding and counting category bullets.

### Risk assessment

**LOW.** The work is documentation and tests only, and the required adjustment is wording precision rather than a design change.

## Plan 16-04 — TEST-01

### Summary

The measured scope and seven-ignore design are correct, and the two-commit ordering is sensible. The plan needs changes for Python 3.10 compatibility and verification robustness before a 166-import mechanical rewrite is safe.

### Strengths

- The inventory is accurate: 166 in-scope violations across 27 files, plus 23 violations in the three deferred paths.
- The two extra archived-spike paths are genuine tracked violations, including [probe.py:374](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/.agents/skills/spike-findings-lifx-async/sources/001-modem-sleep-keepalive/probe.py:374>).
- All seven proposed per-file-ignore patterns work with Ruff’s `--stdin-filename`; the positive in-scope path reports `PLC0415`, while every ignored path suppresses it.
- Landing the mechanical sweep before enabling the rule avoids a deliberately red intermediate commit.
- `tests/conftest.py` really does establish `measurement_support` before test-module import [tests/conftest.py:40](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/tests/conftest.py:40>).

### Concerns

- **HIGH — `tests/test_packaging.py` conflicts with the retained-import policy.** Its local `tomllib` import occurs after a Python 3.10 skip because `tomllib` is unavailable there [test_packaging.py:23](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/tests/test_packaging.py:23>). The plan permits optional/version-gated imports in Step 3, but Step 4 permits reason-bearing retention only for circular-import or patching constraints [16-04-PLAN.md:224](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-04-PLAN.md:224>). Hoisting `tomllib` breaks Python 3.10 collection; retaining it violates the stated permitted set.
- **HIGH — The decisive Task 1 Ruff check can pass on tool failure.** Its command captures Ruff output, discards Ruff’s exit status and succeeds whenever zero `PLC0415` strings are found [16-04-PLAN.md:276](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-04-PLAN.md:276>). I reproduced an unwritable `uv` cache error yielding `in-scope-plc0415=0` and overall exit 0.
- **MEDIUM — The seven-ignore negative control can also pass on invocation failure.** Each command uses `|| true` and treats absence of `PLC0415` as success [16-04-PLAN.md:384](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-04-PLAN.md:384>). The positive control is non-vacuous because it requires the diagnostic; the negative control is not.
- **MEDIUM — The collection floor does not prove “no reduction”.** The live command collects 4,256 default node IDs, but the plan accepts anything at or above 2,400 [16-04-PLAN.md:284](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-04-PLAN.md:284>). Losing one or hundreds of tests could pass.
- **MEDIUM — The backstop’s stated conclusion is reversed.** A targeted run under `tests/` loads `tests/conftest.py`, whose explicit purpose is to insert `.planning/scripts` before importing `test_connection_retry.py` [tests/conftest.py:40](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/tests/conftest.py:40>). It proves independence from `.planning/scripts/tests/conftest.py`, not independence from `tests/conftest.py`.
- **LOW — Repository-wide autoformat commands are broader than the locked sweep.** `ruff check . --fix` and `ruff format .` could modify an excluded or zero-violation file if unrelated formatting drift exists.

### Suggestions

- Replace the version-gated local import with a module-scope compatibility import:
  `try: import tomllib; except ModuleNotFoundError: import tomli as tomllib`.
  `tomli` is already a Python 3.10 development dependency at [pyproject.toml:57](</Volumes/External/Developer/Djelibeybi/lifx-async/.claude/worktrees/gsd-spec-phase-16-8ef55e/pyproject.toml:57>). Then remove the skip and gain Python 3.10 coverage.
- Capture and assert every Ruff process exit status. For ignored-path probes, require exit 0 and preferably Ruff’s successful result, rather than merely the absence of `PLC0415`.
- Save the pre-sweep collected node-ID set and fail if any node ID disappears afterwards.
- Correct the backstop wording to say it proves the targeted run does not depend on the tooling conftest loaded through `testpaths`.
- Run auto-fix and formatting over the authoritative 27-file inventory, followed by repository-wide check-only commands.

### Risk assessment

**MEDIUM-HIGH.** The ignore shape is correct, but the current execution instructions force an unresolved Python 3.10 exception and allow key verification gates to report false success.

## Required replanning changes

Before execution:

1. Repair Plan 16-01’s normalised lookup chain and add an adversarial cached-root test.
2. Correct Plan 16-02 so verification is attributed to the mDNS leg.
3. Resolve `test_packaging.py` with the existing `tomli` compatibility dependency.
4. Make all Ruff probes fail closed and compare collected node IDs against the actual parent set.
5. Tighten the Plan 16-01 casefold test so it exercises a keyed fail-closed guard.

With those changes, the phase topology and scope boundaries are otherwise strong.


---

## OpenCode Review

# Cross-AI Plan Review — Phase 16 (lifx-async)

**Verification method:** every decisive claim below was checked against the working tree — source read at cited lines, ruff measurements re-run with `--no-cache`, and the noqa behaviour reproduced empirically against the pinned ruff. Line references are from this checkout.

---

## Plan 16-01 (MDNS-09, Wave 1)

### Summary
Exceptionally well-grounded plan. The defect, the non-idempotence hazard, the two internal call sites, and the D-04 residual analysis are all accurate against the source. The public/private split (D-01) is the correct fix for the double-normalisation trap. One test-constructability risk in Task 2 deserves attention before execution.

### Strengths
- **Defect claims verified exactly.** `selected_address_for()` uses `owner.lower()` while guards are keyed by `_normalise_dns_name()` (discovery.py:350 vs :400); `_normalise_dns_name()` (discovery.py:144-148) strips exactly one dot — non-idempotent, as claimed.
- **No caller missed.** Grep confirms exactly two internal `self.selected_address_for(` sites (discovery.py:788, :845), both receiving a target normalised once at :659 via `_resolve_srv_endpoint`. The delegate design provably prevents double-normalisation on the internal path.
- **The 16-PATTERNS.md "false negative" resolution is correct.** I traced the suite: the per-owner-overflow term's true arc through `pending_targets()` is genuinely covered (ingest recipe at test_discovery.py:3113-3145, assertion `pending_targets() == []` at :3145); the false arc at :3794/:3848; and the claimed early exits at :3324 (instance-level SRV byte-incomplete, :829) and :3384 (retained-payload early return, :819-820) both hold. The remaining-term analysis (`_address_budget_exhausted`, byte-incomplete keyed on *target*) is accurate — nothing in the existing suite drives those through `pending_targets()`.
- **Branch-coverage story is sound.** Both arcs of the delegate's guard `if` are driven (regression test True, matrix False); both arcs of the changed `pending_targets()` line are covered (existing + new tests). `_owner_is_unusable` is a single return expression, not a branch statement, so the 100% branch patch gate on the changed `src/` range is achievable as claimed.
- The five-condition predicate is a term-for-term move of :351-357, and the retained-payload term's unreachability inside the `pending_targets()` loop (early return at :819-820) is verified in source.

### Concerns
- **MEDIUM — Task 2's `pending_targets()` term-2 test can pass for the wrong reason.** `assert cache.pending_targets() == []` is branch-agnostic: it is empty both when the target guard fires *and* when the method exits earlier (e.g., at :829). The plan's recipe ("`_srv_with_retained_cost`-style oversized-record recipe applied to an address record") underspecifies the construction: for A/AAAA, `_retained_payload_cost` is `len(name) + len(rdata) + 4 + packed_len`, and the standard `_address_record` helper (test_discovery.py:98-108) fixes rdata to the 4/16-byte packed address. If the executor instead lengthens the *owner name* to exceed the 4096-byte record cap, the SRV carrying that target also exceeds the cap (`_retained_payload_cost` for SRV includes the target twice — in rdata and in parsed cost), the *instance* becomes byte-incomplete, and `pending_targets()` exits at :829 for the wrong reason — test green, intended branch never executed. The correct construction (oversized `rdata` bytes with a valid `parsed_data` string, which `_add_record` does not cross-validate, discovery.py:401-419) is possible but not spelled out.
- **LOW — residual not acknowledged.** After D-01, a double-trailing-dot owner (`"host.."`) still reaches guards keyed `"host."` while `records_for` resolves to `"host"` — the bare/single-dot invariant the SPEC demands holds, but the plan's invariant matrix deliberately excludes multi-dot forms. Fine under D-02, but the summary should record this residual so a verifier doesn't read the invariant as universal over all dot forms.

### Suggestions
- Pin the exercised branch in `test_pending_targets_refuses_a_target_the_address_guards_reject` by additionally asserting the public `rejection_counts` evidence (e.g., `("record_byte_capacity", "AAAA")` for term 2, the sweep-budget rejection for term 1), mirroring how `TestLifxRecordCacheByteBounds` already pins outcomes. This keeps D-04's no-private-helper boundary while making the empty-list assertion branch-specific.
- Spell out in the action that the byte-incomplete AAAA must be built with oversized `rdata` and a normal-length owner name (or extend `_address_record` with an `identity=` kwarg like `_srv_record` has).

---

## Plan 16-02 (DOCS-08, Wave 2)

### Summary
The simultaneity constraint is real and the plan expresses it atomically. All four prose surfaces, both phrase-list sites, and the satisfiability of the new repo-wide negative are verified against the tree. Low residual risk.

### Strengths
- **D-12 coupling verified.** The sentence is REQUIRED at test_phase_contract.py:130 (`approved_phrases`) and FORBIDDEN at :395 (`_MOVED_MDNS_LIMITATION_PHRASES`), exactly as claimed. The single-commit action covering `api.py` + `discovery.md` + `test_phase_contract.py` is the correct atomic shape; the verify gate `SIMULTANEITY-HELD` checks all three files in one commit.
- **The repo-wide negative is satisfiable.** Grep over `src/` and `docs/` for `mesh scale|proven synthetically` finds only `src/lifx/api.py` and `docs/user-guide/discovery.md` — both edited by Task 1. No hidden third site will break `tests/test_docs_language.py`.
- **`_REQUIRED_QUERY_MODEL_PATHS` confirmed to include `docs/getting-started/quickstart.md`** (test_phase_contract.py:31-34), so the plan's warning about keeping the query-model assertions satisfiable when auditing quickstart is well-placed.
- Correctly declines `_normalised_prose()` for the walk test: the helper strips `#`-prefixed lines (:69), which under `src/**/*.py` would exempt Python comments — the raw-text choice is right and the reasoning is recorded.
- D-14's proxy prose and D-15's advice recast are specific enough to execute, and the four new approved-phrase fragments are short enough to survive Phase 20's em-dash recast (D-16's stated purpose).

### Concerns
- **LOW — fragment collisions unchecked.** The new `_MOVED_MDNS_LIMITATION_PHRASES` entry `advertises every device on its mesh` must be absent from `advanced-usage.md`; no current occurrence exists, but the plan doesn't gate it directly (it relies on the suite). Acceptable.
- **LOW — `tests/test_docs_language.py` created in wave 2, swept-adjacent in wave 3.** Plan 16-04's zero-violation-file gate would reject it if 16-04 touched it; 16-03/16-04 both mandate module-scope imports, so this is handled, but the cross-plan coupling is implicit rather than stated.

### Suggestions
- In the audit task, add the `tm` TXT-key constraint reminder: `quickstart.md` is in `_PUBLIC_PATHS` (checked by `test_public_docs_and_example_exclude_private_contract_tokens`, :104-119), so any edit there must not introduce the forbidden tokens. The read_first list covers the file but not this specific sibling contract.

---

## Plan 16-03 (DOCS-07, Wave 3)

### Summary
Small, precise, correctly split by assertion home. All structural claims verified: the bullet at advanced-usage.md:143-144, the first of two `##### Non-State Properties` headings at :146, the three-bullet `### State Caching` section at AGENTS.md:347-352, and the CLAUDE.md non-duplication tests exist as named (test_repository_guidance.py:50, :59).

### Strengths
- The two `##### Non-State Properties` headings trap is real and called out (advanced-usage.md:146 and :152) — the positional assertion uses the FIRST heading, correctly.
- The `exactly-one` category assertion as a count (not membership) genuinely fails both the zero and duplicate cases — the right contract shape (T-16-12).
- The verify regex `^- (Cached \(semi-static\)|\*\*Never cached\*\*|\*\*Derived, not cached\*\*)` matches the actual bullet formats at AGENTS.md:349-350 (mixed bold/non-bold), verified.
- `connectivity` currently appears nowhere in AGENTS.md, so the post-change "exactly one" assertion will hold.
- The em-dash gate uses the correct U+2014 UTF-8 sequence (`\342\200\224`).

### Concerns
- **MEDIUM — roadmap-criterion tension the plan doesn't surface.** Roadmap success criterion 2 says "no **repository or published guidance** lists it among the state-backed cached properties", but `docs/api/devices.md:343-352` carries a `### Connectivity` section under `## Device Properties` (the API reference). The SPEC scopes R2 to `advanced-usage.md` + `AGENTS.md`, so the plan matches the SPEC — but a verify pass reading the roadmap criterion could flag devices.md's placement, and the plan's only note is "do not touch". Similarly, AGENTS.md:343's generic "State Caching: Device properties cache values" bullet (Key Design Patterns) is untouched.
- **LOW** — the chosen third-category label `Derived, not cached` is fine, but the marker tuple in Task 2 must use the *delivered* leading substrings; the plan says markers are "written against the delivered text" in read_first. Handled.

### Suggestions
- Record in 16-03-SUMMARY.md an explicit judged-not-a-listing note for `docs/api/devices.md` (API reference section, not a caching claim) and AGENTS.md:343, so verify-phase has the disposition rather than discovering an apparent gap.
- The positional assertion in `test_connectivity_is_not_listed_among_the_state_backed_device_properties` (index of `#### Device Properties` → first `##### Non-State Properties` → next `#### `) is fragile if headings are reworded, but that fragility *is* the drift contract. Accept as-is.

---

## Plan 16-04 (TEST-01, Wave 3)

### Summary
The most empirical plan in the set, and its measurements reproduce exactly. The seven-entry ignore extension is justified, the noqa-form correction is empirically true against the pinned ruff, and the sequencing (sweep before enable) is sound. Two gate-level flaws need fixing before execution.

### Strengths
- **Every measurement reproduces.** `ruff check --no-cache --select PLC0415 .` → 322 total; 189 under `tests/`, 82 `src/`, 49 `.planning/`, 2 in the archived probes; in-scope (three paths excluded) → **exactly 166 violations across exactly 27 files**, with the per-file lead counts matching the plan verbatim (test_discovery.py 51, test_connection.py 19, test_discovery_errors.py 12, test_concurrent_requests.py 11). The `files_modified` list of 27 test files matches the measured inventory file-for-file.
- **The D-05 amendment is necessary, not gold-plating.** With five entries the repo-wide check reports 168; the two extra violations are in git-tracked archived spike harnesses (`.agents/skills/.../probe.py:374` and `.claude/skills/.../probe.py:374`, both confirmed on disk with the function-local `from lifx import discover`). The operator decision point is properly surfaced rather than applied silently.
- **The noqa correction is empirically verified.** I reproduced it: `# noqa: PLC0415: reason` → `warning: Invalid `# noqa` directive ... expected code to consist of uppercase letters followed by digits only` and the violation remains; `# noqa: PLC0415 - reason` → suppressed. 16-PATTERNS.md is indeed wrong and the plan is right to override it with the tested form.
- **Sequencing (D-08) is correct.** Sweep-first means no commit in history has `PLC0415` enabled with violations outstanding.
- **The control probes are not vacuous.** The positive probe greps for `PLC0415` in ruff's output on a synthetic in-scope path (fails if the rule misfires or ruff errors); the negative probe checks each of the seven ignore globs individually. Both run against the committed `pyproject.toml` with no `--select` override.
- **The backstop is real.** `tests/conftest.py:50-52` inserts `.planning/scripts` into `sys.path` at conftest import time (before any test module imports), and `tests/test_discovery_observation.py:19` already imports `measurement_support` at module scope — the pattern the retry-test hoist replicates is proven in-tree.
- Current `pyproject.toml:81` select is `["E", "F", "I", "N", "W", "UP"]` and the five `E501` per-file-ignores at :85-89 exist as described.

### Concerns
- **MEDIUM — self-contradicting gate on mention count.** The acceptance gate demands `grep -c "PLC0415" pyproject.toml == 8` (one select + seven ignores), while the action instructs adding a handoff comment "recording why each excluded path is a visible, deletable line" — a comment that will naturally name `PLC0415`, producing 9 mentions and failing the plan's own gate. Either the gate must say `>= 8`/`-eq 9`, or the comment must be written without naming the rule.
- **MEDIUM — the `SWEEP-SCOPE-OK` gate has a per-file ruff invocation flaw.** It pipes the parent-commit file content via `--stdin-filename "$f"` — but at Task 1 verify time `PLC0415` is not yet in `select`, so the explicit `--select PLC0415` is passed; that part is fine. The real flaw is subtler: `ruff check` on stdin content applies per-file-ignores from config, and a file like `tests/test_network/test_mdns/test_discovery.py` is in scope, so it works — but the loop runs 27+ sequential `uv run ruff` invocations, each paying interpreter startup; on a slow CI runner this gate alone may take minutes. Functional, but consider one batched invocation.
- **LOW — `ruff check . --fix` in Step 2 is repo-wide.** Safe today because the tree is lint-clean so only the swept files change, but a mid-flight unrelated lint failure would entangle unrelated fixes into the sweep commit. Scope the fix to the swept files (`ruff check <files> --fix`).
- **LOW — count drift.** The plan measures 166 now; 16-01 and 16-02 add test code before 16-04 executes. The plan explicitly handles this ("use the measured numbers and record the delta") — adequate.

### Suggestions
- Fix the mention-count gate (concern 1) — it is the one gate guaranteed to misfire as written.
- In Task 1's exception list, add the reverse of the backstop: an import whose *hoist* would change behaviour is a retained import, but so is one whose hoist would shadow a fixture-injected module attribute; the Step 3 list covers the common cases, so this is a wording addition only.

---

## Cross-Plan / Phase-Level

### Strengths
- Wave structure and dependencies are correct: 16-02 depends on 16-01 (patch gate must score a changed range first — 16-01 is the only plan touching `src/`), 16-03 and 16-04 are file-disjoint from each other (16-03's four files vs 16-04's 28; `test_phase_contract.py` is in 16-02/16-03 sequentially, never concurrently), and neither wave-3 plan touches the three Phase 18/19 paths.
- Every plan's file-disjointness gate (`FILE-DISJOINTNESS-HELD`) is mechanically checkable, and 16-01/16-02/16-03 include it too, not just the sweep plan.
- The SPEC's dismissals (R2 empty/ordering, R3 ordering) are carried into the plans' verification sections rather than dropped.

### Concerns
- **MEDIUM (aggregate) — the two MEDIUM test-constructability/gate items above** (16-01 Task 2 branch-pinning; 16-04 mention-count gate) are the only findings that could cause an executor or verifier to report false success. Everything else is LOW.
- **LOW — issue-closure mechanics.** SPEC says issues #213/#215/#216/#217 close "through `Closes` lines in the merge commit", but no plan's commits are a merge commit; the plans commit directly. The close action needs an owner (the phase ship step, presumably) or the issues linger.

---

## Risk Assessment

**Overall: LOW** (with two specific MEDIUM fixes recommended first).

Justification: this is the most thoroughly source-verified plan set I have reviewed — every file:line claim I checked (30+ across four plans) was accurate, including three non-obvious ones (the phrase-list coupling, the noqa colon-form rejection, and the 166/27-file inventory), all reproduced empirically. The design decisions (D-01's split, D-05's seven-entry extension, D-08's commit ordering, D-12's simultaneity) are each backed by a measured or traced mechanism rather than reasoning alone. The residual risks are: (1) the `pending_targets()` term-2 test passing via the wrong branch, (2) the `pyproject.toml` mention-count gate contradicting its own comment instruction, and (3) a verify-time dispute over `docs/api/devices.md` against the broader roadmap wording. All three are cheap to fix now and none blocks the phase goals if unfixed — but (1) and (2) should be fixed before execution, since both produce green gates that don't prove what they claim to prove, which is precisely the failure class this project's Phase 15 guard exists to catch.

---

## Antigravity Review

> **Note on this lane.** The adapter returned its structured review buried under roughly 390 lines
> of raw agent narration; only the structured review is reproduced below. It cited 8 `file:line`
> locations against Codex's 70 and OpenCode's 21. Its central strength claim — that the
> `selected_address_for()` split "perfectly shields the internal callers" — was checked against
> source during aggregation and is **wrong**: the other two lanes both identified a residual it
> denies outright. Its "foolproof / robust against vacuous passing" verdict on 16-04's gates is
> also contradicted by a verified defect in one of them. Down-weighted accordingly.

### 1. Summary
The Phase 16 plans (16-01 through 16-04) display exceptional structural precision and deep adherence to existing repository guarantees, privacy rules, and test-driven contracts. The plans successfully tackle mDNS fail-closed guard evasion (`MDNS-09`), misleading internal validation terminology (`DOCS-08`), inaccurate state caching categorizations (`DOCS-07`), and function-local import hygiene (`TEST-01`). Most impressively, the planner demonstrates high fidelity to test suite internals (identifying exact lines, logic nuances, and edge case coverage) and has implemented virtually foolproof verification boundaries that prevent regression or vacuous compliance. The split logic and verification gates correctly align with the actual state of `lifx-async`.

### 2. Strengths
- **Prevention of Double-Normalisation (`16-01-PLAN.md`):** The planner correctly identified that `_normalise_dns_name()` is NOT idempotent (as it strips exactly one trailing dot, meaning `"host.."` -> `"host."` -> `"host"`). The extraction of `_selected_address_for_normalised()` perfectly shields the internal callers at `src/lifx/network/discovery/mdns/discovery.py:788` and `845`. Both of those paths receive targets from `_resolve_srv_endpoint` (line `657`), which already applies normalisation. This split correctly fixes the fail-closed bypass while preventing cache misses on multi-trailing-dot addresses.
- **Equivalent Guard Behavior for `pending_targets()` (`16-01-PLAN.md`):** The extracted guard `_owner_is_unusable()` incorporates `self._retained_payload_budget_exhausted`. This is completely safe to share with `pending_targets()` at `discovery.py:845`. Line `819` of `pending_targets()` has an early return `if self._retained_payload_budget_exhausted: return targets`, ensuring that the loop body (where the shared guard is called) never evaluates that branch as true. The plan recognized this unreachable state (`T-16-02`), ensuring perfect behavioral equivalence without weakening either function.
- **Atomic Contract Updates (`16-02-PLAN.md`):** The `Mesh scale is proven synthetically.` requirement constraint (`D-12`) is handled meticulously. Because it's checked by a REQUIRED phrase assertion and a FORBIDDEN phrase assertion in `tests/test_network/test_mdns/test_phase_contract.py`, splitting the work would instantly break CI. Forcing Task 1 to commit both the prose removal and the two list updates simultaneously guarantees the suite remains green at all points in the git history.
- **Foolproof Lint Verification (`16-04-PLAN.md`):** The positive and negative control probes for `PLC0415` enforcement are robust against vacuous passing. The positive control uses `stdin` to inject a function-local import (`import os`) and asserts `grep -q PLC0415`, guaranteeing a failure if the rule isn't enforced. The negative control explicitly runs the same command against all 7 excluded paths and asserts no lint failures, ensuring none of the ignores are silently broken.
- **Accurate Pre-existing Issue Discovery (`16-04-PLAN.md`):** The planner rightly appended `.agents/skills/**` and `.claude/skills/**` to the 5 originally proposed ignores. A direct scan confirms that `probe.py:374` inside the archived spike folders contains `from lifx import discover`, validating the planner's necessity to expand to 7 exclusions without contaminating the measured tree.

### 3. Concerns
- **Coverage Tooling Blind Spot (LOW):** Plan 16-01 relies on `100% branch patch coverage`. Because the guard is extracted into `_owner_is_unusable()`, `coverage.py` tracks if the lines are hit *at least once* globally across the suite, not per-caller. While the plan adds targeted assertions for `pending_targets()` on the missing branches (address and byte boundaries), `coverage.py` would technically report 100% even if `pending_targets()` didn't hit them, since `selected_address_for()` already covers them. This is largely mitigated by the planner explicitly adding the tests anyway, but is an inherent limit of line-based coverage.
- **Residual Risk of Normalisation Overuse (LOW):** `_normalise_dns_name()` remains non-idempotent. While `selected_address_for()` correctly walls it off, future contributors might blindly wrap strings in `_normalise_dns_name()` elsewhere in the `discovery` module assuming it is a safe canonicalizer, potentially causing subtle cache misses.

### 4. Suggestions
- **Document Non-Idempotency:** Consider adding an explicit comment inside `_normalise_dns_name()` at `src/lifx/network/discovery/mdns/discovery.py:144` warning future developers that the function is strictly non-idempotent and should only be applied to raw wire data exactly once.
- **Safeguard Existing Lint Configs:** As verified by the plan's `grep -q "\"E501\""` step, when Plan 16-04 appends the 7 `PLC0415` per-file-ignores to `pyproject.toml`, ensure the implementation scripts do not accidentally wipe the existing `["E501"]` ignores for `generator.py`, `packets.py`, and `registry.py`.

### 5. Risk Assessment
**Overall Risk Level: LOW**

**Justification:** The plans exhibit a phenomenal understanding of the codebase and test suite constraints. The solutions proposed for the mDNS normalisation bug correctly identify internal data flows to avoid double-mutation. The documentation and linting fixes are designed to be atomic and use verifiable, non-vacuous gate checks. Cross-phase file-disjointness rules are strictly upheld. There are no risky rewrites, architectural shifts, or dependency updates, and all edge cases have been identified and preemptively mitigated.

---

## Consensus Summary

Three lanes, all source-grounded. **Codex** (70 citations) returned **HIGH** risk. **OpenCode**
(21 citations, empirical reproductions) returned **LOW with two MEDIUM fixes first**.
**Antigravity** (8 citations) returned **LOW**.

Where the lanes disagreed, the claims were re-verified against the working tree during aggregation
rather than resolved by majority. Every finding below carries its verification status.

### Agreed Strengths

All three lanes independently confirmed:

- **The defect is real and correctly diagnosed.** `selected_address_for()` guards on
  `owner.lower()` (`discovery.py:350`) while the cache is keyed by `_normalise_dns_name()`
  (`discovery.py:400`), which strips exactly one trailing dot and casefolds (`discovery.py:144`).
- **`_retained_payload_budget_exhausted` is provably unreachable inside `pending_targets()`'s
  loop** because of the early return at `discovery.py:819-820`, so sharing one predicate that
  includes that term is behaviour-preserving. All three lanes verified this independently. It is
  the strongest single piece of the phase.
- **D-12's simultaneity is correctly expressed as one atomic task.** The phrase is REQUIRED at
  `test_phase_contract.py:130` and FORBIDDEN at `:395`; the plan puts both phrase-list edits and
  both prose removals in one commit.
- **The 166-across-27 inventory is exact.** Codex and OpenCode each re-ran ruff independently and
  reproduced 322 total / 189 under `tests/` / 82 `src/` / 49 `.planning/` / 2 archived, and the
  per-file lead counts match the plan verbatim. OpenCode initially measured 28 files, rechecked,
  and confirmed 27.
- **The seven-entry ignore extension is necessary, not gold-plating**, and the two extra paths are
  genuine tracked violations.
- **The `noqa` form correction is empirically right.** OpenCode reproduced it: `# noqa: PLC0415: reason`
  is rejected as an invalid directive and leaves the violation live; `# noqa: PLC0415 - reason`
  suppresses. `16-PATTERNS.md` is wrong and the plan is right to override it.
- **Plan 16-03 is the cleanest plan** — documentation and tests only, correct contract-test homes.

### Agreed Concerns

- **The `_normalise_dns_name()` non-idempotence residual survives the fix.** Raised by all three,
  at three different severities — see Divergent Views.
- **16-04's gates can report success without proving what they claim.** Codex and OpenCode both
  landed here, on different gates; both are verified real.

### Divergent Views

**1. The double-normalisation residual — the central disagreement, now settled.**

All three lanes describe the same mechanism; they disagree on severity and scope. Codex called it
**HIGH** ("the split does not provide the invariant claimed by T-16-04"). OpenCode called it
**LOW** ("the bare/single-dot invariant the SPEC demands holds"). Antigravity denied it exists
("perfectly shields the internal callers").

Verified against source and SPEC during aggregation. **Both Codex and OpenCode are partly right;
Antigravity is wrong.**

The chain is real: `selected_address_for()` → `_addresses_in_order()` (`discovery.py:359`) →
`records_for()` (`discovery.py:338`) → `_normalise_dns_name(owner)` (`discovery.py:320`). The
delegate *does* re-apply the helper, inside its own call chain.

But the consequence depends on the input:

- **Single trailing dot** (`host.local.`) — the re-application is a **no-op**, because
  `_normalise_dns_name` is idempotent on an already-normalised value. Guard key and lookup key
  agree. **The SPEC's demanded invariant holds.** SPEC R1's acceptance criteria and its three
  `## Edge Coverage` rows cover only "bare, trailing-dot, uppercase and mixed-case" — multi-dot
  is never demanded. OpenCode is right that no acceptance criterion fails.
- **Two or more trailing dots** (`host.local..`) — `:659` normalises once to `host.local.`, the
  guard uses that key, and the lookup normalises again to `host.local` and misses. Guard and
  lookup diverge. Codex is right that the mechanism is live.

**The actual defect is a false claim, not a failed criterion.** Plan 16-01's threat model states
of T-16-04: *"Mitigated by construction, not by test: the private delegate never re-applies the
non-idempotent helper."* That sentence is **false** — the delegate re-applies it via
`records_for()`. So T-16-04 asserts a mitigation the design does not deliver, and D-02's decision
to leave `_normalise_dns_name()` alone means the multi-dot residual is permanent and undocumented.

**Adjudicated severity: MEDIUM.** Below Codex's HIGH, because no SPEC acceptance criterion fails
and the naive-fix failure mode D-01 warns about is not reintroduced for any SPEC-covered form.
Above OpenCode's LOW, because the plan's own threat model records a mitigation that does not
exist, and a verifier reading T-16-04 would conclude the invariant is universal over dot forms.
The proportionate fix is OpenCode's: correct T-16-04's wording and record the multi-dot residual
explicitly, rather than Codex's larger normalised-only-internals refactor — unless you want the
multi-dot case actually closed, which is a scope decision, not a defect fix.

**2. Are 16-04's control probes vacuous?** Codex says the negative control at `:384` can pass on
invocation failure; OpenCode says "the control probes are not vacuous"; Antigravity calls them
"foolproof". Partially settled: the two lanes were reading different commands. Codex's HIGH is
about the Task 1 sweep check at `:276`, which OpenCode never examined — and that one is
**confirmed defective** (below). The dispute over `:384` specifically is unresolved and low-stakes;
OpenCode's own note that the positive probe "currently passes vacuously because `PLC0415` isn't in
`select` yet" cuts against Antigravity's "foolproof" framing either way.

### Verified during aggregation

Checked directly against the tree. All confirmed real:

1. **`16-04-PLAN.md:276` never checks ruff's exit status.** It captures `O=$(uv run … 2>&1)` with
   no `S=$?` and no exit test, so a ruff that fails to run yields `in-scope-plc0415=0` and passes.
   Codex reproduced this with an unwritable `uv` cache. This is the phase's decisive sweep gate.
   *(Codex only.)*
2. **`16-04`'s mention-count gate is guaranteed to misfire.** `:388` demands exactly 8 occurrences
   of `PLC0415` in `pyproject.toml`, while the action at `:64` specifies a handoff comment whose
   own text names `` `PLC0415` `` — a 9th mention. The gate fails on correct work.
   *(OpenCode only — neither other lane caught it.)*
3. **16-02 would publish a false statement.** The plan has the guide say `discover()`'s "UDP leg is
   unicast-verified" (`:188`, repeated in T-16-06 at `:420`). Per `api.py:1112` the UDP leg
   consumes `discover_devices_shared()` directly with no verification; it is the **mDNS** leg that
   calls `_discover_verified_devices_mdns()`. The claim is backwards, and the approved-phrase set
   would not catch it, so the contract stays green while the wrong claim ships. *(Codex only.)*
4. **Empty / DNS-root owner is reachable.** `'.'` and `''` both normalise to `''`, and no guard
   rejects an empty owner, so a cached root-owner address record is returned by both
   `selected_address_for('')` and `selected_address_for('.')`. 16-01's empty-owner test seeds only
   an unrelated owner, so it passes without enforcing the behaviour it claims. *(Codex only.)*
5. **`test_packaging.py` conflicts with the retained-import policy.** It skips below Python 3.11 at
   `:24` then imports `tomllib` function-locally at `:27`. Hoisting bare `tomllib` breaks 3.10
   collection; retaining it needs a `noqa` whose reason is neither circular-import nor patching,
   which D-06/D-07's permitted set does not cover. The fix is an improvement, not a workaround:
   `tomli>=2.0.1 ; python_full_version < '3.11'` is already a dev dependency at `pyproject.toml:57`,
   so a module-scope `try/except` removes the skip and *gains* 3.10 coverage. *(Codex only.)*

### Single-lane findings not independently verified

Reported by one lane, plausible, not checked during aggregation:

- **16-01 Task 2's `pending_targets()` term-2 test can pass via the wrong branch.**
  `assert cache.pending_targets() == []` is branch-agnostic — empty both when the target guard
  fires and when the method exits earlier at `:829`. OpenCode gives a concrete wrong-construction
  path and a fix (assert `rejection_counts` evidence to pin the branch). *(OpenCode.)*
- **Issue closure has no owner.** The SPEC says #213/#215/#216/#217 close via `Closes` lines in the
  merge commit, but no plan produces a merge commit — the plans commit directly. *(OpenCode.)*
- **`docs/api/devices.md:343-352` carries a `### Connectivity` section** under `## Device
  Properties`. The SPEC scopes R2 to `advanced-usage.md` + `AGENTS.md`, so the plan matches the
  SPEC, but roadmap criterion 2 says "no repository **or published guidance**", so a verifier could
  flag it. Worth a recorded disposition. *(OpenCode.)*
- **16-04's `SWEEP-SCOPE-OK` gate runs 27+ sequential `uv run ruff` invocations**, each paying
  interpreter startup — functional but slow on CI. *(OpenCode.)*
- **16-03's "most recent request outcome" is broader than the implementation.**
  `_thread_connection` is written only after correlation validation (`connection.py:1075`).
  *(Codex.)*

### Fix before execution

Ordered by consequence:

1. **`16-04:276` — assert ruff's exit status.** Verified; this gate can green a sweep that never ran.
2. **`16-04:388` / `:64` — reconcile the mention-count gate with the handoff comment.** Verified;
   misfires on correct work.
3. **`16-02:188` and `:420` — correct the verification attribution to the mDNS leg.** Verified;
   otherwise the phase publishes a false statement about a reachability mechanism.
4. **`16-01` T-16-04 — correct the threat-model wording and record the multi-dot residual.**
   Verified; the stated mitigation does not exist.
5. **`16-01` — add `not owner` to the shared predicate and seed the empty-owner test with an
   actually cached root-owner record.** Verified.
6. **`16-04` — resolve `test_packaging.py` via the module-scope `tomli` fallback.** Verified.
7. **`16-01` Task 2 — pin the exercised branch** with `rejection_counts` evidence.
8. **`16-04` — compare collected node-ID sets rather than a 2400 floor** when the tree collects 4256.

### Overall

**Risk: MEDIUM.** Two of three lanes rate the phase LOW once specific gate fixes land, and the
aggregation supports that over Codex's HIGH: no SPEC acceptance criterion fails, the topology,
scope boundaries, file-disjointness, decision coverage and commit shaping are sound, and every
lane praised the measurement discipline. But six verified defects remain, and three of them
(items 1-3) produce green gates or published prose that do not match reality — the failure class
this project's Phase 15 vacuous-gate guard exists to catch. These are replanning changes, not
execution-time adjustments.
