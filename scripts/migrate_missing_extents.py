import argparse
import logging
from urllib.parse import urlsplit

from arcgis.features import FeatureLayerCollection
from arcgis.gis import GIS, Item

from dolly.agol import (
    ensure_feature_layer_extent,
    get_gis_connection,
    get_spatial_index,
    query_feature_layer_extent,
)
from dolly.utils import retry

logger = logging.getLogger(__name__)

SEARCH_PAGE_SIZE = 100
SEARCH_LIMIT = 10_000


def _organization_services(gis: GIS, item_id: str | None) -> list[Item]:
    org_id = gis.properties.get("id")
    if not isinstance(org_id, str) or not org_id:
        raise RuntimeError("The ArcGIS organization ID is unavailable")
    if gis.users.me is None or gis.users.me.role != "org_admin":
        raise PermissionError("An organization administrator is required")

    if item_id:
        item = retry(gis.content.get, item_id)
        if item is None:
            raise LookupError(f"AGOL item {item_id} was not found")
        items = [item]
    else:
        query = f'orgid:{org_id} AND type:"Feature Service"'
        items = []
        start = 1
        expected_total = None
        while True:
            response = retry(
                gis.content.advanced_search,
                query=query,
                start=start,
                max_items=SEARCH_PAGE_SIZE,
            )
            if not isinstance(response, dict) or not isinstance(
                response.get("results"), list
            ):
                raise TypeError("Invalid AGOL organization search response")
            total = response.get("total")
            if not isinstance(total, int) or total < 0:
                raise RuntimeError("AGOL organization search did not return a total")
            if total >= SEARCH_LIMIT:
                raise RuntimeError(
                    "AGOL search reached its 10,000-item limit; inventory is incomplete"
                )
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                raise RuntimeError("AGOL organization inventory changed during search")

            page = response["results"]
            items.extend(page)
            next_start = response.get("nextStart")
            if next_start == -1:
                break
            if not isinstance(next_start, int) or next_start <= start or not page:
                raise RuntimeError("AGOL organization search returned an invalid page")
            start = next_start

        if len(items) != expected_total or len({item.id for item in items}) != len(
            items
        ):
            raise RuntimeError(
                "AGOL organization search returned an incomplete inventory"
            )

    for item in items:
        if item["orgId"] != org_id or item.type != "Feature Service":
            raise ValueError(
                f"Item {item.id} is not a feature service in this organization"
            )
    return items


def _validate_hosted_service_url(item: Item, org_id: str) -> None:
    url = item.url
    if not isinstance(url, str):
        raise TypeError(f"Hosted feature service {item.id} has no URL")
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or not parts.hostname.endswith(".arcgis.com")
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.path.strip("/").split("/")[0] != org_id
    ):
        raise ValueError(f"Hosted feature service {item.id} has an unexpected URL")


def migrate_missing_extents(
    gis: GIS, *, apply: bool = False, item_id: str | None = None
) -> None:
    """Inspect hosted layers in the organization and optionally repair missing extents."""
    items = _organization_services(gis, item_id)
    org_id = gis.properties["id"]
    failures: list[str] = []
    manual_review: list[str] = []
    candidates = 0
    logger.info("Inspecting %s feature service item(s)", len(items))

    for item in items:
        try:
            keywords = item.typeKeywords
            if not isinstance(keywords, list):
                raise TypeError("Feature service type keywords are unavailable")
            if "Hosted Service" not in keywords:
                logger.info("Skipping non-hosted service %s", item.id)
                continue
            _validate_hosted_service_url(item, org_id)
            layers = FeatureLayerCollection.fromitem(item).layers
            if not isinstance(layers, list):
                raise TypeError("Feature service layers are unavailable")
        except Exception:
            logger.exception("Failed to inspect service %s", item.id)
            failures.append(item.id)
            continue

        for layer in layers:
            try:
                properties = layer.properties
                if not properties.get("geometryType"):
                    logger.info("Skipping non-spatial layer %s", layer.url)
                    continue
                if properties.get("extent") is not None:
                    continue
                if query_feature_layer_extent(layer) is None:
                    logger.info(
                        "Skipping layer without spatial features: %s", layer.url
                    )
                    continue
                if "View Service" in keywords or properties.get("isView"):
                    logger.warning("Hosted view requires manual review: %s", layer.url)
                    manual_review.append(layer.url)
                    continue

                get_spatial_index(layer)
                candidates += 1
                if apply:
                    if layer.manager.properties.get("extent") is not None:
                        logger.info("Layer now has an extent; skipping: %s", layer.url)
                    elif ensure_feature_layer_extent(layer, force_rebuild=True):
                        logger.info("Processed missing extent: %s", layer.url)
                else:
                    logger.info("Would rebuild spatial index: %s", layer.url)
            except Exception:
                logger.exception("Failed to inspect or repair layer %s", layer.url)
                failures.append(layer.url)

    logger.info("Found %s repair candidate(s)", candidates)
    if failures or manual_review:
        raise RuntimeError(
            f"{len(failures)} service/layer failure(s); "
            f"{len(manual_review)} affected hosted view(s) require manual review"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect hosted feature layers with missing extents. "
            "The default is a read-only dry run."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Rebuild spatial indexes for affected, non-view hosted layers.",
    )
    parser.add_argument(
        "--item-id",
        help="Inspect only this feature service item in the connected organization.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    migrate_missing_extents(
        get_gis_connection(), apply=args.apply, item_id=args.item_id
    )


if __name__ == "__main__":
    main()
