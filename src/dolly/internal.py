import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from textwrap import dedent
from typing import cast
from zoneinfo import ZoneInfo

import pyodbc
from osgeo import gdal, ogr

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

APP_ENVIRONMENT = os.environ["APP_ENVIRONMENT"]

secrets = get_secrets()
host = secrets["INTERNAL_HOST"]
database = secrets["INTERNAL_DATABASE"]
username = secrets["INTERNAL_USERNAME"]
password = secrets["INTERNAL_PASSWORD"]

CONNECTION_STRING = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={host};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    f"TrustServerCertificate=yes;"
)

DEV_MOCKS_PATH = Path(__file__).parent / "dev_mocks.json"
SOURCE_TIME_ZONE = ZoneInfo("America/Denver")


def _get_database_connection() -> pyodbc.Connection:
    """
    Factory function to create a database connection.

    Returns:
        pyodbc.Connection: Database connection object
    """

    return pyodbc.connect(CONNECTION_STRING)


def _get_internal_connection() -> Path:
    """
    Factory function to create an .sde connection file for ArcPy.

    Returns:
        Path: Path to the .sde connection file
    """
    import arcpy

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    sde_path = OUTPUT_PATH / "internal.sde"
    if not sde_path.exists():
        arcpy.management.CreateDatabaseConnection(
            out_folder_path=str(OUTPUT_PATH),
            out_name="internal.sde",
            database_platform="SQL_SERVER",
            instance=host,
            account_authentication="DATABASE_AUTH",
            username=username,
            password=password,
            database=database,
        )

    return sde_path


def _generate_output_path(
    tables: list[str],
    agol_items_lookup: dict[str, dict],
    batch_index: int | None = None,
) -> Path:
    """
    Generate the output FGDB path based on the tables and lookup data.

    Args:
        tables: List of table names
        agol_items_lookup: Lookup dictionary for AGOL items
        batch_index: Optional batch number (1-based) used to produce unique FGDB names
                     when processing multiple batches of tables.

    Returns:
        Path object for the output FGDB
    """
    if len(tables) == 1:
        first_title = agol_items_lookup[tables[0]]["published_name"]
        category = tables[0].split(".")[1].lower()

        return OUTPUT_PATH / f"{category}_{get_service_from_title(first_title)}.gdb"

    if batch_index is not None:
        return OUTPUT_PATH / f"upload_{batch_index}.gdb"

    return FGDB_PATH


def _get_geometry_option(geometry_type: str) -> str:
    """
    Convert geometry type to GDAL geometry option.

    Args:
        geometry_type: The geometry type from the database

    Returns:
        GDAL-compatible geometry option string
    """
    if geometry_type.upper() == "POLYGON":
        return "MULTIPOLYGON"
    elif geometry_type.upper() == "POLYLINE":
        return "MULTILINESTRING"
    elif geometry_type.upper() == "STAND ALONE":
        return "NONE"
    elif geometry_type.upper() == "POINT":
        return "POINT"
    else:
        raise ValueError(f"Unknown geometry type: {geometry_type}")


def _build_change_detection_hashes_query() -> str:
    """Build SQL query to retrieve current table hashes from ChangeDetection.

    Returns:
        SQL query string selecting table_name and hash.
    """

    return dedent(
        """
        SELECT table_name, hash FROM SGID.META.ChangeDetection
    """
    )


def _build_update_agol_item_query(table: str, item_id: str) -> str:
    """
    Build SQL query for updating AGOL item ID.

    Args:
        table: Table name to update
        item_id: New AGOL item ID to set

    Returns:
        SQL query string
    """

    return dedent(f"""
        UPDATE SGID.META.AGOLItems
        SET AGOL_ITEM_ID = '{item_id}'
        WHERE UPPER(TABLENAME) = UPPER('{table}')
    """)


def get_current_hashes(
    connection: pyodbc.Connection | None = None,
) -> dict[str, str]:
    """Retrieve current hashes for all tables from ChangeDetection.

    Args:
        connection: Optional injected DB connection (testing).

    Returns:
        Mapping of table name (lower-case) -> hash string.
    """
    if APP_ENVIRONMENT in {"dev", "staging"}:
        # Derive synthetic hashes for dev updated tables so logic exercises paths
        data = json.loads(DEV_MOCKS_PATH.read_text(encoding="utf-8"))
        tables = data.get("updated_tables", [])

        return {t.lower(): f"dev-hash-{i}" for i, t in enumerate(tables)}

    query = _build_change_detection_hashes_query()

    if connection is None:
        connection = _get_database_connection()

    try:
        cursor = cast(pyodbc.Connection, connection).cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        return {row[0].lower(): str(row[1]) for row in rows}
    finally:
        connection.close()


