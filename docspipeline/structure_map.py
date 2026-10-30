"""ソースを構文解析して作る、パッケージの構造の地図 (``docspipeline map``)。

コードを ``import`` せずに ``ast`` だけで読み、モジュールどうしの依存を取り出す。
結果は「機械的な地図」で、次の三つに使う。

* **アーキテクチャ文書の下書き**: モジュールの一覧と依存の図を Markdown で出す。
  推定を含むので、人が確認してから使う。そのまま公開しない。
* **依存の向きの点検**: 循環していないか、あるべきでない依存が無いか。
* **手書きの図とのずれの検出**: 構成図が、実際の依存と一致しているか。

外部へは何も送信しない (ローカルの読み取りだけ)。

見つける依存は 2 種類。

``import``
    ``import`` 文による依存 (相対 ``import`` を含む)。
``reference``
    モジュールの名前と **完全に一致する文字列** による参照
    (Sphinx の ``extensions = ["pkg.ext"]`` のような、名前での読み込み)。

``import`` は、モジュールを読み込んだときに実行されるものだけ。次の 2 つは、実行時の循環にならないので、
別に扱う (循環の検出の対象にしない)。

* ``if TYPE_CHECKING:`` の中の import (型検査のときだけ)。依存として数えない。
* 関数の中の import (``deferred``)。呼ばれたときに初めて読み込まれる。循環を断つ定番の書き方。

見つけられないもの: ``importlib.import_module(変数)`` のような動的な読み込み、部分的に組み立てた名前。
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .files import iter_python_files


@dataclass(frozen=True)
class Module:
    """1 つのモジュール。"""

    name: str
    path: Path
    is_package: bool
    summary: str
    lines: int
    public_api: int
    imports: frozenset[str]
    references: frozenset[str]
    external: frozenset[str]
    deferred: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Graph:
    """パッケージ全体の地図。"""

    package: str
    modules: tuple[Module, ...]

    def get(self, name: str) -> Module:
        """名前でモジュールを引く。

        Raises:
            KeyError: 無いとき。
        """
        for m in self.modules:
            if m.name == name:
                return m
        raise KeyError(name)

    def edges(self, kind: str = "import", *, include_root: bool = False) -> set[tuple[str, str]]:
        """依存の組 ``(使う側, 使われる側)`` を返す。

        Args:
            kind: ``import``・``reference``・``deferred`` のいずれか。
                ``import`` はモジュール直下で実行される import、
                ``reference`` はモジュール名と一致する文字列、
                ``deferred`` は関数の中の import で、呼ばれたときに初めて読み込まれる。
            include_root: パッケージ自身 (``__init__``) への依存を含めるか。
                ``from . import __version__`` のような依存で、図が読みにくくなるので既定では除く。
        """
        result = set()
        for m in self.modules:
            for dst in {"import": m.imports, "reference": m.references, "deferred": m.deferred}[kind]:
                if include_root or dst != self.package:
                    result.add((m.name, dst))
        return result

    def cycles(self) -> list[list[str]]:
        """``import`` の循環を、強連結成分として返す (無ければ空)。

        パッケージ自身 (``__init__``) を経由する循環も含める。``__init__`` が子を import し、
        子が ``from pkg import X`` する形は、循環 import の典型だから。
        """
        graph: dict[str, set[str]] = {m.name: set() for m in self.modules}
        for src, dst in self.edges(include_root=True):
            graph[src].add(dst)
        index: dict[str, int] = {}
        low: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        found: list[list[str]] = []
        counter = 0

        def visit(node: str) -> None:
            nonlocal counter
            index[node] = low[node] = counter
            counter += 1
            stack.append(node)
            on_stack.add(node)
            for nxt in sorted(graph[node]):
                if nxt not in index:
                    visit(nxt)
                    low[node] = min(low[node], low[nxt])
                elif nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if low[node] == index[node]:
                component = []
                while True:
                    top = stack.pop()
                    on_stack.discard(top)
                    component.append(top)
                    if top == node:
                        break
                if len(component) > 1:
                    found.append(sorted(component))

        for name in sorted(graph):
            if name not in index:
                visit(name)
        return sorted(found)

    def entry_points(self) -> list[str]:
        """どのモジュールからも使われていないモジュール (入口の候補)。"""
        used = {dst for _, dst in self.edges() | self.edges("reference")}
        return sorted(m.name for m in self.modules if m.name not in used and m.name != self.package)


def _first_line(doc: str | None) -> str:
    for line in (doc or "").strip().splitlines():
        if line.strip():
            return line.strip()
    return ""


def _public_api(tree: ast.Module) -> int:
    return sum(
        1
        for node in tree.body
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_")
    )


def _resolve_from(node: ast.ImportFrom, module: str, is_package: bool, known: set[str]) -> Iterator[str]:
    """``from ... import ...`` が指す、パッケージ内のモジュールを返す。"""
    if node.level:
        parts = module.split(".")
        # 相対 import の基準は、パッケージ (モジュールなら、それを含むパッケージ)
        base_parts = parts if is_package else parts[:-1]
        base_parts = base_parts[: len(base_parts) - (node.level - 1)]
        base = ".".join(base_parts)
        target = f"{base}.{node.module}" if node.module else base
    else:
        target = node.module or ""
    for alias in node.names:
        candidate = f"{target}.{alias.name}"
        if candidate in known:
            yield candidate
        elif target in known:
            yield target


def _is_type_checking(test: ast.expr) -> bool:
    """``if TYPE_CHECKING:`` / ``if typing.TYPE_CHECKING:`` か。"""
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _walk(node: ast.AST, deferred: bool = False) -> Iterator[tuple[ast.AST, bool]]:
    """ノードを順に返す。``deferred`` は、関数の中 (呼ばれたときに実行される) かどうか。

    ``if TYPE_CHECKING:`` の本体は、実行時には読み込まれないので返さない。
    """
    yield node, deferred
    if isinstance(node, ast.If) and _is_type_checking(node.test):
        children = node.orelse
    else:
        children = list(ast.iter_child_nodes(node))
    inside_function = deferred or isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda)
    for child in children:
        yield from _walk(child, inside_function)


def _analyze(path: Path, name: str, is_package: bool, known: set[str]) -> Module:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise ValueError(f"{path}:{exc.lineno}: 構文エラー: {exc.msg}") from exc
    runtime: set[str] = set()
    lazy: set[str] = set()
    references: set[str] = set()
    external: set[str] = set()
    root = name.split(".")[0]
    for node, deferred in _walk(tree):
        found = runtime if not deferred else lazy
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top == root:
                    parts = alias.name.split(".")
                    while parts and ".".join(parts) not in known:
                        parts.pop()
                    if parts:
                        found.add(".".join(parts))
                else:
                    external.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] == root:
                found.update(_resolve_from(node, name, is_package, known))
            elif node.module:
                external.add(node.module.split(".")[0])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in known:
            references.add(node.value)
    runtime.discard(name)
    lazy.discard(name)
    references.discard(name)
    return Module(
        name=name,
        path=path,
        is_package=is_package,
        summary=_first_line(ast.get_docstring(tree)),
        lines=len(text.splitlines()),
        public_api=_public_api(tree),
        imports=frozenset(runtime),
        references=frozenset(references - runtime),
        external=frozenset(external - {"__future__"}),
        deferred=frozenset(lazy - runtime),
    )


def scan_package(root: Path) -> Graph:
    """パッケージのディレクトリを読んで、地図を作る。

    Args:
        root: ``__init__.py`` を持つディレクトリ。

    Returns:
        モジュールの一覧と依存。

    Raises:
        ValueError: ``root`` がパッケージ (``__init__.py`` を持つディレクトリ) でないとき、
            または構文エラーのファイルがあるとき。
    """
    root = root.resolve()
    if not (root / "__init__.py").is_file():
        raise ValueError(f"パッケージではありません (__init__.py が無い): {root}")
    package = root.name
    files: dict[str, tuple[Path, bool]] = {}
    for path in iter_python_files([root]):
        parts = [package, *path.relative_to(root).with_suffix("").parts]
        is_package = parts[-1] == "__init__"
        if is_package:
            parts.pop()
        files[".".join(parts)] = (path, is_package)
    known = set(files)
    modules = tuple(_analyze(path, name, is_pkg, known) for name, (path, is_pkg) in sorted(files.items()))
    return Graph(package, modules)


def _node_id(name: str) -> str:
    return name.replace(".", "_")


def _short(graph: Graph, name: str) -> str:
    return name[len(graph.package) + 1 :] if name != graph.package else name


def to_mermaid(graph: Graph) -> str:
    """依存の図を Mermaid で返す。実線は ``import``、点線は文字列による参照。"""
    lines = ["flowchart LR"]
    for m in graph.modules:
        if m.name == graph.package:
            continue
        summary = m.summary.replace('"', "'").replace("`", "")  # rst の記号は、図のラベルには要らない
        if len(summary) > 28:
            summary = summary[:27] + "…"
        label = f"{_short(graph, m.name)}<br/>{summary}" if summary else _short(graph, m.name)
        lines.append(f'    {_node_id(m.name)}["{label}"]')
    for src, dst in sorted(graph.edges()):
        lines.append(f"    {_node_id(src)} --> {_node_id(dst)}")
    for src, dst in sorted(graph.edges("reference")):
        lines.append(f"    {_node_id(src)} -.-> {_node_id(dst)}")
    for src, dst in sorted(graph.edges("deferred")):
        lines.append(f"    {_node_id(src)} -. 遅延 .-> {_node_id(dst)}")
    return "\n".join(lines) + "\n"


def to_markdown(graph: Graph) -> str:
    """アーキテクチャ文書の下書きを Markdown (MyST) で返す。"""
    imports = graph.edges()
    references = graph.edges("reference")
    out = [
        f"# {graph.package} の構造 (自動生成の下書き)",
        "",
        "```{warning}",
        "このページは `docspipeline map` が、ソースを **構文解析して** 作った下書きです。",
        "推定を含みます。人が確認し、手直ししてから使い、そのまま公開しないでください。",
        "外部へは何も送信していません。",
        "```",
        "",
        "## 依存の地図",
        "",
        "実線は `import`、点線は名前の文字列による参照 (Sphinx の `extensions` など)。",
        "",
        "```mermaid",
        to_mermaid(graph).rstrip(),
        "```",
        "",
        "## モジュール一覧",
        "",
        "| モジュール | 要約 | 行数 | 公開 API | 使う | 使われる |",
        "|---|---|---:|---:|---|---|",
    ]
    for m in graph.modules:
        uses = sorted({_short(graph, d) for s, d in imports | references if s == m.name})
        used_by = sorted({_short(graph, s) for s, d in imports | references if d == m.name})
        summary = m.summary.replace("|", "\\|")
        out.append(
            f"| `{_short(graph, m.name)}` | {summary} | {m.lines} | {m.public_api} "
            f"| {', '.join(f'`{u}`' for u in uses) or '-'} | {', '.join(f'`{u}`' for u in used_by) or '-'} |"
        )
    cycles = graph.cycles()
    out += ["", "## 依存の向きの点検", ""]
    if cycles:
        out.append("**循環があります**:")
        out += [f"- {' ⇄ '.join(_short(graph, n) for n in c)}" for c in cycles]
    else:
        out.append("- `import` の循環: なし")
    entries = graph.entry_points()
    out.append(
        "- どこからも使われていない (入口の候補): " + (", ".join(f"`{_short(graph, e)}`" for e in entries) or "なし")
    )
    out += [
        "",
        "## 読み取れないこと",
        "",
        "- 動的な読み込み (`importlib.import_module(変数)`) と、組み立てた名前は見つけられません。",
        "- 依存の「理由」は分かりません。なぜその依存があるのかは、人が書き足してください。",
        "",
    ]
    return "\n".join(out)


def to_json(graph: Graph) -> str:
    """機械で読める形 (JSON) で返す。"""
    data = {
        "package": graph.package,
        "modules": [
            {
                "name": m.name,
                "summary": m.summary,
                "lines": m.lines,
                "public_api": m.public_api,
                "imports": sorted(m.imports),
                "references": sorted(m.references),
                "deferred": sorted(m.deferred),
                "external": sorted(m.external),
            }
            for m in graph.modules
        ],
        "cycles": graph.cycles(),
        "entry_points": graph.entry_points(),
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
