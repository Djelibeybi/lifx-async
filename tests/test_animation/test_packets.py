"""Tests for packet generators."""

from __future__ import annotations

import struct

import pytest

from lifx.animation.packets import (
    HEADER_SIZE,
    LightPacketGenerator,
    MatrixPacketGenerator,
    MultiZonePacketGenerator,
    PacketTemplate,
)

# Test source and target for templates
TEST_SOURCE = 12345
TEST_TARGET = b"\xd0\x73\xd5\x12\x34\x56"


def get_payload(template: PacketTemplate) -> bytes:
    """Extract payload bytes from a packet template."""
    return bytes(template.data[HEADER_SIZE:])


class TestPacketTemplate:
    """Tests for PacketTemplate class."""

    def test_template_structure(self) -> None:
        """Test PacketTemplate has expected fields."""
        data = bytearray(100)
        tmpl = PacketTemplate(
            data=data,
            color_offset=46,
            color_count=64,
            hsbk_start=0,
            fmt=f"<{'HHHH' * 64}",
        )
        assert tmpl.data is data
        assert tmpl.color_offset == 46
        assert tmpl.color_count == 64
        assert tmpl.hsbk_start == 0
        assert tmpl.fmt == f"<{'HHHH' * 64}"


class TestMatrixPacketGenerator:
    """Tests for MatrixPacketGenerator."""

    # Set64 packet type
    SET64_PKT_TYPE = 715

    def test_pixel_count(self) -> None:
        """Test pixel_count returns correct value."""
        gen = MatrixPacketGenerator(tile_count=2, tile_width=8, tile_height=8)
        assert gen.pixel_count() == 128

    def test_create_templates_single_tile(self) -> None:
        """Test template creation for single tile."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        assert len(templates) == 1
        assert isinstance(templates[0], PacketTemplate)

        # Check tile_index in payload (offset 0)
        payload = get_payload(templates[0])
        assert payload[0] == 0  # tile_index

        # Check fb_index in rect (offset 2)
        assert payload[2] == 0  # fb_index - direct to display buffer

    def test_create_templates_all_tiles(self) -> None:
        """Test template creation for all tiles."""
        gen = MatrixPacketGenerator(tile_count=3, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        assert len(templates) == 3
        # Check tile_index in each payload
        assert get_payload(templates[0])[0] == 0
        assert get_payload(templates[1])[0] == 1
        assert get_payload(templates[2])[0] == 2

    def test_update_colors_invalid_length(self) -> None:
        """Test that wrong data length raises error."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 32

        with pytest.raises((IndexError, struct.error)):
            gen.update_colors(templates, hsbk)

    def test_update_colors_packed(self) -> None:
        """Test that HSBK values are correctly packed into packet bytes."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)
        # Use distinct values to verify conversion
        hsbk: list[tuple[int, int, int, int]] = [(65535, 32768, 16384, 4000)] + [
            (0, 0, 0, 3500)
        ] * 63

        gen.update_colors(templates, hsbk)

        payload = get_payload(templates[0])

        # Colors start at offset 10, each color is 8 bytes (H, S, B, K as uint16)
        h, s, b, k = struct.unpack_from("<HHHH", payload, 10)
        assert h == 65535
        assert s == 32768
        assert b == 16384
        assert k == 4000

    def test_duration_zero_in_payload(self) -> None:
        """Test that duration is always 0 for instant animation updates."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])

        # Duration is at offset 6 (uint32) - should always be 0
        (duration,) = struct.unpack_from("<I", payload, 6)
        assert duration == 0

    def test_payload_size(self) -> None:
        """Test that payload has correct size (522 bytes)."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        assert len(payload) == 522

    def test_is_large_tile_standard(self) -> None:
        """Test that 8x8 tile is not detected as large."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        assert gen.is_large_tile is False
        assert gen.packets_per_tile == 1

    def test_is_large_tile_ceiling(self) -> None:
        """Test that 16x8 tile (128 pixels) is detected as large."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        assert gen.is_large_tile is True
        assert gen.packets_per_tile == 2  # 128 / 64 = 2

    def test_is_large_tile_very_large(self) -> None:
        """Test that very large tile (32x16=512 pixels) is detected."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=32, tile_height=16)
        assert gen.is_large_tile is True
        assert gen.packets_per_tile == 8  # 512 / 64 = 8

    def test_header_contains_source(self) -> None:
        """Test that prebaked header contains the source ID."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # Source is at offset 4 in header (uint32)
        (source,) = struct.unpack_from("<I", templates[0].data, 4)
        assert source == TEST_SOURCE

    def test_header_contains_target(self) -> None:
        """Test that prebaked header contains the target serial."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # Target is at offset 8 in header (8 bytes, little-endian)
        target_bytes = templates[0].data[8:14]  # First 6 bytes of target
        assert target_bytes == TEST_TARGET

    def test_header_packet_type(self) -> None:
        """Test that prebaked header contains correct packet type."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # Packet type is at offset 32 in header (uint16)
        (pkt_type,) = struct.unpack_from("<H", templates[0].data, 32)
        assert pkt_type == self.SET64_PKT_TYPE


class TestMatrixPacketGeneratorLargeTile:
    """Tests for MatrixPacketGenerator with large tiles (>64 pixels)."""

    # Packet types
    SET64_PKT_TYPE = 715
    COPY_FB_PKT_TYPE = 716

    def test_pixel_count_large_tile(self) -> None:
        """Test pixel_count for large tile (16x8 = 128 pixels)."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        assert gen.pixel_count() == 128

    def test_create_templates_large_tile_count(self) -> None:
        """Test that large tile creates Set64 + CopyFrameBuffer templates."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # Should have 2 Set64 templates + 1 CopyFrameBuffer
        assert len(templates) == 3

        # Check packet types in headers
        assert struct.unpack_from("<H", templates[0].data, 32)[0] == self.SET64_PKT_TYPE
        assert struct.unpack_from("<H", templates[1].data, 32)[0] == self.SET64_PKT_TYPE
        assert (
            struct.unpack_from("<H", templates[2].data, 32)[0] == self.COPY_FB_PKT_TYPE
        )

    def test_create_templates_large_tile_fb_index(self) -> None:
        """Test that Set64 templates write to fb_index=1 for large tiles."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # Both Set64 templates should have fb_index=1 (offset 2 in payload)
        assert get_payload(templates[0])[2] == 1  # fb_index
        assert get_payload(templates[1])[2] == 1  # fb_index

    def test_create_templates_large_tile_y_offsets(self) -> None:
        """Test that Set64 templates have correct y offsets."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # First template: y=0 (first 4 rows of 16 pixels = 64 pixels)
        # Second template: y=4 (next 4 rows)
        assert get_payload(templates[0])[4] == 0  # y offset
        assert (
            get_payload(templates[1])[4] == 4
        )  # y offset (64 pixels / 16 width = 4 rows)

    def test_create_templates_large_tile_copy_fb_structure(self) -> None:
        """Test CopyFrameBuffer template structure."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        copy_template = templates[2]
        payload = get_payload(copy_template)

        # Verify CopyFrameBuffer payload structure (15 bytes)
        assert len(payload) == 15

        # Offset 0: tile_index
        assert payload[0] == 0
        # Offset 1: length = 1
        assert payload[1] == 1
        # Offset 2: src_fb_index = 1
        assert payload[2] == 1
        # Offset 3: dst_fb_index = 0
        assert payload[3] == 0
        # Offset 4-7: src_x, src_y, dst_x, dst_y = 0
        assert payload[4:8] == bytes([0, 0, 0, 0])
        # Offset 8: width
        assert payload[8] == 16
        # Offset 9: height
        assert payload[9] == 8
        # Offset 10-13: duration = 0 (instant for animation)
        (duration,) = struct.unpack_from("<I", payload, 10)
        assert duration == 0
        # Offset 14: reserved = 0
        assert payload[14] == 0

    def test_create_templates_large_tile_all_zero_duration(self) -> None:
        """Test that all templates (Set64 and CopyFrameBuffer) have duration=0."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # Set64 templates should have duration=0 (offset 6 in payload)
        (duration1,) = struct.unpack_from("<I", get_payload(templates[0]), 6)
        (duration2,) = struct.unpack_from("<I", get_payload(templates[1]), 6)
        assert duration1 == 0
        assert duration2 == 0

        # CopyFrameBuffer should also have duration=0 (offset 10 in payload)
        (copy_duration,) = struct.unpack_from("<I", get_payload(templates[2]), 10)
        assert copy_duration == 0

    def test_update_colors_large_tile(self) -> None:
        """Test that colors are correctly distributed across templates."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)
        # First 64 pixels red, next 64 blue
        hsbk: list[tuple[int, int, int, int]] = [(0, 65535, 65535, 3500)] * 64 + [
            (43690, 65535, 65535, 3500)
        ] * 64

        gen.update_colors(templates, hsbk)

        # First template should have red
        h1, s1, b1, k1 = struct.unpack_from("<HHHH", get_payload(templates[0]), 10)
        assert h1 == 0  # Red

        # Second template should have blue
        h2, s2, b2, k2 = struct.unpack_from("<HHHH", get_payload(templates[1]), 10)
        assert h2 == 43690  # Blue

    def test_create_templates_all_large_tiles(self) -> None:
        """Test that all large tiles create correct templates."""
        gen = MatrixPacketGenerator(tile_count=2, tile_width=16, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # 2 tiles x (2 Set64 + 1 CopyFrameBuffer) = 6 templates
        assert len(templates) == 6

        # Verify packet types in order
        assert struct.unpack_from("<H", templates[0].data, 32)[0] == self.SET64_PKT_TYPE
        assert struct.unpack_from("<H", templates[1].data, 32)[0] == self.SET64_PKT_TYPE
        assert (
            struct.unpack_from("<H", templates[2].data, 32)[0] == self.COPY_FB_PKT_TYPE
        )
        assert struct.unpack_from("<H", templates[3].data, 32)[0] == self.SET64_PKT_TYPE
        assert struct.unpack_from("<H", templates[4].data, 32)[0] == self.SET64_PKT_TYPE
        assert (
            struct.unpack_from("<H", templates[5].data, 32)[0] == self.COPY_FB_PKT_TYPE
        )

        # Verify tile indices
        assert get_payload(templates[0])[0] == 0
        assert get_payload(templates[1])[0] == 0
        assert get_payload(templates[2])[0] == 0
        assert get_payload(templates[3])[0] == 1
        assert get_payload(templates[4])[0] == 1
        assert get_payload(templates[5])[0] == 1

    def test_copy_fb_template_no_colors(self) -> None:
        """Test that CopyFrameBuffer template has color_count=0."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # CopyFrameBuffer is the last template
        copy_template = templates[2]
        assert copy_template.color_count == 0

    def test_update_colors_skips_copy_fb_templates(self) -> None:
        """Test that update_colors skips CopyFrameBuffer templates (color_count=0)."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # Create HSBK data for all 128 pixels
        hsbk: list[tuple[int, int, int, int]] = [(65535, 65535, 65535, 3500)] * 128

        # This should not raise an error - CopyFrameBuffer templates are skipped
        gen.update_colors(templates, hsbk)

        # Verify Set64 templates were updated
        h1 = struct.unpack_from("<H", get_payload(templates[0]), 10)[0]
        assert h1 == 65535

        # CopyFrameBuffer template should be unchanged (no colors to update)
        assert templates[2].color_count == 0


class TestMultiZonePacketGenerator:
    """Tests for MultiZonePacketGenerator (extended multizone only)."""

    # SetExtendedColorZones packet type
    SET_EXTENDED_PKT_TYPE = 510

    def test_pixel_count(self) -> None:
        """Test pixel_count returns zone count."""
        gen = MultiZonePacketGenerator(zone_count=82)
        assert gen.pixel_count() == 82

    def test_create_templates_single_packet(self) -> None:
        """Test template creation for <=82 zones."""
        gen = MultiZonePacketGenerator(zone_count=82)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        assert len(templates) == 1
        assert isinstance(templates[0], PacketTemplate)

        # Check packet type in header
        (pkt_type,) = struct.unpack_from("<H", templates[0].data, 32)
        assert pkt_type == self.SET_EXTENDED_PKT_TYPE

        # Check colors_count in payload (offset 7)
        payload = get_payload(templates[0])
        assert payload[7] == 82  # colors_count

    def test_update_colors_invalid_length(self) -> None:
        """Test that wrong data length raises error."""
        gen = MultiZonePacketGenerator(zone_count=82)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 40

        with pytest.raises((IndexError, struct.error)):
            gen.update_colors(templates, hsbk)

    def test_update_colors_packed(self) -> None:
        """Test that HSBK values are correctly packed into packet bytes."""
        gen = MultiZonePacketGenerator(zone_count=82)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)
        # Use distinct values for first zone
        hsbk: list[tuple[int, int, int, int]] = [(65535, 32768, 16384, 4000)] + [
            (0, 0, 0, 3500)
        ] * 81

        gen.update_colors(templates, hsbk)
        payload = get_payload(templates[0])

        # Colors start at offset 8, each color is 8 bytes
        h, s, b, k = struct.unpack_from("<HHHH", payload, 8)
        assert h == 65535
        assert s == 32768
        assert b == 16384
        assert k == 4000

    def test_duration_zero_in_payload(self) -> None:
        """Test that duration is always 0 for instant animation updates."""
        gen = MultiZonePacketGenerator(zone_count=82)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])

        # Duration is at offset 0 (uint32) - should always be 0
        (duration,) = struct.unpack_from("<I", payload, 0)
        assert duration == 0

    def test_apply_field_set(self) -> None:
        """Test that apply field is set to APPLY (1)."""
        gen = MultiZonePacketGenerator(zone_count=82)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])

        # Apply is at offset 4 (uint8)
        assert payload[4] == 1  # APPLY

    def test_payload_size(self) -> None:
        """Test that payload has correct size (664 bytes)."""
        gen = MultiZonePacketGenerator(zone_count=82)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        assert len(payload) == 664


