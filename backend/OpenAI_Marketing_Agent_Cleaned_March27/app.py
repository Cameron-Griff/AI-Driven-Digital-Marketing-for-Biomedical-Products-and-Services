from __future__ import annotations

import os
import shutil
from pathlib import Path

import streamlit as st

from main import (
    chat_about_outputs,
    formatInput,
    generate_ad_images,
    generate_brief_lines_from_context,
    gpt,
    summarize_media_files,
    UPLOADS_DIR,
)
from setup_kb import main as setup_kb_main
from openai import OpenAI
from config import BASE_DIR, KB_DIR, VECTOR_STORE_FILE, OPENAI_API_KEY, get_vector_store_id

st.set_page_config(page_title="The Campaign Coach", layout="wide")

OUT_DIR = BASE_DIR / "outputs"
OUT_DIR.mkdir(exist_ok=True)
KB_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

MEDIA_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp",
    ".mp3", ".wav", ".m4a", ".aac",
    ".mp4", ".mov", ".mkv", ".webm",
}

if "ui_messages" not in st.session_state:
    st.session_state.ui_messages = {
        "kb": None,
        "media": None,
        "kb_index": None,
        "brief": None,
    }


def set_ui_message(slot: str, message: str, kind: str = "success") -> None:
    for key in st.session_state.ui_messages:
        st.session_state.ui_messages[key] = None

    st.session_state.ui_messages[slot] = {
        "message": message,
        "kind": kind,
    }


def clear_ui_messages() -> None:
    for key in st.session_state.ui_messages:
        st.session_state.ui_messages[key] = None


def render_ui_message(slot: str, placeholder) -> None:
    placeholder.empty()

    msg = st.session_state.ui_messages.get(slot)
    if not msg:
        return

    kind = msg.get("kind", "success")
    text = msg.get("message", "")

    with placeholder.container():
        if kind == "success":
            st.success(text)
        elif kind == "error":
            st.error(text)
        elif kind == "warning":
            st.warning(text)
        else:
            st.info(text)


st.title("The Campaign Coach")
st.caption("Grounded marketing plans in minutes.")

left, right = st.columns([0.45, 0.55], gap="large")

if "lines" not in st.session_state:
    st.session_state.lines = [""] * 13
for i in range(13):
    k = f"line_{i}"
    if k not in st.session_state:
        st.session_state[k] = st.session_state.lines[i]

if "status_events" not in st.session_state:
    st.session_state.status_events = []

status_placeholder = st.empty()


def render_status() -> None:
    with status_placeholder.container():
        with st.expander("Processing Status", expanded=True):
            if st.session_state.status_events:
                st.markdown("\n".join(f"- {item}" for item in st.session_state.status_events[-12:]))
            else:
                st.caption("No processing events yet.")


def add_status(message: str) -> None:
    st.session_state.status_events.append(message)
    st.session_state.status_events = st.session_state.status_events[-30:]
    render_status()


render_status()

spinner_placeholder = st.empty()


def run_with_global_spinner(text: str, fn, *args, **kwargs):
    try:
        with spinner_placeholder.container():
            with st.spinner(text):
                return fn(*args, **kwargs)
    finally:
        spinner_placeholder.empty()


if "use_rag" not in st.session_state:
    st.session_state["use_rag"] = bool(get_vector_store_id())

if "enable_rag_next_run" not in st.session_state:
    st.session_state["enable_rag_next_run"] = False

if "kb_rebuild_requested" not in st.session_state:
    st.session_state["kb_rebuild_requested"] = False

if "current_run_stamp" not in st.session_state:
    st.session_state["current_run_stamp"] = None

if "generated_ad_image_paths" not in st.session_state:
    st.session_state["generated_ad_image_paths"] = []

if "generated_ad_image_run_stamp" not in st.session_state:
    st.session_state["generated_ad_image_run_stamp"] = None


