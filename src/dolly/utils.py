import json
import logging
from pathlib import Path
from time import sleep
from uuid import UUID

module_logger = logging.getLogger(__name__)

RETRY_MAX_TRIES = 3
RETRY_DELAY_TIME = 2

OUTPUT_PATH = Path("output")
FGDB_PATH = OUTPUT_PATH / "upload.gdb"


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
        FileNotFoundError: If the secrets file can't be found.

    Returns:
        dict: The secrets .json loaded as a dictionary
    """

    secret_folder = Path("/secrets")

    #: Try to get the secrets from the Cloud Function mount point
    #: TODO: update for cloud run
    if secret_folder.exists():
        return json.loads(Path("/secrets/app/secrets.json").read_text(encoding="utf-8"))

    #: Otherwise, try to load a local copy for local development
    secret_folder = Path(__file__).parent / "secrets"
    if secret_folder.exists():
        return json.loads((secret_folder / "secrets.json").read_text(encoding="utf-8"))

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


def is_running_on_cloud_run():
    """Check if the process is running in Google Cloud Run"""
    import os

    return os.getenv("K_SERVICE") is not None


def get_fgdb_name(table: str) -> str:
    """
    Get the FGDB name for a given table.
    """
    # Remove the 'sgid.' prefix and replace '.' with '_'
    """
    TODO - this determines the name of the feature service when publishing for the first time
    It does not match our existing convention. It outputs something like this: society_cemeteries,
    whereas our current convention is to use the table name as is, like "Cemeteries".

    TODO - branch on dev env and add a suffix
    """
    return table[5:].replace(".", "_").lower()
