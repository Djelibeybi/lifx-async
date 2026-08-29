# Phase 11 Privacy Remediation

## Scope

- Repository: `lifx-async`
- Branch: `gsd/phase-11-mdns-hardening`
- Finding location: `.planning/STATE.md:105`
- Candidate categories: `ipv6`, `serial-12hex`
- Current file: sanitised
- External mapping accessed: no

This record implements the identifier-free evidence boundary in D-09 and SPEC
Prohibition P7. It records location, category, scope, and disposition only.

## Current-file remediation

The complete operational line at the finding location was replaced through a
non-echoing in-memory edit. The replacement records that Thread hardware endpoint
values remain operator-controlled evidence outside the repository and must be
re-derived before Phase 14 validation.

## Staged/diff scope

Task 2 covers only the current `.planning/STATE.md` file, this remediation record,
and their staged diff. Every scanner result in that scope must be classified before
commit; an incomplete scan or any live or unresolved candidate blocks the commit.

## History scope

History is not remediated or authorised by this plan. Any history decision or
remediation is routed separately to Plan 11-08. This record makes no claim about
pre-existing commits, non-current-branch refs, pushed history, or operator privacy
attestation.

## Guidance-draft classification

The current guidance files were inspected through the value-suppressed scanner. Findings
were classified only by file, category, count, and disposition:

- `11-RESEARCH.md`: five `ipv6` candidate lines; four are standards-defined protocol
  range references and one is a classifier-syntax false positive.
- `11-PATTERNS.md`: one `ipv6` protocol-range reference, three `serial-12hex` synthetic
  fixture lines, four `ipv4` documentation-range fixture lines, one `ipv4` loopback
  fixture line, and one `mdns-hostname` synthetic fixture line.
- `11-SOURCE-AUDIT.md`: no candidate line.

No live or unresolved candidate was identified in these current files. This classification
does not inspect or attest the external mapping, branch history, non-current refs, or
physical device identity.

## History reachability audit

This audit was captured after a successful read-only refresh of every ref exposed by
`origin`. Remote heads were refreshed in the ordinary remote-tracking namespace, while
all exposed heads, tags, and pull refs were mirrored into an observation-only
remote-tracking namespace. No merge, rebase, checkout, push, pruning, local branch or tag
update, worktree change, reflog expiry, garbage collection, or external mapping access
occurred.

### Decision fields

- repository: `/Volumes/External/Developer/Djelibeybi/lifx-async`
- branch: `gsd/phase-11-mdns-hardening`
- head_before_rewrite: `00537992023540ec2b50b5cdb59c4a63a35741fe`
- origin_main: `70076e4bf87d46d6f1eb05e0bcbea98f6009ef83`
- merge_base: `70076e4bf87d46d6f1eb05e0bcbea98f6009ef83`
- unpushed_range: `70076e4bf87d46d6f1eb05e0bcbea98f6009ef83..00537992023540ec2b50b5cdb59c4a63a35741fe`
- unpushed_commit_count: 61
- upstream: none
- remote_refresh: success
- remote_refresh_scope: 4 heads, 86 tags, and 196 pull refs
- remote_reachability: shared baseline reaches refreshed origin main and tag; phase commits reach no refreshed remote ref
- worktree_reachability: one current worktree only; no other worktree contains a target phase commit
- category: ipv6
- baseline_candidates: 2 target-scope lines in `.planning/STATE.md`
- baseline_live_count: 0
- baseline_approved_pseudonym_count: 1
- baseline_unresolved_count: 0
- phase_owned_candidates: 2 target-scope patch dispositions, one safe relocation and one removal-only remediation
- phase_owned_unresolved_count: 0
- earliest_affected_commit: none
- affected_commit_parent: none
- affected_commit_count: 0
- affected_range: none
- rewrite_required: false
- shared_status: clear
- local_only: false
- rewrite_eligible: false
- preserved_authority_in_affected_range: none
- escalation_reason: none

