"""Tests for the summary module."""

import json
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

from dolly.summary import (
    ProcessSummary,
    finish_summary,
    get_current_summary,
    start_summary,
)


class TestProcessSummary:
    """Test cases for the ProcessSummary class."""

    def test_init_default_values(self):
        """Test that ProcessSummary initializes with correct default values."""
        summary = ProcessSummary()

        assert summary.tables_updated == []
        assert summary.tables_published == []
        assert summary.tables_with_errors == []
        assert summary.updated_item_ids == []
        assert summary.published_item_ids == []
        assert summary.update_errors == []
        assert summary.publish_errors == []
        assert summary.global_errors == []
        assert summary.start_time == 0.0
        assert summary.end_time == 0.0

    def test_add_table_updated(self):
        """Test adding updated tables."""
        summary = ProcessSummary()

        summary.add_table_updated("sgid.test.table1", None)
        summary.add_table_updated("sgid.test.table2", None)

        assert summary.tables_updated == ["sgid.test.table1", "sgid.test.table2"]

        # Test that duplicates are not added
        summary.add_table_updated("sgid.test.table1", None)
        assert summary.tables_updated == ["sgid.test.table1", "sgid.test.table2"]

    def test_add_table_published(self):
        """Test adding published tables."""
        summary = ProcessSummary()

        summary.add_table_published("sgid.test.table1", None)
        summary.add_table_published("sgid.test.table2", None)

        assert summary.tables_published == ["sgid.test.table1", "sgid.test.table2"]

        # Test that duplicates are not added
        summary.add_table_published("sgid.test.table1", None)
        assert summary.tables_published == ["sgid.test.table1", "sgid.test.table2"]

    def test_add_table_error(self):
        """Test adding table errors."""
        summary = ProcessSummary()

        summary.add_table_error("sgid.test.table1", "update", "Connection failed")
        summary.add_table_error("sgid.test.table2", "publish", "Permission denied")

        assert summary.tables_with_errors == ["sgid.test.table1", "sgid.test.table2"]
        assert summary.update_errors == ["sgid.test.table1: Connection failed"]
        assert summary.publish_errors == ["sgid.test.table2: Permission denied"]

        # Test that duplicate table names are not added to tables_with_errors
        summary.add_table_error("sgid.test.table1", "publish", "Another error")
        assert summary.tables_with_errors == ["sgid.test.table1", "sgid.test.table2"]
        assert summary.publish_errors == [
            "sgid.test.table2: Permission denied",
            "sgid.test.table1: Another error",
        ]

    def test_add_global_error(self):
        """Test adding global errors."""
        summary = ProcessSummary()

        summary.add_global_error("ValueError: Invalid configuration")
        summary.add_global_error("ConnectionError: Database unavailable")

        assert summary.global_errors == [
            "ValueError: Invalid configuration",
            "ConnectionError: Database unavailable",
        ]

    def test_add_table_updated_with_item_id(self):
        """Test adding updated tables with AGOL item IDs."""
        summary = ProcessSummary()

        summary.add_table_updated(
            "sgid.test.table1", "583c0f4888d44f0a90791282b2a69829"
        )
        summary.add_table_updated("sgid.test.table2", None)  # No item_id
        summary.add_table_updated(
            "sgid.test.table3", "abcd1234567890123456789012345678"
        )

        assert summary.tables_updated == [
            "sgid.test.table1",
            "sgid.test.table2",
            "sgid.test.table3",
        ]
        assert summary.updated_item_ids == [
            "583c0f4888d44f0a90791282b2a69829",
            None,
            "abcd1234567890123456789012345678",
        ]

        # Test that duplicates are not added
        summary.add_table_updated("sgid.test.table1", "different_id")
        assert len(summary.tables_updated) == 3
        assert len(summary.updated_item_ids) == 3

    def test_add_table_published_with_item_id(self):
        """Test adding published tables with AGOL item IDs."""
        summary = ProcessSummary()

        summary.add_table_published(
            "sgid.test.table1", "583c0f4888d44f0a90791282b2a69829"
        )
        summary.add_table_published("sgid.test.table2", None)  # No item_id
        summary.add_table_published(
            "sgid.test.table3", "abcd1234567890123456789012345678"
        )

        assert summary.tables_published == [
            "sgid.test.table1",
            "sgid.test.table2",
            "sgid.test.table3",
        ]
        assert summary.published_item_ids == [
            "583c0f4888d44f0a90791282b2a69829",
            None,
            "abcd1234567890123456789012345678",
        ]

        # Test that duplicates are not added
        summary.add_table_published("sgid.test.table1", "different_id")
        assert len(summary.tables_published) == 3
        assert len(summary.published_item_ids) == 3

    def test_add_feature_count_mismatch(self):
        """Test adding feature count mismatches."""
        summary = ProcessSummary()

        summary.add_feature_count_mismatch("sgid.test.table1", 1000, 999)
        summary.add_feature_count_mismatch("sgid.test.table2", 500, 501)

        # Feature count mismatches should be added as table errors
        assert "sgid.test.table1" in summary.tables_with_errors
        assert "sgid.test.table2" in summary.tables_with_errors
        assert any(
            "Feature count mismatch - source (internal): 1000 -> destination (AGOL): 999"
            in error
            for error in summary.update_errors
        )
        assert any(
            "Feature count mismatch - source (internal): 500 -> destination (AGOL): 501"
            in error
            for error in summary.update_errors
        )

    def test_get_total_elapsed_time(self):
        """Test elapsed time calculation."""
        summary = ProcessSummary()
        summary.start_time = 1000.0
        summary.end_time = 1010.5

        elapsed = summary.get_total_elapsed_time()
        assert elapsed == timedelta(seconds=10.5)

        # Test with no end time
        summary.end_time = 0.0
        elapsed = summary.get_total_elapsed_time()
        assert elapsed == timedelta(seconds=0.0)

    @patch("dolly.summary.logger")
    def test_log_summary_success_case(self, mock_logger):
        """Test log_summary for successful case."""
        summary = ProcessSummary()
        summary.start_time = 1000.0
        summary.end_time = 1015.0
        summary.add_table_updated("sgid.test.table1", None)
        summary.add_table_published("sgid.test.table2", None)

        summary.log_summary()

        # Check that info was called with expected messages
        mock_logger.info.assert_any_call("=" * 80)
        mock_logger.info.assert_any_call("DOLLY CARTON PROCESS SUMMARY")
        mock_logger.info.assert_any_call("📊 Total tables processed: 2")
        mock_logger.info.assert_any_call("✅ Tables updated: 1")
        mock_logger.info.assert_any_call("   • sgid.test.table1")
        mock_logger.info.assert_any_call("🚀 Tables published: 1")
        mock_logger.info.assert_any_call("   • sgid.test.table2")
        mock_logger.info.assert_any_call("⏱️  Total elapsed time: 15 seconds")
        mock_logger.info.assert_any_call("🟢 Process completed successfully")

    @patch("dolly.summary.logger")
    def test_log_summary_with_errors(self, mock_logger):
        """Test log_summary with errors."""
        summary = ProcessSummary()
        summary.start_time = 1000.0
        summary.end_time = 1010.0
        summary.add_table_error("sgid.test.table1", "update", "Connection failed")
        summary.add_table_error("sgid.test.table2", "publish", "Permission denied")

        summary.log_summary()

        mock_logger.info.assert_any_call("❌ Tables with errors: 2")
        mock_logger.info.assert_any_call("   • sgid.test.table1")
        mock_logger.info.assert_any_call("   • sgid.test.table2")
        mock_logger.info.assert_any_call("📝 Update errors:")
        mock_logger.info.assert_any_call("   • sgid.test.table1: Connection failed")
        mock_logger.info.assert_any_call("📝 Publish errors:")
        mock_logger.info.assert_any_call("   • sgid.test.table2: Permission denied")
        mock_logger.info.assert_any_call("🟡 Process completed with errors")

    @patch("dolly.summary.logger")
    def test_log_summary_no_tables(self, mock_logger):
        """Test log_summary with no tables processed."""
        summary = ProcessSummary()
        summary.start_time = 1000.0
        summary.end_time = 1005.0

        summary.log_summary()

        mock_logger.info.assert_any_call("📊 Total tables processed: 0")
        mock_logger.info.assert_any_call("✅ Tables updated: 0")
        mock_logger.info.assert_any_call("🚀 Tables published: 0")
        mock_logger.info.assert_any_call("🔵 No tables required processing")

    @patch("dolly.summary.logger")
    def test_log_summary_with_global_errors(self, mock_logger):
        """Test log_summary with global errors."""
        summary = ProcessSummary()
        summary.start_time = 1000.0
        summary.end_time = 1010.0
        summary.add_global_error("ValueError: Invalid configuration")
        summary.add_global_error("ConnectionError: Database unavailable")

        summary.log_summary()

        mock_logger.info.assert_any_call("🚨 Global errors: 2")
        mock_logger.info.assert_any_call("   • ValueError: Invalid configuration")
        mock_logger.info.assert_any_call("   • ConnectionError: Database unavailable")
        mock_logger.info.assert_any_call("🔴 Process failed due to global errors")

    @patch("dolly.summary.logger")
    def test_log_summary_with_both_table_and_global_errors(self, mock_logger):
        """Test log_summary with both table and global errors."""
        summary = ProcessSummary()
        summary.start_time = 1000.0
        summary.end_time = 1010.0
        summary.add_table_error("sgid.test.table1", "update", "Connection failed")
        summary.add_global_error("ValueError: Invalid configuration")

        summary.log_summary()

        # Should show both types of errors
        mock_logger.info.assert_any_call("❌ Tables with errors: 1")
        mock_logger.info.assert_any_call("🚨 Global errors: 1")
        # Global errors take precedence in overall status
        mock_logger.info.assert_any_call("🔴 Process failed due to global errors")

    @patch("dolly.summary.logger")
    def test_log_summary_with_feature_count_mismatches(self, mock_logger):
        """Test log_summary with feature count mismatches."""
        summary = ProcessSummary()
        summary.add_table_updated("sgid.test.table1", None)
        summary.add_feature_count_mismatch("sgid.test.table1", 1000, 999)

        summary.log_summary()

        # Feature count mismatches should appear in update errors
        mock_logger.info.assert_any_call("📝 Update errors:")
        mock_logger.info.assert_any_call(
            "   • sgid.test.table1: Feature count mismatch - source (internal): 1000 -> destination (AGOL): 999"
        )
        # Feature count mismatches should result in error status
        mock_logger.info.assert_any_call("🟡 Process completed with errors")


