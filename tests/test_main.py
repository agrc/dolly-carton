from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from dolly.main import _main_logic, clean_up, cleanup_dev_agol_items


class TestCleanUp:
    """Test cases for the clean_up function."""

    @patch("dolly.main.OUTPUT_PATH")
    @patch("dolly.main.logger")
    def test_clean_up_output_path_does_not_exist(self, mock_logger, mock_output_path):
        """Test cleanup when output path doesn't exist."""
        mock_output_path.exists.return_value = False

        clean_up()

        mock_output_path.exists.assert_called_once()
        mock_logger.info.assert_called_once_with("Cleaned up temporary files.")

    @patch("dolly.main.OUTPUT_PATH")
    @patch("dolly.main.logger")
    def test_clean_up_with_files_and_directories(self, mock_logger, mock_output_path):
        """Test cleanup with mixed files and directories."""
        # Setup mock directory structure
        mock_output_path.exists.return_value = True

        # Mock files
        mock_file1 = Mock()
        mock_file1.is_dir.return_value = False
        mock_file1.is_file.return_value = True
        mock_file1.name = "temp_file.txt"

        mock_gitkeep = Mock()
        mock_gitkeep.is_dir.return_value = False
        mock_gitkeep.is_file.return_value = True
        mock_gitkeep.name = ".gitkeep"

        # Mock directory with nested files
        mock_nested_file = Mock()
        mock_nested_file.is_file.return_value = True

        mock_dir = Mock()
        mock_dir.is_dir.return_value = True
        mock_dir.is_file.return_value = False
        mock_dir.rglob.return_value = [mock_nested_file]

        mock_output_path.iterdir.return_value = [mock_file1, mock_gitkeep, mock_dir]

        clean_up()

        # Verify regular file is deleted
        mock_file1.unlink.assert_called_once()

        # Verify .gitkeep is preserved (not deleted)
        mock_gitkeep.unlink.assert_not_called()

        # Verify nested files are deleted and directory is removed
        mock_nested_file.unlink.assert_called_once()
        mock_dir.rmdir.assert_called_once()

        mock_logger.info.assert_called_once_with("Cleaned up temporary files.")

    @patch("dolly.main.OUTPUT_PATH")
    @patch("dolly.main.logger")
    def test_clean_up_empty_directory(self, mock_logger, mock_output_path):
        """Test cleanup with empty output directory."""
        mock_output_path.exists.return_value = True
        mock_output_path.iterdir.return_value = []

        clean_up()

        mock_logger.info.assert_called_once_with("Cleaned up temporary files.")

    @patch("dolly.main.OUTPUT_PATH")
    @patch("dolly.main.logger")
    def test_clean_up_only_gitkeep_file(self, mock_logger, mock_output_path):
        """Test cleanup when only .gitkeep file exists."""
        mock_output_path.exists.return_value = True

        mock_gitkeep = Mock()
        mock_gitkeep.is_dir.return_value = False
        mock_gitkeep.is_file.return_value = True
        mock_gitkeep.name = ".gitkeep"

        mock_output_path.iterdir.return_value = [mock_gitkeep]

        clean_up()

        # .gitkeep should not be deleted
        mock_gitkeep.unlink.assert_not_called()
        mock_logger.info.assert_called_once_with("Cleaned up temporary files.")


