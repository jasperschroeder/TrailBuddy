"""Chat with TrailBuddy page: tool-calling + RAG chat interface."""
import streamlit as st

from services.chat_service import ask_trailbuddy, sync_vectorstore
from state import CHAT_MESSAGES, OLLAMA_STATUS, is_ollama_running


def render() -> None:
    if not is_ollama_running():
        st.title("💬 Chat with TrailBuddy")
        st.error("🔴 AI Chat is currently unavailable.")
        status_message = st.session_state.get(OLLAMA_STATUS, {}).get("message", "unknown")
        st.info(
            f"**Status:** {status_message}\n\n"
            "The chat feature requires Ollama to be running. Please:\n"
            "1. Make sure Ollama is installed (download from https://ollama.ai/download)\n"
            "2. Try clicking the 'Retry Starting Ollama' button in the sidebar\n"
            "3. Or manually start Ollama and refresh this page"
        )
        st.stop()

    title_col, action_col = st.columns([6, 2], vertical_alignment="top")
    with title_col:
        st.markdown("## Chat with TrailBuddy")
        st.caption("Ask about your hikes or get personalized recommendations based on your notes")
    with action_col:
        if st.button("🔄 Sync Vector DB", help="Add new hikes to the vector database"):
            with st.spinner("Syncing vector database..."):
                try:
                    msg = sync_vectorstore()
                    st.success(msg)
                except Exception as e:
                    st.error(f"Failed to sync vector DB: {e}")
        if st.button("🧹 Clear Chat", help="Clear current chat history"):
            st.session_state[CHAT_MESSAGES] = []
            st.rerun()

    st.session_state.setdefault(CHAT_MESSAGES, [])

    for message in st.session_state[CHAT_MESSAGES]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("Tools used", expanded=False):
                    for source in message["sources"]:
                        st.markdown(source)

    if prompt := st.chat_input("Example: What was my longest hike? Based on my notes, what should I pack next time?"):
        st.session_state[CHAT_MESSAGES].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("TrailBuddy is thinking..."):
                answer, sources = ask_trailbuddy(prompt)
                st.markdown(answer)
                if sources:
                    with st.expander("Tools used", expanded=False):
                        for source in sources:
                            st.markdown(source)

        st.session_state[CHAT_MESSAGES].append({
            "role": "assistant",
            "content": answer,
            "sources": sources
        })
