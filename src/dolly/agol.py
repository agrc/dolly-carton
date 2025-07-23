import logging
import os
from pathlib import Path
from shutil import make_archive
from typing import cast

from arcgis.features import FeatureLayer, FeatureLayerCollection, Table
from arcgis.gis import GIS, Item

from dolly.internal import create_fgdb, update_agol_item
from dolly.utils import get_fgdb_name, get_secrets, is_guid, retry

logger = logging.getLogger(__name__)

# Get environment setting
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "dev")

secrets = get_secrets()
gis = GIS(
    "https://utah.maps.arcgis.com",
    username=secrets.get("AGOL_USERNAME"),
    password=secrets.get("AGOL_PASSWORD"),
)


def zip_and_upload_fgdb(fgdb_path: Path) -> Item:
    """
    Zip the FGDB and upload it to AGOL.
    This function can be expanded to handle the actual upload process.
    """

    make_archive(
        str(fgdb_path.with_suffix("")),
        "zip",
        root_dir=fgdb_path.parent,
        base_dir=fgdb_path.name,
    )
    zip_path = fgdb_path.with_suffix(".zip")

    logger.info(f"FGDB zipped to {zip_path}")

    title = f"dolly-carton Temporary upload: {fgdb_path.stem}"
    item_type = "File Geodatabase"
    search_results = []
    try:
        search_results = retry(
            gis.content.search,
            f'title:"{title}" AND owner:{gis.users.me.username}',
            item_type=item_type,
            max_items=1,
        )
    except Exception:
        logger.error(f"Error searching for existing gdb item with title {title}")

    if len(search_results) > 0:
        logger.info(
            f"Found existing gdb item {search_results[0].id}, deleting it before uploading new gdb"
        )
        try:
            result = retry(search_results[0].delete, permanent=True)
            if not result:
                logger.error(
                    f"Failed to delete existing gdb item {search_results[0].id}"
                )
        except Exception as error:
            raise RuntimeError(
                f"Error deleting existing gdb item with title {title}"
            ) from error

    folders = gis.content.folders
    root_folder = folders.get()
    future = retry(
        root_folder.add,
        item_properties={
            "type": item_type,
            "title": title,
            "snippet": "Temporary upload of SGID data to AGOL",
        },
        file=str(zip_path),
    )

    return future.result()


def update_feature_services(
    gdb_item: Item, tables: list[str], agol_items_lookup: dict[str, dict]
) -> None:
    """
    Update the feature services in AGOL with the new FGDB data.
    """
    #: TODO handle missing agol item lookup entry

    has_errors = False
    for table in tables:
        item_id = agol_items_lookup.get(table, {}).get("item_id")
        if item_id is not None and not is_guid(item_id):
            logger.warning(
                f"Skipping table {table} as it does not have a valid AGOL item ID."
            )
            continue
        else:
            item = retry(gis.content.get, item_id)
            if item is None:
                logger.error(f"Item with ID {item_id} not found in AGOL.")
                has_errors = True
                continue

            try:
                if (
                    agol_items_lookup.get(table, {}).get("geometry_type")
                    == "STAND ALONE"
                ):
                    # table
                    service_item = Table.fromitem(item, table_id=0)
                else:
                    # feature service
                    service_item = FeatureLayer.fromitem(item, layer_id=0)

                logger.info(f"Updating feature service for {table} with new FGDB data.")
                logger.info("truncating...")
                truncate_result = retry(
                    service_item.manager.truncate,
                    asynchronous=True,
                    wait=True,
                )

                if truncate_result["status"] != "Completed":
                    raise RuntimeError(
                        f"Failed to truncate existing data in itemid {service_item.itemid}"
                    )

                logger.info("appending...")
                result, messages = retry(
                    service_item.append,
                    item_id=gdb_item.id,
                    upload_format="filegdb",
                    source_table_name=get_fgdb_name(table),
                    return_messages=True,
                    rollback=True,
                )
                if not result:
                    logger.error("Append failed but did not error")
                    has_errors = True
            except Exception as e:
                logger.error(f"Failed to update feature service for {table}: {e}")
                has_errors = True
                continue

    if not has_errors:
        logger.info("deleting temporary FGDB item")
        retry(gdb_item.delete, permanent=True)


def publish_new_feature_services(
    tables: list[str], agol_items_lookup: dict[str, dict]
) -> None:
    """
    Publish new feature services for the provided tables.
    """

    for table in tables:
        logger.info(f"Publishing new feature service for table {table}")
        try:
            #: when publishing we need one FGDB per table
            fgdb_path = create_fgdb(
                [table], agol_items_lookup, table_name=table.split(".")[-1]
            )
            single_item = zip_and_upload_fgdb(fgdb_path)
        except Exception as e:
            logger.error(f"Failed to create FGDB for table {table}: {e}")
            continue

        try:
            item = cast(
                Item,
                retry(
                    single_item.publish,
                    publish_parameters={
                        #: use open sgid naming convention for the feature service (with category prefix) and layer/table
                        "name": get_fgdb_name(table),
                    },
                    file_type="fileGeodatabase",
                ),
            )
        except Exception as e:
            logger.error(f"Failed to publish feature service for table {table}: {e}")
            continue

        try:
            category = table.split(".")[1].title()
            tags = f"UGRC,SGID,{category}"
            title = agol_items_lookup.get(table, {}).get("published_name", item.title)

            if APP_ENVIRONMENT == "dev":
                tags += ",Test"
                title += " (Test)"

            retry(
                item.update,
                {
                    "title": title,
                    "description": "TBD",
                    "snippet": "TBD",
                    "tags": tags,
                },
            )
            #: enable "Allow others to export to different formats" checkbox
            manager = FeatureLayerCollection.fromitem(item).manager
            retry(manager.update_definition, {"capabilities": "Query,Extract"})
            retry(item.move, category)

            if APP_ENVIRONMENT == "prod":
                item.sharing.sharing_level = "EVERYONE"
                retry(item.protect)
                # TODO: authoritative?
        except Exception as e:
            logger.error(f"Failed to update item {item.id} for table {table}: {e}")
            continue

        logger.info(f"Published new feature service for {table} with item ID {item.id}")

        update_agol_item(table, item.id)

        logger.info("deleting temporary FGDB item")
        single_item.delete(permanent=True)
