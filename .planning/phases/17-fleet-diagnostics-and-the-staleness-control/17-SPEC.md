# Phase 17 Specification: Fleet Diagnostics and the Staleness Control

**Created:** 2026-09-08
**Ambiguity score:** 0.117 (gate: ≤ 0.20)
**Requirements:** 8 locked

## Goal

The IPv6 Thread probe reports which of two distinct address states it actually observed
instead of one message covering both, drops the two output paths the library makes
unreachable, and survives a partially assembled instance; and v2.0's two Thread staleness
figures (4140 to 4200 s disappearance-to-expiry, 69.4 s restoration) each gain a WiFi
control measured with the identical protocol.

## Background

**MDNS-10.** `.planning/scripts/ipv6_thread_probe.py` relocated out of the measured tree in
Phase 15 and now sits at `.planning/scripts/`, with its tests at
`.planning/scripts/tests/test_ipv6_thread_probe.py` behind the `--tooling` opt-in flag.
`report_records()` carries three defects, all confirmed against the current source:

1. Line 481 prints `"none - pending address records for SRV target"` whenever `chosen` is
   `None` and an SRV target exists. That covers two states a diagnostic tool exists to tell
   apart: a target for which the cache holds no A or AAAA record at all, and a target whose
   cached AAAA records exist but were refused. `selected_address_for()`
   (`src/lifx/network/discovery/mdns/discovery.py:376`) refuses through `_owner_is_unusable()`
   or through `_pick_address()` dropping every unusable candidate, and the probe cannot
   currently say which happened.
2. `linklocal_chosen` (declared line 428, incremented line 494, reported line 508) and the
   `is_reachable_choice()` warning (line 505) are unreachable. `_pick_address()`
   (discovery.py:215) filters through `_is_usable_mdns_address()`, which rejects an
   unscoped link-local address (discovery.py:210), and DNS AAAA wire data carries no zone
   ID. The only other source of `chosen`, the packet-source fallback, is intercepted by the
   earlier `chosen == view["fallback"]` branch. The counter therefore reports 0 on every run
   and the warning never prints.
3. Three bare asserts sit inside the per-instance reporting loop: `assert isinstance(txt,
   TxtData)` (436), `assert isinstance(aaaa_ips, list)` (437) and `assert isinstance(chosen,
   str)` (485). `_instance_view()` iterates `cache.owners_for(DNS_TYPE_TXT)`, so an owner
   with a TXT record whose payload did not parse into a `TxtData` yields `txt = None` and
   raises `AssertionError`, ending the whole diagnostic run at the first partially assembled
   instance.

**DISC-04.** Phase 14's THREAD-04 ran one staleness trial on 2026-09-04 through
`.planning/scripts/thread_revalidation.py staleness`, recorded in
`.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-STALENESS.jsonl`.
The UDP leg lost the device at poll 1 (t+60 s). The mDNS leg held it to poll 70 (t+4200 s),
confirmed at poll 72, placing true disappearance between t+4140 s and t+4200 s. Restoration
took 69.4 s from the power-on edge to both legs reporting present. No WiFi control exists.

The ROADMAP and REQUIREMENTS entries for this phase both describe "v2.0's 69s Thread
disappearance-to-expiry figure". That conflates two different measurements: 69.4 s was the
restoration duration, and disappearance-to-expiry was 4140 to 4200 s. SEED-002 asks for a
control on both. This specification treats the correction as a deliverable.

`_cli_staleness` (thread_revalidation.py:3409) applies no roster gate, but `_cli_init`
(thread_revalidation.py:2890) calls `validate_expected_roster()`, which refuses to write a
session manifest unless the roster names `Light`, `MultiZoneLight`, two distinct
`MatrixLight` aliases and `CeilingLight`. The production WiFi fleet holds devices in every
one of those classes, so a WiFi roster satisfies the gate without any tooling change.

## Requirements

1. **Refused-versus-absent address diagnosis**: The probe reports which of the two
   non-resolving address states it observed.
   - Current: line 481 prints `"none - pending address records for SRV target"` for both a
     target with no cached A or AAAA record and a target whose cached records were refused
     by `selected_address_for()`
   - Target: two distinct messages, one naming an SRV target for which no address record has
     been cached, one naming an SRV target whose cached address records exist but yielded no
     usable selection, with the refused message reporting the record count it saw
   - Acceptance: a tooling test drives a cache holding no address records for the target and
     asserts the absent message; a second drives a cache holding one or more unscoped
     link-local AAAA records for the target and asserts the refused message; neither test
     passes against the pre-change source

2. **Unreachable link-local counter and warning removed**: The probe stops reporting a
   quantity that cannot be non-zero.
   - Current: `linklocal_chosen` is declared, incremented in a branch `_pick_address()`
     makes unreachable, and printed as `chose a bare link-local addr` on every run; the
     `is_reachable_choice()` warning at line 505 is unreachable for the same reason
   - Target: the counter, its increment, its summary line and the warning are deleted;
     `is_reachable_choice()` is deleted with them if nothing else calls it
   - Acceptance: `grep -n 'linklocal_chosen\|is_reachable_choice' .planning/scripts/ipv6_thread_probe.py`
     returns nothing, and the existing tooling tests for the remaining `WHY` branches
     (IPv4 preferred, fallback source, routable preferred over link-local) still pass

