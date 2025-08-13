"""Tests for internal.py functions"""

from datetime import datetime
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock, patch

import pytest

from dolly.internal import (
    _build_change_detection_query,
    _build_update_agol_item_query,
    _copy_table_to_fgdb,
    _generate_output_path,
    _get_geometry_option,
    _prepare_gdal_options,
    create_fgdb,
    get_agol_items_lookup,
    get_updated_tables,
    update_agol_item,
)


class TestGenerateOutputPath:
    """Test cases for the _generate_output_path function."""

    def test_single_table_generates_category_specific_path(self):
        """Test that single table generates path with category and service name."""
        tables = ["sgid.society.cemeteries"]
        agol_lookup = {"sgid.society.cemeteries": {"published_name": "Utah Cemeteries"}}

        with patch("dolly.internal.OUTPUT_PATH", Path("/test/output")):
            result = _generate_output_path(tables, agol_lookup)

        assert result == Path("/test/output/society_cemeteries.gdb")

    def test_single_table_with_complex_title(self):
        """Test single table with title that needs processing."""
        tables = ["sgid.transportation.roads"]
        agol_lookup = {"sgid.transportation.roads": {"published_name": "Utah Roads"}}

        with patch("dolly.internal.OUTPUT_PATH", Path("/test/output")):
            result = _generate_output_path(tables, agol_lookup)

        assert result == Path("/test/output/transportation_roads.gdb")

    def test_multiple_tables_uses_default_fgdb_path(self):
        """Test that multiple tables use the default FGDB_PATH."""
        tables = ["sgid.society.cemeteries", "sgid.transportation.roads"]
        agol_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"},
            "sgid.transportation.roads": {"published_name": "Utah Roads"},
        }

        with patch("dolly.internal.FGDB_PATH", Path("/test/upload.gdb")):
            result = _generate_output_path(tables, agol_lookup)

        assert result == Path("/test/upload.gdb")

    def test_single_table_with_multi_word_category(self):
        """Test single table with multi-word schema category."""
        tables = ["sgid.health_facilities.hospitals"]
        agol_lookup = {
            "sgid.health_facilities.hospitals": {"published_name": "Utah Hospitals"}
        }

        with patch("dolly.internal.OUTPUT_PATH", Path("/test/output")):
            result = _generate_output_path(tables, agol_lookup)

        assert result == Path("/test/output/health_facilities_hospitals.gdb")

    def test_empty_tables_list(self):
        """Test behavior with empty tables list - should use default path."""
        tables = []
        agol_lookup = {}

        with patch("dolly.internal.FGDB_PATH", Path("/test/upload.gdb")):
            result = _generate_output_path(tables, agol_lookup)

        assert result == Path("/test/upload.gdb")


class TestGetGeometryOption:
    """Test cases for the _get_geometry_option function."""

    def test_polygon_geometry_type(self):
        """Test that POLYGON maps to MULTIPOLYGON."""
        result = _get_geometry_option("POLYGON")
        assert result == "MULTIPOLYGON"

    def test_polyline_geometry_type(self):
        """Test that POLYLINE maps to MULTILINESTRING."""
        result = _get_geometry_option("POLYLINE")
        assert result == "MULTILINESTRING"

    def test_stand_alone_geometry_type(self):
        """Test that STAND ALONE maps to NONE."""
        result = _get_geometry_option("STAND ALONE")
        assert result == "NONE"

    def test_point_geometry_type_passthrough(self):
        """Test that POINT geometry type passes through unchanged."""
        result = _get_geometry_option("POINT")
        assert result == "POINT"

    def test_unknown_geometry_type_passthrough(self):
        """Test that unknown geometry types pass through unchanged."""
        with pytest.raises(ValueError, match="Unknown geometry type: CUSTOM_GEOMETRY"):
            _get_geometry_option("CUSTOM_GEOMETRY")

    def test_empty_string_geometry_type(self):
        """Test handling of empty string geometry type."""
        with pytest.raises(ValueError, match="Unknown geometry type: "):
            _get_geometry_option("")


