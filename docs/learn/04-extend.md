# 拡張のしかた

## 目的

よくある 6 種類の変更を、**手順どおりに、テストつきで** 行えるようにする。どのレシピも
「定義 → 実装 → テスト → 文書」の順で、最後に確認のコマンドを実行する。

## 見るポイント

共通の流れ:

1. **まずテストを書く** (失敗することを確かめる)。
2. 計算の部分を関数にして実装する。実行は薄く。
3. `docs/` に 1 行でも書く (使い方・環境変数・注意)。**文書の無い機能は、無いのと同じ**。
4. 次の三つがすべて通ること。

```bash
python -m pytest -q
ruff check . && ruff format --check .
docspipeline build docs          # 自分の文書が、警告なしで通る
```

---

## レシピ 1: 新しい CLI コマンドを足す

実例: `check-diagrams` (`.drawio` に書き出した SVG があるか)。

1. 計算を部品にする: `docspipeline/diagrams.py` の `find_missing_exports(docs)`。ファイルを探して `list[Path]` を返すだけ。
2. コマンドを足す: `cli.py` に `cmd_check_diagrams(args)` (docstring 必須。`coverage --fail-under 100` が CI で止める)。
3. 引数を登録する: `build_parser()` に `sub.add_parser("check-diagrams", ...)` と `set_defaults(func=...)`。
4. テストを書く: `tests/test_cli.py` の `test_check_diagrams`。`run("check-diagrams", str(tmp_path))` の終了コードと出力を確かめる。
5. 文書: `docs/usage.rst` の表に 1 行。CI で使うなら `ci.yml` と `templates/project/github/workflows/docs.yml.tmpl` にも。

```{admonition} 約束
:class: note
* 終了コードは、成功 `0`、失敗 `1`、**設定の誤り `2`**。
* 出力は日本語で、**何を直せばよいか** まで書く (「失敗」だけにしない)。
* 外のプロセスを起動する部分は `cli._run` を通す (トークンの伏せ字処理がかかる)。
```

## レシピ 2: `build_config` に引数を足す

実例: `use_hou_stub` (Houdini の外で `hou` を使うコードを文書化する)。

1. `config.build_config` の引数に足す (**キーワード専用**。既定値は、既存の利用者の挙動が変わらない値に)。
2. docstring の `Args:` に書く。**`coverage` では引数の説明までは検査しないので、レビューで見る**。
3. 辞書に入れるキーを決める。Sphinx 標準の名前か、`docspipeline_*` (自前の名前。拡張の `setup()` で `add_config_value` する)。
4. `templates/project/docs/conf.py.tmpl` に出すか決める (出すなら `scaffold._values` に値を足し、`@@名前@@` で埋める)。
5. テスト: `tests/test_build.py` のように、サンプルを **実際にビルド** して確かめる。
6. 文書: `docs/usage.rst` か該当ページ。

```{admonition} よくある誤り
:class: warning
Sphinx は **知らない設定名を黙って無視する**。綴りを間違えても、エラーにならない。
`docspipeline_*` を足したら、`setup()` に `add_config_value` を書いたか、必ず確かめる。
```

## レシピ 3: 新しい Sphinx 拡張を足す

雛形は `docspipeline/guard.py` (最小)。

```python
from __future__ import annotations
from typing import Any
from sphinx.application import Sphinx
from . import __version__


def _on_config_inited(app: Sphinx, config: Any) -> None:
    """設定が読み込まれた直後に呼ばれる。"""


def setup(app: Sphinx) -> dict[str, Any]:
    """Sphinx 拡張の登録。"""
    app.add_config_value("docspipeline_myext_option", "既定値", "env")
    app.connect("config-inited", _on_config_inited, priority=100)
    return {"version": __version__, "parallel_read_safe": True, "parallel_write_safe": True}
```

1. `docspipeline/myext.py` を作り、上の形から始める。
2. `config.build_config` の `extensions` に `"docspipeline.myext"` を足す (条件つきなら `if` で)。
3. **外部コマンドを呼ぶなら**: 実行 (`run_*`) と、引数・設定の組み立て (`make_*`) を分ける。見つからないときの方針 (`literal` / `warn` / `error` のような) を設け、CI では厳しい方を選べるようにする。`mermaid.py` が手本。
4. 並列読み込みに安全か考え、`parallel_read_safe` を決める。
5. テスト: 偽のコマンド (次の [テストの書き方](05-testing.md)) で、成功・失敗・コマンド無しの三つを確かめる。

## レシピ 4: 新しい図を足す

図は `tools/diagrams/build_diagrams.py` で **定義** し、`.drawio` と `.drawio.svg` を **生成** する。

