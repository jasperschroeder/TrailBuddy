"""Dashboard page: summary metrics, charts, and admin difficulty backfill tool."""
import pandas as pd
import streamlit as st

from db.hikes_repository import get_all_hikes, update_hike_difficulty
from llm.difficulty_predictor import predict_hike_difficulty


def render() -> None:
    st.title("📊 TrailBuddy Dashboard")

    hikes = get_all_hikes()

    if not hikes:
        st.info("No hikes logged yet. Start by uploading some hikes!")
        st.stop()

    df = pd.DataFrame(hikes)
    df['hike_date'] = pd.to_datetime(df['hike_date'])

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Hikes", len(df))
    with col2:
        total_distance = df['distance'].sum()
        st.metric("Total Distance", f"{total_distance:.1f} km")
    with col3:
        total_elevation = df['elevation_gain'].sum()
        st.metric("Total Elevation", f"{total_elevation:.0f} m")
    with col4:
        avg_distance = df['distance'].mean()
        st.metric("Avg Distance", f"{avg_distance:.1f} km")
    with col5:
        if 'difficulty_score' in df.columns:
            avg_diff = df['difficulty_score'].mean()
            st.metric("Avg Difficulty", f"{avg_diff:.1f}")
        else:
            st.metric("Avg Difficulty", "N/A")

    colA, colB = st.columns(2)
    with colA:
        st.subheader("Hikes per Month")
        df['month'] = df['hike_date'].dt.strftime('%Y-%m')
        monthly = df.groupby('month').size().reset_index(name='count')
        st.bar_chart(data=monthly, x='month', y='count', width="stretch")

    with colB:
        st.subheader("Distance Over Time")
        df_sorted = df.sort_values('hike_date')
        st.line_chart(data=df_sorted, x='hike_date', y='distance', width="stretch")

    st.divider()

    if 'difficulty_score' not in df.columns or df['difficulty_score'].isnull().any():
        with st.expander("🛠️ Admin Tools"):
            st.write("Some hikes are missing difficulty scores. You can backfill them using AI prediction.")
            if st.button("Predict Difficulty for All Hikes"):
                hikes_to_update = [h for h in hikes if h.get('difficulty_score') is None]
                progress_bar = st.progress(0)
                for i, hike in enumerate(hikes_to_update):
                    with st.spinner(f"Predicting for {hike['title']}..."):
                        prediction = predict_hike_difficulty(
                            hike.get('distance', 0),
                            hike.get('elevation_gain', 0),
                            hike.get('notes', "")
                        )
                        update_hike_difficulty(
                            hike['id'],
                            prediction['difficulty_score'],
                            prediction['difficulty_level']
                        )
                    progress_bar.progress((i + 1) / len(hikes_to_update))
                st.success("All hikes updated!")
                st.rerun()

    st.subheader("Recent Hikes")
    recent_df = df.sort_values('hike_date', ascending=False).head(5).copy()
    for col in ["difficulty_level", "difficulty_score"]:
        if col not in recent_df.columns:
            recent_df[col] = None

    recent_df['hike_date'] = recent_df['hike_date'].dt.strftime('%Y-%m-%d')
    recent_df['title'] = recent_df['title'].apply(lambda x: str(x).replace('_', ' ').title() if x else "Untitled")

    display_df = recent_df[[
        "title", "hike_date", "distance", "elevation_gain", "difficulty_level", "difficulty_score"
    ]].rename(columns={
        "title": "Hike",
        "hike_date": "Date",
        "distance": "Distance (km)",
        "elevation_gain": "Elevation (m)",
        "difficulty_level": "Difficulty Level",
        "difficulty_score": "Difficulty Score"
    })
    st.dataframe(display_df, width="stretch", hide_index=True)
