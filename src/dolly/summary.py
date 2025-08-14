"""Summary reporting functionality for Dolly Carton process tracking."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from textwrap import dedent
from typing import List

import humanize
import requests

from dolly.utils import get_secrets

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
    global_errors: List[str] = field(default_factory=list)

    # Timing
    start_time: float = 0.0
    end_time: float = 0.0

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

    def add_global_error(self, error_message: str) -> None:
        """Add a global error that prevented normal process completion."""
        self.global_errors.append(error_message)

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

        if self.global_errors:
            logger.info(f"🚨 Global errors: {len(self.global_errors)}")
            for error in self.global_errors:
                logger.info(f"   • {error}")

        # Timing information
        elapsed_time = self.get_total_elapsed_time()
        logger.info(f"⏱️  Total elapsed time: {humanize.precisedelta(elapsed_time)}")

        # Overall status
        if self.global_errors:
            logger.info("🔴 Process failed due to global errors")
        elif self.tables_with_errors:
            logger.info("🟡 Process completed with errors")
        elif total_tables > 0:
            logger.info("🟢 Process completed successfully")
        else:
            logger.info("🔵 No tables required processing")

        logger.info("=" * 80)

    def _create_text_blocks_with_limit(
        self, title: str, items: List[str], prefix: str = "•", max_chars: int = 2800
    ) -> List[dict]:
        """
        Create multiple blocks if content exceeds character limit.

        Args:
            title: Section title (e.g., "✅ *Updated Tables*")
            items: List of items to include
            prefix: Prefix for each item (default: "•")
            max_chars: Maximum characters per block (leaving buffer for title and formatting)

        Returns:
            List of block dictionaries
        """
        if not items:
            return []

        blocks = []
        current_items = []
        current_length = len(title) + 10  # Buffer for formatting

        for item in items:
            # For table names, wrap in backticks; for error messages, use as-is
            if ":" in item and ("Error" in title or "error" in item.lower()):
                item_text = f"{prefix} {item}\n"
            else:
                item_text = f"{prefix} `{item}`\n"
            item_length = len(item_text)

            # If adding this item would exceed the limit, create a block with current items
            if current_length + item_length > max_chars and current_items:
                item_list = "".join(current_items).rstrip()
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{title}\n{item_list}",
                        },
                    }
                )
                current_items = []
                current_length = len(title) + 10
                # Update title for continuation blocks
                if "*(continued)*" not in title:
                    # Find the last asterisk and insert (continued) before it
                    if title.endswith("*"):
                        title = title[:-1] + "*(continued)*"
                    else:
                        title = title + "*(continued)*"

            current_items.append(item_text)
            current_length += item_length

        # Add the remaining items
        if current_items:
            item_list = "".join(current_items).rstrip()
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{title}\n{item_list}",
                    },
                }
            )

        return blocks

    def format_slack_message(self) -> dict:
        """
        Format the summary as a Slack message payload using webhook-compatible Block Kit layout.
        Handles Slack's 3000 character limit per block by splitting long content.

        Returns:
            dict: Slack message payload with blocks that work with webhooks
        """
        # Determine overall status and emoji
        total_tables = len(set(self.tables_updated + self.tables_published))
        if self.global_errors:
            status_emoji = "🔴"
            status_text = "failed due to global errors"
        elif self.tables_with_errors:
            status_emoji = "🟡"
            status_text = "completed with errors"
        elif total_tables > 0:
            status_emoji = "🟢"
            status_text = "completed successfully"
        else:
            status_emoji = "🔵"
            status_text = "completed - no tables required processing"

        elapsed_time = self.get_total_elapsed_time()

        current_date = datetime.now().strftime("%B %d, %Y")
        host = "local dev"
        is_running_in_gcp = False
        try:
            response = requests.get(
                "http://metadata.google.internal/computeMetadata/v1/project/project-id",
                headers={"Metadata-Flavor": "Google"},
                timeout=5,
            )
            host = response.text
            is_running_in_gcp = True
        except Exception:
            pass

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
                    {"type": "mrkdwn", "text": f"🖥️ *Host:*\n`{host}`"},
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
                    "text": (
                        dedent(f"""
                            *📊 Processing Summary*
                            • Tables processed: *{total_tables}*
                            • Updated: *{len(self.tables_updated)}*
                            • Published: *{len(self.tables_published)}*
                            • Table errors: *{len(self.tables_with_errors)}*
                            • Global errors: *{len(self.global_errors)}*
                        """)
                    ),
                },
            }
        )
        # Add divider before detailed sections
        if (
            self.tables_updated
            or self.tables_published
            or self.tables_with_errors
            or self.global_errors
        ):
            blocks.append({"type": "divider"})

        # Updated tables section
        if self.tables_updated:
            updated_blocks = self._create_text_blocks_with_limit(
                "✅ *Updated Tables*", self.tables_updated
            )
            blocks.extend(updated_blocks)

        # Published tables section
        if self.tables_published:
            published_blocks = self._create_text_blocks_with_limit(
                "🚀 *Published Tables*", self.tables_published
            )
            blocks.extend(published_blocks)

        # Error sections
        if self.tables_with_errors:
            error_blocks = self._create_text_blocks_with_limit(
                "❌ *Tables with Errors*", self.tables_with_errors
            )
            blocks.extend(error_blocks)

            # Update errors with detailed formatting
            if self.update_errors:
                update_error_blocks = self._create_text_blocks_with_limit(
                    "*🔧 Update Error Details:*", self.update_errors, prefix="•"
                )
                blocks.extend(update_error_blocks)

            # Publish errors with detailed formatting
            if self.publish_errors:
                publish_error_blocks = self._create_text_blocks_with_limit(
                    "*📤 Publish Error Details:*", self.publish_errors, prefix="•"
                )
                blocks.extend(publish_error_blocks)

        # Global errors section
        if self.global_errors:
            global_error_blocks = self._create_text_blocks_with_limit(
                "🚨 *Global Errors (Process Failed):*", self.global_errors, prefix="•"
            )
            blocks.extend(global_error_blocks)

        if is_running_in_gcp:
            # Create GCP logs link with time range based on actual process execution time
            # Add 1 hour buffer to start and end times
            buffer_seconds = 900  # 15 minutes
            log_start_time = self.start_time - buffer_seconds
            log_end_time = (
                self.end_time if self.end_time > 0 else datetime.now().timestamp()
            ) + buffer_seconds

            # Convert to ISO format for GCP logs URL
            log_start_datetime = (
                datetime.fromtimestamp(log_start_time).isoformat() + "Z"
            )
            log_end_datetime = datetime.fromtimestamp(log_end_time).isoformat() + "Z"

            blocks.append(
                {
                    "type": "rich_text",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [
                                {
                                    "type": "link",
                                    "text": "GCP Logs",
                                    "url": f"https://console.cloud.google.com/logs/query;query=resource.type%20%3D%20%22cloud_run_job%22%20resource.labels.job_name%20%3D%20%22dolly%22%20resource.labels.location%20%3D%20%22us-west3%22%20severity%3E%3DDEFAULT;storageScope=project;timeRange={log_start_datetime}%2F{log_end_datetime}?authuser=0&inv=1&invt=Ab43MA&project={host}",
                                }
                            ],
                        }
                    ],
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
            logger.error(f"Error posting to Slack: {e}", exc_info=True)

            return False
        except Exception as e:
            logger.error(f"Unexpected error posting to Slack: {e}", exc_info=True)

            return False


# Global instance to track the current process
_current_summary: ProcessSummary | None = None


def start_summary(start_time: float) -> ProcessSummary:
    """
    Initialize a new process summary.

    Args:
        start_time: Process start time (from time.time())

    Returns:
        ProcessSummary instance for tracking
    """
    global _current_summary
    _current_summary = ProcessSummary(start_time=start_time)

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
            slack_webhook_url = secrets["SLACK_WEBHOOK_URL"]

            if slack_webhook_url:
                _current_summary.post_to_slack(slack_webhook_url)
            else:
                logger.info(
                    "No Slack webhook URL configured, skipping Slack notification"
                )

        except Exception as e:
            logger.warning(f"Failed to post summary to Slack: {e}")