1. `build_diagrams.py` に、`Diagram` を返す関数を書く。部品は `kit.py` の `Panel`・`Card`・`Edge`・`Note`。
2. `DIAGRAMS` の辞書に名前を足す。
3. `python tools/diagrams/build_diagrams.py` で作り直す。
4. SVG を画像にして **目で見る** (下の「確認」)。
5. 文書から `.. image:: diagrams/<名前>.drawio.svg` (Markdown なら `![説明](../diagrams/<名前>.drawio.svg)`) で参照する。`alt` を必ず書く。

図の作法 (`kit.py` の冒頭にも書いてある):

* 青 = 主な流れ / 灰色の破線 = 起動・登録・参照 / **オレンジ = 強調する経路** / 赤 = 止まる条件。
* 順序のあるものは、カードに番号 (`badge=1`) を付ける。
* 矢印には、**何が流れるか** を短いラベルで添える。
* 1 枚に詰め込まない。目安: カード 10 個以内。

確認:

* 目で見る: `docs/diagrams/<名前>.drawio.svg` を、ブラウザで開く (`file://` で直接開ける)。
* 自動: `tests/test_diagrams.py` が、**カードの重なり・キャンバスや枠からのはみ出し・番号の欠け・生成物と定義のずれ** を見つける。カードの間隔を詰めすぎたときは、ここで落ちる。

```{admonition} 手で直したいとき
:class: tip
diagrams.net で `.drawio` を開いて直しても構わない。ただし **`build_diagrams.py` の定義も同じ内容に直す**。
でないと、次に作り直したときに、手の修正が消え、`tests/test_diagrams.py` も落ちる。
```

## レシピ 5: 雛形 (`init` の出力) を足す・直す

1. `docspipeline/templates/project/` に `*.tmpl` を置く。**末尾の `.tmpl` を外した名前** で書き出される。
2. 置き換える値は `@@名前@@`。値は `scaffold._values` に足す。
3. 書き出し先を変えたいときは `scaffold._destination` (点で始まる名前、`github/` → `.github/` などの規則がここにある)。
4. 条件つきのファイル (C++ のときだけ、等) は `scaffold.plan` の `continue` の並びに足す。
5. テスト: `tests/test_cli.py` の `test_init_*`。**`@@` が残っていないこと** も確かめる。
6. 確認: 新しいディレクトリで `docspipeline init . ...` → `docspipeline build docs` が、警告なしで通る。

```{admonition} パッケージに入っているか
:class: warning
点で始まるファイルは、パッケージのデータに含まれないことがある (`.gitignore.tmpl` で一度失敗した)。
雛形の側の名前に点を付けず、書き出すときに付ける (`gitignore.tmpl` → `.gitignore`)。
`pip wheel . --no-deps` で作った wheel の中身を、一度は確かめること。
```

## レシピ 6: Confluence の設定を足す (安全に)

`confluence.sphinx_settings` に足す。**ここだけは、特に慎重に**。

1. 公開の可否に関わる項目か考える。関わるなら **環境変数に頼らず、必ず明示** する (ビルダーは、未設定の `confluence_*` を同名の環境変数から補うため)。
2. 名前は、インストール済みのビルダーに実在するものを使う。`tests/test_confluence.py` の
   `test_every_setting_name_is_registered_by_the_installed_confluence_builder` が、実在を確かめる
   (綴りの間違い・版による改名を、ここで見つける)。候補は、ビルダーの `config/checks.py` の
   `validator.conf('confluence_...')` を `grep` すると出る。
3. `local` と `publish` の **両方** で、値が期待どおりかをテストする (`tests/test_confluence.py`)。
4. 環境変数を新しく要求するなら、`REQUIRED_ENV` に足す (足りないときに、名前だけを示して止まるようになる)。
5. 秘密の値が増えるなら、`SECRET_ENV` に足す (出力から伏せ字になる)。
6. `docs/confluence.rst` の表を更新する。

## 使うときの注意

* レシピに無い変更 (新しいビルダー、PDF など) は、[演習](06-exercises.md) の形で、先に設計を書いてから始める。
* 変更が **公開の挙動** に触れるなら、`dryrun` で確かめてから (確かめられない環境なら、その旨を PR に書く)。

## よくある誤り

* テストを後回しにして、実装だけ先に書く。外部コマンドが絡む処理は、後から書くテストが難しい。
* 文書の更新を別の PR にする。[運用手順](../runbook.md) の決まり (同じ PR で更新) に反する。
* `ruff format` を通さずに出す。CI で落ちる。

## 関連

* [テストの書き方](05-testing.md)
* [コードの読み方](02-code-tour.md) — どのファイルを触るか迷ったら
