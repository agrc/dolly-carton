"""Shared pytest fixtures.

This file provides a global (autouse) fixture to prevent any real Slack
webhook posts during tests. Several tests indirectly call
`dolly.summary.finish_summary()`, which posts to Slack if a webhook URL is
configured via secrets. By mocking `requests.post` inside `dolly.summary`, we
ensure no external HTTP requests are made while preserving behavior for tests
that explicitly patch Slack posting themselves.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_slack_webhook(monkeypatch):
    """Mock Slack webhook posting globally for all tests.

    - Replaces `requests.post` used in `dolly.summary` with a MagicMock that
      returns a 200 OK response by default.
    - Tests that need to simulate different Slack responses can still override
      this using their own patching within the test scope.
    """
    # Import within fixture to ensure module is loaded in test runtime
    import dolly.summary as summary

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"

    mock_post = MagicMock(return_value=mock_response)

    # Patch the requests.post used inside the summary module only
    monkeypatch.setattr(summary.requests, "post", mock_post)

    # Yield to allow tests to run with the patched function
    yield


@pytest.fixture(autouse=True)
def fast_retry_for_tests(monkeypatch, request):
    """Enable fast retries for tests by default.

    Sets DOLLY_FAST_RETRY=1 for all tests to avoid exponential backoff sleeps
    and speed up the suite. Skip this for tests marked with @pytest.mark.real_backoff
    """
    if request.node.get_closest_marker("real_backoff") is not None:
        monkeypatch.delenv("DOLLY_FAST_RETRY", raising=False)
        return

    monkeypatch.setenv("DOLLY_FAST_RETRY", "1")
