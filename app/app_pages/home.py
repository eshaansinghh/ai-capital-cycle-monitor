import streamlit as st

st.title("AI Capital Cycle Monitor")
st.subheader("Bubble, buildout or both?")

st.markdown(
    "Are public markets pricing the AI capital cycle faster than cash flows, utilisation and "
    "monetisation can justify, and where is the better risk-adjusted opportunity across US AI "
    "leaders, AI infrastructure providers and European banks?"
)

st.info(
    "**Status: Phase 2, one-company vertical slice.** Only Microsoft's quarterly revenue, "
    "operating cash flow, capex and base free cash flow are built, from SEC filings. There are "
    "no findings yet. Other companies, relative value, compute economics and event studies "
    "come in later phases.",
    icon=":material/construction:",
)

with st.container(border=True):
    st.markdown("**How this project handles data**")
    st.markdown(
        "- Every number traces to a source in `data/source_registry.csv` or an explicit formula.\n"
        "- Reported, derived and modelled values are labelled and never mixed.\n"
        "- Missing values stay missing. Nothing is zero-filled or estimated.\n"
        "- No mock or synthetic data appears in any chart."
    )

st.caption("Educational research, not investment advice.")
