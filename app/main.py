from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from utils.db import initialize_db as init_db
from utils.parse_gpx import parse_gpx_file
from utils.parse_csv import parse_csv_file

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
    import glob

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

    # Charts
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

    st.subheader("Recent Hikes")
    recent_df = df.sort_values('hike_date', ascending=False).head(5)
    display_df = recent_df[["title", "hike_date", "distance", "elevation_gain", "duration_minutes"]]
    st.dataframe(display_df, width="stretch", hide_index=True)
elif page == "Upload Hike":
    st.title("Upload a New Hike")
    st.write("Here you can upload your hiking data (GPX and CSV supported).")

    # Defaults used to reset the upload form after a successful save.
    upload_defaults = {
        "upload_title": "My Hike",
        "upload_date": datetime.now().date(),
        "upload_notes": ""
    }

    upload_form_version = st.session_state.get("upload_form_version", 0)

    # Streamlit widgets can only be updated before they're instantiated.
    # Apply the reset at the top of the next rerun.
    if st.session_state.pop("reset_upload_form", False):
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
    hike_date = st.date_input("Hike Date", value=datetime.now().date(), key="upload_date")

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
        st.session_state.reset_upload_form = True
        st.session_state.upload_form_version = upload_form_version + 1
        st.rerun()

    if save_hike_clicked:
        if not gpx_file:
            st.error("Please upload a GPX file")
        else:
            # Duplicate checks
            from utils.db import get_hike_by_filename, get_hike_by_title_and_date

            duplicate_errors = []
            if get_hike_by_filename(gpx_file.name):
                duplicate_errors.append(f"A hike with GPX file **{gpx_file.name}** was already uploaded.")
            if get_hike_by_title_and_date(title, str(hike_date)):
                duplicate_errors.append(f"A hike titled **{title}** on **{hike_date}** already exists.")

            if duplicate_errors:
                for msg in duplicate_errors:
                    st.error(msg)
            else:

                # Parse files
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
                st.session_state.reset_upload_form = True
                st.session_state.upload_form_version = upload_form_version + 1
                st.rerun()