class TestBuildChangeDetectionQuery:
    """Test cases for the _build_change_detection_query function."""

    def test_query_structure_and_format(self):
        """Test that query has correct structure and datetime formatting."""
        test_datetime = datetime(2025, 1, 15, 14, 30, 45)

        result = _build_change_detection_query(test_datetime)

        expected_query = dedent("""
        SELECT table_name FROM SGID.META.ChangeDetection
        WHERE last_modified > '2025-01-15 14:30:45'
    """)
        assert result.strip() == expected_query.strip()

    def test_datetime_formatting_edge_cases(self):
        """Test datetime formatting with edge cases."""
        # Test with single digit values
        test_datetime = datetime(2025, 1, 1, 1, 1, 1)

        result = _build_change_detection_query(test_datetime)

        assert "'2025-01-01 01:01:01'" in result

    def test_query_contains_required_elements(self):
        """Test that query contains all required SQL elements."""
        test_datetime = datetime(2025, 7, 25, 12, 0, 0)

        result = _build_change_detection_query(test_datetime)

        # Check for required SQL components
        assert "SELECT table_name" in result
        assert "FROM SGID.META.ChangeDetection" in result
        assert "WHERE last_modified >" in result
        assert "2025-07-25 12:00:00" in result


class TestGetUpdatedTables:
    """Test cases for the get_updated_tables function."""

    @patch("dolly.internal.APP_ENVIRONMENT", "dev")
    @patch("dolly.internal.DEV_MOCKS_PATH")
    def test_dev_environment_returns_mock_data(self, mock_path):
        """Test that dev environment returns mock data."""
        mock_path.read_text.return_value = '{"updated_tables": ["table1", "table2"]}'

        result = get_updated_tables(datetime.now())

        assert result == ["table1", "table2"]
        mock_path.read_text.assert_called_once_with(encoding="utf-8")

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._build_change_detection_query")
    def test_production_environment_uses_database(self, mock_query_builder):
        """Test that production environment queries the database."""
        # Setup mocks
        mock_query_builder.return_value = "SELECT table_name FROM ChangeDetection"
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("table1",), ("table2",)]

        test_datetime = datetime(2025, 1, 15, 12, 0, 0)

        result = get_updated_tables(test_datetime, mock_connection)

        assert result == ["table1", "table2"]
        mock_query_builder.assert_called_once_with(test_datetime)
        mock_connection.cursor.assert_called_once()
        mock_cursor.execute.assert_called_once_with(
            "SELECT table_name FROM ChangeDetection"
        )
        mock_cursor.fetchall.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._get_database_connection")
    @patch("dolly.internal._build_change_detection_query")
    def test_creates_connection_when_none_provided(
        self, mock_query_builder, mock_get_connection
    ):
        """Test that function creates connection when none provided."""
        # Setup mocks
        mock_query_builder.return_value = "SELECT table_name FROM ChangeDetection"
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("table1",)]
        mock_get_connection.return_value = mock_connection

        result = get_updated_tables(datetime.now())

        assert result == ["table1"]
        mock_get_connection.assert_called_once()
        mock_connection.close.assert_called_once()

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._build_change_detection_query")
    def test_closes_provided_connection(self, mock_query_builder):
        """Test that function closes provided connection."""
        # Setup mocks
        mock_query_builder.return_value = "SELECT table_name FROM ChangeDetection"
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("table1",)]

        result = get_updated_tables(datetime.now(), mock_connection)

        assert result == ["table1"]
        mock_connection.close.assert_called_once()


