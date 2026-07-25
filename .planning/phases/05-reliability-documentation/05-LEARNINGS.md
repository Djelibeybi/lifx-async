---
phase: 05
phase_name: "reliability-documentation"
project: "lifx-async — Wire Reliability"
generated: "2026-07-18T16:53:22+10:00"
counts:
  decisions: 8
  lessons: 8
  patterns: 7
  surprises: 7
missing_artifacts: []
---

# Phase 05 Learnings: reliability-documentation

## Decisions

### Treat the Gen4 Wake Tail as Latency, Not Packet Loss
The published guidance describes the first-command wake tail as a bounded, sub-250 ms latency effect on gen4 devices over healthy networks. The library deliberately does not ship a keepalive daemon; optional read-only polling remains an application choice.

**Rationale:** Hardware evidence showed zero idle-related packet loss, so a library-owned keepalive would spend traffic to hide a latency quirk rather than solve a reliability problem.
**Source:** 05-01-SUMMARY.md

---

### Publish the Streaming Contract Without Tuning Constants
Streaming documentation exposes ack-paced delivery, latest-frame-wins dropping, and the absence of consumer-facing flow-control configuration, while keeping gate thresholds, acknowledgement expiry, and probe placement out of public prose.

**Rationale:** Consumers need the stable behavioural contract and should not couple themselves to internal tuning values that may change without an API change.
**Source:** 05-02-SUMMARY.md

---

### Retain Legitimate Whole-Operation Retry Guidance
Application retry wrappers were contextualised rather than deleted: the library owns retransmission inside each request timeout, while applications may still retry an entire failed operation.

**Rationale:** Removing the examples would discard valid recovery guidance; the necessary correction was to distinguish whole-operation recovery from per-packet reliability.
**Source:** 05-03-SUMMARY.md

---

### Keep Reliability Claims Version-Neutral
The documentation does not attribute wire behaviour to a package version. Both former "Since v1.1" claims were replaced with direct statements of current behaviour.

**Rationale:** The published package version is derived during release from conventional commits, so predicting or hard-coding a version would recreate a false claim.
**Source:** 05-04-PLAN.md

---

### Use Narrow Overrides for Published Accuracy Defects
Source docstrings and hand-written API-reference prose were edited only through explicitly authorised, line- and defect-scoped overrides. Deferred behavioural defects and unrelated `docs/api` content remained fenced.

**Rationale:** Published falsehoods had to be corrected without turning a documentation phase into an uncontrolled source or API-behaviour change.
**Source:** 05-05-SUMMARY.md

---

### Fix Direct-Connection Claims on Documentation Pages Only
The quickstart and architecture pages now distinguish the IP-only unicast discovery round-trip from the genuine serial-plus-IP zero-discovery path. The `from_ip()` docstring was left untouched because it never made the false no-discovery claim.

**Rationale:** The defect existed in page-level framing, not in the fenced docstring, so the smallest truthful fix was confined to the two pages carrying the false claim.
**Source:** 05-06-SUMMARY.md

---

### Demote Internal IDs Instead of Deleting Traceability
Planning IDs, spike references, and design-lineage vocabulary were removed from rendered docstrings and retained in `# Traceability` comments or existing unrendered surfaces.

**Rationale:** Public readers should not need internal GSD or reference-client vocabulary, but the implementation history remains valuable to maintainers.
**Source:** 05-06-SUMMARY.md

---

### Eliminate the Warning Baseline and Enforce Strict Builds
The missing mDNS API targets were rendered instead of deleting correct index links, the five malformed effects annotations were fixed, and both documentation CI builds now run Zensical with `--strict`.

**Rationale:** The eight warnings were actual defects, not an acceptable baseline; enforcing zero warnings prevents the same class from being silently re-pinned.
**Source:** 05-06-SUMMARY.md

---

## Lessons

### Validate Examples Against the Current Default
An example intended to demonstrate a longer discovery timeout used `10.0`, which is below the actual `15.0` second default. It had to be raised to `30.0` in both the troubleshooting guide and FAQ.

**Context:** The example retained an old value after the documented default changed, making otherwise plausible advice logically backwards.
**Source:** 05-01-SUMMARY.md

---

### Shipped Source Is the Final Authority for Documentation
Several copy-paste examples used removed methods, a nonexistent colour preset, the wrong HSBK type domain, invalid capability membership checks, or incorrect async-generator consumption. Re-checking each example against live source corrected the residual set.

**Context:** Earlier prose and reviews were useful evidence, but only the current API and generated protocol types could establish whether examples actually run.
**Source:** 05-04-SUMMARY.md

---

### A Literal Acceptance Check Can Validate the Wrong Proxy
The plan checked that an `except LifxTimeoutError` count was unchanged, but the real wrapper had always caught `LifxError`; the literal count was zero before and after. The intended invariant required a direct inspection of the actual exception blocks.

**Context:** A mechanically passing grep did not prove that the legitimate whole-operation wrapper survived.
**Source:** 05-04-SUMMARY.md

---

### Documentation UAT Finds Defects Automated Verification Misses
Operator review found six accuracy, readability, and publication gaps after the prior verification had closed all of its automated truths.

**Context:** The gaps included technically false connection wording, confusing API prose, broken rendered lists, internal jargon, leaked planning IDs, and strict-build warnings.
**Source:** 05-UAT.md

---

### Rendered Docstring Formatting Must Be Audited Systemically
A missing blank line under `Features:` was not an isolated markdown blemish. The expanded audit found 23 run-on paragraphs across the built API site and reduced the count to zero.

**Context:** Griffe passes non-Google-style headings through as Markdown, so source that looks readable can render incorrectly without a blank line before a list.
**Source:** 05-UAT.md

