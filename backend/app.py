from fastapi import FastAPI, Form, UploadFile, File, Request
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
import sys
import re
import json
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from openai import OpenAI
from playwright.async_api import async_playwright

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from OpenAI_Marketing_Agent_Cleaned_March27.main import (
    chat_about_outputs,
    generate_ad_images,
    generate_brief_lines_from_context,
    formatInput,
    gpt,
)
from OpenAI_Marketing_Agent_Cleaned_March27.config import (
    BASE_DIR,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)

app = FastAPI(title="Campaign Coach Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=OPENAI_API_KEY)

UPLOADS_DIR = BASE_DIR / "uploads"
KB_DIR = BASE_DIR / "KB"
OUTPUTS_DIR = BASE_DIR / "outputs"
UPLOADS_DIR.mkdir(exist_ok=True)
KB_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)
AUTH_DEBUG_DIR = OUTPUTS_DIR / "auth_debug"
AUTH_DEBUG_DIR.mkdir(exist_ok=True)

app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")


@app.get("/download_output/{filename}")
def download_output(filename: str):
    safe_name = Path(filename).name
    file_path = OUTPUTS_DIR / safe_name

    if not file_path.exists() or not file_path.is_file():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type='text/markdown',
        headers={
            'Content-Disposition': f'attachment; filename="{safe_name}"',
        },
    )

AGENT_MAX_STEPS = 6
AGENT_MAX_CANDIDATES = 18
PAGE_TEXT_LIMIT = 3500
SITE_TEXT_LIMIT = 14000

NAVIGATION_DECISION_INSTRUCTIONS = """
You are selecting the next internal website page to inspect for a marketing brief.

Goal:
Choose the single best next internal page that will improve understanding of:
- what the company/product offers
- who it serves
- benefits and differentiation
- trust/credibility/compliance signals
- tone and positioning

Prefer pages like:
- about
- product
- features
- pricing
- services
- solutions
- use cases
- faq
- contact
- dashboard
- modules
- workflows
- patients
- appointments
- billing
- reports
- settings

Avoid pages like:
- signup
- cart
- checkout
- privacy
- terms
- careers
- blog tag archives
- press archive pages
- legal pages
- social links
- file downloads
- logout

Return valid JSON only in this exact format:
{"choice_index": 3, "reason": "short reason"}

If no candidate is worth visiting, return:
{"choice_index": -1, "reason": "short reason"}
""".strip()

WEBSITE_SUMMARY_INSTRUCTIONS = """
You are helping generate a marketing campaign brief from a company website.

You will receive content gathered by a browser agent from multiple internal pages on the same website.

Write one clean paragraph that summarizes:
- what the company/product appears to offer
- who it appears to be for
- the likely main benefits
- likely differentiation
- the apparent tone/positioning
- any visible trust, compliance, regional, or credibility signals if present
- if the site is a logged-in product, what the main product modules or workflows appear to be

Rules:
- Return plain text only
- One paragraph only
- Around 140 to 220 words
- If uncertain, say "appears", "likely", or "suggests"
- Do not use bullets
- Do not use markdown
""".strip()




_BRAND_STOPWORDS = {
    "the", "and", "for", "with", "from", "your", "their", "this", "that",
    "our", "its", "into", "onto", "platform", "product", "company", "business",
    "solution", "service", "services", "market", "description", "brand", "name",
    "healthcare", "hospital", "clinic", "medical", "software", "system",
}


def _clean_brand_candidate(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "")
    value = value.strip()
    value = value.strip("'\"`.,:;|-_")
    value = re.sub(r"\s{2,}", " ", value)
    return value[:60].strip()


def _looks_like_brand_candidate(value: str) -> bool:
    if not value:
        return False
    if len(value) < 2 or len(value) > 40:
        return False
    if value.lower() in _BRAND_STOPWORDS:
        return False
    if re.fullmatch(r"[0-9\W_]+", value):
        return False
    words = value.split()
    if len(words) > 4:
        return False
    if any(word.lower() in _BRAND_STOPWORDS for word in words):
        return False
    return True


def _extract_brand_name_from_context(raw_context: str) -> str:
    text = re.sub(r"\s+", " ", raw_context or "").strip()
    if not text:
        return ""

    explicit_patterns = [
        r"(?:brand|company|product|platform|solution|business|organization|organisation)\s*(?:name)?\s*[:\-]\s*([A-Za-z][A-Za-z0-9&+./'\-]*(?:\s+[A-Za-z0-9&+./'\-]+){0,3})",
        r"(?:called|named)\s+([A-Za-z][A-Za-z0-9&+./'\-]*(?:\s+[A-Za-z0-9&+./'\-]+){0,3})",
        r"^([A-Za-z][A-Za-z0-9&+./'\-]{1,30})\s+(?:is|offers|provides|helps|connects|serves|allows|enables)",
    ]

    for pattern in explicit_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = _clean_brand_candidate(match.group(1))
            if _looks_like_brand_candidate(candidate):
                return candidate

    camelcase_matches = re.findall(
        r"(?:[a-z]+[A-Z][A-Za-z0-9]*|[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]+)+)",
        text,
    )
    for candidate in camelcase_matches:
        cleaned = _clean_brand_candidate(candidate)
        if _looks_like_brand_candidate(cleaned):
            return cleaned

    capitalized_pairs = re.findall(
        r"([A-Z][A-Za-z0-9&+./'\-]{1,20}(?:\s+[A-Z][A-Za-z0-9&+./'\-]{1,20}){0,2})",
        text,
    )
    for candidate in capitalized_pairs:
        cleaned = _clean_brand_candidate(candidate)
        if _looks_like_brand_candidate(cleaned):
            return cleaned

    return ""


def _inject_brand_into_image_source(examples_text: str, raw_context: str) -> str:
    examples_text = (examples_text or "").strip()
    brand_name = _extract_brand_name_from_context(raw_context)
    if not brand_name:
        return examples_text

    brand_block = (
        f"Brand to represent: {brand_name}\n\n"
        f'Use the exact brand identity "{brand_name}" for every ad concept. '
        f"Do not substitute or invent another company, product, or platform name. "
        f"The visual should clearly feel like an ad for {brand_name}.\n"
    )
    return f"{brand_block}\n{examples_text}".strip()


COMMON_LOGIN_PATHS = [
    "/login",
    "/signin",
    "/sign-in",
    "/auth/login",
    "/auth/signin",
    "/account/login",
    "/user/login",
    "/users/sign_in",
    "/session/new",
    "/portal/login",
]

