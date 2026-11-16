from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import migrate_preferred_time_reference as migration


@pytest.fixture
def dependencies(monkeypatch):
    names = [
        "get_gis_connection",
        "get_agol_items_lookup",
        "_get_gdal_connection",
        "_get_datetime_field_names",
        "get_current_hashes",
        "create_fgdb",
        "zip_and_upload_fgdb",
        "update_feature_services",
        "set_preferred_time_reference",
    ]
    mocks = {name: Mock() for name in names}
    for name, mock in mocks.items():
        monkeypatch.setattr(migration, name, mock)
    source_context = Mock()
    source_context.__enter__ = Mock(return_value=Mock())
    source_context.__exit__ = Mock(return_value=False)
    mocks["_get_gdal_connection"].return_value = source_context
    mocks["_get_datetime_field_names"].return_value = set()
    mocks["get_current_hashes"].return_value = {}
    mocks["create_fgdb"].side_effect = lambda tables, lookup, *, output_path: (
        output_path,
        {tables[0]: 10},
    )
    return mocks


def test_migration_updates_unique_existing_service_ids(dependencies):
    dependencies["get_agol_items_lookup"].return_value = {
        "sgid.society.cemeteries": {"item_id": "service-1"},
        "sgid.society.schools": {"item_id": "service-1"},
        "sgid.transportation.roads": {"item_id": None},
    }
    gis = dependencies["get_gis_connection"].return_value
    item = gis.content.get.return_value

    migration.migrate_existing_services()

    gis.content.get.assert_called_once_with("service-1")
    dependencies["set_preferred_time_reference"].assert_called_once_with(item)
    dependencies["create_fgdb"].assert_not_called()


def test_migration_force_refreshes_only_timestamp_tables(dependencies):
    timestamp_table = "sgid.transportation.roads"
    lookup = {
        timestamp_table: {"item_id": "service-1"},
        "sgid.society.schools": {"item_id": "service-2"},
    }
    dependencies["get_agol_items_lookup"].return_value = lookup
    dependencies["_get_datetime_field_names"].side_effect = [set(), {"updated"}]
    hashes = {timestamp_table: "unchanged-source-hash"}
    dependencies["get_current_hashes"].return_value = hashes
    dependencies["update_feature_services"].return_value = {timestamp_table}
    gis = dependencies["get_gis_connection"].return_value

    migration.migrate_existing_services()

    export_call = dependencies["create_fgdb"].call_args
    assert export_call.args == ([timestamp_table], lookup)
    output_path = export_call.kwargs["output_path"]
    assert isinstance(output_path, Path)
    assert not output_path.parent.exists()
    dependencies["zip_and_upload_fgdb"].assert_called_once_with(output_path, gis)
    dependencies["update_feature_services"].assert_called_once_with(
        dependencies["zip_and_upload_fgdb"].return_value,
        [timestamp_table],
        lookup,
        hashes,
        {timestamp_table: 10},
        gis,
    )
    assert dependencies["set_preferred_time_reference"].call_count == 2


def test_migration_reports_failures_after_attempting_all_services(dependencies):
    dependencies["get_agol_items_lookup"].return_value = {
        "sgid.society.cemeteries": {"item_id": "service-1"},
        "sgid.transportation.roads": {"item_id": "service-2"},
    }
    gis = dependencies["get_gis_connection"].return_value
    gis.content.get.side_effect = [None, Mock()]

    with pytest.raises(RuntimeError, match="service-1"):
        migration.migrate_existing_services()

    assert gis.content.get.call_count == 2
    dependencies["set_preferred_time_reference"].assert_called_once()


@pytest.mark.parametrize("missing_hash", [True, False])
def test_migration_reports_missing_hash_or_failed_data_refresh(
    dependencies, missing_hash
):
    table = "sgid.transportation.roads"
    dependencies["get_agol_items_lookup"].return_value = {
        table: {"item_id": "service-1"},
    }
    dependencies["_get_datetime_field_names"].return_value = {"updated"}
    dependencies["get_current_hashes"].return_value = (
        {} if missing_hash else {table: "hash"}
    )
    dependencies["update_feature_services"].return_value = set()

    with pytest.raises(RuntimeError, match="service-1"):
        migration.migrate_existing_services()

    dependencies["set_preferred_time_reference"].assert_not_called()
    if missing_hash:
        dependencies["create_fgdb"].assert_not_called()
    else:
        dependencies["update_feature_services"].assert_called_once()


def test_migration_dry_run_lists_refreshes_without_writes(dependencies, caplog):
    dependencies["get_agol_items_lookup"].return_value = {
        "sgid.society.cemeteries": {"item_id": "service-1"},
        "sgid.transportation.roads": {"item_id": "service-2"},
    }
    dependencies["_get_datetime_field_names"].side_effect = [set(), {"updated"}]

    with caplog.at_level("INFO"):
        migration.migrate_existing_services(dry_run=True)

    assert "Metadata only: sgid.society.cemeteries" in caplog.text
    assert "Would force data refresh: sgid.transportation.roads" in caplog.text
    assert "datetime fields: updated" in caplog.text
    dependencies["get_gis_connection"].assert_not_called()
    dependencies["get_current_hashes"].assert_not_called()
    dependencies["create_fgdb"].assert_not_called()
    dependencies["update_feature_services"].assert_not_called()
    dependencies["set_preferred_time_reference"].assert_not_called()
