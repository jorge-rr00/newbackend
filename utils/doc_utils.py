"""Document utility functions for managing hidden document text."""
import os
import re
import tempfile
from typing import List

from skimage.filters import threshold_sauvola
from skimage.util import img_as_ubyte
from skimage import io
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

try:
    from PIL import Image
except ImportError:
    Image = None

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

    with open(path, "rb") as f:
        image_bytes = f.read()

    client = ImageAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    result = client.analyze(image_data=image_bytes, visual_features=[VisualFeatures.READ])

    lines = []
    if result.read and result.read.blocks:
        for block in result.read.blocks:
            for line in block.lines:
                txt = line.text
                if txt:
                    lines.append(txt)
    return "\n".join(lines)


def ocr_image(path: str) -> str:
    # Prefer Sauvola + Azure Read for images when possible
    sk_img = io.imread(path, as_gray=True)
    sk_binary = img_as_ubyte(sk_img > threshold_sauvola(sk_img))
    if Image:
        image = Image.fromarray(sk_binary)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
            image.save(tmp, format="PNG")
            tmp.flush()
            text = _ocr_image_with_azure(tmp.name)
            if text.strip():
                return text

    return _ocr_image_with_azure(path)