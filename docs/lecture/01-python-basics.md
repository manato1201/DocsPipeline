# 第 1 回 Python の基礎 (この講義で必要な範囲)

> 所要時間の目安: 2.5 時間 / 前提: プログラミングの基本 (変数・条件・繰り返し・関数)

## この回のゴール

- 型・型ヒント・関数・ジェネレータ・例外・`dataclass`・`pathlib`・モジュールの基本が読める。
- DocsPipeline のコード (`files.py`・`docstring_coverage.py` の `Item` / `Report`) を、迷わず読める。
- 「なぜそう書くのか」(型ヒントを書く理由、ジェネレータを使う理由) を説明できる。

この回は、Python を **全部** 教えるのではなく、このリポジトリのコードを読むのに **必要な範囲** に絞ります。
各節の例は、すべて実行できます。手元で動かしながら読んでください。

## 1. 値と型

Python の値には型があります。変数に型を書かなくても動きますが、**型ヒント** を書くと、読む人と道具が助かります。

```python
# 実行できる
count = 3  # int (整数)
ratio = 0.5  # float (小数)
name = "docs"  # str (文字列)
flags = {"strict": True}  # dict (キーと値の対応)
paths = ["a.py", "b.py"]  # list (順序つきの並び)
unique = {"a", "b", "a"}  # set (重複しない集まり)
pair = (1, 2)  # tuple (変更できない並び)

for value in (count, ratio, name, flags, paths, unique, pair):
    print(type(value).__name__, sorted(value) if isinstance(value, set) else value)
```

```text
# 出力
int 3
float 0.5
str docs
dict {'strict': True}
list ['a.py', 'b.py']
set ['a', 'b']
tuple (1, 2)
```

- `set` は重複を捨てます (`"a"` が 1 つになった)。順序は **保証されません**。
- `tuple` は変更できません。「ひとまとまりの値」(座標・`(使う側, 使われる側)` の組) に向きます。
  `structure_map` の依存の組は `tuple[str, str]` です。

### 型ヒント

型ヒントは、**実行には影響しない** 注釈です。読む人 (と型検査の道具、autodoc) に、意図を伝えます。

```python
# 実行できる
def title_of(path: str, limit: int = 10) -> str:
    """先頭の limit 文字を返す。"""
    return path[:limit]


print(title_of("docspipeline/config.py", 12))
print(title_of.__annotations__)
```

```text
# 出力
docspipeline
{'path': <class 'str'>, 'limit': <class 'int'>, 'return': <class 'str'>}
```

DocsPipeline のコードには、次の書き方が頻繁に出ます。

| 書き方 | 意味 |
|---|---|
| `list[str]` | 文字列のリスト |
| `dict[str, int]` | キーが文字列、値が整数の辞書 |
| `tuple[str, str]` | 文字列 2 つの組 |
| `str \| None` | 文字列か、`None` (無い) |
| `Path` | ファイルパス (`pathlib.Path`) |
| `Iterable[Path]` / `Iterator[Path]` | 繰り返せるもの / 1 つずつ取り出せるもの |

ファイルの先頭の `from __future__ import annotations` は、型ヒントを **文字列として後から評価** させる指定です。
これで、まだ定義されていない型を、先に書けます。このリポジトリの全モジュールの先頭に、この行があります。

## 2. 関数

```python
# 実行できる
def join_names(names, *, sep=", ", prefix=""):
    """名前を連結する。* より後ろは、キーワードで渡す (キーワード専用)。"""
    return prefix + sep.join(names)


print(join_names(["a", "b"]))
print(join_names(["a", "b"], sep="/", prefix=">"))
try:
    join_names(["a"], "/")  # 位置で渡すとエラー
except TypeError as exc:
    print("TypeError:", exc)
```

```text
# 出力
a, b
>a/b
TypeError: join_names() takes 1 positional argument but 2 were given
```

- 引数の `*` は、**これ以降をキーワード専用** にします。`build_config(*, confdir, project, ...)` のように、
  引数が多い関数で、渡し間違い (順序の取り違え) を防ぎます。
- 既定値 (`sep=", "`) は、省略したときの値です。

### docstring

関数の最初の文字列は **docstring** で、関数の説明になります。DocsPipeline は、これを Google 形式で書きます。

```python
# 実行できる
def scale(value, factor=2):
    """値を factor 倍にする。

    Args:
        value: 元の値。
        factor: 倍率。

    Returns:
        factor 倍した値。
    """
    return value * factor


print(scale.__doc__.splitlines()[0])
print(scale(21))
```

