"""Import-boundary tests for the canonical discovery hierarchy."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import lifx.network.discovery as discovery
import lifx.network.discovery.mdns as canonical_mdns
import lifx.network.discovery.udp as udp
import lifx.network.mdns as legacy_mdns
from lifx.network.discovery.mdns.types import _LifxServiceRecord
from lifx.network.mdns.discovery import discover_devices_mdns as legacy_discover_mdns
from lifx.network.mdns.dns import parse_dns_response as legacy_parse_dns_response
from lifx.network.mdns.transport import MdnsTransport as LegacyMdnsTransport
from lifx.network.mdns.types import _LifxServiceRecord as LegacyServiceRecord


def test_udp_compatibility_umbrella_reexports_canonical_implementation() -> None:
    """Documented low-level imports retain their existing object identities."""
    assert discovery.DiscoveredDevice is udp.DiscoveredDevice
    assert discovery.DiscoveryResponse is udp.DiscoveryResponse
    assert discovery.discover_devices is udp.discover_devices
    assert discovery.discover_devices.__module__ == "lifx.network.discovery.udp"


def test_legacy_mdns_surface_reexports_canonical_implementation() -> None:
    """The supported legacy mDNS imports remain thin compatibility aliases."""
    assert legacy_mdns.discover_devices_mdns is canonical_mdns.discover_devices_mdns
    assert legacy_discover_mdns is canonical_mdns.discover_devices_mdns
    assert legacy_parse_dns_response is canonical_mdns.parse_dns_response
    assert LegacyMdnsTransport is canonical_mdns.MdnsTransport
    assert LegacyServiceRecord is _LifxServiceRecord
    assert canonical_mdns.discover_devices_mdns.__module__ == (
        "lifx.network.discovery.mdns.discovery"
    )


def test_production_tree_has_no_observation_or_tests_dependency() -> None:
    """Observation models and capture state exist only in repository tests."""
    assert importlib.util.find_spec("lifx.network.discovery_observation") is None
    source_root = Path(__file__).resolve().parents[2] / "src" / "lifx"
    for source_path in source_root.rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        assert "tests.test_discovery_observation" not in source
        assert "discovery_observation" not in source
        assert "_DiscoveryObservation" not in source


def test_observer_plumbing_is_inert_without_an_async_capture_task() -> None:
    """Ordinary synchronous library use has no repository observer callback."""
    assert udp._current_discovery_observer() is None
