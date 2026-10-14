# altcheck

An alt-text and contrast helper for freelance web developers. Give it one URL and it writes a local `report.html` with **drafted** fixes for you to review. It does not edit your site, crawl, or upload anything. The vision model runs on your machine.

> AI-drafted suggestions. Review before using. This tool does not check full accessibility.

## What it does

1. Loads the page in headless Chromium (Playwright), waits for network idle.
2. Finds `<img>` elements that need attention: missing `alt`, an empty `alt` on an image that looks meaningful, or a weak `alt` (a filename like `IMG_1234.jpg`, or a generic word like `image`, `photo`, `banner`). Images under 50x50 px, tracking pixels, and images marked `role="presentation"` or `aria-hidden` are skipped. A missing `alt` attribute and `alt=""` are treated differently on purpose, because an empty `alt` is valid for decoration.
3. Drafts alt text for up to 5 images (`--max-images`) with a local open-weight vision model, [SmolVLM-500M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct) (Apache 2.0) through `transformers`. It also asks the model whether the image looks purely decorative.
4. Runs [axe-core](https://github.com/dequelabs/axe-core) 4.14.0 (downloaded once from npm via jsDelivr and cached in `~/.cache/altcheck`) with only the `color-contrast` rule and suggests the nearest text color (same hue, adjusted lightness) that passes. Cases it cannot judge safely (gradients, images behind text, no passing shade) are marked "manual review".
5. Writes one self-contained `report.html` (inline CSS and JS, light and dark mode) with thumbnails, selectors, current vs drafted alt, copy buttons, color swatches, and a CSS snippet per contrast fix.

## Install

Python 3.10+.

```bash
git clone https://github.com/DhanushNehru/altcheck
cd altcheck
pip install -e .
playwright install chromium
```

The first run downloads the model from Hugging Face (about 1 GB) and axe-core (about 0.5 MB), so it needs internet once.

## Use

```bash
altcheck https://example.com
altcheck https://example.com --max-images 3 -o my-report.html
altcheck https://example.com --skip-vision        # contrast only, no model
altcheck https://example.com --model HuggingFaceTB/SmolVLM-256M-Instruct
```

Flags: `--max-images`, `--model`, `--device cpu|cuda`, `--dtype`, `--output`, `--screenshot`, `--skip-vision`.

`--model` accepts another Hugging Face vision model that works with `AutoModelForImageTextToText`. Check its license first. Qwen2.5-VL-3B is non-commercial and is blocked. Only SmolVLM-500M-Instruct has been tried.

## Hardware and speed (what was actually tested)

Tested on a 2-core CPU-only Linux box with about 2 GB of RAM:

- `float32` ran out of memory loading the 500M model, so altcheck picks `bfloat16` when under 4 GB of RAM is free. `--dtype` overrides this.
- With `bfloat16` on that box, each image took roughly 20 seconds (two short generations per image). The very first generation was slower.
- Not tested: GPUs, Apple Silicon, Windows, other models, and large or JavaScript-heavy sites.

## Sample run on a real page

Run on the W3C "before" demo page, which is deliberately inaccessible ([source](https://www.w3.org/WAI/demos/bad/before/home.html)), with `--max-images 3` on the CPU box described below. Three images had no `alt` attribute:

| Image | Drafted alt |
| --- | --- |
| `top_weather.gif` | A yellow sun and a gray cloud. |
| `teaser_right1.jpg` | A woman is singing on a microphone in front of a large screen with bright lights. |
| `teaser_right2.jpg` | A flower with a yellow center and white petals. |

I checked the thumbnails by eye and the drafts matched them. They describe what is visible, not what the image is for on the page (for example, the weather icon is really "today's weather"), so a person still has to edit them. This is one page and three images, not a quality measurement. axe-core also reported 2 contrast failures there.

## Limits

- The model is small. Drafts can be vague, repeat the obvious, or be wrong. In testing, long page text in the prompt made it copy that text or make things up, so only the nearest heading is sent. For linked images the destination is added by code, not by the model.
- "Confidence" is a rough heuristic (short or vague drafts are marked low). It is not a measured score.
- The decorative flag is a yes/no question to the same small model. Treat it as a hint.
- SVG images and images that fail to download are listed as "could not be drafted".
- Contrast: only the axe-core `color-contrast` rule. Suggestions assume a flat text and background color.
- This is not an accessibility audit. Many things (keyboard use, headings, forms, screen reader behavior) are not checked. A human has to review every suggestion.
- No benchmark numbers are claimed. Nobody has measured alt-text quality across many sites here.

## Development

```bash
pip install -e ".[dev]"
pytest
```

`examples/demo-site/` is a tiny page with a missing alt, a filename alt, an empty alt and low-contrast text. In that folder run `python make_images.py` (creates the three test images), then `python -m http.server 8765`, then `altcheck http://localhost:8765/index.html`.

## Licenses

altcheck is MIT. SmolVLM is Apache 2.0. axe-core (MPL-2.0) is downloaded at runtime and not redistributed in this repo.
