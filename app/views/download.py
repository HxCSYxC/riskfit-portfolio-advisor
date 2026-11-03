"""Page 4: build the one-page PDF proposal and offer it for download."""

import re
from io import BytesIO

import streamlit as st

from common import DISCLAIMER, require_proposal, usd
from riskfit.config import ASSET_LABELS
from riskfit.report.pdf import build_pdf

proposal = require_proposal()
client, profile, portfolio = proposal.client, proposal.profile, proposal.portfolio

st.title("Download Proposal")
st.write("A one-page PDF written for the client: their profile, the recommended mix, what to expect, how it "
         "would have done in past crises, and a plain-English explanation.")

name, worst = proposal.worst
st.markdown(
    f"- **Client:** {client.name}, age {client.age}, investing {usd(client.investment_amount)}\n"
    f"- **Profile:** {profile.profile.name}\n"
    f"- **Allocation:** " + ", ".join(f"{ASSET_LABELS[a]} {w:.0%}" for a, w in portfolio.weights.items()
                                       if w >= 0.005) + "\n"
    f"- **Worst historical fall:** {worst.max_drawdown:.0%} ({name})"
)


@st.cache_data(show_spinner="Building the PDF...")
def pdf_bytes(_proposal, cache_key):
    """The PDF as bytes. `cache_key` identifies the proposal, so it is rebuilt only when the client changes."""
    buffer = BytesIO()
    build_pdf(_proposal, buffer)
    return buffer.getvalue()


cache_key = (client.name, client.investment_amount, tuple(client.answers.values()),
             client.horizon, client.max_loss, client.liquidity, str(proposal.created))
file_name = "riskfit_proposal_" + re.sub(r"[^a-z0-9]+", "_", client.name.lower()).strip("_") + ".pdf"
st.download_button("Download PDF proposal", data=pdf_bytes(proposal, cache_key), file_name=file_name,
                   mime="application/pdf", type="primary", icon=":material/download:")
st.caption(DISCLAIMER)
