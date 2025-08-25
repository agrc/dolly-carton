"""Tests for hash-based state functions in state.py"""

from unittest.mock import Mock, patch

from dolly.state import get_table_hashes, set_table_hash


class TestGetTableHashes:
    def test_dev_environment_returns_empty_dict(self, monkeypatch):
        monkeypatch.setenv("APP_ENVIRONMENT", "dev")
        result = get_table_hashes()
        assert result == {}

    def test_prod_environment_document_missing_returns_empty(self, monkeypatch):
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = False
        monkeypatch.setenv("APP_ENVIRONMENT", "prod")
        with patch("dolly.state.firestore", mock_firestore):
            result = get_table_hashes()
            assert result == {}

    def test_prod_environment_returns_hashes(self, monkeypatch):
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"sgid.test.table": "abc"}
        monkeypatch.setenv("APP_ENVIRONMENT", "prod")
        with patch("dolly.state.firestore", mock_firestore):
            result = get_table_hashes()
            assert result == {"sgid.test.table": "abc"}


class TestSetTableHash:
    @patch("dolly.state.logger")
    def test_prod_environment_successful_write(self, mock_logger, monkeypatch):
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        monkeypatch.setenv("APP_ENVIRONMENT", "prod")
        with patch("dolly.state.firestore", mock_firestore):
            set_table_hash("SGID.Test.Table", "abc123")
            mock_doc_ref.set.assert_called_once_with(
                {"sgid.test.table": "abc123"}, merge=True
            )
            mock_logger.info.assert_called()


class TestIntegration:
    @patch("dolly.state.logger")
    def test_roundtrip_set_and_get(self, mock_logger, monkeypatch):
        mock_firestore = Mock()
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_doc = Mock()
        mock_firestore.Client.return_value = mock_client
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        # After setting, simulate document containing the hash map
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"sgid.test.table": "h1"}
        monkeypatch.setenv("APP_ENVIRONMENT", "prod")
        with patch("dolly.state.firestore", mock_firestore):
            set_table_hash("SGID.Test.Table", "h1")
            result = get_table_hashes()
            assert result == {"sgid.test.table": "h1"}