LOGIN_LINK_PATTERN = re.compile(
    r"log\s?in|sign\s?in|member\s+login|staff\s+login|provider\s+login|portal\s+login|access\s+portal",
    re.IGNORECASE,
)

NEXT_OR_SUBMIT_PATTERN = re.compile(
    r"next|continue|submit|sign\s?in|log\s?in|access|enter",
    re.IGNORECASE,
)

ROLE_CONTROL_PATTERN = re.compile(
    r"select\s+a\s+role|choose\s+a\s+role|role",
    re.IGNORECASE,
)


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _debug_artifact_web_path(path: Path) -> str:
    try:
        rel = path.relative_to(OUTPUTS_DIR).as_posix()
        return f"/outputs/{rel}"
    except Exception:
        return str(path)


def _normalize_text_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def _normalize_text_for_selector(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_role_variants(role_text: str) -> list[str]:
    base = _normalize_text_for_selector(role_text)
    if not base:
        return []

    pieces = [base]
    slash_split = [part.strip() for part in re.split(r"[\/|,]", base) if part.strip()]
    if len(slash_split) > 1:
        pieces.extend(slash_split)

    words = [word.strip() for word in re.split(r"\s+", base) if word.strip()]
    if words:
        pieces.append(" ".join(words))

    seen = set()
    variants = []
    for piece in pieces:
        norm = _normalize_text_for_match(piece)
        if norm and norm not in seen:
            seen.add(norm)
            variants.append(piece)
    return variants


def _role_regex_variants(role_text: str) -> list[re.Pattern]:
    variants = []
    for value in _normalize_role_variants(role_text):
        escaped = re.escape(_normalize_text_for_selector(value))
        escaped = escaped.replace(r"\ ", r"\s+")
        variants.append(re.compile(rf"^{escaped}$", re.IGNORECASE))
    return variants


def _role_partial_regex_variants(role_text: str) -> list[re.Pattern]:
    variants = []
    for value in _normalize_role_variants(role_text):
        escaped = re.escape(_normalize_text_for_selector(value))
        escaped = escaped.replace(r"\ ", r"\s+")
        variants.append(re.compile(escaped, re.IGNORECASE))
    return variants


def _normalize_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return ""
    if not re.match(r"^https?://", cleaned, flags=re.IGNORECASE):
        cleaned = f"https://{cleaned}"
    return cleaned


def _same_domain(base_netloc: str, candidate_url: str) -> bool:
    try:
        return urlparse(candidate_url).netloc == base_netloc
    except Exception:
        return False


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Could not find JSON object in: {text[:500]}")
    return json.loads(match.group(0))


def _limit_text(text: str, max_len: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[:max_len]
    return text


def _is_auth_related_url(url: str) -> bool:
    lowered = url.lower()
    auth_keywords = [
        "/login",
        "/signin",
        "/sign-in",
        "/signup",
        "/sign-up",
        "/register",
        "/auth",
        "/sso",
        "/users/sign_in",
        "/session/new",
        "/account/login",
    ]
    return any(keyword in lowered for keyword in auth_keywords)


def _is_bad_path(url: str, allow_auth_paths: bool = False) -> bool:
    lowered = url.lower()

    bad_keywords = [
        "/signup",
        "/sign-up",
        "/register",
        "/cart",
        "/checkout",
        "/privacy",
        "/terms",
        "/cookie",
        "/legal",
        "/careers",
        "/jobs",
        "/press",
        "/news",
        "/blog/page/",
        "/tag/",
        "/category/",
        "/logout",
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "mailto:",
        "tel:",
    ]

    if not allow_auth_paths:
        bad_keywords.extend([
            "/login",
            "/signin",
            "/sign-in",
        ])

    bad_exts = [
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".webp",
        ".zip",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
    ]

    return any(k in lowered for k in bad_keywords) or any(lowered.endswith(ext) for ext in bad_exts)


def _score_candidate(url: str, label: str) -> int:
    combined = f"{url} {label}".lower()
    score = 0

    preferred = [
        "about",
        "product",
        "products",
        "feature",
        "features",
        "pricing",
        "service",
        "services",
        "solution",
        "solutions",
        "use case",
        "use-case",
        "usecase",
        "faq",
        "contact",
        "company",
        "how it works",
        "how-it-works",
        "platform",
        "dashboard",
        "patient",
        "patients",
        "appointment",
        "appointments",
        "scheduling",
        "billing",
        "claims",
        "report",
        "reports",
        "analytics",
        "module",
        "modules",
        "workflow",
        "workflows",
        "admin",
        "settings",
    ]

    for i, word in enumerate(preferred):
        if word in combined:
            score += 100 - i

    if combined.count("/") <= 4:
        score += 10

    if "home" in combined:
        score += 3

    return score


def _extract_page_data_from_html(url: str, html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    def meta(attr_name: str, attr_value: str) -> str:
        tag = soup.find("meta", attrs={attr_name: attr_value})
        if tag and tag.get("content"):
            return tag["content"].strip()
        return ""

    meta_description = meta("name", "description")
    og_title = meta("property", "og:title")
    og_description = meta("property", "og:description")

    headings = []
    for tag_name in ["h1", "h2"]:
        for tag in soup.find_all(tag_name):
            text = tag.get_text(" ", strip=True)
            if text:
                headings.append(text)
    headings = headings[:12]

    body_text = " ".join(soup.stripped_strings)
    body_text = _limit_text(body_text, PAGE_TEXT_LIMIT)

    if len(body_text) < 150:
        return None

    return {
        "url": url,
        "title": title,
        "meta_description": meta_description,
        "og_title": og_title,
        "og_description": og_description,
        "headings": headings,
        "text": body_text,
    }


def _extract_internal_link_candidates(
    current_url: str,
    html: str,
    base_netloc: str,
    allow_auth_paths: bool = False,
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    candidates = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith("#"):
            continue

        absolute = urljoin(current_url, href)
        parsed = urlparse(absolute)

        if parsed.scheme not in ("http", "https"):
            continue

        cleaned = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            cleaned += f"?{parsed.query}"

        if not _same_domain(base_netloc, cleaned):
            continue

        if _is_bad_path(cleaned, allow_auth_paths=allow_auth_paths):
            continue

        if cleaned in seen:
            continue
        seen.add(cleaned)

        label = a.get_text(" ", strip=True)
        if not label:
            label = a.get("title", "").strip() or a.get("aria-label", "").strip()

        if not label:
            label = parsed.path.strip("/") or "home"

        candidates.append(
            {
                "url": cleaned,
                "label": _limit_text(label, 120),
                "score": _score_candidate(cleaned, label),
            }
        )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:AGENT_MAX_CANDIDATES]


def _choose_next_link(current_page: dict, candidates: list[dict], visited_urls: set[str]) -> str | None:
    filtered = [c for c in candidates if c["url"] not in visited_urls]
    if not filtered:
        return None

    candidate_lines = []
    for i, c in enumerate(filtered):
        candidate_lines.append(f"{i}: label='{c['label']}' | url='{c['url']}'")

    prompt = f"""
Current page URL:
{current_page.get('url', 'N/A')}

Current page title:
{current_page.get('title', 'N/A')}

Current page headings:
{', '.join(current_page.get('headings', [])) if current_page.get('headings') else 'N/A'}

Current page summary text excerpt:
{current_page.get('text', '')[:1200]}

Already visited URLs:
{chr(10).join(sorted(visited_urls)) if visited_urls else 'None'}

Candidate next pages:
{chr(10).join(candidate_lines)}
""".strip()

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=NAVIGATION_DECISION_INSTRUCTIONS,
            input=prompt,
        )
        data = _extract_json_object(response.output_text)
        choice_index = int(data.get("choice_index", -1))
        if 0 <= choice_index < len(filtered):
            return filtered[choice_index]["url"]
    except Exception as e:
        print(f"Navigation decision fallback used: {e}")

    return filtered[0]["url"] if filtered else None


async def _wait_for_page_hydration(page, extra_wait_ms: int = 1200) -> None:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    try:
        await page.wait_for_load_state("load", timeout=8000)
    except Exception:
        pass

    try:
        await page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass

    if extra_wait_ms > 0:
        await page.wait_for_timeout(extra_wait_ms)


async def _load_rendered_html(page, url: str) -> str:
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await _wait_for_page_hydration(page, extra_wait_ms=1500)

    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.6)")
        await page.wait_for_timeout(700)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)
    except Exception:
        pass

    return await page.content()


