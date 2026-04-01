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
    "Generate a professional academic journal style figure for the paper below, "
    "visualizing the method it proposes.\n\n"
    "{paper_text}\n\n"
    "The figure should be clean, engaging, and use academic journal style with clear diagrams. "
    "Do not include any figure number, caption, or title inside the image."
)

_REFERENCE_PROMPT = (
    "Generate a figure that visualizes the method described below.\n\n"
    "Closely follow the visual style of the provided reference (line style, color palette, "
    "shading, icon style, arrow aesthetics). Layout and structure may differ freely.\n\n"
    "Method:\n\"\"\"\n{paper_text}\n\"\"\"\n\n"
    "Do not include any figure number, caption, or title inside the image."
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
