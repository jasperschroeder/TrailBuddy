import sqlite3
from pathlib import Path

# Ensure data directory exists
DATA_DIR = Path("data")
HIKES_DIR = DATA_DIR / "hikes"
HIKES_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "trailbuddy.db"


def get_db_connection():
    """Establish a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    return conn


def initialize_db():
    """Initialize the database with the hikes table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
            CREATE TABLE IF NOT EXISTS hikes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hike_date TEXT NOT NULL,
                title TEXT,
                distance REAL,
                elevation_gain REAL,
                duration_minutes INTEGER,
                gpx_filename TEXT,
                csv_filename TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    conn.commit()
    conn.close()


def save_hike(data: dict):
    """Save a new hike to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO hikes
        (title, hike_date, distance, elevation_gain, duration_minutes,
         gpx_filename, csv_filename, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get("title"),
        data.get("hike_date"),
        data.get("distance"),
        data.get("elevation_gain"),
        data.get("duration_minutes"),
        data.get("gpx_filename"),
        data.get("csv_filename"),
        data.get("notes")
    ))

    conn.commit()
    hike_id = cursor.lastrowid
    conn.close()
    return hike_id


def get_all_hikes():
    """Return all hikes as list of dicts. With better error handling."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hikes ORDER BY hike_date DESC")
        rows = cursor.fetchall()
        conn.close()
        hikes = [dict(row) for row in rows]
        print(f"DEBUG: Retrieved {len(hikes)} hikes from database")  # temporary debug
        return hikes
    except Exception as e:
        print(f"ERROR in get_all_hikes: {e}")
        return []


def delete_hike(hike_id: int):
    """Delete a hike by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hikes WHERE id = ?", (hike_id,))
    conn.commit()
    conn.close()


def update_hike(hike_id: int, data: dict):
    """Update editable fields (title, hike_date, notes) for a hike."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE hikes SET title = ?, hike_date = ?, notes = ? WHERE id = ?",
        (data.get("title"), data.get("hike_date"), data.get("notes"), hike_id)
    )
    conn.commit()
    conn.close()


def get_hike_by_filename(filename: str):
    """Return a hike matching the given GPX filename, or None."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hikes WHERE gpx_filename = ? LIMIT 1", (filename,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_hike_by_title_and_date(title: str, hike_date: str):
    """Return a hike matching the given title and date, or None."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM hikes WHERE title = ? AND hike_date = ? LIMIT 1",
        (title, hike_date)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# Initialize on import
initialize_db()
