"""Shared fixtures for performance benchmark tests."""

from __future__ import annotations

from typing import Any


def pytest_benchmark_update_machine_info(
    config: Any,  # noqa: ARG001
    machine_info: dict[str, Any],
) -> None:
    """Redact hostname from saved benchmark data."""
    machine_info["node"] = "redacted"
