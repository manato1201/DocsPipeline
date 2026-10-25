"""サンプルと、この文書自身を実際に Sphinx でビルドする (遅いので slow)。"""

import os
import shutil
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("sphinx")
pytest.importorskip("myst_parser")

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.slow


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CONFLUENCE_", "DOCSPIPELINE_"))}
    # 外部サイトにつながない。mmdc が PATH に残っていても使わない (偽物か、無いときの挙動を試す)。
    path = f"{Path(sys.executable).parent}{os.pathsep}/usr/bin{os.pathsep}/bin"
    env.update(DOCSPIPELINE_OFFLINE="1", PATH=path)
    env.update(extra)
    return env


def _build(project: Path, builder: str, env: dict[str, str], *extra: str) -> subprocess.CompletedProcess:
    docs = project / "docs"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-W",
            "--keep-going",
            "-b",
            builder,
            *extra,
            str(docs),
            str(docs / "_build" / builder),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _copy_example(name: str, tmp_path: Path) -> Path:
    dest = tmp_path / name
    shutil.copytree(
        ROOT / "examples" / name, dest, ignore=shutil.ignore_patterns("_build", "_generated", "_doxygen", "__pycache__")
    )
    return dest


def _fake_mmdc(path: Path) -> str:
    path.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import sys
            out = sys.argv[sys.argv.index("-o") + 1]
            open(out, "w").write('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
            """
        )
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@pytest.mark.parametrize("builder", ["html", "confluence"])
def test_python_sample_builds_without_warnings(tmp_path, builder):
    project = _copy_example("python_sample", tmp_path)
    result = _build(project, builder, _env(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout


def test_python_sample_documents_the_api_including_hou_users(tmp_path):
    project = _copy_example("python_sample", tmp_path)
    assert _build(project, "html", _env(tmp_path), "-n").returncode == 0  # nitpicky でも通る
    api = (project / "docs" / "_build" / "html" / "api.html").read_text(encoding="utf-8")
    for expected in ("Stopwatch", "measure", "NodeCounter", "count_children", "selected_names"):
        assert expected in api


def test_mermaid_becomes_an_image_when_mmdc_exists(tmp_path):
    project = _copy_example("python_sample", tmp_path)
    env = _env(tmp_path, DOCSPIPELINE_MMDC=_fake_mmdc(tmp_path / "mmdc"), DOCSPIPELINE_MERMAID_MISSING="error")
    html = _build(project, "html", env)
    assert html.returncode == 0, html.stderr + html.stdout
    design = (project / "docs" / "_build" / "html" / "design.html").read_text(encoding="utf-8")
    assert "_images/mermaid-" in design
    conf = _build(project, "confluence", env)
    assert conf.returncode == 0, conf.stderr + conf.stdout
    assert list((project / "docs" / "_build" / "confluence" / "svgs").glob("*.svg"))


def test_mermaid_without_mmdc_falls_back_to_code_by_default(tmp_path):
    project = _copy_example("python_sample", tmp_path)
    assert _build(project, "html", _env(tmp_path)).returncode == 0
    design = (project / "docs" / "_build" / "html" / "design.html").read_text(encoding="utf-8")
    assert "flowchart LR" in design and "_images/mermaid-" not in design


def test_mermaid_without_mmdc_fails_when_required(tmp_path):
    project = _copy_example("python_sample", tmp_path)
    result = _build(project, "html", _env(tmp_path, DOCSPIPELINE_MERMAID_MISSING="error"))
    assert result.returncode != 0
    assert "mmdc" in result.stderr + result.stdout


def test_warnings_fail_the_build(tmp_path):
    project = _copy_example("python_sample", tmp_path)
    (project / "docs" / "overview.rst").write_text("概要\n====\n\n:ref:`存在しない参照`\n", encoding="utf-8")
    assert _build(project, "html", _env(tmp_path)).returncode != 0


@pytest.mark.skipif(shutil.which("doxygen") is None, reason="doxygen が無い")
def test_cpp_sample_pulls_in_doxygen_output(tmp_path):
    project = _copy_example("cpp_sample", tmp_path)
    result = _build(project, "html", _env(tmp_path))
    assert result.returncode == 0, result.stderr + result.stdout
    page = (project / "docs" / "_build" / "html" / "cpp.html").read_text(encoding="utf-8")
    # 関数名が、実際のヘッダーと一致している
    header = (ROOT / "examples" / "cpp_sample" / "include" / "sample_engine" / "index.hpp").read_text(encoding="utf-8")
    for name in ("add", "search", "size"):
        assert f" {name}(" in header
        assert name in page


@pytest.mark.skipif(shutil.which("doxygen") is None, reason="doxygen が無い")
def test_doxygen_comment_errors_become_warnings(tmp_path):
    project = _copy_example("cpp_sample", tmp_path)
    header = project / "include" / "sample_engine" / "index.hpp"
    header.write_text(header.read_text(encoding="utf-8").replace("@param id ", "@param nosuchparam "), encoding="utf-8")
    assert _build(project, "html", _env(tmp_path)).returncode != 0


def test_missing_doxygen_is_an_error_unless_skipped(tmp_path):
    project = _copy_example("cpp_sample", tmp_path)
    env = _env(tmp_path, PATH=str(Path(sys.executable).parent))
    failed = _build(project, "html", env)
    assert failed.returncode != 0 and "doxygen が見つかりません" in failed.stderr + failed.stdout

    docs = project / "docs"
    skipped = subprocess.run(
        [sys.executable, "-m", "sphinx", "-b", "html", str(docs), str(docs / "_build" / "skipped")],
        capture_output=True,
        text=True,
        env={**env, "DOCSPIPELINE_SKIP_DOXYGEN": "1"},
        check=False,
    )
    output = skipped.stdout + skipped.stderr
    assert skipped.returncode == 0, output  # 警告は出るが、ビルドは通る
    assert "Doxygen を飛ばします" in output
    assert "Cannot find file" in output  # 飛ばすと、C++ の指示子は警告になる


def test_a_typo_in_the_mode_is_reported_by_sphinx(tmp_path):
    project = _copy_example("python_sample", tmp_path)
    result = _build(project, "html", _env(tmp_path, DOCSPIPELINE_CONFLUENCE_MODE="publsh"))
    assert result.returncode != 0 and "DOCSPIPELINE_CONFLUENCE_MODE" in result.stderr + result.stdout


def test_docspipeline_documents_itself(tmp_path):
    project = tmp_path / "self"
    shutil.copytree(ROOT / "docs", project / "docs", ignore=shutil.ignore_patterns("_build", "_generated"))
    # conf.py の package_paths ("../") は、リポジトリのルートを指す
    shutil.copytree(ROOT / "docspipeline", project / "docspipeline", ignore=shutil.ignore_patterns("__pycache__"))
    for builder in ("html", "confluence"):
        # 標準ライブラリの型は intersphinx で解決する前提。オフラインでは nitpicky を切って確かめる
        result = _build(project, builder, _env(tmp_path))
        assert result.returncode == 0, result.stderr + result.stdout
