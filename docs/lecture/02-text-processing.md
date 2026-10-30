# 第 2 回 文字列・正規表現・ハッシュ

> 所要時間の目安: 3 時間 / 前提: 第 1 回

## この回のゴール

- 文字 (`str`) とバイト (`bytes`)、UTF-8 の関係を説明できる。
- **文字の「幅」** が、図や文書の見た目に影響する理由と、その扱い方が分かる。
- 正規表現の基本 (文字クラス・量指定子・グループ・先読み) を使い、DocsPipeline の 3 つの正規表現を読める。
- 文字列の **置き換えの落とし穴** (置換の連鎖) を説明し、避けられる。
- ハッシュで **内容から名前を作る** (キャッシュのキー) 仕組みが分かる。
- 秘密情報を出力から **伏せる** 実装 (`mask_secrets`) の、細部の判断を説明できる。

## 1. 文字とバイト

コンピュータが保存・送受信するのは **バイト** (0〜255 の数の並び) です。
人が読む **文字** との対応が **文字コード** で、現在は **UTF-8** が標準です。

```python
# 実行できる
text = "日本語 abc"
print(len(text), "文字")
data = text.encode("utf-8")  # str → bytes
print(len(data), "バイト", data[:6])
print(data.decode("utf-8"))  # bytes → str
broken = data[:4]  # 文字の途中で切れたバイト列
print(repr(broken.decode("utf-8", errors="replace")))
try:
    broken.decode("utf-8")
except UnicodeDecodeError as exc:
    print("UnicodeDecodeError:", exc.reason)
```

```text
# 出力
7 文字
13 バイト b'\xe6\x97\xa5\xe6\x9c\xac'
日本語 abc
'日�'
UnicodeDecodeError: unexpected end of data
```

- 日本語 1 文字は、UTF-8 で **3 バイト**、英数字は 1 バイトです。
- 文字の途中で切れたバイト列は、そのままでは読めません。`errors="replace"` なら、読めない部分が `�` (�) に置き換わります。

**なぜ大事か**: 外部コマンド (`mmdc`・`doxygen`・`sphinx`) の出力を読むとき、OS の既定の文字コード
(Windows では cp932 など) で読むと、**日本語の出力で、読み込み中に落ちる** ことがあります。
DocsPipeline は、子プロセスの出力を読む場所で、**文字コードと、読めないときの扱い** を明示しています (第 3 回)。

## 2. 文字の「幅」

等幅のコンソールや、図の中で、**全角の文字は半角の 2 倍の幅** を取ります。
文字数 (`len`) と、見た目の幅は、一致しません。

```python
# 実行できる
import unicodedata

for ch in ["a", "あ", "漢", "ｱ", "１", "A"]:
    print(repr(ch), unicodedata.east_asian_width(ch))
```

```text
# 出力
'a' Na
'あ' W
'漢' W
'ｱ' H
'１' F
'A' Na
```

`east_asian_width` は、文字の **東アジアの幅の分類** を返します。

| 分類 | 意味 | 幅 |
|---|---|---|
| `W` (Wide) | 全角の漢字・かな | 2 |
| `F` (Fullwidth) | 全角の英数字・記号 | 2 |
| `Na` (Narrow) | 半角の英数字 | 1 |
| `H` (Halfwidth) | 半角のカナ | 1 |
| `A` (Ambiguous) | 場面で変わる (ギリシャ文字など) | 1 または 2 |

### 使い道 (1): reStructuredText の見出しの下線

reStructuredText の見出しは、**下線の長さが、見出しの幅以上** でなければなりません。
全角の見出しで、下線が足りないと、docutils が警告します。

```python
# 引用: docspipeline/scaffold.py::title_rule
def title_rule(text: str) -> str:
    """reStructuredText の見出しの下線を返す。

    全角の文字は幅 2 として数える。足りないと docutils が警告するため。
    """
    width = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return "=" * max(width, 4)
```

`sum(... for c in text)` は、**ジェネレータ式** (第 1 回の内包表記の仲間) で、各文字の幅を足します。
`max(width, 4)` は、極端に短い見出しでも、下線が 4 文字以上になるようにします。

