"""構成図の作図キット。同じ定義から、diagrams.net の ``.drawio`` と書き出し SVG (``.drawio.svg``) を作る。

読みやすさのために、次の作法に揃える。

* **カード**: 角丸の枠にアイコン、その下に名前 (太字) と説明 (等幅・灰色)。
* **パネル**: 用途ごとに枠でまとめる。題名は枠の内側か、枠の上辺に載せるタグ。
* **番号つきの丸**: 順序のある流れは、1 から始まる番号をカードの角に付ける。
* **矢印の色**: 青 = 主な流れ / 灰色の破線 = 補助 (起動・登録・参照) / オレンジ = 強調する経路 / 赤の破線 = 止まる分岐。
* 矢印には、何が流れるか (またはどのタイミングか) を短いラベルで添える。

座標はすべて絶対値 (px)。矢印は折れ線で、点を列で与える。diagrams.net で開いたときも、同じ形で出る。
"""

from __future__ import annotations

import base64
import html
import unicodedata
from dataclasses import dataclass, field

FONT = "'Noto Sans JP','Hiragino Sans','Yu Gothic',Meiryo,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',monospace"

INK = "#101828"
MUTED = "#667085"
LINE = "#d0d5dd"

#: 矢印の色: (線, ラベルの文字)
COLORS = {
    "blue": ("#1a73e8", "#1558b0"),
    "gray": ("#667085", "#475467"),
    "orange": ("#e8710a", "#b45309"),
    "red": ("#d92d20", "#b42318"),
}

#: アイコン (48x48 の座標、線画)。商標のロゴは使わず、意味だけを示す単純な図にする。
ICONS = {
    "code": '<polyline points="18,14 8,24 18,34"/><polyline points="30,14 40,24 30,34"/><line x1="27" y1="10" x2="21" y2="38"/>',
    "doc": '<path d="M12 6h17l9 9v27H12z"/><polyline points="29,6 29,15 38,15"/><line x1="18" y1="24" x2="32" y2="24"/><line x1="18" y1="30" x2="32" y2="30"/><line x1="18" y1="36" x2="26" y2="36"/>',
    "braces": '<path d="M18 8c-5 0-6 2-6 6v5c0 3-2 5-5 5 3 0 5 2 5 5v5c0 4 1 6 6 6"/><path d="M30 8c5 0 6 2 6 6v5c0 3 2 5 5 5-3 0-5 2-5 5v5c0 4-1 6-6 6"/>',
    "diagram": '<rect x="16" y="6" width="16" height="12" rx="2"/><rect x="5" y="30" width="16" height="12" rx="2"/><rect x="27" y="30" width="16" height="12" rx="2"/><path d="M24 18v6M13 30v-6h22v6"/>',
    "gear": '<circle cx="24" cy="24" r="7"/><circle cx="24" cy="24" r="15" stroke-dasharray="5 4.7"/><circle cx="24" cy="24" r="12"/>',
    "cloud": '<path d="M14 36a9 9 0 0 1-1-18 12 12 0 0 1 23 3 7.5 7.5 0 0 1-1 15z"/>',
    "lock": '<rect x="11" y="22" width="26" height="18" rx="3"/><path d="M16 22v-6a8 8 0 0 1 16 0v6"/><circle cx="24" cy="31" r="2"/>',
    "check": '<circle cx="24" cy="24" r="16"/><polyline points="16,24 22,30 33,18"/>',
    "user": '<circle cx="24" cy="16" r="7"/><path d="M9 40a15 13 0 0 1 30 0"/>',
    "globe": '<circle cx="24" cy="24" r="16"/><ellipse cx="24" cy="24" rx="7" ry="16"/><line x1="8" y1="24" x2="40" y2="24"/>',
    "shield": '<path d="M24 6l14 5v11c0 9-6 16-14 20-8-4-14-11-14-20V11z"/><polyline points="18,24 22,28 30,19"/>',
    "terminal": '<rect x="6" y="9" width="36" height="30" rx="4"/><polyline points="13,19 19,24 13,29"/><line x1="23" y1="30" x2="33" y2="30"/>',
    "package": '<path d="M24 6l16 8v20l-16 8-16-8V14z"/><polyline points="8,14 24,22 40,14"/><line x1="24" y1="22" x2="24" y2="42"/>',
    "wrench": '<path d="M33 8a9 9 0 0 0-8 12L9 36a3.5 3.5 0 0 0 5 5l16-16a9 9 0 0 0 12-8l-6 5-5-1-1-5z"/>',
    "book": '<path d="M8 10h13a3 3 0 0 1 3 3v26a3 3 0 0 0-3-3H8z"/><path d="M40 10H27a3 3 0 0 0-3 3v26a3 3 0 0 1 3-3h13z"/>',
    "plug": '<path d="M17 6v10M31 6v10"/><path d="M11 16h26v8a13 13 0 0 1-26 0z"/><line x1="24" y1="37" x2="24" y2="44"/>',
    "branch": '<circle cx="14" cy="12" r="4"/><circle cx="14" cy="36" r="4"/><circle cx="34" cy="20" r="4"/><line x1="14" y1="16" x2="14" y2="32"/><path d="M34 24c0 8-20 4-20 8"/>',
    "link": '<path d="M20 28a7 7 0 0 0 10 0l7-7a7 7 0 0 0-10-10l-3 3"/><path d="M28 20a7 7 0 0 0-10 0l-7 7a7 7 0 0 0 10 10l3-3"/>',
}