---

### Internal Design Vocabulary Spreads Across Public Surfaces
The reported phrase "Photons-shaped retransmits" led to a broader audit that found reference-client lineage, wall-time jargon, planning IDs, and spike figures across multiple rendered docstrings.

**Context:** Pulling one terminology thread revealed a defect class, not a single bad sentence, so the repair had to cover every published docstring target.
**Source:** 05-UAT.md

---

### A Stable Warning Count Can Hide Permanent Defects
The eight Zensical warnings repeatedly treated as a baseline were five malformed Markdown link references and three anchors whose public mDNS symbols were never rendered.

**Context:** Pinning the count as success normalised the defects and prevented ordinary builds from forcing closure.
**Source:** 05-UAT.md

---

### IP-Only Connection Still Performs Discovery
`from_ip(ip)` without a serial opens a temporary broadcast-serial connection and performs a unicast `GetService` round-trip to learn the serial before constructing the device. Only supplying both serial and IP skips discovery.

**Context:** The quickstart heading and architecture bullet incorrectly equated a targeted unicast lookup with no discovery.
**Source:** 05-UAT.md

---

## Patterns

### Claim-to-Source Traceability
Record every published number and behavioural statement against a concrete source row, constant, shipped implementation, hardware verdict, or previous phase artifact.

**When to use:** Use for documentation that publishes timing, throughput, defaults, device-class limits, or protocol behaviour.
**Source:** 05-01-SUMMARY.md

---

### Exact Replacement With Idempotency Gates
Use exact-string replacements and exact-count positive and negative checks so a completed documentation edit cannot compound silently when re-run.

**When to use:** Use for gap-closure plans that may be resumed or executed again against an already-partially-fixed tree.
**Source:** 05-04-SUMMARY.md

---

### Diff-Shape Scope Fences
Verify narrow overrides with path lists, insertion/deletion counts, forbidden-line greps, and byte-identical checks for adjacent fenced sections.

**When to use:** Use when a documentation task is authorised to touch selected source docstrings or selected hand-written regions inside generated-reference pages.
**Source:** 05-05-SUMMARY.md

---

### Target-Derived Public-Docstring Sweeps
Derive the audit surface live from the `:::` targets in `docs/api/*.md`, resolve re-exports with import machinery, and scan the resulting public docstrings for vocabulary, formatting, and tuning-constant defects.

**When to use:** Use when publication targets can change and a hard-coded file allowlist would become stale.
**Source:** 05-06-SUMMARY.md

---

### Verify the Rendered Site as Well as the Source
Combine AST/source checks with strict documentation builds and built-HTML detectors for run-on paragraphs and missing symbols.

**When to use:** Use for mkdocstrings or Markdown issues whose failure mode appears only after rendering.
**Source:** 05-VERIFICATION.md

---

### Atomic Task Commits With Green Boundaries
Execute related documentation fixes sequentially, commit each task atomically, and leave every commit boundary buildable before starting the next slice.

**When to use:** Use for multi-file accuracy passes where interruption or resumption must not leave a mixed publication state.
**Source:** 05-04-SUMMARY.md

---

### Pin Cross-Page Anchors and Validate Their Consumers
Choose anchor headings deliberately, document their exact generated fragment, and make the documentation build validate every inbound link.

**When to use:** Use when several plans or pages depend on an anchor created earlier in the phase.
**Source:** 05-01-SUMMARY.md

---

## Surprises

### The Planned Timeout Increase Was Actually a Decrease
The plan prescribed `timeout=10.0` as an increased discovery timeout even though the shipped default was already `15.0` seconds.

**Impact:** Both edited examples would have taught the opposite of the intended recovery action until execution corrected them to `30.0`.
**Source:** 05-01-SUMMARY.md

---

### Six UAT Gaps Appeared After a Fully Green Automated Cycle
The previous verification had closed all 37 of its truths, yet operator UAT still identified six material gaps requiring a sixth execution plan.

**Impact:** Phase closure expanded from a straightforward verification pass into a systemic rendered-docstring audit, accuracy rewrite, and CI hardening cycle.
**Source:** 05-VERIFICATION.md

---

### One Rendering Report Expanded to 23 Broken Paragraphs
The operator reported one missing blank line in the `DeviceConnection` feature list; the full audit found 23 run-on paragraphs across 10 built API pages.

**Impact:** The fix grew from a single whitespace edit into a repository-wide, rendered-surface blank-line sweep.
**Source:** 05-06-SUMMARY.md

---

### The Eight Warnings Were Two Unrelated Defect Classes
The warning baseline combined five Markdown annotations parsed as links with three missing mDNS render targets.

**Impact:** Closing the baseline required both local syntax fixes and API-reference wiring, followed by strict CI enforcement.
**Source:** 05-UAT.md

---

### The mDNS Index Links Were Already Correct
The three failing mDNS anchors were not misspelled links; the linked public symbols had never been rendered on their destination pages.

**Impact:** Deleting or rewriting the links would have hidden missing API documentation, so the correct repair was to publish the targets.
**Source:** 05-UAT.md

---

### Required Prose Failed the Source Formatter
The literal single-line `DeviceConnection` correlation bullet was 116 characters and failed Ruff's 88-character `E501` gate.

**Impact:** The sentence had to wrap across two docstring lines while preserving the required verification substring and meaning.
**Source:** 05-05-SUMMARY.md

---

### Automated Success Still Required a Human Judgment Checkpoint
All automated checks passed, but nine values-tier prohibition verdicts remained explicitly non-authoritative until the operator reviewed and accepted them.

**Impact:** The phase could not treat mechanical verification as sufficient for prose boundaries, deferral fences, and traceability-preservation judgments.
**Source:** 05-UAT.md
