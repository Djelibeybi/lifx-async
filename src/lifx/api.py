"""High-level API for convenient LIFX device control.

This module provides simplified interfaces for common operations:

- Simplified discovery with context managers
- Batch operations across multiple devices
- Filtered discovery by label, location, etc.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncGenerator, Iterator, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Literal

from lifx.color import HSBK
from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_TIMEOUT,
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_UDP_PORT,
    MAX_RESPONSE_TIME,
)
from lifx.devices import (
    CollectionInfo,
    Device,
    HevLight,
    InfraredLight,
    Light,
    MatrixLight,
    MultiZoneLight,
)
from lifx.network.discovery import (
    DiscoveredDevice,
    _discover_with_packet,
    discover_devices,
)
from lifx.protocol import packets
from lifx.theme import Theme


@dataclass
class LocationGrouping:
    """Organizational structure for location-based grouping."""

    uuid: str
    label: str
    devices: list[Device]
    updated_at: int  # Most recent updated_at from all devices

    def to_device_group(self) -> DeviceGroup:
        """Convert to DeviceGroup for batch operations."""
        return DeviceGroup(self.devices)


@dataclass
class GroupGrouping:
    """Organizational structure for group-based grouping."""

    uuid: str
    label: str
    devices: list[Device]
    updated_at: int

    def to_device_group(self) -> DeviceGroup:
        """Convert to DeviceGroup for batch operations."""
        return DeviceGroup(self.devices)


class DeviceGroup:
    """A group of devices for batch operations.

    Provides convenient methods to control multiple devices simultaneously.

    Example:
        ```python
        # Collect devices from discovery
        devices = []
        async for device in discover():
            devices.append(device)

        # Create group and perform batch operations
        group = DeviceGroup(devices)
        await group.set_power(True)
        await group.set_color(Colors.BLUE)
        ```
    """

    def __init__(
        self,
        devices: Sequence[
            Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight
        ],
    ) -> None:
        """Initialize device group.

        Args:
            devices: List of Device instances
        """
        self._devices = devices
        self._lights = [light for light in devices if isinstance(light, Light)]
        self._hev_lights = [light for light in devices if type(light) is HevLight]
        self._infrared_lights = [
            light for light in devices if type(light) is InfraredLight
        ]
        self._multizone_lights = [
            light for light in devices if type(light) is MultiZoneLight
        ]
        self._matrix_lights = [light for light in devices if type(light) is MatrixLight]
        self._locations_cache: dict[str, DeviceGroup] | None = None
        self._groups_cache: dict[str, DeviceGroup] | None = None
        self._location_metadata: dict[str, LocationGrouping] | None = None
        self._group_metadata: dict[str, GroupGrouping] | None = None

    async def __aenter__(self) -> DeviceGroup:
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context manager and close all device connections."""
        for device in self._devices:
            await device.connection.close()

    def __iter__(
        self,
    ) -> Iterator[
        Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight
    ]:
        """Iterate over devices in the group."""
        return iter(self._devices)

    def __len__(self) -> int:
        """Get number of devices in the group."""
        return len(self._devices)

    def __getitem__(
        self, index: int
    ) -> Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight:
        """Get device by index."""
        return self._devices[index]

    @property
    def devices(
        self,
    ) -> Sequence[
        Device | HevLight | InfraredLight | Light | MultiZoneLight | MatrixLight
    ]:
        """Get all the devices in the group."""
        return self._devices

    @property
    def lights(self) -> list[Light]:
        """Get all Light devices in the group."""
        return self._lights

    @property
    def hev_lights(self) -> list[HevLight]:
        """Get the HEV lights in the group."""
        return self._hev_lights

    @property
    def infrared_lights(self) -> list[InfraredLight]:
        """Get the Infrared lights in the group."""
        return self._infrared_lights

    @property
    def multizone_lights(self) -> list[MultiZoneLight]:
        """Get all MultiZone light devices in the group."""
        return self._multizone_lights

    @property
    def matrix_lights(self) -> list[MatrixLight]:
        """Get all Matrix light devices in the group."""
        return self._matrix_lights

    async def set_power(self, on: bool, duration: float = 0.0) -> None:
        """Set power state for all devices in the group.

        Args:
            on: True to turn on, False to turn off
            duration: Transition duration in seconds (default 0.0)

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            await group.set_power(True, duration=1.0)
            ```
        """
        async with asyncio.TaskGroup() as tg:
            for light in self.lights:
                tg.create_task(light.set_power(on, duration))

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Set color for all Light devices in the group.

        Args:
            color: HSBK color to set
            duration: Transition duration in seconds (default 0.0)

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            await group.set_color(HSBK.from_rgb(255, 0, 0), duration=2.0)
            ```
        """
        async with asyncio.TaskGroup() as tg:
            for light in self.lights:
                tg.create_task(light.set_color(color, duration))

    async def set_brightness(self, brightness: float, duration: float = 0.0) -> None:
        """Set brightness for all Light devices in the group.

        Args:
            brightness: Brightness level (0.0-1.0)
            duration: Transition duration in seconds (default 0.0)

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            await group.set_brightness(0.5, duration=1.0)
            ```
        """
        async with asyncio.TaskGroup() as tg:
            for light in self.lights:
                tg.create_task(light.set_brightness(brightness, duration))

    async def pulse(
        self, color: HSBK, period: float = 1.0, cycles: float = 1.0
    ) -> None:
        """Pulse effect for all Light devices.

        Args:
            color: Color to pulse to
            period: Period of one cycle in seconds
            cycles: Number of cycles

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            await group.pulse(Colors.RED, period=1.0, cycles=1.0)
            ```
        """
        async with asyncio.TaskGroup() as tg:
            for light in self.lights:
                tg.create_task(light.pulse(color, period, cycles))

    # Location and Group Organization Methods

    async def _fetch_location_metadata(self) -> None:
        """Fetch location info from all devices concurrently.

        Groups devices by location UUID and resolves label conflicts
        (uses label from device with most recent updated_at).
        Skips devices with empty UUID (b'\\x00' * 16).
        Logs warnings for failed queries but continues gracefully.
        """
        location_data: dict[str, list[tuple[Device, CollectionInfo]]] = defaultdict(
            list
        )

        # Fetch all location info concurrently
        tasks: dict[str, asyncio.Task[CollectionInfo | None]] = {}
        async with asyncio.TaskGroup() as tg:
            for device in self._devices:
                tasks[device.serial] = tg.create_task(device.get_location())

        results: list[tuple[Device, CollectionInfo | None]] = []
        for device in self._devices:
            results.append((device, tasks[device.serial].result()))

        # Group by location UUID
        for device, location_info in results:
            if location_info is None:
                continue

            # Skip empty UUIDs (unassigned)
            if location_info.uuid == "0000000000000000":
                continue

            location_data[location_info.uuid].append((device, location_info))

        # Build metadata dictionary with conflict resolution
        self._location_metadata = {}
        for location_uuid, device_list in location_data.items():
            if not device_list:
                continue

            # Find the most recent updated_at and corresponding label
            most_recent = max(device_list, key=lambda x: x[1].updated_at)
            label = most_recent[1].label
            updated_at = most_recent[1].updated_at

            # Collect all devices for this location
            devices = [device for device, _ in device_list]

            self._location_metadata[location_uuid] = LocationGrouping(
                uuid=location_uuid,
                label=label,
                devices=devices,
                updated_at=updated_at,
            )

    async def _fetch_group_metadata(self) -> None:
        """Fetch group info from all devices concurrently.

        Groups devices by group UUID and resolves label conflicts
        (uses label from device with most recent updated_at).
        Skips devices with empty UUID (b'\\x00' * 16).
        Logs warnings for failed queries but continues gracefully.
        """
        # Collect group info from all devices concurrently
        group_data: dict[str, list[tuple[Device, CollectionInfo]]] = defaultdict(list)

        tasks: dict[str, asyncio.Task[CollectionInfo | None]] = {}
        async with asyncio.TaskGroup() as tg:
            for device in self._devices:
                tasks[device.serial] = tg.create_task(device.get_group())

        # Fetch all group info concurrently
        results: list[tuple[Device, CollectionInfo | None]] = []
        for device in self._devices:
            results.append((device, tasks[device.serial].result()))

        # Group by group UUID
        for device, group_info in results:
            if group_info is None:
                continue

            # Skip empty UUIDs (unassigned)
            if group_info.uuid == "0000000000000000":
                continue

            group_data[group_info.uuid].append((device, group_info))

        # Build metadata dictionary with conflict resolution
        self._group_metadata = {}
        for group_uuid, device_list in group_data.items():
            if not device_list:
                continue

            # Find the most recent updated_at and corresponding label
            most_recent = max(device_list, key=lambda x: x[1].updated_at)
            label = most_recent[1].label
            updated_at = most_recent[1].updated_at

            # Collect all devices for this group
            devices = [device for device, _ in device_list]

            self._group_metadata[group_uuid] = GroupGrouping(
                uuid=group_uuid,
                label=label,
                devices=devices,
                updated_at=updated_at,
            )

    def _build_location_groups(
        self, include_unassigned: bool
    ) -> dict[str, DeviceGroup]:
        """Build dict of label -> DeviceGroup from location metadata.

        Args:
            include_unassigned: Include "Unassigned" group

        Returns:
            Dictionary mapping location labels to DeviceGroup instances

        Raises:
            RuntimeError: If metadata hasn't been fetched yet
        """
        if self._location_metadata is None:
            raise RuntimeError(
                "Location metadata not fetched. Call organize_by_location() first."
            )

        result: dict[str, DeviceGroup] = {}
        label_uuids: dict[str, str] = {}

        for location_uuid, grouping in self._location_metadata.items():
            label = grouping.label

            # Handle naming conflicts: if two different UUIDs have the same label,
            # append UUID suffix
            if label in label_uuids and label_uuids[label] != location_uuid:
                label = f"{label} ({location_uuid[:8]})"

            label_uuids[label] = location_uuid
            result[label] = DeviceGroup(grouping.devices)

        # Add unassigned devices if requested
        if include_unassigned:
            unassigned = self.get_unassigned_devices(metadata_type="location")
            if unassigned:
                result["Unassigned"] = DeviceGroup(unassigned)

        return result

    def _build_group_groups(self, include_unassigned: bool) -> dict[str, DeviceGroup]:
        """Build dict of label -> DeviceGroup from group metadata.

        Args:
            include_unassigned: Include "Unassigned" group

        Returns:
            Dictionary mapping group labels to DeviceGroup instances

        Raises:
            RuntimeError: If metadata hasn't been fetched yet
        """
        if self._group_metadata is None:
            raise RuntimeError(
                "Group metadata not fetched. Call organize_by_group() first."
            )

        result: dict[str, DeviceGroup] = {}
        label_uuids: dict[str, str] = {}

        for group_uuid, grouping in self._group_metadata.items():
            label = grouping.label

            # Handle naming conflicts: if two different UUIDs have the same label,
            # append UUID suffix
            if label in label_uuids and label_uuids[label] != group_uuid:
                label = f"{label} ({group_uuid[:8]})"

            label_uuids[label] = group_uuid
            result[label] = DeviceGroup(grouping.devices)

        # Add unassigned devices if requested
        if include_unassigned:
            unassigned = self.get_unassigned_devices(metadata_type="group")
            if unassigned:
                result["Unassigned"] = DeviceGroup(unassigned)

        return result

    def _has_location(self, device: Device) -> bool:
        """Check if device has location metadata.

        Args:
            device: Device to check

        Returns:
            True if device has location assigned, False otherwise

        Raises:
            RuntimeError: If metadata hasn't been fetched yet
        """
        if self._location_metadata is None:
            raise RuntimeError(
                "Location metadata not fetched. Call organize_by_location() first."
            )

        # Check if device is in any location grouping
        for grouping in self._location_metadata.values():
            if device in grouping.devices:
                return True
        return False

    def _has_group(self, device: Device) -> bool:
        """Check if device has group metadata.

        Args:
            device: Device to check

        Returns:
            True if device has group assigned, False otherwise

        Raises:
            RuntimeError: If metadata hasn't been fetched yet
        """
        if self._group_metadata is None:
            raise RuntimeError(
                "Group metadata not fetched. Call organize_by_group() first."
            )

        # Check if device is in any group grouping
        for grouping in self._group_metadata.values():
            if device in grouping.devices:
                return True
        return False

    async def organize_by_location(
        self, include_unassigned: bool = False
    ) -> dict[str, DeviceGroup]:
        """Organize devices by location label.

        Fetches location metadata if not cached and groups devices by location label.

        Args:
            include_unassigned: Include "Unassigned" group

        Returns:
            Dictionary mapping location labels to DeviceGroup instances

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            by_location = await group.organize_by_location()
            kitchen = by_location["Kitchen"]
            await kitchen.set_color(Colors.BLUE)
            ```
        """
        # Fetch metadata if not cached
        if self._location_metadata is None:
            await self._fetch_location_metadata()

        # Build and cache groups
        if self._locations_cache is None:
            self._locations_cache = self._build_location_groups(include_unassigned)

        return self._locations_cache

    async def organize_by_group(
        self, include_unassigned: bool = False
    ) -> dict[str, DeviceGroup]:
        """Organize devices by group label.

        Fetches group metadata if not cached and groups devices by group label.

        Args:
            include_unassigned: Include "Unassigned" group

        Returns:
            Dictionary mapping group labels to DeviceGroup instances

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            by_group = await group.organize_by_group()
            bedroom = by_group["Bedroom Lights"]
            await bedroom.set_power(False)
            ```
        """
        # Fetch metadata if not cached
        if self._group_metadata is None:
            await self._fetch_group_metadata()

        # Build and cache groups
        if self._groups_cache is None:
            self._groups_cache = self._build_group_groups(include_unassigned)

        return self._groups_cache

    async def filter_by_location(
        self, label: str, case_sensitive: bool = False
    ) -> DeviceGroup:
        """Filter devices to a specific location.

        Args:
            label: Location label to filter by
            case_sensitive: If True, performs case-sensitive matching (default False)

        Returns:
            DeviceGroup containing devices in the specified location

        Raises:
            KeyError: If location label not found

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            living_room = await group.filter_by_location("Living Room")
            await living_room.set_brightness(0.7)
            ```
        """
        locations = await self.organize_by_location(include_unassigned=False)

        # Find matching label
        if case_sensitive:
            if label not in locations:
                raise KeyError(f"Location '{label}' not found")
            return locations[label]
        else:
            label_lower = label.lower()
            for loc_label, device_group in locations.items():
                if loc_label.lower() == label_lower:
                    return device_group
            raise KeyError(f"Location '{label}' not found")

    async def filter_by_group(
        self, label: str, case_sensitive: bool = False
    ) -> DeviceGroup:
        """Filter devices to a specific group.

        Args:
            label: Group label to filter by
            case_sensitive: If True, performs case-sensitive matching (default False)

        Returns:
            DeviceGroup containing devices in the specified group

        Raises:
            KeyError: If group label not found

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            bedroom = await group.filter_by_group("Bedroom Lights")
            await bedroom.set_color(Colors.WARM_WHITE)
            ```
        """
        groups = await self.organize_by_group(include_unassigned=False)

        # Find matching label
        if case_sensitive:
            if label not in groups:
                raise KeyError(f"Group '{label}' not found")
            return groups[label]
        else:
            label_lower = label.lower()
            for grp_label, device_group in groups.items():
                if grp_label.lower() == label_lower:
                    return device_group
            raise KeyError(f"Group '{label}' not found")

    def get_unassigned_devices(
        self, metadata_type: Literal["location", "group"] = "location"
    ) -> list[Device]:
        """Get devices without location or group assigned.

        Args:
            metadata_type: Type of metadata to check ("location" or "group")

        Returns:
            List of devices without the specified metadata type

        Raises:
            RuntimeError: If metadata hasn't been fetched yet

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            await group.organize_by_location()
            unassigned = group.get_unassigned_devices(metadata_type="location")
            print(f"Found {len(unassigned)} devices without location")
            ```
        """
        if metadata_type == "location":
            if self._location_metadata is None:
                raise RuntimeError(
                    "Location metadata not fetched. Call organize_by_location() first."
                )
            return [d for d in self._devices if not self._has_location(d)]
        else:
            if self._group_metadata is None:
                raise RuntimeError(
                    "Group metadata not fetched. Call organize_by_group() first."
                )
            return [d for d in self._devices if not self._has_group(d)]

    async def apply_theme(
        self, theme: Theme, power_on: bool = False, duration: float = 0.0
    ) -> None:
        """Apply a theme to all devices in the group.

        Each device applies the theme according to its capabilities:
        - Light: Selects random color from theme
        - MultiZoneLight: Distributes colors evenly across zones
        - MatrixLight: Uses interpolation for smooth gradients
        - Other devices: No action (themes only apply to color devices)

        Args:
            theme: Theme to apply
            power_on: Turn on devices if True
            duration: Transition duration in seconds

        Example:
            ```python
            from lifx.theme import get_theme

            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)
            evening = get_theme("evening")
            await group.apply_theme(evening, power_on=True, duration=1.0)
            ```
        """
        async with asyncio.TaskGroup() as tg:
            # Apply theme to all lights
            for light in self.lights:
                tg.create_task(light.apply_theme(theme, power_on, duration))

            # Apply theme to all multizone lights
            for multizone in self.multizone_lights:
                tg.create_task(multizone.apply_theme(theme, power_on, duration))

            # Apply theme to all matrix light devices
            for matrix in self.matrix_lights:
                tg.create_task(matrix.apply_theme(theme, power_on, duration))

    def invalidate_metadata_cache(self) -> None:
        """Clear all cached location and group metadata.

        Use this if you've changed device locations/groups and want to re-fetch.

        Example:
            ```python
            devices = []
            async for device in discover():
                devices.append(device)
            group = DeviceGroup(devices)

            # First organization
            by_location = await group.organize_by_location()

            # ... change device locations ...

            # Clear cache and re-organize
            group.invalidate_metadata_cache()
            by_location = await group.organize_by_location()
            ```
        """
        self._locations_cache = None
        self._groups_cache = None
        self._location_metadata = None
        self._group_metadata = None


async def discover(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[Device, None]:
    """Discover LIFX devices and yield them as they are found.

    Args:
        timeout: Discovery timeout in seconds (default 3.0)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered devices
        max_retries: max retries per request set on discovered devices
    Yields:
        Device instances as they are discovered

    Example:
        ```python
        # Process devices as they're discovered
        async for device in discover():
            print(f"Found: {device.serial}")
            async with device:
                await device.set_power(True)

        # Or collect all devices first
        devices = []
        async for device in discover():
            devices.append(device)
        ```
    """
    async for discovered in discover_devices(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        device_timeout=device_timeout,
        max_retries=max_retries,
    ):
        device = await discovered.create_device()
        if device is not None:
            yield device


async def discover_mdns(
    timeout: float = DISCOVERY_TIMEOUT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[Light, None]:
    """Discover LIFX devices via mDNS and yield them as they are found.

    Uses mDNS/DNS-SD discovery with the _lifx._udp.local service type.
    This method is faster than broadcast discovery as device type information
    is included in the mDNS TXT records, eliminating the need for additional
    device queries.

    Note: mDNS discovery requires the mDNS multicast group (224.0.0.251:5353)
    to be accessible. Some network configurations may block multicast traffic.

    Args:
        timeout: Discovery timeout in seconds (default 15.0)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered devices
        max_retries: max retries per request set on discovered devices

    Yields:
        Device instances as they are discovered

    Example:
        ```python
        # Process devices as they're discovered
        async for device in discover_mdns():
            print(f"Found: {device.serial}")
            async with device:
                await device.set_power(True)

        # Or collect all devices first
        devices = []
        async for device in discover_mdns():
            devices.append(device)
        ```
    """
    from lifx.network.mdns.discovery import discover_devices_mdns

    async for device in discover_devices_mdns(
        timeout=timeout,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        device_timeout=device_timeout,
        max_retries=max_retries,
    ):
        yield device


async def find_by_serial(
    serial: str,
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Device | None:
    """Find a specific device by serial number.

    Args:
        serial: Serial number as hex string (with or without separators)
        timeout: Discovery timeout in seconds (default DISCOVERY_TIMEOUT)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered device
        max_retries: max retries per request set on discovered device

    Returns:
        Device instance if found, None otherwise

    Example:
        ```python
        # Find by serial number
        device = await find_by_serial("d073d5123456")
        if device:
            async with device:
                await device.set_power(True)
        ```
    """
    # Normalize serial to string format (12-digit hex, no separators)
    serial_str = serial.replace(":", "").replace("-", "").lower()

    async for disc in discover_devices(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        device_timeout=device_timeout,
        max_retries=max_retries,
    ):
        if disc.serial.lower() == serial_str:
            # Detect device type and return appropriate class
            return await disc.create_device()

    return None


async def find_by_ip(
    ip: str,
    timeout: float = DISCOVERY_TIMEOUT,
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Device | None:
    """Find a LIFX device by IP address.

    Uses a targeted discovery by sending the broadcast to the specific IP address,
    which means only that device will respond (if it exists). This is more efficient
    than broadcasting to all devices and filtering.

    Args:
        ip: Target device IP address
        timeout: Discovery timeout in seconds (default DISCOVERY_TIMEOUT)
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered device
        max_retries: max retries per request set on discovered device

    Returns:
        Device instance if found, None otherwise

    Example:
        ```python
        # Find device at specific IP
        device = await find_by_ip("192.168.1.100")
        if device:
            async with device:
                print(f"Found: {device.label}")
        ```
    """
    # Use the target IP as the "broadcast" address - only that device will respond
    async for discovered in discover_devices(
        timeout=timeout,
        broadcast_address=ip,  # Protocol trick: send directly to target IP
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        device_timeout=device_timeout,
        max_retries=max_retries,
    ):
        # Should only get one response (or none)
        return await discovered.create_device()

    return None


async def find_by_label(
    label: str,
    exact_match: bool = False,
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[Device]:
    """Find LIFX devices by label (name).

    Uses a protocol trick by broadcasting GetLabel instead of GetService,
    which returns all device labels in StateLabel responses. This is more
    efficient than querying each device individually.

    Args:
        label: Device label to search for (case-insensitive)
        exact_match: If True, match label exactly and yield at most one device;
                     if False, match substring and yield all matching devices
                     (default False)
        timeout: Discovery timeout in seconds (default DISCOVERY_TIMEOUT)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered device(s)
        max_retries: max retries per request set on discovered device(s)

    Yields:
        Matching Device instance(s)

    Example:
        ```python
        # Find all devices with "Living" in the label
        async for device in find_by_label("Living"):
            async with device:
                await device.set_power(True)

        # Find device by exact label match (yields at most one)
        async for device in find_by_label("Living Room", exact_match=True):
            async with device:
                await device.set_power(True)
            break  # exact_match yields at most one device
        ```
    """
    async for resp in _discover_with_packet(
        packets.Device.GetLabel(),
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    ):
        device_label = resp.response_payload.get("label", "")
        matched = False

        if exact_match:
            # Exact match - return first match only
            if device_label.lower() == label.lower():
                matched = True
        else:
            # Substring match - return all matches
            if label.lower() in device_label.lower():
                matched = True

        if matched:
            # Create DiscoveredDevice from response
            disc = DiscoveredDevice(
                serial=resp.serial,
                ip=resp.ip,
                port=resp.port,
                response_time=resp.response_time,
                timeout=device_timeout,
                max_retries=max_retries,
            )

            device = await disc.create_device()
            if device is not None:
                yield device


__all__ = [
    "DeviceGroup",
    "LocationGrouping",
    "GroupGrouping",
    "discover",
    "discover_mdns",
    "find_by_serial",
    "find_by_ip",
    "find_by_label",
]
