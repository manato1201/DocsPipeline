"""docstring が無い公開 API の一覧 (カバレッジの確認)。

Sphinx の autodoc は docstring が無い項目を黙って飛ばすので、``-W`` でも気づけない。
このモジュールはソースを構文解析 (``ast``) して、公開 API のうち docstring が無いものを数える。
コードは ``import`` しない。副作用のあるモジュールや、``hou`` のように環境が要るモジュールでも安全に使える。

公開 API とは、次のものをいう。

* ``_`` で始まらない名前のモジュール・クラス・関数・メソッド
* モジュールに ``__all__`` があるときは、そこに載っている名前だけ

``@overload`` と、プロパティの ``setter`` / ``deleter`` は数えない (docstring を書く場所ではないため)。
"""

from __future__ import annotations

import ast
import contextlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .files import iter_python_files


@dataclass(frozen=True)
class Item:
    """カバレッジの対象 1 件。"""

    path: Path
    qualname: str
    kind: str
    line: int
    documented: bool


@dataclass(frozen=True)
class Report:
    """カバレッジの集計。"""

    items: tuple[Item, ...]

    @property
    def missing(self) -> list[Item]:
        """docstring が無い項目。"""
        return [i for i in self.items if not i.documented]

    @property
    def percent(self) -> float:
        """docstring がある項目の割合 (対象が無ければ 100)。"""
        if not self.items:
            return 100.0
        return 100.0 * (len(self.items) - len(self.missing)) / len(self.items)


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _exported(tree: ast.Module) -> set[str] | None:
    """``__all__`` の中身を返す。無い (または静的に読めない) ときは ``None``。

    ``__all__ = [...]``・``__all__: list[str] = [...]``・``__all__ += [...]`` を読む。
    """
    names: set[str] | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            value_node, replace = node.value, True
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            if node.value is None:
                continue
            value_node, replace = node.value, True
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            value_node, replace = node.value, False
        else:
            continue
        try:
            value = ast.literal_eval(value_node)
        except ValueError:
            return None
        if not (isinstance(value, list | tuple) and all(isinstance(v, str) for v in value)):
            return None
        names = set(value) if replace or names is None else names | set(value)
    return names


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names = set()
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute):
            names.add(target.attr)
        elif isinstance(target, ast.Name):
            names.add(target.id)
    return names


def scan_file(path: Path, *, module_name: str | None = None) -> list[Item]:
    """1 ファイルの公開 API を調べる。

    Args:
        path: Python のソースファイル。
        module_name: 結果に使うモジュール名。省略するとファイル名から付ける。

    Returns:
        見つかった項目。

    Raises:
        ValueError: ファイルが構文エラーのとき (ファイル名と行を含む)。
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise ValueError(f"{path}:{exc.lineno}: 構文エラー: {exc.msg}") from exc
    module = module_name or path.stem
    exported = _exported(tree)
    items: list[Item] = []

    def visit_body(body: list[ast.stmt], prefix: str, top_level: bool) -> None:
        for node in body:
            if isinstance(node, (ast.If, ast.Try, ast.With)):
                # 条件つきの定義 (try: import ... / if sys.version_info ...) も、同じ階層として扱う
                visit_body(node.body, prefix, top_level)
                visit_body(getattr(node, "orelse", []), prefix, top_level)
                for handler in getattr(node, "handlers", []):
                    visit_body(handler.body, prefix, top_level)
                visit_body(getattr(node, "finalbody", []), prefix, top_level)
            elif isinstance(node, ast.ClassDef):
                if not _is_public(node.name) or (top_level and exported is not None and node.name not in exported):
                    continue
                qual = f"{prefix}.{node.name}"
                items.append(Item(path, qual, "class", node.lineno, ast.get_docstring(node) is not None))
                visit_body(node.body, qual, top_level=False)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not _is_public(node.name) or (top_level and exported is not None and node.name not in exported):
                    continue
                decorators = _decorator_names(node)
                if decorators & {"overload", "setter", "deleter"}:
                    continue
                kind = "function" if top_level else "method"
                qual = f"{prefix}.{node.name}"
                items.append(Item(path, qual, kind, node.lineno, ast.get_docstring(node) is not None))

    items.append(Item(path, module, "module", 1, ast.get_docstring(tree) is not None))
    visit_body(tree.body, module, top_level=True)
    return items


def _is_private_module(path: Path, root: Path) -> bool:
    """``_`` で始まる名前 (``_compat.py``・``_impl/``) の下にあるか。``__init__`` は、パッケージ自身なので除く。"""
    if not root.is_dir():
        return False
    parts = path.relative_to(root).with_suffix("").parts
    return any(part.startswith("_") and part != "__init__" for part in parts)


def _module_name(path: Path, root: Path) -> str:
    """``root`` からの相対パスでモジュール名を付ける。``root`` がパッケージなら、その名前から始める。"""
    if not root.is_dir():
        return path.stem
    parts = list(path.relative_to(root).with_suffix("").parts)
    if (root / "__init__.py").exists():
        parts.insert(0, root.name)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or root.name


def scan(roots: Iterable[Path]) -> Report:
    """``roots`` 配下の公開 API を調べて集計する。

    Raises:
        ValueError: 存在しないパスがあるとき、または構文エラーのファイルがあるとき。
            存在しないパスを「100%」と報告すると、パスの打ち間違いや移動で、検査が黙って空になる。
    """
    items: list[Item] = []
    for root in roots:
        if not root.exists():
            raise ValueError(f"パスがありません: {root}")
        for path in iter_python_files([root]):
            if _is_private_module(path, root):
                continue  # 公開 API の定義は「_ で始まらない名前」。非公開のモジュールは数えない
            items.extend(scan_file(path, module_name=_module_name(path, root)))
    return Report(tuple(items))


def format_report(report: Report, *, base: Path | None = None) -> str:
    """人が読む形に整形する。"""
    lines = []
    for item in report.missing:
        shown = item.path
        if base is not None:
            with contextlib.suppress(ValueError):  # base の外にあるファイルは、そのまま表示する
                shown = item.path.relative_to(base)
        lines.append(f"{shown}:{item.line}: {item.kind} {item.qualname} に docstring がありません")
    total = len(report.items)
    lines.append(f"docstring のカバレッジ: {report.percent:.1f}% ({total - len(report.missing)}/{total})")
    return "\n".join(lines)
