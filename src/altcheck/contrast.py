"""Turn axe-core color-contrast results into reviewable findings with a suggested foreground color."""
from __future__ import annotations

import colorsys
from dataclasses import dataclass


def parse_hex(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def to_hex(rgb) -> str:
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb)


def luminance(rgb) -> float:
    def f(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def suggest_foreground(fg_hex: str, bg_hex: str, required: float) -> str | None:
    """Nearest color to fg (same hue/saturation, lightness adjusted) that meets the ratio on bg."""
    fg, bg = parse_hex(fg_hex), parse_hex(bg_hex)
    h, l, s = colorsys.rgb_to_hls(*fg)
    best = None
    for direction in (1, -1):
        step = 0
        while True:
            nl = l + direction * step / 1000
            if nl < 0 or nl > 1:
                break
            cand = colorsys.hls_to_rgb(h, nl, s)
            if ratio(cand, bg) >= required:
                best = (step, cand) if best is None or step < best[0] else best
                break
            step += 1
    return to_hex(best[1]) if best else None


@dataclass
class ContrastFinding:
    selector: str
    html: str
    text: str
    fg: str
    bg: str
    ratio: float
    required: float
    suggested_fg: str | None
    manual_review: str  # non-empty = could not suggest safely
    message: str


def findings_from_axe(result: dict, limit: int = 25) -> list[ContrastFinding]:
    out: list[ContrastFinding] = []
    for v in result.get("violations", []):
        for node in v.get("nodes", []):
            data = {}
            for part in node.get("any", []) + node.get("all", []):
                if part.get("id") == "color-contrast":
                    data = part.get("data") or {}
            fg, bg = data.get("fgColor"), data.get("bgColor")
            req = data.get("expectedContrastRatio")
            req_f = float(str(req).split(":")[0]) if req else 4.5
            cur = data.get("contrastRatio") or 0
            reason = ""
            sugg = None
            if not (fg and bg and fg.startswith("#") and bg.startswith("#")):
                reason = "Colors could not be read (gradient, image or overlay behind the text). Check by hand."
            else:
                sugg = suggest_foreground(fg[:7], bg[:7], req_f)
                if not sugg:
                    reason = "No foreground shade of this hue passes on this background. Change the background or pick another color."
                if data.get("messageKey") or (data.get("bgOverlap") is not None):
                    reason = reason or "Text overlaps another element or image. Verify the suggestion visually."
            out.append(ContrastFinding(
                selector=" ".join(node.get("target", [""])[0:1]) if node.get("target") else "",
                html=node.get("html", "")[:300],
                text=(node.get("html", "").split(">", 1)[-1].split("<", 1)[0] or "").strip()[:120],
                fg=fg or "?", bg=bg or "?", ratio=float(cur), required=req_f,
                suggested_fg=sugg, manual_review=reason,
                message=node.get("failureSummary", "").splitlines()[-1] if node.get("failureSummary") else "",
            ))
            if len(out) >= limit:
                return out
    return out
