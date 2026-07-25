---
phase: 05-reliability-documentation
verified: 2026-07-17T13:38:09Z
status: passed
score: 12/12 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 37/37
  gaps_closed:

    - "G-05-2 — quickstart.md and overview.md no longer claim IP-only connection skips discovery; the IP-only path is documented as a unicast discovery round-trip (traced to base.py:454-516) and the serial+IP constructor form is documented as the genuine zero-discovery path"
    - "G-05-3 — docs/api/animation.md Direct UDP Delivery lead-in is the operator's agreed_text verbatim ('purpose-built network stack with the following characteristics'); drop framing reads 'expected', not 'by design'"
    - "G-05-4 — zero run-on paragraphs across all 10 site/api/ pages (was 23 at planning time); every :::-reachable heading-plus-list docstring site carries its blank line (independent AST sweep clean against the 15-key out-of-scope allowlist)"
    - "G-05-5 — no Photons/Glowup/wall-time/blind-sleep vocabulary in any of the 53 :::-reachable public docstrings; the connection.py retransmit bullet matches overview.md:150's published wording verbatim"
    - "G-05-6 — zero planning IDs (RETRY-xx, D3-xx, ANIM-xx, D4-xx, spike/plan numbers) in rendered docstrings; every removed ID survives in the three additive # Traceability comments or a pre-existing unrendered surface (demotion map verified line-by-line)"
    - "G-05-7 — `zensical build --clean --strict` exits 0 with zero warnings (former 8-warning baseline eliminated): 5 effects.md annotations backticked, 3 mDNS ::: targets rendered (index.md untouched, diff empty), both CI invocations in docs.yml carry --strict"
  gaps_remaining: []
  regressions: []
human_verification:

  - test: "Review the 9 judgment-tier prohibition verdicts (all upheld, non-authoritative) in the Flagged Prohibitions section"
    expected: "Human concurs that the D5-19/D5-21 deferral fence, D5-09-as-written (no constants, no dispute work), D5-12 version neutrality, widened-D5-14/narrow-D5-23 ::: and page fences, D5-01 nav fence, comments-out-of-scope fence, base.py from_ip fence, whitespace-only discipline, and no-traceability-deletion rule all held"
    why_human: "Judgment-tier prohibitions in an autonomous run carry NON-AUTHORITATIVE LLM-judge verdicts; per fail-closed routing they need the end-of-phase human checkpoint and must not be silently absorbed into a passed verdict"
---

# Phase 5: Reliability Documentation Verification Report (Third Cycle — after 05-06 UAT gap closure)

**Phase Goal:** Users can find accurate guidance on the wire behaviour the library now guarantees and the device quirks it deliberately does not paper over
**Verified:** 2026-07-17T13:38:09Z
**Status:** human_needed (all automated checks pass; 9 flagged prohibitions await the human checkpoint)
**Re-verification:** Yes — after third gap closure (plan 05-06, closing operator-diagnosed UAT gaps G-05-2..G-05-7 under D5-22/D5-23)

## Goal Achievement

### Re-verification Focus: The Six UAT Gaps

The previous verification closed 37/37; this cycle's gaps came from operator UAT (05-UAT.md), not from verification failures. All six were verified against live files, the built site, and shipped source — never against SUMMARY claims.

### 05-06 Must-Have Truths

