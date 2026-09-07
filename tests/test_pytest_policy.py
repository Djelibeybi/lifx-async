"""Regression tests for repository-wide pytest policy."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest_retry.configs import Defaults
from pytest_timeout import get_env_settings

from lifx.const import DEFAULT_REQUEST_TIMEOUT
from lifx.exceptions import LifxConnectionError, LifxNetworkError, LifxTimeoutError
from tests.conftest import (
    _OPT_IN_MARKER_FLAGS,
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

    config = MagicMock()
    config.getoption.return_value = False

    windows_item = MagicMock(fixturenames=[])
    windows_item.get_closest_marker.side_effect = marker_for
    with patch("tests.conftest.sys.platform", "win32"):
        pytest_collection_modifyitems(config, [windows_item])

    added = windows_item.add_marker.call_args.args[0]
    assert added.name == "flaky"
    assert added.kwargs == targeted_ipv6_retry_policy("win32")

    linux_item = MagicMock(fixturenames=[])
    linux_item.get_closest_marker.side_effect = marker_for
    with patch("tests.conftest.sys.platform", "linux"):
        pytest_collection_modifyitems(config, [linux_item])

    linux_item.add_marker.assert_not_called()


def test_addopts_carries_no_marker_expression(pytestconfig: pytest.Config) -> None:
    """D-09 replaces `-m` selection with opt-in flags; no `-m` may return."""
    addopts = pytestconfig.getini("addopts")
    assert not any(option == "-m" or option.startswith("-m") for option in addopts)


def test_opt_in_marker_flags_are_fully_registered(pytestconfig: pytest.Config) -> None:
    """A future opt-in category is a table entry, not a silent hole."""
    marker_names = {
        line.split(":", 1)[0].strip() for line in pytestconfig.getini("markers")
    }
    for marker_name, flag in _OPT_IN_MARKER_FLAGS.items():
        assert marker_name in marker_names
        # Raises if the parser never registered this flag.
        pytestconfig.getoption(flag)


def _item_with_marker(marker_name: str | None) -> MagicMock:
    """Return a mock collection item carrying at most one named marker."""
    item = MagicMock(fixturenames=[])

    def _get_closest_marker(
        name: str, _marker_name: str | None = marker_name
    ) -> object | None:
        return object() if name == _marker_name else None

    item.get_closest_marker.side_effect = _get_closest_marker
    return item


def test_deselection_hook_drops_opt_in_items_with_all_flags_off() -> None:
    """All flags off deselects both opt-in categories and reports them."""
    config = MagicMock()
    config.getoption.return_value = False

    tooling_item = _item_with_marker("tooling")
    benchmark_item = _item_with_marker("benchmark")
    plain_item = _item_with_marker(None)
    items = [tooling_item, benchmark_item, plain_item]

    with patch("tests.conftest.sys.platform", "linux"):
        pytest_collection_modifyitems(config, items)

    config.hook.pytest_deselected.assert_called_once()
    deselected = config.hook.pytest_deselected.call_args.kwargs["items"]
    assert set(deselected) == {tooling_item, benchmark_item}
    assert items == [plain_item]


def test_deselection_hook_readmits_tooling_when_its_flag_is_set() -> None:
    """--tooling selects the tooling item while benchmark stays deselected."""
    config = MagicMock()
    config.getoption.side_effect = lambda flag: flag == "--tooling"

    tooling_item = _item_with_marker("tooling")
    benchmark_item = _item_with_marker("benchmark")
    plain_item = _item_with_marker(None)
    items = [tooling_item, benchmark_item, plain_item]

    with patch("tests.conftest.sys.platform", "linux"):
        pytest_collection_modifyitems(config, items)

    deselected = config.hook.pytest_deselected.call_args.kwargs["items"]
    assert deselected == [benchmark_item]
    assert items == [tooling_item, plain_item]


def test_every_tooling_test_module_declares_the_marker_at_module_scope() -> None:
    """A tooling test missing its marker would silently join the default suite.

    Verdict is reached by parsing each file with ``ast`` and walking only
    ``Module.body`` for an assignment targeting the name ``pytestmark``, then
    checking the assigned value names ``pytest.mark.tooling``. A substring
    search for ``pytestmark`` would also match a comment, a docstring, or an
    assignment nested inside a function body, none of which pytest reads as
    a module-level marker, so no assertion here relies on one.
    """
    repo_root = Path(__file__).resolve().parent.parent
    tooling_dir = repo_root / ".planning" / "scripts" / "tests"
    tooling_test_files = sorted(tooling_dir.glob("test_*.py"))
    assert tooling_test_files, (
        f"expected at least one relocated tooling test module under {tooling_dir}"
    )

    for path in tooling_test_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        declared_value: str | None = None
        for node in tree.body:
            target_name: str | None = None
            value_node: ast.expr | None = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                (target,) = node.targets
                if isinstance(target, ast.Name):
                    target_name = target.id
                    value_node = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target_name = node.target.id
                value_node = node.value
            if target_name == "pytestmark" and value_node is not None:
                declared_value = ast.unparse(value_node)
                break

        assert declared_value == "pytest.mark.tooling", (
            f"{path}: expected module-scope `pytestmark = pytest.mark.tooling`, "
            f"found {declared_value!r}"
        )
