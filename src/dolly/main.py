import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

import humanize
import typer
from arcgis.gis import GIS
from osgeo import gdal

from dolly.agol import (
    publish_new_feature_services,
    update_feature_services,
    zip_and_upload_fgdb,
)
from dolly.internal import create_fgdb, get_agol_items_lookup, get_updated_tables
from dolly.state import get_last_checked, set_last_checked
from dolly.summary import finish_summary, start_summary
from dolly.utils import OUTPUT_PATH, get_secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#: throw exceptions on errors rather than returning None
gdal.UseExceptions()

APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT")


def clean_up() -> None:
    """
    Clean up
    """
    #: recursively delete everything in the output directory including subdirectories
    if OUTPUT_PATH.exists():
        for item in OUTPUT_PATH.iterdir():
            if item.is_dir():
                for subitem in item.rglob("*"):
                    if subitem.is_file():
                        subitem.unlink()
                item.rmdir()
            elif item.is_file():
                #: skip .gitkeep file
                if item.name == ".gitkeep":
                    continue
                item.unlink()

    logger.info("Cleaned up temporary files.")


def _main_logic(tables: Optional[str] = None) -> None:
    """
    Core business logic for the Dolly Carton process.

    This function is separated from main() to enable easier testing. Since Typer's main()
    function uses decorators and dependency injection for CLI argument parsing, it's
    difficult to test directly. By extracting the core logic into this function,
    we can test the business logic independently by passing parameters directly,
    while keeping the CLI interface clean and modern with Typer.

    Args:
        tables: Optional comma-separated list of tables to process.
                If provided, overrides automatic change detection.
    """
    logger.info("Starting Dolly Carton process...")

    start_summary(time.time())

    try:
        clean_up()

        # Use CLI-provided tables if specified, otherwise use change detection
        if tables:
            updated_tables = [
                table.strip() for table in tables.split(",") if table.strip()
            ]
            logger.info(f"Using CLI-provided tables: {updated_tables}")
        else:
            last_checked = get_last_checked()
            logger.info(f"Last checked: {last_checked}")

            updated_tables = get_updated_tables(last_checked)
            logger.info(f"Updated tables: {updated_tables}")

        if not updated_tables:
            logger.info("No updated tables found.")

            return

        agol_items_lookup = get_agol_items_lookup()

        #: separate out items that do not have a valid AGOL item ID
        updated_tables_with_existing_services = []
        updated_tables_without_existing_services = []
        for table in updated_tables:
            if agol_items_lookup[table]["item_id"] is not None:
                updated_tables_with_existing_services.append(table)
            else:
                updated_tables_without_existing_services.append(table)

        if len(updated_tables_with_existing_services) > 0:
            logger.info(
                f"Updating existing feature services for tables: {updated_tables_with_existing_services}"
            )

            fgdb_path = create_fgdb(
                updated_tables_with_existing_services,
                agol_items_lookup,
            )
            gdb_item = zip_and_upload_fgdb(fgdb_path)

            update_feature_services(
                gdb_item,
                updated_tables_with_existing_services,
                agol_items_lookup,
            )
        else:
            logger.info("No existing feature services to update.")

        if len(updated_tables_without_existing_services) > 0:
            publish_new_feature_services(
                updated_tables_without_existing_services,
                agol_items_lookup,
            )
        else:
            logger.info("No new feature services to publish.")

        # Update the last checked timestamp after successful processing
        # Only update if we used change detection (not CLI tables)
        if not tables:
            current_time = datetime.now()
            set_last_checked(current_time)

    finally:
        finish_summary(time.time())


def main(
    tables: Optional[str] = typer.Option(
        None,
        help="Comma-separated list of tables to process (e.g., sgid.society.cemeteries,sgid.boundaries.municipalities). If provided, overrides automatic change detection.",
    ),
) -> None:
    """
    Dolly Carton: Pull data from SGID Internal and push to AGOL

    This is the main CLI entry point using Typer for argument parsing and rich help output.
    The actual business logic is implemented in _main_logic() to enable easier unit testing
    without dealing with Typer's CLI framework complexities.
    """
    _main_logic(tables)


def cleanup_dev_agol_items() -> None:
    """
    Cleans up feature services that are published during dev runs
    """
    start_time = time.time()
    logger.info("Starting cleanup of dev feature services...")

    try:
        if APP_ENVIRONMENT != "dev":
            raise ValueError("This command should only be run in dev environment!")

        secrets = get_secrets()
        gis = GIS(
            "https://utah.maps.arcgis.com",
            username=secrets.get("AGOL_USERNAME"),
            password=secrets.get("AGOL_PASSWORD"),
        )
        agol_items_lookup = get_agol_items_lookup()

        for table in agol_items_lookup:
            item_id = agol_items_lookup[table]["item_id"]
            if item_id is not None:
                continue

            logger.info(f"Cleaning up dev item for table {table} (item_id: {item_id})")
            title = f"{agol_items_lookup[table]['published_name']} (Test)"
            search_results = gis.content.search(
                f'title:"{title}" AND owner:{gis.users.me.username}',
                max_items=1,
            )
            if not search_results:
                logger.warning(
                    f"Item with title: {title} not found, skipping deletion."
                )
                continue
            else:
                item = search_results[0]
                logger.info(f"Deleting item {item.id} for table {table}")
                result = item.delete(permanent=True)
                if not result:
                    raise RuntimeError(f"Failed to delete item {item_id}")

    finally:
        end_time = time.time()
        duration = end_time - start_time
        duration_delta = timedelta(seconds=duration)
        logger.info(
            f"Dev feature services cleanup completed in {humanize.precisedelta(duration_delta)}"
        )


def cli() -> None:
    """
    CLI entry point for the dolly command defined in setup.py.

    This function is the actual console script entry point that gets called when
    users run 'dolly' from the command line. It uses typer.run() to handle
    the CLI framework setup and delegates to main() for argument processing.
    """
    typer.run(main)
