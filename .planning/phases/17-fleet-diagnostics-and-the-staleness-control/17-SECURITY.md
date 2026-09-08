---
phase: "17"
slug: "fleet-diagnostics-and-the-staleness-control"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-08"
---

# Phase 17 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

This phase produced two committed hardware evidence artefacts from a live fleet, so almost
every threat here is an information-disclosure threat about identifiers reaching a public
repository. The register was authored at plan time across all five plans and verified
retrospectively by `gsd-security-auditor` at ASVS level 1 with a `high` blocking threshold.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Live fleet to operator terminal | The probe and the revalidation tool query real devices and print what they observe | Real serials, MAC addresses, IPv4 and IPv6 addresses, `.local` hostnames |
| Operator terminal to git repository | The one run whose output is committed passes through `--alias-map` redaction, an automated staged-diff backstop, and a blocking operator inspection | Format-preserving pseudonyms only |
| Private alias map to process memory | The raw-serial-to-alias mapping lives outside the repository and is read into memory only | The mapping itself, which must never be written anywhere tracked |
| Repository to published documentation | Measured durations reach `docs/user-guide/` as caller-facing prose | Figures and qualitative claims, no identifiers |
| This phase to v2.0's committed evidence | Phase 14's Thread baseline is cited as the comparison and must not be edited | Read-only |
| Plan 17-03 to plan 17-04 | Both stage into one git index and share `17-EVIDENCE/`; serialised into separate waves | Staged artefacts |

---

## Threat Register

29 threats, T-17-01 to T-17-29 (T-17-29 is counted once; it appears in `17-03-PLAN.md` and
`17-04-PLAN.md` with the same substance). All closed.

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-17-01 | Denial of Service | `report_records()` over a partially assembled instance | medium | mitigate | Rendered marker replaces the bare TXT assertion; `test_report_records_completes_over_a_malformed_middle_instance` | closed |
| T-17-02 | Information Disclosure | Probe stdout carrying live identifiers | high | accept | Scoped acceptance, re-verified. See Accepted Risks Log, ACC-17-01 | closed |
| T-17-03 | Tampering | Accidental edit to Phase 14's committed evidence | low | mitigate | Branch-diff gate over `.planning/milestones/v2.0-phases/`; 0 hits | closed |
| T-17-04 | Information Disclosure | Incomplete redaction before a commit | high | mitigate | Whole-text serial substitution across three spellings plus single-pass address substitution; committed transcript scans clean | closed |
| T-17-05 | Information Disclosure | Double substitution leaving a partial token | medium | mitigate | Two forward-only `re.sub()` passes; neither re-scans its replacement | closed |
| T-17-06 | Input Validation | Malformed or hostile `--alias-map` JSON | low | mitigate | `_load_probe_alias_map()` reuses the hardened contract; four rejection tests | closed |
| T-17-07 | Tampering | An alias map committed by accident | high | mitigate | Loader refuses any path resolving inside the repository; no alias map tracked anywhere | closed |
| T-17-08 | Information Disclosure | A live identifier reaching the committed transcript | high | mitigate | Redaction, automated staged-diff backstop, blocking operator inspection; all three verified | closed |
| T-17-09 | Information Disclosure | A live hostname that is not serial-shaped | medium | mitigate | All 46 `.local` tokens enumerated and adjudicated by the operator into two named classes | closed |
| T-17-10 | Information Disclosure | The private alias map itself committed | high | mitigate | Same loader refusal; map read into memory only | closed |
| T-17-11 | Tampering | Accidental edit to Phase 14's evidence | low | mitigate | Same branch-diff gate; 0 hits | closed |
| T-17-12 | Information Disclosure | A live identifier in the committed manifest or JSONL | high | mitigate | Tool writes aliases not serials; backstop over both files reports none; operator gate recorded | closed |
| T-17-13 | Tampering | A second power cut on an already-recorded device | medium | mitigate | Same-alias check returns before the first power-script call | closed |
| T-17-14 | Tampering | The frozen cadence, cap or confirmation rule changed | medium | mitigate | **Closed by a different mechanism than the register states.** See note below | closed |
| T-17-15 | Denial of Service | A failed power-on leaving a device dark | medium | mitigate | `power_on_failed` names manual recovery; four distinct stop answers in the resume signal | closed |
| T-17-16 | Tampering | Accidental edit to the comparison baseline | low | mitigate | Same branch-diff gate; 0 hits | closed |
| T-17-17 | Repudiation | A published figure read as a guarantee or lease value | medium | mitigate | Single-trial qualifier in the locked fragments, above the pre-existing timeout disclaimer | closed |
| T-17-18 | Tampering | A later recast dropping the liveness claim | low | mitigate | Three fragments inside the owning test's `approved_phrases` tuple; 24/24 pass | closed |
| T-17-19 | Information Disclosure | An address reaching published documentation | low | mitigate | New prose carries no address literal; the documentation-safe-address test passes | closed |
| T-17-20 | Tampering | The Thread baseline edited while being cited | low | mitigate | Same branch-diff gate; 0 hits | closed |
| T-17-21 | Information Disclosure | A partially substituted IPv4-mapped IPv6 token | high | mitigate | One combined alternation applied once, IPv6 branch first; `::ffff:` values consumed whole | closed |
| T-17-22 | Information Disclosure | A failed probe run recorded as a successful capture | medium | mitigate | `set -o pipefail`, recorded exit status, independent fenced-content gate | closed |
| T-17-23 | Repudiation | A power-on-failed row carried forward as a completed trial | medium | mitigate | Gate rejects a null `restoration_duration_s`; recovery preserves the failed session whole | closed |
| T-17-24 | Repudiation | Publishing a caller-facing claim the library does not honour | high | mitigate | SPEC amendment A3 corrected the attribution; published prose names `discover_mdns()`, not `discover()` | closed |
| T-17-25 | Tampering | A redacting stream outliving its run | medium | mitigate | `contextlib.redirect_stdout()` rather than assignment; asserted restored on both the normal and raising paths | closed |
| T-17-26 | Tampering | 17-04's recovery reaching 17-03's committed transcript | high | mitigate | Waves serialised; every staging operation names its own paths; recovery moves only its two files | closed |
| T-17-27 | Repudiation | A same-alias rerun claimed but never performed | medium | mitigate | Three scratch records written and compared by gate; hashes asserted equal both ways | closed |
| T-17-28 | Information Disclosure | A pseudonym drawn from operational address space | high | mitigate | Every pseudonym inside `2001:db8::/32` or `192.0.2.0/24`; no `fd00:` or `fe80:` token survives | closed |
| T-17-29 | Denial of Service | An unreachable adjudication route stranding a hardware sitting | medium | mitigate | D-23 splits the backstop; all-decimal runs report without failing, so the operator checkpoint is reachable | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Note on T-17-14

