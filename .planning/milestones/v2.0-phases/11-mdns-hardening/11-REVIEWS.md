---
phase: 11
reviewers: [claude, opencode, antigravity]
reviewed_at: 2026-08-28T05:52:55.029Z
plans_reviewed: [11-01-PLAN.md, 11-02-PLAN.md, 11-03-PLAN.md, 11-04-PLAN.md, 11-05-PLAN.md]
models:
  claude: "claude-opus-5 (reasoning=high)"
  opencode: "openrouter/z-ai/glm-5.3 (reasoning=high)"
  antigravity: "gemini-3.1-pro-high"
model_sources:
  claude: "pinned"
  opencode: "pinned"
  antigravity: "pinned"
---

# Cross-AI Plan Review — Phase 11

## Claude Review

I read the five plans against the actual repo. Findings below cite `path:line`.

# Cross-AI Plan Review — Phase 11: mDNS Hardening

## 1. Summary

These are unusually well-grounded plans: nearly every file, line range, symbol, and bound they cite is real, and several non-obvious details check out exactly (the 64-target/2-attempt ledger at `src/lifx/network/mdns/discovery.py:509-545`, the `_MAX_ENTRIES = 1024` admission shape at `:100-119`, the last-wins `TxtData.pairs` at `src/lifx/network/mdns/dns.py:242-244`, the seventeenth-address drop test at `tests/test_network/test_mdns/test_discovery.py:1199`, and the fact that `scripts/ipv6_thread_probe.py:206` and `scripts/mdns_probe.py:416` are the *only* two `IP_ADD_MEMBERSHIP` consumers — the exact allow-list 11-05 encodes). Wave ordering is sound and the file-disjointness claim for Wave 2 holds. The material problems are three: a new deterministic TXT/SRV eviction policy in 11-02 that trades a security property for test determinism; a dataclass-field-default question in 11-01 that is unstated and will break 26 construction sites if resolved the wrong way, with no full-suite gate in that wave to catch it; and 11-05 quietly widening the locked D-03 API break to a third symbol.

## 2. Strengths

- **The privacy/audit boundary is genuinely engineered, not asserted.** `11-PHASE-BASE.txt` is written before any edit (11-01 Task 1) and consumed by 11-05 for both the privacy diff and `scripts/check_patch_coverage.py --base`. The script really does require a full 40-hex SHA (`scripts/check_patch_coverage.py:88`) and really does support `--base/--coverage/--source/--check-weakening-only` (`:319-342`). The plan also correctly notes that `git diff` misses untracked files and adds a separate `git status --short` review — a failure mode most plans miss.
- **The rg gates were verified against the tree, not invented.** I ran them: `rg "IP_ADD_MEMBERSHIP|..." src scripts docs examples AGENTS.md CLAUDE.md` returns exactly `scripts/ipv6_thread_probe.py:206` and `scripts/mdns_probe.py:416` — the two paths 11-05 allow-lists. `docs/changelog.md` contains zero references to the removed symbols, so the "generated changelog is evidence, not a cleanup target" rule does not deadlock the `docs`-wide gate. Standalone `tm` appears nowhere in `docs`/`examples` today, so that regex starts clean.
- **11-01's tracer is the right shape.** It fails first on an absent `Device.connectivity`, then threads cache → record → `create_device_from_record()` → `Light`. The chosen `_set_connectivity()` plumbing sidesteps research Pitfall 5 (the five explicit subclass signatures at `src/lifx/devices/infrared.py:88`, `hev.py:113`, `multizone.py:227`, `matrix.py:393`, `ceiling.py:356`) and sits squarely inside the CONTEXT "planner's discretion" grant for constructor plumbing.
- **The MDNS-01 test design avoids the obvious race.** Keeping the real `MdnsTransport` open and reading `transport._socket.getsockname()[1]` (the bind is `sock.bind(("", 0))` at `src/lifx/network/mdns/transport.py:107`, port logged at `:113`) is correct; a probe/free/rebind fixture would race. The refusal to fall back to a daemon or hardware is right for CI.
- **11-05 correctly identified `_pick_address` as having exactly two consumers** (`src/lifx/network/mdns/discovery.py:215`, `scripts/ipv6_thread_probe.py:365`) and 11-02 migrates the probe in the same wave that changes the seam, rather than leaving it to break silently.
- **11-04's documented limitations are true at Wave 2, not aspirational.** I checked: the cache really is per-call (`discovery.py:354`), and `cache_flush` really is never read by the cache today (`dns.py:137` is defined but unused in `discovery.py`) — so "cache-flush semantics are not applied" is already factual when 11-04 lands.