class TestMultiZonePacketGeneratorLargeZones:
    """Tests for MultiZonePacketGenerator with >82 zones."""

    SET_EXTENDED_PKT_TYPE = 510

    def test_create_templates_120_zones_needs_two_packets(self) -> None:
        """Test that 120 zones (Outdoor Neon Flex) creates 2 templates."""
        gen = MultiZonePacketGenerator(zone_count=120)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        assert len(templates) == 2
        assert (
            struct.unpack_from("<H", templates[0].data, 32)[0]
            == self.SET_EXTENDED_PKT_TYPE
        )
        assert (
            struct.unpack_from("<H", templates[1].data, 32)[0]
            == self.SET_EXTENDED_PKT_TYPE
        )

    def test_create_templates_120_zones_zone_indices(self) -> None:
        """Test that zone indices are correct for 120 zones."""
        gen = MultiZonePacketGenerator(zone_count=120)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # First template: zones 0-81 (82 zones)
        # zone_index at offset 5-6 (uint16)
        zone_idx1 = struct.unpack_from("<H", get_payload(templates[0]), 5)[0]
        assert zone_idx1 == 0
        # colors_count at offset 7
        assert get_payload(templates[0])[7] == 82

        # Second template: zones 82-119 (38 zones)
        zone_idx2 = struct.unpack_from("<H", get_payload(templates[1]), 5)[0]
        assert zone_idx2 == 82
        # colors_count at offset 7
        assert get_payload(templates[1])[7] == 38

    def test_create_templates_164_zones_needs_two_packets(self) -> None:
        """Test that exactly 164 zones (2x82) needs 2 templates."""
        gen = MultiZonePacketGenerator(zone_count=164)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        assert len(templates) == 2
        # Both templates should have 82 zones
        assert get_payload(templates[0])[7] == 82
        assert get_payload(templates[1])[7] == 82

    def test_create_templates_165_zones_needs_three_packets(self) -> None:
        """Test that 165 zones needs 3 templates."""
        gen = MultiZonePacketGenerator(zone_count=165)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        assert len(templates) == 3
        assert get_payload(templates[0])[7] == 82  # First 82
        assert get_payload(templates[1])[7] == 82  # Next 82
        assert get_payload(templates[2])[7] == 1  # Last 1

    def test_update_colors_large_zone(self) -> None:
        """Test that colors are correctly split across templates for 120 zones."""
        gen = MultiZonePacketGenerator(zone_count=120)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)
        # First 82 zones red, remaining 38 zones blue
        hsbk: list[tuple[int, int, int, int]] = [(0, 65535, 65535, 3500)] * 82 + [
            (43690, 65535, 65535, 3500)
        ] * 38

        gen.update_colors(templates, hsbk)

        # First template should have red
        h1 = struct.unpack_from("<H", get_payload(templates[0]), 8)[0]
        assert h1 == 0  # Red

        # Second template should have blue
        h2 = struct.unpack_from("<H", get_payload(templates[1]), 8)[0]
        assert h2 == 43690  # Blue


