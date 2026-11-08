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
    (tmp_path / "src").mkdir()
    assert run("init", str(tmp_path), "--project", "A", "--author", "me", "--package", "../src") == 0
    workflow = (tmp_path / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    assert "docspipeline coverage src --fail-under 80" in workflow


def test_min_coverage_is_configurable(tmp_path):
    (tmp_path / "src").mkdir()
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


# ---- 増分ビルドで、方針が素通りしない ----


def test_publish_and_required_mermaid_rebuild_from_scratch(tmp_path, monkeypatch):
    """-E (保存済みの環境を使わない) が付く。付けないと、前のビルドが「コードのまま」で済ませたページが、
    変更なしとして飛ばされ、Mermaid の方針 (画像にならなければ失敗) が効かない。"""
    for name in confluence.REQUIRED_ENV:
        monkeypatch.setenv(name, "x" * 12)
    calls = []
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: calls.append(list(cmd)) or 0)
    run("publish", str(tmp_path), "--mode", "publish", "--skip-connection-test")
    run("publish", str(tmp_path), "--mode", "dryrun", "--skip-connection-test")
    run("build", str(tmp_path), "--require-mermaid")
    run("publish", str(tmp_path))  # local
    run("build", str(tmp_path))
    assert ["-E" in c for c in calls] == [True, True, True, False, False]


# ---- Windows のパス・存在確認 ----


def test_split_command_keeps_backslashes_on_windows():
    path = r"C:\Users\me\node_modules\.bin\mmdc.cmd"
    assert mmdc.split_command(path, windows=True) == [path]
    assert mmdc.split_command(f'"{path}" --flag', windows=True) == [path, "--flag"]
    assert mmdc.split_command("npx --no-install mmdc", windows=False) == ["npx", "--no-install", "mmdc"]
    assert mmdc.split_command(r"a\ b", windows=False) == ["a b"]  # POSIX では、従来どおり


def test_command_exists(tmp_path):
    script = _write(tmp_path / "tool", "#!/bin/sh\n")
    assert mmdc.command_exists([str(script), "--flag"])
    assert mmdc.command_exists([sys.executable])
    assert not mmdc.command_exists([str(tmp_path / "nope")])
    assert not mmdc.command_exists([])


def test_doctor_does_not_report_a_nonexistent_mmdc_as_ok():
    from docspipeline import doctor

    checks = doctor.run_checks({"DOCSPIPELINE_MMDC": "/nonexistent/mmdc"})
    check = next(c for c in checks if c.name.startswith("mmdc"))
    assert not check.ok and "見つからない" in check.detail


# ---- 非公開のモジュールは、docstring の対象外 ----


def test_private_modules_are_not_counted(tmp_path):
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", '"""p."""\n')
    _write(pkg / "_compat.py", "def shim():\n    pass\n")
    _write(pkg / "_impl" / "__init__.py", "")
    _write(pkg / "_impl" / "core.py", "def run():\n    pass\n")
    _write(pkg / "public.py", '"""p."""\ndef api():\n    "d"\n')
    report = docstring_coverage.scan([pkg])
    assert {i.qualname for i in report.items} == {"pkg", "pkg.public", "pkg.public.api"}
    assert report.percent == 100.0


def test_a_package_init_is_still_counted(tmp_path):
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    assert [i.documented for i in docstring_coverage.scan([pkg]).items] == [False]


# ---- 型検査用・関数の中の import は、実行時の循環ではない ----


def test_type_checking_import_is_not_a_dependency(tmp_path):
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    _write(pkg / "a.py", "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from .b import B\n")
    _write(pkg / "b.py", "from .a import A\n")
    graph = structure_map.scan_package(pkg)
    assert graph.cycles() == []
    assert graph.edges() == {("pkg.b", "pkg.a")}


def test_function_local_import_is_deferred_and_does_not_make_a_cycle(tmp_path):
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    _write(pkg / "a.py", "def f():\n    from . import b\n")
    _write(pkg / "b.py", "from . import a\n")
    graph = structure_map.scan_package(pkg)
    assert graph.cycles() == []
    assert graph.edges("deferred") == {("pkg.a", "pkg.b")}
    assert graph.edges() == {("pkg.b", "pkg.a")}
    assert "-. 遅延 .->" in structure_map.to_mermaid(graph)


def test_else_branch_of_type_checking_is_still_read(tmp_path):
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    _write(pkg / "a.py", "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    pass\nelse:\n    from . import b\n")
    _write(pkg / "b.py", "")
    assert structure_map.scan_package(pkg).edges() == {("pkg.a", "pkg.b")}


# ---- init: 打ち間違い・特殊な名前・不要なディレクトリ ----


def test_init_rejects_a_mistyped_source_path(tmp_path, capsys):
    assert run("init", str(tmp_path), "--project", "X", "--author", "me", "--package", "../scr") == 2
    assert "ソースの場所がありません" in capsys.readouterr().err
    assert not (tmp_path / "docs").exists()  # 何も書かずに止まる


def test_init_with_awkward_project_names_still_writes_valid_python(tmp_path):
    name = 'A"""B\\C @@author_repr@@ \'q\''
    assert run("init", str(tmp_path), "--project", name, "--author", "o'brien") == 0
    namespace: dict = {}
    source = (tmp_path / "docs" / "conf.py").read_text(encoding="utf-8")
    compile(source, "conf.py", "exec")
    assert repr(name) in source and "@@" not in source.replace(repr(name), "")
    assert namespace == {}


