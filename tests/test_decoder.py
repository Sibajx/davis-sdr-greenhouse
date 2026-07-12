"""
Unit tests for the pure decoding functions in davis_monitor.py (DavisDecoder).

Note: importing davis_monitor.py runs a few module-level side effects
(creates ~/davis_captures/ and configures file logging). This is a known
side effect of the original script and does not affect the outcome of
these tests, but it would be worth refactoring in the future to separate
configuration from pure logic (see README, "Recommended improvements").
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from davis_monitor import DavisDecoder  # noqa: E402


class TestValidateCRC:
    def test_valid_frame_is_accepted(self):
        # 6-byte payload + CRC-16/CCITT (poly 0x1021, init 0) correctly
        # computed for that payload.
        valid_frame = "8000641234569962"
        assert DavisDecoder.validate_crc(valid_frame) is True

    def test_corrupted_frame_is_rejected(self):
        # same CRC as the valid frame, but with one payload byte altered
        corrupted_frame = "8000641234579962"
        assert DavisDecoder.validate_crc(corrupted_frame) is False

    def test_frame_too_short_is_rejected(self):
        assert DavisDecoder.validate_crc("8000") is False

    def test_invalid_hex_does_not_raise(self):
        # non-hexadecimal string: should return False, not raise
        assert DavisDecoder.validate_crc("not_hex") is False

    def test_empty_string_is_rejected(self):
        assert DavisDecoder.validate_crc("") is False


class TestDegreesToCardinal:
    def test_north(self):
        assert DavisDecoder.degrees_to_cardinal(0) == "N"

    def test_east(self):
        assert DavisDecoder.degrees_to_cardinal(90) == "E"

    def test_south(self):
        assert DavisDecoder.degrees_to_cardinal(180) == "S"

    def test_west(self):
        assert DavisDecoder.degrees_to_cardinal(270) == "W"

    def test_wraps_at_360_degrees(self):
        # 360 degrees should wrap back around to "N" (index % 16)
        assert DavisDecoder.degrees_to_cardinal(360) == "N"