class TestLightPacketGenerator:
    """Tests for LightPacketGenerator (single light)."""

    SET_COLOR_PKT_TYPE = 102

    def test_pixel_count(self) -> None:
        """Test pixel_count always returns 1."""
        gen = LightPacketGenerator()
        assert gen.pixel_count() == 1

    def test_create_templates_single(self) -> None:
        """Test template creation for single light."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        assert len(templates) == 1
        assert isinstance(templates[0], PacketTemplate)

    def test_header_packet_type(self) -> None:
        """Test header contains SetColor packet type (102)."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        (pkt_type,) = struct.unpack_from("<H", templates[0].data, 32)
        assert pkt_type == self.SET_COLOR_PKT_TYPE

    def test_payload_size(self) -> None:
        """Test payload has correct size (13 bytes)."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        assert len(payload) == 13

    def test_reserved_byte(self) -> None:
        """Test first byte of payload is reserved (0)."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        assert payload[0] == 0

    def test_default_duration_zero(self) -> None:
        """Test default duration is 0 for instant updates."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        (duration,) = struct.unpack_from("<I", payload, 9)
        assert duration == 0

    def test_custom_duration(self) -> None:
        """Test custom duration is correctly packed."""
        gen = LightPacketGenerator(duration_ms=500)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        (duration,) = struct.unpack_from("<I", payload, 9)
        assert duration == 500

    def test_update_colors(self) -> None:
        """Test HSBK values are correctly packed into payload."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)
        hsbk: list[tuple[int, int, int, int]] = [(65535, 32768, 16384, 4000)]

        gen.update_colors(templates, hsbk)

        payload = get_payload(templates[0])
        h, s, b, k = struct.unpack_from("<HHHH", payload, 1)
        assert h == 65535
        assert s == 32768
        assert b == 16384
        assert k == 4000

    def test_header_contains_source(self) -> None:
        """Test prebaked header contains source ID."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        (source,) = struct.unpack_from("<I", templates[0].data, 4)
        assert source == TEST_SOURCE

    def test_header_contains_target(self) -> None:
        """Test prebaked header contains target serial."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        target_bytes = templates[0].data[8:14]
        assert target_bytes == TEST_TARGET

    def test_color_offset(self) -> None:
        """Test color_offset points to correct position (header + 1 reserved byte)."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        assert templates[0].color_offset == HEADER_SIZE + 1

    def test_color_count(self) -> None:
        """Test color_count is 1."""
        gen = LightPacketGenerator()
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        assert templates[0].color_count == 1


class TestMatrixPacketGeneratorDuration:
    """Tests for MatrixPacketGenerator duration_ms parameter."""

    def test_default_duration_zero(self) -> None:
        """Test default duration is 0."""
        gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        (duration,) = struct.unpack_from("<I", payload, 6)
        assert duration == 0

    def test_custom_duration(self) -> None:
        """Test custom duration is packed into Set64 payload."""
        gen = MatrixPacketGenerator(
            tile_count=1, tile_width=8, tile_height=8, duration_ms=100
        )
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        (duration,) = struct.unpack_from("<I", payload, 6)
        assert duration == 100

    def test_custom_duration_large_tile(self) -> None:
        """Test custom duration on large tile Set64 packets."""
        gen = MatrixPacketGenerator(
            tile_count=1, tile_width=16, tile_height=8, duration_ms=200
        )
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        # Set64 packets should have the custom duration
        (duration1,) = struct.unpack_from("<I", get_payload(templates[0]), 6)
        (duration2,) = struct.unpack_from("<I", get_payload(templates[1]), 6)
        assert duration1 == 200
        assert duration2 == 200

        # CopyFrameBuffer should still have duration=0
        (copy_duration,) = struct.unpack_from("<I", get_payload(templates[2]), 10)
        assert copy_duration == 0


class TestMultiZonePacketGeneratorDuration:
    """Tests for MultiZonePacketGenerator duration_ms parameter."""

    def test_default_duration_zero(self) -> None:
        """Test default duration is 0."""
        gen = MultiZonePacketGenerator(zone_count=82)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        (duration,) = struct.unpack_from("<I", payload, 0)
        assert duration == 0

    def test_custom_duration(self) -> None:
        """Test custom duration is packed into payload."""
        gen = MultiZonePacketGenerator(zone_count=82, duration_ms=150)
        templates = gen.create_templates(TEST_SOURCE, TEST_TARGET)

        payload = get_payload(templates[0])
        (duration,) = struct.unpack_from("<I", payload, 0)
        assert duration == 150