3. **Defensive per-instance reporting**: A malformed instance is described, not fatal.
   - Current: three bare asserts (436, 437, 485) raise `AssertionError` and end the run at
     the first instance with an unparsed TXT payload, a non-list AAAA value or a non-string
     chosen address
   - Target (amended, see below): the two conditions that a malformed wire payload can still
     produce are handled at run time, and the third is eliminated by construction rather than
     re-armed. An instance whose TXT owner yields no parseable `TxtData` prints a diagnostic
     line naming the malformed field, and the loop continues to the remaining instances, each
     malformed field named once and the instance's remaining well-formed fields still printing.
     An instance with no usable chosen address renders through the non-resolving states of R1's
     five-state model rather than terminating the run. The non-list AAAA condition ceases to
     exist: `_InstanceView.aaaa` is `tuple[str, ...]` built inside `_instance_view()` from the
     cache's own values, so no runtime value can be non-list, and the phase records that
     elimination instead of adding a branch that cannot be taken
   - Acceptance: a tooling test builds three instances where the middle one has a TXT owner
     with no parseable `TxtData`, runs `report_records()`, and asserts that the run
     completes, that the malformed instance is named as malformed, and that the third
     instance's output is present and unchanged; the test fails against the pre-change
     source with `AssertionError`

4. **Probe change evidenced on real hardware**: The changed output is shown as an operator
   sees it, not only as a fixture.
   - Current: no committed transcript of a probe run exists in this repository
   - Target: one run of the changed probe against the real Thread fleet, pseudonymised by the
     probe's own opt-in `--alias-map` redaction (amended, see below), committed under the phase
     evidence directory
   - Acceptance: the transcript exists, every identifier in it is a pseudonym, and the
     accompanying finding states explicitly which of the new messages the hardware did and
     did not produce on the day rather than implying all were observed

5. **WiFi staleness control measured**: The Thread figures gain a same-protocol baseline.
   - Current: one Thread trial exists, with no WiFi comparison; SEED-002 is fired but
     unexecuted
   - Target: one trial against one WiFi bulb through
     `.planning/scripts/thread_revalidation.py staleness`, using the frozen 60 s absolute
     cadence, the three consecutive both-legs-absent confirmation rule and the three hour
     `STALENESS_CAP_S` cap unchanged, producing a disappearance-to-expiry result and a
     `restoration_duration_s` value, with the session manifest and staleness JSONL committed
     to a `17-EVIDENCE/` directory in the phase directory
   - Acceptance: `17-EVIDENCE/` holds a manifest and a staleness JSONL with exactly one
     WiFi alias row carrying a `disposition`, a `first_absence_poll`, a
     `confirmed_expiry_poll` where the disposition is `confirmed_expiry`, every intervening
     poll, and a `restoration_duration_s`; a `censored` disposition satisfies this
     requirement and is recorded as the observed result

6. **Recorded verdict with corrected figures**: The phase answers the question the control
   exists to answer, and fixes the conflated number.
   - Current: the 4140 to 4200 s figure stands alone with no control; ROADMAP and
     REQUIREMENTS both call 69 s the disappearance-to-expiry figure
   - Target: a committed finding placing both WiFi figures beside both Thread figures,
     stating whether the Thread lingering is Thread-specific or a general mDNS TTL and
     goodbye artefact, bounding that statement by what one paired trial supports, naming in
     advance the observation that would have supported the other answer, and correcting the
     ROADMAP and REQUIREMENTS wording so 69.4 s is identified as restoration duration and
     4140 to 4200 s as disappearance-to-expiry
   - Acceptance: the finding names all four figures with their measurement resolutions,
     never presents the 60 s-quantised WiFi bound as a point value comparable with the
     Thread interval, and the ROADMAP and REQUIREMENTS entries for DISC-04 no longer
     describe 69 s as a disappearance-to-expiry figure

7. **Caller-facing discovery liveness documentation**: The measured consumer hazard is
   published where a caller will find it. (amended, see below)
   - Current: SEED-002 records both hazards as undocumented. The qualitative distinction is
     in fact already documented, in wording Phase 16 locked: `docs/user-guide/discovery.md`
     and `discover_mdns()`'s own docstring both say an mDNS result proves an advertisement
     exists, not that the advertised device is currently reachable, and that `discover()`'s
     mDNS candidates must answer a correlated device request before they are yielded. What
     is undocumented is how long a stale advertisement outlives its device, and that a
     device can stay undiscoverable for tens of seconds after power returns
   - Target: caller-facing prose putting the measured durations on the claim the page
     already makes. It states that `discover_mdns()` can yield a device built from an
     advertisement whose device has already gone, for as long as that advertisement
     lingers; that `discover()` and `find_by_serial()` instead verify an mDNS candidate
     with a correlated request before yielding it, which is a point-in-time observation and
     not a continuing reachability guarantee; and that a device can remain undiscoverable
     for tens of seconds after power returns, by any method. Both directions carry the
     Thread and WiFi figures, named as this fleet's single-trial observations
   - Acceptance: the page exists, states both directions with their figures and their trial
     count, attributes the stale-advertisement direction to `discover_mdns()` and not to
     `discover()`, presents no figure as a guarantee or a library constant, contains no em
     dash, and the documentation build passes under `--strict` with zero warnings

8. **Pseudonymised committed artefacts**: No live identifier reaches the repository.
   - Current: the probe prints raw serials, mDNS instance names, SRV target hostnames and
     IPv6 addresses; the staleness tool emits raw serials into its session files
   - Target: every artefact this phase commits, from both runs, carries format-preserving
     pseudonyms from the operator's private mapping, with the same device reading as the
     same alias in every field, including mDNS instance names and SRV target hostnames,
     which embed the serial and therefore leak it even when the TXT `id` value is substituted
   - Acceptance: the staged diff for every commit in this phase contains no live serial, MAC
     address, IPv4 or IPv6 literal, or `.local` hostname; the operator has inspected the
     staged diff against the private mapping before each commit; a device appearing in both
     the probe transcript and the staleness evidence carries the same alias in both

