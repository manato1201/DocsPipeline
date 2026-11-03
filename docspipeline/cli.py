"""``docspipeline`` コマンド。

各コマンドは薄く保つ。雛形づくりは :mod:`docspipeline.scaffold`、環境の確認は
:mod:`docspipeline.doctor` にある。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from . import confluence, diagrams, docstring_coverage, doctor, messages, mmdc, scaffold, structure_map
from .files import iter_markdown_files

#: Ctrl-C で中断したときの終了コード (シェルの慣習: 128 + SIGINT)
EXIT_INTERRUPTED = 130


def _fail(what: str, why: str, next_step: str, *, label: str = "エラー", code: int = 2) -> int:
    """エラーを 3 行 (何が起きた / なぜ / 次にどうする) で標準エラーに出して、終了コードを返す。"""
    print(messages.format_error(what, why, next_step, label=label), file=sys.stderr)
    return code


def _run(cmd: Sequence[str], env: dict[str, str] | None = None) -> int:
    """コマンドを走らせ、出力から API トークンを伏せて表示する。

    Ctrl-C では、子プロセスを止めて、終了コード 130 を返す (止めた理由と、次の一手を表示する)。
    """
    merged = {**os.environ, **(env or {})}
    with subprocess.Popen(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",  # 読めない文字で、ビルドの途中で落ちない
        env=merged,
    ) as proc:
        try:
            for line in proc.stdout or ():
                print(confluence.mask_secrets(line, merged), end="", flush=True)
            return proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            return _fail(
                "Ctrl-C で中断しました",
                "実行中のコマンドを止めました。出力は途中までです",
                "もう一度実行する。途中の結果が気になるときは、docs/_build を消してから実行する",
                label="中断",
                code=EXIT_INTERRUPTED,
            )


def _sphinx(
    builder: str, docs: Path, *, mode: str, strict: bool, extra_env: dict[str, str] | None = None, fresh: bool = False
) -> int:
    """Sphinx を走らせる。

    Confluence のモードは **必ず引数で決める** (環境変数に残っていた値は使わない)。
    ``build`` が、環境の都合で意図せず公開してしまうのを防ぐため。
    """
    out = docs / "_build" / builder
    cmd = [sys.executable, "-m", "sphinx", "-b", builder, str(docs), str(out)]
    print(f"== {builder} ビルドを始めます: {docs} ==", file=sys.stderr)
    if strict:
        # 警告をエラー扱いにする。--keep-going で、止まらずに全部の警告を出す。
        cmd += ["-W", "--keep-going"]
    if fresh:
        # 保存済みの環境 (増分ビルドのキャッシュ) を使わず、全部を読み直す。
        # 環境変数の方針 (Mermaid が画像にならなければ失敗) は、読み込み時にしか効かない。
        # 前のビルドが「コードのまま」で済ませたページを、変更なしとして飛ばされると、方針が素通りする。
        cmd += ["-E"]
    started = time.monotonic()
    rc = _run(cmd, {confluence.MODE_ENV: mode, **(extra_env or {})})
    elapsed = messages.format_elapsed(time.monotonic() - started)
    if rc == 0:
        print(f"完了: {builder} ({elapsed})", file=sys.stderr)
        if builder == "html":
            print(f"次の一手: {out / 'index.html'} をブラウザで開く", file=sys.stderr)
    elif rc != EXIT_INTERRUPTED:
        if builder == "linkcheck":
            why = "外部リンクが切れているか、外部サイトにつながっていません"
            next_step = "上の出力の broken の行を直す。つながらない環境では DOCSPIPELINE_OFFLINE=1"
        else:
            why = "上の出力の WARNING / ERROR が原因です (既定では、警告も失敗にします)"
            next_step = (
                "最初の WARNING / ERROR を直す。まず docspipeline doctor で環境を確かめる。"
                "全部の警告は --no-strict で読める"
            )
        _fail(f"{builder} のビルドに失敗しました (終了コード {rc}、{elapsed})", why, next_step, label="失敗", code=rc)
    return rc


def _require_confluence_env() -> bool:
    """公開に必要な環境変数が揃っているか。足りなければ、名前だけを示す。"""
    missing = confluence.missing_env()
    if missing:
        _fail(
            f"次の環境変数が未設定です: {', '.join(missing)}",
            "dryrun / publish は、接続先と認証の設定が全部そろわないと始めません (取り違えて公開しないため)",
            "名前の環境変数を設定する (トークンは CI のシークレットなどに置き、ファイルに書かない)。"
            "確認は docspipeline doctor",
        )
    return not missing


def cmd_build(args: argparse.Namespace) -> int:
    """``build``: Sphinx でビルドする。Confluence 形式でも公開はしない (``local`` 固定)。"""
    extra = {"DOCSPIPELINE_MERMAID_MISSING": "error"} if args.require_mermaid else None
    return _sphinx(
        args.builder,
        Path(args.docs),
        mode="local",
        strict=not args.no_strict,
        extra_env=extra,
        fresh=args.require_mermaid,
    )


def cmd_linkcheck(args: argparse.Namespace) -> int:
    """``linkcheck``: 外部リンクの切れを確認する。"""
    return _sphinx("linkcheck", Path(args.docs), mode="local", strict=False)


def cmd_coverage(args: argparse.Namespace) -> int:
    """``coverage``: docstring が無い公開 API を一覧し、基準に満たなければ失敗にする。"""
    try:
        report = docstring_coverage.scan([Path(p) for p in args.paths])
    except ValueError as exc:
        return _fail(
            str(exc),
            "渡した場所が存在しないか、Python として読めないファイルがあります",
            "メッセージのパス (ファイルと行) を確かめて直す。CI の設定 (docs.yml) のパスも見直す",
        )
    print(docstring_coverage.format_report(report, base=Path.cwd()))
    if args.fail_under is not None and report.percent < args.fail_under:
        return _fail(
            f"カバレッジが基準 {args.fail_under}% を下回っています ({report.percent:.1f}%)",
            "docstring が無い公開 API があります (上の一覧)",
            "一覧の関数・クラスに docstring を書く。基準を見直すなら --fail-under (init では --min-coverage)",
            label="失敗",
            code=1,
        )
    return 0


def cmd_check_diagrams(args: argparse.Namespace) -> int:
    """``check-diagrams``: 書き出した SVG が無い ``.drawio`` があれば失敗にする。"""
    try:
        missing = diagrams.find_missing_exports(Path(args.docs))
    except ValueError as exc:
        return _fail(
            str(exc),
            "渡したディレクトリが存在しません",
            "パスの打ち間違いを確かめる (引数を省略すると docs を調べる)",
        )
    for path in missing:
        print(f"{path}: 書き出した SVG がありません (diagrams.net の Export → SVG)")
    if missing:
        print(
            "次の一手: 上の .drawio を diagrams.net で開き、Export → SVG (「ドキュメントのコピーを含める」) で\n"
            "  .drawio.svg を置く",
            file=sys.stderr,
        )
    return 1 if missing else 0


def cmd_confluence_check(args: argparse.Namespace) -> int:
    """``confluence-check``: 認証・権限・親ページを確認する (ページは変更しない)。"""
    if not _require_confluence_env():
        return 2
    rc = _connection_test(args.docs)
    if rc not in (0, EXIT_INTERRUPTED):
        _fail(
            f"接続テストに失敗しました (終了コード {rc})",
            "認証・権限・スペース・親ページのいずれかが通っていません (詳しくは上の出力。トークンの値は表示されません)",
            "ユーザー・スペースのキー・親ページの名前を見直し、トークンの期限と権限を確かめる。"
            "設定の過不足は docspipeline doctor",
            label="失敗",
            code=rc,
        )
    return rc


def _connection_test(docs: str) -> int:
    """Confluence への接続テストを走らせる (失敗の説明は、呼び出し側が書く)。"""
    cmd = [sys.executable, "-m", "sphinxcontrib.confluencebuilder", "connection-test", "--work-dir", docs]
    return _run(cmd, {confluence.MODE_ENV: "dryrun"})


def cmd_publish(args: argparse.Namespace) -> int:
    """``publish``: Confluence 形式でビルドする。公開するのは ``--mode publish`` のときだけ。

    ``dryrun`` と ``publish`` では、先に接続テストを行い、失敗したらビルドしない。
    """
    connecting = args.mode != "local"
    total = 1 if not connecting else (2 if args.skip_connection_test else 3)
    step = 0
    if connecting:
        step += 1
        print(f"[{step}/{total}] 環境変数の確認")
        if not _require_confluence_env():
            return 2
        if not args.skip_connection_test:
            step += 1
            print(f"[{step}/{total}] 接続テスト")
            rc = _connection_test(args.docs)
            if rc != 0:
                if rc == EXIT_INTERRUPTED:
                    return rc
                return _fail(
                    f"接続テストに失敗したため、ビルドを始めずに中止します (終了コード {rc})",
                    "公開の前提 (認証・権限・スペース・親ページ) が確認できていません (詳しくは上の出力)",
                    "ユーザー・スペースのキー・親ページの名前・トークンを見直してから、もう一度実行する。"
                    "手元の確認は --mode dryrun",
                    label="中止",
                    code=rc,
                )
    print(f"[{step + 1}/{total}] Confluence ビルド (mode={args.mode})")
    # 接続する・公開するときは、Mermaid が画像にならなければ失敗させる。
    # 黙ってコードのままにすると、Confluence のページが、図の無いページに置き換わってしまう。
    extra = {"DOCSPIPELINE_MERMAID_MISSING": "error"} if args.mode != "local" else None
    return _sphinx(
        "confluence", Path(args.docs), mode=args.mode, strict=args.strict, extra_env=extra, fresh=args.mode != "local"
    )


def cmd_init(args: argparse.Namespace) -> int:
    """``init``: ``docs/`` の雛形と CI の設定を作る。既存のファイルは ``--force`` なしでは上書きしない。"""
    opts = scaffold.Options(
        target=Path(args.target).resolve(),
        project=args.project,
        author=args.author,
        package=tuple(args.package),
        cpp=tuple(args.cpp),
        hou=args.hou,
        min_coverage=args.min_coverage,
    )
    missing = scaffold.missing_sources(opts)
    if missing:
        return _fail(
            "ソースの場所がありません: " + ", ".join(str(p) for p in missing),
            "--package / --cpp は docs/ からの相対パスで解決され、その場所に実在しません",
            "docs/ から見た相対パスで、実在する場所を指定する (例: --package ../src)。何も書いていません",
        )
    try:
        created = scaffold.write(opts, force=args.force)
    except scaffold.ScaffoldError as exc:
        return _fail(
            "既にあります: " + ", ".join(str(p) for p in exc.existing),
            "既存のファイルを壊さないため、1 つも書かずに止まりました",
            "上書きするなら、先にコミットしてから --force を付ける (後で差分を見て戻せる)。"
            "残すなら、別の場所を指定する",
            code=1,
        )
    for path in created:
        print(f"作成: {path}")
    print(f"次の手順: pip install 'docspipeline[docs]' && docspipeline build {opts.target / 'docs'}")
    return 0


def cmd_check_mermaid(args: argparse.Namespace) -> int:
    """``check-mermaid``: 全ての Mermaid ブロックが、標準の ``%%{init}%%`` の行で始まっているかを確かめる。

    GitHub (Markdown のまま) と Sphinx (``mmdc`` で SVG にした HTML) で、図の色とフォントを揃えるため。
    ``--fix`` で、足りない行を入れる。
    """
    roots = [Path(p) for p in args.paths]
    missing_paths = [p for p in roots if not p.exists()]
    if missing_paths:
        return _fail(
            "パスがありません: " + ", ".join(str(p) for p in missing_paths),
            "指定した場所が存在しません (既定は docs と README.md)",
            "パスの打ち間違いを確かめる。リポジトリのルートで実行しているかも確かめる",
        )
    problems = 0
    for path in iter_markdown_files(roots):
        text = path.read_text(encoding="utf-8")
        lines = mmdc.check_mermaid_text(text)
        if not lines:
            continue
        if args.fix:
            path.write_text(mmdc.fix_mermaid_text(text), encoding="utf-8")
            print(f"修正: {path} ({len(lines)} か所)")
        else:
            problems += len(lines)
            for line in lines:
                print(f"{path}:{line}: Mermaid ブロックが、標準の %%{{init}}%% の行で始まっていません")
    if problems:
        print("docspipeline check-mermaid --fix で、標準の行を入れられます", file=sys.stderr)
    return 1 if problems else 0


def cmd_mermaid_style(args: argparse.Namespace) -> int:
    """``mermaid-style``: 標準の ``%%{init}%%`` の行と ``classDef`` の組を表示する (貼り付け用)。"""
    print(mmdc.MERMAID_INIT)
    print(mmdc.MERMAID_CLASSDEFS)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """``doctor``: 使える機能を確認する。"""
    checks = doctor.run_checks()
    print(doctor.format_checks(checks))
    return doctor.exit_code(checks)


def cmd_map(args: argparse.Namespace) -> int:
    """``map``: ソースを構文解析して、依存の地図を作る。ローカルで読むだけで、外部へは送信しない。"""
    try:
        graph = structure_map.scan_package(Path(args.package))
    except ValueError as exc:
        return _fail(
            str(exc),
            "渡した場所が Python のパッケージ (__init__.py を持つディレクトリ) ではないか、読めないファイルがあります",
            "パッケージのディレクトリ (例: src/mypkg) を指定する。構文エラーなら、メッセージのファイルと行を直す",
        )
    render = {"markdown": structure_map.to_markdown, "mermaid": structure_map.to_mermaid, "json": structure_map.to_json}
    text = render[args.format](graph)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"作成: {args.output}")
    else:
        print(text, end="")
    cycles = graph.cycles()
    if cycles:
        for cycle in cycles:
            print(f"循環があります: {' <-> '.join(cycle)}", file=sys.stderr)
        if args.fail_on_cycle:
            return 1
    return 0


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
    p.add_argument(
        "--min-coverage", type=int, default=80, metavar="PERCENT", help="CI の docstring 網羅の基準 (既定 80)"
    )
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

    p = sub.add_parser("map", help="ソースを構文解析して、依存の地図を作る (外部へは送信しない)")
    p.add_argument("package", help="__init__.py を持つディレクトリ")
    p.add_argument("--format", choices=("markdown", "mermaid", "json"), default="markdown")
    p.add_argument("-o", "--output", help="書き出すファイル (省略すると標準出力)")
    p.add_argument("--fail-on-cycle", action="store_true", help="import の循環があれば失敗させる")
    p.set_defaults(func=cmd_map)

    p = sub.add_parser("check-mermaid", help="Mermaid ブロックが、標準の %%%%{init}%%%% の行で始まるか確認する")
    p.add_argument("paths", nargs="*", default=["docs", "README.md"], help="検査する場所 (既定: docs と README.md)")
    p.add_argument("--fix", action="store_true", help="足りない行を入れる")
    p.set_defaults(func=cmd_check_mermaid)

    p = sub.add_parser("mermaid-style", help="標準の %%%%{init}%%%% の行と classDef を表示する")
    p.set_defaults(func=cmd_mermaid_style)

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
        return _fail(
            str(exc),
            "公開の設定が、足りないか、安全でない値です (黙って別の動作にはしません)",
            "docspipeline doctor で、不足している名前と、モードの値を確かめる",
            label="設定エラー",
        )
    except KeyboardInterrupt:
        return _fail(
            "Ctrl-C で中断しました",
            "実行を止めました",
            "もう一度実行する",
            label="中断",
            code=EXIT_INTERRUPTED,
        )


if __name__ == "__main__":
    sys.exit(main())
