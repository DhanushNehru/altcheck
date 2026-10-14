"""altcheck: draft alt text and contrast fixes for one URL, for a human to review."""
from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

from . import __version__


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="altcheck",
        description="Alt-text and contrast helper. Writes a local report.html with drafted fixes for you to review.",
    )
    ap.add_argument("url", help="page to check, e.g. https://example.com")
    ap.add_argument("-o", "--output", default="report.html", help="report path (default: report.html)")
    ap.add_argument("--max-images", type=int, default=5, help="max images to draft alt text for (default: 5)")
    ap.add_argument("--model", default=None, help="Hugging Face vision model id with an open license (default: SmolVLM-500M-Instruct)")
    ap.add_argument("--device", default=None, choices=["cpu", "cuda"], help="default: cuda if available, else cpu")
    ap.add_argument("--dtype", default=None, choices=["float32", "bfloat16", "float16"], help="override model precision")
    ap.add_argument("--screenshot", default=None, help="also save a full-page screenshot to this path")
    ap.add_argument("--skip-vision", action="store_true", help="contrast check only (no model download)")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)

    url = args.url if "://" in args.url else "https://" + args.url
    from .contrast import findings_from_axe
    from .images import select_candidates
    from .render import render
    from .report import build
    from .vision import DEFAULT_MODEL, Draft, VisionDrafter

    print(f"Rendering {url} ...", file=sys.stderr)
    try:
        raw, axe, title, final_url = render(url, Path(args.screenshot) if args.screenshot else None)
    except Exception as exc:
        print(f"Could not load the page: {exc}", file=sys.stderr)
        return 2

    cands, notes = select_candidates(raw, max_images=args.max_images)
    contrast = findings_from_axe(axe)
    print(f"{len(cands)} image(s) to draft, {len(contrast)} contrast failure(s).", file=sys.stderr)

    results = []
    model_desc = "vision step skipped"
    if cands and not args.skip_vision:
        print("Loading vision model (first run downloads it) ...", file=sys.stderr)
        drafter = VisionDrafter(args.model or DEFAULT_MODEL, args.device, args.dtype)
        model_desc = drafter.describe()
        with tempfile.TemporaryDirectory(prefix="altcheck_") as tmp:
            for i, c in enumerate(cands, 1):
                t = time.time()
                d = drafter.draft(c, final_url, Path(tmp))
                print(f"  [{i}/{len(cands)}] {time.time() - t:.0f}s {d.alt or d.error}", file=sys.stderr)
                results.append((c, d))
    else:
        results = [(c, Draft(error="vision step skipped")) for c in cands]

    out = Path(args.output)
    out.write_text(build(final_url, title, results, contrast, notes, model_desc), encoding="utf-8")
    print(f"Wrote {out.resolve()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
