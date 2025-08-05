"""Summary reporting functionality for Dolly Carton process tracking."""

import logging
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List
from dolly.utils import get_secrets

import humanize
import requests

logger = logging.getLogger(__name__)


@dataclass
class ProcessSummary:
    """
    Tracks the summary of the Dolly Carton process execution.

    This class accumulates information about what was accomplished during
    a Dolly Carton run, including successful updates, publications, errors,
    and timing information.
    """

    # Tables processed
    tables_updated: List[str] = field(default_factory=list)
    tables_published: List[str] = field(default_factory=list)
    tables_with_errors: List[str] = field(default_factory=list)

    # Error details
    update_errors: List[str] = field(default_factory=list)
    publish_errors: List[str] = field(default_factory=list)

    # Timing
    start_time: float = 0.0
    end_time: float = 0.0

    # Mode information
    cli_tables_provided: bool = False
    change_detection_used: bool = False

    def add_table_updated(self, table: str) -> None:
        """Add a table that was successfully updated."""
        if table not in self.tables_updated:
            self.tables_updated.append(table)

    def add_table_published(self, table: str) -> None:
        """Add a table that was successfully published."""
        if table not in self.tables_published:
            self.tables_published.append(table)

    def add_table_error(self, table: str, error_type: str, error_message: str) -> None:
        """Add a table that encountered an error during processing."""
        if table not in self.tables_with_errors:
            self.tables_with_errors.append(table)

        error_detail = f"{table}: {error_message}"
        if error_type == "update":
            self.update_errors.append(error_detail)
        elif error_type == "publish":
            self.publish_errors.append(error_detail)

    def get_total_elapsed_time(self) -> timedelta:
        """Get the total elapsed time as a timedelta object."""
        if self.end_time > 0:
            duration = self.end_time - self.start_time
        else:
            duration = 0.0

        return timedelta(seconds=duration)

    def log_summary(self) -> None:
        """Log a comprehensive summary of the process execution."""
        logger.info("=" * 80)
        logger.info("DOLLY CARTON PROCESS SUMMARY")
        logger.info("=" * 80)

        # Mode information
        if self.cli_tables_provided:
            logger.info("📋 Mode: CLI-provided tables")
        elif self.change_detection_used:
            logger.info("🔍 Mode: Automatic change detection")
        else:
            logger.info("❓ Mode: Unknown")

        # Success metrics
        total_tables = len(set(self.tables_updated + self.tables_published))
        logger.info(f"📊 Total tables processed: {total_tables}")

        if self.tables_updated:
            logger.info(f"✅ Tables updated: {len(self.tables_updated)}")
            for table in self.tables_updated:
                logger.info(f"   • {table}")
        else:
            logger.info("✅ Tables updated: 0")

        if self.tables_published:
            logger.info(f"🚀 Tables published: {len(self.tables_published)}")
            for table in self.tables_published:
                logger.info(f"   • {table}")
        else:
            logger.info("🚀 Tables published: 0")

        # Error reporting
        if self.tables_with_errors:
            logger.info(f"❌ Tables with errors: {len(self.tables_with_errors)}")
            for table in self.tables_with_errors:
                logger.info(f"   • {table}")

            if self.update_errors:
                logger.info("📝 Update errors:")
                for error in self.update_errors:
                    logger.info(f"   • {error}")

            if self.publish_errors:
                logger.info("📝 Publish errors:")
                for error in self.publish_errors:
                    logger.info(f"   • {error}")
        else:
            logger.info("❌ Tables with errors: 0")

        # Timing information
        elapsed_time = self.get_total_elapsed_time()
        logger.info(f"⏱️  Total elapsed time: {humanize.precisedelta(elapsed_time)}")

        # Overall status
        if self.tables_with_errors:
            logger.info("🟡 Process completed with errors")
        elif total_tables > 0:
            logger.info("🟢 Process completed successfully")
        else:
            logger.info("🔵 No tables required processing")

        logger.info("=" * 80)

    def format_slack_message(self) -> dict:
        """
        Format the summary as a Slack message payload using webhook-compatible Block Kit layout.

        Returns:
            dict: Slack message payload with blocks that work with webhooks
        """
        # Determine overall status and emoji
        total_tables = len(set(self.tables_updated + self.tables_published))
        if self.tables_with_errors:
            status_emoji = "🟡"
            status_text = "completed with errors"
        elif total_tables > 0:
            status_emoji = "🟢"
            status_text = "completed successfully"
        else:
            status_emoji = "🔵"
            status_text = "completed - no tables required processing"

        # Mode information
        if self.cli_tables_provided:
            mode_text = "📋 CLI-provided tables"
        elif self.change_detection_used:
            mode_text = "🔍 Automatic change detection"
        else:
            mode_text = "❓ Unknown mode"

        elapsed_time = self.get_total_elapsed_time()

        # Get current date and machine name
        current_date = datetime.now().strftime("%B %d, %Y")
        machine_name = socket.gethostname()

        blocks = []

        # Header section
        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🛒 Dolly Carton Process Summary",
                    "emoji": True,
                },
            }
        )

        # Status section
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *Status:* Process {status_text}",
                },
            }
        )

        # Context info section
        blocks.append(
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"📅 *Date:*\n{current_date}"},
                    {"type": "mrkdwn", "text": f"🖥️ *Machine:*\n`{machine_name}`"},
                    {"type": "mrkdwn", "text": f"⚙️ *Mode:*\n{mode_text}"},
                    {
                        "type": "mrkdwn",
                        "text": f"⏱️ *Duration:*\n{humanize.precisedelta(elapsed_time)}",
                    },
                ],
            }
        )

        # Key metrics section
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📊 Processing Summary*\n• Tables processed: *{total_tables}*\n• Updated: *{len(self.tables_updated)}*\n• Published: *{len(self.tables_published)}*\n• Errors: *{len(self.tables_with_errors)}*",
                },
            }
        )

        # Add divider before detailed sections
        if self.tables_updated or self.tables_published or self.tables_with_errors:
            blocks.append({"type": "divider"})

        # Updated tables section
        if self.tables_updated:
            table_list = "\n".join([f"• `{table}`" for table in self.tables_updated])
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ *Updated Tables*\n{table_list}",
                    },
                }
            )

        # Published tables section
        if self.tables_published:
            table_list = "\n".join([f"• `{table}`" for table in self.tables_published])
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🚀 *Published Tables*\n{table_list}",
                    },
                }
            )

        # Error sections
        if self.tables_with_errors:
            table_list = "\n".join(
                [f"• `{table}`" for table in self.tables_with_errors]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"❌ *Tables with Errors*\n{table_list}",
                    },
                }
            )

            # Update errors with detailed formatting
            if self.update_errors:
                error_list = "\n".join([f"• {error}" for error in self.update_errors])
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*🔧 Update Error Details:*\n{error_list}",
                        },
                    }
                )

            # Publish errors with detailed formatting
            if self.publish_errors:
                error_list = "\n".join([f"• {error}" for error in self.publish_errors])
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*📤 Publish Error Details:*\n{error_list}",
                        },
                    }
                )

        return {"blocks": blocks}

    def post_to_slack(self, webhook_url: str) -> bool:
        """
        Post the summary to a Slack channel via webhook.

        Handles Slack's 50-block limit by splitting large messages into multiple parts.

        Args:
            webhook_url: Slack webhook URL for posting messages

        Returns:
            bool: True if all messages posted successfully, False otherwise
        """
        try:
            payload = self.format_slack_message()
            blocks = payload["blocks"]

            # Slack limit is 50 blocks per message
            MAX_BLOCKS_PER_MESSAGE = 50

            if len(blocks) <= MAX_BLOCKS_PER_MESSAGE:
                # Single message - send as is
                response = requests.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )

                if response.status_code == 200:
                    logger.info("Successfully posted summary to Slack")
                    return True
                else:
                    logger.warning(
                        f"Failed to post to Slack. Status code: {response.status_code}, "
                        f"Response: {response.text}"
                    )
                    return False
            else:
                # Multiple messages needed
                logger.info(
                    f"Message has {len(blocks)} blocks, splitting into multiple messages"
                )

                # Split blocks into chunks
                message_chunks = []
                for i in range(0, len(blocks), MAX_BLOCKS_PER_MESSAGE):
                    chunk_blocks = blocks[i : i + MAX_BLOCKS_PER_MESSAGE]
                    message_chunks.append({"blocks": chunk_blocks})

                # Send all chunks
                all_successful = True
                for part_num, chunk in enumerate(message_chunks, 1):
                    response = requests.post(
                        webhook_url,
                        json=chunk,
                        headers={"Content-Type": "application/json"},
                        timeout=30,
                    )

                    if response.status_code == 200:
                        logger.info(
                            f"Successfully posted part {part_num} of {len(message_chunks)} to Slack"
                        )
                    else:
                        logger.warning(
                            f"Failed to post part {part_num} to Slack. "
                            f"Status code: {response.status_code}, Response: {response.text}"
                        )
                        all_successful = False

                if all_successful:
                    logger.info(
                        f"Successfully posted all {len(message_chunks)} message parts to Slack"
                    )

                return all_successful

        except requests.exceptions.RequestException as e:
            logger.error(f"Error posting to Slack: {e}")

            return False
        except Exception as e:
            logger.error(f"Unexpected error posting to Slack: {e}")

            return False


