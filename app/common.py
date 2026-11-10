"""Helpers shared by all app pages: cached data, the current proposal, and display utilities."""

import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))   # so `import riskfit` works when run with `streamlit run app/streamlit_app.py`

import matplotlib.pyplot as plt  # noqa: E402
import streamlit as st  # noqa: E402

from riskfit.config import DEFAULT_EQUITY_STYLE  # noqa: E402
from riskfit.data.loader import load_prices  # noqa: E402
from riskfit.optimiser.frontier import efficient_frontier  # noqa: E402
from riskfit.optimiser.mean_variance import build_all_profiles, market_inputs  # noqa: E402

EXAMPLES_DIR = ROOT / "examples"
DISCLAIMER = "For illustration only. Not investment advice. All clients are fictional."

PAGES = {
    "questionnaire": "views/questionnaire.py",
    "portfolio": "views/portfolio.py",
    "stress": "views/stress_tests.py",
    "download": "views/download.py",
}


# Data and model inputs are cached per equity style ("global" or "hk_tilt"),
# so they load once per app session rather than on every click.
@st.cache_data
def get_prices(equity_style=DEFAULT_EQUITY_STYLE):
    return load_prices(equity_style)


@st.cache_data
def get_market_inputs(equity_style=DEFAULT_EQUITY_STYLE):
    return market_inputs(get_prices(equity_style))


@st.cache_data
def get_frontier(equity_style=DEFAULT_EQUITY_STYLE):
    mu, cov = get_market_inputs(equity_style)
    return efficient_frontier(mu, cov)


@st.cache_data
def get_profile_portfolios(equity_style=DEFAULT_EQUITY_STYLE):
    mu, cov = get_market_inputs(equity_style)
    return build_all_profiles(mu, cov)


def require_proposal():
    """Return the current client's proposal, or stop the page with a pointer to the questionnaire."""
    proposal = st.session_state.get("proposal")
    if proposal is None:
        st.info("No client yet. Please complete the client questionnaire first.")
        st.page_link(PAGES["questionnaire"], label="Go to the client questionnaire", icon=":material/arrow_back:")
        st.stop()
    return proposal


def show_figure(fig, width="stretch", transparent=False):
    """Render a matplotlib figure as a sharp PNG."""
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=200, bbox_inches="tight", transparent=transparent)
    plt.close(fig)
    st.image(buffer, width=width)
