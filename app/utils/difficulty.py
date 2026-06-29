def calculate_difficulty_score(distance_km: float, elevation_gain_m: float) -> float:
    """
    Calculate a simple difficulty score based on distance and elevation gain.
    Formula: score = distance (km) + (elevation_gain (m) / 100) * 2
    This is a heuristic where 100m of climb is roughly equivalent to 2km of flat walking.
    """
    if distance_km is None:
        distance_km = 0.0
    if elevation_gain_m is None:
        elevation_gain_m = 0.0

    return round(distance_km + (elevation_gain_m / 100.0) * 2, 1)


def get_difficulty_level(score: float) -> str:
    """
    Categorize the difficulty based on the calculated score.
    """
    if score < 5:
        return "Easy"
    elif score < 12:
        return "Moderate"
    elif score < 20:
        return "Challenging"
    elif score < 35:
        return "Hard"
    else:
        return "Expert"
