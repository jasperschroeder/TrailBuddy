"""Session-state key constants and shared session-state helpers.

Centralizing the key names avoids typo-prone string literals scattered
across page modules.
"""
import streamlit as st

from utils.ollama_service import start_ollama_service

OLLAMA_STATUS = "ollama_status"
CHAT_MESSAGES = "chat_messages"
EDITING_HIKE_ID = "editing_hike_id"
CONFIRM_DELETE_ID = "confirm_delete_id"
VIEWING_HIKE_ID = "viewing_hike_id"
UPLOAD_FORM_VERSION = "upload_form_version"
RESET_UPLOAD_FORM = "reset_upload_form"


def refresh_ollama_status() -> None:
    """(Re)check/start Ollama and store the result in session state."""
    is_running, status_msg = start_ollama_service()
    st.session_state[OLLAMA_STATUS] = {"running": is_running, "message": status_msg}


def init_ollama_status() -> None:
    """Ensure ollama status is present in session state, starting Ollama if needed."""
    if OLLAMA_STATUS not in st.session_state:
        refresh_ollama_status()


def is_ollama_running() -> bool:
    return bool(st.session_state.get(OLLAMA_STATUS, {}).get("running"))