```python
# 実行できる
import io
from docutils.core import publish_doctree
from docspipeline.scaffold import title_rule


def warnings_for(source):
    stream = io.StringIO()
    publish_doctree(source, settings_overrides={"warning_stream": stream, "report_level": 2})
    return stream.getvalue().strip().splitlines()


title = "日本語の見出し"
print("文字数", len(title), "/ 幅", len(title_rule(title)))
print("下線が文字数ぶん:", warnings_for(f"{title}\n{'=' * len(title)}\n\n本文\n"))
print("title_rule:", warnings_for(f"{title}\n{title_rule(title)}\n\n本文\n"))
```

```text
# 出力
文字数 7 / 幅 14
下線が文字数ぶん: ['<string>:2: (WARNING/2) Title underline too short.', '', '日本語の見出し', '=======']
title_rule: []
```

下線が **文字数ぶん** だと、docutils が「下線が短い」と警告します。`title_rule` を使うと、警告が出ません。

### 使い道 (2): 図の中のラベルの幅

構成図の矢印のラベルには、**白い背景の四角** を敷きます。その幅を決めるには、文字列の幅を **見積もる** 必要があります。

```python
# 引用: tools/diagrams/kit.py::text_width
def text_width(text: str, size: float, mono: bool = False) -> float:
    """文字列の幅 (px) の見積り。全角は 1 文字ぶん、半角は約 0.55 (等幅は 0.6) 文字ぶん。

    小数第 2 位に丸める。Python 3.12 から、浮動小数点の ``sum`` の誤差の出方が変わり、
    丸めないと、版によって生成物 (.drawio / .svg) の末尾の桁が違ってしまう。
    """
    ascii_w = 0.6 if mono else 0.55
    return round(sum(size if unicodedata.east_asian_width(c) in "WF" else size * ascii_w for c in text), 2)
```

全角 1 文字は `size` (フォントの大きさ) と同じ幅、半角は約 0.55 倍 (等幅フォントは 0.6 倍) と見積もっています。
正確な値は、フォントごとに違うので、**見積り** です。ずれても読めるよう、背景の四角に、余白を足しています (第 11 回)。

## 3. 正規表現

正規表現は、文字列の **パターン** を書く小さな言語です。Python では `re` モジュールを使います。

| 記法 | 意味 | 例 |
|---|---|---|
| `.` | 任意の 1 文字 (改行を除く) | `a.c` は `abc` |
| `\d` `\w` `\s` | 数字 / 英数字と `_` / 空白 | `\d{4}` は 4 桁の数字 |
| `[abc]` `[^abc]` | クラス: これらのどれか / これら **以外** | `[^\s]` は空白以外 |
| `*` `+` `?` | 0 回以上 / 1 回以上 / 0 か 1 回 | `\d+` は数字の並び |
| `{n}` `{n,}` `{n,m}` | n 回 / n 回以上 / n〜m 回 | `{8,}` は 8 回以上 |
| `( )` `(?P<名>...)` | グループ (取り出す) / 名前つきグループ | |
| `(?: )` | **取り出さない** グループ | `(?:ab)+` |
| `\|` | または | `TOKEN\|SECRET` |
| `^` `$` | 行頭 / 行末 | |
| `(?! )` | **先読み (否定)**: 直後が、これでないこと | `(?![<$])` |

```python
# 実行できる
import re

text = "build 2026-10-30 ok, build 2026-11-02 failed"
print(re.findall(r"\d{4}-\d{2}-\d{2}", text))
m = re.search(r"build (\d{4})-(\d{2})", text)
print(m.group(0), "|", m.group(1), m.group(2), "|", m.span())
print(re.sub(r"\d", "#", text))
print(re.split(r"[,\s]+", text))
```

```text
# 出力
['2026-10-30', '2026-11-02']
build 2026-10 | 2026 10 | (0, 13)
build ####-##-## ok, build ####-##-## failed
['build', '2026-10-30', 'ok', 'build', '2026-11-02', 'failed']
```

### 貪欲と最短

量指定子は、既定で **できるだけ長く** 取ります (貪欲)。`?` を後ろに付けると、**できるだけ短く** 取ります。

```python
# 実行できる
import re

html = "<b>太字</b> と <b>別</b>"
print(re.findall(r"<b>.*</b>", html))  # 貪欲: 最初の <b> から最後の </b> まで
print(re.findall(r"<b>.*?</b>", html))  # 最短: 1 組ずつ
```

