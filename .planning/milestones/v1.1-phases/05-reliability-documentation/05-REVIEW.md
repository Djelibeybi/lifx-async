---
phase: 05-reliability-documentation
reviewed: 2026-07-17T03:13:38Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - docs/api/animation.md
  - docs/architecture/overview.md
  - docs/faq.md
  - docs/user-guide/advanced-usage.md
  - docs/user-guide/animation.md
  - docs/user-guide/ceiling-lights.md
  - docs/user-guide/troubleshooting.md
  - src/lifx/api.py
  - CLAUDE.md
findings:
  critical: 3
  warning: 8
  info: 5
  total: 16
status: issues_found
---

# Phase 5: Code Review Report (re-review after gap closure)

**Reviewed:** 2026-07-17T03:13:38Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

All six previously closed findings were independently re-verified against the shipped source and **all six are genuinely fixed**:

1. **Version pins** — no `Since v*` / version attribution of wire-reliability behaviour anywhere in the reviewed files (grep for `since v[0-9]`, `in v[0-9]`, `v1.1` across all nine files: zero hits). ✅
2. **CLAUDE.md idle timeout** — now reads "~4 seconds (max_response_time × idle_timeout_multiplier)", matching `MAX_RESPONSE_TIME = 1.0` × `IDLE_TIMEOUT_MULTIPLIER = 4.0` (`src/lifx/const.py:31,34`); overall default corrected to 15.0 matching `DISCOVERY_TIMEOUT` (`const.py:28`). ✅
3. **`discover()` docstring** — now "default 15.0" (`src/lifx/api.py:758`), consistent with `discover_mdns()` (`api.py:814`) and `DISCOVERY_TIMEOUT`. ✅
4. **FPS claim** — `docs/api/animation.md:5` now "up to ~20 FPS", consistent with the animation guide and CLAUDE.md. ✅
5. **overview.md layer numbering** — prose sections Layer 1–8 match the mermaid diagram's Layer 1–8 subgraph labels. ✅
6. **Code examples runnable** — **NOT fully closed.** Multiple examples in scope still cannot run as shown, and the gap-closure edit itself introduced one new broken example (CR-01). Details below.

However, this review found **3 Critical, 8 Warning, 5 Info** issues that remain in the reviewed files, including one regression introduced by plan 05-04 and a factual concurrency-model claim repeated in three files that contradicts the shipped source.

All animation-layer claims verified against source: `AnimatorStats.gated` / `.acks_outstanding` / `.packets_sent` exist (`src/lifx/animation/animator.py:80-83`), `animation/flow.py` exists, `Animator.for_matrix`/`for_multizone`/`send_frame`/`close`/`canvas_width`/`canvas_height`/`pixel_count` all exist, `set_extended_color_zones(..., fast=True)` exists (`src/lifx/devices/multizone.py:591-598`), and all mkdocstrings identifiers in `docs/api/animation.md` resolve. HSBK dual-format discipline is respected throughout (protocol examples use `LightHsbk` uint16, user-facing examples use float `HSBK`).

## Critical Issues

### CR-01: `discover_devices()` awaited as a coroutine — examples raise TypeError (one instance newly introduced by the gap-closure fix)

**File:** `docs/user-guide/troubleshooting.md:27`, `docs/user-guide/troubleshooting.md:70-84`, `docs/user-guide/troubleshooting.md:110`
**Issue:** `discover_devices()` is an async generator (`src/lifx/network/discovery.py:477-485`, returns `AsyncGenerator[DiscoveredDevice, None]`). All three examples do `devices = await discover_devices(...)` and then call `len(devices)` / iterate the result. `await` on an async generator raises `TypeError: object async_generator can't be used in 'await' expression` — none of these examples can run.

Note: the instance at line 110 was **introduced by the 05-04 gap-closure diff itself** (it replaced the old `thorough_discovery()` multi-pass example). Lines 27 and 70-84 are pre-existing but in scope.
**Fix:**
```python
from lifx.network.discovery import discover_devices

devices = []
async for device in discover_devices(timeout=30.0):
    devices.append(device)
print(f"Found {len(devices)} devices")
```
Apply the same `async for` collection pattern to the `diagnose_discovery()` example (lines 62-87), including the `if not devices:` branch which works unchanged once `devices` is a list.

