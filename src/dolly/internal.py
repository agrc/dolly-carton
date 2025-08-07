import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import cast

import pyodbc
from osgeo import gdal

from dolly.domains import (
    apply_domains_to_fields,
    create_domains_in_fgdb,
    get_domain_metadata,
    get_table_field_domains,
)
from dolly.utils import (
    FGDB_PATH,
    OUTPUT_PATH,
    get_gdal_layer_name,
    get_secrets,
    get_service_from_title,
    is_guid,
)

logger = logging.getLogger(__name__)

APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT")

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

DEV_MOCKS_PATH = Path(__file__).parent / "dev_mocks.json"


def _get_database_connection() -> pyodbc.Connection:
    """
    Factory function to create a database connection.

    Returns:
        pyodbc.Connection: Database connection object
    """

    return pyodbc.connect(CONNECTION_STRING)


def _get_gdal_connection() -> gdal.Dataset:
    """
    Factory function to create a GDAL database connection.

    Returns:
        gdal.Dataset: GDAL database connection object
    """
    #: I could not get this to work with the open_options parameter
    with gdal.config_options({"MSSQLSPATIAL_LIST_ALL_TABLES": "YES"}):
        return gdal.OpenEx(f"MSSQL:{CONNECTION_STRING}", gdal.OF_VECTOR)


def _generate_output_path(
    tables: list[str], agol_items_lookup: dict[str, dict]
) -> Path:
    """
    Generate the output FGDB path based on the tables and lookup data.

    Args:
        tables: List of table names
        agol_items_lookup: Lookup dictionary for AGOL items

    Returns:
        Path object for the output FGDB
    """
    if len(tables) == 1:
        first_title = agol_items_lookup[tables[0]]["published_name"]
        category = tables[0].split(".")[1].lower()

        return OUTPUT_PATH / f"{category}_{get_service_from_title(first_title)}.gdb"

    return FGDB_PATH


def _get_geometry_option(geometry_type: str) -> str:
    """
    Convert geometry type to GDAL geometry option.

    Args:
        geometry_type: The geometry type from the database

    Returns:
        GDAL-compatible geometry option string
    """
    if geometry_type == "POLYGON":
        return "MULTIPOLYGON"
    elif geometry_type == "POLYLINE":
        return "MULTILINESTRING"
    elif geometry_type == "STAND ALONE":
        return "NONE"
    elif geometry_type == "POINT":
        return "POINT"
    else:
        raise ValueError(f"Unknown geometry type: {geometry_type}")


def _build_change_detection_query(last_checked: datetime) -> str:
    """
    Build SQL query for retrieving updated tables from change detection.

    Args:
        last_checked: The datetime to check for updates since

    Returns:
        SQL query string
    """

    return f"""
        SELECT table_name FROM SGID.META.ChangeDetection
        WHERE last_modified > '{last_checked.strftime("%Y-%m-%d %H:%M:%S")}'
    """


def _build_update_agol_item_query(table: str, item_id: str) -> str:
    """
    Build SQL query for updating AGOL item ID.

    Args:
        table: Table name to update
        item_id: New AGOL item ID to set

    Returns:
        SQL query string
    """

    return f"""
        UPDATE SGID.META.AGOLItems
        SET AGOL_ITEM_ID = '{item_id}'
        WHERE UPPER(TABLENAME) = UPPER('{table}')
    """


def get_updated_tables(
    last_checked: datetime, connection: pyodbc.Connection | None = None
) -> list[str]:
    """
    Get a list of updated feature classes/tables since the last checked time.

    Args:
        last_checked: The datetime to check for updates since
        connection: Database connection (optional, will create new if not provided).
                   Primarily used for testing to inject mock connections.

    Returns:
        List of table names that have been updated
    """
    if APP_ENVIRONMENT == "dev" or APP_ENVIRONMENT == "staging":
        return json.loads(DEV_MOCKS_PATH.read_text(encoding="utf-8"))["updated_tables"]

    query = _build_change_detection_query(last_checked)

    # Use provided connection or create a new one
    if connection is None:
        connection = _get_database_connection()

    try:
        cursor = cast(pyodbc.Connection, connection).cursor()
        cursor.execute(query)
        updated_tables = cursor.fetchall()
        cursor.close()

        return [table[0] for table in updated_tables]
    finally:
        connection.close()


def get_agol_items_lookup(
    connection: pyodbc.Connection | None = None,
) -> dict[str, dict]:
    """
    Get a lookup dictionary between table names and AGOL item IDs.

    Args:
        connection: Database connection (optional, will create new if not provided).
                   Primarily used for testing to inject mock connections.

    Returns:
        Dictionary mapping table names to AGOL item information
    """
    if APP_ENVIRONMENT == "dev" or APP_ENVIRONMENT == "staging":
        return json.loads(DEV_MOCKS_PATH.read_text(encoding="utf-8"))[
            "agol_items_lookup"
        ]

    query = """
        SELECT TABLENAME, AGOL_ITEM_ID, AGOL_PUBLISHED_NAME, GEOMETRY_TYPE
        FROM SGID.META.AGOLItems
    """

    # Use provided connection or create a new one
    if connection is None:
        connection = _get_database_connection()

    try:
        cursor = cast(pyodbc.Connection, connection).cursor()
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
                "published_name": row[2],
                "geometry_type": row[3],
            }

        return lookup
    finally:
        connection.close()