def determine_updated_tables(
    stored_hashes: dict[str, str], current_hashes: dict[str, str]
) -> list[str]:
    """Determine which tables need processing based on hash diffs.

    A table needs processing if:
      - It's new (not in stored_hashes)
      - Its hash value differs from the stored one

    Args:
        stored_hashes: Previously processed hashes from Firestore.
        current_hashes: Current hashes from ChangeDetection.

    Returns:
        List of fully qualified table names needing processing (as keys present in current_hashes).
    """
    updated: list[str] = []
    for table, hash in current_hashes.items():
        if table not in stored_hashes or stored_hashes[table] != hash:
            updated.append(table)

    return updated


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

    query = dedent("""
        SELECT TABLENAME, AGOL_ITEM_ID, AGOL_PUBLISHED_NAME, GEOMETRY_TYPE
        FROM SGID.META.AGOLItems
    """)

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


def _count_features_in_internal_table(
    table: str, connection: pyodbc.Connection | None = None
) -> int:
    """
    Count features in an internal database table using SQL.

    Args:
        table: Table name in format "sgid.schema.table"
        connection: Database connection (optional, will create new if not provided)

    Returns:
        Number of features in the table
    """
    if connection is None:
        connection = _get_database_connection()

    try:
        # Convert table name to SQL format (SGID.Schema.Table)
        parts = table.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"Table name '{table}' must be in format 'sgid.schema.table'"
            )

        sql_table_name = f"{parts[0].upper()}.{parts[1].title()}.{parts[2].title()}"
        query = f"SELECT COUNT(*) FROM {sql_table_name}"

        cursor = connection.cursor()
        cursor.execute(query)
        count = cursor.fetchone()[0]
        cursor.close()

        return count
    except Exception:
        logger.exception(f"Failed to count features in table {table}")
        return -1
    finally:
        if connection:
            connection.close()


def _count_features_in_fgdb_layer(fgdb_path, layer_name: str) -> int:
    """
    Count features in a File Geodatabase layer using GDAL.

    Args:
        fgdb_path: Path to the File Geodatabase
        layer_name: Name of the layer within the FGDB

    Returns:
        Number of features in the layer
    """
    try:
        # Open the FGDB using GDAL
        dataset = gdal.OpenEx(str(fgdb_path), gdal.OF_VECTOR)
        if dataset is None:
            logger.error(f"Failed to open FGDB at {fgdb_path}")
            return -1

        # Get the layer by name
        layer = dataset.GetLayerByName(layer_name)
        if layer is None:
            logger.error(f"Layer {layer_name} not found in FGDB {fgdb_path}")
            return -1

        count = layer.GetFeatureCount()

        # Clean up
        layer = None
        dataset = None

        return count
    except Exception:
        logger.exception(f"Failed to count features in FGDB layer {layer_name}")
        return -1


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
            "-nln",  #: new layer name
            get_service_from_title(title),
            "-nlt",  #: new layer type
            geometry_option,
            "-a_srs",  #: assign spatial reference system
            "EPSG:26912",
        ],
        "accessMode": "append",
    }


def _copy_table_to_fgdb(
    internal: Path,
    table: str,
    output_path: Path,
    agol_item_info: dict,
) -> bool:
    """
    Copy a single table to FGDB using ArcPy and release its workspace cache.

    Args:
        internal: Path to the internal SQL Server connection file
        table: Table name to copy
        output_path: Path to the output FGDB
        agol_item_info: AGOL item information dictionary

    Returns:
        Success status boolean
    """
    logger.info(f"Copying layer {table} to FGDB.")

    try:
        import arcpy

        try:
            datetime_field_names = {
                field.name
                for field in arcpy.ListFields(str(internal / table))
                if field.type == "Date"
            }

            if not arcpy.Exists(str(output_path)):
                logger.debug(f"Creating FGDB at {output_path}")
                arcpy.management.CreateFileGDB(
                    out_folder_path=str(output_path.parent),
                    out_name=output_path.name,
                )

            if agol_item_info["geometry_type"].upper() == "STAND ALONE":
                logger.debug(
                    f"Using arcpy to copy table {table} to FGDB at {output_path}"
                )
                arcpy.conversion.TableToTable(
                    str(internal / table),
                    str(output_path),
                    get_service_from_title(agol_item_info["published_name"]),
                )
            else:
                logger.debug(f"Using arcpy to project {table} to FGDB at {output_path}")
                arcpy.management.Project(
                    str(internal / table),
                    str(
                        output_path
                        / get_service_from_title(agol_item_info["published_name"])
                    ),
                    out_coor_system=arcpy.SpatialReference(3857),
                    transform_method="NAD_1983_To_WGS_1984_5",
                ),
        finally:
            # ArcPy can retain schema locks after geoprocessing tools return.
            arcpy.management.ClearWorkspaceCache(str(output_path))

        layer_name = get_service_from_title(agol_item_info["published_name"])
        if datetime_field_names:
            _convert_fgdb_datetime_fields_to_utc(
                output_path, layer_name, datetime_field_names
            )

        logger.info(f"Successfully copied layer {table} to FGDB.")

        return True
    except Exception:
        logger.exception(f"Failed to copy layer {table} to FGDB")

        return False


