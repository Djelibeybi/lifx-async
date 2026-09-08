---
phase: 17-fleet-diagnostics-and-the-staleness-control
plan: 03
subsystem: diagnostics
tags: [evidence, hardware, mdns, ipv6, thread, privacy, redaction]

requires:
  - phase: 17-fleet-diagnostics-and-the-staleness-control (plan 02)
    provides: "The opt-in --alias-map redaction (_load_probe_alias_map(), _TranscriptRedactor, --alias-map CLI flag) this plan's capture used unmodified"
provides:
  - "17-EVIDENCE/17-PROBE-TRANSCRIPT.md: one committed, redacted, real Thread-fleet run of the changed probe, evidencing R4/MDNS-10 on hardware rather than fixtures alone"
  - "SPEC amendment A7, applied and closed out: a firmware-assigned bare-hex SRV .local label is accepted as committable evidence, with the backstop's label-hex boundary defect fixed and the widening scoped to non-twelve-character all-hex labels"
affects: [17-04-fleet-diagnostics-and-the-staleness-control, 17-05-fleet-diagnostics-and-the-staleness-control]

actuals:
  tokens: 3100
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Two-category identity backstop (D-23): identifier-only shapes block the gate outright; an all-decimal twelve-character run or an alias-shaped-but-unverifiable .local label is enumerated for operator adjudication instead of failing closed with no route forward"

key-files:
  created:
    - .planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/17-PROBE-TRANSCRIPT.md
  modified: []

key-decisions:
  - "Operator adjudicated the gate's full local-tokens-for-operator list (46 entries) as exactly two classes with no residue: the 10 bare-hex 16-character SRV labels A7 names, and 36 operator-chosen LIFX-<Type>-<n> aliases (including several LIFX-<Type>-<hex-group> instance names for Candle, Ceiling 13x26, DL Intl, Luna, Mini, Neon Outdoor and Tube, which are the alias map's own format-preserving pseudonyms in LIFX's dashed-hex naming convention for those product families, not raw device identifiers)"
  - "AMBIGUOUS-NUMERIC-TOKENS reported none, so no numeric-artefact adjudication was required at Task 3"
  - "Did not hand-edit the committed transcript to record the Task 3 adjudication narrative; Task 2's action explicitly forbids any edit after staging (the index/worktree parity gate exists precisely to catch that), so the adjudication and its basis are recorded here in the SUMMARY instead, which is where D-23's AMBIGUOUS-NUMERIC-TOKENS adjudication was already specified to live"

requirements-completed: [MDNS-10]

coverage:
  - id: D1
    description: "One real Thread-fleet run of the changed probe, captured under pipefail with its own exit status recorded, redacted by --alias-map, and committed as 17-EVIDENCE/17-PROBE-TRANSCRIPT.md"
    requirement: "MDNS-10"
    verification:
      - kind: other
        ref: "Task 2 shape gate (TRANSCRIPT-SHAPE-OK): required headings and Probe exit status: 0 present"
        status: pass
      - kind: other
        ref: "Task 2 element-status gate (ELEMENT-DEFECTS: none): recorded date parses as ISO, all five element keys carry an explicit observed/not-observed status with a captured Would have needed: marker of at least 40 characters on each not-observed element"
        status: pass
      - kind: other
        ref: "Task 2 fenced-transcript gate (missing-transcript-elements=[], transcript-lines=289): the fence inside ## Transcript, selected by position, holds an instance header, an SRV line, a CHOSEN line and the summary block"
        status: pass
      - kind: other
        ref: "Task 2 em-dash gate (em-dash-lines=[])"
        status: pass
      - kind: other
        ref: "Task 2 index/worktree parity gate (INDEX-WORKTREE-PARITY-OK)"
        status: pass
      - kind: other
        ref: "Task 2 identity backstop over the staged diff (IDENTITY-SHAPED-TOKENS: none, AMBIGUOUS-NUMERIC-TOKENS: none, staged-added-lines=350)"
        status: pass
      - kind: other
        ref: "Task 2 v2.0-evidence-untouched gate (V2.0-EVIDENCE-UNTOUCHED)"
        status: pass
    human_judgment: true
    rationale: "Task 3 is a blocking operator checkpoint (D-23, AC-22, SPEC prohibition P3) inspecting the staged diff's local-tokens-for-operator list against the private mapping and the operator's own network knowledge; no automated check can perform that inspection, and the SPEC resolves it as judgment rather than test."

duration: 12min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 3: Thread-fleet probe hardware evidence for MDNS-10 Summary

**One redacted, real Thread-fleet run of the changed probe (23 instances, 59 packets, 0 malformed) committed as `17-EVIDENCE/17-PROBE-TRANSCRIPT.md`, with SPEC amendment A7's firmware-hex-label class adjudicated and accepted at the Task 3 checkpoint.**

## Performance

