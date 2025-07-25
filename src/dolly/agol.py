import logging
import os
from pathlib import Path
from shutil import make_archive
from typing import cast

from arcgis.features import FeatureLayer, FeatureLayerCollection, Table
from arcgis.gis import GIS, Item

from dolly.internal import create_fgdb, update_agol_item
from dolly.utils import get_secrets, get_service_from_title, retry

logger = logging.getLogger(__name__)

# Get environment setting
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "dev")


def _generate_upload_title(fgdb_stem: str) -> str:
    """
    Generate title for temporary FGDB upload.

    Args:
        fgdb_stem: The stem name of the FGDB file

    Returns:
        Formatted title string for AGOL upload
    """
    title = f"dolly-carton Temporary upload: {fgdb_stem}"
    if APP_ENVIRONMENT == "dev":
        title += " (Test)"

    return title


def _generate_upload_tags() -> str:
    """
    Generate tags for temporary FGDB upload.

    Returns:
        Comma-separated tags string
    """
    tags = "Temporary,Dolly-Carton"
    if APP_ENVIRONMENT == "dev":
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
    if APP_ENVIRONMENT == "dev":
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
    if APP_ENVIRONMENT == "dev":
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
        username=secrets.get("AGOL_USERNAME"),
        password=secrets.get("AGOL_PASSWORD"),
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
        logger.error(f"Error searching for existing gdb item with title {title}")

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


def _truncate_service_data(service_item: Table | FeatureLayer) -> bool:
    """
    Truncate all existing data from a service.

    Args:
        service_item: The Table or FeatureLayer service to truncate

    Returns:
        True if truncation was successful, False otherwise

    Raises:
        RuntimeError: If truncation fails
    """
    logger.info("truncating...")
    truncate_result = retry(
        service_item.manager.truncate,
        asynchronous=True,
        wait=True,
    )

    if truncate_result["status"] != "Completed":
        raise RuntimeError("Failed to truncate existing data in service")

    return True


def _append_new_data_to_service(
    service_item: Table | FeatureLayer,
    gdb_item: Item,
    service_name: str,
) -> bool:
    """
    Append new data from FGDB to a service.

    Args:
        service_item: The Table or FeatureLayer service to update
        gdb_item: The FGDB item containing new data
        service_name: Name of the service layer in the FGDB

    Returns:
        True if append was successful, False otherwise
    """
    logger.info(f"appending: {service_name}")
    result, messages = retry(
        service_item.append,
        item_id=gdb_item.id,
        upload_format="filegdb",
        source_table_name=service_name,
        return_messages=True,
        rollback=True,
    )
    if not result:
        logger.error("Append failed but did not error")

        return False

    return True


def update_feature_services(
    gdb_item: Item,
    tables: list[str],
    agol_items_lookup: dict[str, dict],
    gis_connection: GIS | None = None,
) -> None:
    """
    Update feature services in AGOL with new FGDB data.

    Args:
        gdb_item: The uploaded AGOL item containing the FGDB
        tables: List of table names to update
        agol_items_lookup: Lookup dictionary with AGOL item information
        gis_connection: GIS connection (optional, will create new if not provided).
                       Primarily used for testing to inject mock connections.
    """
    #: TODO handle missing agol item lookup entry

    if gis_connection is None:
        gis_connection = _get_gis_connection()

    has_errors = False
    for table in tables:
        # Get the AGOL item for this table
        item = _get_service_item_from_agol(table, agol_items_lookup, gis_connection)
        if item is None:
            has_errors = True
            continue

        try:
            # Get the appropriate service layer (Table or FeatureLayer)
            service_item = _get_appropriate_service_layer(
                item, table, agol_items_lookup
            )

            logger.info(f"Updating feature service for {table} with new FGDB data.")

            # Truncate existing data
            _truncate_service_data(service_item)

            # Append new data from FGDB
            title = agol_items_lookup[table]["published_name"]
            service_name = get_service_from_title(title)
            success = _append_new_data_to_service(service_item, gdb_item, service_name)

            if not success:
                has_errors = True
        except Exception as e:
            logger.error(f"Failed to update feature service for {table}: {e}")
            has_errors = True
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
        fgdb_path = create_fgdb(
            [table], agol_items_lookup, table_name=table.split(".")[-1]
        )
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
        logger.error(f"Failed to create and publish service for table {table}: {e}")

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
            f"Failed to configure published service {item.id} for table {table}: {e}"
        )

        return False


def publish_new_feature_services(
    tables: list[str],
    agol_items_lookup: dict[str, dict],
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

    for table in tables:
        logger.info(f"Publishing new feature service for table {table}")

        # Create FGDB and publish as feature service
        item = _create_and_publish_service(table, agol_items_lookup, gis_connection)
        if item is None:
            continue

        # Configure the published service
        success = _configure_published_service(item, table, agol_items_lookup)
        if not success:
            continue

        logger.info(f"Published new feature service for {table} with item ID {item.id}")

        # Update the internal database with the new item ID
        update_agol_item(table, item.id)
