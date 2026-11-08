# 全体像

## 目的

DocsPipeline が **何を入力に、何を作り、何で守っているか** を一枚で掴む。細部は次のページ以降。

![書く・組み立てる・届ける・守る](../diagrams/system-overview.drawio.svg)

## 見るポイント

### 四つの役割

| 役割 | 中身 | 担当 |
|---|---|---|
| 書く | Python の docstring、既存の Markdown、C++ のコメント、図 | 利用者 (各リポジトリ) |
| 組み立てる | Sphinx と、DocsPipeline の拡張 (`mermaid`・`doxygen`・`guard`) | `docs/conf.py` → {py:func}`docspipeline.config.build_config` |
| 届ける | HTML (確認用) と Confluence (公開) | Sphinx のビルダー。公開だけは {py:mod}`docspipeline.confluence` が守る |
| 守る | `-W` ビルド・docstring の網羅・図の書き出し・リンク切れ・トークン | CI (`.github/workflows/ci.yml`) と CLI |

### 設計の軸は三つ

1. **安全側が既定**。何も指定しなければ `local` で、ネットワークにつながない。公開は、環境変数がそろい、接続テストを通り、モードを明示した場合だけ。
2. **失敗は早く、名前だけ出す**。足りない環境変数は、ビルドの前に **名前だけ** を示して止まる。トークンの値は、画面にもログにも出さない。
3. **生成物と定義を一致させる**。図・雛形・設定名は、テストが「定義どおりか」を確かめる。手で直してずれると、CI が落ちる。

### 一つのコマンドが何をするか

| コマンド | 中で起きること |
|---|---|
| `docspipeline build docs` | `sphinx -W` を子プロセスで起動 (モードは `local` 固定)。出力はトークンを伏せて表示 |
| `docspipeline publish docs --mode dryrun` | 環境変数の確認 → 接続テスト → 接続してのビルド (ページは変更しない) |
| `docspipeline coverage PATH` | コードを `import` せず、`ast` で公開 API の docstring を数える |
| `docspipeline init . --project X --author Y` | 雛形 (`templates/project`) の `@@名前@@` を置き換えて、`docs/` と CI を書き出す |
| `docspipeline doctor` | `sphinx`・`mmdc`・`doxygen`・環境変数の有無を一覧する |

## 使うときの注意

* DocsPipeline は **Sphinx の上に載っている**。Sphinx 自体の挙動 (イベント、ディレクティブ、ビルダー) を知らないと、中を読んでも分かりにくい。[ビルドの内側](03-build-internals.md) で補う。
* 「公開する」機能は、実際の Confluence 環境では検証していない ([Confluence への公開](../confluence.md) の「検証できていないこと」)。変更するときは、特に慎重に。

## よくある誤り

* **`conf.py` に処理を書き足す**。共通の設定は {py:func}`docspipeline.config.build_config` に集め、各リポジトリの `conf.py` は名前と対象パスだけにする。リポジトリごとに設定が散らばると、更新が追いつかなくなる。
* **`docs/_build` や `docs/_generated` をコミットする**。どちらも生成物 (`.gitignore` 済み)。
* **図の SVG だけを手で直す**。元データ (`.drawio`) と食い違い、次に作り直したときに消える。

## 関連

* 用語が分からなくなったら [用語集](glossary.md)
* 次は [コードの読み方](02-code-tour.md)