### CR-02: ceiling-lights.md "MatrixLight Compatibility" example uses three APIs that do not exist

**File:** `docs/user-guide/ceiling-lights.md:259-273`
**Issue:** The example is triply broken against shipped source:
1. `await ceiling.get_tile_chain()` — no such method. The real method is `get_device_chain()` (`src/lifx/devices/matrix.py:378`). Nothing named `get_tile_chain` exists anywhere in `src/lifx/`.
2. `from lifx.protocol.protocol_types import TileEffectType` — ImportError. The protocol generator explicitly removes `TileEffectType` and merges it into `FirmwareEffect` (`src/lifx/protocol/generator.py:302-338`).
3. `await ceiling.set_tile_effect(effect_type=..., speed=5000)` — no such method. The real method is `set_effect()` (`src/lifx/devices/matrix.py:926`), and its `speed` parameter is **seconds** (`float`, default 3.0), so `speed=5000` would also be wrong by three orders of magnitude if translated literally.

**Fix:**
```python
from lifx.protocol.protocol_types import FirmwareEffect

async with await CeilingLight.from_ip("192.168.1.100") as ceiling:
    all_colors = await ceiling.get_all_tile_colors()
    device_chain = await ceiling.get_device_chain()

    await ceiling.set_matrix_colors(0, colors)

    await ceiling.set_effect(
        effect_type=FirmwareEffect.MORPH,
        speed=5.0,  # seconds
    )
```

### CR-03: "Request serialization" concurrency claims contradict the shipped source (and each other) in three reviewed files

**File:** `docs/faq.md:199`, `docs/user-guide/advanced-usage.md:229`, `CLAUDE.md` (Concurrency Considerations section)
**Issue:** Three in-scope files claim requests on a single connection are serialised:
- `faq.md:199`: "**Request Serialization**: Prevents response mixing on same connection"
- `advanced-usage.md:229`: "Requests are serialized to prevent response mixing"
- `CLAUDE.md`: "Requests on a single connection are serialized via `_request_lock` (asyncio.Lock) to prevent response mixing on the same UDP socket"

This is factually wrong per the shipped source: **no `_request_lock` exists anywhere in `src/lifx/network/connection.py`** (grep: zero hits; the only lock discussion is a comment explaining why a *poll loop* is used instead of a Lock for `open()`, lines 125-129). The actual model is a background receiver task routing responses to per-request `asyncio.Queue`s keyed by `(source, sequence, serial)` (`connection.py:147-152, 200-201`) — concurrent requests are supported and response mixing is prevented by *correlation*, not serialisation.

Worse, `advanced-usage.md` **contradicts itself within the same file**: line 229 says requests are serialised, while lines 241-253 demonstrate `asyncio.gather()` on one device and state "Concurrent requests execute with maximum parallelism". `docs/architecture/overview.md`'s Concurrency Model section (lines 392-412) describes the receiver-task model correctly — these two stale claims plus CLAUDE.md contradict it.
**Fix:**
- `faq.md:199`: replace with "**Response Correlation**: Per-request response routing prevents response mixing on the same connection".
- `advanced-usage.md:229`: replace "Requests are serialized to prevent response mixing" with "Concurrent requests are correlated by sequence number, so responses never mix".
- `CLAUDE.md`: rewrite the first Concurrency Considerations bullet to describe the background receiver + per-request queue model (as overview.md already does) and delete the `_request_lock` reference.
- (Out of scope but same root cause: `src/lifx/network/connection.py:64` class docstring contains the identical stale line "Request serialization to prevent response mixing" — flag for follow-up.)

## Warnings

### WR-01: `Colors.WARM_WHITE` in `filter_by_group` docstring example does not exist

