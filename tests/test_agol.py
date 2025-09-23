from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from dolly.agol import (
    _count_features_in_agol_service,
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
    _truncate_and_append,
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

    @patch("dolly.agol.APP_ENVIRONMENT", "other")
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

    @patch("dolly.agol.APP_ENVIRONMENT", "other")
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

    @patch("dolly.agol.APP_ENVIRONMENT", "other")
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
            f"Error searching for existing gdb item with title {title}", exc_info=True
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


class TestTruncateAndAppend:
    """Tests for the combined _truncate_and_append operation."""

    def setup_method(self):
        self.mock_service = Mock()
        self.mock_gdb_item = Mock()
        self.mock_gdb_item.id = "gdb-id"

    def test_success_bool_tuple(self):
        # Simulate truncate success and append returning (True, messages)
        self.mock_service.manager.truncate.return_value = {"status": "Completed"}
        self.mock_service.append.return_value = (True, [])

        assert _truncate_and_append(self.mock_service, self.mock_gdb_item, "svc")
        self.mock_service.manager.truncate.assert_called_once()
        self.mock_service.append.assert_called_once()

    def test_success_bool_only(self):
        # Simulate append returning just True
        self.mock_service.manager.truncate.return_value = {"status": "Completed"}
        self.mock_service.append.return_value = True

        assert _truncate_and_append(self.mock_service, self.mock_gdb_item, "svc")

    def test_truncate_failure_raises(self):
        self.mock_service.manager.truncate.return_value = {"status": "Failed"}

        with pytest.raises(RuntimeError, match="Failed to truncate"):
            _truncate_and_append(self.mock_service, self.mock_gdb_item, "svc")

    def test_append_failure_raises(self):
        self.mock_service.manager.truncate.return_value = {"status": "Completed"}
        # Simulate append returning (False, messages)
        self.mock_service.append.return_value = (False, ["error"])

        with pytest.raises(RuntimeError, match="Append failed"):
            _truncate_and_append(self.mock_service, self.mock_gdb_item, "svc")


class TestZipAndUploadFgdb:
    """Test cases for the zip_and_upload_fgdb function."""

    @patch("dolly.agol._upload_item_to_agol")
    @patch("dolly.agol._delete_agol_item")
    @patch("dolly.agol._search_existing_item")
    @patch("dolly.agol._generate_upload_tags")
    @patch("dolly.agol._generate_upload_title")
    @patch("dolly.agol._create_zip_from_fgdb")
    @patch("dolly.agol._get_gis_connection")
    def test_zip_and_upload_without_existing_item(
        self,
        mock_get_gis,
        mock_create_zip,
        mock_generate_title,
        mock_generate_tags,
        mock_search_existing,
        mock_delete_item,
        mock_upload_item,
    ):
        """Test zip and upload when no existing item exists."""
        # Setup mocks
        fgdb_path = Path("/test/data.gdb")
        zip_path = Path("/test/data.zip")
        mock_create_zip.return_value = zip_path
        mock_generate_title.return_value = "Test Title"
        mock_generate_tags.return_value = "Test,Tags"
        mock_search_existing.return_value = []
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis
        mock_uploaded_item = Mock()
        mock_upload_item.return_value = mock_uploaded_item

        from dolly.agol import zip_and_upload_fgdb

        result = zip_and_upload_fgdb(fgdb_path)

        # Verify all functions were called correctly
        mock_create_zip.assert_called_once_with(fgdb_path)
        mock_generate_title.assert_called_once_with(fgdb_path.stem)
        mock_generate_tags.assert_called_once()
        mock_search_existing.assert_called_once_with("Test Title", mock_gis)
        mock_delete_item.assert_not_called()
        mock_upload_item.assert_called_once_with(
            zip_path, "Test Title", "Test,Tags", mock_gis
        )

        assert result == mock_uploaded_item

    @patch("dolly.agol._upload_item_to_agol")
    @patch("dolly.agol._delete_agol_item")
    @patch("dolly.agol._search_existing_item")
    @patch("dolly.agol._generate_upload_tags")
    @patch("dolly.agol._generate_upload_title")
    @patch("dolly.agol._create_zip_from_fgdb")
    @patch("dolly.agol.logger")
    def test_zip_and_upload_with_existing_item(
        self,
        mock_logger,
        mock_create_zip,
        mock_generate_title,
        mock_generate_tags,
        mock_search_existing,
        mock_delete_item,
        mock_upload_item,
    ):
        """Test zip and upload when existing item needs to be deleted."""
        # Setup mocks
        fgdb_path = Path("/test/data.gdb")
        zip_path = Path("/test/data.zip")
        mock_create_zip.return_value = zip_path
        mock_generate_title.return_value = "Test Title"
        mock_generate_tags.return_value = "Test,Tags"

        existing_item = Mock()
        existing_item.id = "existing-id"
        mock_search_existing.return_value = [existing_item]
        mock_delete_item.return_value = True

        mock_gis = Mock()
        mock_uploaded_item = Mock()
        mock_upload_item.return_value = mock_uploaded_item

        from dolly.agol import zip_and_upload_fgdb

        result = zip_and_upload_fgdb(fgdb_path, mock_gis)

        # Verify existing item was deleted
        mock_delete_item.assert_called_once_with(existing_item)
        mock_logger.info.assert_called_once_with(
            f"Found existing gdb item {existing_item.id}, deleting it before uploading new gdb"
        )
        mock_upload_item.assert_called_once_with(
            zip_path, "Test Title", "Test,Tags", mock_gis
        )

        assert result == mock_uploaded_item


class TestUpdateFeatureServices:
    """Test cases for the update_feature_services function."""

    @patch("dolly.agol._count_features_in_agol_service")
    @patch("dolly.agol.set_table_hash")
    @patch("dolly.agol.retry")
    @patch("dolly.agol.get_service_from_title")
    @patch("dolly.agol._truncate_and_append")
    @patch("dolly.agol._get_appropriate_service_layer")
    @patch("dolly.agol._get_service_item_from_agol")
    @patch("dolly.agol._get_gis_connection")
    @patch("dolly.agol.logger")
    def test_update_feature_services_success(
        self,
        mock_logger,
        mock_get_gis,
        mock_get_service_item,
        mock_get_service_layer,
        mock_truncate_and_append,
        mock_get_service_from_title,
        mock_retry,
        mock_set_table_hash,
        mock_count_features,
    ):
        """Test successful update of feature services."""
        # Setup mocks
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis

        mock_gdb_item = Mock()
        mock_gdb_item.id = "gdb-item-id"

        tables = ["sgid.society.cemeteries", "sgid.transportation.roads"]
        current_hashes = {
            "sgid.society.cemeteries": "hash1",
            "sgid.transportation.roads": "hash2",
        }
        agol_items_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"},
            "sgid.transportation.roads": {"published_name": "Utah Roads"},
        }

        mock_item1 = Mock()
        mock_item2 = Mock()
        mock_get_service_item.side_effect = [mock_item1, mock_item2]

        mock_service1 = Mock()
        mock_service2 = Mock()
        mock_get_service_layer.side_effect = [mock_service1, mock_service2]

        mock_truncate_and_append.return_value = True
        mock_get_service_from_title.side_effect = ["cemeteries", "roads"]
        mock_count_features.return_value = 1000  # Mock feature count

        source_counts = {
            "sgid.society.cemeteries": 1000,
            "sgid.transportation.roads": 2000,
        }

        from dolly.agol import update_feature_services

        update_feature_services(
            mock_gdb_item, tables, agol_items_lookup, current_hashes, source_counts
        )

        # Verify all services were processed
        assert mock_get_service_item.call_count == 2
        assert mock_get_service_layer.call_count == 2
        assert mock_truncate_and_append.call_count == 2

        # Verify cleanup - gdb item should be deleted
        mock_retry.assert_called_once_with(mock_gdb_item.delete, permanent=True)
        mock_logger.info.assert_any_call("deleting temporary FGDB item")

    @patch("dolly.agol._get_service_item_from_agol")
    @patch("dolly.agol._get_gis_connection")
    @patch("dolly.agol.logger")
    def test_update_feature_services_missing_item(
        self, mock_logger, mock_get_gis, mock_get_service_item
    ):
        """Test update when AGOL item is missing."""
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis
        mock_gdb_item = Mock()

        tables = ["sgid.society.cemeteries"]
        current_hashes = {"sgid.society.cemeteries": "hash1"}
        agol_items_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"}
        }

        mock_get_service_item.return_value = None

        source_counts = {"sgid.society.cemeteries": 1000}

        from dolly.agol import update_feature_services

        update_feature_services(
            mock_gdb_item, tables, agol_items_lookup, current_hashes, source_counts
        )

        # Should not delete gdb item when there are errors
        mock_gdb_item.delete.assert_not_called()

    @patch("dolly.agol._get_service_item_from_agol")
    @patch("dolly.agol._get_gis_connection")
    @patch("dolly.agol.logger")
    def test_update_feature_services_no_gis_connection_provided(
        self, mock_logger, mock_get_gis, mock_get_service_item
    ):
        """Test update when no GIS connection is provided (covers line 365)."""
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis
        mock_gdb_item = Mock()

        tables = ["sgid.society.cemeteries"]
        current_hashes = {"sgid.society.cemeteries": "hash1"}
        agol_items_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"}
        }

        mock_get_service_item.return_value = None

        from dolly.agol import update_feature_services

        source_counts = {"sgid.society.cemeteries": 1000}

        # Call without providing gis_connection (None by default)
        update_feature_services(
            mock_gdb_item, tables, agol_items_lookup, current_hashes, source_counts
        )

        # Verify _get_gis_connection was called
        mock_get_gis.assert_called_once()
        mock_get_service_item.assert_called_once_with(
            "sgid.society.cemeteries", agol_items_lookup, mock_gis
        )

    @patch("dolly.agol._count_features_in_agol_service")
    @patch("dolly.agol.get_service_from_title")
    @patch("dolly.agol._truncate_and_append")
    @patch("dolly.agol._get_appropriate_service_layer")
    @patch("dolly.agol._get_service_item_from_agol")
    @patch("dolly.agol._get_gis_connection")
    @patch("dolly.agol.logger")
    def test_update_feature_services_append_failure(
        self,
        mock_logger,
        mock_get_gis,
        mock_get_service_item,
        mock_get_service_layer,
        mock_truncate_and_append,
        mock_get_service_from_title,
        mock_count_features,
    ):
        """Test update when append operation fails (covers line 390)."""
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis
        mock_gdb_item = Mock()

        tables = ["sgid.society.cemeteries"]
        current_hashes = {"sgid.society.cemeteries": "hash1"}
        agol_items_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"}
        }

        mock_item = Mock()
        mock_get_service_item.return_value = mock_item

        mock_service = Mock()
        mock_get_service_layer.return_value = mock_service

        mock_truncate_and_append.return_value = (
            False  # This should trigger has_errors = True
        )
        mock_get_service_from_title.return_value = "cemeteries"
        mock_count_features.return_value = 1000  # Mock feature count

        source_counts = {"sgid.society.cemeteries": 1000}

        from dolly.agol import update_feature_services

        update_feature_services(
            mock_gdb_item, tables, agol_items_lookup, current_hashes, source_counts
        )

        # Verify combined op was called and returned False
        mock_truncate_and_append.assert_called_once()
        # Should not delete gdb item when there are errors
        mock_gdb_item.delete.assert_not_called()

    @patch("dolly.agol._count_features_in_agol_service")
    @patch("dolly.agol._truncate_and_append")
    @patch("dolly.agol._get_appropriate_service_layer")
    @patch("dolly.agol._get_service_item_from_agol")
    @patch("dolly.agol._get_gis_connection")
    @patch("dolly.agol.logger")
    def test_update_feature_services_with_exception(
        self,
        mock_logger,
        mock_get_gis,
        mock_get_service_item,
        mock_get_service_layer,
        mock_truncate_and_append,
        mock_count_features,
    ):
        """Test update when an exception occurs during processing."""
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis
        mock_gdb_item = Mock()

        tables = ["sgid.society.cemeteries"]
        current_hashes = {"sgid.society.cemeteries": "hash1"}
        agol_items_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"}
        }

        mock_item = Mock()
        mock_get_service_item.return_value = mock_item
        mock_get_service_layer.side_effect = Exception("Service layer error")

        source_counts = {"sgid.society.cemeteries": 1000}

        from dolly.agol import update_feature_services

        update_feature_services(
            mock_gdb_item, tables, agol_items_lookup, current_hashes, source_counts
        )

        # Should log the error
        mock_logger.error.assert_called_once()
        # Should not delete gdb item when there are errors
        mock_gdb_item.delete.assert_not_called()


