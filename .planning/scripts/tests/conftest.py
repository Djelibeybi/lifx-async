"""Path bootstrap for tooling tests importing their subjects flatly.

``.planning/scripts/tests`` is a ``testpaths`` entry, so this file is an
initial-argument conftest: pytest loads it on every run that uses
``testpaths``, including the default one, not only while the tooling tests
themselves are executing. The three ``sys.path`` inserts below are therefore
session-wide for the whole run, not confined to this directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_TOOLING_SCRIPTS_DIR = _TESTS_DIR.parent
_GITHUB_DIR = _TESTS_DIR.parent.parent.parent / ".github"
_REPO_ROOT = _TESTS_DIR.parent.parent.parent

for _insert_dir in (_TOOLING_SCRIPTS_DIR, _GITHUB_DIR, _REPO_ROOT):
    if str(_insert_dir) not in sys.path:
        sys.path.insert(0, str(_insert_dir))