- **Duration:** 12 min (this resumed session; Task 1's hardware capture and Task 2's assembly were completed by a prior session, halted at the identity backstop pending SPEC amendment A7)
- **Started:** 2026-09-08T15:40:00+10:00
- **Completed:** 2026-09-08T15:52:00+10:00
- **Tasks:** 3 (Task 1 and Task 2 already satisfied on entry; this session resumed at Task 2's verification, then ran Task 3)
- **Files modified:** 1

## Accomplishments

- Re-ran all seven of Task 2's `<verify>` gates against the staged transcript, amended in commit `dd4d97b` after SPEC amendment A7: shape, recorded-date/element-status, fenced-transcript-content (selected by position), em-dash, index/worktree parity, the identity backstop (with A7's label-hex boundary fix and the entirely-hexadecimal-and-not-twelve-characters widening), and the v2.0-evidence-untouched guard. All seven passed
- The identity backstop reported `IDENTITY-SHAPED-TOKENS: none` and `AMBIGUOUS-NUMERIC-TOKENS: none` with `staged-added-lines=350`, and enumerated 46 `.local` tokens under `local-tokens-for-operator`
- Classified all 46 enumerated tokens programmatically: exactly 10 are the 16-character bare-hex SRV labels A7 names (`028E70F024E538FA.local` through `FAAF9CFE7AB46C6E.local`), matching A7's "ten matrix-class instances" count precisely; the remaining 36 are `LIFX-`-prefixed operator-chosen aliases with no residue outside those two classes
- Ran Task 3's operator-inspection checkpoint. The operator had already adjudicated both label classes when authoring SPEC amendment A7 and the instructions for this resumption: the 10 firmware-assigned bare-hex labels are accepted on the packet-inspection finding recorded in A7 (no mapping to a real device identifier in either direction), and the 36 `LIFX-<Type>-<n>` aliases are accepted as the operator's own deliberately-chosen, non-sensitive names. No genuinely new or unaccounted-for token class was found. `AMBIGUOUS-NUMERIC-TOKENS: none` meant no numeric-artefact adjudication was required
- Committed the transcript alone (`e950cc8`), not the `17-EVIDENCE/` directory, per the plan's output instructions
- Marked `MDNS-10` complete via `requirements mark-complete` — all three plans declaring it (`17-01`, `17-02`, `17-03`) now carry a `*-SUMMARY.md`

## Task Commits

1. **Task 1: Run the changed probe against the real Thread fleet with redaction enabled** — satisfied by the operator before this session (hardware run, `probe-exit=0`, 2026-09-08, git revision `50063fab244fca07d50b7ede09be26e9417e61b6`, 23 instances, 59 packets, 0 malformed); no commit of its own, evidence assembled into the transcript by a prior session
2. **Task 2: Assemble the narrated transcript, stage it, and run the identity backstop over the staged diff** — assembled and staged by a prior session; this session re-ran all seven `<verify>` gates against the amended backstop, no new commit (the transcript file itself was unchanged)
3. **Task 3: Operator inspection of the staged diff against the private mapping** — `e950cc8` (docs(evidence): commit real Thread-fleet probe transcript for MDNS-10)

**Plan metadata:** committed below (docs: complete plan)

## Files Created/Modified

- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/17-PROBE-TRANSCRIPT.md` - MDNS-10's hardware evidence: instrument, exit status, per-element observed/not-observed disposition (AC-11), and the redacted stdout capture

## Decisions Made

- The Task 3 checkpoint's operator adjudication (both label classes accepted, basis stated) is recorded here in the SUMMARY rather than by editing the committed transcript, because Task 2's action explicitly forbids any edit to the transcript after staging (the index/worktree parity gate exists to catch exactly that drift), and the checkpoint's own instructions specify the plan SUMMARY as where an adjudication decision is recorded
- No re-redaction was needed: the identity backstop's `IDENTITY-SHAPED-TOKENS: none` and the operator's classification of every `local-tokens-for-operator` entry into the two accepted classes confirmed the staged diff carries no live serial, MAC, address literal outside the six reserved forms, or unaccounted-for hostname

## Deviations from Plan

None - plan executed exactly as amended. The identity backstop's amendment (label-hex boundary fix plus A7's widening) was already applied to `17-03-PLAN.md` in commit `dd4d97b` before this session began; this session used the plan exactly as it reads on disk.

## Issues Encountered

None. The prior session's halt at the identity backstop was the correct behaviour for an unresolved SPEC gap, not an error; SPEC amendment A7 resolved it before this session resumed.

## User Setup Required

None - Task 1's hardware precondition (private alias map outside the repository, Thread fleet powered and advertising) was already satisfied by the operator before this session.

## Next Phase Readiness

- R4 is CLOSED: the committed transcript at `17-EVIDENCE/17-PROBE-TRANSCRIPT.md` is the evidence D-21 (as amended) required
- `MDNS-10` is now fully satisfied at the requirement level (all three declaring plans summarized)
- `17-04-PLAN.md` (wave 4, the WiFi staleness trial) can proceed. It depends on this plan finishing, not on it succeeding, and this plan finished successfully with R4 closed rather than left open
- `17-04-PLAN.md`'s Task 5 checkpoint must still confirm that any device appearing in both this transcript and the WiFi staleness evidence carries the same alias in both (AC-24); the aliases visible in this committed transcript are the ones to match against
- No blockers

## Self-Check: PASSED

- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/17-PROBE-TRANSCRIPT.md` — FOUND
- Commit `e950cc8` — FOUND

---
*Phase: 17-fleet-diagnostics-and-the-staleness-control*
*Completed: 2026-09-08*
