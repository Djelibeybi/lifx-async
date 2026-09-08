---
phase: 17
phase_name: "fleet-diagnostics-and-the-staleness-control"
project: "lifx-async"
generated: "2026-09-09"
counts:
  decisions: 8
  lessons: 8
  patterns: 8
  surprises: 6
missing_artifacts:
  - "17-UAT.md"
---

# Phase 17 Learnings: Fleet Diagnostics and the Staleness Control

This phase amended its own specification three times during execution (A7, A8, A9) and ran a
four-pass code review loop. Most of what is worth keeping here comes from those corrections rather
than from the original plans, so the sources skew towards `17-SPEC.md`'s amendments,
`17-SECURITY.md` and `17-REVIEW-FIX.md`.

## Decisions

### Redaction belongs in the tool, not in a hand-substitution step
The probe gained an opt-in `--alias-map` flag rather than the spec phase's original plan of
hand-pseudonymising the committed transcript.

**Rationale:** The decision was originally made without knowing that `thread_revalidation.py` and
`measure_merged_discovery.py` both already carried an alias-map loader reading the mapping from
outside the repository into memory only. With the precedent two scripts deep, a structural
guarantee replaced a manual step. Raw output stays the default because the probe's diagnostic value
depends on naming the physical device.
**Source:** 17-SPEC.md amendment A2, 17-02-PLAN.md

### An arm that cannot run leaves its requirement open, never closed
Both hardware arms could fail independently, and either failing leaves its requirement carried
forward rather than recorded as a closed gap.

**Rationale:** Recording an unrun experiment as a closed gap would launder it as a completed one,
which is what the roster gate exists to prevent. THREAD-01 to THREAD-05 carrying from v1.1 into v2.0
is the precedent.
**Source:** 17-SPEC.md decision D-21 as amended, 17-03-PLAN.md, 17-04-PLAN.md

### The tool's hardcoded evidence filenames are not renamed
The WiFi session's files land as `17-EVIDENCE/14-MANIFEST.json` and `14-STALENESS.jsonl`: a `17-`
prefix on the directory, the tool's own `14-` prefix on the files.

**Rationale:** The names are module-level constants and are not parameterised by `--session-dir`.
`reload_staleness_events()` and the same-alias resume check read those literal names back, so
renaming would break the resume guarantee AC-15 exists to prove.
**Source:** 17-SPEC.md decision D-13 as amended, 17-04-PLAN.md

### Two plans sharing a git index are serialised, not isolated
`17-03-PLAN.md` and `17-04-PLAN.md` moved to separate waves rather than running concurrently in
isolated worktrees.

**Rationale:** File-disjointness was the wrong test. Both stage into the same index and both inspect
the same evidence directory. Isolated worktrees were considered and rejected because two worktrees
would need two commits merged by hand into one branch, adding a merge step to the one part of the
phase where a mistake is unrecoverable.
**Source:** 17-SPEC.md decision D-21 as amended, 17-03-PLAN.md

### A firmware-assigned SRV hostname is committable evidence
Ten matrix-class instances publish a bare sixteen-character hexadecimal `.local` SRV target that the
alias map structurally cannot reach. They are admitted into committed evidence.

**Rationale:** The operator inspected the raw DNS-SD packet and the LIFX details a user can retrieve
from a device, and found no mapping in either direction between such a label and any real
user-retrievable device-specific value. A label that cannot be resolved to a device identity by any
means available to a reader is functionally already a pseudonym.
**Source:** 17-SPEC.md amendment A7

### The tool is pinned by content hash, not by a diff against the base
`17-04-PLAN.md`'s gate pins `thread_revalidation.py` to an exact blob, checked against both `HEAD`
and the working tree, replacing a gate that required the file to be absent from the branch diff.

**Rationale:** The diff form had to change once the operator authorised four tool changes, and a
content hash is strictly stronger: a diff against the base can be satisfied by a revert-and-reapply
pair, a content hash cannot. Any further change must update the hash under an authorising amendment.
**Source:** 17-SPEC.md amendments A8 and A9