## Boundaries

**In scope:**

- The three `report_records()` fixes in `.planning/scripts/ipv6_thread_probe.py` (R1, R2, R3)
- Tooling tests in `.planning/scripts/tests/test_ipv6_thread_probe.py` covering each fix
- One pseudonymised probe transcript from the real Thread fleet (R4)
- One WiFi staleness trial through the unchanged `staleness` subcommand, with a WiFi roster
  satisfying `validate_expected_roster()` (R5)
- A `17-EVIDENCE/` directory holding the WiFi session manifest and staleness JSONL (R5)
- A written finding with the verdict and the figure correction (R6)
- ROADMAP and REQUIREMENTS corrections for the conflated 69 s figure (R6)
- One caller-facing discovery liveness page or section in `docs/` (R7)
- Pseudonymisation of every committed artefact (R8)

**Out of scope:**

- Changes to `src/lifx/` library code. Both requirements are operator tooling plus
  documentation; the library behaviour the probe reports on was settled by Phase 16
- Changes to `validate_expected_roster()` or to `STALENESS_CAP_S`. A WiFi roster satisfies
  the existing gate, and the frozen cadence and cap are what make the two runs comparable
- A finer poll cadence for the WiFi leg. Protocol identity with THREAD-04 is the point of a
  control; a bounded WiFi result of "at most 60 s" against a 4140 to 4200 s Thread interval
  already answers the question
- Repeated WiFi trials or additional device classes. One trial mirrors THREAD-04's design;
  variance bounding is a separate piece of work
- Root-causing a surprising WiFi result. If a WiFi bulb outlives its power, that is recorded
  and escalated as a new requirement or seed; chasing library-side caching is unbounded and
  belongs to its own phase
- Settling LIFX's SRP lease value. One trial cannot distinguish a genuine 70 minute lease
  from OpenThread's 7200 s default sampled mid-cycle, and SEED-002 says so
- Editing `docs/changelog.md`. That file is generated by the release workflow
- The em dash sweep of pre-existing `docs/` prose. That is Phase 20; this phase only avoids
  adding new occurrences

## Constraints

- Both requirements produce hardware evidence and are hardware-gated. Neither can be
  verified by the emulator suite and neither may block CI or any other phase
- The probe and the staleness tool sit under `.planning/scripts/`, outside the measured tree
  as established by Phase 15's two-target `--cov` rule. Their tests are the `--tooling`
  opt-in category and are not run by any CI job
- `.planning/**` is absent from `ci.yml`'s `pull_request.paths` filter, so a change confined
  to these scripts does not trigger CI
- The 60 s absolute cadence, the three consecutive both-legs-absent confirmation rule and the
  three hour `STALENESS_CAP_S` cap are frozen for this phase
- Phase 17 is serial after Phase 16 because the probe drives `selected_address_for()`, whose
  owner-name normalisation MDNS-09 settled
- Australian English throughout, and no em dash in any prose this phase adds
- Any change to `docs/` must keep the documentation build green under `--strict`

## Acceptance Criteria

- [ ] A tooling test asserts the view reports the absent-record state for a target with no cached A or AAAA record, and fails against the pre-change source (amended, see below)
- [ ] A tooling test asserts the view reports the refused-record state, with the record count and per-record classification, for a target holding unscoped link-local AAAA records, and fails against the pre-change source (amended, see below)
- [ ] The refused-record message reports how many address records were seen for the target
- [ ] The probe keys `addresses_for()` and `selected_address_for()` on the same normalised owner, so a trailing-dot SRV target reaches the same lookup key as its bare form
- [ ] An instance whose cached records were refused but which has a usable packet-source fallback reports the fallback, or states that a fallback existed and was not used
- [ ] `grep -n 'linklocal_chosen\|is_reachable_choice' .planning/scripts/ipv6_thread_probe.py` returns nothing
- [ ] The IPv4-preferred, fallback-source and routable-preferred `WHY` branches still print, and their tooling tests pass
- [ ] A tooling test asserts the view marks a malformed middle instance and still returns all three entries in order, and a smoke test calls `report_records()` over the same cache and asserts it returns normally (amended, see below)
- [ ] A TXT payload parsing as `TxtData` but carrying no `id`, `p` or `fw` key prints `?` for the missing values without raising
- [ ] A pseudonymised transcript of one real Thread-fleet probe run is committed under `17-EVIDENCE/`
- [ ] The probe's `--alias-map` redaction replaces every mapped serial wherever it appears, including inside mDNS instance names and SRV target hostnames, and rewrites every address to a literal inside a documentation range, drawn from a sub-range reserved for that address's source class, no two source classes sharing a sub-range, stably within a run (amended twice, see below)
- [ ] With no `--alias-map` given, the probe prints raw identifiers exactly as it does today
- [ ] The finding states which new probe messages the hardware run did and did not produce
- [ ] `17-EVIDENCE/` holds a WiFi session manifest and a staleness JSONL with exactly one WiFi alias row and every intervening poll
- [ ] The WiFi row carries a `disposition`, a `first_absence_poll` and a `restoration_duration_s`; `confirmed_expiry_poll` is present when the disposition is `confirmed_expiry`
- [ ] A `censored` WiFi disposition is recorded as the observed result and closes R5 rather than blocking the phase
- [ ] A same-alias rerun of `staleness` records no second row and runs no power script
- [ ] Exactly one device is unplugged at a time and the WiFi run shares no session directory with any other run
- [ ] The finding names all four figures with their measurement resolutions and does not compare the 60 s-quantised WiFi bound against the Thread interval as if both were point values
- [ ] The finding names in advance the observation that would have supported the opposite verdict
- [ ] The ROADMAP and REQUIREMENTS entries for DISC-04 no longer call 69 s a disappearance-to-expiry figure
- [ ] A `docs/` page states that `discover_mdns()` can yield a device whose advertisement has outlived it, and that `discover()` verifies an mDNS candidate with a correlated request before yielding it, with both directions, both figures and the trial count (amended, see below)
- [ ] The documentation build passes under `--strict` with zero warnings and the new prose contains no em dash
- [ ] The staged diff for every commit in this phase contains no live serial, MAC address, IPv4 or IPv6 literal, or `.local` hostname
- [ ] mDNS instance names and SRV target hostnames are pseudonymised, not only the TXT `id` value
- [ ] A device appearing in both the probe transcript and the staleness evidence carries the same alias in both