class TestGetAgolItemsLookup:
    """Test cases for the get_agol_items_lookup function."""

    @patch("dolly.internal.APP_ENVIRONMENT", "dev")
    @patch("dolly.internal.DEV_MOCKS_PATH")
    def test_dev_environment_returns_mock_data(self, mock_path):
        """Test that dev environment returns mock data."""
        mock_path.read_text.return_value = '{"agol_items_lookup": {"table1": {"item_id": "123", "geometry_type": "POLYGON"}}}'

        result = get_agol_items_lookup()

        assert "table1" in result
        mock_path.read_text.assert_called_once_with(encoding="utf-8")

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal.is_guid")
    def test_production_environment_filters_invalid_guids(self, mock_is_guid):
        """Test that production environment filters out invalid GUIDs."""
        # Setup mocks
        mock_is_guid.side_effect = lambda x: x == "valid-guid-123"

        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("table1", "valid-guid-123", "POLYGON", "Table 1"),
            ("table2", "invalid-guid", "POINT", "Table 2"),
            ("table3", None, "POLYLINE", "Table 3"),
        ]

        result = get_agol_items_lookup(mock_connection)

        # Should only include table1 (valid GUID) and table3 (None GUID)
        assert len(result) == 2
        assert "table1" in result
        assert "table3" in result
        assert "table2" not in result  # Filtered out due to invalid GUID

        assert result["table1"]["item_id"] == "valid-guid-123"
        assert result["table3"]["item_id"] is None

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._get_database_connection")
    @patch("dolly.internal.is_guid")
    def test_creates_connection_when_none_provided(
        self, mock_is_guid, mock_get_connection
    ):
        """Test that function creates connection when none provided."""
        # Setup mocks
        mock_is_guid.return_value = True
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("table1", "guid-123", "POLYGON", "Table 1")
        ]
        mock_get_connection.return_value = mock_connection

        result = get_agol_items_lookup()

        assert "table1" in result
        mock_get_connection.assert_called_once()
        mock_connection.close.assert_called_once()

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal.is_guid")
    def test_closes_provided_connection(self, mock_is_guid):
        """Test that function closes provided connection."""
        # Setup mocks
        mock_is_guid.return_value = True
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("table1", "guid-123", "POLYGON", "Table 1")
        ]

        result = get_agol_items_lookup(mock_connection)

        assert "table1" in result
        mock_connection.close.assert_called_once()


