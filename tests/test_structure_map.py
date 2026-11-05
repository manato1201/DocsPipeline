"""構造の地図 (structure_map) と、それを使った依存の向きの点検。"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from docspipeline import cli, structure_map

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "docspipeline"

#: Sphinx / docutils を import してよいモジュール (Sphinx の拡張)。それ以外は、Sphinx が無くても動くこと。
SPHINX_EXTENSIONS = {"docspipeline.guard", "docspipeline.mermaid", "docspipeline.doxygen", "docspipeline.prompt"}


def _make_package(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "pkg"
    for rel, text in {"__init__.py": '"""p."""\n', **files}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
    return root


# ---- 地図そのもの ----


def test_finds_relative_absolute_and_from_package_imports(tmp_path):
    root = _make_package(
        tmp_path,
        {
            "a.py": '"""A の説明。\n\n詳細。"""\nfrom . import b\nfrom .c import f\nimport pkg.d\nimport json\n',
            "b.py": "from . import c\n",
            "c.py": "def f():\n    pass\n",
            "d.py": "from pkg import c as cc\n",
        },
    )
    g = structure_map.scan_package(root)
    assert g.edges() == {
        ("pkg.a", "pkg.b"),
        ("pkg.a", "pkg.c"),
        ("pkg.a", "pkg.d"),
        ("pkg.b", "pkg.c"),
        ("pkg.d", "pkg.c"),
    }
    assert g.get("pkg.a").summary == "A の説明。"
    assert g.get("pkg.a").external == {"json"}
    assert g.get("pkg.c").public_api == 1


def test_relative_import_inside_a_subpackage(tmp_path):
    root = _make_package(
        tmp_path,
        {"sub/__init__.py": "", "sub/x.py": "from . import y\nfrom .. import top\n", "sub/y.py": "", "top.py": ""},
    )
    g = structure_map.scan_package(root)
    assert g.edges() == {("pkg.sub.x", "pkg.sub.y"), ("pkg.sub.x", "pkg.top")}


def test_import_of_the_package_itself_is_hidden_unless_asked(tmp_path):
    root = _make_package(tmp_path, {"a.py": "from . import __version__\n"})
    g = structure_map.scan_package(root)
    assert g.edges() == set()
    assert g.edges(include_root=True) == {("pkg.a", "pkg")}


def test_string_references_are_found_separately(tmp_path):
    root = _make_package(tmp_path, {"cfg.py": 'EXT = ["pkg.ext", "other.thing"]\n', "ext.py": ""})
    g = structure_map.scan_package(root)
    assert g.edges() == set()
    assert g.edges("reference") == {("pkg.cfg", "pkg.ext")}


def test_cycles_and_entry_points(tmp_path):
    root = _make_package(
        tmp_path, {"a.py": "from . import b\n", "b.py": "from . import a\n", "c.py": "from . import a\n"}
    )
    g = structure_map.scan_package(root)
    assert g.cycles() == [["pkg.a", "pkg.b"]]
    assert g.entry_points() == ["pkg.c"]


def test_no_cycle_in_a_chain(tmp_path):
    root = _make_package(tmp_path, {"a.py": "from . import b\n", "b.py": "from . import c\n", "c.py": ""})
    assert structure_map.scan_package(root).cycles() == []


def test_a_directory_without_init_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="パッケージ"):
        structure_map.scan_package(tmp_path)


def test_renderers(tmp_path):
    root = _make_package(
        tmp_path, {"a.py": '"""説明 | 縦線。"""\nfrom . import b\nX = "pkg.c"\n', "b.py": "", "c.py": ""}
    )
    g = structure_map.scan_package(root)
    mermaid = structure_map.to_mermaid(g)
    assert mermaid.startswith("flowchart LR") and "pkg_a --> pkg_b" in mermaid and "pkg_a -.-> pkg_c" in mermaid
    md = structure_map.to_markdown(g)
    assert "自動生成の下書き" in md and "そのまま公開しないでください" in md and "外部へは何も送信していません" in md
    assert "```mermaid" in md and "説明 \\| 縦線。" in md
    data = json.loads(structure_map.to_json(g))
    assert data["package"] == "pkg" and data["cycles"] == []
    assert next(m for m in data["modules"] if m["name"] == "pkg.a")["imports"] == ["pkg.b"]


# ---- CLI ----


def test_map_command_writes_a_file_and_reports_cycles(tmp_path, capsys):
    root = _make_package(tmp_path, {"a.py": "from . import b\n", "b.py": "from . import a\n"})
    out = tmp_path / "map.md"
    assert cli.main(["map", str(root), "-o", str(out)]) == 0
    assert "pkg_a --> pkg_b" in out.read_text(encoding="utf-8")
    assert "循環があります" in capsys.readouterr().err
    assert cli.main(["map", str(root), "--format", "json", "--fail-on-cycle"]) == 1


def test_map_command_rejects_a_non_package(tmp_path, capsys):
    assert cli.main(["map", str(tmp_path)]) == 2
    assert "パッケージ" in capsys.readouterr().err


# ---- このリポジトリ自身の、依存の向きのルール ----


@pytest.fixture(scope="module")
def graph():
    return structure_map.scan_package(PACKAGE)


def test_no_import_cycles(graph):
    assert graph.cycles() == []


def test_only_sphinx_extensions_import_sphinx(graph):
    # core の CLI (init / coverage / map / doctor) は、Sphinx が入っていない環境でも動くこと
    offenders = {
        m.name: sorted(m.external & {"sphinx", "docutils"})
        for m in graph.modules
        if m.external & {"sphinx", "docutils"}
    }
    assert set(offenders) <= SPHINX_EXTENSIONS, offenders


def test_leaf_modules_import_nothing_internal(graph):
    leaves = ["confluence", "diagrams", "files", "mmdc"]
    for name in leaves:
        assert graph.get(f"docspipeline.{name}").imports == frozenset(), name


def test_file_walkers_depend_only_on_the_shared_listing(graph):
    # ファイルの列挙の規則は files.py の一か所。docstring_coverage・scaffold・structure_map は、それだけを使う
    for name in ("docstring_coverage", "scaffold", "structure_map"):
        assert graph.get(f"docspipeline.{name}").imports == {"docspipeline.files"}, name


def test_cli_does_not_import_the_sphinx_side(graph):
    # CLI は Sphinx を「子プロセス」として起動する。拡張や config を直接 import しない
    forbidden = {"docspipeline.config", *SPHINX_EXTENSIONS}
    assert not (graph.get("docspipeline.cli").imports & forbidden)
    assert not any(m.imports & {"docspipeline.cli"} for m in graph.modules if m.name != "docspipeline.__main__")


def test_the_cli_starts_without_sphinx_installed():
    """Sphinx を隠した状態で、core のモジュールを import できる (doctor 経由で Sphinx を引き込んだ不具合の再発防止)。"""
    code = (
        "import sys\n"
        "for name in ('sphinx', 'docutils', 'myst_parser'):\n"
        "    sys.modules[name] = None\n"
        "import docspipeline.cli, docspipeline.doctor, docspipeline.config, docspipeline.structure_map\n"
        "print('ok')\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False, cwd=ROOT)
    assert result.returncode == 0 and "ok" in result.stdout, result.stderr
