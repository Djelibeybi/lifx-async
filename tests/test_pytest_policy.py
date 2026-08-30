"""Regression tests for repository-wide pytest policy."""

from __future__ import annotations

import pytest

from lifx.const import DEFAULT_REQUEST_TIMEOUT
from lifx.exceptions import LifxConnectionError, LifxNetworkError, LifxTimeoutError
from tests.conftest import NETWORK_RETRY_EXCEPTIONS, pytest_set_filtered_exceptions


def test_retry_policy_is_exactly_one_network_only_retry(
    pytestconfig: pytest.Config,
) -> None:
    """Configuration cannot silently broaden retries to assertion failures."""
    assert int(pytestconfig.getini("retries")) == 1
    assert float(pytestconfig.getini("retry_delay")) == 0
    assert NETWORK_RETRY_EXCEPTIONS == (
        LifxTimeoutError,
        LifxConnectionError,
        LifxNetworkError,
    )
    assert pytest_set_filtered_exceptions() == NETWORK_RETRY_EXCEPTIONS
    assert AssertionError not in NETWORK_RETRY_EXCEPTIONS


def test_retry_timeout_covers_two_complete_default_request_attempts(
    pytestconfig: pytest.Config,
) -> None:
    """The thread timeout cannot kill pytest during the approved retry."""
    attempts = int(pytestconfig.getini("retries")) + 1
    timeout = float(pytestconfig.getini("timeout"))

    assert timeout > attempts * DEFAULT_REQUEST_TIMEOUT
