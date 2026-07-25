---
phase: quick-260726-42c
verified: 2026-07-26T00:00:00Z
status: passed
score: 6/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
behavior_unverified_items:
  - truth: "Broadcast sweep prints a Rich table with the eight locked columns plus a summary panel grouping verdict counts by product + firmware"
    test: "On the fleet network run `uv run scripts/serial_mac_audit.py`"
    expected: "Transient progress bar on stderr during the sweep, then a colour-coded table (green identical / yellow off-by-one / red mismatch / dim unknown) and the 'Correlation by product + firmware' panel; a known gen3 device shows derived_mac differing from serial by +1 in the final octet"
    why_human: "Requires ~73 real LIFX devices on the operator's L2 segment; the sweep cannot run in verification without hardware"
  - truth: "`--csv` mode emits ONLY CSV rows on stdout so `--csv > file` pipes cleanly"
    test: "Run `uv run scripts/serial_mac_audit.py --csv > /tmp/audit.csv` on the fleet network, then `head /tmp/audit.csv`"
    expected: "Progress appears on stderr only; the file contains just the CSV_COLUMNS header row and data rows — no Rich chrome or progress fragments"
    why_human: "stdout/stderr separation is structurally sound in the code (csv.writer is the only stdout writer; Progress is bound to Console(stderr=True)), but clean-pipe behaviour under a live Rich Progress render needs a real run"
  - truth: "A device that fails to answer, or has no/incomplete ARP entry, produces a row with verdict unknown instead of aborting the sweep"
    test: "During the fleet run, confirm quiesced/dead devices appear as dim 'unknown' rows and the sweep completes"
    expected: "Sweep finishes with unknown rows for non-responders; no traceback, no aborted run"
    why_human: "The try/except LifxError + finally-close + gather(return_exceptions=True) path is present and wired, but no hardware-free test can exercise a real device timing out mid-probe"
human_verification:
  - test: "Fleet sweep (Task 3 checkpoint, step 1): `uv run scripts/serial_mac_audit.py` on the ~73-device network"
    expected: "Progress bar on stderr, colour-coded verdict table, 'Correlation by product + firmware' summary panel; gen3 spot-check shows off-by-one verdict where the library rule predicts it"
    why_human: "Requires the operator's physical LIFX fleet — blocking checkpoint:human-verify gate in the plan"
  - test: "Clean CSV pipe (Task 3 checkpoint, step 2): `uv run scripts/serial_mac_audit.py --csv > /tmp/audit.csv` then `head /tmp/audit.csv`"
    expected: "File contains only the header row and CSV data rows; all progress/warnings appeared on stderr"
    why_human: "Live Rich Progress + stdout redirection interaction can only be observed at runtime"
  - test: "Failure isolation (Task 3 checkpoint, implicit): observe quiesced/dead devices during the sweep"
    expected: "Non-responders yield dim 'unknown' rows; the run never aborts on a single silent device"
    why_human: "Needs real devices that time out; not reproducible hardware-free"
---

# Quick Task 260726-42c: Serial/MAC Correlation Audit Script — Verification Report

