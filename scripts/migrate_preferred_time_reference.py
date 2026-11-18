import argparse
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from osgeo import gdal

from dolly.agol import (
    get_gis_connection,
    set_preferred_time_reference,
    update_feature_services,
    zip_and_upload_fgdb,
)
from dolly.internal import (
    _get_database_connection,
    _get_datetime_field_names,
    create_fgdb,
    get_agol_items_lookup,
    get_current_hashes,
)
from dolly.utils import retry

logger = logging.getLogger(__name__)


def migrate_existing_services(dry_run: bool = False) -> None:
    """Refresh timestamp-bearing datasets and set every service's time reference."""
    agol_items_lookup = get_agol_items_lookup()
    services: dict[str, list[str]] = {}
    for table, item_info in sorted(agol_items_lookup.items()):
        if item_info.get("item_id"):
            services.setdefault(item_info["item_id"], []).append(table)

    logger.info("Found %s existing services in the AGOLItems inventory", len(services))
    if not services:
        return

    gis_connection = None if dry_run else get_gis_connection()
    current_hashes = {} if dry_run else get_current_hashes()
    failures = []
    source = _get_database_connection()
    try:
        for item_id, tables in services.items():
            try:
                refresh_tables = []
                for table in tables:
                    fields = _get_datetime_field_names(source, table)
                    if fields:
                        refresh_tables.append(table)
                        logger.info(
                            "%s data refresh: %s (datetime fields: %s)",
                            "Would force" if dry_run else "Forcing",
                            table,
                            ", ".join(sorted(fields)),
                        )
                    else:
                        logger.info("Metadata only: %s", table)

                if dry_run:
                    logger.info("Would set preferred time reference: %s", item_id)
                    continue

                if gis_connection is None:
                    raise RuntimeError("AGOL connection is required for migration")
                item = retry(gis_connection.content.get, item_id)
                if item is None:
                    raise LookupError(f"AGOL item {item_id} was not found")

                for table in refresh_tables:
                    if table not in current_hashes:
                        raise LookupError(f"No current source hash for {table}")
                    with TemporaryDirectory(prefix="dolly-timezone-") as output:
                        fgdb_path, source_counts = create_fgdb(
                            [table],
                            agol_items_lookup,
                            output_path=Path(output) / "migration.gdb",
                        )
                        gdb_item = zip_and_upload_fgdb(fgdb_path, gis_connection)
                        updated = update_feature_services(
                            gdb_item,
                            [table],
                            agol_items_lookup,
                            current_hashes,
                            source_counts,
                            gis_connection,
                        )
                        if table not in updated:
                            raise RuntimeError(f"Data refresh failed for {table}")

                set_preferred_time_reference(item)
                logger.info("Migrated service %s", item_id)
            except Exception:
                logger.exception(
                    "Failed to migrate service %s",
                    item_id,
                )
                failures.append(item_id)
    finally:
        source.close()

    if failures:
        raise RuntimeError(
            f"Failed to migrate {len(failures)} service(s): {', '.join(failures)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Force-refresh datetime-bearing datasets from internal in UTC and "
            "set the preferred time reference on all existing Dolly services."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List metadata-only services and forced data refreshes without changes.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    gdal.UseExceptions()
    migrate_existing_services(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