```text
# 出力
['<b>太字</b> と <b>別</b>']
['<b>太字</b>', '<b>別</b>']
```

### 読解 1: Markdown のコードフェンスを見つける

`docspipeline check-mermaid` は、Markdown の中の **Mermaid のコードブロック** を探します。その入口が、この正規表現です。

```python
# 抜粋ファイル: docspipeline/mmdc.py
_FENCE_OPEN = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})\s*\{?mermaid\}?\s*$")
```

部品ごとに読みます。

| 部品 | 意味 |
|---|---|
| `^` ... `$` | 行の **全体** がこの形 (本文の途中に「mermaid のフェンス」と書いても、一致しない) |
| `(?P<indent> {0,3})` | 行頭の空白が 0〜3 個 (Markdown の規則。4 個以上は、コードとして扱われる) |
| `(?P<fence>...)` | 逆引用符 3 個以上、または `~` 3 個以上 (コードフェンスの記号) |
| `\s*` | 空白があってもよい |
| `\{?mermaid\}?` | `mermaid`、または MyST の `{mermaid}` |

```python
# 実行できる
from docspipeline.mmdc import _FENCE_OPEN

for line in [
    "```mermaid",
    "````mermaid",
    "  ```{mermaid}",
    "~~~mermaid",
    "    ```mermaid",
    "```python",
    "本文に ```mermaid と書く",
]:
    m = _FENCE_OPEN.match(line)
    print(f"{line!r:34} → ", "一致" if m else "不一致")