async def _locator_is_visible(locator) -> bool:
    try:
        count = await locator.count()
        if count == 0:
            return False
        return await locator.first.is_visible()
    except Exception:
        return False


async def _find_first_visible_locator(page, selectors: list[str]):
    for selector in selectors:
        locator = page.locator(selector)
        if await _locator_is_visible(locator):
            return locator.first
    return None


async def _locator_is_enabled(locator) -> bool:
    try:
        return await locator.is_enabled()
    except Exception:
        return False


async def _blur_active_field(page) -> None:
    try:
        await page.mouse.click(12, 12)
        await page.wait_for_timeout(250)
        return
    except Exception:
        pass

    try:
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(250)
    except Exception:
        pass


async def _find_visible_username_field(page):
    selectors = [
        "input[type='email']",
        "input[autocomplete='username']",
        "input[autocomplete='email']",
        "input[name*='user']",
        "input[name*='email']",
        "input[name*='login']",
        "input[id*='user']",
        "input[id*='email']",
        "input[id*='login']",
        "input[placeholder*='user']",
        "input[placeholder*='email']",
        "input[placeholder*='login']",
        "input[type='text']",
    ]
    return await _find_first_visible_locator(page, selectors)


async def _find_visible_password_field(page):
    selectors = [
        "input[type='password']",
        "input[autocomplete='current-password']",
        "input[autocomplete='password']",
    ]
    return await _find_first_visible_locator(page, selectors)


async def _find_first_visible_role_dropdown(page):
    selectors = [
        "select[name*='role']",
        "select[id*='role']",
        "select[aria-label*='role']",
        "select",
        "[role='combobox'][aria-label*='role']",
        "[role='combobox'][name*='role']",
        "[role='combobox'][id*='role']",
        "[role='combobox']",
        "[aria-haspopup='listbox'][aria-label*='role']",
        "[aria-haspopup='listbox'][name*='role']",
        "[aria-haspopup='listbox'][id*='role']",
        "[aria-haspopup='listbox']",
    ]
    return await _find_first_visible_locator(page, selectors)


async def _try_select_role_in_native_select(locator, role_text: str) -> bool:
    role_clean = role_text.strip()
    if not role_clean:
        return True

    try:
        await locator.select_option(label=role_clean, timeout=3000)
        await asyncio.sleep(0.6)
        return True
    except Exception:
        pass

    try:
        await locator.select_option(value=role_clean, timeout=3000)
        await asyncio.sleep(0.6)
        return True
    except Exception:
        pass

    try:
        matched_value = await locator.evaluate(
            """(el, desiredRole) => {
                const target = (desiredRole || "").trim().toLowerCase();
                const normalize = (value) => (value || "").trim().toLowerCase();
                const options = Array.from(el.options || []);
                const exact = options.find((opt) => {
                    return (
                        normalize(opt.label) === target ||
                        normalize(opt.text) === target ||
                        normalize(opt.value) === target
                    );
                });
                if (exact) return exact.value;

                const partial = options.find((opt) => {
                    const label = normalize(opt.label);
                    const text = normalize(opt.text);
                    const value = normalize(opt.value);
                    return (
                        label.includes(target) ||
                        text.includes(target) ||
                        value.includes(target) ||
                        target.includes(label) ||
                        target.includes(text) ||
                        target.includes(value)
                    );
                });

                return partial ? partial.value : null;
            }""",
            role_clean,
        )
        if matched_value is not None:
            await locator.select_option(value=str(matched_value), timeout=3000)
            await asyncio.sleep(0.6)
            return True
    except Exception:
        pass

    return False


async def _click_first_visible_from_candidates(candidates) -> bool:
    for candidate in candidates:
        try:
            count = await candidate.count()
            if count == 0:
                continue
            target = candidate.first
            if not await target.is_visible():
                continue
            await target.click(timeout=3000)
            await asyncio.sleep(0.7)
            return True
        except Exception:
            continue
    return False


