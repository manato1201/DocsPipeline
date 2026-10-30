# 用語集

読み方の目安として、**この資料での意味** を書く。公式の定義は、各リンク先を参照。

```{list-table}
:header-rows: 1
:widths: 22 78

* - 用語
  - 意味
* - [Sphinx](https://www.sphinx-doc.org/)
  - 文書のビルド本体。入力 (reStructuredText・Markdown) を読み、HTML や Confluence 形式などを出す
* - reStructuredText (rst)
  - Sphinx の標準の記法。この資料の `docs/*.rst`。ディレクティブ (`.. image::` など) が書ける
* - [MyST](https://myst-parser.readthedocs.io/)
  - Markdown を Sphinx に読ませる拡張。`docs/runbook.md`・この資料は Markdown
* - autodoc
  - Python のコードを `import` して、docstring から API 文書を作る Sphinx の標準拡張
* - napoleon
  - Google 形式の docstring (`Args:`・`Returns:`) を、autodoc が読める形に変える拡張
* - [Breathe](https://breathe.readthedocs.io/)
  - Doxygen の XML を Sphinx のディレクティブ (`doxygenclass` など) として取り込む拡張
* - [Doxygen](https://www.doxygen.nl/)
  - C++ のコメントから、構造を取り出すツール。ここでは XML だけを出す
* - ビルダー (builder)
  - Sphinx の出力形式の担当。`html`・`confluence`・`linkcheck` など。`-b` で選ぶ
* - 拡張 (extension)
  - Sphinx に機能を足す Python のモジュール。`setup(app)` を持つ
* - ディレクティブ (directive)
  - rst の `.. 名前::` の形の命令。`mermaid` は、この資料の拡張が足したもの
* - イベント
  - ビルドの途中で Sphinx が通知する合図 (`config-inited`・`builder-inited`)。拡張が `app.connect` で受ける
* - nitpicky
  - 解決できない参照をすべて警告にする設定。`-W` と組み合わせて、リンク切れを CI で止める
* - intersphinx
  - 他の文書 (Python 標準など) への参照を解決する仕組み。オンラインが要る
* - `-W`
  - 警告をエラー扱いにする Sphinx のオプション。`--keep-going` で、止まらず全部の警告を出す
* - [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (`mmdc`)
  - Mermaid のコードを SVG / PNG にするコマンド。内部で Chromium を使う
* - [diagrams.net](https://www.diagrams.net/)
  - 図の編集ツール。`.drawio` (元データ) と、書き出した `.drawio.svg` を両方置く
* - [Confluence ビルダー](https://sphinxcontrib-confluencebuilder.readthedocs.io/)
  - Sphinx の出力を Confluence のページとして出す / 公開する拡張
* - 親ページ
  - Confluence で、公開の対象にする **専用の** ページ。この配下だけを更新する
* - モード (`local` / `dryrun` / `publish`)
  - 公開の段階。既定の `local` は、ネットワークにつながない
* - 伏せ字 (マスク)
  - 出力に混ざったトークンの値を `***` に置き換えること (`confluence.mask_secrets`)
* - スタブ
  - 実物が動かない環境で、`import` だけを通すための偽物 (`hou` など)
* - プロンプトのブロック
  - 手順に添える、Claude Code にそのまま渡せるプロンプト (`.. prompt::`)。HTML ではコピーボタンが付く
* - 機械の地図
  - ソースを `ast` で読んで作る、モジュールの依存の一覧。事実だけを持ち、理由は持たない (`docspipeline map`)
* - カバレッジ (docstring)
  - 公開 API のうち、docstring がある割合。`docspipeline coverage`
```
