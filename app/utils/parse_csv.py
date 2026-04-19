import pandas as pd


def parse_csv_file(csv_file) -> dict:
    """
    Parse CSV lap times / splits and extract basic stats.
    For MVP we just calculate total duration from lap times.
    """

    try:
        df = pd.read_csv(csv_file)

        # Very flexible - look for common columns
        total_duration = None
        if 'time' in df.columns or 'duration' in df.columns:
            # Simple heuristic - sum a duration column if present
            duration_col = 'time' if 'time' in df.columns else 'duration'
            # Assume minutes or convert if needed
            total_duration = int(df[duration_col].sum())

        return {
            "csv_summary": f"CSV with {len(df)} rows processed",
            "duration_from_csv": total_duration
        }

    except Exception as e:
        print(f"CSV parsing error: {e}")
        return {
            "csv_summary": "CSV parsing failed",
            "duration_from_csv": None
        }
