"""設計書のひな形のスキル (``skills/design-doc``) と、その検査スクリプト。"""

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "design-doc"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_design_doc", SKILL / "scripts" / "check_design_doc.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()

VALID = """\
# X 設計書

## 目的

何かを実現する。

## 構成

流れ。

## 契約と副作用の境界

| 関数 | 層 | 事前条件 | 事後条件 | 不変条件 | 検証するテスト |
|---|---|---|---|---|---|
| `m.f` | 純粋 | なし | 値を返す | 冪等 | `tests/test_m.py::test_f` |
| `m.g` | 書き込み・起動 | 既存が無い | ファイルを作る | 既存を壊さない | `tests/test_m.py::test_g` |

## 判断の記録

決めたこと。

## 未確認のこと

* 実機。
"""


# ---- スキルの形式 ----


def _front_matter(text: str) -> dict[str, str]:
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md の先頭に、--- で囲んだ front matter が要る"
    return dict(line.split(":", 1) for line in match.group(1).splitlines())


def test_skill_has_the_required_front_matter():
    meta = {k.strip(): v.strip() for k, v in _front_matter((SKILL / "SKILL.md").read_text(encoding="utf-8")).items()}
    assert meta["name"] == SKILL.name == "design-doc"  # フォルダ名と同じ
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", meta["name"])
    assert 0 < len(meta["description"]) <= 1024
    assert set(meta) == {"name", "description"}


def test_skill_links_point_to_existing_files():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)#]+)\)", text)
    assert {"template.md", "scripts/check_design_doc.py"} <= set(targets)
    for target in targets:
        assert (SKILL / target).is_file(), target


def test_skill_does_not_ask_to_copy_external_text():
    """外部のコード・文章を写さない約束 (設計書: 構造と考え方だけを取り入れる) を、スキル自身が書いている。"""
    assert "写さない" in (SKILL / "SKILL.md").read_text(encoding="utf-8")


# ---- 検査 ----


def test_a_complete_document_passes():
    assert checker.check(VALID) == []


def test_the_template_has_the_required_structure_and_only_placeholders_remain():
    """ひな形は、構造として正しく、残る問題は「書き換え忘れ」だけ。写したまま出すと検査が落ちる。"""
    problems = checker.check((SKILL / "template.md").read_text(encoding="utf-8"))
    assert problems, "ひな形をそのまま出しても通ってしまう"
    assert all("書き換え忘れ" in p for p in problems), problems


def test_the_template_headings_match_the_design_page_template_of_init():
    """``docspipeline init`` が作る設計ページの見出しと、ひな形の見出しが食い違わない。"""
    init_template = (ROOT / "docspipeline/templates/project/docs/design.rst.tmpl").read_text(encoding="utf-8")
    template = (SKILL / "template.md").read_text(encoding="utf-8")
    for heading in ("構成", "契約と副作用の境界", "判断の記録"):
        assert re.search(rf"^{heading}\n-+$", init_template, re.MULTILINE), heading
        assert f"## {heading}" in template, heading


@pytest.mark.parametrize("heading", checker.REQUIRED_HEADINGS)
def test_each_missing_heading_is_reported(heading):
    problems = checker.check(VALID.replace(f"## {heading}", f"## {heading}の別名"))
    assert any(f"「## {heading}」" in p for p in problems), problems


def test_missing_contract_table_is_reported():
    broken = VALID.replace("| 関数 | 層 | 事前条件 | 事後条件 | 不変条件 | 検証するテスト |", "| 関数 | 層 |")
    assert any("契約の表がありません" in p for p in checker.check(broken))


def test_unknown_layer_is_reported_with_its_line():
    problems = checker.check(VALID.replace("| 純粋 |", "| 副作用なし |"))
    assert len(problems) == 1 and "層「副作用なし」" in problems[0] and "15 行目" in problems[0], problems


@pytest.mark.parametrize("column", ["事前条件", "事後条件", "不変条件", "検証するテスト"])
def test_empty_cells_are_reported_per_column(column):
    index = checker.CONTRACT_COLUMNS.index(column)
    cells = ["`m.f`", "純粋", "なし", "値を返す", "冪等", "`tests/test_m.py::test_f`"]
    cells[index] = ""
    row = "| " + " | ".join(cells) + " |"
    problems = checker.check(
        VALID.replace("| `m.f` | 純粋 | なし | 値を返す | 冪等 | `tests/test_m.py::test_f` |", row)
    )
    assert len(problems) == 1 and f"「{column}」が空" in problems[0], problems


def test_wrong_column_count_is_reported():
    problems = checker.check(VALID.replace("| `m.f` | 純粋 | なし |", "| `m.f` | 純粋 |"))
    assert any("列の数" in p for p in problems), problems


def test_a_table_with_only_a_header_is_reported():
    header_only = "\n".join(line for line in VALID.splitlines() if not line.startswith("| `m."))
    assert any("行がありません" in p for p in checker.check(header_only))


def test_placeholders_are_found_but_not_inside_code_blocks():
    assert any("書き換え忘れ 〈ここ〉" in p for p in checker.check(VALID + "\n〈ここ〉\n"))
    # 書き方の例としてコードブロックに書いた `〈…〉` は、書き換え忘れではない
    assert checker.check(VALID + "\n```\n〈ここ〉\n```\n") == []
    assert checker.check(VALID + "\n~~~\n〈ここ〉\n~~~\n") == []


def test_check_is_deterministic_and_does_not_change_its_input():
    text = VALID.replace("| 純粋 |", "| x |") + "\n〈a〉\n"
    assert checker.check(text) == checker.check(text)


def test_the_repository_contract_table_passes_the_same_rules():
    """このリポジトリ自身の契約の表 (docs/contracts.md) が、検査の規則を満たす。規則が実態から離れていない証拠。"""
    problems = checker.check((ROOT / "docs" / "contracts.md").read_text(encoding="utf-8"))
    table_problems = [p for p in problems if not p.startswith("見出し")]
    assert table_problems == []


# ---- コマンド ----


def test_main_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.md"
    good.write_text(VALID, encoding="utf-8")
    assert checker.main([str(good)]) == 0
    assert "問題なし" in capsys.readouterr().out

    bad = tmp_path / "bad.md"
    bad.write_text(VALID.replace("## 目的", "## 趣旨"), encoding="utf-8")
    assert checker.main([str(bad)]) == 1
    captured = capsys.readouterr()
    assert "「## 目的」" in captured.out and "1 件" in captured.err

    assert checker.main([]) == 2
    assert checker.main([str(tmp_path / "none.md")]) == 2
    assert "読めません" in capsys.readouterr().err


def test_the_checker_only_reads(tmp_path):
    doc = tmp_path / "d.md"
    doc.write_text(VALID, encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    checker.main([str(doc)])
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