def latest_run_stamp() -> str | None:
    index_files = sorted(
        OUT_DIR.glob("00_index_*.md"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    if not index_files:
        return None

    # Filename format: 00_index_<stamp>.md
    return index_files[0].stem.replace("00_index_", "", 1)


def run_file(prefix: str, stamp: str | None) -> Path | None:
    if not stamp:
        return None
    p = OUT_DIR / f"{prefix}_{stamp}.md"
    return p if p.exists() else None


def request_kb_rebuild() -> None:
    if st.session_state.get("kb_rebuild_in_progress", False):
        return
    st.session_state["kb_rebuild_requested"] = True
    st.session_state["kb_rebuild_in_progress"] = True


def set_brief_lines(lines: list[str], sync_widgets: bool = False) -> None:
    st.session_state.lines = lines
    if sync_widgets:
        for i, line in enumerate(lines):
            st.session_state[f"line_{i}"] = line


def list_saved_media_files() -> list[Path]:
    """
    Only use top-level files in UPLOADS_DIR as the source of truth.
    This avoids accidentally re-processing extracted ffmpeg assets that
    main.py may place in nested video_* folders.
    """
    UPLOADS_DIR.mkdir(exist_ok=True)
    files = [
        p for p in UPLOADS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS
    ]
    return sorted(files, key=lambda p: p.name.lower())


def save_uploaded_media(files) -> list[Path]:
    UPLOADS_DIR.mkdir(exist_ok=True)
    saved: list[Path] = []
    for uf in files or []:
        target = UPLOADS_DIR / uf.name
        target.write_bytes(uf.getbuffer())
        saved.append(target)
    return saved


def clear_saved_media() -> int:
    """
    Clears top-level saved media files and any nested extracted video work dirs.
    """
    UPLOADS_DIR.mkdir(exist_ok=True)
    removed = 0

    for p in UPLOADS_DIR.iterdir():
        try:
            if p.is_file():
                p.unlink()
                removed += 1
            elif p.is_dir() and p.name.startswith("video_"):
                shutil.rmtree(p, ignore_errors=True)
                removed += 1
        except Exception:
            pass

    return removed


def list_saved_kb_files() -> list[Path]:
    KB_DIR.mkdir(exist_ok=True)
    files = [p for p in KB_DIR.rglob("*") if p.is_file()]
    return sorted(files, key=lambda p: p.as_posix().lower())


def clear_saved_kb_files() -> tuple[int, bool]:
    """
    Deletes the active remote vector store first, then clears local KB files
    and removes the saved pointer. This avoids orphaning remote vector stores.

    Returns:
        (removed_local_file_count, remote_deleted)
    """
    KB_DIR.mkdir(exist_ok=True)

    current_vs_id = get_vector_store_id()
    remote_deleted = False

    # Delete the currently active remote vector store first
    if current_vs_id:
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "Cannot clear KB safely because OPENAI_API_KEY is missing."
            )

        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            client.vector_stores.delete(current_vs_id)
            remote_deleted = True
        except Exception as e:
            raise RuntimeError(
                f"Could not delete active remote vector store ({current_vs_id}). "
                f"Clear aborted to avoid leaving an orphaned remote KB. Details: {e}"
            )

    removed = 0

    # Now clear local KB files/folders
    for p in sorted(KB_DIR.rglob("*"), reverse=True):
        try:
            if p.is_file():
                p.unlink()
                removed += 1
            elif p.is_dir():
                p.rmdir()
        except Exception:
            pass

    # Remove the saved pointer only after remote cleanup succeeds
    if VECTOR_STORE_FILE.exists():
        try:
            VECTOR_STORE_FILE.unlink()
        except Exception as e:
            raise RuntimeError(f"Failed to remove .vector_store_id: {e}")

    st.session_state["use_rag"] = False
    st.session_state["enable_rag_next_run"] = False

    return removed, remote_deleted


with left:
    st.subheader("1) Product + Market Input (Concise)")
    raw_context = st.text_area(
        "Describe product, audience, channel goals, and constraints",
        height=220,
        placeholder=(
            "Paste product notes, website copy, target audience, goals, market context, "
            "compliance constraints, and any campaign objectives."
        ),
    )

    st.subheader("2) Knowledge Base Upload (for RAG)")
    kb_uploads = st.file_uploader(
        "Upload PDFs/TXTs for vector search grounding",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        key="kb_uploader",
    )

    kb_saved = list_saved_kb_files()

    kb_c1, kb_c2 = st.columns(2)
    with kb_c1:
        if st.button("Save Files to KB", width='stretch'):
            if not kb_uploads:
                set_ui_message("kb", "Upload at least one PDF/TXT first.", "warning")
                st.rerun()
            else:
                add_status("Saving uploaded KB file(s).")
                saved = []
                for uf in kb_uploads:
                    target = KB_DIR / uf.name
                    target.write_bytes(uf.getbuffer())
                    saved.append(target.name)

                add_status(f"Saved {len(saved)} KB file(s).")
                set_ui_message("kb", "Successfully saved KB.", "success")
                st.rerun()

    with kb_c2:
        if st.button("Clear Saved KB Files", width='stretch'):
            try:
                removed, remote_deleted = clear_saved_kb_files()

                msg = f"Cleared saved KB file(s) ({removed} file(s) removed). Disabled KB usage."
                if remote_deleted:
                    msg += " Deleted the active remote vector store."
                else:
                    msg += " No deletion as no active vector store was set yet."

                add_status(msg)
                set_ui_message("kb", "Successfully cleared KB.", "success")
                st.rerun()

            except Exception as e:
                msg = f"KB clear failed: {e}"
                add_status(msg)
                set_ui_message("kb", msg, "error")
                st.rerun()

    kb_message_placeholder = st.empty()
    render_ui_message("kb", kb_message_placeholder)

    kb_saved = list_saved_kb_files()
    st.caption(f"Saved KB files: {len(kb_saved)} file(s)")

    if kb_saved:
        with st.expander("View saved KB files"):
            for p in kb_saved:
                st.markdown(f"- `{p.relative_to(KB_DIR)}`")

    st.subheader("3) Upload Product Media")
    uploaded_media = st.file_uploader(
        "Images, audio, or video",
        type=["png", "jpg", "jpeg", "webp", "mp3", "wav", "m4a", "aac", "mp4", "mov", "mkv", "webm"],
        accept_multiple_files=True,
        key="media_uploader",
    )

    saved_media = list_saved_media_files()

    mc1, mc2 = st.columns(2)
    with mc1:
        if st.button("Save Media Files", width='stretch'):
            if not uploaded_media:
                set_ui_message("media", "Upload at least one media file first.", "warning")
                st.rerun()
            else:
                add_status("Saving uploaded media file(s).")
                saved_paths = save_uploaded_media(uploaded_media)

                add_status(f"Saved {len(saved_paths)} media file(s).")
                set_ui_message("media", "Successfully saved media.", "success")
                st.rerun()

    with mc2:
        if st.button("Clear Saved Media", width='stretch'):
            removed = clear_saved_media()
            add_status(f"Cleared saved media ({removed} item(s) removed).")
            set_ui_message("media", "Successfully cleared media.", "success")
            st.rerun()

    media_message_placeholder = st.empty()
    render_ui_message("media", media_message_placeholder)

    saved_media = list_saved_media_files()
    st.caption(f"Saved media: {len(saved_media)} file(s)")

    if saved_media:
        with st.expander("View saved media files"):
            for p in saved_media:
                st.markdown(f"- `{p.name}`")

    if st.button("Auto-Generate 13 Brief Fields from Product Input", width='stretch'):
        clear_ui_messages()
        kb_message_placeholder.empty()
        media_message_placeholder.empty()

        if not raw_context.strip():
            st.error("Add product context first.")
        else:
            try:
                def _run_auto_brief():
                    add_status("Starting 13-field brief auto-generation.")
                    add_status("Reading product and market input.")

                    media_paths = list_saved_media_files()

                    if media_paths:
                        add_status(f"Using {len(media_paths)} saved media file(s) for analysis.")
                        add_status("Analyzing media.")
                        media_context = summarize_media_files(media_paths)
                        add_status("Media analysis complete.")
                    else:
                        add_status("No saved media found. Continuing with text-only product context.")
                        media_context = ""

                    full_context = raw_context.strip()
                    if media_context:
                        add_status("Combining product/market input with media evidence.")
                        full_context += "\n\nMEDIA EVIDENCE\n" + media_context
                    else:
                        add_status("Using product/market input only.")

                    add_status("Generating concise 13-field brief from combined context.")
                    generated_lines = generate_brief_lines_from_context(full_context)
                    return generated_lines

                generated_lines = run_with_global_spinner(
                    "Auto-generating 13-field brief...",
                    _run_auto_brief,
                )

                set_brief_lines(generated_lines, sync_widgets=True)
                add_status("13-field brief generated successfully.")
                set_ui_message("brief", "13-field brief generated. Review/edit below.", "success")
                st.rerun()
            except Exception as e:
                st.error(str(e))
                add_status(f"Brief generation failed: {e}")
   
    brief_message_placeholder = st.empty()
    render_ui_message("brief", brief_message_placeholder)

    st.subheader("4) Marketing Brief (13 Fields)")
    placeholders = [
        "Value proposition",
        "Benefits",
        "Constraints",
        "Goal",
        "Platform",
        "Tone",
        "Format",
        "Platform constraints",
        "Region",
        "Regulation",
        "Audience",
        "Awareness",
        "Pain points",
    ]

    inputs = []
    for i in range(13):
        val = st.text_area(
            placeholder=placeholders[i],
            key=f"line_{i}",
            label=placeholders[i],
        )
        inputs.append(val.strip())
    st.session_state.lines = inputs

    generate_examples = st.checkbox("Generate Example Posts", value=True)

    kb_ready = bool(get_vector_store_id())

    if kb_ready and st.session_state.get("enable_rag_next_run"):
        st.session_state["use_rag"] = True
        st.session_state["enable_rag_next_run"] = False

    use_rag = st.checkbox(
        "Use Knowledge Base",
        key="use_rag",
        disabled=not kb_ready,
    )

    debug = st.checkbox("Debug Mode", value=False)

    kb_file_count = len(kb_saved)

    c1, c2 = st.columns(2)
    with c1:
        rebuild_in_progress = st.session_state.get("kb_rebuild_in_progress", False)
        rebuild_disabled = kb_file_count == 0 or rebuild_in_progress

        st.button(
            "Rebuild KB Index",
            key="rebuild_kb_index_btn",
            width='stretch',
            disabled=rebuild_disabled,
            help=(
                "Save at least one KB file first." if kb_file_count == 0
                else "KB index rebuild is already in progress." if rebuild_in_progress
                else None
            ),
            on_click=request_kb_rebuild if kb_file_count > 0 and not rebuild_in_progress else None,
        )

    # Run the rebuild after the button has already been rendered once in disabled mode
    if st.session_state.get("kb_rebuild_requested", False):
        st.session_state["kb_rebuild_requested"] = False

        try:
            add_status("Starting KB index rebuild.")
            run_with_global_spinner("Rebuilding KB index...", setup_kb_main)
            st.session_state["enable_rag_next_run"] = True
            add_status("KB indexed successfully. Knowledge Base will be enabled.")
            set_ui_message("kb_index", "Indexing successful.", "success")
        except Exception as e:
            msg = f"KB indexing failed: {e}"
            add_status(msg)
            set_ui_message("kb_index", msg, "error")
        finally:
            st.session_state["kb_rebuild_in_progress"] = False

        st.rerun()

    with c2:
        st.caption(f"KB status: {kb_file_count} local file(s)")
        if kb_file_count == 0:
            st.caption("Upload and save KB files to enable rebuilding.")

    kb_index_message_placeholder = st.empty()
    render_ui_message("kb_index", kb_index_message_placeholder)

    if st.button("Generate", type="primary", width='stretch'):
        clear_ui_messages()
        kb_message_placeholder.empty()
        media_message_placeholder.empty()
        kb_index_message_placeholder.empty()

        filled = [x for x in inputs if x]
        if len(filled) != 13:
            st.error(f"Need 13 fields. You have {len(filled)}.")
            add_status(f"Generation blocked: {len(filled)}/13 fields filled.")
        else:
            os.environ["GENERATE_EXAMPLE_POSTS"] = str(generate_examples).lower()
            os.environ["USE_RAG"] = str(use_rag).lower()
            os.environ["DEBUG_FILE_SEARCH"] = str(debug).lower()
            brief = formatInput(inputs)
            try:
                add_status("Starting campaign generation.")
                run_with_global_spinner("Generating campaign outputs...", gpt, brief, status_cb=add_status)

                st.session_state.current_run_stamp = latest_run_stamp()
                st.session_state.chat_history = []
                st.session_state["generated_ad_image_paths"] = []
                st.session_state["generated_ad_image_run_stamp"] = None

                st.success("Generated successfully.")
                add_status("Campaign outputs generated successfully.")
            except Exception as e:
                st.error(str(e))
                add_status(f"Campaign generation failed: {e}")

with right:
    st.subheader("Outputs")

    current_run_stamp = st.session_state.current_run_stamp

    run_files = {
        "plan": run_file("01_detailed_marketing_plan", current_run_stamp),
        "playbooks": run_file("02_platform_playbooks", current_run_stamp),
        "calendar": run_file("03_week_by_week_calendar", current_run_stamp),
        "examples": run_file("04_example_posts", current_run_stamp),
        "debug": run_file("retrieval_debug", current_run_stamp),
    }

    tabs = st.tabs(["Plan", "Playbooks", "Calendar", "Examples", "Debug"])
    tab_keys = ["plan", "playbooks", "calendar", "examples", "debug"]

    for tab, key in zip(tabs, tab_keys):
        with tab:
            file = run_files[key]
            if file:
                st.markdown(file.read_text(encoding="utf-8"))
            else:
                st.info("No output yet.")

    # Build downstream context ONLY from campaign content in the same run.
    # Keep debug out of this context.
    context_files = [
        run_files["plan"],
        run_files["playbooks"],
        run_files["calendar"],
    ]

    if run_files["examples"] is not None:
        context_files.append(run_files["examples"])

    latest_context = "\n\n".join(
        f.read_text(encoding="utf-8") for f in context_files if f is not None
    ) if current_run_stamp else ""

    if latest_context:
        st.subheader("Ad/Image Generation")
        num_images = st.slider("Images to generate", 1, 4, 2)
        if st.button("Generate Ad Images from Latest Outputs", width='stretch'):
            try:
                add_status(f"Generating {num_images} ad image(s) from latest run outputs.")
                generated = run_with_global_spinner(
                    f"Generating {num_images} ad image(s)...",
                    generate_ad_images,
                    latest_context,
                    num_images=num_images,
                )
                st.session_state["generated_ad_image_paths"] = [str(p) for p in generated]
                st.session_state["generated_ad_image_run_stamp"] = current_run_stamp
                st.success(f"Generated {len(generated)} image(s).")
                add_status(f"Generated {len(generated)} ad image(s).")
            except Exception as e:
                st.error(f"Image generation failed: {e}")
                add_status(f"Ad image generation failed: {e}")

        if (
            st.session_state.get("generated_ad_image_paths")
            and st.session_state.get("generated_ad_image_run_stamp") == current_run_stamp
        ):
            for p in st.session_state["generated_ad_image_paths"]:
                st.image(p, caption=Path(p).name, width='stretch')

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if latest_context:
        st.subheader("Campaign Chatbot")
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        q = st.chat_input("Ask about your generated strategy, content calendar, or playbooks.")
        if q:
            st.session_state.chat_history.append({"role": "user", "content": q})
            with st.chat_message("user"):
                st.markdown(q)
            try:
                add_status("Running chatbot response over latest run outputs.")
                reply = run_with_global_spinner(
                    "Generating chatbot response...",
                    chat_about_outputs,
                    q,
                    latest_context,
                    st.session_state.chat_history[:-1],
                )
                add_status("Chatbot response generated.")
            except Exception as e:
                reply = f"Chat failed: {e}"
                add_status(f"Chatbot failed: {e}")
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)