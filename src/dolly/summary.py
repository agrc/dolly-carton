"""Summary reporting functionality for Dolly Carton process tracking."""

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import List

import humanize

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
