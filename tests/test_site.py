"""HTML 版 (``site/``) が、元の文書・ソース・図と、ずれていないこと。"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_site  # noqa: E402


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs" / "_build").mkdir(parents=True)
    (root / "docs" / "_generated").mkdir()
    (root / "docspipeline" / "__pycache__").mkdir(parents=True)
    (root / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
    (root / "docspipeline" / "m.py").write_text('"""m."""\n', encoding="utf-8")
    (root / "docs" / "_build" / "junk.html").write_text("x", encoding="utf-8")
    (root / "docs" / "_generated" / "g.svg").write_text("x", encoding="utf-8")
    (root / "docspipeline" / "__pycache__" / "m.pyc").write_bytes(b"\0")
    return root


def test_hash_changes_when_a_document_or_a_docstring_changes(tmp_path):
    root = _tree(tmp_path)
    before = build_site.compute_hash(root)
    (root / "docs" / "a.md").write_text("# B\n", encoding="utf-8")
    assert build_site.compute_hash(root) != before
    changed = build_site.compute_hash(root)
    (root / "docspipeline" / "m.py").write_text('"""m2."""\n', encoding="utf-8")
    assert build_site.compute_hash(root) != changed


def test_hash_changes_when_a_file_is_added_or_renamed(tmp_path):
    root = _tree(tmp_path)
    before = build_site.compute_hash(root)
    (root / "docs" / "b.md").write_text("# new\n", encoding="utf-8")
    added = build_site.compute_hash(root)
    assert added != before
    (root / "docs" / "b.md").rename(root / "docs" / "c.md")
    assert build_site.compute_hash(root) != added  # 内容が同じでも、パスが変われば別


def test_hash_ignores_generated_files_caches_and_line_endings(tmp_path):
    root = _tree(tmp_path)
    before = build_site.compute_hash(root)
    (root / "docs" / "_build" / "junk.html").write_text("changed", encoding="utf-8")
    (root / "docs" / "_generated" / "g.svg").write_text("changed", encoding="utf-8")
    (root / "docspipeline" / "__pycache__" / "m.pyc").write_bytes(b"\1\2")
    assert build_site.compute_hash(root) == before
    (root / "docs" / "a.md").write_bytes(b"# A\r\n")  # CRLF
    assert build_site.compute_hash(root) == before


def test_hash_does_not_include_site_itself(tmp_path):
    root = _tree(tmp_path)
    before = build_site.compute_hash(root)
    (root / "site").mkdir()
    (root / "site" / "index.html").write_text("x", encoding="utf-8")
    assert build_site.compute_hash(root) == before


def test_committed_site_matches_the_sources():
    """文書・docstring・図を変えたのに、HTML 版を作り直し忘れると、ここで落ちる。"""
    if not build_site.STAMP.exists():
        pytest.fail("site/ がありません。python tools/build_site.py で作る")
    assert build_site.check() == 0, "site/ が古い: python tools/build_site.py で作り直す"


def test_committed_site_is_a_browsable_html_bundle():
    site = build_site.SITE
    assert (site / "index.html").is_file()
    index = (site / "index.html").read_text(encoding="utf-8")
    assert "DocsPipeline" in index
    for page in ("overview.html", "usage.html", "confluence.html", "design.html", "api.html"):
        assert (site / page).is_file(), page
    assert list((site / "_images").glob("mermaid-*.svg")), "Mermaid の図が SVG になっていない (mmdc で作ること)"
    assert not (site / ".doctrees").exists()


#: コードのまま HTML に入った Mermaid: コードブロックの先頭が、標準の %%{init ...}%% の行になっている
#: (check-mermaid が、全ての図の先頭に、この行を置かせる。書き方の例の `flowchart` だけのブロックは、対象にしない)
_RAW_MERMAID = re.compile(r"<pre[^>]*>(?:<[^>]+>)*\s*%%\{init")

#: 講義・テストの例に使う、ダミーの値と、山括弧のプレースホルダー (``TOKEN=<トークン>``)、伏せ字 (``TOKEN=***``)。
#: どれも、本物の秘密ではない。
DUMMY_SECRET_FRAGMENTS = ("abcd1234", "abcdef123456", "0123456789", "sk-live-1234567890", "hunter2", "&lt;", "***")


def test_committed_site_has_no_raw_mermaid_code_or_secrets():
    """mmdc が無いまま作ると、図がコードのまま入る。トークンらしき値 (ダミーを除く) も入っていないこと。"""
    from docspipeline.prompt import SECRET_PATTERN

    for path in build_site.SITE.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        # 図がコードのまま入ると、コードブロックの先頭が %%{init ...}%% になる
        # (講義が、標準の行を例として出力に載せるときは、先頭が別の文字なので、引っかからない)
        assert not _RAW_MERMAID.search(text), f"{path.name}: 図がコードのまま"
        real = [
            m.group(0)
            for m in SECRET_PATTERN.finditer(text)
            if not any(d in m.group(0) for d in DUMMY_SECRET_FRAGMENTS)
        ]
        assert not real, f"{path.name}: 秘密情報らしき値 ({len(real)} 件)"
