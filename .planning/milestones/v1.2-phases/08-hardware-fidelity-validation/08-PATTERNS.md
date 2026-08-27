# Phase 8: Hardware Fidelity Validation - Pattern Map

**Mapped:** 2026-08-15
**Files analysed:** 10
**Analogues found:** 10 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analogue | Match Quality |
|---|---|---|---|---|
| `.planning/phases/08-hardware-fidelity-validation/uat_theme_fidelity.py` | utility / UAT runner | event-driven, request-response, file-I/O | `.claude/theme-capture/tools/sweep_themes.py` | role and flow match |
| `.planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py` | test | transform, event-driven | `tests/test_theme/test_theme.py` | role match |
| `.planning/phases/08-hardware-fidelity-validation/08-UAT-RESULTS.json` | evidence config/data | file-I/O, batch | `.planning/milestones/v1.1-phases/03-retry-schedule-reshape/03-UAT-RESULTS.json` | exact output role |
| `.planning/phases/08-hardware-fidelity-validation/08-UAT.md` | evidence documentation | batch | `.planning/phases/06-generated-theme-library/06-UAT.md` | exact output role |
| `.gitignore` | config | file-I/O | existing `.gitignore` local-storage section | exact role |
| `.planning/PROJECT.md` | planning documentation | transform | `.planning/REQUIREMENTS.md` Fidelity section | role match |
| `.planning/REQUIREMENTS.md` | requirements documentation | transform | `.planning/ROADMAP.md` Phase 8 success criteria | role match |
| `.planning/ROADMAP.md` | roadmap documentation | transform | `.planning/REQUIREMENTS.md` Fidelity section | role match |
| `.claude/theme-capture/README.md` | capture documentation | transform | its Caveats section | exact role |
| `data/themes.jsonl` | model/data source | batch, transform | existing generated theme record source | existing source; read-only input only |

`data/themes.jsonl` is the mechanically authoritative input for the 25-row table. Phase 8 must not alter theme palettes, so it is classified here for data flow but should not be modified.

## Pattern Assignments

### `.planning/phases/08-hardware-fidelity-validation/uat_theme_fidelity.py` (utility / UAT runner; event-driven, request-response, file-I/O)

**Primary analogue:** `.claude/theme-capture/tools/sweep_themes.py`

**Harness lifecycle and safe device cleanup** (lines 194-216):

```python
async def read_palette(ip: str) -> list[dict[str, float]] | None:
    device = await Device.connect(ip)
    try:
        if not isinstance(device, MatrixLight):
            return None
        effect = await device.get_effect()
        if effect.effect_type is FirmwareEffect.OFF or not effect.palette:
            return None
        return [...]
    finally:
        await device.close()
```

Use targeted, private bindings rather than the analogue's public `--ip` option, but retain its `try`/`finally` resource-close shape. The Phase 8 outer state machine must extend this pattern with a restoration `finally`; no official evidence can be emitted until restoration and final validation complete.

**Semantic UI hierarchy extraction** (lines 84-110):

```python
def dump() -> ET.Element:
    sh("shell", "uiautomator", "dump", "/sdcard/s.xml")
    sh("pull", "/sdcard/s.xml", str(DATA / "s.xml"))
    return ET.parse(DATA / "s.xml").getroot()

def visible_cells(root: ET.Element) -> dict[str, tuple[int, int]]:
    cells: dict[str, tuple[int, int]] = {}
    for node in root.iter("node"):
        text = (node.get("text") or "").strip()
        ...
        cells[text] = ((x1 + x2) // 2, (y1 + y2) // 2)
    return cells
```

Reuse the fixed-argument ADB helper, XML parser and semantic `text`/resource-id interrogation. Phase 8 must make the current hierarchy's expected category, exact display name and Save control authoritative; recorded coordinates can only be the final tap mechanism after current semantic resolution.

**Resumable append-only event output** (lines 239-301):

```python
done = set()
if out.exists():
    done = {json.loads(line)["name"] for line in out.read_text().splitlines() if line}

with out.open("a") as handle:
    for index, name in enumerate(names):
        if name in done:
            continue
        ...
        handle.write(json.dumps(record) + "\\n")
        handle.flush()
```

Copy the append-and-flush shape for *private* JSONL polls and cycles only. Phase 8 resumes only after exact provenance equality, and keeps transitional reads rather than replacing them. Never use the analogue's `frozenset` palette comparison, because Phase 8 must preserve duplicates with `Counter`.

**Supporting analogue:** `.planning/milestones/v1.1-phases/03-retry-schedule-reshape/uat_zero_loss.py`

**CLI, explicit defaults, structured outcome and exit status** (lines 155-245):

```python
parser.add_argument("--timeout", type=float, default=2.0, ...)
parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT, ...)
...
results = build_results(trials)
args.json_out.parent.mkdir(parents=True, exist_ok=True)
args.json_out.write_text(json.dumps(results, indent=2) + "\\n")
...
if results["pass"]:
    return 0
return 1
```