async def _select_role_if_requested(page, role_text: str) -> bool:
    role_clean = role_text.strip()
    if not role_clean:
        return True

    role_locator = await _find_first_visible_role_dropdown(page)
    if role_locator is not None:
        try:
            tag_name = await role_locator.evaluate("(el) => el.tagName.toLowerCase()")
        except Exception:
            tag_name = ""

        if tag_name == "select":
            if await _try_select_role_in_native_select(role_locator, role_clean):
                return True

    trigger_candidates = []
    if role_locator is not None:
        trigger_candidates.append(role_locator)

    trigger_candidates.extend(
        [
            page.get_by_role("combobox"),
            page.locator("[role='combobox']"),
            page.locator("[aria-haspopup='listbox']"),
            page.get_by_role("button", name=ROLE_CONTROL_PATTERN),
            page.get_by_text(ROLE_CONTROL_PATTERN),
        ]
    )

    role_clicked = await _click_first_visible_from_candidates(trigger_candidates)
    if not role_clicked:
        return False

    exact_variants = _role_regex_variants(role_clean)
    partial_variants = _role_partial_regex_variants(role_clean)

    for role_regex in exact_variants:
        option_candidates = [
            page.get_by_role("option", name=role_regex),
            page.get_by_role("listitem", name=role_regex),
            page.get_by_role("button", name=role_regex),
            page.get_by_text(role_regex),
            page.locator("li, [role='option'], [role='menuitem'], button, div, span").filter(
                has_text=role_regex
            ),
        ]

        if await _click_first_visible_from_candidates(option_candidates):
            return True

    for partial_regex in partial_variants:
        partial_option_candidates = [
            page.get_by_role("option", name=partial_regex),
            page.get_by_role("listitem", name=partial_regex),
            page.get_by_role("button", name=partial_regex),
            page.get_by_text(partial_regex),
            page.locator("li, [role='option'], [role='menuitem'], button, div, span").filter(
                has_text=partial_regex
            ),
        ]

        if await _click_first_visible_from_candidates(partial_option_candidates):
            return True

    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass

    return False


async def _click_first_matching_auth_entry(page) -> bool:
    candidates = [
        page.get_by_role("link", name=LOGIN_LINK_PATTERN),
        page.get_by_role("button", name=LOGIN_LINK_PATTERN),
        page.locator("a[href*='login']"),
        page.locator("a[href*='signin']"),
        page.locator("button").filter(has_text=LOGIN_LINK_PATTERN),
    ]

    for candidate in candidates:
        try:
            count = await candidate.count()
            if count == 0:
                continue
            target = candidate.first
            if not await target.is_visible():
                continue
            await target.click(timeout=3000)
            await page.wait_for_timeout(1500)
            return True
        except Exception:
            continue

    return False


async def _find_first_visible_submit_target(page):
    candidates = [
        page.get_by_role("button", name=NEXT_OR_SUBMIT_PATTERN),
        page.locator("button[type='submit']"),
        page.locator("input[type='submit']"),
        page.locator("button").filter(has_text=NEXT_OR_SUBMIT_PATTERN),
    ]

    for candidate in candidates:
        try:
            count = await candidate.count()
            if count == 0:
                continue
            target = candidate.first
            if not await target.is_visible():
                continue
            return target
        except Exception:
            continue

    return None


async def _click_first_matching_submit(page) -> bool:
    target = await _find_first_visible_submit_target(page)
    if target is None:
        return False

    try:
        await target.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass

    for _ in range(8):
        if await _locator_is_enabled(target):
            break
        await page.wait_for_timeout(250)

    try:
        await target.click(timeout=3000)
        await page.wait_for_timeout(1800)
        return True
    except Exception:
        try:
            await target.click(timeout=3000, force=True)
            await page.wait_for_timeout(1800)
            return True
        except Exception:
            return False


async def _extract_body_text(page, timeout: int = 2500) -> str:
    try:
        return await page.locator("body").inner_text(timeout=timeout)
    except Exception:
        return ""


async def _extract_visible_login_errors(page) -> list[str]:
    errors: list[str] = []

    selectors = [
        "[role='alert']",
        "[aria-live='assertive']",
        "[aria-invalid='true']",
        ".error",
        ".errors",
        ".alert",
        ".alert-danger",
        ".alert-error",
        ".invalid-feedback",
        ".error-message",
        ".form-error",
        ".text-danger",
        ".text-red-500",
        ".notification-error",
        ".ant-form-item-explain-error",
        ".chakra-form__error-message",
    ]

    for selector in selectors:
        locator = page.locator(selector)
        try:
            count = min(await locator.count(), 6)
        except Exception:
            count = 0

        for i in range(count):
            try:
                item = locator.nth(i)
                if not await item.is_visible():
                    continue
                text = re.sub(r"\s+", " ", (await item.inner_text()).strip())
                if text and 2 <= len(text) <= 400:
                    errors.append(text)
            except Exception:
                continue

    text_patterns = [
        re.compile(r"invalid", re.IGNORECASE),
        re.compile(r"incorrect", re.IGNORECASE),
        re.compile(r"failed", re.IGNORECASE),
        re.compile(r"required", re.IGNORECASE),
        re.compile(r"unable", re.IGNORECASE),
        re.compile(r"try again", re.IGNORECASE),
        re.compile(r"not authorized", re.IGNORECASE),
        re.compile(r"wrong", re.IGNORECASE),
        re.compile(r"missing", re.IGNORECASE),
        re.compile(r"error", re.IGNORECASE),
    ]

    for pattern in text_patterns:
        try:
            candidate = page.get_by_text(pattern)
            count = min(await candidate.count(), 3)
        except Exception:
            count = 0

        for i in range(count):
            try:
                item = candidate.nth(i)
                if not await item.is_visible():
                    continue
                text = re.sub(r"\s+", " ", (await item.inner_text()).strip())
                if text and 2 <= len(text) <= 400:
                    errors.append(text)
            except Exception:
                continue

    deduped = []
    seen = set()
    for error in errors:
        key = error.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(error)

    return deduped[:8]


async def _perform_submit_attempt(page, password_field, method_name: str) -> bool:
    submit_target = await _find_first_visible_submit_target(page)

    if submit_target is not None:
        try:
            await submit_target.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass

        for _ in range(10):
            if await _locator_is_enabled(submit_target):
                break
            await page.wait_for_timeout(250)

    if method_name == "button_click":
        if submit_target is None:
            return False
        try:
            await submit_target.click(timeout=3500)
            await page.wait_for_timeout(1800)
            return True
        except Exception:
            try:
                await submit_target.click(timeout=3500, force=True)
                await page.wait_for_timeout(1800)
                return True
            except Exception:
                return False

    if method_name == "enter_key":
        if password_field is None:
            return False
        try:
            await password_field.focus()
        except Exception:
            pass
        try:
            await password_field.press("Enter")
            await page.wait_for_timeout(1800)
            return True
        except Exception:
            return False

    if method_name == "js_click":
        if submit_target is None:
            return False
        try:
            await submit_target.evaluate("(el) => el.click()")
            await page.wait_for_timeout(1800)
            return True
        except Exception:
            return False

    if method_name == "form_submit":
        js = """(el) => {
            const form = el.closest('form');
            if (!form) return false;
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit();
                return true;
            }
            form.submit();
            return true;
        }"""
        if submit_target is not None:
            try:
                did_submit = await submit_target.evaluate(js)
                if did_submit:
                    await page.wait_for_timeout(1800)
                    return True
            except Exception:
                pass
        if password_field is not None:
            try:
                did_submit = await password_field.evaluate(js)
                if did_submit:
                    await page.wait_for_timeout(1800)
                    return True
            except Exception:
                pass
        return False

    return False


