"""Row rendering for the History page: summary line + action buttons."""
import streamlit as st

from db.ranking_repository import add_hike_to_ranking, remove_hike_from_ranking
from state import CONFIRM_DELETE_ID, EDITING_HIKE_ID, VIEWING_HIKE_ID


def render_history_row(hike: dict, rank_position: int | None) -> None:
    """Render one hike's summary row with edit/delete/view/rank actions."""
    hike_id = hike["id"]
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2.5, 1.5, 1.2, 1.2, 1.5, 1.0, 1.0, 1.0])
    with col1:
        st.markdown(f"**{hike['title'] or 'Untitled'}**")
    with col2:
        st.text(hike["hike_date"])
    with col3:
        st.text(f"{hike['distance'] or 0:.1f} km")
    with col4:
        st.text(f"{hike['elevation_gain'] or 0:.0f} m gain")
    with col5:
        level = hike.get("difficulty_level") or "N/A"
        score = hike.get("difficulty_score") or 0.0
        st.text(f"Diff: {level} ({score:.1f})")
    with col6:
        if st.button("✏️", key=f"edit_btn_{hike_id}", help="Edit hike"):
            st.session_state[EDITING_HIKE_ID] = hike_id
            st.session_state[CONFIRM_DELETE_ID] = None
            st.session_state[VIEWING_HIKE_ID] = None
            st.rerun()
    with col6:
        if st.button("🗑️", key=f"del_btn_{hike_id}", help="Delete hike"):
            st.session_state[CONFIRM_DELETE_ID] = hike_id
            st.session_state[EDITING_HIKE_ID] = None
            st.session_state[VIEWING_HIKE_ID] = None
            st.rerun()
    with col7:
        if st.button("👁️", key=f"view_btn_{hike_id}", help="View hike details and map"):
            if st.session_state.get(VIEWING_HIKE_ID) == hike_id:
                st.session_state[VIEWING_HIKE_ID] = None
            else:
                st.session_state[VIEWING_HIKE_ID] = hike_id
            st.session_state[EDITING_HIKE_ID] = None
            st.session_state[CONFIRM_DELETE_ID] = None
            st.rerun()
    with col8:
        if rank_position is None:
            if st.button("🏆", key=f"rank_add_btn_{hike_id}", help="Add hike to ranking"):
                new_position = add_hike_to_ranking(hike_id)
                if new_position is None:
                    st.warning("Ranking is full (max 10). Remove a hike from Ranking first.")
                else:
                    st.rerun()
        else:
            if st.button("❌", key=f"rank_remove_btn_{hike_id}", help="Remove from ranking"):
                remove_hike_from_ranking(hike_id)
                st.rerun()