Apply this argument/default/result pattern, but use the locked Phase 8 statuses: pass, validation mismatch, incomplete/preflight failure and restoration failure. Record each effective timeout in provenance. Write official JSON only through the Phase 8 allowlist finaliser after restoration; local checkpoint/JSONL paths are excluded from git.

### `.planning/phases/08-hardware-fidelity-validation/tests/test_uat_theme_fidelity.py` (test; transform and event-driven)

**Analogue:** `tests/test_theme/test_theme.py`

**Duplicate-sensitive unordered equality** (lines 326-343):

```python
def test_different_duplicate_counts_do_not_match(self) -> None:
    a = Theme([Colors.RED, Colors.RED, Colors.GREEN])
    b = Theme([Colors.RED, Colors.GREEN, Colors.GREEN])

    assert not a.palette_equals(b)
```

Test the runner's pure palette canonicalisation/stability functions against reordered equal palettes and duplicate-count mismatches. Do not use sets or floating-point tolerance.

**MORPH emulator seam** (from `tests/test_devices/test_matrix.py`, lines 277-298):

```python
await matrix.set_effect(
    effect_type=FirmwareEffect.MORPH,
    speed=5000,
    palette=rainbow,
)
effect = await matrix.get_effect()
assert effect.effect_type == FirmwareEffect.MORPH
assert len(effect.palette) == 4
```

Use emulator/mocks only for pure support, schema, redaction, provenance and restore-orchestration branch tests. The real Tile and non-Tile comparisons remain UAT evidence and cannot be marked satisfied by these tests.

### `.planning/phases/08-hardware-fidelity-validation/08-UAT-RESULTS.json` (sanitised evidence data; file-I/O, batch)

**Analogue:** `.planning/milestones/v1.1-phases/03-retry-schedule-reshape/03-UAT-RESULTS.json`

**Stable result structure** (lines 1-16):

```json
{
  "timestamp": "...",
  "trials": [
    {"tx_count": 1, "latency_ms": 8.216082991566509, "ok": true}
  ],
  "trials_run": 60,
  "failures": 0,
  "pass": true
}
```

Produce a machine-checkable public projection with a fixed allowlist: runner invocation/revision, fixed theme records/hash, public device role plus model/product/firmware, each app/library cycle's stable comparison result, 25 mechanically derived ceiling determinations, restoration verdicts and terminal outcome. Reject unknown keys and private address/serial/MAC/household-label patterns before writing.

### `.planning/phases/08-hardware-fidelity-validation/08-UAT.md` (rendered evidence documentation; batch)

**Analogue:** `.planning/phases/06-generated-theme-library/06-UAT.md`

**Review-oriented coverage record** (lines 1-25):

```markdown
---
status: complete
phase: 06-generated-theme-library
source: [06-01-SUMMARY.md, 06-02-SUMMARY.md]
---

## Tests

### 1. End-to-end generated theme pipeline (THEME-04)
expected: ...
result: pass
source: automated
verification: ...
```

Render Markdown solely from the validated public JSON projection. Preserve an auditable per-device/per-theme account of all six cycles, the exact 25-row table and restoration outcome; show `human_needed`, failed or incomplete honestly. Never copy raw trace paths, screenshots, hierarchy dumps or private target identity into Markdown.

### `.gitignore` (config; file-I/O)

**Analogue:** `.gitignore` local-storage entries (lines 89-95):

```gitignore
# Local storage
.notes/
.claude/settings.local.json
.mcp.json
.serena/
.full-review/
.gsd/
```

Add one narrow, explicit rule for the Phase 8 private checkpoint/diagnostic root before it is created. Do not broadly ignore `.planning/`, the tracked phase directory, `08-UAT-RESULTS.json`, or `08-UAT.md`.

### Documentation corrections: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.claude/theme-capture/README.md` (documentation; transform)

**Analogues and exact stale locations:**

```markdown
# .planning/REQUIREMENTS.md:71-77
- [ ] **FIDELITY-01**: The 26 themes that returned exactly 16 colours ...

# .planning/ROADMAP.md:141-151
3. Each of the 26 exactly-16-colour themes carries a committed determination ...

# .claude/theme-capture/README.md:69-72
**Sixteen-colour palettes may be truncated.** 21 themes returned exactly 16
colours, the protocol's palette ceiling.
```

Correct all active planning/capture prose to distinguish 26 raw captured records (including sport) from 25 shipped non-sport `lifx-app` records. State the protocol-ceiling limitation accurately and retain the rule that a device cannot establish a length above 16. In `PROJECT.md`, update all affected claims at lines 58, 76 and 160, keeping its surrounding historical-capture context.

### `data/themes.jsonl` (authoritative model/data input; batch, transform)

