import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from shutil import make_archive
from typing import cast

import pyodbc
from arcgis.features import FeatureLayer, FeatureLayerCollection, Table
from arcgis.gis import GIS, Item
from osgeo import gdal

from dolly.log import setup_logging
from dolly.utils import get_secrets, is_guid, retry

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("output")
FGDB_PATH = OUTPUT_PATH / "upload.gdb"

secrets = get_secrets()
gis = GIS(
    "https://utah.maps.arcgis.com",
    username=secrets.get("AGOL_USERNAME"),
    password=secrets.get("AGOL_PASSWORD"),
)

# Get environment setting
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "dev")

#: throw exceptions on errors rather than returning None
gdal.UseExceptions()

host = secrets.get("INTERNAL_HOST")
database = secrets.get("INTERNAL_DATABASE")
username = secrets.get("INTERNAL_USERNAME")
password = secrets.get("INTERNAL_PASSWORD")

internal_connection_string = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={host};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    f"TrustServerCertificate=yes;"
)
internal_connection = pyodbc.connect(internal_connection_string)


def get_last_checked() -> datetime:
    """
    Get the last time the change detection was checked.
    This could be stored in a file, database, or any other persistent storage.
    """

    # return yesterday
    #: todo - convert this to some sort of state, firestore or cloud storage?
    return datetime.now() - timedelta(days=1)


def get_updated_tables(last_checked: datetime) -> list[str]:
    """
    Get a list of updated feature classes/tables since the last checked time.
    """
    if APP_ENVIRONMENT == "dev":
        # Return hardcoded test data for development
        return [
            "sgid.environment.deqmap_tier2rptyr",
            "sgid.society.cemeteries",
            "sgid.boundaries.municipalities",
        ]

    # connect to sql database and query the SGID.META.ChangeDetection table
    query = f"""
        SELECT table_name FROM SGID.META.ChangeDetection
        WHERE last_modified > '{last_checked.strftime("%Y-%m-%d %H:%M:%S")}'
    """

    # Execute the query and fetch results using
    cursor = cast(pyodbc.Connection, internal_connection).cursor()
    cursor.execute(query)
    updated_tables = cursor.fetchall()
    cursor.close()

    return [table[0] for table in updated_tables]


def get_agol_items_lookup() -> dict[str, dict]:
    """
    Get a lookup dictionary between table names and AGOL item IDs.
    """
    if APP_ENVIRONMENT == "dev":
        # Return hardcoded test data for development
        return {
            "sgid.society.cemeteries": {
                "item_id": None,
                "geometry_type": "POINT",
                "published_name": "Utah Cemeteries",
            },
            "sgid.boundaries.municipalities": {
                "item_id": "e682d8db7c4f40cb98b7a55f2fd4d176",
                "geometry_type": "POLYGON",
                "published_name": "Utah Municipalities",
            },
            "sgid.environment.deqmap_tier2rptyr": {
                "item_id": "984b6ce3308f4630a9f996694d95ee2a",
                "geometry_type": "STAND ALONE",
                "published_name": "Utah DEQ Map Tier 2 Report Year",
            },
        }

    query = """
        SELECT TABLENAME, AGOL_ITEM_ID, AGOL_PUBLISHED_NAME, GEOMETRY_TYPE
        FROM SGID.META.AGOLItems
    """

    # Execute the query and fetch results using
    cursor = cast(pyodbc.Connection, internal_connection).cursor()
    cursor.execute(query)
    rows = cursor.fetchall()

    cursor.close()

    lookup = {}
    for row in rows:
        lookup[row[0].lower()] = {
            "item_id": row[1],
            "geometry_type": row[2],
            "published_name": row[3],
        }

    return lookup


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


def get_fgdb_name(table: str) -> str:
    """
    Get the FGDB name for a given table.
    """
    # Remove the 'sgid.' prefix and replace '.' with '_'
    """
    TODO - this determines the name of the feature service when publishing for the first time
    It does not match our existing convention. It outputs something like this: society_cemeteries,
    whereas our current convention is to use the table name as is, like "Cemeteries".

    TODO - branch on dev env and add a suffix
    """
    return table[5:].replace(".", "_").lower()


