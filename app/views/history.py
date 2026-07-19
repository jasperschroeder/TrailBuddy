"""History page: list all hikes with edit/delete/view/rank actions."""
from datetime import datetime

import streamlit as st

from components.hike_row import render_history_row
from components.map_view import render_hike_detail
from db.hikes_repository import delete_hike, get_all_hikes, update_hike
from db.ranking_repository import get_ranking_position
from services.hike_service import delete_hike_files
from state import CONFIRM_DELETE_ID, EDITING_HIKE_ID, VIEWING_HIKE_ID


def render() -> None:
    st.title("Hike History")

    st.session_state.setdefault(EDITING_HIKE_ID, None)
    st.session_state.setdefault(CONFIRM_DELETE_ID, None)

    hikes = get_all_hikes()

    if not hikes:
        st.info("No hikes logged yet. Go to 'Upload Hike' to get started!")
        return

    st.caption(f"Total hikes: {len(hikes)}")
    st.divider()

    for hike in hikes:
        hike_id = hike["id"]
        rank_position = get_ranking_position(hike_id)
        render_history_row(hike, rank_position)

        if st.session_state.get(VIEWING_HIKE_ID) == hike_id:
            render_hike_detail(hike)

        if st.session_state.get(EDITING_HIKE_ID) == hike_id:
            with st.form(key=f"edit_form_{hike_id}"):
                new_title = st.text_input("Title", value=hike["title"] or "")
                new_date = st.date_input(
                    "Date",
                    value=datetime.strptime(hike["hike_date"], "%Y-%m-%d").date()
                )
                new_notes = st.text_area("Notes", value=hike["notes"] or "")
                save_col, cancel_col = st.columns([1, 1])
                with save_col:
                    saved = st.form_submit_button("Save", type="primary")
                with cancel_col:
                    cancelled = st.form_submit_button("Cancel")

            if saved:
                update_hike(hike_id, {
                    "title": new_title,
                    "hike_date": str(new_date),
                    "notes": new_notes
                })
                st.session_state[EDITING_HIKE_ID] = None
                st.rerun()
            elif cancelled:
                st.session_state[EDITING_HIKE_ID] = None
                st.rerun()

        if st.session_state.get(CONFIRM_DELETE_ID) == hike_id:
            st.warning(
                f"Are you sure you want to delete **{hike['title'] or 'this hike'}**? This cannot be undone."
            )
            confirm_col, cancel_col2 = st.columns([1, 1])
            with confirm_col:
                if st.button("Confirm Delete", key=f"confirm_del_{hike_id}", type="primary"):
                    delete_hike(hike_id)
                    delete_hike_files(hike_id)
                    st.session_state[CONFIRM_DELETE_ID] = None
                    st.rerun()
            with cancel_col2:
                if st.button("Cancel", key=f"cancel_del_{hike_id}"):
                    st.session_state[CONFIRM_DELETE_ID] = None
                    st.rerun()

        st.divider()
