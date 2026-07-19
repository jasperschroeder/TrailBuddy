"""Centralized path and environment configuration for TrailBuddy.

All other modules should import paths/env constants from here instead of
recomputing them locally, so there is a single source of truth for where
data lives and how the app talks to Ollama.
"""
import os
from pathlib import Path

# Project root is one level up from this file (app/config.py -> project root).
ROOT_DIR = Path(__file__).parents[1]
DATA_DIR = ROOT_DIR / "data"
HIKES_DIR = DATA_DIR / "hikes"
HIKES_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "trailbuddy.db"

CHROMA_PATH = DATA_DIR / "chroma_db"
CHROMA_COLLECTION = "trailbuddy_hikes"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral-nemo:12b")
SKIP_OLLAMA_START = os.getenv("SKIP_OLLAMA_START", "false").lower() == "true"