## 3. Concerns

**HIGH — 11-02's lexicographic-least-16 TXT/SRV retention lets an attacker *evict* the genuine record, where the status quo could only add a conflict.**
11-02 Task 1 specifies: "order the existing identities plus the candidate by complete RR identity and retain the lexicographically least 16 ... admit it and evict the lexicographically greatest old identity when it sorts into the retained set." The stated goal is packet-order independence (a *testability* property). But RR identity includes raw `rdata` (`dns.py:128`), which is entirely attacker-chosen. Failure scenario: a genuine device's TXT RR is cached; an attacker sends 17 forged TXT RRs for the same owner name with rdata sorting below the genuine one, all carrying one consistent valid-looking `id`. The genuine RR is evicted as "greatest", conflict detection sees exactly one live valid ID, and the instance resolves entirely from attacker data. Under a simpler "reject any new identity once full" rule, a late attacker can only ever be refused. This directly undercuts threat T-11-06/T-11-05 in the plan's own register. Note this is a *new* policy: the SPEC, CONTEXT D-01..D-14, and `11-RESEARCH.md` require bounded admission but nowhere require eviction.

**HIGH — 11-01 adds a field to a frozen dataclass with 26 construction sites, does not say whether it has a default, and has no full-suite gate in that wave.**
`LifxServiceRecord` (`src/lifx/network/mdns/types.py:9-25`) has five no-default fields. `grep -rn "LifxServiceRecord(" tests src scripts` returns 27 sites, 26 of them in tests, five positional (e.g. `tests/test_network/test_mdns/test_discovery.py:1001`, `:1033`, `:1054`) and one at `tests/test_scripts/test_ipv6_thread_probe.py:58`. 11-01 adds "a record connectivity field" without stating a default; 11-02 later adds `addresses`. If either lands without a default, all 26 sites break. 11-01's `files_modified` omits `tests/test_scripts/test_ipv6_thread_probe.py`, and its `<verification>` block runs only a scoped file list — no `uv run --frozen pytest -q`. So Wave 1 would close green while the repository is red, and the failure would only surface in 11-02's full-suite run one wave later.

**MEDIUM — 11-05 widens the locked D-03 API break to a third symbol on the planner's own authority.**
D-03 and SPEC AC5 name exactly `LifxServiceRecord`, `discover_lifx_services()`, and `TransportMethod`. 11-05 Task 1 additionally renames `create_device_from_record` → `_create_device_from_record` and removes it from `src/lifx/network/mdns/__init__.py:43`, where it is currently a public export. The plan's coherence argument ("a supported function whose only input type is intentionally private") is a good one, and it labels the reversibility one-way — but it cites D-03 as the authorising decision, and D-03 does not cover this symbol. This is an extra breaking change to a public export, decided inside a plan rather than by the user.

**MEDIUM — 11-03's narrowing of `except Exception` must name `struct.error`, which is not a `ValueError`.**
11-03 Task 2 says "Narrow the current broad packet-processing `except Exception` to the parser's recoverable error types" without enumerating them. Reading `src/lifx/network/mdns/dns.py`, `parse_dns_response` can raise `ValueError` (`:76`, `:179`, `:186`, `:195`, `:205`, `:266`, `:273`) and `struct.error` from `struct.unpack` (`:77`, `:268`, `:293`) — and `struct.error` does **not** subclass `ValueError`. A literal `except ValueError:` would let a truncated-but-header-valid packet abort the whole sweep. The repo already has the correct triple at `scripts/ipv6_thread_probe.py:257`: `except (ValueError, IndexError, struct.error)`. Separately, the narrowing itself is an availability tradeoff on an untrusted-input path — an unforeseen `AttributeError` from a hostile packet now ends discovery instead of skipping one packet.