| # | Truth (abridged) | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| 1 | No published page claims IP-only connection skips discovery (G-05-2) | ✓ VERIFIED | quickstart.md:95 heading is `### Direct Connection` (parenthetical dropped, `No Discovery` → 0); lead-in states the unicast round-trip ("unicast / discovery round-trip" — phrase wraps at line 97/98, verified by reading, which is why a single-line grep misses it); serial+IP example `async with Light(serial="d073d5010203", ip=...)` (:123, constructor, never awaited); overview.md:253 is exactly the plan's replacement bullet. **Source-traced:** base.py:454-516 read in full — serial=None → temp conn with broadcast serial `000000000000` → unicast `Device.GetService()` → serial from `StateService` → close → construct; serial given → straight `cls(serial=..., ip=...)`. The docs now state exactly what ships |
| 2 | animation.md lead-in agreed_text verbatim; 'expected' drop framing (G-05-3) | ✓ VERIFIED | Section read in full: lead-in and all three bullets byte-match the UAT agreed_text ('characteristics' per resolved_nit, not 'features'); `is by design` → 0, `bypasses the connection layer` → 0, `paced against device acknowledgements` ×1 preserved |
| 3 | Zero run-on paragraphs under site/api/ (G-05-4) | ✓ VERIFIED | Run-on detector re-run independently against the freshly built site: 10 pages scanned, **0 run-ons** (was 23 at planning time); connection.py:59 `Features:` now followed by a truly-empty line (read in context) |
| 4 | Rendered docstrings speak plain reader vocabulary; retransmit wording matches overview.md:150 (G-05-5) | ✓ VERIFIED | Vocabulary sweep re-run independently over the live target-derived set: **53 :::-reachable files, zero hits**; connection.py Features bullet is the UAT proposed_text verbatim ("Automatic retransmits on an escalating schedule within each request's / timeout, listening for a reply throughout"), matching overview.md:150 word-for-word; `wall-time` → 0 in connection.py; discovery.py public paragraph reads "re-broadcast several times on an escalating schedule"; `Photons-shaped` ×1 and `cumulative offsets` ×1 remain only at the private/unrendered discovery.py sites (correct per the out-of-scope map) |
| 5 | Zero planning IDs on published API pages; traceability demoted, never deleted (G-05-6) | ✓ VERIFIED | Same 53-file sweep: zero `(ANIM|DISC|RETRY|DOCS)-nn`/`Dn-nn`/spike/plan hits in public docstrings; demotion map verified line-by-line: RETRY-01..04 + D3-01..05 in connection.py:494-496 `# Traceability` comment; D4-01..04 + spike 003 figure in packets.py:157-159; D4-04/Glowup/ANIM-04 UAT/plan 04-07 in packets.py:275-278; ANIM-01/ANIM-02/D4-02..04 preserved untouched in animator.py:5 module docstring and :162-165 comments |
| 6 | No D5-09 tuning constant in rendered prose; public defaults legitimately remain | ✓ VERIFIED | Sweep patterns (0.0%, frames/s, roughly one second, two or more probe, cumulative offsets) → 0 across all 53 files; Animator docstring read in full — "slow floor" with no figure, no gate threshold, no expiry; discovery.py keeps only the ~4 s idle window (derived from the two PUBLIC parameters named beside it, per CLAUDE.md) and 15 s `DISCOVERY_TIMEOUT` (documented public default, D5-13 precedent); connection.py Args keep only defaults 8 and 16.0 (documented API) |
| 7 | D5-22 audit ran over every :::-reachable docstring, all three defect classes | ✓ VERIFIED | Both sweeps re-executed by this verifier (not trusted from the SUMMARY): vocabulary+constants sweep clean over 53 files; blank-line AST sweep over the whole src/lifx tree clean against exactly the 15-key pinned allowlist — no unexpected residual, no unexplained allowlist growth |
| 8 | `uv run zensical build --strict` exits 0 — zero warnings, baseline eliminated (G-05-7/D5-23) | ✓ VERIFIED | Orchestrator-run against the current tree: `--clean --strict` → "No issues found", exit 0 (full clean build; single-run rule — not re-run). Corroborated independently against the build output: run-on detector 0, `discover_mdns` ×13 in site/api/high-level/index.html, mDNS symbols ×47 in site/api/network/index.html — the three formerly-dangling api/index.md anchors resolve |
| 9 | CI gates on --strict in both docs.yml invocations (G-05-7c) | ✓ VERIFIED | docs.yml:56 and :114 both read `uv run zensical build --clean --strict`; no un-strict invocation remains |
| 10 | Three mDNS symbols render on their index-linked pages, audited before going live | ✓ VERIFIED | `::: lifx.api.discover_mdns` at high-level.md:13; `::: lifx.network.mdns.discover_lifx_services` at network.md:21 and `LifxServiceRecord` at :27; network.md `^::: ` count = 7 (was 5); the mdns modules resolve into the 53-file sweep set automatically and are clean (D5-23 inheritance discharged) |
| 11 | pytest/ruff/format/pyright all green | ✓ VERIFIED | Orchestrator-run: 2618 passed + 12 deselected (baseline), ruff clean, 228 files formatted, pyright 0/0 (single-full-run rule; not re-run) |
| 12 | (backstop) Rewritten prose preserves every behavioural claim, introduces no new factual claim | ✓ VERIFIED | Explicit evidence, no abstention needed: every rewritten docstring read in full. Connection Args claims (max_retries+1 transmissions; keeps listening until timeout; timeout as overall wall limit) restate RETRY-01/02/03 semantics the previous docstring carried in jargon form; Animator/send_frame claims (ack-paced, latest-frame-wins, drop-never-queue, degrade-not-stall, synchronous non-blocking sweep) match the flow.py/animator contract verified in cycle 2; discovery claims (escalating re-broadcast, per-serial dedup, idle-window completion) match DISC-01/02 and CLAUDE.md; the quickstart's new from_ip claim traced to base.py:454-516 line-by-line. No timing figure, diagram, or override guidance was added anywhere (the open D5-09 dispute was not acted on) |

