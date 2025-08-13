import logging
import xml.etree.ElementTree as ET
from textwrap import dedent
from typing import Dict, Optional

import pyodbc
from osgeo import gdal, ogr

logger = logging.getLogger(__name__)


def get_domain_metadata(connection: pyodbc.Connection) -> Dict[str, Dict]:
    """
    Get domain metadata from the geodatabase.

    Args:
        connection: Database connection

    Returns:
        Dictionary mapping domain names to domain information
    """
    logger.info("Getting domain metadata from geodatabase")

    # Get all domains from the geodatabase
    query = dedent("""
        SELECT d.Name, d.Definition
        FROM sde.GDB_ITEMS d
        JOIN sde.GDB_ITEMTYPES dt ON d.Type = dt.UUID
        WHERE dt.Name IN ('Coded Value Domain', 'Range Domain')
    """)

    cursor = connection.cursor()
    cursor.execute(query)

    domains = {}
    for row in cursor.fetchall():
        domain_name = row[0]
        definition_xml = row[1]

        if definition_xml:
            domain_info = parse_domain_xml(definition_xml)
            if domain_info:
                domains[domain_name] = domain_info
                logger.debug(f"Parsed domain: {domain_name} ({domain_info['type']})")

    cursor.close()
    logger.info(f"Found {len(domains)} domains in geodatabase")

    return domains


def parse_domain_xml(xml_string: str) -> Optional[Dict]:
    """
    Parse domain XML definition into a structured dictionary.

    Args:
        xml_string: XML definition from geodatabase

    Returns:
        Dictionary with domain information or None if parsing fails
    """
    try:
        root = ET.fromstring(xml_string)

        domain_type = root.tag
        if domain_type == "GPCodedValueDomain2":
            return parse_coded_value_domain(root)
        elif domain_type == "GPRangeDomain2":
            return parse_range_domain(root)
        else:
            logger.warning(f"Unknown domain type: {domain_type}")

            return None

    except ET.ParseError as e:
        logger.error(f"Failed to parse domain XML: {e}")

        return None


def parse_coded_value_domain(root: ET.Element) -> Dict:
    """
    Parse coded value domain from XML element.

    Args:
        root: XML root element for coded value domain

    Returns:
        Dictionary with coded value domain information
    """
    # Extract basic domain information
    domain_name = root.find("DomainName")
    field_type = root.find("FieldType")
    description = root.find("Description")

    domain_info = {
        "type": "coded_value",
        "name": domain_name.text if domain_name is not None else "",
        "description": description.text if description is not None else "",
        "field_type": field_type.text if field_type is not None else "",
        "coded_values": [],
    }

    # Parse coded values
    coded_values = root.find("CodedValues")
    if coded_values is not None:
        for coded_value in coded_values.findall("CodedValue"):
            code_elem = coded_value.find("Code")
            name_elem = coded_value.find("Name")

            code = (
                code_elem.text
                if code_elem is not None and code_elem.text is not None
                else ""
            )
            name = (
                name_elem.text
                if name_elem is not None and name_elem.text is not None
                else ""
            )

            domain_info["coded_values"].append({"code": code, "name": name})

    logger.debug(
        f"Parsed coded value domain '{domain_info['name']}' with {len(domain_info['coded_values'])} values"
    )

    return domain_info


def parse_range_domain(root: ET.Element) -> Dict:
    """
    Parse range domain from XML element.

    Args:
        root: XML root element for range domain

    Returns:
        Dictionary with range domain information
    """
    # Extract basic domain information
    domain_name = root.find("DomainName")
    field_type = root.find("FieldType")
    description = root.find("Description")
    min_value = root.find("MinValue")
    max_value = root.find("MaxValue")

    domain_info = {
        "type": "range",
        "name": domain_name.text if domain_name is not None else "",
        "description": description.text if description is not None else "",
        "field_type": field_type.text if field_type is not None else "",
        "min_value": min_value.text if min_value is not None else "",
        "max_value": max_value.text if max_value is not None else "",
    }

    logger.debug(
        f"Parsed range domain '{domain_info['name']}' with range {domain_info['min_value']}-{domain_info['max_value']}"
    )

    return domain_info