**Analogue:** the generated source-of-truth pattern established for Phase 6, reflected in `.planning/phases/06-generated-theme-library/06-UAT.md` lines 43-48:

```markdown
expected: 166 records, 168 resolvable names, every app palette multiset-equal
to its capture record ... canonical D-24 order; pure ASCII
```

Read the JSONL records, filter `disposition == "lifx-app"` and palette length `== 16`, sort by ASCII slug, and generate the exact 25-row determination table from that result. Do not duplicate a slug list, CSV or editable parallel inventory; do not modify this input in Phase 8.

## Shared Patterns

### Hardware scope, resource cleanup and restoration

**Sources:** `.claude/theme-capture/tools/sweep_themes.py:194-216`; `.planning/milestones/v1.1-phases/03-retry-schedule-reshape/uat_zero_loss.py:197-221`

```python
conn = DeviceConnection(serial="000000000000", ip=args.ip)
try:
    reachable = await probe(conn, timeout=max(args.timeout, 5.0))
    ...
finally:
    await conn.close()
```

Phase 8 must use the same `try`/`finally` discipline but add state restoration for every selected target and Android keep-awake-setting restoration on every exit. Preflight snapshots must complete before any mutation, and failures must remain explicit terminal outcomes.

### Exact palette comparison

**Source:** `src/lifx/theme/theme.py:242-284`

```python
if not isinstance(other, Theme):
    raise TypeError(
        f"palette_equals() expects a Theme, got {type(other).__name__}"
    )
return Counter(self.colors) == Counter(other.colors)
```

Apply this exact unordered-multiset rule to every expected, app and library readback. HSBK equality is already uint16/protocol-granular, so Phase 8 must neither convert to floats nor use a `set`/`frozenset`.

### MORPH protocol seam

**Source:** `src/lifx/devices/matrix.py:1059-1108, 1169-1279`

```python
palette = [
    HSBK.from_protocol(proto_color)
    for proto_color in response.settings.palette[: response.settings.palette_count]
]
...
await self.connection.send_packet(packets.Tile.SetEffect(settings=settings))
```

Use `MatrixLight.get_effect()` and `MatrixLight.set_effect(FirmwareEffect.MORPH, palette=...)`; do not hand-build packets. The setter pads to 16 slots while retaining `palette_count`, so the observed readback is the only valid protocol-level comparison input.

### Matrix and Ceiling restoration reads

**Sources:** `src/lifx/devices/matrix.py:1416-1473`; `src/lifx/devices/ceiling.py:675-802`

```python
all_tile_colors = await self.get_all_tile_colors()
effect = await self.get_effect()
self._state.tile_colors = [c for tile in all_tile_colors for c in tile]
...
uplight_color = tile_colors[self.uplight_zone]
downlight_colors = tile_colors[self.downlight_zones]
```

Snapshot full matrix pixels/effect plus base colour/power before mutation. If the target is a `CeilingLight`, also preserve and verify component state via `get_uplight_color()` and `get_downlight_colors()`; a generic matrix-only restoration is insufficient.

### Evidence truthfulness

**Source:** `.planning/milestones/v1.1-phases/02-discovery-rebroadcast/uat_rounds.py:108-154`

```python
if roster_size < ROSTER_SANITY_FLOOR:
    print("ENV-ERROR: ... not recording a pass")
    return 2
if median == roster_size:
    print("PASS: ...")
    return 0
print("FAIL: ... measured coverage shortfall")
return 1
```

Separate pass, validation mismatch, incomplete/preflight and restoration-failure exits. A missing non-Tile target is `human_needed`/incomplete, never a Tile-only or emulator pass. Stable mismatch still records all remaining locked cycles before restoration/finalisation.

## No Analogue Found

| File / responsibility | Role | Data Flow | Reason and planner direction |
|---|---|---|---|
| Strict public-evidence allowlist, identifier-pattern rejection and provenance-gated resume | utility | transform, file-I/O | No existing Phase runner combines sanitised public projection with resumable private checkpointing. Implement as deterministic pure helpers in `uat_theme_fidelity.py`, tested without hardware, following the Phase 8 contract rather than inventing a public library API. |
| Two-consecutive-unordered-palette stability rule and retained mismatch evidence | utility | request-response, event-driven | Existing capture uses a fixed sleep plus a one-off unchanged retry (`sweep_themes.py:279-285`), not Phase 8's required retained-poll stability state machine. The capture-era reset observation is not a canonical sentinel; implement the locked two-read rule and retain stable unexpected palettes as mismatches in pure/testable helpers. |

## Metadata

**Analogue search scope:** `.claude/theme-capture/`, `.planning/phases/`, `.planning/milestones/`, `src/lifx/devices/`, `src/lifx/theme/`, `tests/`, root configuration

**Files scanned:** 18

**Pattern extraction date:** 2026-08-15
