# Phase 5: Reliability Documentation - Pattern Map

**Mapped:** 2026-07-17
**Files analysed:** 6 modified (0 new — D5-01 forbids new pages)
**Analogs found:** 6 / 6

Documentation-only phase. Every file is an existing docs page being extended or
corrected in place; the "analogs" are the in-repo docs conventions on those same
pages (and their sibling exemplars). No source code is touched.

## File Classification

| Modified File | Role | Data Flow | Closest Analog (convention source) | Match Quality |
|---------------|------|-----------|-------------------------------------|---------------|
| `docs/user-guide/troubleshooting.md` | docs page (problem/solution guide) | prose + snippets | itself — Symptom/Causes/Solution section template (lines 15–58, 89–113) | exact |
| `docs/user-guide/animation.md` | docs page (how-to guide) | prose + runnable examples | itself — canonical `send_frame()` loop (lines 34–48) | exact |
| `docs/faq.md` | docs page (FAQ) | prose + snippets | itself — `## Category` / `### Question` structure | exact |
| `docs/user-guide/ceiling-lights.md` | docs page (device guide) | prose, cross-link only | itself — existing admonition + link style | exact |
| `docs/user-guide/advanced-usage.md` | docs page (patterns guide) | prose + snippets | troubleshooting.md/animation.md conventions | role-match |
| `docs/architecture/overview.md` | docs page (architecture) | prose | itself — layer-bullet style (lines 186–197) | exact |

No nav changes: all pages already in `mkdocs.yml` nav (lines 191–221). Never touch
`docs/changelog.md` or `docs/api/*.md` (baseline warnings live in api/effects.md ×5
and api/index.md ×3; "builds cleanly" = exit 0, ≤ 8 warnings, none on edited pages).

## Pattern Assignments

### `docs/user-guide/troubleshooting.md` (DOCS-01 wake-tail section + stale fixes)

**Analog:** the page's own section template.

**Section pattern** (lines 89–113 — copy this shape for the new wake-tail section):
```markdown
### Partial Device Discovery

**Symptom:** Only some devices discovered

**Causes:**

- Devices on different subnets
- ...

**Solution:**

```python
...
```
```

