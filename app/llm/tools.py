"""Agent tools: SQL access to structured hike data and semantic note search."""
import json
import re
import sqlite3

from langchain_core.tools import tool

from db.schema import DB_PATH
from llm.vectorstore import get_or_create_vectorstore

# Comprehensive SQL injection protection
_ALLOWED_SQL = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

# Dangerous keywords that should never appear in user queries
_DANGEROUS_SQL_KEYWORDS = [
    'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE',
    'PRAGMA', 'ATTACH', 'DETACH', 'EXEC', 'EXECUTE',
    'REPLACE', 'TRUNCATE', 'GRANT', 'REVOKE'
]

SQL_SCHEMA = (
    "Table: hikes\n"
    "Columns: id INTEGER, hike_date TEXT (YYYY-MM-DD), title TEXT, "
    "distance REAL (km), elevation_gain REAL (meters), "
    "duration_minutes INTEGER, notes TEXT, "
    "difficulty_score REAL, difficulty_level TEXT, created_at TEXT\n\n"
    "IMPORTANT: For date queries, use SQLite date functions:\n"
    "  - Current date: date('now')\n"
    "  - This year: WHERE strftime('%Y', hike_date) = strftime('%Y', 'now')\n"
    "  - This month: WHERE strftime('%Y-%m', hike_date) = strftime('%Y-%m', 'now')\n"
    "  - Last 7 days: WHERE hike_date >= date('now', '-7 days')\n"
    "  - Specific month: WHERE strftime('%Y-%m', hike_date) = '2026-05'"
)


def _validate_sql_query(sql: str) -> tuple[bool, str]:
    """Validate SQL query for security. Returns (is_valid, error_message)."""
    # Remove comments to prevent hidden commands
    sql_no_comments = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    sql_no_comments = re.sub(r'/\*.*?\*/', '', sql_no_comments, flags=re.DOTALL)

    # Check for multiple statements (semicolon-separated)
    if ';' in sql_no_comments.rstrip(';'):
        return False, "Error: multiple statements not allowed"

    # Check it starts with SELECT
    if not _ALLOWED_SQL.match(sql_no_comments.strip()):
        return False, "Error: only SELECT queries are permitted"

    # Check for dangerous keywords
    sql_upper = sql_no_comments.upper()
    for keyword in _DANGEROUS_SQL_KEYWORDS:
        # Use word boundaries to avoid false positives in column names
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False, f"Error: dangerous keyword '{keyword}' not allowed"

    # Ensure only querying the 'hikes' table (or 'ranking') in any FROM/JOIN clause.
    # This prevents querying system tables like sqlite_master via JOINs or nested queries.
    table_refs = re.findall(r"\b(?:FROM|JOIN)\s+([a-z_][\w]*)", sql_no_comments, flags=re.IGNORECASE)
    for table in table_refs:
        if table.lower() not in ["hikes", "ranking"]:
            return False, f"Error: access to table '{table}' not allowed"

    return True, ""


@tool
def query_hikes_db(sql: str) -> str:
    """Run a read-only SQL SELECT query against the hikes database.

    Schema - hikes(id, hike_date TEXT YYYY-MM-DD, title TEXT,
    distance REAL km, elevation_gain REAL meters,
    duration_minutes INTEGER, notes TEXT, created_at TEXT).

    Use this tool for exact numbers, counts, sums, averages, rankings,
    or filtering by date / distance / elevation.
    """
    # Multi-layer validation
    is_valid, error_msg = _validate_sql_query(sql)
    if not is_valid:
        return error_msg

    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Enable read-only mode for extra safety
            conn.execute("PRAGMA query_only = ON")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql.strip())
            rows = cursor.fetchall()
        if not rows:
            return "No results found."
        return json.dumps([dict(row) for row in rows], default=str)
    except sqlite3.Error as exc:
        return f"SQL error: {exc}"


@tool
def search_hike_notes(query: str) -> str:
    """Search hike notes and descriptions using semantic similarity.

    Use this tool when the question is about the *feel*, *experience*, or
    free-text content of hikes — e.g. 'any hike where I mentioned rain?'
    or 'hikes where I felt tired'.
    """
    vectorstore = get_or_create_vectorstore()
    docs = vectorstore.as_retriever(search_kwargs={"k": 5}).invoke(query)
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


TOOLS = [query_hikes_db, search_hike_notes]
TOOL_MAP = {t.name: t for t in TOOLS}
