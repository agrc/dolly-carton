from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from dolly.agol import (
    _append_new_data_to_service,
    _create_zip_from_fgdb,
    _delete_agol_item,
    _generate_service_tags,
    _generate_service_title,
    _generate_upload_tags,
    _generate_upload_title,
    _get_appropriate_service_layer,
    _get_gis_connection,
    _get_service_item_from_agol,
    _search_existing_item,
    _truncate_service_data,
    _upload_item_to_agol,
)


class TestGenerateUploadTitle:
    """Test cases for the _generate_upload_title function."""

    @patch("dolly.agol.APP_ENVIRONMENT", "prod")
    def test_production_environment_title(self):
        """Test title generation in production environment."""
        fgdb_stem = "society_cemeteries"

        result = _generate_upload_title(fgdb_stem)

        expected = "dolly-carton Temporary upload: society_cemeteries"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "dev")
    def test_development_environment_title(self):
        """Test title generation in development environment."""
        fgdb_stem = "transportation_roads"

        result = _generate_upload_title(fgdb_stem)

        expected = "dolly-carton Temporary upload: transportation_roads (Test)"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "staging")
    def test_other_environment_title(self):
        """Test title generation in other environments (treated as prod)."""
        fgdb_stem = "boundaries_counties"

        result = _generate_upload_title(fgdb_stem)

        expected = "dolly-carton Temporary upload: boundaries_counties"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "prod")
    def test_complex_fgdb_stem(self):
        """Test title generation with complex FGDB stem."""
        fgdb_stem = "geoscience_mineral_resources_detailed"

        result = _generate_upload_title(fgdb_stem)

        expected = (
            "dolly-carton Temporary upload: geoscience_mineral_resources_detailed"
        )
        assert result == expected


class TestGenerateUploadTags:
    """Test cases for the _generate_upload_tags function."""

    @patch("dolly.agol.APP_ENVIRONMENT", "prod")
    def test_production_environment_tags(self):
        """Test tags generation in production environment."""
        result = _generate_upload_tags()

        expected = "Temp"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "dev")
    def test_development_environment_tags(self):
        """Test tags generation in development environment."""
        result = _generate_upload_tags()

        expected = "Temp,Test"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "staging")
    def test_other_environment_tags(self):
        """Test tags generation in other environments (treated as prod)."""
        result = _generate_upload_tags()

        expected = "Temp"
        assert result == expected


class TestGenerateServiceTags:
    """Test cases for the _generate_service_tags function."""

    @patch("dolly.agol.APP_ENVIRONMENT", "prod")
    def test_production_environment_tags(self):
        """Test service tags generation in production environment."""
        table = "sgid.society.cemeteries"

        result = _generate_service_tags(table)

        expected = "UGRC,SGID,Society"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "dev")
    def test_development_environment_tags(self):
        """Test service tags generation in development environment."""
        table = "sgid.transportation.roads"

        result = _generate_service_tags(table)

        expected = "UGRC,SGID,Transportation,Test"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "prod")
    def test_different_categories(self):
        """Test service tags with different table categories."""
        test_cases = [
            ("sgid.boundaries.counties", "UGRC,SGID,Boundaries"),
            ("sgid.geoscience.geology", "UGRC,SGID,Geoscience"),
            ("sgid.water.streams", "UGRC,SGID,Water"),
            ("sgid.health.hospitals", "UGRC,SGID,Health"),
        ]

        for table, expected in test_cases:
            result = _generate_service_tags(table)
            assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "dev")
    def test_development_with_different_categories(self):
        """Test service tags in dev environment with different categories."""
        test_cases = [
            ("sgid.boundaries.counties", "UGRC,SGID,Boundaries,Test"),
            ("sgid.geoscience.geology", "UGRC,SGID,Geoscience,Test"),
            ("sgid.water.streams", "UGRC,SGID,Water,Test"),
        ]

        for table, expected in test_cases:
            result = _generate_service_tags(table)
            assert result == expected