class TestCreateAndPublishService:
    """Test cases for the _create_and_publish_service function."""

    @patch("dolly.agol.retry")
    @patch("dolly.agol.zip_and_upload_fgdb")
    @patch("dolly.agol.create_fgdb")
    @patch("dolly.agol.logger")
    def test_create_and_publish_service_success(
        self, mock_logger, mock_create_fgdb, mock_zip_upload, mock_retry
    ):
        """Test successful creation and publishing of service."""
        # Setup mocks
        table = "sgid.society.cemeteries"
        agol_items_lookup = {table: {"published_name": "Utah Cemeteries"}}
        mock_gis = Mock()

        fgdb_path = Path("/test/society_cemeteries.gdb")
        source_counts = {table: 1000}
        mock_create_fgdb.return_value = (fgdb_path, source_counts)

        mock_single_item = Mock()
        mock_zip_upload.return_value = mock_single_item

        mock_published_item = Mock()
        mock_retry.return_value = mock_published_item

        from dolly.agol import _create_and_publish_service

        result = _create_and_publish_service(table, agol_items_lookup, mock_gis)

        # Verify function calls
        mock_create_fgdb.assert_called_once_with([table], agol_items_lookup)
        mock_zip_upload.assert_called_once_with(fgdb_path, mock_gis)
        mock_retry.assert_called_once_with(
            mock_single_item.publish,
            publish_parameters={"name": fgdb_path.stem},
            file_type="fileGeodatabase",
        )
        mock_single_item.delete.assert_called_once_with(permanent=True)

        assert result == mock_published_item

    @patch("dolly.agol.create_fgdb")
    @patch("dolly.agol.logger")
    def test_create_and_publish_service_exception(self, mock_logger, mock_create_fgdb):
        """Test exception handling during service creation."""
        table = "sgid.society.cemeteries"
        agol_items_lookup = {table: {"published_name": "Utah Cemeteries"}}
        mock_gis = Mock()

        mock_create_fgdb.side_effect = Exception("FGDB creation failed")

        from dolly.agol import _create_and_publish_service

        result = _create_and_publish_service(table, agol_items_lookup, mock_gis)

        assert result is None
        mock_logger.error.assert_called_once()


