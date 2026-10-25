"""diagrams.net の図の取り扱い。

図は元ファイル (``名前.drawio``) と、書き出した SVG (``名前.drawio.svg`` または ``名前.svg``) の
両方をリポジトリに置く。SVG だけが文書に取り込まれるので、元ファイルだけをコミットすると図が出ない。
"""

from __future__ import annotations

from pathlib import Path


def find_missing_exports(docs: Path) -> list[Path]:
    """書き出した SVG が隣に無い ``.drawio`` を返す。

    Args:
        docs: 探す場所。``_build`` の下は除く。

    Returns:
        SVG が無い ``.drawio`` のパス (整列済み)。
    """
    missing = []
    for src in sorted(docs.rglob("*.drawio")):
        if "_build" in src.parts:
            continue
        if not (src.with_suffix(".svg").exists() or src.with_suffix(".drawio.svg").exists()):
            missing.append(src)
    return missing
