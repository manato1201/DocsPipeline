"""``docspipeline doctor``: 手元の環境で、どの機能が使えるかを確認する。

「図がコードのまま出る」「C++ の節が空」といった症状の原因は、たいてい外部のコマンドが無いことにある。
どこを見ればよいかを、1 コマンドで示す。API トークンの **値は出さず**、設定の有無だけを示す。
"""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import sys
from collections.abc import Mapping
from dataclasses import dataclass

from . import confluence
from .mmdc import MMDC_ENV, command_exists, find_mmdc


@dataclass(frozen=True)
class Check:
    """確認の結果 1 件。"""

    name: str
    ok: bool
    detail: str
    required: bool = False


def _version(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def run_checks(environ: Mapping[str, str] | None = None) -> list[Check]:
    """環境を調べる。

    Args:
        environ: 環境変数。省略すると ``os.environ``。

    Returns:
        確認の結果。``required`` の項目が失敗すると、文書をビルドできない。
    """
    env = os.environ if environ is None else environ
    checks = [Check("Python", sys.version_info >= (3, 11), sys.version.split()[0], required=True)]

    for label, dist, required in (
        ("Sphinx", "sphinx", True),
        ("MyST (Markdown の取り込み)", "myst-parser", True),
        ("テーマ furo", "furo", True),
        ("Breathe (C++)", "breathe", False),
        ("Confluence ビルダー", "sphinxcontrib-confluencebuilder", False),
    ):
        version = _version(dist)
        checks.append(Check(label, version is not None, version or f"pip install '{dist}' (extras を参照)", required))

    mmdc = find_mmdc(env.get(MMDC_ENV), os.getcwd())
    if mmdc is None:
        checks.append(Check("mmdc (Mermaid → SVG)", False, "無い: 図はコードのまま出る"))
    elif not command_exists(mmdc):
        # DOCSPIPELINE_MMDC に、存在しないコマンドを指定している
        checks.append(Check("mmdc (Mermaid → SVG)", False, f"指定されたコマンドが見つからない: {' '.join(mmdc)}"))
    else:
        checks.append(Check("mmdc (Mermaid → SVG)", True, " ".join(mmdc)))
    doxygen = shutil.which("doxygen")
    checks.append(Check("doxygen (C++)", doxygen is not None, doxygen or "無い: C++ の文書を作るときだけ必要"))

    try:
        mode = confluence.current_mode(env)
        checks.append(Check("Confluence のモード", True, mode))
    except confluence.ConfluenceSettingsError as exc:
        checks.append(Check("Confluence のモード", False, str(exc)))
    missing = confluence.missing_env(env)
    checks.append(
        Check(
            "Confluence の環境変数",
            not missing,
            "すべて設定済み" if not missing else f"未設定: {', '.join(missing)} (公開するときだけ必要)",
        )
    )
    return checks


def format_checks(checks: list[Check]) -> str:
    """人が読む形に整形する。"""
    lines = []
    for c in checks:
        mark = "OK  " if c.ok else ("NG  " if c.required else "なし")
        lines.append(f"[{mark}] {c.name}: {c.detail}")
    return "\n".join(lines)


def exit_code(checks: list[Check]) -> int:
    """必須の項目が 1 つでも失敗していれば 1。"""
    return 1 if any(c.required and not c.ok for c in checks) else 0