**MEDIUM — 11-02 removes the existing per-owner address cap and replaces it with nothing.**
`discovery.py:162` currently caps a host at 16 AAAA addresses. 11-02 removes it ("Apply neither per-owner constant nor any global RR-count truncation to A/AAAA") and records the residual as accepted risk T-11-07R. D-05/AC12 require "every unique valid" address, which a generous bound (say 1024/owner) would satisfy just as well as no bound; "unbounded" is a stronger reading than the decision demands. With 1024 admitted owners and an unbounded per-owner address set, the only remaining limit on cache growth is the caller's deadline.

**MEDIUM — 11-05's patch-coverage `--source` list is hand-maintained and will silently under-measure any deviation.**
`scripts/check_patch_coverage.py:226` requires at least one explicit `--source`; it does not derive the set from the diff. 11-05 hardcodes seven paths. Any Rule 1–3 deviation touching a source file outside that list (e.g. `src/lifx/network/utils.py` for expiry-aware timing) is diffed for privacy but never checked for coverage — and the gate passes.

**LOW — 11-04 writes Wave-3 behaviour into docstrings during Wave 2.** The plan is honest about this ("target contract documentation") and 11-05 Task 2 Test 8 re-checks after 11-03 lands. I verified the specific claims are already true today, so the exposure is smaller than it reads — but the re-check is the only thing stopping a documentation lie if 11-03 deviates.

**LOW — the bounds-suite migration is under-specified for the defensive bounds.** `test_resolved_instances_are_directly_bounded` (`tests/test_network/test_mdns/test_discovery.py:1302`) deliberately bypasses `add_packet` to prove `resolve()` is *independently* bounded. Under 11-02's owner-admission model that bound may become implicit, at which point "replaced in place by an equal-or-stronger assertion" is not satisfiable as written.

**LOW — the multicast-prose rg gate is a negation heuristic.** `rg -ni "multicast.*(membership|join)..." | rg -vi "\b(no|not|never|without|does not|is not)\b"` passes any sentence containing the word "no" anywhere on the line. It will catch a blatant regression and miss a subtle one.

**LOW — 11-05's "/tmp ... leaves no repository-root artefact" is inaccurate.** `pyproject.toml:113-124` already sets `--cov-report=xml` and `--junitxml=junit.xml` in `addopts`; adding `--cov-report=json:/tmp/...` appends a report rather than replacing them, so `coverage.xml`, `junit.xml` and `.coverage` are still written to the repo root. Harmless in effect — all three are in `.gitignore:48-56`, so the untracked-file review stays clean — but the stated rationale does not hold.

**LOW — `Device.adopt_cached_metadata()` will not carry connectivity.** `src/lifx/devices/base.py:547-559` copies version/firmware/capabilities/MAC between instances. With 11-01's private-storage design, `_connectivity` is not in that list, so any future path that builds a device via that helper silently reports `"wifi"`. Not reachable in Phase 11 (mDNS constructs directly), but Phase 13's merge is exactly the kind of code that would use it.

## 4. Suggestions

