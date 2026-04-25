from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from .config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    MAX_FILE_SEARCH_RESULTS,
    DEBUG_FILE_SEARCH,
    GENERATE_EXAMPLE_POSTS,
    get_vector_store_id,
)

# ----------------------------
# Init
# ----------------------------
client = OpenAI(api_key=OPENAI_API_KEY)

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "outputs"
OUT_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# ----------------------------
# Utils
# ----------------------------
def write_md(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _runtime_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() == "true"


def _to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"

def _build_file_search_tools() -> list[dict] | None:
    vector_store_id = get_vector_store_id()
    if not vector_store_id:
        return None

    return [{
        "type": "file_search",
        "vector_store_ids": [vector_store_id],
        "max_num_results": MAX_FILE_SEARCH_RESULTS,
    }]


# ----------------------------
# Prompt contracts (STRICT HEADERS FOR SPLITTING)
# ----------------------------
gptInstructions = """
You are a marketing strategist.

Output MUST be valid markdown and MUST include these exact H1 headers on their own lines (copy exactly):
# 1) Detailed Marketing Plan
# 2) Platform-Specific Playbooks
# 3) Week-by-Week Content Calendar

Rules:
- Do not rename the headers.
- Do not use "1)" "2)" "3)" anywhere else as a heading.
- Section 3 MUST include a markdown table.
- If details are missing, state assumptions explicitly inside Section 1.

Now produce the content under the three headers in order.
"""

examplePostInstructions = """
You are a marketing strategist and copywriter.
Create platform-ready example posts based strictly on the provided marketing plan + playbooks + calendar.

Output markdown with these sections (in order):
# 4) Example Posts
## LinkedIn (2 posts)
## Instagram Carousel (2 posts)
## Short-form Video (2 scripts: TikTok/Reels/Shorts)
## Website/Blog (1 outline + 1 short intro paragraph)

For each social post include:
- Goal (Awareness/Engage/Convert)
- Caption (include a compliant disclaimer line)
- Media type (carousel/reel/single image/video)
- Visual direction (what to show in each slide or shot list)
- CTA (exact wording)

Safety constraints:
- Do NOT diagnose or prescribe.
- Always include a non-diagnosis disclaimer and encourage urgent care/emergency services when appropriate.
Keep it concise and practical.
"""

briefBuilderInstructions = """
You convert product and market notes into exactly 13 concise fields for a marketing brief.
Return valid JSON only:
{
  "lines": [
    "<1) Value proposition>",
    "<2) Benefits and differentiation>",
    "<3) Constraints and maturity>",
    "<4) Primary goal>",
    "<5) Publishing platform/channel>",
    "<6) Tone/style>",
    "<7) Format>",
    "<8) Platform constraints>",
    "<9) Region geography and language>",
    "<10) Cultural/regulatory context>",
    "<11) Audience personas/roles>",
    "<12) Audience awareness stage>",
    "<13) Audience pain points/barriers>"
  ]
}
Rules:
- Exactly 13 strings in order.
- Each line max 20 words.
- If data is missing, infer a reasonable assumption and keep it explicit.
"""


# ----------------------------
# Splitting (GUARANTEED) — ONLY ON EXACT H1 HEADERS
# ----------------------------
H1_1 = "# 1) Detailed Marketing Plan"
H1_2 = "# 2) Platform-Specific Playbooks"
H1_3 = "# 3) Week-by-Week Content Calendar"


def split_sections_strict(full_md: str) -> dict[str, str]:
    """
    Split ONLY on the exact H1 headers defined above.
    If any are missing or out of order, raise an error (so you never silently break GUI tabs).
    """
    text = full_md.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")

    # Find exact header lines (start of line match)
    def find_header(h: str) -> int:
        m = re.search(rf"(?m)^{re.escape(h)}\s*$", text)
        return -1 if not m else m.start()

    i1 = find_header(H1_1)
    i2 = find_header(H1_2)
    i3 = find_header(H1_3)

    if i1 == -1 or i2 == -1 or i3 == -1:
        missing = []
        if i1 == -1: missing.append(H1_1)
        if i2 == -1: missing.append(H1_2)
        if i3 == -1: missing.append(H1_3)
        raise RuntimeError(
            "Model output is missing required section headers. Missing:\n- "
            + "\n- ".join(missing)
            + "\n\nFix: Ensure gptInstructions are unchanged and model follows the header contract."
        )

    if not (i1 < i2 < i3):
        raise RuntimeError(
            "Section headers found but out of order. "
            "Fix: Ensure the model outputs sections in order 1 -> 2 -> 3."
        )

    s1 = text[i1:i2].strip()
    s2 = text[i2:i3].strip()
    s3 = text[i3:].strip()

    return {
        "01_detailed_marketing_plan": s1,
        "02_platform_playbooks": s2,
        "03_week_by_week_calendar": s3,
    }


def build_index_md(stamp: str, files: dict[str, Path]) -> str:
    lines = [
        "# Output Package",
        "",
        f"- Run timestamp: `{stamp}`",
        "",
        "## Files",
    ]
    for key, path in files.items():
        lines.append(f"- **{key}**: `{path.name}`")
    lines.append("")
    return "\n".join(lines)


# ----------------------------
# Core generation
# ----------------------------
def generate_brief_lines_from_context(context: str) -> list[str]:
    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=briefBuilderInstructions,
        input=context,
    )
    text = response.output_text.strip()
    try:
        data = json.loads(text)
        lines = data["lines"]
    except Exception as e:
        raise RuntimeError(f"Brief generation returned invalid JSON: {text[:500]}") from e

    if not isinstance(lines, list) or len(lines) != 13:
        raise RuntimeError("Brief generation did not return exactly 13 lines.")
    return [str(x).strip() for x in lines]