def _get_datetime_field_names(connection: pyodbc.Connection, table: str) -> set[str]:
    """Inspect SQL Server timestamp columns without requiring GDAL's MSSQL driver."""
    parts = table.split(".")
    if len(parts) != 3 or not all(parts):
        raise ValueError(f"Table name '{table}' must be in format 'sgid.schema.table'")

    query = dedent("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_CATALOG = ? AND TABLE_SCHEMA = ? AND TABLE_NAME = ?
    """)
    cursor = connection.cursor()
    try:
        cursor.execute(query, *parts)
        rows = cursor.fetchall()
    finally:
        cursor.close()

    if not rows:
        raise LookupError(f"No visible columns found for {table}")

    return {
        name
        for name, data_type in rows
        if data_type.lower()
        in {"datetime", "datetime2", "smalldatetime", "datetimeoffset"}
    }


def _convert_fgdb_datetime_fields_to_utc(
    fgdb_path: Path, layer_name: str, datetime_field_names: set[str]
) -> None:
    """Convert source timestamp fields in an FGDB layer from Mountain time to UTC."""
    dataset = gdal.OpenEx(str(fgdb_path), gdal.OF_VECTOR | gdal.OF_UPDATE)
    layer = dataset.GetLayerByName(layer_name)
    if layer is None:
        raise ValueError(f"Layer {layer_name} not found in FGDB {fgdb_path}")

    datetime_field_names = {name.casefold() for name in datetime_field_names}
    datetime_fields = [
        index
        for index in range(layer.GetLayerDefn().GetFieldCount())
        if layer.GetLayerDefn().GetFieldDefn(index).GetType() == ogr.OFTDateTime
        and layer.GetLayerDefn().GetFieldDefn(index).GetNameRef().casefold()
        in datetime_field_names
    ]
    if not datetime_fields:
        return

    if not layer.TestCapability(ogr.OLCRandomWrite):
        raise RuntimeError(f"FGDB layer {layer_name} does not support feature updates")

    for feature in layer:
        changed = False
        for index in datetime_fields:
            if not feature.IsFieldSetAndNotNull(index):
                continue

            year, month, day, hour, minute, seconds, _ = feature.GetFieldAsDateTime(
                index
            )
            local_datetime = datetime(year, month, day, hour, minute) + timedelta(
                seconds=seconds
            )
            utc_datetime = local_datetime.replace(tzinfo=SOURCE_TIME_ZONE).astimezone(
                UTC
            )
            feature.SetField(
                index,
                utc_datetime.year,
                utc_datetime.month,
                utc_datetime.day,
                utc_datetime.hour,
                utc_datetime.minute,
                utc_datetime.second + utc_datetime.microsecond / 1_000_000,
                ogr.TZFLAG_UTC,
            )
            changed = True

        if changed and layer.SetFeature(feature) != ogr.OGRERR_NONE:
            raise RuntimeError(
                f"Failed to convert timestamp fields for feature {feature.GetFID()} "
                f"in FGDB layer {layer_name}"
            )

    dataset = None


def create_fgdb(
    tables: list[str],
    agol_items_lookup: dict[str, dict],
    *,
    batch_index: int | None = None,
    output_path: Path | None = None,
) -> tuple[Path, dict[str, int]]:
    """
    Create a File Geodatabase (FGDB) from the specified tables.

    Args:
        tables: List of table names to include in the FGDB
        agol_items_lookup: Lookup dictionary with AGOL item information
        output_path: Optional FGDB destination, for isolated migration exports.
        batch_index: Optional batch number (1-based) forwarded to _generate_output_path to
                     produce unique FGDB names when processing multiple batches.

    Returns:
        Tuple of (Path to the created FGDB, dictionary mapping table names to source feature counts)
    """
    if len(tables) == 0:
        raise ValueError("No tables provided to create FGDB.")

    internal = _get_internal_connection()
    try:
        output_gdb_path = (
            output_path
            if output_path is not None
            else _generate_output_path(tables, agol_items_lookup, batch_index)
        )

        # Copy tables first to create the FGDB structure
        source_counts = {}
        for table in tables:
            # Count features in source table before copying
            source_count = _count_features_in_internal_table(table)
            if source_count >= 0:
                logger.info(f"📊 Source table {table}: {source_count:,} features")
                source_counts[table] = source_count

            success = _copy_table_to_fgdb(
                internal, table, output_gdb_path, agol_items_lookup[table]
            )
            if not success:
                raise RuntimeError(f"Failed to copy table {table} to FGDB")

            # Count features in the created FGDB layer
            title = agol_items_lookup[table]["published_name"]
            layer_name = get_service_from_title(title)
            fgdb_count = _count_features_in_fgdb_layer(output_gdb_path, layer_name)
            if fgdb_count >= 0:
                logger.info(f"📊 FGDB layer {layer_name}: {fgdb_count:,} features")

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

        return output_gdb_path, source_counts
    finally:
        internal = None
