# 機械の地図 (`docspipeline map`)

## 目的

ソースを読んで **依存の地図を機械的に作り**、(1) アーキテクチャ文書の下書き、(2) 依存の向きの点検、
(3) 手書きの構成図とのずれの検出、に使う。

設計書の追補 (Z16: oh-my-mermaid、X3: Graphify) の考え方を、自前の部品として実装したもの。外部のツールは使わず、
**コードの情報を外部へ送らない** (ローカルで読むだけ)。

## 見るポイント

### 二層で持つ

| 層 | 中身 | 作り方 | 直し方 |
|---|---|---|---|
| 事実 | どのモジュールが、どれを import しているか | `docspipeline map` (毎回作り直せる) | 直さない。コードを直す |
| 理由 | なぜその依存があるのか、どう読めばよいか | 人が書く ([コードの読み方](02-code-tour.md)・[設計](../design.md)) | 人が書く。**地図とのずれは、テストで検出する** |

### 使い方

```bash
docspipeline map docspipeline                       # Markdown の下書き (標準出力)
docspipeline map docspipeline -o /tmp/draft.md      # ファイルへ
docspipeline map docspipeline --format mermaid      # 図だけ
docspipeline map docspipeline --format json         # 機械で読む用
docspipeline map docspipeline --fail-on-cycle       # import の循環があれば、終了コード 1
```

Markdown の下書きには、**札の見方**、依存の図 (Mermaid)、モジュール一覧 (要約・行数・公開 API の数・使う/使われる)、
**札つきの依存の一覧**、循環と「どこからも使われていない」モジュール、**読み取れないこと** が入る。冒頭に「自動生成の下書き。
人が確認してから使い、そのまま公開しない」という警告が付く。

### 見つける依存の種類

| 種類 | 例 | 地図での表現 | 札 |
|---|---|---|---|
| `import` | `from . import confluence`、`import pkg.mod` (モジュールを読み込んだときに実行されるもの) | 実線 | `EXTRACTED` (読んだ) |
| `deferred` | 関数の中の `import` (呼ばれたときに、初めて読み込まれる) | 点線 (「遅延」) | `EXTRACTED` (読んだ) |
| `reference` | `extensions = ["docspipeline.guard"]` のような、**モジュール名と完全に一致する文字列** | 点線 (「推測」) | `INFERRED` (推測) |

### 「読んだ」と「推測した」を区別する

自動で作った図は、読む人が **どこまで信じてよいか** を、辺ごとに見分けられるようにする。

| 札 | 意味 | この地図での例 |
|---|---|---|
| `EXTRACTED` (読んだ) | 原文に **明示されている** ことを、そのまま読み取った | `import` 文による依存、要約 (docstring の 1 行目)、行数、公開 API の数、循環の判定 |
| `INFERRED` (推測) | 書き方から **推し量った**。外れることがある | 文字列の一致による参照、「どこからも使われていない」の判定 |

* 図では、推測の辺に「推測」と書く。モジュール一覧では、推測だけで結ばれた依存に `(推測)` を付ける。
* **循環は、読んだ辺だけで判定する**。文字列の参照が輪になっていても、循環とは断定しない。
* 「どこからも使われていない」は、**使い道が見つからなかった** というだけ。関数の中の `import` や動的な読み込みで使われているかもしれない。
* 機械で読む用の JSON は、辺ごとに `kind` と `label` を持つ (`edges`)。
* 札は、種類から決まる (`structure_map.EDGE_LABELS`)。新しい種類の依存を足すときは、**読んだか推測かを先に決める**。
  決め方に迷うなら、推測にする (読んだことにして外れるより、安全)。

### 実例: この地図で見つかった不備

`doctor` コマンドを足したとき、`mmdc` の探索関数を `mermaid.py` から import した。ところが `mermaid.py` は
Sphinx の拡張で、先頭で `docutils` を import する。結果、**Sphinx が入っていない環境で、`docspipeline` の
どのコマンドも起動時にクラッシュ** した (`cli → doctor → mermaid → docutils`)。

テストは Sphinx が入った環境で走っていたので、気付けなかった。依存の地図を見て分かり、次のように直した。