**Negative criteria (from the prohibition probe):**

- [ ] No committed artefact or prose presents the single WiFi trial, or the Thread and WiFi pair, as a general guarantee, a lease value, a universal limit, or a tuning input for any library constant
- [ ] No committed artefact contains a serial-shaped, MAC-shaped, IPv4 or IPv6 literal, or `.local` hostname token that is not a documented pseudonym
- [ ] No commit is made before the operator has inspected its staged diff against the private mapping
- [ ] The phase does not close over a failed power-on that leaves a device dark; a power-on failure is an explicit stop naming manual recovery
- [ ] `STALENESS_CAP_S` is not extended and no `censored` disposition is converted into an expiry
- [ ] No file under `.planning/milestones/v2.0-phases/` is modified

## Edge Coverage

**Coverage:** 18/22 applicable edges resolved · 0 unresolved · 4 dismissed

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | AC-05: refused records plus a usable packet-source fallback must not silently discard the fallback. |
| empty | R1 | ✅ covered | AC-01: a target with zero cached address records is R1's absent case. |
| encoding | R1 | ✅ covered | AC-04: the probe passes `srv.target.lower()`, but `selected_address_for()` normalises via `_normalise_dns_name()`; both lookups key on the same normalised owner. |
| ordering | R1 | ⛔ dismissed | `_instance_view()` already sorts instances lexically; R1 changes message text within an instance, not iteration order. |
| adjacency | R2 | ✅ covered | AC-07: the three still-reachable `WHY` branches keep printing after the dead branch is removed. |
| empty | R2 | ⛔ dismissed | `report_records()` returns before the summary block when `views` is empty, so the removed line is unreachable there. |
| ordering | R2 | ⛔ dismissed | Summary line order is presentational; no behavioural contract depends on it. |
| adjacency | R3 | ✅ covered | AC-08: each malformed field is named once and the instance's remaining well-formed fields still print. |
| empty | R3 | ✅ covered | AC-08: a TXT owner with no parseable `TxtData` is R3's core case. |
| encoding | R3 | ✅ covered | AC-09: a `TxtData` carrying no `id`, `p` or `fw` key prints `?` rather than raising. |
| ordering | R3 | ✅ covered | AC-08: instances after the malformed one print unchanged and in the same order. |
| unclassified | R4 | ✅ covered | AC-11: where a state was not observed on hardware, the finding says so rather than implying it was shown. |
| boundary | R5 | ✅ covered | AC-13, AC-14: absent-at-poll-1 is recorded as a bound, and a censored run at the cap is a valid recorded outcome. |
| precision | R5 | ✅ covered | AC-17: each figure carries its measurement resolution; the 60 s-quantised bound is never treated as a point value. |
| concurrency | R5 | ✅ covered | AC-16: one device unplugged at a time, no shared session directory. Added by the author; not proposed by the classifier. |
| idempotency | R5 | ✅ covered | AC-15: a same-alias rerun records nothing and runs no power script. Added by the author; not proposed by the classifier. |
| boundary | R6 | ✅ covered | AC-18: the finding names in advance the observation that would have supported the opposite verdict, so it is not retrofitted. |
| precision | R6 | ✅ covered | AC-17, AC-19: all four figures named with their resolutions; 4140 to 4200 s is not rounded to a point value. |
| unclassified | R7 | ✅ covered | AC-20, AC-21: figures stated as single-trial fleet observations, no em dash added. |
| adjacency | R8 | ✅ covered | AC-23: mDNS instance names and SRV target hostnames embed the serial and are pseudonymised alongside the TXT `id`. |
| empty | R8 | ⛔ dismissed | R4 and R5 both mandate a committed artefact, so the no-artefact case is already excluded. |
| ordering | R8 | 🧪 backstop | Substitution order could double-substitute when one pseudonym prefixes another live value. Held-out check for plan-phase `must_haves`: the operator greps the staged diff for the private mapping's live values before committing. Cannot be a committed test, because the mapping lives outside the repository. |

## Prohibitions (must-NOT)

