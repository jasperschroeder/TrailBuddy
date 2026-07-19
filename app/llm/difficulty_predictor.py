"""Difficulty prediction: LLM-refined score with a deterministic fallback."""
from pathlib import Path

from langchain_core.messages import HumanMessage

from llm.client import get_llm
from llm.json_utils import extract_json_from_llm_response
from utils.difficulty import calculate_difficulty_score, get_difficulty_level

_GUIDELINES_PATH = Path(__file__).parents[1] / "utils" / "difficulty_guidelines.md"


def predict_hike_difficulty(distance: float, elevation_gain: float, notes: str = "") -> dict:
    """
    Predict hike difficulty using the LLM and RAG guidelines.
    Falls back to heuristic calculation if LLM is unavailable.

    Returns:
        dict with keys: difficulty_score (float), difficulty_level (str), used_ai (bool)
    """
    guidelines = ""
    if _GUIDELINES_PATH.exists():
        with open(_GUIDELINES_PATH, "r") as f:
            guidelines = f.read()

    prompt = f"""
    You are an expert hiking guide. Based on the following guidelines and hike details,
    predict a numerical difficulty score (1-50) and a level (Easy, Moderate, Challenging, Hard, Expert).

    GUIDELINES:
    {guidelines}

    HIKE DETAILS:
    - Distance: {distance} km
    - Elevation Gain: {elevation_gain} m
    - Notes: {notes}

    Return ONLY a JSON object with keys: "difficulty_score" (float) and "difficulty_level" (string).
    """

    try:
        response = get_llm().invoke([HumanMessage(content=prompt)])

        result = extract_json_from_llm_response(response.content, {
            "difficulty_score": (float, None),
            "difficulty_level": (str, None)
        })

        if result:
            return {
                "difficulty_score": result.get("difficulty_score", 0.0),
                "difficulty_level": result.get("difficulty_level", "Unknown"),
                "used_ai": True
            }

    except Exception as e:
        print(f"LLM prediction failed: {str(e)}")
        # Fall through to heuristic calculation

    # Fallback to local calculation if LLM fails or is unavailable
    print("Using heuristic difficulty calculation (LLM unavailable or failed)")
    score = calculate_difficulty_score(distance, elevation_gain)
    return {
        "difficulty_score": score,
        "difficulty_level": get_difficulty_level(score),
        "used_ai": False
    }