```text
# 出力
値を factor 倍にする。
42
```

Sphinx の autodoc は、`__doc__` を読んで API 文書を作ります。**docstring が無い関数は、文書に載りません**
(第 4 回で、これを検出する道具を読みます)。

## 3. 繰り返しとジェネレータ

リストを作らず、必要なときに **1 つずつ** 値を返すのが **ジェネレータ** です。`yield` を使います。

```python
# 実行できる
def countdown(n):
    while n > 0:
        yield n  # 値を 1 つ返して、ここで一時停止する
        n -= 1


gen = countdown(3)
print(next(gen), next(gen))
print(list(gen))  # 残りを全部取り出す
```

```text
# 出力
3 2
[1]
```

DocsPipeline で、ジェネレータの実例を読みましょう。ファイルを列挙する関数です。

```python
# 引用: docspipeline/files.py::iter_python_files
def iter_python_files(roots: Iterable[Path]) -> Iterator[Path]:
    """``roots`` 配下の ``.py`` ファイルを、生成物や仮想環境を除いて列挙する。

    Args:
        roots: ディレクトリ、または ``.py`` ファイル。

    Yields:
        見つかったファイル (各 ``root`` の中は整列済み)。
    """
    for root in roots:
        if root.is_file():
            yield root
            continue
        for path in sorted(root.rglob("*.py")):
            if not SKIP_DIRS.intersection(path.relative_to(root).parts):
                yield path
```

読み方:

1. `roots` は、ディレクトリまたはファイルの **並び**。
2. `root.is_file()` なら、そのファイルを `yield` して、次の `root` へ (`continue`)。
3. ディレクトリなら、`rglob("*.py")` で **再帰的に** `.py` を探し、`sorted` で順序を固定する。
4. `SKIP_DIRS` (`.venv`・`node_modules` など) の名前を **パスのどこかに含む** ファイルは、飛ばす。

なぜリストでなく、ジェネレータなのか。

- 大きなパッケージでも、**全部を先にメモリに載せない**。
- 呼ぶ側が `for` で回すだけで、**途中で打ち切れる**。
- 戻り値の型 `Iterator[Path]` が、「1 つずつ取り出せる」ことを示している。

実際に動かしてみます。一時ディレクトリに小さなパッケージを作って、列挙します。

```python
# 実行できる
import tempfile
from pathlib import Path
from docspipeline.files import iter_python_files

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "pkg").mkdir()
    (root / "pkg" / "a.py").write_text("x = 1\n")
    (root / ".venv" / "lib").mkdir(parents=True)
    (root / ".venv" / "lib" / "junk.py").write_text("y = 2\n")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "m.py").write_text("z = 3\n")
    for path in iter_python_files([root]):
        print(path.relative_to(root))
```

```text
# 出力
pkg/a.py
```

`.venv` と `node_modules` の中が、**出てきません**。これが「探さない場所」の規則です。
この規則を `files.py` の **一か所** に置いたことで、`coverage`・`map`・`init` が同じ規則で動きます。

### 内包表記

リストを作る繰り返しは、**内包表記** で短く書けます。

```python
# 実行できる
numbers = [1, 2, 3, 4, 5, 6]
squares = [n * n for n in numbers]
evens = [n for n in numbers if n % 2 == 0]
lookup = {n: n * n for n in numbers if n < 4}
print(squares)
print(evens)
print(lookup)
```

```text
# 出力
[1, 4, 9, 16, 25, 36]
[2, 4, 6]
{1: 1, 2: 4, 3: 9}
```

`Report.missing` (後で読みます) が、この書き方です。

## 4. 例外

エラーは **例外** として投げられ、`try` / `except` で受けます。

```python
# 実行できる
def parse_port(text):
    try:
        port = int(text)
    except ValueError as exc:
        raise ValueError(f"ポートは整数にしてください: {text!r}") from exc
    if not 0 < port < 65536:
        raise ValueError(f"範囲外です: {port}")
    return port


for sample in ("8080", "http", "70000"):
    try:
        print(parse_port(sample))
    except ValueError as exc:
        print("エラー:", exc)
```

```text
# 出力
8080
エラー: ポートは整数にしてください: 'http'
エラー: 範囲外です: 70000
```

- `raise ... from exc` は、**元の例外** (`exc`) を原因として残します。デバッグのとき、原因を辿れます。
- 例外の型は、**意味** で選びます。入力の値が悪いなら `ValueError`、無いものを探したなら `KeyError`、など。

