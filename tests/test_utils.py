"""Tests for utility functions in dolly.utils module."""

from uuid import uuid4

import pytest

from dolly.utils import get_gdal_layer_name, get_service_from_title, is_guid


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


class TestGetServiceFromTitle:
    """Test cases for the get_service_from_title function."""

    def test_remove_utah_prefix(self):
        """Test that 'Utah ' prefix is removed from titles."""
        test_cases = [
            ("Utah Municipalities", "municipalities"),
            ("Utah State Parks", "state_parks"),
            ("Utah Counties", "counties"),
            ("Utah Zip Codes", "zip_codes"),
        ]

        for input_title, expected_output in test_cases:
            assert get_service_from_title(input_title) == expected_output

    def test_replace_spaces_with_underscores(self):
        """Test that spaces are replaced with underscores."""
        test_cases = [
            ("City Boundaries", "city_boundaries"),
            ("School Districts", "school_districts"),
            ("Fire Stations", "fire_stations"),
            ("Water Bodies", "water_bodies"),
        ]

        for input_title, expected_output in test_cases:
            assert get_service_from_title(input_title) == expected_output

    def test_convert_to_lowercase(self):
        """Test that titles are converted to lowercase."""
        test_cases = [
            ("MUNICIPALITIES", "municipalities"),
            ("School DISTRICTS", "school_districts"),
            ("Fire Stations", "fire_stations"),
            ("WATER Bodies", "water_bodies"),
        ]

        for input_title, expected_output in test_cases:
            assert get_service_from_title(input_title) == expected_output

    def test_combined_transformations(self):
        """Test that all transformations work together."""
        test_cases = [
            ("Utah City Boundaries", "city_boundaries"),
            ("Utah SCHOOL DISTRICTS", "school_districts"),
            ("Utah Fire Stations", "fire_stations"),
            ("Utah Water Bodies", "water_bodies"),
            ("Utah Environmental Health", "environmental_health"),
            ("Utah DEQ Map Tier 2 Report Year", "deq_map_tier_2_report_year"),
        ]

        for input_title, expected_output in test_cases:
            assert get_service_from_title(input_title) == expected_output

    def test_none_input(self):
        """Test that None input returns None."""
        assert get_service_from_title(None) is None

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert get_service_from_title("") == ""

    def test_only_utah_prefix(self):
        """Test titles that are just 'Utah' or 'Utah '."""
        test_cases = [
            ("Utah", ""),
            ("Utah ", ""),
            ("utah", ""),
            ("utah ", ""),
        ]

        for input_title, expected_output in test_cases:
            with pytest.raises((ValueError, TypeError)):
                get_service_from_title(input_title)

    def test_utah_not_at_beginning(self):
        """Test that 'Utah' in the middle or end is not removed."""
        test_cases = [
            ("Southern Utah Counties", "southern_utah_counties"),
            ("Northern Utah Boundaries", "northern_utah_boundaries"),
            ("Counties Utah", "counties_utah"),
            ("City Courts of Utah", "city_courts_of_utah"),
        ]

        for input_title, expected_output in test_cases:
            assert get_service_from_title(input_title) == expected_output

    def test_multiple_spaces(self):
        """Test titles with multiple consecutive spaces."""
        test_cases = [
            ("Utah  Multiple   Spaces", "multiple_spaces"),
            ("City  Boundaries", "city_boundaries"),
            ("   Leading Spaces", "leading_spaces"),
            ("Trailing Spaces   ", "trailing_spaces"),
        ]

        for input_title, expected_output in test_cases:
            assert get_service_from_title(input_title) == expected_output

    def test_special_characters(self):
        """Test titles with special characters and numbers."""
        test_cases = [
            ("Utah Census 2020", "census_2020"),
            ("Utah Fire-Stations", "fire-stations"),
            ("Utah Water/Sewer", "water/sewer"),
            ("Utah Schools (K-12)", "schools_(k-12)"),
            ("Utah ZIP+4 Codes", "zip+4_codes"),
        ]

        for input_title, expected_output in test_cases:
            assert get_service_from_title(input_title) == expected_output


