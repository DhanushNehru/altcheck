"""Build a single self-contained report.html (inline CSS and JS, no external assets)."""
from __future__ import annotations

import html
from datetime import datetime

BANNER = "AI-drafted suggestions. Review before using. This tool does not check full accessibility."

CSS = """
:root{--bg:#fff;--fg:#1b1f24;--muted:#5b6470;--card:#f5f6f8;--line:#d9dde3;--warn:#fff4d6;--warnfg:#5c4300;--accent:#0b5fff}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--fg:#e8eaee;--muted:#a0a8b4;--card:#1d2128;--line:#343a44;--warn:#3a2f10;--warnfg:#ffe29a;--accent:#7aa7ff}}
body{font:16px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:24px;max-width:1000px;margin-inline:auto}
h1{font-size:1.5rem;margin:0 0 4px}h2{margin-top:2rem}
.banner{background:var(--warn);color:var(--warnfg);padding:12px 16px;border-radius:8px;font-weight:600;margin:16px 0}
.meta{color:var(--muted)}.summary{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
.pill{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px 14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:14px 0;display:flex;gap:16px;flex-wrap:wrap}
.card img.thumb{max-width:160px;max-height:160px;border-radius:6px;border:1px solid var(--line);background:#8883}
.body{flex:1;min-width:260px}dl{margin:0;display:grid;grid-template-columns:max-content 1fr;gap:4px 12px}dt{color:var(--muted)}dd{margin:0;word-break:break-word}
pre{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px;overflow:auto;white-space:pre-wrap;margin:8px 0}
button{background:var(--accent);color:#fff;border:0;border-radius:6px;padding:6px 12px;cursor:pointer;font:inherit}
.tag{display:inline-block;padding:0 8px;border-radius:4px;border:1px solid var(--line)}
.sw{display:inline-block;width:1.1em;height:1.1em;border:1px solid var(--line);vertical-align:-.2em;border-radius:3px;margin-right:4px}
.err{color:#c0392b}
"""

JS = """
document.querySelectorAll('button[data-copy]').forEach(function(b){b.addEventListener('click',function(){
var t=document.getElementById(b.dataset.copy).textContent;
(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).catch(function(){
var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove();});
var o=b.textContent;b.textContent='Copied';setTimeout(function(){b.textContent=o},1200);});});
"""

e = html.escape


def alt_snippet(c, d) -> str:
    """Suggested replacement tag. Escaped when rendered; this returns raw HTML text."""
    alt = "" if d.decorative else d.alt
    src = html.escape(c.src, quote=True)
    return f'<img src="{src}" alt="{html.escape(alt, quote=True)}">'


def css_snippet(f) -> str:
    sel = f.selector or "/* element */"
    return f"{sel} {{\n  color: {f.suggested_fg};\n}}"


def build(url: str, title: str, images, contrast, notes: list[str], model_desc: str) -> str:
    # images: list of (Candidate, Draft)
    n_dec = sum(1 for _, d in images if d.decorative)
    n_fail = sum(1 for _, d in images if d.error)
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>altcheck report - {e(url)}</title><style>{CSS}</style></head><body>",
        f"<h1>altcheck report</h1><div class='meta'>{e(url)}"
        + (f" - {e(title)}" if title else "")
        + f"<br>{datetime.now().strftime('%Y-%m-%d %H:%M')} - model: {e(model_desc)}</div>",
        f"<div class='banner' role='note'>{e(BANNER)}</div>",
        "<div class='summary'>"
        f"<span class='pill'>{len(images)} image(s) reviewed</span>"
        f"<span class='pill'>{n_dec} flagged decorative</span>"
        f"<span class='pill'>{n_fail} could not be drafted</span>"
        f"<span class='pill'>{len(contrast)} contrast failure(s)</span></div>",
    ]
    for n in notes:
        parts.append(f"<p class='meta'>{e(n)}</p>")
    parts.append("<h2>Images</h2>")
    if not images:
        parts.append("<p>No images with missing, empty-but-meaningful or weak alt text were found (among the images checked).</p>")
    for i, (c, d) in enumerate(images):
        parts.append("<div class='card'>")
        if d.thumb_data_uri:
            parts.append(f"<img class='thumb' src='{d.thumb_data_uri}' alt='Thumbnail of the image being reviewed'>")
        cur = "(no alt attribute)" if c.current_alt is None else ('(empty alt="")' if c.current_alt == "" else c.current_alt)
        issue = c.issue + (f" - {c.extra['weak_reason']}" if c.extra.get("weak_reason") else "")
        parts.append("<div class='body'><dl>")
        parts.append(f"<dt>Selector</dt><dd><code>{e(c.selector)}</code></dd>")
        parts.append(f"<dt>Source</dt><dd>{e(c.src)}</dd>")
        parts.append(f"<dt>Issue</dt><dd><span class='tag'>{e(issue)}</span></dd>")
        parts.append(f"<dt>Current alt</dt><dd>{e(cur)}</dd>")
        if c.link_href:
            parts.append(f"<dt>Inside link</dt><dd>{e(c.link_href)} ({e(c.link_text or 'no link text')})</dd>")
        if d.error:
            parts.append(f"<dt>Draft</dt><dd class='err'>{e(d.error)}. Write this one by hand.</dd></dl>")
        else:
            parts.append(f"<dt>Drafted alt</dt><dd><strong>{e(d.alt)}</strong></dd>")
            parts.append(f"<dt>Decorative?</dt><dd>{'Yes, the model thinks this is decorative. Consider alt=&quot;&quot; after checking.' if d.decorative else 'No'}</dd>")
            parts.append(f"<dt>Confidence</dt><dd>{e(d.confidence)} (a rough heuristic: short or vague drafts are marked low)</dd></dl>")
            snip = alt_snippet(c, d)
            parts.append(f"<pre id='s{i}'>{e(snip)}</pre><button type='button' data-copy='s{i}'>Copy</button>")
        parts.append("</div></div>")
    parts.append("<h2>Contrast (axe-core color-contrast rule only)</h2>")
    if not contrast:
        parts.append("<p>axe-core found no color-contrast failures it could evaluate. Elements it could not evaluate are not listed.</p>")
    for j, f in enumerate(contrast):
        parts.append("<div class='card'><div class='body'><dl>")
        parts.append(f"<dt>Element</dt><dd><code>{e(f.html)}</code></dd>")
        parts.append(f"<dt>Text</dt><dd>{e(f.text)}</dd>")
        parts.append(f"<dt>Colors</dt><dd><span class='sw' style='background:{e(f.fg)}'></span>{e(f.fg)} on <span class='sw' style='background:{e(f.bg)}'></span>{e(f.bg)}</dd>")
        parts.append(f"<dt>Ratio</dt><dd>{f.ratio:.2f}:1 (needs {f.required:g}:1)</dd>")
        if f.suggested_fg:
            parts.append(f"<dt>Suggested text color</dt><dd><span class='sw' style='background:{e(f.suggested_fg)}'></span>{e(f.suggested_fg)}</dd></dl>")
            parts.append(f"<pre id='c{j}'>{e(css_snippet(f))}</pre><button type='button' data-copy='c{j}'>Copy</button>")
        else:
            parts.append("</dl>")
        if f.manual_review:
            parts.append(f"<p><span class='tag'>manual review</span> {e(f.manual_review)}</p>")
        parts.append("</div></div>")
    parts.append(f"<script>{JS}</script></body></html>")
    return "".join(parts)
