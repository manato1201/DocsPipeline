# 演習

## 目的

レシピ ([拡張のしかた](04-extend.md)) の **応用** を、自分で設計して実装する。答えのコードは載せない。
代わりに、**ヒント** と、**できたかどうかの確認** を書く。

## 見るポイント

どの演習も、次の順で進める。

1. 何を変えるか、**ファイル名と関数名で** 3 行で書く。
2. 失敗するテストを書く。
3. 実装する。
4. 文書を更新する。
5. `pytest`・`ruff check .`・`ruff format --check .`・`docspipeline build docs` を通す。

### 演習 1 (易): `coverage` に `--format json` を足す

機械で読める形で、docstring の無い項目を出す。

* ヒント: `docstring_coverage.Report` と `Item` は `dataclass`。`dataclasses.asdict` が使える。`Path` は文字列にする。
* 出力の形 (例): `{"percent": 91.7, "missing": [{"path": "...", "line": 12, "qualname": "...", "kind": "function"}]}`
* 確認: `tests/test_cli.py` に、`json.loads(capsys.readouterr().out)` で読み戻すテストを足す。**既存の人が読む形式は変えない** こと。

### 演習 2 (易): Mermaid の指示子に `:width:` を足す

* ヒント: `MermaidDirective.option_spec` に `"width"` を足す。`docutils.parsers.rst.directives.length_or_percentage_or_unitless` が使える。画像のノードの `width` に入れる。
* 先に読む: [出力形式ごとの取り決め](../output-formats.md) — Confluence の出力には、幅が **反映されない**。それでも HTML では効く。
* 確認: HTML の出力に `width` が出るテスト (`test_build.py` の `fake mmdc` の型を使う)。

### 演習 3 (中): `doctor --json`

* ヒント: `doctor.Check` を辞書にする。**トークンの値が出ない** ことを、既存のテスト (`test_confluence_names_are_shown_but_never_values`) と同じ形で確かめる。
* 考えどころ: 終了コードは、人が読む形式のときと同じ規則にするか。なぜか、docstring に書く。

### 演習 4 (中): 図の「古さ」を検出する

`check-diagrams` は、SVG が **有るか** しか見ない。`.drawio` を直して SVG を書き出し忘れても、通ってしまう。

* ヒント: `.drawio.svg` の `content` 属性に、元の `.drawio` が埋め込まれている (このリポジトリの生成物はそう)。HTML エスケープを戻して、`.drawio` と比べる。
* 注意: **diagrams.net が書き出した SVG は、`content` が圧縮されていることがある**。その場合の扱い (比べられないものは警告にとどめる、など) を設計に含める。確かめていないので、実際の書き出しで調べること。
* 確認: 一致・不一致・埋め込み無し・圧縮されている、の四つのテスト。

### 演習 5 (難): Confluence を **公開せずに** 差分だけ見る

`dryrun` は、実環境への接続を要する。接続せずに「どのページが作られるか」を一覧する機能を考える。

* ヒント: `docspipeline build docs -b confluence` の出力ディレクトリ (`docs/_build/confluence`) にある `*.conf` のファイル名と、中身の先頭。ビルダーの出力を読むだけでよい。`scb-manifest.json` も出るが、中身の意味は未確認なので、使うなら先に調べる。
* 設計の問い: 一覧に、題名の **重複** (Confluence のスペース内で一意でなければならない) の検出を含めるか。
* 確認: 同じ題名の文書が二つあるサンプルで、検出できること。

### 演習 6 (難): PDF を出力形式に足す

* 先にやること: [出力形式ごとの取り決め](../output-formats.md) の表の「PDF」の行を読み、**何が未対応か** を確かめる。
* 設計に含めるもの: ビルダー (`latex` / `latexpdf`) の選択、日本語フォント、図 (SVG) の扱い、CI に何が要るか、**表の行をどう更新するか**。
* 注意: 実装の前に、設計を 1 ページ (`docs/` の新しいページ) に書き、読む人に見せる。

## 使うときの注意

* 演習の答え合わせは、**テストが通ること** と、**文書が更新されていること**。
* 迷ったら、似た機能の実装を探す: `grep -rn "check_diagrams\|check-diagrams" docspipeline tests docs`。

## よくある誤り

* 既存の出力の形式を変えてしまう (人が読む形式に依存している人がいる)。
* 失敗の分岐のテストを書かない。成功の一本道だけだと、一番壊れやすい所が守られない。

## 関連

* [拡張のしかた](04-extend.md)、[テストの書き方](05-testing.md)