The register states this threat's mitigation as "a separate gate fails if `thread_revalidation.py`
appears in the branch diff at all". That gate no longer exists: SPEC amendment A8 authorised four
changes to the tool, and `17-04-PLAN.md`'s gate was rewritten to pin the file to blob
`ad0fea79ba0d83b15e3f1990ecdf762213b8670a` against both `HEAD` and the working tree.

The audit found something more useful than a stale reference. **The original mitigation was aimed
at the wrong file and could never have worked.** The three constants T-17-14 exists to protect are
defined in `measurement_support.py:479-481`, not in `thread_revalidation.py`, which only imports
them. Freezing a file that imports a constant freezes nothing.

What actually closes the threat: `measurement_support.py` is absent from this phase's branch diff
with all three definitions intact (60.0, 3, 10800.0); the committed `14-MANIFEST.json` independently
records those literals; and `_validate_staleness_event()` still derives the confirmation window from
`STALENESS_CONFIRM_ABSENT_POLLS` and still requires a `censored` disposition for any run reaching
the cap.

One correction to amendment A8's own wording. A8 asserts "What R5 names as frozen is untouched".
That is true of the constants and slightly overstated about the rule enforcing the cap: A8 change 2
narrowed the assertion at `thread_revalidation.py:1207` from `elapsed_s > STALENESS_CAP_S` to
`elapsed_s > STALENESS_CAP_S and not is_last_poll`, permitting the final poll's measured wall-clock
time to exceed the cap. That is a narrowing of the validator rather than an extension of the cap,
it cannot convert a censored disposition into an expiry, and it sits within A8's authorisation, but
the amendment's blanket phrasing overstates it.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| ACC-17-01 | T-17-02 | The probe prints live serials, mDNS instance names, SRV hostnames and addresses to the operator's own terminal. That is the tool's diagnostic purpose: identifying which physical device is misbehaving requires naming it. The acceptance is scoped to plan 17-02, which commits no artefact, and was re-verified at audit: 17-01's three commits touch source and tests only, and the one run whose output was committed (17-03) went through 17-02's `--alias-map` redaction, the automated staged-diff backstop and a blocking operator inspection. | Operator | 2026-09-08 |

