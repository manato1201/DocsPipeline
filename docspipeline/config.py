"""各リポジトリの ``docs/conf.py`` から読み込む共通の Sphinx 設定。

使い方 (``docs/conf.py``)::

    from docspipeline.config import build_config

    globals().update(
        build_config(
            confdir=__file__,
            project="ProfilingTool",
            author="manato1201",
            package_paths=["../src"],
        )
    )

個別のリポジトリが決めるのは名前と対象のパスだけで、拡張・autodoc・Markdown 取り込み・
Confluence の設定はここに集める。
"""

from __future__ import annotations

import html
import importlib.util
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from . import confluence

OFFLINE_ENV = "DOCSPIPELINE_OFFLINE"

STUBS_DIR = Path(__file__).parent / "stubs"

_TRUE = {"1", "true", "yes", "on"}


def is_offline(environ: dict[str, str] | None = None) -> bool:
    """外部サイトにつなげない環境か。

    ``DOCSPIPELINE_OFFLINE=1`` のとき、intersphinx と nitpicky を無効にする。
    """
    env = os.environ if environ is None else environ
    return env.get(OFFLINE_ENV, "").lower() in _TRUE


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _resolve(confdir: Path, paths: list[str | Path]) -> list[Path]:
    return [(confdir / p).resolve() for p in paths]


def _write_confluence_footer(confdir: Path, note: str) -> str:
    """Confluence の各ページ末尾に付ける注記ファイルを書き、そのパスを返す。"""
    out = confdir / "_generated" / "confluence_footer.xhtml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"<hr/><p><small>{html.escape(note)}</small></p>\n", encoding="utf-8")
    return str(out)


def build_config(
    *,
    confdir: str | Path,
    project: str,
    author: str,
    release: str = "",
    language: str = "ja",
    package_paths: list[str | Path] | None = None,
    mock_imports: list[str] | None = None,
    use_hou_stub: bool = False,
    cpp_sources: list[str | Path] | None = None,
    cpp_predefined: list[str] | None = None,
    license_note: str = "",
    extra_extensions: list[str] | None = None,
) -> dict[str, Any]:
    """Sphinx の設定を辞書で返す。

    Args:
        confdir: ``conf.py`` の場所。``__file__`` をそのまま渡してよい。
        project: 文書の題名 (プロジェクト名)。
        author: 著作者名。
        release: バージョン表記。
        language: 文書の言語。
        package_paths: autodoc が ``import`` できるようにする Python のソースの場所
            (``confdir`` からの相対パス)。
        mock_imports: autodoc のときだけ偽物に差し替えるモジュール名。
        use_hou_stub: Houdini の ``hou`` が無い環境用のスタブを使うか。
            本物の ``hou`` が ``import`` できる環境では、そちらが優先される。
        cpp_sources: Doxygen に読ませる C++ のソースの場所 (``confdir`` からの相対パス)。
            指定すると Breathe と :mod:`docspipeline.doxygen` を有効にする。
        cpp_predefined: Doxygen のマクロ定義 (``PREDEFINED``)。
        license_note: 出典・ライセンスの注記。HTML のフッターと Confluence の各ページ末尾に固定する。
        extra_extensions: 追加の Sphinx 拡張。

    Returns:
        ``conf.py`` の名前空間へ ``update`` する設定の辞書。
    """
    confdir = Path(confdir).resolve()
    if confdir.is_file():
        confdir = confdir.parent
    offline = is_offline()

    for path in _resolve(confdir, package_paths or []):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    if use_hou_stub and str(STUBS_DIR) not in sys.path:
        # 末尾に足す。Houdini の中で動かすときは、本物の hou が先に見つかる。
        sys.path.append(str(STUBS_DIR))

    extensions = [
        "sphinx.ext.autodoc",
        "sphinx.ext.napoleon",
        "myst_parser",
        "docspipeline.guard",
        "docspipeline.mermaid",
    ]
    if not offline:
        extensions.append("sphinx.ext.intersphinx")
    if cpp_sources:
        extensions += ["breathe", "docspipeline.doxygen"]
    if _has_module("sphinxcontrib.confluencebuilder"):
        extensions.append("sphinxcontrib.confluencebuilder")
    extensions += extra_extensions or []

    # 本物を import できない (偽物にしている) モジュールは、継承元などの参照が解決できない。
    # nitpicky の警告から外す。
    faked = list(mock_imports or []) + (["hou"] if use_hou_stub else [])
    nitpick_ignore_regex = [(r"py:.*", rf"{re.escape(name)}(\..*)?") for name in faked]

    year = date.today().year
    copyright_text = f"{year}, {author}"
    if license_note:
        copyright_text += f"。{license_note}"

    cfg: dict[str, Any] = {
        "project": project,
        "author": author,
        "copyright": copyright_text,
        "release": release,
        "language": language,
        "extensions": extensions,
        "source_suffix": {".rst": "restructuredtext", ".md": "markdown"},
        "exclude_patterns": ["_build", "_doxygen", "_generated", "Thumbs.db", ".DS_Store", "*.tmpl"],
        # 未解決の参照を警告にする。-W と組み合わせて、リンク切れを CI で止める。
        "nitpicky": not offline,
        "nitpick_ignore_regex": nitpick_ignore_regex,
        # autodoc / napoleon (Google 形式の docstring)
        "autodoc_default_options": {
            "members": True,
            "show-inheritance": True,
            "member-order": "bysource",
        },
        "autodoc_typehints": "description",
        "autodoc_mock_imports": list(mock_imports or []),
        "napoleon_google_docstring": True,
        "napoleon_numpy_docstring": False,
        # 既存の Markdown 文書の再利用
        "myst_enable_extensions": ["colon_fence", "deflist"],
        "myst_heading_anchors": 3,
        # ```mermaid の囲みを docspipeline.mermaid の指示子として扱う
        "myst_fence_as_directive": ["mermaid"],
        # 見た目
        "html_theme": "furo",
        "html_title": project,
    }
    if not offline:
        cfg["intersphinx_mapping"] = {"python": ("https://docs.python.org/3", None)}

    if cpp_sources:
        slug = project.replace(" ", "_")
        cfg["docspipeline_doxygen_project"] = slug
        cfg["docspipeline_doxygen_inputs"] = [str(p) for p in _resolve(confdir, list(cpp_sources))]
        cfg["docspipeline_doxygen_predefined"] = list(cpp_predefined or [])
        cfg["docspipeline_doxygen_output"] = str(confdir / "_doxygen")
        cfg["breathe_projects"] = {slug: str(confdir / "_doxygen" / "xml")}
        cfg["breathe_default_project"] = slug
        cfg["breathe_domain_by_extension"] = {"h": "cpp", "hpp": "cpp", "hh": "cpp"}

    footer = _write_confluence_footer(confdir, license_note) if license_note else None
    try:
        cfg.update(confluence.sphinx_settings(footer_file=footer))
    except confluence.ConfluenceSettingsError as exc:
        # conf.py の中で例外にすると、Sphinx はスタックトレースつきの内部エラーとして出す。
        # 公開しない設定のまま、メッセージを docspipeline.guard に渡して、整った形で失敗させる。
        cfg.update(confluence.sphinx_settings({}, footer_file=footer))
        cfg["docspipeline_config_error"] = str(exc)
    return cfg
