"""Tests for HevLight state management using LIFX Emulator."""

from __future__ import annotations

import asyncio

import pytest

from lifx.devices.hev import HevLight, HevLightState


class TestHevLightStateManagement:
    """Tests for HevLight state management using emulator."""

    @pytest.mark.asyncio
    async def test_hev_state_property_before_init_raises(
        self, emulator_devices
    ) -> None:
        """Test accessing state property before initialization raises RuntimeError."""
        hev_light: HevLight = emulator_devices[3]  # d073d5000004

        # State is None before using Device.connect()
        with pytest.raises(RuntimeError, match="State not found."):
            _ = hev_light.state

    @pytest.mark.asyncio
    async def test_initialize_state_creates_hev_state(self, emulator_devices) -> None:
        """Test Device.connect() creates HevLightState instance."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        # Use Device.connect() to get a properly initialized device
        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            # Verify state is HevLightState
            assert hev_light._state is not None
            assert isinstance(hev_light._state, HevLightState)
            assert isinstance(hev_light._state.label, str)
            assert isinstance(hev_light._state.power, int)
            assert hasattr(hev_light._state, "hev_cycle")
            assert hasattr(hev_light._state, "hev_config")
            assert hasattr(hev_light._state, "hev_result")

    @pytest.mark.asyncio
    async def test_state_property_after_init_returns_hev_state(
        self, emulator_devices
    ) -> None:
        """Test state property returns HevLightState after initialization."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            # Access state property
            state = hev_light.state
            assert isinstance(state, HevLightState)
            assert isinstance(state.label, str)
            assert hasattr(state, "hev_cycle")
            assert hasattr(state, "hev_config")
            assert hasattr(state, "hev_result")

    @pytest.mark.asyncio
    async def test_refresh_state_updates_hev_cycle(self, emulator_devices) -> None:
        """Test refresh_state() updates HEV cycle fields."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            assert isinstance(hev_light, HevLight)

            initial_remaining = hev_light._state.hev_cycle.remaining_s

            # Start a HEV cycle
            await hev_light.set_hev_cycle(enable=True, duration_seconds=7200)

            # Refresh state
            await hev_light.refresh_state()

            # HEV cycle should be updated (might be running or just finished)
            assert hev_light.state.hev_cycle.duration_s == 7200
            assert hev_light.state.hev_cycle.remaining_s != initial_remaining

    @pytest.mark.asyncio
    async def test_get_hev_cycle_updates_state(self, emulator_devices) -> None:
        """Test get_hev_cycle() updates state when it exists."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            assert isinstance(hev_light, HevLight)

            # Get HEV cycle state
            state = await hev_light.get_hev_cycle()

            # State should be updated
            assert hev_light.state.hev_cycle.duration_s == state.duration_s
            assert hev_light.state.hev_cycle.remaining_s == state.remaining_s
            assert hev_light.state.hev_cycle.last_power == state.last_power

    @pytest.mark.asyncio
    async def test_set_hev_cycle_optimistic_update(self, emulator_devices) -> None:
        """Test set_hev_cycle() updates state optimistically."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            assert isinstance(hev_light, HevLight)

            # stop any running HEV cycle then wait for the refresh
            await hev_light.set_hev_cycle(enable=False, duration_seconds=0)
            await asyncio.sleep(1)

            initial_remaining = hev_light._state.hev_cycle.remaining_s

            # Set HEV cycle with different duration and wait for refresh
            await hev_light.set_hev_cycle(enable=True, duration_seconds=3600)
            await asyncio.sleep(1)

            # State should reflect the new cycle (remaining time updated)
            assert hev_light.state.hev_cycle.remaining_s >= initial_remaining
            # Verify the cycle is running or was just started
            assert hev_light.state.hev_cycle.duration_s == 3600

    @pytest.mark.asyncio
    async def test_get_hev_config_updates_state(self, emulator_devices) -> None:
        """Test get_hev_config() updates state when it exists."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            assert isinstance(hev_light, HevLight)

            # Get HEV config
            config = await hev_light.get_hev_config()

            # State should be updated
            assert hev_light.state.hev_config.indication == config.indication
            assert hev_light.state.hev_config.duration_s == config.duration_s

    @pytest.mark.asyncio
    async def test_set_hev_config_updates_device(self, emulator_devices) -> None:
        """Test set_hev_config() updates device configuration."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            assert isinstance(hev_light, HevLight)

            # Set HEV config
            await hev_light.set_hev_config(indication=True, duration_seconds=7200)

            # Verify by getting config
            config = await hev_light.get_hev_config()
            assert config.indication is True
            assert config.duration_s == 7200

    @pytest.mark.asyncio
    async def test_get_last_hev_result_updates_state(self, emulator_devices) -> None:
        """Test get_last_hev_result() updates state when it exists."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            assert isinstance(hev_light, HevLight)

            # Get last HEV result
            result = await hev_light.get_last_hev_result()

            # State should be updated
            assert hev_light.state.hev_result == result

    @pytest.mark.asyncio
    async def test_state_dataclass_properties(self, emulator_devices) -> None:
        """Test HevLightState dataclass computed properties."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            state = hev_light.state

            # Test is_on property
            await hev_light.set_power(True)
            await hev_light.refresh_state()
            assert state.is_on is True

            await hev_light.set_power(False)
            await hev_light.refresh_state()
            assert state.is_on is False

            # Test age property (should be very recent)
            age = state.age
            assert age >= 0
            assert age < 5  # Should be less than 5 seconds old

            # Test is_fresh property (should be fresh)
            assert state.is_fresh(max_age=10) is True

    @pytest.mark.asyncio
    async def test_refresh_state_calls_initialize_on_none(
        self, emulator_server, emulator_port
    ):
        """Test refresh_state() raises calls _initialize_sate() when state is None."""
        hev_light = HevLight(
            serial="d073d5000004",
            ip="127.0.0.1",
            port=emulator_port,
        )

        # Don't initialize state - it should be None
        assert hev_light._state is None
        await hev_light.refresh_state()  # type: ignore
        assert isinstance(hev_light.state, HevLightState)
        await hev_light.close()


class TestHevAcknowledgementBasedStateUpdates:
    """Tests that HEV state is only updated when acknowledgements are received."""

    @pytest.mark.asyncio
    async def test_set_hev_config_updates_state_on_ack(self, emulator_devices) -> None:
        """Test set_hev_config() updates both cache and state when ack received."""
        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            # Get initial config
            assert isinstance(hev_light, HevLight)
            initial_config = await hev_light.get_hev_config()
            new_indication = bool(not initial_config.indication)
            new_duration = initial_config.duration_s * 2

            # Set new config
            await hev_light.set_hev_config(
                indication=new_indication, duration_seconds=new_duration
            )

            # Both cache and state should be updated
            assert hev_light._hev_config is not None
            assert hev_light._hev_config.indication is new_indication
            assert hev_light._hev_config.duration_s == new_duration
            assert hev_light.state.hev_config.indication is new_indication
            assert hev_light.state.hev_config.duration_s == new_duration

    @pytest.mark.asyncio
    async def test_set_hev_config_no_update_without_ack(self, emulator_devices) -> None:
        """Test set_hev_config() does NOT update state when ack not received."""
        from unittest.mock import patch

        template: HevLight = emulator_devices[3]  # d073d5000004

        async with await HevLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as hev_light:
            # Get initial config
            assert isinstance(hev_light, HevLight)
            initial_config = hev_light._state.hev_config

            with patch(
                "lifx.network.connection.DeviceConnection.request", return_value=False
            ):
                await hev_light.set_hev_config(indication=True, duration_seconds=7200)

                # State should NOT be updated
                # Cache should not be updated (stays None or unchanged)
                if hev_light._hev_config is not None:
                    assert hev_light._hev_config.indication == initial_config.indication
                    assert hev_light._hev_config.duration_s == initial_config.duration_s
                # State should not change
                assert (
                    hev_light._state.hev_config.indication == initial_config.indication
                )
                assert (
                    hev_light._state.hev_config.duration_s == initial_config.duration_s
                )
