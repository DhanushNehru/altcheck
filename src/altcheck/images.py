"""Pick which images need attention and attach context."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

GENERIC = {
    "image", "img", "photo", "picture", "pic", "banner", "graphic", "icon",
    "logo", "thumbnail", "thumb", "untitled", "placeholder", "spacer", "image.png",
}
FILENAME_RE = re.compile(r"^[\w\-. ()]*\.(jpe?g|png|gif|webp|svg|avif|bmp)$", re.I)
CAMERA_RE = re.compile(r"^(img|dsc|dscn|pxl|image|photo|screenshot)[-_ ]?\d+", re.I)
TRACKER_HINTS = ("pixel", "track", "beacon", "analytics", "1x1", "spacer")


@dataclass
class Candidate:
    selector: str
    src: str
    current_alt: str | None  # None = attribute missing, "" = present but empty
    issue: str  # missing | empty | weak
    heading: str = ""
    surrounding: str = ""
    link_href: str = ""
    link_text: str = ""
    role_guess: str = "content"
    width: int = 0
    height: int = 0
    html: str = ""
    extra: dict = field(default_factory=dict)


def weak_reason(alt: str) -> str | None:
    a = alt.strip()
    if a.lower() in GENERIC:
        return "generic word"
    if FILENAME_RE.match(a) or CAMERA_RE.match(a):
        return "looks like a filename"
    return None


def guess_role(d: dict) -> str:
    cls = (d.get("cls") or "") + " " + (d.get("src") or "")
    if re.search(r"logo", cls, re.I):
        return "logo"
    if d.get("in_header") and d["width"] < 250 and d["height"] < 120:
        return "logo"
    if re.search(r"product|item|sku|shop", cls, re.I):
        return "product"
    if re.search(r"deco|divider|bg|background|pattern|shape", cls, re.I):
        return "decorative guess"
    return "content"


def select_candidates(raw: list[dict], max_images: int = 5, min_size: int = 50) -> tuple[list[Candidate], list[str]]:
    """Return (candidates, skip notes). Respects missing vs empty alt."""
    cands: list[Candidate] = []
    notes: list[str] = []
    seen: set[str] = set()
    for d in raw:
        src = d.get("src") or ""
        if not src or src.startswith("data:image/gif;base64,R0lGOD"):
            continue
        if d["width"] < min_size or d["height"] < min_size:
            continue
        low = src.lower()
        if any(h in low for h in TRACKER_HINTS) and max(d["natural_w"], d["natural_h"]) <= 3:
            continue
        if d.get("role") in ("presentation", "none") or d.get("aria_hidden") == "true":
            # Author explicitly marked as decorative; respect it.
            continue
        if src in seen:
            continue
        alt = d.get("alt") if d.get("has_alt_attr") else None
        if alt is None:
            issue = "missing"
        elif alt.strip() == "":
            # Empty alt is valid for decorative images. Only flag it when the image
            # looks like content: linked, inside a figure caption, or large.
            role = guess_role(d)
            if role == "decorative guess" or (not d["link_href"] and not d["figcaption"] and d["width"] * d["height"] < 40000):
                continue
            issue = "empty"
        else:
            if not weak_reason(alt):
                continue
            issue = "weak"
        seen.add(src)
        cands.append(Candidate(
            selector=d["selector"], src=src, current_alt=alt, issue=issue,
            heading=d["heading"], surrounding=d["surrounding"] or d["figcaption"],
            link_href=d["link_href"], link_text=d["link_text"],
            role_guess=guess_role(d), width=d["width"], height=d["height"], html=d["outer"],
            extra={"weak_reason": weak_reason(alt) if alt else None},
        ))
    total = len(cands)
    if total > max_images:
        notes.append(f"{total} images need attention; processed the first {max_images}. Use --max-images to change.")
        cands = cands[:max_images]
    return cands, notes