**Coverage:** 6/6 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT present the single WiFi trial, or the Thread and WiFi pair, as a general guarantee, a lease value, a universal limit, or a tuning input for any library constant | R6, R7 | resolved | judgment. Mirrors the discipline THREAD-04 held when it refused to call 4200 s a lease. |
| MUST NOT commit an artefact containing a serial-shaped, MAC-shaped, IPv4 or IPv6 literal, or `.local` hostname token that is not a documented pseudonym | R8 | resolved | test. Descriptor not captured at spec time; the wired check is chosen during planning. |
| MUST NOT commit before the operator has inspected the staged diff against the private mapping | R8 | resolved | judgment. The mapping lives outside the repository, so only the operator can perform this check. |
| MUST NOT close the phase over a failed power-on that leaves a device physically dark | R5 | resolved | judgment. The tool already emits the verdict; the prohibition is on treating it as a close. |
| MUST NOT extend `STALENESS_CAP_S` or convert a `censored` disposition into an expiry | R5 | resolved | test. Descriptor not captured at spec time; `thread_revalidation.py:462` already asserts the manifest cap matches the constant. |
| MUST NOT modify any file under `.planning/milestones/v2.0-phases/` | R6 | resolved | test. Descriptor not captured at spec time; a staged-path check is the likely wiring. |

**Canon referral:** argv handling and path safety in the operator-supplied power-off and
power-on scripts is canon security, owned by `/gsd-secure-phase`, and is not minted here.

## Amendments

Two amendments were made during `/gsd-discuss-phase 17` on 2026-09-08. Neither changes a
requirement; both change how a requirement is evidenced. Four more were made during
`/gsd-plan-phase 17` on 2026-09-08, each after a cross-AI review found a claim the shipped
code cannot support. A3 changes what R7 publishes; A4 and A5 change the contract AC-21 holds
the address redaction to, A5 correcting an error A4 introduced; A6 splits R3's three
conditions by whether they can still occur. A7 and A8 were made during `/gsd-execute-phase 17` on
the same date, and A9 during `/gsd-code-review 17 --fix` the day after: A7 after real-hardware output halted at the identity backstop on an identifier class
the redactor cannot reach, and A8 after preparing the WiFi arm against the real fleet falsified the
spec phase's expectation that no tooling change would be needed.

**A1. AC-01, AC-02 and AC-08 become state-level.** As written they asserted on printed message
text. The discussion located the malformed-instance handling in `_instance_view()` rather than in
`report_records()`, and put the R1 and R3 tests in the existing `TestSyntheticCacheReporting`
class, which asserts on the view rather than on stdout. Message-text criteria are therefore
unsatisfiable from where the tests live. AC-01 and AC-02 now assert the state the view reports,
leaving the wording free to change. AC-08 keeps one smoke test that calls `report_records()` over
a cache with a malformed middle instance and asserts it returns normally, because "the run
completes" is R3's reason for existing and no view-level assertion covers it.

**A2. The probe gains an opt-in `--alias-map` redaction, replacing hand-pseudonymisation.** The
spec-phase decision chose a hand-substituted transcript over adding redaction to the probe. That
was decided without knowing that `thread_revalidation.py:3070` and `measure_merged_discovery.py`
both already carry an alias-map loader that reads the mapping from outside the repository into
memory only, so raw identities never reach tracked evidence. With the precedent two scripts deep,
a structural guarantee replaces a manual step. The flag is opt-in and raw output stays the
default, because the probe's diagnostic value to the operator depends on naming the physical
device. The serial-keyed map alone is insufficient, since the transcript also carries A, AAAA and
packet-source addresses that AC-22 forbids, so the redaction also rewrites addresses to
documentation-range equivalents of the same class. Substitution is a whole-line replace of any
mapped serial, which covers mDNS instance names and SRV target hostnames without the probe
needing to know each field's format. (The "same class" clause in this paragraph is superseded by
A4 below, which replaces the round-trip contract with a prefix reservation; the rest of A2
stands.)

**A3. R7 and AC-20 attributed the staleness hazard to the wrong function.** As written, R7
required prose stating that `discover()` yielding a device is not evidence the device is
reachable. That is false for the shipped library. `discover()` routes its mDNS candidates
through `_discover_verified_devices_mdns` (`src/lifx/api.py:1128`), which hands each candidate
to `_verify_mdns_candidate` (`src/lifx/network/discovery/mdns/discovery.py:1351`); that opens a
`DeviceConnection`, sends `Light.GetColor()` or an `EchoRequest`, rejects a serial mismatch, and
yields only on a correlated answer. A device built from a stale advertisement therefore cannot
reach a `discover()` caller. `find_by_serial()` verifies through the same helper
(`src/lifx/api.py:1374`, inside `_race_serial_sources`). The function that can yield an
unverified advertisement is `discover_mdns()` (`src/lifx/api.py:1268`), which calls
`discover_devices_mdns` directly.

R7's "Current" statement was wrong in the same direction: it claimed nothing in `docs/` states
the hazard, when `docs/user-guide/discovery.md`'s Limitations section and `discover_mdns()`'s
docstring both already draw the distinction, in wording Phase 16 deliberately locked into the
approved-phrase tuple. Publishing R7 as originally written would have contradicted the shipped
behaviour, contradicted the page it was extending, and required breaking a Phase 16 lock to do it.

The amendment keeps R7's purpose and narrows its claim. What this phase adds is not the
distinction, which exists, but the measured durations on both sides of it, plus the
restoration-delay direction, which is genuinely undocumented. D-16 needs no amendment: it
already frames R7 as quantifying the existing claim and adding its converse, which is exactly
what the corrected R7 does. D-17, D-18 and D-19 are unaffected.

Found by the Codex lane of `/gsd-review --phase 17`, verified against source before this
amendment was made.

