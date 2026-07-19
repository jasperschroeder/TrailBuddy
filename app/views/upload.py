"""Upload Hike page: form to add a new hike."""
from datetime import datetime, timezone

import streamlit as st

from services.hike_service import find_duplicate_errors, save_new_hike
from state import RESET_UPLOAD_FORM, UPLOAD_FORM_VERSION, is_ollama_running


def render() -> None:
    st.title("Upload a New Hike")
    st.write("Here you can upload your hiking data (GPX and CSV supported).")

    # Defaults used to reset the upload form after a successful save.
    upload_defaults = {
        "upload_title": "My Hike",
        "upload_date": datetime.now(timezone.utc).date(),
        "upload_notes": ""
    }

    upload_form_version = st.session_state.get(UPLOAD_FORM_VERSION, 0)

    # Streamlit widgets can only be updated before they're instantiated.
    # Apply the reset at the top of the next rerun.
    if st.session_state.pop(RESET_UPLOAD_FORM, False):
        for key, value in upload_defaults.items():
            st.session_state[key] = value

    col1, col2 = st.columns(2)
    with col1:
        gpx_file = st.file_uploader(
            "Upload GPX route file",
            type=["gpx"],
            key=f"upload_gpx_{upload_form_version}"
        )
    with col2:
        csv_file = st.file_uploader(
            "Upload CSV (lap times / splits) file",
            type=["csv"],
            key=f"upload_csv_{upload_form_version}"
        )

    title = st.text_input("Hike Title (optional)", value="My Hike", key="upload_title")
    hike_date = st.date_input("Hike Date", value=datetime.now(timezone.utc).date(), key="upload_date")

    notes = st.text_area("Add any notes about this hike (optional)",
                         placeholder="E.g., Weather was great, trail was muddy, etc.",
                         key="upload_notes")

    st.markdown(
        """
        <style>
        div[data-testid="stButton"] {
            display: inline-block;
            margin-right: 0.5rem;
            vertical-align: top;
        }

        div[data-testid="stButton"] > button {
            width: 180px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    save_hike_clicked = st.button("Save Hike", type="primary")
    reset_form_clicked = st.button("Reset to Defaults")

    if reset_form_clicked:
        st.session_state[RESET_UPLOAD_FORM] = True
        st.session_state[UPLOAD_FORM_VERSION] = upload_form_version + 1
        st.rerun()

    if not save_hike_clicked:
        return

    if not gpx_file:
        st.error("Please upload a GPX file")
        return

    duplicate_errors = find_duplicate_errors(gpx_file.name, title, str(hike_date))
    if duplicate_errors:
        for msg in duplicate_errors:
            st.error(msg)
        return

    ai_available = is_ollama_running()
    if ai_available:
        with st.spinner("Predicting hike difficulty with AI..."):
            result = save_new_hike(gpx_file, csv_file, title, str(hike_date), notes, ai_available)
    else:
        result = save_new_hike(gpx_file, csv_file, title, str(hike_date), notes, ai_available)

    if result["ai_warning"]:
        st.warning(f"⚠️ {result['ai_warning']}")

    st.success(f"Hike saved successfully with ID {result['hike_id']}!")
    st.balloons()
    st.session_state[RESET_UPLOAD_FORM] = True
    st.session_state[UPLOAD_FORM_VERSION] = upload_form_version + 1
    # Don't rerun immediately - let balloons animate first.
    # Form will reset on next interaction.
