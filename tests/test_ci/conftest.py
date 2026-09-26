"""Make the CI tooling under ``.github/`` importable for its tests.

``check_patch_coverage`` and ``patch_coverage_guard`` are standalone scripts
that CI runs directly, so they are not on any import path. This conftest
sits beside the only tests that import them, so the insert happens only
when this directory is collected.
"""

from __future__ import annotations

import sys
from pathlib import Path

_GITHUB_DIR = Path(__file__).resolve().parents[2] / ".github"

if str(_GITHUB_DIR) not in sys.path:
    sys.path.insert(0, str(_GITHUB_DIR))
