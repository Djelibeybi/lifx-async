"""Tests for Switch device class."""

from __future__ import annotations

import pytest

from lifx.color import HSBK
from lifx.devices.switch import ButtonConfig, Switch, SwitchState
from lifx.exceptions import LifxUnsupportedCommandError
from lifx.protocol import packets
from lifx.protocol.protocol_types import LightHsbk

GREEN = LightHsbk(hue=21845, saturation=65535, brightness=52428, kelvin=3500)
DIM_WHITE = LightHsbk(hue=0, saturation=0, brightness=6553, kelvin=3500)


def _state_config(
    haptic_duration_ms: int = 30,
    backlight_on_color: LightHsbk = GREEN,
    backlight_off_color: LightHsbk = DIM_WHITE,
) -> packets.Button.StateConfig:
    """Build a StateConfig response packet."""
    return packets.Button.StateConfig(
        haptic_duration_ms=haptic_duration_ms,
        backlight_on_color=backlight_on_color,
        backlight_off_color=backlight_off_color,
    )


class TestSwitch:
    """Tests for Switch class."""

    def test_create_switch(self) -> None:
        """Test creating a switch."""
        switch = Switch(
            serial="d073d5010203",
            ip="192.168.1.100",
            port=56700,
        )

        assert switch.serial == "d073d5010203"
        assert switch.ip == "192.168.1.100"
        assert switch.port == 56700
        assert switch.button_config is None

    async def test_get_button_config(self, switch: Switch) -> None:
        """Test getting the button configuration."""
        switch.connection.request.return_value = _state_config()

        config = await switch.get_button_config()

        assert isinstance(config, ButtonConfig)
        assert config.haptic_duration_ms == 30
        assert config.backlight_on_color == HSBK.from_protocol(GREEN)
        assert config.backlight_off_color == HSBK.from_protocol(DIM_WHITE)
        switch.connection.request.assert_called_once()

        # The fetched config is cached
        assert switch.button_config == config

    async def test_get_button_config_sends_get_packet(self, switch: Switch) -> None:
        """Test that get_button_config sends a Button.GetConfig packet."""
        switch.connection.request.return_value = _state_config()

        await switch.get_button_config()

        packet = switch.connection.request.call_args[0][0]
        assert isinstance(packet, packets.Button.GetConfig)

    async def test_get_button_config_unhandled(self, switch: Switch) -> None:
        """Test that StateUnhandled raises LifxUnsupportedCommandError."""
        switch.connection.request.return_value = packets.Device.StateUnhandled(
            unhandled_type=packets.Button.GetConfig.PKT_TYPE
        )

        with pytest.raises(LifxUnsupportedCommandError):
            await switch.get_button_config()

    async def test_set_button_config_all_fields(self, switch: Switch) -> None:
        """Test setting the full button configuration."""
        switch.connection.request.return_value = True

        on_color = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
        off_color = HSBK(hue=0, saturation=0.0, brightness=0.1, kelvin=3500)

        await switch.set_button_config(
            haptic_duration_ms=100,
            backlight_on_color=on_color,
            backlight_off_color=off_color,
        )

        switch.connection.request.assert_called_once()
        packet = switch.connection.request.call_args[0][0]

        assert isinstance(packet, packets.Button.SetConfig)
        assert packet.haptic_duration_ms == 100
        assert packet.backlight_on_color == on_color.to_protocol()
        assert packet.backlight_off_color == off_color.to_protocol()

        # Cache is updated optimistically on acknowledgement
        assert switch.button_config is not None
        assert switch.button_config.haptic_duration_ms == 100
        assert switch.button_config.backlight_on_color == on_color
        assert switch.button_config.backlight_off_color == off_color

    async def test_set_button_config_partial_uses_cached_config(
        self, switch: Switch
    ) -> None:
        """Test that omitted fields are filled from the cached configuration."""
        switch.connection.request.return_value = _state_config()
        await switch.get_button_config()
        switch.connection.request.reset_mock()

        switch.connection.request.return_value = True
        on_color = HSBK(hue=200, saturation=1.0, brightness=0.5, kelvin=3500)

        await switch.set_button_config(backlight_on_color=on_color)

        # Only the set request went out - no extra fetch
        switch.connection.request.assert_called_once()
        packet = switch.connection.request.call_args[0][0]

        assert isinstance(packet, packets.Button.SetConfig)
        assert packet.haptic_duration_ms == 30
        assert packet.backlight_on_color == on_color.to_protocol()
        assert packet.backlight_off_color == DIM_WHITE

    async def test_set_button_config_partial_fetches_when_not_cached(
        self, switch: Switch
    ) -> None:
        """Test that omitted fields are fetched from the device when not cached."""
        switch.connection.request.side_effect = [_state_config(), True]

        await switch.set_button_config(haptic_duration_ms=0)

        assert switch.connection.request.call_count == 2
        get_packet = switch.connection.request.call_args_list[0][0][0]
        set_packet = switch.connection.request.call_args_list[1][0][0]

        assert isinstance(get_packet, packets.Button.GetConfig)
        assert isinstance(set_packet, packets.Button.SetConfig)
        assert set_packet.haptic_duration_ms == 0
        assert set_packet.backlight_on_color == GREEN
        assert set_packet.backlight_off_color == DIM_WHITE

    async def test_set_button_config_haptic_bounds(self, switch: Switch) -> None:
        """Test haptic duration validation."""
        with pytest.raises(ValueError, match="Haptic duration must be 0-500ms"):
            await switch.set_button_config(haptic_duration_ms=-1)

        with pytest.raises(ValueError, match="Haptic duration must be 0-500ms"):
            await switch.set_button_config(haptic_duration_ms=501)

        switch.connection.request.assert_not_called()

    async def test_set_button_config_haptic_limits_accepted(
        self, switch: Switch
    ) -> None:
        """Test that 0 and 500 are valid haptic durations."""
        # First set fetches the config to fill the omitted fields; the second
        # reuses the cache primed by the first, so only three requests go out.
        switch.connection.request.side_effect = [
            _state_config(),
            True,
            True,
        ]

        await switch.set_button_config(haptic_duration_ms=0)
        await switch.set_button_config(haptic_duration_ms=500)

        assert switch.connection.request.call_count == 3

    async def test_set_button_config_unhandled(self, switch: Switch) -> None:
        """Test that StateUnhandled raises LifxUnsupportedCommandError."""
        switch.connection.request.return_value = packets.Device.StateUnhandled(
            unhandled_type=packets.Button.SetConfig.PKT_TYPE
        )

        with pytest.raises(LifxUnsupportedCommandError):
            await switch.set_button_config(
                haptic_duration_ms=30,
                backlight_on_color=HSBK.from_protocol(GREEN),
                backlight_off_color=HSBK.from_protocol(DIM_WHITE),
            )

    async def test_state_raises_before_initialization(self, switch: Switch) -> None:
        """Test that accessing state before initialization raises."""
        with pytest.raises(RuntimeError, match="State not found"):
            _ = switch.state

    async def test_initialize_state(
        self, mock_device_factory, mock_product_info
    ) -> None:
        """Test transactional state initialization for a switch."""
        switch = mock_device_factory(Switch)
        switch._capabilities = mock_product_info(
            pid=70,
            name="LIFX Switch",
            has_color=False,
            has_multizone=False,
            has_relays=True,
            has_buttons=True,
        )

        async def mock_request(packet):
            if isinstance(packet, packets.Button.GetConfig):
                return _state_config()
            if isinstance(packet, packets.Device.GetLabel):
                return packets.Device.StateLabel(label="Hallway Switch")
            if isinstance(packet, packets.Device.GetPower):
                return packets.Device.StatePower(level=65535)
            if isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=3, version_minor=90
                )
            if isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=0, version_minor=1
                )
            if isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16, label="Home", updated_at=0
                )
            if isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label="Hallway", updated_at=0
                )
            raise AssertionError(f"Unexpected packet: {packet!r}")

        switch.connection.request.side_effect = mock_request

        state = await switch._initialize_state()

        assert isinstance(state, SwitchState)
        assert state.label == "Hallway Switch"
        assert state.power == 65535
        assert state.button_config.haptic_duration_ms == 30
        assert state.button_config.backlight_on_color == HSBK.from_protocol(GREEN)
        assert switch.state is state

    async def test_initialize_state_tolerates_unsupported_button_config(
        self, mock_device_factory, mock_product_info
    ) -> None:
        """State initialization survives firmware without packet 909 support."""
        switch = mock_device_factory(Switch)
        switch._capabilities = mock_product_info(
            pid=70,
            name="LIFX Switch",
            has_color=False,
            has_multizone=False,
            has_relays=True,
            has_buttons=True,
        )

        async def mock_request(packet):
            if isinstance(packet, packets.Button.GetConfig):
                return packets.Device.StateUnhandled(
                    unhandled_type=packets.Button.GetConfig.PKT_TYPE
                )
            if isinstance(packet, packets.Device.GetLabel):
                return packets.Device.StateLabel(label="Hallway Switch")
            if isinstance(packet, packets.Device.GetPower):
                return packets.Device.StatePower(level=65535)
            if isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=3, version_minor=90
                )
            if isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=0, version_minor=1
                )
            if isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16, label="Home", updated_at=0
                )
            if isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label="Hallway", updated_at=0
                )
            raise AssertionError(f"Unexpected packet: {packet!r}")

        switch.connection.request.side_effect = mock_request

        state = await switch._initialize_state()

        assert isinstance(state, SwitchState)
        assert state.label == "Hallway Switch"
        assert state.button_config is None
        assert state.as_dict["button_config"] is None

    async def test_refresh_state_updates_button_config(
        self, mock_device_factory, mock_product_info
    ) -> None:
        """Test that refresh_state re-fetches the button configuration."""
        switch = mock_device_factory(Switch)
        switch._capabilities = mock_product_info(
            pid=70,
            name="LIFX Switch",
            has_color=False,
            has_multizone=False,
            has_relays=True,
            has_buttons=True,
        )

        config_holder = {"haptic": 30}

        async def mock_request(packet):
            if isinstance(packet, packets.Button.GetConfig):
                return _state_config(haptic_duration_ms=config_holder["haptic"])
            if isinstance(packet, packets.Device.GetLabel):
                return packets.Device.StateLabel(label="Hallway Switch")
            if isinstance(packet, packets.Device.GetPower):
                return packets.Device.StatePower(level=65535)
            if isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=3, version_minor=90
                )
            if isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=0, version_minor=1
                )
            if isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16, label="Home", updated_at=0
                )
            if isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label="Hallway", updated_at=0
                )
            raise AssertionError(f"Unexpected packet: {packet!r}")

        switch.connection.request.side_effect = mock_request

        await switch._initialize_state()
        assert switch.state.button_config.haptic_duration_ms == 30

        # Device-side change is picked up by refresh
        config_holder["haptic"] = 250
        await switch.refresh_state()

        assert switch.state.button_config.haptic_duration_ms == 250


class TestButtonConfig:
    """Tests for the ButtonConfig dataclass."""

    def test_as_dict(self) -> None:
        """Test ButtonConfig serialisation to dict."""
        config = ButtonConfig(
            haptic_duration_ms=30,
            backlight_on_color=HSBK.from_protocol(GREEN),
            backlight_off_color=HSBK.from_protocol(DIM_WHITE),
        )

        result = config.as_dict

        assert result["haptic_duration_ms"] == 30
        assert result["backlight_on_color"] == HSBK.from_protocol(GREEN).as_dict
        assert result["backlight_off_color"] == HSBK.from_protocol(DIM_WHITE).as_dict