def summarize_images(image_paths: list[Path]) -> str:
    if not image_paths:
        return ""

    chunks = []
    for p in image_paths:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Summarize this product image for marketing strategy in 6 bullet points."},
                        {"type": "input_image", "image_url": _to_data_url(p)},
                    ],
                }
            ],
        )
        chunks.append(f"Image `{p.name}`:\n{response.output_text.strip()}")
    return "\n\n".join(chunks)


def transcribe_audio_file(audio_path: Path) -> str:
    with audio_path.open("rb") as f:
        t = client.audio.transcriptions.create(
            model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
            file=f,
        )
    return t.text.strip()


def _extract_video_assets(video_path: Path) -> tuple[list[Path], Path | None]:
    stamp = now_stamp()
    work_dir = UPLOADS_DIR / f"video_{stamp}_{video_path.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_out = work_dir / "audio.wav"
    frame_pattern = work_dir / "frame_%02d.jpg"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(audio_out),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-vf",
                "fps=1/3",
                "-frames:v",
                "4",
                str(frame_pattern),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ([], None)

    frames = sorted(work_dir.glob("frame_*.jpg"))
    return (frames, audio_out if audio_out.exists() else None)


def summarize_media_files(media_paths: list[Path]) -> str:
    image_paths = [p for p in media_paths if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    audio_paths = [p for p in media_paths if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac"}]
    video_paths = [p for p in media_paths if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}]

    out = []
    img_summary = summarize_images(image_paths)
    if img_summary:
        out.append("## Image insights\n" + img_summary)

    for ap in audio_paths:
        transcript = transcribe_audio_file(ap)
        out.append(f"## Audio transcript `{ap.name}`\n{transcript}")

    for vp in video_paths:
        frames, audio_out = _extract_video_assets(vp)
        if not frames and audio_out is None:
            out.append(f"## Video `{vp.name}`\nUnable to process video automatically (ffmpeg not available).")
            continue
        if frames:
            out.append(f"## Video frame insights `{vp.name}`\n{summarize_images(frames)}")
        if audio_out:
            try:
                transcript = transcribe_audio_file(audio_out)
                out.append(f"## Video audio transcript `{vp.name}`\n{transcript}")
            except Exception:
                out.append(f"## Video audio transcript `{vp.name}`\nTranscription failed.")

    return "\n\n".join(out).strip()


def chat_about_outputs(question: str, output_context: str, history: list[dict[str, str]] | None = None) -> str:
    history = history or []
    chat_input = [{"role": m["role"], "content": m["content"]} for m in history]
    chat_input.append({"role": "user", "content": question})
    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=(
            "You are Campaign Coach assistant. Answer using the provided campaign outputs first, "
            "and be explicit when you are making an assumption.\n\n"
            f"Campaign context:\n{output_context}"
        ),
        input=chat_input,
    )
    return response.output_text.strip()


def generate_ad_images(source_text: str, num_images: int = 2) -> list[Path]:
    prompts = client.responses.create(
        model=OPENAI_MODEL,
        instructions=(
            "Create concise ad image prompts from this marketing output. "
            "Return JSON with key `prompts` containing up to 6 strings."
        ),
        input=source_text,
    )
    try:
        parsed = json.loads(prompts.output_text)
        prompt_list = [str(p).strip() for p in parsed.get("prompts", []) if str(p).strip()]
    except Exception:
        prompt_list = [source_text[:600]]

    image_paths: list[Path] = []
    for i, prompt in enumerate(prompt_list[: max(1, num_images)]):
        img = client.images.generate(
            model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1.5"),
            prompt=prompt,
            size="1024x1024",
        )
        b64 = img.data[0].b64_json
        out_path = OUT_DIR / f"ad_image_{now_stamp()}_{i+1}.png"
        out_path.write_bytes(base64.b64decode(b64))
        image_paths.append(out_path)
    return image_paths