class TestGenerateServiceTitle:
    """Test cases for the _generate_service_title function."""

    @patch("dolly.agol.APP_ENVIRONMENT", "prod")
    def test_production_environment_title(self):
        """Test service title generation in production environment."""
        published_name = "Utah Cemeteries"

        result = _generate_service_title(published_name)

        expected = "Utah Cemeteries"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "dev")
    def test_development_environment_title(self):
        """Test service title generation in development environment."""
        published_name = "Utah Roads"

        result = _generate_service_title(published_name)

        expected = "Utah Roads (Test)"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "staging")
    def test_other_environment_title(self):
        """Test service title generation in other environments (treated as prod)."""
        published_name = "Utah Counties"

        result = _generate_service_title(published_name)

        expected = "Utah Counties"
        assert result == expected

    @patch("dolly.agol.APP_ENVIRONMENT", "prod")
    def test_complex_published_names(self):
        """Test service title with complex published names."""
        test_cases = [
            "Utah Geological Survey Mineral Resources",
            "SITLA Land Ownership",
            "School District Boundaries - Elementary",
            "Wetlands - National Wetlands Inventory",
        ]

        for published_name in test_cases:
            result = _generate_service_title(published_name)
            assert result == published_name

    @patch("dolly.agol.APP_ENVIRONMENT", "dev")
    def test_complex_published_names_in_dev(self):
        """Test service title with complex published names in dev."""
        test_cases = [
            (
                "Utah Geological Survey Mineral Resources",
                "Utah Geological Survey Mineral Resources (Test)",
            ),
            ("SITLA Land Ownership", "SITLA Land Ownership (Test)"),
            (
                "School District Boundaries - Elementary",
                "School District Boundaries - Elementary (Test)",
            ),
        ]

        for published_name, expected in test_cases:
            result = _generate_service_title(published_name)
            assert result == expected


class TestCreateZipFromFgdb:
    """Test cases for the _create_zip_from_fgdb function."""

    @patch("dolly.agol.make_archive")
    @patch("dolly.agol.logger")
    def test_creates_zip_file_successfully(self, mock_logger, mock_make_archive):
        """Test successful zip file creation from FGDB."""
        fgdb_path = Path("/test/output/society_cemeteries.gdb")

        result = _create_zip_from_fgdb(fgdb_path)

        # Verify make_archive was called with correct parameters
        mock_make_archive.assert_called_once_with(
            "/test/output/society_cemeteries",
            "zip",
            root_dir=Path("/test/output"),
            base_dir="society_cemeteries.gdb",
        )

        # Verify return value
        expected_zip_path = Path("/test/output/society_cemeteries.zip")
        assert result == expected_zip_path

        # Verify logging
        mock_logger.info.assert_called_once_with(f"FGDB zipped to {expected_zip_path}")

    @patch("dolly.agol.make_archive")
    @patch("dolly.agol.logger")
    def test_different_fgdb_paths(self, mock_logger, mock_make_archive):
        """Test zip creation with different FGDB paths."""
        test_cases = [
            Path("/data/upload.gdb"),
            Path("/tmp/boundaries_counties.gdb"),
            Path("/output/geoscience_geology_detailed.gdb"),
        ]

        for fgdb_path in test_cases:
            mock_make_archive.reset_mock()
            mock_logger.reset_mock()

            result = _create_zip_from_fgdb(fgdb_path)

            expected_zip_path = fgdb_path.with_suffix(".zip")
            assert result == expected_zip_path

            mock_make_archive.assert_called_once_with(
                str(fgdb_path.with_suffix("")),
                "zip",
                root_dir=fgdb_path.parent,
                base_dir=fgdb_path.name,
            )

    @patch("dolly.agol.make_archive")
    @patch("dolly.agol.logger")
    def test_handles_path_with_spaces(self, mock_logger, mock_make_archive):
        """Test zip creation with FGDB path containing spaces."""
        fgdb_path = Path("/test/output/utah roads network.gdb")

        result = _create_zip_from_fgdb(fgdb_path)

        expected_zip_path = Path("/test/output/utah roads network.zip")
        assert result == expected_zip_path

        mock_make_archive.assert_called_once_with(
            "/test/output/utah roads network",
            "zip",
            root_dir=Path("/test/output"),
            base_dir="utah roads network.gdb",
        )


class TestGetGisConnection:
    """Test cases for the _get_gis_connection function."""

    @patch("dolly.agol.get_secrets")
    @patch("dolly.agol.GIS")
    def test_creates_gis_connection_successfully(self, mock_gis, mock_get_secrets):
        """Test successful GIS connection creation."""
        # Setup mocks
        mock_secrets = {
            "AGOL_USERNAME": "test_user",
            "AGOL_PASSWORD": "test_password",
        }
        mock_get_secrets.return_value = mock_secrets
        mock_gis_instance = Mock()
        mock_gis.return_value = mock_gis_instance

        result = _get_gis_connection()

        # Verify get_secrets was called
        mock_get_secrets.assert_called_once()

        # Verify GIS was called with correct parameters
        mock_gis.assert_called_once_with(
            "https://utah.maps.arcgis.com",
            username="test_user",
            password="test_password",
        )

        # Verify return value
        assert result == mock_gis_instance


