"""Shared application configuration."""
import os


def get_gemini_model() -> str:
    """Return the Gemini model id, reading GEMINI_MODEL from the environment at call time."""
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")


# Backward-compatible alias; prefer get_gemini_model() so .env is respected after load_dotenv().
DEFAULT_GEMINI_MODEL = get_gemini_model()
