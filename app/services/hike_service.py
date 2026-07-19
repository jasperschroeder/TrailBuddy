"""Business logic for parsing, predicting difficulty for, and persisting a
new hike upload. Contains no Streamlit calls so it can be exercised directly."""
import config
from db.hikes_repository import get_hike_by_filename, get_hike_by_title_and_date, save_hike
from llm.difficulty_predictor import predict_hike_difficulty
from utils.difficulty import calculate_difficulty_score, get_difficulty_level
from utils.parse_csv import parse_csv_file
from utils.parse_gpx import parse_gpx_file


def find_duplicate_errors(gpx_filename: str, title: str, hike_date: str) -> list[str]:
    """Return human-readable duplicate warnings, or an empty list if none."""
    errors = []
    if get_hike_by_filename(gpx_filename):
        errors.append(f"A hike with GPX file **{gpx_filename}** was already uploaded.")
    if get_hike_by_title_and_date(title, hike_date):
        errors.append(f"A hike titled **{title}** on **{hike_date}** already exists.")
    return errors


def save_new_hike(gpx_file, csv_file, title: str, hike_date: str, notes: str, ai_available: bool) -> dict:
    """Parse uploaded GPX/CSV files, predict difficulty, and persist the hike.

    Returns a dict with keys: hike_id, difficulty_score, difficulty_level,
    used_ai, ai_warning (None if AI prediction succeeded or wasn't needed).
    """
    gpx_data = parse_gpx_file(gpx_file)
    csv_data = parse_csv_file(csv_file) if csv_file else {}

    distance = gpx_data.get("distance", 0.0)
    elevation_gain = gpx_data.get("elevation_gain", 0.0)

    heuristic_score = calculate_difficulty_score(distance, elevation_gain)
    heuristic_level = get_difficulty_level(heuristic_score)

    ai_warning = None
    if ai_available:
        llm_prediction = predict_hike_difficulty(distance, elevation_gain, notes)
        difficulty_score = llm_prediction.get("difficulty_score", heuristic_score)
        difficulty_level = llm_prediction.get("difficulty_level", heuristic_level)
        used_ai = llm_prediction.get("used_ai", False)
        if not used_ai:
            ai_warning = (
                "AI prediction unavailable. Using heuristic calculation "
                "based on distance and elevation."
            )
    else:
        difficulty_score = heuristic_score
        difficulty_level = heuristic_level
        used_ai = False
        ai_warning = "AI is unavailable. Using heuristic difficulty calculation based on distance and elevation."

    save_data = {
        "title": title,
        "hike_date": hike_date,
        "distance": distance,
        "elevation_gain": elevation_gain,
        "duration_minutes": gpx_data.get("duration_minutes") or csv_data.get("duration_from_csv"),
        "gpx_filename": gpx_file.name,
        "csv_filename": csv_file.name if csv_file else None,
        "notes": notes,
        "difficulty_score": difficulty_score,
        "difficulty_level": difficulty_level
    }

    hike_id = save_hike(save_data)

    gpx_path = config.HIKES_DIR / f"hike_{hike_id}_{gpx_file.name}"
    with open(gpx_path, "wb") as f:
        f.write(gpx_file.getbuffer())

    if csv_file:
        csv_path = config.HIKES_DIR / f"hike_{hike_id}_{csv_file.name}"
        with open(csv_path, "wb") as f:
            f.write(csv_file.getbuffer())

    return {
        "hike_id": hike_id,
        "difficulty_score": difficulty_score,
        "difficulty_level": difficulty_level,
        "used_ai": used_ai,
        "ai_warning": ai_warning,
    }


def delete_hike_files(hike_id: int) -> None:
    """Remove any GPX/CSV files on disk associated with a hike."""
    for file_path in config.HIKES_DIR.glob(f"hike_{hike_id}_*"):
        file_path.unlink(missing_ok=True)