def get_table_field_domains(
    table_name: str, connection: pyodbc.Connection
) -> Dict[str, str]:
    """
    Get field-to-domain mappings for a specific table.

    Args:
        table_name: Name of the table
        connection: Database connection

    Returns:
        Dictionary mapping field names to domain names
    """
    logger.debug(f"Getting field domain mappings for table: {table_name}")

    # Query to get table definition from geodatabase metadata
    # Look for the table using the full name first, then fall back to just the table name
    query = dedent("""
        SELECT t.Definition
        FROM sde.GDB_ITEMS t
        JOIN sde.GDB_ITEMTYPES tt ON t.Type = tt.UUID
        WHERE tt.Name IN ('Feature Class', 'Table')
        AND (UPPER(t.Name) = UPPER(?) OR UPPER(t.Name) = UPPER(?))
    """)

    cursor = connection.cursor()
    full_table_name = table_name
    short_table_name = table_name.split(".")[
        -1
    ]  # Get just the table name without schema
    cursor.execute(query, (full_table_name, short_table_name))

    field_domains = {}
    row = cursor.fetchone()
    if row and row[0]:
        field_domains = parse_table_field_domains(row[0])

    cursor.close()
    logger.debug(f"Found {len(field_domains)} fields with domains in {table_name}")

    return field_domains


def parse_table_field_domains(xml_string: str) -> Dict[str, str]:
    """
    Parse table XML definition to extract field domain associations.

    Args:
        xml_string: XML definition from geodatabase

    Returns:
        Dictionary mapping field names to domain names
    """
    try:
        root = ET.fromstring(xml_string)
        field_domains = {}

        # Look for GPFieldInfoEx elements which contain field definitions
        field_infos = root.findall(".//GPFieldInfoEx")

        for field_info in field_infos:
            name_elem = field_info.find("Name")
            domain_elem = field_info.find("DomainName")

            if name_elem is not None and domain_elem is not None:
                field_name = name_elem.text
                domain_name = domain_elem.text

                if field_name and domain_name:
                    field_domains[field_name] = domain_name

        return field_domains

    except ET.ParseError as e:
        logger.error(f"Failed to parse table definition XML: {e}")

        return {}


def create_domains_in_fgdb(domains: Dict[str, Dict], fgdb_path: str) -> bool:
    """
    Create domains in the File Geodatabase.

    Args:
        domains: Domain definitions dictionary
        fgdb_path: Path to the FGDB

    Returns:
        True if domains were created successfully
    """
    if not domains:
        logger.info("No domains to create")

        return True

    logger.info(f"Attempting to create {len(domains)} domains in FGDB: {fgdb_path}")

    try:
        # Open FGDB for writing
        fgdb_ds = gdal.OpenEx(fgdb_path, gdal.OF_UPDATE)
        if not fgdb_ds:
            logger.error(f"Could not open FGDB for writing: {fgdb_path}")

            return False

        success_count = 0
        for domain_name, domain_info in domains.items():
            if domain_info["type"] == "coded_value":
                success = create_coded_value_domain(fgdb_ds, domain_name, domain_info)
            elif domain_info["type"] == "range":
                success = create_range_domain(fgdb_ds, domain_name, domain_info)
            else:
                logger.warning(f"Unsupported domain type: {domain_info['type']}")
                continue

            if success:
                success_count += 1
            else:
                logger.warning(f"Failed to create domain: {domain_name}")

        fgdb_ds = None

        logger.info(f"Successfully created {success_count}/{len(domains)} domains")

        return success_count > 0

    except Exception as e:
        logger.error(f"Error creating domains in FGDB: {e}", exc_info=True)

        return False