DocsPipeline の方針: **入力の打ち間違いは、黙って成功させず、例外 → 終了コード 2** にします。
たとえば `docspipeline coverage srcc` は、存在しない `srcc` を、「100%」ではなくエラーにします (第 8 回)。

## 5. dataclass

「データを持つだけのクラス」は、`@dataclass` で短く書けます。`__init__`・`__repr__`・`__eq__` を自動で作ります。

```python
# 実行できる
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: int
    y: int = 0  # 既定値


p = Point(3)
print(p, p == Point(3, 0))
try:
    p.x = 5  # frozen=True なので、変更できない
except Exception as exc:
    print(type(exc).__name__)
```

```text
# 出力
Point(x=3, y=0) True
FrozenInstanceError
```

`frozen=True` は **不変** (変更できない) にします。不変の値は、他から勝手に書き換えられないので、
バグが起きにくく、`set` の要素や `dict` のキーにもできます。DocsPipeline の `Item`・`Report` を読みましょう。

```python
# 引用: docspipeline/docstring_coverage.py::Item
@dataclass(frozen=True)
class Item:
    """カバレッジの対象 1 件。"""

    path: Path
    qualname: str
    kind: str
    line: int
    documented: bool
```

```python
# 引用: docspipeline/docstring_coverage.py::Report
@dataclass(frozen=True)
class Report:
    """カバレッジの集計。"""

    items: tuple[Item, ...]

    @property
    def missing(self) -> list[Item]:
        """docstring が無い項目。"""
        return [i for i in self.items if not i.documented]

    @property
    def percent(self) -> float:
        """docstring がある項目の割合 (対象が無ければ 100)。"""
        if not self.items:
            return 100.0
        return 100.0 * (len(self.items) - len(self.missing)) / len(self.items)
```

- `Item` は、公開 API **1 件** (どのファイルの何行目の何という名前か、docstring があるか)。
- `Report` は、その **集計**。`@property` は、メソッドを **属性のように** 呼べるようにします
  (`report.percent` と書ける。`report.percent()` ではない)。
- `percent` は、**対象が 0 件なら 100** を返します。0 で割る事故を避けるためです。

動かしてみます。

```python
# 実行できる
from pathlib import Path
from docspipeline.docstring_coverage import Item, Report

p = Path("m.py")
report = Report(
    (
        Item(p, "m", "module", 1, True),
        Item(p, "m.f", "function", 3, True),
        Item(p, "m.g", "function", 9, False),
    )
)
print(len(report.items), "件中", len(report.missing), "件が docstring なし")
print(f"{report.percent:.1f}%")
print(Report(()).percent)
```

```text
# 出力
3 件中 1 件が docstring なし
66.7%
100.0
```

## 6. pathlib: パスをオブジェクトとして扱う

