"""SQLite connection management and schema initialization/migrations."""
import sqlite3
from contextlib import contextmanager

import config

# Module-level path (not just imported inline in each function) so evaluation
# scripts can monkeypatch it directly, e.g. `db.schema.DB_PATH = fixture_path`,
# mirroring the pattern the previous utils/db.py used.
DB_PATH = config.DB_PATH


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


# Initialize on import
initialize_db()
