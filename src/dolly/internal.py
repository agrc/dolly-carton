import logging
import os
from datetime import datetime
from pathlib import Path
from typing import cast

import pyodbc
from osgeo import gdal

from dolly.utils import FGDB_PATH, OUTPUT_PATH, get_fgdb_name, get_secrets

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
        internal = gdal.OpenEx(f"MSSQL:{CONNECTION_STRING}", gdal.OF_VECTOR)

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