def create_coded_value_domain(
    fgdb_ds: gdal.Dataset, domain_name: str, domain_info: Dict
) -> bool:
    """
    Create a coded value domain in the FGDB using GDAL's domain support.

    Args:
        fgdb_ds: GDAL dataset for the FGDB
        domain_name: Name of the domain
        domain_info: Domain information dictionary

    Returns:
        True if domain was created successfully
    """
    logger.info(f"Creating coded value domain: {domain_name}")

    try:
        # Convert Esri field type to OGR field type
        field_type_map = {
            "esriFieldTypeString": ogr.OFTString,
            "esriFieldTypeInteger": ogr.OFTInteger,
            "esriFieldTypeSmallInteger": ogr.OFTInteger,
            "esriFieldTypeDouble": ogr.OFTReal,
            "esriFieldTypeSingle": ogr.OFTReal,
            "esriFieldTypeDate": ogr.OFTDate,
            "esriFieldTypeGUID": ogr.OFTString,
        }

        esri_field_type = domain_info.get("field_type", "esriFieldTypeString")
        ogr_field_type = field_type_map.get(esri_field_type, ogr.OFTString)

        # Create coded values dictionary
        coded_values = {}
        for cv in domain_info["coded_values"]:
            code = cv["code"]
            name = cv["name"]
            # Convert code to appropriate type based on field type
            if ogr_field_type == ogr.OFTInteger:
                try:
                    code = int(code) if code else 0
                except ValueError:
                    code = 0
            elif ogr_field_type == ogr.OFTReal:
                try:
                    code = float(code) if code else 0.0
                except ValueError:
                    code = 0.0
            # For string types, keep as string
            coded_values[code] = name

        # Create the coded field domain
        domain = ogr.CreateCodedFieldDomain(
            domain_name,
            domain_info.get("description", ""),
            ogr_field_type,
            ogr.OFSTNone,  # Field subtype
            coded_values,
        )

        if domain is None:
            logger.error(f"Failed to create coded domain object: {domain_name}")
            return False

        # Add domain to FGDB (will throw exception on failure when gdal.UseExceptions() is set)
        fgdb_ds.AddFieldDomain(domain)

        logger.info(
            f"Successfully created coded value domain: {domain_name} with {len(coded_values)} values"
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to create coded value domain {domain_name}: {e}", exc_info=True
        )

        return False