### The emitter and the backstop whitelist are one contract
The set of address forms the redactor can emit and the set the staged-diff backstop whitelists must
match exactly, and move together or not at all.

**Rationale:** A code review fix widened the IPv4 pseudonym pool to three RFC 5737 ranges without
widening the whitelist, so the gate would have reported the tool's own correct output as a
live-address leak. That is the same dead end T-17-29 was written to eliminate. The rule was
made explicit rather than left implicit in A5.
**Source:** 17-SPEC.md amendment A9, 17-REVIEW-FIX.md

### Redaction fails closed on an unmapped identifier
With `--alias-map` supplied, a serial the map does not cover now fails the run rather than passing
through raw and silently. The no-map path is untouched.

**Rationale:** The tool's output is committed evidence, so a silent pass-through is fail-open on the
one thing the map governs: a device joining the fleet between map updates would leak by default.
The raw-by-default path stays because naming the physical device is what makes the probe a
diagnostic.
**Source:** 17-REVIEW.md IN-01, 17-REVIEW-FIX.md

---

## Lessons

### A mitigation can be aimed at the wrong file and never have worked
The threat register's mitigation for T-17-14, freezing `thread_revalidation.py` so the cadence, cap
and confirmation rule could not change, could never have achieved that. All three constants are
defined in `measurement_support.py` and merely imported. Freezing an importer freezes nothing.

**Context:** Found by the security audit while checking whether a stale mitigation still held after
A8 authorised four tool changes. The threat is genuinely closed, by the constants' own file being
absent from the branch diff and by the committed manifest recording the literals, but by a
different mechanism than anyone had written down. The gap predated A8 rather than being caused by it.
**Source:** 17-SECURITY.md, note on T-17-14

### A fix applied to one sibling plan does not propagate to the other
The nominal-versus-measured bound defect was fixed in `17-04-PLAN.md`, then found again unfixed in
`17-05-PLAN.md`'s own gates. Separately, amendment A7 anchored the hostname-label test in 17-03's
gate but not 17-04's, while 17-04's prose still claimed the two predicates were deliberately
identical.

**Context:** Both were caught late, one by an executor refusing to publish a figure its evidence
contradicted, the other by the security audit. Sibling plans that duplicate a gate need the
duplication checked whenever either copy changes.
**Source:** 17-05-SUMMARY.md deviations, 17-SECURITY.md UF-02

### Each review pass found the previous fix's own defect
Four passes were needed to reach clean. Pass 2 found that IN-01's fix skipped the interrupt path.
Pass 3's boundary narrowing traded a visible corruption for an invisible miss. The IN-02 fix broke
the emitter/whitelist contract outright and was reverted.

**Context:** A single pass would have left three defects in the tree, each introduced by a fix for a
different one. The iteration cap of three was reached and a fourth pass was run deliberately to
close the loop.
**Source:** 17-REVIEW.md iterations 1 through 4, 17-REVIEW-FIX.md

### For a redactor, a miss is worse than a corruption
The first anchoring of the serial pattern drew its boundary at every alphanumeric, so a serial
adjacent to a non-hex character silently failed to substitute.

**Context:** A miss leaves the identifier intact; the hybrid it was avoiding at least has the
identifier removed. The boundary is now drawn to prefer substituting, and the unmapped-token
detector was narrowed with it so the detector does not share the substituter's blind spot.
**Source:** 17-SECURITY.md UF-01 resolution, 17-REVIEW.md iteration 2

### A recorded quantity can have consumers outside the code that records it
Changing per-poll `elapsed_s` from nominal to measured broke bound-derivation expressions living in
two plan files, not in the source.

**Context:** The plans' gates computed the disappearance bound from the nominal cadence constant.
Left unfixed they would have published `at most 60 s` where the evidence supports `at most
80.85 s`, on the one line the downstream plan consumes as its headline figure.
**Source:** 17-05-SUMMARY.md deviations, 17-SPEC.md amendment A9