- **11-02: drop the eviction rule.** Retain the first 16 distinct TXT/SRV identities per admitted owner and refuse the rest, incrementing `rr_identity_limit`. Arrival-order determinism is still testable (feed a fixed script; assert the retained set), and a late attacker can no longer displace an early genuine record. If packet-order independence is truly required, make the retained set order-independent *without* eviction — e.g. reject once full, and assert that the union of legitimate identities never exceeds 2 in practice.
- **11-01: state the field defaults explicitly.** Add to the `<action>`: "new `_LifxServiceRecord` fields are keyword fields with defaults (`connectivity: Literal["wifi","thread"] = "wifi"`), so the 26 existing construction sites are unchanged." Then add `uv run --frozen pytest -q` to 11-01's `<verification>` block, or add `tests/test_scripts/test_ipv6_thread_probe.py` to its `files_modified` and scoped run.
- **11-05: escalate the `create_device_from_record` removal.** Either raise it as a decision checkpoint (it is a third public-export break beyond D-03), or record it as a new decision `D-15` in `11-CONTEXT.md` with the user's confirmation before Wave 4 runs.
- **11-03: name the caught exception tuple.** Write `except (ValueError, IndexError, struct.error)` into the plan text, citing `scripts/ipv6_thread_probe.py:257` as the in-repo precedent, and add a test that a truncated packet (raising `struct.error`) is counted as `malformed_packet` rather than ending the sweep.
- **11-05: derive the coverage source list.** Replace the seven hardcoded `--source` flags with `git diff --name-only "$phase_base" -- 'src/lifx/**/*.py'` expanded into `--source` arguments, so a deviation cannot escape the gate.
- **11-02: keep a generous per-owner address bound** (e.g. 1024) rather than none. It satisfies D-05/AC12 for any realistic advertisement while preserving a hard memory ceiling, and lets T-11-07R be closed rather than accepted.
- **11-03: constrain the `finally` emission.** State that the per-sweep summary is emitted by a synchronous `_LOGGER.debug()` with no `await` — a `finally` that awaits during `GeneratorExit` raises `RuntimeError: async generator ignored GeneratorExit` and would fail Test 7 in a confusing way.
- **11-03: update `test_resolved_record_survives_unrelated_query_failure`.** Its `assert "parse_error" not in actions` (`tests/test_network/test_mdns/test_discovery.py:1608`) becomes vacuously true once `parse_error` logging is removed; re-point it at the aggregate summary.
- **Phase-level observation (no action required):** the one-second goodbye/rescue machinery in 11-03 Task 1 — `expires_at` on every RR, `next_expiry_delay()`, `expire()`, and a restructured receive loop with a defined ordering for simultaneously-due events — exists to serve exactly one behavioural outcome inside a ~15s sweep: D-12 conflict recovery. Records are yielded exact-once and never retracted, so nothing else observes expiry. It is SPEC-locked (MDNS-07/D-11) so the plan is right to implement it, but it is the largest complexity block in the phase serving the narrowest case, and is worth naming in the summary as such.

## 5. Risk Assessment

**MEDIUM.**

Downward pressure: the plans are verified against the tree to an unusual degree, the wave graph is correct and genuinely file-disjoint where it claims to be, the security and privacy gates are executable rather than aspirational, and the scope fences against Phases 12–14 are explicit and repeatedly restated.

Upward pressure: three findings can each produce a bad outcome that the plans' own gates would not catch. The 11-02 eviction rule *passes* every test the plan specifies while weakening the spoofing posture the phase exists to improve — a correctness-by-construction failure, not a test gap. The 11-01 dataclass-default question is a coin flip that, resolved wrongly, leaves Wave 1 closing green over a red repository, because that wave has no full-suite gate. And 11-05's `create_device_from_record` removal is a public break made on planner authority against a decision that does not authorise it.

None of these threaten the phase goal — the mDNS leg will reach broadcast-grade per-sweep quality — and all three are cheap to fix in the plan text before execution starts.

---

## OpenCode Review

# Phase 11 Plan Review (11-01 … 11-05)

Reviewed against source: `src/lifx/network/mdns/{discovery,types,transport,dns}.py`, `src/lifx/network/address.py`, `src/lifx/network/utils.py`, `src/lifx/devices/base.py`, `src/lifx/__init__.py`, `src/lifx/network/mdns/__init__.py`, `scripts/{ipv6_thread_probe,mdns_probe,check_patch_coverage}.py`, `tests/test_network/test_mdns/test_discovery.py`, `docs/`, `examples/`, `11-SPEC.md`. Claims verified line-by-line where cited.

## Summary

Strong plan set. Research citations match the actual code almost everywhere I checked: the last-wins cache slots (`discovery.py:93-98`), per-host 16-AAAA truncation (`discovery.py:162`), the retransmit-assuming timeout handler (`discovery.py:429-437`), identifier-bearing `parse_error` logging (`discovery.py:547-556`), ephemeral bind (`transport.py:107`), probe imports (`scripts/ipv6_thread_probe.py:77-90`), both `IP_ADD_MEMBERSHIP` allow-list candidates (`ipv6_thread_probe.py:206`, `mdns_probe.py:416`), docs/examples that promote the low-level API (`examples/discovery_mdns.py:58`, `docs/api/network.md`), and `check_patch_coverage.py`'s actual flag surface (`--base/--coverage/--source/--check-weakening-only`, with the documented mutual exclusion at lines 336-337). Wave ordering is dependency-correct and Wave 2 is genuinely file-disjoint. Risks are moderate and mostly around scheduler cost under the deliberately uncapped A/AAAA retention, one un-migrated identifier-bearing log path, and docs-before-code drift between Waves 2 and 4.

## Strengths

