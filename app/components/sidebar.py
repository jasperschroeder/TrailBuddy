"""Sidebar widgets shared across all pages."""
import streamlit as st

from state import OLLAMA_STATUS, refresh_ollama_status


def render_ollama_status() -> None:
    """Render the Ollama availability indicator and retry button."""
    status = st.session_state[OLLAMA_STATUS]
    if status["running"]:
        st.sidebar.success("🟢 AI Available")
    else:
        st.sidebar.error("🔴 AI Unavailable")
        st.sidebar.caption(status["message"])
        if st.sidebar.button("🔄 Retry Starting Ollama"):
            refresh_ollama_status()
            st.rerun()