**A4. AC-21 required a class round trip that no documentation range can satisfy.** As written,
AC-21 required every address to be rewritten "to a documentation-range equivalent of the same
class". Three of the four classes can do this: `classify_address("192.0.2.1")` returns `IPv4`,
`classify_address("fd00::2")` returns `ULA`, and `classify_address("fe80::7")` returns
`link-local`. GUA cannot. `2001:db8::/32` is the documentation range, and Python's `ipaddress`
reports `is_global` False for it, so `classify_address("2001:db8:1::5")` returns `IPv6-other`.
There is no documentation-safe IPv6 range that classifies as `GUA`, which makes a round-trip
contract for that class unsatisfiable by construction rather than by oversight. Verified by
running the shipped classifier at `.planning/scripts/ipv6_thread_probe.py`.

AC-21 now requires a **prefix reservation**: each source class gets its own documentation prefix,
no two classes share one, and substitution is stable within a run. That is what the redactor can
actually guarantee, and it preserves the property the criterion existed to protect. What R1's
refused case demonstrates is that the cached records were of a class the selector rejects; a
reader of the committed transcript can still recover that distinction from the reserved prefix.
What is lost is only the ability to recover the class by re-running `classify_address()` over the
redacted text, which nothing in this phase does. `2001:db8:1::` and `2001:db8:2::` both collapse
to `IPv6-other` under re-classification, so the reserved prefix rather than the classifier is
what carries the class after redaction, and `_TranscriptRedactor`'s docstring must say so.

D-11 carries the same "same class" claim in decision form and is amended alongside this, so the
SPEC and the decision record do not disagree. D-09, D-10 and D-12 are unaffected.

Found by the Codex lane of the second `/gsd-review --phase 17` pass, which flagged the plan as
formally non-conforming to its own locked criterion. The plan's engineering was already correct;
the criterion was wrong. Verified against source before this amendment was made.

**A5. A4's prefix table named two operational ranges as documentation ranges.** A4 replaced AC-21's
class round trip with a prefix reservation, and the table it settled on mapped ULA sources to
`fd00::N` and link-local sources to `fe80::N`. Neither is a documentation range. `fd00::/8` is the
locally-assigned half of the operational Unique Local space (RFC 4193) and `fe80::/10` is
operational link-local space (RFC 4291); the only IPv6 range reserved for documentation is
`2001:db8::/32` (RFC 3849), alongside `192.0.2.0/24` for IPv4 (RFC 5737). A pseudonym drawn from an
operational range is not a pseudonym in the sense AC-22 needs: it is a different real address.

The concrete harm was in the backstop rather than the transcript. The staged-diff gate whitelisted
`fd00::` and `fe80::` forms as safe output, so a live short operational address passed it. Verified
by running the predicate: `fe80::1` and `fd00::abcd` are accepted. The exposure was bounded, because
the whitelist caps the suffix at four hex characters and so still rejected a live LIFX EUI-64
address such as `fe80::d073:d5ff:fe00:1234` and a live routable ULA such as `fd12:3456:789a::1`, but
a gateway's `fe80::1` is exactly the kind of packet-source address the probe prints.

Every IPv6 pseudonym now comes from inside `2001:db8::/32`, one sub-range per source class:
`2001:db8:1::` for GUA, `2001:db8:2::` for IPv6-other, `2001:db8:3::` for ULA and `2001:db8:4::` for
link-local. IPv4 stays at `192.0.2.x` and an IPv4-mapped value stays at `::ffff:192.0.2.x`. This
keeps A4's principle intact, that the reserved sub-range rather than `classify_address()` carries
the source class, and it makes the backstop exact rather than approximately safe: after this change
any `fd00::` or `fe80::` token in a staged diff is a leak by definition, with no whitelisted form to
hide behind. A reader loses nothing, because a redacted link-local address is still identified as
link-local by the probe's own message text and by its preserved zone suffix, not by its literal.

D-11 is amended to the same table. Found by the Codex lane of the third `/gsd-review --phase 17`
pass, which correctly identified that the error was introduced by A4 itself.

**A6. R3 required a diagnostic for a condition the typed view makes impossible.** R3's target said
each of three bare assertions becomes a diagnostic line. Two remain reachable and do: an unparsed
TXT payload prints a diagnostic and the loop continues, and an instance with no usable chosen
address now renders through R1's non-resolving states instead of terminating. The third, the
non-list AAAA check, is eliminated by construction once `_InstanceView.aaaa` is typed
`tuple[str, ...]` and built inside `_instance_view()`. Re-adding it as a runtime branch would create
exactly the dead code R2 is deleting elsewhere in this same phase, and CONTEXT records that
converting an unreachable guard into a branch was already rejected on that ground.

The defect was not the engineering, which is right, but that the locked target and the plan's own
`must_haves` both continued to promise a diagnostic that will not exist, so execution could not
honestly mark both satisfied. R3 now states the three dispositions separately and requires the
elimination to be recorded rather than evidenced by a branch. Found by the Codex lane of the third
review pass.

**A7. A firmware-assigned SRV hostname is committable evidence.** Added during
`/gsd-execute-phase 17` on 2026-09-08, after plan `17-03-PLAN.md` halted at its identity backstop
on real-hardware output. Ten of the sweep's matrix-class instances publish an SRV target that is a
bare sixteen-character hexadecimal `.local` label rather than the operator-chosen
`LIFX-<Type>-<n>.local` form the other instances use. They are stable across sweeps, so they are
durable per-device identifiers, and the alias map cannot reach them: none contains a mapped serial,
so D-10's serial-keyed substitution has nothing to substitute, and they do not parse as addresses,
so the address pass does not apply either.

