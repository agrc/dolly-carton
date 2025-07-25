import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import cast

import pyodbc
from osgeo import gdal

from dolly.utils import (
    FGDB_PATH,
    OUTPUT_PATH,
    get_gdal_layer_name,
    get_secrets,
    get_service_from_title,
    is_guid,
)

logger = logging.getLogger(__name__)

# Get environment setting
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "dev")

secrets = get_secrets()
host = secrets.get("INTERNAL_HOST")
database = secrets.get("INTERNAL_DATABASE")
username = secrets.get("INTERNAL_USERNAME")
password = secrets.get("INTERNAL_PASSWORD")

CONNECTION_STRING = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={host};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    f"TrustServerCertificate=yes;"
)
internal_connection = pyodbc.connect(CONNECTION_STRING)

DEV_MOCKS_PATH = Path(__file__).parent / "dev_mocks.json"


def get_updated_tables(last_checked: datetime) -> list[str]:
    """
    Get a list of updated feature classes/tables since the last checked time.
    """
    if APP_ENVIRONMENT == "dev":
        return json.loads(DEV_MOCKS_PATH.read_text(encoding="utf-8"))["updated_tables"]

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
        return json.loads(DEV_MOCKS_PATH.read_text(encoding="utf-8"))[
            "agol_items_lookup"
        ]

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
        # ignore row if AGOL_ITEM_ID has a value but it's not a valid GUID
        # these are datasets that are hosted by another agency and not published by us
        if row[1] is not None and not is_guid(row[1]):
            continue
        lookup[row[0].lower()] = {
            "item_id": row[1],
            "geometry_type": row[2],
            "published_name": row[3],
        }

    return lookup


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


def create_fgdb(
    tables: list[str],
    agol_items_lookup: dict[str, dict],
    table_name: None | str = None,
) -> Path:
    #: I could not get this to work with the open_options parameter
    with gdal.config_options({"MSSQLSPATIAL_LIST_ALL_TABLES": "YES"}):
        internal = gdal.OpenEx(f"MSSQL:{CONNECTION_STRING}", gdal.OF_VECTOR)

    logger.debug(f"Total layers found in internal: {internal.GetLayerCount()}")

    if len(tables) == 0:
        raise ValueError("No tables provided to create FGDB.")

        # Get the first table's published name for the FGDB name
    first_title = agol_items_lookup[tables[0]]["published_name"]
    output_gdb_path = FGDB_PATH
    if len(tables) == 1:
        category = tables[0].split(".")[1].lower()
        output_gdb_path = (
            OUTPUT_PATH / f"{category}_{get_service_from_title(first_title)}.gdb"
        )

    tables_copied = False
    for table in tables:
        logger.info(f"Copying layer {table} to FGDB.")

        layer_name = get_gdal_layer_name(table)
        geometry_type = agol_items_lookup[table]["geometry_type"]
        geometry_option = None
        if geometry_type == "POLYGON":
            geometry_option = "MULTIPOLYGON"
        elif geometry_type == "POLYLINE":
            geometry_option = "MULTILINESTRING"
        elif geometry_type == "STAND ALONE":
            geometry_option = "NONE"
        else:
            geometry_option = geometry_type

        title = agol_items_lookup[table]["published_name"]

        try:
            gdal.VectorTranslate(
                destNameOrDestDS=str(output_gdb_path),
                srcDS=internal,
                format="OpenFileGDB",
                layers=[layer_name],
                #: table name controls the name of the layer in the feature service when publishing for the first time
                options=[
                    "-nln",
                    table_name if table_name else get_service_from_title(title),
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
