"""State management for per-table hash change detection using Firestore."""

import logging
import os
from typing import Dict

from google.cloud import firestore

logger = logging.getLogger(__name__)

COLLECTION = "dolly-carton"
DOCUMENT = "state"


def get_table_hashes() -> Dict[str, str]:
    """Retrieve the stored table hash map from Firestore.

    Returns:
        dict mapping lower-cased table names to their last successfully processed hash.

    Behavior:
        - prod/staging: reads Firestore; if document or field is missing, returns empty dict.
        - dev/other: returns empty dict (no persistence) so all current differences appear updated.
    """
    if os.environ["APP_ENVIRONMENT"] == "prod":
        db = firestore.Client()
        doc_ref = db.collection(COLLECTION).document(DOCUMENT)
        doc = doc_ref.get()
        if not doc.exists:
            logger.info(
                "No state document found in Firestore; starting with empty hash map"
            )

            return {}

        return doc.to_dict() or {}

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

    db = firestore.Client()
    doc_ref = db.collection(COLLECTION).document(DOCUMENT)

    updates = {table_lower: hash_value}

    doc_ref.set(updates, merge=True)

    logger.info(f"Updated hash for {table_lower} to {hash_value} in Firestore")