- **Verified seams.** Every "Current:" claim in the plans traces to real code. Example: the loop-termination hazard the plan fixes — `discovery.py:431-437` treats any pre-deadline `LifxTimeoutError` as a retransmit slot — is exactly what 11-03 Task 1 reworks, and `TestMdnsRemainingNonPositiveGuard` (test_discovery.py:1074) already pins the `max(remaining, 0.01)` floor the new expiry clamp must respect.
- **Correct wave topology.** 11-01 (tracer + transport proof) → 11-02 (cache model) → 11-03 (timed semantics) → 11-05 (cutover); 11-04 file-disjoint in Wave 2 (docs/api/AGENTS/CLAUDE vs discovery/types/probe/tests — no overlap).
- **11-01's setter approach is sound and cheaper than research Pattern 4.** `Device` is a plain class, not a dataclass (`base.py:435` hand-written `__init__`), so `_connectivity` + `_set_connectivity()` works without touching five subclass signatures (`infrared.py:88`, `hev.py:113`, `multizone.py:227`, `matrix.py:393`, `ceiling.py:356`). Within CONTEXT's stated planner discretion.
- **11-02 handles the double last-wins hole correctly.** `dns.py:244` (`pairs[key] = value`) and `discovery.py:145` (`_add` overwrite) are both real; deriving IDs from `TxtData.strings` including repeated keys closes both. The lexicographic-least-16 retention is genuinely arrival-order-independent (final set = least-16 of all distinct identities).
- **11-03's deadline discipline is right.** `IdleDeadline` (`utils.py:19-57`) owns both clocks; the plan never lets expiry call `mark_response()` and clamps receive timeouts only downward. Goodbye expiry needs the loop-wake fix the plan specifies — with no packet after a goodbye, nothing today would ever call an `expire()`.
- **11-05's privacy gate is well-engineered.** The immutable `11-PHASE-BASE.txt` + `git diff <base> -- .` covers committed Waves 1-4 plus working tree, and the plan correctly notes untracked files need separate `git status --short` inspection (git diffs exclude them). The two-script `IP_ADD_MEMBERSHIP` allow-list matches reality exactly.
- **Probe migration is correctly sequenced.** `ipv6_thread_probe.py` imports `_pick_address`, `create_device_from_record`, `discover_lifx_services` today (lines 77-80); 11-02 ports the cache-view seam in the same wave it changes the cache, so the probe cannot break unseen.

## Concerns

- **MEDIUM — Expiry scheduler is O(total cached RRs) per loop iteration, and A/AAAA cardinality is uncapped.** `next_expiry_delay(now)` scanning every retained identity each receive-timeout, plus per-packet, over 1,024 admitted owners × unbounded addresses (T-11-07R accepted residual), turns the accepted memory residual into a CPU residual: an address-flooding attacker makes each wake and each timeout computation scan tens of thousands of identities. Duration-bounded by the caller deadline, so not a blocker, but the research (A1) rejected a heap for simplicity without costing this interaction.
- **MEDIUM — The `invalid_address` debug event in `discover_devices_mdns` is never migrated.** `discovery.py:611-620` logs `serial` and `address` per rejected record at DEBUG. D-09 forbids identifiers in rejection diagnostics, 11-03 Task 2 replaces the `parse_error` path (`discovery.py:547-556`), and `invalid_address` appears in the locked reason vocabulary — but no task explicitly removes or aggregates this second identifier-bearing rejection log. If it survives, the phase ships a D-09-adjacent leak the 11-05 audit's `rg` patterns won't catch (they scan for public names/membership tokens, not this log shape).
- **MEDIUM — Docs-before-code window (11-04, Wave 2 vs 11-05, Wave 4).** Public docs remove the raw-record API and AGENTS/CLAUDE adopt private terminology while `LifxServiceRecord`/`discover_lifx_services` remain exported (`src/lifx/__init__.py:76,165-166`, `mdns/__init__.py:39-58`) until 11-05. If the phase aborts between waves, docs describe an API state that doesn't exist. Acknowledged in-plan (11-05 re-check), but it's a real mid-phase incoherence window, and 11-04's Task 2 docstrings describe 11-03's goodbye/cache-flush behaviour before 11-03 lands — any implementation-driven design shift in Wave 3 invalidates Wave 2 prose unless the 11-05 re-check is enforced.
- **LOW — TXT/SRV 16-identity ceiling and `rr_identity_limit` are plan-introduced policy, not SPEC-locked.** I searched `11-SPEC.md`: no mention of `rr_identity_limit`, per-owner ceilings, or lexicographic eviction. It's defensible under planner discretion and better than the SPEC-silent alternative (the old per-table 1,024 bound disappears with the last-wins tables), but it's new de-facto API surface locked by tests with no recorded decision trail outside the plans themselves.
- **LOW — Ambiguous diagnostic counting for replayed over-cap candidates.** 11-02 says "every distinct over-cap observation increments `rr_identity_limit` once" while 11-03 says "repetition affects only bounded counts". Whether the *same* rejected candidate arriving N times increments N times or once is stated differently in different places; tests will lock one reading by accident.
- **LOW — 11-05's prose-negation audit heuristic is fragile.** The `rg -vi "\b(no|not|never|without|does not|is not)\b"` filter over multicast-membership phrasing false-fails honest wording like "membership is deliberately absent" (no listed negation word) and could false-pass clever phrasing. Gate friction, not a correctness hole.
- **LOW — 11-05's runtime export assertions use `uv run python` without `--frozen`**, unlike every other verification command. Trivial, but inconsistent with the repo's own gate discipline.
- **LOW — `MdnsTransport`, `DnsResourceRecord`, `parse_dns_response` etc. stay public in `mdns/__init__.py`.** D-03 names only the record and generator. Defensible scope reading, but the "one coherent private raw-record surface" story in 11-05 Task 1 stops at three symbols while the DNS parser layer the record is built from remains exported.

