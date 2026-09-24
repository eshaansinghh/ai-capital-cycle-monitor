import streamlit as st

st.set_page_config(
    page_title="AI Capital Cycle Monitor",
    page_icon=":material/monitoring:",
    layout="wide",
)

pages = [
    st.Page("app_pages/home.py", title="Overview", icon=":material/home:", default=True),
    st.Page("app_pages/capital_cycle.py", title="Capital cycle", icon=":material/bar_chart:"),
]
st.navigation(pages).run()
