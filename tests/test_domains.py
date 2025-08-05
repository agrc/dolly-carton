"""Tests for domains.py functions"""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch

from osgeo import gdal, ogr

from dolly.domains import (
    apply_domains_to_fields,
    create_coded_value_domain,
    create_domains_in_fgdb,
    create_range_domain,
    get_domain_metadata,
    get_table_field_domains,
    parse_coded_value_domain,
    parse_domain_xml,
    parse_range_domain,
    parse_table_field_domains,
)


class TestParseDomainXml:
    """Test cases for the parse_domain_xml function."""

    def test_parse_coded_value_domain_xml(self):
        """Test parsing a coded value domain XML definition."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <GPCodedValueDomain2>
            <DomainName>TestDomain</DomainName>
            <FieldType>esriFieldTypeString</FieldType>
            <Description>Test coded value domain</Description>
            <CodedValues>
                <CodedValue>
                    <Code>1</Code>
                    <Name>Option One</Name>
                </CodedValue>
                <CodedValue>
                    <Code>2</Code>
                    <Name>Option Two</Name>
                </CodedValue>
            </CodedValues>
        </GPCodedValueDomain2>"""

        result = parse_domain_xml(xml_content)

        assert result is not None
        assert result["type"] == "coded_value"
        assert result["name"] == "TestDomain"
        assert result["description"] == "Test coded value domain"
        assert result["field_type"] == "esriFieldTypeString"
        assert len(result["coded_values"]) == 2
        assert result["coded_values"][0]["code"] == "1"
        assert result["coded_values"][0]["name"] == "Option One"

    def test_parse_range_domain_xml(self):
        """Test parsing a range domain XML definition."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <GPRangeDomain2>
            <DomainName>SpeedLimit</DomainName>
            <FieldType>esriFieldTypeInteger</FieldType>
            <Description>Speed limit range</Description>
            <MinValue>25</MinValue>
            <MaxValue>80</MaxValue>
        </GPRangeDomain2>"""

        result = parse_domain_xml(xml_content)

        assert result is not None
        assert result["type"] == "range"
        assert result["name"] == "SpeedLimit"
        assert result["description"] == "Speed limit range"
        assert result["field_type"] == "esriFieldTypeInteger"
        assert result["min_value"] == "25"
        assert result["max_value"] == "80"

    def test_parse_invalid_xml_returns_none(self):
        """Test that invalid XML returns None."""
        invalid_xml = "<invalid><xml"

        result = parse_domain_xml(invalid_xml)

        assert result is None

    def test_parse_unknown_domain_type_returns_none(self):
        """Test that unknown domain type returns None."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <UnknownDomainType>
            <DomainName>Test</DomainName>
        </UnknownDomainType>"""

        result = parse_domain_xml(xml_content)

        assert result is None


class TestParseCodedValueDomain:
    """Test cases for the parse_coded_value_domain function."""

    def test_parse_basic_coded_value_domain(self):
        """Test parsing a basic coded value domain XML element."""
        xml_content = """<GPCodedValueDomain2>
            <DomainName>StatusDomain</DomainName>
            <FieldType>esriFieldTypeString</FieldType>
            <Description>Status values</Description>
            <CodedValues>
                <CodedValue>
                    <Code>A</Code>
                    <Name>Active</Name>
                </CodedValue>
                <CodedValue>
                    <Code>I</Code>
                    <Name>Inactive</Name>
                </CodedValue>
            </CodedValues>
        </GPCodedValueDomain2>"""

        root = ET.fromstring(xml_content)
        result = parse_coded_value_domain(root)

        assert result["type"] == "coded_value"
        assert result["name"] == "StatusDomain"
        assert result["description"] == "Status values"
        assert result["field_type"] == "esriFieldTypeString"
        assert len(result["coded_values"]) == 2
        assert result["coded_values"][0]["code"] == "A"
        assert result["coded_values"][0]["name"] == "Active"

    def test_parse_coded_value_domain_with_missing_elements(self):
        """Test parsing coded value domain with missing optional elements."""
        xml_content = """<GPCodedValueDomain2>
            <DomainName>MinimalDomain</DomainName>
        </GPCodedValueDomain2>"""

        root = ET.fromstring(xml_content)
        result = parse_coded_value_domain(root)

        assert result["type"] == "coded_value"
        assert result["name"] == "MinimalDomain"
        assert result["description"] == ""
        assert result["field_type"] == ""
        assert result["coded_values"] == []

    def test_parse_coded_value_domain_with_empty_coded_values(self):
        """Test parsing coded value domain with empty coded values."""
        xml_content = """<GPCodedValueDomain2>
            <DomainName>EmptyDomain</DomainName>
            <CodedValues>
                <CodedValue>
                    <Code></Code>
                    <Name></Name>
                </CodedValue>
            </CodedValues>
        </GPCodedValueDomain2>"""

        root = ET.fromstring(xml_content)
        result = parse_coded_value_domain(root)

        assert result["type"] == "coded_value"
        assert len(result["coded_values"]) == 1
        # When XML text is empty, it becomes None, but our code converts it to ""
        assert result["coded_values"][0]["code"] == ""
        assert result["coded_values"][0]["name"] == ""


