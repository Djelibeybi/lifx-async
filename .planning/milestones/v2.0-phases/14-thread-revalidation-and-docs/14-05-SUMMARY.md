---
phase: 14-thread-revalidation-and-docs
plan: 05
subsystem: docs
tags: [mkdocs, pymdownx-snippets, discovery, mdns, asyncio, agents-md, claude-md]

# Dependency graph
requires:
  - phase: 14-thread-revalidation-and-docs (plan 01)
    provides: request-observer seam and scripts groundwork (unrelated to this plan's files, but shares the phase branch)
provides:
  - Canonical consumer-journey discovery guide (docs/user-guide/discovery.md)
  - Single executable source for discovery migration snippets (examples/discovery_progressive.py)
  - Strict pymdownx.snippets path checking (mkdocs.yml)
  - AGENTS.md as the sole canonical shared/GSD architecture source
  - CLAUDE.md reduced to an @AGENTS.md import
affects: [docs, AGENTS.md, CLAUDE.md, mkdocs.yml, tests/test_network/test_mdns]

# Actuals (#2632)
actuals:
  tokens: 17934
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pymdownx.snippets region markers (--8<-- [start:x]/[end:x]) as the single executable source for guide code samples"
    - "AGENTS.md canonical / CLAUDE.md import-only for shared architecture guidance"

key-files:
  created:
    - docs/user-guide/discovery.md
    - examples/discovery_progressive.py
    - tests/test_repository_guidance.py
  modified:
    - docs/user-guide/advanced-usage.md
    - docs/api/network.md
    - docs/user-guide/troubleshooting.md
    - mkdocs.yml
    - AGENTS.md
    - CLAUDE.md
    - tests/test_network/test_mdns/test_phase_contract.py

key-decisions:
  - "Removed CLAUDE.md from _REQUIRED_QUERY_MODEL_PATHS in test_phase_contract.py rather than trying to satisfy both the old duplication contract and the new import-only contract on the same file — the two were mutually exclusive, as the Phase 14 review flagged."
  - "Fixed two additional verified-wrong facts in AGENTS.md while already editing the file (Pyright standard vs strict mode, 26 vs 30+ built-in effects) per the project's 'if you see it, fix it' rule; left broader Testing Strategy count staleness (both files, pre-existing, unrelated to this task) untouched as out of scope."
  - "CLAUDE.md's only retained content beyond the @AGENTS.md import is a one-line note about Skill() invocation syntax — no other genuinely Claude-specific guidance was found to preserve."

requirements-completed: [DOCS-04, DOCS-05, DOCS-06]

coverage:
  - id: D1
    description: "Canonical discovery.md guide with one executable progressive example covering discover(), discover_udp(), discover_mdns() and targeted find_by_ip()/IPv6 lookup"
    requirement: "DOCS-04"
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_phase_contract.py::TestPhase14DiscoveryGuideContract"
        status: pass
    human_judgment: false
  - id: D2
    description: "Advanced usage, API reference and troubleshooting pages link to the guide instead of duplicating it; mkdocs.yml enforces check_paths so a broken snippet include fails the real build"
    requirement: "DOCS-04"
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_phase_contract.py::TestPhase14DiscoveryLinkingContract"
        status: pass
      - kind: other
        ref: "uv run --frozen zensical build (manually broke and restored a snippet path to confirm check_paths fails loudly)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Discovery guide documents the four mDNS limitations (IPv4 multicast query, legacy-unicast-only replies, no unsolicited announcements, synthetic mesh-scale proof) plus merged/source-specific visibility and the Phase 14 fleet-specific evidence qualification"
    requirement: "DOCS-05"
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_phase_contract.py::TestPhase11SurfaceContract::test_public_guidance_uses_the_approved_limitation_phrases"
        status: pass
    human_judgment: false
  - id: D4
    description: "AGENTS.md and CLAUDE.md contain no false asyncio.TaskGroup device-concurrency claim; AGENTS.md documents Python 3.10-compatible asyncio.gather()/asyncio.create_task() fan-out; troubleshooting.md's keepalive-poll example uses the same 3.10-compatible pattern"
    requirement: "DOCS-06"
    verification:
      - kind: integration
        ref: "tests/test_repository_guidance.py"
        status: pass
      - kind: integration
        ref: "tests/test_network/test_mdns/test_phase_contract.py::TestPhase14DiscoveryLinkingContract::test_troubleshooting_gives_python_310_compatible_fan_out_advice"
        status: pass
    human_judgment: false
  - id: D5
    description: "AGENTS.md is the sole shared/GSD architecture source; CLAUDE.md is a literal @AGENTS.md import plus only Claude-specific content; the two formerly conflicting test contracts (duplication vs import-only) now encode complementary rules"
    requirement: "DOCS-06"
    verification:
      - kind: integration
        ref: "tests/test_repository_guidance.py::TestClaudeImportsAgents"
        status: pass
      - kind: unit
        ref: "uv run --frozen pytest (full suite, 4495 passed)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-04
status: complete
---

# Phase 14 Plan 05: Discovery Guide, Snippet Enforcement, AGENTS/CLAUDE Canonicalisation Summary

**One executable-example discovery guide (docs/user-guide/discovery.md + examples/discovery_progressive.py) replacing duplicated UDP/mDNS prose across advanced-usage.md/network.md/troubleshooting.md, strict pymdownx.snippets path checking in mkdocs.yml, a corrected Python 3.10 asyncio.gather()/create_task() story in place of the false asyncio.TaskGroup claim, and CLAUDE.md reduced to a literal @AGENTS.md import.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-09-04T13:20:00+10:00 (approx.)
- **Completed:** 2026-09-04T13:38:29+10:00
- **Tasks:** 3
- **Files modified:** 10 (3 created, 7 modified)

## Accomplishments

- Created `docs/user-guide/discovery.md`, the canonical consumer-journey discovery guide (unchanged `discover()` migration, explicit `discover_udp()`/`discover_mdns()` control, targeted `find_by_ip()`/IPv6 lookup, method-selection table, the four mDNS limitations plus a fleet-specific Phase 14 evidence qualification, and troubleshooting).
- Created `examples/discovery_progressive.py` as the single executable source for the guide's code snippets, using `pymdownx.snippets` region markers and only RFC 5737/RFC 3849 documentation addresses.
- Moved the substantive UDP/mDNS material out of `docs/user-guide/advanced-usage.md` (replaced with a summary and link), linked `docs/api/network.md` to the guide while keeping it signature-led, and configured `pymdownx.snippets` with `check_paths: true`/`base_path: [.]` so a broken snippet include fails the real `zensical build` (verified by deliberately breaking and restoring one).
- Replaced the Python-3.11-only `asyncio.TaskGroup` keepalive recommendation in `docs/user-guide/troubleshooting.md` with Python 3.10-compatible `asyncio.create_task()` ownership/cancellation guidance.
- Resolved the direct test conflict the Phase 14 review flagged: reduced `CLAUDE.md` to an `@AGENTS.md` import (removing ~460 lines of drifted duplicate prose) and removed `CLAUDE.md` from `_REQUIRED_QUERY_MODEL_PATHS` in `test_phase_contract.py`, while `tests/test_repository_guidance.py` now proves the import exists and no shared architecture guidance is duplicated in `CLAUDE.md`.
- Fixed the false `asyncio.TaskGroup` device-concurrency claim in `AGENTS.md` (now `asyncio.gather()`/`asyncio.create_task()`, with the Python 3.10 floor and the 3.11 TaskGroup requirement named explicitly) and the inaccurate `find_by_ip()` "targeted broadcast" description (now targeted UDP unicast with IPv6 zone handling).

## Task Commits

Each task was committed atomically:

1. **Task 1: Create the executable progressive discovery journey** - `7f4c69c` (feat)
2. **Task 2: Link the canonical guide, enforce snippet paths and correct user-facing concurrency advice** - `79d8eb5` (docs)
3. **Task 3: Resolve the AGENTS/CLAUDE contract conflict (TDD)** - `f73ebb9` (test, RED) → `6e2829c` (feat, GREEN)

**Plan metadata:** committed separately after this SUMMARY (docs: complete plan)

_Note: Task 3 used TDD (RED/GREEN); no REFACTOR commit was needed._

## Files Created/Modified

- `docs/user-guide/discovery.md` - New canonical discovery guide (created)
- `examples/discovery_progressive.py` - New single executable source for guide snippets (created)
- `docs/user-guide/advanced-usage.md` - Discovery Methods section replaced with summary + link; duplicate method-selection table removed
- `docs/api/network.md` - Links to the Discovery Guide; stays signature-led
- `docs/user-guide/troubleshooting.md` - Python 3.10-compatible `asyncio.create_task()` guidance replaces `asyncio.TaskGroup`
- `mkdocs.yml` - `pymdownx.snippets` strict path checking; discovery.md added to nav and llmstxt sections
- `AGENTS.md` - TaskGroup claim, find_by_ip() description, Pyright mode and effects count corrected
- `CLAUDE.md` - Reduced to `@AGENTS.md` import plus a Claude-specific Skill() note
- `tests/test_network/test_mdns/test_phase_contract.py` - New `TestPhase14DiscoveryGuideContract` and `TestPhase14DiscoveryLinkingContract` classes; `_PUBLIC_GUIDANCE_PATH` repointed to discovery.md; `CLAUDE.md` removed from `_REQUIRED_QUERY_MODEL_PATHS` (created new test classes; modified existing constants)
- `tests/test_repository_guidance.py` - New AGENTS/CLAUDE canonical-guidance contract test (created)

## Decisions Made

- Removed `CLAUDE.md` from `_REQUIRED_QUERY_MODEL_PATHS` rather than scoping the new no-duplication test to exclude the mDNS block — the two requirements on the same file were flatly incompatible once CLAUDE.md became import-only, and the review's own suggested resolution was to drop CLAUDE.md from that list with the D-24 rationale recorded (done here).
- Fixed two additional verified-wrong AGENTS.md facts encountered while editing the concurrency/find_by_ip prose (Pyright standard vs strict mode; 26 vs "30+" built-in effects) under the project's "if you see it, fix it" rule, since both were one-line, high-confidence, in-file corrections. Left the broader Testing Strategy count staleness (present, unchanged, in both files before this plan) out of scope — it is a larger, fuzzier renumbering effort unrelated to DOCS-06's TaskGroup/Python-floor/query-model scope.
- Kept CLAUDE.md's Claude-specific content to one short note about `Skill()` invocation syntax; no other genuinely Claude-only guidance was found in the original file after removing the drifted architecture duplication.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected Pyright mode and effects-count claims in AGENTS.md**
- **Found during:** Task 3 (AGENTS/CLAUDE canonicalisation)
- **Issue:** AGENTS.md claimed "strict Pyright validation" (actual `pyproject.toml` config: `typeCheckingMode = "standard"`) and "30+ built-in effects" (actual: 26 effect modules in `src/lifx/effects/`) — both directly verifiable and wrong.
- **Fix:** Corrected both bullets (and the matching bash comment and Testing Strategy line) to match verified source/config facts.
- **Files modified:** AGENTS.md
- **Verification:** `grep typeCheckingMode pyproject.toml` and `ls src/lifx/effects/*.py` confirm the corrected values; full test suite passes.
- **Committed in:** `6e2829c` (Task 3 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix, bundled as two related one-line corrections in the same commit)
**Impact on plan:** Small, high-confidence factual corrections made while already editing the same file for the named TaskGroup/find_by_ip fixes. No scope creep beyond AGENTS.md itself; broader Testing Strategy staleness deliberately left untouched.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Docs work for DOCS-04/05/06 is complete and independent of the Phase 14 hardware evidence plans (14-01/14-02/14-03/14-04/14-06); no blockers for those plans or for CI.
- Full test suite (4495 tests), `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` all pass clean on the files this plan touched.
- `uv run --frozen zensical build` and `uv run --frozen llmstxt-standalone build` both succeed with the new guide in navigation.

---
*Phase: 14-thread-revalidation-and-docs*
*Completed: 2026-09-04*

## Self-Check: PASSED

- All key-files (created and modified) verified present on disk with `[ -f ]`.
- All 5 commit hashes (`7f4c69c`, `79d8eb5`, `f73ebb9`, `6e2829c`, `259eb32`) verified present via `git log --oneline --all`.
- Re-ran all three task-level `<verify>` commands: `tests/test_network/test_mdns/test_phase_contract.py` (23 passed), `zensical build` + `llmstxt-standalone build` (both clean), `tests/test_repository_guidance.py` + `test_phase_contract.py` together (31 passed).
- Re-ran the plan-level `<verification>` checks: all three task commands pass without hardware/network access; SPEC.md's DOCS-04/05/06 edge table confirmed at 12 rows (3 `empty` covered, 9 backstop dismissed); plan frontmatter confirms `wave: 1`, `depends_on: []`.
- Full suite (`uv run --frozen pytest`): 4495 passed. `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`: all clean on files this plan touched.
