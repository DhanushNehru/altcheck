from altcheck.contrast import ratio, parse_hex, suggest_foreground
from altcheck.images import select_candidates
from altcheck.report import build
from altcheck.vision import Draft, parse_output


def img(**kw):
    d = dict(selector="img", src="a.png", has_alt_attr=False, alt=None, role=None, aria_hidden=None, cls="",
             width=200, height=200, natural_w=400, natural_h=400, in_header=False, in_footer=False,
             heading="", surrounding="", figcaption="", link_href="", link_text="", outer="<img>")
    d.update(kw)
    return d


def test_missing_vs_empty_vs_weak():
    raw = [
        img(src="m.png"),
        img(src="e.png", has_alt_attr=True, alt="", width=60, height=60),  # small empty alt: leave alone
        img(src="w.png", has_alt_attr=True, alt="IMG_1234.jpg"),
        img(src="ok.png", has_alt_attr=True, alt="Team photo at the 2024 offsite"),
    ]
    cands, _ = select_candidates(raw)
    assert [(c.src, c.issue) for c in cands] == [("m.png", "missing"), ("w.png", "weak")]


def test_skips_tiny_and_presentation():
    raw = [img(width=20, height=20), img(src="p.png", role="presentation")]
    assert select_candidates(raw)[0] == []


def test_max_images():
    raw = [img(src=f"{i}.png") for i in range(8)]
    cands, notes = select_candidates(raw, max_images=5)
    assert len(cands) == 5 and notes


def test_suggested_color_passes():
    s = suggest_foreground("#aaaaaa", "#ffffff", 4.5)
    assert ratio(parse_hex(s), parse_hex("#ffffff")) >= 4.5


def test_parse_rejects_parroting():
    assert parse_output("Describe what the image shows in one short sentence").error
    assert parse_output("A red brick cottage by the sea with a blue door").confidence == "high"


def test_report_escapes_html():
    from altcheck.images import Candidate
    c = Candidate(selector="img", src='x.png" onerror="x', current_alt=None, issue="missing")
    out = build("http://t", "<b>t</b>", [(c, Draft(alt='a "quote" <script>', confidence="low"))], [], [], "m")
    assert "<script>a" not in out and "&lt;b&gt;t&lt;/b&gt;" in out