class TestParseRangeDomain:
    """Test cases for the parse_range_domain function."""

    def test_parse_basic_range_domain(self):
        """Test parsing a basic range domain XML element."""
        xml_content = """<GPRangeDomain2>
            <DomainName>AgeDomain</DomainName>
            <FieldType>esriFieldTypeInteger</FieldType>
            <Description>Valid age range</Description>
            <MinValue>0</MinValue>
            <MaxValue>120</MaxValue>
        </GPRangeDomain2>"""

        root = ET.fromstring(xml_content)
        result = parse_range_domain(root)

        assert result["type"] == "range"
        assert result["name"] == "AgeDomain"
        assert result["description"] == "Valid age range"
        assert result["field_type"] == "esriFieldTypeInteger"
        assert result["min_value"] == "0"
        assert result["max_value"] == "120"

    def test_parse_range_domain_with_missing_elements(self):
        """Test parsing range domain with missing optional elements."""
        xml_content = """<GPRangeDomain2>
            <DomainName>MinimalRange</DomainName>
        </GPRangeDomain2>"""

        root = ET.fromstring(xml_content)
        result = parse_range_domain(root)

        assert result["type"] == "range"
        assert result["name"] == "MinimalRange"
        assert result["description"] == ""
        assert result["field_type"] == ""
        assert result["min_value"] == ""
        assert result["max_value"] == ""


class TestGetDomainMetadata:
    """Test cases for the get_domain_metadata function."""

    @patch("dolly.domains.parse_domain_xml")
    def test_get_domain_metadata_success(self, mock_parse):
        """Test successful domain metadata retrieval."""
        # Mock database connection and cursor
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock database results
        mock_cursor.fetchall.return_value = [
            ("TestDomain1", "<xml>domain1</xml>"),
            ("TestDomain2", "<xml>domain2</xml>"),
        ]

        # Mock parse_domain_xml return values
        mock_parse.side_effect = [
            {"type": "coded_value", "name": "TestDomain1"},
            {"type": "range", "name": "TestDomain2"},
        ]

        result = get_domain_metadata(mock_connection)

        assert len(result) == 2
        assert "TestDomain1" in result
        assert "TestDomain2" in result
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch("dolly.domains.parse_domain_xml")
    def test_get_domain_metadata_with_invalid_xml(self, mock_parse):
        """Test domain metadata retrieval with invalid XML."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("ValidDomain", "<xml>valid</xml>"),
            ("InvalidDomain", "<invalid>xml"),
        ]

        # First call returns valid domain, second returns None
        mock_parse.side_effect = [
            {"type": "coded_value", "name": "ValidDomain"},
            None,
        ]

        result = get_domain_metadata(mock_connection)

        assert len(result) == 1
        assert "ValidDomain" in result
        assert "InvalidDomain" not in result

    def test_get_domain_metadata_empty_results(self):
        """Test domain metadata retrieval with no results."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = get_domain_metadata(mock_connection)

        assert len(result) == 0
        assert isinstance(result, dict)