class TestGetGdalLayerName:
    """Test cases for the get_gdal_layer_name function."""

    def test_standard_table_names(self):
        """Test standard SGID table name conversions."""
        test_cases = [
            ("sgid.transportation.roads", "Transportation.ROADS"),
            ("sgid.boundaries.municipalities", "Boundaries.MUNICIPALITIES"),
            ("sgid.society.cemeteries", "Society.CEMETERIES"),
            ("sgid.environment.deqmap_tier2rptyr", "Environment.DEQMAP_TIER2RPTYR"),
            ("sgid.cadastre.parcels_utah", "Cadastre.PARCELS_UTAH"),
        ]

        for input_table, expected_output in test_cases:
            assert get_gdal_layer_name(input_table) == expected_output

    def test_multi_word_schema_names(self):
        """Test schema names with multiple words."""
        test_cases = [
            ("sgid.health_facilities.hospitals", "Health_Facilities.HOSPITALS"),
            ("sgid.water_quality.monitoring_sites", "Water_Quality.MONITORING_SITES"),
            ("sgid.natural_resources.wetlands", "Natural_Resources.WETLANDS"),
            ("sgid.public_safety.fire_stations", "Public_Safety.FIRE_STATIONS"),
        ]

        for input_table, expected_output in test_cases:
            assert get_gdal_layer_name(input_table) == expected_output

    def test_table_names_with_numbers(self):
        """Test table names containing numbers."""
        test_cases = [
            ("sgid.demographic.census2020_blocks", "Demographic.CENSUS2020_BLOCKS"),
            ("sgid.planning.zoning_districts_2023", "Planning.ZONING_DISTRICTS_2023"),
            ("sgid.utilities.telecom_towers_5g", "Utilities.TELECOM_TOWERS_5G"),
        ]

        for input_table, expected_output in test_cases:
            assert get_gdal_layer_name(input_table) == expected_output

    def test_case_variations(self):
        """Test different case variations in input."""
        test_cases = [
            ("SGID.TRANSPORTATION.ROADS", "Transportation.ROADS"),
            ("sgid.BOUNDARIES.municipalities", "Boundaries.MUNICIPALITIES"),
            ("Sgid.Society.Cemeteries", "Society.CEMETERIES"),
        ]

        for input_table, expected_output in test_cases:
            assert get_gdal_layer_name(input_table) == expected_output

    def test_invalid_table_formats(self):
        """Test invalid table name formats."""
        invalid_tables = [
            "sgid.transportation",  # Missing table name
            "transportation.roads",  # Missing sgid prefix
            "sgid.transportation.roads.extra",  # Too many parts
            "sgid",  # Only prefix
            "roads",  # Only table name
            "",  # Empty string
        ]

        for invalid_table in invalid_tables:
            with pytest.raises(
                ValueError, match="must be in format 'sgid.schema.table'"
            ):
                get_gdal_layer_name(invalid_table)

    def test_special_characters_in_names(self):
        """Test table names with special characters."""
        test_cases = [
            ("sgid.environment.air_quality_pm2_5", "Environment.AIR_QUALITY_PM2_5"),
            ("sgid.transportation.roads_i_15", "Transportation.ROADS_I_15"),
            ("sgid.utilities.gas_wells_co2", "Utilities.GAS_WELLS_CO2"),
        ]

        for input_table, expected_output in test_cases:
            assert get_gdal_layer_name(input_table) == expected_output

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        test_cases = [
            ("sgid.a.b", "A.B"),  # Single character parts
            (
                "sgid.very_long_schema_name.very_long_table_name",
                "Very_Long_Schema_Name.VERY_LONG_TABLE_NAME",
            ),
        ]

        for input_table, expected_output in test_cases:
            assert get_gdal_layer_name(input_table) == expected_output
