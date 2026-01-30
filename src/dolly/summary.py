"""Summary reporting functionality for Dolly Carton process tracking."""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from textwrap import dedent
from typing import List

import humanize
import requests
from supervisor.message_handlers import SlackHandler
from supervisor.models import MessageDetails
from supervisor.slack import DividerBlock, Message, SectionBlock

from dolly.utils import get_secrets

logger = logging.getLogger(__name__)
AGOL_URL = "https://utah.maps.arcgis.com/home/item.html?id="

# Rotating Dolly Parton quotes for encouragement
DOLLY_QUOTES = [
    "If you want the rainbow, you gotta put up with the rain.",
    "There's no failure, only quitting.",
    "Do the best you can, with what you have, where you are.",
    "Find out who you are and do it on purpose.",
]


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

    # AGOL item IDs for linking (parallel arrays to tables_updated/published)
    updated_item_ids: List[str | None] = field(default_factory=list)
    published_item_ids: List[str | None] = field(default_factory=list)

    # Error details
    update_errors: List[str] = field(default_factory=list)
    publish_errors: List[str] = field(default_factory=list)
    global_errors: List[str] = field(default_factory=list)

    # Timing
    start_time: float = 0.0
    end_time: float = 0.0

    def add_table_updated(self, table: str, item_id: str | None) -> None:
        """Add a table that was successfully updated.

        Args:
            table: Table name
            item_id: AGOL item ID for linking (can be None if no item exists)
        """
        if table not in self.tables_updated:
            self.tables_updated.append(table)
            self.updated_item_ids.append(item_id)

    def add_table_published(self, table: str, item_id: str | None) -> None:
        """Add a table that was successfully published.

        Args:
            table: Table name
            item_id: AGOL item ID for linking (can be None if no item exists)
        """
        if table not in self.tables_published:
            self.tables_published.append(table)
            self.published_item_ids.append(item_id)

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

    def add_feature_count_mismatch(
        self, table: str, source_count: int, final_count: int
    ) -> None:
        """Add a feature count mismatch error for a table."""
        # Add it as a table error
        self.add_table_error(
            table,
            "update",
            f"Feature count mismatch - source (internal): {source_count} -> destination (AGOL): {final_count}",
        )

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

        quote = random.choice(DOLLY_QUOTES)
        logger.info(f'\u2728 "{quote}" - Dolly Parton')

    @staticmethod
    def _get_client_version() -> str:
        try:
            return version("dolly-carton")
        except PackageNotFoundError:
            return "unknown"

    @staticmethod
    def _get_host_info() -> tuple[str, bool]:
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

        return host, is_running_in_gcp

    def build_slack_messages(self) -> List[Message]:
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
        host, is_running_in_gcp = self._get_host_info()

        message = Message(text="Dolly Carton Process Summary")
        message.add(SectionBlock(text="*🛒 Dolly Carton Process Summary*"))
        message.add(
            SectionBlock(text=f"{status_emoji} *Status:* Process {status_text}")
        )
        message.add(
            SectionBlock(
                fields=[
                    f"📅 *Date:*\n{current_date}",
                    f"🖥️ *Host:*\n`{host}`",
                    f"⏱️ *Duration:*\n{humanize.precisedelta(elapsed_time)}",
                ]
            )
        )
        message.add(
            SectionBlock(
                text=dedent(
                    f"""
                    *📊 Processing Summary*
                    • Tables processed: *{total_tables}*
                    • Updated: *{len(self.tables_updated)}*
                    • Published: *{len(self.tables_published)}*
                    • Table errors: *{len(self.tables_with_errors)}*
                    • Global errors: *{len(self.global_errors)}*
                    """
                ).strip()
            )
        )

        if (
            self.tables_updated
            or self.tables_published
            or self.tables_with_errors
            or self.global_errors
        ):
            message.add(DividerBlock())

        if self.tables_updated:
            message.add(SectionBlock(text="✅ *Updated Tables*"))
            for table, item_id in zip(self.tables_updated, self.updated_item_ids):
                message.add(SectionBlock(text=f"• <{AGOL_URL}{item_id}|`{table}`>"))

        if self.tables_published:
            message.add(SectionBlock(text="🚀 *Published Tables*"))
            for table, item_id in zip(self.tables_published, self.published_item_ids):
                message.add(SectionBlock(text=f"• <{AGOL_URL}{item_id}|`{table}`>"))

        if self.tables_with_errors:
            message.add(SectionBlock(text="🚨 *Tables with Errors*"))
            for table in self.tables_with_errors:
                message.add(SectionBlock(text=f"• `{table}`"))

        if self.update_errors:
            message.add(SectionBlock("*🔧 Update Error Details:*"))
            for error in self.update_errors:
                message.add(SectionBlock(text=f"• {error}"))

        if self.publish_errors:
            message.add(SectionBlock("*📤 Publish Error Details:*"))
            for error in self.publish_errors:
                message.add(SectionBlock(text=f"• {error}"))

        if self.global_errors:
            message.add(SectionBlock("🚨 *Global Errors (Process Failed):*"))
            for error in self.global_errors:
                message.add(SectionBlock(text=f"• {error}"))

        if is_running_in_gcp:
            buffer_seconds = 900
            log_start_time = self.start_time - buffer_seconds
            log_end_time = (
                self.end_time if self.end_time > 0 else datetime.now().timestamp()
            ) + buffer_seconds

            log_start_datetime = (
                datetime.fromtimestamp(log_start_time).isoformat() + "Z"
            )
            log_end_datetime = datetime.fromtimestamp(log_end_time).isoformat() + "Z"

            gcp_logs_url = (
                "https://console.cloud.google.com/logs/query;"
                "query=resource.type%20%3D%20%22cloud_run_job%22%20resource.labels.job_name%20%3D%20%22dolly%22%20resource.labels.location%20%3D%20%22us-west3%22%20severity%3E%3DDEFAULT;"
                f"storageScope=project;timeRange={log_start_datetime}%2F{log_end_datetime}?authuser=0&inv=1&invt=Ab43MA&project={host}"
            )
            message.add(SectionBlock(text=f"🔗 <{gcp_logs_url}|GCP Logs>"))

        message.add(DividerBlock())
        message.add(SectionBlock(f'"{random.choice(DOLLY_QUOTES)}" - Dolly Parton'))
        message.add(DividerBlock())
        message.add(SectionBlock(text=" "))

        return [message]


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
                handler = SlackHandler(
                    {"webhook_url": slack_webhook_url},
                    client_name="dolly-carton",
                    client_version=_current_summary._get_client_version(),
                )
                message_details = MessageDetails()
                message_details.slack_messages = _current_summary.build_slack_messages()
                handler.send_message(message_details)
            else:
                logger.info(
                    "No Slack webhook URL configured, skipping Slack notification"
                )

        except Exception as e:
            logger.warning(f"Failed to post summary to Slack: {e}")
