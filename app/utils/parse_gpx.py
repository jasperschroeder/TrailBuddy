import gpxpy
import gpxpy.gpx
from datetime import datetime


def parse_gpx_file(gpx_file) -> dict:
    """
    Parse GPX file and extract key hiking stats.
    Returns a dict with extracted data or empty values if parsing fails.
    """

    try:
        # gpx_file can be UploadedFile or file path
        if hasattr(gpx_file, "read"):
            gpx_content = gpx_file.read()
            gpx = gpxpy.parse(gpx_content)
        else:
            with open(gpx_file, "r") as f:
                gpx = gpxpy.parse(f)

        # Basic stats
        distance = 0.0
        elevation_gain = 0.0
        start_time = None
        end_time = None

        for track in gpx.tracks:
            for segment in track.segments:
                distance += segment.length_3d() / 1000  # meters to km

                # Calculate elevation gain by comparing consecutive points
                if len(segment.points) > 1:
                    prev_elev = segment.points[0].elevation
                    for point in segment.points[1:]:
                        if point.elevation is not None and prev_elev is not None:
                            if point.elevation > prev_elev:
                                elevation_gain += point.elevation - prev_elev
                            prev_elev = point.elevation

        # Try to get time range
        if gpx.tracks and gpx.tracks[0].segments and gpx.tracks[0].segments[0].points:
            points = gpx.tracks[0].segments[0].points
            if points[0].time:
                start_time = points[0].time
            if points[-1].time:
                end_time = points[-1].time

        duration_minutes = None
        if start_time and end_time:
            duration_minutes = int((end_time - start_time).total_seconds() / 60)

        return {
            "distance": round(distance, 2),  # in km
            "elevation_gain": round(elevation_gain, 1),  # in meters
            "duration_minutes": duration_minutes,
            "title": gpx.name or "Unnamed Hike",
            "date": start_time.strftime("%Y-%m-%d") if start_time else datetime.now().strftime("%Y-%m-%d")
        }

    except Exception as e:
        print(f"GPX parsing error: {e}")
        return {
            "distance": 0.0,
            "elevation_gain": 0.0,
            "duration_minutes": None,
            "title": "Unnamed Hike",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
