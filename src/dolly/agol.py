import logging
import os
from pathlib import Path
from shutil import make_archive
from typing import cast

from arcgis.features import FeatureLayer, FeatureLayerCollection, Table
from arcgis.gis import GIS, Item

from dolly.internal import create_fgdb, update_agol_item
from dolly.state import set_table_hash
from dolly.summary import get_current_summary
from dolly.utils import get_secrets, get_service_from_title, retry

logger = logging.getLogger(__name__)

APP_ENVIRONMENT = os.environ["APP_ENVIRONMENT"]


def _generate_upload_title(fgdb_stem: str) -> str:
    """
    Generate title for temporary FGDB upload.

    Args:
        fgdb_stem: The stem name of the FGDB file

    Returns:
        Formatted title string for AGOL upload
    """
    title = f"dolly-carton Temporary upload: {fgdb_stem}"
    if APP_ENVIRONMENT == "dev" or APP_ENVIRONMENT == "staging":
        title += " (Test)"

    return title


def _generate_upload_tags() -> str:
    """
    Generate tags for temporary FGDB upload.

    Returns:
        Comma-separated tags string
    """
    tags = "Temp"
    if APP_ENVIRONMENT == "dev" or APP_ENVIRONMENT == "staging":
        tags += ",Test"

    return tags


def _generate_service_tags(table: str) -> str:
    """
    Generate tags for published feature service.

    Args:
        table: Table name in format schema.category.name

    Returns:
        Comma-separated tags string
    """
    category = table.split(".")[1].title()
    tags = f"UGRC,SGID,{category}"
    if APP_ENVIRONMENT == "dev" or APP_ENVIRONMENT == "staging":
        tags += ",Test"

    return tags


def _generate_service_title(published_name: str) -> str:
    """
    Generate title for published feature service.

    Args:
        published_name: The published name from AGOL items lookup

    Returns:
        Formatted title string
    """
    title = published_name
    if APP_ENVIRONMENT == "dev" or APP_ENVIRONMENT == "staging":
        title += " (Test)"

    return title


def _create_zip_from_fgdb(fgdb_path: Path) -> Path:
    """
    Create a zip file from an FGDB directory.

    Args:
        fgdb_path: Path to the FGDB directory

    Returns:
        Path to the created zip file
    """
    make_archive(
        str(fgdb_path.with_suffix("")),
        "zip",
        root_dir=fgdb_path.parent,
        base_dir=fgdb_path.name,
    )
    zip_path = fgdb_path.with_suffix(".zip")
    logger.info(f"FGDB zipped to {zip_path}")

    return zip_path


def _get_gis_connection() -> GIS:
    """
    Factory function to create a GIS connection.

    Returns:
        GIS: ArcGIS Online connection object
    """
    secrets = get_secrets()

    return GIS(
        "https://utah.maps.arcgis.com",
        username=secrets["AGOL_USERNAME"],
        password=secrets["AGOL_PASSWORD"],
    )


def _search_existing_item(title: str, gis_connection: GIS | None = None) -> list[Item]:
    """
    Search for existing AGOL items by title.

    Args:
        title: Title to search for
        gis_connection: GIS connection (optional, will create new if not provided).
                       Primarily used for testing to inject mock connections.

    Returns:
        List of matching items
    """
    if gis_connection is None:
        gis_connection = _get_gis_connection()

    try:
        return retry(
            gis_connection.content.search,
            f'title:"{title}" AND owner:{gis_connection.users.me.username}',
            item_type="File Geodatabase",
            max_items=1,
        )
    except Exception:
        logger.error(
            f"Error searching for existing gdb item with title {title}", exc_info=True
        )

        return []


