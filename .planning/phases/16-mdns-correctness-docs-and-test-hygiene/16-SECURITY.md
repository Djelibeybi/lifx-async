---
phase: "16"
slug: "mdns-correctness-docs-and-test-hygiene"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-07"
---

# Phase 16 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register origin: `register_authored_at_plan_time: true`. All four PLAN.md files carried a
parseable `<threat_model>` block, so the auditor verified declared mitigations rather than
building a register retroactively. No SUMMARY.md carried a `## Threat Flags` section, so
nothing was added at execution time.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| mDNS responder to `_LifxRecordCache` | Untrusted DNS wire data crosses here. Owner names, SRV targets and address records arrive from any host on the local link, including a Thread border router answering for devices it does not own. | Owner names, SRV targets, A/AAAA records |
| `_LifxRecordCache` to caller (`discover_mdns()`, `find_by_*`) | A selected address becomes a socket destination. A wrong answer here directs traffic at a host the cache never validated. | Socket destination addresses |
| Published documentation to caller behaviour | A caller sizes timeouts, retry policy and reachability conclusions from this prose. Prose that overclaims what a bounded sweep or a border-router advertisement establishes leads a caller to treat an mDNS result as proof of reachability. | Reachability claims, timing guidance |
| `AGENTS.md` to every downstream agent | `AGENTS.md` is the canonical shared guidance agents act on. A caching model with no home for a real property leaves an agent to guess. | Property classification guidance |
| `AGENTS.md` to `CLAUDE.md` | `CLAUDE.md` is a literal `@AGENTS.md` import only. Duplicating shared architecture guidance into it breaks the canonical-source contract. | Architecture guidance |
| Repository lint configuration to every future contribution | A rule that is configured but not enforced, or enforced but silently ignored over an in-scope path, gives false assurance to every later change. | Lint enforcement coverage |
| Test-collection order to module-scope imports | Hoisting an import changes when it runs relative to conftest setup, `sys.path` mutation and patching. A relocation that silently changes what a test exercises is a weakened test wearing a green tick. | Test binding and patch targets |
| Excluded lint paths to Phases 18 and 19 | The per-file-ignore entries preserve the locked v2.1 file-disjointness property. Touching an excluded path, or hiding the exclusion, breaks a cross-phase guarantee. | Phase boundary contract |
| Committed artefacts to git history | The AGENTS.md privacy rule binds here. A real serial, MAC, IP or hostname committed once persists in history. | Hardware and network identifiers |
| Generated artefact (`docs/changelog.md`) to repository contract | The release workflow owns that file. A contract that walks it would force a hand edit to a generated artefact. | Release-generated content |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-16-01 | Spoofing | `selected_address_for()` owner argument | high | mitigate | `discovery.py:389-398` routes the public entry point through `_normalise_dns_name()` so the guard set and the record lookup key on one identity. Proven load-bearing: HEAD's `TestLifxRecordCacheOwnerNormalisation` run against pre-fix source in a detached worktree gives 3 failed / 6 passed; 8/8 at HEAD. | closed |
| T-16-01b | Spoofing | Empty and DNS-root owner names | high | mitigate | `not owner` is the first term of `_owner_is_unusable()` (`discovery.py:362-369`). `test_empty_and_root_owners_are_refused_even_when_an_address_is_cached` fails against pre-fix source, proving the refusal is the guard rather than record absence. | closed |
| T-16-02 | Tampering | `_owner_is_unusable()` extraction | high | mitigate | Term-for-term diff of base against HEAD: base carried 5 terms in `selected_address_for` and 4 in the `pending_targets` loop; HEAD's predicate carries all 5 plus `not owner`. No term dropped or weakened. `pending_targets()` calls it at `:883`; the retained-payload term is genuinely unreachable there because of the early return at `:861-862`. | closed |
| T-16-03 | Information disclosure | New test fixtures and diagnostic text | medium | mitigate | The phase diff over `src/` adds zero logging, exception and raise lines; `count_rejection()` keys stay `(reason, record_type)` pairs (`discovery.py:322-324`). Diff scan of added lines: zero serials, zero MAC literals. See note 1 below, which narrows the mitigation plan's stated enforcement claim. | closed |
| T-16-04 | Denial of service | Permanent pending-target loop | medium | mitigate (partial, residual accepted) | Both internal callers reach the private delegate on a target normalised exactly once (`:755`, consumed at `:830` and `:888`). The permanent multi-dot residual is recorded at source in `_normalise_dns_name()`'s docstring (`:144-151`) and again in `_selected_address_for_normalised()`'s (`:371-384`). Residual logged under Accepted Risks as R-16-01. | closed |
| T-16-05 | Elevation of privilege | n/a | low | accept | No privilege boundary, no authentication surface, no credential material in the module. The negative statement at `src/lifx/api.py:1286` is retained unchanged. | closed |
| T-16-06 | Spoofing | Border-router proxy advertisements described to callers | high | mitigate | The `## Limitations` proxy paragraph attributes enumeration to the border router's advertisement and verification to `discover()`'s mDNS candidates. Positive lock: 4 of 5 new fragments in `approved_phrases` (`test_phase_contract.py`). Negative lock: `_FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES` (`test_docs_language.py:51-54`). See note 2 on the lock's width. | closed |
| T-16-07 | Repudiation | Prose overclaiming what a bounded sweep establishes | medium | mitigate | Enumeration attributed to the advertisement, never the sweep. The retained practical rule states a bounded timeout finding nothing is evidence of silence during that window, not proof of absence. The fleet paragraph is recast as advice rather than a benchmark. | closed |
| T-16-08 | Tampering | The `docs/changelog.md` exclusion | medium | mitigate | `test_generated_changelog_is_excluded_by_name` (`test_docs_language.py:87-90`) pins `_GENERATED_DOCS` to exactly one path and asserts that path exists on disk. `docs/changelog.md` is absent from the phase diff. | closed |
| T-16-09 | Information disclosure | New documentation prose | medium | mitigate | Zero IPv4, IPv6, MAC or serial literals added anywhere under `docs/` in the phase diff. `test_discovery_surfaces_use_only_documentation_safe_addresses` green. | closed |
| T-16-10 | Denial of service | n/a | low | accept | The `src/lifx/api.py` diff is a docstring-only 4-line change. No runtime path, resource budget or timing constant is touched. | closed |
| T-16-11 | Spoofing | Documentation of `Device.connectivity` | medium | mitigate | The new `AGENTS.md` category bullet contains none of `authenticat`, `trust boundary`, `secure` or `proves the device`. The relocated `advanced-usage.md:146-147` bullet describes derivation only. The `api.py:1286` negative is retained. | closed |
| T-16-12 | Tampering | The caching-category contract | medium | mitigate | `test_connectivity_appears_in_exactly_one_caching_category` asserts `len(matching_categories) == 1`, a count, so both zero and duplicate membership fail. Verified as source text rather than by test name. | closed |
| T-16-13 | Repudiation | Guidance drift between `AGENTS.md` and `CLAUDE.md` | low | mitigate | `### State Caching` is present in `AGENTS.md` and has zero matches in `CLAUDE.md`. The new category landed inside that section. `test_repository_guidance.py` 10/10 green. | closed |
| T-16-14 | Information disclosure | n/a | low | accept | The 16-03 diff adds no identifier, address or example value. | closed |
| T-16-15 | Elevation of privilege | n/a | low | accept | `src/lifx/devices/base.py` confirmed unchanged across the phase diff. | closed |
| T-16-16 | Tampering | Tests silently weakened to make the sweep pass | high | mitigate | Empirical node-ID set comparison: 4256 collected IDs at the phase base against 4272 at HEAD, `comm -23` gives zero lost and 16 gained. Zero removed `def test_` and zero removed `assert` lines in the phase test diff; zero skip or xfail added, one removed. `pyproject.toml` is absent from sweep commit `ebae217`, and config commit `283a134` contains only `pyproject.toml`. None of the 27 swept files is covered by any of the seven ignore globs. | closed |
| T-16-17 | Tampering | A vacuously configured ruff rule | high | mitigate | Positive control with no `--select` flag: a real on-disk probe file under `tests/` was reported for `PLC0415` at exit 1, and the probe was deleted. The same result via `--stdin-filename` for six representative in-scope paths. Negative controls: all seven ignored paths exit 0 with zero hits, with no ignore leakage into siblings. | closed |
| T-16-18 | Tampering | Behaviour-changing import relocation | high | mitigate | An AST sweep of all 27 files at the phase base found only two function-local imports nested inside `with` or `try`. Both were checked by hand: the `matrix_module` alias resolves to the already-imported `MatrixLight` (`m.MatrixLight is MatrixLight` is `True`, so the monkeypatch-and-restore is byte-identical), and the nine `LifxTimeoutError` imports inside `except StopIteration:` are never a patch target. The 38 `_discover_lifx_services` and 11 `discover_devices_mdns` hoists all sat at function statement level before their `with patch(...)` blocks in the base, so binding is unchanged. Backstop: `pytest tests/test_network/test_connection_retry.py` 36 passed. | closed |
| T-16-19 | Repudiation | An invisible exclusion | medium | mitigate | `pyproject.toml:90-97` carries an 8-line comment above the entries naming Phase 18, Phase 19 and the reason each remaining path is deferred. Each exclusion is a separate deletable line. | closed |
| T-16-20 | Denial of service | n/a | low | accept | 16-04 changes no `src/` line. Import relocation plus one lint configuration entry. | closed |
| T-16-21 | Tampering | A gate reporting success when its tool never ran | high | mitigate | The failure was reproduced and the gate proven to catch it. The decisive sweep gate run as written gives `ruff-exit=0 / in-scope-plc0415=0 / SWEEP-COMPLETE` at exit 0; re-run under an unwritable `UV_CACHE_DIR`, the exact condition the cross-AI review reproduced at `16-REVIEWS.md:147`, ruff exits 2, the gate prints `RUFF-DID-NOT-SUCCEED`, suppresses `SWEEP-COMPLETE` and exits 1. Every `<automated>` block across all four plans was audited: each ruff invocation either propagates status directly or captures it and asserts an exact value with an explicit failure branch, and no deciding `test` sits mid-chain with its status discarded. | closed |
| T-16-SC | Tampering | Package-manager installs | low | accept | `uv.lock` unchanged. The `pyproject.toml` diff touches only `[tool.ruff.lint]`; `[project].dependencies` is untouched. No `uv add`, `pip`, `npm` or `cargo` anywhere in the phase. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-16-01 | T-16-04 | An owner carrying two or more trailing dots keys the guard on `host.local.` while `records_for()` resolves `host.local`, so the two diverge and the target stays permanently pending. D-02 declined to make `_normalise_dns_name()` idempotent, because widening it would change cache keying for every other caller. No SPEC acceptance criterion and no `## Edge Coverage` row covers a multi-dot owner form. The residual is recorded in `_normalise_dns_name()`'s docstring, in `_selected_address_for_normalised()`'s docstring and in plan 16-01, so the owner-form invariant is not read as universal over all dot forms. | Avi Miller (D-02) | 2026-09-07 |
| R-16-02 | T-16-19 | `"src/**" = ["PLC0415"]` disables the import-position rule across the entire shipped library, where 82 violations currently sit. This is deliberate and visibly documented as a deletable line with a named future owner, not an oversight, but it means the phase's lint enforcement covers `tests/` only. | Avi Miller (D-05) | 2026-09-07 |

