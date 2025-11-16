"""Tests for HEV light device class."""

from __future__ import annotations

import pytest

from lifx.devices.hev import HevLight
from lifx.protocol import packets
from lifx.protocol.models import HevConfig, HevCycleState
from lifx.protocol.protocol_types import LightLastHevCycleResult


class TestHevLight:
    """Tests for HevLight class."""

    def test_create_hev_light(self) -> None:
        """Test creating a HEV light."""
        light = HevLight(
            serial="d073d5010203",
            ip="192.168.1.100",
            port=56700,
        )

        assert light.serial == "d073d5010203"
        assert light.ip == "192.168.1.100"
        assert light.port == 56700

    async def test_get_hev_cycle(self, hev_light: HevLight) -> None:
        """Test getting HEV cycle state."""
        # Mock StateHevCycle response
        mock_state = packets.Light.StateHevCycle(
            duration_s=3600,
            remaining_s=1800,
            last_power=True,
        )
        hev_light.connection.request.return_value = mock_state

        cycle_state = await hev_light.get_hev_cycle()

        assert isinstance(cycle_state, HevCycleState)
        assert cycle_state.duration_s == 3600
        assert cycle_state.remaining_s == 1800
        assert cycle_state.last_power is True
        assert cycle_state.is_running is True
        hev_light.connection.request.assert_called_once()

    async def test_get_hev_cycle_not_running(self, hev_light: HevLight) -> None:
        """Test getting HEV cycle state when not running."""
        mock_state = packets.Light.StateHevCycle(
            duration_s=3600,
            remaining_s=0,
            last_power=False,
        )
        hev_light.connection.request.return_value = mock_state

        cycle_state = await hev_light.get_hev_cycle()

        assert cycle_state.remaining_s == 0
        assert cycle_state.is_running is False

    async def test_set_hev_cycle_enable(self, hev_light: HevLight) -> None:
        """Test starting a HEV cleaning cycle."""
        hev_light.connection.request.return_value = True

        await hev_light.set_hev_cycle(enable=True, duration_seconds=7200)

        # Verify packet was sent
        hev_light.connection.request.assert_called_once()
        call_args = hev_light.connection.request.call_args
        packet = call_args[0][0]

        assert isinstance(packet, packets.Light.SetHevCycle)
        assert packet.enable is True
        assert packet.duration_s == 7200

    async def test_set_hev_cycle_disable(self, hev_light: HevLight) -> None:
        """Test stopping a HEV cleaning cycle."""
        hev_light.connection.request.return_value = True

        await hev_light.set_hev_cycle(enable=False, duration_seconds=0)

        call_args = hev_light.connection.request.call_args
        packet = call_args[0][0]

        assert packet.enable is False
        assert packet.duration_s == 0

    async def test_set_hev_cycle_invalid_duration(self, hev_light: HevLight) -> None:
        """Test setting HEV cycle with invalid duration."""
        with pytest.raises(ValueError, match="Duration must be non-negative"):
            await hev_light.set_hev_cycle(enable=True, duration_seconds=-100)

    async def test_get_hev_config(self, hev_light: HevLight) -> None:
        """Test getting HEV configuration."""
        # Mock StateHevCycleConfiguration response
        mock_state = packets.Light.StateHevCycleConfiguration(
            indication=True,
            duration_s=7200,
        )
        hev_light.connection.request.return_value = mock_state

        config = await hev_light.get_hev_config()

        assert isinstance(config, HevConfig)
        assert config.indication is True
        assert config.duration_s == 7200
        hev_light.connection.request.assert_called_once()

    async def test_set_hev_config(self, hev_light: HevLight) -> None:
        """Test setting HEV configuration."""
        hev_light.connection.request.return_value = True

        await hev_light.set_hev_config(indication=True, duration_seconds=3600)

        # Verify packet was sent
        hev_light.connection.request.assert_called_once()
        call_args = hev_light.connection.request.call_args
        packet = call_args[0][0]

        assert isinstance(packet, packets.Light.SetHevCycleConfiguration)
        assert packet.indication is True
        assert packet.duration_s == 3600

    async def test_set_hev_config_invalid_duration(self, hev_light: HevLight) -> None:
        """Test setting HEV config with invalid duration."""
        with pytest.raises(ValueError, match="Duration must be non-negative"):
            await hev_light.set_hev_config(indication=True, duration_seconds=-1)

    async def test_get_last_hev_result_success(self, hev_light: HevLight) -> None:
        """Test getting last HEV cycle result - success."""
        mock_state = packets.Light.StateLastHevCycleResult(
            result=LightLastHevCycleResult.SUCCESS,
        )
        hev_light.connection.request.return_value = mock_state

        result = await hev_light.get_last_hev_result()

        assert result == LightLastHevCycleResult.SUCCESS
        hev_light.connection.request.assert_called_once()

    async def test_get_last_hev_result_interrupted(self, hev_light: HevLight) -> None:
        """Test getting last HEV cycle result - interrupted."""
        mock_state = packets.Light.StateLastHevCycleResult(
            result=LightLastHevCycleResult.INTERRUPTED_BY_LAN,
        )
        hev_light.connection.request.return_value = mock_state

        result = await hev_light.get_last_hev_result()

        assert result == LightLastHevCycleResult.INTERRUPTED_BY_LAN

    async def test_get_last_hev_result_none(self, hev_light: HevLight) -> None:
        """Test getting last HEV cycle result - none."""
        mock_state = packets.Light.StateLastHevCycleResult(
            result=LightLastHevCycleResult.NONE,
        )
        hev_light.connection.request.return_value = mock_state

        result = await hev_light.get_last_hev_result()

        assert result == LightLastHevCycleResult.NONE

    async def test_hev_cycle_caching(self, hev_light: HevLight) -> None:
        """Test HEV cycle state caching."""
        mock_state = packets.Light.StateHevCycle(
            duration_s=3600,
            remaining_s=1800,
            last_power=True,
        )
        hev_light.connection.request.return_value = mock_state

        # First call should hit the device
        _ = await hev_light.get_hev_cycle()
        assert hev_light.connection.request.call_count == 1

    async def test_hev_config_caching(self, hev_light: HevLight) -> None:
        """Test HEV config caching."""
        mock_state = packets.Light.StateHevCycleConfiguration(
            indication=True,
            duration_s=7200,
        )
        hev_light.connection.request.return_value = mock_state

        # First call should hit the device and store the value
        config1 = await hev_light.get_hev_config()
        assert hev_light.connection.request.call_count == 1

        # Check that value is stored in cache
        stored = hev_light.hev_config
        assert stored is not None
        assert stored.duration_s == config1.duration_s

    async def test_hev_result_caching(self, hev_light: HevLight) -> None:
        """Test HEV result caching."""
        mock_state = packets.Light.StateLastHevCycleResult(
            result=LightLastHevCycleResult.SUCCESS,
        )
        hev_light.connection.request.return_value = mock_state

        # First call should hit the device and store the value
        result1 = await hev_light.get_last_hev_result()
        assert hev_light.connection.request.call_count == 1

        # Check that value is stored in cache
        stored = hev_light.hev_result
        assert stored is not None
        assert stored == result1

    async def test_hev_config_property(self, hev_light: HevLight) -> None:
        """Test hev_config property returns cached value."""
        # Initially no stored value
        assert hev_light.hev_config is None

        # Set stored value
        config = HevConfig(indication=True, duration_s=7200)
        hev_light._hev_config = config

        # Property should return stored value
        stored = hev_light.hev_config
        assert stored is not None
        assert stored == config
        assert stored.duration_s == 7200

    async def test_hev_result_property(self, hev_light: HevLight) -> None:
        """Test hev_result property returns cached value."""
        # Initially no stored value
        assert hev_light.hev_result is None

        # Set stored value
        hev_light._hev_result = LightLastHevCycleResult.SUCCESS

        # Property should return stored value
        stored = hev_light.hev_result
        assert stored is not None
        assert stored == LightLastHevCycleResult.SUCCESS

    async def test_set_hev_config_updates_store(self, hev_light: HevLight) -> None:
        """Test that setting HEV config updates the store."""
        hev_light.connection.request.return_value = True

        await hev_light.set_hev_config(indication=False, duration_seconds=5400)

        # Check store was updated in cache
        stored = hev_light.hev_config
        assert stored is not None
        assert stored.indication is False
        assert stored.duration_s == 5400
