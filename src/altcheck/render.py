"""Render a page with headless Chromium and collect raw data from the DOM."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

AXE_VERSION = "4.14.0"
AXE_URL = f"https://cdn.jsdelivr.net/npm/axe-core@{AXE_VERSION}/axe.min.js"
AXE_PATH = Path.home() / ".cache" / "altcheck" / f"axe-core-{AXE_VERSION}.min.js"


def ensure_axe() -> str:
    """Return axe-core source. It is downloaded once (MPL-2.0, from npm via jsDelivr) and cached."""
    if not AXE_PATH.exists():
        import urllib.request
        AXE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(AXE_URL, timeout=30) as r:
            AXE_PATH.write_bytes(r.read())
    return AXE_PATH.read_text(encoding="utf-8")

COLLECT_JS = r"""
() => {
  const out = [];
  const clip = (s, n) => (s || "").replace(/\s+/g, " ").trim().slice(0, n);
  const cssPath = (el) => {
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 6) {
      let p = el.tagName.toLowerCase();
      if (el.id) { parts.unshift(p + "#" + CSS.escape(el.id)); break; }
      const sib = el.parentElement ? Array.from(el.parentElement.children).filter(c => c.tagName === el.tagName) : [];
      if (sib.length > 1) p += ":nth-of-type(" + (sib.indexOf(el) + 1) + ")";
      parts.unshift(p);
      el = el.parentElement;
    }
    return parts.join(" > ");
  };
  document.querySelectorAll("img").forEach((img) => {
    const r = img.getBoundingClientRect();
    const a = img.closest("a");
    let h = null, n = img;
    while (n && n !== document.body) {
      let s = n.previousElementSibling;
      while (s) {
        if (/^H[1-6]$/.test(s.tagName)) { h = s; break; }
        const inner = s.querySelector && s.querySelectorAll("h1,h2,h3,h4,h5,h6");
        if (inner && inner.length) { h = inner[inner.length - 1]; break; }
        s = s.previousElementSibling;
      }
      if (h) break;
      n = n.parentElement;
    }
    const block = img.closest("figure, p, li, div, section, article") || img.parentElement;
    const figcap = img.closest("figure") ? img.closest("figure").querySelector("figcaption") : null;
    out.push({
      selector: cssPath(img),
      src: img.currentSrc || img.src || "",
      has_alt_attr: img.hasAttribute("alt"),
      alt: img.getAttribute("alt"),
      role: img.getAttribute("role"),
      aria_hidden: img.getAttribute("aria-hidden"),
      cls: (img.className && img.className.toString ? img.className.toString() : ""),
      width: Math.round(r.width), height: Math.round(r.height),
      natural_w: img.naturalWidth, natural_h: img.naturalHeight,
      in_header: !!img.closest("header, nav"),
      in_footer: !!img.closest("footer"),
      heading: h ? clip(h.textContent, 120) : "",
      surrounding: clip(block ? block.innerText : "", 200),
      figcaption: figcap ? clip(figcap.textContent, 160) : "",
      link_href: a ? a.href : "",
      link_text: a ? clip(a.innerText || a.getAttribute("aria-label") || a.title, 120) : "",
      outer: img.outerHTML.slice(0, 400),
    });
  });
  return out;
}
"""


def render(url: str, screenshot_path: Path | None = None, timeout_ms: int = 45000):
    """Return (images, contrast_violations, title). Raises on navigation failure."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            if screenshot_path:
                page.screenshot(path=str(screenshot_path), full_page=True)
            images = page.evaluate(COLLECT_JS)
            page.add_script_tag(content=ensure_axe())
            result = page.evaluate(
                "async () => await axe.run(document, {runOnly: {type: 'rule', values: ['color-contrast']}})"
            )
            title = page.title()
            final_url = page.url
        finally:
            browser.close()
    return images, result, title, final_url