**Task Goal:** Create a script that enumerates MAC address and serial number along with LIFX product type and firmware version, to correlate which products and firmware versions have an off-by-one serial-to-MAC relationship and which have serial == MAC.
**Verified:** 2026-07-26
**Status:** human_needed — all automated must-haves verified; Task 3 blocking human checkpoint (real fleet sweep) legitimately outstanding
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Sweep prints Rich table (serial, derived_mac, real_mac, verdict, product_id, product_name, firmware, ip) plus summary panel grouped by product + firmware | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `CSV_COLUMNS` (lines 52-61) matches the locked set exactly; `render_results()` (322-341) builds the table in that order; `build_summary_panel()` (303-319) groups `Counter` by `(product_name, firmware)` per verdict. Rendering against a real fleet is the Task 3 checkpoint. |
| 2 | `--csv` emits only CSV on stdout; all Rich chrome on Console(stderr=True) in both modes | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `write_csv()` (295-300) uses stdlib `csv.writer(sys.stdout)` and is the sole stdout writer in `--csv` mode; `err_console = Console(stderr=True)` (437) owns `Progress(console=err_console, transient=True)` (247) and all warnings; the trailing reminder (454-457) is on stderr. Clean-pipe behaviour under a live run is checkpoint step 2. |
| 3 | Verdict classifies identical / off-by-one / mismatch / unknown with both MACs normalised to zero-padded lowercase octets before comparison | ✓ VERIFIED | `classify_verdict()` (160-180) normalises via `normalise_mac()` before comparing; `--self-test` ran during verification, exit 0, covering unpadded octets (`00:00:5e:00:53:e`), wraparound `(0xff+1)%256`, +2 rejection, non-final-octet mismatch, and None→unknown. |
| 4 | Script imports lifx from the LOCAL checkout via PEP 723 `[tool.uv.sources]` editable path; pyproject.toml untouched | ✓ VERIFIED | PEP 723 block (lines 2-8) pins `lifx-async = { path = "../", editable = true }`; self-test assertion (384-391) proves `lifx.__file__` resolves to `<repo>/src/lifx/__init__.py` and PASSED in this verification run; `git diff --quiet d52c856 HEAD -- pyproject.toml uv.lock` exits 0; working tree clean apart from `.planning/quick/`. |
| 5 | A device that fails to answer, or has no/incomplete ARP entry, produces verdict unknown instead of aborting the sweep | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `_probe()` (198-240) initialises every row as `verdict="unknown"`, wraps the probe in `try/except LifxError`, closes the connection in `finally`, always appends the row; `_sweep()` backstops with `gather(return_exceptions=True)` (263); `main()` (444-446) only reclassifies when `derived_mac` is non-empty, so failed probes stay unknown even with an ARP entry. No hardware-free test exercises a real mid-probe timeout — folded into the fleet run. |
| 6 | `--self-test` exercises normalisation, ARP parsing, and verdict logic against fixtures (macOS arp line shapes, private-range addresses) with zero hardware, exiting 0 | ✓ VERIFIED | Ran `uv run scripts/serial_mac_audit.py --self-test` during verification: "Self-test passed: all assertions OK.", exit 0. `ARP_FIXTURE_DARWIN` reproduces the 4-line capture's shapes with placeholder addresses; assertions cover the `(incomplete)` skip and duplicate-IP first-wins (363-368). |

