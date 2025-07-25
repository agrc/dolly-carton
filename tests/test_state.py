"""Tests for state.py functions"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

# Test imports
from dolly.state import get_last_checked, set_last_checked


class TestGetLastChecked:
    """Test cases for the get_last_checked function."""

    def test_dev_environment_returns_yesterday(self):
        """Test that dev environment returns approximately yesterday."""
        with patch("dolly.state.APP_ENVIRONMENT", "dev"):
            result = get_last_checked()
            yesterday = datetime.now() - timedelta(days=1)

            # Allow for a small time difference (within 1 minute)
            time_diff = abs((result - yesterday).total_seconds())
            assert time_diff < 60, f"Time difference too large: {time_diff} seconds"

    def test_prod_environment_no_firestore_raises_import_error(self):
        """Test that production environment without Firestore raises ImportError."""
        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", None),
        ):
            with pytest.raises(
                ImportError,
                match="Firestore is required in production but google-cloud-firestore is not available",
            ):
                get_last_checked()

    def test_prod_environment_document_exists_with_timestamp(self):
        """Test that production environment returns timestamp from Firestore when document exists."""
        # Setup mock
        expected_timestamp = datetime(2025, 7, 24, 12, 0, 0)
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()

        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"last_checked": expected_timestamp}

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            result = get_last_checked()

            assert result == expected_timestamp
            mock_client.collection.assert_called_once_with("dolly-carton")
            mock_client.collection.return_value.document.assert_called_once_with(
                "state"
            )
            mock_doc_ref.get.assert_called_once()

    def test_prod_environment_document_not_exists_raises_value_error(self):
        """Test that production environment raises ValueError when document doesn't exist."""
        # Setup mock
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()

        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = False

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            with pytest.raises(
                ValueError, match="No last_checked timestamp found in Firestore"
            ):
                get_last_checked()

    def test_prod_environment_document_exists_no_last_checked_field_raises_value_error(
        self,
    ):
        """Test that production environment raises ValueError when document exists but has no last_checked field."""
        # Setup mock
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()

        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"other_field": "value"}

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            with pytest.raises(
                ValueError, match="No last_checked timestamp found in Firestore"
            ):
                get_last_checked()

    def test_prod_environment_document_exists_null_data_raises_value_error(self):
        """Test that production environment raises ValueError when document exists but returns None data."""
        # Setup mock
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()

        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = None

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            with pytest.raises(
                ValueError, match="No last_checked timestamp found in Firestore"
            ):
                get_last_checked()

    def test_prod_environment_firestore_client_exception_propagates(self):
        """Test that Firestore client exceptions are propagated."""
        # Setup mock to raise exception
        mock_firestore = Mock()
        mock_firestore.Client.side_effect = Exception("Firestore connection failed")

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            with pytest.raises(Exception, match="Firestore connection failed"):
                get_last_checked()


class TestSetLastChecked:
    """Test cases for the set_last_checked function."""

    @patch("dolly.state.logger")
    def test_dev_environment_logs_message(self, mock_logger):
        """Test that dev environment logs the timestamp."""
        test_timestamp = datetime(2025, 7, 25, 14, 30, 0)

        with patch("dolly.state.APP_ENVIRONMENT", "dev"):
            set_last_checked(test_timestamp)

            mock_logger.info.assert_called_once_with(
                f"Dev environment: would set last_checked to {test_timestamp}"
            )

    def test_prod_environment_no_firestore_raises_import_error(self):
        """Test that production environment without Firestore raises ImportError."""
        test_timestamp = datetime(2025, 7, 25, 14, 30, 0)

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", None),
        ):
            with pytest.raises(
                ImportError,
                match="Firestore is required in production but google-cloud-firestore is not available",
            ):
                set_last_checked(test_timestamp)

    @patch("dolly.state.logger")
    def test_prod_environment_successful_write(self, mock_logger):
        """Test that production environment successfully writes to Firestore."""
        # Setup mock
        test_timestamp = datetime(2025, 7, 25, 14, 30, 0)
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()

        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            set_last_checked(test_timestamp)

            # Verify Firestore calls
            mock_client.collection.assert_called_once_with("dolly-carton")
            mock_client.collection.return_value.document.assert_called_once_with(
                "state"
            )
            mock_doc_ref.set.assert_called_once_with(
                {"last_checked": test_timestamp}, merge=True
            )

            # Verify logging
            mock_logger.info.assert_called_once_with(
                f"Updated last_checked in Firestore to {test_timestamp}"
            )

    def test_prod_environment_firestore_exception_propagates(self):
        """Test that Firestore exceptions are propagated."""
        # Setup mock to raise exception
        test_timestamp = datetime(2025, 7, 25, 14, 30, 0)
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()

        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.set.side_effect = Exception("Firestore write failed")

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            with pytest.raises(Exception, match="Firestore write failed"):
                set_last_checked(test_timestamp)

    def test_prod_environment_client_creation_exception_propagates(self):
        """Test that Firestore client creation exceptions are propagated."""
        # Setup mock to raise exception on client creation
        test_timestamp = datetime(2025, 7, 25, 14, 30, 0)
        mock_firestore = Mock()
        mock_firestore.Client.side_effect = Exception(
            "Failed to create Firestore client"
        )

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            with pytest.raises(Exception, match="Failed to create Firestore client"):
                set_last_checked(test_timestamp)

    @patch("dolly.state.logger")
    def test_non_prod_environment_logs_message(self, mock_logger):
        """Test that non-prod environments (other than dev) also log the timestamp."""
        test_timestamp = datetime(2025, 7, 25, 14, 30, 0)

        with patch("dolly.state.APP_ENVIRONMENT", "staging"):
            set_last_checked(test_timestamp)

            mock_logger.info.assert_called_once_with(
                f"Dev environment: would set last_checked to {test_timestamp}"
            )


class TestIntegration:
    """Integration tests for the Firestore functions."""

    @patch("dolly.state.logger")
    def test_roundtrip_get_and_set(self, mock_logger):
        """Test that we can set a timestamp and then retrieve it."""
        # Setup mock for both functions
        test_timestamp = datetime(2025, 7, 25, 14, 30, 0)
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()

        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref

        # Setup for set_last_checked
        mock_doc_ref.set.return_value = None

        # Setup for get_last_checked
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"last_checked": test_timestamp}

        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            # Test the roundtrip
            set_last_checked(test_timestamp)
            result = get_last_checked()

            assert result == test_timestamp

            # Verify both functions called Firestore correctly
            assert mock_client.collection.call_count == 2
            assert mock_doc_ref.set.call_count == 1
            assert mock_doc_ref.get.call_count == 1
