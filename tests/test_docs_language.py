"""Repository-wide prose contract for DOCS-08.

Guards two concerns across every `.py` under `src/`, every `.md` under `docs/`
(excluding the generated `docs/changelog.md`) and the repository-root Markdown
that `tests/test_repository_guidance.py` treats as canonical guidance:

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

Scans file text with whitespace collapsed but headings and comments retained,
rather than reusing `test_phase_contract.py`'s `.md`-shaped
`_normalised_prose()` helper. That helper drops every line starting with `#`,
which under `src/**/*.py` would drop Python comments and under `docs/**/*.md`
would drop headings, and this contract must catch the phrase wherever it
appears, including in a comment or a heading (16-CONTEXT.md leaves this choice
to discretion). Collapsing whitespace is not optional: this repository hard
wraps prose, so a two-word phrase split across a line break would otherwise
slip past a raw substring scan.

Phase 20's DOCS-09 em-dash sweep should extend this module rather than
create another, per 16-CONTEXT.md's `<deferred>` note.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The internal validation language DOCS-08 removes from `src/lifx/api.py` and
# `docs/user-guide/discovery.md` (see 16-02-PLAN.md Task 1). Casefolded.
_FORBIDDEN_INTERNAL_VALIDATION_PHRASES = (
    "proven synthetically",
    "mesh scale",
)

# The false verification attribution the Phase 16 cross-AI plan review found:
# `discover()`'s UDP leg consumes `discover_devices_shared()` directly and
# verifies nothing; it is `discover()`'s mDNS leg, via
# `_discover_verified_devices_mdns()`, that requires a correlated device
# response before yielding, per `_verify_mdns_candidate()` in
# `src/lifx/network/discovery/mdns/discovery.py`. Cover the exact clause
# naming the UDP leg as unicast-verified and the same clause without the
# `unicast-` qualifier. Casefolded.
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

# Each entry is (directory, glob). The repository root is walked
# non-recursively so the canonical guidance files are covered without
# reaching into `.planning/`, which records the retired phrases deliberately.
_WALKED_TREES = (
    ("src", "**/*.py"),
    ("docs", "**/*.md"),
    (".", "*.md"),
)


def _scannable_text(path: Path) -> str:
    """Return the file's text with runs of whitespace collapsed to one space.

    Headings and comments are deliberately retained; only the line breaks
    this repository's hard wrapping introduces are removed, so a forbidden
    two-word phrase is caught whether or not it straddles a line break.
    """
    return " ".join(path.read_text(encoding="utf-8").split()).casefold()


@pytest.mark.parametrize(("directory", "pattern"), _WALKED_TREES)
def test_tree_carries_no_internal_validation_language(
    directory: str, pattern: str
) -> None:
    """Neither forbidden concern appears anywhere in a walked tree."""
    paths = sorted((_REPO_ROOT / directory).glob(pattern))
    assert paths, (
        f"{directory}/{pattern} matched no files; the walk is vacuous and "
        "would pass whether or not the forbidden phrases were present"
    )

    offences = [
        (str(path.relative_to(_REPO_ROOT)), phrase)
        for path in paths
        if path.relative_to(_REPO_ROOT) not in _GENERATED_DOCS
        for phrase in _FORBIDDEN_PHRASES
        if phrase in _scannable_text(path)
    ]
    assert not offences, f"forbidden phrases found: {offences}"


def test_generated_changelog_is_excluded_by_name() -> None:
    """The exclusion names a file that exists, so it is not a stale name."""
    for excluded in _GENERATED_DOCS:
        assert (_REPO_ROOT / excluded).exists(), (
            f"{excluded} is excluded by name but does not exist; the exemption is stale"
        )