async def _page_has_authenticated_shell(page) -> bool:
    shell_selectors = [
        "aside",
        "nav",
        "header",
        "main",
        "[role='navigation']",
        "[role='main']",
        "[class*='sidebar']",
        "[class*='drawer']",
        "[class*='menu']",
        "[class*='navbar']",
        "[class*='topbar']",
        "[class*='sidenav']",
        "[class*='app-shell']",
        "[class*='dashboard']",
    ]

    visible_count = 0
    for selector in shell_selectors:
        locator = page.locator(selector)
        if await _locator_is_visible(locator):
            visible_count += 1
            if visible_count >= 2:
                return True

    text_markers = [
        re.compile(r"sign\s*out", re.IGNORECASE),
        re.compile(r"log\s*out", re.IGNORECASE),
        re.compile(r"profile", re.IGNORECASE),
        re.compile(r"my\s+account", re.IGNORECASE),
        re.compile(r"dashboard", re.IGNORECASE),
        re.compile(r"patients?", re.IGNORECASE),
        re.compile(r"appointments?", re.IGNORECASE),
        re.compile(r"billing", re.IGNORECASE),
        re.compile(r"reports?", re.IGNORECASE),
        re.compile(r"settings", re.IGNORECASE),
        re.compile(r"schedule", re.IGNORECASE),
    ]

    for pattern in text_markers:
        try:
            candidate = page.get_by_text(pattern)
            if await _locator_is_visible(candidate):
                return True
        except Exception:
            continue

    return False


async def _page_still_looks_like_login(page, body_text: str = "") -> bool:
    password_field = await _find_visible_password_field(page)
    if password_field is not None:
        return True

    lowered = body_text.lower() if body_text else ""
    auth_terms = [
        "login",
        "log in",
        "sign in",
        "password",
        "remember me",
        "forgot password",
        "email address",
    ]
    auth_hits = sum(1 for term in auth_terms if term in lowered)
    if auth_hits >= 3 and not await _page_has_authenticated_shell(page):
        return True

    if _is_auth_related_url(page.url) and auth_hits >= 1:
        return True

    return False


async def _page_looks_logged_in(page, before_submit_url: str | None = None) -> bool:
    body_text = await _extract_body_text(page, timeout=2500)

    if await _page_still_looks_like_login(page, body_text=body_text):
        return False

    current_url = page.url
    current_auth = _is_auth_related_url(current_url)

    parsed = urlparse(current_url)
    app_path_markers = [
        "/dashboard",
        "/app",
        "/portal",
        "/patients",
        "/appointments",
        "/schedule",
        "/billing",
        "/reports",
        "/settings",
        "/home",
    ]

    if any(marker in parsed.path.lower() for marker in app_path_markers) and not current_auth:
        return True

    if await _page_has_authenticated_shell(page):
        return True

    lowered = body_text.lower()
    if any(
        marker in lowered
        for marker in [
            "sign out",
            "log out",
            "logout",
            "my account",
            "dashboard",
            "patients",
            "appointments",
            "schedule",
            "billing",
            "reports",
            "settings",
            "welcome",
        ]
    ):
        return True

    if before_submit_url and current_url != before_submit_url and not current_auth:
        return True

    return False


async def _save_login_debug_artifacts(page, prefix: str = "login_failure") -> list[str]:
    stamp = _now_stamp()
    png_path = AUTH_DEBUG_DIR / f"{prefix}_{stamp}.png"
    html_path = AUTH_DEBUG_DIR / f"{prefix}_{stamp}.html"
    text_path = AUTH_DEBUG_DIR / f"{prefix}_{stamp}.txt"

    saved = []

    try:
        await page.screenshot(path=str(png_path), full_page=True)
        saved.append(_debug_artifact_web_path(png_path))
    except Exception:
        pass

    try:
        html = await page.content()
        html_path.write_text(html, encoding="utf-8")
        saved.append(_debug_artifact_web_path(html_path))
    except Exception:
        pass

    try:
        body_text = await _extract_body_text(page, timeout=1500)
        text_parts = [
            f"URL: {page.url}",
            "",
            "BODY TEXT:",
            body_text or "<empty>",
        ]
        text_path.write_text("\n".join(text_parts), encoding="utf-8")
        saved.append(_debug_artifact_web_path(text_path))
    except Exception:
        pass

    return saved


async def _wait_for_login_completion(page, before_submit_url: str) -> bool:
    for _ in range(24):
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=1500)
        except Exception:
            pass

        try:
            await page.wait_for_load_state("networkidle", timeout=1500)
        except Exception:
            pass

        await page.wait_for_timeout(700)

        if await _page_looks_logged_in(page, before_submit_url=before_submit_url):
            return True

    return False


async def _open_login_page_if_needed(page, start_url: str, base_netloc: str) -> bool:
    password_field = await _find_visible_password_field(page)
    if password_field is not None:
        return True

    if await _click_first_matching_auth_entry(page):
        await _wait_for_page_hydration(page, extra_wait_ms=1800)
        password_field = await _find_visible_password_field(page)
        if password_field is not None:
            return True

    parsed = urlparse(start_url)
    base_origin = f"{parsed.scheme}://{base_netloc}"
    for path in COMMON_LOGIN_PATHS:
        candidate_url = f"{base_origin}{path}"
        try:
            await page.goto(candidate_url, wait_until="domcontentloaded", timeout=15000)
            await _wait_for_page_hydration(page, extra_wait_ms=1800)
            password_field = await _find_visible_password_field(page)
            if password_field is not None:
                return True
        except Exception:
            continue

    return False


