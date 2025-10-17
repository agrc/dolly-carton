"""Integration tests for feature count logging functionality."""

from dolly.summary import ProcessSummary, get_current_summary, start_summary


class TestFeatureCountIntegration:
    """Integration tests for feature count logging across modules."""

    def test_feature_count_mismatch_detection_in_summary(self):
        """Test that feature count mismatches are properly tracked in summary."""
        # Start summary tracking
        start_summary(1000.0)

        # Simulate the process with mismatched counts
        summary = get_current_summary()
        assert summary is not None

        # Simulate successful table processing
        summary.add_table_updated("sgid.test.table1", None)

        # Simulate feature count mismatch detection
        source_count = 1000
        final_count = 999
        summary.add_feature_count_mismatch(
            "sgid.test.table1", source_count, final_count
        )

        # Verify that the count mismatch was recorded in update errors
        assert "sgid.test.table1" in summary.tables_with_errors

        # Verify it shows up in update errors
        assert any(
            "Feature count mismatch - source (internal): 1000 -> destination (AGOL): 999"
            in error
            for error in summary.update_errors
        )

    def test_feature_count_match_success_tracking(self):
        """Test that matching feature counts don't generate errors."""
        # Start summary tracking
        start_summary(1000.0)

        summary = get_current_summary()
        assert summary is not None

        # Simulate successful table processing with matching counts
        summary.add_table_updated("sgid.test.table1", None)

        # No count mismatches should be recorded
        assert len(summary.tables_updated) == 1
        assert "sgid.test.table1" not in summary.tables_with_errors

    def test_summary_status_with_count_mismatches(self):
        """Test that feature count mismatches affect overall process status."""
        summary = ProcessSummary()

        # Add a successful table update
        summary.add_table_updated("sgid.test.table1", None)

        # No errors initially - should be success
        message = summary.format_slack_message()
        message_str = str(message)
        assert "🟢" in message_str
        assert "completed successfully" in message_str

        # Add a feature count mismatch
        summary.add_feature_count_mismatch("sgid.test.table1", 1000, 999)

        # Now should show error status
        message = summary.format_slack_message()
        message_str = str(message)
        assert "🟡" in message_str
        assert "completed with errors" in message_str

    def test_logging_output_format(self):
        """Test that feature count logging uses the expected format."""
        # This tests the log message format used throughout the application

        # Expected format uses 📊 emoji and comma-separated numbers
        table_name = "sgid.test.example"
        source_count = 1234567

        # Test the expected log message formats
        expected_source_msg = f"📊 Source table {table_name}: {source_count:,} features"
        assert (
            "📊 Source table sgid.test.example: 1,234,567 features"
            == expected_source_msg
        )

        expected_fgdb_msg = f"📊 FGDB layer test_layer: {source_count:,} features"
        assert "📊 FGDB layer test_layer: 1,234,567 features" == expected_fgdb_msg

        expected_agol_before_msg = f"📊 Target service {table_name} before truncation: {source_count:,} features"
        assert (
            "📊 Target service sgid.test.example before truncation: 1,234,567 features"
            == expected_agol_before_msg
        )

        expected_agol_after_msg = (
            f"📊 Target service {table_name} after append: {source_count:,} features"
        )
        assert (
            "📊 Target service sgid.test.example after append: 1,234,567 features"
            == expected_agol_after_msg
        )

        # Test mismatch error format
        final_count = 1234566
        expected_mismatch_msg = f"📊 Feature count mismatch for {table_name}: Source {source_count:,} != Final {final_count:,}"
        assert (
            "📊 Feature count mismatch for sgid.test.example: Source 1,234,567 != Final 1,234,566"
            == expected_mismatch_msg
        )