1. Sphinx に依存しない部分を `docspipeline/mmdc.py` に分けた。拡張 (`mermaid.py`) と `doctor.py` が、そこから使う。
2. 再発しないよう、テストにした (下の「ルール」)。

教訓: **「動く環境」でしかテストしていないと、依存の向きの誤りは見えない**。地図は、環境に依らずに、構造そのものを検査できる。

### ルール (`tests/test_structure_map.py`)

| ルール | なぜ |
|---|---|
| `import` に循環が無い | 循環があると、読む順序が定まらず、`import` の時点で壊れやすい |
| Sphinx / docutils を import してよいのは、拡張 (`guard`・`mermaid`・`doxygen`) だけ | core の CLI を、Sphinx なしで動かすため |
| `confluence`・`diagrams`・`docstring_coverage`・`mmdc`・`scaffold` は、他の内部モジュールを import しない (葉) | 単体で試せる部品にするため |
| `cli` は `config`・拡張を import しない | CLI は Sphinx を **子プロセス** として起動する。同じプロセスに引き込まない |
| Sphinx を隠した状態で、core が import できる (実行して確かめる) | 地図の読み取りに頼らない、最後の砦 |

### 手書きの図との突き合わせ

[module-map](../diagrams/module-map.drawio.svg) の矢印は、`tools/diagrams/build_diagrams.py` の
`MODULE_IMPORTS` / `MODULE_REFERENCES` から作る。`tests/test_diagrams.py` が、**同じ読み取り** で作った実際の依存と
突き合わせ、次を検出する。

* 図にあるのに、実際には無い依存 (古くなった矢印)
* 実際にあるのに、図に無い依存 (描き忘れ。`cli → structure_map` が、実際にこれで見つかった)

新しい依存を足したら、テストが落ちる。`MODULE_IMPORTS` に矢印の経路を足し、図を作り直す
([拡張のしかた](04-extend.md) のレシピ 4)。

## 使うときの注意

* **下書きは、そのまま公開しない**。「なぜ」は載っていない。人が確認し、理由を書き足してから使う。
* 見つけられないもの: `importlib.import_module(変数)` のような動的な読み込み、組み立てた名前。**文字列の参照は、完全一致だけ**。
* 対象は Python のみ。C++ の `#include` の地図は、実装していない。
* Graphify との比較は、未実施 (導入していない)。比べるなら、**導入前に SKILL.md と監査結果を読む**。

## よくある誤り

* 地図を **コミットする**。コードから毎回作れるものを置くと、古くなる。残すのは、人が書いた説明と、テスト。
* 「循環が無い」ことを、図で目視して済ませる。`--fail-on-cycle` かテストに任せる。
* 関数の中の `import` や、`if TYPE_CHECKING:` の中の `import` を、循環として数える。前者は循環を断つ定番の書き方で、
  後者は型検査のときだけ。どちらも、実行時の循環ではないので、循環の検出の対象にしない (`TYPE_CHECKING` の中は、依存としても数えない)。
* `reference` を `import` と同じ強さで扱う。`reference` は名前の一致だけで、**実際に読み込まれるかは分からない**(札は `INFERRED`)。
* 札を見ずに、図の全ての辺を事実として引用する。**推測の辺は、人が確かめてから** 文書に書く。

## 演習

1. `docspipeline map` の出力に、**外部ライブラリ** (`module.external`) の一覧の列を足す。Sphinx を使うモジュールが、一目で分かるようになる。
2. 「`cli` は `config` を import しない」のような **禁止の依存** を、テストの中のリストではなく、設定ファイル (TOML) で宣言できるようにする。
3. C++ の `#include` の地図を作る ([C++ の文書](../cpp.md))。何を「モジュール」とし、どこまでを内部とするか、先に設計を書く。

## 関連

* [コードの読み方](02-code-tour.md) — 地図の「理由」の層
* [テストの書き方](05-testing.md)
* [設計](../design.md) — Z16 (地図)・Z47 (札) の取り込み方
* [契約と副作用の境界](../contracts.md) — `labeled_edges`・`to_markdown` の契約