class TestCreateFgdb:
    """Test cases for the create_fgdb function."""

    @patch("dolly.internal.get_table_field_domains")
    @patch("dolly.internal._get_database_connection")
    @patch("dolly.internal._generate_output_path")
    @patch("dolly.internal.get_gdal_layer_name")
    @patch("dolly.internal._get_geometry_option")
    @patch("dolly.internal.get_service_from_title")
    @patch("dolly.internal.gdal.VectorTranslate")
    @patch("dolly.internal.logger")
    def test_successful_fgdb_creation(
        self,
        mock_logger,
        mock_translate,
        mock_get_service,
        mock_get_geom_option,
        mock_get_layer_name,
        mock_generate_path,
        mock_get_db_connection,
        mock_get_table_field_domains,
    ):
        """Test successful FGDB creation with provided GDAL connection."""
        # Setup mocks
        mock_gdal_connection = Mock()
        mock_gdal_connection.GetLayerCount.return_value = 5

        mock_db_connection = Mock()
        mock_get_db_connection.return_value = mock_db_connection

        # Mock field domains function to return empty dict
        mock_get_table_field_domains.return_value = {}

        mock_generate_path.return_value = Path("/test/output.gdb")
        mock_get_layer_name.return_value = "test_layer"
        mock_get_geom_option.return_value = "MULTIPOLYGON"
        mock_get_service.return_value = "test_service"
        mock_translate.return_value = None  # VectorTranslate returns None on success

        tables = ["sgid.test.table1"]
        agol_lookup = {
            "sgid.test.table1": {
                "geometry_type": "POLYGON",
                "published_name": "Test Table",
            }
        }

        result = create_fgdb(tables, agol_lookup, gdal_connection=mock_gdal_connection)

        assert result == Path("/test/output.gdb")
        mock_gdal_connection.GetLayerCount.assert_called_once()
        mock_translate.assert_called_once()
        mock_logger.info.assert_called()

    @patch("dolly.internal.get_table_field_domains")
    @patch("dolly.internal._get_database_connection")
    @patch("dolly.internal._get_gdal_connection")
    @patch("dolly.internal._generate_output_path")
    @patch("dolly.internal.get_gdal_layer_name")
    @patch("dolly.internal._get_geometry_option")
    @patch("dolly.internal.get_service_from_title")
    @patch("dolly.internal.gdal.VectorTranslate")
    def test_creates_gdal_connection_when_none_provided(
        self,
        mock_translate,
        mock_get_service,
        mock_get_geom_option,
        mock_get_layer_name,
        mock_generate_path,
        mock_get_gdal_connection,
        mock_get_db_connection,
        mock_get_table_field_domains,
    ):
        """Test that function creates GDAL connection when none provided."""
        # Setup mocks
        mock_gdal_connection = Mock()
        mock_gdal_connection.GetLayerCount.return_value = 5
        mock_get_gdal_connection.return_value = mock_gdal_connection

        mock_db_connection = Mock()
        mock_get_db_connection.return_value = mock_db_connection

        # Mock field domains function to return empty dict
        mock_get_table_field_domains.return_value = {}

        mock_generate_path.return_value = Path("/test/output.gdb")
        mock_get_layer_name.return_value = "test_layer"
        mock_get_geom_option.return_value = "MULTIPOLYGON"
        mock_get_service.return_value = "test_service"
        mock_translate.return_value = None

        tables = ["sgid.test.table1"]
        agol_lookup = {
            "sgid.test.table1": {
                "geometry_type": "POLYGON",
                "published_name": "Test Table",
            }
        }

        result = create_fgdb(tables, agol_lookup)

        assert result == Path("/test/output.gdb")
        mock_get_gdal_connection.assert_called_once()
        mock_gdal_connection.GetLayerCount.assert_called_once()
        mock_translate.assert_called_once()

    def test_raises_error_for_empty_tables_list(self):
        """Test that function raises ValueError for empty tables list."""
        mock_gdal_connection = Mock()

        with pytest.raises(ValueError, match="No tables provided to create FGDB"):
            create_fgdb([], {}, gdal_connection=mock_gdal_connection)

    @patch("dolly.internal._generate_output_path")
    @patch("dolly.internal.get_gdal_layer_name")
    @patch("dolly.internal._get_geometry_option")
    @patch("dolly.internal.get_service_from_title")
    @patch("dolly.internal.gdal.VectorTranslate")
    @patch("dolly.internal.logger")
    def test_raises_error_when_all_tables_fail(
        self,
        mock_logger,
        mock_translate,
        mock_get_service,
        mock_get_geom_option,
        mock_get_layer_name,
        mock_generate_path,
    ):
        """Test that function raises exception when all tables fail to copy."""
        # Setup mocks
        mock_gdal_connection = Mock()
        mock_gdal_connection.GetLayerCount.return_value = 5

        mock_generate_path.return_value = Path("/test/output.gdb")
        mock_get_layer_name.return_value = "test_layer"
        mock_get_geom_option.return_value = "MULTIPOLYGON"
        mock_get_service.return_value = "test_service"
        mock_translate.side_effect = Exception("Copy failed")

        tables = ["sgid.test.table1", "sgid.test.table2"]
        agol_lookup = {
            "sgid.test.table1": {
                "geometry_type": "POLYGON",
                "published_name": "Test Table 1",
            },
            "sgid.test.table2": {
                "geometry_type": "POINT",
                "published_name": "Test Table 2",
            },
        }

        with pytest.raises(Exception, match="FGDB creation failed for all tables"):
            create_fgdb(tables, agol_lookup, gdal_connection=mock_gdal_connection)


