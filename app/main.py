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

    notes = st.text_area("Add any notes about this hike (optional)",
                         placeholder="E.g., Weather was great, trail was muddy, etc.")

    if st.button("Save Hike"):
        st.success("Hike would be saved here (we'll implement this next)!")
        st.write("GPX uploaded:", gpx_file.name if gpx_file else "None")
        st.write("CSV uploaded:", csv_file.name if csv_file else "None")
        st.write("Notes:", notes[:2000] + "..." if notes else "None")

elif page == "History":
    st.title("Hiking History")
    st.write("This is where your past hikes will be displayed in a nice timeline format.")
    st.info("No hikes uploaded yet. Start by uploading a hike on the 'Upload Hike' page!")

elif page == "Chat with TrailBuddy":
    st.title("Chat with TrailBuddy, your AI hiking buddy!")
    st.write("Ask TrailBuddy anything about your hikes, get recommendations, or just have a chat!")

    # Placeholder chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What was my longest hike? or How can I improve my packing?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            st.markdown("I'm ready to answer once we connect the RAG pipeline (next steps)!")
            st.caption("This will later use your personal hike data + notes.")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("TrailBuddy v0.1 || Local & Private || Built for learning")