class TestMain:
    """Test cases for the main function."""

    def setup_method(self):
        """Setup common mocks for main function tests."""
        self.mock_agol_items_lookup = {
            "sgid.society.cemeteries": {
                "item_id": "existing-item-id",
                "published_name": "Utah Cemeteries",
            },
            "sgid.transportation.roads": {
                "item_id": None,
                "published_name": "Utah Roads",
            },
        }

    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.set_last_checked")
    @patch("dolly.main.get_updated_tables")
    @patch("dolly.main.get_last_checked")
    @patch("dolly.main.clean_up")
    @patch("dolly.summary.requests.post")
    @patch("dolly.main.logger")
    def test_main_no_updated_tables(
        self,
        mock_logger,
        mock_requests_post,
        mock_clean_up,
        mock_get_last_checked,
        mock_get_updated_tables,
        mock_set_last_checked,
        mock_precisedelta,
        mock_time,
    ):
        """Test main function when no tables have been updated."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1005.0]  # start and end times
        mock_last_checked = datetime(2023, 1, 1)
        mock_get_last_checked.return_value = mock_last_checked
        mock_get_updated_tables.return_value = []
        mock_precisedelta.return_value = "5 seconds"
        # Mock Slack requests to prevent actual HTTP calls
        mock_requests_post.return_value.status_code = 200

        _main_logic()

        # Verify function calls
        mock_clean_up.assert_called_once()
        mock_get_last_checked.assert_called_once()
        mock_get_updated_tables.assert_called_once_with(mock_last_checked)

        # Should not call set_last_checked when no tables are updated
        mock_set_last_checked.assert_not_called()

        # Verify logging
        mock_logger.info.assert_any_call("Starting Dolly Carton process...")
        mock_logger.info.assert_any_call(f"Last checked: {mock_last_checked}")
        mock_logger.info.assert_any_call("Updated tables: []")
        mock_logger.info.assert_any_call("No updated tables found.")

    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.set_last_checked")
    @patch("dolly.main.datetime")
    @patch("dolly.main.update_feature_services")
    @patch("dolly.main.zip_and_upload_fgdb")
    @patch("dolly.main.create_fgdb")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_updated_tables")
    @patch("dolly.main.get_last_checked")
    @patch("dolly.main.clean_up")
    @patch("dolly.summary.requests.post")
    @patch("dolly.main.logger")
    def test_main_only_existing_services_to_update(
        self,
        mock_logger,
        mock_requests_post,
        mock_clean_up,
        mock_get_last_checked,
        mock_get_updated_tables,
        mock_get_agol_items_lookup,
        mock_create_fgdb,
        mock_zip_and_upload_fgdb,
        mock_update_feature_services,
        mock_datetime,
        mock_set_last_checked,
        mock_precisedelta,
        mock_time,
    ):
        """Test main function with only existing services to update."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1010.0]
        mock_last_checked = datetime(2023, 1, 1)
        mock_get_last_checked.return_value = mock_last_checked
        mock_get_updated_tables.return_value = ["sgid.society.cemeteries"]
        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup
        # Mock Slack requests to prevent actual HTTP calls
        mock_requests_post.return_value.status_code = 200

        mock_fgdb_path = Path("/test/output/data.gdb")
        mock_create_fgdb.return_value = mock_fgdb_path

        mock_gdb_item = Mock()
        mock_zip_and_upload_fgdb.return_value = mock_gdb_item

        mock_current_time = datetime(2023, 1, 2)
        mock_datetime.now.return_value = mock_current_time
        mock_precisedelta.return_value = "10 seconds"

        _main_logic()

        # Verify workflow for existing services
        mock_create_fgdb.assert_called_once_with(
            ["sgid.society.cemeteries"], self.mock_agol_items_lookup
        )
        mock_zip_and_upload_fgdb.assert_called_once_with(mock_fgdb_path)
        mock_update_feature_services.assert_called_once_with(
            mock_gdb_item,
            ["sgid.society.cemeteries"],
            self.mock_agol_items_lookup,
        )

        # Verify timestamp update
        mock_set_last_checked.assert_called_once_with(mock_current_time)

        # Verify logging
        mock_logger.info.assert_any_call(
            "Updating existing feature services for tables: ['sgid.society.cemeteries']"
        )
        mock_logger.info.assert_any_call("No new feature services to publish.")

    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.set_last_checked")
    @patch("dolly.main.datetime")
    @patch("dolly.main.publish_new_feature_services")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_updated_tables")
    @patch("dolly.main.get_last_checked")
    @patch("dolly.main.clean_up")
    @patch("dolly.summary.requests.post")
    @patch("dolly.main.logger")
    def test_main_only_new_services_to_publish(
        self,
        mock_logger,
        mock_requests_post,
        mock_clean_up,
        mock_get_last_checked,
        mock_get_updated_tables,
        mock_get_agol_items_lookup,
        mock_publish_new_feature_services,
        mock_datetime,
        mock_set_last_checked,
        mock_precisedelta,
        mock_time,
    ):
        """Test main function with only new services to publish."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1015.0]
        mock_last_checked = datetime(2023, 1, 1)
        mock_get_last_checked.return_value = mock_last_checked
        mock_get_updated_tables.return_value = ["sgid.transportation.roads"]
        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup
        # Mock Slack requests to prevent actual HTTP calls
        mock_requests_post.return_value.status_code = 200

        mock_current_time = datetime(2023, 1, 2)
        mock_datetime.now.return_value = mock_current_time
        mock_precisedelta.return_value = "15 seconds"

        _main_logic()

        # Verify workflow for new services
        mock_publish_new_feature_services.assert_called_once_with(
            ["sgid.transportation.roads"], self.mock_agol_items_lookup
        )

        # Verify timestamp update
        mock_set_last_checked.assert_called_once_with(mock_current_time)

        # Verify logging
        mock_logger.info.assert_any_call("No existing feature services to update.")
        mock_logger.info.assert_any_call(
            "Updated tables: ['sgid.transportation.roads']"
        )

    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.set_last_checked")
    @patch("dolly.main.datetime")
    @patch("dolly.main.publish_new_feature_services")
    @patch("dolly.main.update_feature_services")
    @patch("dolly.main.zip_and_upload_fgdb")
    @patch("dolly.main.create_fgdb")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_updated_tables")
    @patch("dolly.main.get_last_checked")
    @patch("dolly.main.clean_up")
    @patch("dolly.summary.requests.post")
    @patch("dolly.main.logger")
    def test_main_both_existing_and_new_services(
        self,
        mock_logger,
        mock_requests_post,
        mock_clean_up,
        mock_get_last_checked,
        mock_get_updated_tables,
        mock_get_agol_items_lookup,
        mock_create_fgdb,
        mock_zip_and_upload_fgdb,
        mock_update_feature_services,
        mock_publish_new_feature_services,
        mock_datetime,
        mock_set_last_checked,
        mock_precisedelta,
        mock_time,
    ):
        """Test main function with both existing and new services."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1020.0]
        mock_last_checked = datetime(2023, 1, 1)
        mock_get_last_checked.return_value = mock_last_checked
        mock_get_updated_tables.return_value = [
            "sgid.society.cemeteries",
            "sgid.transportation.roads",
        ]
        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup
        # Mock Slack requests to prevent actual HTTP calls
        mock_requests_post.return_value.status_code = 200

        mock_fgdb_path = Path("/test/output/data.gdb")
        mock_create_fgdb.return_value = mock_fgdb_path

        mock_gdb_item = Mock()
        mock_zip_and_upload_fgdb.return_value = mock_gdb_item

        mock_current_time = datetime(2023, 1, 2)
        mock_datetime.now.return_value = mock_current_time
        mock_precisedelta.return_value = "20 seconds"

        _main_logic()

        # Verify both workflows are executed
        mock_create_fgdb.assert_called_once_with(
            ["sgid.society.cemeteries"], self.mock_agol_items_lookup
        )
        mock_update_feature_services.assert_called_once_with(
            mock_gdb_item,
            ["sgid.society.cemeteries"],
            self.mock_agol_items_lookup,
        )
        mock_publish_new_feature_services.assert_called_once_with(
            ["sgid.transportation.roads"], self.mock_agol_items_lookup
        )

        # Verify timestamp update
        mock_set_last_checked.assert_called_once_with(mock_current_time)

    @patch("dolly.main.time.time")
    @patch("dolly.main.get_last_checked")
    @patch("dolly.main.clean_up")
    @patch("dolly.summary.requests.post")
    @patch("dolly.main.logger")
    def test_main_exception_handling(
        self,
        mock_logger,
        mock_requests_post,
        mock_clean_up,
        mock_get_last_checked,
        mock_time,
    ):
        """Test main function exception handling in finally block."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1005.0]
        mock_get_last_checked.side_effect = Exception("Database error")
        # Mock Slack requests to prevent actual HTTP calls
        mock_requests_post.return_value.status_code = 200

        # Exception should propagate, but finally block should still execute
        with pytest.raises(Exception, match="Database error"):
            _main_logic()

        # Verify cleanup is called even when exception occurs
        mock_clean_up.assert_called_once()

        # Verify finally block logging still executes
        mock_logger.info.assert_any_call("Starting Dolly Carton process...")

    @patch("dolly.main.publish_new_feature_services")
    @patch("dolly.main.update_feature_services")
    @patch("dolly.main.zip_and_upload_fgdb")
    @patch("dolly.main.create_fgdb")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.set_last_checked")
    @patch("dolly.main.get_updated_tables")
    @patch("dolly.main.get_last_checked")
    @patch("dolly.main.clean_up")
    @patch("dolly.summary.requests.post")
    @patch("dolly.main.logger")
    def test_main_with_cli_tables_parameter(
        self,
        mock_logger,
        mock_requests_post,
        mock_clean_up,
        mock_get_last_checked,
        mock_get_updated_tables,
        mock_set_last_checked,
        mock_get_agol_items_lookup,
        mock_create_fgdb,
        mock_zip_and_upload_fgdb,
        mock_update_feature_services,
        mock_publish_new_feature_services,
    ):
        """Test main function with CLI tables parameter overriding automatic detection."""
        # Setup mocks
        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup
        # Mock Slack requests to prevent actual HTTP calls
        mock_requests_post.return_value.status_code = 200

        mock_fgdb_path = Path("/test/output/data.gdb")
        mock_create_fgdb.return_value = mock_fgdb_path

        mock_gdb_item = Mock()
        mock_zip_and_upload_fgdb.return_value = mock_gdb_item

        # Call main with CLI tables parameter
        _main_logic(tables="sgid.society.cemeteries,sgid.transportation.roads")

        # Verify function calls
        mock_clean_up.assert_called_once()

        # get_last_checked and get_updated_tables should NOT be called when using CLI tables
        mock_get_last_checked.assert_not_called()
        mock_get_updated_tables.assert_not_called()

        # set_last_checked should NOT be called when using CLI tables
        mock_set_last_checked.assert_not_called()

        mock_get_agol_items_lookup.assert_called_once()

        # Both services should be processed (one existing, one new)
        mock_create_fgdb.assert_called_once_with(
            ["sgid.society.cemeteries"], self.mock_agol_items_lookup
        )
        mock_zip_and_upload_fgdb.assert_called_once_with(mock_fgdb_path)
        mock_update_feature_services.assert_called_once_with(
            mock_gdb_item,
            ["sgid.society.cemeteries"],
            self.mock_agol_items_lookup,
        )
        mock_publish_new_feature_services.assert_called_once_with(
            ["sgid.transportation.roads"],
            self.mock_agol_items_lookup,
        )

        # Verify logging
        mock_logger.info.assert_any_call("Starting Dolly Carton process...")
        mock_logger.info.assert_any_call(
            "Using CLI-provided tables: ['sgid.society.cemeteries', 'sgid.transportation.roads']"
        )


class TestCleanupDevAgolItems:
    """Test cases for the cleanup_dev_agol_items function."""

    def setup_method(self):
        """Setup common mocks for cleanup function tests."""
        self.mock_agol_items_lookup = {
            "sgid.society.cemeteries": {
                "item_id": "existing-item-id",
                "published_name": "Utah Cemeteries",
            },
            "sgid.transportation.roads": {
                "item_id": None,
                "published_name": "Utah Roads",
            },
        }

    @patch("dolly.main.APP_ENVIRONMENT", "prod")
    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.logger")
    def test_cleanup_dev_agol_items_not_in_dev_environment(
        self, mock_logger, mock_precisedelta, mock_time
    ):
        """Test cleanup function when not in dev environment."""
        mock_time.side_effect = [1000.0, 1005.0]
        mock_precisedelta.return_value = "5 seconds"

        with pytest.raises(
            ValueError, match="This command should only be run in dev environment!"
        ):
            cleanup_dev_agol_items()

        # Verify finally block still executes
        mock_logger.info.assert_any_call("Starting cleanup of dev feature services...")
        mock_logger.info.assert_any_call(
            "Dev feature services cleanup completed in 5 seconds"
        )

    @patch("dolly.main.os.getenv")
    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.GIS")
    @patch("dolly.main.get_secrets")
    @patch("dolly.main.logger")
    def test_cleanup_dev_agol_items_success(
        self,
        mock_logger,
        mock_get_secrets,
        mock_gis_class,
        mock_get_agol_items_lookup,
        mock_precisedelta,
        mock_time,
        mock_getenv,
    ):
        """Test successful cleanup of dev AGOL items."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1010.0]
        mock_getenv.return_value = "dev"
        mock_precisedelta.return_value = "10 seconds"

        mock_secrets = {"AGOL_USERNAME": "test_user", "AGOL_PASSWORD": "test_pass"}
        mock_get_secrets.return_value = mock_secrets

        mock_gis = Mock()
        mock_gis.users.me.username = "test_user"
        mock_gis_class.return_value = mock_gis

        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup

        # Mock search results for item without existing item_id
        mock_item = Mock()
        mock_item.id = "test-item-id"
        mock_item.delete.return_value = True
        mock_gis.content.search.return_value = [mock_item]

        cleanup_dev_agol_items()

        # Verify GIS connection
        mock_gis_class.assert_called_once_with(
            "https://utah.maps.arcgis.com",
            username="test_user",
            password="test_pass",
        )

        # Verify search is called for table without item_id
        mock_gis.content.search.assert_called_once_with(
            'title:"Utah Roads (Test)" AND owner:test_user',
            max_items=1,
        )

        # Verify item deletion
        mock_item.delete.assert_called_once_with(permanent=True)

        # Verify logging
        mock_logger.info.assert_any_call("Starting cleanup of dev feature services...")
        mock_logger.info.assert_any_call(
            "Cleaning up dev item for table sgid.transportation.roads (item_id: None)"
        )
        mock_logger.info.assert_any_call(
            "Deleting item test-item-id for table sgid.transportation.roads"
        )

    @patch("dolly.main.os.getenv")
    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.GIS")
    @patch("dolly.main.get_secrets")
    @patch("dolly.main.logger")
    def test_cleanup_dev_agol_items_no_search_results(
        self,
        mock_logger,
        mock_get_secrets,
        mock_gis_class,
        mock_get_agol_items_lookup,
        mock_precisedelta,
        mock_time,
        mock_getenv,
    ):
        """Test cleanup when no search results are found."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1010.0]
        mock_getenv.return_value = "dev"
        mock_precisedelta.return_value = "10 seconds"

        mock_secrets = {"AGOL_USERNAME": "test_user", "AGOL_PASSWORD": "test_pass"}
        mock_get_secrets.return_value = mock_secrets

        mock_gis = Mock()
        mock_gis.users.me.username = "test_user"
        mock_gis_class.return_value = mock_gis

        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup

        # Mock empty search results
        mock_gis.content.search.return_value = []

        cleanup_dev_agol_items()

        # Verify warning is logged
        mock_logger.warning.assert_called_once_with(
            "Item with title: Utah Roads (Test) not found, skipping deletion."
        )

    @patch("dolly.main.os.getenv")
    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.GIS")
    @patch("dolly.main.get_secrets")
    @patch("dolly.main.logger")
    def test_cleanup_dev_agol_items_deletion_failure(
        self,
        mock_logger,
        mock_get_secrets,
        mock_gis_class,
        mock_get_agol_items_lookup,
        mock_precisedelta,
        mock_time,
        mock_getenv,
    ):
        """Test cleanup when item deletion fails."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1010.0]
        mock_getenv.return_value = "dev"
        mock_precisedelta.return_value = "10 seconds"

        mock_secrets = {"AGOL_USERNAME": "test_user", "AGOL_PASSWORD": "test_pass"}
        mock_get_secrets.return_value = mock_secrets

        mock_gis = Mock()
        mock_gis.users.me.username = "test_user"
        mock_gis_class.return_value = mock_gis

        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup

        # Mock search results with failed deletion
        mock_item = Mock()
        mock_item.id = "test-item-id"
        mock_item.delete.return_value = False  # Deletion fails
        mock_gis.content.search.return_value = [mock_item]

        with pytest.raises(RuntimeError, match="Failed to delete item None"):
            cleanup_dev_agol_items()

    @patch("dolly.main.os.getenv")
    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.GIS")
    @patch("dolly.main.get_secrets")
    @patch("dolly.main.logger")
    def test_cleanup_dev_agol_items_skips_existing_items(
        self,
        mock_logger,
        mock_get_secrets,
        mock_gis_class,
        mock_get_agol_items_lookup,
        mock_precisedelta,
        mock_time,
        mock_getenv,
    ):
        """Test cleanup skips tables that already have item_ids."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1010.0]
        mock_getenv.return_value = "dev"
        mock_precisedelta.return_value = "10 seconds"

        mock_secrets = {"AGOL_USERNAME": "test_user", "AGOL_PASSWORD": "test_pass"}
        mock_get_secrets.return_value = mock_secrets

        mock_gis = Mock()
        mock_gis_class.return_value = mock_gis

        # Only include table with existing item_id
        agol_items_lookup = {
            "sgid.society.cemeteries": {
                "item_id": "existing-item-id",
                "published_name": "Utah Cemeteries",
            }
        }
        mock_get_agol_items_lookup.return_value = agol_items_lookup

        cleanup_dev_agol_items()

        # Verify no search or deletion occurs for existing items
        mock_gis.content.search.assert_not_called()

        # Verify completion logging
        mock_logger.info.assert_any_call(
            "Dev feature services cleanup completed in 10 seconds"
        )
