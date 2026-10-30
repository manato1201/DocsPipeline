"""``.. prompt::`` (コピーできるプロンプト) の拡張。"""

import subprocess
import sys
from pathlib import Path

import pytest

from docspipeline import prompt

pytest.importorskip("sphinx")
pytest.importorskip("myst_parser")

ROOT = Path(__file__).resolve().parent.parent

RST_PAGE = """\
手順
====

.. prompt:: リポジトリに docs/ を作る

   このリポジトリに DocsPipeline で docs/ を作ってください。
   docspipeline build docs を実行し、警告が出たら原因を直してください。
   環境変数は CONFLUENCE_API_TOKEN=<トークン> のように、名前だけを書き、値は書かないでください。

.. prompt::

   題名を省略した例です。
"""

MD_PAGE = """\
# Markdown の手順

```{prompt} Markdown から書く
文書を更新してください。`docspipeline build docs` を通してください。
```
"""


# ---- 秘密情報の検出 (単体) ----


@pytest.mark.parametrize(
    "text",
    [
        "CONFLUENCE_API_TOKEN=abcd1234efgh",
        "export API_KEY: 'sk-live-1234567890'",
        "password = hunter2hunter2",
        'SECRET_TOKEN="0123456789abcdef"',
    ],
)
def test_secret_like_values_are_found_and_not_echoed(text):
    found = prompt.find_secret(text)
    assert found is not None and found.endswith("=***")
    assert (
        "abcd1234" not in found and "1234567890" not in found and "hunter2" not in found and "0123456789" not in found
    )


@pytest.mark.parametrize(
    "text",
    [
        "CONFLUENCE_API_TOKEN=<トークン>",
        "CONFLUENCE_API_TOKEN=$CONFLUENCE_API_TOKEN",
        "環境変数 CONFLUENCE_API_TOKEN に設定する",
        "token=short",
        "docspipeline publish docs --mode dryrun",
    ],
)
def test_names_and_placeholders_are_not_secrets(text):
    assert prompt.find_secret(text) is None


def test_static_assets_ship_with_the_package():
    assert (prompt.STATIC_DIR / "dp_prompt.js").is_file()
    assert (prompt.STATIC_DIR / "dp_prompt.css").is_file()


# ---- Sphinx での出力 ----


def _project(tmp_path: Path, rst: str = RST_PAGE, md: str = MD_PAGE) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "conf.py").write_text(
        "from docspipeline.config import build_config\n"
        'globals().update(build_config(confdir=__file__, project="T", author="me"))\n',
        encoding="utf-8",
    )
    (docs / "index.rst").write_text("T\n=\n\n.. toctree::\n\n   page\n   notes\n", encoding="utf-8")
    (docs / "page.rst").write_text(rst, encoding="utf-8")
    (docs / "notes.md").write_text(md, encoding="utf-8")
    return docs


def _build(docs: Path, builder: str) -> subprocess.CompletedProcess:
    env = {"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin", "DOCSPIPELINE_OFFLINE": "1"}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-W",
            "--keep-going",
            "-b",
            builder,
            str(docs),
            str(docs / "_build" / builder),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.slow
def test_html_has_the_block_the_assets_and_the_script_tag(tmp_path):
    docs = _project(tmp_path)
    result = _build(docs, "html")
    assert result.returncode == 0, result.stderr + result.stdout
    out = docs / "_build" / "html"
    for page in ("page.html", "notes.html"):
        html = (out / page).read_text(encoding="utf-8")
        assert 'class="dp-prompt' in html and "dp-prompt-title" in html
        assert "dp_prompt.js" in html and "dp_prompt.css" in html
    page = (out / "page.html").read_text(encoding="utf-8")
    assert "リポジトリに docs/ を作る" in page and "Claude Code に渡すプロンプト" in page  # 題名の指定と、既定の題名
    assert "docspipeline build docs を実行し" in page
    assert (out / "_static" / "dp_prompt.js").is_file() and (out / "_static" / "dp_prompt.css").is_file()


@pytest.mark.slow
def test_confluence_gets_the_title_and_a_plain_code_block_without_a_button(tmp_path):
    docs = _project(tmp_path)
    result = _build(docs, "confluence")
    assert result.returncode == 0, result.stderr + result.stdout
    page = (docs / "_build" / "confluence" / "page.conf").read_text(encoding="utf-8")
    assert "リポジトリに docs/ を作る" in page
    assert "docspipeline build docs を実行し" in page
    assert "プロンプトをコピー" not in page and "<button" not in page


@pytest.mark.slow
def test_a_secret_like_value_fails_a_strict_build_without_echoing_it(tmp_path):
    leaked = "CONFLUENCE_API_TOKEN=abcd1234efgh5678"
    docs = _project(tmp_path, rst=f"手順\n====\n\n.. prompt::\n\n   次を実行する: {leaked}\n")
    result = _build(docs, "html")
    assert result.returncode != 0
    output = result.stderr + result.stdout
    assert "秘密情報らしき値" in output
    assert "abcd1234efgh5678" not in output  # 警告にも、値は出さない


@pytest.mark.slow
def test_an_empty_prompt_is_a_warning(tmp_path):
    docs = _project(tmp_path, rst="手順\n====\n\n.. prompt:: 空\n")
    assert _build(docs, "html").returncode != 0
