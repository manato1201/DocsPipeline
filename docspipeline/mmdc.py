"""``mmdc`` (mermaid-cli) の探索と実行。Sphinx に依存しない。

:mod:`docspipeline.mermaid` (Sphinx 拡張) と、:mod:`docspipeline.doctor` (環境の確認) の両方が使う。
Sphinx が入っていない環境でも ``docspipeline`` の各コマンドが動くように、拡張の側 (Sphinx を
``import`` する) とは別のモジュールにしている。
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MMDC_ENV = "DOCSPIPELINE_MMDC"
PUPPETEER_ENV = "DOCSPIPELINE_PUPPETEER_CONFIG"

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
    # Windows の npm は、拡張子なしのシェルスクリプトと mmdc.cmd の両方を置く。実行できるのは .cmd の方。
    names = ("mmdc.cmd", "mmdc") if sys.platform == "win32" else ("mmdc",)
    for base in (Path(confdir), Path(confdir).parent):
        for name in names:
            candidate = base / "node_modules" / ".bin" / name
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
    key = hashlib.sha1(json.dumps([code, fmt, MERMAID_CONFIG], sort_keys=True).encode("utf-8")).hexdigest()[:16]
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
