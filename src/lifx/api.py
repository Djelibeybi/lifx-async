"""High-level API for convenient LIFX device control.

This module provides simplified interfaces for common operations:

- Simplified discovery with context managers
- Batch operations across multiple devices
- Filtered discovery by label, location, etc.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from types import TracebackType
from typing import Literal

from lifx.color import HSBK
from lifx.const import (
    IDLE_TIMEOUT_MULTIPLIER,
    LIFX_UDP_PORT,
    MAX_RESPONSE_TIME,
)
from lifx.devices import (
    Device,
    GroupInfo,
    HevLight,
    InfraredLight,
    Light,
    LocationInfo,
    MultiZoneLight,
    TileDevice,
)
from lifx.exceptions import LifxTimeoutError
from lifx.network.connection import DeviceConnection
from lifx.network.discovery import DiscoveredDevice, discover_devices
from lifx.products import get_device_class_name
from lifx.protocol import packets
from lifx.theme import Theme

_LOGGER = logging.getLogger(__name__)


@dataclass
class LocationGrouping:
    """Organizational structure for location-based grouping."""

    uuid: bytes
    label: str
    devices: list[Device]
    updated_at: int  # Most recent updated_at from all devices

    def to_device_group(self) -> DeviceGroup:
        """Convert to DeviceGroup for batch operations."""
        return DeviceGroup(self.devices)


@dataclass
class GroupGrouping:
    """Organizational structure for group-based grouping."""

    uuid: bytes
    label: str
    devices: list[Device]
    updated_at: int

    def to_device_group(self) -> DeviceGroup:
        """Convert to DeviceGroup for batch operations."""
        return DeviceGroup(self.devices)


async def _detect_device_type(
    discovered: DiscoveredDevice,
) -> Device | Light | HevLight | InfraredLight | MultiZoneLight | TileDevice | None:
    """Detect device type and instantiate appropriate class.

    Queries the device for its version information and uses the products
    database to determine the most appropriate device class.

    Args:
        discovered: DiscoveredDevice with serial, ip, and port

    Returns:
        Device instance of the appropriate type
        or None if unresponsive
    """

    conn = DeviceConnection(
        serial=discovered.serial,
        ip=discovered.ip,
        port=discovered.port,
    )

    try:
        state_version = await conn.request(
            packets.Device.GetVersion(),
            timeout=2.0,
        )
        product_id = state_version.product

        # Determine appropriate device class based on product capabilities
        class_name = get_device_class_name(product_id)

    except Exception as e:
        _LOGGER.warning(
            {
                "class": "_detect_device_type",
                "method": "detect",
                "action": "query_failed",
                "serial": discovered.serial,
                "reason": str(e),
            }
        )
        return None

    # Instantiate the appropriate class
    device_class_map = {
        "Device": Device,
        "Light": Light,
        "HevLight": HevLight,
        "InfraredLight": InfraredLight,
        "MultiZoneLight": MultiZoneLight,
        "TileDevice": TileDevice,
    }

    device_class = device_class_map.get(class_name, Light)
    device = device_class(
        serial=discovered.serial, ip=discovered.ip, port=discovered.port
    )

    return device


class DiscoveryContext:
    """Async context manager for device discovery.

    Handles device discovery and automatic connection/disconnection.
    Use with the `discover()` function for convenient device discovery.

    Example:
        ```python
        async with discover(timeout=5.0) as group:
            await group.set_power(True)
        ```
    """

    def __init__(
        self,
        timeout: float,
        broadcast_address: str,
        port: int,
        max_response_time: float = MAX_RESPONSE_TIME,
        idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    ) -> None:
        """Initialize discovery context.

        Args:
            timeout: Discovery timeout in seconds
            broadcast_address: Broadcast address to use
            port: Port to use
            max_response_time: Max time to wait for responses
            idle_timeout_multiplier: Idle timeout multiplier
        """
        self.timeout = timeout
        self.broadcast_address = broadcast_address
        self.port = port
        self._group: DeviceGroup | None = None
        self._max_response_time = max_response_time
        self._idle_timeout_multiplier = idle_timeout_multiplier

    async def __aenter__(self) -> DeviceGroup:
        """Discover devices and connect to them.

        Returns:
            DeviceGroup containing all discovered devices
        """
        # Perform discovery
        discovered = await discover_devices(
            timeout=self.timeout,
            broadcast_address=self.broadcast_address,
            port=self.port,
            max_response_time=self._max_response_time,
            idle_timeout_multiplier=self._idle_timeout_multiplier,
        )

        # Detect device types and instantiate appropriate classes
        results: list[Device | None] = [None] * len(discovered)

        async def detect_and_store(index: int, disc: DiscoveredDevice) -> None:
            results[index] = await _detect_device_type(disc)

        async with asyncio.TaskGroup() as tg:
            for i, disc in enumerate(discovered):
                tg.create_task(detect_and_store(i, disc))

        # Filter out None values (unresponsive devices)
        devices = [d for d in results if d is not None]

        # Create group and connect all devices
        self._group = DeviceGroup(devices)
        await self._group.__aenter__()

        return self._group

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Disconnect from all devices."""
        if self._group:
            await self._group.__aexit__(exc_type, exc_val, exc_tb)