The absence of an upstream is not used as evidence of local-only status. There is no
phase-owned live or unresolved candidate requiring a current-branch rewrite. The
operator confirmed that baseline-2 is an approved stable pseudonym: its serial prefix is
deliberately outside the real LIFX prefix and its OMR prefix is fabricated. The values and
the private mapping were neither inspected nor repeated. Shared reachability therefore
does not create a live-identifier exposure, and the `no-rewrite` disposition is supported.

### Operator attestation

On 2026-08-29, the operator confirmed baseline-2 is intentionally anonymised and does
not exist in real hardware or infrastructure. This attestation classifies the candidate
without recording its value, a value hash, the private mapping, or a physical identity.

### Target candidate classification

The scanner found two target-scope candidate identities in the merge-base
`.planning/STATE.md` snapshot. Equality was checked locally without printing, hashing, or
persisting either value.

| Candidate | Merge-base location | category | Classification | Phase direction | Current disposition |
|---|---|---|---|---|---|
| baseline-1 | `.planning/STATE.md:97` | ipv6 | Clearly safe loopback fixture | Commit `70d300d7ca3b00e967213a0c8eedb019cfbf23f9` relocated the exact candidate from `STATE.md` to `STATE-ARCHIVE.md` | Present only as the same safe loopback fixture in `.planning/STATE-ARCHIVE.md:18` |
| baseline-2 | `.planning/STATE.md:117` | ipv6 and serial-12hex | Operator-confirmed approved stable pseudonym with a deliberately non-LIFX serial prefix and fabricated OMR prefix | Commit `416259eb9e821023cf8a511b3b2407ea5f7d3ea3` removed the exact inherited candidate; no phase commit added it | Absent from current `STATE.md`; safely retained only in shared historical objects as pseudonymised evidence |

The category-only patch hint at
`70d300d7ca3b00e967213a0c8eedb019cfbf23f9` is therefore not baseline-2. It is
baseline-1, a loopback fixture, and the patch is an exact relocation rather than an
identifier addition. Baseline-2 is the distinct approved pseudonym removed later by
`416259eb9e821023cf8a511b3b2407ea5f7d3ea3`.

### Snapshot scans

All streams passed through the value-suppressed scanner. The broad counts below are
mechanical snapshot context, not a claim that every pre-existing repository fixture was
re-adjudicated by this target audit.

| Snapshot | Revision | Scope | Result |
|---|---|---|---|
| Merge base | `70076e4bf87d46d6f1eb05e0bcbea98f6009ef83` | Entire tracked tree | Complete; 262 candidate-bearing files and 3,172 candidate-bearing lines across email, IPv4, IPv6, MAC, mDNS hostname, serial, tooling-path, and UUID categories |
| Merge base | `70076e4bf87d46d6f1eb05e0bcbea98f6009ef83` | `.planning/STATE.md` | Two lines: baseline-1 safe loopback and baseline-2 operator-confirmed approved pseudonym |
| Pre-relocation | parent of `70d300d7ca3b00e967213a0c8eedb019cfbf23f9` | `.planning/STATE.md` | Same two exact baseline identities |
| Post-relocation | `70d300d7ca3b00e967213a0c8eedb019cfbf23f9` | `STATE.md` plus `STATE-ARCHIVE.md` | Baseline-1 moved to the archive; baseline-2 remained in `STATE.md` |
| Pre-remediation | parent of `416259eb9e821023cf8a511b3b2407ea5f7d3ea3` | `.planning/STATE.md` | Baseline-2 still present |
| Post-remediation | `416259eb9e821023cf8a511b3b2407ea5f7d3ea3` | `.planning/STATE.md` | Clean |
| Current head | `00537992023540ec2b50b5cdb59c4a63a35741fe` | Entire tracked tree | Complete; 271 candidate-bearing files and 3,410 candidate-bearing lines across the same broad categories |
| Current head | `00537992023540ec2b50b5cdb59c4a63a35741fe` | `.planning/STATE.md` | Clean |
| Current head | `00537992023540ec2b50b5cdb59c4a63a35741fe` | `.planning/STATE-ARCHIVE.md` | Baseline-1 safe loopback fixture only |

