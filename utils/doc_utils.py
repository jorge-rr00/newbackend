"""Document utility functions for managing hidden document text."""
import os
import re
import time
from typing import List

import requests

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

HIST_TAG_START = "<!--HISTORICAL_DOC_TEXT-->"
HIST_TAG_END = "<!--END_HISTORICAL_DOC_TEXT-->"
MAX_DOC_CHARS = 20000  # to keep requests efficient & cheap (Azure + tokens)


def strip_hidden_doc_tags(text: str) -> str:
    """Strip hidden document tags from text."""
    if not text:
        return ""
    return re.sub(
        re.escape(HIST_TAG_START) + r".*?" + re.escape(HIST_TAG_END),
        "",
        text,
        flags=re.DOTALL,
    ).strip()


def extract_hidden_doc_text(text: str) -> str:
    """Extract hidden document text from tags."""
    if not text:
        return ""
    m = re.search(
        re.escape(HIST_TAG_START) + r"(.*?)" + re.escape(HIST_TAG_END),
        text,
        flags=re.DOTALL,
    )
    return (m.group(1) if m else "").strip()


def truncate_doc(text: str, max_chars: int = MAX_DOC_CHARS) -> str:
    """Truncate document text to max_chars."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    # keep the tail (often contains signatures/parties)
    return text[-max_chars:]


def get_last_user_text(messages: list) -> str:
    """Get last user message from message list."""
    from langchain_core.messages import HumanMessage
    
    # Robust: find last HumanMessage (avoid list index errors)
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            return m.content or ""
    return ""


def _ocr_image_with_azure(path: str) -> str:
    endpoint = (os.getenv("AZURE_VISION_ENDPOINT") or "").strip()
    key = (os.getenv("AZURE_VISION_KEY") or "").strip()
    if not endpoint or not key:
        return ""

    url = endpoint.rstrip("/") + "/vision/v3.2/read/analyze?language=es"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/octet-stream",
    }

    with open(path, "rb") as f:
        resp = requests.post(url, headers=headers, data=f, timeout=20)
    if resp.status_code not in (200, 202):
        return ""

    op_url = resp.headers.get("Operation-Location")
    if not op_url:
        return ""

    for _ in range(10):
        time.sleep(0.7)
        poll = requests.get(op_url, headers={"Ocp-Apim-Subscription-Key": key}, timeout=20)
        data = poll.json()
        status = (data.get("status") or "").lower()
        if status == "succeeded":
            lines = []
            for page in data.get("analyzeResult", {}).get("readResults", []):
                for line in page.get("lines", []):
                    txt = line.get("text", "")
                    if txt:
                        lines.append(txt)
            return "\n".join(lines)
        if status == "failed":
            break

    return ""


def ocr_image(path: str) -> str:
    if pytesseract and Image:
        try:
            text = pytesseract.image_to_string(Image.open(path))
            if text.strip():
                return text
        except Exception:
            pass

    return _ocr_image_with_azure(path)