class DeviceGroup:
    """A group of devices for batch operations.

    Provides convenient methods to control multiple devices simultaneously.

    Example:
        ```python
        async with discover() as group:
            await group.set_power(True)
            await group.set_color(Colors.BLUE)
        ```
    """

    def __init__(
        self,
        devices: list[
            Device | Light | HevLight | InfraredLight | MultiZoneLight | TileDevice
        ],
    ) -> None:
        """Initialize device group.

        Args:
            devices: List of Device instances
        """
        self._devices = devices
        self._locations_cache: dict[str, DeviceGroup] | None = None
        self._groups_cache: dict[str, DeviceGroup] | None = None
        self._location_metadata: dict[bytes, LocationGrouping] | None = None
        self._group_metadata: dict[bytes, GroupGrouping] | None = None

    async def __aenter__(self) -> DeviceGroup:
        """Enter async context manager.

        Note: With the new connection architecture, explicit connect/disconnect
        is not needed. Connections are managed automatically by the connection
        pool when requests are made.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context manager.

        Note: Cleanup is handled automatically by the connection pool.
        """
        pass

    def __iter__(
        self,
    ) -> Iterator[
        Device | Light | HevLight | InfraredLight | MultiZoneLight | TileDevice
    ]:
        """Iterate over devices in the group."""
        return iter(self._devices)

    def __len__(self) -> int:
        """Get number of devices in the group."""
        return len(self._devices)

    @property
    def devices(self) -> list[Device]:
        """Get all the devices in the group."""
        return self._devices

    @property
    def lights(self) -> list[Light]:
        """Get all Light devices in the group."""
        return [d for d in self._devices if isinstance(d, Light)]

    @property
    def hev_lights(self) -> list[HevLight]:
        """Get the HEV lights in the group."""
        return [d for d in self._devices if isinstance(d, HevLight)]

    @property
    def infrared_lights(self) -> list[InfraredLight]:
        """Get the Infrared lights in the group."""
        return [d for d in self._devices if isinstance(d, InfraredLight)]

    @property
    def multizone_lights(self) -> list[MultiZoneLight]:
        """Get all MultiZone light devices in the group."""
        return [d for d in self._devices if isinstance(d, MultiZoneLight)]

    @property
    def tiles(self) -> list[TileDevice]:
        """Get all Tile devices in the group."""
        return [d for d in self._devices if isinstance(d, TileDevice)]

    async def set_power(self, on: bool, duration: float = 0.0) -> None:
        """Set power state for all devices in the group.

        Args:
            on: True to turn on, False to turn off
            duration: Transition duration in seconds (default 0.0)

        Example:
            ```python
            async with discover() as group:
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
            async with discover() as group:
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
            async with discover() as group:
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
            async with discover() as group:
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
        location_data: dict[bytes, list[tuple[Device, LocationInfo]]] = defaultdict(
            list
        )

        # Fetch all location info concurrently
        tasks: dict[str, asyncio.Task[LocationInfo | None]] = {}
        async with asyncio.TaskGroup() as tg:
            for device in self._devices:
                tasks[device.serial] = tg.create_task(device.get_location())

        results: list[tuple[Device, LocationInfo | None]] = []
        for device in self._devices:
            results.append((device, tasks[device.serial].result()))

        # Group by location UUID
        for device, location_info in results:
            if location_info is None:
                continue

            # Skip empty UUIDs (unassigned)
            if location_info.location == b"\x00" * 16:
                continue

            location_data[location_info.location].append((device, location_info))

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
        group_data: dict[bytes, list[tuple[Device, GroupInfo]]] = defaultdict(list)

        tasks: dict[str, asyncio.Task[GroupInfo | None]] = {}
        async with asyncio.TaskGroup() as tg:
            for device in self._devices:
                tasks[device.serial] = tg.create_task(device.get_group())

        # Fetch all group info concurrently
        results: list[tuple[Device, GroupInfo | None]] = []
        for device in self._devices:
            results.append((device, tasks[device.serial].result()))

        # Group by group UUID
        for device, group_info in results:
            if group_info is None:
                continue

            # Skip empty UUIDs (unassigned)
            if group_info.group == b"\x00" * 16:
                continue

            group_data[group_info.group].append((device, group_info))

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
        label_uuids: dict[str, bytes] = {}

        for location_uuid, grouping in self._location_metadata.items():
            label = grouping.label

            # Handle naming conflicts: if two different UUIDs have the same label,
            # append UUID suffix
            if label in label_uuids and label_uuids[label] != location_uuid:
                label = f"{label} ({location_uuid.hex()[:8]})"

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
        label_uuids: dict[str, bytes] = {}

        for group_uuid, grouping in self._group_metadata.items():
            label = grouping.label

            # Handle naming conflicts: if two different UUIDs have the same label,
            # append UUID suffix
            if label in label_uuids and label_uuids[label] != group_uuid:
                label = f"{label} ({group_uuid.hex()[:8]})"

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
            async with discover() as group:
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
            async with discover() as group:
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
            async with discover() as group:
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
            async with discover() as group:
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
            async with discover() as group:
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
        - TileDevice: Uses interpolation for smooth gradients
        - Other devices: No action (themes only apply to color devices)

        Args:
            theme: Theme to apply
            power_on: Turn on devices if True
            duration: Transition duration in seconds

        Example:
            ```python
            from lifx.theme import get_theme

            async with discover() as group:
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

            # Apply theme to all tile devices
            for tile in self.tiles:
                tg.create_task(tile.apply_theme(theme, power_on, duration))

    def invalidate_metadata_cache(self) -> None:
        """Clear all cached location and group metadata.

        Use this if you've changed device locations/groups and want to re-fetch.

        Example:
            ```python
            async with discover() as group:
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


def discover(
    timeout: float = 3.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> DiscoveryContext:
    """Discover LIFX devices and return a discovery context manager.

    This function returns an async context manager that performs device
    discovery and automatically handles connection/disconnection.

    Args:
        timeout: Discovery timeout in seconds (default 3.0)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier

    Returns:
        DiscoveryContext async context manager

    Example:
        ```python
        # Discover and control all devices using context manager
        async with discover() as group:
            await group.set_power(True)
            await group.set_color(Colors.BLUE)
        ```
    """
    return DiscoveryContext(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    )


async def find_lights(
    label_contains: str | None = None,
    timeout: float = 3.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> list[Light]:
    """Find Light devices with optional label filtering.

    Args:
        label_contains: Filter by label substring (case-insensitive)
        timeout: Discovery timeout in seconds (default 3.0)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier

    Returns:
        List of Light instances matching the criteria

    Example:
        ```python
        # Find all lights with "bedroom" in the label
        lights = await find_lights(label_contains="bedroom")
        for light in lights:
            async with light:
                await light.set_color(Colors.WARM_WHITE)
        ```
    """
    discovered = await discover_devices(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    )

    # Detect device types in parallel
    results: list[Device | None] = [None] * len(discovered)

    async def detect_and_store(index: int, disc: DiscoveredDevice) -> None:
        results[index] = await _detect_device_type(disc)

    async with asyncio.TaskGroup() as tg:
        for i, disc in enumerate(discovered):
            tg.create_task(detect_and_store(i, disc))

    devices = [d for d in results if d is not None]

    # Filter to only Light devices (and subclasses like MultiZoneLight, TileDevice)
    lights: list[Light] = [d for d in devices if isinstance(d, Light)]

    # If label filtering is requested, connect and check label
    if label_contains is not None:
        filtered_lights: list[Light] = []
        for light in lights:
            async with light:
                try:
                    label = await light.get_label()
                    if label_contains.lower() in label.lower():
                        filtered_lights.append(light)
                except LifxTimeoutError:
                    # Skip devices that fail to respond
                    _LOGGER.warning(
                        {
                            "class": "find_lights",
                            "method": "filter_devices",
                            "action": "no_response",
                            "serial": light.serial,
                            "ip": light.ip,
                        }
                    )
        return filtered_lights

    return lights


async def find_by_serial(
    serial: bytes | str,
    timeout: float = 3.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> Device | None:
    """Find a specific device by serial number.

    Args:
        serial: Serial number as bytes or hex string (with or without separators)
        timeout: Discovery timeout in seconds (default 3.0)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier

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
    if isinstance(serial, bytes):
        serial_str = serial.hex()
    else:
        serial_str = serial.replace(":", "").replace("-", "").lower()

    discovered = await discover_devices(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    )

    for d in discovered:
        if d.serial.lower() == serial_str:
            # Detect device type and return appropriate class
            return await _detect_device_type(d)

    return None


__all__ = [
    "DiscoveryContext",
    "DeviceGroup",
    "LocationGrouping",
    "GroupGrouping",
    "discover",
    "find_lights",
    "find_by_serial",
]
