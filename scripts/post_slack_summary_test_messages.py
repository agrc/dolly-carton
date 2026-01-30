"""Post Slack summary messages covering all summary content types."""

from __future__ import annotations

import logging
import time
from typing import Iterable

from supervisor.message_handlers import SlackHandler
from supervisor.models import MessageDetails

from dolly.summary import ProcessSummary
from dolly.utils import get_secrets

logger = logging.getLogger(__name__)


def _build_success_summary() -> ProcessSummary:
    start_time = time.time() - 142
    summary = ProcessSummary(start_time=start_time)
    summary.add_table_updated(
        "sgid.transportation.roads", "3b3d6bb54b1a48d2a0b1c78d8a1f4d2e"
    )
    summary.add_table_updated(
        "sgid.boundaries.counties", "9c5b7a0f9b7a4c1a9f2e0a1a2b3c4d5e"
    )
    summary.add_table_published(
        "sgid.society.cemeteries", "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d"
    )
    summary.end_time = time.time()

    return summary


def _build_error_summary() -> ProcessSummary:
    start_time = time.time() - 388
    summary = ProcessSummary(start_time=start_time)
    summary.add_table_updated(
        "sgid.water.waterbodies", "7f8e9d0c1b2a3d4e5f6a7b8c9d0e1f2a"
    )
    summary.add_table_published(
        "sgid.environment.uicfacility", "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
    )
    summary.add_table_error(
        "sgid.transportation.airstrips",
        "update",
        "Failed to update layer definition: timeout while polling edit status",
    )
    summary.add_table_error(
        "sgid.geoscience.faults",
        "publish",
        "Publish failed: service name already exists",
    )
    summary.add_feature_count_mismatch("sgid.water.streams", 4821, 4790)
    summary.end_time = time.time()

    return summary


def _build_global_error_summary() -> ProcessSummary:
    start_time = time.time() - 51
    summary = ProcessSummary(start_time=start_time)
    summary.add_global_error("Connection to ArcGIS Online failed: invalid credentials")
    summary.add_global_error(
        "Aborting remaining processing due to authentication failure"
    )
    summary.end_time = time.time()

    return summary


def _build_empty_summary() -> ProcessSummary:
    start_time = time.time() - 12
    summary = ProcessSummary(start_time=start_time)
    summary.end_time = time.time()

    return summary


def _build_many_updated_tables_summary() -> ProcessSummary:
    start_time = time.time() - 203
    summary = ProcessSummary(start_time=start_time)
    for index in range(30):
        table_name = f"sgid.test.table{index}"
        item_id = f"{index:02d}" * 16
        summary.add_table_updated(table_name, item_id)
    summary.end_time = time.time()

    return summary


def _send_summary(handler: SlackHandler, summary: ProcessSummary) -> None:
    message_details = MessageDetails()
    message_details.slack_messages = summary.build_slack_messages()
    handler.send_message(message_details)


def _get_handler() -> SlackHandler:
    secrets = get_secrets()
    slack_webhook_url = secrets.get("SLACK_WEBHOOK_URL")
    if not slack_webhook_url:
        raise RuntimeError(
            "SLACK_WEBHOOK_URL is not configured in secrets; cannot post test messages"
        )

    return SlackHandler(
        {"webhook_url": slack_webhook_url},
        client_name="dolly-carton",
        client_version=ProcessSummary._get_client_version(),
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        handler = _get_handler()
    except RuntimeError as exc:
        logger.error(str(exc))
        return 1

    summaries: Iterable[ProcessSummary] = (
        _build_success_summary(),
        _build_error_summary(),
        _build_global_error_summary(),
        _build_empty_summary(),
        _build_many_updated_tables_summary(),
    )

    for summary in summaries:
        _send_summary(handler, summary)

    logger.info("Posted Slack summary test messages.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
