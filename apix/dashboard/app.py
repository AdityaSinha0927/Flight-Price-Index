"""Streamlit multi-page entry point for the APIx dashboard."""

import streamlit as st


st.set_page_config(page_title="APIx Airfare Price Index", page_icon="✈️", layout="wide")

st.markdown(
    """
    <style>
    .block-container { max-width: 1400px; padding-top: 2rem; padding-bottom: 3rem; }
    div[data-testid="stAppViewContainer"] { font-family: "Segoe UI", Arial, sans-serif; }
    h1, h2, h3 { letter-spacing: -0.02em; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.sidebar.title("APIx Dashboard")
st.sidebar.caption("Select a page from the navigation.")

st.title("APIx — Real-time Airfare Price Index")
st.write("Choose a dashboard page from the sidebar to get started.")
