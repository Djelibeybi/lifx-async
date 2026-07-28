# set_all_color_zones design

Date: 2026-07-28
Status: accepted
Scope: `src/lifx/devices/multizone.py`

## Problem

`MultiZoneLight` has `get_all_color_zones()`, which hides the legacy/extended
split behind one call, but no matching setter. Callers wanting to write a
per-zone colour list must choose the packet themselves, know the 82-colour
cap, know whether the device supports extended multizone, and sequence
`NO_APPLY`/`APPLY` by hand.

`apply_theme` got this wrong until 05fcfba: it called
`set_extended_color_zones(0, colors)` unconditionally, so it raised
`LifxUnsupportedCommandError` on firmware without extended multizone and
`ValueError` on any strip longer than 82 zones.

That fix introduced `MultiZoneLight._write_zone_colors(colors, duration)`,
which already does the routing but is private and hardcoded to start at zone
0. This spec generalises it and exposes it.

## Why the getter unified easily and the setter does not

Both read paths return the same shape — a list of colours — so chunking is an
invisible implementation detail. The write paths do not take the same shape of
argument:

| Packet | Takes | Packets for N zones |
|---|---|---|
| `SetColorZones` (501) | a range + **one** colour | one per run of identical colours |
| `SetExtendedColorZones` (510) | a start index + **≤82 colours** | `ceil(N/82)` |

Legacy encodes *runs*; extended encodes *lists*. A unified signature must take
a per-zone list, because that is the only shape that can express what extended
does, and then run-length encode it back into ranges for legacy.

RLE collapses flat blocks well, and `HSBK.__eq__` compares at uint16 (wire)
granularity, so colours that serialise identically merge correctly. It does
nothing for a gradient: 60 distinct colours is 60 legacy packets. The protocol
offers no more compact encoding, so this cost is inherent, not an
implementation weakness.

## API

```python
async def set_all_color_zones(
    self,
    colors: list[HSBK],
    start: int = 0,
    end: int | None = None,
    duration: float = 0.0,
    apply: MultiZoneApplicationRequest = MultiZoneApplicationRequest.APPLY,
) -> None:
    """Set zone colours from a full-length colour list.

    ``colors`` is indexed by absolute zone number: ``colors[i]`` is the colour
    for zone ``i``. ``start`` and ``end`` (both inclusive) select which zones
    to actually write; the rest of the list is left alone. ``end`` defaults to
    the last zone in the list.
    """
```

### Decisions

**`colors` is full-length and absolutely indexed; `start`/`end` window it.**
This is the driving use case: read every zone, change a few, write back only
what changed.

```python
colors = await light.get_all_color_zones()
colors[10:20] = [red] * 10
await light.set_all_color_zones(colors, start=10, end=19)
```

`end` is therefore *not* derivable from `len(colors)` — the list describes the
whole strip while the window describes the write. The invariant that makes
this unambiguous is **list index equals zone index**, which also makes the
call round-trip cleanly with `get_all_color_zones()` and keeps `start`/`end`
meaning exactly what they mean in `get_color_zones(start, end)`.

The rejected alternative was passing only the subset, with `start` as the
target offset and `end` implied by the length. It forces callers doing
read-modify-write to slice the list themselves and to keep the slice offset in
step with `start`, which is the error this signature exists to prevent.

**`apply` stays in the signature.** The method owns the internal `NO_APPLY`
sequencing regardless, but the caller still needs to say what the *final*
packet does, so several `set_all_color_zones` calls can be composed into one
visible change. Semantics: every packet but the last is forced to `NO_APPLY`;
the last carries the caller's value.

**No `fast=` parameter.** `set_extended_color_zones` has one for
fire-and-forget animation frames. It does not generalise: a multi-packet
unacked write has no way to detect a lost `NO_APPLY`, so the strip would
silently render a partial frame. High-frequency work belongs in the Animation
Layer (`src/lifx/animation/`), which is built for it.

## Behaviour

### Routing

1. `await self._ensure_capabilities()` if `self.capabilities is None`.
2. `capabilities.has_extended_multizone` → extended path.
3. Otherwise → legacy path.

Both paths operate on the window `window = colors[start : end + 1]`, writing
it back to zones `start` through `end`. Only the window is transmitted; zones
outside it are never addressed and keep whatever they were showing.

### Extended path

Chunk `window` into runs of ≤82. Chunk *i* is written at zone index
`start + i * 82`. Every chunk but the last is sent `NO_APPLY`.

### Legacy path

Run-length encode `window` into `(run_start, run_end, colour)` triples, offset
by `start`, one `SetColorZones` per run. Every run but the last is sent
`NO_APPLY`.

Note the RLE runs over the *window*, not the whole list — two zones either
side of the window boundary sharing a colour must not merge into one packet,
or the write would spill outside the requested range.

`_encode_zone_runs` already exists and is correct; it needs an offset
parameter, or the caller adds `start` to each index.

### Validation

| Condition | Result |
|---|---|
| `colors` empty | `ValueError` |
| `start < 0` | `ValueError` |
| `end < start` | `ValueError` |
| `end >= len(colors)` | `ValueError` — the window must lie inside the list |
| legacy and `end > 255` | `ValueError`, naming the uint8 limit |
| `end >= zone_count`, when cached | `ValueError` |