def create_range_domain(
    fgdb_ds: gdal.Dataset, domain_name: str, domain_info: Dict
) -> bool:
    """
    Create a range domain in the FGDB using GDAL's domain support.

    Args:
        fgdb_ds: GDAL dataset for the FGDB
        domain_name: Name of the domain
        domain_info: Domain information dictionary

    Returns:
        True if domain was created successfully
    """
    logger.info(f"Creating range domain: {domain_name}")

    try:
        # Convert Esri field type to OGR field type
        field_type_map = {
            "esriFieldTypeString": ogr.OFTString,
            "esriFieldTypeInteger": ogr.OFTInteger,
            "esriFieldTypeSmallInteger": ogr.OFTInteger,
            "esriFieldTypeDouble": ogr.OFTReal,
            "esriFieldTypeSingle": ogr.OFTReal,
            "esriFieldTypeDate": ogr.OFTDate,
        }

        esri_field_type = domain_info.get("field_type", "esriFieldTypeInteger")
        ogr_field_type = field_type_map.get(esri_field_type, ogr.OFTInteger)

        # Convert min/max values to appropriate type
        min_value = domain_info.get("min_value", "")
        max_value = domain_info.get("max_value", "")

        try:
            if ogr_field_type == ogr.OFTInteger:
                min_val = int(min_value) if min_value else 0
                max_val = int(max_value) if max_value else 0
            elif ogr_field_type == ogr.OFTReal:
                min_val = float(min_value) if min_value else 0.0
                max_val = float(max_value) if max_value else 0.0
            else:
                logger.warning(
                    f"Range domain {domain_name} has unsupported field type: {esri_field_type}"
                )

                return False
        except ValueError as e:
            logger.error(
                f"Failed to convert range values for domain {domain_name}: {e}",
                exc_info=True,
            )

            return False

        # Create the range field domain
        domain = ogr.CreateRangeFieldDomain(
            domain_name,
            domain_info.get("description", ""),
            ogr_field_type,
            ogr.OFSTNone,  # Field subtype
            min_val,
            True,  # min_inclusive
            max_val,
            True,  # max_inclusive
        )

        if domain is None:
            logger.error(f"Failed to create range domain object: {domain_name}")
            return False

        # Add domain to FGDB (will throw exception on failure when gdal.UseExceptions() is set)
        fgdb_ds.AddFieldDomain(domain)

        logger.info(
            f"Successfully created range domain: {domain_name} ({min_val} - {max_val})"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to create range domain {domain_name}: {e}", exc_info=True)

        return False


def apply_domains_to_fields(
    fgdb_path: str, table_field_domains: Dict[str, Dict[str, str]]
) -> bool:
    """
    Apply domain associations to fields in the copied tables.

    This function associates domains with fields after the tables
    have been copied to the FGDB using GDAL's field domain support.

    Args:
        fgdb_path: Path to the FGDB
        table_field_domains: Dictionary mapping table names to field-domain mappings

    Returns:
        True if domain associations were applied successfully
    """
    if not table_field_domains:
        logger.info("No field domain associations to apply")
        return True

    logger.info(f"Applying domain associations to fields in FGDB: {fgdb_path}")

    try:
        fgdb_ds = gdal.OpenEx(fgdb_path, gdal.OF_UPDATE)
        if not fgdb_ds:
            logger.error(
                f"Could not open FGDB for field domain association: {fgdb_path}"
            )
            return False

        success_count = 0
        total_associations = 0

        for table_name, field_domains in table_field_domains.items():
            layer = fgdb_ds.GetLayerByName(table_name)
            if not layer:
                logger.warning(f"Could not find layer {table_name} in FGDB")
                continue

            logger.info(
                f"Applying domains to {len(field_domains)} fields in layer {table_name}"
            )

            for field_name, domain_name in field_domains.items():
                total_associations += 1

                try:
                    # Get the layer definition
                    layer_defn = layer.GetLayerDefn()
                    field_idx = layer_defn.GetFieldIndex(field_name)

                    if field_idx < 0:
                        logger.warning(
                            f"Field {field_name} not found in layer {table_name}"
                        )
                        continue

                    # Get the field definition
                    field_defn = layer_defn.GetFieldDefn(field_idx)

                    # Check if domain exists in FGDB
                    domain = fgdb_ds.GetFieldDomain(domain_name)
                    if domain is None:
                        logger.warning(f"Domain {domain_name} not found in FGDB")
                        continue

                    # Create a new field definition with the domain
                    new_field_defn = ogr.FieldDefn(
                        field_defn.GetName(), field_defn.GetType()
                    )
                    new_field_defn.SetSubType(field_defn.GetSubType())
                    new_field_defn.SetWidth(field_defn.GetWidth())
                    new_field_defn.SetPrecision(field_defn.GetPrecision())
                    new_field_defn.SetNullable(field_defn.IsNullable())
                    new_field_defn.SetDefault(field_defn.GetDefault())
                    new_field_defn.SetAlternativeName(field_defn.GetAlternativeName())

                    # Set the domain
                    new_field_defn.SetDomainName(domain_name)

                    # Alter the field to apply the domain (will throw exception on failure when gdal.UseExceptions() is set)
                    layer.AlterFieldDefn(
                        field_idx, new_field_defn, ogr.ALTER_DOMAIN_FLAG
                    )

                    logger.debug(
                        f"✓ Applied domain {domain_name} to field {field_name} in {table_name}"
                    )
                    success_count += 1

                except Exception as e:
                    logger.warning(
                        f"Error applying domain {domain_name} to field {field_name}: {e}"
                    )

        fgdb_ds = None

        logger.info(
            f"Successfully applied {success_count}/{total_associations} domain associations"
        )
        return success_count > 0

    except Exception as e:
        logger.error(f"Error applying domain associations: {e}", exc_info=True)

        return False