### A check placed after a context manager misses the paths that leave it early
The fail-closed unmapped-identifier report sat in sequential code after the `with` block, so a
`KeyboardInterrupt` returned 130 from inside the block and any uncaught exception propagated, both
skipping it entirely.

**Context:** A records sweep takes seconds but a full run does not, so an interrupt is a routine
outcome, and 130 reads like a clean operator-initiated abort while the captured transcript holds raw
identifiers. The report moved into a `finally`.
**Source:** 17-REVIEW.md iteration 2, 17-REVIEW-FIX.md

### An amendment's blanket phrasing can overstate what it verified
Amendment A8 asserted that what R5 names as frozen is untouched. True of the constants, and slightly
overstated about the rule enforcing the cap: change 2 narrowed one assertion so the final poll's
measured time may exceed it.

**Context:** Caught by the security audit rather than at authoring time. The narrowing follows
necessarily from recording measured rather than nominal time, and cannot convert a censored
disposition into an expiry, so the prohibition holds. The wording was corrected rather than left to
be rediscovered.
**Source:** 17-SECURITY.md, note on T-17-14

### A plan's verify command can be defeated by the local shell
The literal `grep -qF "$s"` in a verify block fails when the search string is `--alias-map`, because
a bare double-dash-prefixed pattern is parsed as an unrecognised long option.

**Context:** A shell argument-parsing quirk, not a source defect. Re-running with `grep -qF --` on
the same input confirmed the string was present. Verify commands embedded in plans need the same
argument hygiene as any other shipped script.
**Source:** 17-02-SUMMARY.md issues encountered

---

## Patterns

### Pin a tool by content hash rather than by a diff against the base
Assert an exact blob against both `HEAD` and the working tree.

**When to use:** Whenever a gate needs a file to be exactly some known content, rather than merely
unchanged relative to a branch point. A revert-and-reapply pair satisfies a diff and cannot satisfy
a hash. Pair it with a rule that the hash moves only under an authorising amendment.
**Source:** 17-SPEC.md amendments A8 and A9, 17-04-PLAN.md

### Split a fail-closed gate into blocking and adjudicable categories
Tokens that can only be an identifier fail the gate. Tokens that are ambiguous print on a separate
line without failing, and a human names them at a checkpoint.

**When to use:** When a gate protects something irreversible and its own subject can produce
false positives. Without the split, the checkpoint meant to adjudicate a false positive sits behind
a gate that can never pass, stranding the work after an expensive step.
**Source:** 17-SPEC.md decision D-23, threat T-17-29

### Scope every staged inspection to the plan's own paths
Name individual files in `git add`, `git diff --cached` and every gate, never the shared directory.

**When to use:** Whenever two units of work write into one directory or one git index. It makes a
concurrent run unable to read or judge another's artefacts even if the serialisation that was
supposed to prevent concurrency fails.
**Source:** 17-03-PLAN.md, 17-04-PLAN.md, threat T-17-26

### Report a leak by count, never by echoing the identifier
The unmapped-identifier warning names how many tokens leaked and never which.

**When to use:** Any diagnostic that warns about sensitive content. Echoing an identifier to warn
that an identifier leaked puts a second copy in the operator's scrollback and, under `tee`, in the
capture file as well.
**Source:** 17-REVIEW-FIX.md IN-01

### Emit a safety report from a `finally`
Place the report on the path that runs regardless of how the block is left, and make it incapable of
raising.

**When to use:** When the report tells the operator their output is unsafe. A crash while reporting
a leak would hide the leak, and the interrupt path is often the likeliest exit on long-running work.
**Source:** 17-REVIEW-FIX.md, commit 892cc4a

### Derive a measured bound from what was observed, not from the schedule
Compute an interval from the poll records' own measured times rather than from the nominal cadence
constant.

