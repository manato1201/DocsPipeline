"""手順に添える「プロンプトのコピー」ブロック (``.. prompt::``)。

手順の説明に、そのまま Claude Code に渡せるプロンプトを載せ、HTML ではコピーボタンを付ける。
読む人は、手順を自分で言い直さずに、そのまま貼り付けられる。

使い方 (reStructuredText)::

    .. prompt:: 新しいリポジトリに docs/ を作る

       このリポジトリに DocsPipeline で docs/ を作ってください。
       docspipeline init と docspipeline build を実行し、警告が出たら原因を直してください。

Markdown (MyST) では::

    ```{prompt} 新しいリポジトリに docs/ を作る
    このリポジトリに ...
    ```

出力:

* **HTML**: 題名・本文・「プロンプトをコピー」ボタン。ボタンは JavaScript で足す
  (JavaScript が無くても、本文は読めて、選択してコピーできる)。
* **Confluence などの HTML 以外**: 題名と、普通のコードブロック。ボタンは出ない。

プロンプトに **秘密情報を入れない**。トークンやパスワードらしき値 (``API_TOKEN=abcdef123456`` の形) が
含まれていると、警告を出す。``-W`` ならビルドが失敗する。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from . import __version__

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_TITLE = "Claude Code に渡すプロンプト"

#: 秘密情報らしき ``名前=値`` の形。名前に TOKEN / SECRET / PASSWORD / API_KEY を含み、値が 8 文字以上。
#: 値の例 (``<値>``・``$変数``・``...``) は、除く。
SECRET_PATTERN = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY)\w*\s*[=:]\s*['\"]?(?![<$.])[^\s'\"<>$]{8,}", re.IGNORECASE
)


def find_secret(text: str) -> str | None:
    """秘密情報らしき記述を見つけて、値を伏せた形で返す。見つからなければ ``None``。"""
    match = SECRET_PATTERN.search(text)
    if not match:
        return None
    head = re.split(r"[=:]", match.group(0), maxsplit=1)[0].strip()
    return f"{head}=***"


class PromptDirective(SphinxDirective):
    """``.. prompt::`` 指示子。引数は題名 (省略できる)。本文がプロンプト。"""

    has_content = True
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True

    def run(self) -> list[nodes.Node]:
        """題名と本文を、標準のノード (container・paragraph・literal_block) で組み立てる。"""
        body = "\n".join(self.content).strip()
        if not body:
            return [self.state.document.reporter.warning("prompt の本文が空です", line=self.lineno)]

        found = find_secret(body)
        if found:
            logger.warning(
                "プロンプトに秘密情報らしき値が含まれています (%s)。環境変数の名前だけを書いてください",
                found,
                location=(self.env.docname, self.lineno),
            )

        title = self.arguments[0].strip() if self.arguments else DEFAULT_TITLE
        heading = nodes.paragraph("", "", nodes.strong(title, title), classes=["dp-prompt-title"])
        literal = nodes.literal_block(body, body, classes=["dp-prompt-body"])
        literal["language"] = "text"
        container = nodes.container("", heading, literal, classes=["dp-prompt"])
        self.set_source_info(container)
        return [container]


def _add_static(app: Sphinx, config: Any) -> None:
    """コピーボタンの JavaScript と CSS を、HTML の静的ファイルに加える。"""
    static = str(STATIC_DIR)
    if static not in config.html_static_path:
        config.html_static_path.append(static)


def setup(app: Sphinx) -> dict[str, Any]:
    """Sphinx 拡張の登録。"""
    app.add_directive("prompt", PromptDirective)
    app.connect("config-inited", _add_static)
    app.add_css_file("dp_prompt.css")
    app.add_js_file("dp_prompt.js")
    return {"version": __version__, "parallel_read_safe": True, "parallel_write_safe": True}
