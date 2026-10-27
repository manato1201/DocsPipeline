"""レビューで見つかった不備の再発防止。

どれも「黙って成功する」「原因の分からない落ち方をする」種類の不備で、CI の関門が空になる恐れがあった。
"""

import sys
import textwrap
from pathlib import Path

import pytest

from docspipeline import cli, confluence, diagrams, docstring_coverage, mmdc, scaffold, structure_map


def run(*argv):
    return cli.main(list(argv))


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


# ---- 打ち間違いで、検査が黙って空にならない ----


def test_coverage_of_a_missing_path_is_an_error_not_100_percent(tmp_path, capsys):
    assert run("coverage", str(tmp_path / "srcc"), "--fail-under", "80") == 2
    assert "パスがありません" in capsys.readouterr().err
    with pytest.raises(ValueError, match="パスがありません"):
        docstring_coverage.scan([tmp_path / "nothing"])


def test_check_diagrams_on_a_missing_directory_is_an_error(tmp_path, capsys):
    assert run("check-diagrams", str(tmp_path / "dcos")) == 2
    assert "ディレクトリがありません" in capsys.readouterr().err


def test_check_diagrams_skips_generated_and_vendored_directories(tmp_path):
    for rel in ("_generated/a.drawio", "node_modules/pkg/b.drawio", ".hidden/c.drawio", "_doxygen/d.drawio"):
        _write(tmp_path / rel, "<x/>")
    _write(tmp_path / "real.drawio", "<x/>")
    assert [p.name for p in diagrams.find_missing_exports(tmp_path)] == ["real.drawio"]


# ---- 構文エラーは、スタックトレースではなく、場所つきのエラー ----


def test_syntax_errors_name_the_file_and_line(tmp_path, capsys):
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", '"""p."""\n')
    _write(pkg / "bad.py", "x = 1\ndef f(:\n")
    for command in (["coverage", str(pkg)], ["map", str(pkg)]):
        assert run(*command) == 2, command
        err = capsys.readouterr().err
        assert "bad.py:2: 構文エラー" in err and "Traceback" not in err


def test_a_syntax_error_is_not_confused_with_a_cycle(tmp_path):
    # --fail-on-cycle の終了コード 1 と、構文エラーの 2 は区別できる
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    _write(pkg / "bad.py", "def f(:\n")
    assert run("map", str(pkg), "--fail-on-cycle") == 2


# ---- import の循環は、パッケージ自身 (__init__) を経由するものも見つける ----


def test_cycle_through_the_package_init_is_detected(tmp_path):
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "from .a import X\n")
    _write(pkg / "a.py", "from . import Y\nX = 1\n")
    graph = structure_map.scan_package(pkg)
    assert graph.cycles() == [["pkg", "pkg.a"]]
    assert run("map", str(pkg), "--format", "json", "--fail-on-cycle") == 1


def test_importing_the_package_version_is_not_a_cycle(tmp_path):
    # 子が __init__ の定数を読むだけ (__init__ は子を import しない) なら、循環ではない
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", '__version__ = "1"\n')
    _write(pkg / "a.py", "from . import __version__\n")
    assert structure_map.scan_package(pkg).cycles() == []


# ---- __all__ の書き方 ----


def _report(tmp_path, source):
    path = _write(tmp_path / "m.py", source)
    return {i.qualname: i.documented for i in docstring_coverage.scan_file(path)}


def test_all_with_a_type_annotation_is_honoured(tmp_path):
    items = _report(tmp_path, '"""m."""\n__all__: list[str] = ["a"]\ndef a():\n    "d"\ndef b():\n    pass\n')
    assert "m.b" not in items and items["m.a"] is True


def test_all_extended_with_plus_equals_is_honoured(tmp_path):
    items = _report(
        tmp_path,
        '"""m."""\n__all__ = ["a"]\n__all__ += ["b"]\ndef a():\n    pass\ndef b():\n    pass\ndef c():\n    pass\n',
    )
    assert {"m.a", "m.b"} <= set(items) and "m.c" not in items


def test_all_that_cannot_be_read_statically_counts_everything(tmp_path):
    items = _report(tmp_path, '"""m."""\n__all__ = [name for name in dir()]\ndef a():\n    pass\n')
    assert "m.a" in items


# ---- publish は、図が画像にならなければ失敗させる ----


def test_publish_beyond_local_requires_mermaid_images(tmp_path, monkeypatch):
    for name in confluence.REQUIRED_ENV:
        monkeypatch.setenv(name, "x" * 12)
    calls = []
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: calls.append((list(cmd), env or {})) or 0)
    assert run("publish", str(tmp_path), "--mode", "dryrun", "--skip-connection-test") == 0
    assert run("publish", str(tmp_path), "--mode", "publish", "--skip-connection-test") == 0
    assert run("publish", str(tmp_path)) == 0  # local
    dryrun, publish, local = (env for _, env in calls)
    assert dryrun["DOCSPIPELINE_MERMAID_MISSING"] == "error"
    assert publish["DOCSPIPELINE_MERMAID_MISSING"] == "error"
    assert "DOCSPIPELINE_MERMAID_MISSING" not in local


# ---- init が作る CI の、docstring の関門は、実際に落ちる ----


def test_generated_ci_coverage_step_can_fail(tmp_path):
    assert run("init", str(tmp_path), "--project", "A", "--author", "me", "--package", "../src") == 0
    workflow = (tmp_path / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    assert "docspipeline coverage src --fail-under 80" in workflow


def test_min_coverage_is_configurable(tmp_path):
    assert (
        run("init", str(tmp_path), "--project", "A", "--author", "me", "--package", "../src", "--min-coverage", "95")
        == 0
    )
    assert "--fail-under 95" in (tmp_path / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")


def test_coverage_paths_use_forward_slashes_and_are_quoted(tmp_path):
    opts = scaffold.Options(target=tmp_path, project="A", author="me", package=("../my src/lib",))
    workflow = next(text for path, text in scaffold.plan(opts).items() if path.name == "docs.yml")
    assert "docspipeline coverage 'my src/lib' --fail-under 80" in workflow


# ---- 外部コマンドの出力・Windows ----


def test_child_output_with_undecodable_bytes_does_not_crash(capsys):
    code = "import sys; sys.stdout.buffer.write(b'ok \\xff\\xfe done\\n')"
    assert cli._run([sys.executable, "-c", code]) == 0
    out = capsys.readouterr().out
    assert "ok" in out and "done" in out


def test_find_mmdc_prefers_the_cmd_shim_on_windows(tmp_path, monkeypatch):
    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "mmdc").write_text("")
    (bin_dir / "mmdc.cmd").write_text("")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv(mmdc.MMDC_ENV, raising=False)
    assert mmdc.find_mmdc(None, tmp_path) == [str(bin_dir / "mmdc")]
    monkeypatch.setattr(mmdc.sys, "platform", "win32")
    monkeypatch.setattr(
        mmdc.shutil, "which", lambda name: None
    )  # sys.platform の偽装で、which が Windows 用の処理に入らないように
    assert mmdc.find_mmdc(None, tmp_path) == [str(bin_dir / "mmdc.cmd")]
