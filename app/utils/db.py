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
    print(f"Database initialized at {DB_PATH}")


# Initialize on import
initialize_db()
