"""Tests for utility functions in dolly.utils module."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from dolly.utils import (
    get_gdal_layer_name,
    get_secrets,
    get_service_from_title,
    is_guid,
    retry,
)


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


class TestGetSecrets:
    """Test cases for the get_secrets function."""

    @patch("dolly.utils.json.loads")
    def test_load_secrets_from_cloud_run_mount(self, mock_json_loads):
        """Test loading secrets from Cloud Run mount point at /secrets."""
        expected_secrets = {"api_key": "test_key", "database_url": "test_url"}

        # Mock json.loads to return expected data
        mock_json_loads.return_value = expected_secrets

        # Mock the path operations directly
        with (
            patch("dolly.utils.Path") as mock_path_class,
            patch(
                "dolly.utils.__file__", "/workspaces/dolly-carton/src/dolly/utils.py"
            ),
        ):
            # Set up the path chain: Path(__file__).parent / "secrets"
            mock_file_path = mock_path_class.return_value
            mock_parent = mock_path_class.return_value
            mock_secrets_folder = mock_path_class.return_value
            mock_cloud_secrets_file = mock_path_class.return_value

            # Configure the mock chain
            mock_file_path.parent = mock_parent
            mock_parent.__truediv__ = (
                lambda self, other: mock_secrets_folder
                if other == "secrets"
                else mock_path_class.return_value
            )

            # Configure the secrets folder operations
            mock_secrets_folder.exists.return_value = True
            mock_secrets_folder.__truediv__ = lambda self, other: (
                mock_path_class.return_value
                if other == "app"
                else mock_path_class.return_value
            )

            # Create a mock for the app folder and its operations
            mock_app_folder = mock_path_class.return_value
            mock_app_folder.__truediv__ = (
                lambda self, other: mock_cloud_secrets_file
                if other == "secrets.json"
                else mock_path_class.return_value
            )

            # Override the secrets folder's truediv to return the app folder for "app"
            mock_secrets_folder.__truediv__ = lambda self, other: (
                mock_app_folder
                if other == "app"
                else mock_cloud_secrets_file
                if other == "secrets.json"
                else mock_path_class.return_value
            )

            # Configure cloud secrets file
            mock_cloud_secrets_file.exists.return_value = True
            mock_cloud_secrets_file.read_text.return_value = '{"api_key": "test_key"}'

            # Configure Path constructor
            def path_constructor(path_str):
                if path_str == "/workspaces/dolly-carton/src/dolly/utils.py":
                    return mock_file_path
                return mock_path_class.return_value

            mock_path_class.side_effect = path_constructor

            result = get_secrets()

        assert result == expected_secrets
        mock_json_loads.assert_called_once_with('{"api_key": "test_key"}')

    @patch("dolly.utils.json.loads")
    @patch("dolly.utils.Path")
    def test_load_secrets_from_local_development(
        self, mock_path_class, mock_json_loads
    ):
        """Test loading secrets from local development folder when Cloud Run mount doesn't exist."""
        expected_secrets = {"local_key": "local_value", "debug": True}

        # Mock the cloud folder to NOT exist, local folder to exist
        mock_cloud_folder = mock_path_class.return_value
        mock_cloud_folder.exists.return_value = False

        mock_cloud_secrets_file = mock_path_class.return_value
        mock_cloud_secrets_file.exists.return_value = False

        mock_local_folder = mock_path_class.return_value
        mock_local_folder.exists.return_value = True

        mock_local_file = mock_path_class.return_value
        mock_local_file.exists.return_value = True
        mock_local_file.read_text.return_value = '{"local_key": "local_value"}'

        # Mock json.loads to return expected data
        mock_json_loads.return_value = expected_secrets

        # Mock the Path(__file__).parent / "secrets" chain
        mock_file_path = mock_path_class.return_value
        mock_file_path.parent = mock_path_class.return_value
        mock_file_path.parent.__truediv__ = (
            lambda self, other: mock_local_folder
            if other == "secrets"
            else mock_path_class.return_value
        )
        mock_local_folder.__truediv__ = (
            lambda self, other: mock_local_file
            if other == "secrets.json"
            else mock_path_class.return_value
        )

        def path_constructor(path_str):
            if path_str == "/secrets":
                return mock_cloud_folder
            elif path_str == "/secrets/app/secrets.json":
                return mock_cloud_secrets_file
            elif path_str == "/workspaces/dolly-carton/src/dolly/utils.py":
                return mock_file_path
            return mock_path_class.return_value

        mock_path_class.side_effect = path_constructor

        # Mock sys.modules to not contain pytest and os.getenv to return None
        with (
            patch(
                "dolly.utils.__file__", "/workspaces/dolly-carton/src/dolly/utils.py"
            ),
            patch("sys.modules", {}),
            patch("os.getenv", return_value=None),
        ):
            result = get_secrets()

        assert result == expected_secrets
        mock_json_loads.assert_called_once_with('{"local_key": "local_value"}')

    def test_secrets_file_not_found_returns_mock_in_testing(self):
        """Test that mock secrets are returned when no secrets folder is found in testing mode."""
        # Since this test runs under pytest, it should return mock secrets instead of raising an error
        with patch("dolly.utils.Path") as mock_path_class:
            # Mock both cloud and local folders/files to not exist
            mock_cloud_folder = mock_path_class.return_value
            mock_cloud_folder.exists.return_value = False

            mock_cloud_secrets_file = mock_path_class.return_value
            mock_cloud_secrets_file.exists.return_value = False

            mock_local_folder = mock_path_class.return_value
            mock_local_folder.exists.return_value = False

            mock_local_file = mock_path_class.return_value
            mock_local_file.exists.return_value = False

            # Mock the Path(__file__).parent / "secrets" chain
            mock_file_path = mock_path_class.return_value
            mock_file_path.parent = mock_path_class.return_value
            mock_file_path.parent.__truediv__ = (
                lambda self, other: mock_local_folder
                if other == "secrets"
                else mock_path_class.return_value
            )
            mock_local_folder.__truediv__ = (
                lambda self, other: mock_local_file
                if other == "secrets.json"
                else mock_path_class.return_value
            )

            def path_constructor(path_str):
                if path_str == "/secrets":
                    return mock_cloud_folder
                elif path_str == "/secrets/app/secrets.json":
                    return mock_cloud_secrets_file
                elif path_str == "/workspaces/dolly-carton/src/dolly/utils.py":
                    return mock_file_path
                return mock_path_class.return_value

            mock_path_class.side_effect = path_constructor

            with patch(
                "dolly.utils.__file__", "/workspaces/dolly-carton/src/dolly/utils.py"
            ):
                result = get_secrets()

            # In testing mode, should return mock secrets
            assert result == {
                "AGOL_USERNAME": "test_username",
                "AGOL_PASSWORD": "test_password",
                "INTERNAL_HOST": "test_host",
                "INTERNAL_USERNAME": "test_user",
                "INTERNAL_PASSWORD": "test_password",
                "INTERNAL_DATABASE": "test_db",
                "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test/webhook",
            }

    @patch("dolly.utils.json.loads")
    @patch("dolly.utils.Path")
    def test_invalid_json_raises_error(self, mock_path_class, mock_json_loads):
        """Test handling of invalid JSON in secrets file."""
        # Mock the cloud folder to exist
        mock_cloud_folder = mock_path_class.return_value
        mock_cloud_folder.exists.return_value = True

        mock_secrets_file = mock_path_class.return_value
        mock_secrets_file.read_text.return_value = '{"invalid": json}'

        # Mock json.loads to raise ValueError for invalid JSON
        mock_json_loads.side_effect = ValueError("Invalid JSON")

        def path_constructor(path_str):
            if path_str == "/secrets":
                return mock_cloud_folder
            elif path_str == "/secrets/app/secrets.json":
                return mock_secrets_file
            return mock_path_class.return_value

        mock_path_class.side_effect = path_constructor

        with pytest.raises(ValueError, match="Invalid JSON"):
            get_secrets()

    @patch("dolly.utils.json.loads")
    def test_empty_secrets_file(self, mock_json_loads):
        """Test handling of empty secrets file."""
        # Mock json.loads to return empty dict
        mock_json_loads.return_value = {}

        with (
            patch("dolly.utils.Path") as mock_path_class,
            patch(
                "dolly.utils.__file__", "/workspaces/dolly-carton/src/dolly/utils.py"
            ),
        ):
            # Set up the path chain: Path(__file__).parent / "secrets"
            mock_file_path = mock_path_class.return_value
            mock_parent = mock_path_class.return_value
            mock_secrets_folder = mock_path_class.return_value
            mock_cloud_secrets_file = mock_path_class.return_value

            # Configure the mock chain
            mock_file_path.parent = mock_parent
            mock_parent.__truediv__ = (
                lambda self, other: mock_secrets_folder
                if other == "secrets"
                else mock_path_class.return_value
            )

            # Configure the secrets folder operations
            mock_secrets_folder.exists.return_value = True

            # Create a mock for the app folder and its operations
            mock_app_folder = mock_path_class.return_value
            mock_app_folder.__truediv__ = (
                lambda self, other: mock_cloud_secrets_file
                if other == "secrets.json"
                else mock_path_class.return_value
            )

            # Override the secrets folder's truediv to return the app folder for "app"
            mock_secrets_folder.__truediv__ = lambda self, other: (
                mock_app_folder
                if other == "app"
                else mock_path_class.return_value
                if other == "secrets.json"
                else mock_path_class.return_value
            )

            # Configure cloud secrets file to exist and return empty JSON
            mock_cloud_secrets_file.exists.return_value = True
            mock_cloud_secrets_file.read_text.return_value = "{}"

            # Configure Path constructor
            def path_constructor(path_str):
                if path_str == "/workspaces/dolly-carton/src/dolly/utils.py":
                    return mock_file_path
                return mock_path_class.return_value

            mock_path_class.side_effect = path_constructor

            result = get_secrets()

        assert result == {}
        mock_json_loads.assert_called_once_with("{}")

    @patch("dolly.utils.json.loads")
    def test_secrets_file_with_nested_structure(self, mock_json_loads):
        """Test loading secrets file with nested JSON structure."""
        expected_secrets = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"username": "user", "password": "pass"},
            },
            "api": {"keys": ["key1", "key2"], "timeout": 30},
        }

        nested_json_str = '{"database": {"host": "localhost", "port": 5432}}'

        # Mock json.loads to return nested structure
        mock_json_loads.return_value = expected_secrets

        with (
            patch("dolly.utils.Path") as mock_path_class,
            patch(
                "dolly.utils.__file__", "/workspaces/dolly-carton/src/dolly/utils.py"
            ),
        ):
            # Set up the path chain: Path(__file__).parent / "secrets"
            mock_file_path = mock_path_class.return_value
            mock_parent = mock_path_class.return_value
            mock_secrets_folder = mock_path_class.return_value
            mock_cloud_secrets_file = mock_path_class.return_value

            # Configure the mock chain
            mock_file_path.parent = mock_parent
            mock_parent.__truediv__ = (
                lambda self, other: mock_secrets_folder
                if other == "secrets"
                else mock_path_class.return_value
            )

            # Configure the secrets folder operations
            mock_secrets_folder.exists.return_value = True

            # Create a mock for the app folder and its operations
            mock_app_folder = mock_path_class.return_value
            mock_app_folder.__truediv__ = (
                lambda self, other: mock_cloud_secrets_file
                if other == "secrets.json"
                else mock_path_class.return_value
            )

            # Override the secrets folder's truediv to return the app folder for "app"
            mock_secrets_folder.__truediv__ = lambda self, other: (
                mock_app_folder
                if other == "app"
                else mock_path_class.return_value
                if other == "secrets.json"
                else mock_path_class.return_value
            )

            # Configure cloud secrets file to exist and return nested JSON
            mock_cloud_secrets_file.exists.return_value = True
            mock_cloud_secrets_file.read_text.return_value = nested_json_str

            # Configure Path constructor
            def path_constructor(path_str):
                if path_str == "/workspaces/dolly-carton/src/dolly/utils.py":
                    return mock_file_path
                return mock_path_class.return_value

            mock_path_class.side_effect = path_constructor

            result = get_secrets()

        assert result == expected_secrets
        mock_json_loads.assert_called_once_with(nested_json_str)


