"""Tests for internal.py functions"""

import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock, patch

import pytest

from dolly.internal import (
    _build_change_detection_hashes_query,
    _build_update_agol_item_query,
    _copy_table_to_fgdb,
    _generate_output_path,
    _get_geometry_option,
    _get_internal_connection,
    _prepare_gdal_options,
    create_fgdb,
    determine_updated_tables,
    get_agol_items_lookup,
    get_current_hashes,
    update_agol_item,
)


def _mock_arcpy(monkeypatch):
    arcpy = Mock()
    arcpy.Exists.return_value = True
    arcpy.ListFields.return_value = []
    monkeypatch.setitem(sys.modules, "arcpy", arcpy)
    return arcpy


def test_internal_connection_creates_output_directory(monkeypatch, tmp_path):
    arcpy = _mock_arcpy(monkeypatch)
    output_path = tmp_path / "output"
    monkeypatch.setattr("dolly.internal.OUTPUT_PATH", output_path)

    assert _get_internal_connection() == output_path / "internal.sde"
    assert output_path.is_dir()
    assert arcpy.management.CreateDatabaseConnection.call_args.kwargs[
        "out_folder_path"
    ] == str(output_path)


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

    def test_multiple_tables_with_batch_index_uses_indexed_path(self):
        """Test that multiple tables with a batch_index produce a unique indexed FGDB name."""
        tables = ["sgid.society.cemeteries", "sgid.transportation.roads"]
        agol_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"},
            "sgid.transportation.roads": {"published_name": "Utah Roads"},
        }

        with patch("dolly.internal.OUTPUT_PATH", Path("/test/output")):
            result = _generate_output_path(tables, agol_lookup, batch_index=3)

        assert result == Path("/test/output/upload_3.gdb")


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


class TestBuildChangeDetectionHashesQuery:
    """Tests for the _build_change_detection_hashes_query function."""

    def test_query_structure(self):
        result = _build_change_detection_hashes_query()
        assert "SELECT table_name, hash FROM SGID.META.ChangeDetection" in result


class TestGetCurrentHashes:
    @patch("dolly.internal.APP_ENVIRONMENT", "dev")
    @patch("dolly.internal.DEV_MOCKS_PATH")
    def test_dev_environment_synthetic_hashes(self, mock_path):
        mock_path.read_text.return_value = '{"updated_tables": ["Table1", "Table2"]}'
        result = get_current_hashes()
        assert "table1" in result and "table2" in result
        assert result["table1"].startswith("dev-hash-")

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._build_change_detection_hashes_query")
    def test_prod_environment_queries_database(self, mock_query_builder):
        mock_query_builder.return_value = "SELECT table_name, hash FROM ChangeDetection"
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("Table1", "h1"), ("Table2", "h2")]
        result = get_current_hashes(mock_connection)
        assert result == {"table1": "h1", "table2": "h2"}
        mock_cursor.execute.assert_called_once_with(
            "SELECT table_name, hash FROM ChangeDetection"
        )
        mock_connection.close.assert_called_once()

    @patch("dolly.internal.APP_ENVIRONMENT", "prod")
    @patch("dolly.internal._get_database_connection")
    @patch("dolly.internal._build_change_detection_hashes_query")
    def test_creates_connection_when_none(self, mock_query_builder, mock_get_conn):
        mock_query_builder.return_value = "SELECT table_name, hash FROM ChangeDetection"
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("Table1", "h1")]
        mock_get_conn.return_value = mock_connection
        result = get_current_hashes()
        assert result == {"table1": "h1"}
        mock_get_conn.assert_called_once()
        mock_connection.close.assert_called_once()


