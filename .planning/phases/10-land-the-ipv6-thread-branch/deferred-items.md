# Phase 10: Deferred Items

Out-of-scope discoveries logged during execution. Each names why it was not fixed
where it was found.

## `src/lifx/network/mdns/dns.py` — em dash in `build_address_query()` docstring

**Found during:** plan 10-03, Task 4
**Line:** 367, `"...included in the service response — e.g. when a Thread border router's..."`

The project's standing prose rule is no em dashes (recast the sentence instead). This one
arrived with the rebased branch commits, not with any Phase 10 fix.

**Why it was not fixed here.** Plan 10-03 Task 4 is explicitly a test-only commit
("Change no source file in this task... that is a finding, not a licence"), and its
acceptance criteria require `git diff HEAD~1 --name-only` to list only files under
`tests/`. B4's docstring scope is `network/mdns/transport.py` alone, so this line is not
in any Task 1 to 3 commit either.

**Suggested owner:** Phase 11, which owns the mDNS documentation pass (MDNS-08).
