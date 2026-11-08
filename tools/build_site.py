"""HTML 版 (``site/``) を作る。

    python tools/build_site.py           # docs/ をビルドして、site/ に置く (mmdc が要る)
    python tools/build_site.py --check   # 元の文書と site/ が、ずれていないか確かめる (CI・pytest 用)

``site/`` は **生成物** なので、手で直さない。ブラウザで ``site/index.html`` を開けば、サーバーなしで読める。

ずれの検出: ビルドの元になったもの (文書・ソースの docstring・図・静的ファイル) の内容から、ハッシュを作り、
``site/.source-hash`` に記録する。``--check`` は、今のハッシュと記録を比べる。HTML の出力そのものは、
Sphinx や furo の版で変わるので、比べない。

出力を再現しやすくするため、``DOCSPIPELINE_OFFLINE=1`` でビルドする (外部サイトにつながない)。
リンク切れ・未解決の参照の厳しい検査 (nitpicky) は、CI の ``docspipeline build docs`` が行う。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SITE = ROOT / "site"
STAMP = SITE / ".source-hash"

#: ハッシュの元にする場所 (リポジトリのルートからの相対)。
SOURCES = ("docs", "docspipeline")
#: 元にしない場所・ファイル (生成物・キャッシュ)。
SKIP_DIRS = {"_build", "_generated", "_doxygen", "__pycache__", "node_modules", ".git"}
SKIP_SUFFIXES = {".pyc"}


def source_files(root: Path = ROOT) -> list[Path]:
    """ハッシュの元になるファイルを、整列して返す。"""
    files = []
    for name in SOURCES:
        base = root / name
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix in SKIP_SUFFIXES:
                continue
            if SKIP_DIRS.intersection(path.relative_to(base).parts):
                continue
            files.append(path)
    return files


def compute_hash(root: Path = ROOT) -> str:
    """元の文書・ソース・図の内容から、ハッシュを作る。パスと内容の両方を含める。"""
    digest = hashlib.sha256()
    for path in source_files(root):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        # 改行コードの違い (Windows など) でハッシュが変わらないようにする
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def check() -> int:
    """``site/`` が、今の元と一致しているか。一致なら 0。"""
    if not STAMP.exists():
        print("site/ がありません (python tools/build_site.py で作る)", file=sys.stderr)
        return 1
    recorded = STAMP.read_text(encoding="utf-8").strip()
    current = compute_hash()
    if recorded != current:
        print(
            "site/ が古いです。文書・ソース・図が変わっています (python tools/build_site.py で作り直す)",
            file=sys.stderr,
        )
        return 1
    return 0


def build() -> int:
    """``docs/`` をビルドして、``site/`` に置く。"""
    env = {**os.environ, "DOCSPIPELINE_OFFLINE": "1"}
    shutil.rmtree(DOCS / "_build", ignore_errors=True)
    shutil.rmtree(DOCS / "_generated", ignore_errors=True)
    result = subprocess.run(
        [sys.executable, "-m", "docspipeline", "build", str(DOCS), "--require-mermaid"],
        env=env,
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print("docs のビルドに失敗したので、site/ は作り直しません", file=sys.stderr)
        return result.returncode

    html = DOCS / "_build" / "html"
    shutil.rmtree(SITE, ignore_errors=True)
    shutil.copytree(html, SITE, ignore=shutil.ignore_patterns(".doctrees", ".buildinfo", ".buildinfo.bak"))
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    STAMP.write_text(compute_hash() + "\n", encoding="utf-8")
    shutil.rmtree(DOCS / "_build", ignore_errors=True)
    shutil.rmtree(DOCS / "_generated", ignore_errors=True)
    pages = len(list(SITE.rglob("*.html")))
    print(f"作成: {SITE} ({pages} ページ)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """``--check`` なら検査、なければ作り直す。"""
    args = sys.argv[1:] if argv is None else argv
    return check() if "--check" in args else build()


if __name__ == "__main__":
    sys.exit(main())