class TestSearchExistingItem:
    """Test cases for the _search_existing_item function."""

    @patch("dolly.agol.retry")
    @patch("dolly.agol._get_gis_connection")
    def test_successful_search_with_results(self, mock_get_gis, mock_retry):
        """Test successful search that finds existing items."""
        # Setup mocks
        mock_gis = Mock()
        mock_gis.users.me.username = "test_user"
        mock_get_gis.return_value = mock_gis

        mock_item = Mock()
        mock_retry.return_value = [mock_item]

        title = "Test Title"
        result = _search_existing_item(title)

        # Verify retry was called with correct parameters
        mock_retry.assert_called_once_with(
            mock_gis.content.search,
            f'title:"{title}" AND owner:test_user',
            item_type="File Geodatabase",
            max_items=1,
        )

        # Verify return value
        assert result == [mock_item]

    @patch("dolly.agol.retry")
    def test_search_with_provided_connection(self, mock_retry):
        """Test search with provided GIS connection."""
        mock_gis = Mock()
        mock_gis.users.me.username = "provided_user"
        mock_retry.return_value = []

        title = "Test Title"
        result = _search_existing_item(title, mock_gis)

        # Verify retry was called with provided connection
        mock_retry.assert_called_once_with(
            mock_gis.content.search,
            f'title:"{title}" AND owner:provided_user',
            item_type="File Geodatabase",
            max_items=1,
        )

        assert result == []

    @patch("dolly.agol.retry")
    @patch("dolly.agol._get_gis_connection")
    @patch("dolly.agol.logger")
    def test_search_exception_handling(self, mock_logger, mock_get_gis, mock_retry):
        """Test search exception handling."""
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis
        mock_retry.side_effect = Exception("Search failed")

        title = "Test Title"
        result = _search_existing_item(title)

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            f"Error searching for existing gdb item with title {title}"
        )

        # Should return empty list on exception
        assert result == []


class TestDeleteAgolItem:
    """Test cases for the _delete_agol_item function."""

    @patch("dolly.agol.retry")
    @patch("dolly.agol.logger")
    def test_successful_deletion(self, mock_logger, mock_retry):
        """Test successful item deletion."""
        mock_item = Mock()
        mock_item.id = "test-item-id"
        mock_retry.return_value = True

        result = _delete_agol_item(mock_item)

        # Verify retry was called correctly
        mock_retry.assert_called_once_with(mock_item.delete, permanent=True)

        # Verify success logging
        mock_logger.info.assert_called_once_with(
            "Successfully deleted existing gdb item test-item-id"
        )

        assert result is True

    @patch("dolly.agol.retry")
    @patch("dolly.agol.logger")
    def test_failed_deletion(self, mock_logger, mock_retry):
        """Test failed item deletion."""
        mock_item = Mock()
        mock_item.id = "test-item-id"
        mock_retry.return_value = False

        result = _delete_agol_item(mock_item)

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Failed to delete existing gdb item test-item-id"
        )

        assert result is False

    @patch("dolly.agol.retry")
    def test_deletion_exception(self, mock_retry):
        """Test deletion exception handling."""
        mock_item = Mock()
        mock_item.title = "Test Item"
        mock_retry.side_effect = Exception("Delete failed")

        with pytest.raises(RuntimeError, match="Error deleting existing gdb item"):
            _delete_agol_item(mock_item)


class TestUploadItemToAgol:
    """Test cases for the _upload_item_to_agol function."""

    @patch("dolly.agol.retry")
    @patch("dolly.agol._get_gis_connection")
    def test_successful_upload(self, mock_get_gis, mock_retry):
        """Test successful item upload."""
        # Setup mocks
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis

        mock_folder = Mock()
        mock_gis.content.folders.get.return_value = mock_folder

        mock_future = Mock()
        mock_item = Mock()
        mock_future.result.return_value = mock_item
        mock_retry.return_value = mock_future

        zip_path = Path("/test/upload.zip")
        title = "Test Upload"
        tags = "Test,Tags"

        result = _upload_item_to_agol(zip_path, title, tags)

        # Verify retry was called with correct parameters
        mock_retry.assert_called_once_with(
            mock_folder.add,
            item_properties={
                "type": "File Geodatabase",
                "title": title,
                "snippet": "Temporary upload of SGID data to AGOL",
                "tags": tags,
            },
            file=str(zip_path),
        )

        assert result == mock_item

    @patch("dolly.agol.retry")
    def test_upload_with_provided_connection(self, mock_retry):
        """Test upload with provided GIS connection."""
        mock_gis = Mock()
        mock_folder = Mock()
        mock_gis.content.folders.get.return_value = mock_folder

        mock_future = Mock()
        mock_item = Mock()
        mock_future.result.return_value = mock_item
        mock_retry.return_value = mock_future

        zip_path = Path("/test/upload.zip")
        title = "Test Upload"
        tags = "Test,Tags"

        _upload_item_to_agol(zip_path, title, tags, mock_gis)

        # Verify retry was called with provided connection's folder
        mock_retry.assert_called_once_with(
            mock_folder.add,
            item_properties={
                "type": "File Geodatabase",
                "title": title,
                "snippet": "Temporary upload of SGID data to AGOL",
                "tags": tags,
            },
            file=str(zip_path),
        )


