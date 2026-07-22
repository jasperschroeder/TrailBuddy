"""Shared pytest configuration for the TrailBuddy test suite.

The application code expects to be executed with ``app/`` on ``sys.path``
(e.g. via ``streamlit run app/main.py``). This conftest ensures the same
import context is available when running pytest from the project root.
"""
import sys
from pathlib import Path

APP_DIR = Path(__file__).parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
