"""Houdini のノードを扱う補助 (``hou`` を使う例)。

Houdini の外では ``hou`` が ``import`` できない。文書の生成では
``docspipeline.stubs.hou`` のスタブがその代わりになる。
"""

from __future__ import annotations

import hou


class NodeCounter(hou.Node):
    """子ノードの数を数える。``hou.Node`` を継承した例。"""

    def count_children(self) -> int:
        """子ノードの数を返す。

        Returns:
            直下の子ノードの数。
        """
        return len(self.children())


def selected_names() -> list[str]:
    """選択中のノードの名前を返す。

    Returns:
        ノード名のリスト。何も選択していなければ空。
    """
    return [node.name() for node in hou.selectedNodes()]
