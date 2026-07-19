"""TrailBuddy Streamlit entrypoint.

This file only wires up page configuration, one-time startup initialization,
and navigation between pages. All page rendering lives in `views/`, business
logic in `services/` and `llm/`, and data access in `db/`.
"""
import streamlit as st

from components.sidebar import render_ollama_status
from db.schema import initialize_db
from state import init_ollama_status
from views import chat, dashboard, history, ranking, upload

# Page configuration
st.set_page_config(
    page_title="TrailBuddy",
    page_icon="🥾",
    layout="wide"
)

# One-time startup initialization
initialize_db()
init_ollama_status()

# Sidebar
st.sidebar.title("TrailBuddy")
st.sidebar.markdown("Your personal hiking companion + AI buddy.")
render_ollama_status()

# Navigation
# Every page module exposes a function named `render`, so an explicit
# url_path is required for each — otherwise Streamlit infers the URL
# pathname from the callable name and every page collides on "render".
# position="hidden" disables Streamlit's built-in nav widget, which always
# renders itself at the very top of the sidebar (above our title/status)
# and can't be reordered. We render our own st.page_link list below instead,
# so it appears after the TrailBuddy branding as intended.
pages = [
    st.Page(dashboard.render, title="Dashboard", icon="📊", url_path="dashboard", default=True),
    st.Page(upload.render, title="Upload Hike", icon="⬆️", url_path="upload"),
    st.Page(history.render, title="History", icon="🕓", url_path="history"),
    st.Page(ranking.render, title="Ranking", icon="🏆", url_path="ranking"),
    st.Page(chat.render, title="Chat with TrailBuddy", icon="💬", url_path="chat"),
]
nav = st.navigation(pages, position="hidden")

st.sidebar.divider()
for page in pages:
    st.sidebar.page_link(page)

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("TrailBuddy v0.1 || Local & Private || Built for learning")

nav.run()
