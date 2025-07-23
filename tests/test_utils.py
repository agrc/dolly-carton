"""Tests for utility functions in dolly.utils module."""

from uuid import uuid4

import pytest

from dolly.utils import is_guid


class TestIsGuid:
    """Test cases for the is_guid function."""

    def test_valid_guid_string(self):
        """Test that valid GUID strings return True."""
        valid_guids = [
            "da0db6d91f134adfa55ca622b9b36427",
            "123456781234567812345678abcdef01",
            "ABCDEF012345678912345678ABCDEF01",
            "00000000000000000000000000000000",
            "ffffffffffffffffffffffffffffffff",
            str(uuid4()).replace(
                "-", ""
            ),  # Generate a random valid UUID without hyphens
        ]

        for guid in valid_guids:
            assert is_guid(guid) is True, f"Expected {guid} to be valid"

    def test_valid_guid_different_cases(self):
        """Test that GUIDs with different cases are valid."""
        guid_lower = "da0db6d91f134adfa55ca622b9b36427"
        guid_upper = "DA0DB6D91F134ADFA55CA622B9B36427"
        guid_mixed = "Da0Db6D91F134AdFa55Ca622B9B36427"

        assert is_guid(guid_lower) is True
        assert is_guid(guid_upper) is True
        assert is_guid(guid_mixed) is True

    def test_invalid_guid_strings(self):
        """Test that invalid GUID strings return False."""
        invalid_guids = [
            "hosted by DNR",
            "not-a-guid-at-all",
            "some descriptive text",
            "123",
            "",  # Empty string
            "table name",
            "feature service",
            "data source unknown",
            "published by AGRC",
            "municipal boundaries",
        ]

        for invalid_guid in invalid_guids:
            assert is_guid(invalid_guid) is False, (
                f"Expected {invalid_guid} to be invalid"
            )

    def test_none_input(self):
        """Test that None input raises TypeError or returns False."""
        with pytest.raises(TypeError):
            is_guid(None)

    def test_non_string_inputs(self):
        """Test that non-string inputs raise TypeError."""
        non_string_inputs = [
            123,
            12.34,
            [],
            {},
            uuid4(),  # UUID object, not string
            True,
            False,
        ]

        for non_string_input in non_string_inputs:
            with pytest.raises((TypeError, AttributeError)):
                is_guid(non_string_input)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        edge_cases = [
            "   da0db6d91f134adfa55ca622b9b36427   ",  # With whitespace
            "\tda0db6d91f134adfa55ca622b9b36427\n",  # With tabs/newlines
            "da0db6d91f134adfa55ca622b9b36427\x00",  # With null character
        ]

        for edge_case in edge_cases:
            # These should be invalid because UUID() is strict about format
            assert is_guid(edge_case) is False, (
                f"Expected {repr(edge_case)} to be invalid"
            )

    def test_special_characters(self):
        """Test strings with special characters."""
        special_char_cases = [
            "da0db6d91f134adfa55ca622b9b3642!",
            "da0db6d91f134adfa55ca622b9b364@7",
            "da0db6d91f134adfa55ca622b9b364#7",
            "da0db6d91f134adfa55ca622b9b364$7",
        ]

        for special_case in special_char_cases:
            assert is_guid(special_case) is False, (
                f"Expected {special_case} to be invalid"
            )
