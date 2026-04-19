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
    ["Dashboard", "Upload Hike", "History", "Chat with TrailBuddy"],
    help="Choose a section"
)

# Simple page routing
if page == "Dashboard":
    st.title("Dashboard")
    st.write("Welcome to TrailBuddy!")
    st.info("This is your dashboard where you can see an overview of your hiking activities and stats.")

    # Placeholder for future charts
    st.subheader("Your Hiking Stats (coming soon)")
    st.caption("Here you will see charts and insights about your hiking activities.")

elif page == "Upload Hike":
    st.title("Upload a New Hike")
    st.write("Here you can upload your hiking data (GPX and CSV supported).")

    col1, col2 = st.columns(2)
    with col1:
        gpx_file = st.file_uploader("Upload GPX route file", type=["gpx"])
    with col2:
        csv_file = st.file_uploader("Upload CSV (lap times / splites) file", type=["csv"])

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
    st.title("💬 Chat with TrailBuddy")
    st.caption("Ask about your hikes or get personalized recommendations based on your notes")

    from utils.rag import ask_trailbuddy

    # Chat history
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("What was my longest hike this year? How can I improve my packing?"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking about your hikes..."):
                response = ask_trailbuddy(prompt)
                st.markdown(response)

        st.session_state.chat_messages.append({"role": "assistant", "content": response})

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("TrailBuddy v0.1 || Local & Private || Built for learning")