The operator inspected the raw DNS-SD packet and the LIFX details a user can retrieve from a device
and found no mapping in either direction between such a label and any real, user-retrievable
device-specific value. A label that cannot be resolved to a device identity by any means available
to a reader is functionally already a pseudonym. On that finding the class is accepted into
committed evidence.

The backstop is narrowed accordingly, in two parts. First, a defect: the label hex test carried a
bare `[0-9a-fA-F]{12}`, which matched the twelve-character substring inside a longer all-hex label,
so a sixteen-character label blocked on a rule written for twelve-character serials. It now carries
the same alphanumeric boundaries the free-standing token test in the same expression already used.
Second, the widening this amendment authorises: a label that is **entirely hexadecimal and not
exactly twelve characters long** is enumerated for operator adjudication rather than blocked. A raw
LIFX serial is exactly twelve hex characters and still fails the gate, as does a separator-less MAC
address, and any label carrying a non-hexadecimal character still faces the full alias grammar. The
exemption admits the firmware class and nothing else.

This does not relax AC-23, which governs SRV hostnames that embed the serial. Those are still
pseudonymised, and a label embedding one still fails the gate.

**A8. `thread_revalidation.py` is modified, under four named authorisations.** Added during
`/gsd-execute-phase 17` on 2026-09-08, before the WiFi arm ran. The spec phase recorded that a WiFi
roster would satisfy `validate_expected_roster()` "unchanged; no tooling change", and `17-04-PLAN.md`
carried a gate asserting the tool was byte-identical to `main`. Preparing the arm against the real
fleet falsified that expectation four times over, and the operator authorised each change explicitly:

1. **The discovery timeout is passed at the call site as 45 s**, not the library's 15 s default. The
   fleet is roughly 66 devices on a contested network, and a target that replies after 15 s reads as
   absent; three such polls would confirm an expiry that never happened. `lifx.const.DISCOVERY_TIMEOUT`
   is untouched -- this is an explicit `timeout=` argument, so no shipped library behaviour changes.
2. **Each poll records measured wall-clock elapsed time, not `poll_index * interval_s`.** At 45 s a
   fully-absent poll runs both legs sequentially and overruns the 60 s interval, so the nominal figure
   would have understated the expiry bound by roughly 1.5x. THREAD-04 had no overruns, so nominal and
   measured were identical for it; this makes the WiFi arm correct without changing what the two arms
   are being compared on.
3. **Restoration closes on the first discovery leg present, is bounded, and records each leg.** It
   previously required *both* legs in an unbounded `while True`. A WiFi bulb has no Thread Border
   Router rebroadcasting its records, so one that answers `discover()` in seconds may never
   re-advertise over mDNS inside the session -- the old loop would have hung the run forever. Two
   nullable row fields, `restoration_discover_s` and `restoration_mdns_s`, keep the transports
   distinguishable, and being nullable is what lets v2.0's committed row still validate.
4. **The manifest inventory accepts `InfraredLight` and `HevLight`.** The schema restricted them to
   named gaps, encoding an assumption that the operator owns none. The operator owns five, so a
   full-fleet roster was rejected outright. Mutual exclusivity is preserved per roster -- zero aliases
   closes as a named gap, aliases present must close with evidence, never both.

**What R5 names as frozen is untouched, with one narrowing recorded below.** R5's target specifies
the 60 s absolute cadence, the three consecutive both-legs-absent confirmation rule and the
three-hour `STALENESS_CAP_S` cap. All three live in `measurement_support.py`, which no authorised
commit modified, and all three still read 60.0, 3 and 10800.0. The `MUST NOT extend
STALENESS_CAP_S or convert a censored disposition into an expiry` prohibition stands and its
manifest assertion is still in place.

The security audit of 2026-09-08 found this paragraph's original blanket phrasing slightly
overstated, and it is corrected here rather than left to be rediscovered. Change 2 narrowed one
cap-adjacent assertion in `_validate_staleness_event()` from `elapsed_s > STALENESS_CAP_S` to
`elapsed_s > STALENESS_CAP_S and not is_last_poll`, so the final poll's measured wall-clock time may
now exceed the cap. That follows necessarily from recording measured rather than nominal time, since
a poll that overruns its interval can carry the run past the cap on the very poll that closes it. It
narrows the validator rather than extending the cap, and it cannot convert a censored disposition
into an expiry, so the prohibition holds. The constants are untouched; the rule enforcing the cap
was narrowed by exactly this much.

**The arms are no longer protocol-matched, and the phase must say so.** DISC-04 as worded asks for a
control using "the same protocol THREAD-04 used". After these four changes that is no longer strictly
true, on top of the confounder asymmetry the operator has recorded -- the Thread network is
uncontested, the WiFi network is not. `17-05-PLAN.md`'s verdict must state both departures plainly
rather than presenting the two runs as a matched pair. DISC-04's own wording also conflates the
69.4 s restoration figure with the disappearance-to-expiry interval, which `17-05-PLAN.md` already
exists to correct.

`17-04-PLAN.md`'s `THREAD-REVALIDATION-MODIFIED` gate is rewritten under this amendment: it pins the
tool to the authorised content by blob hash, checked against both `HEAD` and the working tree, rather
than diffing against `main`. Any further change to the tool must update that hash deliberately, with
the amendment that authorises it.

**A9. The code review's fixes land in the pinned tool, and the pin moves with them.** Added during
`/gsd-code-review 17 --fix --auto --all` on 2026-09-09, after the phase was already complete,
verified and secured. A8 required that any further authorised change to `thread_revalidation.py`
update its blob pin "deliberately and with the amendment that authorises it". This is that
amendment.

