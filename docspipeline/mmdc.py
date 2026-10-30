"""``mmdc`` (mermaid-cli) の探索と実行。Sphinx に依存しない。

:mod:`docspipeline.mermaid` (Sphinx 拡張) と、:mod:`docspipeline.doctor` (環境の確認) の両方が使う。
Sphinx が入っていない環境でも ``docspipeline`` の各コマンドが動くように、拡張の側 (Sphinx を
``import`` する) とは別のモジュールにしている。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MMDC_ENV = "DOCSPIPELINE_MMDC"
PUPPETEER_ENV = "DOCSPIPELINE_PUPPETEER_CONFIG"

FONT_FAMILY = "Noto Sans JP, Hiragino Sans, Meiryo, sans-serif"

#: 図の色とフォント。GitHub (Markdown のまま表示) と、Sphinx (``mmdc`` で SVG にした HTML) の
#: 両方で、同じ見た目にするための値。色はこのリポジトリの構成図 (diagrams.net) と揃えてある。
THEME_VARIABLES = {
    "fontFamily": FONT_FAMILY,
    "primaryColor": "#ffffff",
    "primaryBorderColor": "#d0d5dd",
    "primaryTextColor": "#101828",
    "lineColor": "#667085",
    "clusterBkg": "#f2f4f7",
    "clusterBorder": "#d0d5dd",
    "edgeLabelBackground": "#ffffff",
}

#: 流れ図の設定。``wrappingWidth`` を大きくしないと、日本語の長い行が、単語の途中で折り返される。
FLOWCHART_CONFIG = {"wrappingWidth": 480, "nodeSpacing": 40, "rankSpacing": 56, "padding": 14}

#: 順序図の設定。下に同じ参加者を繰り返さず (``mirrorActors``)、横幅を詰めて、文字が小さくならないようにする。
SEQUENCE_CONFIG = {"mirrorActors": False, "wrap": False, "width": 150, "actorMargin": 30, "messageMargin": 34}

#: 各 Mermaid ブロックの 1 行目に置く、標準の初期化の行 (``%%{init: ...}%%``)。
#: GitHub は、この行から色とフォントを読む。``docspipeline check-mermaid`` が、全ブロックにあるかを確かめる。
MERMAID_INIT = (
    "%%{init: "
    + json.dumps(
        {
            "theme": "base",
            "fontFamily": FONT_FAMILY,
            "themeVariables": THEME_VARIABLES,
            "flowchart": FLOWCHART_CONFIG,
            "sequence": SEQUENCE_CONFIG,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    + "}%%"
)

#: 図の部品に色を付ける ``classDef`` の標準の組。入力 = 青、Sphinx・処理 = 緑、出力・公開 = オレンジ、
#: 止まる・失敗 = 赤、補助 = 白。ブロックの末尾に貼って使う。
MERMAID_CLASSDEFS = """\
    classDef input fill:#dae8fc,stroke:#1a73e8,color:#101828
    classDef proc fill:#e6f4f1,stroke:#0f9d8a,color:#101828
    classDef out fill:#fff7ed,stroke:#e8710a,color:#101828
    classDef stop fill:#fef3f2,stroke:#d92d20,color:#101828
    classDef plain fill:#ffffff,stroke:#d0d5dd,color:#101828"""

#: ``mmdc`` に渡す設定。文字を HTML (foreignObject) ではなく SVG の ``<text>`` で描かせる。
#: foreignObject は SVG を画像として取り込む先 (Confluence など) で文字が消えることがある。
#: 図に ``%%{init}%%`` が無くても、同じ見た目になるよう、色とフォントもここに入れる。
MERMAID_CONFIG = {
    "htmlLabels": False,
    "theme": "base",
    "fontFamily": FONT_FAMILY,
    "themeVariables": THEME_VARIABLES,
    "flowchart": {**FLOWCHART_CONFIG, "htmlLabels": False},
    "sequence": SEQUENCE_CONFIG,
}


class MermaidRenderError(Exception):
    """``mmdc`` の実行に失敗したときの例外。"""