def create_fgdb(
    tables: list[str],
    agol_items_lookup: dict[str, dict],
    table_name: None | str = None,
) -> Path:
    table_name_map = {}
    non_spatial_table_names = []
    for table in tables:
        parts = table.split(".")
        db_table_name = f"{parts[1].title()}.{parts[2].upper()}"
        table_name_map[table] = db_table_name

        if agol_items_lookup.get(table, {}).get("geometry_type") == "STAND ALONE":
            non_spatial_table_names.append(db_table_name)

    #: I could not get this to work with the open_options parameter
    with gdal.config_options({"MSSQLSPATIAL_LIST_ALL_TABLES": "YES"}):
        internal = gdal.OpenEx(f"MSSQL:{internal_connection_string}", gdal.OF_VECTOR)

    logger.debug(f"Total layers found in internal: {internal.GetLayerCount()}")

    if len(tables) == 0:
        raise ValueError("No tables provided to create FGDB.")

    output_gdb_path = (
        FGDB_PATH
        if len(tables) > 1
        else OUTPUT_PATH / f"{get_fgdb_name(tables[0])}.gdb"
    )

    tables_copied = False
    for table in tables:
        logger.info(f"Copying layer {table} to FGDB.")

        layer_to_copy = table_name_map.get(table)

        geometry_type = agol_items_lookup.get(table, {}).get("geometry_type")
        geometry_option = None
        if geometry_type == "POLYGON":
            geometry_option = "MULTIPOLYGON"
        elif geometry_type == "POLYLINE":
            geometry_option = "MULTILINESTRING"
        elif geometry_type == "STAND ALONE":
            geometry_option = "NONE"
        else:
            geometry_option = geometry_type

        try:
            gdal.VectorTranslate(
                destNameOrDestDS=str(output_gdb_path),
                srcDS=internal,
                format="OpenFileGDB",
                layers=[layer_to_copy],
                #: table name controls the name of the layer in the feature service when publishing for the first time
                options=[
                    "-nln",
                    table_name if table_name else get_fgdb_name(table),
                    "-nlt",
                    geometry_option,
                ],
                accessMode="append",
            )
            logger.info(f"Successfully copied layer {table} to FGDB.")
            tables_copied = True
        except Exception as e:
            logger.error(f"Failed to copy layer {table} to FGDB. Error: {e}")

    internal = None

    if not tables_copied:
        raise Exception("FGDB creation failed for all tables.")

    return output_gdb_path


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


def update_agol_item(table: str, item_id: str) -> None:
    """
    Update the AGOL item ID for a given table in the database.
    """
    logger.info(f"Updating AGOL item ID for table {table} to {item_id}")
    # query = f"""
    # UPDATE SGID.META.AGOLItems
    # SET AGOL_ITEM_ID = '{item_id}'
    # WHERE TABLENAME = '{table}'
    # """

    # # Execute the query using
    # cursor = cast(pyodbc.Connection, internal_connection).cursor()
    # cursor.execute(query)
    # internal_connection.commit()
    # cursor.close()


def update_feature_services(
    gdb_item: Item, tables: list[str], agol_items_lookup: dict[str, dict]
) -> None:
    """
    Update the feature services in AGOL with the new FGDB data.
    """
    #: TODO handle missing agol item lookup entry

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
                raise Exception(f"Item with ID {item_id} not found in AGOL.")

            if agol_items_lookup.get(table, {}).get("geometry_type") == "STAND ALONE":
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
                raise RuntimeError("Append failed but did not error")

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
        #: when publishing we need one FGDB per table
        fgdb_path = create_fgdb(
            [table], agol_items_lookup, table_name=table.split(".")[-1]
        )
        single_item = zip_and_upload_fgdb(fgdb_path)

        item = cast(
            Item,
            retry(
                single_item.publish,
                publish_parameters={
                    "name": get_fgdb_name(table),
                },
                file_type="fileGeodatabase",
            ),
        )

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

        logger.info(f"Published new feature service for {table} with item ID {item.id}")

        update_agol_item(table, item.id)

        logger.info("deleting temporary FGDB item")
        single_item.delete(permanent=True)


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
