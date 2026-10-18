"""Upstream commit lookup shared by the protocol and product generators.

The generated modules record which upstream commit they came from. The lookup
asks the GitHub commits API for the latest commit touching the source file.
A failed lookup never stops generation: it records ``unknown`` instead.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import urlopen

_LOGGER = logging.getLogger(__name__)

UNKNOWN = "unknown"


@dataclass(frozen=True)
class UpstreamCommit:
    """The upstream commit a generated file was built from.

    Attributes:
        sha: Full commit hash, or ``unknown`` when the lookup failed
        date: Commit timestamp (ISO 8601, UTC), or ``unknown``. This is the
            commit's own timestamp, not the wall clock, so regenerating from
            the same upstream commit reproduces the file byte for byte.
    """

    sha: str = UNKNOWN
    date: str = UNKNOWN

    def header_lines(self) -> str:
        """Render the lines a generated module header carries."""
        return f"Upstream commit: {self.sha}\nUpstream commit timestamp: {self.date}"


def fetch_upstream_commit(repo: str, branch: str, path: str) -> UpstreamCommit:
    """Fetch the latest commit that touched ``path`` on ``branch`` of ``repo``.

    Args:
        repo: GitHub repository as ``owner/name``
        branch: Branch to inspect
        path: File path within the repository

    Returns:
        The commit, or an all-``unknown`` commit if the lookup fails
    """
    query = urlencode({"path": path, "sha": branch, "per_page": 1})
    url = f"https://api.github.com/repos/{repo}/commits?{query}"
    try:
        with urlopen(url, timeout=15) as response:  # nosec B310
            payload = json.loads(response.read())
        latest = payload[0]
        return UpstreamCommit(
            sha=str(latest["sha"]),
            date=str(latest["commit"]["committer"]["date"]),
        )
    except (OSError, ValueError, LookupError, TypeError) as exc:
        _LOGGER.warning(
            {
                "function": "fetch_upstream_commit",
                "action": "lookup_failed",
                "path": path,
                "error": str(exc),
            }
        )
        return UpstreamCommit()