def update_agol_item(
    table: str,
    item_id: str,
    connection: pyodbc.Connection | None = None,
) -> None:
    """
    Update the AGOL item ID for a given table in the database.

    Args:
        table: Table name to update
        item_id: New AGOL item ID to set
        connection: Database connection (optional, will create new if not provided).
                   Primarily used for testing to inject mock connections.
    """
    logger.info(f"Updating AGOL item ID for table {table} to {item_id}")

    if APP_ENVIRONMENT == "dev" or APP_ENVIRONMENT == "staging":
        logger.info(
            f"DEV MODE: Would update AGOL item ID for table {table} to {item_id}"
        )
        return

    query = _build_update_agol_item_query(table, item_id)

    # Use provided connection or create a new one
    if connection is None:
        connection = _get_database_connection()

    try:
        cursor = cast(pyodbc.Connection, connection).cursor()
        cursor.execute(query)
        connection.commit()
        cursor.close()

        logger.info(f"Successfully updated AGOL item ID for table {table}")
    finally:
        connection.close()


def _prepare_gdal_options(table: str, agol_item_info: dict) -> dict:
    """
    Prepare GDAL translation options for a table.

    Args:
        table: Table name to prepare options for
        agol_item_info: AGOL item information dictionary

    Returns:
        Dictionary containing GDAL VectorTranslate parameters
    """
    layer_name = get_gdal_layer_name(table)
    geometry_type = agol_item_info["geometry_type"]
    geometry_option = _get_geometry_option(geometry_type)
    title = agol_item_info["published_name"]

    return {
        "layers": [layer_name],
        "format": "OpenFileGDB",
        "options": [
            "-nln",
            get_service_from_title(title),
            "-nlt",
            geometry_option,
            "-a_srs",
            "EPSG:26912",
        ],
        "accessMode": "append",
    }


def _copy_table_to_fgdb(
    gdal_connection: gdal.Dataset,
    table: str,
    output_path: Path,
    agol_item_info: dict,
) -> bool:
    """
    Copy a single table to FGDB using GDAL operations.

    Args:
        gdal_connection: GDAL database connection
        table: Table name to copy
        output_path: Path to the output FGDB
        agol_item_info: AGOL item information dictionary

    Returns:
        True if copy was successful, False otherwise
    """
    logger.info(f"Copying layer {table} to FGDB.")

    try:
        gdal_options = _prepare_gdal_options(table, agol_item_info)

        gdal.VectorTranslate(
            destNameOrDestDS=str(output_path), srcDS=gdal_connection, **gdal_options
        )

        logger.info(f"Successfully copied layer {table} to FGDB.")

        return True
    except Exception as e:
        logger.error(f"Failed to copy layer {table} to FGDB. Error: {e}")

        return False


def create_fgdb(
    tables: list[str],
    agol_items_lookup: dict[str, dict],
    gdal_connection: gdal.Dataset | None = None,
) -> Path:
    """
    Create a File Geodatabase (FGDB) from the specified tables.

    Args:
        tables: List of table names to include in the FGDB
        agol_items_lookup: Lookup dictionary with AGOL item information
        gdal_connection: GDAL database connection (optional, will create new if not provided).
                        Primarily used for testing to inject mock connections.

    Returns:
        Path to the created FGDB
    """
    # Use provided connection or create a new one
    if gdal_connection is None:
        internal = _get_gdal_connection()
    else:
        internal = gdal_connection

    try:
        logger.debug(f"Total layers found in internal: {internal.GetLayerCount()}")

        if len(tables) == 0:
            raise ValueError("No tables provided to create FGDB.")

        output_gdb_path = _generate_output_path(tables, agol_items_lookup)

        # Copy tables first to create the FGDB structure
        tables_copied = False
        for table in tables:
            success = _copy_table_to_fgdb(
                internal, table, output_gdb_path, agol_items_lookup[table]
            )
            if success:
                tables_copied = True

        if not tables_copied:
            raise Exception("FGDB creation failed for all tables.")

        db_connection = _get_database_connection()
        try:
            # Get field-domain mappings for each table first
            table_field_domains = {}
            used_domain_names = set()

            for table in tables:
                field_domains = get_table_field_domains(table, db_connection)
                if field_domains:
                    # Use the service name as the layer name in FGDB
                    service_name = get_service_from_title(
                        agol_items_lookup[table]["published_name"]
                    )
                    table_field_domains[service_name] = field_domains
                    # Collect domain names used by this table
                    used_domain_names.update(field_domains.values())

            # Get all domain metadata and filter to only the ones actually used
            if used_domain_names:
                logger.info(
                    f"Found {len(used_domain_names)} unique domains used by tables"
                )
                all_domains = get_domain_metadata(db_connection)
                # Filter to only include domains that are actually used by the tables
                domains = {
                    name: info
                    for name, info in all_domains.items()
                    if name in used_domain_names
                }
                logger.info(
                    f"Filtered to {len(domains)} domains for the specified tables"
                )
            else:
                domains = {}
                logger.info("No domain associations found for the specified tables")

            # Create domains in FGDB if any were found
            if domains:
                logger.info(f"Creating {len(domains)} domains in FGDB")
                create_domains_in_fgdb(domains, str(output_gdb_path))
            else:
                logger.info("No domains found for the specified tables")

            # Apply domain associations to fields
            if table_field_domains:
                logger.info("Applying domain associations to copied tables")
                apply_domains_to_fields(str(output_gdb_path), table_field_domains)

        finally:
            db_connection.close()

        return output_gdb_path
    finally:
        if internal is not None:
            internal = None
