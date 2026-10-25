"""``docspipeline`` コマンド。

各コマンドは薄く保つ。雛形づくりは :mod:`docspipeline.scaffold`、環境の確認は
:mod:`docspipeline.doctor` にある。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from . import confluence, diagrams, docstring_coverage, doctor, scaffold


def _run(cmd: Sequence[str], env: dict[str, str] | None = None) -> int:
    """コマンドを走らせ、出力から API トークンを伏せて表示する。"""
    merged = {**os.environ, **(env or {})}
    with subprocess.Popen(list(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=merged) as proc:
        for line in proc.stdout or ():
            print(confluence.mask_secrets(line, merged), end="", flush=True)
        return proc.wait()


def _sphinx(builder: str, docs: Path, *, mode: str, strict: bool, extra_env: dict[str, str] | None = None) -> int:
    """Sphinx を走らせる。

    Confluence のモードは **必ず引数で決める** (環境変数に残っていた値は使わない)。
    ``build`` が、環境の都合で意図せず公開してしまうのを防ぐため。
    """
    out = docs / "_build" / builder
    cmd = [sys.executable, "-m", "sphinx", "-b", builder, str(docs), str(out)]
    if strict:
        # 警告をエラー扱いにする。--keep-going で、止まらずに全部の警告を出す。
        cmd += ["-W", "--keep-going"]
    return _run(cmd, {confluence.MODE_ENV: mode, **(extra_env or {})})


def _require_confluence_env() -> bool:
    """公開に必要な環境変数が揃っているか。足りなければ、名前だけを示す。"""
    missing = confluence.missing_env()
    if missing:
        print(f"次の環境変数が未設定です: {', '.join(missing)}", file=sys.stderr)
    return not missing


def cmd_build(args: argparse.Namespace) -> int:
    """``build``: Sphinx でビルドする。Confluence 形式でも公開はしない (``local`` 固定)。"""
    extra = {"DOCSPIPELINE_MERMAID_MISSING": "error"} if args.require_mermaid else None
    return _sphinx(args.builder, Path(args.docs), mode="local", strict=not args.no_strict, extra_env=extra)


def cmd_linkcheck(args: argparse.Namespace) -> int:
    """``linkcheck``: 外部リンクの切れを確認する。"""
    return _sphinx("linkcheck", Path(args.docs), mode="local", strict=False)


def cmd_coverage(args: argparse.Namespace) -> int:
    """``coverage``: docstring が無い公開 API を一覧し、基準に満たなければ失敗にする。"""
    report = docstring_coverage.scan([Path(p) for p in args.paths])
    print(docstring_coverage.format_report(report, base=Path.cwd()))
    if args.fail_under is not None and report.percent < args.fail_under:
        print(f"カバレッジが基準 {args.fail_under}% を下回っています", file=sys.stderr)
        return 1
    return 0


def cmd_check_diagrams(args: argparse.Namespace) -> int:
    """``check-diagrams``: 書き出した SVG が無い ``.drawio`` があれば失敗にする。"""
    missing = diagrams.find_missing_exports(Path(args.docs))
    for path in missing:
        print(f"{path}: 書き出した SVG がありません (diagrams.net の Export → SVG)")
    return 1 if missing else 0


def cmd_confluence_check(args: argparse.Namespace) -> int:
    """``confluence-check``: 認証・権限・親ページを確認する (ページは変更しない)。"""
    if not _require_confluence_env():
        return 2
    cmd = [sys.executable, "-m", "sphinxcontrib.confluencebuilder", "connection-test", "--work-dir", args.docs]
    return _run(cmd, {confluence.MODE_ENV: "dryrun"})


def cmd_publish(args: argparse.Namespace) -> int:
    """``publish``: Confluence 形式でビルドする。公開するのは ``--mode publish`` のときだけ。

    ``dryrun`` と ``publish`` では、先に接続テストを行い、失敗したらビルドしない。
    """
    if args.mode != "local":
        if not _require_confluence_env():
            return 2
        if not args.skip_connection_test:
            print("== 接続テスト ==")
            rc = cmd_confluence_check(argparse.Namespace(docs=args.docs))
            if rc != 0:
                print("接続テストに失敗したため、中止します", file=sys.stderr)
                return rc
    print(f"== Confluence ビルド (mode={args.mode}) ==")
    return _sphinx("confluence", Path(args.docs), mode=args.mode, strict=args.strict)


def cmd_init(args: argparse.Namespace) -> int:
    """``init``: ``docs/`` の雛形と CI の設定を作る。既存のファイルは ``--force`` なしでは上書きしない。"""
    opts = scaffold.Options(
        target=Path(args.target).resolve(),
        project=args.project,
        author=args.author,
        package=tuple(args.package),
        cpp=tuple(args.cpp),
        hou=args.hou,
    )
    try:
        created = scaffold.write(opts, force=args.force)
    except scaffold.ScaffoldError as exc:
        for path in exc.existing:
            print(f"既にあります: {path}", file=sys.stderr)
        print("上書きするには --force を付けてください", file=sys.stderr)
        return 1
    for path in created:
        print(f"作成: {path}")
    print(f"次の手順: pip install 'docspipeline[docs]' && docspipeline build {opts.target / 'docs'}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """``doctor``: 使える機能を確認する。"""
    checks = doctor.run_checks()
    print(doctor.format_checks(checks))
    return doctor.exit_code(checks)


def build_parser() -> argparse.ArgumentParser:
    """``docspipeline`` の引数の定義を作る。"""
    parser = argparse.ArgumentParser(prog="docspipeline", description="API 文書の生成と Confluence への公開")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="リポジトリに docs/ の雛形と CI を作る")
    p.add_argument("target", help="対象リポジトリのルート")
    p.add_argument("--project", required=True, help="文書の題名")
    p.add_argument("--author", required=True)
    p.add_argument(
        "--package", action="append", default=[], metavar="PATH", help="Python のソース (docs/ からの相対)。複数可"
    )
    p.add_argument("--cpp", action="append", default=[], metavar="PATH", help="C++ のソース (docs/ からの相対)。複数可")
    p.add_argument("--hou", action="store_true", help="Houdini の hou スタブを使う")
    p.add_argument("--force", action="store_true", help="既存のファイルを上書きする")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("build", help="Sphinx でビルドする (既定は警告をエラー扱い。公開はしない)")
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
    p.add_argument(
        "--mode",
        choices=confluence.MODES,
        default="local",
        help="local: 出力のみ (既定) / dryrun: 接続して確認のみ / publish: 公開",
    )
    p.add_argument("--skip-connection-test", action="store_true")
    # 文書の品質は build (-W) で止める。コメント付きのページを飛ばしたときの警告で、公開まで失敗させない
    p.add_argument("--strict", action="store_true", help="警告をエラー扱いにする (既定は警告を表示するだけ)")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("doctor", help="手元の環境で使える機能を確認する")
    p.set_defaults(func=cmd_doctor)
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