class TestDetermineUpdatedTables:
    def test_new_table_detected(self):
        stored = {"table1": "h1"}
        current = {"table1": "h1", "table2": "h2"}
        assert determine_updated_tables(stored, current) == ["table2"]

    def test_changed_hash_detected(self):
        stored = {"table1": "h1"}
        current = {"table1": "h2"}
        assert determine_updated_tables(stored, current) == ["table1"]

    def test_no_changes(self):
        stored = {"table1": "h1"}
        current = {"table1": "h1"}
        assert determine_updated_tables(stored, current) == []

    def test_multiple_mixed(self):
        stored = {"table1": "h1", "table2": "h2"}
        current = {"table1": "h1", "table2": "h3", "table3": "h4"}
        result = determine_updated_tables(stored, current)
        assert set(result) == {"table2", "table3"}


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

    @pytest.mark.parametrize("output_path", [None, Path("/test/migration.gdb")])
    def test_successful_fgdb_creation(self, monkeypatch, output_path):
        internal = Path("/test/internal.sde")
        generated_path = Path("/test/output.gdb")
        mock_internal_connection = Mock(return_value=internal)
        mock_copy_table = Mock(return_value=True)
        mock_generate_path = Mock(return_value=generated_path)
        mock_count_internal = Mock(return_value=1000)
        mock_count_fgdb = Mock(return_value=1000)
        mock_database_connection = Mock()

        monkeypatch.setattr(
            "dolly.internal._get_internal_connection", mock_internal_connection
        )
        monkeypatch.setattr("dolly.internal._copy_table_to_fgdb", mock_copy_table)
        monkeypatch.setattr("dolly.internal._generate_output_path", mock_generate_path)
        monkeypatch.setattr(
            "dolly.internal._count_features_in_internal_table", mock_count_internal
        )
        monkeypatch.setattr(
            "dolly.internal._count_features_in_fgdb_layer", mock_count_fgdb
        )
        monkeypatch.setattr(
            "dolly.internal.get_table_field_domains", Mock(return_value={})
        )
        monkeypatch.setattr(
            "dolly.internal._get_database_connection",
            Mock(return_value=mock_database_connection),
        )
        monkeypatch.setattr(
            "dolly.internal.get_service_from_title", Mock(return_value="test_table")
        )
        tables = ["sgid.test.table1"]
        agol_lookup = {
            "sgid.test.table1": {
                "geometry_type": "POLYGON",
                "published_name": "Test Table",
            }
        }

        result = create_fgdb(tables, agol_lookup, output_path=output_path)

        expected_path = output_path or generated_path
        assert result == (expected_path, {"sgid.test.table1": 1000})
        mock_internal_connection.assert_called_once()
        mock_copy_table.assert_called_once_with(
            internal, "sgid.test.table1", expected_path, agol_lookup["sgid.test.table1"]
        )
        mock_count_internal.assert_called_once_with("sgid.test.table1")
        mock_count_fgdb.assert_called_once_with(expected_path, "test_table")
        mock_database_connection.close.assert_called_once()
        if output_path is not None:
            mock_generate_path.assert_not_called()
        else:
            mock_generate_path.assert_called_once_with(tables, agol_lookup, None)

    def test_raises_error_for_empty_tables_list(self, monkeypatch):
        """Test that function raises ValueError for empty tables list."""
        mock_internal_connection = Mock()
        monkeypatch.setattr(
            "dolly.internal._get_internal_connection", mock_internal_connection
        )

        with pytest.raises(ValueError, match="No tables provided to create FGDB"):
            create_fgdb([], {})

        mock_internal_connection.assert_not_called()

    def test_raises_error_when_table_copy_fails(self, monkeypatch):
        """Test that function raises exception when all tables fail to copy."""
        monkeypatch.setattr(
            "dolly.internal._get_internal_connection",
            Mock(return_value=Path("/test/internal.sde")),
        )
        monkeypatch.setattr(
            "dolly.internal._count_features_in_internal_table", Mock(return_value=1000)
        )
        monkeypatch.setattr(
            "dolly.internal._copy_table_to_fgdb", Mock(return_value=False)
        )
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

        with pytest.raises(
            RuntimeError, match="Failed to copy table sgid.test.table1 to FGDB"
        ):
            create_fgdb(tables, agol_lookup)

    def test_copy_projects_with_esri_transform_and_converts_dates(
        self, monkeypatch, tmp_path
    ):
        arcpy = _mock_arcpy(monkeypatch)
        arcpy.Exists.return_value = False
        date_field = Mock()
        date_field.name = "updated"
        date_field.type = "Date"
        arcpy.ListFields.return_value = [date_field]
        convert_dates = Mock()
        convert_dates.side_effect = (
            lambda *args: arcpy.management.ClearWorkspaceCache.assert_called_once_with(
                str(tmp_path / "output.gdb")
            )
        )
        monkeypatch.setattr(
            "dolly.internal._convert_fgdb_datetime_fields_to_utc", convert_dates
        )
        monkeypatch.setattr(
            "dolly.internal.get_service_from_title", Mock(return_value="test_layer")
        )

        internal = tmp_path / "internal.sde"
        output_path = tmp_path / "output.gdb"
        result = _copy_table_to_fgdb(
            internal,
            "sgid.test.table1",
            output_path,
            {"geometry_type": "POLYGON", "published_name": "Test Table"},
        )

        assert result is True
        arcpy.management.CreateFileGDB.assert_called_once_with(
            out_folder_path=str(tmp_path), out_name="output.gdb"
        )
        project_call = arcpy.management.Project.call_args
        assert project_call.args == (
            str(internal / "sgid.test.table1"),
            str(output_path / "test_layer"),
        )
        assert (
            project_call.kwargs["out_coor_system"]
            == arcpy.SpatialReference.return_value
        )
        assert project_call.kwargs["transform_method"] == "NAD_1983_To_WGS_1984_5"
        convert_dates.assert_called_once_with(output_path, "test_layer", {"updated"})

    def test_copy_uses_table_to_table_for_standalone_tables(
        self, monkeypatch, tmp_path
    ):
        arcpy = _mock_arcpy(monkeypatch)
        monkeypatch.setattr(
            "dolly.internal.get_service_from_title", Mock(return_value="test_table")
        )

        internal = tmp_path / "internal.sde"
        output_path = tmp_path / "output.gdb"
        result = _copy_table_to_fgdb(
            internal,
            "sgid.test.table1",
            output_path,
            {"geometry_type": "STAND ALONE", "published_name": "Test Table"},
        )

        assert result is True
        arcpy.conversion.TableToTable.assert_called_once_with(
            str(internal / "sgid.test.table1"),
            str(output_path),
            "test_table",
        )
        arcpy.management.Project.assert_not_called()

    @pytest.mark.parametrize("geometry_type", ["POLYGON", "STAND ALONE"])
    @pytest.mark.parametrize("copy_fails", [False, True])
    def test_copy_releases_workspace_cache(
        self, monkeypatch, tmp_path, geometry_type, copy_fails
    ):
        arcpy = _mock_arcpy(monkeypatch)
        operation = (
            arcpy.conversion.TableToTable
            if geometry_type == "STAND ALONE"
            else arcpy.management.Project
        )
        if copy_fails:
            operation.side_effect = RuntimeError("Export failed")
        output_path = tmp_path / "migration.gdb"

        result = _copy_table_to_fgdb(
            tmp_path / "internal.sde",
            "sgid.test.table1",
            output_path,
            {"geometry_type": geometry_type, "published_name": "Test Table"},
        )

        assert result is not copy_fails
        operation.assert_called_once()
        arcpy.management.ClearWorkspaceCache.assert_called_once_with(str(output_path))


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

    def test_source_field_detection_excludes_date_only_and_time_only(self):
        from dolly.internal import _get_datetime_field_names

        connection = Mock()
        cursor = connection.cursor.return_value
        cursor.fetchall.return_value = [
            ("created", "datetime"),
            ("updated", "datetime2"),
            ("legacy", "smalldatetime"),
            ("offset", "datetimeoffset"),
            ("calendar_date", "date"),
            ("clock_time", "time"),
            ("version", "timestamp"),
            ("row_version", "rowversion"),
            ("label", "nvarchar"),
        ]

        assert _get_datetime_field_names(connection, "sgid.society.source_table") == {
            "created",
            "updated",
            "legacy",
            "offset",
        }
        query, *parameters = cursor.execute.call_args.args
        assert "TABLE_CATALOG = ? AND TABLE_SCHEMA = ? AND TABLE_NAME = ?" in query
        assert parameters == ["sgid", "society", "source_table"]
        cursor.close.assert_called_once()
        connection.close.assert_not_called()

    @pytest.mark.parametrize("table", ["source", "society.source", "sgid..source"])
    def test_source_field_detection_rejects_unqualified_tables(self, table):
        from dolly.internal import _get_datetime_field_names

        connection = Mock()
        with pytest.raises(ValueError, match="sgid.schema.table"):
            _get_datetime_field_names(connection, table)
        connection.cursor.assert_not_called()

    def test_source_field_detection_reports_missing_or_inaccessible_table(self):
        from dolly.internal import _get_datetime_field_names

        connection = Mock()
        connection.cursor.return_value.fetchall.return_value = []
        with pytest.raises(LookupError, match="No visible columns"):
            _get_datetime_field_names(connection, "sgid.society.missing")
        connection.cursor.return_value.close.assert_called_once()

    def test_source_field_detection_closes_cursor_on_query_failure(self):
        from dolly.internal import _get_datetime_field_names

        connection = Mock()
        cursor = connection.cursor.return_value
        cursor.execute.side_effect = RuntimeError("Cannot read schema")
        with pytest.raises(RuntimeError, match="Cannot read schema"):
            _get_datetime_field_names(connection, "sgid.society.source")
        cursor.close.assert_called_once()

    def test_converts_local_timestamps_and_preserves_date_fields(self, tmp_path):
        from osgeo import gdal, ogr

        from dolly.internal import _convert_fgdb_datetime_fields_to_utc

        fgdb_path = tmp_path / "timestamps.gdb"
        driver = ogr.GetDriverByName("OpenFileGDB")
        dataset = driver.CreateDataSource(str(fgdb_path))
        layer = dataset.CreateLayer("timestamps", geom_type=ogr.wkbNone)
        layer.CreateField(ogr.FieldDefn("timestamp", ogr.OFTDateTime))
        layer.CreateField(ogr.FieldDefn("calendar_date", ogr.OFTDate))

        summer_feature = ogr.Feature(layer.GetLayerDefn())
        summer_feature.SetField("timestamp", 2025, 9, 3, 0, 0, 0, ogr.TZFLAG_UNKNOWN)
        summer_feature.SetField("calendar_date", 2025, 9, 3, 0, 0, 0, 0)
        layer.CreateFeature(summer_feature)

        winter_feature = ogr.Feature(layer.GetLayerDefn())
        winter_feature.SetField("timestamp", 2025, 1, 3, 0, 0, 0, ogr.TZFLAG_UNKNOWN)
        winter_feature.SetField("calendar_date", 2025, 1, 3, 0, 0, 0, 0)
        layer.CreateFeature(winter_feature)

        null_feature = ogr.Feature(layer.GetLayerDefn())
        null_feature.SetFieldNull("timestamp")
        null_feature.SetField("calendar_date", 2025, 1, 3, 0, 0, 0, 0)
        layer.CreateFeature(null_feature)
        layer = None
        dataset = None

        _convert_fgdb_datetime_fields_to_utc(fgdb_path, "timestamps", {"timestamp"})

        dataset = gdal.OpenEx(str(fgdb_path), gdal.OF_VECTOR)
        layer = dataset.GetLayerByName("timestamps")
        features = list(layer)

        assert features[0].GetFieldAsDateTime("timestamp") == [
            2025,
            9,
            3,
            6,
            0,
            0.0,
            ogr.TZFLAG_UTC,
        ]
        assert features[1].GetFieldAsDateTime("timestamp") == [
            2025,
            1,
            3,
            7,
            0,
            0.0,
            ogr.TZFLAG_UTC,
        ]
        assert features[2].IsFieldNull("timestamp")
        assert features[0].GetFieldAsDateTime("calendar_date")[:6] == [
            2025,
            9,
            3,
            0,
            0,
            0.0,
        ]
        dataset = None


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
