"""Rendering for the hike detail view: weather snapshot + GPX route map."""
import glob

import folium
import streamlit as st
from streamlit_folium import st_folium

import config
from utils.parse_gpx import parse_gpx_file
from utils.weather import fetch_weather_cached


def _find_gpx_path(hike: dict) -> str | None:
    """Locate the GPX file for a hike on disk."""
    hike_id = hike["id"]
    matches = glob.glob(str(config.HIKES_DIR / f"hike_{hike_id}_*.gpx"))
    if matches:
        return matches[0]

    if hike.get("gpx_filename"):
        candidate_path = config.HIKES_DIR / hike["gpx_filename"]
        if candidate_path.exists():
            return str(candidate_path)

    return None


def render_hike_detail(hike: dict) -> None:
    """Render full hike details: stats, weather snapshot, and route map."""
    hike_id = hike["id"]
    st.markdown(f"### {hike['title'] or 'Untitled'} ({hike['hike_date']})")
    st.write(f"**Distance:** {hike['distance'] or 0:.2f} km")
    st.write(f"**Elevation Gain:** {hike['elevation_gain'] or 0:.0f} m")
    st.write(f"**Duration:** {hike.get('duration_minutes', 'N/A')} min")
    st.write(f"**Notes:** {hike.get('notes', '')}")

    gpx_path = _find_gpx_path(hike)
    if not gpx_path:
        st.info("No GPX file found for this hike.")
        return

    gpx_data = parse_gpx_file(gpx_path)
    points = gpx_data.get("points", [])

    try:
        if points:
            coord = points[0]
            date_str = gpx_data.get("date") or hike.get("hike_date")
            weather = fetch_weather_cached(coord[0], coord[1], date_str, cache_key=f"hike_{hike_id}")
            if weather:
                with st.expander("Weather on Hike", expanded=False):
                    st.write(f"**Condition:** {weather.get('condition', 'N/A')}")
                    st.write(f"Avg temp: {weather.get('avg_temp_c', 'N/A')} °C")
                    st.write(f"Precipitation: {weather.get('total_precip_mm', 'N/A')} mm")
                    st.write(f"Avg wind: {weather.get('avg_wind_kmh', 'N/A')} km/h")
            else:
                st.info("Weather data unavailable")
    except Exception:
        st.info("Weather data unavailable")

    if not points:
        st.warning("No points found in the GPX file to display on the map.")
        return

    map_center = points[0]
    m = folium.Map(location=map_center, zoom_start=13)
    folium.PolyLine(points, color="blue", weight=2.5, opacity=1).add_to(m)
    st_folium(m, width=700, height=500, key=f"history_map_{hike_id}", returned_objects=[])
