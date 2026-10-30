"""docs/diagrams/ の図を作る。

    python tools/diagrams/build_diagrams.py          # 作り直す
    python tools/diagrams/build_diagrams.py --check  # 生成物が定義と一致しているか確かめる (CI 用)

図の定義はここに書き、``.drawio`` と ``.drawio.svg`` は生成物としてリポジトリに置く。
diagrams.net で手直しして書き出した SVG を上書きした場合は、このファイルの定義も合わせること。
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kit import Card, Diagram, Edge, Note, Panel

BLUE = "#1a73e8"
TEAL = "#0f9d8a"
TEAL_DARK = "#0b6b5d"
ORANGE = "#e8710a"
RED = "#d92d20"
GRAY = "#344054"
MUTED_TEXT = "#667085"

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "diagrams"


def system_overview() -> Diagram:
    """全体像: 何を書き、どこで組み立て、どこへ届け、何で守るか。"""
    d = Diagram("system-overview", 1200, 940)
    d.panels += [
        Panel(160, 40, 250, 620, "書く", "リポジトリの中身"),
        Panel(450, 40, 480, 620, "組み立てる", "docspipeline (Sphinx + 拡張)"),
        Panel(
            474,
            112,
            432,
            530,
            "Sphinx",
            "docs/conf.py → build_config()",
            fill="#e6f4f1",
            stroke=TEAL,
            title_color=TEAL_DARK,
        ),
        Panel(970, 40, 200, 620, "届ける", "出力"),
        Panel(160, 700, 1010, 200, "守る", "GitHub Actions (ci.yml)"),
    ]
    d.cards += [
        Card(80, 350, "開発者", "docs/ を書く・PR", "user", GRAY),
        Card(285, 150, "Python コード", "docstring (Google 形式)", "code", BLUE),
        Card(285, 290, "Markdown 文書", "既存の .md・手順のプロンプト", "doc", BLUE),
        Card(285, 430, "C++ ヘッダー", "Doxygen コメント", "braces", BLUE),
        Card(285, 570, "図", "Mermaid / diagrams.net", "diagram", BLUE),
        Card(560, 225, "autodoc", "+ napoleon", "book", TEAL),
        Card(690, 225, "MyST", "Markdown を取り込む", "doc", TEAL),
        Card(820, 225, "mermaid 拡張", "mmdc で SVG に", "diagram", TEAL),
        Card(560, 355, "Breathe", "Doxygen の XML", "braces", TEAL),
        Card(690, 355, "guard", "設定エラーの報告", "shield", TEAL),
        Card(820, 355, "prompt 拡張", "コピーできる手順", "terminal", TEAL),
        Card(690, 485, "Confluence 設定", "公開の安全装置", "lock", TEAL),
        Card(1070, 230, "HTML", "docs/_build/html", "globe", GRAY),
        Card(1070, 470, "Confluence", "専用の親ページ配下だけ", "cloud", ORANGE),
        Card(300, 805, "build -W", "警告はエラー", "check", GRAY),
        Card(480, 805, "coverage", "docstring 100%", "check", GRAY),
        Card(660, 805, "check-diagrams", ".drawio に SVG", "diagram", GRAY),
        Card(840, 805, "linkcheck", "週 1 回", "link", GRAY),
        Card(1020, 805, "secrets", "トークンは公開の手順だけ", "lock", GRAY),
    ]
    d.edges += [
        Edge([(114, 350), (156, 350)], color="gray"),
        Edge([(322, 150), (472, 150)], "autodoc", "blue"),
        Edge([(322, 290), (472, 290)], "MyST", "blue"),
        Edge([(322, 430), (472, 430)], "Doxygen → Breathe", "blue"),
        Edge([(322, 570), (472, 570)], "mmdc → SVG", "blue"),
        Edge([(908, 230), (1034, 230)], "-b html", "blue"),
        Edge([(908, 470), (1034, 470)], "-b confluence", "orange"),
        Edge([(690, 698), (690, 664)], "検査", "gray", dashed=True),
    ]
    d.notes += [
        Note(690, 620, ["-W: 警告はエラー (リンク切れ・未解決の参照も止める)"], TEAL_DARK, 12, "middle", bold=True),
        Note(1070, 600, ["local → dryrun → publish", "の順に進める (既定は local)"], "#b45309", 12, "middle"),
    ]
    return d


def publish_flow() -> Diagram:
    """公開の流れ: どこで止まり、何を守っているか。番号は実行順。"""
    d = Diagram("publish-flow", 1200, 700)
    d.panels += [
        Panel(40, 60, 840, 500, "GitHub Actions: publish ジョブ", ".github/workflows/ci.yml"),
        Panel(
            920,
            290,
            240,
            270,
            "Confluence Cloud",
            "専用の親ページ配下だけ",
            fill="#fff7ed",
            stroke=ORANGE,
            title_color="#b45309",
        ),
    ]
    d.cards += [
        Card(130, 190, "main へ反映", "push", "branch", GRAY, badge=1),
        Card(330, 190, "テストと文書ビルド", "test / docs ジョブ", "check", GRAY, badge=2),
        Card(530, 190, "公開してよいか", "CONFLUENCE_PUBLISH", "shield", GRAY, badge=3),
        Card(730, 190, "環境変数の確認", "5 つの設定がそろうか", "lock", GRAY, badge=4),
        Card(130, 420, "接続テスト", "認証・権限・親ページ", "plug", GRAY, badge=5),
        Card(380, 420, "Confluence 形式でビルド", "--mode publish", "gear", GRAY, badge=6),
        Card(
            1040,
            420,
            "親ページ配下へ反映",
            "更新はする、消さない",
            "cloud",
            ORANGE,
            badge=7,
            sub2="外の同名ページは上書きしない",
        ),
    ]
    d.edges += [
        Edge([(164, 190), (296, 190)], "成功したら", "blue"),
        Edge([(364, 190), (496, 190)], "成功したら", "blue"),
        Edge([(564, 190), (696, 190)], "true", "blue"),
        Edge([(764, 190), (850, 190), (850, 330), (130, 330), (130, 382)], "", "blue"),
        Edge([(164, 420), (344, 420)], "成功したら", "blue"),
        Edge([(414, 420), (1004, 420)], "ページを作成・更新", "orange", label_t=0.5),
    ]
    d.notes += [
        Note(530, 292, ["false →", "公開ジョブを飛ばす"], RED, 12, "middle"),
        Note(730, 292, ["不足 → 終了コード 2", "(ビルド前に止まる)"], RED, 12, "middle"),
        Note(130, 510, ["失敗 → 中止", "(ビルドしない)"], RED, 12, "middle"),
        Note(40, 610, ["手元では、先に乾燥実行で確かめる:"], GRAY, 13, bold=True),
        Note(40, 635, ["docspipeline publish docs --mode dryrun"], BLUE, 13, mono=True),
        Note(40, 660, ["dryrun は接続して確認するだけで、ページを変更しない。"], GRAY, 12),
    ]
    return d


#: module-map の矢印。キーは (使う側, 使われる側) のモジュール名 (パッケージ名を除く)。値は、矢印の折れ線と、ラベル。
#: 実際の依存と一致していることは tests/test_diagrams.py が確かめる (docspipeline map と同じ読み取り)。
BUS = 215
CLI_X = 545


def _bus(cx: float) -> list[tuple[float, float]]:
    """cli から、部品のカードへ降りる折れ線。"""
    if cx == CLI_X:
        return [(CLI_X, 190), (CLI_X, 282)]
    return [(CLI_X, 190), (CLI_X, BUS), (cx, BUS), (cx, 282)]


MODULE_IMPORTS: dict[tuple[str, str], tuple[list[tuple[float, float]], str]] = {
    ("cli", "scaffold"): (_bus(215), ""),
    ("cli", "diagrams"): (_bus(380), ""),
    ("cli", "docstring_coverage"): (_bus(545), ""),
    ("cli", "structure_map"): (_bus(710), ""),
    ("cli", "doctor"): (_bus(875), ""),
    ("cli", "confluence"): ([(CLI_X, 190), (CLI_X, BUS), (1170, BUS), (1170, 282)], ""),
    ("cli", "mmdc"): ([(CLI_X, 190), (CLI_X, BUS), (985, BUS), (985, 540), (925, 540), (925, 572)], "書式の検査"),
    ("doctor", "confluence"): ([(909, 320), (1136, 320)], "モードと環境変数"),
    ("doctor", "mmdc"): ([(875, 402), (875, 446), (900, 446), (900, 572)], "mmdc を探す"),
    ("config", "confluence"): ([(104, 578), (104, 470), (1170, 470), (1170, 412)], "sphinx_settings()"),
    ("mermaid", "mmdc"): ([(395, 696), (395, 728), (900, 728), (900, 704)], "変換を依頼"),
}
#: 名前の文字列による参照 (config が extensions の名前で読み込む)。
#: 図に矢印を描かない依存の行き先 (共通部品)。使うモジュールが多く、矢印が図を埋めてしまうため。
#: 使う側は、カードの説明に書き、tests/test_structure_map.py が実際の依存を検査する。
UTILITY_MODULES = {"files"}
MODULE_REFERENCES: dict[tuple[str, str], list[tuple[float, float]]] = {
    ("config", "guard"): [(255, 545), (255, 576)],
    ("config", "mermaid"): [(395, 545), (395, 576)],
    ("config", "doxygen"): [(535, 545), (535, 576)],
    ("config", "prompt"): [(675, 545), (675, 576)],
}


def module_map() -> Diagram:
    """モジュールの依存: どれがどれを呼ぶか。読む順番の地図。

    矢印は ``MODULE_IMPORTS`` / ``MODULE_REFERENCES`` から作る。実際の依存とのずれは、テストが検出する。
    """
    d = Diagram("module-map", 1340, 830)
    d.panels += [
        Panel(40, 240, 925, 190, "CLI の部品", tab=True),
        Panel(1005, 240, 295, 190, "公開の安全装置", tab=True, fill="#fff7ed", stroke=ORANGE, title_color="#b45309"),
        Panel(
            40,
            500,
            740,
            250,
            "Sphinx に読み込まれる",
            tab=True,
            tab_dx=200,
            dashed=True,
            fill="#e6f4f1",
            stroke=TEAL,
            title_color=TEAL_DARK,
        ),
        Panel(820, 500, 480, 250, "Sphinx なしで動く部品", tab=True, tab_dx=150),
    ]
    d.cards += [
        Card(CLI_X, 100, "cli", "コマンドの入口", "terminal", GRAY),
        Card(215, 320, "scaffold", "init の雛形", "package", GRAY),
        Card(380, 320, "diagrams", "SVG の有無", "diagram", GRAY),
        Card(545, 320, "docstring_coverage", "ast で検査", "check", GRAY),
        Card(710, 320, "structure_map", "依存の地図 (map)", "branch", GRAY),
        Card(875, 320, "doctor", "環境の確認", "wrench", GRAY),
        Card(1170, 320, "confluence", "モード・トークン伏せ字", "lock", ORANGE),
        Card(120, 610, "config", "build_config()", "gear", TEAL),
        Card(255, 610, "guard", "設定エラーの報告", "shield", TEAL),
        Card(395, 610, "mermaid", "Mermaid の指示子", "diagram", TEAL),
        Card(535, 610, "doxygen", "Doxygen → XML", "braces", TEAL),
        Card(675, 610, "prompt", "コピーできる手順", "doc", TEAL),
        Card(900, 610, "mmdc", "mmdc の探索と実行", "plug", GRAY),
        Card(1050, 610, "stubs.hou", "hou のスタブ", "package", GRAY, sub2="sys.path の末尾に足す"),
        Card(1215, 610, "files", "ファイルの列挙 (共通)", "doc", GRAY, sub2="coverage・map・init が使う"),
    ]
    for (src, dst), (points, label) in MODULE_IMPORTS.items():
        d.edges.append(
            Edge(points, label, "blue", label_t={("doctor", "mmdc"): 0.4, ("cli", "mmdc"): 0.8}.get((src, dst), 0.5))
        )
    for points in MODULE_REFERENCES.values():
        d.edges.append(Edge(points, "", "gray", dashed=True))
    d.edges += [
        Edge([(513, 100), (18, 100), (18, 610), (86, 610)], "sphinx を起動", "gray", dashed=True, label_t=0.25),
        Edge([(120, 578), (120, 545), (675, 545)], "extensions", "gray", dashed=True, arrow=False, label_t=0.5),
        Edge([(40, 800), (90, 800)], "", "blue"),
        Edge([(330, 800), (380, 800)], "", "gray", dashed=True),
    ]
    d.notes += [
        Note(102, 805, ["import (関数の呼び出し)"], GRAY, 12),
        Note(392, 805, ["起動・名前による参照"], GRAY, 12),
        Note(1300, 805, ["矢印は実際の依存と一致 (共通部品 files への矢印は省略)"], MUTED_TEXT, 12, "end"),
    ]
    return d


def build_internals() -> Diagram:
    """Sphinx のビルドの内側: どの順に、どのモジュールが働くか。番号は実行順。"""
    d = Diagram("build-internals", 1200, 700)
    d.panels += [Panel(40, 40, 1120, 600, "ビルドの流れ", "sphinx -b html docs (docspipeline build の中身)")]
    d.cards += [
        Card(130, 200, "ビルドを始める", "docspipeline build", "terminal", GRAY, badge=1),
        Card(380, 200, "conf.py を読む", "build_config()", "gear", TEAL, badge=2),
        Card(630, 200, "設定を検査する", "config-inited", "shield", TEAL, badge=3, sub2="guard / mermaid"),
        Card(880, 200, "Doxygen を走らせる", "builder-inited", "braces", TEAL, badge=4, sub2="C++ があるときだけ"),
        Card(130, 450, "Mermaid を画像に", "指示子の実行時", "diagram", TEAL, badge=5, sub2="mmdc → SVG"),
        Card(380, 450, "docstring を読む", "autodoc が import", "book", TEAL, badge=6, sub2="hou はスタブ"),
        Card(630, 450, "参照を解決する", "nitpicky", "link", TEAL, badge=7, sub2="未解決は警告"),
        Card(880, 450, "書き出す", "html / confluence", "globe", ORANGE, badge=8),
    ]
    d.edges += [
        Edge([(164, 200), (346, 200)], "実行", "blue"),
        Edge([(414, 200), (596, 200)], "設定がそろう", "blue"),
        Edge([(664, 200), (846, 200)], "ビルダー起動", "blue"),
        Edge([(914, 200), (1100, 200), (1100, 340), (130, 340), (130, 412)], "", "blue"),
        Edge([(164, 450), (346, 450)], "同じ読み込みの中で", "blue"),
        Edge([(414, 450), (596, 450)], "全部読んだら", "blue"),
        Edge([(664, 450), (846, 450)], "解決できたら", "blue"),
    ]
    d.notes += [
        Note(630, 310, ["エラーなら、ここで止まる", "(設定エラーの報告)"], RED, 12, "middle"),
        Note(130, 560, ["mmdc が無いとき:", "literal / warn / error"], RED, 12, "middle"),
        Note(630, 560, ["-W なら、警告で失敗する"], RED, 12, "middle"),
        Note(880, 310, ["DOCSPIPELINE_SKIP_DOXYGEN=1", "で飛ばせる"], "#667085", 12, "middle", mono=True),
        Note(60, 610, ["読む順の目安: 2 → config.py / 3 → guard.py・mermaid.py / 4 → doxygen.py"], GRAY, 12),
    ]
    return d


DIAGRAMS: dict[str, Callable[[], Diagram]] = {
    "system-overview": system_overview,
    "publish-flow": publish_flow,
    "module-map": module_map,
    "build-internals": build_internals,
}


def render(diagram: Diagram) -> tuple[str, str]:
    """(``.drawio`` の中身, ``.drawio.svg`` の中身) を返す。"""
    xml = diagram.to_drawio()
    return xml, diagram.to_svg(xml.strip())


def main(argv: list[str] | None = None) -> int:
    """図を作り直す。``--check`` では、書き出さずに、生成物との一致だけを確かめる。"""
    args = sys.argv[1:] if argv is None else argv
    check = "--check" in args
    stale = []
    for name, factory in DIAGRAMS.items():
        xml, svg = render(factory())
        for suffix, text in ((".drawio", xml), (".drawio.svg", svg)):
            path = OUT_DIR / f"{name}{suffix}"
            if check:
                if not path.exists() or path.read_text(encoding="utf-8") != text:
                    stale.append(path)
            else:
                OUT_DIR.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                print(f"作成: {path}")
    for path in stale:
        print(f"定義と一致しません: {path} (python tools/diagrams/build_diagrams.py で作り直す)", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
