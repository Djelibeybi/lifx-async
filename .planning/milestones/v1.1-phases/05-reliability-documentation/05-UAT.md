---
status: complete
phase: 05-reliability-documentation
source: [05-VERIFICATION.md]
started: 2026-07-17T07:38:52Z
updated: 2026-07-17T13:58:30Z
---

## Current Test

[testing complete]

## Tests

### 1. Prohibition verdict review (8 judgment-tier verdicts from plan 05-05)

expected: |
  All 8 prohibitions in 05-05 are judgment-tier (category: values, no test-tier enforcement).
  In an autonomous run their verdicts are NON-AUTHORITATIVE LLM-judge outputs and cannot be
  silently absorbed into a passed verdict — this checkpoint exists to make them authoritative.

  The verifier recorded all 8 as `upheld`, and the orchestrator independently re-confirmed
  verdicts 1, 2, 3, 4, 5 and 8 against the git diff (84d91b2..HEAD) before this file was
  written. Verdicts 6 and 7 rest on prose judgement and are the ones most worth your eye.

  | # | Prohibition (abridged) | Verdict | Evidence |
  | --- | --- | --- | --- |
  | 1 | No version attribution of any kind (D5-12) | upheld | `Since v[0-9]` → 0 files across docs/, CLAUDE.md, src/ |
  | 2 | No source docstring edit beyond the three authorised sites (D5-18/D5-20) | upheld | src/ diff = exactly 3 files; api.py:758 override not re-exercised |
  | 3 | create_device docstring outside its Example untouched (D5-21) | upheld | No Returns:/Raises: line in diff; routed to API-01(d) |
  | 4 | No mkdocstrings-fed content or changelog edits (widened D5-14) | upheld | Only animation.md + network.md under docs/api; 0 `:::` lines in either diff |
  | 5 | No API-01 deferred-defect fixes or paper-overs (D5-19) | upheld | api.py diff = line 620 only; 260-331/515-557/974-1016 byte-identical |
  | 6 | No internal tuning constants in rewritten prose (D5-09) | upheld | Gate-threshold/expiry/gap-value patterns → 0; `(source, sequence, serial)` judged correlation identity, not a tuning constant |
  | 7 | No latest-frame-wins-as-defect framing / retry advice | upheld | "dropped, never queued (latest-frame-wins)"; "A dropped frame is never retried; … by design" |
  | 8 | No mkdocs.yml nav changes / new pages (D5-01) | upheld | mkdocs.yml diff empty; no created files |

  Pass when you concur with all 8. Report an issue naming the verdict number if any fence
  reads as breached.

