"""Test cases for feature counting functions and error handling."""

from pathlib import Path
from unittest.mock import Mock, patch

from dolly.internal import (
    _count_features_in_internal_table,
    _count_features_in_fgdb_layer,
)


class TestFeatureCountingErrorPaths:
    """Test error handling in feature counting functions."""

    @patch("dolly.internal._get_database_connection")
    def test_count_internal_table_invalid_format(self, mock_get_connection):
        """Test counting features with invalid table name format."""
        mock_connection = Mock()
        mock_get_connection.return_value = mock_connection

        # Test invalid table name format
        result = _count_features_in_internal_table("invalid_table_name")

        assert result == -1
        mock_connection.close.assert_called_once()

    @patch("dolly.internal._get_database_connection")
    def test_count_internal_table_database_error(self, mock_get_connection):
        """Test counting features with database error."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        # Simulate database error
        mock_cursor.execute.side_effect = Exception("Database connection failed")

        result = _count_features_in_internal_table("sgid.test.table")

        assert result == -1
        mock_connection.close.assert_called_once()

    @patch("dolly.internal.gdal.OpenEx")
    def test_count_fgdb_layer_open_failure(self, mock_open):
        """Test counting FGDB features when GDAL can't open the file."""
        mock_open.side_effect = Exception(
            "GDAL open failure"
        )  # GDAL raises exception on failure

        result = _count_features_in_fgdb_layer(
            Path("/nonexistent/path.gdb"), "test_layer"
        )

        assert result == -1
        mock_open.assert_called_once()

    @patch("dolly.internal.gdal.OpenEx")
    def test_count_fgdb_layer_not_found(self, mock_open):
        """Test counting FGDB features when layer is not found."""
        mock_dataset = Mock()
        mock_open.return_value = mock_dataset
        mock_dataset.GetLayerByName.side_effect = Exception(
            "Layer not found"
        )  # Simulate GDAL exception

        result = _count_features_in_fgdb_layer(
            Path("/test/path.gdb"), "nonexistent_layer"
        )

        assert result == -1
        mock_open.assert_called_once()

    @patch("dolly.internal.gdal.OpenEx")
    def test_count_fgdb_layer_exception(self, mock_open):
        """Test counting FGDB features with exception during processing."""
        mock_open.side_effect = Exception("GDAL processing error")

        result = _count_features_in_fgdb_layer(Path("/test/path.gdb"), "test_layer")

        assert result == -1

    @patch("dolly.internal._get_database_connection")
    def test_count_internal_table_provided_connection(self, mock_get_connection):
        """Test counting with provided connection."""
        provided_connection = Mock()
        mock_cursor = Mock()
        provided_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [100]

        result = _count_features_in_internal_table(
            "sgid.test.table", provided_connection
        )

        assert result == 100
        # Should not call _get_database_connection when connection is provided
        mock_get_connection.assert_not_called()
        provided_connection.close.assert_called_once()

    @patch("dolly.internal.gdal.OpenEx")
    def test_count_fgdb_layer_success_cleanup(self, mock_open):
        """Test successful FGDB counting with proper cleanup."""
        mock_dataset = Mock()
        mock_layer = Mock()
        mock_open.return_value = mock_dataset
        mock_dataset.GetLayerByName.return_value = mock_layer
        mock_layer.GetFeatureCount.return_value = 250

        result = _count_features_in_fgdb_layer(Path("/test/path.gdb"), "test_layer")

        assert result == 250
        mock_open.assert_called_once()
        mock_dataset.GetLayerByName.assert_called_once_with("test_layer")
        mock_layer.GetFeatureCount.assert_called_once()