class TestPrepareGdalOptions:
    """Test cases for the _prepare_gdal_options function."""

    @patch("dolly.internal.get_gdal_layer_name")
    @patch("dolly.internal._get_geometry_option")
    @patch("dolly.internal.get_service_from_title")
    def test_prepare_options_with_default_table_name(
        self, mock_get_service, mock_get_geom_option, mock_get_layer_name
    ):
        """Test preparing GDAL options with default table name."""
        # Setup mocks
        mock_get_layer_name.return_value = "test_layer"
        mock_get_geom_option.return_value = "MULTIPOLYGON"
        mock_get_service.return_value = "test_service"

        table = "sgid.test.table1"
        agol_item_info = {
            "geometry_type": "POLYGON",
            "published_name": "Test Table",
        }

        result = _prepare_gdal_options(table, agol_item_info)

        expected = {
            "layers": ["test_layer"],
            "format": "OpenFileGDB",
            "options": [
                "-nln",
                "test_service",
                "-nlt",
                "MULTIPOLYGON",
                "-a_srs",
                "EPSG:26912",
            ],
            "accessMode": "append",
        }

        assert result == expected
        mock_get_layer_name.assert_called_once_with(table)
        mock_get_geom_option.assert_called_once_with("POLYGON")
        mock_get_service.assert_called_once_with("Test Table")

    @patch("dolly.internal.get_gdal_layer_name")
    @patch("dolly.internal._get_geometry_option")
    @patch("dolly.internal.get_service_from_title")
    def test_prepare_options_with_different_geometry_types(
        self, mock_get_service, mock_get_geom_option, mock_get_layer_name
    ):
        """Test preparing GDAL options with different geometry types."""
        # Setup mocks
        mock_get_layer_name.return_value = "test_layer"
        mock_get_geom_option.return_value = "MULTILINESTRING"
        mock_get_service.return_value = "test_service"

        table = "sgid.test.table1"
        agol_item_info = {
            "geometry_type": "POLYLINE",
            "published_name": "Test Roads",
        }

        result = _prepare_gdal_options(table, agol_item_info)

        assert result["options"][3] == "MULTILINESTRING"
        mock_get_geom_option.assert_called_once_with("POLYLINE")


class TestCopyTableToFgdb:
    """Test cases for the _copy_table_to_fgdb function."""

    @patch("dolly.internal._prepare_gdal_options")
    @patch("dolly.internal.gdal.VectorTranslate")
    @patch("dolly.internal.logger")
    def test_successful_table_copy(
        self, mock_logger, mock_translate, mock_prepare_options
    ):
        """Test successful table copy to FGDB."""
        # Setup mocks
        mock_gdal_connection = Mock()
        mock_prepare_options.return_value = {
            "layers": ["test_layer"],
            "format": "OpenFileGDB",
            "options": ["-nln", "test_service", "-nlt", "MULTIPOLYGON"],
            "accessMode": "append",
        }
        mock_translate.return_value = None

        table = "sgid.test.table1"
        output_path = Path("/test/output.gdb")
        agol_item_info = {
            "geometry_type": "POLYGON",
            "published_name": "Test Table",
        }

        result = _copy_table_to_fgdb(
            mock_gdal_connection, table, output_path, agol_item_info
        )

        assert result is True
        mock_prepare_options.assert_called_once_with(table, agol_item_info)
        mock_translate.assert_called_once_with(
            destNameOrDestDS=str(output_path),
            srcDS=mock_gdal_connection,
            layers=["test_layer"],
            format="OpenFileGDB",
            options=["-nln", "test_service", "-nlt", "MULTIPOLYGON"],
            accessMode="append",
        )
        mock_logger.info.assert_called()

    @patch("dolly.internal._prepare_gdal_options")
    @patch("dolly.internal.gdal.VectorTranslate")
    @patch("dolly.internal.logger")
    def test_failed_table_copy(self, mock_logger, mock_translate, mock_prepare_options):
        """Test failed table copy to FGDB."""
        # Setup mocks
        mock_gdal_connection = Mock()
        mock_prepare_options.return_value = {
            "layers": ["test_layer"],
            "format": "OpenFileGDB",
            "options": ["-nln", "test_service", "-nlt", "MULTIPOLYGON"],
            "accessMode": "append",
        }
        mock_translate.side_effect = Exception("GDAL translation failed")

        table = "sgid.test.table1"
        output_path = Path("/test/output.gdb")
        agol_item_info = {
            "geometry_type": "POLYGON",
            "published_name": "Test Table",
        }

        result = _copy_table_to_fgdb(
            mock_gdal_connection, table, output_path, agol_item_info
        )

        assert result is False
        mock_logger.error.assert_called_once()
        error_call_args = mock_logger.error.call_args[0][0]
        assert "Failed to copy layer" in error_call_args
        assert "GDAL translation failed" in error_call_args

    @patch("dolly.internal._prepare_gdal_options")
    @patch("dolly.internal.gdal.VectorTranslate")
    @patch("dolly.internal.logger")
    def test_logs_correct_messages(
        self, mock_logger, mock_translate, mock_prepare_options
    ):
        """Test that correct log messages are generated."""
        # Setup mocks
        mock_gdal_connection = Mock()
        mock_prepare_options.return_value = {"layers": ["test_layer"]}
        mock_translate.return_value = None

        table = "sgid.test.table1"
        output_path = Path("/test/output.gdb")
        agol_item_info = {
            "geometry_type": "POLYGON",
            "published_name": "Test Table",
        }

        _copy_table_to_fgdb(mock_gdal_connection, table, output_path, agol_item_info)

        # Check log messages
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any(
            "Copying layer sgid.test.table1 to FGDB" in msg for msg in info_calls
        )
        assert any(
            "Successfully copied layer sgid.test.table1 to FGDB" in msg
            for msg in info_calls
        )


