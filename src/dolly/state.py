"""State management functions for Dolly Carton using Firestore."""

import logging
import os
from datetime import datetime, timedelta

# Conditional import for Firestore (only needed in production)
firestore = None
if os.getenv("APP_ENVIRONMENT") == "prod":
    from google.cloud import firestore

logger = logging.getLogger(__name__)

# Get environment setting
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "dev")


def get_last_checked() -> datetime:
    """
    Get the last time the change detection was checked.
    In production, this is stored in Firestore and will raise exceptions if it fails.
    In dev, it returns yesterday.
    """
    if APP_ENVIRONMENT == "prod" and firestore is not None:
        db = firestore.Client()
        doc_ref = db.collection("dolly-carton").document("state")
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            if data and "last_checked" in data:
                # Firestore stores timestamps as datetime objects
                return data["last_checked"]

        # If document doesn't exist or doesn't have last_checked, raise an exception
        raise ValueError(
            "No last_checked timestamp found in Firestore. Initial setup may be required."
        )

    elif APP_ENVIRONMENT == "prod" and firestore is None:
        raise ImportError(
            "Firestore is required in production but google-cloud-firestore is not available"
        )
    else:
        # In dev environment, return yesterday
        return datetime.now() - timedelta(days=1)


def set_last_checked(timestamp: datetime) -> None:
    """
    Set the last checked timestamp.
    In production, this is stored in Firestore and will raise exceptions if it fails.
    In dev, this is a no-op.
    """
    if APP_ENVIRONMENT == "prod" and firestore is not None:
        db = firestore.Client()
        doc_ref = db.collection("dolly-carton").document("state")
        doc_ref.set({"last_checked": timestamp}, merge=True)
        logger.info(f"Updated last_checked in Firestore to {timestamp}")
    elif APP_ENVIRONMENT == "prod" and firestore is None:
        raise ImportError(
            "Firestore is required in production but google-cloud-firestore is not available"
        )
    else:
        # In dev environment, just log
        logger.info(f"Dev environment: would set last_checked to {timestamp}")
