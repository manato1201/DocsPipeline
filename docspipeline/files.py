"""Python のソースファイルの列挙。``docspipeline`` の複数のモジュールが共有する。

探さない場所の規則を一か所に置く。``coverage``・``map``・``init`` で規則が食い違うと、
同じパッケージなのに、数えるファイルが変わってしまう (仮想環境の中身が API として並ぶ、など)。
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

#: 探さない場所。仮想環境・キャッシュ・生成物・外部のコード。
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", "_build", "build", "dist", ".tox"}


def iter_python_files(roots: Iterable[Path]) -> Iterator[Path]:
    """``roots`` 配下の ``.py`` ファイルを、生成物や仮想環境を除いて列挙する。

    Args:
        roots: ディレクトリ、または ``.py`` ファイル。

    Yields:
        見つかったファイル (各 ``root`` の中は整列済み)。
    """
    for root in roots:
        if root.is_file():
            yield root
            continue
        for path in sorted(root.rglob("*.py")):
            if not SKIP_DIRS.intersection(path.relative_to(root).parts):
                yield path