class TestRetry:
    """Test cases for the retry function."""

    def test_successful_function_no_retry_needed(self):
        """Test that a successful function executes once and returns the result."""

        def successful_function(value):
            return f"success: {value}"

        result = retry(successful_function, "test")
        assert result == "success: test"

    def test_function_with_args_and_kwargs(self):
        """Test that retry properly passes args and kwargs to the worker function."""

        def function_with_params(arg1, arg2, keyword_arg=None):
            return f"{arg1}-{arg2}-{keyword_arg}"

        result = retry(function_with_params, "first", "second", keyword_arg="third")
        assert result == "first-second-third"

    def test_function_succeeds_after_failures(self):
        """Test that retry succeeds when function fails initially but succeeds on retry."""
        call_count = 0

        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 times
                raise Exception(f"Failure {call_count}")
            return "success on attempt 3"

        with patch("dolly.utils.sleep"):  # Mock sleep to speed up test
            result = retry(flaky_function)
            assert result == "success on attempt 3"
            assert call_count == 3

    def test_function_fails_after_max_retries(self):
        """Test that retry raises the final exception after max retries are exhausted."""
        call_count = 0

        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception(f"Failure {call_count}")

        with patch("dolly.utils.sleep"):  # Mock sleep to speed up test
            with pytest.raises(
                Exception, match="Failure 4"
            ):  # RETRY_MAX_TRIES=3, so 4 total attempts
                retry(always_failing_function)
            assert call_count == 4  # Initial try + 3 retries

    def test_retry_respects_custom_max_tries(self):
        """Test that retry respects custom RETRY_MAX_TRIES setting."""
        call_count = 0

        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception(f"Failure {call_count}")

        # Patch the module-level constants
        with patch("dolly.utils.RETRY_MAX_TRIES", 1), patch("dolly.utils.sleep"):
            with pytest.raises(
                Exception, match="Failure 2"
            ):  # 1 retry = 2 total attempts
                retry(always_failing_function)
            assert call_count == 2

    def test_retry_delay_calculation(self):
        """Test that retry uses exponential backoff (delay^tries)."""
        call_count = 0
        sleep_times = []

        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception(f"Failure {call_count}")

        def mock_sleep(time):
            sleep_times.append(time)

        with patch("dolly.utils.sleep", side_effect=mock_sleep):
            with pytest.raises(Exception):
                retry(always_failing_function)

            # With RETRY_DELAY_TIME=2, should be 2^1=2, 2^2=4, 2^3=8
            expected_delays = [2, 4, 8]
            assert sleep_times == expected_delays

    def test_retry_respects_custom_delay_time(self):
        """Test that retry respects custom RETRY_DELAY_TIME setting."""
        call_count = 0
        sleep_times = []

        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception(f"Failure {call_count}")

        def mock_sleep(time):
            sleep_times.append(time)

        # Use custom delay time of 3 seconds
        with (
            patch("dolly.utils.RETRY_DELAY_TIME", 3),
            patch("dolly.utils.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(Exception):
                retry(always_failing_function)

            # With RETRY_DELAY_TIME=3, should be 3^1=3, 3^2=9, 3^3=27
            expected_delays = [3, 9, 27]
            assert sleep_times == expected_delays

    def test_retry_logs_debug_messages(self):
        """Test that retry logs debug messages for each retry attempt."""
        call_count = 0

        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:  # Fail first time only
                raise Exception("Network error")
            return "success"

        with (
            patch("dolly.utils.sleep"),
            patch("dolly.utils.module_logger") as mock_logger,
        ):
            result = retry(flaky_function)
            assert result == "success"

            # Should have logged one debug message for the retry
            mock_logger.debug.assert_called_once()
            args = mock_logger.debug.call_args[0]
            # The logging call format: ('Exception "%s" thrown on "%s". Retrying after %s seconds...', error, worker_method, wait_time)
            assert "Network error" in str(args[1])  # error message (Exception object)
            assert args[2] == flaky_function  # worker_method
            assert args[3] == 2  # wait_time (2^1)

    def test_retry_preserves_exception_type(self):
        """Test that retry preserves the original exception type."""

        def function_with_specific_error():
            raise ValueError("Specific error message")

        with patch("dolly.utils.sleep"):
            with pytest.raises(ValueError, match="Specific error message"):
                retry(function_with_specific_error)

    def test_retry_with_no_arguments(self):
        """Test that retry works with functions that take no arguments."""
        call_count = 0

        def no_args_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Fail once")
            return 42

        with patch("dolly.utils.sleep"):
            result = retry(no_args_function)
            assert result == 42
            assert call_count == 2

    def test_retry_with_complex_return_types(self):
        """Test that retry properly returns complex data types."""

        def function_returning_dict():
            return {"key": "value", "number": 123, "list": [1, 2, 3]}

        result = retry(function_returning_dict)
        assert result == {"key": "value", "number": 123, "list": [1, 2, 3]}

    def test_retry_with_none_return(self):
        """Test that retry properly handles functions that return None."""

        def function_returning_none():
            return None

        result = retry(function_returning_none)
        assert result is None


class TestFeatureCountingFunctions:
    """Test cases for feature counting utility functions."""

    def test_count_features_in_internal_table_not_implemented(self):
        """Test that internal table counting raises NotImplementedError."""
        from dolly.utils import count_features_in_internal_table

        with pytest.raises(NotImplementedError):
            count_features_in_internal_table("sgid.test.table")

    def test_count_features_in_fgdb_layer_not_implemented(self):
        """Test that FGDB layer counting raises NotImplementedError."""
        from dolly.utils import count_features_in_fgdb_layer

        with pytest.raises(NotImplementedError):
            count_features_in_fgdb_layer("/path/to/test.gdb", "test_layer")

    def test_count_features_in_agol_service_not_implemented(self):
        """Test that AGOL service counting raises NotImplementedError."""
        from dolly.utils import count_features_in_agol_service

        mock_service = MagicMock()
        with pytest.raises(NotImplementedError):
            count_features_in_agol_service(mock_service)