### Phase patch scan

Every candidate-bearing changed line in the merge-base-to-head range was scanned by
commit, repository-relative path, direction, and category with diff metadata suppressed.
Unchanged diff context was excluded. The classifications below consolidate only entries
with the same evidence disposition; every candidate-bearing commit is named.

| Commits | Locations and directions | Categories | Classification |
|---|---|---|---|
| `97767ddfe032bd4fc3d592240f92b5d2daa674bf` | `11-RESEARCH.md`, added | ipv6 | Standards-defined protocol ranges and one scanner-syntax false positive |
| `6e65626d98bb5b430a8d4649ca4ac5583550ebbb` | Plans 11-01 through 11-05 and `11-PATTERNS.md`, added | ipv4, ipv6, mDNS hostname, serial, tooling-path | Framework references plus synthetic, documentation-range, loopback, and protocol fixtures |
| `56c2751b3a57b8ba3b01bf90176fc43c46b05264`, `5488ece2205702912ce9ff8feaf16f87b246d68c`, `8ae4918a4b63d299d5216a19f51ff9550fd8ac72` | Phase plans, added and removed | ipv6, tooling-path | Protocol-range edits and framework references; no live identity introduced |
| `aa55a3456cea64dcde1e561ee0505a0cc9edc6b3`, `d6be5e50e9e6cee58447d0bdd95d58a3ef18f921` | `11-REVIEWS.md`, added then removed | ipv4, ipv6 | Synthetic and protocol fixture narration |
| `fac3429c4bad9e49a17b26dbdfd2d0439cec6e04`, `81777177186018a1e20d95e0751f8ce9be88838f`, `562821f798518e6a3c33ca4ad62c4a7f89fcf312` | mDNS, API, device, and transport tests, added or replaced | ipv4, mDNS hostname, serial | Synthetic, documentation-range, wildcard, and loopback fixtures |
| `70d300d7ca3b00e967213a0c8eedb019cfbf23f9` | `.planning/STATE.md`, removed; `.planning/STATE-ARCHIVE.md`, added | ipv6 | Exact relocation of baseline-1, the safe loopback fixture; not baseline-2 |
| `abc5b5ae520645d31b7564d6c1c109865ddd8ba2`, `4dda1b6b3777eceba3afd044fe757ec35041418a` | mDNS implementation, discovery tests, and probe tests, added or replaced | ipv4, ipv6, mDNS hostname, serial | Standards-defined protocol constants plus synthetic, documentation-range, multicast, wildcard, and loopback fixtures |
| `9b18d25367b3c7bd0c963a94d2b95fa5c9741fd8`, `1d3a346f8b24bf5f13b69fde81faeec9e12e2837`, `8af49d933538d01c4b7629c5b1d565fb506681f4`, `d7411b83c8014e6e3d34a35a9b468aa5230edd67` | mDNS discovery tests, added or replaced | ipv4, ipv6, MAC, mDNS hostname, serial | Synthetic and reserved test fixtures |
| `22b97d65c415be9d971148c8baedc27641c40dea`, `964c507c76086606e857954768aad218c19a3e82`, `c2811a1ed11bb450fc11ca8af75467e8d04823df` | API implementation and mDNS discovery tests, added, removed, or replaced | ipv4, ipv6, mDNS hostname, serial | Synthetic, reserved, wildcard, and loopback fixtures |
| `b69820f52ebc93350d7694c293699d32e0e6dbde`, `3836ca25c7c358828f83ab66ebd818e10e110a9b`, `8f29f8649ebb9b881d925359d1e12cfc9878648f` | API, mDNS discovery, and transport tests, added or replaced | ipv4, ipv6, mDNS hostname, serial | Synthetic, documentation-range, multicast, wildcard, and loopback fixtures |
| `a0c7853d9179dffbf76c65da089f6fd0b18da9f1`, `4fcf7aa6d257e65e3674be9da14f0bff2c5f256c` | mDNS discovery tests, added or replaced | ipv4, ipv6, mDNS hostname, serial | Synthetic and reserved bounds/error fixtures |
| `73b041e8774ad4c213446f6ae04269e80966ace8`, `3119f731e58f2972a305edec6d769b8647c0703a` | `11-07-PLAN.md`, added then removed | tooling-path | Framework execution references; no candidate value retained in the current plan |
| `416259eb9e821023cf8a511b3b2407ea5f7d3ea3` | `.planning/STATE.md`, removed | ipv6, serial | Removal-only edit of exact inherited approved pseudonym baseline-2; no replacement candidate |
| `571febd7913dedd28832bbbbd2a0b8362c85506d` | `11-RESEARCH.md`, added and removed | ipv6 | Protocol-range guidance edit |

