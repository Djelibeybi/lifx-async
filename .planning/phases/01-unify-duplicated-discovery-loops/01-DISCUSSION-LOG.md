# Phase 1: Unify duplicated discovery loops - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 1-Unify duplicated discovery loops
**Areas discussed:** Validation hoist semantics, Dedup placement, Adjacent cleanup scope, Test strategy, IdleDeadline API shape, Deprecation mechanics, mDNS error-handling parity

---

## Validation hoist semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Debug log + skip | Mirror discover_devices' current behaviour; quiet on hostile networks | ✓ |
| Rate-limited warning + skip | First + every Nth at WARNING with running count | |
| Warning log + skip | Every rejection at WARNING; floodable | |

**User's choice:** Debug log + skip (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Unconditional | Pure DoS protection; no caller should want it off | ✓ |
| Opt-out parameter | validate_serial=True keyword, default on | |

**User's choice:** Unconditional (recommended)

---

## Dedup placement

| Option | Description | Selected |
|--------|-------------|----------|
| Shared generator | First response per serial wins; fixes find_by_label duplicate-yield | ✓ |
| Keep in discover_devices wrapper | Generator streams raw; most conservative | |
| Opt-in parameter | dedup=True keyword on the generator | |

**User's choice:** Shared generator (recommended)

---

## Adjacent cleanup scope

| Option | Description | Selected |
|--------|-------------|----------|
| IdleDeadline helper + mDNS | Extract triplicated deadline arithmetic; adopt in both loops | ✓ |
| Deprecate receive_many | DeprecationWarning now, removal next major | ✓ (after follow-up) |
| Remove receive_many outright | Breaking change without deprecation cycle | |
| None — keep phase minimal | Defer everything adjacent | |

**User's choice:** IdleDeadline helper + mDNS; then asked "Isn't receive_many used by the
extended multizone devices?" — verified live: zero production callers (definition +
test_transport.py only; multizone multi-response flows use `connection.request_stream()`).
With that confirmed, user chose **Deprecate now** for receive_many.

---

## Test strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Rewrite freely | Tests of retired internals may be deleted/rewritten if behavioural coverage preserved | ✓ |
| Adapt minimally | Keep files/structure; change only what breaks | |

**User's choice:** Rewrite freely (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, test shared generator | Prove validation + dedup where they now live | ✓ |
| Existing coverage only | Trust the shared path transitively | |

**User's choice:** Yes, test shared generator (recommended)

---

## IdleDeadline API shape

| Option | Description | Selected |
|--------|-------------|----------|
| Small class | remaining()/mark_response(), monotonic, caller-controlled idle reset | ✓ |
| Plain functions | Stateless helpers re-threading timestamps per call | |

**User's choice:** Small class (recommended)

---

## Deprecation mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| warnings.warn + docstring | DeprecationWarning, stacklevel=2, removal in v2.0 | ✓ |
| Logger warning | _LOGGER.warning on first call | |

**User's choice:** warnings.warn + docstring (recommended)

---

## mDNS error-handling parity

| Option | Description | Selected |
|--------|-------------|----------|
| Tighten to match | Catch LifxTimeoutError; network/unexpected errors handled distinctly | ✓ |
| Leave bare except | Keep swallow-everything behaviour | |

**User's choice:** Tighten to match (recommended)

## Claude's Discretion

- DEBUG log wording/format for rejected serials (house dict-style structured logs)
- Exact deprecation message text (names v2.0, points to alternatives)
- IdleDeadline internals (attribute names, monotonic call caching)
- Test placement/naming within tests/test_network/

## Deferred Ideas

- Retry-budget unification in connection.py (out of scope per ROADMAP goal)
- receive_many actual removal (v2.0, after deprecation cycle)
- Transport base-class extraction (~100 parallel scaffolding lines; revisit on next touch)