class TestConfigurePublishedService:
    """Test cases for the _configure_published_service function."""

    @patch("dolly.agol.APP_ENVIRONMENT", "prod")
    @patch("dolly.agol.retry")
    @patch("dolly.agol.FeatureLayerCollection")
    @patch("dolly.agol._generate_service_title")
    @patch("dolly.agol._generate_service_tags")
    def test_configure_published_service_prod_success(
        self,
        mock_generate_tags,
        mock_generate_title,
        mock_flc_class,
        mock_retry,
    ):
        """Test successful configuration in production environment."""
        # Setup mocks
        mock_item = Mock()
        table = "sgid.society.cemeteries"
        agol_items_lookup = {table: {"published_name": "Utah Cemeteries"}}

        mock_generate_tags.return_value = "UGRC,SGID,Society"
        mock_generate_title.return_value = "Utah Cemeteries"

        mock_manager = Mock()
        mock_flc = Mock()
        mock_flc.manager = mock_manager
        mock_flc_class.fromitem.return_value = mock_flc

        from dolly.agol import _configure_published_service

        result = _configure_published_service(mock_item, table, agol_items_lookup)

        # Verify metadata update
        mock_retry.assert_any_call(
            mock_item.update,
            {
                "title": "Utah Cemeteries",
                "description": "TBD",
                "snippet": "TBD",
                "tags": "UGRC,SGID,Society",
            },
        )

        # Verify capabilities update
        mock_retry.assert_any_call(
            mock_manager.update_definition, {"capabilities": "Query,Extract"}
        )

        # Verify move to category folder
        mock_retry.assert_any_call(mock_item.move, "Society")

        # Verify production permissions
        assert mock_item.sharing.sharing_level == "EVERYONE"
        assert mock_item.content_status == "public_authoritative"
        mock_retry.assert_any_call(mock_item.protect)

        assert result is True

    @patch("dolly.agol.APP_ENVIRONMENT", "dev")
    @patch("dolly.agol.retry")
    @patch("dolly.agol.FeatureLayerCollection")
    @patch("dolly.agol._generate_service_title")
    @patch("dolly.agol._generate_service_tags")
    def test_configure_published_service_dev_success(
        self,
        mock_generate_tags,
        mock_generate_title,
        mock_flc_class,
        mock_retry,
    ):
        """Test successful configuration in development environment."""
        mock_item = Mock()
        table = "sgid.society.cemeteries"
        agol_items_lookup = {table: {"published_name": "Utah Cemeteries"}}

        mock_generate_tags.return_value = "UGRC,SGID,Society,Test"
        mock_generate_title.return_value = "Utah Cemeteries (Test)"

        mock_manager = Mock()
        mock_flc = Mock()
        mock_flc.manager = mock_manager
        mock_flc_class.fromitem.return_value = mock_flc

        from dolly.agol import _configure_published_service

        result = _configure_published_service(mock_item, table, agol_items_lookup)

        # Should not set production permissions in dev
        assert (
            not hasattr(mock_item.sharing, "sharing_level")
            or mock_item.sharing.sharing_level != "EVERYONE"
        )
        mock_item.protect.assert_not_called()

        assert result is True

    @patch("dolly.agol._generate_service_tags")
    @patch("dolly.agol.logger")
    def test_configure_published_service_exception(
        self, mock_logger, mock_generate_tags
    ):
        """Test exception handling during service configuration."""
        mock_item = Mock()
        mock_item.id = "test-item-id"
        table = "sgid.society.cemeteries"
        agol_items_lookup = {table: {"published_name": "Utah Cemeteries"}}

        mock_generate_tags.side_effect = Exception("Configuration failed")

        from dolly.agol import _configure_published_service

        result = _configure_published_service(mock_item, table, agol_items_lookup)

        assert result is False
        mock_logger.error.assert_called_once()


