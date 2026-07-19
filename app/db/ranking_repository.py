"""CRUD and reordering operations for the top-10 `ranking` table."""
from db.schema import get_db_connection

_RANKING_POSITION_QUERY = "SELECT rank_position FROM ranking WHERE hike_id = ?"


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
            return None

        current_position = current_row["rank_position"]
        cursor.execute("SELECT COALESCE(MAX(rank_position), 0) AS max_position FROM ranking")
        max_position = cursor.fetchone()["max_position"] or 0

        if direction == "up" and current_position <= 1:
            return current_position
        if direction == "down" and current_position >= max_position:
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
        return target_position
