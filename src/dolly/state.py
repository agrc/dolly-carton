"""State management for per-table hash change detection using Firestore."""

import logging
import os
from typing import Dict

APP_ENVIRONMENT = os.environ["APP_ENVIRONMENT"]
GCP_ENVIRONMENTS = {"prod", "staging"}


def is_running_in_gcp() -> bool:
    return APP_ENVIRONMENT in GCP_ENVIRONMENTS


# Conditional import for Firestore (only needed in prod/staging)
firestore = None
if is_running_in_gcp():
    try:  # pragma: no cover - import guard
        from google.cloud import firestore  # type: ignore
    except (ImportError, ModuleNotFoundError):  # pragma: no cover
        firestore = None

logger = logging.getLogger(__name__)

COLLECTION = "dolly-carton"
DOCUMENT = "state"


def _ensure_firestore_available() -> None:
    if is_running_in_gcp() and firestore is None:
        raise ImportError(
            "Firestore is required in production/staging but google-cloud-firestore is not available"
        )


def get_table_hashes() -> Dict[str, str]:
    """Retrieve the stored table hash map from Firestore.

    Returns:
        dict mapping lower-cased table names to their last successfully processed hash.

    Behavior:
        - prod/staging: reads Firestore; if document or field is missing, returns empty dict.
        - dev/other: returns empty dict (no persistence) so all current differences appear updated.
    """
    if is_running_in_gcp():
        _ensure_firestore_available()
        db = firestore.Client()  # type: ignore[attr-defined]
        doc_ref = db.collection(COLLECTION).document(DOCUMENT)
        doc = doc_ref.get()
        if not doc.exists:
            logger.info(
                "No state document found in Firestore; starting with empty hash map"
            )

            return {}
        data = doc.to_dict() or {}
        hashes = data.get("table_hashes", {}) or {}
        # Normalize keys to lower-case for consistent comparisons.
        normalized = {k.lower(): str(v) for k, v in hashes.items()}
        logger.info(f"Loaded {len(normalized)} table hash entries from Firestore")

        return normalized

    # dev or other environments
    logger.info("Dev environment: returning empty stored table hash map")

    return {}


def set_table_hash(table: str, hash_value: str) -> None:
    """Persist (or update) a single table hash after successful processing.

    Args:
        table: Fully qualified table name (will be stored lower-cased)
        hash_value: The hash string from ChangeDetection representing current table contents

    Behavior:
        - prod/staging: performs Firestore merge of nested map key
        - dev/other: logs only (no persistence)
    """
    table_lower = table.lower()

    if is_running_in_gcp():
        _ensure_firestore_available()
        db = firestore.Client()  # type: ignore[attr-defined]
        doc_ref = db.collection(COLLECTION).document(DOCUMENT)
        doc_ref.set({"table_hashes": {table_lower: hash_value}}, merge=True)
        logger.info(f"Updated hash for {table_lower} to {hash_value} in Firestore")

        return

    logger.info(
        f"Dev environment: would update hash for {table_lower} to {hash_value} (not persisted)"
    )
