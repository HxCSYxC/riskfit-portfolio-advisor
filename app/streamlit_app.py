"""RiskFit Streamlit app.

Run from the project root:
    streamlit run app/streamlit_app.py
"""

import streamlit as st

from common import DISCLAIMER, PAGES

st.set_page_config(page_title="RiskFit: Portfolio Proposal Engine", page_icon=":material/donut_large:",
                   layout="wide")

pages = [
    st.Page(PAGES["questionnaire"], title="1. Client Questionnaire", icon=":material/assignment:", default=True),
    st.Page(PAGES["portfolio"], title="2. Recommended Portfolio", icon=":material/donut_large:"),
    st.Page(PAGES["stress"], title="3. Stress Tests", icon=":material/trending_down:"),
    st.Page(PAGES["download"], title="4. Download Proposal", icon=":material/download:"),
]

with st.sidebar:
    st.markdown("### RiskFit")
    st.caption("Private wealth portfolio proposal engine")
    proposal = st.session_state.get("proposal")
    if proposal is not None:
        st.markdown(f"**Client:** {proposal.client.name}  \n**Profile:** {proposal.profile.profile.name}")

current = st.navigation(pages)

with st.sidebar:
    st.divider()
    st.caption(DISCLAIMER)

current.run()