def text_width(text: str, size: float, mono: bool = False) -> float:
    """文字列の幅 (px) の見積り。全角は 1 文字ぶん、半角は約 0.55 (等幅は 0.6) 文字ぶん。"""
    ascii_w = 0.6 if mono else 0.55
    return sum(size if unicodedata.east_asian_width(c) in "WF" else size * ascii_w for c in text)


@dataclass
class Panel:
    """用途ごとにまとめる枠。"""

    x: float
    y: float
    w: float
    h: float
    title: str = ""
    subtitle: str = ""
    fill: str = "#f2f4f7"
    stroke: str = "#d0d5dd"
    title_color: str = INK
    dashed: bool = False
    tab: bool = False  # True: 題名を枠の上辺に載せるタグにする
    tab_dx: float = 0  # タグの横方向のずらし


@dataclass
class Card:
    """アイコン + 名前 + 説明。``cx, cy`` はアイコンの中心。"""

    cx: float
    cy: float
    label: str
    sub: str = ""
    icon: str = "package"
    accent: str = "#344054"
    badge: int | None = None
    sub2: str = ""  # 説明の 2 行目

    SIZE = 64

    @property
    def top(self) -> float:
        return self.cy - self.SIZE / 2

    @property
    def bottom(self) -> float:
        return self.cy + self.SIZE / 2

    @property
    def left(self) -> float:
        return self.cx - self.SIZE / 2

    @property
    def right(self) -> float:
        return self.cx + self.SIZE / 2

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """アイコンと文字を含む、占有範囲 (左, 上, 右, 下)。"""
        lines = [(self.label, 15, False), *[(s, 11.5, True) for s in (self.sub, self.sub2) if s]]
        half = max(self.SIZE, *(text_width(t, size, mono) for t, size, mono in lines)) / 2
        return self.cx - half, self.top, self.cx + half, self.text_bottom

    @property
    def text_bottom(self) -> float:
        """名前と説明を含めた、カードの下端。"""
        return self.bottom + (62 if self.sub2 else 46 if self.sub else 28)


@dataclass
class Edge:
    """折れ線の矢印。"""

    points: list[tuple[float, float]]
    label: str = ""
    color: str = "blue"
    dashed: bool = False
    label_t: float = 0.5  # ラベルを置く位置 (経路の長さに対する割合)
    arrow: bool = True