No candidate-bearing patch scan was incomplete. The phase patch population contains no
phase-introduced live or unresolved value. Baseline-2 is an operator-confirmed approved
pseudonym, and its removal-only edit did not introduce a replacement candidate.

### Ref, tag, and worktree reachability

The refreshed graph establishes the following complete target disposition:

- Local branches present: `archive/task-2-replay`, `feat/mirror-light`, `gh-pages`,
  `gsd/phase-11-mdns-hardening`, `main`, and `renovate/lock-file-maintenance`.
- Refreshed remote heads present: `feat/mirror-light`, `gh-pages`, `main`, and
  `renovate/lock-file-maintenance`.
- The shared baseline commit is reachable from refreshed `origin/main`, refreshed remote
  tag `v6.6.1`, and the corresponding local tag. It is not reachable from a refreshed
  pull ref.
- Commit `70d300d7ca3b00e967213a0c8eedb019cfbf23f9` and removal commit
  `416259eb9e821023cf8a511b3b2407ea5f7d3ea3` are reachable only from the current local
  branch and current worktree. Neither is reachable from any refreshed remote head, tag,
  pull ref, another local branch, local tag, or another worktree.
- Exactly one worktree exists: this repository root, attached to
  `gsd/phase-11-mdns-hardening` at the audited head.
- The successful refresh observed 86 remote tags and 196 pull refs. The containment
  checks covered all of them, not only the current branch's configured fetch refspec.

Remote reachability proves that the phase commits are unshared. Baseline-2 remains
reachable from the shared baseline and its tag, but its operator-confirmed pseudonym
status means that reachability creates no live-identifier exposure and requires no
history rewrite.

### Preserved authority and rewrite boundary

- preserved authority commit D-15: `cd0c3aceb35c724a79df2598b3bd9fe083436800`
- preserved authority commit D-16: `f7c7c6f096da8a6102e37a83c57011c7240e37fa`
- exact object preservation: required; neither object was changed by this audit
- affected rewrite range: none, because no phase-owned live or unresolved candidate was
  introduced
- preserved_authority_in_affected_range: none

`rewrite_eligible` remains false because `rewrite_required` is false and there is no
affected current-branch range. The supported disposition is `no-rewrite`; no shared or
local history mutation is necessary.

An authorised rewrite in a later plan could leave old objects reachable from local
reflogs or object storage. Plan 11-09 is not authorised to expire reflogs or run garbage
collection. That observation grants no rewrite authority here.

## Final history disposition result

The operator-approved disposition was applied at a distinct history boundary before this
ledger evidence was added. All fields below are limited to Git object identifiers,
category/location/direction/disposition evidence, and invariant outcomes.

### Disposition boundary

