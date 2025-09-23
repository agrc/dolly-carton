from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from dolly.main import _main_logic, cleanup_dev_agol_items


class TestMain:
    """Tests for _main_logic with hash-based change detection."""

    def setup_method(self):
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
    @patch("dolly.main.get_current_hashes")
    @patch("dolly.main.determine_updated_tables")
    @patch("dolly.main.get_table_hashes")
    @patch("dolly.main.clean_up")
    @patch("dolly.main.logger")
    def test_main_no_updated_tables(
        self,
        mock_logger,
        mock_clean_up,
        mock_get_table_hashes,
        mock_determine_updated,
        mock_get_current_hashes,
        mock_precisedelta,
        mock_time,
    ):
        mock_time.side_effect = [1000.0, 1005.0]
        mock_get_table_hashes.return_value = {}
        mock_get_current_hashes.return_value = {}
        mock_determine_updated.return_value = []
        mock_precisedelta.return_value = "5 seconds"

        _main_logic()

        mock_clean_up.assert_called_once()
        mock_get_table_hashes.assert_called_once()
        mock_get_current_hashes.assert_called_once()
        mock_determine_updated.assert_called_once()
        mock_logger.info.assert_any_call("Starting Dolly Carton process...")
        mock_logger.info.assert_any_call("Tables with changed hashes: []")
        mock_logger.info.assert_any_call("No updated tables found.")

    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_current_hashes")
    @patch("dolly.main.determine_updated_tables")
    @patch("dolly.main.get_table_hashes")
    @patch("dolly.main.update_feature_services")
    @patch("dolly.main.zip_and_upload_fgdb")
    @patch("dolly.main.create_fgdb")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.clean_up")
    @patch("dolly.main.logger")
    def test_main_only_existing_services(
        self,
        mock_logger,
        mock_clean_up,
        mock_get_gis_connection,
        mock_get_agol_items_lookup,
        mock_create_fgdb,
        mock_zip_and_upload_fgdb,
        mock_update_feature_services,
        mock_get_table_hashes,
        mock_determine_updated,
        mock_get_current_hashes,
        mock_precisedelta,
        mock_time,
    ):
        mock_time.side_effect = [1000.0, 1010.0]
        mock_get_gis_connection.return_value = Mock()
        mock_get_table_hashes.return_value = {"sgid.society.cemeteries": "h0"}
        mock_get_current_hashes.return_value = {"sgid.society.cemeteries": "h1"}
        mock_determine_updated.return_value = ["sgid.society.cemeteries"]
        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup
        mock_precisedelta.return_value = "10 seconds"
        mock_create_fgdb.return_value = (
            Path("/test/output/data.gdb"),
            {"sgid.society.cemeteries": 1000},
        )
        mock_zip_and_upload_fgdb.return_value = Mock()

        _main_logic()

        mock_update_feature_services.assert_called_once()
        mock_logger.info.assert_any_call(
            "Updating existing feature services for tables: ['sgid.society.cemeteries']"
        )

    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_current_hashes")
    @patch("dolly.main.determine_updated_tables")
    @patch("dolly.main.get_table_hashes")
    @patch("dolly.main.publish_new_feature_services")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.clean_up")
    @patch("dolly.main.logger")
    def test_main_only_new_services(
        self,
        mock_logger,
        mock_clean_up,
        mock_get_gis_connection,
        mock_get_agol_items_lookup,
        mock_publish_new_feature_services,
        mock_get_table_hashes,
        mock_determine_updated,
        mock_get_current_hashes,
        mock_precisedelta,
        mock_time,
    ):
        mock_time.side_effect = [1000.0, 1015.0]
        mock_get_gis_connection.return_value = Mock()
        mock_get_table_hashes.return_value = {}
        mock_get_current_hashes.return_value = {"sgid.transportation.roads": "h2"}
        mock_determine_updated.return_value = ["sgid.transportation.roads"]
        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup
        mock_precisedelta.return_value = "15 seconds"

        _main_logic()

        mock_publish_new_feature_services.assert_called_once()

    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_current_hashes")
    @patch("dolly.main.determine_updated_tables")
    @patch("dolly.main.get_table_hashes")
    @patch("dolly.main.publish_new_feature_services")
    @patch("dolly.main.update_feature_services")
    @patch("dolly.main.zip_and_upload_fgdb")
    @patch("dolly.main.create_fgdb")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.clean_up")
    @patch("dolly.main.logger")
    def test_main_both_existing_and_new(
        self,
        mock_logger,
        mock_clean_up,
        mock_get_gis_connection,
        mock_get_agol_items_lookup,
        mock_create_fgdb,
        mock_zip_and_upload_fgdb,
        mock_update_feature_services,
        mock_publish_new_feature_services,
        mock_get_table_hashes,
        mock_determine_updated,
        mock_get_current_hashes,
        mock_precisedelta,
        mock_time,
    ):
        mock_time.side_effect = [1000.0, 1020.0]
        mock_get_gis_connection.return_value = Mock()
        mock_get_table_hashes.return_value = {"sgid.society.cemeteries": "h0"}
        mock_get_current_hashes.return_value = {
            "sgid.society.cemeteries": "h1",
            "sgid.transportation.roads": "h2",
        }
        mock_determine_updated.return_value = [
            "sgid.society.cemeteries",
            "sgid.transportation.roads",
        ]
        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup
        mock_precisedelta.return_value = "20 seconds"
        mock_create_fgdb.return_value = (
            Path("/test/output/data.gdb"),
            {"sgid.society.cemeteries": 1000, "sgid.transportation.roads": 2000},
        )
        mock_zip_and_upload_fgdb.return_value = Mock()

        _main_logic()

        mock_update_feature_services.assert_called_once()
        mock_publish_new_feature_services.assert_called_once()

    @patch("dolly.main.time.time")
    @patch("dolly.main.get_table_hashes")
    @patch("dolly.main.clean_up")
    @patch("dolly.main.logger")
    def test_main_exception_handling(
        self,
        mock_logger,
        mock_clean_up,
        mock_get_table_hashes,
        mock_time,
    ):
        from dolly.summary import get_current_summary

        mock_time.side_effect = [1000.0, 1005.0]
        mock_get_table_hashes.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            _main_logic()

        mock_clean_up.assert_called_once()
        mock_logger.error.assert_called_once()
        assert any(
            "Global error occurred" in c[0][0] for c in mock_logger.error.call_args_list
        )
        # Ensure summary captured error if created
        summary = get_current_summary()
        if summary:
            assert any("Database error" in e for e in summary.global_errors)

    @patch("dolly.main.time.time")
    @patch("dolly.main.get_table_hashes")
    @patch("dolly.main.clean_up")
    @patch("dolly.summary.get_current_summary")
    @patch("dolly.main.logger")
    def test_main_global_error_recorded_in_summary(
        self,
        mock_logger,
        mock_get_current_summary,
        mock_clean_up,
        mock_get_table_hashes,
        mock_time,
    ):
        from dolly.summary import ProcessSummary

        mock_time.side_effect = [1000.0, 1005.0]
        mock_get_table_hashes.side_effect = ValueError("Invalid configuration")
        test_summary = ProcessSummary()
        mock_get_current_summary.return_value = test_summary

        with pytest.raises(ValueError, match="Invalid configuration"):
            _main_logic()

        assert len(test_summary.global_errors) == 1
        assert "ValueError: Invalid configuration" in test_summary.global_errors[0]

    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_current_hashes")
    @patch("dolly.main.determine_updated_tables")
    @patch("dolly.main.get_table_hashes")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.clean_up")
    @patch("dolly.main.logger")
    def test_main_skips_tables_not_in_lookup(
        self,
        mock_logger,
        mock_clean_up,
        mock_get_gis_connection,
        mock_get_agol_items_lookup,
        mock_get_table_hashes,
        mock_determine_updated,
        mock_get_current_hashes,
        mock_precisedelta,
        mock_time,
    ):
        mock_time.side_effect = [1000.0, 1005.0]
        mock_get_gis_connection.return_value = Mock()
        mock_get_table_hashes.return_value = {}
        mock_get_current_hashes.return_value = {"sgid.unknown.table": "h1"}
        mock_determine_updated.return_value = ["sgid.unknown.table"]
        mock_get_agol_items_lookup.return_value = {}
        mock_precisedelta.return_value = "5 seconds"

        _main_logic()

        mock_logger.info.assert_any_call(
            "skipping sgid.unknown.table since it does not show up in the agol items lookup"
        )

    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_current_hashes")
    @patch("dolly.main.determine_updated_tables")
    @patch("dolly.main.get_table_hashes")
    @patch("dolly.main.publish_new_feature_services")
    @patch("dolly.main.update_feature_services")
    @patch("dolly.main.zip_and_upload_fgdb")
    @patch("dolly.main.create_fgdb")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.clean_up")
    @patch("dolly.main.logger")
    def test_main_cli_tables_parameter(
        self,
        mock_logger,
        mock_clean_up,
        mock_get_gis_connection,
        mock_get_agol_items_lookup,
        mock_create_fgdb,
        mock_zip_and_upload_fgdb,
        mock_update_feature_services,
        mock_publish_new_feature_services,
        mock_get_table_hashes,
        mock_determine_updated,
        mock_get_current_hashes,
        mock_precisedelta,
        mock_time,
    ):
        mock_get_gis_connection.return_value = Mock()
        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup
        mock_create_fgdb.return_value = (
            Path("/test/output/data.gdb"),
            {"sgid.society.cemeteries": 1000},
        )
        mock_zip_and_upload_fgdb.return_value = Mock()
        mock_get_current_hashes.return_value = {
            "sgid.society.cemeteries": "h1",
            "sgid.transportation.roads": "h2",
        }
        mock_time.side_effect = [1000.0, 1020.0]
        mock_precisedelta.return_value = "20 seconds"

        _main_logic(cli_tables="sgid.society.cemeteries,sgid.transportation.roads")

        mock_get_table_hashes.assert_not_called()
        mock_determine_updated.assert_not_called()
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

    @patch("dolly.main.APP_ENVIRONMENT", "dev")
    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.logger")
    def test_cleanup_dev_agol_items_success(
        self,
        mock_logger,
        mock_get_gis_connection,
        mock_get_agol_items_lookup,
        mock_precisedelta,
        mock_time,
    ):
        """Test successful cleanup of dev AGOL items."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1010.0, 1020.0, 1030.0]
        mock_precisedelta.return_value = "10 seconds"

        mock_gis = Mock()
        mock_gis.users.me.username = "test_user"
        mock_get_gis_connection.return_value = mock_gis

        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup

        # Mock search results for item without existing item_id
        mock_item = Mock()
        mock_item.id = "test-item-id"
        mock_item.delete.return_value = True
        mock_gis.content.search.return_value = [mock_item]

        cleanup_dev_agol_items()

        # Verify GIS connection
        mock_get_gis_connection.assert_called_once()

        # Verify search is called for table without item_id
        mock_gis.content.search.assert_called_once_with(
            'title:"Utah Roads (Test)" AND owner:test_user',
            max_items=1,
        )

        # Verify item deletion
        mock_item.delete.assert_called_once_with(permanent=True)

        # Verify logging
        mock_logger.info.assert_any_call(
            "Deleting item test-item-id for table sgid.transportation.roads"
        )
        mock_logger.info.assert_any_call(
            "Dev feature services cleanup completed in 10 seconds"
        )

    @patch("dolly.main.APP_ENVIRONMENT", "dev")
    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.logger")
    def test_cleanup_dev_agol_items_no_search_results(
        self,
        mock_logger,
        mock_get_gis_connection,
        mock_get_agol_items_lookup,
        mock_precisedelta,
        mock_time,
    ):
        """Test cleanup when no search results are found."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1010.0, 1020.0, 1030.0]
        mock_precisedelta.return_value = "10 seconds"

        mock_gis = Mock()
        mock_gis.users.me.username = "test_user"
        mock_get_gis_connection.return_value = mock_gis

        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup

        # Mock empty search results
        mock_gis.content.search.return_value = []

        cleanup_dev_agol_items()

        # Verify warning is logged
        mock_logger.warning.assert_called_once_with(
            "Item with title: Utah Roads (Test) not found, skipping deletion."
        )

    @patch("dolly.main.APP_ENVIRONMENT", "dev")
    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.logger")
    def test_cleanup_dev_agol_items_deletion_failure(
        self,
        mock_logger,
        mock_get_gis_connection,
        mock_get_agol_items_lookup,
        mock_precisedelta,
        mock_time,
    ):
        """Test cleanup when item deletion fails."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1010.0, 1020.0, 1030.0]
        mock_precisedelta.return_value = "10 seconds"

        mock_gis = Mock()
        mock_gis.users.me.username = "test_user"
        mock_get_gis_connection.return_value = mock_gis

        mock_get_agol_items_lookup.return_value = self.mock_agol_items_lookup

        # Mock search results with failed deletion
        mock_item = Mock()
        mock_item.id = "test-item-id"
        mock_item.delete.return_value = False  # Deletion fails
        mock_gis.content.search.return_value = [mock_item]

        with pytest.raises(RuntimeError, match="Failed to delete item None"):
            cleanup_dev_agol_items()

    @patch("dolly.main.APP_ENVIRONMENT", "dev")
    @patch("dolly.main.time.time")
    @patch("dolly.main.humanize.precisedelta")
    @patch("dolly.main.get_agol_items_lookup")
    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.logger")
    def test_cleanup_dev_agol_items_skips_existing_items(
        self,
        mock_logger,
        mock_get_gis_connection,
        mock_get_agol_items_lookup,
        mock_precisedelta,
        mock_time,
    ):
        """Test cleanup skips tables that already have item_ids."""
        # Setup mocks
        mock_time.side_effect = [1000.0, 1010.0, 1020.0, 1030.0]
        mock_precisedelta.return_value = "10 seconds"

        mock_gis = Mock()
        mock_get_gis_connection.return_value = mock_gis

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
