"""講義資料 (docs/lecture/) の、コードの引用と、実行できるコードの検査。

講義の説明が、コードの変更で嘘にならないようにする。
- ``# 引用:`` のブロックは、今のソースと **完全に一致** する
- ``# 抜粋:`` のブロックの各行は、そのソースに、この順で現れる
- ``# 実行できる`` のブロックは、実際に実行でき、直後の ``# 出力`` のブロックと、標準出力が一致する
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import quote_code  # noqa: E402

LECTURES = sorted((ROOT / "docs" / "lecture").glob("*.md"))
REQUIRED_SECTIONS = ("## この回のゴール", "## 確認問題", "## 解答", "## まとめ")


# ---- 道具そのもの ----


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text(
        textwrap.dedent(
            '''\
            def f(x):
                """二倍。"""
                return x * 2


            class C:
                def method(self):
                    return 1

                def other(self):
                    return 2
            '''
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_source_of_finds_functions_classes_and_methods(tmp_path):
    root = _repo(tmp_path)
    assert quote_code.source_of("pkg/m.py::f", root).startswith("def f(x):\n    ")
    assert quote_code.source_of("pkg/m.py::C.method", root) == "def method(self):\n    return 1"
    assert quote_code.source_of("pkg/m.py::C", root).startswith("class C:")
    with pytest.raises(KeyError):
        quote_code.source_of("pkg/m.py::nope", root)
    with pytest.raises(FileNotFoundError):
        quote_code.source_of("pkg/none.py::f", root)


def test_placeholder_is_expanded_and_then_checks_clean(tmp_path):
    root = _repo(tmp_path)
    text = "前\n\n@@引用 pkg/m.py::f@@\n\n後\n"
    assert quote_code.problems(text, root) == ["3: 展開されていない引用のプレースホルダー"]
    expanded = quote_code.refresh(text, root)
    assert "# 引用: pkg/m.py::f" in expanded and "return x * 2" in expanded and "@@" not in expanded
    assert quote_code.problems(expanded, root) == []
    assert quote_code.refresh(expanded, root) == expanded  # 何度やっても同じ


def test_drift_is_detected_and_refresh_repairs_it(tmp_path):
    root = _repo(tmp_path)
    expanded = quote_code.refresh("@@引用 pkg/m.py::f@@\n", root)
    (root / "pkg" / "m.py").write_text(
        (root / "pkg" / "m.py").read_text(encoding="utf-8").replace("x * 2", "x * 3"), encoding="utf-8"
    )
    assert any("今のソースと違う" in p for p in quote_code.problems(expanded, root))
    assert quote_code.problems(quote_code.refresh(expanded, root), root) == []


def test_excerpt_lines_must_exist_in_order(tmp_path):
    root = _repo(tmp_path)
    ok = "```python\n# 抜粋: pkg/m.py::f\ndef f(x):\n    ...\n    return x * 2\n```\n"
    assert quote_code.problems(ok, root) == []
    wrong_order = "```python\n# 抜粋: pkg/m.py::f\nreturn x * 2\ndef f(x):\n```\n"
    assert quote_code.problems(wrong_order, root)
    invented = "```python\n# 抜粋: pkg/m.py::f\ndef f(x):\n    return x * 99\n```\n"
    assert quote_code.problems(invented, root)


def test_nested_fences_are_one_block():
    text = "````text\n```python\nx\n```\n````\n\n```python\ny\n```\n"
    blocks = quote_code.fenced_blocks(text)
    assert len(blocks) == 2 and blocks[0].lines[0] == "```python" and blocks[1].lines == ["y"]


# ---- 講義そのもの ----


def test_there_are_lectures():
    assert len(LECTURES) >= 14, "講義資料が足りない"


@pytest.mark.parametrize("path", LECTURES, ids=lambda p: p.name)
def test_quotes_and_excerpts_match_the_current_source(path):
    assert quote_code.problems(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("path", [p for p in LECTURES if p.name != "index.md"], ids=lambda p: p.name)
def test_every_lecture_has_the_standard_sections(path):
    text = path.read_text(encoding="utf-8")
    for heading in REQUIRED_SECTIONS:
        assert heading in text, f"{path.name}: 「{heading}」が無い"


def _runnable(path: Path):
    blocks = quote_code.fenced_blocks(path.read_text(encoding="utf-8"))
    for i, block in enumerate(blocks):
        if block.lines and block.lines[0].strip() == quote_code.RUN_MARK:
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            expected = None
            if nxt and nxt.lines and nxt.lines[0].strip() == quote_code.OUTPUT_MARK:
                expected = "\n".join(nxt.lines[1:]).strip()
            yield block.start + 1, "\n".join(block.lines[1:]), expected


@pytest.mark.parametrize("path", LECTURES, ids=lambda p: p.name)
def test_runnable_examples_run_and_print_what_the_lecture_says(path, tmp_path):
    # 2 回走らせる。-I はハッシュの種を毎回ランダムにするので、集合の順序などに頼る例は、どちらかで食い違う
    for line, code, expected in _runnable(path):
        for _attempt in range(2):
            result = subprocess.run(
                [sys.executable, "-I", "-c", code],
                capture_output=True,
                text=True,
                cwd=tmp_path,
                timeout=60,
                check=False,
            )
            assert result.returncode == 0, f"{path.name}:{line}: 実行に失敗\n{result.stderr}"
            if expected is not None:
                assert result.stdout.strip() == expected, (
                    f"{path.name}:{line}: 出力が講義の記述と違う (実行ごとに変わる出力かもしれない)\n{result.stdout}"
                )


def test_runnable_examples_exist_in_total():
    total = sum(len(list(_runnable(p))) for p in LECTURES)
    assert total >= 30, f"実行できる例が少ない ({total})"
