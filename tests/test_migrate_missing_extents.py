import sys
from unittest.mock import Mock, call

import pytest

from scripts import migrate_missing_extents as migration


@pytest.fixture
def gis():
    connection = Mock()
    connection.properties = {"id": "test-org"}
    connection.users.me.role = "org_admin"
    return connection


@pytest.fixture
def dependencies(monkeypatch):
    mocks = {
        "FeatureLayerCollection": Mock(),
        "query_feature_layer_extent": Mock(),
        "get_spatial_index": Mock(),
        "ensure_feature_layer_extent": Mock(return_value=True),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(migration, name, mock)
    return mocks


def make_item(item_id, keywords=None, org_id="test-org"):
    item = Mock()
    item.id = item_id
    item.type = "Feature Service"
    item.typeKeywords = ["Hosted Service"] if keywords is None else keywords
    item.url = f"https://services.arcgis.com/{org_id}/arcgis/rest/services/{item_id}/FeatureServer"
    item.get.side_effect = lambda key: org_id if key == "orgId" else None
    return item


def make_layer(item, layer_id, *, extent=None, geometry_type="esriGeometryPoint"):
    layer = Mock()
    layer.url = f"{item.url}/{layer_id}"
    layer.properties = {"geometryType": geometry_type, "extent": extent}
    layer.manager.properties = {"extent": extent}
    return layer


def test_dry_run_paginates_and_reports_affected_views(gis, dependencies, caplog):
    hosted = make_item("hosted")
    view = make_item("view", ["Hosted Service", "View Service"])
    non_hosted = make_item("external", [])
    missing = make_layer(hosted, 0)
    healthy = make_layer(hosted, 1, extent={"xmin": 1})
    empty = make_layer(hosted, 2)
    table = make_layer(hosted, 3, geometry_type=None)
    affected_view = make_layer(view, 0)
    healthy_view = make_layer(view, 1, extent={"xmin": 1})
    collections = {
        hosted: Mock(layers=[missing, healthy, empty, table]),
        view: Mock(layers=[affected_view, healthy_view]),
    }
    dependencies["FeatureLayerCollection"].fromitem.side_effect = collections.get
    dependencies["query_feature_layer_extent"].side_effect = {
        missing: {"xmin": 1},
        empty: None,
        affected_view: {"xmin": 1},
    }.get
    gis.content.advanced_search.side_effect = [
        {"total": 3, "results": [hosted, view], "nextStart": 3},
        {"total": 3, "results": [non_hosted], "nextStart": -1},
    ]

    with (
        caplog.at_level("INFO"),
        pytest.raises(RuntimeError, match="1 affected hosted view"),
    ):
        migration.migrate_missing_extents(gis)

    assert gis.content.advanced_search.call_args_list == [
        call(
            query='accountid:test-org AND type:"Feature Service"',
            start=1,
            max_items=100,
        ),
        call(
            query='accountid:test-org AND type:"Feature Service"',
            start=3,
            max_items=100,
        ),
    ]
    assert f"Would rebuild spatial index: {missing.url}" in caplog.text
    assert f"Hosted view requires manual review: {affected_view.url}" in caplog.text
    assert "Skipping non-hosted service external" in caplog.text
    dependencies["get_spatial_index"].assert_called_once_with(missing)
    dependencies["ensure_feature_layer_extent"].assert_not_called()


def test_apply_repairs_only_missing_nonempty_layers(gis, dependencies):
    item = make_item("hosted")
    missing = make_layer(item, 0)
    healthy = make_layer(item, 1, extent={"xmin": 1})
    empty = make_layer(item, 2)
    gis.content.get.return_value = item
    dependencies["FeatureLayerCollection"].fromitem.return_value.layers = [
        missing,
        healthy,
        empty,
    ]
    dependencies["query_feature_layer_extent"].side_effect = {
        missing: {"xmin": 1},
        empty: None,
    }.get

    migration.migrate_missing_extents(gis, apply=True, item_id=item.id)

    gis.content.get.assert_called_once_with(item.id)
    gis.content.advanced_search.assert_not_called()
    dependencies["get_spatial_index"].assert_called_once_with(missing)
    dependencies["ensure_feature_layer_extent"].assert_called_once_with(
        missing, force_rebuild=True
    )


def test_layer_that_gains_an_extent_is_not_rebuilt(gis, dependencies):
    item = make_item("hosted")
    missing = make_layer(item, 0)
    missing.manager.properties["extent"] = {"xmin": 1}
    gis.content.get.return_value = item
    dependencies["FeatureLayerCollection"].fromitem.return_value.layers = [missing]
    dependencies["query_feature_layer_extent"].return_value = {"xmin": 1}

    migration.migrate_missing_extents(gis, apply=True, item_id=item.id)

    dependencies["ensure_feature_layer_extent"].assert_not_called()


def test_migration_reports_failures_after_attempting_other_layers(gis, dependencies):
    item = make_item("hosted")
    first = make_layer(item, 0)
    second = make_layer(item, 1)
    gis.content.get.return_value = item
    dependencies["FeatureLayerCollection"].fromitem.return_value.layers = [
        first,
        second,
    ]
    dependencies["query_feature_layer_extent"].return_value = {"xmin": 1}
    dependencies["ensure_feature_layer_extent"].side_effect = [
        RuntimeError("rebuild failed"),
        True,
    ]

    with pytest.raises(RuntimeError, match="1 service/layer failure"):
        migration.migrate_missing_extents(gis, apply=True, item_id=item.id)

    assert dependencies["ensure_feature_layer_extent"].call_args_list == [
        call(first, force_rebuild=True),
        call(second, force_rebuild=True),
    ]


@pytest.mark.parametrize(
    "response",
    [
        {"total": 10_000, "results": [], "nextStart": -1},
        {"total": 1, "results": [], "nextStart": -1},
        {"total": 1, "results": [], "nextStart": 1},
    ],
)
def test_incomplete_organization_inventory_aborts_before_writes(
    gis, dependencies, response
):
    gis.content.advanced_search.return_value = response

    with pytest.raises(RuntimeError):
        migration.migrate_missing_extents(gis, apply=True)

    dependencies["FeatureLayerCollection"].fromitem.assert_not_called()
    dependencies["ensure_feature_layer_extent"].assert_not_called()


def test_rejects_an_item_from_another_organization(gis, dependencies):
    gis.content.get.return_value = make_item("outside", org_id="other-org")

    with pytest.raises(ValueError, match="not a feature service in this organization"):
        migration.migrate_missing_extents(gis, apply=True, item_id="outside")

    dependencies["FeatureLayerCollection"].fromitem.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "https://name:password@services.arcgis.com/test-org/FeatureServer",
        "https://services.arcgis.com/test-org/FeatureServer?token=password",
        "https://services.arcgis.com/test-org/FeatureServer#password",
    ],
)
def test_rejects_unexpected_hosted_url_without_exposing_credentials(
    gis, dependencies, caplog, url
):
    item = make_item("hosted")
    item.url = url
    gis.content.get.return_value = item

    with pytest.raises(RuntimeError, match="1 service/layer failure"):
        migration.migrate_missing_extents(gis, apply=True, item_id=item.id)

    assert "password" not in caplog.text
    dependencies["FeatureLayerCollection"].fromitem.assert_not_called()


def test_requires_organization_administrator(gis, dependencies):
    gis.users.me.role = "org_user"

    with pytest.raises(PermissionError, match="organization administrator"):
        migration.migrate_missing_extents(gis, apply=True)

    gis.content.advanced_search.assert_not_called()
    dependencies["ensure_feature_layer_extent"].assert_not_called()


def test_cli_defaults_to_read_only(monkeypatch, gis):
    run_migration = Mock()
    monkeypatch.setattr(migration, "get_gis_connection", Mock(return_value=gis))
    monkeypatch.setattr(migration, "migrate_missing_extents", run_migration)
    monkeypatch.setattr(sys, "argv", ["migrate_missing_extents"])

    migration.main()

    run_migration.assert_called_once_with(gis, apply=False, item_id=None)