elif page == "History":
    st.title("Hike History")

    from utils.db import get_all_hikes, delete_hike, update_hike
    import glob

    if "editing_hike_id" not in st.session_state:
        st.session_state.editing_hike_id = None
    if "confirm_delete_id" not in st.session_state:
        st.session_state.confirm_delete_id = None

    hikes = get_all_hikes()

    if not hikes:
        st.info("No hikes logged yet. Go to 'Upload Hike' to get started!")
    else:
        st.caption(f"Total hikes: {len(hikes)}")
        st.divider()

        for hike in hikes:
            hike_id = hike["id"]
            col1, col2, col3, col4, col5, col6, col7 = st.columns([3, 2, 1.5, 1.5, 1.25, 1.25, 1.25])
            with col1:
                st.markdown(f"**{hike['title'] or 'Untitled'}**")
            with col2:
                st.text(hike["hike_date"])
            with col3:
                st.text(f"{hike['distance'] or 0:.1f} km")
            with col4:
                st.text(f"{hike['elevation_gain'] or 0:.0f} m gain")
            with col5:
                if st.button("✏️", key=f"edit_btn_{hike_id}", help="Edit hike"):
                    st.session_state.editing_hike_id = hike_id
                    st.session_state.confirm_delete_id = None
                    st.session_state.viewing_hike_id = None
                    st.rerun()
            with col6:
                if st.button("🗑️", key=f"del_btn_{hike_id}", help="Delete hike"):
                    st.session_state.confirm_delete_id = hike_id
                    st.session_state.editing_hike_id = None
                    st.session_state.viewing_hike_id = None
                    st.rerun()
            with col7:
                if st.button("👁️", key=f"view_btn_{hike_id}", help="View hike details and map"):
                    if st.session_state.get("viewing_hike_id") == hike_id:
                        st.session_state.viewing_hike_id = None
                    else:
                        st.session_state.viewing_hike_id = hike_id
                    st.session_state.editing_hike_id = None
                    st.session_state.confirm_delete_id = None
                    st.rerun()

            # View details and map
            if st.session_state.get("viewing_hike_id") == hike_id:
                st.markdown(f"### {hike['title'] or 'Untitled'} ({hike['hike_date']})")
                st.write(f"**Distance:** {hike['distance'] or 0:.2f} km")
                st.write(f"**Elevation Gain:** {hike['elevation_gain'] or 0:.0f} m")
                st.write(f"**Duration:** {hike.get('duration_minutes', 'N/A')} min")
                st.write(f"**Notes:** {hike.get('notes', '')}")
                # Try to find the GPX file for this hike
                gpx_pattern = f"data/hikes/hike_{hike_id}_*.gpx"
                gpx_files = glob.glob(gpx_pattern)
                if gpx_files:
                    gpx_data = parse_gpx_file(gpx_files[0])
                    points = gpx_data.get("points", [])
                    if points:
                        map_center = points[0]
                        m = folium.Map(location=map_center, zoom_start=13)
                        folium.PolyLine(points, color="blue", weight=2.5, opacity=1).add_to(m)
                        st_folium(
                            m,
                            width=700,
                            height=500,
                            key=f"history_map_{hike_id}",
                            returned_objects=[]
                        )
                    else:
                        st.warning("No points found in the GPX file to display on the map.")
                else:
                    st.info("No GPX file found for this hike.")

            # Edit form
            if st.session_state.editing_hike_id == hike_id:
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
                    st.session_state.editing_hike_id = None
                    st.rerun()
                elif cancelled:
                    st.session_state.editing_hike_id = None
                    st.rerun()

            # Delete confirmation
            if st.session_state.confirm_delete_id == hike_id:
                st.warning(f"Are you sure you want to delete **{hike['title'] or 'this hike'}**? This cannot be undone.")  # noqa
                confirm_col, cancel_col2 = st.columns([1, 1])
                with confirm_col:
                    if st.button("Confirm Delete", key=f"confirm_del_{hike_id}", type="primary"):
                        delete_hike(hike_id)
                        # Remove GPX file from disk if it exists
                        for gpx_file_path in glob.glob(f"data/hikes/hike_{hike_id}_*"):
                            Path(gpx_file_path).unlink(missing_ok=True)
                        st.session_state.confirm_delete_id = None
                        st.rerun()
                with cancel_col2:
                    if st.button("Cancel", key=f"cancel_del_{hike_id}"):
                        st.session_state.confirm_delete_id = None
                        st.rerun()

            st.divider()

elif page == "Chat with TrailBuddy":
    from utils.rag import ask_trailbuddy, rebuild_vectorstore

    title_col, action_col = st.columns([6, 2], vertical_alignment="top")
    with title_col:
        st.markdown("## Chat with TrailBuddy")
        st.caption("Ask about your hikes or get personalized recommendations based on your notes")
    with action_col:
        if st.button("🔄 Rebuild Vector DB", help="Re-index all hikes into the vector database"):
            with st.spinner("Rebuilding vector database..."):
                try:
                    rebuild_vectorstore()
                    st.success("Vector DB rebuilt successfully!")
                except Exception as e:
                    st.error(f"Failed to rebuild vector DB: {e}")
        if st.button("🧹 Clear Chat", help="Clear current chat history"):
            st.session_state.chat_messages = []
            st.rerun()

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Display previous messages if any
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("Tools used", expanded=False):
                    for source in message["sources"]:
                        st.markdown(source)

    if prompt := st.chat_input("Example: What was my longest hike? Based on my notes, what should I pack next time?"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
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

        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources
        })


# Footer
st.sidebar.markdown("---")
st.sidebar.caption("TrailBuddy v0.1 || Local & Private || Built for learning")
