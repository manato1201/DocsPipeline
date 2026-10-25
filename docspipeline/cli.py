"""``docspipeline`` コマンド。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unicodedata
from collections.abc import Sequence
from pathlib import Path

from . import confluence, docstring_coverage

TEMPLATES = Path(__file__).parent / "templates" / "project"


def _run(cmd: Sequence[str], env: dict[str, str] | None = None) -> int:
    """コマンドを走らせ、出力から API トークンを伏せて表示する。"""
    merged = {**os.environ, **(env or {})}
    proc = subprocess.Popen(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=merged,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(confluence.mask_secrets(line, merged), end="", flush=True)
    return proc.wait()


def _sphinx(builder: str, docs: Path, out: Path, *, strict: bool, env: dict[str, str] | None = None) -> int:
    # モードの綴り間違いは、Sphinx を起動する前に分かりやすく止める
    confluence.current_mode({**os.environ, **(env or {})})
    cmd = [sys.executable, "-m", "sphinx", "-b", builder, str(docs), str(out)]
    if strict:
        # 警告をエラー扱いにする。--keep-going で、止まらずに全部の警告を出す。
        cmd += ["-W", "--keep-going"]
    return _run(cmd, env)


def cmd_build(args: argparse.Namespace) -> int:
    """``build``: Sphinx でビルドする。"""
    docs = Path(args.docs)
    env = {"DOCSPIPELINE_MERMAID_MISSING": "error"} if args.require_mermaid else {}
    return _sphinx(args.builder, docs, docs / "_build" / args.builder, strict=not args.no_strict, env=env)


def cmd_linkcheck(args: argparse.Namespace) -> int:
    """``linkcheck``: 外部リンクの切れを確認する。"""
    docs = Path(args.docs)
    return _sphinx("linkcheck", docs, docs / "_build" / "linkcheck", strict=False)


def cmd_coverage(args: argparse.Namespace) -> int:
    """``coverage``: docstring が無い公開 API を一覧し、基準に満たなければ失敗にする。"""
    report = docstring_coverage.scan([Path(p) for p in args.paths])
    print(docstring_coverage.format_report(report, base=Path.cwd()))
    if args.fail_under is not None and report.percent < args.fail_under:
        print(f"カバレッジが基準 {args.fail_under}% を下回っています", file=sys.stderr)
        return 1
    return 0


def find_missing_diagram_exports(docs: Path) -> list[Path]:
    """書き出した SVG が無い ``.drawio`` を返す。

    diagrams.net の元ファイルだけをコミットすると、ビルドで図が出ない。
    ``名前.svg`` か ``名前.drawio.svg`` のどちらかが隣にあれば良しとする。
    """
    missing = []
    for src in sorted(docs.rglob("*.drawio")):
        if "_build" in src.parts:
            continue
        if not (src.with_suffix(".svg").exists() or src.with_suffix(".drawio.svg").exists()):
            missing.append(src)
    return missing


def cmd_check_diagrams(args: argparse.Namespace) -> int:
    """``check-diagrams``: 書き出した SVG が無い ``.drawio`` があれば失敗にする。"""
    missing = find_missing_diagram_exports(Path(args.docs))
    for path in missing:
        print(f"{path}: 書き出した SVG がありません (diagrams.net の Export → SVG)")
    return 1 if missing else 0


def _confluence_env(mode: str) -> dict[str, str]:
    return {confluence.MODE_ENV: mode}


def cmd_confluence_check(args: argparse.Namespace) -> int:
    """認証・権限・親ページを確認する (ページは変更しない)。"""
    env = _confluence_env("dryrun")
    missing = confluence.missing_env()
    if missing:
        print(f"次の環境変数が未設定です: {', '.join(missing)}", file=sys.stderr)
        return 2
    cmd = [sys.executable, "-m", "sphinxcontrib.confluencebuilder", "connection-test", "--work-dir", args.docs]
    return _run(cmd, env)


def cmd_publish(args: argparse.Namespace) -> int:
    """``publish``: Confluence 形式でビルドする。公開するのは ``--mode publish`` のときだけ。

    ``dryrun`` と ``publish`` では、先に接続テストを行い、失敗したらビルドしない。
    """
    docs = Path(args.docs)
    mode = args.mode
    env = _confluence_env(mode)
    out = docs / "_build" / "confluence"

    if mode != "local":
        missing = confluence.missing_env()
        if missing:
            print(f"次の環境変数が未設定です: {', '.join(missing)}", file=sys.stderr)
            return 2
        if not args.skip_connection_test:
            print("== 接続テスト ==")
            rc = cmd_confluence_check(argparse.Namespace(docs=str(docs)))
            if rc != 0:
                print("接続テストに失敗したため、中止します", file=sys.stderr)
                return rc
    print(f"== Confluence ビルド (mode={mode}) ==")
    return _sphinx("confluence", docs, out, strict=args.strict, env=env)


def _render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@@{key}@@", value)
    return template


def _py_list(items: Sequence[str]) -> str:
    return "[" + ", ".join(repr(i) for i in items) + "]"


def _title_rule(text: str) -> str:
    """見出しの下線。全角の文字は幅 2 として数える (足りないと docutils が警告する)。"""
    width = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return "=" * max(width, 4)


def _python_modules(source_root: Path) -> list[str]:
    """``source_root`` の下にある公開モジュールの名前を返す (``import`` はしない)。"""
    names = []
    for path in sorted(source_root.rglob("*.py")):
        rel = path.relative_to(source_root).with_suffix("")
        parts = list(rel.parts)
        if any(p.startswith("_") and p != "__init__" for p in parts) or any(p in ("tests", "test") for p in parts):
            continue
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            names.append(".".join(parts))
    return names


def _api_modules(docs: Path, package_paths: Sequence[str]) -> str:
    blocks = []
    for rel in package_paths:
        root = (docs / rel).resolve()
        if not root.is_dir():
            continue
        names = _python_modules(root)
        for name in names:
            # 子のモジュールがあるパッケージは、__init__ の再公開で同じ項目が二重に出るのを避ける
            has_children = any(other.startswith(name + ".") for other in names)
            options = "   :no-members:\n" if has_children else ""
            blocks.append(f"\n.. automodule:: {name}\n{options}")
    return "".join(blocks)


_DOXYGEN_STEP = """      - name: Install Doxygen
        run: sudo apt-get update && sudo apt-get install -y doxygen