文字列でパスをいじると、区切り文字 (`/` と `\`) の違いで壊れます。`pathlib.Path` を使います。

```python
# 実行できる
from pathlib import Path

p = Path("docs") / "learn" / "index.md"  # / で連結
print(p, p.name, p.stem, p.suffix, p.parent)
print(p.with_suffix(".html"))
print(p.relative_to("docs"))
print(p.parts)
print(Path("a/b/../c").as_posix())
```

```text
# 出力
docs/learn/index.md index.md index .md docs/learn
docs/learn/index.html
learn/index.md
('docs', 'learn', 'index.md')
a/b/../c
```

| 道具 | 働き |
|---|---|
| `/` | パスを連結する (OS ごとの区切りを使う) |
| `.name` / `.stem` / `.suffix` | ファイル名 / 拡張子なしの名前 / 拡張子 |
| `.with_suffix(".x")` | 拡張子を付け替える |
| `.relative_to(base)` | `base` からの相対にする (含まれないと `ValueError`) |
| `.rglob("*.py")` | 配下を再帰的に探す |
| `.read_text(encoding="utf-8")` | 文字コードを **明示して** 読む |
| `.as_posix()` | `/` 区切りの文字列にする (CI の設定に書くときに使う) |

## 7. モジュールとパッケージ

- **モジュール** = 1 つの `.py` ファイル。`import docspipeline.files` で読み込む。
- **パッケージ** = `__init__.py` を持つディレクトリ。モジュールをまとめる。
- **相対 import**: `from .files import iter_python_files` の `.` は、「同じパッケージの」を意味する。
- `__all__ = [...]` は、`from m import *` で公開する名前を決める (公開 API の宣言にも使う)。
- `python -m docspipeline` は、パッケージの `__main__.py` を実行する。

```python
# 実行できる
import importlib
import docspipeline
import docspipeline.files as files

print(docspipeline.__version__)
print(files.__name__)
print(files.iter_python_files.__module__)
print(importlib.import_module("docspipeline.files") is files)  # 同じモジュールは 1 回だけ読み込まれる
```

```text
# 出力
0.1.0
docspipeline.files
docspipeline.files
True
```

`import` した時点で、そのモジュールの **先頭から** コードが実行されます (関数の定義も、実行の一種です)。
だから、モジュールの先頭に **重い処理や副作用** を書いてはいけません。
DocsPipeline で `core` が Sphinx を `import` しない決まりも、この性質からきています (第 7 回・第 10 回)。

## 8. f-string と書式

```python
# 実行できる
name, count, ratio = "coverage", 41, 91.666
print(f"{name}: {count} 件")
print(f"{ratio:.1f}%")  # 小数 1 桁
print(f"{count:>6}|{count:<6}|")  # 右寄せ・左寄せ
print(f"{name!r}")  # repr (引用符つき)
print(f"{count = }")  # 式と値を一緒に出す
```

```text
# 出力
coverage: 41 件
91.7%
    41|41    |
'coverage'
count = 41
```

## ハンズオン

1. `python -i` (または `python`) を起動し、上の例を **自分の手で** 打つ。
2. `docspipeline/files.py` を開き、`iter_python_files` の `SKIP_DIRS` に、好きな名前を足して、挙動を確かめる (戻すこと)。
3. `docspipeline coverage docspipeline` を実行し、出力の最後の行 (`docstring のカバレッジ: ...`) を読む。

## 確認問題

1. `def f(a, *, b=1)` を `f(1, 2)` と呼ぶと、何が起きますか。なぜ、この書き方をしますか。
2. ジェネレータとリストの違いを、メモリの観点から説明してください。
3. `Report.percent` が、対象 0 件のときに 100 を返す理由は何ですか。
4. `from __future__ import annotations` は、何のためにありますか。
5. 次のコードの出力を予想してください。

```python
values = [3, 1, 2, 3, 1]
print(sorted({v * 10 for v in values}))
```

6. (書く問題) `Path` のリストを受け取り、`.md` のファイルだけを **ジェネレータ** で返す関数 `only_markdown(paths)` を書いてください。

## 解答

1. `TypeError` (`f() takes 1 positional argument but 2 were given`)。`*` 以降は、キーワードでしか渡せない。
   引数が多い関数で、**値の渡し間違い** (順序の取り違え) を、呼ぶ側で防ぐため。
2. リストは、全要素を **先に作って** メモリに持つ。ジェネレータは、必要なときに **1 つずつ** 作るので、
   全要素を同時に持たない。大きなものでも、少ないメモリで回せる。途中で打ち切ることもできる。
3. 0 で割る (`ZeroDivisionError`) のを避けるため。もう 1 つの理由は、「検査する対象が無い」ことを
   「不足あり」と扱うのが不自然なため (ただし、パスの打ち間違いは、別に `scan` がエラーにする)。
4. 型ヒントを、**文字列として後から評価** させる。まだ定義されていないクラスを型に書ける。実行時の負荷も減る。
5. `[10, 20, 30]` (集合内包表記で重複が消え、`sorted` で並ぶ)。
6. 例 (実行して確かめてある):

```python
# 実行できる
from pathlib import Path


def only_markdown(paths):
    for path in paths:
        if path.suffix == ".md":
            yield path


found = only_markdown([Path("a.md"), Path("b.py"), Path("c.md")])
print([p.name for p in found])
```

```text
# 出力
['a.md', 'c.md']
```

## まとめ

| 概念 | 要点 | このリポジトリでの例 |
|---|---|---|
| 型ヒント | 実行に影響しない注釈。読む人と道具のため | 全モジュール |
| キーワード専用引数 | `*` の後ろ。渡し間違いを防ぐ | `build_config(*, ...)` |
| ジェネレータ | `yield` で 1 つずつ返す。メモリが少ない | `iter_python_files` |
| 例外 | 意味で型を選び、`from` で原因を残す | `ValueError` → 終了コード 2 |
| dataclass | データを持つだけのクラスを短く。`frozen` で不変 | `Item`・`Report` |
| pathlib | パスをオブジェクトで扱う | `files.py`・`scaffold.py` |
| import の副作用 | 読み込んだ時点でコードが実行される | `core` は Sphinx を `import` しない |

## 次回

[第 2 回 文字列・正規表現・ハッシュ](02-text-processing.md): 文字の「幅」、正規表現、置換の落とし穴、ハッシュを学びます。