**Score:** 12/12 truths verified (0 present, behaviour-unverified)

### Roadmap Success Criteria (regression — all hold)

| SC | Status | Evidence |
| --- | --- | --- |
| SC1: gen4 wake-tail documented (sub-250 ms, polling guidance, no keepalive daemon) | ✓ HOLDS | troubleshooting.md untouched this cycle: `sub-250 ms wake tail` (:341), gen4-only scoping (:328), `keep_awake` polling recipe with `asyncio.sleep(15)` (:359), "deliberately ships no keepalive daemon" admonition (:374); faq.md:250 restates it |
| SC2: streaming-consumer guidance (ack-gated pacing, latest-frame-wins, do-not-reimplement) | ✓ HOLDS | user-guide/animation.md untouched this cycle: "paces frame delivery against device acknowledgements" (:332), no-consumer-facing-configuration (:334), "Frame-retry wrappers — retrying a dropped frame is actively wrong" (:346), degradation-by-design framing (:374/:391); api/animation.md now states the same contract with the operator's improved lead-in |
| SC3: docs build cleanly with content linked from relevant pages | ✓ HOLDS — STRENGTHENED | Build now passes `--strict` with ZERO warnings (previous cycles pinned an 8-warning baseline); all cross-links and the three mDNS anchors resolve; CI enforces the class permanently |

### Regression Check — Previously Verified Truths (quick sanity on this cycle's touched files)

- connection.py 05-05 correlation bullet intact: "Response correlation: a background receiver routes each reply to its request, so concurrent requests never mix"
- api.py:620 `Colors.WARM` untouched — api.py diff vs c139542 is exactly one hunk, one inserted blank line at :681 (apply_theme docstring)
- discovery.py `async for device in discover_devices(` Example intact; Returns:/Raises:/Example: lines absent from the diff
- api/animation.md bullets 1-2 byte-preserved inside the new lead-in ("paced against device acknowledgements" ×1, latest-frame-wins framing intact)
- Version neutrality (D5-12): `grep -rlE 'Since v[0-9]' docs/ CLAUDE.md src/` → 0 files
- troubleshooting.md, faq.md, CLAUDE.md, user-guide/animation.md, mkdocs.yml, docs/changelog.md: all absent from the c139542..HEAD execution diff — every prior truth hosted on them holds by non-modification

**No regressions found.**

### Required Artifacts (05-06 — all 12)