**Score:** 3/6 truths verified (3 present + wired, behaviour awaiting the operator's fleet run — all three map directly onto the Task 3 blocking human checkpoint)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `scripts/serial_mac_audit.py` | Standalone PEP 723 diagnostic, single file | ✓ VERIFIED | 461 lines, substantive (pure core + sweep + output, no stubs); runs via `uv run` (`--help` and `--self-test` both exit 0, proving the PEP 723 env resolves rich + editable local lifx); all imports at top per CLAUDE.md; Australian English (`normalise_mac`, "colour-coded"). |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| PEP 723 block | local `src/lifx` | `[tool.uv.sources]` editable path `"../"` | ✓ WIRED | Self-test assertion on `lifx.__file__` passed in this run — proven at import time, not claimed. |
| Per-device probe | derived_mac | `get_version()` + `get_host_firmware()` then cached `get_mac_address()` | ✓ WIRED | `_probe()` issues exactly those two requests; `src/lifx/devices/base.py:666-683` confirms `get_mac_address()` reuses `self._host_firmware` and caches `_mac_address` — no third packet. |
| Single `arp -an` snapshot | real_mac + verdict | `read_arp_table()` → `parse_arp_darwin()` → `arp_map.get(row.ip)` | ✓ WIRED | Called exactly once in `main()` after `_sweep()` completes; fixed argv list, no shell; strict regex + `_is_valid_mac` shape guard (T-Q42C-01 mitigation); Linux `/proc/net/arp` + `ip neigh` fallback present as the bonus path. |
| Console(stderr=True) | Progress in both modes | `Progress(console=err_console)` | ✓ WIRED | Line 247; `csv.writer(sys.stdout)` is the only stdout writer in `--csv` mode; the human-mode `Console()` (324) is only reached in the non-CSV branch. |

### Behavioral Spot-Checks

| Behaviour | Command | Result | Status |
| --------- | ------- | ------ | ------ |
| Self-test passes hardware-free | `uv run scripts/serial_mac_audit.py --self-test` | "Self-test passed: all assertions OK.", exit 0 | ✓ PASS |
| PEP 723 env resolves at import | `uv run scripts/serial_mac_audit.py --help` | Usage + epilog with responders-only caveat, exit 0 | ✓ PASS |
| Lint/format clean | `uv run ruff check` + `uv run ruff format --check` | "All checks passed!" / "1 file already formatted" | ✓ PASS |
| Zero-dependency surface untouched | `git diff --quiet d52c856 HEAD -- pyproject.toml uv.lock` | exit 0 | ✓ PASS |
| Fleet sweep / CSV pipe / failure isolation | — | Requires real hardware | ? SKIP → human checkpoint |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| QUICK-260726-42c | 260726-42c-PLAN.md | Serial/MAC/product/firmware correlation script | ? NEEDS HUMAN | All buildable evidence satisfied; the correlation dataset itself requires the operator's fleet run (Task 3). |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | None | — | No TBD/FIXME/XXX/TODO markers. The single grep hit for "placeholder" (line 86) is docstring prose describing the dim-dash rendering of a missing real_mac, not a stub. `# nosec B404/B603/B607` markers carry adjacent justification comments matching the plan's T-Q42C-01 mitigation and the documented SUMMARY deviation. |

### Human Verification Required

These are the Task 3 blocking checkpoint items from the plan — legitimately outstanding, not gaps.

### 1. Fleet sweep renders correctly

**Test:** On the fleet network (~73 devices): `uv run scripts/serial_mac_audit.py`
**Expected:** Transient progress bar on stderr; colour-coded table (green identical / yellow off-by-one / red mismatch / dim unknown); "Correlation by product + firmware" panel. Spot-check a known gen3 device: derived_mac differs from serial by +1 in the final octet and verdict reads off-by-one if the library rule is right for it.
**Why human:** Requires the physical LIFX fleet on the operator's L2 segment.

### 2. CSV pipe stays clean

**Test:** `uv run scripts/serial_mac_audit.py --csv > /tmp/audit.csv` then `head /tmp/audit.csv`
**Expected:** Progress still on stderr; the file contains ONLY the header row and CSV data rows — no Rich chrome or progress fragments.
**Why human:** Live Rich Progress + redirection interaction is runtime-only.

### 3. Failure isolation on real non-responders

**Test:** Observe quiesced/dead devices during the sweep (optionally re-run — single rounds under-count, median 48/73).
**Expected:** Non-responders appear as dim unknown rows; the sweep never aborts.
**Why human:** Needs real devices timing out mid-probe.

### Gaps Summary

No gaps. Everything verifiable without hardware is verified against the actual code and by running the plan's automated verification commands in this session (not trusted from SUMMARY.md): self-test exit 0 including the local-checkout import proof, `--help` exit 0, ruff clean, pyproject.toml/uv.lock untouched, all three claimed commits (`1ada1f9`, `120e949`, `d3b4fcd`) present in history touching only `scripts/serial_mac_audit.py`. The sole outstanding item is the plan's own blocking `checkpoint:human-verify` (Task 3): the real-fleet sweep that produces the correlation dataset. Resume signal per the plan: "approved" or a description of issues.

---

_Verified: 2026-07-26_
_Verifier: Claude (gsd-verifier)_

---

## Fleet Run Sign-Off — 2026-07-26

Operator signed off the Task 3 `checkpoint:human-verify` gate. The three previously
human-blocked truths were all exercised against the production fleet:

| Truth | Result |
|-------|--------|
| Broadcast sweep renders the Rich table + correlation summary panel | Verified — 31 responders, colour-coded verdicts, summary grouped by product + firmware |
| `--csv` emits only CSV on stdout | Verified — `--csv > /tmp/audit.csv` produced header + data rows only; progress stayed on stderr |
| Non-responders degrade to `unknown` without aborting the sweep | Verified — sweep completed across repeated rounds with no traceback |

Two rendering defects were found by the run and fixed in `0f5b228` before sign-off:
the progress bar oscillated between 100% and ~96% once per device (running `total`
set inside the discovery loop), and every table column ellipsised — including both
off-by columns in the summary panel, which rendered identically as `off-by-…`.

### Audit finding

`get_mac_address()` disagreed with the real ARP MAC on 2 of 31 graded devices: LIFX
Tiles on firmware 3.50, whose real MAC equalled their serial while the
`version_major == 3` rule predicted serial + 1. All other 3.x responders were 3.90
and genuinely off-by-one.

Corrected rule (supplied by LIFX, via the operator -- vendor-stated, not inferred
from the sweep): the offset requires
`version_major == 3 and version_minor >= 70`. Applied to `src/lifx/devices/base.py`
in `f625afd`, with a parametrised boundary test covering 3.9, 3.50, 3.69, 3.70,
3.90, 3.255, 4.90 and 2.90. Full suite: 2625 passed.

Note the integer comparison — minor `9` is below minor `70`, so reading the version
as a decimal would misclassify 3.9. The boundary test pins this.
