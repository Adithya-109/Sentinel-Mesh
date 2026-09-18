"""Smoke-test every UI page by actually running the Streamlit script.

Streamlit serves HTML before it ever executes the script, so "the port
answers" proves nothing -- a NameError on the Incidents page would only show
up when someone clicks it, which on demo day means on stage. AppTest runs the
script for real and surfaces exceptions.

These tests hit a live console API on :8000 when one is up, and assert the
page still renders when it is not: the UI must degrade to an error message,
never a traceback.
"""
import os
import sys

import pytest

CONSOLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONSOLE_DIR)

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(CONSOLE_DIR, "ui", "app.py")
PAGES = ["Timeline", "Incidents", "Scan", "Trace recording", "Evidence"]


def run_page(page: str, timeout: int = 60) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=timeout)
    at.run()
    # the sidebar radio selects the page; index into its options
    radio = at.sidebar.radio[0]
    radio.set_value(page).run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    at = run_page(page)
    assert not at.exception, f"{page} raised: {[e.value for e in at.exception]}"


def test_default_page_is_the_timeline():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    assert at.sidebar.radio[0].value == "Timeline"


def test_ui_survives_a_dead_console_api():
    """Points the app at a closed port; it must show an error, not crash."""
    at = AppTest.from_file(APP, default_timeout=60)
    os.environ["SENTINEL_CONSOLE_URL"] = "http://127.0.0.1:9"      # nothing listens here
    os.environ["SENTINEL_ML_URL"] = "http://127.0.0.1:9"
    try:
        at.run()
        assert not at.exception
        assert at.error, "a dead console should produce a visible error message"
    finally:
        os.environ.pop("SENTINEL_CONSOLE_URL", None)
        os.environ.pop("SENTINEL_ML_URL", None)
