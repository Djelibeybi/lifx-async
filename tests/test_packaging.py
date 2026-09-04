"""The published distribution must stay dependency-free.

Zero runtime dependencies is the library's headline property, stated in the
README, the docs and AGENTS.md. Nothing enforced it, so a `uv add` that
should have been `uv add --dev` put a 14 MB type checker into
``[project].dependencies`` and it reached PyPI in 7.1.2 before anyone
noticed. These two checks close that gap from both ends: the declaration in
``pyproject.toml`` and the metadata an installed wheel actually carries.
"""

from __future__ import annotations

import sys
from importlib.metadata import requires
from pathlib import Path

import pytest

DISTRIBUTION = "lifx-async"
PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_pyproject_declares_no_runtime_dependencies() -> None:
    """``[project].dependencies`` is the source of truth and must be empty."""
    if sys.version_info < (3, 11):
        pytest.skip("tomllib requires Python 3.11; CI covers 3.11 through 3.14")

    import tomllib

    manifest = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert manifest["project"]["dependencies"] == []


def test_installed_metadata_declares_no_runtime_dependencies() -> None:
    """What a wheel installs is what ``pip install lifx-async`` pulls in.

    Development dependencies live in ``[dependency-groups]``, which is not
    distribution metadata, so they never reach ``requires()``. Anything that
    does appear here is a runtime dependency of the published wheel.
    """
    assert requires(DISTRIBUTION) is None