async def _complete_login_if_requested(
    page,
    start_url: str,
    username: str,
    password: str,
    role_required: bool = False,
    role: str = "",
) -> str:
    parsed_start = urlparse(start_url)
    base_netloc = parsed_start.netloc

    await page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
    await _wait_for_page_hydration(page, extra_wait_ms=2000)

    already_logged_in = await _page_looks_logged_in(page)
    if already_logged_in and not _is_auth_related_url(page.url):
        return page.url

    found_login_page = await _open_login_page_if_needed(page, start_url, base_netloc)
    if not found_login_page:
        raise RuntimeError(
            "Could not find a login form automatically. For best results, paste the direct login page URL when credentials are required."
        )

    await _wait_for_page_hydration(page, extra_wait_ms=1500)

    if role_required and role.strip():
        role_selected = await _select_role_if_requested(page, role.strip())
        if not role_selected:
            debug_paths = await _save_login_debug_artifacts(page, prefix="role_selection_failure")
            debug_note = f" Debug artifacts: {', '.join(debug_paths)}" if debug_paths else ""
            raise RuntimeError(
                "A login page was found, but the role dropdown option could not be selected automatically." + debug_note
            )

    username_field = await _find_visible_username_field(page)
    if username_field is not None:
        try:
            await username_field.click(timeout=3000)
        except Exception:
            pass
        try:
            await username_field.fill(username, timeout=5000)
        except Exception:
            pass

    password_field = await _find_visible_password_field(page)
    if password_field is None and username_field is not None:
        await _click_first_matching_submit(page)
        await _wait_for_page_hydration(page, extra_wait_ms=1800)
        password_field = await _find_visible_password_field(page)

    if password_field is None:
        debug_paths = await _save_login_debug_artifacts(page, prefix="password_field_missing")
        debug_note = f" Debug artifacts: {', '.join(debug_paths)}" if debug_paths else ""
        raise RuntimeError(
            "A login page was found, but the password field could not be detected. This login flow may require a custom enterprise or SSO flow." + debug_note
        )

    try:
        await password_field.click(timeout=3000)
    except Exception:
        pass
    await password_field.fill(password, timeout=5000)
    await _blur_active_field(page)
    await page.wait_for_timeout(500)

    attempt_logs: list[str] = []
    observed_errors: list[str] = []
    submit_methods = [
        ("button_click", "button click"),
        ("enter_key", "Enter key"),
        ("js_click", "JavaScript click"),
        ("form_submit", "form submit"),
    ]

    any_submit_triggered = False

    for method_name, method_label in submit_methods:
        before_submit_url = page.url
        attempt_logs.append(f"Attempt: {method_label}")
        attempt_logs.append(f"URL before attempt: {before_submit_url}")

        triggered = await _perform_submit_attempt(page, password_field, method_name)
        if not triggered:
            attempt_logs.append("Result: submit method could not be triggered")
            attempt_logs.append("")
            continue

        any_submit_triggered = True
        attempt_logs.append("Result: submit method triggered")

        login_completed = await _wait_for_login_completion(page, before_submit_url=before_submit_url)
        if login_completed:
            return page.url

        current_errors = await _extract_visible_login_errors(page)
        if current_errors:
            for error in current_errors:
                if error.lower() not in {e.lower() for e in observed_errors}:
                    observed_errors.append(error)
            attempt_logs.append("Visible login errors after attempt:")
            attempt_logs.extend(current_errors)
        else:
            attempt_logs.append("Visible login errors after attempt: <none detected>")

        attempt_logs.append(f"URL after attempt: {page.url}")
        attempt_logs.append("")

        await _wait_for_page_hydration(page, extra_wait_ms=1200)
        await _blur_active_field(page)

    if not any_submit_triggered:
        debug_paths = await _save_login_debug_artifacts(
            page,
            prefix="submit_failure",
            extra_lines=attempt_logs,
        )
        debug_note = f" Debug artifacts: {', '.join(debug_paths)}" if debug_paths else ""
        raise RuntimeError(
            "The login form was found, but the submit action could not be triggered automatically." + debug_note
        )

    error_note = ""
    if observed_errors:
        error_note = " Visible login errors: " + " | ".join(observed_errors[:4])

    debug_paths = await _save_login_debug_artifacts(
        page,
        prefix="login_completion_failure",
        extra_lines=attempt_logs,
    )
    debug_note = f" Debug artifacts: {', '.join(debug_paths)}" if debug_paths else ""
    raise RuntimeError(
        "Login did not appear to complete successfully. The credentials may be incorrect, or the site may require MFA, CAPTCHA, or a custom SSO flow." + error_note + debug_note
    )


async def _run_browser_agent(
    start_url: str,
    credentials_required: bool = False,
    username: str = "",
    password: str = "",
    role_required: bool = False,
    role: str = "",
) -> list[dict]:
    normalized_start = _normalize_url(start_url)
    parsed_start = urlparse(normalized_start)
    base_netloc = parsed_start.netloc

    visited_urls: set[str] = set()
    collected_pages: list[dict] = []
    current_url = normalized_start

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        try:
            if credentials_required:
                current_url = await _complete_login_if_requested(
                    page=page,
                    start_url=normalized_start,
                    username=username,
                    password=password,
                    role_required=role_required,
                    role=role,
                )
                print(f"🔐 Login completed. Starting exploration from: {current_url}")

            for step in range(AGENT_MAX_STEPS):
                if current_url in visited_urls:
                    break

                print(f"🤖 Agent visiting [{step + 1}/{AGENT_MAX_STEPS}]: {current_url}")

                try:
                    html = await _load_rendered_html(page, current_url)
                except Exception as e:
                    if step == 0:
                        raise RuntimeError(f"Could not load starting page: {e}") from e
                    print(f"Skipping failed page: {current_url} | {e}")
                    break

                visited_urls.add(current_url)

                page_data = _extract_page_data_from_html(current_url, html)
                if page_data:
                    collected_pages.append(page_data)

                candidates = _extract_internal_link_candidates(
                    current_url,
                    html,
                    base_netloc,
                    allow_auth_paths=False,
                )
                next_url = _choose_next_link(
                    page_data or {"url": current_url, "text": ""},
                    candidates,
                    visited_urls,
                )

                if not next_url:
                    break

                current_url = next_url

        finally:
            await context.close()
            await browser.close()

    if not collected_pages:
        raise RuntimeError(
            "The browser agent could not extract enough readable content from the website."
        )

    return collected_pages


