"""Smoke test of the Streamlit app: submit an example client and open every page without errors."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from riskfit.config import PROJECT_ROOT  # noqa: E402

APP = str(PROJECT_ROOT / "app" / "streamlit_app.py")


@pytest.fixture(scope="module")
def app():
    if not (PROJECT_ROOT / "riskfit" / "data" / "cache" / "prices.csv").exists():
        pytest.skip("price cache not available")
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def test_questionnaire_scores_example_client(app):
    assert not app.exception
    app.selectbox[0].select_index(2).run()          # "Example: Ms Lee Ka Yan"
    app.button[0].click().run()                      # "Score client and build portfolio"
    assert not app.exception
    assert app.session_state["proposal"].profile.profile.name == "Balanced"


@pytest.mark.parametrize("page, title", [
    ("views/portfolio.py", "Recommended Portfolio"),
    ("views/stress_tests.py", "Stress Tests"),
    ("views/download.py", "Download Proposal"),
])
def test_each_page_renders(app, page, title):
    app.switch_page(page).run()
    assert not app.exception
    assert app.title[0].value == title


def test_blank_form_shows_error():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.button[0].click().run()
    assert any("client's name" in e.value for e in at.error)