`end` defaults to `len(colors) - 1`, so the common "write the whole strip"
case stays a single argument.

The legacy bound applies to `end` rather than `len(colors)`, because the
window is what gets addressed: a 400-entry list is fine on legacy firmware so
long as the window stays at or below zone 255. `SetColorZones.StartIndex` and
`EndIndex` are `uint8` (`packets.py:980-981`), so legacy firmware cannot
address past that. Extended's `index` is `uint16` and has no such limit.

### Duration

Extended: one value on each packet, and since the device applies the buffered
set in one step the whole strip fades together.

Legacy: each `SetColorZones` carries its own duration, but the transition is
governed by the packet carrying `APPLY` — confirmed, not assumed. Passing the
same duration to every packet, as `_write_zone_colors` does, is therefore safe
and matches Photons. Both paths produce the same fade.

## The packet-count cliff

The same call can cost 1 packet or 60 depending on firmware and content, with
a matching difference in latency and failure surface. Devices handle roughly
20 messages/second and this library imposes no rate limiting, so a 60-zone
legacy gradient is a multi-second write.

In practice this is close to unreachable. Product 31 — the only multizone
product whose registry entry lacks extended support — is old enough that
surviving units are vanishingly rare. The remaining route to the legacy path
is `_process_capabilities` stripping `EXTENDED_MULTIZONE` from a product 32 or
38 running firmware below 2.77, which means a Z or Beam that has never been
updated.

So the legacy path is a correctness fallback, not a hot path. Keep it correct,
do not spend effort optimising it, and do not let its cost shape the public
API. Still emit a `_LOGGER.debug` record with the chosen path and packet count
so anyone who does land on it can see why their strip is slow without reading
the implementation.

Atomicity is *not* a reason to avoid the method: `SetColorZones` sets
`_requires_ack: True` and `request()` waits, so a dropped `NO_APPLY` is
retried before `APPLY` is sent. It costs a round trip per packet, which feeds
back into the latency above.

## Migration

1. Generalise `_write_zone_colors` to take `start`, `end` and an `apply` for
   the final packet.
2. Add the public `set_all_color_zones` wrapper.
3. Point `apply_theme` at the public method. It passes a full-length list and
   no window, so it uses the defaults and behaviour is unchanged.
4. Document it in `docs/user-guide/` alongside `get_all_color_zones`.

`_write_zone_colors` can then either stay as the private core or be folded
into the public method entirely — the wrapper adds nothing once the window and
`apply` are parameters, so folding is preferred.

## Tests

Existing coverage in `TestWriteZoneColors` (extended chunking, legacy RLE,
gradient cost, uint8 bound, empty input) transfers directly. Add:

- omitting `end` writes the whole list
- a window writes only `colors[start : end + 1]`, to zones `start`..`end`
- zones outside the window appear in no packet — the strongest guarantee here,
  since a spill silently overwrites colours the caller asked to keep
- a window narrower than 82 is one extended packet at index `start`, not at 0
- non-zero `start` offsets extended chunk indices by `start + i * 82`
- non-zero `start` offsets legacy run indices
- RLE does not merge across the window boundary: identical colours just
  outside the window do not extend the run
- read-modify-write round-trip: `get_all_color_zones` → mutate one zone →
  write that zone back → only one zone is addressed
- caller's `apply` reaches the final packet only; earlier packets are
  `NO_APPLY`
- `apply=NO_APPLY` means no packet applies, so two calls can compose
- legacy bound is `end > 255`, so a long list with a low window is accepted
- `end` past a cached `zone_count` raises rather than clamping
- an uncached `zone_count` skips that check and sends no extra request
- `apply_theme` delegates to the public method

## Resolved

- **No `set_zone_color(index, colour)` convenience.** Under the full-length
  convention the equivalent is
  `set_all_color_zones(colors, start=index, end=index)`, which needs the whole
  list in hand — exactly the read-modify-write case. A convenience taking a
  single zone and colour would have to fetch the list itself or accept a
  subset, reintroducing the ambiguity this signature exists to avoid.
  `set_color_zones(start, end, colour)` remains the way to set one colour
  without a list.


- **The legacy `APPLY` packet governs the buffered set.** Confirmed, so
  passing the same duration to every packet is correct and both paths fade
  identically.

- **Validate `end` against `self._zone_count`, but never fetch it.** The count
  is cached at three sites — `get_zone_count`, and opportunistically from the
  `count` field of the `StateMultiZone` and `StateExtendedColorZones`
  responses (`multizone.py:272`, `353`, `452`). `_initialize_state` calls
  `get_all_color_zones()`, so any device that went through `connect()` or the
  async context manager already has it.

  The only uncached case is a hand-constructed `MultiZoneLight` whose first
  zone operation is a write, and that caller cannot have built a sensible
  full-length colour list without knowing the zone count anyway. So validate
  when `self._zone_count is not None` and let the device reject otherwise; a
  round trip purely to validate is never warranted.

  This mirrors `get_color_zones` (`multizone.py:335-337`) with one deliberate
  difference: the getter *clamps* `end` to the zone count, which is harmless
  because the caller simply receives fewer zones. A setter must raise instead
  — silently clamping a write would drop zones the caller explicitly asked to
  change.
