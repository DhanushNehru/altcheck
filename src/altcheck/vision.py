"""Draft alt text with a local open-weight vision model (default: SmolVLM-500M-Instruct, Apache 2.0)."""
from __future__ import annotations

import io
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

DEFAULT_MODEL = "HuggingFaceTB/SmolVLM-500M-Instruct"
BLOCKED_MODEL_HINTS = ("qwen2.5-vl-3b", "qwen2_5_vl_3b")  # non-commercial license


@dataclass
class Draft:
    alt: str = ""
    decorative: bool = False
    confidence: str = "low"
    error: str = ""
    thumb_data_uri: str = ""
    raw_output: str = ""


def download(src: str, base_url: str, folder: Path, timeout: int = 20) -> Path:
    url = urljoin(base_url, src)
    if url.startswith("data:"):
        import base64
        head, _, data = url.partition(",")
        path = folder / "inline.img"
        path.write_bytes(base64.b64decode(data) if ";base64" in head else data.encode())
        return path
    req = urllib.request.Request(url, headers={"User-Agent": "altcheck/0.1 (+local alt-text helper)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(15_000_000)
    path = folder / f"img_{abs(hash(url))}.img"
    path.write_bytes(data)
    return path


def make_thumb(img, size: int = 160) -> str:
    import base64
    t = img.copy()
    t.thumbnail((size, size))
    buf = io.BytesIO()
    t.convert("RGB").save(buf, "JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build_prompt(c) -> str:
    """Short, visual prompt. Testing showed this small model copies long page text or invents content
    when the prompt carries link or paragraph context, so only the nearest heading goes in."""
    if c.heading:
        return f'This image appears under the heading "{c.heading[:80]}". In one short sentence, describe what the image shows.'
    return "Describe this image in one short sentence."


def add_link_note(alt: str, c) -> str:
    """For linked images, add the destination in code so it is never guessed by the model."""
    if not c.link_href or not alt:
        return alt
    from urllib.parse import urlparse
    dest = c.link_text or urlparse(c.link_href).path.strip("/") or urlparse(c.link_href).netloc
    note = f" (link to {dest[:40]})"
    return alt if len(alt) + len(note) > 125 else alt.rstrip(".") + note


DECORATIVE_PROMPT = "Is this image purely decorative, with no information a reader would miss? Answer yes or no."


def _looks_parroted(alt: str) -> bool:
    low = alt.lower()
    return any(p in low for p in ("alt text", "one short sentence", "describe what the image", "<"))


def parse_output(text: str) -> Draft:
    d = Draft(raw_output=text)
    first = re.split(r"(?<=[.!?])\s+", text.strip())[0] if text.strip() else ""
    alt = re.sub(r"^(ALT|Alt text)\s*:\s*", "", first).strip().strip('"')
    m = re.match(r"^(the|this) (image|picture|photo) (shows|depicts|features|is)\s+", alt, re.I)
    if m:
        alt = alt[m.end():]
        alt = alt[:1].upper() + alt[1:]
    if len(alt) > 125:
        alt = alt[:122].rsplit(" ", 1)[0] + "..."
    d.alt = alt
    if not alt:
        d.error = "model returned no usable text"
    elif _looks_parroted(alt):
        d.error = "model repeated the instructions instead of describing the image"
        d.alt = ""
    # Confidence is a heuristic, not a measurement: short or generic answers are marked low.
    d.confidence = "high" if d.alt and len(d.alt.split()) >= 4 else "low"
    return d


class VisionDrafter:
    def __init__(self, model_id: str = DEFAULT_MODEL, device: str | None = None, dtype: str | None = None):
        if any(h in model_id.lower() for h in BLOCKED_MODEL_HINTS):
            raise SystemExit("That model has a non-commercial license. Pick an open-licensed model (default: %s)." % DEFAULT_MODEL)
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        if dtype:
            td = getattr(torch, dtype)
        elif self.device == "cuda":
            td = torch.float16
        else:
            td = torch.float32 if _free_ram_gb() >= 4 else torch.bfloat16
        self.dtype = td
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForImageTextToText.from_pretrained(model_id, dtype=td).to(self.device)
        self.model.eval()
        self.model_id = model_id

    def describe(self) -> str:
        return f"{self.model_id} on {self.device} ({str(self.dtype).replace('torch.', '')})"

    def _ask(self, img, prompt: str, max_new: int) -> str:
        msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
        chat = self.processor.apply_chat_template(msgs, add_generation_prompt=True)
        inputs = self.processor(text=chat, images=[img], return_tensors="pt", do_image_splitting=False).to(self.device)
        with self.torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=max_new, do_sample=False)
        return self.processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]

    def draft(self, c, base_url: str, folder: Path) -> Draft:
        from PIL import Image
        try:
            path = download(c.src, base_url, folder)
            img = Image.open(path)
            img.load()
        except Exception as e:  # network, svg, corrupt file
            return Draft(error=f"could not load image ({type(e).__name__}: {e})")
        d = Draft()
        try:
            thumb = make_thumb(img)
            img = img.convert("RGB")
            text = self._ask(img, build_prompt(c), 40)
            d = parse_output(text)
            d.alt = add_link_note(d.alt, c)
            d.thumb_data_uri = thumb
            if d.alt:
                ans = self._ask(img, DECORATIVE_PROMPT, 4)
                d.decorative = ans.strip().lower().startswith("yes")
        except Exception as e:
            d.error = f"model failed ({type(e).__name__}: {e})"
        return d


def _free_ram_gb() -> float:
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) / 1048576
    except OSError:
        pass
    return 8.0
