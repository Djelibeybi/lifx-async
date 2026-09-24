---
status: complete
phase: 18-typed-move-and-morph-palette-effects
source: [18-VERIFICATION.md, 18-09-SUMMARY.md]
started: 2026-09-23T11:14:21Z
updated: 2026-09-24T00:31:53Z
---

## Current Test

[testing complete]

## Tests

### 1. Default Move and Morph palettes match the LIFX app on real hardware
expected: Single-colour devices animate the generated three-colour palette like the LIFX app; multi-colour devices animate their existing colours with no repaint.
result: pass
retested: "Passed on retest as test 2 (2026-09-24) after 18-09 closed G-18-1; Move was already correct here"
originally_reported: "Testing against a Thread-enabled Luna: the first morph works, the second morph doesn't start, regardless of --white. get_effect in both A and C returns OFF not MORPH."
severity: major

### 2. Palette-less Morph starts on a multi-colour Luna, and Move is unchanged
expected: On the Thread-enabled Luna already showing several colours, set_effect(FirmwareEffect.MORPH, speed=3.0) with no palette visibly starts morphing through the device's own colours, and get_effect() reports MORPH (not OFF). Repeating the Move checks on a real strip (single-colour and multi-colour) behaves as before.
result: pass

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-18-1
  truth: "MORPH started with no palette on a device showing several colours animates those colours"
  status: resolved
  resolved_by: 18-09-PLAN.md
  resolved_at: 2026-09-24
  reason: "User reported: Testing against a Thread-enabled Luna: the first morph works, the second morph doesn't start, regardless of --white. get_effect in both A and C returns OFF not MORPH."
  severity: major
  test: 1
  root_cause: "D-14 assumed firmware animates the current pixels when Tile.SetEffect carries palette_count=0. On the Luna the firmware does not start MORPH at all with palette_count=0 (get_effect reports OFF), so MatrixLight.set_effect(MORPH, palette=None) silently does nothing on any multi-colour device. Photons never sends an empty MORPH palette (photons_control/tile.py:106)."
  artifacts:
    - path: "src/lifx/devices/component_state.py"
      issue: "derive_effect_palette() returns None for multi-colour input, which becomes palette_count=0"
    - path: "src/lifx/devices/matrix.py"
      issue: "set_effect() sends palette_count=0 for MORPH when the derived palette is None"
  missing:
    - "MORPH must always send a non-empty palette; the multi-colour case needs a palette built from the device's own colours"
    - "When the device shows more than 16 distinct colours, choose them by even sampling: 16 pixels spaced evenly across the whole device, then de-duplicated (maintainer decision 2026-09-24)"
  evidence:
    - "Probe variant A and C (palette_count=0 after painting a three-colour theme): get_effect reports OFF, no visible morph"
    - "Probe variant B (device's own distinct colours as the palette): get_effect reports MORPH and it visibly morphs; the blended theme showed 35 distinct colours"
    - "Move on a real strip (single-colour and multi-colour scenarios): works as expected, so the multi-colour no-repaint Move path needs no change"
  debug_session: ""
