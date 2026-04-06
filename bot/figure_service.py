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
    "Do not include any figure number, caption, or title inside the image.\n"
    "- CRITICAL: Strictly proofread all generated text labels. Do not invent spellings. Only use the exact terminology provided in the text (e.g., 'TensorFlow', 'Infrastructure').\n"
    "- Ensure generous whitespace and padding between all blocks and text. The layout must feel spacious and uncluttered.\n"
    "- You may slightly condense or abbreviate the text labels if necessary to maintain a clean visual balance, but keep the core terminology.\n"
    "- CRITICAL VISUALS: Include meaningful icons, diagrams, arrows, and visual elements to illustrate each component. Do not rely on text boxes alone — each key concept should have a relevant icon or graphic symbol to make the figure visually rich and intuitive."
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