def _delete_agol_item(item: Item) -> bool:
    """
    Delete an AGOL item permanently.

    Args:
        item: The AGOL item to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        result = retry(item.delete, permanent=True)
        if not result:
            logger.error(f"Failed to delete existing gdb item {item.id}")

            return False
        logger.info(f"Successfully deleted existing gdb item {item.id}")

        return True
    except Exception as error:
        raise RuntimeError(
            f"Error deleting existing gdb item with title {item.title}"
        ) from error


def _upload_item_to_agol(
    zip_path: Path, title: str, tags: str, gis_connection: GIS | None = None
) -> Item:
    """
    Upload a zip file to AGOL as a File Geodatabase item.

    Args:
        zip_path: Path to the zip file to upload
        title: Title for the uploaded item
        tags: Tags for the uploaded item
        gis_connection: GIS connection (optional, will create new if not provided).
                       Primarily used for testing to inject mock connections.

    Returns:
        The uploaded AGOL item
    """
    if gis_connection is None:
        gis_connection = _get_gis_connection()

    folders = gis_connection.content.folders
    root_folder = folders.get()
    future = retry(
        root_folder.add,
        item_properties={
            "type": "File Geodatabase",
            "title": title,
            "snippet": "Temporary upload of SGID data to AGOL",
            "tags": tags,
        },
        file=str(zip_path),
    )

    return future.result()


def zip_and_upload_fgdb(fgdb_path: Path, gis_connection: GIS | None = None) -> Item:
    """
    Zip the FGDB and upload it to AGOL.

    Args:
        fgdb_path: Path to the FGDB to zip and upload
        gis_connection: GIS connection (optional, will create new if not provided).
                       Primarily used for testing to inject mock connections.

    Returns:
        The uploaded AGOL item
    """
    zip_path = _create_zip_from_fgdb(fgdb_path)
    title = _generate_upload_title(fgdb_path.stem)
    tags = _generate_upload_tags()

    if gis_connection is None:
        gis_connection = _get_gis_connection()

    search_results = _search_existing_item(title, gis_connection)

    if len(search_results) > 0:
        logger.info(
            f"Found existing gdb item {search_results[0].id}, deleting it before uploading new gdb"
        )
        _delete_agol_item(search_results[0])

    return _upload_item_to_agol(zip_path, title, tags, gis_connection)


def _count_features_in_agol_service(service_item) -> int:
    """
    Count features in an ArcGIS Online service using the ArcGIS API.

    Args:
        service_item: ArcGIS service item (Table or FeatureLayer)

    Returns:
        Number of features in the service
    """
    try:
        #: get new reference to item to avoid stale data from AGOL cache
        if service_item.properties["type"] == "Table":
            new_item = Table.fromitem(
                Item(_get_gis_connection(), service_item.properties["serviceItemId"])
            )
        else:
            new_item = FeatureLayer.fromitem(
                Item(_get_gis_connection(), service_item.properties["serviceItemId"])
            )

        result = retry(new_item.query, return_count_only=True)

        return result
    except Exception as e:
        logger.error(f"Failed to count features in AGOL service: {e}", exc_info=True)
        return -1


def _get_service_item_from_agol(
    table: str, agol_items_lookup: dict[str, dict], gis_connection: GIS
) -> Item | None:
    """
    Get and validate an AGOL item for a given table.

    Args:
        table: Table name to get item for
        agol_items_lookup: Lookup dictionary with AGOL item information
        gis_connection: GIS connection to use

    Returns:
        The AGOL item if found, None otherwise
    """
    item_id = agol_items_lookup[table]["item_id"]
    item = retry(gis_connection.content.get, item_id)
    if item is None:
        logger.error(f"Item with ID {item_id} not found in AGOL.")

    return item


def _get_appropriate_service_layer(
    item: Item, table: str, agol_items_lookup: dict[str, dict]
) -> Table | FeatureLayer:
    """
    Get the appropriate service layer (Table or FeatureLayer) based on geometry type.

    Args:
        item: The AGOL item
        table: Table name
        agol_items_lookup: Lookup dictionary with AGOL item information

    Returns:
        Either a Table or FeatureLayer object
    """
    if agol_items_lookup[table]["geometry_type"] == "STAND ALONE":
        # table
        return Table.fromitem(item, table_id=0)
    else:
        # feature service
        return FeatureLayer.fromitem(item, layer_id=0)


def _truncate_and_append(
    service_item: Table | FeatureLayer,
    gdb_item: Item,
    service_name: str,
) -> bool:
    """
    Truncate existing data and append new data in a single retryable operation.

    This wraps both truncate and append in a single retry so that if append fails
    after a successful truncate, the retry will re-run the truncate to ensure the
    target stays clean and avoids duplicate features.

    Args:
        service_item: The Table or FeatureLayer service to update
        gdb_item: The FGDB item containing new data
        service_name: Name of the service layer in the FGDB

    Returns:
        True if the combined operation succeeded

    Raises:
        RuntimeError: If either truncate or append fails
    """

    def _worker() -> bool:
        # Do NOT use per-step retry here; the entire operation is retried as a unit
        logger.info("truncating...")
        truncate_result = cast(
            dict,
            service_item.manager.truncate(
                asynchronous=True,
                wait=True,
            ),
        )
        if truncate_result.get("status") != "Completed":
            raise RuntimeError("Failed to truncate existing data in service")

        logger.info(f"appending: {service_name}")
        append_result = service_item.append(
            item_id=gdb_item.id,
            upload_format="filegdb",
            source_table_name=service_name,
            return_messages=True,
            rollback=True,
        )
        # ArcGIS API may return either a bool or a (bool, messages) tuple
        result = (
            append_result[0]
            if isinstance(append_result, tuple)
            else bool(append_result)
        )
        if not result:
            logger.error("Append failed but did not error")
            raise RuntimeError("Append failed")

        return True

    # Retry the combined operation as a unit
    return retry(_worker)


def update_feature_services(
    gdb_item: Item,
    tables: list[str],
    agol_items_lookup: dict[str, dict],
    current_hashes: dict[str, str],
    source_counts: dict[str, int],
    gis_connection: GIS | None = None,
) -> None:
    """
    Update feature services in AGOL with new FGDB data.

    Args:
        gdb_item: The uploaded AGOL item containing the FGDB
        tables: List of table names to update
        agol_items_lookup: Lookup dictionary with AGOL item information
        current_hashes: Dictionary mapping table names to their current hashes
        source_counts: Dictionary mapping table names to their source feature counts
        gis_connection: GIS connection (optional, will create new if not provided).
                       Primarily used for testing to inject mock connections.
    """
    if gis_connection is None:
        gis_connection = _get_gis_connection()

    summary = get_current_summary()
    has_errors = False
    for table in tables:
        # Get the AGOL item for this table
        item = _get_service_item_from_agol(table, agol_items_lookup, gis_connection)
        if item is None:
            has_errors = True
            error_msg = "No entry in AGOLItems with this table name"
            logger.error(f"Failed to update feature service for {table}: {error_msg}")
            if summary:
                summary.add_table_error(table, "update", error_msg)
            continue

        try:
            # Get the appropriate service layer (Table or FeatureLayer)
            service_item = _get_appropriate_service_layer(
                item, table, agol_items_lookup
            )

            logger.info(f"Updating feature service for {table} with new FGDB data.")

            # Count features before truncation
            pre_truncate_count = _count_features_in_agol_service(service_item)
            if pre_truncate_count >= 0:
                logger.info(
                    f"📊 Target service {table} before truncation: {pre_truncate_count:,} features"
                )

            # Truncate and append as a single retryable operation
            title = agol_items_lookup[table]["published_name"]
            service_name = get_service_from_title(title)
            success = _truncate_and_append(service_item, gdb_item, service_name)

            if not success:
                has_errors = True
                error_msg = "Failed to append new data"
                logger.error(
                    f"Failed to update feature service for {table}: {error_msg}"
                )
                if summary:
                    summary.add_table_error(table, "update", error_msg)
            else:
                # Count features after append and compare with source
                post_append_count = _count_features_in_agol_service(service_item)
                if post_append_count >= 0:
                    logger.info(
                        f"📊 Target service {table} after append: {post_append_count:,} features"
                    )

                    # Check for zero features (indicates a problem)
                    if post_append_count == 0:
                        error_msg = f"Target service {table} has 0 features after append - this may indicate a data loss issue"
                        logger.error(f"📊 {error_msg}")
                        if summary:
                            summary.add_table_error(table, "zero_features", error_msg)
                    else:
                        # Check for count mismatch with source
                        source_count = source_counts.get(table, -1)
                        if source_count >= 0 and source_count != post_append_count:
                            if summary:
                                summary.add_feature_count_mismatch(
                                    table, source_count, post_append_count
                                )
                            logger.error(
                                f"📊 Feature count mismatch for {table}: Source {source_count:,} != Final {post_append_count:,}"
                            )

                logger.info(f"Successfully updated feature service for {table}")
                if summary:
                    item_id = agol_items_lookup[table]["item_id"]
                    summary.add_table_updated(table, item_id)
                set_table_hash(table, current_hashes[table])
        except Exception as e:
            logger.error(
                f"Failed to update feature service for {table}: {e}", exc_info=True
            )
            has_errors = True
            if summary:
                summary.add_table_error(table, "update", str(e))
            continue

    if not has_errors:
        logger.info("deleting temporary FGDB item")
        retry(gdb_item.delete, permanent=True)


def _create_and_publish_service(
    table: str, agol_items_lookup: dict[str, dict], gis_connection: GIS
) -> Item | None:
    """
    Create FGDB and publish it as a new feature service.

    Args:
        table: Table name to publish
        agol_items_lookup: Lookup dictionary with AGOL item information
        gis_connection: GIS connection to use

    Returns:
        The published service item if successful, None otherwise
    """
    try:
        # Create FGDB for this single table
        logger.info("Uploading FGDB")
        fgdb_path, source_counts = create_fgdb([table], agol_items_lookup)
        single_item = zip_and_upload_fgdb(fgdb_path, gis_connection)

        # Publish the FGDB as a feature service
        logger.info("Publishing feature service")
        item = cast(
            Item,
            retry(
                single_item.publish,
                publish_parameters={
                    #: use open sgid naming convention for the feature service (with category prefix) and layer/table
                    "name": fgdb_path.stem
                },
                file_type="fileGeodatabase",
            ),
        )

        # Clean up temporary FGDB item
        logger.info("deleting temporary FGDB item")
        single_item.delete(permanent=True)

        return item
    except Exception as e:
        logger.error(
            f"Failed to create and publish service for table {table}: {e}",
            exc_info=True,
        )

        return None


def _configure_published_service(
    item: Item, table: str, agol_items_lookup: dict[str, dict]
) -> bool:
    """
    Configure a published service with metadata, permissions, and settings.

    Args:
        item: The published service item to configure
        table: Table name
        agol_items_lookup: Lookup dictionary with AGOL item information

    Returns:
        True if configuration was successful, False otherwise
    """
    try:
        category = table.split(".")[1].title()
        tags = _generate_service_tags(table)
        title = _generate_service_title(agol_items_lookup[table]["published_name"])

        # Update item metadata
        retry(
            item.update,
            {
                "title": title,
                "description": "TBD",
                "snippet": "TBD",
                "tags": tags,
            },
        )

        # Enable "Allow others to export to different formats" checkbox
        manager = FeatureLayerCollection.fromitem(item).manager
        retry(manager.update_definition, {"capabilities": "Query,Extract"})

        # Move to appropriate category folder
        retry(item.move, category)

        # Set production permissions if in prod environment
        if APP_ENVIRONMENT == "prod":
            item.sharing.sharing_level = "EVERYONE"
            item.content_status = "public_authoritative"
            retry(item.protect)

        return True
    except Exception as e:
        logger.error(
            f"Failed to configure published service {item.id} for table {table}: {e}",
            exc_info=True,
        )

        return False


def publish_new_feature_services(
    tables: list[str],
    agol_items_lookup: dict[str, dict],
    current_hashes: dict[str, str],
    gis_connection: GIS | None = None,
) -> None:
    """
    Publish new feature services for the provided tables.

    Args:
        tables: List of table names to publish
        agol_items_lookup: Lookup dictionary with AGOL item information
        gis_connection: GIS connection (optional, will create new if not provided).
                       Primarily used for testing to inject mock connections.
    """
    if gis_connection is None:
        gis_connection = _get_gis_connection()

    summary = get_current_summary()
    for table in tables:
        logger.info(f"Publishing new feature service for table {table}")

        # Create FGDB and publish as feature service
        item = _create_and_publish_service(table, agol_items_lookup, gis_connection)
        if item is None:
            error_msg = "Failed to create and publish service"
            logger.error(f"Failed to publish feature service for {table}: {error_msg}")
            if summary:
                summary.add_table_error(table, "publish", error_msg)
            continue

        # Configure the published service
        success = _configure_published_service(item, table, agol_items_lookup)
        if not success:
            error_msg = "Failed to configure published service"
            logger.error(f"Failed to publish feature service for {table}: {error_msg}")
            if summary:
                summary.add_table_error(table, "publish", error_msg)
            continue

        logger.info(f"Published new feature service for {table} with item ID {item.id}")
        if summary:
            summary.add_table_published(table, item.id)
        set_table_hash(table, current_hashes[table])

        # Update the internal database with the new item ID
        update_agol_item(table, item.id)
