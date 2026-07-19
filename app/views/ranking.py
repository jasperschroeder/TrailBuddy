"""Ranking page: reorderable top-10 list."""
import streamlit as st

from db.ranking_repository import get_ranked_hikes, move_ranking_position, remove_hike_from_ranking


def render() -> None:
    st.title("🏆 Top 10 Ranking")

    ranked_hikes = get_ranked_hikes()

    st.caption("Add hikes from History, then reorder them here.")

    if not ranked_hikes:
        st.info("No hikes are ranked yet. Go to History and click the trophy button to add one.")
        return

    for index, hike in enumerate(ranked_hikes):
        hike_id = hike["id"]
        rank_position = hike["rank_position"]
        is_first = index == 0
        is_last = index == len(ranked_hikes) - 1

        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([0.7, 3, 1.6, 1.2, 1.2, 0.8, 0.8, 1.0])
        with col1:
            st.markdown(f"**{rank_position}.**")
        with col2:
            st.markdown(f"**{hike['title'] or 'Untitled'}**")
        with col3:
            st.text(hike["hike_date"])
        with col4:
            st.text(f"{hike['distance'] or 0:.1f} km")
        with col5:
            st.text(f"{hike['elevation_gain'] or 0:.0f} m")
        with col6:
            if st.button("⬆️", key=f"rank_up_{hike_id}", help="Move up", disabled=is_first):
                move_ranking_position(hike_id, "up")
                st.rerun()
        with col7:
            if st.button("⬇️", key=f"rank_down_{hike_id}", help="Move down", disabled=is_last):
                move_ranking_position(hike_id, "down")
                st.rerun()
        with col8:
            if st.button("❌", key=f"rank_remove_{hike_id}", help="Remove from ranking"):
                remove_hike_from_ranking(hike_id)
                st.rerun()