---

## Unregistered Findings

Raised by independent verification rather than declared in any SUMMARY. None is blocking; all
three are recorded so they are not rediscovered as novel.

**UF-01 (Warning) — partial substitution by substring collision on the serial path.**
`_TranscriptRedactor`'s serial pattern (`ipv6_thread_probe.py:294-296`) is a bare `re.escape()`
alternation with no boundary anchors, unlike the deliberately lookaround-bounded
`_ADDRESS_LITERAL_PATTERN`. A mapped serial inside a longer hex token is partially substituted:
`'aad073d5aa11bbbb'` becomes `'aadevice-abb'`. Reproduced against the shipped code, and matching
`17-REVIEW.md` WR-01.

Adjudicated as a separate finding rather than a reopening of T-17-04, T-17-05, T-17-21 or T-17-28.
T-17-21 and T-17-28 are scoped to the address path, which is anchored and correct. T-17-04 and
T-17-05 name different mechanisms, both of which are present and behave as declared. The
disclosure impact is bounded below the accepted baseline: a hybrid removes the mapped serial and
leaks fragments of the surrounding token, and the only class where that token is itself an
identifier is A7's firmware label, which A7 authorises committing in full.

The residual concern is evidence integrity rather than disclosure. A hybrid is neither the raw
value nor a valid pseudonym, and the automated backstop cannot see it. The only layer that catches
it is the operator inspection, which does name it: `17-03-PLAN.md` requires that no partially
substituted token is present. Both committed artefacts were checked and contain no hybrid.

**Resolved on 2026-09-09, after this audit was written.** `/gsd-code-review 17 --fix --auto --all`
ran four review passes over the phase's changed files, and the serial pattern is now anchored with a
substring-collision regression test, so the hybrid this finding describes can no longer be produced.

Two corrections to the fix followed, both worth recording because they moved in the direction this
finding cares about. The first anchoring drew its boundary at every alphanumeric, which meant a
serial adjacent to a non-hex character silently failed to substitute. That is a **miss**, and a miss
is strictly worse here than the corruption it replaced: a hybrid has the identifier removed, a miss
leaves it intact. The boundary is now hex digits and separators, chosen to prefer substituting, and
`_UNMAPPED_IDENTIFIER_PATTERN` was narrowed with it so the detector still backstops the substituter
rather than sharing its blind spot.

The register class this finding recommended is still worth carrying into any future phase that runs
the redactor, and the recommendation stands: the automated backstop cannot see a hybrid, so the
operator inspection remains the only layer that catches one.

**UF-02 (Info) — the two backstops are no longer identical, and the prose still claims they are.**
`17-03-PLAN.md`'s hostname-label test carries A7's alphanumeric boundaries; `17-04-PLAN.md`'s is
still a bare `re.search(r'[0-9a-fA-F]{12}', lab)`. `17-04-PLAN.md` states the predicate is
"deliberately identical so the two evidence artefacts are held to one standard", which stopped
being true when A7 amended only 17-03's copy. It fails closed, since 17-04's is the stricter of the
two, and it is moot for this run because neither committed file contains a `.local` token. Corrected
in the same commit as this file.

**UF-03 (Info) — placeholder threat IDs in shipped comments.** `thread_revalidation.py` carries
literal `T-17-XX change 2` and `T-17-XX change 3` markers. Traceability hygiene only; the changes
are the ones A8 authorises.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-08 | 29 | 29 | 0 | gsd-security-auditor (ASVS 1, block_on high) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-08