def gpt(brief: str, status_cb=None) -> None:
    def emit(msg: str) -> None:
        if status_cb:
            status_cb(msg)

    debug_file_search = _runtime_flag("DEBUG_FILE_SEARCH", DEBUG_FILE_SEARCH)
    generate_example_posts = _runtime_flag("GENERATE_EXAMPLE_POSTS", GENERATE_EXAMPLE_POSTS)
    use_rag = _runtime_flag("USE_RAG", True)
    include_fields = ["file_search_call.results"] if debug_file_search else None

    emit("Preparing campaign generation request.")

    request_kwargs = {
        "model": OPENAI_MODEL,
        "instructions": gptInstructions,
        "input": brief,
        "include": include_fields,
    }

    file_search_tools = _build_file_search_tools()

    if use_rag and file_search_tools:
        request_kwargs["tools"] = file_search_tools
    elif use_rag and not file_search_tools:
        print("[Info] USE_RAG=true but no KB is indexed yet. Continuing without file_search.")
        emit("KB requested but no KB is indexed. Continuing without RAG.")

    emit("Sending request to the model.")
    response = client.responses.create(**request_kwargs)
    emit("Main campaign content received.")

    stamp = now_stamp()
    full_text = response.output_text

    full_path = OUT_DIR / f"output_full_{stamp}.md"
    write_md(full_path, full_text)

    parts = split_sections_strict(full_text)

    p1 = OUT_DIR / f"01_detailed_marketing_plan_{stamp}.md"
    p2 = OUT_DIR / f"02_platform_playbooks_{stamp}.md"
    p3 = OUT_DIR / f"03_week_by_week_calendar_{stamp}.md"

    write_md(p1, parts["01_detailed_marketing_plan"])
    write_md(p2, parts["02_platform_playbooks"])
    write_md(p3, parts["03_week_by_week_calendar"])
    print(f"[Saved] {full_path}")
    print(f"[Saved] {p1}")
    print(f"[Saved] {p2}")
    print(f"[Saved] {p3}")
    emit("Saved plan, playbooks, and calendar files.")

    ex_path: Path | None = None
    if generate_example_posts:
        emit("Generating example posts.")
        ex_path = OUT_DIR / f"04_example_posts_{stamp}.md"
        context_for_examples = (
            parts["01_detailed_marketing_plan"]
            + "\n\n"
            + parts["02_platform_playbooks"]
            + "\n\n"
            + parts["03_week_by_week_calendar"]
        )

        ex_response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=examplePostInstructions,
            input=context_for_examples
        )
        write_md(ex_path, ex_response.output_text)
        emit("Saved example posts file.")
        print(f"[Saved] {ex_path}")
    else:
        emit("Example post generation disabled.")

    index_path = OUT_DIR / f"00_index_{stamp}.md"
    saved_files = {
        "output_full": full_path,
        "01_detailed_marketing_plan": p1,
        "02_platform_playbooks": p2,
        "03_week_by_week_calendar": p3,
    }
    if ex_path is not None:
        saved_files["04_example_posts"] = ex_path

    write_md(index_path, build_index_md(stamp, saved_files))
    print(f"[Saved] {index_path}")

    if debug_file_search:
        debug_md_path = OUT_DIR / f"retrieval_debug_{stamp}.md"
        raw = response.model_dump() if hasattr(response, "model_dump") else json.loads(str(response))

        write_md(
            debug_md_path,
            "# Retrieval Debug\n\n"
            "Raw response payload including file_search results.\n\n"
            "```json\n"
            + json.dumps(raw, indent=2)
            + "\n```\n"
        )
        emit("Saved retrieval debug file.")
        print(f"[Saved] {debug_md_path}")


# ----------------------------
# Input formatting (13-line schema)
# ----------------------------
def userInput(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        rawInput = [line.strip() for line in f if line.strip() != ""]
    return formatInput(rawInput)


def formatInput(rawInput: list[str]) -> str:
    if len(rawInput) != 13:
        raise ValueError(
            f"userInput.txt should have exactly 13 non-empty lines, but found {len(rawInput)}.\n"
            "Expected order:\n"
            "1) productVP\n2) productBD\n3) productCM\n4) productPG\n"
            "5) publishingP\n6) publishingTS\n7) publishingF\n8) publishingPC\n"
            "9) regionGL\n10) regionCRC\n"
            "11) audiencePR\n12) audienceAS\n13) audiencePPB\n"
        )

    (
        productVP, productBD, productCM, productPG,
        publishingP, publishingTS, publishingF, publishingPC,
        regionGL, regionCRC,
        audiencePR, audienceAS, audiencePPB
    ) = rawInput

    brief = f"""
PRODUCT
- Value proposition: {productVP}
- Benefits & differentiation: {productBD}
- Constraints & maturity: {productCM}
- Primary goal: {productPG}

PUBLISHING PLATFORM
- Channel: {publishingP}
- Tone/style: {publishingTS}
- Format: {publishingF}
- Constraints: {publishingPC}

REGION
- Geography & language: {regionGL}
- Cultural/regulatory context: {regionCRC}

AUDIENCE
- Personas/roles: {audiencePR}
- Awareness stage: {audienceAS}
- Pain points/barriers: {audiencePPB}
"""
    return brief


def main():
    gptInput = userInput(str(BASE_DIR / "userInput.txt"))
    gpt(gptInput)


if __name__ == "__main__":
    main()