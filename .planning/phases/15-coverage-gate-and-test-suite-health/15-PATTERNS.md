# Phase 15: Coverage Gate and Test-Suite Health - Pattern Map

**Mapped:** 2026-09-05
**Files analysed:** 14 (5 moved scripts, 1 relocated CI tool, 4 relocated test files, 1 new conftest.py, 3 config files, 1 new CI guard)
**Analogs found:** 13 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `.planning/scripts/serial_mac_audit.py` (moved, unchanged) | utility/CLI (operator tooling) | file-I/O | itself (git mv) | exact |
| `.planning/scripts/measurement_support.py` (moved, unchanged) | utility (shared primitives) | file-I/O | itself (git mv) | exact |
| `.planning/scripts/ipv6_thread_probe.py` (moved, import edited) | utility/CLI (operator tooling) | file-I/O | `scripts/serial_mac_audit.py` for PEP 723 header shape | role-match |
| `.planning/scripts/measure_merged_discovery.py` (moved, import edited) | utility/CLI (operator tooling) | file-I/O | `scripts/serial_mac_audit.py` | role-match |
| `.planning/scripts/thread_revalidation.py` (moved, import edited) | utility/CLI (operator tooling) | file-I/O | `scripts/serial_mac_audit.py` | role-match |
| `.github/check_patch_coverage.py` (moved, unchanged) | utility/CLI (maintainer CI tooling) | batch (diff + coverage.xml intersection) | itself (git mv) | exact |
| `.planning/scripts/tests/conftest.py` (new) | config/fixture (sys.path bootstrap) | request-response (import hook) | none — new mechanism (D-05) | no analog |
| `.planning/scripts/tests/test_check_patch_coverage.py` (moved) | test | batch | itself (git mv) | exact |
| `.planning/scripts/tests/test_ipv6_thread_probe.py` (moved) | test | batch | itself (git mv) | exact |
| `.planning/scripts/tests/test_measure_merged_discovery.py` (moved) | test | batch | itself (git mv) | exact |
| `.planning/scripts/tests/test_thread_revalidation.py` (moved) | test | batch | itself (git mv) | exact |
| `.github/workflows/ci.yml` (guard step added) | config (CI step) | request-response (reads coverage.xml + GH status API) | `.github/workflows/ci.yml:193` (`LIFX_REQUIRE_IPV6` designated-cell pattern) | role-match |
| `.github/patch_coverage_guard.py` (new, Claude's discretion on name/location) | utility/CLI (CI guard) | batch (diff/coverage/status intersection) | `.github/check_patch_coverage.py` (import target, not reimplementation) | role-match |
| `pyproject.toml` (testpaths/pythonpath/markers/`--cov`/pyright include edits) | config | — | itself, edited in place | exact |
| `AGENTS.md` (invocation docs + measured-tree rule) | config/doc | — | itself, edited in place | exact |

## Pattern Assignments

### `.planning/scripts/ipv6_thread_probe.py`, `measure_merged_discovery.py`, `thread_revalidation.py`

**Analog for PEP 723 header:** `scripts/serial_mac_audit.py` lines 1-7 (already git-tracked, verify with `git ls-files -- scripts/serial_mac_audit.py`):

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=15.0.0", "lifx-async"]
#
# [tool.uv.sources]
# lifx-async = { path = "../", editable = true }
# ///
```

For the three relocated scripts, per D-03, the `[tool.uv.sources]` path must be adjusted for the
new depth (`.planning/scripts/` is one level deeper than `scripts/` was, relative to repo root):

```python
# [tool.uv.sources]
# lifx-async = { path = "../../", editable = true }
```

Per D-03, each of the four scripts lacking a header (only `serial_mac_audit.py` currently has
one) gains this block, with its own `dependencies` list reflecting actual imports (5-15 `lifx`
imports per script — enumerate via existing `import lifx...` / `from lifx...` lines already in
each file rather than guessing).

**Import pattern to change (D-01), flat sibling import instead of package-qualified:**

Current (`scripts/ipv6_thread_probe.py` line ~101):
```python
from scripts.measurement_support import CapturedState, restore_and_verify_device_state
from scripts.measurement_support import capture_device_state as _capture_device_state
```

Current (`scripts/measure_merged_discovery.py` line ~41):
```python
from scripts.measurement_support import (
    _capture_discovery_observations,
    _DiscoveryObservation,
)
```

Current (`scripts/thread_revalidation.py` line ~46):
```python
from scripts.measurement_support import (
    ANIMATION_SCHEDULE,
    DISCOVERY_ROUNDS,
    REQUEST_TRIALS,
    STALENESS_CAP_S,
    STALENESS_CONFIRM_ABSENT_POLLS,
    STALENESS_POLL_INTERVAL_S,
    CapturedState,
    RestoreOutcome,
    _capture_request_observations,
)
```

New form for all three (drop the `scripts.` prefix — flat import relies on `sys.path[0]` being
the script's own directory when run directly, per D-01):
```python
from measurement_support import CapturedState, restore_and_verify_device_state
from measurement_support import capture_device_state as _capture_device_state
```
```python
from measurement_support import (
    _capture_discovery_observations,
    _DiscoveryObservation,
)
```
```python
from measurement_support import (
    ANIMATION_SCHEDULE,
    DISCOVERY_ROUNDS,
    REQUEST_TRIALS,
    STALENESS_CAP_S,
    STALENESS_CONFIRM_ABSENT_POLLS,
    STALENESS_POLL_INTERVAL_S,
    CapturedState,
    RestoreOutcome,
    _capture_request_observations,
)
```

All other imports (the `lifx.*`, `lifx_emulator.*`, stdlib imports already at the top of these
three files) are unchanged by the move — only the `scripts.measurement_support` lines change.

**Do not touch:** `scripts/generate_theme_data.py` stays exactly where it is — it is the one file
the target state names as remaining in `scripts/`, and `tests/test_theme/test_theme_generator.py:36`
depends on `import generate_theme_data` resolving through the unchanged `pythonpath` entry
(D-02).

---

### `.planning/scripts/measurement_support.py`

Moves unchanged (git mv only) — it has no `scripts.`-prefixed self-import to fix, per D-01/D-02
it is the shared sibling module the other three import flatly.

---

### `.github/check_patch_coverage.py`

Moves unchanged (git mv) — its own imports are pure stdlib (`argparse`, `subprocess`, `pathlib`,
etc. — see lines 1-16 above) with no `scripts.` self-reference, so nothing internal to the file
needs editing. External references to its old path (`scripts/check_patch_coverage.py`) inside
GSD phase plan files under `.planning/milestones/` are historical records and are explicitly
**not** rewritten (SPEC boundary). Any reference in a currently active/non-archived location
(e.g. a future plan template) must be updated to `.github/check_patch_coverage.py`.

---

### `.planning/scripts/tests/conftest.py` (new file, D-05)

No existing analog — this is a new mechanism. Its sole job is to make `.planning/scripts` importable
during collection since the relocated tests import rather than execute their subjects (so
`sys.path[0]` does not help, unlike direct script execution). Pattern to follow, styled on the
existing `tests/conftest.py` module docstring convention (see `tests/conftest.py:1`, `"""Shared
fixtures for all tests."""`):

```python
"""Path bootstrap for tooling tests importing their .planning/scripts subjects."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
```

Scope this conftest strictly to `.planning/scripts/tests/` (D-05: "confines it to the tooling
tests, which are excluded by default anyway").

**The scope of that prohibition, corrected after cross-AI review round 2.** This paragraph
previously read "do not add anything to the root `tests/conftest.py` or to `pyproject.toml`'s
`pythonpath` for this purpose", and an executor could read it as binding on plan 15-02's task 3,
which deliberately does add a `.planning/scripts` insert to the root `tests/conftest.py`. The two
are not the same purpose and only one of them is prohibited:

- **Prohibited, and this is what D-05 is about.** Do not bootstrap the *tooling tests'* subject
  imports from the root `tests/conftest.py` or from `pyproject.toml`'s `pythonpath`. The tooling
  tests get their path from the conftest beside them, so the mechanism stays confined to the
  directory it serves.
- **Required, and owned by plan 15-02 task 3.** Two *library* tests in the default suite,
  `tests/test_discovery_observation.py` and `tests/test_network/test_connection_retry.py`, import
  `measurement_support` because they exercise the request and discovery observation seams through
  it. A targeted single-file invocation such as
  `uv run --frozen pytest tests/test_network/test_connection_retry.py` suppresses `testpaths`, so
  the tooling conftest is never loaded and those two imports fail. The root `tests/conftest.py`
  is the only placement pytest loads under every documented invocation, so the insert goes there.
  That is still test infrastructure rather than a `pythonpath` entry, so D-02 and D-05 both
  continue to hold.

`pyproject.toml`'s `pythonpath` gains nothing for either purpose. That part of the prohibition is
unchanged.

---

### `.planning/scripts/tests/test_*.py` (four files, moved with `pytestmark`, D-11)

**Analog:** existing test-marking convention. The repo's `benchmark` marker
(`pyproject.toml` markers list, line ~144-148) is applied per-test via `@pytest.mark.benchmark`
decorators today; D-11 instead specifies **module-level** `pytestmark` for greppability. Add to
the top of each of the four relocated test files, immediately after the module docstring and
imports:

```python
pytestmark = pytest.mark.tooling
```

**Marker registration pattern** — analog is the existing `markers` list in
`pyproject.toml` (`[tool.pytest.ini_options]`, current lines ~144-148):

```python
markers = [
    "emulator: tests that require the lifx-emulator-core embedded emulator",
    "targeted_ipv6_windows: focused targeted-IPv6 test enabled on Windows CI",
    "benchmark: performance benchmark tests — run with -m benchmark to measure baselines",
]
```

New entry to add (D-10 names it `tooling`). Plan 15-01 task 1 owns the exact string, and this is
it verbatim, so copying it from here cannot introduce a variant. Note that it names the
`--tooling` flag rather than a marker expression, and that it carries no em dash: the sample above
quotes the *existing* `benchmark` description, which does contain one today and which 15-01
rewrites in the same edit.
```python
    "tooling: relocated hardware and CI tooling tests under .planning/scripts/tests, run with --tooling",
```

---

### Deselection mechanism (D-09) — extends `tests/conftest.py`

**Analog:** `tests/conftest.py`'s existing `pytest_collection_modifyitems` hook (current lines
~140-158 as read above):

```python
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply focused retry and timeout policies before plugin defaults."""
    targeted_retry = targeted_ipv6_retry_policy(sys.platform)
    for item in items:
        if (
            targeted_retry is not None
            and item.get_closest_marker("targeted_ipv6_windows") is not None
        ):
            item.add_marker(pytest.mark.flaky(**targeted_retry))

        uses_emulator = item.get_closest_marker("emulator") is not None or (
            hasattr(item, "fixturenames")
            and _EMULATOR_FIXTURES & set(item.fixturenames)
        )
        if uses_emulator and item.get_closest_marker("timeout") is None:
            item.add_marker(pytest.mark.timeout(_EMULATOR_TIMEOUT))
```

D-09 extends this same hook (not a new one — it already exists and already does conditional,
marker-driven item mutation) to deselect items carrying the `tooling` (and post-migration
`benchmark`) marker unless the corresponding `--tooling`/`--benchmark` flag was passed. The
flags must be registered through the `pytest_addoption` hook that already exists in the same
`tests/conftest.py` at line 105, where it registers `--disable-emulator`. Extend that hook rather
than adding a second one; two `pytest_addoption` definitions in one module would shadow each other
and only the last would register:

```python
def pytest_addoption(parser: pytest.Parser) -> None:
    """Register opt-in flags for categories deselected by default."""
    parser.addoption(
        "--tooling", action="store_true", default=False,
        help="run relocated tooling tests under .planning/scripts/tests",
    )
    parser.addoption(
        "--benchmark", action="store_true", default=False,
        help="run performance benchmark tests",
    )
```

Then inside `pytest_collection_modifyitems`, using `pytest.Config.hook.pytest_collection_modifyitems`'s
existing `config` access pattern (via `item.config`) or an added `config: pytest.Config` parameter,
add a deselect branch alongside the existing retry/timeout branches, using `items[:] = ...` or
`config.hook.pytest_deselected(items=...)` the way pytest's own `-k`/`-m` filtering does internally.
Model on `pytest`'s documented `pytest_collection_modifyitems(config, items)` signature — the
existing hook here only takes `items`, so the signature itself needs the `config` parameter added
in the same edit that adds the flags.

**`addopts` change:** remove `-m "not benchmark"` (current `pyproject.toml` line ~127) entirely,
since D-09 replaces `-m` negation with the flag-based hook. No `-m` expression remains in
`addopts` afterward.

---

### `pyproject.toml` — `testpaths`, `pythonpath`, `--cov`, `[tool.pyright] include`

**Current state (all read directly, lines cited above):**

```toml
testpaths = ["tests"]
pythonpath = ["src", "scripts"]
```
```toml
    --cov=lifx
    --cov=generate_theme_data
    --cov=scripts.measurement_support
    --cov=scripts.thread_revalidation
```
```toml
include = [
    "src",
    "scripts/generate_theme_data.py",
    "scripts/measurement_support.py",
    "scripts/thread_revalidation.py",
    "scripts/measure_merged_discovery.py",
    "scripts/ipv6_thread_probe.py",
]
```

**Target state per SPEC R2/R3, D-02, D-12:**

```toml
testpaths = ["tests", ".planning/scripts/tests"]
pythonpath = ["src", "scripts"]  # unchanged — generate_theme_data.py still needs it (D-02)
```
```toml
    --cov=lifx
    --cov=generate_theme_data
```
```toml
include = [
    "src",
    "scripts/generate_theme_data.py",
]
```

The comment above `[tool.pyright] include` (current lines 92-98) referencing the "Phase 14
measurement scripts" must be rewritten or removed since those scripts no longer live under
`scripts/` and are no longer pyright-included from this project's config (they move with their
own project context under `.planning/scripts/` — confirm during planning whether pyright still
type-checks them there or whether that responsibility now lives implicitly with `ruff`/manual
review, per SPEC's silence on pyright coverage of the relocated tree).

---

### `AGENTS.md` — invocation docs and measured-tree rule

**Current pattern to replace** (from `AGENTS.md`, "Running the measurement scripts" section):

```markdown
uv run --frozen python -m scripts.thread_revalidation <subcommand>
uv run --frozen python -m scripts.ipv6_thread_probe
uv run --frozen python -m scripts.measure_merged_discovery
```

with the accompanying explanation:

> `from scripts.measurement_support import ...` resolves only when the repository root is on
> `sys.path`. `python -m` puts it there; running the file directly puts `scripts/` there
> instead and fails with `ModuleNotFoundError: No module named 'scripts'`.

**New form (D-04):**

```markdown
uv run .planning/scripts/thread_revalidation.py <subcommand>
uv run .planning/scripts/ipv6_thread_probe.py
uv run .planning/scripts/measure_merged_discovery.py
```

The `python -m` explanation paragraph is retired in full — replace with a note that these are
now PEP 723 standalone scripts run directly, resolving `measurement_support` via `sys.path[0]`.

**New measured-tree rule prose (R3), styled on existing AGENTS.md prose sections** (e.g. the
"Privacy and Hardware Identifiers" section's declarative style):

```markdown
## Measured Tree

Coverage measures the shipped library (`src/lifx`) plus any code a CI job executes
(`generate_theme_data.py`). Operator and maintainer tooling — anything under
`.planning/scripts/` or `.github/check_patch_coverage.py` — is never part of the measured
tree, regardless of its own test coverage.
```

Also update: the `scripts/serial_mac_audit.py` citation for the firmware 3.70+ MAC rule (in the
"Key Gotchas" section) to `.planning/scripts/serial_mac_audit.py`.

---

### `.github/workflows/ci.yml` — vacuous-gate guard step (R4)

**Analog for cell-designation pattern:** the existing `LIFX_REQUIRE_IPV6` step comment (current
lines ~185-190, reproduced above) already documents and reuses the same
`matrix.os == 'ubuntu-latest' && matrix.python-version == '3.10'` designated cell. D-07 reuses
this identical conditional for gating the new guard step. Insert the new step immediately after
"Upload coverage to Codecov" (which is the point `coverage.xml` is guaranteed present, per D-06)
and before "Upload test results to Codecov" or after both uploads — either is fine since the
guard only reads local `coverage.xml`, not the uploaded report:

```yaml
    - name: Guard against vacuous coverage gate
      if: ${{ !cancelled() && matrix.os == 'ubuntu-latest' && matrix.python-version == '3.10' }}
      run: uv run --frozen python .github/patch_coverage_guard.py --base ${{ github.event.pull_request.base.sha }}
```

Do not add `continue-on-error: true` or `|| true` (explicit prohibition, SPEC R4/prohibitions
table) — the step must be capable of failing the job exactly like the existing "Run unit tests"
step above it, which has no soft-fail wrapper.

---

### `.github/patch_coverage_guard.py` (new file — location/name at Claude's discretion, SPEC explicitly permits)

**Analog:** must import `.github/check_patch_coverage.py`'s intersection logic, not reimplement
it (SPEC R4, "reused... by importing the module"). Concretely reuse:
- `CoverageEntry` dataclass (executed/missing/excluded lines and branches) — see
  `check_patch_coverage.py` lines ~48-56
- Whatever function currently backs `check_coverage(base, coverage_path, sources)` (called from
  `run()` in the tail excerpt above) — import and call its line/branch intersection helper
  directly rather than duplicating the hunk-parsing regex (`HUNK_HEADER` pattern, line ~14) or
  the `AddedLine` dataclass (lines ~40-46).

Import shape:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_patch_coverage import CoverageEntry, PatchCoverageError  # + intersection helper
```

New logic this file owns and `check_patch_coverage.py` does not: deriving its own changed-file
set from `git diff --merge-base` (not accepting `--source` args, per SPEC "does not depend on
that tool's `--source` gap"), applying the R3 measured-tree filter (only `src/lifx/**` and
`generate_theme_data.py` count), and the GitHub combined-status cross-check via `gh api
repos/:owner/:repo/commits/:sha/status` or equivalent, matching against the two recorded
description forms:
- `r"(\d+(?:\.\d+)?)% of diff hit \(target (\d+(?:\.\d+)?)%\)"` (scored)
- `r"Coverage not affected when comparing \S+\.\.\.\S+"` (vacuous)

No test-file analog exists in-repo for a fixture-driven local-only CI guard test; model the new
test file on `tests/test_scripts/test_check_patch_coverage.py`'s existing fixture-and-subprocess
style (same directory, same author, same subject family) once relocated to
`.planning/scripts/tests/test_patch_coverage_guard.py` — do not add this new guard's tests to the
default-collected `tests/` tree, since it lives in `.github/` and its tests are, per D-11's
model, tooling tests deselected by default.

## Shared Patterns

### PEP 723 + `[tool.uv.sources]` editable path
**Source:** `scripts/serial_mac_audit.py` lines 1-7 (verified git-tracked)
**Apply to:** `ipv6_thread_probe.py`, `measure_merged_discovery.py`, `thread_revalidation.py`
after their move to `.planning/scripts/` — same block shape, `path = "../../"` instead of
`path = "../"` because of the extra directory nesting.

### Flat sibling import (no package prefix)
**Source:** D-01, applies uniformly across all three scripts
**Apply to:** every `from scripts.measurement_support import ...` line → `from measurement_support import ...`

### Conditional marker-driven item mutation in `pytest_collection_modifyitems`
**Source:** `tests/conftest.py` current `pytest_collection_modifyitems` (lines ~140-158)
**Apply to:** the new deselection branch for `tooling`/`benchmark` markers — extend, do not
replace, this existing hook.

### Designated always-present CI cell
**Source:** `.github/workflows/ci.yml` current `LIFX_REQUIRE_IPV6` step comment (~lines 185-190)
**Apply to:** the new guard step's `if:` condition (D-07) — identical `matrix.os ==
'ubuntu-latest' && matrix.python-version == '3.10'` predicate.

### `tests/test_pytest_policy.py` update (D-13)
**Source:** existing assertions on `addopts` at `tests/test_pytest_policy.py:76` (not yet read
in full — planner/executor must read this file directly before editing, since it is the
repository's own guard on pytest policy and must assert the new `-m`-free mechanism rather than
merely stop asserting the old `-m "not benchmark"` string).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `.planning/scripts/tests/conftest.py` | config/fixture | request-response (import hook) | New mechanism (D-05); no existing sys.path-bootstrap conftest exists anywhere in the repo — this is the first one |

## Metadata

**Analog search scope:** `scripts/`, `tests/conftest.py`, `tests/test_scripts/`, `pyproject.toml`,
`AGENTS.md`, `.github/workflows/ci.yml`, `.github/check_patch_coverage.py`
**Files scanned:** ~14 (all files named in SPEC R1/R2/R4 scope, plus their direct analogs)
**Pattern extraction date:** 2026-09-05
**Note on tracked-source gate:** All analog paths cited above (`scripts/serial_mac_audit.py`,
`tests/conftest.py`, `.github/workflows/ci.yml`, `.github/check_patch_coverage.py`,
`pyproject.toml`, `AGENTS.md`) are ordinary git-tracked source files at their current repository
locations, not gitignored mirrors — no `.gsd/capabilities/` or plugin-synced paths were used as
analogs.
