"""diagrams.net の図の取り扱い。

図は元ファイル (``名前.drawio``) と、書き出した SVG (``名前.drawio.svg`` または ``名前.svg``) の
両方をリポジトリに置く。SVG だけが文書に取り込まれるので、元ファイルだけをコミットすると図が出ない。
"""

from __future__ import annotations

from pathlib import Path

#: 探さない場所。生成物・外部のコード・隠しディレクトリ。
SKIP_DIRS = {"_build", "_generated", "_doxygen", "node_modules"}


def find_missing_exports(docs: Path) -> list[Path]:
    """書き出した SVG が隣に無い ``.drawio`` を返す。

    Args:
        docs: 探す場所。生成物 (``_build``・``_generated``・``_doxygen``)・``node_modules``・
            隠しディレクトリの下は除く。

    Returns:
        SVG が無い ``.drawio`` のパス (整列済み)。

    Raises:
        ValueError: ``docs`` が無いとき。打ち間違いで、検査が黙って空になるのを防ぐ。
    """
    if not docs.is_dir():
        raise ValueError(f"ディレクトリがありません: {docs}")
    missing = []
    for src in sorted(docs.rglob("*.drawio")):
        relative = src.relative_to(docs).parts[:-1]
        if any(part in SKIP_DIRS or part.startswith(".") for part in relative):
            continue
        if not (src.with_suffix(".svg").exists() or src.with_suffix(".drawio.svg").exists()):
            missing.append(src)
    return missing