class TestPublishNewFeatureServices:
    """Test cases for the publish_new_feature_services function."""

    @patch("dolly.agol.set_table_hash")
    @patch("dolly.agol.update_agol_item")
    @patch("dolly.agol._configure_published_service")
    @patch("dolly.agol._create_and_publish_service")
    @patch("dolly.agol._get_gis_connection")
    @patch("dolly.agol.logger")
    def test_publish_new_feature_services_success(
        self,
        mock_logger,
        mock_get_gis,
        mock_create_publish,
        mock_configure,
        mock_update_agol_item,
        mock_set_table_hash,
    ):
        """Test successful publishing of new feature services."""
        # Setup mocks
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis

        tables = ["sgid.society.cemeteries", "sgid.transportation.roads"]
        current_hashes = {
            "sgid.society.cemeteries": "hash1",
            "sgid.transportation.roads": "hash2",
        }
        agol_items_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"},
            "sgid.transportation.roads": {"published_name": "Utah Roads"},
        }

        mock_item1 = Mock()
        mock_item1.id = "item1-id"
        mock_item2 = Mock()
        mock_item2.id = "item2-id"

        mock_create_publish.side_effect = [mock_item1, mock_item2]
        mock_configure.return_value = True

        from dolly.agol import publish_new_feature_services

        publish_new_feature_services(tables, agol_items_lookup, current_hashes)

        # Verify all tables were processed
        assert mock_create_publish.call_count == 2
        assert mock_configure.call_count == 2
        assert mock_update_agol_item.call_count == 2

        # Verify specific calls
        mock_create_publish.assert_any_call(
            "sgid.society.cemeteries", agol_items_lookup, mock_gis
        )
        mock_create_publish.assert_any_call(
            "sgid.transportation.roads", agol_items_lookup, mock_gis
        )

        mock_update_agol_item.assert_any_call("sgid.society.cemeteries", "item1-id")
        mock_update_agol_item.assert_any_call("sgid.transportation.roads", "item2-id")

    @patch("dolly.agol._create_and_publish_service")
    @patch("dolly.agol._get_gis_connection")
    @patch("dolly.agol.logger")
    def test_publish_new_feature_services_creation_failure(
        self, mock_logger, mock_get_gis, mock_create_publish
    ):
        """Test handling of creation failure."""
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis

        tables = ["sgid.society.cemeteries"]
        current_hashes = {"sgid.society.cemeteries": "hash1"}
        agol_items_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"}
        }

        mock_create_publish.return_value = None

        from dolly.agol import publish_new_feature_services

        publish_new_feature_services(tables, agol_items_lookup, current_hashes)

        # Should continue processing even if creation fails
        mock_create_publish.assert_called_once()

    @patch("dolly.agol._configure_published_service")
    @patch("dolly.agol._create_and_publish_service")
    @patch("dolly.agol._get_gis_connection")
    def test_publish_new_feature_services_configuration_failure(
        self, mock_get_gis, mock_create_publish, mock_configure
    ):
        """Test handling of configuration failure."""
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis

        tables = ["sgid.society.cemeteries"]
        current_hashes = {"sgid.society.cemeteries": "hash1"}
        agol_items_lookup = {
            "sgid.society.cemeteries": {"published_name": "Utah Cemeteries"}
        }

        mock_item = Mock()
        mock_create_publish.return_value = mock_item
        mock_configure.return_value = False

        from dolly.agol import publish_new_feature_services

        publish_new_feature_services(
            tables, agol_items_lookup, current_hashes, mock_gis
        )

        # Should continue processing even if configuration fails
        mock_configure.assert_called_once()


