"""構成図の生成物が、定義と一致していて、読める状態であること。"""

import sys
import xml.dom.minidom
from html import unescape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "diagrams"))

import build_diagrams  # noqa: E402

NAMES = sorted(build_diagrams.DIAGRAMS)


def _overlap(a, b, margin: float = 6) -> bool:
    """余白 (margin) を含めて重なるか。ぴったり接しているだけでも、読みにくいので重なりとみなす。"""
    return a[0] < b[2] + margin and b[0] < a[2] + margin and a[1] < b[3] + margin and b[1] < a[3] + margin


def test_generated_files_match_the_definitions():
    # 定義を変えたのに作り直し忘れた、または SVG だけ手で直した、を検出する
    assert build_diagrams.main(["--check"]) == 0


@pytest.mark.parametrize("name", NAMES)
def test_cards_do_not_overlap_each_other(name):
    cards = build_diagrams.DIAGRAMS[name]().cards
    for i, a in enumerate(cards):
        for b in cards[i + 1 :]:
            assert not _overlap(a.bbox, b.bbox), f"{name}: {a.label} と {b.label} が重なっている"


@pytest.mark.parametrize("name", NAMES)
def test_everything_is_inside_the_canvas(name):
    d = build_diagrams.DIAGRAMS[name]()
    for c in d.cards:
        left, top, right, bottom = c.bbox
        assert left >= 0 and top >= 0 and right <= d.width and bottom <= d.height, c.label
    for p in d.panels:
        assert p.x >= 0 and p.y >= 0 and p.x + p.w <= d.width and p.y + p.h <= d.height, p.title
    for e in d.edges:
        assert all(0 <= x <= d.width and 0 <= y <= d.height for x, y in e.points)


@pytest.mark.parametrize("name", NAMES)
def test_cards_stay_inside_their_panel(name):
    d = build_diagrams.DIAGRAMS[name]()
    for c in d.cards:
        containing = [p for p in d.panels if p.x <= c.cx <= p.x + p.w and p.y <= c.cy <= p.y + p.h]
        for p in containing:
            left, _top, right, bottom = c.bbox
            assert left >= p.x and right <= p.x + p.w and bottom <= p.y + p.h, (
                f"{name}: {c.label} が {p.title} からはみ出す"
            )


@pytest.mark.parametrize("name", NAMES)
def test_svg_embeds_the_drawio_source_and_both_are_valid_xml(name):
    drawio = (ROOT / "docs" / "diagrams" / f"{name}.drawio").read_text(encoding="utf-8")
    svg = (ROOT / "docs" / "diagrams" / f"{name}.drawio.svg").read_text(encoding="utf-8")
    xml.dom.minidom.parseString(drawio)
    xml.dom.minidom.parseString(svg)
    assert unescape(svg.split('content="', 1)[1].split('"', 1)[0]) == drawio.strip()


def test_numbered_badges_are_unique_and_start_at_one():
    for name in ("publish-flow", "build-internals"):
        numbers = sorted(c.badge for c in build_diagrams.DIAGRAMS[name]().cards if c.badge is not None)
        assert numbers == list(range(1, len(numbers) + 1)), name