**File:** `src/lifx/api.py:620`
**Issue:** The docstring example ends with `await bedroom.set_color(Colors.WARM_WHITE)`. There is no `WARM_WHITE` preset in `src/lifx/color.py` (grep: the only usage in the whole repo is this docstring). Running the example raises `AttributeError`. Docstring examples surface verbatim in the rendered API docs.
**Fix:** Use an existing preset, e.g. `Colors.WARM` (`color.py:873`).

### WR-02: `_fetch_location_metadata`/`_fetch_group_metadata` docstrings promise graceful failure handling that does not exist

**File:** `src/lifx/api.py:260-267, 273-279, 313-319, 325-331`
**Issue:** Both docstrings claim "Logs warnings for failed queries but continues gracefully." Neither is true:
1. There is no logger in this module and nothing is logged.
2. `asyncio.gather()` is called **without** `return_exceptions=True`; `Device.get_location()`/`get_group()` return `CollectionInfo` and *raise* on failure (`src/lifx/devices/base.py:1171, 1365` — Raises: `LifxTimeoutError`, etc.), so one offline device aborts the entire `organize_by_location()`/`organize_by_group()` call.
3. The `CollectionInfo | None` annotations and `if location_info is None: continue` branches (lines 277-279, 284-285, 329-331, 335-336) are dead code that masks the mismatch.

**Fix:** Either implement the promise — `results = await asyncio.gather(*coros, return_exceptions=True)`, skip-and-log exceptions via a module logger — or correct the docstrings to state that a failing device propagates its exception.

### WR-03: `find_by_label(exact_match=True)` docstring says "yield at most one device" but the loop yields every exact match

**File:** `src/lifx/api.py:974-976, 996-999, 1013-1016`
**Issue:** The docstring ("If True, match label exactly and yield at most one device"), the inline comment ("Exact match - return first match only"), and the example comment ("exact_match yields at most one device") all claim single-yield semantics, but the generator has no `return`/`break` after yielding an exact match. LIFX labels are not unique — two bulbs named "Bedroom" both match, and both are yielded.
**Fix:** Add `return` after `yield device` when `exact_match` is true, or correct the docstring/comments to say all exact-label matches are yielded.

### WR-04: `organize_by_location`/`organize_by_group` ignore `include_unassigned` when the cache is warm

**File:** `src/lifx/api.py:515-523, 549-557`
**Issue:** The result cache is keyed only on `self._locations_cache is None`, not on the `include_unassigned` argument. Call sequence: `filter_by_location(...)` internally calls `organize_by_location(include_unassigned=False)` and populates the cache; a subsequent user call `organize_by_location(include_unassigned=True)` silently returns the cached dict **without** the "Unassigned" group. Same defect for groups.
**Fix:** Cache per flag value (e.g. `dict[bool, dict[str, DeviceGroup]]`), or rebuild when the requested flag differs from the cached one.

### WR-05: `measure_latency` example uses `asyncio.gather` without importing `asyncio`

**File:** `docs/user-guide/troubleshooting.md:239-261`
**Issue:** The example presents itself as complete (it imports `time` and `Light`) but uses `asyncio.gather(...)` at line 259 without `import asyncio` — `NameError` at runtime.
**Fix:** Add `import asyncio` to the example's imports.

### WR-06: `best_effort_control` example uses `Colors` without importing it

**File:** `docs/user-guide/advanced-usage.md:338-351`
**Issue:** The example imports `discover, DeviceGroup, LifxError` but calls `light.set_color(Colors.GREEN)` — `NameError` at runtime for an example that otherwise presents complete imports.
**Fix:** `from lifx import discover, DeviceGroup, Colors, LifxError`.

### WR-07: `wave_effect` example fires tasks and returns immediately — the effect never runs under `asyncio.run()`

**File:** `docs/user-guide/advanced-usage.md:456-471`
**Issue:** `asyncio.create_task(delayed_color_change(...))` results are discarded and `wave_effect()` returns without awaiting them. Run as shown (`asyncio.run(wave_effect())`), the event loop closes before any `delayed_color_change` sleep completes, so no colour changes happen; the unreferenced tasks are also eligible for garbage collection mid-flight (documented CPython pitfall). The example teaches a fire-and-forget anti-pattern in a guide whose sibling sections explicitly warn against reimplementing delivery patterns.
**Fix:**
```python
async def wave_effect():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    async with asyncio.TaskGroup() as tg:
        for i, device in enumerate(group.devices):
            tg.create_task(delayed_color_change(device, Colors.BLUE, delay=i * 0.3))
```
(or collect the tasks and `await asyncio.gather(*tasks)`).

