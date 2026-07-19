"""CRUD operations for the `hikes` table."""
from db.schema import get_db_connection


def save_hike(data: dict):
    """Save a new hike to the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO hikes
            (title, hike_date, distance, elevation_gain, duration_minutes,
            gpx_filename, csv_filename, notes, difficulty_score, difficulty_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get("title"),
            data.get("hike_date"),
            data.get("distance"),
            data.get("elevation_gain"),
            data.get("duration_minutes"),
            data.get("gpx_filename"),
            data.get("csv_filename"),
            data.get("notes"),
            data.get("difficulty_score"),
            data.get("difficulty_level")
        ))

        return cursor.lastrowid


def update_hike_difficulty(hike_id: int, score: float, level: str):
    """Update difficulty score and level for an existing hike."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE hikes
            SET difficulty_score = ?, difficulty_level = ?
            WHERE id = ?
        ''', (score, level, hike_id))


def get_all_hikes():
    """Return all hikes as list of dicts."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hikes ORDER BY hike_date DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"ERROR in get_all_hikes: {e}")
        return []


def update_hike(hike_id: int, data: dict):
    """Update editable fields (title, hike_date, notes) for a hike."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE hikes SET title = ?, hike_date = ?, notes = ? WHERE id = ?",
            (data.get("title"), data.get("hike_date"), data.get("notes"), hike_id)
        )


def get_hike_by_filename(filename: str):
    """Return a hike matching the given GPX filename, or None."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hikes WHERE gpx_filename = ? LIMIT 1", (filename,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_hike_by_title_and_date(title: str, hike_date: str):
    """Return a hike matching the given title and date, or None."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM hikes WHERE title = ? AND hike_date = ? LIMIT 1",
            (title, hike_date)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_hike(hike_id: int):
    """Delete a hike by ID (and remove it from the ranking if present)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ranking WHERE hike_id = ?", (hike_id,))
        cursor.execute("DELETE FROM hikes WHERE id = ?", (hike_id,))
