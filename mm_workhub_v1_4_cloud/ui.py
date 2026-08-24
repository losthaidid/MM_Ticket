from __future__ import annotations

import streamlit as st


def page_setup(title: str, icon: str = "📊"):
    st.set_page_config(page_title=f"MM WorkHub | {title}", page_icon=icon, layout="wide")
    st.markdown("""
    <style>
      .block-container {padding-top: 1.6rem; padding-bottom: 3rem;}
      [data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.22); padding: 14px; border-radius: 10px;}
      .muted {color:#808080;font-size:.9rem;}
      .ticket-card {padding:14px 16px;border:1px solid rgba(128,128,128,.24);border-radius:10px;margin-bottom:10px;}
    </style>
    """, unsafe_allow_html=True)
    st.title(title)


def status_badge(status):
    status = status or "Unknown"
    return status
