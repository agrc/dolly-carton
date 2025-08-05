"""Tests for the summary module."""

import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests

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
        assert summary.update_errors == []
        assert summary.publish_errors == []
        assert summary.start_time == 0.0
        assert summary.end_time == 0.0
        assert not summary.cli_tables_provided
        assert not summary.change_detection_used

    def test_add_table_updated(self):
        """Test adding updated tables."""
        summary = ProcessSummary()

        summary.add_table_updated("sgid.test.table1")
        summary.add_table_updated("sgid.test.table2")

        assert summary.tables_updated == ["sgid.test.table1", "sgid.test.table2"]

        # Test that duplicates are not added
        summary.add_table_updated("sgid.test.table1")
        assert summary.tables_updated == ["sgid.test.table1", "sgid.test.table2"]

    def test_add_table_published(self):
        """Test adding published tables."""
        summary = ProcessSummary()

        summary.add_table_published("sgid.test.table1")
        summary.add_table_published("sgid.test.table2")

        assert summary.tables_published == ["sgid.test.table1", "sgid.test.table2"]

        # Test that duplicates are not added
        summary.add_table_published("sgid.test.table1")
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
        summary.cli_tables_provided = True
        summary.add_table_updated("sgid.test.table1")
        summary.add_table_published("sgid.test.table2")

        summary.log_summary()

        # Check that info was called with expected messages
        mock_logger.info.assert_any_call("=" * 80)
        mock_logger.info.assert_any_call("DOLLY CARTON PROCESS SUMMARY")
        mock_logger.info.assert_any_call("📋 Mode: CLI-provided tables")
        mock_logger.info.assert_any_call("📊 Total tables processed: 2")
        mock_logger.info.assert_any_call("✅ Tables updated: 1")
        mock_logger.info.assert_any_call("   • sgid.test.table1")
        mock_logger.info.assert_any_call("🚀 Tables published: 1")
        mock_logger.info.assert_any_call("   • sgid.test.table2")
        mock_logger.info.assert_any_call("❌ Tables with errors: 0")
        mock_logger.info.assert_any_call("⏱️  Total elapsed time: 15 seconds")
        mock_logger.info.assert_any_call("🟢 Process completed successfully")

    @patch("dolly.summary.logger")
    def test_log_summary_with_errors(self, mock_logger):
        """Test log_summary with errors."""
        summary = ProcessSummary()
        summary.start_time = 1000.0
        summary.end_time = 1010.0
        summary.change_detection_used = True
        summary.add_table_error("sgid.test.table1", "update", "Connection failed")
        summary.add_table_error("sgid.test.table2", "publish", "Permission denied")

        summary.log_summary()

        mock_logger.info.assert_any_call("🔍 Mode: Automatic change detection")
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
        mock_logger.info.assert_any_call("❌ Tables with errors: 0")
        mock_logger.info.assert_any_call("🔵 No tables required processing")


class TestSummaryGlobalFunctions:
    """Test cases for global summary functions."""

    def test_start_and_get_current_summary(self):
        """Test starting and getting current summary."""
        start_time = time.time()

        summary = start_summary(start_time, cli_tables_provided=True)

        assert summary.start_time == start_time
        assert summary.cli_tables_provided
        assert not summary.change_detection_used

        # Test getting current summary
        current = get_current_summary()
        assert current is summary

    def test_start_summary_change_detection(self):
        """Test starting summary for change detection mode."""
        start_time = time.time()

        summary = start_summary(start_time, cli_tables_provided=False)

        assert not summary.cli_tables_provided
        assert summary.change_detection_used

    @patch("dolly.summary.get_secrets")
    @patch("dolly.summary.logger")
    def test_finish_summary(self, mock_logger, mock_get_secrets):
        """Test finishing summary."""
        start_time = time.time()
        end_time = start_time + 10

        # Mock secrets to prevent Slack posting
        mock_get_secrets.return_value = {}

        # Start a summary
        summary = start_summary(start_time)
        summary.add_table_updated("sgid.test.table1")

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


@patch("dolly.summary.requests.post")
class TestSlackIntegration:
    """Test cases for Slack integration functionality."""

    def test_format_slack_message_success(self, mock_post):
        """Test formatting a successful process summary as Slack message."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_updated("sgid.test.table1")
        summary.add_table_published("sgid.test.table1")

        message = summary.format_slack_message()

        assert "blocks" in message
        assert (
            len(message["blocks"]) >= 5
        )  # Header, status, context, metrics, divider + tables

        # Check that the message contains key elements
        message_text = str(message)
        assert "🟢" in message_text  # Success emoji
        assert "Process completed successfully" in message_text
        assert "sgid.test.table1" in message_text

    def test_format_slack_message_with_errors(self, mock_post):
        """Test formatting a process summary with errors as Slack message."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_error("sgid.test.table1", "update", "Connection failed")

        message = summary.format_slack_message()

        assert "blocks" in message
        blocks = message["blocks"]
        assert (
            len(blocks) >= 5
        )  # Header, status, context, metrics, divider + error sections

        # Check that the message contains key elements
        message_text = str(message)
        assert "🟡" in message_text  # Warning emoji
        assert "Process completed with errors" in message_text
        assert "sgid.test.table1" in message_text
        assert "Connection failed" in message_text

    def test_format_slack_message_no_tables(self, mock_post):
        """Test formatting a summary with no tables processed."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        message = summary.format_slack_message()

        assert "blocks" in message
        blocks = message["blocks"]
        assert (
            len(blocks) >= 4
        )  # Header, status, context, metrics (no divider since no tables)

        # Check that the message contains key elements
        message_text = str(message)
        assert "🔵" in message_text  # Blue emoji
        assert "Process completed - no tables required processing" in message_text

    def test_post_to_slack_success(self, mock_post):
        """Test successful posting to Slack."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        summary = ProcessSummary()
        result = summary.post_to_slack("https://hooks.slack.com/test")

        assert result is True
        mock_post.assert_called_once()

    def test_post_to_slack_failure(self, mock_post):
        """Test failed posting to Slack."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        summary = ProcessSummary()
        result = summary.post_to_slack("https://hooks.slack.com/test")

        assert result is False

    def test_post_to_slack_request_exception(self, mock_post):
        """Test Slack posting with request exception."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        summary = ProcessSummary()
        result = summary.post_to_slack("https://hooks.slack.com/test")

        assert result is False

    @patch("dolly.summary.get_secrets")
    def test_finish_summary_with_slack(self, mock_get_secrets, mock_post):
        """Test finish_summary posts to Slack when webhook URL is available."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Start a summary so we have a current one
        start_time = time.time()
        summary = start_summary(start_time)

        # Mock secrets with Slack webhook
        mock_get_secrets.return_value = {
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"
        }

        finish_summary(start_time + 10)

        # Verify that requests.post was called (meaning Slack posting was attempted)
        mock_post.assert_called_once()

    @patch("dolly.summary.get_secrets")
    def test_finish_summary_no_slack_webhook(self, mock_get_secrets, mock_post):
        """Test finish_summary when no Slack webhook URL is configured."""
        # Start a summary so we have a current one
        start_time = time.time()
        summary = start_summary(start_time)

        # Mock secrets without Slack webhook
        mock_get_secrets.return_value = {}

        finish_summary(start_time + 10)

        # Verify that requests.post was NOT called (no Slack posting attempted)
        mock_post.assert_not_called()