def _build_site_context(pages: list[dict]) -> str:
    chunks = []
    total_len = 0

    for i, page in enumerate(pages, start=1):
        chunk = "\n".join(
            [
                f"PAGE {i}",
                f"URL: {page['url']}",
                f"Title: {page['title'] or 'N/A'}",
                f"Meta description: {page['meta_description'] or 'N/A'}",
                f"OG title: {page['og_title'] or 'N/A'}",
                f"OG description: {page['og_description'] or 'N/A'}",
                f"Headings: {', '.join(page['headings']) if page['headings'] else 'N/A'}",
                "Visible text:",
                page["text"],
            ]
        )

        if total_len + len(chunk) > SITE_TEXT_LIMIT:
            remaining = SITE_TEXT_LIMIT - total_len
            if remaining > 300:
                chunks.append(chunk[:remaining])
            break

        chunks.append(chunk)
        total_len += len(chunk)

    return "\n\n".join(chunks)


def _summarize_site_context(site_context: str) -> str:
    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=WEBSITE_SUMMARY_INSTRUCTIONS,
        input=site_context,
    )

    summary = response.output_text.strip()
    if not summary:
        raise RuntimeError("The AI returned an empty website summary.")
    return summary


async def _analyze_website_agent(
    url: str,
    credentials_required: bool = False,
    username: str = "",
    password: str = "",
    role_required: bool = False,
    role: str = "",
) -> dict:
    normalized_url = _normalize_url(url)
    pages = await _run_browser_agent(
        normalized_url,
        credentials_required=credentials_required,
        username=username,
        password=password,
        role_required=role_required,
        role=role,
    )
    site_context = _build_site_context(pages)
    website_summary = _summarize_site_context(site_context)

    role_context_note = ""
    if role_required and role.strip():
        role_context_note = (
            f" The authenticated exploration used the {role.strip()} role, "
            f"which suggests the product or the analyzed workflow is targeted to {role.strip()} users."
        )
        if role_context_note.strip() not in website_summary:
            website_summary = f"{website_summary}{role_context_note}".strip()

    brief_lines = generate_brief_lines_from_context(website_summary)

    return {
        "normalized_url": normalized_url,
        "website_summary": website_summary,
        "brief_lines": brief_lines,
        "page_count": len(pages),
        "pages_visited": [p["url"] for p in pages],
        "role_context_note": role_context_note.strip(),
    }


@app.post("/analyze_url")
async def analyze_url(
    url: str = Form(...),
    credentials_required: bool = Form(False),
    username: str = Form(""),
    password: str = Form(""),
    role_required: bool = Form(False),
    role: str = Form(""),
):
    try:
        print(f"🔎 Agent analyzing URL: {url}")

        if credentials_required and (not username.strip() or not password):
            raise ValueError("Credentials Required is enabled, but the username or password is missing.")

        if credentials_required and role_required and not role.strip():
            raise ValueError("Role Required is enabled, but the role is missing.")

        analysis = await _analyze_website_agent(
            url,
            credentials_required=credentials_required,
            username=username.strip(),
            password=password,
            role_required=role_required,
            role=role.strip(),
        )

        return {
            "status": "success",
            "data": {
                "url": analysis["normalized_url"],
                "description": analysis["website_summary"],
                "brief_lines": analysis["brief_lines"],
                "page_count": analysis["page_count"],
                "pages_visited": analysis["pages_visited"],
            },
        }

    except Exception as e:
        print(f"❌ URL analysis failed: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/chat_outputs")
async def chat_campaign_outputs(request: Request):
    try:
        content_type = (request.headers.get("content-type") or "").lower()

        if "application/json" in content_type:
            payload = await request.json()
        else:
            form = await request.form()
            payload = dict(form)

        question = str(payload.get("question", "") or "").strip()
        if not question:
            return {"status": "error", "message": "No chatbot question was provided."}

        raw_history = payload.get("history", []) or []
        if isinstance(raw_history, str):
            try:
                raw_history = json.loads(raw_history)
            except Exception:
                raw_history = []

        history: list[dict[str, str]] = []
        if isinstance(raw_history, list):
            for item in raw_history:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role", "") or "").strip()
                content = str(item.get("content", "") or "").strip()
                if role and content:
                    history.append({"role": role, "content": content})

        source_parts = [
            str(payload.get("plan", "") or "").strip(),
            str(payload.get("playbooks", "") or "").strip(),
            str(payload.get("calendar", "") or "").strip(),
            str(payload.get("examples", "") or "").strip(),
        ]
        source_text = "\n\n".join(part for part in source_parts if part)

        if not source_text:
            return {
                "status": "error",
                "message": "No campaign outputs were provided for chatbot context.",
            }

        print("💬 Generating chatbot response from campaign outputs")
        reply = chat_about_outputs(question, source_text, history)

        if not reply.strip():
            raise RuntimeError("The chatbot returned an empty response.")

        return {
            "status": "success",
            "data": {
                "reply": reply,
            },
        }

    except Exception as e:
        print(f"❌ Chatbot failed: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/generate_ad_images")
async def generate_campaign_ad_images(
    request: Request,
    plan: str = Form(""),
    playbooks: str = Form(""),
    calendar: str = Form(""),
    examples: str = Form(""),
    raw_context: str = Form(""),
    num_images: int = Form(2),
):
    try:
        num_images = max(1, min(int(num_images), 4))

        source_text = _inject_brand_into_image_source(
            examples_text=examples.strip(),
            raw_context=raw_context.strip(),
        )

        if not source_text:
            return {
                "status": "error",
                "message": "No example posts were provided for image generation.",
            }

        brand_name = _extract_brand_name_from_context(raw_context.strip())
        if brand_name:
            print(
                f"🖼️ Generating {num_images} branded ad image(s) for {brand_name} from example posts"
            )
        else:
            print(f"🖼️ Generating {num_images} ad image(s) from example posts")

        generated_paths = generate_ad_images(source_text, num_images=num_images)

        base_url = str(request.base_url).rstrip("/")
        image_urls = [
            f"{base_url}/outputs/{path.name}"
            for path in generated_paths
        ]

        return {
            "status": "success",
            "data": {
                "images": image_urls,
                "count": len(image_urls),
            },
        }

    except Exception as e:
        print(f"❌ Ad image generation failed: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/generate")
