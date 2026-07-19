import os
import subprocess
import time
import urllib.request
import urllib.error

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
SKIP_OLLAMA_START = os.getenv("SKIP_OLLAMA_START", "false").lower() == "true"


def check_ollama_health() -> tuple[bool, str]:
    """Check if Ollama is running and responding.

    Returns:
        (is_healthy, status_message)
    """
    try:
        req = urllib.request.Request(f'{OLLAMA_HOST}/api/tags', method='GET')
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                return True, "Ollama is running"
            return False, f"Ollama returned status {response.status}"
    except urllib.error.URLError:
        return False, "Ollama is not responding"
    except Exception as e:
        return False, f"Ollama health check failed: {str(e)}"


def start_ollama_service() -> tuple[bool, str]:
    """Check if Ollama is running, and start it if not.

    Returns:
        (is_running, status_message)
    """
    # First check if already running
    is_healthy, _ = check_ollama_health()
    if is_healthy:
        return True, "Ollama is already running"

    if SKIP_OLLAMA_START:
        return False, f"Ollama is not running at {OLLAMA_HOST} and auto-start is disabled."

    # Try to start Ollama
    try:
        # Start ollama serve in background (detached process)
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )

        # Wait up to 10 seconds for Ollama to start
        for _ in range(20):
            time.sleep(0.5)
            is_healthy, _ = check_ollama_health()
            if is_healthy:
                return True, "Ollama started successfully"

        return False, "Ollama started but not responding yet (may need more time)"

    except FileNotFoundError:
        return False, "Ollama is not installed. Download from https://ollama.ai/download"
    except Exception as e:
        return False, f"Failed to start Ollama: {str(e)}"
