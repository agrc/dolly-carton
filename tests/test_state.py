"""Tests for hash-based state functions in state.py"""

from unittest.mock import Mock, patch

import pytest

from dolly.state import get_table_hashes, set_table_hash


class TestGetTableHashes:
    def test_dev_environment_returns_empty_dict(self):
        with patch("dolly.state.APP_ENVIRONMENT", "dev"):
            result = get_table_hashes()
            assert result == {}

    def test_prod_environment_no_firestore_raises_import_error(self):
        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", None),
        ):
            with pytest.raises(ImportError):
                get_table_hashes()

    def test_prod_environment_document_missing_returns_empty(self):
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
            result = get_table_hashes()
            assert result == {}

    def test_prod_environment_returns_hashes(self):
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"table_hashes": {"SGID.Test.Table": "abc"}}
        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            result = get_table_hashes()
            assert result == {"sgid.test.table": "abc"}


class TestSetTableHash:
    @patch("dolly.state.logger")
    def test_dev_environment_logs_only(self, mock_logger):
        with patch("dolly.state.APP_ENVIRONMENT", "dev"):
            set_table_hash("SGID.Test.Table", "abc123")
            mock_logger.info.assert_called()

    def test_prod_environment_no_firestore_raises_import_error(self):
        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", None),
        ):
            with pytest.raises(ImportError):
                set_table_hash("SGID.Test.Table", "abc123")

    @patch("dolly.state.logger")
    def test_prod_environment_successful_write(self, mock_logger):
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            set_table_hash("SGID.Test.Table", "abc123")
            mock_doc_ref.set.assert_called_once_with(
                {"table_hashes": {"sgid.test.table": "abc123"}}, merge=True
            )
            mock_logger.info.assert_called()


class TestIntegration:
    @patch("dolly.state.logger")
    def test_roundtrip_set_and_get(self, mock_logger):
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        # After setting, simulate document containing the hash map
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"table_hashes": {"sgid.test.table": "h1"}}
        with (
            patch("dolly.state.APP_ENVIRONMENT", "prod"),
            patch("dolly.state.firestore", mock_firestore),
        ):
            set_table_hash("SGID.Test.Table", "h1")
            result = get_table_hashes()
            assert result == {"sgid.test.table": "h1"}
