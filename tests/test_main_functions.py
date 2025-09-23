"""Test cases for main.py functions and cleanup logic."""

from unittest.mock import Mock, patch

from dolly.main import _main_logic, clean_up


class TestMainFunctions:
    """Test main functions and cleanup logic."""

    @patch("dolly.main.OUTPUT_PATH")
    @patch("dolly.main.logger")
    def test_clean_up_with_files_and_subdirs(self, mock_logger, mock_output_path):
        """Test cleanup function with files and subdirectories."""
        # Mock directory structure
        mock_output_path.exists.return_value = True

        # Create mock files and directories
        mock_file1 = Mock()
        mock_file1.is_dir.return_value = False
        mock_file1.is_file.return_value = True
        mock_file1.name = "test.txt"

        mock_gitkeep = Mock()
        mock_gitkeep.is_dir.return_value = False
        mock_gitkeep.is_file.return_value = True
        mock_gitkeep.name = ".gitkeep"

        mock_subdir = Mock()
        mock_subdir.is_dir.return_value = True
        mock_subdir.is_file.return_value = False

        # Mock subdirectory contents
        mock_subfile = Mock()
        mock_subfile.is_file.return_value = True
        mock_subdir.rglob.return_value = [mock_subfile]

        mock_output_path.iterdir.return_value = [mock_file1, mock_gitkeep, mock_subdir]

        clean_up()

        # Verify files were processed
        mock_file1.unlink.assert_called_once()
        mock_gitkeep.unlink.assert_not_called()  # Should skip .gitkeep
        mock_subfile.unlink.assert_called_once()
        mock_subdir.rmdir.assert_called_once()
        mock_logger.info.assert_called_with("Cleaned up temporary files.")

    @patch("dolly.main.OUTPUT_PATH")
    @patch("dolly.main.logger")
    def test_clean_up_nonexistent_directory(self, mock_logger, mock_output_path):
        """Test cleanup when output directory doesn't exist."""
        mock_output_path.exists.return_value = False

        clean_up()

        # Should not try to iterate if directory doesn't exist
        mock_output_path.iterdir.assert_not_called()
        mock_logger.info.assert_called_with("Cleaned up temporary files.")

    @patch("dolly.main.OUTPUT_PATH")
    @patch("dolly.main.logger")
    def test_clean_up_empty_directory(self, mock_logger, mock_output_path):
        """Test cleanup with empty directory."""
        mock_output_path.exists.return_value = True
        mock_output_path.iterdir.return_value = []  # Empty directory

        clean_up()

        mock_logger.info.assert_called_with("Cleaned up temporary files.")

    @patch("dolly.main._main_logic")
    def test_main_calls_main_logic(self, mock_main_logic):
        """Test that main() properly calls _main_logic()."""
        from dolly.main import main

        main("test_tables")

        mock_main_logic.assert_called_once_with("test_tables")

    @patch("dolly.main.start_summary")
    @patch("dolly.main.clean_up")
    @patch("dolly.main.get_current_hashes")
    @patch("dolly.main.get_table_hashes")
    @patch("dolly.main.determine_updated_tables")
    @patch("dolly.main.time.time")
    @patch("dolly.main.logger")
    def test_main_logic_no_updated_tables(
        self,
        mock_logger,
        mock_time,
        mock_determine_updated,
        mock_get_table_hashes,
        mock_get_current_hashes,
        mock_clean_up,
        mock_start_summary,
    ):
        """Test _main_logic when no tables need updating."""
        mock_time.return_value = 1000.0
        mock_get_current_hashes.return_value = {"sgid.test.table": "hash1"}
        mock_get_table_hashes.return_value = {"sgid.test.table": "hash1"}
        mock_determine_updated.return_value = []  # No updated tables

        _main_logic()

        mock_clean_up.assert_called_once()
        mock_determine_updated.assert_called_once()
        mock_logger.info.assert_any_call("No updated tables found.")

    @patch("dolly.main.get_gis_connection")
    @patch("dolly.main.start_summary")
    @patch("dolly.main.clean_up")
    @patch("dolly.main.get_current_hashes")
    @patch("dolly.main.time.time")
    @patch("dolly.main.logger")
    def test_main_logic_with_cli_tables_string(
        self,
        mock_logger,
        mock_time,
        mock_get_current_hashes,
        mock_clean_up,
        mock_start_summary,
        mock_get_gis_connection,
    ):
        """Test _main_logic with CLI-provided tables as comma-separated string."""
        mock_time.return_value = 1000.0
        mock_get_current_hashes.return_value = {
            "sgid.test.table1": "hash1",
            "sgid.test.table2": "hash2",
        }

        # Mock the rest of the process to return early and avoid complex execution
        with patch("dolly.main.get_agol_items_lookup") as mock_get_agol:
            # Return empty lookup to trigger early return
            mock_get_agol.return_value = {}

            # Test with CLI tables - should not call determine_updated_tables
            with patch("dolly.main.determine_updated_tables") as mock_determine:
                # Test the parsing of CLI tables parameter
                _main_logic("sgid.test.table1, sgid.test.table2")

                # Should not call determine_updated_tables when CLI tables provided
                mock_determine.assert_not_called()
                mock_logger.info.assert_any_call(
                    "Using CLI-provided tables: ['sgid.test.table1', 'sgid.test.table2']"
                )