---

## Auditor Notes

These narrow a stated mitigation without opening a threat. Each is recorded so a later
reader does not over-read the register.

1. **T-16-03's stated enforcement mechanism is narrower than the mitigation plan claims.**
   Plan 16-01 says fixture privacy is enforced by the pre-existing
   `test_discovery_surfaces_use_only_documentation_safe_addresses` contract. That test walks
   `docs/user-guide/discovery.md` and the progressive example only; it does not walk `tests/`.
   Separately, four new fixture lines in `tests/test_network/test_mdns/test_discovery.py`
   (`:3918`, `:3922`, `:3956`, `:3960`) pass `192.168.1.50` as a packet source address rather
   than the `192.0.2.0/24` documentation range the 16-01 prohibition text names. They follow
   that file's own pre-existing convention, which the phase inherited at 61 occurrences and
   left at 65. The value is RFC1918 private space, generic and synthetic, and discloses no
   live identifier, so the threat is closed. The accurate correction is to the enforcement
   claim, not to the fixtures; changing four of sixty-five would leave the file inconsistent.

2. **T-16-06's negative lock is two literal strings.**
   `_FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES = ("udp leg is unicast-verified", "udp leg is
   verified")`. A differently worded reintroduction, for example "the UDP leg verifies each
   responder", would pass. The declared mitigation is present exactly as declared, so the
   threat is closed, but the lock is narrower than the concern it names.

3. **Unrelated to any declared threat, recorded for future gate authors.** `ruff check` exits
   0, printing only a `warning: Failed to lint ...` line, when handed a path that does not
   exist. A future gate that passes a wrong path would therefore report green. Every gate in
   this phase's plans passes real paths, so nothing here is affected.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-07 | 23 | 23 | 0 | gsd-security-auditor (opus, ASVS L1, block_on high) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-07
