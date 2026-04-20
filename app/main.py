from datetime import datetime
from pathlib import Path
import streamlit as st

from utils.db import initialize_db as init_db


# Page configuration
st.set_page_config(
    page_title="TrailBuddy",
    page_icon="🥾",
    layout="wide"
)
# Initialize database
init_db()


# Sidebar
st.sidebar.title("TrailBuddy")
st.sidebar.markdown("Your personal hiking companion + AI buddy.")

# Navigation
page = st.sidebar.selectbox(
    "Navigate",
    ["Dashboard", "Upload Hike", "History", "Chat with TrailBuddy"],  # noqa
    help="Choose a section"
)

# Simple page routing
if page == "Dashboard":
    st.title("📊 TrailBuddy Dashboard")

    from utils.db import get_all_hikes
    import pandas as pd

    hikes = get_all_hikes()

    if not hikes:
        st.info("No hikes logged yet. Start by uploading some hikes!")
        st.stop()

    df = pd.DataFrame(hikes)
    df['hike_date'] = pd.to_datetime(df['hike_date'])

    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
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

    st.divider()

    # Charts
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Hikes per Month")
        df['month'] = df['hike_date'].dt.strftime('%Y-%m')
        monthly = df.groupby('month').size().reset_index(name='count')
        st.bar_chart(data=monthly, x='month', y='count', use_container_width=True)

    with colB:
        st.subheader("Distance Over Time")
        df_sorted = df.sort_values('hike_date')
        st.line_chart(data=df_sorted, x='hike_date', y='distance', use_container_width=True)

    st.divider()

    st.subheader("Recent Hikes")
    recent_df = df.sort_values('hike_date', ascending=False).head(5)
    display_df = recent_df[["title", "hike_date", "distance", "elevation_gain", "duration_minutes"]]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
elif page == "Upload Hike":
    st.title("Upload a New Hike")
    st.write("Here you can upload your hiking data (GPX and CSV supported).")

    col1, col2 = st.columns(2)
    with col1:
        gpx_file = st.file_uploader("Upload GPX route file", type=["gpx"])
    with col2:
        csv_file = st.file_uploader("Upload CSV (lap times / splits) file", type=["csv"])

    title = st.text_input("Hike Title (optional)", value="My Hike")
    hike_date = st.date_input("Hike Date", value=datetime.now().date())

    notes = st.text_area("Add any notes about this hike (optional)",
                         placeholder="E.g., Weather was great, trail was muddy, etc.")

    if st.button("Save Hike", type="primary"):
        if not gpx_file:
            st.error("Please upload a GPX file")
        else:
            # Parse files
            from utils.parse_gpx import parse_gpx_file
            from utils.parse_csv import parse_csv_file
            from utils.db import save_hike

            gpx_data = parse_gpx_file(gpx_file)
            csv_data = parse_csv_file(csv_file) if csv_file else {}

            # Prepare data for DB
            save_data = {
                "title": title,
                "hike_date": str(hike_date),
                "distance": gpx_data.get("distance", 0.0),
                "elevation_gain": gpx_data.get("elevation_gain", 0.0),
                "duration_minutes": gpx_data.get("duration_minutes") or csv_data.get("duration_from_csv"),
                "gpx_filename": gpx_file.name,
                "csv_filename": csv_file.name if csv_file else None,
                "notes": notes
            }

            hike_id = save_hike(save_data)

            # Save raw files (optional but can be nice)
            if gpx_file:
                gpx_path = Path("data/hikes") / f"hike_{hike_id}_{gpx_file.name}"
                with open(gpx_path, "wb") as f:
                    f.write(gpx_file.getbuffer())

            st.success(f"Hike saved successfully with ID {hike_id}!")
            st.balloons()

elif page == "History":
    st.title("Hike History")

    from utils.db import get_all_hikes

    hikes = get_all_hikes()

    if not hikes:
        st.info("No hikes logged yet. Go to 'Upload Hike' to get started!")
    else:
        # Convert to DataFrame for nice table
        import pandas as pd
        df = pd.DataFrame(hikes)
        # Clean column names for display
        display_df = df[["id", "title", "hike_date", "distance", "elevation_gain", "duration_minutes", "notes"]]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.caption(f"Total hikes: {len(hikes)}")

elif page == "Chat with TrailBuddy":
    st.title("Chat with TrailBuddy")
    st.caption("Ask about your hikes or get personalized recommendations based on your notes")

    from utils.rag import ask_trailbuddy

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Display previous messages if any
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("Sources", expanded=False):
                    for source in message["sources"]:
                        st.write(source)

    if prompt := st.chat_input("Example: What was my longest hike? Based on my notes, what should I pack next time?"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("TrailBuddy is thinking..."):
                answer, sources = ask_trailbuddy(prompt)
                st.markdown(answer)
                if sources:
                    with st.expander("Sources", expanded=False):
                        for source in sources:
                            st.write(source)

        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources
        })


# Footer
st.sidebar.markdown("---")
st.sidebar.caption("TrailBuddy v0.1 || Local & Private || Built for learning")