class TestSummaryGlobalFunctions:
    """Test cases for global summary functions."""

    def test_start_and_get_current_summary(self):
        """Test starting and getting current summary."""
        start_time = time.time()

        summary = start_summary(start_time)

        assert summary.start_time == start_time

        # Test getting current summary
        current = get_current_summary()
        assert current is summary

    @patch("dolly.summary.logger")
    def test_finish_summary(self, mock_logger):
        """Test finishing summary."""
        start_time = time.time()
        end_time = start_time + 10

        # Start a summary
        summary = start_summary(start_time)
        summary.add_table_updated("sgid.test.table1", None)

        # Finish it
        finish_summary(end_time)

        # Check that end time was set and log_summary was called
        assert summary.end_time == end_time
        mock_logger.info.assert_called()

    def test_get_current_summary_none(self):
        """Test getting current summary when none exists."""
        # Reset global state
        import dolly.summary

        dolly.summary._current_summary = None

        current = get_current_summary()
        assert current is None


class TestSlackIntegration:
    """Test cases for Slack integration functionality."""

    def test_build_slack_messages_success(self):
        """Test building a successful process summary as Slack messages."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_updated("sgid.test.table1", None)
        summary.add_table_published("sgid.test.table1", None)

        messages = summary.build_slack_messages()

        assert len(messages) == 1
        payload = json.loads(messages[0].json())
        payload_str = json.dumps(payload, ensure_ascii=False)

        assert "🟢 *Status:* Process completed successfully" in payload_str
        assert "sgid.test.table1" in payload_str
        assert "Global errors: *0*" in payload_str

    def test_build_slack_messages_with_errors(self):
        """Test building a process summary with errors as Slack messages."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_error("sgid.test.table1", "update", "Connection failed")

        payload = json.loads(summary.build_slack_messages()[0].json())
        payload_str = json.dumps(payload, ensure_ascii=False)

        assert "🟡 *Status:* Process completed with errors" in payload_str
        assert "sgid.test.table1" in payload_str
        assert "Global errors: *0*" in payload_str

    def test_build_slack_messages_no_tables(self):
        """Test building a summary with no tables processed."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        payload = json.loads(summary.build_slack_messages()[0].json())
        payload_str = json.dumps(payload, ensure_ascii=False)

        assert (
            "🔵 *Status:* Process completed - no tables required processing"
            in payload_str
        )
        assert "Global errors: *0*" in payload_str

    def test_build_slack_messages_with_global_errors(self):
        """Test building a process summary with global errors as Slack messages."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_global_error("ValueError: Invalid configuration")
        summary.add_global_error("ConnectionError: Database unavailable")

        payload = json.loads(summary.build_slack_messages()[0].json())
        payload_str = json.dumps(payload, ensure_ascii=False)

        assert "🔴 *Status:* Process failed due to global errors" in payload_str
        assert "Global errors: *2*" in payload_str
        assert "🚨 *Global Errors (Process Failed):*" in payload_str
        assert "ValueError: Invalid configuration" in payload_str
        assert "ConnectionError: Database unavailable" in payload_str

    def test_build_slack_messages_with_feature_count_mismatches(self):
        """Test building Slack messages with feature count mismatches."""
        summary = ProcessSummary()
        summary.add_table_updated("sgid.test.table1", None)
        summary.add_feature_count_mismatch("sgid.test.table1", 1000, 999)
        summary.add_feature_count_mismatch("sgid.test.table2", 500, 501)

        payload = json.loads(summary.build_slack_messages()[0].json())
        payload_str = json.dumps(payload, ensure_ascii=False)

        assert "🟡" in payload_str
        assert "completed with errors" in payload_str
        assert "*🔧 Update Error Details:*" in payload_str
        assert (
            "Feature count mismatch - source (internal): 1000 -> destination (AGOL): 999"
            in payload_str
        )
        assert (
            "Feature count mismatch - source (internal): 500 -> destination (AGOL): 501"
            in payload_str
        )
        assert "📊 *Feature Count Mismatches:*" not in payload_str

    def test_build_slack_messages_with_many_updated_tables(self):
        """Test building Slack messages with a long list of updated tables."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        for index in range(30):
            table_name = f"sgid.test.table{index}"
            item_id = f"{index:02d}" * 16
            summary.add_table_updated(table_name, item_id)

        payload = json.loads(summary.build_slack_messages()[0].json())
        payload_str = json.dumps(payload, ensure_ascii=False)

        assert "✅ *Updated Tables*" in payload_str
        assert "Updated: *30*" in payload_str
        for index in range(30):
            assert f"sgid.test.table{index}" in payload_str

    @patch("dolly.summary.get_secrets")
    def test_finish_summary_with_slack(self, mock_get_secrets):
        """Test finish_summary posts to Slack when webhook URL is available."""
        # Start a summary so we have a current one
        start_time = time.time()
        start_summary(start_time)

        with patch("dolly.summary.SlackHandler.send_message") as mock_send:
            mock_get_secrets.return_value = {
                "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"
            }

            finish_summary(start_time + 10)

            mock_send.assert_called_once()

    @patch("dolly.summary.get_secrets")
    def test_finish_summary_no_slack_webhook(self, mock_get_secrets):
        """Test finish_summary when no Slack webhook URL is configured."""
        # Start a summary so we have a current one
        start_time = time.time()
        start_summary(start_time)

        with patch("dolly.summary.SlackHandler.send_message") as mock_send:
            mock_get_secrets.return_value = {}

            finish_summary(start_time + 10)

            mock_send.assert_not_called()

    def test_build_slack_messages_with_agol_links(self):
        """Test building Slack message with AGOL item links."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_updated(
            "sgid.test.table1", "583c0f4888d44f0a90791282b2a69829"
        )
        summary.add_table_updated("sgid.test.table2", None)  # No item_id
        summary.add_table_published(
            "sgid.test.table3", "abcd1234567890123456789012345678"
        )

        payload = json.loads(summary.build_slack_messages()[0].json())
        payload_str = json.dumps(payload, ensure_ascii=False)

        # Check that links are created for tables with item_ids
        assert (
            "https://utah.maps.arcgis.com/home/item.html?id=583c0f4888d44f0a90791282b2a69829"
            in payload_str
        )
        assert (
            "https://utah.maps.arcgis.com/home/item.html?id=abcd1234567890123456789012345678"
            in payload_str
        )

        # Check that the link format is correct
        assert (
            "<https://utah.maps.arcgis.com/home/item.html?id=583c0f4888d44f0a90791282b2a69829|`sgid.test.table1`>"
            in payload_str
        )
        assert (
            "<https://utah.maps.arcgis.com/home/item.html?id=abcd1234567890123456789012345678|`sgid.test.table3`>"
            in payload_str
        )

        # Check that tables without item_ids still appear as plain text
        assert "`sgid.test.table2`" in payload_str

        # Ensure the message structure is still correct
        assert "🟢 *Status:* Process completed successfully" in payload_str
        assert "✅ *Updated Tables*" in payload_str
        assert "🚀 *Published Tables*" in payload_str

    def test_build_slack_messages_with_long_table_list(self):
        """Test building a message with many tables that exceed Slack block limits."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        # Add many tables to trigger block splitting
        for i in range(100):
            long_table_name = f"sgid.very_long_schema_name.very_long_table_name_that_makes_text_exceed_limits_{i:03d}"
            summary.add_table_updated(long_table_name, None)

        message = summary.build_slack_messages()[0]
        payload = json.loads(message.json())
        payload_str = json.dumps(payload, ensure_ascii=False)

        # Should have many blocks with all tables included
        assert len(payload["blocks"]) > 100
        # Verify all tables are present in the message
        for i in range(100):
            long_table_name = f"sgid.very_long_schema_name.very_long_table_name_that_makes_text_exceed_limits_{i:03d}"
            assert long_table_name in payload_str

    def test_build_slack_messages_with_gcp_environment(self):
        """Test building a message when running in GCP environment."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_updated("sgid.test.table1", None)

        # Mock the GCP metadata request to simulate running in GCP
        with patch("dolly.summary.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = "test-project"
            mock_get.return_value = mock_response

            message = summary.build_slack_messages()[0]
            message_str = message.json()

            # Should contain GCP logs link
            assert "GCP Logs" in message_str
            # Find URLs in the message, and check for proper console.cloud.google.com hostname
            import re
            from urllib.parse import urlparse

            urls = re.findall(r"https?://[^\s\]>]+", message_str)
            assert any(urlparse(u).hostname == "console.cloud.google.com" for u in urls)

    def test_build_slack_messages_with_publish_errors(self):
        """Test build_slack_messages includes publish errors section."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        summary.add_table_error("sgid.test.table1", "publish", "Authentication failed")
        summary.add_table_error("sgid.test.table2", "publish", "Invalid geometry")

        payload = json.loads(summary.build_slack_messages()[0].json())
        payload_str = json.dumps(payload, ensure_ascii=False)
        assert "📤 Publish Error Details" in payload_str
        assert "Authentication failed" in payload_str
        assert "Invalid geometry" in payload_str

    @patch("dolly.summary.logger")
    def test_finish_summary_logs_no_slack_webhook(self, mock_logger):
        """Test that finish_summary logs when no Slack webhook URL is provided."""
        with patch("dolly.summary.get_secrets") as mock_get_secrets:
            # Mock secrets with empty/None Slack webhook
            mock_get_secrets.return_value = {"SLACK_WEBHOOK_URL": None}

            # Start a summary
            start_time = time.time()
            start_summary(start_time)

            # Call finish_summary which should log the no webhook message
            finish_summary(start_time + 10)

            # Verify the logger.info was called with the expected message
            # Check for any call that contains our expected message
            expected_message = (
                "No Slack webhook URL configured, skipping Slack notification"
            )
            info_calls = [
                call
                for call in mock_logger.info.call_args_list
                if call[0][0] == expected_message
            ]
            assert len(info_calls) > 0, (
                f"Expected message not found in logger.info calls: {mock_logger.info.call_args_list}"
            )