class TestGetServiceItemFromAgol:
    """Test cases for the _get_service_item_from_agol function."""

    def setup_method(self):
        self.mock_gis = Mock()
        self.agol_items_lookup = {"schema.category.table": {"item_id": "mock_item_id"}}

    @patch("dolly.agol.retry")
    def test_get_service_item_success(self, mock_retry):
        mock_item = Mock()
        mock_retry.return_value = mock_item

        result = _get_service_item_from_agol(
            "schema.category.table", self.agol_items_lookup, self.mock_gis
        )

        assert result == mock_item
        mock_retry.assert_called_once_with(self.mock_gis.content.get, "mock_item_id")

    @patch("dolly.agol.retry")
    @patch("dolly.agol.logger")
    def test_get_service_item_not_found(self, mock_logger, mock_retry):
        mock_retry.return_value = None

        result = _get_service_item_from_agol(
            "schema.category.table", self.agol_items_lookup, self.mock_gis
        )

        assert result is None
        mock_logger.error.assert_called_once_with(
            "Item with ID mock_item_id not found in AGOL."
        )


class TestGetAppropriateServiceLayer:
    """Test cases for the _get_appropriate_service_layer function."""

    def setup_method(self):
        self.mock_item = Mock()
        self.agol_items_lookup = {}

    @patch("dolly.agol.Table")
    def test_get_table_for_stand_alone(self, mock_table_class):
        mock_table = Mock()
        mock_table_class.fromitem.return_value = mock_table
        self.agol_items_lookup["schema.category.table"] = {
            "geometry_type": "STAND ALONE"
        }

        result = _get_appropriate_service_layer(
            self.mock_item, "schema.category.table", self.agol_items_lookup
        )

        assert result == mock_table
        mock_table_class.fromitem.assert_called_once_with(self.mock_item, table_id=0)

    @patch("dolly.agol.FeatureLayer")
    def test_get_feature_layer_for_geometry(self, mock_feature_layer_class):
        mock_feature_layer = Mock()
        mock_feature_layer_class.fromitem.return_value = mock_feature_layer
        self.agol_items_lookup["schema.category.table"] = {"geometry_type": "POLYGON"}

        result = _get_appropriate_service_layer(
            self.mock_item, "schema.category.table", self.agol_items_lookup
        )

        assert result == mock_feature_layer
        mock_feature_layer_class.fromitem.assert_called_once_with(
            self.mock_item, layer_id=0
        )


class TestTruncateServiceData:
    """Test cases for the _truncate_service_data function."""

    @patch("dolly.agol.retry")
    @patch("dolly.agol.logger")
    def test_truncate_success(self, mock_logger, mock_retry):
        mock_service_item = Mock()
        mock_retry.return_value = {"status": "Completed"}

        result = _truncate_service_data(mock_service_item)

        assert result is True
        mock_retry.assert_called_once_with(
            mock_service_item.manager.truncate,
            asynchronous=True,
            wait=True,
        )
        mock_logger.info.assert_called_once_with("truncating...")

    @patch("dolly.agol.retry")
    def test_truncate_failure(self, mock_retry):
        mock_service_item = Mock()
        mock_retry.return_value = {"status": "Failed"}

        with pytest.raises(
            RuntimeError, match="Failed to truncate existing data in service"
        ):
            _truncate_service_data(mock_service_item)


class TestAppendNewDataToService:
    """Test cases for the _append_new_data_to_service function."""

    @patch("dolly.agol.retry")
    @patch("dolly.agol.logger")
    def test_append_success(self, mock_logger, mock_retry):
        mock_service_item = Mock()
        mock_gdb_item = Mock()
        mock_gdb_item.id = "gdb_item_id"
        mock_retry.return_value = (True, [])

        result = _append_new_data_to_service(
            mock_service_item, mock_gdb_item, "service_name"
        )

        assert result is True
        mock_retry.assert_called_once_with(
            mock_service_item.append,
            item_id="gdb_item_id",
            upload_format="filegdb",
            source_table_name="service_name",
            return_messages=True,
            rollback=True,
        )
        mock_logger.info.assert_called_once_with("appending: service_name")

    @patch("dolly.agol.retry")
    @patch("dolly.agol.logger")
    def test_append_failure(self, mock_logger, mock_retry):
        mock_service_item = Mock()
        mock_gdb_item = Mock()
        mock_gdb_item.id = "gdb_item_id"
        mock_retry.return_value = (False, [])

        result = _append_new_data_to_service(
            mock_service_item, mock_gdb_item, "service_name"
        )

        assert result is False
        mock_logger.error.assert_called_once_with("Append failed but did not error")
