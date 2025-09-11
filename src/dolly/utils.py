import json
import logging
import os
import re
import sys
from pathlib import Path
from time import sleep
from uuid import UUID

module_logger = logging.getLogger(__name__)

RETRY_MAX_TRIES = 3
RETRY_DELAY_TIME = 2

OUTPUT_PATH = Path("output")
FGDB_PATH = OUTPUT_PATH / "upload.gdb"
APP_ENVIRONMENT = os.environ["APP_ENVIRONMENT"]


#: copied from palletjack
def retry(worker_method, *args, **kwargs):
    """Allows you to retry a function/method to overcome network jitters or other transient errors.

    Retries worker_method RETRY_MAX_TRIES times (for a total of n+1 tries, including the initial attempt), pausing
    2^RETRY_DELAY_TIME seconds between each retry. Any arguments for worker_method can be passed in as additional
    parameters to retry() following worker_method: retry(foo_method, arg1, arg2, keyword_arg=3).

    RETRY_MAX_TRIES and RETRY_DELAY_TIME default to 3 tries and 2 seconds, but can be overridden by setting the
    palletjack.utils.RETRY_MAX_TRIES and palletjack.utils.RETRY_DELAY_TIME constants in the client script.

    Args:
        worker_method (callable): The name of the method to be retried (minus the calling parens)

    Raises:
        error: The final error that causes worker_method to fail after 3 retries

    Returns:
        various: The value(s) returned by worked_method
    """
    tries = 1
    max_tries = RETRY_MAX_TRIES
    delay = RETRY_DELAY_TIME  #: in seconds

    #: this inner function (closure? almost-closure?) allows us to keep track of tries without passing it as an arg
    def _inner_retry(worker_method, *args, **kwargs):
        nonlocal tries

        try:
            return worker_method(*args, **kwargs)

        #: ArcGIS API for Python loves throwing bog-standard Exceptions, so we can't narrow this down further
        except Exception as error:
            if tries <= max_tries:  # pylint: disable=no-else-return
                wait_time = delay**tries
                module_logger.debug(
                    'Exception "%s" thrown on "%s". Retrying after %s seconds...',
                    error,
                    worker_method,
                    wait_time,
                )
                sleep(wait_time)
                tries += 1

                return _inner_retry(worker_method, *args, **kwargs)
            else:
                raise error

    return _inner_retry(worker_method, *args, **kwargs)


def get_secrets():
    """A helper method for loading secrets from either a cloud run mount point or the local secrets.json file

    Raises:
        FileNotFoundError: If the secrets file can't be found and not in testing mode.

    Returns:
        dict: The secrets .json loaded as a dictionary, or mock secrets for testing
    """
    #: Try to get the secrets from the Cloud Run mount point
    cloud_secrets_file = Path("/secrets") / "app" / "secrets.json"
    if cloud_secrets_file.exists():
        return json.loads(cloud_secrets_file.read_text(encoding="utf-8"))

    #: Otherwise, try to load a local copy for local development
    local_secrets_file = (
        Path(__file__).parent / "secrets" / f"secrets.{APP_ENVIRONMENT}.json"
    )
    if local_secrets_file.exists():
        return json.loads(local_secrets_file.read_text(encoding="utf-8"))

    #: If we're in a testing environment (pytest is running), return mock secrets
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        return {
            "AGOL_USERNAME": "test_username",
            "AGOL_PASSWORD": "test_password",
            "INTERNAL_HOST": "test_host",
            "INTERNAL_USERNAME": "test_user",
            "INTERNAL_PASSWORD": "test_password",
            "INTERNAL_DATABASE": "test_db",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test/webhook",
        }

    raise FileNotFoundError("Secrets folder not found; secrets not loaded.")


def is_guid(value: str) -> bool:
    """
    Check if a string is a valid GUID.
    """
    try:
        UUID(value)

        return True
    except ValueError:
        return False


def get_service_from_title(title):
    """
    Convert a title to a standardized service name by removing "Utah" and replacing spaces with underscores.
    This is copied from cloudb (https://github.com/agrc/open-sgid)
    """
    if title is None:
        return title

    # Handle edge case where title would result in empty string after processing
    if title.lower().strip() in ["utah", "utah "]:
        raise ValueError(f"Title '{title}' would result in empty service name")

    new_title = title.lower()

    #: only remove "Utah" if it is at the beginning of the title
    if new_title.startswith("utah "):
        new_title = new_title.replace("utah ", "", 1)

    # Normalize multiple spaces to single spaces before replacing with underscores
    new_title = re.sub(r"\s+", " ", new_title).strip()
    new_title = new_title.replace(" ", "_")

    logging.debug("updating %s to %s", title, new_title)

    return new_title


def get_gdal_layer_name(table: str) -> str:
    """
    Convert a table name to GDAL layer name format.

    Args:
        table: Table name in format "sgid.schema.table"

    Returns:
        GDAL layer name in format "Schema.TABLE"

    Example:
        "sgid.transportation.roads" -> "Transportation.ROADS"
    """
    parts = table.split(".")
    if len(parts) != 3:
        raise ValueError(f"Table name '{table}' must be in format 'sgid.schema.table'")

    schema = parts[1].title()  # Capitalize first letter of each word
    table_name = parts[2].upper()  # Convert to uppercase

    return f"{schema}.{table_name}"


# Feature counting functionality
def count_features_in_internal_table(table: str, connection=None) -> int:
    """
    Count features in an internal database table.

    This function is a placeholder that will be implemented with database connection logic.
    It's placed in utils.py to allow for mocking in tests.

    Args:
        table: Table name in format "sgid.schema.table"
        connection: Database connection (optional, for dependency injection in tests)

    Returns:
        Number of features in the table

    Note:
        This function will be called from internal.py where the actual
        database connection logic will be implemented.
    """
    # This is a placeholder - actual implementation will be in internal.py
    # but the interface is defined here for testing purposes
    raise NotImplementedError(
        "This function should be called with proper database connection from internal.py"
    )


def count_features_in_fgdb_layer(fgdb_path, layer_name: str) -> int:
    """
    Count features in a File Geodatabase layer.

    This function is a placeholder that will be implemented with GDAL logic.
    It's placed in utils.py to allow for mocking in tests.

    Args:
        fgdb_path: Path to the File Geodatabase
        layer_name: Name of the layer within the FGDB

    Returns:
        Number of features in the layer

    Note:
        This function will be called from internal.py where the actual
        GDAL connection logic will be implemented.
    """
    # This is a placeholder - actual implementation will use GDAL
    # but the interface is defined here for testing purposes
    raise NotImplementedError(
        "This function should be called with proper GDAL logic from internal.py"
    )


def count_features_in_agol_service(service_item) -> int:
    """
    Count features in an ArcGIS Online service.

    This function is a placeholder that will be implemented with ArcGIS API logic.
    It's placed in utils.py to allow for mocking in tests.

    Args:
        service_item: ArcGIS service item (Table or FeatureLayer)

    Returns:
        Number of features in the service

    Note:
        This function will be called from agol.py where the actual
        ArcGIS API logic will be implemented.
    """
    # This is a placeholder - actual implementation will use ArcGIS API
    # but the interface is defined here for testing purposes
    raise NotImplementedError(
        "This function should be called with proper ArcGIS API logic from agol.py"
    )