### WR-08: overview.md characterises the retransmit strategy as "exponential backoff" — the source uses Photons-shaped escalating gaps

**File:** `docs/architecture/overview.md:150`
**Issue:** "Retry Logic: Automatic retry with exponential backoff" mischaracterises `REQUEST_RETRANSMIT_GAPS = (0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0, 2.0, 3.0, 4.0, 5.0)` (`src/lifx/const.py:53-65`) — an escalating, roughly linear-then-stepped schedule, not exponential. This phase's own updated prose in advanced-usage.md and troubleshooting.md correctly says "escalating schedule"; overview.md is the remaining stale characterisation of exactly the wire-reliability behaviour Phase 5 set out to document accurately.
**Fix:** "Retry Logic: Automatic retransmits on an escalating schedule within each request's timeout".

## Info

### IN-01: US spellings remain in reviewed prose (project rule: Australian English)

**File:** multiple
**Issue:** Prose (not API identifiers) using US spelling: `docs/api/animation.md:138` "initialization"; `docs/architecture/overview.md:117` "Serialization", `:291` "acknowledgment", `:293` "Deserialize"; `docs/user-guide/advanced-usage.md:14,473` "Performance Optimization", `:430` "Synchronized Multi-Device Effects"; `docs/user-guide/animation.md:186` "Normalize" (comment), `:308` "vectorized"; `CLAUDE.md:160` "Optimized" (a line touched by this phase's diff). API-mandated identifiers like `set_color`/`color=` are correctly exempt.
**Fix:** initialisation, serialisation/deserialise, acknowledgement, Optimisation, Synchronised, Normalise, vectorised, Optimised.

### IN-02: overview.md Layer 4 prose omits `CeilingLight` while its own diagram includes it

**File:** `docs/architecture/overview.md:173, 178-185`
**Issue:** The "Device Types" bullet lists "Base, Light, HevLight, InfraredLight, MultiZoneLight, MatrixLight" and the Key Files list omits `ceiling.py`, but the mermaid diagram (line 36) shows `CeilingLight` and it is a shipped, documented class.
**Fix:** Add `CeilingLight` to the bullet and `ceiling.py` to Key Files.

### IN-03: CLAUDE.md Animation Layer file list omits `flow.py`

**File:** `CLAUDE.md` (Architecture section 5, Animation Layer)
**Issue:** Lists `animator.py`, `framebuffer.py`, `packets.py`, `orientation.py` but omits `animation/flow.py` (ack-gated flow control), which exists on disk and which `docs/architecture/overview.md:212` correctly lists.
**Fix:** Add `flow.py`: Ack-gated flow control.

### IN-04: ceiling-lights.md presents the inherited `MatrixLightState` attribute list as exhaustive but omits `tile_orientations`

**File:** `docs/user-guide/ceiling-lights.md:170`
**Issue:** "Plus all attributes inherited from `MatrixLightState`: `chain`, `tile_colors`, `tile_count`, `effect`" — the actual dataclass (`src/lifx/devices/matrix.py:285-289`) also has `tile_orientations`.
**Fix:** Add `tile_orientations` to the list.

### IN-05: FAQ drops the "healthy networks" qualifier from the zero-packet-loss claim

**File:** `docs/faq.md:247-249`
**Issue:** FAQ states unconditionally "Zero packets are lost", while `docs/user-guide/troubleshooting.md:323-324` (the canonical section it links to) correctly qualifies: "on healthy networks, an idle device loses zero packets". Given this phase's focus on precise wire-reliability wording, the unqualified absolute is a consistency gap.
**Fix:** "On healthy networks, zero packets are lost — …".

---

_Reviewed: 2026-07-17T03:13:38Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