def split_command(text: str, *, windows: bool | None = None) -> list[str]:
    """コマンドの文字列を、引数の列に分ける。

    POSIX の規則だと、Windows のパスの ``\\`` が消える (``C:\\Users\\me`` → ``C:Usersme``)。
    Windows では、``\\`` を残し、引用符だけを外す。

    Args:
        text: ``DOCSPIPELINE_MMDC`` などの値。
        windows: Windows の規則で分けるか。省略すると、実行中の OS に合わせる。
    """
    if windows is None:
        windows = os.name == "nt"
    parts = shlex.split(text, posix=not windows)
    if windows:
        parts = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]
    return parts


def command_exists(cmd: list[str]) -> bool:
    """コマンドの先頭 (実行ファイル) が、実在するか。``PATH`` の検索と、パスの直接指定の両方を見る。"""
    return bool(cmd) and (shutil.which(cmd[0]) is not None or Path(cmd[0]).exists())


def find_mmdc(configured: str | None, confdir: str | Path) -> list[str] | None:
    """``mmdc`` の起動コマンドを探す。

    探す順序: 設定値 → 環境変数 ``DOCSPIPELINE_MMDC`` → ``PATH`` →
    ``confdir`` とその親の ``node_modules/.bin``。

    Returns:
        コマンドの引数列。見つからなければ ``None``。
    """
    explicit = configured or os.environ.get(MMDC_ENV)
    if explicit:
        return split_command(explicit)
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
        args = [*cmd, "-i", str(src), "-o", str(tmp_out), "-c", str(conf), "-b", "white", "-q"]
        if puppeteer_config:
            args += ["-p", puppeteer_config]
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=False
            )
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


# ---- Markdown の中の Mermaid ブロックの、書式の統一 ----

_FENCE_OPEN = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})\s*\{?mermaid\}?\s*$")


def mermaid_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Markdown の行から、Mermaid のコードブロックの位置を探す。

    Args:
        lines: ファイルの行 (改行なし)。

    Returns:
        各ブロックの ``(開きの囲みの行, 閉じの囲みの行)`` (0 始まり)。閉じが無ければ、末尾まで。
    """
    blocks = []
    i = 0
    while i < len(lines):
        match = _FENCE_OPEN.match(lines[i])
        if not match:
            i += 1
            continue
        fence = match.group("fence")
        end = i + 1
        while end < len(lines) and not (
            lines[end].strip().startswith(fence[0] * len(fence)) and not lines[end].strip().strip(fence[0])
        ):
            end += 1
        blocks.append((i, end))
        i = end + 1
    return blocks


def _first_content_line(lines: list[str], start: int, end: int) -> int | None:
    for index in range(start + 1, min(end, len(lines))):
        if lines[index].strip():
            return index
    return None


def check_mermaid_text(text: str) -> list[int]:
    """標準の ``%%{init}%%`` の行で始まっていない Mermaid ブロックの、開きの行 (1 始まり) を返す。"""
    lines = text.splitlines()
    missing = []
    for start, end in mermaid_blocks(lines):
        first = _first_content_line(lines, start, end)
        if first is None or lines[first].strip() != MERMAID_INIT:
            missing.append(start + 1)
    return missing


def fix_mermaid_text(text: str) -> str:
    """標準の ``%%{init}%%`` の行を、全ブロックの先頭に入れる。

    別の ``%%{init ...}%%`` で始まるブロックは、標準の行に置き換える。
    """
    lines = text.split("\n")
    for start, end in reversed(mermaid_blocks(lines)):
        indent = _FENCE_OPEN.match(lines[start]).group("indent")  # type: ignore[union-attr]
        first = _first_content_line(lines, start, end)
        if first is not None and lines[first].strip().startswith("%%{init"):
            lines[first] = indent + MERMAID_INIT
        elif first is None or lines[first].strip() != MERMAID_INIT:
            lines.insert(start + 1, indent + MERMAID_INIT)
    return "\n".join(lines)
