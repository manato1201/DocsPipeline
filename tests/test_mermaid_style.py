"""Mermaid ブロックの書式の統一 (標準の ``%%{init}%%`` の行)。"""

import json

from docspipeline import cli, mmdc

INIT = mmdc.MERMAID_INIT


def run(*argv):
    return cli.main(list(argv))


def test_the_standard_init_line_is_valid_mermaid_init_json():
    assert INIT.startswith("%%{init: ") and INIT.endswith("}%%")
    config = json.loads(INIT.removeprefix("%%{init: ").removesuffix("}%%"))
    assert config["theme"] == "base"
    assert config["themeVariables"]["fontFamily"] == config["fontFamily"] == mmdc.FONT_FAMILY
    assert "\n" not in INIT  # 1 行であること (GitHub が読む)


def test_mmdc_config_matches_the_init_line_so_both_renderers_look_alike():
    config = mmdc.MERMAID_CONFIG
    assert config["theme"] == "base" and config["themeVariables"] == mmdc.THEME_VARIABLES
    assert config["flowchart"]["htmlLabels"] is False  # Confluence でも文字が消えないように、SVG の text で描く


def test_blocks_are_found_with_any_fence_length_and_the_directive_form():
    text = (
        "a\n```mermaid\nflowchart LR\n```\n\n"
        "````mermaid\ngraph TD\n````\n\n"
        "```{mermaid}\nflowchart LR\n```\n\n"
        "```python\nx = 1\n```\n"
    )
    assert [s for s, _ in mmdc.mermaid_blocks(text.splitlines())] == [1, 5, 9]


def test_check_reports_blocks_without_the_init_line():
    text = f"```mermaid\nflowchart LR\n```\n\n```mermaid\n{INIT}\nflowchart LR\n```\n"
    assert mmdc.check_mermaid_text(text) == [1]


def test_fix_inserts_the_line_and_is_idempotent():
    text = "# 題\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\n本文\n"
    fixed = mmdc.fix_mermaid_text(text)
    assert fixed == f"# 題\n\n```mermaid\n{INIT}\nflowchart LR\n  A --> B\n```\n\n本文\n"
    assert mmdc.check_mermaid_text(fixed) == []
    assert mmdc.fix_mermaid_text(fixed) == fixed


def test_fix_replaces_a_different_init_line():
    text = '```mermaid\n%%{init: {"theme":"dark"}}%%\nflowchart LR\n```\n'
    fixed = mmdc.fix_mermaid_text(text)
    assert fixed == f"```mermaid\n{INIT}\nflowchart LR\n```\n"


def test_fix_keeps_the_indent_of_an_indented_block():
    fixed = mmdc.fix_mermaid_text("- 項目\n\n  ```mermaid\n  flowchart LR\n  ```\n")
    assert f"  {INIT}\n" in fixed


def test_other_code_blocks_and_text_are_untouched():
    text = "```bash\n$ ls\n```\n\n本文に ```mermaid という語があっても\n"
    assert mmdc.fix_mermaid_text(text) == text and mmdc.check_mermaid_text(text) == []


def test_unclosed_block_does_not_hang():
    assert mmdc.check_mermaid_text("```mermaid\nflowchart LR\n") == [1]


def test_check_mermaid_command(tmp_path, capsys):
    good = tmp_path / "good.md"
    bad = tmp_path / "docs" / "bad.md"
    bad.parent.mkdir()
    good.write_text(f"```mermaid\n{INIT}\nflowchart LR\n```\n", encoding="utf-8")
    bad.write_text("```mermaid\nflowchart LR\n```\n", encoding="utf-8")
    skipped = tmp_path / "_build" / "x.md"
    skipped.parent.mkdir()
    skipped.write_text("```mermaid\nflowchart LR\n```\n", encoding="utf-8")

    assert run("check-mermaid", str(tmp_path)) == 1
    err = capsys.readouterr()
    assert "bad.md:1" in err.out and "good.md" not in err.out and "_build" not in err.out

    assert run("check-mermaid", str(tmp_path), "--fix") == 0
    assert run("check-mermaid", str(tmp_path)) == 0
    assert INIT in bad.read_text(encoding="utf-8")
    assert INIT not in skipped.read_text(encoding="utf-8")  # 生成物は触らない


def test_check_mermaid_on_a_missing_path_is_an_error(tmp_path, capsys):
    assert run("check-mermaid", str(tmp_path / "nope")) == 2
    assert "パスがありません" in capsys.readouterr().err


def test_mermaid_style_command_prints_paste_ready_text(capsys):
    assert run("mermaid-style") == 0
    out = capsys.readouterr().out
    assert out.startswith(INIT) and "classDef input" in out and "classDef stop" in out
