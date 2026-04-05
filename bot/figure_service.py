"""
figure_service.py — Single-stage pipeline for the AutoFigure Telegram bot.

Stage 1 (Image LLM — Gemini):  paper text (+ optional reference image)  →  PNG bytes
"""

from __future__ import annotations

import asyncio
import io
import os

from google import genai
from google.genai import types
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_IMAGE_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-pro-image-preview")


_DIRECT_PROMPT = (
    "You must follow the CO-STAR framework to generate a premium visualization.\n\n"
    "# [C] Context\n"
    "You are a world-class technical information designer working for top-tier academic journals (e.g., Nature, Science) and cutting-edge tech companies.\n\n"
    "# [O] Objective\n"
    "Translate the complex architecture described in the text below into a highly intuitive, visually stunning, and logically structured diagram.\n\n"
    "# [S] Style\n"
    "* Layout: Spacious, logically layered (e.g., strictly aligned top-to-bottom or Isometric 3D projection). Ensure extremely generous whitespace.\n"
    "* Aesthetics: Employ modern high-end design languages such as 'Glassmorphism' (frosted glass), subtle glowing accents, or ultra-crisp minimalist vector art.\n"
    "* Colors: Use a luxurious, cohesive color palette (e.g., sleek dark mode with neon routing lines, or pure white with subtle elegant gradients).\n"
    "* Elements: Incorporate elegant, intuitive ICONS for each main component to make it highly engaging.\n\n"
    "# [T] Tone\n"
    "Cutting-edge, luxurious, authoritative, and scientifically rigorous.\n\n"
    "# [A] Audience\n"
    "Expert researchers who expect state-of-the-art UI/UX data visualization.\n\n"
    "# [R] Response & CRITICAL TEXT RULES (ANTI-HALLUCINATION)\n"
    "* EXTREME COMPRESSION: You MUST aggressively summarize the text. NEVER write full sentences or long phrases.\n"
    "* MAXIMUM 1 TO 2 WORDS: Only use ultra-short labels or standard acronyms (e.g., use 'NLU' instead of 'Natural Language Understanding', use 'LLM').\n"
    "* SPELLING: Strictly double-check the spelling of these short keywords. Do not invent words.\n"
    "* EXCLUSION: Do NOT include any figure number, caption, or title inside the canvas.\n\n"
    "Input Paper Text:\n"
    "\"\"\"\n{paper_text}\n\"\"\"\n"
)

_REFERENCE_PROMPT = (
    "Generate a figure that visualizes the method described below.\n\n"
    "Method:\n\"\"\"\n{paper_text}\n\"\"\"\n\n"
    "Style & Layout constraints:\n"
    "- Do not include any figure number, caption, or title inside the image.\n"
    "- CRITICAL TEXT: Strictly check spelling to match the provided content; DO NOT introduce any spelling errors. If the provided text content is too long, you MUST extract only the core keywords/phrases to generate the image.\n"
    "- CRITICAL SPACE: Without deleting core keywords, if the content is extensive, appropriately widen the canvas aspect ratio to ensure ALL content is displayed in a SINGLE horizontal line. The image MUST NOT be overcrowded; provide appropriate generous whitespace and breathing room around and inside the blocks.\n"
    "- CRITICAL STYLE: Extract the core style/colors from the reference image, but elevate it to a PREMIUM, GORGEOUS, and HIGH-END academic infographic style (e.g., Nature/Science journal quality). You MUST incorporate elegant, minimalist, and context-relevant ICONS for each core block to make it highly engaging and intuitive. Use refined aesthetics (e.g., high-quality vector finish, subtle elegant shading) while strictly maintaining a UNIFIED and COHESIVE visual style. Use a consistent color palette (e.g., monochromatic or strict two-tone) for blocks of the same logical level. DO NOT use random, chaotic, or 'rainbow' colors. Ensure pure white background and straight orthogonal lines."
)


# ── Image generation ──────────────────────────────────────────────────────────

def _extract_image_bytes(response) -> bytes:
    for cand in (getattr(response, "candidates", None) or []):
        for part in (getattr(getattr(cand, "content", None), "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                img = Image.open(io.BytesIO(inline.data))
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
    raise RuntimeError("Gemini image response contained no image data")


def _get_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def _call_image_gemini(contents: list, api_key: str) -> bytes:
    client = _get_client(api_key)
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
        image_config=types.ImageConfig(image_size="4K"),
    )
    response = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=contents,
        config=config,
    )
    return _extract_image_bytes(response)


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_from_text(paper_text: str, gemini_api_key: str) -> bytes:
    """
    paper_text → [Gemini image] → PNG bytes
    """
    prompt = _DIRECT_PROMPT.format(paper_text=paper_text)
    loop = asyncio.get_event_loop()
    png_bytes = await loop.run_in_executor(None, _call_image_gemini, [prompt], gemini_api_key)
    return png_bytes


async def generate_with_reference(
    paper_text: str,
    ref_img_bytes: bytes,
    gemini_api_key: str,
) -> bytes:
    """
    paper_text + reference image → [Gemini image] → PNG bytes
    """
    prompt = _REFERENCE_PROMPT.format(paper_text=paper_text)
    ref_img = Image.open(io.BytesIO(ref_img_bytes)).convert("RGB")
    loop = asyncio.get_event_loop()
    png_bytes = await loop.run_in_executor(
        None, _call_image_gemini, [ref_img, prompt], gemini_api_key
    )
    return png_bytes