# Global instance to track the current process
_current_summary: ProcessSummary | None = None


def start_summary(
    start_time: float, cli_tables_provided: bool = False
) -> ProcessSummary:
    """
    Initialize a new process summary.

    Args:
        start_time: Process start time (from time.time())
        cli_tables_provided: Whether tables were provided via CLI

    Returns:
        ProcessSummary instance for tracking
    """
    global _current_summary
    _current_summary = ProcessSummary(
        start_time=start_time,
        cli_tables_provided=cli_tables_provided,
        change_detection_used=not cli_tables_provided,
    )

    return _current_summary


def get_current_summary() -> ProcessSummary | None:
    """Get the current process summary instance."""

    return _current_summary


def finish_summary(end_time: float) -> None:
    """
    Finalize the summary and log the results.

    Args:
        end_time: Process end time (from time.time())
    """
    global _current_summary
    if _current_summary is not None:
        _current_summary.end_time = end_time
        _current_summary.log_summary()

        # Post to Slack if webhook URL is available
        try:
            secrets = get_secrets()
            slack_webhook_url = secrets.get("SLACK_WEBHOOK_URL")

            if slack_webhook_url:
                _current_summary.post_to_slack(slack_webhook_url)
            else:
                logger.info(
                    "No Slack webhook URL configured, skipping Slack notification"
                )

        except Exception as e:
            logger.warning(f"Failed to post summary to Slack: {e}")
