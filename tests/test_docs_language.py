"""Repository-wide prose contract for DOCS-08.

Guards two concerns, walking every `.py` under `src/` and every `.md` under
`docs/` (excluding the generated `docs/changelog.md`):

1. The internal validation language DOCS-08 removes (`"proven synthetically"`,
   `"mesh scale"`) must never reappear anywhere in the walked tree.
2. The false verification attribution the Phase 16 cross-AI plan review found
   (a claim that `discover()`'s UDP leg is unicast-verified, when it consumes
   `discover_devices_shared()` results directly and verifies nothing; it is
   the mDNS leg, via `_discover_verified_devices_mdns()`, that requires a
   correlated device response) must also never reappear.

This module runs in the default pytest suite and in CI (D-11): it guards
published documentation, which every pull request can regress, and
deselecting it by default would let a docs regression reach `main`
unchallenged.

Scans raw file text rather than reusing `test_phase_contract.py`'s
`.md`-shaped `_normalised_prose()` helper. That helper drops every line
starting with `#`, which under `src/**/*.py` would drop Python comments and
under `docs/**/*.md` would drop headings, and this contract must catch the
phrase wherever it appears, including in a comment or a heading
(16-CONTEXT.md leaves this choice to discretion).

Phase 20's DOCS-09 em-dash sweep should extend this module rather than
create another, per 16-CONTEXT.md's `<deferred>` note.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The internal validation language DOCS-08 removes from `src/lifx/api.py` and
# `docs/user-guide/discovery.md` (see 16-02-PLAN.md Task 1). Casefolded.
_FORBIDDEN_INTERNAL_VALIDATION_PHRASES = (
    "proven synthetically",
    "mesh scale",
)

# The false verification attribution the Phase 16 cross-AI plan review found:
# `discover()`'s UDP leg consumes `discover_devices_shared()` directly at
# `src/lifx/api.py:1112` and verifies nothing; it is `discover()`'s mDNS leg,
# via `_discover_verified_devices_mdns()` at `src/lifx/api.py:1125`, that
# requires a correlated device response before yielding, per
# `src/lifx/network/discovery/mdns/discovery.py:1361`. Cover the exact
# clause naming the UDP leg as unicast-verified and the same clause without
# the `unicast-` qualifier. Casefolded.
_FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES = (
    "udp leg is unicast-verified",
    "udp leg is verified",
)

_FORBIDDEN_PHRASES = (
    _FORBIDDEN_INTERNAL_VALIDATION_PHRASES + _FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES
)

# The release workflow generates this file; it is never hand edited (SPEC
# prohibition P7). Excluding it by name here, rather than by convention,
# satisfies the prohibition structurally.
_GENERATED_DOCS = (Path("docs/changelog.md"),)


def test_src_carries_no_internal_validation_language() -> None:
    """Neither forbidden concern appears anywhere under `src/`."""
    for source_path in sorted((_REPO_ROOT / "src").rglob("*.py")):
        text = source_path.read_text(encoding="utf-8").casefold()
        relative_path = source_path.relative_to(_REPO_ROOT)
        for phrase in _FORBIDDEN_PHRASES:
            assert phrase not in text, f"{phrase!r} found in {relative_path}"


def test_docs_carry_no_internal_validation_language() -> None:
    """Neither forbidden concern appears anywhere under `docs/`, excluding
    the generated `docs/changelog.md`."""
    for doc_path in sorted((_REPO_ROOT / "docs").rglob("*.md")):
        relative_path = doc_path.relative_to(_REPO_ROOT)
        if relative_path in _GENERATED_DOCS:
            continue
        text = doc_path.read_text(encoding="utf-8").casefold()
        for phrase in _FORBIDDEN_PHRASES:
            assert phrase not in text, f"{phrase!r} found in {relative_path}"


def test_generated_changelog_is_excluded_by_name() -> None:
    """The exclusion is a live structural exemption, not a stale name."""
    assert _GENERATED_DOCS == (Path("docs/changelog.md"),)
    assert (_REPO_ROOT / "docs/changelog.md").exists()


def test_forbidden_phrase_set_covers_both_concerns() -> None:
    """Neither source tuple can be dropped from the walk silently."""
    assert _FORBIDDEN_INTERNAL_VALIDATION_PHRASES
    assert _FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES
    for phrase in _FORBIDDEN_INTERNAL_VALIDATION_PHRASES:
        assert phrase in _FORBIDDEN_PHRASES
    for phrase in _FORBIDDEN_VERIFICATION_ATTRIBUTION_PHRASES:
        assert phrase in _FORBIDDEN_PHRASES