async def generate_campaign(
    raw_context: str = Form(...),
    product_url: str = Form(""),
    generate_examples: bool = Form(True),
    use_rag: bool = Form(False),
    credentials_required: bool = Form(False),
    username: str = Form(""),
    password: str = Form(""),
    role_required: bool = Form(False),
    role: str = Form(""),
):
    try:
        print("🔄 Received generation request")

        if credentials_required and (not username.strip() or not password):
            raise ValueError("Credentials Required is enabled, but the username or password is missing.")

        if credentials_required and role_required and not role.strip():
            raise ValueError("Role Required is enabled, but the role is missing.")

        full_context = raw_context.strip()
        normalized_url = ""
        website_summary = ""
        website_error = ""
        pages_visited: list[str] = []
        role_context_note = ""

        if product_url.strip():
            try:
                analysis = await _analyze_website_agent(
                    product_url.strip(),
                    credentials_required=credentials_required,
                    username=username.strip(),
                    password=password,
                    role_required=role_required,
                    role=role.strip(),
                )
                normalized_url = analysis["normalized_url"]
                website_summary = analysis["website_summary"]
                pages_visited = analysis["pages_visited"]
                role_context_note = analysis.get("role_context_note", "")

                if website_summary and website_summary not in full_context:
                    if full_context:
                        full_context += f"\n\nWEBSITE-DERIVED DESCRIPTION:\n{website_summary}"
                    else:
                        full_context = website_summary

                print(f"✅ Agent analyzed website successfully: {normalized_url}")
                print(f"✅ Pages visited: {len(pages_visited)}")

            except Exception as website_exc:
                website_error = str(website_exc)
                print(f"⚠️ Website analysis failed during generate: {website_error}")

        if credentials_required and role_required and role.strip():
            role_context_line = (
                f"Target user / login role context: The product experience analyzed for this run used the {role.strip()} role, "
                f"so the generated product and market description should consider the product or this workflow as being targeted to {role.strip()} users."
            )
            if role_context_line not in full_context:
                if full_context:
                    full_context += f"\n\n{role_context_line}"
                else:
                    full_context = role_context_line

        brief_lines = generate_brief_lines_from_context(full_context)
        brief = formatInput(brief_lines)

        os.environ["GENERATE_EXAMPLE_POSTS"] = str(generate_examples).lower()
        os.environ["USE_RAG"] = str(use_rag).lower()

        def status_cb(msg: str):
            print(f"[Agent] {msg}")

        gpt(brief, status_cb=status_cb)

        outputs_dir = BASE_DIR / "outputs"
        index_files = sorted(
            outputs_dir.glob("00_index_*.md"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        if not index_files:
            return {"status": "error", "message": "No output generated"}

        stamp = index_files[0].stem.replace("00_index_", "")

        plan_path = outputs_dir / f"01_detailed_marketing_plan_{stamp}.md"
        playbooks_path = outputs_dir / f"02_platform_playbooks_{stamp}.md"
        calendar_path = outputs_dir / f"03_week_by_week_calendar_{stamp}.md"
        examples_path = outputs_dir / f"04_example_posts_{stamp}.md"

        assessment_parts = ["# 0) Honest Strategic Assessment", ""]

        if normalized_url:
            assessment_parts.extend([
                "## Website URL Used",
                normalized_url,
                "",
            ])

        if credentials_required:
            assessment_parts.extend([
                "## Authentication Mode",
                "Authenticated website exploration was requested for this run.",
                "",
            ])

        if credentials_required and role_required and role.strip():
            assessment_parts.extend([
                "## Role Used During Login",
                role.strip(),
                "",
            ])

        if pages_visited:
            assessment_parts.extend([
                "## Pages Visited By Browser Agent",
                *pages_visited,
                "",
            ])

        if website_summary:
            assessment_parts.extend([
                "## Website-Derived Description",
                website_summary,
                "",
                "## Suggested 13 Brief Values",
            ])
            for i, line in enumerate(brief_lines, start=1):
                assessment_parts.append(f"{i}) {line}")
            assessment_parts.append("")

        if website_error:
            assessment_parts.extend([
                "## Website Analysis Note",
                f"Website could not be analyzed automatically: {website_error}",
                "",
            ])

        if not website_summary and not website_error and not normalized_url:
            assessment_parts.extend([
                "No website URL was used. Campaign was generated from the manually entered description only.",
                "",
            ])

        assessment_md = "\n".join(assessment_parts).strip()
        assessment_path = outputs_dir / f"05_URL_assessment_{stamp}.md"
        assessment_path.write_text(assessment_md, encoding="utf-8")

        output_files = {
            "plan": {
                "filename": plan_path.name,
                "download_url": f"/download_output/{plan_path.name}",
            },
            "playbooks": {
                "filename": playbooks_path.name,
                "download_url": f"/download_output/{playbooks_path.name}",
            },
            "calendar": {
                "filename": calendar_path.name,
                "download_url": f"/download_output/{calendar_path.name}",
            },
            "assessment": {
                "filename": assessment_path.name,
                "download_url": f"/download_output/{assessment_path.name}",
            },
        }
        if examples_path.exists():
            output_files["examples"] = {
                "filename": examples_path.name,
                "download_url": f"/download_output/{examples_path.name}",
            }

        return {
            "status": "success",
            "data": {
                "assessment": assessment_md,
                "plan": plan_path.read_text(encoding="utf-8") if plan_path.exists() else "# 1) Detailed Marketing Plan\n\nNot found",
                "playbooks": playbooks_path.read_text(encoding="utf-8") if playbooks_path.exists() else "# 2) Platform-Specific Playbooks\n\nNot found",
                "calendar": calendar_path.read_text(encoding="utf-8") if calendar_path.exists() else "# 3) Week-by-Week Content Calendar\n\nNot found",
                "examples": examples_path.read_text(encoding="utf-8") if examples_path.exists() else "# 4) Example Posts\n\nNot found",
                "output_files": output_files,
            }
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/upload_kb")
async def upload_kb(files: list[UploadFile] = File(...)):
    saved = []
    for file in files:
        try:
            file_path = KB_DIR / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved.append(file.filename)
            print(f"✅ Saved KB file: {file.filename}")
        except Exception as e:
            print(f"Failed to save {file.filename}: {e}")
    return {"status": "success", "saved": saved, "count": len(saved)}


@app.post("/upload_media")
async def upload_media(files: list[UploadFile] = File(...)):
    saved = []
    for file in files:
        try:
            file_path = UPLOADS_DIR / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved.append(file.filename)
            print(f"✅ Saved media file: {file.filename}")
        except Exception as e:
            print(f"Failed to save {file.filename}: {e}")
    return {"status": "success", "saved": saved, "count": len(saved)}


if __name__ == "__main__":
    print("🚀 Campaign Coach Backend starting at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