def test_values_are_not_substituted_twice(tmp_path):
    opts = scaffold.Options(target=tmp_path, project="@@author_repr@@", author="me")
    index = next(text for path, text in scaffold.plan(opts).items() if path.name == "index.rst")
    assert index.splitlines()[0] == "@@author_repr@@"


def test_api_modules_skip_virtualenvs_and_vendored_code(tmp_path):
    root = tmp_path / "src"
    _write(root / "pkg" / "__init__.py", "")
    _write(root / "pkg" / "core.py", "")
    _write(root / ".venv" / "lib" / "junk" / "__init__.py", "")
    _write(root / "node_modules" / "x" / "y.py", "")
    text = scaffold.api_modules(tmp_path / "docs", ["../src"])
    assert "pkg.core" in text and "junk" not in text and "node_modules" not in text


# ---- CI の設定: トークンの渡し方・版の固定 ----


def _workflows(tmp_path):
    yaml = pytest.importorskip("yaml")
    root = Path(__file__).resolve().parent.parent
    template = root / "docspipeline" / "templates" / "project" / "github" / "workflows" / "docs.yml.tmpl"
    filled = template.read_text(encoding="utf-8").replace("@@doxygen_step@@", "").replace("@@coverage_step@@", "")
    return {
        "ci.yml": yaml.safe_load((root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")),
        "docs.yml.tmpl": yaml.safe_load(filled),
    }


def test_the_api_token_reaches_only_the_publish_step(tmp_path):
    """トークンを job 全体の env に置くと、pip / npm のインストール scripts (依存の更新で変わりうる) からも読める。"""
    for name, workflow in _workflows(tmp_path).items():
        job = workflow["jobs"]["publish"]
        assert "CONFLUENCE_API_TOKEN" not in job.get("env", {}), name
        holders = [s for s in job["steps"] if "CONFLUENCE_API_TOKEN" in s.get("env", {})]
        assert [s["name"] for s in holders] == ["Publish to Confluence"], name
        assert "secrets.CONFLUENCE_API_TOKEN" in holders[0]["env"]["CONFLUENCE_API_TOKEN"], name


def test_the_token_is_not_given_to_the_jobs_that_run_on_every_pull_request(tmp_path):
    for name, workflow in _workflows(tmp_path).items():
        for job_name, job in workflow["jobs"].items():
            if job_name == "publish":
                continue
            text = repr(job) + repr(workflow.get("env", {}))
            assert "CONFLUENCE_API_TOKEN" not in text, (name, job_name)


def test_npm_installs_are_pinned_to_a_version():
    root = Path(__file__).resolve().parent.parent
    for path in (
        root / ".github" / "workflows" / "ci.yml",
        root / "docspipeline" / "templates" / "project" / "github" / "workflows" / "docs.yml.tmpl",
    ):
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if "npm install" in ln]
        assert lines, path
        for line in lines:
            assert "@mermaid-js/mermaid-cli@" in line and line.rstrip()[-1].isdigit(), (path.name, line)
