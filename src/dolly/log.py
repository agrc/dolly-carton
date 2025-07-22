import logging

from google.cloud.logging import Client

from dolly.utils import is_running_on_cloud_run

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def setup_logging():
    if is_running_on_cloud_run():
        try:
            client = Client()
            client.setup_logging(log_level=logging.DEBUG)
        except Exception as e:
            log.error("Failed to initialize Google Cloud Logging client: %s", e)
            log.warning("Continuing without Google Cloud Logging.")