## Suggestions

- In 11-03 Task 1, require `next_expiry_delay()` to be O(expiring identities), not O(all identities): keep a separate small set/heap of goodbye-pending identities (only TTL-zero-marked RRs enter it; rescue removes). This sidesteps the uncapped-A/AAAA scan cost entirely without a general timer heap.
- Add an explicit task item (11-03 Task 2 or 11-05 Task 2): remove or aggregate the `invalid_address` per-record event at `discovery.py:611-620` into the reason-only summary, with a test asserting no serial/address appears on that path.
- Pin the replayed-candidate counting semantics in one sentence in 11-02 (suggest: same candidate observed over-cap N times increments N times — counts are integers, "bounded" refers to key cardinality, not magnitude — then mirror that wording in 11-03).
- Swap the negation-word blocklist for an allowlist of exact doc phrases 11-04 is permitted to use (e.g. "does not join", "no multicast group membership"), so the 11-05 gate checks the approved wording rather than guessing intent.
- Consider moving the 11-04 Task 2 AGENTS/CLAUDE private-terminology edits into 11-05 (they're prose-only and 11-05 already owns the cutover), shrinking the docs/code incoherence window to one wave.

## Risk Assessment

**Overall: LOW-MEDIUM.** The plans are unusually well-grounded — I traced every load-bearing code claim to real line numbers and found no factual errors, and the wave structure, privacy gates, and dependency ordering are correct. The substantive residual risks are the O(N) expiry scan interacting with deliberately uncapped A/AAAA retention (bounded by the caller deadline, so a degradation not an outage), the un-migrated `invalid_address` log path, and the Wave 2→4 documentation coherence window. None blocks execution; all are cheap to fix in-plan now.

---

## Antigravity Review

### Phase 11 mDNS Hardening Review

**Summary**
The Phase 11 plans present a rigorous, deeply researched approach to hardening mDNS discovery in `lifx-async`. By breaking the work into precise increments (connectivity tracing, cache bounding, expiry/diagnostics, documentation, and API cutover), the plans effectively resolve the complexities of RFC 6762 mesh-scale traffic while strictly adhering to the project's zero-dependency, privacy, and architectural constraints. The transition from a brittle last-wins cache to a bounded, deterministic multi-value identity model is handled with excellent synthetic test strategies and explicit limits, ensuring production stability without live hardware dependence.

**Strengths**
* **Deterministic Identity Cache**: The `11-02-PLAN.md` plan elegantly replaces the race-prone last-wins mapping with an explicit distinct-owner bounded cache. It successfully limits TXT and SRV identities to 16 per owner, using a lexicographic sort to guarantee reproducible state independent of packet arrival order. (Evidence: `.planning/phases/11-mdns-hardening/11-02-PLAN.md:139`, "retain the lexicographically least 16").
* **Privacy-Safe Diagnostics**: The `11-03-PLAN.md` plan introduces an exact, single-emission diagnostic summary at generator termination. It completely segregates identifier tracking from aggregate event telemetry by reducing DoS/over-cap cases into structural reason counts (`rr_identity_limit`), preventing accidental PII logging. (Evidence: `.planning/phases/11-mdns-hardening/11-03-PLAN.md:174`).
* **Targeted Test Boundaries**: The `11-01-PLAN.md` plan creates a pre-implementation stable commit boundary (`11-PHASE-BASE.txt`). The test design across all plans correctly patches `time.monotonic` and the transport socket to synthetically assert complex mDNS lifecycle semantics without brittle true `sleep` statements. (Evidence: `.planning/phases/11-mdns-hardening/11-01-PLAN.md:136`).
* **Clean API Cutover**: The `11-05-PLAN.md` plan comprehensively internalizes the raw mDNS generator and service records, correctly enforcing decision D-03 by stripping them from `__all__` and documentation, leaving only the stable, typed Device paths. (Evidence: `.planning/phases/11-mdns-hardening/11-05-PLAN.md:141`).

**Concerns**
* **(MEDIUM) Unbounded A/AAAA Address Retention**: While `11-02-PLAN.md` limits TXT and SRV identities, it explicitly exempts A/AAAA records from per-owner truncation to comply with D-05's lossless requirement. A malicious responder flooding valid unique A/AAAA records for an admitted owner could potentially exhaust memory. (Evidence: `.planning/phases/11-mdns-hardening/11-02-PLAN.md:139`, "Apply neither per-owner constant nor any global RR-count truncation to A/AAAA...").
* **(LOW) Post-Initialization State Mutation**: `11-01-PLAN.md` opts to inject connectivity metadata into instantiated devices via a private setter (`Device._set_connectivity()`) before returning them from the factory. While avoiding broad constructor signature changes, this briefly exposes a partially-initialized state within the factory function. (Evidence: `.planning/phases/11-mdns-hardening/11-01-PLAN.md:136`, "private `_set_connectivity()` method used solely by the mDNS factory").
* **(LOW) Fragile Bash Regex Assertions**: `11-05-PLAN.md` relies heavily on complex, multiline PCRE2 bash pipelines to verify API compliance and absence of live identifiers. These checks are rigorous but brittle; formatters or multiline strings could evade or break the pipeline constraints. (Evidence: `.planning/phases/11-mdns-hardening/11-05-PLAN.md:247`).

**Suggestions**
* **Bounded Lossless Definition**: Revisit the interpretation of D-05's "lossless" requirement for addresses. Consider defining an overwhelmingly high hard cap (e.g., 256 unique IPs per owner) that acts effectively lossless for Thread mesh deployments but provides a definitive ceiling against intentional memory exhaustion.
* **Type-Strict Setter Validation**: In `src/lifx/devices/base.py`, ensure `Device._set_connectivity` utilizes strict `Literal["wifi", "thread"]` type annotations so Pyright can catch any invalid mappings statically during the factory assembly.
* **Event-Loop Tick Safety in Tests**: When patching `time.monotonic` in `11-03-PLAN.md`, explicitly advance the mocked clock in precise test-controlled increments, ensuring `asyncio` event loop yields actually correspond to expected timeout checks in `IdleDeadline`.

**Risk Assessment**
**LOW**. The implementation plans heavily prioritize determinism, security, and synthetic testing. The reliance on standard library abstractions and the complete elimination of live hardware constraints dramatically de-risk the execution. Memory and state bounds are largely defined and mitigated, and where unmitigated (like A/AAAA counts), they are explicitly documented as accepted risks rather than oversights. The phased execution approach ensures that architectural contracts are locked prior to the final API cutover.

---

## Consensus Summary

All three reviewers inspected the repository and cited concrete source or plan lines; no lane is down-weighted for missing repository access or missing source citations. The plans are consistently judged unusually well grounded, with correct wave ordering and strong synthetic verification. The principal open issue is not whether Phase 11 is implementable, but whether several plan-introduced policies preserve the security and scope decisions they claim to enforce.

### Agreed Strengths

- **Source grounding and dependency ordering:** all reviewers confirmed that the plans' current-state claims map to real code and that the four-wave dependency graph is sound, including genuine Wave 2 file-disjointness.
- **Privacy and evidence boundaries:** Claude and OpenCode specifically validated the immutable phase-base mechanism, complete-range audit intent, and privacy-safe aggregate diagnostics; Antigravity independently praised the same phase-base and diagnostic design.
- **Deterministic synthetic validation:** the ephemeral-port regression, test-controlled timing, cache-to-Device tracer and probe migration are consistently treated as strong, CI-appropriate choices.

### Agreed Concerns

- **Unbounded A/AAAA retention:** all three reviewers flagged the absence of any address ceiling. Claude and Antigravity focused on memory exhaustion; OpenCode additionally identified O(total cached RRs) expiry scans that turn the accepted memory residual into a CPU residual. This conflicts with the current D-05 interpretation only if a cap drops a valid admitted address, so any revision must explicitly reconcile the security bound with the locked lossless requirement rather than silently choosing one.
- **Brittle text/audit gates:** all three reviewers found the multiline or negation-based `rg` checks fragile. Claude also found the hard-coded patch-coverage source list can miss implementation deviations; OpenCode found the current audit does not explicitly catch the identifier-bearing `invalid_address` log path.

### Divergent Views

- **TXT/SRV lexicographic retention is the highest-priority disagreement.** Claude rates lexicographic eviction HIGH risk because attacker-controlled RR data can displace an earlier genuine identity. OpenCode and Antigravity praise the same least-16 rule for arrival-order determinism. This policy is plan-introduced rather than SPEC-locked and needs an explicit resolution before execution.
- **Private connectivity setter:** Claude and OpenCode consider `Device._set_connectivity()` a sound way to avoid subclass-constructor churn; Antigravity sees a low-risk partially-initialised-state concern. Claude separately requires explicit defaults for new record fields and a Wave 1 full-suite gate so existing construction sites cannot break unnoticed.
- **API cutover scope:** Claude finds that renaming/removing `create_device_from_record` widens locked D-03 beyond its named symbols and needs an explicit decision. The other reviewers accept the cutover as coherent.
- **Overall risk:** Claude rates the plan set MEDIUM, OpenCode LOW-MEDIUM, and Antigravity LOW. Their difference is driven mainly by whether plan-introduced retention and API-cutover policies are treated as acceptable implementation discretion or unresolved security/scope decisions.

### Reviewer-Specific Actionable Findings

- **Claude:** name `(ValueError, IndexError, struct.error)` as the recoverable parser exception tuple; derive patch-coverage sources from the phase diff; clarify defaults for new `LifxServiceRecord` fields and add a Wave 1 full-suite gate; resolve the extra public API break; update the vacuous `parse_error` assertion and connectivity metadata adoption path.
- **OpenCode:** bound or restructure expiry scheduling so it does not scan every uncapped address; aggregate the identifier-bearing `invalid_address` event; pin over-cap replay counting semantics; reduce the Wave 2 documentation-before-code incoherence window.
- **Antigravity:** keep the connectivity setter type-strict and make mocked-clock/event-loop advancement explicit in timing tests.

### Plan-Checker Resolution: Outcome-Level Non-Displacement

- **Resolved:** first-admitted TXT/SRV ceilings prevent later identities from evicting cached identities, but cache admission alone is not treated as source authenticity.
- **Fail-closed TXT outcome:** when complete live TXT records carrying the same valid serial disagree on product, firmware, or derived connectivity, the service instance remains unresolved. No arrival-order or lexicographic winner supplies effective metadata.
- **Fail-closed SRV outcome:** when live SRV records for one service instance disagree on target or port, the service instance remains unresolved. No arrival-order or lexicographic winner supplies the endpoint.
- **Recovery:** deterministic ordering remains available only for storage or presentation. Resolution becomes possible only when goodbye expiry leaves one consistent TXT construction tuple and one consistent SRV target/port value.
- **Adversarial proof:** Plans 11-02 and 11-03 require later lower-sorting RRs that preserve the genuine serial but change each TXT construction field, SRV target, or SRV port; each case must remain unresolved until the conflicting RR expires.
