"""Sphinx のビルド開始時に Doxygen を走らせて XML を作る拡張。

C++ の文書は Doxygen が XML にし、Breathe が Sphinx へ取り込む。この拡張は、その前段
(Doxygen の実行) を ``sphinx-build`` の中に閉じ込めて、別の手順を覚えなくて済むようにする。

Doxygen が出す警告 (コメントの書式の誤りなど) は Sphinx の警告として転送するので、
``-W`` で CI を止められる。

Doxygen が手元に無い環境では、環境変数 ``DOCSPIPELINE_SKIP_DOXYGEN=1`` で飛ばせる。
その場合、Breathe の指示子が「XML が無い」という警告を出す。``-W`` ではビルドが失敗するので、
手元で C++ 以外を確認したいときは ``docspipeline build --no-strict`` と組み合わせる。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sphinx.application import Sphinx
from sphinx.errors import ExtensionError
from sphinx.util import logging

from . import __version__

logger = logging.getLogger(__name__)

SKIP_ENV = "DOCSPIPELINE_SKIP_DOXYGEN"

_TRUE = {"1", "true", "yes", "on"}

_FILE_PATTERNS = "*.h *.hh *.hpp *.hxx *.c *.cc *.cpp *.cxx"


def make_doxyfile(project: str, inputs: list[str], output: str, predefined: list[str]) -> str:
    """XML だけを出す最小の Doxyfile を作る。

    Args:
        project: Doxygen の ``PROJECT_NAME``。
        inputs: 読み込むソースの場所。
        output: 出力先 (この下の ``xml/`` が Breathe の入力になる)。
        predefined: ``PREDEFINED`` に渡すマクロ。

    Returns:
        Doxyfile の中身。
    """

    def q(value: str) -> str:
        return '"' + value.replace('"', '\\"') + '"'

    lines = {
        "PROJECT_NAME": q(project),
        "OUTPUT_DIRECTORY": q(output),
        "INPUT": " ".join(q(i) for i in inputs),
        "FILE_PATTERNS": _FILE_PATTERNS,
        "RECURSIVE": "YES",
        "GENERATE_XML": "YES",
        "XML_PROGRAMLISTING": "NO",
        "GENERATE_HTML": "NO",
        "GENERATE_LATEX": "NO",
        "QUIET": "YES",
        # コメントの書式の誤りは拾う。コメントが無いこと自体は、docspipeline coverage の役目。
        "WARNINGS": "YES",
        "WARN_IF_DOC_ERROR": "YES",
        "WARN_IF_UNDOCUMENTED": "NO",
        "JAVADOC_AUTOBRIEF": "YES",
        "MARKDOWN_SUPPORT": "YES",
        "ENABLE_PREPROCESSING": "YES",
        "MACRO_EXPANSION": "YES",
        "EXPAND_ONLY_PREDEF": "YES",
        "PREDEFINED": " ".join(predefined),
    }
    return "\n".join(f"{key} = {value}" for key, value in lines.items()) + "\n"


def run_doxygen(app: Sphinx) -> None:
    """``builder-inited`` で Doxygen を走らせ、警告を Sphinx の警告として転送する。

    Raises:
        sphinx.errors.ExtensionError: ``doxygen`` が無い、または失敗したとき。
    """
    config = app.config
    inputs: list[str] = config.docspipeline_doxygen_inputs
    if not inputs:
        return

    if os.environ.get(SKIP_ENV, "").lower() in _TRUE:
        logger.info("%s が設定されているため Doxygen を飛ばします", SKIP_ENV)
        return

    doxygen = shutil.which(config.docspipeline_doxygen_cmd)
    if doxygen is None:
        raise ExtensionError(
            f"doxygen が見つかりません。インストールするか、{SKIP_ENV}=1 で C++ の節を飛ばしてください"
        )

    output = Path(config.docspipeline_doxygen_output)
    output.mkdir(parents=True, exist_ok=True)
    # 古い XML が残って、消したはずの関数が文書に出続けるのを避ける。
    shutil.rmtree(output / "xml", ignore_errors=True)

    doxyfile = output / "Doxyfile"
    doxyfile.write_text(
        make_doxyfile(
            config.docspipeline_doxygen_project,
            inputs,
            str(output),
            config.docspipeline_doxygen_predefined,
        ),
        encoding="utf-8",
    )
    logger.info("Doxygen を実行します: %s", doxyfile)
    proc = subprocess.run(
        [doxygen, str(doxyfile)], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    for line in proc.stderr.splitlines():
        if line.strip():
            logger.warning("doxygen: %s", line.strip())
    if proc.returncode != 0:
        raise ExtensionError(f"doxygen が失敗しました (終了コード {proc.returncode})")


def setup(app: Sphinx) -> dict[str, Any]:
    """Sphinx 拡張の登録。"""
    app.add_config_value("docspipeline_doxygen_project", "project", "env")
    app.add_config_value("docspipeline_doxygen_inputs", [], "env")
    app.add_config_value("docspipeline_doxygen_predefined", [], "env")
    app.add_config_value("docspipeline_doxygen_output", "_doxygen", "env")
    app.add_config_value("docspipeline_doxygen_cmd", "doxygen", "env")
    # Breathe より先に走らせる (小さい数字ほど先)。
    app.connect("builder-inited", run_doxygen, priority=100)
    return {"version": __version__, "parallel_read_safe": True}
