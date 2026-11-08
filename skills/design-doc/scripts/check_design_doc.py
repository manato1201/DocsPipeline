"""設計書 (Markdown) の検査。ひな形どおりに書かれているかを、書き忘れの観点で確かめる。

    python check_design_doc.py 設計書.md

確かめること:

* 必須の見出しがある (``## 目的``・``## 構成``・``## 契約と副作用の境界``・``## 判断の記録``・``## 未確認のこと``)。
* 契約の表がある。列は ``関数 / 層 / 事前条件 / 事後条件 / 不変条件 / 検証するテスト``。
* 表の各行で、層が 純粋 / 読み取り / 書き込み・起動 のどれかで、残りの欄が空でない。
* ひな形の書き換え忘れ (``〈…〉``) が残っていない。コードブロックの中は数えない。

内容が正しいかどうかは、確かめない (書き忘れを見つけるだけ)。標準ライブラリだけで動き、ファイルは読むだけ。
終了コードは、問題が無ければ 0、あれば 1、使い方の誤りは 2。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_HEADINGS = ("目的", "構成", "契約と副作用の境界", "判断の記録", "未確認のこと")
CONTRACT_COLUMNS = ("関数", "層", "事前条件", "事後条件", "不変条件", "検証するテスト")
LAYERS = ("純粋", "読み取り", "書き込み・起動")

_PLACEHOLDER = re.compile(r"〈[^〉]*〉")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")


def _outside_code(text: str) -> list[tuple[int, str]]:
    """コードブロックの外の行を、(行番号, 行) で返す。"""
    lines: list[tuple[int, str]] = []
    fence = ""
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        marker = stripped[:3] if stripped[:3] in ("```", "~~~") else ""
        if marker:
            if not fence:
                fence = marker
            elif marker == fence:
                fence = ""
            continue
        if not fence:
            lines.append((number, line))
    return lines


def _cells(line: str) -> list[str]:
    """表の 1 行を、セルに分ける (前後の ``|`` と空白は除く)。"""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip() for c in body.split("|")]


def check(text: str) -> list[str]:
    """問題の一覧を返す (無ければ空)。同じ入力なら、同じ結果。"""
    problems: list[str] = []
    lines = _outside_code(text)

    headings = {m.group(2) for _, line in lines if (m := _HEADING.match(line)) and len(m.group(1)) == 2}
    problems += [f"見出し「## {name}」がありません" for name in REQUIRED_HEADINGS if name not in headings]

    header_at = next(
        (
            i
            for i, (_, line) in enumerate(lines)
            if line.lstrip().startswith("|") and tuple(_cells(line)) == CONTRACT_COLUMNS
        ),
        None,
    )
    if header_at is None:
        problems.append("契約の表がありません (列: " + " / ".join(CONTRACT_COLUMNS) + ")")
    else:
        rows = []
        for number, line in lines[header_at + 1 :]:
            if not line.lstrip().startswith("|"):
                break
            if _SEPARATOR.match(line.strip()):
                continue
            rows.append((number, _cells(line)))
        if not rows:
            problems.append("契約の表に、行がありません")
        for number, cells in rows:
            if len(cells) != len(CONTRACT_COLUMNS):
                problems.append(f"{number} 行目: 列の数が {len(cells)} です ({len(CONTRACT_COLUMNS)} 列にする)")
                continue
            if _PLACEHOLDER.search(cells[1]) is None and cells[1] not in LAYERS:
                problems.append(f"{number} 行目: 層「{cells[1]}」は、{' / '.join(LAYERS)} のどれかにする")
            for name, value in zip(CONTRACT_COLUMNS[2:], cells[2:], strict=True):
                if not value:
                    problems.append(f"{number} 行目: 「{name}」が空です (ないときは「なし」と、理由を書く)")

    for number, line in lines:
        for match in _PLACEHOLDER.finditer(line):
            problems.append(f"{number} 行目: 書き換え忘れ {match.group(0)}")
    return problems


def main(argv: list[str] | None = None) -> int:
    """コマンドの入口。問題を 1 行ずつ出して、あれば 1 を返す。"""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("使い方: python check_design_doc.py 設計書.md", file=sys.stderr)
        return 2
    path = Path(args[0])
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"読めません: {path} ({exc.strerror})", file=sys.stderr)
        return 2
    problems = check(text)
    for problem in problems:
        print(f"{path}: {problem}")
    if problems:
        print(f"{len(problems)} 件の問題があります", file=sys.stderr)
        return 1
    print(f"{path}: 問題なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
