"""
Tests for dolly-carton functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import internal
import dolly


class TestInternal(unittest.TestCase):
    """Test cases for the internal module."""

    def test_get_updated_tables_returns_list(self):
        """Test that get_updated_tables returns a list."""
        result = internal.get_updated_tables()
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
    
    def test_get_updated_tables_returns_expected_tables(self):
        """Test that get_updated_tables returns the expected sample tables."""
        result = internal.get_updated_tables()
        expected = [
            "sgid.boundaries.counties",
            "sgid.location.addresspoints",
            "sgid.transportation.roads"
        ]
        self.assertEqual(result, expected)


class TestDollyArgParsing(unittest.TestCase):
    """Test cases for dolly argument parsing."""

    def test_parse_arguments_no_args(self):
        """Test parsing with no arguments."""
        with patch('sys.argv', ['dolly.py']):
            args = dolly.parse_arguments()
            self.assertIsNone(args.force_tables)

    def test_parse_arguments_with_force_tables(self):
        """Test parsing with --force-tables argument."""
        with patch('sys.argv', ['dolly.py', '--force-tables', 'table1,table2']):
            args = dolly.parse_arguments()
            self.assertEqual(args.force_tables, 'table1,table2')


class TestDollyMain(unittest.TestCase):
    """Test cases for dolly main functionality."""

    @patch('dolly.internal.get_updated_tables')
    @patch('sys.argv', ['dolly.py'])
    @patch('builtins.print')
    def test_main_without_force_tables(self, mock_print, mock_get_updated_tables):
        """Test main function without force-tables parameter."""
        mock_get_updated_tables.return_value = ['test.table1', 'test.table2']
        
        dolly.main()
        
        mock_get_updated_tables.assert_called_once()
        # Check that the expected print calls were made
        expected_calls = [
            unittest.mock.call('Tables to update from internal logic: [\'test.table1\', \'test.table2\']'),
            unittest.mock.call('Processing 2 table(s)...'),
            unittest.mock.call('  - test.table1'),
            unittest.mock.call('  - test.table2'),
            unittest.mock.call('Processing complete.')
        ]
        mock_print.assert_has_calls(expected_calls)

    @patch('dolly.internal.get_updated_tables')
    @patch('sys.argv', ['dolly.py', '--force-tables', 'sgid.society.cemeteries,sgid.boundaries.municipalities'])
    @patch('builtins.print')
    def test_main_with_force_tables(self, mock_print, mock_get_updated_tables):
        """Test main function with force-tables parameter."""
        dolly.main()
        
        # get_updated_tables should not be called when force-tables is provided
        mock_get_updated_tables.assert_not_called()
        
        # Check that the expected print calls were made
        expected_calls = [
            unittest.mock.call('Force updating tables: [\'sgid.society.cemeteries\', \'sgid.boundaries.municipalities\']'),
            unittest.mock.call('Processing 2 table(s)...'),
            unittest.mock.call('  - sgid.society.cemeteries'),
            unittest.mock.call('  - sgid.boundaries.municipalities'),
            unittest.mock.call('Processing complete.')
        ]
        mock_print.assert_has_calls(expected_calls)

    @patch('dolly.internal.get_updated_tables')
    @patch('sys.argv', ['dolly.py', '--force-tables', ''])
    @patch('builtins.print')
    def test_main_with_empty_force_tables(self, mock_print, mock_get_updated_tables):
        """Test main function with empty force-tables parameter."""
        mock_get_updated_tables.return_value = ['test.table1']
        
        dolly.main()
        
        # With empty string, it should fall back to internal logic
        mock_get_updated_tables.assert_called_once()
        
        # Should process tables from internal logic
        mock_print.assert_any_call('Tables to update from internal logic: [\'test.table1\']')


    @patch('dolly.internal.get_updated_tables')
    @patch('sys.argv', ['dolly.py', '--force-tables', 'table1, , table2,  '])
    @patch('builtins.print')
    def test_main_with_mixed_empty_force_tables(self, mock_print, mock_get_updated_tables):
        """Test main function with force-tables parameter containing empty values."""
        dolly.main()
        
        # get_updated_tables should not be called when valid tables are provided
        mock_get_updated_tables.assert_not_called()
        
        # Check that the expected print calls were made, filtering out empty values
        expected_calls = [
            unittest.mock.call('Force updating tables: [\'table1\', \'table2\']'),
            unittest.mock.call('Processing 2 table(s)...'),
            unittest.mock.call('  - table1'),
            unittest.mock.call('  - table2'),
            unittest.mock.call('Processing complete.')
        ]
        mock_print.assert_has_calls(expected_calls)


if __name__ == '__main__':
    unittest.main()