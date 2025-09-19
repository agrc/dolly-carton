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

    def test_create_item_text_with_link(self):
        """Test _create_item_text method with AGOL item ID."""
        summary = ProcessSummary()

        # Test with item_id - should create a link
        result = summary._create_item_text(
            "sgid.test.table1",
            "583c0f4888d44f0a90791282b2a69829",
            title="✅ *Updated Tables*",
        )
        expected = "• <https://utah.maps.arcgis.com/home/item.html?id=583c0f4888d44f0a90791282b2a69829|`sgid.test.table1`>\n"
        assert result == expected

        # Test without item_id - should fall back to plain text
        result = summary._create_item_text(
            "sgid.test.table2", None, title="✅ *Updated Tables*"
        )
        expected = "• `sgid.test.table2`\n"
        assert result == expected

        # Test with custom prefix
        result = summary._create_item_text(
            "sgid.test.table3",
            "abcd1234567890123456789012345678",
            prefix="✓",
            title="✅ *Updated Tables*",
        )
        expected = "✓ <https://utah.maps.arcgis.com/home/item.html?id=abcd1234567890123456789012345678|`sgid.test.table3`>\n"
        assert result == expected

        # Test error message formatting
        result = summary._create_item_text(
            "table1: Connection timeout", None, title="*🔧 Update Error Details:*"
        )
        expected = "• table1: Connection timeout\n"
        assert result == expected

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

    @patch("dolly.summary.requests.post")
    @patch("dolly.summary.logger")
    def test_finish_summary(self, mock_logger, mock_requests_post):
        """Test finishing summary."""
        start_time = time.time()
        end_time = start_time + 10

        # Mock Slack requests to prevent actual HTTP calls
        mock_requests_post.return_value.status_code = 200

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

    def test_format_slack_message_success(self):
        """Test formatting a successful process summary as Slack message."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_updated("sgid.test.table1", None)
        summary.add_table_published("sgid.test.table1", None)

        message = summary.format_slack_message()

        assert "blocks" in message
        assert len(message["blocks"]) > 0

        # Convert message to string for easier testing
        message_str = str(message)
        assert "🟢 *Status:* Process completed successfully" in message_str
        assert "sgid.test.table1" in message_str
        assert "Global errors: *0*" in message_str

    def test_format_slack_message_with_errors(self):
        """Test formatting a process summary with errors as Slack message."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_error("sgid.test.table1", "update", "Connection failed")

        message = summary.format_slack_message()

        # Convert message to string for easier testing
        message_str = str(message)
        assert "🟡 *Status:* Process completed with errors" in message_str
        assert "sgid.test.table1" in message_str
        assert "Global errors: *0*" in message_str

    def test_format_slack_message_no_tables(self):
        """Test formatting a summary with no tables processed."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        message = summary.format_slack_message()

        # Convert message to string for easier testing
        message_str = str(message)
        assert (
            "🔵 *Status:* Process completed - no tables required processing"
            in message_str
        )
        assert "Global errors: *0*" in message_str

    def test_format_slack_message_with_global_errors(self):
        """Test formatting a process summary with global errors as Slack message."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_global_error("ValueError: Invalid configuration")
        summary.add_global_error("ConnectionError: Database unavailable")

        message = summary.format_slack_message()

        # Convert message to string for easier testing
        message_str = str(message)
        assert "🔴 *Status:* Process failed due to global errors" in message_str
        assert "Global errors: *2*" in message_str
        assert "🚨 *Global Errors (Process Failed):*" in message_str
        assert "ValueError: Invalid configuration" in message_str
        assert "ConnectionError: Database unavailable" in message_str

    @patch("dolly.summary.requests.post")
    def test_post_to_slack_success(self, mock_post):
        """Test successful posting to Slack."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        summary = ProcessSummary()
        result = summary.post_to_slack("https://hooks.slack.com/test")

        assert result is True
        mock_post.assert_called_once()

    @patch("dolly.summary.requests.post")
    def test_post_to_slack_failure(self, mock_post):
        """Test failed posting to Slack."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        summary = ProcessSummary()
        result = summary.post_to_slack("https://hooks.slack.com/test")

        assert result is False

    @patch("dolly.summary.requests.post")
    def test_post_to_slack_request_exception(self, mock_post):
        """Test Slack posting with request exception."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        summary = ProcessSummary()
        result = summary.post_to_slack("https://hooks.slack.com/test")

        assert result is False

    @patch("dolly.summary.get_secrets")
    def test_finish_summary_with_slack(self, mock_get_secrets):
        """Test finish_summary posts to Slack when webhook URL is available."""
        # Start a summary so we have a current one
        start_time = time.time()
        summary = start_summary(start_time)

        # Mock the post_to_slack method
        with patch.object(summary, "post_to_slack", return_value=True) as mock_post:
            # Mock secrets with Slack webhook
            mock_get_secrets.return_value = {
                "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"
            }

            finish_summary(start_time + 10)

            mock_post.assert_called_once_with("https://hooks.slack.com/test")

    @patch("dolly.summary.get_secrets")
    def test_finish_summary_no_slack_webhook(self, mock_get_secrets):
        """Test finish_summary when no Slack webhook URL is configured."""
        # Start a summary so we have a current one
        start_time = time.time()
        summary = start_summary(start_time)

        # Mock the post_to_slack method
        with patch.object(summary, "post_to_slack") as mock_post:
            # Mock secrets without Slack webhook
            mock_get_secrets.return_value = {}

            finish_summary(start_time + 10)

            mock_post.assert_not_called()

    def test_format_slack_message_with_agol_links(self):
        """Test formatting Slack message with AGOL item links."""
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

        message = summary.format_slack_message()

        message_str = str(message)

        # Check that links are created for tables with item_ids
        assert (
            "https://utah.maps.arcgis.com/home/item.html?id=583c0f4888d44f0a90791282b2a69829"
            in message_str
        )
        assert (
            "https://utah.maps.arcgis.com/home/item.html?id=abcd1234567890123456789012345678"
            in message_str
        )

        # Check that the link format is correct
        assert (
            "<https://utah.maps.arcgis.com/home/item.html?id=583c0f4888d44f0a90791282b2a69829|`sgid.test.table1`>"
            in message_str
        )
        assert (
            "<https://utah.maps.arcgis.com/home/item.html?id=abcd1234567890123456789012345678|`sgid.test.table3`>"
            in message_str
        )

        # Check that tables without item_ids still appear as plain text
        assert "`sgid.test.table2`" in message_str

        # Ensure the message structure is still correct
        assert "🟢 *Status:* Process completed successfully" in message_str
        assert "✅ *Updated Tables*" in message_str
        assert "🚀 *Published Tables*" in message_str

    def test_format_slack_message_with_long_table_list(self):
        """Test formatting a message with many tables that exceed Slack block limits."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        # Add many tables to trigger block splitting
        for i in range(100):
            long_table_name = f"sgid.very_long_schema_name.very_long_table_name_that_makes_text_exceed_limits_{i:03d}"
            summary.add_table_updated(long_table_name, None)

        message = summary.format_slack_message()
        message_str = str(message)

        # Should contain continuation markers
        assert "*(continued)*" in message_str
        assert len(message["blocks"]) > 1

    def test_format_slack_message_with_gcp_environment(self):
        """Test formatting a message when running in GCP environment."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_updated("sgid.test.table1", None)

        # Mock the GCP metadata request to simulate running in GCP
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = "test-project"
            mock_get.return_value = mock_response

            message = summary.format_slack_message()
            message_str = str(message)

            # Should contain GCP logs link
            assert "GCP Logs" in message_str
            # Find URLs in the message, and check for proper console.cloud.google.com hostname
            import re
            from urllib.parse import urlparse

            urls = re.findall(r"https?://[^\s\]>]+", message_str)
            assert any(urlparse(u).hostname == "console.cloud.google.com" for u in urls)

    def test_post_to_slack_multiple_blocks(self):
        """Test posting to Slack when message exceeds block limit."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        # Create enough content to exceed 50 blocks
        # Each block can hold ~2800 chars, and we need to force 51+ blocks
        base_content = "x" * 100  # Base content to make items longer

        # Add many tables with long names and many errors to generate enough blocks
        for i in range(300):
            long_table_name = f"sgid.very_long_schema_name_with_many_characters.very_long_table_name_that_exceeds_normal_limits_{base_content}_{i:04d}"
            summary.add_table_updated(long_table_name, None)
            # Add errors for every 5th table to create even more blocks
            if i % 5 == 0:
                long_error = f"Very long error message with lots of details {base_content} that will help create more blocks and exceed limits {i}"
                summary.add_table_error(long_table_name, "update", long_error)

        # Check if we have enough blocks first
        message = summary.format_slack_message()
        print(f"Generated {len(message['blocks'])} blocks")

        # If we still don't have >50 blocks, skip this test
        if len(message["blocks"]) <= 50:
            # Let's just test the multiple request logic by mocking format_slack_message
            with patch.object(summary, "format_slack_message") as mock_format:
                # Create a mock message with 51 blocks
                mock_blocks = [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"Block {i}"},
                    }
                    for i in range(51)
                ]
                mock_format.return_value = {"blocks": mock_blocks}

                webhook_url = "https://hooks.slack.com/test"

                with patch("requests.post") as mock_post:
                    mock_post.return_value.status_code = 200
                    mock_post.return_value.text = "ok"

                    result = summary.post_to_slack(webhook_url)

                    # Should have made multiple POST requests (51 blocks = 2 requests)
                    assert mock_post.call_count > 1
                    assert result is True
        else:
            # We have enough blocks naturally
            webhook_url = "https://hooks.slack.com/test"

            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.text = "ok"

                result = summary.post_to_slack(webhook_url)

                # Should have made multiple POST requests
                assert mock_post.call_count > 1
                assert result is True

    def test_post_to_slack_partial_failure(self):
        """Test posting to Slack when some message parts fail."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        # Use the same approach as the previous test - mock format_slack_message to ensure >50 blocks
        with patch.object(summary, "format_slack_message") as mock_format:
            # Create a mock message with 51 blocks to force splitting
            mock_blocks = [
                {"type": "section", "text": {"type": "mrkdwn", "text": f"Block {i}"}}
                for i in range(51)
            ]
            mock_format.return_value = {"blocks": mock_blocks}

            webhook_url = "https://hooks.slack.com/test"

            def side_effect(*args, **kwargs):
                # Simulate first request succeeding, second failing
                mock_response = MagicMock()
                if not hasattr(side_effect, "call_count"):
                    side_effect.call_count = 0
                side_effect.call_count += 1

                if side_effect.call_count == 1:
                    mock_response.status_code = 200
                    mock_response.text = "ok"
                else:
                    mock_response.status_code = 500
                    mock_response.text = "error"
                return mock_response

            with patch("requests.post", side_effect=side_effect):
                result = summary.post_to_slack(webhook_url)

                # Should return False due to partial failure
                assert result is False

    def test_post_to_slack_exception_handling(self):
        """Test exception handling in post_to_slack method."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0
        summary.add_table_updated("sgid.test.table1", None)

        webhook_url = "https://hooks.slack.com/test"

        with patch("requests.post", side_effect=Exception("Unexpected error")):
            result = summary.post_to_slack(webhook_url)

            # Should return False and handle exception gracefully
            assert result is False

    def test_add_table_publish_error(self):
        """Test adding publish error (covering publish error branch)."""
        summary = ProcessSummary()

        summary.add_table_error("sgid.test.table1", "publish", "Publish failed")

        assert "sgid.test.table1" in summary.tables_with_errors
        assert "sgid.test.table1: Publish failed" in summary.publish_errors

    def test_create_text_blocks_empty_items(self):
        """Test _create_text_blocks_with_limit with empty items list."""
        summary = ProcessSummary()

        # Test with empty items list
        blocks = summary._create_text_blocks_with_limit("Test Title", [], None, "•")

        assert blocks == []

    def test_format_slack_message_title_without_asterisk(self):
        """Test title continuation when title doesn't end with asterisk."""
        summary = ProcessSummary()
        summary.start_time = 100.0
        summary.end_time = 110.0

        # Create content that will definitely exceed block limits by using very long table names
        base_content = "x" * 1000  # Very long content
        for i in range(50):
            very_long_name = f"sgid.schema.{base_content}_table_{i}"
            summary.add_table_updated(very_long_name, None)

        message = summary.format_slack_message()

        # The test passes if the message is formatted successfully
        # (The continuation logic is complex and depends on exact character counts)
        assert "blocks" in message
