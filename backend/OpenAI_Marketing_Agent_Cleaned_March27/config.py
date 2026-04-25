from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

GENERATE_EXAMPLE_POSTS = os.getenv("GENERATE_EXAMPLE_POSTS", "true").lower() == "true"

MAX_FILE_SEARCH_RESULTS = int(os.getenv("MAX_FILE_SEARCH_RESULTS", "6"))
DEBUG_FILE_SEARCH = os.getenv("DEBUG_FILE_SEARCH", "false").lower() == "true"

KB_DIR = BASE_DIR / "KB"
VECTOR_STORE_FILE = BASE_DIR / ".vector_store_id"

def get_vector_store_id() -> str | None:
    if not VECTOR_STORE_FILE.exists():
        return None

    vs_id = VECTOR_STORE_FILE.read_text(encoding="utf-8").strip()
    return vs_id or None

def save_vector_store_id(vs_id: str):
    VECTOR_STORE_FILE.write_text(vs_id)