**TOC pattern** (lines 5–11 — the page has a bullet TOC; a new `##`-level home for
the wake-tail section needs a TOC entry; `###` under an existing TOC'd `##` does not):
```markdown
- [Discovery Issues](#discovery-issues)
- [Connection Problems](#connection-problems)
```

**Cross-link pattern** (lines 404–407 — relative paths, `../` for parent dir):
```markdown
- [Advanced Usage](advanced-usage.md) — Optimization patterns
- [FAQ](../faq.md) — Frequently asked questions
```

**Stale fixes on this page** (per RESEARCH audit #5–#8):
- Lines 89–113 "Partial Device Discovery": replace the multi-pass loop with
  "one call already re-broadcasts (DISC-01); increase `timeout` if needed".
- Line ~220: fix `async with discover(...)` misuse — `discover()` is an async
  generator (`async for device in discover()`), correct usage exists in faq.md:70
  and troubleshooting.md:49–57. Also fix "# Default is 3.0" → 15.0 s
  (`src/lifx/const.py:28`).
- Lines 152–185 "Connection Drops": contextualise, don't delete — library already
  retransmits within each request (RETRY-01..04); wrapper is for whole-operation
  failures.

**Code-example format for the polling recipe** — device-layer, no colour
construction, 15 s cadence (RESEARCH §Code Examples, D5-04):
```python
import asyncio
from lifx import Light

async def keep_awake(light: Light) -> None:
    """Optional: poll periodically so a gen4 device's radio stays awake."""
    while True:
        await light.get_color()  # one request returns colour, power and label
        await asyncio.sleep(15)  # 10-15 s keeps the wake tail away
```

**Gen4 identification snippet** (verified live; do NOT use a product-ID list —
registry has no generation field):
```python
firmware = await device.get_host_firmware()
if firmware.version_major >= 4:
    ...
```

---

### `docs/user-guide/animation.md` (DOCS-02 streaming section + own stale fixes)

**Analog:** the page's own canonical loop (lines 34–48).

**Core loop pattern** (copy this shape; note raw uint16 HSBK tuples, synchronous
`send_frame()`, try/finally + `animator.close()`, top-level `asyncio.run(main())`):
```python
    try:
        for _ in range(100):
            # Generate frame (H, S, B, K as uint16)
            frame = [(65535, 65535, 65535, 3500)] * animator.pixel_count

            # send_frame() is synchronous for speed
            stats = animator.send_frame(frame)

            await asyncio.sleep(1 / 30)  # 30 FPS   <-- STALE, change to 20
    finally:
        animator.close()
```

**Setup pattern** (lines 54–62):
```python
async with await MultiZoneLight.from_ip("192.168.1.100") as device:
    animator = await Animator.for_multizone(device)
```

**Stale fixes on this page** (audit #1–#4): lines 4 and 10 ("30+ FPS", "20+ FPS")
→ ~20 FPS ceiling framing; lines 44, 71, 276 `1 / 30` → `1 / 20`; lines 329–340
"Flickering or Glitches" → rewrite: primary cause is device saturation
(latest-frame-wins stutter, by design), distinguish from genuine network loss.

**D5-09 boundary:** narrative uses D4-01/D4-02 behavioural wording only
(ack-paced, latest-frame-wins, no consumer configuration). Do NOT copy the
`Animator` docstring's tuning constants (2-outstanding gate, ~1 s expiry).
`stats.gated` / `stats.acks_outstanding` are public and MAY appear in an aside.

---

### `docs/faq.md` (short wake-tail entry, link-only)

**Analog:** the page's own structure — `## Category` / `### Question` headings
(General, Installation & Setup, Usage, ...). Add the entry under `## Performance`
or `## Troubleshooting` if present, else the closest existing category; body links
to `user-guide/troubleshooting.md#<wake-tail-anchor>`.

**Correct discover() usage exemplar on this page** (line 70):
```python
async for device in discover():
    print(f"Found {device.serial} at {device.ip}")
```

Optional minor fix (audit #14): "Why can't discovery find my devices?"
(lines 47–61) may note discovery re-broadcasts automatically.

---

### `docs/user-guide/ceiling-lights.md` (one cross-link only, D5-02)

**Analog:** its own link + admonition style. Cross-link format:
```markdown
See [gen4 power-save wake tail](troubleshooting.md#<anchor>) ...
```
(Same-directory relative link, heading anchor — matches troubleshooting.md:404–407.)

---

### `docs/user-guide/advanced-usage.md` (stale fixes only)

**Analogs:** troubleshooting.md section conventions; animation.md loop style.
- Lines 280–303 "Batched Discovery": remove two-pass pattern, same replacement
  rationale as troubleshooting #5 (DISC-01).
- Lines 553–594 "Fire-and-Forget Mode": rework — point sustained streaming at the
  animation guide; keep `fast=True` for occasional one-shots; fix 30 FPS figure.
- Lines 327–346 "Robust Error Handling": contextualise like troubleshooting #8.

---

### `docs/architecture/overview.md` (stale fixes only)

**Analog:** its own layer-description bullet style (lines 186–197).
- Line 186: "30+ FPS" → ~20 FPS ceiling framing.
- Layer 5 bullets: add ack-gated pacing as internal behaviour; add
  `animation/flow.py` to Key Files.

---

## Shared Patterns

### Admonitions (D5-06 keepalive callout)
**Source:** `docs/user-guide/ceiling-lights.md` lines 126–129 and 373–374 — the
only two in-repo exemplars. Material style, custom quoted title, 4-space indented
body:
```markdown
!!! note "State Properties Require Recent Data"
    The `uplight_is_on` and `downlight_is_on` properties rely on cached data.
    Call `get_uplight_color()` or `get_downlight_colors()` first to ensure
    accurate state.
```
```markdown
!!! tip "Choosing the right origin"
    For **LIFX Ceiling** and **LIFX Ceiling Capsule** devices, always use `origin="center"` ...
```
**Apply to:** the D5-06 "no keepalive daemon" callout in troubleshooting.md
(use `!!! note "..."` or `!!! info "..."` with a custom title; must include the
"why": zero idle loss measured, polling is the application's choice).

### Anchor-stable cross-links
**Source:** troubleshooting.md:404–407, faq links. Relative paths + toc-generated
anchors (`toc permalink: true`). **Ordering constraint:** write the wake-tail
heading FIRST (DOCS-01 task); the three linking pages (faq.md,
ceiling-lights.md, animation.md) depend on that anchor text.

### HSBK format discipline
- troubleshooting.md snippets = device layer (`get_color()`, float HSBK — but the
  polling recipe needs no colour construction at all).
- animation.md snippets = raw uint16 tuples `(hue, sat, bright, kelvin)`,
  0–65535. Never mix.

### Verification per edit
`uv run zensical build` — exit 0, ≤ 8 warnings (baseline, all in api/ pages).
Australian English throughout. "CCT/brightness-only", never "white-only".

## No Analog Found

None — every file is an existing page with its own established conventions.

## Metadata

**Analog search scope:** `docs/` (host pages read directly; conventions verified
in RESEARCH.md against mkdocs.yml and grep of docs/)
**Files scanned:** 6 host/target pages + mkdocs.yml (via research)
**Pattern extraction date:** 2026-07-17
