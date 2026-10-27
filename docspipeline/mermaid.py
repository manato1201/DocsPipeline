"""Mermaid の図をビルド時に画像 (SVG) へ変換する Sphinx 拡張。

Confluence では Mermaid がそのまま描画されない可能性がある。このため HTML でも
Confluence でも、同じ画像を取り込む。変換には `mermaid-cli`_ (``mmdc``) を使う。

使い方::

    .. mermaid::
       :alt: 全体の流れ

       flowchart LR
           A --> B

Markdown では、言語名を ``mermaid`` にしたコードフェンスがそのまま使える (``myst_fence_as_directive``)。

``mmdc`` の探索と実行は、Sphinx に依存しない :mod:`docspipeline.mmdc` にある。
``mmdc`` が無いときの挙動は ``docspipeline_mermaid_missing`` で決める。

``literal``
    コードをそのまま表示する (手元の確認用。既定)。
``warn``
    警告を出したうえで、コードをそのまま表示する。
``error``
    ビルドを失敗させる (CI 用)。

.. _mermaid-cli: https://github.com/mermaid-js/mermaid-cli
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from . import __version__
from .mmdc import PUPPETEER_ENV, MermaidRenderError, find_mmdc, render

logger = logging.getLogger(__name__)

MISSING_ENV = "DOCSPIPELINE_MERMAID_MISSING"
MISSING_POLICIES = ("literal", "warn", "error")


class MermaidDirective(SphinxDirective):
    """``.. mermaid::`` 指示子。"""

    has_content = True
    required_arguments = 0
    option_spec: ClassVar[dict[str, Any]] = {
        "alt": lambda arg: arg or "",
        "caption": lambda arg: arg or "",
    }

    def run(self) -> list[nodes.Node]:
        """本文を画像に変換して返す。変換できないときは ``docspipeline_mermaid_missing`` に従う。"""
        code = "\n".join(self.content).strip()
        if not code:
            return [self.state.document.reporter.warning("mermaid の本文が空です", line=self.lineno)]

        config = self.env.config
        policy = os.environ.get(MISSING_ENV) or config.docspipeline_mermaid_missing
        cmd = find_mmdc(config.docspipeline_mermaid_cmd, self.env.srcdir)

        if cmd is None:
            return self._fallback(code, policy, "mmdc (mermaid-cli) が見つかりません")

        out_dir = Path(self.env.srcdir) / "_generated" / "mermaid"
        puppeteer = os.environ.get(PUPPETEER_ENV) or config.docspipeline_mermaid_puppeteer_config
        try:
            image = render(
                code,
                out_dir,
                cmd=cmd,
                fmt=config.docspipeline_mermaid_format,
                puppeteer_config=puppeteer,
            )
        except MermaidRenderError as exc:
            return self._fallback(code, policy, str(exc))

        # 先頭の "/" は、ソースのルートからの相対を意味する。
        uri = "/" + image.relative_to(self.env.srcdir).as_posix()
        img = nodes.image(uri=uri, alt=self.options.get("alt", ""))
        img["candidates"] = {"*": uri}
        self.set_source_info(img)
        caption = self.options.get("caption")
        if not caption:
            return [img]
        figure = nodes.figure("", img)
        figure += nodes.caption(caption, caption)
        return [figure]

    def _fallback(self, code: str, policy: str, reason: str) -> list[nodes.Node]:
        if policy == "error":
            raise ExtensionError(f"{self.env.docname}: Mermaid を画像にできません。{reason}")
        if policy == "warn":
            logger.warning("Mermaid を画像にできません。%s", reason, location=(self.env.docname, self.lineno))
        else:
            logger.info("Mermaid をコードのまま表示します。%s", reason)
        block = nodes.literal_block(code, code)
        block["language"] = "text"
        self.set_source_info(block)
        return [block]


def _check_policy(app: Sphinx, config: Any) -> None:
    for value in (config.docspipeline_mermaid_missing, os.environ.get(MISSING_ENV) or "literal"):
        if value not in MISSING_POLICIES:
            raise ExtensionError(
                f"docspipeline_mermaid_missing は {', '.join(MISSING_POLICIES)} のいずれかにしてください: {value!r}"
            )
    if config.docspipeline_mermaid_format not in ("svg", "png"):
        raise ExtensionError("docspipeline_mermaid_format は svg か png にしてください")


def setup(app: Sphinx) -> dict[str, Any]:
    """Sphinx 拡張の登録。"""
    app.add_config_value("docspipeline_mermaid_cmd", None, "env")
    app.add_config_value("docspipeline_mermaid_format", "svg", "env")
    app.add_config_value("docspipeline_mermaid_missing", "literal", "env")
    app.add_config_value("docspipeline_mermaid_puppeteer_config", None, "env")
    app.add_directive("mermaid", MermaidDirective)
    app.connect("config-inited", _check_policy)
    return {"version": __version__, "parallel_read_safe": True, "parallel_write_safe": True}
