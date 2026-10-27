"""``docspipeline init``: 対象リポジトリに ``docs/`` の雛形と CI の設定を作る。

雛形は ``docspipeline/templates/project`` にあり、``@@名前@@`` の印を値に置き換えて書き出す。
点で始まるファイルはパッケージのデータに含まれないことがあるので、雛形の側では点を付けない
(``gitignore.tmpl`` → ``.gitignore``)。
"""

from __future__ import annotations

import os
import pathlib
import shlex
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

TEMPLATES = Path(__file__).parent / "templates" / "project"

_DOXYGEN_STEP = """      - name: Install Doxygen
        run: sudo apt-get update && sudo apt-get install -y doxygen
"""

_COVERAGE_STEP = """      - name: Docstring coverage
        run: docspipeline coverage {paths} --fail-under {minimum}
"""


class ScaffoldError(Exception):
    """雛形を作れないときの例外。既存のファイルがあるときに投げる。"""

    def __init__(self, existing: list[pathlib.Path]) -> None:
        """既存のファイルの一覧から、メッセージを作る。"""
        super().__init__(f"既にあります: {', '.join(str(p) for p in existing)}")
        self.existing = existing


@dataclass(frozen=True)
class Options:
    """``init`` の入力。"""

    target: Path
    project: str
    author: str
    package: tuple[str, ...] = ()
    cpp: tuple[str, ...] = ()
    hou: bool = False
    min_coverage: int = 80


def title_rule(text: str) -> str:
    """reStructuredText の見出しの下線を返す。

    全角の文字は幅 2 として数える。足りないと docutils が警告するため。
    """
    width = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return "=" * max(width, 4)


def python_modules(source_root: Path) -> list[str]:
    """``source_root`` の下にある公開モジュールの名前を返す (``import`` はしない)。

    ``_`` で始まる名前と、``tests`` / ``test`` の下は除く。
    """
    names = []
    for path in sorted(source_root.rglob("*.py")):
        parts = list(path.relative_to(source_root).with_suffix("").parts)
        if any(p.startswith("_") and p != "__init__" for p in parts) or any(p in ("tests", "test") for p in parts):
            continue
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            names.append(".".join(parts))
    return names


def api_modules(docs: Path, package_paths: Sequence[str]) -> str:
    """``api.rst`` に並べる ``automodule`` の指示子を作る。

    子のモジュールがあるパッケージは、``__init__`` の再公開で同じ項目が二重に出るのを避けるため
    ``:no-members:`` にする。
    """
    blocks = []
    for rel in package_paths:
        root = (docs / rel).resolve()
        if not root.is_dir():
            continue
        names = python_modules(root)
        for name in names:
            has_children = any(other.startswith(name + ".") for other in names)
            options = "   :no-members:\n" if has_children else ""
            blocks.append(f"\n.. automodule:: {name}\n{options}")
    return "".join(blocks)


def _py_list(items: Sequence[str]) -> str:
    return "[" + ", ".join(repr(i) for i in items) + "]"


def _values(opts: Options) -> dict[str, str]:
    docs = opts.target / "docs"
    # CI は Linux で動く。区切りは / に揃え、空白などを含む名前は引用する
    coverage_paths = " ".join(
        shlex.quote(Path(os.path.relpath((docs / p).resolve(), opts.target)).as_posix()) for p in opts.package
    )
    return {
        "project": opts.project,
        "project_repr": repr(opts.project),
        "author_repr": repr(opts.author),
        "title_rule": title_rule(opts.project),
        "package_paths": _py_list(opts.package),
        "cpp_sources": _py_list(opts.cpp),
        "use_hou_stub": "True" if opts.hou else "False",
        "extra_toctree": ("   api\n" if opts.package else "") + ("   cpp\n" if opts.cpp else ""),
        "api_modules": api_modules(docs, opts.package),
        "doxygen_step": _DOXYGEN_STEP if opts.cpp else "",
        "coverage_step": _COVERAGE_STEP.format(paths=coverage_paths, minimum=opts.min_coverage) if opts.package else "",
    }


def _destination(rel: Path) -> Path:
    """雛形の相対パスから、書き出し先の相対パスを決める。"""
    rel = rel.with_suffix("")  # 末尾の .tmpl を外す
    if rel.parts[0] == "github":
        rel = Path(".github", *rel.parts[1:])
    if rel.name == "gitignore":
        rel = rel.with_name(".gitignore")
    if rel.name == "page-template.rst":
        # 雛形は Sphinx に読ませない (toctree に無い警告を避ける) ので、拡張子を残す
        rel = rel.with_name("page-template.rst.tmpl")
    return rel


def plan(opts: Options) -> dict[Path, str]:
    """書き出すファイルと中身を決める。ファイルには触れない。"""
    values = _values(opts)
    result: dict[Path, str] = {}
    for src in sorted(TEMPLATES.rglob("*.tmpl")):
        rel = src.relative_to(TEMPLATES)
        if rel.with_suffix("").name == "cpp.rst" and not opts.cpp:
            continue
        if rel.with_suffix("").name == "api.rst" and not opts.package:
            continue
        text = src.read_text(encoding="utf-8")
        for key, value in values.items():
            text = text.replace(f"@@{key}@@", value)
        result[opts.target / _destination(rel)] = text
    return result


def write(opts: Options, *, force: bool = False) -> list[Path]:
    """雛形を書き出して、作ったファイルを返す。

    Raises:
        ScaffoldError: 既存のファイルがあり、``force`` が偽のとき。何も書かずに止まる。
    """
    files = plan(opts)
    existing = [p for p in files if p.exists()]
    if existing and not force:
        raise ScaffoldError(existing)
    for dest, text in files.items():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    return list(files)
