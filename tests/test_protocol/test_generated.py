"""Tests for generated protocol types and packets."""

from lifx.protocol.packets import Device, Light, Sensor
from lifx.protocol.protocol_types import DeviceService, LightHsbk, LightWaveform


class TestGeneratedEnums:
    """Test generated enum types."""

    def test_service_enum(self) -> None:
        """Test Service enum."""
        assert DeviceService.UDP == 1
        assert isinstance(DeviceService.UDP, int)

    def test_light_waveform_enum(self) -> None:
        """Test LightWaveform enum."""
        assert LightWaveform.SAW == 0
        assert LightWaveform.SINE == 1
        assert LightWaveform.HALF_SINE == 2
        assert LightWaveform.TRIANGLE == 3
        assert LightWaveform.PULSE == 4


class TestGeneratedFields:
    """Test generated field structures."""

    def test_hsbk_creation(self) -> None:
        """Test creating HSBK color."""
        color = LightHsbk(
            hue=32768,
            saturation=65535,
            brightness=32768,
            kelvin=3500,
        )

        assert color.hue == 32768
        assert color.saturation == 65535
        assert color.brightness == 32768
        assert color.kelvin == 3500

    def test_hsbk_is_dataclass(self) -> None:
        """Test HSBK is a dataclass."""
        color = LightHsbk(hue=0, saturation=0, brightness=0, kelvin=3500)
        assert hasattr(color, "__dataclass_fields__")


class TestGeneratedPackets:
    """Test generated packet types."""

    def test_device_get_service(self) -> None:
        """Test Device.GetService packet."""
        packet = Device.GetService()
        assert packet.PKT_TYPE == 2

    def test_device_get_label(self) -> None:
        """Test Device.GetLabel packet."""
        packet = Device.GetLabel()
        assert packet.PKT_TYPE == 23

    def test_device_set_power(self) -> None:
        """Test Device.SetPower packet."""
        packet = Device.SetPower(level=65535)
        assert packet.PKT_TYPE == 21
        assert packet.level == 65535

    def test_device_state_label(self) -> None:
        """Test Device.StateLabel packet."""
        label = b"Test Label" + b"\x00" * 22
        packet = Device.StateLabel(label=label)
        assert packet.PKT_TYPE == 25
        assert packet.label == label

    def test_light_set_color(self) -> None:
        """Test Light.SetColor packet."""
        color = LightHsbk(hue=0, saturation=65535, brightness=32768, kelvin=3500)
        packet = Light.SetColor(
            color=color,
            duration=1000,
        )
        assert packet.PKT_TYPE == 102
        assert packet.color == color
        assert packet.duration == 1000

    def test_light_state(self) -> None:
        """Test Light.StateColor packet."""
        color = LightHsbk(hue=0, saturation=0, brightness=0, kelvin=3500)
        label = b"My Light" + b"\x00" * 24
        packet = Light.StateColor(
            color=color,
            power=65535,
            label=label,
        )
        assert packet.PKT_TYPE == 107
        assert packet.color == color
        assert packet.power == 65535
        assert packet.label == label

    def test_packet_is_dataclass(self) -> None:
        """Test packets are dataclasses."""
        packet = Device.GetService()
        assert hasattr(packet, "__dataclass_fields__")

    def test_packet_has_pkt_type(self) -> None:
        """Test all packets have PKT_TYPE class variable."""
        packets = [
            Device.GetService,
            Device.GetLabel,
            Device.SetPower,
            Light.SetColor,
            Light.StateColor,
        ]

        for packet_class in packets:
            assert hasattr(packet_class, "PKT_TYPE")
            assert isinstance(packet_class.PKT_TYPE, int)

    def test_sensor_get_ambient_light_packet(self) -> None:
        """Test SensorGetAmbientLight packet structure."""
        packet = Sensor.GetAmbientLight()

        assert packet.PKT_TYPE == 401
        assert packet.STATE_TYPE == 402
        assert hasattr(packet, "__dataclass_fields__")

    def test_sensor_state_ambient_light_packet(self) -> None:
        """Test SensorStateAmbientLight packet structure."""
        packet = Sensor.StateAmbientLight(lux=100.5)

        assert packet.PKT_TYPE == 402
        assert packet.lux == 100.5
        assert hasattr(packet, "__dataclass_fields__")

    def test_sensor_state_ambient_light_zero_lux(self) -> None:
        """Test SensorStateAmbientLight with zero lux."""
        packet = Sensor.StateAmbientLight(lux=0.0)

        assert packet.lux == 0.0

    def test_sensor_state_ambient_light_high_lux(self) -> None:
        """Test SensorStateAmbientLight with high lux value."""
        packet = Sensor.StateAmbientLight(lux=50000.0)

        assert packet.lux == 50000.0

    def test_sensor_packets_serialization(self) -> None:
        """Test sensor packet serialization roundtrip."""
        # Test GetAmbientLight (no fields)
        get_packet = Sensor.GetAmbientLight()
        packed = get_packet.pack()
        assert isinstance(packed, bytes)

        # Test StateAmbientLight with lux value
        state_packet = Sensor.StateAmbientLight(lux=250.75)
        packed = state_packet.pack()
        assert isinstance(packed, bytes)
        assert len(packed) == 4  # float32 is 4 bytes

        # Unpack and verify
        unpacked = Sensor.StateAmbientLight.unpack(packed)
        assert abs(unpacked.lux - 250.75) < 0.01  # Float comparison with tolerance
