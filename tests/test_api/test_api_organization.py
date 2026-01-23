"""Tests for DeviceGroup organization and filtering features.

This module tests:
- organize_by_location() - Group devices by location
- organize_by_group() - Group devices by group
- filter_by_location() - Filter to specific location
- filter_by_group() - Filter to specific group
- get_unassigned_devices() - Find devices without metadata
- invalidate_metadata_cache() - Clear cached metadata

Note: Since the emulator subprocess creates devices with default metadata,
these tests verify the organization logic works but may not test all edge cases
that require specific custom metadata.
"""

from __future__ import annotations

import pytest

from lifx.api import DeviceGroup


@pytest.mark.emulator
class TestOrganizeMetadata:
    """Test organization by location and group metadata."""

    @pytest.mark.parametrize(
        "organize_method",
        ["organize_by_location", "organize_by_group"],
        ids=["location", "group"],
    )
    async def test_organize_basic(self, emulator_devices: DeviceGroup, organize_method):
        """Test basic organization by metadata type."""
        group = emulator_devices

        # Organize by metadata type
        organize_func = getattr(group, organize_method)
        by_metadata = await organize_func(include_unassigned=True)

        # Should have at least one metadata group (or Unassigned)
        assert len(by_metadata) >= 1

        # Total devices across all groups should match group size
        total_devices = sum(len(g.devices) for g in by_metadata.values())
        assert total_devices == len(group.devices)

    @pytest.mark.parametrize(
        "organize_method",
        ["organize_by_location", "organize_by_group"],
        ids=["location", "group"],
    )
    async def test_organize_caching(
        self, emulator_devices: DeviceGroup, organize_method
    ):
        """Test that metadata is cached."""
        group = emulator_devices

        # First call fetches metadata
        organize_func = getattr(group, organize_method)
        by_metadata1 = await organize_func()

        # Second call should use cached data (same object)
        by_metadata2 = await organize_func()

        # Should be the same dict object (cached)
        assert by_metadata1 is by_metadata2


@pytest.mark.emulator
class TestFilterMetadata:
    """Test filtering by location and group metadata."""

    @pytest.mark.parametrize(
        "filter_method,organize_method,metadata_type",
        [
            ("filter_by_location", "organize_by_location", "location"),
            ("filter_by_group", "organize_by_group", "group"),
        ],
        ids=["location", "group"],
    )
    async def test_filter_with_existing_metadata(
        self,
        emulator_devices: DeviceGroup,
        filter_method,
        organize_method,
        metadata_type,
    ):
        """Test filtering by existing metadata."""
        group = emulator_devices

        # First organize to see what metadata exists
        organize_func = getattr(group, organize_method)
        by_metadata = await organize_func(include_unassigned=True)

        # Skip test if no metadata found
        if not by_metadata:
            pytest.skip(f"No {metadata_type} found in emulator devices")

        # Get first metadata name
        metadata_name = list(by_metadata.keys())[0]

        # Filter by that metadata
        filter_func = getattr(group, filter_method)
        filtered = await filter_func(metadata_name, case_sensitive=False)

        # Should get a DeviceGroup back
        assert isinstance(filtered, DeviceGroup)
        assert len(filtered.devices) > 0

    @pytest.mark.parametrize(
        "filter_method,error_name",
        [
            ("filter_by_location", "NonExistentLocation"),
            ("filter_by_group", "NonExistentGroup"),
        ],
        ids=["location", "group"],
    )
    async def test_filter_not_found(
        self, emulator_devices: DeviceGroup, filter_method, error_name
    ):
        """Test that KeyError is raised for non-existent metadata."""
        group = emulator_devices

        filter_func = getattr(group, filter_method)
        with pytest.raises(KeyError, match=f"{error_name}.*not found"):
            await filter_func(error_name)


@pytest.mark.emulator
class TestGetUnassignedDevices:
    """Test get_unassigned_devices() method."""

    @pytest.mark.parametrize(
        "metadata_type,organize_method",
        [
            ("location", "organize_by_location"),
            ("group", "organize_by_group"),
        ],
        ids=["location", "group"],
    )
    async def test_get_unassigned_devices(
        self, emulator_devices: DeviceGroup, metadata_type, organize_method
    ):
        """Test getting devices without metadata."""
        group = emulator_devices

        # Fetch metadata first
        organize_func = getattr(group, organize_method)
        await organize_func(include_unassigned=True)

        # Get unassigned devices
        unassigned = group.get_unassigned_devices(metadata_type=metadata_type)

        # Should return a list (may be empty if all devices have metadata)
        assert isinstance(unassigned, list)

    @pytest.mark.parametrize(
        "metadata_type,error_message",
        [
            ("location", "Location metadata not fetched"),
            ("group", "Group metadata not fetched"),
        ],
        ids=["location", "group"],
    )
    async def test_get_unassigned_devices_without_fetch_raises_error(
        self, emulator_devices: DeviceGroup, metadata_type, error_message
    ):
        """Test that RuntimeError is raised if metadata not fetched."""
        group = emulator_devices

        # Try to get unassigned without fetching metadata (new group instance)
        fresh_group = DeviceGroup(list(group.devices))
        with pytest.raises(RuntimeError, match=error_message):
            fresh_group.get_unassigned_devices(metadata_type=metadata_type)


@pytest.mark.emulator
class TestMetadataStore:
    """Test metadata caching and invalidation."""

    async def test_metadata_refetch_after_invalidation(
        self, emulator_devices: DeviceGroup
    ):
        """Test that metadata can be re-fetched after invalidation."""
        group = emulator_devices

        # Fetch and cache
        by_location1 = await group.organize_by_location()

        # Invalidate
        group.invalidate_metadata_cache()

        # Re-fetch
        by_location2 = await group.organize_by_location()

        # Should be different objects (new fetch)
        assert by_location1 is not by_location2

        # But should have same content
        assert set(by_location1.keys()) == set(by_location2.keys())


@pytest.mark.emulator
class TestOrganizeEdgeCases:
    """Test edge cases in organization methods."""

    async def test_organize_empty_device_group(self):
        """Test organizing an empty DeviceGroup."""
        empty_group = DeviceGroup([])

        by_location = await empty_group.organize_by_location()
        by_group = await empty_group.organize_by_group()

        # Should return empty dicts
        assert by_location == {}
        assert by_group == {}

    async def test_organize_with_concurrent_operations(
        self, emulator_devices: DeviceGroup
    ):
        """Test that concurrent organization operations work correctly."""
        import asyncio

        group = emulator_devices

        # Run both operations concurrently
        by_location, by_group = await asyncio.gather(
            group.organize_by_location(), group.organize_by_group()
        )

        # Both should succeed
        assert len(by_location) >= 0
        assert len(by_group) >= 0