@dataclass
class Note:
    """補足の文字。"""

    x: float
    y: float
    lines: list[str]
    color: str = MUTED
    size: float = 12
    anchor: str = "start"  # start / middle
    mono: bool = False
    bold: bool = False


@dataclass
class Diagram:
    """1 枚の図。"""

    name: str
    width: int
    height: int
    panels: list[Panel] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)

    # ---- 共通 ----
    @staticmethod
    def _path_point(points: list[tuple[float, float]], t: float) -> tuple[float, float]:
        segs = [(points[i], points[i + 1]) for i in range(len(points) - 1)]
        lengths = [
            abs(b[0] - a[0]) + abs(b[1] - a[1])
            if (a[0] == b[0] or a[1] == b[1])
            else ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            for a, b in segs
        ]
        target = sum(lengths) * t
        for (a, b), length in zip(segs, lengths, strict=True):
            if target <= length or (a, b) == segs[-1]:
                f = 0 if length == 0 else min(target / length, 1)
                return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            target -= length
        return points[-1]

    # ---- SVG ----
    def _icon_svg(self, card: Card, x: float, y: float) -> str:
        return (
            f'<g transform="translate({x + 8},{y + 8})" fill="none" stroke="{card.accent}" '
            f'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">{ICONS[card.icon]}</g>'
        )

    def to_svg(self, drawio_xml: str) -> str:
        """書き出し SVG。``content`` に元データを埋め込み、diagrams.net で開き直せるようにする。"""
        out = [
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{self.width}px" height="{self.height}px" '
            f'viewBox="0 0 {self.width} {self.height}" content="{html.escape(drawio_xml, quote=True)}">',
            "<defs>",
        ]
        for name, (stroke, _) in COLORS.items():
            out.append(
                f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
                f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{stroke}"/></marker>'
            )
        out += ["</defs>", '<rect width="100%" height="100%" fill="#ffffff"/>']

        for p in self.panels:
            dash = ' stroke-dasharray="7 5"' if p.dashed else ""
            out.append(
                f'<rect x="{p.x}" y="{p.y}" width="{p.w}" height="{p.h}" rx="14" fill="{p.fill}" stroke="{p.stroke}" stroke-width="1.5"{dash}/>'
            )
            if p.title and p.tab:
                w = text_width(p.title, 13) + 28
                tx = p.x + 22 + p.tab_dx
                out.append(
                    f'<rect x="{tx}" y="{p.y - 13}" width="{w}" height="26" rx="13" fill="#ffffff" stroke="{p.stroke}" stroke-width="1.5"/>'
                )
                out.append(
                    f'<text x="{tx + w / 2}" y="{p.y + 5}" text-anchor="middle" font-family="{FONT}" font-size="13" '
                    f'font-weight="700" fill="{p.title_color}">{html.escape(p.title)}</text>'
                )
            elif p.title:
                out.append(
                    f'<text x="{p.x + 22}" y="{p.y + 34}" font-family="{FONT}" font-size="17" font-weight="700" fill="{p.title_color}">{html.escape(p.title)}</text>'
                )
                if p.subtitle:
                    out.append(
                        f'<text x="{p.x + 22}" y="{p.y + 54}" font-family="{MONO}" font-size="11.5" fill="{MUTED}">{html.escape(p.subtitle)}</text>'
                    )

        for e in self.edges:
            stroke, label_color = COLORS[e.color]
            dash = ' stroke-dasharray="7 5"' if e.dashed else ""
            marker = f' marker-end="url(#arrow-{e.color})"' if e.arrow else ""
            pts = " ".join(f"{x},{y}" for x, y in e.points)
            out.append(
                f'<polyline points="{pts}" fill="none" stroke="{stroke}" stroke-width="2" stroke-linejoin="round"{dash}{marker}/>'
            )

        for c in self.cards:
            out.append(
                f'<rect x="{c.left}" y="{c.top}" width="{Card.SIZE}" height="{Card.SIZE}" rx="13" fill="#ffffff" stroke="{LINE}" stroke-width="1.5"/>'
            )
            out.append(self._icon_svg(c, c.left, c.top))
            out.append(
                f'<text x="{c.cx}" y="{c.bottom + 22}" text-anchor="middle" font-family="{FONT}" font-size="15" font-weight="700" fill="{INK}">{html.escape(c.label)}</text>'
            )
            for i, sub in enumerate(filter(None, [c.sub, c.sub2])):
                out.append(
                    f'<text x="{c.cx}" y="{c.bottom + 40 + i * 16}" text-anchor="middle" font-family="{MONO}" font-size="11.5" fill="{MUTED}">{html.escape(sub)}</text>'
                )
            if c.badge is not None:
                out.append(
                    f'<circle cx="{c.left + 2}" cy="{c.top + 2}" r="13" fill="#1a73e8" stroke="#ffffff" stroke-width="2"/>'
                )
                out.append(
                    f'<text x="{c.left + 2}" y="{c.top + 7}" text-anchor="middle" font-family="{FONT}" font-size="14" font-weight="700" fill="#ffffff">{c.badge}</text>'
                )

        for e in self.edges:
            if not e.label:
                continue
            _, label_color = COLORS[e.color]
            lx, ly = self._path_point(e.points, e.label_t)
            w = text_width(e.label, 12) + 14
            out.append(
                f'<rect x="{lx - w / 2}" y="{ly - 11}" width="{w}" height="22" rx="5" fill="#ffffff" fill-opacity="0.96"/>'
            )
            out.append(
                f'<text x="{lx}" y="{ly + 4}" text-anchor="middle" font-family="{FONT}" font-size="12" fill="{label_color}">{html.escape(e.label)}</text>'
            )

        for n in self.notes:
            family = MONO if n.mono else FONT
            weight = ' font-weight="700"' if n.bold else ""
            for i, line in enumerate(n.lines):
                out.append(
                    f'<text x="{n.x}" y="{n.y + i * (n.size + 5)}" text-anchor="{n.anchor}" font-family="{family}" font-size="{n.size}"{weight} fill="{n.color}">{html.escape(line)}</text>'
                )
        out.append("</svg>\n")
        return "\n".join(out)

    # ---- drawio ----
    def to_drawio(self) -> str:
        """diagrams.net の ``mxfile``。アイコンは SVG の画像として埋め込む。"""
        cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
        n = 0

        def add(value: str, style: str, x: float, y: float, w: float, h: float, vertex: bool = True) -> None:
            nonlocal n
            n += 1
            kind = 'vertex="1"' if vertex else ""
            cells.append(
                f'<mxCell id="c{n}" value="{html.escape(value, quote=True)}" style="{style}" {kind} parent="1">'
                f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
            )

        font = "fontFamily=Noto Sans JP;"
        for p in self.panels:
            dash = "dashed=1;" if p.dashed else ""
            base = f"rounded=1;arcSize=5;whiteSpace=wrap;html=1;fillColor={p.fill};strokeColor={p.stroke};strokeWidth=1.5;{dash}"
            if p.title and not p.tab:
                value = f'<b style="font-size:17px">{html.escape(p.title)}</b>'
                if p.subtitle:
                    value += f'<br><span style="font-size:11px;color:{MUTED};font-family:Courier New">{html.escape(p.subtitle)}</span>'
                add(
                    value,
                    base
                    + f"align=left;verticalAlign=top;spacingLeft=20;spacingTop=14;fontColor={p.title_color};{font}",
                    p.x,
                    p.y,
                    p.w,
                    p.h,
                )
            else:
                add("", base, p.x, p.y, p.w, p.h)
                if p.title and p.tab:
                    w = text_width(p.title, 13) + 28
                    add(
                        html.escape(p.title),
                        f"rounded=1;arcSize=50;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor={p.stroke};strokeWidth=1.5;fontStyle=1;fontSize=13;fontColor={p.title_color};{font}",
                        p.x + 22 + p.tab_dx,
                        p.y - 13,
                        w,
                        26,
                    )

        for e in self.edges:
            n += 1
            stroke, label_color = COLORS[e.color]
            dash = "dashed=1;" if e.dashed else ""
            end = "endArrow=block;endFill=1;" if e.arrow else "endArrow=none;"
            style = (
                f"edgeStyle=none;html=1;rounded=0;{end}strokeColor={stroke};strokeWidth=2;{dash}"
                f"labelBackgroundColor=#ffffff;fontSize=12;fontColor={label_color};{font}"
            )
            first, last, middle = e.points[0], e.points[-1], e.points[1:-1]
            pts = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in middle)
            array = f'<Array as="points">{pts}</Array>' if middle else ""
            cells.append(
                f'<mxCell id="c{n}" value="{html.escape(e.label, quote=True)}" style="{style}" edge="1" parent="1">'
                f'<mxGeometry x="{round(e.label_t * 2 - 1, 3)}" relative="1" as="geometry">'
                f'<mxPoint x="{first[0]}" y="{first[1]}" as="sourcePoint"/><mxPoint x="{last[0]}" y="{last[1]}" as="targetPoint"/>{array}'
                f"</mxGeometry></mxCell>"
            )

        for c in self.cards:
            add(
                "",
                f"rounded=1;arcSize=20;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor={LINE};strokeWidth=1.5;",
                c.left,
                c.top,
                Card.SIZE,
                Card.SIZE,
            )
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48" fill="none" stroke="{c.accent}" '
                f'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">{ICONS[c.icon]}</svg>'
            )
            data = base64.b64encode(svg.encode()).decode()
            add(
                "",
                f"shape=image;verticalLabelPosition=bottom;aspect=fixed;imageAspect=0;image=data:image/svg+xml,{data};",
                c.left + 8,
                c.top + 8,
                48,
                48,
            )
            add(
                html.escape(c.label),
                f"text;html=1;align=center;verticalAlign=middle;fontStyle=1;fontSize=15;fontColor={INK};{font}",
                c.cx - 100,
                c.bottom + 10,
                200,
                24,
            )
            for i, sub in enumerate(filter(None, [c.sub, c.sub2])):
                add(
                    html.escape(sub),
                    f"text;html=1;align=center;verticalAlign=middle;fontSize=11;fontColor={MUTED};fontFamily=Courier New;",
                    c.cx - 110,
                    c.bottom + 32 + i * 16,
                    220,
                    18,
                )
            if c.badge is not None:
                add(
                    str(c.badge),
                    f"ellipse;whiteSpace=wrap;html=1;fillColor=#1a73e8;strokeColor=#ffffff;strokeWidth=2;fontColor=#ffffff;fontStyle=1;fontSize=14;{font}",
                    c.left - 11,
                    c.top - 11,
                    26,
                    26,
                )

        for note in self.notes:
            family = "Courier New" if note.mono else "Noto Sans JP"
            style = f"text;html=1;align={'center' if note.anchor == 'middle' else 'left'};verticalAlign=top;fontSize={int(note.size)};fontColor={note.color};fontFamily={family};{'fontStyle=1;' if note.bold else ''}"
            width = max(text_width(line, note.size, note.mono) for line in note.lines) + 16
            x = note.x - width / 2 if note.anchor == "middle" else note.x
            add(
                "<br>".join(html.escape(line) for line in note.lines),
                style,
                x,
                note.y - note.size - 2,
                width,
                (note.size + 5) * len(note.lines) + 4,
            )

        model = (
            f'<mxGraphModel dx="{self.width}" dy="{self.height}" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
            f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{self.width}" pageHeight="{self.height}" math="0" shadow="0">'
            f"<root>{''.join(cells)}</root></mxGraphModel>"
        )
        return (
            f'<mxfile host="app.diagrams.net"><diagram id="{self.name}" name="{self.name}">{model}</diagram></mxfile>\n'
        )
