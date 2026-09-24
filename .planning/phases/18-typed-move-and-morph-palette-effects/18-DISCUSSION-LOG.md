# Phase 18: Animator Connectivity Guard and Typed Move Effect - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md. This log preserves the alternatives considered.

**Date:** 2026-09-09
**Phase:** 18-typed-move-and-morph-palette-effects
**Areas discussed:** Exception class for the refusal, Guard placement and exclusion logging, Thread test fixture strategy, Move API internals

---

## Exception class for the refusal

| Option | Description | Selected |
|--------|-------------|----------|
| New subclass of LifxUnsupportedCommandError | Specific class; existing LifxUnsupportedCommandError and LifxError handlers keep working | ✓ |
| Reuse LifxUnsupportedCommandError as-is | No new class; indistinguishable from StateUnhandled without parsing the message | |
| Reuse LifxUnsupportedDeviceError | Docstring is about unsupported product types; discovery filters it to None | |

**User's choice:** New subclass of LifxUnsupportedCommandError

| Option | Description | Selected |
|--------|-------------|----------|
| LifxThreadAnimationError | Names the exact situation | ✓ |
| LifxUnsupportedTransportError | More general, could cover future transport-gated operations | |

**User's choice:** LifxThreadAnimationError

| Option | Description | Selected |
|--------|-------------|----------|
| Reason plus the override | Message states the boundary and names enable_thread=True | ✓ |
| Reason only | Consumer finds the override in the docs | |

**User's choice:** Reason plus the override

---

## Guard placement and exclusion logging

| Option | Description | Selected |
|--------|-------------|----------|
| One helper in the animation package | Factories call it after queries; Conductor imports it lazily in predicate form | ✓ |
| Factories share a helper, Conductor does its own check | Two places encode the rule | |
| Method on Device | Puts animation policy on the device base class | |

**User's choice:** One helper in the animation package

| Option | Description | Selected |
|--------|-------------|----------|
| Separate step after compatibility filtering | Knows whether Thread exclusion emptied the list; capability-empty path untouched | ✓ |
| Folded into _filter_compatible_lights() | One pass; raise condition needs extra bookkeeping | |

**User's choice:** Separate step after compatibility filtering

| Option | Description | Selected |
|--------|-------------|----------|
| WARNING | Visible in default log output; matches the existing no-compatible warning | ✓ |
| INFO | Quiet by default | |
| DEBUG | Matches the per-light compatibility filter entries | |

**User's choice:** WARNING

---

## Thread test fixture strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Add a Thread flag to lifx-emulator-core | Per-device option so every reply header carries thread_connection; real receive path | ✓ |
| Patch the receive path in tests | Monkeypatch header parsing or bit adoption; asserts on a patched pipeline | |
| Mock devices for the Thread cases | MagicMock with connectivity=THREAD; query-then-guard ordering never exercised | |

**User's choice:** Add a Thread flag to lifx-emulator-core
**Notes:** Flipping the private bit is undone by the emulator's clear-bit replies to the factories' own queries, which is what made the emulator change necessary rather than convenient.

| Option | Description | Selected |
|--------|-------------|----------|
| Emulator change lands first, blocking prerequisite | Ship and release the emulator change, bump the pin, then execute | ✓ |
| Interim patch, swap to the emulator later | Two rounds of test work | |

**User's choice:** Emulator change lands first, blocking prerequisite

| Option | Description | Selected |
|--------|-------------|----------|
| Mocks for exclusion, emulator for no-traffic proof | Existing MagicMock fixtures gain connectivity; one emulator test proves no packets to an excluded participant | ✓ |
| Emulator for everything | Slower; needs the emulator flag for all Conductor tests | |

**User's choice:** Mocks for exclusion, emulator for no-traffic proof

---

## Move API internals

| Option | Description | Selected |
|--------|-------------|----------|
| Shared private helper, setter adopts it too | One _coerce_direction() for move(), set_move_effect() and the direction setter | ✓ |
| Helper used by move() only, setter stays enum-only | Two rules for the same field | |

**User's choice:** Shared private helper, setter adopts it too

| Option | Description | Selected |
|--------|-------------|----------|
| Thin delegate with its own docstring example | set_effect(MultiZoneEffect.move(...)); docstring carries the runnable example | ✓ |
| Own validation and packet build | Duplicates conversion logic | |

**User's choice:** Thin delegate with its own docstring example

| Option | Description | Selected |
|--------|-------------|----------|
| Short sections in animation.md and effects.md | Thread notes under "When to Use Animation" and "Conductor"; a Firmware Move example in effects.md | ✓ |
| Docstrings and migration guide only | No user-guide prose this phase | |

**User's choice:** Short sections in animation.md and effects.md

---

## Claude's Discretion

- Guard helper name and module; predicate versus caught exception in the Conductor
- Location of the uint32 / uint64 bounds for converted speed and duration
- Test file layout for the new emulator-backed Thread tests
- Wording of the user-guide notes and the migration-guide rewrite

## Deferred Ideas

- Gate get_wifi_info() and get_wifi_firmware() on Thread and add Thread RSSI once LIFX ships the replacement packets