"""

_COVERAGE_STEP = """      - name: Docstring coverage
        run: docspipeline coverage {paths}
"""


def cmd_init(args: argparse.Namespace) -> int:
    """``init``: ``docs/`` の雛形と CI の設定を作る。既存のファイルは ``--force`` なしでは上書きしない。"""
    target = Path(args.target).resolve()
    docs = target / "docs"
    coverage_paths = " ".join(os.path.relpath((docs / p).resolve(), target) for p in args.package)
    values = {
        "project": args.project,
        "project_repr": repr(args.project),
        "author_repr": repr(args.author),
        "title_rule": _title_rule(args.project),
        "package_paths": _py_list(args.package),
        "cpp_sources": _py_list(args.cpp),
        "use_hou_stub": "True" if args.hou else "False",
        "extra_toctree": ("   api\n" if args.package else "") + ("   cpp\n" if args.cpp else ""),
        "api_modules": _api_modules(docs, args.package),
        "doxygen_step": _DOXYGEN_STEP if args.cpp else "",
        "coverage_step": _COVERAGE_STEP.format(paths=coverage_paths) if args.package else "",
    }
    plan: dict[Path, str] = {}
    for src in sorted(TEMPLATES.rglob("*.tmpl")):
        rel = src.relative_to(TEMPLATES).with_suffix("")  # 末尾の .tmpl を外す
        if rel.parts[0] == "github":
            rel = Path(".github", *rel.parts[1:])
        if rel.name == "gitignore":
            rel = rel.with_name(".gitignore")  # 点で始まるファイルは、パッケージのデータに含まれないことがある
        if rel.name == "cpp.rst" and not args.cpp:
            continue
        if rel.name == "api.rst" and not args.package:
            continue
        dest = target / rel
        if dest.name == "page-template.rst":
            # 雛形は Sphinx に読ませない (toctree に無い警告を避ける) ので、拡張子を残す
            dest = dest.with_name("page-template.rst.tmpl")
        plan[dest] = _render(src.read_text(encoding="utf-8"), values)

    existing = [p for p in plan if p.exists()]
    if existing and not args.force:
        for p in existing:
            print(f"既にあります: {p}", file=sys.stderr)
        print("上書きするには --force を付けてください", file=sys.stderr)
        return 1
    for dest, text in plan.items():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        print(f"作成: {dest}")
    print(f"次の手順: pip install 'docspipeline[docs]' && docspipeline build {docs}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """``docspipeline`` の引数の定義を作る。"""
    parser = argparse.ArgumentParser(prog="docspipeline", description="API 文書の生成と Confluence への公開")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="リポジトリに docs/ の雛形と CI を作る")
    p.add_argument("target", help="対象リポジトリのルート")
    p.add_argument("--project", required=True, help="文書の題名")
    p.add_argument("--author", required=True)
    p.add_argument("--package", action="append", default=[], metavar="PATH", help="Python のソース (docs/ からの相対)。複数可")
    p.add_argument("--cpp", action="append", default=[], metavar="PATH", help="C++ のソース (docs/ からの相対)。複数可")
    p.add_argument("--hou", action="store_true", help="Houdini の hou スタブを使う")
    p.add_argument("--force", action="store_true", help="既存のファイルを上書きする")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("build", help="Sphinx でビルドする (既定は警告をエラー扱い)")
    p.add_argument("docs", nargs="?", default="docs")
    p.add_argument("-b", "--builder", default="html")
    p.add_argument("--no-strict", action="store_true", help="警告をエラー扱いにしない")
    p.add_argument("--require-mermaid", action="store_true", help="mmdc が無ければ失敗させる (CI 用)")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("linkcheck", help="外部リンクの切れを確認する")
    p.add_argument("docs", nargs="?", default="docs")
    p.set_defaults(func=cmd_linkcheck)

    p = sub.add_parser("coverage", help="docstring が無い公開 API を一覧する")
    p.add_argument("paths", nargs="+")
    p.add_argument("--fail-under", type=float, metavar="PERCENT")
    p.set_defaults(func=cmd_coverage)

    p = sub.add_parser("check-diagrams", help=".drawio に書き出した SVG があるか確認する")
    p.add_argument("docs", nargs="?", default="docs")
    p.set_defaults(func=cmd_check_diagrams)

    p = sub.add_parser("confluence-check", help="Confluence への接続・認証・権限を確認する")
    p.add_argument("docs", nargs="?", default="docs")
    p.set_defaults(func=cmd_confluence_check)

    p = sub.add_parser("publish", help="Confluence 形式でビルドする。公開は --mode publish のときだけ")
    p.add_argument("docs", nargs="?", default="docs")
    p.add_argument("--mode", choices=confluence.MODES, default="local", help="local: 出力のみ (既定) / dryrun: 接続して確認のみ / publish: 公開")
    p.add_argument("--skip-connection-test", action="store_true")
    # 文書の品質は build (-W) で止める。コメント付きのページを飛ばしたときの警告で、公開まで失敗させない
    p.add_argument("--strict", action="store_true", help="警告をエラー扱いにする (既定は警告を表示するだけ)")
    p.set_defaults(func=cmd_publish)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI の入口。

    Args:
        argv: 引数。省略すると ``sys.argv`` を使う。

    Returns:
        終了コード。設定の誤りは 2。
    """
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except confluence.ConfluenceSettingsError as exc:
        print(f"設定エラー: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
