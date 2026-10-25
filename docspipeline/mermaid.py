"""Mermaid の図をビルド時に画像 (SVG) へ変換する Sphinx 拡張。

Confluence では Mermaid がそのまま描画されない可能性がある。このため HTML でも
Confluence でも、同じ画像を取り込む。変換には `mermaid-cli`_ (``mmdc``) を使う。

使い方::

    .. mermaid::
       :alt: 全体の流れ

       flowchart LR
           A --> B

Markdown では、言語名を ``mermaid`` にしたコードフェンスがそのまま使える (``myst_fence_as_directive``)。

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

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

logger = logging.getLogger(__name__)

MMDC_ENV = "DOCSPIPELINE_MMDC"
PUPPETEER_ENV = "DOCSPIPELINE_PUPPETEER_CONFIG"
MISSING_ENV = "DOCSPIPELINE_MERMAID_MISSING"
MISSING_POLICIES = ("literal", "warn", "error")

#: 文字を HTML (foreignObject) ではなく SVG の ``<text>`` で描かせる。
#: foreignObject は SVG を画像として取り込む先 (Confluence など) で文字が消えることがある。
MERMAID_CONFIG = {
    "htmlLabels": False,
    "flowchart": {"htmlLabels": False},
}


class MermaidRenderError(Exception):
    """``mmdc`` の実行に失敗したときの例外。"""


def find_mmdc(configured: str | None, confdir: str | Path) -> list[str] | None:
    """``mmdc`` の起動コマンドを探す。

    探す順序: 設定値 → 環境変数 ``DOCSPIPELINE_MMDC`` → ``PATH`` →
    ``confdir`` とその親の ``node_modules/.bin``。

    Returns:
        コマンドの引数列。見つからなければ ``None``。
    """
    explicit = configured or os.environ.get(MMDC_ENV)
    if explicit:
        return shlex.split(explicit)
    on_path = shutil.which("mmdc")
    if on_path:
        return [on_path]
    for base in (Path(confdir), Path(confdir).parent):
        candidate = base / "node_modules" / ".bin" / "mmdc"
        if candidate.exists():
            return [str(candidate)]
    return None


def render(code: str, out_dir: Path, *, cmd: list[str], fmt: str = "svg", puppeteer_config: str | None = None) -> Path:
    """Mermaid のコードを画像にして ``out_dir`` に置く。

    ファイル名は内容のハッシュ。同じ図は再変換しない。

    Args:
        code: Mermaid のコード。
        out_dir: 出力先のディレクトリ。
        cmd: ``mmdc`` の起動コマンド。
        fmt: 出力形式 (``svg`` または ``png``)。
        puppeteer_config: ``mmdc -p`` に渡す設定ファイル (サンドボックス無効化など)。

    Returns:
        作成 (または既存) の画像ファイルのパス。

    Raises:
        MermaidRenderError: ``mmdc`` が失敗したとき。
    """
    key = hashlib.sha1(
        json.dumps([code, fmt, MERMAID_CONFIG], sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"mermaid-{key}.{fmt}"
    if out.exists():
        return out

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "diagram.mmd"
        src.write_text(code, encoding="utf-8")
        conf = tmp_dir / "mermaid.json"
        conf.write_text(json.dumps(MERMAID_CONFIG), encoding="utf-8")
        tmp_out = tmp_dir / f"diagram.{fmt}"
        args = [*cmd, "-i", str(src), "-o", str(tmp_out), "-c", str(conf), "-b", "transparent", "-q"]
        if puppeteer_config:
            args += ["-p", puppeteer_config]
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MermaidRenderError(f"mmdc を実行できません: {exc}") from exc
        if proc.returncode != 0 or not tmp_out.exists():
            detail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
            raise MermaidRenderError("mmdc が失敗しました: " + " / ".join(detail))
        # 並列ビルドで半端なファイルを読まれないよう、同じ場所に写してから 1 手で置き換える。
        part = out.with_suffix(out.suffix + ".part")
        shutil.copyfile(tmp_out, part)
        os.replace(part, out)
    return out


class MermaidDirective(SphinxDirective):
    """``.. mermaid::`` 指示子。"""

    has_content = True
    required_arguments = 0
    option_spec = {
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
    return {"version": "0.1.0", "parallel_read_safe": True, "parallel_write_safe": True}