result: pass
reported: "pass for UAT"
note: |
  Operator separately disputed the D5-09 prohibition ITSELF ("I don't think I agree with the
  prohibition") — not this verdict. Plan 05-05 complied with D5-09 as written and all 8 verdicts
  hold. The rule's future is tracked as an open decision in 05-CONTEXT.md (D5-09 — OPEN), with
  linked spike candidate 006. That dispute does not affect this pass.

### 2. Direct-connection guidance is accurate about discovery

expected: |
  No published page claims that connecting by IP alone skips discovery. The shipped behaviour
  (base.py:454-516) is that `from_ip(ip)` with `serial=None` opens a temp connection using the
  broadcast serial 000000000000, sends `Device.GetService()` to the IP, reads the serial off the
  `StateService` reply, closes the temp connection, and only then constructs the instance — a
  unicast discovery round-trip before the first real command. Only `from_ip(ip, serial=...)` /
  `Light(serial=..., ip=...)` skips it, going straight to `cls(serial=..., ip=...)`.

result: pass
reported: "http://localhost:8000/lifx-async/getting-started/quickstart/#direct-connection-no-discovery is technically not true. If you only know the IP address, then `lifx_async` does a unicast discovery to determine the serial number first, then it starts controlling the bulb. The only 100% genuinely honest way to connect to a bulb and control it immediately, i.e. in the same packet, is if you know both the serial and the IP address."
severity: major
found_during: test 1 review (operator-reported, outside plan 05-05's edited set)
resolution: |
  Closed by plan 05-06 (G-05-2, commit 64aff6e). quickstart.md now frames the IP-only path as a
  unicast discovery round-trip and documents the serial+IP form as the genuine zero-discovery path
  (docs/index.md:41 precedent); overview.md:253's bullet says the same. The verifier re-traced
  base.py:454-516 in full and confirmed the new text matches shipped behaviour. from_ip()'s
  docstring left untouched per this gap's fence_note.
  Marked pass on automated + verifier evidence, NOT an operator re-test — re-open at
  /gsd-verify-work if the wording does not read right to you.

### 3. Direct UDP Delivery lead-in describes what the stack does, not only what it bypasses

expected: |
  docs/api/animation.md's "Direct UDP Delivery" lead-in should name the animation module's
  purpose-built network stack rather than say it "bypasses the connection layer entirely" — the
  bypass framing states only a negative and sits directly above a bullet saying delivery is
  ack-paced, which reads as a contradiction even though both are true (flow.py acks are separate
  from DeviceConnection). Drop-framing wording reads "expected" rather than "by design".

result: pass
reported: "We could say something like \"The animation module uses its a purpose-built network stack that provides the following features:\" then replace \"by design\" with \"expected\""
severity: minor
found_during: test 1 review (operator-directed prose improvement, not a fence breach)
resolution: |
  Closed by plan 05-06 (G-05-3, commit 64aff6e) using your agreed_text verbatim: the lead-in now
  reads "purpose-built network stack with the following characteristics" and the drop framing reads
  "expected". Verifier confirmed "is by design" and "bypasses the connection layer" both drop to
  zero on the page, and bullets 1-2 are byte-preserved.
  Marked pass on automated + verifier evidence, NOT an operator re-test — re-open at
  /gsd-verify-work if the wording does not read right to you.

### 4. Rendered docstrings render their lists as lists

expected: |
  A "Features:"-style heading in a docstring that mkdocstrings publishes is followed by a blank
  line, so the bullet list under it renders as a list rather than a run-on paragraph.

result: pass
reported: "Under http://localhost:8000/lifx-async/api/network/#lifx.network.connection.DeviceConnection - there is a blank line missing under \"Features\" so the Markdown list is not being rendered correctly"
severity: minor
found_during: test 1 review (operator-reported; behind the D5-11 docstring fence)
resolution: |
  Closed by plan 05-06 (G-05-4, commit 95c60d6) under the D5-22 override. The reported
  DeviceConnection "Features" site is fixed, and the mandated audit swept every :::-reachable
  docstring rather than only that one: 23 run-on paragraphs across the built site are now 0
  (independently re-detected on site/api/ by both the verifier and the orchestrator). All fixes are
  whitespace-only — 0 deletion lines across the 10 pure-whitespace files.
  Marked pass on automated + verifier evidence, NOT an operator re-test — re-open at
  /gsd-verify-work if any page still renders wrong.

### 5. Published docstrings use reader vocabulary, not internal design vocabulary

expected: |
  No published API page explains behaviour by reference to another library's internals. A reader
  who has never heard of Photons can understand every published sentence.

result: pass
reported: "The whole sentence \"Wall-time request budget with escalating Photons-shaped retransmits that listen continuously between sends (no blind sleeps)\" needs less jargon / \"Photons-shaped retransmits\" means nothing to someone who has never heard of Photons"
severity: major
found_during: test 1 review (operator-reported; behind the D5-11 docstring fence)
resolution: |
  Closed by plan 05-06 (G-05-5 + G-05-6, commits 6d0280d and 95c60d6) under the D5-22 override. The
  reported sentence is gone; the retransmit bullet now reads "Automatic retransmits on an escalating
  schedule within each request's..." — matching overview.md:150's published wording. The mandated
  audit swept all 53 :::-reachable public docstrings for design-lineage vocabulary AND planning IDs:
  zero hits on either, re-run independently by the verifier. Every removed ID survives in the three
  additive "# Traceability" comments or a pre-existing unrendered surface (demotion map checked
  line-by-line) — traceability demoted, never deleted.
  Marked pass on automated + verifier evidence, NOT an operator re-test — re-open at
  /gsd-verify-work if any published sentence still reads as jargon.

### 6. Prohibition verdict review (9 judgment-tier verdicts from plan 05-06)

expected: |
  All 9 prohibitions in 05-06 are judgment-tier (category: values, no test-tier enforcement).
  In an autonomous run their verdicts are NON-AUTHORITATIVE LLM-judge outputs and cannot be
  silently absorbed into a passed verdict — this checkpoint exists to make them authoritative.
  Same shape as test 1, which covered plan 05-05's eight verdicts.

  The verifier recorded all 9 as `upheld`. The orchestrator independently re-confirmed the
  mechanical ones against the git diff (5cb7b57..HEAD) before this file was written: the api.py
  one-hunk scope (verdict 1), the untouched index.md/mkdocs.yml/changelog.md (verdicts 4, 5), and
  the zero-deletion whitespace files (verdict 8). Verdicts 2 and 9 rest on prose judgement and are
  the ones most worth your eye.

  | # | Prohibition (abridged) | Verdict | Evidence |
  | --- | --- | --- | --- |
  | 1 | D5-19/D5-21: deferred api.py defects + create_device Returns:/Raises: untouched | upheld | api.py diff = 1 blank line at :681 only; discovery.py diff has zero Returns:/Raises:/Example: lines |
  | 2 | D5-09 as written: no tuning constants; no dispute work (timings/override guidance/diagram) | upheld | Sweep patterns → 0 across 53 files; all new prose read in full — no timing figure, no diagram, no override guidance |
  | 3 | D5-12: no version attribution | upheld | `Since v[0-9]` → 0 files across docs/, CLAUDE.md, src/ |
  | 4 | Widened D5-14 / narrow D5-23: no existing ::: edits; changelog fenced; docs/api edits confined | upheld | animation.md diff zero ::: lines; high-level/network insertion-only; effects.md deletions only annotation lines; index.md and changelog.md diffs empty |
  | 5 | D5-01: no mkdocs.yml nav changes, no new pages | upheld | mkdocs.yml diff empty; zero created files |
  | 6 | Comments/unrendered docstrings untouched except 3 additive Traceability comments | upheld | const.py/flow.py absent from diff; connection.py:518 comment intact; discovery.py private sites keep lineage vocabulary |
  | 7 | base.py from_ip docstring untouched; only two blank-line insertions | upheld | base.py diff = hunks at :275/:746 only; from_ip absent from diff |
  | 8 | Whitespace-only sites: zero character changes | upheld | 0 deletion lines in all 10 pure-whitespace files |
  | 9 | No traceability deleted outright | upheld | Demotion map verified: all removed IDs present in connection.py:494-496, packets.py:157-159/:275-278, or pre-existing animator.py/discovery.py unrendered surfaces |

  Pass when you concur with all 9. Report an issue naming the verdict number if any fence
  reads as breached.

result: pass
reported: "pass"
note: |
  Operator concurred with all 9 verdicts (2026-07-17). This makes the judgment-tier verdicts
  authoritative — including verdict 2 (D5-09 discipline in the rewritten prose) and verdict 9
  (demotion completeness), the two resting on prose judgement.

  Unchanged by this pass: the operator's separate dispute of the D5-09 prohibition ITSELF (not its
  verdict) remains an open decision in 05-CONTEXT.md with linked spike candidate 006. Plan 05-06
  complied with D5-09 as written; the rule's future is tracked there, not here. Same posture as
  test 1's note for 05-05.

## Summary

total: 6
passed: 6  # test 1 (05-05 verdicts), tests 2-5 (gaps G-05-2..G-05-7 closed by plan 05-06), test 6 (05-06 verdicts)
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-05-2
  truth: "No published page claims that connecting by IP alone skips discovery; the honest zero-discovery path (serial + IP) is the one documented as such"
  status: resolved
  resolved_by: 05-06-PLAN.md
  resolved_at: 2026-07-17
  reason: |
    User reported: the quickstart's "Direct Connection (No Discovery)" section is technically untrue.
    Confirmed against source — from_ip(ip) with serial=None performs a unicast Device.GetService()
    round-trip to learn the serial before any control packet (base.py:454-516). Only the
    serial+IP form skips discovery.

    Two published surfaces carry the false claim:
      - docs/getting-started/quickstart.md:95 — heading "Direct Connection (No Discovery)" over a
        `Light.from_ip("192.168.1.100")` example (no serial). Dates to the initial commit (5d62622);
        never touched by the rewrite that corrected the equivalent claim on docs/index.md:41 in
        11b3cb2 ("Connect most efficiently without discovery using serial and IP" — accurate).
      - docs/architecture/overview.md:253 — "**Direct Connection**: Connect by IP without discovery".
        Page was edited by 05-05 for retry wording/CeilingLight/AU spelling; line 253 was out of scope.

    NOT defects (no "no discovery" claim; unicast GetService genuinely solves broadcast-blocked
    routers): docs/getting-started/installation.md:115, docs/faq.md:54.

    Root cause: the D5-10 stale-content audit scoped user-guide/, architecture/ and api/ but never
    getting-started/, so quickstart.md was never audited by this phase.
  severity: major
  test: 2
  artifacts:
    - "docs/getting-started/quickstart.md"
    - "docs/architecture/overview.md"
  missing:
    - "Version-neutral, accurate framing of the IP-only path as a unicast discovery round-trip"
    - "The serial+IP form documented as the genuine zero-discovery path (per docs/index.md:41 precedent)"
  fence_note: |
    quickstart.md and overview.md are hand-written prose outside the docs/api mkdocstrings fence —
    editable without a new override. The from_ip() docstring (base.py:454) is NOT a falsehood (it
    never claims "no discovery") but omits the GetService round-trip; it remains fenced by D5-11 and
    would need a new override decision to touch. Recommend doc-page fix only.

- gap_id: G-05-3
  truth: "docs/api/animation.md's Direct UDP Delivery lead-in names the animation module's purpose-built network stack rather than framing it only as a bypass, and drop-framing reads 'expected' rather than 'by design'"
  status: resolved
  resolved_by: 05-06-PLAN.md
  resolved_at: 2026-07-17
  reason: |
    Operator-directed prose improvement raised during test 1 review. The lead-in at
    docs/api/animation.md:129 reads "The animation module bypasses the connection layer entirely:"
    — pre-existing text that plan 05-05 did not touch. It states only a negative and now sits
    directly above the rewritten bullet "Delivery is paced against device acknowledgements
    internally", which reads as a contradiction to a first-time reader. Both statements are true
    (animation-layer acks live in flow.py and are independent of DeviceConnection), so this is a
    clarity defect, not a factual one.

    NOT a prohibition breach: verdict 7 holds under either wording. "expected" and "by design" are
    both intent-framing; neither frames latest-frame-wins as a defect nor advises retrying a
    dropped frame.
  severity: minor
  test: 3
  artifacts:
    - "docs/api/animation.md"
  missing:
    - "Lead-in naming the purpose-built network stack (operator wording, typo corrected and 'features' -> 'characteristics' per operator ruling)"
    - "'by design' -> 'expected' in the frame-loss bullet"
  agreed_text: |
    The animation module uses a purpose-built network stack with the following characteristics:

    - Frame packets are sent via a raw UDP socket; `send_frame()` never blocks
    - Delivery is paced against device acknowledgements internally — when a device falls behind, new frames are dropped, never queued (latest-frame-wins)
    - A dropped frame is never retried; occasional frame loss under saturation is expected (visual artefacts are brief)
  fence_note: |
    docs/api/animation.md hand-written prose (the "Performance Characteristics" section) is editable
    under the D5-18-widened hand-written-prose fence — no ::: block involved, no new override needed.
    Introduces no tuning constants (D5-09 holds) and no version attribution (D5-12 holds).
  resolved_nit: "'features' vs 'characteristics' — operator ruled 'characteristics' (2026-07-17), matching the parent 'Performance Characteristics' heading and avoiding calling a non-retried frame a feature."

- gap_id: G-05-4
  truth: "Every docstring heading that mkdocstrings publishes is followed by a blank line, so its bullet list renders as a list"
  status: resolved
  resolved_by: 05-06-PLAN.md
  resolved_at: 2026-07-17
  reason: |
    Operator observed the DeviceConnection "Features:" list rendering as a run-on paragraph on
    /api/network/. Confirmed in built HTML (site/api/network/index.html): no <ul> follows
    "Features:" — the bullets render as literal text inside one <p>.

    Cause: "Features:" is not a Google-style section (Args/Returns/Raises/Example are), so griffe
    passes it through as raw markdown, and markdown requires a blank line before a list.
    connection.py:59-60 has none.

    Systemic, not isolated: 14 sites in src/ have a "Heading:" line with a bullet directly beneath.
    Rendered (owned by a ::: target, so publicly broken):
      - src/lifx/network/connection.py:59  (DeviceConnection)      <- operator-reported
      - src/lifx/protocol/base.py:74       (Packet)
      - src/lifx/animation/orientation.py:39 (Orientation)
      - src/lifx/devices/matrix.py:333     (MatrixLight)
      - src/lifx/devices/base.py:277       (Device)
      - src/lifx/devices/base.py:748       (Device.capabilities)
      - src/lifx/devices/light.py:106      (Light.get_color)
      - src/lifx/api.py:680                (DeviceGroup.apply_theme)
    Not rendered (private / unexported / comments): discovery.py:177, products/quirks.py:23,
    protocol/generator.py:148/171/192/268.
  severity: minor
  test: 4
  artifacts:
    - "src/lifx/network/connection.py"
  missing:
    - "Blank line between the heading and its list at each rendered site (whitespace-only; no prose change)"
  fence_note: |
    AUTHORISED under D5-22 (operator ruling, 2026-07-17 UAT): rendered docstrings are in scope for
    prose and whitespace. Was blocked by D5-11 — connection.py:59 is the "Features:" heading, not
    the :64 bullet the D5-18 override covered, so even the operator-reported instance was fenced.
    All eight rendered sites now in scope. Whitespace-only; zero prose or behavioural-claim change.

- gap_id: G-05-5
  truth: "No published API page explains behaviour by reference to another library's internals; a reader who has never heard of Photons understands every published sentence"
  status: resolved
  resolved_by: 05-06-PLAN.md
  resolved_at: 2026-07-17
  reason: |
    Operator reported that "Wall-time request budget with escalating Photons-shaped retransmits
    that listen continuously between sends (no blind sleeps)" (connection.py:62-63) is jargon, and
    that "Photons-shaped" is meaningless to a reader who does not know delfick's Photons library.
    Confirmed: it is an internal design-lineage reference leaked onto a published page.

    Not isolated. "Photons-shaped" reaches three published surfaces:
      - src/lifx/network/connection.py:62      (DeviceConnection class docstring)  <- reported
      - src/lifx/network/connection.py:443/515 (DeviceConnection.request — renders as a member)
      - src/lifx/network/discovery.py:490      (discover_devices — ::: target on api/network.md)
    Same class of leak, same docstrings: "wall-time budget" (connection.py:109-113, 457, 479-480)
    and "no blind sleeps" (connection.py:63).
    Unrendered, therefore out of scope: discovery.py:171 (private _discover_with_packet),
    const.py:36/48/51 (comments), animation/flow.py:8 (module docstring, no ::: target).

    This bullet is PRE-EXISTING — plan 05-05 edited only the line below it (:64, response
    correlation). The jargon predates this phase.
  severity: major
  test: 5
  artifacts:
    - "src/lifx/network/connection.py"
    - "src/lifx/network/discovery.py"
  missing:
    - "Plain-language retransmit description on every rendered surface, matching the already-published wording at docs/architecture/overview.md:150"
  proposed_text: |
    Replaces connection.py:62-63:

    - Automatic retransmits on an escalating schedule within each request's
      timeout, listening for a reply throughout

    Rationale: matches the phrasing already published at docs/architecture/overview.md:150, so the
    docstring and the architecture page state the same contract in the same words. Names no tuning
    constant (D5-09 holds), no version (D5-12 holds).
  fence_note: |
    AUTHORISED under D5-22 (operator ruling, 2026-07-17 UAT). Was blocked by D5-11: connection.py:62-63
    is not the :64 bullet D5-18 covered, and discovery.py:490 is not the create_device Example D5-20
    covered. D5-09 still binds the rewrite (no tuning constants) and D5-12 still binds (no versions).

- gap_id: G-05-6
  truth: "No published API page references internal planning artifacts — requirement IDs, decision IDs, spike numbers or plan numbers that exist only in .planning/"
  status: resolved
  resolved_by: 05-06-PLAN.md
  resolved_at: 2026-07-17
  reason: |
    Found while scoping G-05-5 (same defect class: published docstrings speaking internal
    vocabulary). Rendered docstrings cite GSD planning IDs a reader cannot resolve:
      - src/lifx/network/connection.py:450-469 (DeviceConnection.request — renders on api/network.md):
        "Schedule (RETRY-01, D3-01)", "Wall budget (RETRY-03, D3-03)", "(RETRY-02, D3-02)",
        "``max_retries`` interaction rule (D3-05)", "Correlation contract (RETRY-04, D3-04)"
      - src/lifx/animation/animator.py:69, 77, 91, 98, 359 (Animator — renders on api/animation.md):
        "(ANIM-01)", "(D4-02)", "(ANIM-01/ANIM-02, D4-03)", "(D4-04)"
      - src/lifx/animation/packets.py:162-167, 273-280 (PacketGenerator/MatrixPacketGenerator —
        render on api/animation.md): "(D4-03)", "spike 003 measured at 0.0%", "(D4-01)", "(D4-02)",
        "D4-04 decision (recorded here for the phase record)", "ANIM-04 UAT (plan 04-07)"

    packets.py:273 is the clearest case: a planning decision deliberately parked "for the phase
    record" inside a docstring that mkdocstrings publishes.

    OUT OF SCOPE (do not render — # comments and untargeted modules): discovery.py:250,
    connection.py:507/548/601/657, animation/flow.py (whole module, no ::: target).
    Internal IDs in comments are legitimate and should stay.
  severity: major
  test: 5
  artifacts:
    - "src/lifx/network/connection.py"
    - "src/lifx/animation/animator.py"
    - "src/lifx/animation/packets.py"
  missing:
    - "Behavioural contract stated in reader vocabulary on every rendered docstring; internal IDs demoted to # comments where the traceability is still wanted"
  fence_note: |
    AUTHORISED under D5-22 (operator ruling, 2026-07-17 UAT). Largest of the three: a multi-file
    docstring prose rewrite across connection.py, animator.py and packets.py. D5-09 still constrains
    it — packets.py:164 currently cites a measured spike figure ("0.0% concurrent-query loss") which
    is a tuning constant, not a contract, and must not survive the rewrite. Prefer demoting internal
    IDs to `#` comments over deleting the traceability outright.
  audit_required: |
    Operator chose full closure in Phase 5 over a separately-planned phase, accepting the stated risk
    that the leak list is incomplete. Per D5-22 the gap-closure plan MUST carry an audit task over
    every :::-reachable docstring (internal vocabulary, missing blank lines, D5-09 constants). The
    known sites came from pulling one thread; they are not known to be exhaustive. Anything the audit
    surfaces is in scope for the same plan.
  relates_to: "G-05-5 — same class (published docstrings using internal vocabulary); differs in blast radius and files touched"

- gap_id: G-05-7
  truth: "uv run zensical build --strict exits 0 — no unresolved links or missing anchors on any published page, and CI gates on it"
  status: resolved
  resolved_by: 05-06-PLAN.md
  resolved_at: 2026-07-17
  reason: |
    Operator: "There are 8 warnings in strict mode when running Zensical, btw. We should look into
    those too."

    These are the SAME 8 that every plan in this phase pins as "the pre-existing baseline"
    (5x api/effects.md, 3x api/index.md). They were never a background constant — D5-14 deferred
    them explicitly: "every other docs/api page stays fenced even where it carries known defects
    (surfaced as findings, not fixed)". Pinning a broken-link count as a success criterion is what
    made them permanent.

    They decompose into two unrelated defects:

    (a) api/effects.md:60, 82, 101, 115, 194 — "unresolved link reference". A markdown bug, not a
        content error: the lines read `participants` (list[Light]) with the type annotation OUTSIDE
        the backticks, so markdown parses [Light] as a shortcut link reference and cannot resolve
        it. Backticking the annotation closes all five.

    (b) api/index.md:58, 95, 96 — "anchor does not exist". Not a link typo: there are NO ::: render
        targets for any mDNS symbol anywhere in docs/api/. The index links to reference docs that
        were never created:
          58 -> high-level.md#lifx.api.discover_mdns
          95 -> network.md#lifx.network.mdns.discover_lifx_services
          96 -> network.md#lifx.network.mdns.LifxServiceRecord
        All three are PUBLIC API — exported from lifx/__init__.py __all__ (:143, :151, :152) and
        from lifx.network.mdns.__all__. CLAUDE.md documents the whole mdns/ module as a shipped
        feature. The dead links are the symptom; the missing API reference is the defect.

    Enforcement gap: `zensical build --strict` ("abort the build on warnings") exists, but CI runs
    plain `uv run zensical build --clean` (.github/workflows/docs.yml:56, :114). Nothing has ever
    failed on these. Fixing the 8 and switching CI to --strict makes the class unrepeatable.
  severity: major
  test: 6
  artifacts:
    - "docs/api/effects.md"
    - "docs/api/index.md"
    - ".github/workflows/docs.yml"
  missing:
    - "(a) backticked type annotations in api/effects.md (5 sites)"
    - "(b) an operator ruling on mDNS: render the missing ::: targets, or remove the dead links"
    - "CI gating on `zensical build --strict` so the class cannot regress"
  fence_note: |
    AUTHORISED under D5-23 (operator ruling, 2026-07-17 UAT: "Amend it"). D5-14 lifted for exactly
    api/effects.md and api/index.md, for exactly these defects. Was blocked because D5-14 covers every
    docs/api page except animation.md/network.md and explicitly chose to surface these rather than fix
    them; D5-22 did not help (it lifted D5-11 for rendered DOCSTRINGS, not D5-14 for docs/api PAGES).

    mDNS ruling: RENDER the missing targets, do not delete the links. All three symbols are public
    (lifx/__init__.py __all__ :143/:151/:152). D5-01 is NOT touched — both destination pages already
    exist and the links already name them:
      - `::: lifx.api.discover_mdns` -> docs/api/high-level.md, beside `::: lifx.api.discover` (:8)
      - `::: lifx.network.mdns.discover_lifx_services` -> docs/api/network.md, beside
        `::: lifx.network.discovery.discover_devices` (:9)
      - `::: lifx.network.mdns.LifxServiceRecord` -> docs/api/network.md, same group
    No new page, no mkdocs.yml nav change. Match surrounding blocks' `options:` exactly.
    index.md needs NO edit — its links are correct; their destinations never existed.

    The newly-rendered mDNS docstrings have never been published and so have never been audited —
    they are in scope for the D5-22 audit task before going live.
  blocks: |
    Plan 05-06 (created 2026-07-17, pre-dates D5-23) pins "exits 0 at the 8-issue baseline" as a
    must_have and CANNOT execute as written alongside this gap. Amendment required:
      - must_have inverts: "8-issue baseline" -> "`uv run zensical build --strict` exits 0"
      - .github/workflows/docs.yml:56 and :114 gain --strict (else the counter just drifts again)
      - files_modified gains docs/api/effects.md, docs/api/high-level.md, .github/workflows/docs.yml
      - gap_ids gains G-05-7
