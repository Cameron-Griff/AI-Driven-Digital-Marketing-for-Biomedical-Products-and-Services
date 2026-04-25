from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openai import OpenAI
from config import (
    OPENAI_API_KEY,
    KB_DIR,
    get_vector_store_id,
    save_vector_store_id,
)


def _list_kb_files() -> list[Path]:
    KB_DIR.mkdir(exist_ok=True)
    return sorted([p for p in KB_DIR.rglob("*") if p.is_file()], key=lambda p: p.as_posix().lower())


def _safe_delete_vector_store(client: OpenAI, vector_store_id: str | None) -> None:
    if not vector_store_id:
        return
    try:
        client.vector_stores.delete(vector_store_id)
        print(f"Deleted old vector store: {vector_store_id}")
    except Exception as e:
        print(f"Warning: could not delete vector store {vector_store_id}: {e}")


def main(delete_old: bool = True) -> str:
    if not OPENAI_API_KEY:
        raise SystemExit("Missing OPENAI_API_KEY in .env")

    files = _list_kb_files()
    if not files:
        raise SystemExit("No files found in KB/. Upload KB files first, then rebuild.")

    client = OpenAI(api_key=OPENAI_API_KEY)

    old_vs_id = get_vector_store_id()

    # Always create a fresh vector store for a real rebuild
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vs = client.vector_stores.create(name=f"Marketing KB {stamp}")
    print(f"Created new vector store: {vs.id}")

    uploaded_count = 0

    try:
        for p in files:
            with p.open("rb") as f:
                client.vector_stores.files.upload_and_poll(
                    vector_store_id=vs.id,
                    file=f,
                )
            uploaded_count += 1
            print(f"Uploaded: {p.name}")

        # Only save the new ID after all uploads succeed
        save_vector_store_id(vs.id)
        print(f"KB ready. Uploaded {uploaded_count} file(s). Active vector store: {vs.id}")

    except Exception:
        # Cleanup the half-built new store if uploads fail
        _safe_delete_vector_store(client, vs.id)
        raise

    # Cleanup the previous store after the new one is fully ready
    if delete_old and old_vs_id and old_vs_id != vs.id:
        _safe_delete_vector_store(client, old_vs_id)

    return vs.id


if __name__ == "__main__":
    main()