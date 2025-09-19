"""Test cases for domain processing logic and other internal functions."""

from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from dolly.internal import create_fgdb


class TestDomainProcessing:
    """Test domain processing logic in create_fgdb."""

    @patch("dolly.internal._count_features_in_fgdb_layer")
    @patch("dolly.internal._count_features_in_internal_table")
    @patch("dolly.internal.apply_domains_to_fields")
    @patch("dolly.internal.create_domains_in_fgdb")
    @patch("dolly.internal.get_domain_metadata")
    @patch("dolly.internal.get_table_field_domains")
    @patch("dolly.internal._get_database_connection")
    @patch("dolly.internal._generate_output_path")
    @patch("dolly.internal.get_gdal_layer_name")
    @patch("dolly.internal._get_geometry_option")
    @patch("dolly.internal.get_service_from_title")
    @patch("dolly.internal.gdal.VectorTranslate")
    @patch("dolly.internal.logger")
    def test_create_fgdb_with_domains(
        self,
        mock_logger,
        mock_translate,
        mock_get_service,
        mock_get_geom_option,
        mock_get_layer_name,
        mock_generate_path,
        mock_get_db_connection,
        mock_get_table_field_domains,
        mock_get_domain_metadata,
        mock_create_domains,
        mock_apply_domains,
        mock_count_internal,
        mock_count_fgdb,
    ):
        """Test create_fgdb with domain processing."""
        # Setup mocks
        mock_gdal_connection = Mock()
        mock_gdal_connection.GetLayerCount.return_value = 5

        mock_db_connection = Mock()
        mock_get_db_connection.return_value = mock_db_connection

        # Mock domain processing
        field_domains = {"field1": "domain1", "field2": "domain2"}
        mock_get_table_field_domains.return_value = field_domains
        
        all_domains = {
            "domain1": {"type": "coded", "values": {"A": "Apple"}},
            "domain2": {"type": "range", "min": 0, "max": 100},
            "unused_domain": {"type": "coded", "values": {"X": "Unused"}}
        }
        mock_get_domain_metadata.return_value = all_domains

        # Mock feature counting functions
        mock_count_internal.return_value = 1000
        mock_count_fgdb.return_value = 1000

        mock_generate_path.return_value = Path("/test/output.gdb")
        mock_get_layer_name.return_value = "test_layer"
        mock_get_geom_option.return_value = "MULTIPOLYGON"
        mock_get_service.return_value = "test_service"
        mock_translate.return_value = None

        tables = ["sgid.test.table1"]
        agol_lookup = {
            "sgid.test.table1": {
                "geometry_type": "POLYGON",
                "published_name": "Test Table",
            }
        }

        result = create_fgdb(tables, agol_lookup, gdal_connection=mock_gdal_connection)

        # Verify result
        assert result == (Path("/test/output.gdb"), {"sgid.test.table1": 1000})

        # Verify domain processing was called
        mock_get_table_field_domains.assert_called_once()
        mock_get_domain_metadata.assert_called_once_with(mock_db_connection)
        
        # Verify only used domains were processed
        expected_domains = {
            "domain1": {"type": "coded", "values": {"A": "Apple"}},
            "domain2": {"type": "range", "min": 0, "max": 100}
        }
        mock_create_domains.assert_called_once_with(expected_domains, "/test/output.gdb")
        mock_apply_domains.assert_called_once()

    @patch("dolly.internal._count_features_in_fgdb_layer")
    @patch("dolly.internal._count_features_in_internal_table")
    @patch("dolly.internal.apply_domains_to_fields")
    @patch("dolly.internal.create_domains_in_fgdb")
    @patch("dolly.internal.get_domain_metadata")
    @patch("dolly.internal.get_table_field_domains")
    @patch("dolly.internal._get_database_connection")
    @patch("dolly.internal._generate_output_path")
    @patch("dolly.internal.get_gdal_layer_name")
    @patch("dolly.internal._get_geometry_option")
    @patch("dolly.internal.get_service_from_title")
    @patch("dolly.internal.gdal.VectorTranslate")
    @patch("dolly.internal.logger")
    def test_create_fgdb_no_domains(
        self,
        mock_logger,
        mock_translate,
        mock_get_service,
        mock_get_geom_option,
        mock_get_layer_name,
        mock_generate_path,
        mock_get_db_connection,
        mock_get_table_field_domains,
        mock_get_domain_metadata,
        mock_create_domains,
        mock_apply_domains,
        mock_count_internal,
        mock_count_fgdb,
    ):
        """Test create_fgdb when no domains are found."""
        # Setup mocks
        mock_gdal_connection = Mock()
        mock_gdal_connection.GetLayerCount.return_value = 5

        mock_db_connection = Mock()
        mock_get_db_connection.return_value = mock_db_connection

        # Mock no domains found
        mock_get_table_field_domains.return_value = {}

        # Mock feature counting functions
        mock_count_internal.return_value = 1000
        mock_count_fgdb.return_value = 1000

        mock_generate_path.return_value = Path("/test/output.gdb")
        mock_get_layer_name.return_value = "test_layer"
        mock_get_geom_option.return_value = "MULTIPOLYGON"
        mock_get_service.return_value = "test_service"
        mock_translate.return_value = None

        tables = ["sgid.test.table1"]
        agol_lookup = {
            "sgid.test.table1": {
                "geometry_type": "POLYGON",
                "published_name": "Test Table",
            }
        }

        result = create_fgdb(tables, agol_lookup, gdal_connection=mock_gdal_connection)

        # Verify result
        assert result == (Path("/test/output.gdb"), {"sgid.test.table1": 1000})

        # Verify domain processing was not called when no domains
        mock_get_table_field_domains.assert_called_once()
        mock_get_domain_metadata.assert_not_called()
        mock_create_domains.assert_not_called()
        mock_apply_domains.assert_not_called()