- selected_disposition: no-rewrite
- current_branch: `gsd/phase-11-mdns-hardening`
- merge_base: `70076e4bf87d46d6f1eb05e0bcbea98f6009ef83`
- disposition_boundary_head_before: `f1e26d5a55f28b4d98cba5fb57bf280a74ddffae`
- disposition_boundary_head_after: `f1e26d5a55f28b4d98cba5fb57bf280a74ddffae`
- disposition_boundary_tree_before: `f5396e51f8b57068fdf7de2f36423c56b5c3acdb`
- disposition_boundary_tree_after: `f5396e51f8b57068fdf7de2f36423c56b5c3acdb`
- disposition_tree_equal: true
- pre_existing_identity_range: `70076e4bf87d46d6f1eb05e0bcbea98f6009ef83..f1e26d5a55f28b4d98cba5fb57bf280a74ddffae`
- pre_existing_identity_count: 64
- complete_pre_existing_commit_id_sequence_equal: true
- ordered_author_date_subject_digest_equal: true
- disposition_commit_count_equal: true
- disposition_signature_result: verified
- disposition_dco_result: verified
- disposition_ref_result: unchanged
- affected_range: none
- affected_commit_count: 0
- preserved_authority_d15: `cd0c3aceb35c724a79df2598b3bd9fe083436800`
- preserved_authority_d16: `f7c7c6f096da8a6102e37a83c57011c7240e37fa`
- preserved_authority_exact_and_ancestor: true
- safety_ref_created: false
- rewrite_performed: false
- push_performed: false
- garbage_collection_performed: false
- reflog_expiry_performed: false
- external_mapping_accessed: false
- evidence_commit: this ledger's separate post-boundary signed commit; its exact Git
  object identifier is recorded in `11-09-SUMMARY.md` after commit creation

The complete ordered 64-commit identity sequence, its count, the boundary tree, the
non-sensitive ordered authorship/date/subject digest, and the observed refs remained
unchanged through the no-rewrite boundary. The later evidence commit is intentionally not
part of those equality claims. No history rewrite created unreachable replacement objects;
ordinary local object and reflog retention was not altered.

### Final bounded privacy classification

- audited_state_scope: `.planning/STATE.md` at the merge base, disposition boundary,
  current working file, diffs, and the complete confirmed unpushed STATE patch stream
- baseline_candidate_count: 2
- baseline_live_count: 0
- baseline_approved_pseudonym_count: 1
- baseline_unresolved_count: 0
- phase_owned_candidate_dispositions: one exact safe-fixture relocation and one
  removal-only approved-pseudonym remediation
- phase_owned_live_count: 0
- phase_owned_unresolved_count: 0
- claim: zero live or unresolved phase-owned candidate in the audited STATE scope
- inherited_baseline_disposition: one clearly safe loopback fixture and one
  operator-confirmed approved stable pseudonym
- inherited_shared_history_action: none required

The inherited baseline findings remain separately dispositioned. This result does not
claim whole-repository privacy provenance, inspect the external mapping, identify physical
hardware, or attest any evidence population outside the declared STATE and ledger scope.

### Fresh final-head gates

- current_state_scan: complete; no candidate line
- remediation_ledger_scan: complete; no candidate line
- unstaged_diff_scan: complete; no candidate line
- staged_ledger_scan: complete; no candidate line
- staged_binary_diff_scan: complete; no candidate line
- merge_base_state_snapshot_scan: complete; two inherited baseline candidate lines,
  separately classified above as one clearly safe loopback fixture and one
  operator-confirmed approved pseudonym
- boundary_head_state_snapshot_scan: complete; no candidate line
- complete_unpushed_state_patch_scan: complete; two removal-direction candidate lines,
  separately classified above as the safe-fixture relocation and approved-pseudonym
  remediation; no added candidate line
- d15_d16_exact_assertion: passed; exact address ceilings 256 and 1,024
- d15_d16_focused_regressions: 3 passed
- phase_11_focused_regressions: 413 passed with `ResourceWarning` treated as an error
- complete_frozen_suite: 3,871 passed, 12 deselected, 7 existing deprecation warnings
- ruff_check: passed
- ruff_format_check: passed; 261 files already formatted
- strict_pyright: passed; 0 errors, 0 warnings, 0 information messages
- diff_check: passed

These results are fresh for the disposition boundary and the later evidence-only ledger
diff. They do not relabel the historical `11-VERIFICATION.md` result, which remains
`gaps_found` until independent Phase 11 re-verification.