**When to use:** Any time a sampling loop can overrun its interval. Nominal and measured agree until
they do not, and the disagreement is silent: the recorded figure simply understates.
**Source:** 17-SPEC.md amendment A9, commits 21fd669 and 23aa862

### Prove a regression test fails against the pre-fix code
Load the old and new implementations side by side and confirm the new test genuinely fails against
the old one.

**When to use:** In a final review pass, or any time a test is added alongside the fix it covers. It
is the only way to distinguish a real regression test from one that passes vacuously.
**Source:** 17-REVIEW.md iteration 4

### Record an unrun experiment as open, with the arm's failure named
Name the specific condition that could not be met, and carry the requirement forward.

**When to use:** Whenever evidence collection depends on something outside the automated
environment. It keeps the requirement visible instead of closing it on the strength of an attempt.
**Source:** 17-SPEC.md decision D-21 as amended

---

## Surprises

### WiFi and Thread advertisement staleness differ by roughly two orders of magnitude
The Thread arm held its advertisement for 4140 to 4200 seconds. The WiFi arm's was already gone at
the first poll, bounding it at most 80.85 seconds.

**Impact:** This is the phase's headline finding. The mechanism is that WiFi bulbs have no Thread
Border Router rebroadcasting their records, so nothing sustains a WiFi advertisement the way a
border router sustains a Thread one.
**Source:** 17-EVIDENCE/17-STALENESS-CONTROL.md, 17-04-SUMMARY.md

### The 60 second cadence was too coarse to measure the thing it was pointed at
`first_absence_poll: 1` means the device was absent before the first observation, so the
disappearance interval was never measured, only bounded.

**Impact:** The figure is a ceiling rather than a value, and every artefact had to state it that
way. A third round at 1 Hz using a targeted unicast probe is recorded as future work, superseding
the disappearance figure only and not the restoration figures, which are well resolved.
**Source:** 17-04-SUMMARY.md, 17-05-SUMMARY.md

### The mDNS leg restored before the broadcast leg
Restoration came in at 14.557 seconds on mDNS and 15.530 seconds on broadcast.

**Impact:** The opposite of the expectation that drove the restoration redesign, which anticipated a
WiFi bulb answering broadcast promptly while never re-advertising over mDNS inside the session. The
per-leg fields exist because of that expectation and were worth adding regardless, since they are
what made the ordering observable.
**Source:** 17-EVIDENCE/14-STALENESS.jsonl, 17-04-SUMMARY.md

### The probe reports below the layer that filters unsupported devices
Twenty-six instances advertise on `_lifx._udp.local`, of which three are Switch products the library
filters at device construction, so `discover_mdns()` would yield twenty-three.

**Impact:** Both numbers are true and answer different questions. The probe deliberately reports at
the mDNS record layer, because a device that advertises badly needs to appear in a fleet diagnostic
whether or not the library would instantiate it.
**Source:** 17-EVIDENCE/17-PROBE-TRANSCRIPT.md, 17-03-SUMMARY.md

### A fix guarded against a condition the fleet cannot reach, and broke a real contract doing it
The IPv4 pseudonym pool was widened to three documentation ranges to avoid exhausting at 254
addresses. The committed run emitted 17.

**Impact:** The widening broke the emitter/whitelist contract and was reverted. The ceiling was
never the defect; the mid-write failure mode was, and that is what the final fix addresses. One
run's literals are memoised per address, and a whole-fleet WiFi sweep would reach roughly 70.
**Source:** 17-SPEC.md amendment A9, 17-REVIEW.md iteration 2

### The security audit's most useful finding was about a mitigation that predated the phase
T-17-14's registered mitigation could never have worked, and the audit found it while checking
whether A8 had invalidated it.

**Impact:** A stale reference prompted the check, and the check found something better: the
mitigation had been wrong since it was written. Auditing a mitigation because something around it
changed is worth doing even when the change turns out not to be the problem.
**Source:** 17-SECURITY.md, note on T-17-14
