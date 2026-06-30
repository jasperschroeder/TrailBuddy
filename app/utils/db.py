import sqlite3
from pathlib import Path
from contextlib import contextmanager

# Ensure data directory exists relative to the project root
ROOT_DIR = Path(__file__).parents[2]
DATA_DIR = ROOT_DIR / "data"
HIKES_DIR = DATA_DIR / "hikes"
HIKES_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "trailbuddy.db"

_RANKING_POSITION_QUERY = "SELECT rank_position FROM ranking WHERE hike_id = ?"


@contextmanager
def get_db_connection():
    """Establish a connection to the SQLite database as a context manager."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_db():
    """Initialize the database tables if they don't exist."""
    with get_db_connection() as conn:
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
                difficulty_score REAL,
                difficulty_level TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Migration for existing DBs: add columns if they don't exist
        try:
            cursor.execute("ALTER TABLE hikes ADD COLUMN difficulty_score REAL")
        except sqlite3.OperationalError:
            pass  # already exists
        try:
            cursor.execute("ALTER TABLE hikes ADD COLUMN difficulty_level TEXT")
        except sqlite3.OperationalError:
            pass  # already exists

        cursor.execute('''
                CREATE TABLE IF NOT EXISTS ranking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hike_id INTEGER NOT NULL UNIQUE,
                    rank_position INTEGER NOT NULL UNIQUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')


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
    """Return all hikes as list of dicts. With better error handling."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hikes ORDER BY hike_date DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"ERROR in get_all_hikes: {e}")
        return []


def get_ranked_hikes():
    """Return the current ranking joined with hike details."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.rank_position, h.*
                FROM ranking r
                JOIN hikes h ON h.id = r.hike_id
                ORDER BY r.rank_position ASC
                """
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"ERROR in get_ranked_hikes: {e}")
        return []


def get_ranking_position(hike_id: int):
    """Return the ranking position for a hike, or None if not ranked."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_RANKING_POSITION_QUERY, (hike_id,))
        row = cursor.fetchone()
        return row["rank_position"] if row else None


def add_hike_to_ranking(hike_id: int):
    """Add a hike to the bottom of the top 10 ranking."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(_RANKING_POSITION_QUERY, (hike_id,))
        existing = cursor.fetchone()
        if existing:
            return existing["rank_position"]

        cursor.execute("SELECT COALESCE(MAX(rank_position), 0) AS max_position FROM ranking")
        max_position = cursor.fetchone()["max_position"] or 0
        if max_position >= 10:
            return None

        new_position = max_position + 1
        cursor.execute(
            "INSERT INTO ranking (hike_id, rank_position) VALUES (?, ?)",
            (hike_id, new_position)
        )
        return new_position


def remove_hike_from_ranking(hike_id: int):
    """Remove a hike from the ranking and close any gaps."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_RANKING_POSITION_QUERY, (hike_id,))
        row = cursor.fetchone()
        if not row:
            return False

        removed_position = row["rank_position"]
        cursor.execute("DELETE FROM ranking WHERE hike_id = ?", (hike_id,))
        cursor.execute(
            "UPDATE ranking SET rank_position = rank_position - 1 WHERE rank_position > ?",
            (removed_position,)
        )
        return True


def move_ranking_position(hike_id: int, direction: str):
    """Move a ranked hike one slot up or down."""
    if direction not in {"up", "down"}:
        return None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT hike_id, rank_position FROM ranking WHERE hike_id = ?", (hike_id,))
    current_row = cursor.fetchone()
    if not current_row:
        conn.close()
        return None

    current_position = current_row["rank_position"]
    cursor.execute("SELECT COALESCE(MAX(rank_position), 0) AS max_position FROM ranking")
    max_position = cursor.fetchone()["max_position"] or 0

    if direction == "up" and current_position <= 1:
        conn.close()
        return current_position
    if direction == "down" and current_position >= max_position:
        conn.close()
        return current_position

    target_position = current_position - 1 if direction == "up" else current_position + 1

    temp_position = -current_position
    cursor.execute("UPDATE ranking SET rank_position = ? WHERE hike_id = ?", (temp_position, hike_id))
    cursor.execute(
        "UPDATE ranking SET rank_position = ? WHERE rank_position = ?",
        (current_position, target_position)
    )
    cursor.execute(
        "UPDATE ranking SET rank_position = ? WHERE hike_id = ?",
        (target_position, hike_id)
    )
    conn.commit()
    conn.close()
    return target_position


def delete_hike(hike_id: int):
    """Delete a hike by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ranking WHERE hike_id = ?", (hike_id,))
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
