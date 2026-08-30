"""Regression tests for repository-wide pytest policy."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from pytest_retry.configs import Defaults
from pytest_timeout import get_env_settings

from lifx.const import DEFAULT_REQUEST_TIMEOUT
from lifx.exceptions import LifxConnectionError, LifxNetworkError, LifxTimeoutError
from tests.conftest import (
    NETWORK_RETRY_EXCEPTIONS,
    WINDOWS_IPV6_RETRY_EXCEPTIONS,
    pytest_collection_modifyitems,
    targeted_ipv6_retry_policy,
)
from tests.test_api.test_ipv6_e2e import (
    TestIpv6TargetedDiscovery as Ipv6TargetedDiscoveryTests,
)


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
    assert tuple(Defaults.FILTERED_EXCEPTIONS) == NETWORK_RETRY_EXCEPTIONS
    assert AssertionError not in Defaults.FILTERED_EXCEPTIONS


def test_explicit_retry_policy_is_limited_to_targeted_ipv6(
    request: pytest.FixtureRequest,
) -> None:
    """Only the known socket flake may override the global retry timing."""
    target = Ipv6TargetedDiscoveryTests.test_find_by_ip_over_ipv6
    target_markers = [marker for marker in target.pytestmark if marker.name == "flaky"]
    assert target_markers == []
    assert targeted_ipv6_retry_policy("win32") == {
        "retries": 2,
        "delay": 1,
        "only_on": WINDOWS_IPV6_RETRY_EXCEPTIONS,
    }
    assert targeted_ipv6_retry_policy("linux") is None
    assert targeted_ipv6_retry_policy("darwin") is None

    target_suffix = (
        "tests/test_api/test_ipv6_e2e.py::TestIpv6TargetedDiscovery::"
        "test_find_by_ip_over_ipv6"
    )
    for item in request.session.items:
        marker = item.get_closest_marker("flaky")
        assert marker is not None
        expected = (
            targeted_ipv6_retry_policy("win32")
            if item.nodeid.endswith(target_suffix)
            and targeted_ipv6_retry_policy(sys.platform) is not None
            else {"retries": Defaults.RETRIES}
        )
        assert marker.kwargs == expected


def test_retry_timeout_covers_two_complete_default_request_attempts(
    pytestconfig: pytest.Config,
) -> None:
    """The thread timeout cannot kill pytest during the approved retry."""
    attempts = Defaults.RETRIES + 1
    addopts = pytestconfig.getini("addopts")
    assert all(not option.startswith("--timeout") for option in addopts)
    timeout = get_env_settings(pytestconfig).timeout

    assert timeout is not None
    assert timeout > attempts * DEFAULT_REQUEST_TIMEOUT


def test_collection_hook_adds_the_focused_policy_only_on_windows() -> None:
    """The dynamic override exists on Windows and nowhere else."""

    def marker_for(name: str) -> object | None:
        return object() if name == "targeted_ipv6_windows" else None

    windows_item = MagicMock(fixturenames=[])
    windows_item.get_closest_marker.side_effect = marker_for
    with patch("tests.conftest.sys.platform", "win32"):
        pytest_collection_modifyitems([windows_item])

    added = windows_item.add_marker.call_args.args[0]
    assert added.name == "flaky"
    assert added.kwargs == targeted_ipv6_retry_policy("win32")

    linux_item = MagicMock(fixturenames=[])
    linux_item.get_closest_marker.side_effect = marker_for
    with patch("tests.conftest.sys.platform", "linux"):
        pytest_collection_modifyitems([linux_item])

    linux_item.add_marker.assert_not_called()