class TestCountFeaturesInAgolService:
    """Tests for the _count_features_in_agol_service helper."""

    @patch("dolly.agol.retry")
    @patch("dolly.agol.Table")
    @patch("dolly.agol.Item")
    @patch("dolly.agol._get_gis_connection")
    def test_counts_table_features_success(
        self, mock_get_gis, mock_item_cls, mock_table_cls, mock_retry
    ):
        # Arrange
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis

        mock_item_instance = Mock()
        mock_item_cls.return_value = mock_item_instance

        mock_layer = Mock()
        mock_table_cls.fromitem.return_value = mock_layer

        mock_retry.return_value = 123

        service_item = Mock()
        service_item.properties = {"type": "Table", "serviceItemId": "abc123"}

        # Act
        result = _count_features_in_agol_service(service_item)

        # Assert
        assert result == 123
        mock_item_cls.assert_called_once_with(mock_gis, "abc123")
        mock_table_cls.fromitem.assert_called_once_with(mock_item_instance)
        mock_retry.assert_called_once_with(mock_layer.query, return_count_only=True)

    @patch("dolly.agol.retry")
    @patch("dolly.agol.FeatureLayer")
    @patch("dolly.agol.Item")
    @patch("dolly.agol._get_gis_connection")
    def test_counts_feature_layer_success(
        self, mock_get_gis, mock_item_cls, mock_fl_cls, mock_retry
    ):
        # Arrange
        mock_gis = Mock()
        mock_get_gis.return_value = mock_gis

        mock_item_instance = Mock()
        mock_item_cls.return_value = mock_item_instance

        mock_layer = Mock()
        mock_fl_cls.fromitem.return_value = mock_layer

        mock_retry.return_value = 456

        service_item = Mock()
        service_item.properties = {
            "type": "Feature Layer",
            "serviceItemId": "svc-789",
        }

        # Act
        result = _count_features_in_agol_service(service_item)

        # Assert
        assert result == 456
        mock_item_cls.assert_called_once_with(mock_gis, "svc-789")
        mock_fl_cls.fromitem.assert_called_once_with(mock_item_instance)
        mock_retry.assert_called_once_with(mock_layer.query, return_count_only=True)

    @patch("dolly.agol.logger")
    @patch("dolly.agol.Table")
    @patch("dolly.agol.Item")
    @patch("dolly.agol._get_gis_connection")
    def test_error_path_returns_negative_one(
        self, mock_get_gis, mock_item_cls, mock_table_cls, mock_logger
    ):
        # Arrange: make fromitem raise
        mock_table_cls.fromitem.side_effect = Exception("boom")

        service_item = Mock()
        service_item.properties = {"type": "Table", "serviceItemId": "oops"}

        # Act
        result = _count_features_in_agol_service(service_item)

        # Assert
        assert result == -1
        mock_logger.error.assert_called_once()
