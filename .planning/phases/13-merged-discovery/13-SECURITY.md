---
phase: 13-merged-discovery
status: secured
asvs_level: 1
threats_closed: 32
threats_open: 0
audited: 2026-08-31
implementation_revision: 39bad58c42627ac3612868503bb5fb9305b04cc3
---

# Phase 13 Security Verification

## Verdict

**SECURED.** All 32 registered Phase 13 threats are closed. The final production
implementation is `39bad58c42627ac3612868503bb5fb9305b04cc3`; no production source,
measurement-script, or CI-workflow differences exist between that revision and
the audited head.

The final-revision evidence gate passes with one paired hermetic emulator run and
six paired representative fleet rounds stamped with that production revision.
The pre-reword 224,312-byte canonical evidence prefix is unchanged.
Phase-specific measurement logic remains absent from the permanent CI workflow.

## Threat Disposition

The independent auditor verified the implemented mitigations for:

- UDP and mDNS identity, endpoint, packet, serial, and response correlation;
- bounded parser, candidate, worker, queue, task, socket, thread, and shutdown
  lifecycles;
- exact caller deadlines, cancellation propagation, deterministic reaping, and
  post-fork reset;
- expected-failure isolation and fail-fast unexpected-error propagation;
- concrete route-selected IPv4 mDNS binding with matching multicast-interface
  selection, an ephemeral legacy-unicast reply port, and no all-interface
  listener;
- alias-only append-before-validate measurement evidence, private external
  mapping, and ignored mode-0600 operator handoff;
- immutable revision stamping, append-only canonical evidence, deterministic
  summary generation, and removal of Phase-specific CI measurement logic.

T-13-32, the all-interface mDNS reply-listener exposure reported by GitHub code
scanning alert 18, is mitigated by binding the live unconnected socket to the
concrete IPv4 source selected for the mDNS route and pinning multicast egress to
that same interface. Fail-closed selector, descriptor cleanup, exact bind,
direct-reply, and cancellation tests passed. Bandit, CodeQL, and the independent
post-patch bypass review found no remaining wildcard bind; GitHub records alert
18 as fixed. No unregistered threat flags remain.

## Accepted Risks

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---|---|---|---|---|
| AR-13-01 | T-13-08 | The process-local coordinator crosses asyncio loop and thread ownership boundaries but no authentication or operating-system privilege boundary. Residual lifecycle misuse is constrained by thread-safe scheduling, caller-owned queues, idempotent detach, bounded shutdown, post-fork reset and cross-loop lifecycle tests. | Phase 13 plan authority | 2026-08-31 |
| AR-13-02 | T-13-20 | Dual-source serial lookup introduces no new diagnostic surface and reuses the tested merged-discovery failure policy: expected network failures are value-suppressed and isolated, while unexpected programming errors propagate only after owned work is reaped. | Phase 13 plan authority | 2026-08-31 |

## Evidence Integrity

- Final-revision validation passed for the production implementation revision.
- The current revision contains 14 evidence rows: one emulator pair and six
  fleet pairs.
- Repeated summary generation was byte-identical.
- The pre-restamp 282,350-byte canonical prefix retained SHA-256
  `db10fa2387b858a55a8e06c0cafed49a667b9d7e07dacbcd3d007e84653eb59d`.
- The regenerated summary has SHA-256
  `d0aa02d57348ad65b6b4a9148cd74477d81c265efc259b14fff044bccadea9e2`.
- No raw identifiers, mapping contents, addresses, hostnames, packets, or
  exception text are present in tracked evidence.

_Auditors: GSD security auditor; post-fix independent security regression reviewer_