class TestBuildUpdateAgolItemQuery:
    """Test cases for the _build_update_agol_item_query function."""

    def test_query_structure_and_parameters(self):
        """Test that query has correct structure and parameters."""
        table = "sgid.test.table1"
        item_id = "abc123-def456-ghi789"

        result = _build_update_agol_item_query(table, item_id)

        expected_query = dedent("""
        UPDATE SGID.META.AGOLItems
        SET AGOL_ITEM_ID = 'abc123-def456-ghi789'
        WHERE UPPER(TABLENAME) = UPPER('sgid.test.table1')
    """)
        assert result.strip() == expected_query.strip()

    def test_query_contains_required_elements(self):
        """Test that query contains all required SQL elements."""
        table = "sgid.society.cemeteries"
        item_id = "xyz789-abc123-def456"

        result = _build_update_agol_item_query(table, item_id)

        # Check for required SQL components
        assert "UPDATE SGID.META.AGOLItems" in result
        assert "SET AGOL_ITEM_ID =" in result
        assert "WHERE UPPER(TABLENAME) =" in result
        assert f"'{table}'" in result
        assert f"'{item_id}'" in result

    def test_query_handles_special_characters(self):
        """Test that query handles tables and IDs with special characters."""
        table = "sgid.test.table_with_underscores"
        item_id = "guid-with-dashes-123"

        result = _build_update_agol_item_query(table, item_id)

        assert f"'{table}'" in result
        assert f"'{item_id}'" in result


