"""Houdini の ``hou`` モジュールのスタブ。

Houdini の外では ``import hou`` ができず、``hou`` を使うコードは autodoc で読み込めない。
このモジュールは、``import hou`` と、``hou.Node`` のような属性の参照・継承・呼び出しを
エラーなしで通すための偽物で、文書生成とテストの両方から使う。

Houdini の中では本物の ``hou`` が先に見つかるように、スタブの場所は ``sys.path`` の
末尾に足す (``docspipeline.config.STUBS_DIR``)。

このスタブは何も実装していない。値を返す挙動が要るテストは、テスト側で
``monkeypatch`` などを使って必要な関数だけを差し替えること。
"""

from __future__ import annotations

from typing import Any

#: スタブであることを判定するための印。
IS_STUB = True


class _Meta(type):
    """クラス属性の参照を、新しいプレースホルダーのクラスで返す。"""

    def __getattr__(cls, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _placeholder(f"{cls.__name__}.{name}")


class _Any(metaclass=_Meta):
    """何を呼んでも自分自身を返す、何もしないオブジェクト。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self

    def __iter__(self) -> Any:
        return iter(())

    def __bool__(self) -> bool:
        return False


_cache: dict[str, type] = {}


def _placeholder(name: str) -> type:
    if name not in _cache:
        _cache[name] = _Meta(name.rsplit(".", 1)[-1], (_Any,), {"__module__": "hou"})
    return _cache[name]


def __getattr__(name: str) -> Any:
    """``hou.<名前>`` をすべてプレースホルダーとして返す (モジュールの属性参照)。"""
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    return _placeholder(name)