```

```text
# 出力
'```mermaid'                       →  一致
'````mermaid'                      →  一致
'  ```{mermaid}'                   →  一致
'~~~mermaid'                       →  一致
'    ```mermaid'                   →  不一致
'```python'                        →  不一致
'本文に ```mermaid と書く'               →  不一致
```

### 読解 2: 秘密情報らしき記述を見つける

手順書に載せるプロンプトに、**トークンの値** が混ざっていないかを調べる正規表現です (第 7 回の `prompt` 拡張)。

```python
# 抜粋ファイル: docspipeline/prompt.py
SECRET_PATTERN = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY)\w*\s*[=:]\s*['\"]?(?![<$.])[^\s'\"<>$]{8,}", re.IGNORECASE
)
```

| 部品 | 意味 |
|---|---|
| `(?:TOKEN\|SECRET\|PASSWORD\|PASSWD\|API_?KEY)` | 名前に、これらのどれかを含む |
| `\w*` | 名前の続き (`TOKEN_SCOPED` など) |
| `\s*[=:]\s*` | `=` か `:` で、値につながる |
| `['\"]?` | 値を囲む引用符 (あってもなくても) |
| `(?![<$.])` | **先読み (否定)**: 値が `<`・`$`・`.` で **始まらない** |
| `[^\s'\"<>$]{8,}` | 空白・引用符・`<>`・`$` **以外** の文字が、8 個以上 |
| `re.IGNORECASE` | 大文字小文字を区別しない |

**設計の判断**: 先読みの `(?![<$.])` が大事です。手順書には、`CONFLUENCE_API_TOKEN=<トークン>` や
`CONFLUENCE_API_TOKEN=$CONFLUENCE_API_TOKEN` のような **例** を書きます。これらは **秘密ではない** ので、
警告してはいけません。警告が多すぎると、人は警告を無視するようになります。

```python
# 実行できる
from docspipeline.prompt import find_secret

samples = [
    "CONFLUENCE_API_TOKEN=abcd1234efgh",  # 値らしきもの
    "export API_KEY: 'sk-live-1234567890'",
    "CONFLUENCE_API_TOKEN=<トークン>",  # 例 (プレースホルダー)
    "CONFLUENCE_API_TOKEN=$CONFLUENCE_API_TOKEN",
    "token=short",  # 短すぎる (8 文字未満)
    "環境変数 CONFLUENCE_API_TOKEN に設定する",  # = が無い
]
for text in samples:
    print(f"{text!r:50} →", find_secret(text))
```

```text
# 出力
'CONFLUENCE_API_TOKEN=abcd1234efgh'                → TOKEN=***
"export API_KEY: 'sk-live-1234567890'"             → API_KEY=***
'CONFLUENCE_API_TOKEN=<トークン>'                      → None
'CONFLUENCE_API_TOKEN=$CONFLUENCE_API_TOKEN'       → None
'token=short'                                      → None
'環境変数 CONFLUENCE_API_TOKEN に設定する'                  → None
```

`find_secret` は、見つけても **値を返しません** (`名前=***` の形)。警告にも、値を出さないためです。

## 4. 置き換えの落とし穴: 置換の連鎖

雛形に値を埋め込む (`@@project@@` → `My Tool`) とき、**1 つずつ** `str.replace` を繰り返すと、
置き換えた結果が、**次の置換の対象になる** ことがあります。

```python
# 実行できる
import re

template = "name=@@project@@ author=@@author@@"
values = {"project": "@@author@@", "author": "me"}  # プロジェクト名が、たまたま @@author@@ だった

chained = template
for key, value in values.items():
    chained = chained.replace(f"@@{key}@@", value)
print("連鎖 :", chained)

single = re.sub(r"@@(\w+)@@", lambda m: values.get(m.group(1), m.group(0)), template)
print("1 回 :", single)
```

```text
# 出力
連鎖 : name=me author=me
1 回 : name=@@author@@ author=me
```

- **連鎖**: `project` を置き換えると `@@author@@` が現れ、次の `author` の置換で、**それも** 置き換わってしまいます (`name=me`)。
- **1 回の走査**: 元の文字列を **1 度だけ** 左から読み、一致した所を、その場で置き換えます。置き換えた結果は、読み直しません。

`re.sub` の第 2 引数に **関数** を渡せる点が、ポイントです。一致ごとに、関数が呼ばれ、**置き換える文字列を返します**。
`values.get(key, m.group(0))` は、辞書に無い名前を、**そのまま残します** (`m.group(0)` は、一致した全体)。

実際の雛形の処理 (`scaffold.plan`) は、この書き方です (第 8 回で全体を読みます)。

```python
# 抜粋: docspipeline/scaffold.py::plan
        # 1 回の走査で置き換える。値の中に @@名前@@ があっても、さらに置き換わらない
        text = re.sub(r"@@(\w+)@@", lambda m: values.get(m.group(1), m.group(0)), src.read_text(encoding="utf-8"))
```

## 5. ハッシュ: 内容から「名前」を作る

**ハッシュ関数** は、任意の長さのデータから、**固定長の指紋** を作ります。性質は 3 つです。

1. **同じ入力 → 同じ出力** (決まった値)。
2. **入力が少し違うだけで、出力は大きく変わる**。
3. 出力から、入力を **逆算できない**。

```python
# 実行できる
import hashlib


def short(text, n=12):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


print(short("flowchart LR\n A --> B"))
print(short("flowchart LR\n A --> B"))  # 同じ入力 → 同じ
print(short("flowchart LR\n A --> C"))  # 1 文字違うだけで、まるで別
print(len(hashlib.sha256(b"").hexdigest()), "文字 (16 進)")
```

```text
# 出力
919f7bf25c14
919f7bf25c14
aa818067c3e9
64 文字 (16 進)
```

### 使い道 (1): キャッシュのキー (`mmdc.render`)

Mermaid の図を SVG に変える処理は、**数秒かかります** (Chromium を起動する)。同じ図を何度も変換したくありません。
そこで、**図のコードのハッシュ** を、ファイル名にします。

```python
# 抜粋: docspipeline/mmdc.py::render
    key = hashlib.sha1(json.dumps([code, fmt, MERMAID_CONFIG], sort_keys=True).encode("utf-8")).hexdigest()[:16]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"mermaid-{key}.{fmt}"
    if out.exists():
        return out
```

- キーの元は、**コード・形式 (svg か png)・設定** の 3 つ。どれかが変わると、別のファイルになり、**古い画像を使い回しません**。
- ファイルが **すでにあれば、変換せずに返します** (キャッシュのヒット)。
- `sort_keys=True` は、辞書の **キーの順序を固定** します。順序が違うだけで別のハッシュにならないようにするためです。
- `[:16]` で、先頭 16 文字だけを使います。衝突の確率は、実用上ゼロに近いです。

ここでは、安全のためではなく **指紋として** ハッシュを使っているので、`sha1` で足ります。
**セキュリティが目的なら**、`sha256` 以上を使います (改ざんの検出など)。

### 使い道 (2): 生成物のずれの検出 (HTML 版)

`site/` (HTML 版) が、**元の文書と合っているか** を確かめるのにも、ハッシュを使います。
文書・ソース・図の内容から、1 つのハッシュを作り、`site/.source-hash` に記録します。
元が変わるとハッシュが変わるので、「作り直し忘れ」を検出できます (第 12 回)。

## 6. JSON

JSON は、辞書・リスト・文字列・数・真偽値・`null` を表す、テキストの形式です。

```python
# 実行できる
import json

data = {"name": "日本語", "items": [1, 2], "ok": True, "none": None}
print(json.dumps(data))  # 既定: 日本語がエスケープされる
print(json.dumps(data, ensure_ascii=False))  # そのまま
print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))  # 空白なし (1 行を短く)
print(json.loads('{"a": [1, 2, {"b": null}]}'))
```

```text
# 出力
{"name": "\u65e5\u672c\u8a9e", "items": [1, 2], "ok": true, "none": null}
{"name": "日本語", "items": [1, 2], "ok": true, "none": null}
{"name":"日本語","items":[1,2],"ok":true,"none":null}
{'a': [1, 2, {'b': None}]}
```

Mermaid の図の 1 行目 (標準の `%%{init}%%` の行) は、JSON を `separators=(",", ":")` で **短く 1 行** にして作っています。

```python
# 実行できる
from docspipeline.mmdc import MERMAID_INIT

print(MERMAID_INIT[:70], "...")
print("全体の長さ:", len(MERMAID_INIT), "/ 行数:", MERMAID_INIT.count("\n") + 1)
```

```text
# 出力
%%{init: {"theme":"base","fontFamily":"Noto Sans JP, Hiragino Sans, Me ...
全体の長さ: 537 / 行数: 1
```

GitHub は、この **1 行** から、図の色とフォントを読みます。だから、改行を含まないことが、仕様です。

## 7. 秘密情報を伏せる: `mask_secrets`

DocsPipeline は、子プロセスの出力を表示するとき、**API トークンの値を `***` に置き換えます**。

```python
# 引用: docspipeline/confluence.py::mask_secrets
def mask_secrets(text: str, environ: Mapping[str, str] | None = None) -> str:
    """文字列中のトークンの値を ``***`` に置き換える。

    Args:
        text: ログなどの出力。
        environ: 環境変数。省略すると ``os.environ``。

    Returns:
        トークンを伏せた文字列。
    """
    env = os.environ if environ is None else environ
    for name in SECRET_ENV:
        value = env.get(name)
        # 極端に短い値は通常の文字列まで潰してしまうので対象外にする。
        if value and len(value) >= 8:
            text = text.replace(value, "***")
    return text
```

細部の判断を読みます。

1. **`environ` を引数に取る**: `os.environ` を直接読まず、`Mapping` を受け取ります。テストで、辞書を渡せます (第 3 回)。
2. **`len(value) >= 8`**: 値が短いと、**普通の文字列まで潰します**。たとえばトークンが `a` なら、出力中の全ての `a` が `***` になります。
   これは、読めない出力を作る **別の事故** です。8 文字未満は、そもそもトークンとして不自然なので、対象外にします。
3. **`str.replace`**: 値を **そのまま** 探して置き換えます。正規表現ではないので、トークンに記号が含まれていても、安全です
   (正規表現にすると、`.` や `+` が特別な意味を持つ)。
4. **限界**: 出力が **値を加工して** 表示する場合 (たとえば Base64 にする) は、検出できません。
   だから、トークンを **そもそも出力に出さない** 設計 (名前だけを示す) が、第一の防御です。

```python
# 実行できる
from docspipeline.confluence import mask_secrets

env = {"CONFLUENCE_API_TOKEN": "tok-0123456789abcdef"}
print(mask_secrets("auth failed for tok-0123456789abcdef (user me@example.com)", env))
print(mask_secrets("a b c", {"CONFLUENCE_API_TOKEN": "a"}))  # 短い値は対象外
print(mask_secrets("token is tok-0123456789abcdef", {}))  # 環境に無ければ、置き換えない
```

```text
# 出力
auth failed for *** (user me@example.com)
a b c
token is tok-0123456789abcdef
```

## ハンズオン

1. 第 2 節の `title_rule` で、自分の名前・好きな見出しの下線の長さを調べる。半角と全角を混ぜてみる。
2. `re.findall` で、`docs/` の Markdown から、`[テキスト](リンク先)` の形を **全部** 抜き出す正規表現を作る。
   (ヒント: `\[([^\]]+)\]\(([^)]+)\)`。`docs/**/*.md` を `Path.rglob` で読む)
3. `docspipeline check-mermaid docs` を実行し、終了コードを確かめる (`echo $?`)。

## 確認問題

1. `"日本語"` を UTF-8 に変換すると、何バイトになりますか。なぜ、文字数と違うのですか。
2. `east_asian_width` が `W` と `F` の文字を、幅 2 と数える理由は何ですか。
3. `re.findall(r"<b>.*</b>", s)` が、期待より長く取ってしまうのはなぜですか。直し方は。
4. `SECRET_PATTERN` の `(?![<$.])` は、何のためにありますか。外すと、何が困りますか。
5. 置換の連鎖とは何ですか。`re.sub` の 1 回の走査で、なぜ防げますか。
6. `mmdc.render` のキーに、図のコードだけでなく、**設定** (`MERMAID_CONFIG`) も入れているのはなぜですか。
7. (書く問題) 文字列から、`@@名前@@` の **名前の一覧** を、出てくる順に、重複なしで返す関数 `placeholders(text)` を書いてください。

## 解答

1. 9 バイト。日本語 1 文字が、UTF-8 で 3 バイトだから (文字数は 3)。バイト数と文字数は、別の概念。
2. 等幅のコンソールや、見出しの下線・図のラベルで、全角の文字が、半角の **2 倍の幅** を取るため。
   幅を無視すると、下線が足りなくなる (docutils の警告)、ラベルの背景がはみ出す、などが起きる。
3. 量指定子 `*` が **貪欲** で、できるだけ長く取る (最初の `<b>` から、最後の `</b>` まで)。
   `.*?` と、最短にする。
4. 値が `<`・`$`・`.` で始まるものを、**例 (プレースホルダー)** として除くため。外すと、
   `API_TOKEN=<トークン>` のような、正しい書き方にも警告が出る。警告が多すぎると、本物の警告が無視される。
5. 1 つずつ置換すると、前の置換の **結果** が、次の置換の対象になる現象。`re.sub` は、元の文字列を **1 度だけ** 読み、
   置き換えた結果を読み直さないので、起きない。
6. 設定 (フォント・色・`htmlLabels`) が変わると、**同じコードでも、違う画像** になるから。設定をキーに入れないと、
   設定を変えても、古い見た目の画像が使い回される。
7. 例 (実行して確かめてある):

```python
# 実行できる
import re


def placeholders(text):
    seen = []
    for name in re.findall(r"@@(\w+)@@", text):
        if name not in seen:
            seen.append(name)
    return seen


print(placeholders("@@a@@ と @@b@@ と @@a@@、@@project_repr@@"))
```

```text
# 出力
['a', 'b', 'project_repr']
```

## まとめ

| 概念 | 要点 | このリポジトリでの例 |
|---|---|---|
| 文字とバイト | 文字コードを **明示** する。`errors=` で、読めないときの扱いを決める | 子プロセスの出力 |
| 文字の幅 | 全角は 2。`east_asian_width` | `title_rule`・`text_width` |
| 正規表現 | 部品に分けて読む。先読みで、例外を除く | `_FENCE_OPEN`・`SECRET_PATTERN` |
| 置換の連鎖 | 1 つずつ置換しない。`re.sub` に関数を渡して、1 回の走査で | `scaffold.plan` |
| ハッシュ | 内容から名前・指紋を作る。キャッシュ・ずれの検出 | `mmdc.render`・`site/.source-hash` |
| 伏せ字 | 短い値は対象外。値を出さない設計が第一 | `mask_secrets` |

## 次回

[第 3 回 ファイルとプロセス](03-files-and-processes.md): ファイルの安全な書き方、環境変数、外部コマンドの実行を学びます。
