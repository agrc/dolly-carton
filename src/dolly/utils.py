import concurrent.futures
import inspect
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

#: Default timeout (in seconds) for AGOL calls that otherwise have no
#: client-side timeout. Used by `call_with_timeout` as a safety net so that
#: functions like `append`, `truncate`, and `publish` cannot hang forever if
#: AGOL leaves a job in a pending state indefinitely.
AGOL_CALL_TIMEOUT = 20 * 60

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

    # Optional test-mode fast retry: when DOLLY_FAST_RETRY=1 is set in the
    # environment (e.g., within targeted pytest scopes), skip backoff sleeps.
    if os.getenv("DOLLY_FAST_RETRY") == "1":
        delay = 0

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


def _supports_future_kwarg(worker_method) -> bool:
    """Return True if ``worker_method`` accepts a ``future`` keyword argument.

    Used by :func:`call_with_timeout` to decide whether it can delegate to the
    ArcGIS API's own ``future=True`` mode, or must fall back to running the
    call in a :class:`~concurrent.futures.ThreadPoolExecutor`.
    """
    try:
        sig = inspect.signature(worker_method)
    except (TypeError, ValueError):
        return False

    for param in sig.parameters.values():
        if param.name == "future":
            return True
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            #: accepts **kwargs — assume the method forwards `future` through
            return True

    return False


def call_with_timeout(worker_method, timeout_seconds, *args, **kwargs):
    """Call an ArcGIS API function with a client-side timeout.

    Several ArcGIS Python API functions do not expose a timeout parameter, so
    if AGOL leaves a job in a pending state indefinitely those calls will
    hang forever. Some of them (e.g., :meth:`Item.publish`,
    :meth:`FeatureLayer.append`) accept ``future=True``, which changes their
    return type to a :class:`concurrent.futures.Future` that supports a
    timeout on :meth:`~concurrent.futures.Future.result`. Others (e.g.,
    :meth:`FeatureLayerManager.truncate`) do not accept ``future``; for those
    this helper runs the call in a :class:`ThreadPoolExecutor` so the
    timeout can still be enforced on the calling thread.

    When the target supports ``future``, ``future=True`` is injected into
    ``kwargs`` and the returned Future is awaited. Otherwise the call is
    submitted to a single-worker executor. In both cases, if the timeout
    elapses, a :class:`TimeoutError` is raised (and the future is cancelled
    on a best-effort basis). Note that in the executor fallback the worker
    thread cannot be forcibly cancelled once it has started running — but
    the calling thread is freed so :func:`retry` can take over.

    Args:
        worker_method (callable): The ArcGIS API method to invoke.
        timeout_seconds (float): Maximum number of seconds to wait for the
            underlying future to complete.
        *args: Positional arguments forwarded to ``worker_method``.
        **kwargs: Keyword arguments forwarded to ``worker_method``. When
            ``worker_method`` accepts a ``future`` parameter, ``future=True``
            is injected automatically.

    Raises:
        TimeoutError: If ``worker_method`` does not complete within
            ``timeout_seconds``.

    Returns:
        The value produced by ``worker_method`` (i.e., what it would normally
        return when called without ``future=True``).
    """
    executor = None
    if _supports_future_kwarg(worker_method):
        kwargs["future"] = True
        future = worker_method(*args, **kwargs)
    else:
        #: Fallback for ArcGIS functions like FeatureLayerManager.truncate
        #: that don't accept a `future` kwarg. Running the call in an
        #: executor lets us enforce a client-side timeout even though the
        #: underlying call remains synchronous/blocking in its own thread.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(worker_method, *args, **kwargs)

    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError as error:
        #: Best-effort cancellation; many ArcGIS futures cannot be cancelled
        #: once running, but we try anyway so resources are released when
        #: possible.
        try:
            future.cancel()
        except Exception:  # pragma: no cover - defensive
            module_logger.debug(
                "Failed to cancel future for %s after timeout", worker_method
            )

        raise TimeoutError(
            f"Call to {getattr(worker_method, '__qualname__', repr(worker_method))} "
            f"timed out after {timeout_seconds} seconds"
        ) from error
    finally:
        if executor is not None:
            #: Do not block shutdown on a potentially hung worker thread.
            executor.shutdown(wait=False)


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
