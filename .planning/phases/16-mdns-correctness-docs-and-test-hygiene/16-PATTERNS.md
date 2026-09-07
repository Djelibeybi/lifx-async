# Phase 16: mDNS Correctness, Docs and Test Hygiene - Pattern Map

**Mapped:** 2026-09-07
**Files analyzed:** ~34 (1 source module, 6 doc surfaces, 2 test-contract files, 1 new test module, `AGENTS.md`, `pyproject.toml`, plus 27 files swept for R4)
**Analogs found:** 6 / 6 named targets (R4's 27-file sweep is mechanical; no analog needed beyond the ruff-flagged sites themselves)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `src/lifx/network/discovery/mdns/discovery.py` (`selected_address_for`, guard extraction) | service (cache lookup) | request-response | same file, `_normalise_dns_name()` / `pending_targets()` guard block | exact (self-referential refactor) |
| `tests/test_docs_language.py` (new) | test | batch/transform (file walk + regex) | `tests/test_network/test_mdns/test_phase_contract.py::test_discovery_surfaces_use_only_documentation_safe_addresses` (+ `_normalised_prose`/`_count_prose_matches` helpers) | exact structural analogue |
| `tests/test_repository_guidance.py` (extend for D-09 AGENTS.md half) | test | transform | same file, `_SHARED_ARCHITECTURE_MARKERS` marker-tuple-plus-loop | exact (extend existing pattern in-file) |
| `tests/test_network/test_mdns/test_phase_contract.py` (phrase-list edits, advanced-usage half of D-09) | test | transform | same file — `approved_phrases` tuple (~121-143) and `_MOVED_MDNS_LIMITATION_PHRASES`/`_ADVANCED_USAGE_PATH` (~386-415) | exact (in-place edit) |
| `pyproject.toml` (`[tool.ruff.lint]`) | config | request-response (linter config) | same file, existing `select`/`per-file-ignores` block (~80-89) | exact |
| 27 files under `tests/` (R4 import-sweep) | test | transform (mechanical import hoist) | `tests/test_network/test_mdns/test_discovery.py` module-scope imports of `_discover_lifx_services_sweep` / `_LifxRecordCache` (proves the pattern is safe, no barrier) | exact (precedent within same package) |
| `docs/user-guide/discovery.md`, `docs/getting-started/quickstart.md`, `docs/migration/mdns-low-level-api-7.0.0.md`, `src/lifx/api.py` (`discover_mdns()` docstring), `docs/user-guide/advanced-usage.md` | doc/docstring | request-response (prose) | `docs/user-guide/discovery.md` Limitations section itself (~110-137) and `AGENTS.md:349-350` caching lists | exact (edit existing prose blocks) |

## Pattern Assignments

### `src/lifx/network/discovery/mdns/discovery.py` — `selected_address_for()` fix (R1, D-01/D-02/D-03)

**Analog:** the module's own established normalisation and guard patterns.

**Normalisation helper** (lines ~144-148):
```python
def _normalise_dns_name(name: str) -> str:
    """Canonicalise a DNS name without changing its label structure."""
    if name.endswith("."):
        name = name[:-1]
    return name.casefold()
```
Strips exactly **one** trailing dot — not idempotent. This is why D-01 requires a public/private split rather than a naive `owner = _normalise_dns_name(owner)` insert.

**Current defect** — `selected_address_for()` (lines ~347-357):
```python
def selected_address_for(self, owner: str) -> str | None:
    """Select a usable address without exposing same-class ordering."""
    owner = owner.lower()
    if (
        self._retained_payload_budget_exhausted
        or self._address_budget_exhausted
        or owner in self._address_overflowed_owners
        or (owner, DNS_TYPE_A) in self._byte_incomplete_owner_types
        or (owner, DNS_TYPE_AAAA) in self._byte_incomplete_owner_types
    ):
        return None
    return _pick_address(self._addresses_in_order(owner))
```
Copy this five-condition `if` block verbatim as the shape for the new private guard predicate that D-03 extracts (it takes an already-normalised owner and returns `bool`). The public `selected_address_for()` becomes: normalise via `_normalise_dns_name()`, then delegate to the private predicate + `_addresses_in_order()`.

**Duplicated guard in `pending_targets()`** (lines ~838-846) — the four-condition subset D-03 must reconcile with the five-condition set above (note: `pending_targets()` omits the `_retained_payload_budget_exhausted` check because that condition already causes an early `return targets` at the top of the method, lines ~816-817):
```python
if (
    self._address_budget_exhausted
    or target in self._address_overflowed_owners
    or (target, DNS_TYPE_A) in self._byte_incomplete_owner_types
    or (target, DNS_TYPE_AAAA) in self._byte_incomplete_owner_types
):
    continue
if self.selected_address_for(target) is not None:
    continue
targets.append(target)
```
`target` here is already normalised once, at the SRV-target normalisation site below — this is exactly the "internal caller already normalised" case D-01's rationale describes.

**Internal callers requiring the private (no-renormalise) path** — `discovery.py:788-789` (inside the main resolution loop):
```python
target = srv_endpoint[0]
addresses = self.addresses_for(target)
ip = self.selected_address_for(target)
```
and `discovery.py:845` (`pending_targets()`, shown above) — `target` comes from `_resolve_srv_endpoint()`, whose target was normalised at `discovery.py:657-659`:
```python
endpoints.add(
    (
        _normalise_dns_name(record.parsed_data.target),
        record.parsed_data.port,
    )
)
```
Both call sites should switch to calling the new private delegate directly (already-normalised owner) rather than the public `selected_address_for()`, to avoid the double-normalisation trap D-01's rationale describes.

**Ingest-side normalisation** (`_add_record`, ~line 400) — the other place `_normalise_dns_name()` is called, confirming the "normalise once at ingest, once at lookup" two-convention pattern:
```python
name = _normalise_dns_name(record.name)
```

**Naming convention observed in this module:** no existing `_leading_underscore` "public wrapper delegates to private twin" pair exists yet in `_LifxRecordCache` (methods like `_admit_owner`, `_add_record`, `_resolve_srv_endpoint`, `_reject` are private helpers called from public methods, but none currently mirrors a public method's name with a private counterpart, e.g. there's no `_records_for`/`records_for` pair). The closest naming precedent is `_addresses_in_order()` — a private helper already invoked by both `addresses_for()` and `selected_address_for()`. A reasonable name for D-01/D-03's new methods would follow that private-helper style (e.g. `_selected_address_for_normalised()` / `_owner_is_unusable()`), but there is no in-repo pair to copy verbatim — this is genuinely Claude's Discretion per CONTEXT.md.

---

### `tests/test_docs_language.py` (new, D-10) — repository-wide prose negative

**Analog:** `tests/test_network/test_mdns/test_phase_contract.py`

**Helpers to reuse/mirror** (lines 62-76):
```python
def _normalised_prose(relative_path: Path) -> str:
    """Return prose with headings and comments excluded from negative checks."""
    text = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    prose_lines = (
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return " ".join(" ".join(prose_lines).split()).casefold()


def _count_prose_matches(relative_path: Path, pattern: str) -> int:
    """Count semantic matches only in normalised, non-comment prose."""
    return len(re.findall(pattern, _normalised_prose(relative_path)))
```
`_normalised_prose` is `.md`-shaped (strips `#`-heading lines and HTML comments). For the new module's `.py` walk under `src/`, either normalise similarly (skip `#`-comment lines, since Python comments also start with `#`) or just scan raw file text — D-10 explicitly leaves this to discretion (CONTEXT.md D-10/`## Claude's Discretion`).

**Structural walk-and-assert analogue** (lines 367-380):
```python
def test_discovery_surfaces_use_only_documentation_safe_addresses(self) -> None:
    """No raw/live identifier or private-infrastructure example reaches
    the canonical guide or its executable source."""
    private_ipv4_patterns = (
        r"\b192\.168\.\d{1,3}\.\d{1,3}\b",
        r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b",
    )

    for relative_path in (_DISCOVERY_GUIDE_PATH, _PROGRESSIVE_EXAMPLE_PATH):
        text = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for pattern in private_ipv4_patterns:
            assert not re.search(pattern, text), (
                f"private-looking IPv4 literal found in {relative_path}"
            )
```
For `tests/test_docs_language.py`, replace the fixed two-path tuple with a `Path("src").rglob("*.py")` / `Path("docs").rglob("*.md")` walk, excluding `docs/changelog.md` by name with an inline comment (per D-10, satisfies P7 structurally). Assert `"proven synthetically"` and `"mesh scale"` (casefolded) appear in zero files.

**Placement note:** does NOT carry the Phase 15 opt-in tooling marker (D-11) — no `@pytest.mark.tooling`-style decorator; it runs in the default suite. Check `tests/conftest.py`'s deselection hook (mentioned in AGENTS.md) only applies to `.planning/scripts/tests/` and `benchmark`-marked tests — this new module is unmarked and unaffected.

---

### `tests/test_repository_guidance.py` — D-09 `AGENTS.md` third-category assertion

**Analog:** same file, `_SHARED_ARCHITECTURE_MARKERS` pattern (lines 24-34):
```python
_SHARED_ARCHITECTURE_MARKERS = (
    "## Architecture",
    "### Layered Architecture (Bottom-Up)",
    "### Device Capabilities Matrix",
    "### Exception Hierarchy",
    "### Key Design Patterns",
    "### State Caching",
    "## Common Patterns",
    "### Key Gotchas",
    "### Concurrency Considerations",
)
```
used with a loop-based assertion (lines ~49-55):
```python
def test_claude_md_does_not_duplicate_shared_architecture_guidance(
    self,
) -> None:
    text = _read(_CLAUDE_PATH)
    for marker in _SHARED_ARCHITECTURE_MARKERS:
        assert marker not in text, (
            f"{marker!r} duplicated in CLAUDE.md; it belongs in AGENTS.md only"
        )
```
For D-09's new assertion, add a tuple of the three category markers/labels (cached-semi-static, never-cached-volatile, derived-not-cached) and assert `connectivity` (or the exact bullet text naming it) appears in exactly one category's bullet list — count occurrences across the three, assert `== 1`. `_read()` (line 37) is the file-loading helper to reuse.

**Target text today** (`AGENTS.md:349-350`, under `## Common Patterns` → `### State Caching`):
```
- Cached (semi-static): `label`, `version`, `host_firmware`, `wifi_firmware`, `location`, `group`, `hev_config`, `hev_result`, `zone_count`, `multizone_effect`, `tile_chain`, `tile_count`, `tile_effect`
- **Never cached** (volatile): `power`, `color`, `hev_cycle`, `zones`, `tile_colors`, `ambient_light_level` — always use `get_*()` methods
```
D-09/R2 adds a third bullet (naming/position at Claude's discretion) for `connectivity`.

---

### `tests/test_network/test_mdns/test_phase_contract.py` — phrase-list edits (D-12, R3)

**Site 1 — required phrase** (`approved_phrases` tuple, lines 121-137, inside `test_public_guidance_uses_the_approved_limitation_phrases`):
```python
approved_phrases = (
    "ephemeral source port",
    "legacy-unicast replies",
    "does not join the multicast group",
    "does not receive unsolicited announcements",
    "does not authenticate or correlate responders",
    "mesh scale is proven synthetically",   # <- REMOVE, replace per D-13
    "A DNS AAAA record cannot carry that ID",
    "use `discover()` as the compatibility fallback",
    "schedules re-broadcasts 0.6, 1.8, 3.6, 5.6 and 7.6 seconds later",
    "they are not scaled to the requested discovery timeout",
    "a due re-broadcast is sent only while discovery remains active",
    "does not extend the overall timeout",
)
```
Existing phrase style to match for D-16's new entries: short distinctive fragments, not full sentences (`"does not join the multicast group"`, `"does not authenticate or correlate responders"`).

**Site 2 — forbidden phrase** (`_MOVED_MDNS_LIMITATION_PHRASES`, lines 391-395, class `TestPhase14DiscoveryLinkingContract`):
```python
_MOVED_MDNS_LIMITATION_PHRASES = (
    "does not join the multicast group",
    "does not receive unsolicited announcements",
    "mesh scale is proven synthetically",   # <- REMOVE, replace per D-13
)
```
used at lines ~407-410:
```python
for phrase in self._MOVED_MDNS_LIMITATION_PHRASES:
    assert phrase not in prose, (
        f"{phrase!r} still duplicated in {self._ADVANCED_USAGE_PATH}"
    )
```
`_ADVANCED_USAGE_PATH = Path("docs/user-guide/advanced-usage.md")` (class attribute, line ~389). Both sites 1 and 2 must move together in the same commit (D-12) or the suite goes red — site 1 requires the phrase present in `discovery.md`, site 2 forbids it in `advanced-usage.md`; deleting the sentence without updating both breaks one or the other.

---

### `pyproject.toml` — D-05 ruff `PLC0415` enablement

**Current state** (lines 80-89):
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = []

[tool.ruff.lint.per-file-ignores]
"src/lifx/{protocol,products}/generator.py" = ["E501"]
"src/lifx/protocol/packets.py" = ["E501"]
"src/lifx/products/registry.py" = ["E501"]
"benchmarks/*.py" = ["E501"]
"tests/benchmarks/*.py" = ["E501"]
```
D-05's edit: add `"PLC0415"` to `select`, then add five new `per-file-ignores` entries (one glob per excluded path) for `src/**`, `.planning/**`, `tests/test_animation/**`, `tests/test_theme/**`, `tests/test_devices/test_multizone.py`, each ignoring `["PLC0415"]`. Follow the existing per-file-ignore glob style shown above (path key → list of rule codes).

---

### R4 import sweep — analog for "safe to hoist" cases

**Analog:** `tests/test_network/test_mdns/test_discovery.py` module header already imports at module scope:
```python
from lifx.network.discovery.mdns.discovery import (
    _discover_lifx_services_sweep,
    _LifxRecordCache,
    ...
)
```
while 50 functions in the same file import `_discover_lifx_services` and `discover_devices_mdns` from the identical module *inside* the function body — proving, per CONTEXT.md's "Established Patterns" section, that no circular-import barrier exists for those 50 and the function-local form is habit, not constraint. Use this file as the reference precedent when justifying a hoist elsewhere: if a same-module sibling import already sits at module scope with no import-time side effect problem, the local one can hoist too.

**D-06 retained-import comment convention** — no existing `# noqa: PLC0415` comments exist yet in the repo to copy (rule is not currently enabled). The required shape per D-06/D-07:
```python
from x import y  # noqa: PLC0415: <named circular-import or patching reason>
```
A bare `# noqa: PLC0415` with no reason is prohibited (D-06, P6).

---

## Shared Patterns

### Prose-comparison helper (`_normalised_prose` / `_count_prose_matches`)
**Source:** `tests/test_network/test_mdns/test_phase_contract.py:62-76`
**Apply to:** `tests/test_docs_language.py` (new), and any phrase-list assertions touched in `test_phase_contract.py` itself.

### Marker-tuple-plus-loop assertion shape
**Source:** `tests/test_repository_guidance.py:24-55`
**Apply to:** D-09's `AGENTS.md` three-category assertion.

### Ruff per-file-ignore glob style
**Source:** `pyproject.toml:84-89`
**Apply to:** D-05's five new ignore entries.

### `_normalise_dns_name()` non-idempotence
**Source:** `src/lifx/network/discovery/mdns/discovery.py:144-148`
**Apply to:** any new code calling this helper — never call it twice on the same value.

## No Analog Found

None — every named file in CONTEXT.md's `<canonical_refs>` and `<code_context>` sections has a same-file or sibling-file analog, since this phase is entirely edits to existing files plus one new test module with a clear structural sibling.

## Answers to specific analog questions

1. **`tests/test_docs_language.py` analogue:** `test_discovery_surfaces_use_only_documentation_safe_addresses` (lines 367-380) plus `_normalised_prose`/`_count_prose_matches` (lines 62-76) — both excerpted above.
2. **D-09 `AGENTS.md` marker pattern:** `_SHARED_ARCHITECTURE_MARKERS` (lines 24-34) plus its loop-assertion use (lines 49-55) — excerpted above.
3. **Private-delegate + guard-predicate shape:** `_normalise_dns_name()` (144-148), `selected_address_for()` including its guard block (347-357), the duplicate guard in `pending_targets()` (838-846), the two internal call sites (788-789, 845), and the ingest (400) / SRV-normalisation (657-659) sites — all excerpted above. **No existing public/private-delegate naming pair exists in this module** — naming is genuinely open (Claude's Discretion).
4. **`pending_targets()` guard-branch coverage:** `TestLifxRecordCachePendingTargets` in `tests/test_network/test_mdns/test_discovery.py` (~3765-3848) exercises: no-SRV-record, known-A-target, IPv6-only-target, and link-local-only-target-stays-pending. **None of these tests set `_address_budget_exhausted`, populate `_address_overflowed_owners`, or trigger `byte_incomplete_owner_types` for A/AAAA and then call `pending_targets()`** — a targeted grep confirms no test co-occurrence of those three internal-state names with `pending_targets()`. D-04's residual is real: the existing suite does not exercise all four guard branches through `pending_targets()`. Per the task instructions this is reported only, not written.
5. **`pyproject.toml` ruff block today:** lines 80-89, excerpted above verbatim.
6. **`test_phase_contract.py` phrase-list sites for D-12:** `approved_phrases` tuple (121-137, full excerpt above) and `_MOVED_MDNS_LIMITATION_PHRASES`/`_ADVANCED_USAGE_PATH` (389-395 plus the assertion loop at 407-410) — both excerpted above.

## Metadata

**Analog search scope:** `src/lifx/network/discovery/mdns/discovery.py`, `tests/test_network/test_mdns/test_phase_contract.py`, `tests/test_network/test_mdns/test_discovery.py`, `tests/test_repository_guidance.py`, `AGENTS.md`, `pyproject.toml`
**Files scanned:** 6 read directly (targeted ranges), plus 1 grep sweep over `tests/test_network/test_mdns/*.py` for guard-branch coverage
**Pattern extraction date:** 2026-09-07