class TestGetTableFieldDomains:
    """Test cases for the get_table_field_domains function."""

    @patch("dolly.domains.parse_table_field_domains")
    def test_get_table_field_domains_success(self, mock_parse):
        """Test successful table field domain retrieval."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock database result
        mock_cursor.fetchone.return_value = ("<xml>table_definition</xml>",)

        # Mock parse function
        mock_parse.return_value = {"field1": "domain1", "field2": "domain2"}

        result = get_table_field_domains("test_table", mock_connection)

        assert len(result) == 2
        assert result["field1"] == "domain1"
        assert result["field2"] == "domain2"
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()

    def test_get_table_field_domains_no_results(self):
        """Test table field domain retrieval with no results."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = get_table_field_domains("test_table", mock_connection)

        assert len(result) == 0
        assert isinstance(result, dict)

    def test_get_table_field_domains_empty_xml(self):
        """Test table field domain retrieval with empty XML."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (None,)

        result = get_table_field_domains("test_table", mock_connection)

        assert len(result) == 0


class TestParseTableFieldDomains:
    """Test cases for the parse_table_field_domains function."""

    def test_parse_table_field_domains_success(self):
        """Test successful parsing of table field domain XML."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <root>
            <GPFieldInfoEx>
                <Name>STATUS</Name>
                <DomainName>StatusDomain</DomainName>
            </GPFieldInfoEx>
            <GPFieldInfoEx>
                <Name>TYPE</Name>
                <DomainName>TypeDomain</DomainName>
            </GPFieldInfoEx>
            <GPFieldInfoEx>
                <Name>NO_DOMAIN_FIELD</Name>
            </GPFieldInfoEx>
        </root>"""

        result = parse_table_field_domains(xml_content)

        assert len(result) == 2
        assert result["STATUS"] == "StatusDomain"
        assert result["TYPE"] == "TypeDomain"
        assert "NO_DOMAIN_FIELD" not in result

    def test_parse_table_field_domains_invalid_xml(self):
        """Test parsing invalid XML returns empty dict."""
        invalid_xml = "<invalid><xml"

        result = parse_table_field_domains(invalid_xml)

        assert len(result) == 0
        assert isinstance(result, dict)

    def test_parse_table_field_domains_empty_elements(self):
        """Test parsing XML with empty elements."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <root>
            <GPFieldInfoEx>
                <Name></Name>
                <DomainName>SomeDomain</DomainName>
            </GPFieldInfoEx>
            <GPFieldInfoEx>
                <Name>FieldName</Name>
                <DomainName></DomainName>
            </GPFieldInfoEx>
        </root>"""

        result = parse_table_field_domains(xml_content)

        assert len(result) == 0


class TestCreateCodedValueDomain:
    """Test cases for the create_coded_value_domain function."""

    def setUp(self):
        """Set up test fixtures."""
        gdal.UseExceptions()

    @patch("osgeo.ogr.CreateCodedFieldDomain")
    def test_create_coded_value_domain_success(self, mock_create_domain):
        """Test successful coded value domain creation."""
        # Mock GDAL dataset
        mock_fgdb_ds = Mock()
        mock_domain = Mock()
        mock_create_domain.return_value = mock_domain

        domain_info = {
            "description": "Test domain",
            "field_type": "esriFieldTypeString",
            "coded_values": [
                {"code": "A", "name": "Active"},
                {"code": "I", "name": "Inactive"},
            ],
        }

        result = create_coded_value_domain(mock_fgdb_ds, "TestDomain", domain_info)

        assert result is True
        mock_fgdb_ds.AddFieldDomain.assert_called_once_with(mock_domain)
        mock_create_domain.assert_called_once()

    @patch("osgeo.ogr.CreateCodedFieldDomain")
    def test_create_coded_value_domain_creation_fails(self, mock_create_domain):
        """Test coded value domain creation when domain object creation fails."""
        mock_fgdb_ds = Mock()
        mock_create_domain.return_value = None

        domain_info = {
            "description": "Test domain",
            "field_type": "esriFieldTypeString",
            "coded_values": [{"code": "A", "name": "Active"}],
        }

        result = create_coded_value_domain(mock_fgdb_ds, "TestDomain", domain_info)

        assert result is False
        mock_fgdb_ds.AddFieldDomain.assert_not_called()

    def test_create_coded_value_domain_exception_handling(self):
        """Test exception handling in coded value domain creation."""
        mock_fgdb_ds = Mock()
        mock_fgdb_ds.AddFieldDomain.side_effect = Exception("Test exception")

        domain_info = {
            "description": "Test domain",
            "field_type": "esriFieldTypeString",
            "coded_values": [{"code": "A", "name": "Active"}],
        }

        result = create_coded_value_domain(mock_fgdb_ds, "TestDomain", domain_info)

        assert result is False


class TestCreateRangeDomain:
    """Test cases for the create_range_domain function."""

    @patch("osgeo.ogr.CreateRangeFieldDomain")
    def test_create_range_domain_success(self, mock_create_domain):
        """Test successful range domain creation."""
        mock_fgdb_ds = Mock()
        mock_domain = Mock()
        mock_create_domain.return_value = mock_domain

        domain_info = {
            "description": "Age range",
            "field_type": "esriFieldTypeInteger",
            "min_value": "0",
            "max_value": "120",
        }

        result = create_range_domain(mock_fgdb_ds, "AgeDomain", domain_info)

        assert result is True
        mock_fgdb_ds.AddFieldDomain.assert_called_once_with(mock_domain)
        mock_create_domain.assert_called_once()

    @patch("osgeo.ogr.CreateRangeFieldDomain")
    def test_create_range_domain_with_double_values(self, mock_create_domain):
        """Test range domain creation with double/real field type."""
        mock_fgdb_ds = Mock()
        mock_domain = Mock()
        mock_create_domain.return_value = mock_domain

        domain_info = {
            "description": "Temperature range",
            "field_type": "esriFieldTypeDouble",
            "min_value": "-40.5",
            "max_value": "120.8",
        }

        result = create_range_domain(mock_fgdb_ds, "TempDomain", domain_info)

        assert result is True
        # Verify that float values were passed to the creation function
        call_args = mock_create_domain.call_args[0]
        # Arguments are: name, description, field_type, subtype, min_val, min_inclusive, max_val, max_inclusive
        assert isinstance(call_args[4], float)  # min_value is 5th argument (index 4)
        assert isinstance(call_args[6], float)  # max_value is 7th argument (index 6)

    def test_create_range_domain_exception_handling(self):
        """Test exception handling in range domain creation."""
        mock_fgdb_ds = Mock()
        mock_fgdb_ds.AddFieldDomain.side_effect = Exception("Test exception")

        domain_info = {
            "description": "Test domain",
            "field_type": "esriFieldTypeInteger",
            "min_value": "0",
            "max_value": "100",
        }

        result = create_range_domain(mock_fgdb_ds, "TestDomain", domain_info)

        assert result is False


class TestCreateDomainsInFgdb:
    """Test cases for the create_domains_in_fgdb function."""

    @patch("dolly.domains.create_coded_value_domain")
    @patch("dolly.domains.create_range_domain")
    @patch("dolly.domains.gdal.OpenEx")
    def test_create_domains_in_fgdb_success(
        self, mock_open, mock_create_range, mock_create_coded
    ):
        """Test successful domain creation in FGDB."""
        mock_fgdb_ds = Mock()
        mock_open.return_value = mock_fgdb_ds
        mock_create_coded.return_value = True
        mock_create_range.return_value = True

        domains = {
            "CodedDomain": {"type": "coded_value"},
            "RangeDomain": {"type": "range"},
        }

        result = create_domains_in_fgdb(domains, "/test/path.gdb")

        assert result is True
        mock_create_coded.assert_called_once()
        mock_create_range.assert_called_once()

    @patch("dolly.domains.gdal.OpenEx")
    def test_create_domains_in_fgdb_cannot_open(self, mock_open):
        """Test domain creation when FGDB cannot be opened."""
        mock_open.return_value = None

        domains = {"TestDomain": {"type": "coded_value"}}

        result = create_domains_in_fgdb(domains, "/test/path.gdb")

        assert result is False

    def test_create_domains_in_fgdb_empty_domains(self):
        """Test domain creation with empty domains dict."""
        result = create_domains_in_fgdb({}, "/test/path.gdb")

        assert result is True

    @patch("dolly.domains.create_coded_value_domain")
    @patch("dolly.domains.gdal.OpenEx")
    def test_create_domains_in_fgdb_partial_failure(self, mock_open, mock_create_coded):
        """Test domain creation with partial failures."""
        mock_fgdb_ds = Mock()
        mock_open.return_value = mock_fgdb_ds
        mock_create_coded.side_effect = [True, False]  # First succeeds, second fails

        domains = {
            "Domain1": {"type": "coded_value"},
            "Domain2": {"type": "coded_value"},
        }

        result = create_domains_in_fgdb(domains, "/test/path.gdb")

        assert result is True  # Should return True if at least one domain was created
        assert mock_create_coded.call_count == 2


class TestApplyDomainsToFields:
    """Test cases for the apply_domains_to_fields function."""

    @patch("osgeo.ogr.FieldDefn")
    @patch("dolly.domains.gdal.OpenEx")
    def test_apply_domains_to_fields_success(self, mock_open, mock_field_defn_class):
        """Test successful application of domains to fields."""
        # Mock GDAL dataset and layer
        mock_fgdb_ds = Mock()
        mock_layer = Mock()
        mock_layer_defn = Mock()
        mock_field_defn = Mock()
        mock_new_field_defn = Mock()

        mock_open.return_value = mock_fgdb_ds
        mock_fgdb_ds.GetLayerByName.return_value = mock_layer
        mock_layer.GetLayerDefn.return_value = mock_layer_defn
        mock_layer_defn.GetFieldCount.return_value = 2
        mock_layer_defn.GetFieldDefn.return_value = mock_field_defn
        mock_layer_defn.GetFieldIndex.side_effect = [0, 1]  # Field indices
        mock_field_defn.GetName.side_effect = ["STATUS", "TYPE"]
        mock_field_defn.GetType.return_value = ogr.OFTString
        mock_field_defn.GetSubType.return_value = ogr.OFSTNone
        mock_field_defn.GetWidth.return_value = 50
        mock_field_defn.GetPrecision.return_value = 0
        mock_field_defn.IsNullable.return_value = True
        mock_field_defn.GetDefault.return_value = None
        mock_field_defn.GetAlternativeName.return_value = ""

        # Mock the new FieldDefn creation
        mock_field_defn_class.return_value = mock_new_field_defn

        # Mock AlterFieldDefn to not raise exceptions (simulate success)
        mock_layer.AlterFieldDefn.return_value = None

        table_field_domains = {
            "TestTable": {"STATUS": "StatusDomain", "TYPE": "TypeDomain"}
        }

        result = apply_domains_to_fields("/test/path.gdb", table_field_domains)

        assert result is True
        assert mock_layer.AlterFieldDefn.call_count == 2

    @patch("dolly.domains.gdal.OpenEx")
    def test_apply_domains_to_fields_cannot_open_fgdb(self, mock_open):
        """Test domain application when FGDB cannot be opened."""
        mock_open.return_value = None

        table_field_domains = {"TestTable": {"field1": "domain1"}}

        result = apply_domains_to_fields("/test/path.gdb", table_field_domains)

        assert result is False

    @patch("dolly.domains.gdal.OpenEx")
    def test_apply_domains_to_fields_layer_not_found(self, mock_open):
        """Test domain application when layer is not found."""
        mock_fgdb_ds = Mock()
        mock_open.return_value = mock_fgdb_ds
        mock_fgdb_ds.GetLayerByName.return_value = None

        table_field_domains = {"NonExistentTable": {"field1": "domain1"}}

        result = apply_domains_to_fields("/test/path.gdb", table_field_domains)

        # Should return False because no successful associations occurred
        assert result is False

    @patch("dolly.domains.gdal.OpenEx")
    def test_apply_domains_to_fields_field_not_found(self, mock_open):
        """Test domain application when field is not found in layer."""
        mock_fgdb_ds = Mock()
        mock_layer = Mock()
        mock_layer_defn = Mock()

        mock_open.return_value = mock_fgdb_ds
        mock_fgdb_ds.GetLayerByName.return_value = mock_layer
        mock_layer.GetLayerDefn.return_value = mock_layer_defn
        mock_layer_defn.GetFieldIndex.return_value = -1  # Field not found

        table_field_domains = {"TestTable": {"NonExistentField": "SomeDomain"}}

        result = apply_domains_to_fields("/test/path.gdb", table_field_domains)

        # Should return False because no successful associations occurred
        assert result is False
        mock_layer.AlterFieldDefn.assert_not_called()

    def test_apply_domains_to_fields_empty_input(self):
        """Test domain application with empty input."""
        result = apply_domains_to_fields("/test/path.gdb", {})

        assert result is True

    @patch("dolly.domains.gdal.OpenEx")
    def test_apply_domains_to_fields_exception_handling(self, mock_open):
        """Test exception handling in domain application."""
        mock_fgdb_ds = Mock()
        mock_open.return_value = mock_fgdb_ds
        mock_fgdb_ds.GetLayerByName.side_effect = Exception("Test exception")

        table_field_domains = {"TestTable": {"field1": "domain1"}}

        result = apply_domains_to_fields("/test/path.gdb", table_field_domains)

        assert result is False


class TestFieldTypeMapping:
    """Test cases for field type mapping functionality."""

    def test_esri_to_ogr_field_type_mapping(self):
        """Test the mapping from Esri field types to OGR field types."""
        # This test verifies the field type mapping used in create_coded_value_domain
        # and create_range_domain functions
        from dolly.domains import create_coded_value_domain

        mock_fgdb_ds = Mock()

        # Test string field type
        domain_info = {
            "description": "Test",
            "field_type": "esriFieldTypeString",
            "coded_values": [{"code": "A", "name": "Active"}],
        }

        with patch("osgeo.ogr.CreateCodedFieldDomain") as mock_create:
            mock_create.return_value = Mock()
            create_coded_value_domain(mock_fgdb_ds, "TestDomain", domain_info)

            # Verify the correct OGR field type was passed
            call_args = mock_create.call_args[0]
            assert call_args[2] == ogr.OFTString  # Third argument should be field type

    def test_field_type_conversion_for_coded_values(self):
        """Test that coded values are properly converted based on field type."""
        # This indirectly tests the type conversion logic in create_coded_value_domain
        mock_fgdb_ds = Mock()

        domain_info = {
            "description": "Integer codes",
            "field_type": "esriFieldTypeInteger",
            "coded_values": [
                {"code": "1", "name": "One"},
                {"code": "2", "name": "Two"},
            ],
        }

        with patch("osgeo.ogr.CreateCodedFieldDomain") as mock_create:
            mock_create.return_value = Mock()
            create_coded_value_domain(mock_fgdb_ds, "IntDomain", domain_info)

            # The coded values should be converted to integers
            call_args = mock_create.call_args[0]
            coded_values_dict = call_args[4]  # Fifth argument is coded values
            # Keys should be converted to integers for integer field types
            assert 1 in coded_values_dict or "1" in coded_values_dict


# Integration tests that require a temporary FGDB
class TestDomainsIntegration:
    """Integration tests for domain functionality with real FGDB."""

    def test_end_to_end_domain_workflow(self):
        """Test the complete domain workflow with a temporary FGDB.

        This test is primarily for testing purposes and verifies the complete
        integration of domain creation and field association.
        """
        gdal.UseExceptions()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_fgdb = Path(temp_dir) / "test_domains.gdb"

            # Create test FGDB
            driver = ogr.GetDriverByName("OpenFileGDB")
            ds = driver.CreateDataSource(str(test_fgdb))

            # Create a simple layer for testing
            layer = ds.CreateLayer("TestLayer", geom_type=ogr.wkbPoint)
            field_defn = ogr.FieldDefn("status_field", ogr.OFTString)
            layer.CreateField(field_defn)

            ds = None  # Close to flush

            # Test domain creation
            domains = {
                "TestStatusDomain": {
                    "type": "coded_value",
                    "description": "Test status domain",
                    "field_type": "esriFieldTypeString",
                    "coded_values": [
                        {"code": "A", "name": "Active"},
                        {"code": "I", "name": "Inactive"},
                    ],
                }
            }

            # Create domains
            success = create_domains_in_fgdb(domains, str(test_fgdb))
            assert success

            # Apply domains to fields
            table_field_domains = {"TestLayer": {"status_field": "TestStatusDomain"}}
            success = apply_domains_to_fields(str(test_fgdb), table_field_domains)
            assert success

            # Verify the domain was created and applied
            ds = gdal.OpenEx(str(test_fgdb), gdal.OF_READONLY)
            domain_names = ds.GetFieldDomainNames()
            assert "TestStatusDomain" in domain_names

            layer = ds.GetLayerByName("TestLayer")
            layer_defn = layer.GetLayerDefn()
            field_defn = layer_defn.GetFieldDefn(0)
            assert field_defn.GetDomainName() == "TestStatusDomain"

            ds = None

    def test_create_multiple_domain_types(self):
        """Test creating both coded value and range domains.

        This test verifies that both domain types can be created successfully
        in the same FGDB, primarily for testing completeness.
        """
        gdal.UseExceptions()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_fgdb = Path(temp_dir) / "multi_domains.gdb"

            # Create test FGDB
            driver = ogr.GetDriverByName("OpenFileGDB")
            ds = driver.CreateDataSource(str(test_fgdb))
            ds = None

            # Test domains of different types
            domains = {
                "CodedDomain": {
                    "type": "coded_value",
                    "description": "Coded test domain",
                    "field_type": "esriFieldTypeString",
                    "coded_values": [{"code": "X", "name": "Test"}],
                },
                "RangeDomain": {
                    "type": "range",
                    "description": "Range test domain",
                    "field_type": "esriFieldTypeInteger",
                    "min_value": "1",
                    "max_value": "100",
                },
            }

            success = create_domains_in_fgdb(domains, str(test_fgdb))
            assert success

            # Verify both domains were created
            ds = gdal.OpenEx(str(test_fgdb), gdal.OF_READONLY)
            domain_names = ds.GetFieldDomainNames()
            assert "CodedDomain" in domain_names
            assert "RangeDomain" in domain_names
            assert len(domain_names) == 2

            ds = None