| Artifact | Contains gate | Status |
| -------- | ----------- | ------ |
| `docs/getting-started/quickstart.md` | "unicast discovery round-trip" | ✓ VERIFIED (phrase wraps across lines 97-98 — present in the rendered text; verified by reading, not grep) |
| `docs/architecture/overview.md` | "unicast discovery round-trip" ×1 (:253) | ✓ VERIFIED |
| `docs/api/animation.md` | "purpose-built network stack with the following characteristics" ×1 | ✓ VERIFIED |
| `src/lifx/network/connection.py` | "Automatic retransmits on an escalating schedule within each request's" ×1 | ✓ VERIFIED |
| `src/lifx/network/discovery.py` | "re-broadcast several times on an escalating schedule" ×1 | ✓ VERIFIED |
| `src/lifx/animation/animator.py` | "no flow-control toggle; consumers keep" ×1 | ✓ VERIFIED |
| `src/lifx/animation/packets.py` | "# Traceability:" ×2 (:157, :275) | ✓ VERIFIED |
| `src/lifx/devices/ceiling.py` | "Either:" (four Args-nested lists; whitespace-only, 0 deletions) | ✓ VERIFIED |
| `docs/api/effects.md` | "(`list[Light]`)" ×5, unbackticked form ×0, :194 heading form present | ✓ VERIFIED |
| `docs/api/high-level.md` | `::: lifx.api.discover_mdns` (:13, insertion-only diff) | ✓ VERIFIED |
| `docs/api/network.md` | `::: lifx.network.mdns.discover_lifx_services` (:21; insertion-only diff; existing 5 blocks byte-identical) | ✓ VERIFIED |
| `.github/workflows/docs.yml` | `--strict` ×2 (:56, :114) | ✓ VERIFIED |

### Key Link Verification (05-06 — all 6)

| From | To | Via | Status |
| ---- | --- | --- | ------ |
| connection.py | overview.md | rendered bullet states the same retransmit contract in the same words ("Automatic retransmits on an escalating schedule within each request's timeout" — overview.md:150 verbatim) | ✓ WIRED |
| docs/api/animation.md | docs/user-guide/animation.md | shared ack-paced latest-frame-wins wording ("against device acknowledgements" on both pages: api bullet 2, guide :332) | ✓ WIRED |
| quickstart.md | src/lifx/devices/base.py | IP-only lead-in describes exactly what from_ip() ships (base.py:454-516 read in full); serial+IP example matches the docs/index.md:41 constructor precedent | ✓ WIRED |
| animator.py | flow.py | rewritten Animator docstring states only the behavioural contract flow.py implements ("latest-frame-wins" present; tuning constants stay in flow.py, which is unchanged and unrendered) | ✓ WIRED |
| docs/api/index.md | docs/api/high-level.md | index's untouched discover_mdns link resolves — target exists, symbol renders (×13 in built HTML) | ✓ WIRED |
| docs/api/index.md | docs/api/network.md | index's untouched mDNS links resolve — both targets exist, symbols render (×47 in built HTML); --strict exit 0 proves zero dangling anchors | ✓ WIRED |

### Fence Verification (all diffs run against c139542, the plan's pinned base)

| Fence | Gate | Result |
| --- | --- | --- |
| D5-19/API-01: api.py deferred defects untouched | api.py diff = exactly 1 insertion / 0 deletions / 1 hunk (the apply_theme blank line at :681); ranges 260-331/515-557/974-1016 byte-identical | HELD |
| D5-21: create_device Returns:/Raises: untouched | discovery.py diff contains zero Returns:/Raises:/Example: lines | HELD |
| Widened D5-14: no existing ::: block or changelog edit | animation.md diff has zero `:::` lines; high-level.md and network.md diffs have 0 deletion lines (insertion-only); changelog.md diff empty; docs/api execution diff = exactly animation/effects/high-level/network | HELD |
| D5-23 narrow: effects.md exactly the 5 defects | effects.md diff deletions beyond `list[Light]` annotation lines → NONE | HELD |
| api/index.md untouched | diff empty | HELD |
| D5-01: no nav change, no new pages | mkdocs.yml diff empty; `created: []` in SUMMARY confirmed — no new files in the execution commits | HELD |
| D5-12: version neutrality | `Since v[0-9]` → 0 files across docs/, CLAUDE.md, src/ | HELD |
| base.py from_ip docstring fenced | base.py diff = 2 hunks at :275 and :746 (the two authorised blank lines); zero mentions of from_ip in the diff | HELD |
| Whitespace-only sites | all 10 pure-whitespace files show 0 deletion lines — no existing character changed | HELD |
| Comments/unrendered docstrings untouched except 3 additive Traceability comments | const.py and flow.py absent from the diff; connection.py:518 comment still opens "Photons-shaped retransmit schedule. Read the module attribute"; discovery.py private docstring keeps its lineage adjective and offsets (×1 each) | HELD |