class TestUpdateAgolItem:
    """Test cases for the update_agol_item function."""

    @patch("dolly.internal.APP_ENVIRONMENT", "dev")
    @patch("dolly.internal.logger")
    def test_dev_environment_only_logs(self, mock_logger):
        """Test that dev environment only logs the change without updating database."""
        table = "sgid.test.table1"
        item_id = "abc123-def456"

        update_agol_item(table, item_id)

        # Should log both messages
        mock_logger.info.assert_any_call(
            f"Updating AGOL item ID for table {table} to {item_id}"
        )
        mock_logger.info.assert_any_call(
            f"DEV MODE: Would update AGOL item ID for table {table} to {item_id}"
        )

        # Should have exactly 2 log calls
        assert mock_logger.info.call_count == 2

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._build_update_agol_item_query")
    @patch("dolly.internal.logger")
    def test_successful_update_with_provided_connection(
        self, mock_logger, mock_query_builder
    ):
        """Test successful AGOL item update with provided connection."""
        # Setup mocks
        mock_query_builder.return_value = "UPDATE SGID.META.AGOLItems SET..."
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        table = "sgid.test.table1"
        item_id = "abc123-def456"

        update_agol_item(table, item_id, mock_connection)

        # Verify function calls
        mock_query_builder.assert_called_once_with(table, item_id)
        mock_connection.cursor.assert_called_once()
        mock_cursor.execute.assert_called_once_with("UPDATE SGID.META.AGOLItems SET...")
        mock_connection.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

        # Verify logging
        mock_logger.info.assert_any_call(
            f"Updating AGOL item ID for table {table} to {item_id}"
        )
        mock_logger.info.assert_any_call(
            f"Successfully updated AGOL item ID for table {table}"
        )

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._get_database_connection")
    @patch("dolly.internal._build_update_agol_item_query")
    @patch("dolly.internal.logger")
    def test_creates_connection_when_none_provided(
        self, mock_logger, mock_query_builder, mock_get_connection
    ):
        """Test that function creates connection when none provided."""
        # Setup mocks
        mock_query_builder.return_value = "UPDATE SGID.META.AGOLItems SET..."
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection

        table = "sgid.test.table1"
        item_id = "abc123-def456"

        update_agol_item(table, item_id)

        # Verify connection creation
        mock_get_connection.assert_called_once()
        mock_connection.close.assert_called_once()

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._build_update_agol_item_query")
    @patch("dolly.internal.logger")
    def test_closes_connection_on_success(self, mock_logger, mock_query_builder):
        """Test that connection is closed after successful update."""
        # Setup mocks
        mock_query_builder.return_value = "UPDATE SGID.META.AGOLItems SET..."
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        table = "sgid.test.table1"
        item_id = "abc123-def456"

        update_agol_item(table, item_id, mock_connection)

        mock_connection.close.assert_called_once()

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._build_update_agol_item_query")
    @patch("dolly.internal.logger")
    def test_closes_connection_on_exception(self, mock_logger, mock_query_builder):
        """Test that connection is closed even when exception occurs."""
        # Setup mocks
        mock_query_builder.return_value = "UPDATE SGID.META.AGOLItems SET..."
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        table = "sgid.test.table1"
        item_id = "abc123-def456"

        with pytest.raises(Exception, match="Database error"):
            update_agol_item(table, item_id, mock_connection)

        # Connection should still be closed
        mock_connection.close.assert_called_once()

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._build_update_agol_item_query")
    @patch("dolly.internal.logger")
    def test_commits_transaction(self, mock_logger, mock_query_builder):
        """Test that database transaction is committed."""
        # Setup mocks
        mock_query_builder.return_value = "UPDATE SGID.META.AGOLItems SET..."
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        table = "sgid.test.table1"
        item_id = "abc123-def456"

        update_agol_item(table, item_id, mock_connection)

        # Verify commit is called
        mock_connection.commit.assert_called_once()

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._build_update_agol_item_query")
    @patch("dolly.internal.logger")
    def test_logging_messages(self, mock_logger, mock_query_builder):
        """Test that appropriate log messages are generated."""
        # Setup mocks
        mock_query_builder.return_value = "UPDATE SGID.META.AGOLItems SET..."
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        table = "sgid.society.cemeteries"
        item_id = "xyz789-abc123"

        update_agol_item(table, item_id, mock_connection)

        # Check that both log messages are called
        expected_calls = [
            f"Updating AGOL item ID for table {table} to {item_id}",
            f"Successfully updated AGOL item ID for table {table}",
        ]

        actual_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        for expected_call in expected_calls:
            assert expected_call in actual_calls
