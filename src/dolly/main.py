import logging
from datetime import datetime, timedelta

from osgeo import gdal

from dolly.agol import (
    publish_new_feature_services,
    update_feature_services,
    zip_and_upload_fgdb,
)
from dolly.internal import create_fgdb, get_agol_items_lookup, get_updated_tables
from dolly.log import setup_logging
from dolly.utils import OUTPUT_PATH

logger = logging.getLogger(__name__)

#: throw exceptions on errors rather than returning None
gdal.UseExceptions()


def get_last_checked() -> datetime:
    """
    Get the last time the change detection was checked.
    This could be stored in a file, database, or any other persistent storage.
    """

    # return yesterday
    #: todo - convert this to some sort of state, firestore or cloud storage?
    return datetime.now() - timedelta(days=1)


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
                item.unlink()

    logger.info("Cleaned up temporary files.")


def main() -> None:
    setup_logging()
    clean_up()

    last_checked = get_last_checked()
    logger.info(f"Last checked: {last_checked}")

    updated_tables = get_updated_tables(last_checked)
    logger.info(f"Updated tables: {updated_tables}")

    if not updated_tables:
        logger.info("No updated tables found.")
        return

    agol_items_lookup = get_agol_items_lookup()

    #: separate out items that do not have a valid AGOL item ID
    updated_tables_with_existing_services = [
        table
        for table in updated_tables
        if agol_items_lookup.get(table, {}).get("item_id") is not None
    ]
    updated_tables_without_existing_services = [
        table
        for table in updated_tables
        if agol_items_lookup.get(table, {}).get("item_id") is None
    ]

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