Two of the five code-review findings live in that file: **WR-02**, the session-summary projection
dropping the `restoration_discover_s` and `restoration_mdns_s` fields A8 change 3 added, so
`generate_report()` silently lost the per-leg data that change existed to produce; and **IN-03**, a
bounded second-leg restoration wait that could overrun its own bound by up to one poll. Both are
fixed. The pin moves from `ad0fea79ba0d83b15e3f1990ecdf762213b8670a` to
`a57bd684f9e09e644744b6812980f5f321e3ba53`.

R5's frozen constants are untouched again: `measurement_support.py` is absent from the fix commits,
and the cadence, confirmation rule and cap still read 60.0, 3 and 10800.0. The narrowing A8 recorded
for the cap-adjacent assertion is unchanged. No committed evidence was edited, and both v2.0's
session and this phase's still load and validate through the fixed code.

**One fix was reverted rather than kept, and the reason is a rule worth stating.** IN-02 reported
that the IPv4 pseudonym pool exhausts at 254 distinct addresses and raises partway through a write.
The first attempt widened the pool to all three RFC 5737 documentation ranges. That broke the
invariant A5 exists to hold: the staged-diff identity backstop whitelists `192.0.2.` alone, so an
emitted `198.51.100.x` would have been reported as a live-address leak and failed the gate. It is
the same dead end T-17-29 was written to eliminate, a gate failing closed on output the tool itself
legitimately produced.

**The emittable set and the backstop whitelist are one contract and must move together or not at
all.** They did not need to move here. One run's distinct IPv4 literals are memoised per address on
a fresh redactor per invocation; the committed transcript emitted 17 against a ceiling of 254, and a
whole-fleet WiFi sweep would reach roughly 70, since only devices with an A record contribute and
the Thread devices have none. The ceiling was never the defect. The failure mode was, and it is
fixed: the message now names the limit, states that the partial transcript must be discarded, and
warns against widening the pool.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                                        |
|--------------------|-------|------|--------|--------------------------------------------------------------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Control target and counter disposition both locked in round 1 |
| Boundary Clarity   | 0.88  | 0.70 | ✓      | Explicit out-of-scope list with reasons                       |
| Constraint Clarity | 0.86  | 0.65 | ✓      | Cadence, cap and roster gate all frozen                       |
| Acceptance Criteria| 0.88  | 0.70 | ✓      | 24 positive plus 6 negative pass/fail criteria                |
| **Ambiguity**      | 0.117 | ≤0.20| ✓      |                                                              |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective     | Question summary                                  | Decision locked                                                                          |
|-------|-----------------|---------------------------------------------------|------------------------------------------------------------------------------------------|
| 1     | Researcher      | Which figure does the WiFi control target?         | Both. The roadmap's "69s disappearance-to-expiry" conflates 69.4 s restoration with the 4140 to 4200 s interval; the correction is a deliverable |
| 1     | Researcher      | `linklocal_chosen`: make reachable or remove?      | Remove the counter, its increment, its summary line and the `is_reachable_choice()` warning |
| 1     | Simplifier      | How much hardware does the WiFi run cover?          | One WiFi bulb, one trial, mirroring THREAD-04's design                                     |
| 2     | Researcher      | How does the WiFi session get a manifest past the six-class roster gate? | A WiFi roster satisfies `validate_expected_roster()` unchanged; no tooling change          |
| 2     | Simplifier      | What does the phase owe if the WiFi result surprises? | Record and escalate as a new requirement or seed; root-causing is out of scope             |
| 2     | Boundary Keeper | Does the phase publish the consumer hazard in `docs/`? | Yes, a caller-facing discovery liveness note                                               |
| 3     | Boundary Keeper | Is a 60 s-quantised WiFi bound an acceptable control? | Yes. Protocol identity is what makes the comparison valid; cadence and cap stay frozen     |
| 3     | Boundary Keeper | What proves MDNS-10's three fixes?                  | Tooling tests for each fix, plus one pseudonymised real-hardware run                        |
| 3     | Boundary Keeper | What is committed as DISC-04's deliverable?         | A `17-EVIDENCE/` directory mirroring Phase 14, plus a separate written finding              |
| 4     | Failure Analyst | What does a censored WiFi run mean?                 | A valid and interesting recorded result that closes R5, unlike THREAD-04's blocking rule    |
| 4     | Failure Analyst | How is the probe transcript's privacy risk controlled? | Hand-pseudonymised transcript with staged-diff inspection; no redaction mode added          |
| 4     | Failure Analyst | What claim strength must the verdict meet?          | Stated with its own limits, naming what one paired trial supports and what it does not      |
| 5.5   | Edge probe      | Does the probe's trailing-dot lookup seam belong here? | In scope. Both lookups key on the same normalised owner                                     |
| 5.5   | Edge probe      | Do mDNS instance names and SRV targets need pseudonyms? | Yes. Both embed the serial, so substituting the TXT `id` alone still leaks it               |
| 5.5   | Edge probe      | Do the four dismissals hold?                        | All four confirmed with reasons on the record                                               |
| 5.6   | Prohibition probe | Which must-NOT statements survive the precision filter? | All six kept: one privacy pair, one claim-strength, one safety, two evidence-integrity      |

---

*Phase: 17-fleet-diagnostics-and-the-staleness-control*
*Spec created: 2026-09-08*
*Next step: /gsd-discuss-phase 17, which covers implementation decisions: message wording, test fixture shape, evidence layout and docs placement*