### Data-Flow Trace (Level 4)

N/A in the component sense — this is a documentation phase. The equivalent trace performed: published claim → shipped source. Every factual claim in the rewritten prose was traced to its implementing code (base.py from_ip round-trip, connection.py receiver/correlation model, flow.py ack gate, discovery.py re-broadcast schedule and dedup). No claim without a source; no hollow prose found.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Docs build cleanly under strict (SC3/G-05-7) | `uv run zensical build --clean --strict` | "No issues found", exit 0 | ✓ PASS (orchestrator-run, current tree; corroborated against built-site artifacts) |
| Full test suite | `uv run --frozen pytest` | 2618 passed, 12 deselected | ✓ PASS (orchestrator-run; single-full-run rule) |
| Vocabulary/constants sweep | verifier-run AST scan over live target-derived set | 53 files, zero hits | ✓ PASS (independent re-run) |
| Blank-line sweep | verifier-run AST scan over src/lifx | clean vs 15-key allowlist | ✓ PASS (independent re-run) |
| Run-on paragraph detector | verifier-run regex over site/api/*.html | 10 pages, 0 run-ons | ✓ PASS (independent re-run) |
| Claimed commits exist | `git cat-file -t` | 64aff6e, 6d0280d, 95c60d6 all commits; messages match SUMMARY | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exist and no plan declares probes — N/A for this documentation phase. The strict build, full suite, and the three verifier-run sweeps are the runnable gates; all executed against the current tree.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| DOCS-01 | 05-01, 05-04, 05-05, 05-06 | Gen4 wake-tail documented (sub-250 ms; when to poll; no keepalive daemon) | ✓ SATISFIED | Wake-tail section, polling recipe, and no-keepalive admonition all hold (untouched this cycle); the adjacent direct-connection guidance is now honest about the IP-only unicast round-trip (G-05-2) |
| DOCS-02 | 05-02, 05-03, 05-04, 05-05, 05-06 | Streaming-consumer guidance (what the layer handles, what not to reimplement) | ✓ SATISFIED | User-guide contract holds; the API reference now states the same contract behind an accurate lead-in (G-05-3), in reader vocabulary free of lineage jargon, planning IDs, and tuning constants (G-05-5/G-05-6), with lists rendering as lists (G-05-4) and the mDNS API published (G-05-7b) |

No orphaned requirements: REQUIREMENTS.md maps exactly DOCS-01 and DOCS-02 to Phase 5 (both Complete); 05-06 claims exactly those two. The deferred API-01(a)-(d) entries exist in REQUIREMENTS.md as D5-19/D5-21 specify. Not gaps: the D5-19 api.py behavioural defects and create_device docstring mismatch (deferred to API-01 by operator decision) and the D5-09 timing-documentation dispute (BLOCKED on an open decision + spike candidate 006).

### Flagged Planner Assumptions (05-06 — verifier dispositions)

1. **Idempotency** — Upheld. Every replaced source string now greps to 0 (`No Discovery`, `bypasses the connection layer`, `is by design`, `wall-time`, `(list[Light])`, all planning-ID parentheticals); re-execution would be a detectable no-op.
2. **Concurrency** — Upheld. Three sequential signed commits (64aff6e, 6d0280d, 95c60d6), each a self-contained slice; final state green under --strict and the full suite.
3. **Live verifier instruction** — Followed. G-05-5/G-05-6 judged by the RENDERED surfaces: built-HTML run-on detector (0), built-HTML mDNS presence, and the target-derived public-docstring sweeps (private docstrings and # comments excluded by construction). G-05-7 judged by the --strict exit code and the docs.yml diff. All factual claims independently probed against shipped source, not the SUMMARY.

### Flagged Prohibitions (judgment-tier — NON-AUTHORITATIVE LLM-judge verdicts; human review recommended)

All 9 prohibitions in 05-06 are judgment-tier (category: values, no test-tier enforcement). Autonomous run: each carries a non-authoritative verdict; none silently passes.

| # | Prohibition (abridged) | LLM-judge verdict | Evidence |
| --- | --- | --- | --- |
| 1 | D5-19/D5-21: deferred api.py defects + create_device Returns:/Raises: untouched | upheld | api.py diff = 1 blank line at :681 only; discovery.py diff has zero Returns:/Raises:/Example: lines |
| 2 | D5-09 as written: no tuning constants; no dispute work (timings/override guidance/diagram) | upheld | Sweep patterns → 0 across 53 files; all new prose read in full — no timing figure, no diagram, no override guidance anywhere |
| 3 | D5-12: no version attribution | upheld | `Since v[0-9]` → 0 files across docs/, CLAUDE.md, src/ |
| 4 | Widened D5-14 / narrow D5-23: no existing ::: edits; changelog fenced; docs/api edits confined | upheld | animation.md diff zero ::: lines; high-level/network insertion-only; effects.md deletions only annotation lines; index.md and changelog.md diffs empty; no other docs/api page in the diff |
| 5 | D5-01: no mkdocs.yml nav changes, no new pages | upheld | mkdocs.yml diff empty; zero created files |
| 6 | Comments/unrendered docstrings untouched except 3 additive Traceability comments | upheld | const.py/flow.py absent from diff; connection.py:518 comment intact; discovery.py private sites keep lineage vocabulary (×1 each, exactly the out-of-scope map) |
| 7 | base.py from_ip docstring untouched; only two blank-line insertions | upheld | base.py diff = hunks at :275/:746 only; from_ip absent from diff |
| 8 | Whitespace-only sites: zero character changes | upheld | 0 deletion lines in all 10 pure-whitespace files |
| 9 | No traceability deleted outright | upheld | Demotion map verified: all removed IDs present in connection.py:494-496, packets.py:157-159/:275-278, or pre-existing animator.py/discovery.py unrendered surfaces |

### Anti-Patterns Found

No TBD/FIXME/XXX markers in any of the 21 files modified by this plan (the plan's own `planner-discipline-allow` annotation lives in .planning/, not shipped code). No stub patterns, placeholder text, or empty implementations — all edits are prose/whitespace corrections verified against source.

### Human Verification Required

#### 1. Prohibition verdict review

**Test:** Review the 9 upheld judgment-tier prohibition verdicts above at the end-of-phase checkpoint.
**Expected:** Human concurs the fences and content constraints held.
**Why human:** Autonomous-run judgment-tier verdicts are non-authoritative by rule; per fail-closed routing they must not be silently absorbed into a passed verdict. Verdicts 2 (no new factual claims / D5-09 discipline in the rewritten prose) and 9 (demotion completeness) rest most heavily on prose judgement.

### Gaps Summary

None. All six operator-diagnosed UAT gaps are closed and verified against shipped source and the built site: the quickstart and architecture pages now tell the truth about the IP-only unicast round-trip (traced line-by-line to base.py:454-516), the animation API page carries the operator's agreed lead-in verbatim, every published docstring list renders as a list (0 run-ons, was 23), no published sentence requires knowing Photons, Glowup, or GSD planning vocabulary (53-file sweep clean, re-run independently), all demoted IDs survive as comments, the three public mDNS symbols render on the pages api/index.md always linked, and the docs build is warning-free under `--strict` with CI gating on it permanently — the 8-warning baseline is eliminated, not re-pinned. All 12 plan must-haves verify, all 3 roadmap success criteria hold (SC3 strengthened), and no prior truth regressed. The only outstanding item is the human checkpoint on the 9 judgment-tier prohibition verdicts.

---

_Verified: 2026-07-17T13:38:09Z_
_Verifier: Claude (gsd-verifier)_
