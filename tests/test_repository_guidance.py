"""Repository guidance contract: AGENTS.md canonical, CLAUDE.md import-only.

D-24: shared and GSD-facing architecture guidance stays canonical in
`AGENTS.md`. `CLAUDE.md` is reduced to a literal `@AGENTS.md` import plus
only genuinely Claude-specific instructions. This resolves the direct
conflict the Phase 14 review flagged between that reduction and the older
`tests/test_network/test_mdns/test_phase_contract.py` expectation that
`CLAUDE.md` duplicate the shared mDNS query-model prose (see 14-REVIEWS.md,
"CLAUDE.md reduction (D-24) breaks an existing passing test").
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENTS_PATH = _REPO_ROOT / "AGENTS.md"
_CLAUDE_PATH = _REPO_ROOT / "CLAUDE.md"

# Markers that only ever belong to the canonical shared architecture guide.
# Their presence in CLAUDE.md would mean architecture prose was copied
# rather than imported.
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestClaudeImportsAgents:
    """D-24: CLAUDE.md imports AGENTS.md instead of duplicating it."""

    def test_claude_md_contains_a_literal_agents_md_import(self) -> None:
        text = _read(_CLAUDE_PATH)
        assert re.search(r"^@AGENTS\.md\s*$", text, re.MULTILINE), (
            "CLAUDE.md must contain a literal `@AGENTS.md` import line"
        )

    def test_claude_md_does_not_duplicate_shared_architecture_guidance(
        self,
    ) -> None:
        text = _read(_CLAUDE_PATH)
        for marker in _SHARED_ARCHITECTURE_MARKERS:
            assert marker not in text, (
                f"{marker!r} duplicated in CLAUDE.md; it belongs in AGENTS.md only"
            )

    def test_agents_md_remains_the_canonical_architecture_source(self) -> None:
        text = _read(_AGENTS_PATH)
        for marker in _SHARED_ARCHITECTURE_MARKERS:
            assert marker in text, f"{marker!r} missing from canonical AGENTS.md"


class TestPython310ConcurrencyGuidance:
    """D-24: AGENTS.md accurately describes Python 3.10-compatible fan-out."""

    def test_agents_md_documents_gather_and_create_task(self) -> None:
        text = _read(_AGENTS_PATH)
        assert "asyncio.gather()" in text
        assert "asyncio.create_task()" in text

    def test_agents_md_ties_the_replacement_to_the_python_3_10_floor(
        self,
    ) -> None:
        text = _read(_AGENTS_PATH)
        assert re.search(r"python 3\.10", text, re.IGNORECASE)
        # Names the version that actually introduces TaskGroup, so the
        # rationale for not using it is explicit rather than implied.
        assert "3.11" in text


class TestNoTaskGroupClaim:
    """D-24/AC-12: neither file claims the library uses asyncio.TaskGroup
    for its own concurrency. AGENTS.md may still name the exact identifier
    while explaining why it is unavailable on the Python 3.10 floor; only
    an affirmative usage claim is forbidden."""

    _FALSE_USAGE_CLAIM = re.compile(
        r"\b(?:via|uses?|using)\s+`?asyncio\.TaskGroup`?", re.IGNORECASE
    )

    def test_agents_md_has_no_taskgroup_usage_claim(self) -> None:
        text = _read(_AGENTS_PATH)
        assert self._FALSE_USAGE_CLAIM.search(text) is None

    def test_claude_md_has_no_taskgroup_claim(self) -> None:
        assert "TaskGroup" not in _read(_CLAUDE_PATH)


class TestDiscoveryQueryModelAccuracy:
    """D-24 (discovery/query-model scope): find_by_ip() is documented as a
    targeted unicast lookup, not a broadcast."""

    def test_agents_md_describes_find_by_ip_as_targeted_not_broadcast(
        self,
    ) -> None:
        text = _read(_AGENTS_PATH)
        assert "find_by_ip()" in text
        assert "targeted broadcast" not in text
        assert "IPv4 or IPv6 literal" in text
