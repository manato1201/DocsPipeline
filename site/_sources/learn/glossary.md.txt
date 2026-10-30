# 用語集

読み方の目安として、**この資料での意味** を書く。公式の定義は、各リンク先を参照。

| 用語 | 意味 |
|---|---|
| [Sphinx](https://www.sphinx-doc.org/) | 文書のビルド本体。入力 (reStructuredText・Markdown) を読み、HTML や Confluence 形式などを出す |
| reStructuredText (rst) | Sphinx の標準の記法。API リファレンス (`docs/api.rst`)。ディレクティブ (`.. image::` など) が書ける |
| [MyST](https://myst-parser.readthedocs.io/) | Markdown を Sphinx に読ませる拡張。`docs/runbook.md`・この資料は Markdown |
| autodoc | Python のコードを `import` して、docstring から API 文書を作る Sphinx の標準拡張 |
| napoleon | Google 形式の docstring (`Args:`・`Returns:`) を、autodoc が読める形に変える拡張 |
| [Breathe](https://breathe.readthedocs.io/) | Doxygen の XML を Sphinx のディレクティブ (`doxygenclass` など) として取り込む拡張 |
| [Doxygen](https://www.doxygen.nl/) | C++ のコメントから、構造を取り出すツール。ここでは XML だけを出す |
| ビルダー (builder) | Sphinx の出力形式の担当。`html`・`confluence`・`linkcheck` など。`-b` で選ぶ |
| 拡張 (extension) | Sphinx に機能を足す Python のモジュール。`setup(app)` を持つ |
| ディレクティブ (directive) | rst の `.. 名前::` の形の命令。`mermaid` は、この資料の拡張が足したもの |
| イベント | ビルドの途中で Sphinx が通知する合図 (`config-inited`・`builder-inited`)。拡張が `app.connect` で受ける |
| nitpicky | 解決できない参照をすべて警告にする設定。`-W` と組み合わせて、リンク切れを CI で止める |
| intersphinx | 他の文書 (Python 標準など) への参照を解決する仕組み。オンラインが要る |
| `-W` | 警告をエラー扱いにする Sphinx のオプション。`--keep-going` で、止まらず全部の警告を出す |
| [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (`mmdc`) | Mermaid のコードを SVG / PNG にするコマンド。内部で Chromium を使う |
| [diagrams.net](https://www.diagrams.net/) | 図の編集ツール。`.drawio` (元データ) と、書き出した `.drawio.svg` を両方置く |
| [Confluence ビルダー](https://sphinxcontrib-confluencebuilder.readthedocs.io/) | Sphinx の出力を Confluence のページとして出す / 公開する拡張 |
| 親ページ | Confluence で、公開の対象にする **専用の** ページ。この配下だけを更新する |
| モード (`local` / `dryrun` / `publish`) | 公開の段階。既定の `local` は、ネットワークにつながない |
| 伏せ字 (マスク) | 出力に混ざったトークンの値を `***` に置き換えること (`confluence.mask_secrets`) |
| スタブ | 実物が動かない環境で、`import` だけを通すための偽物 (`hou` など) |
| プロンプトのブロック | 手順に添える、Claude Code にそのまま渡せるプロンプト (`.. prompt::`)。HTML ではコピーボタンが付く |
| 機械の地図 | ソースを `ast` で読んで作る、モジュールの依存の一覧。事実だけを持ち、理由は持たない (`docspipeline map`) |
| カバレッジ (docstring) | 公開 API のうち、docstring がある割合。`docspipeline coverage` |
| 標準の `%%{init}%%` の行 | Mermaid のブロックの 1 行目に置く、色とフォントの指定。GitHub と HTML で見た目を揃える。`check-mermaid --fix` が入れる |
| `classDef` の 5 色 | 図の部品の役割を色で示す約束。入力 = 青、処理 = 緑、出力・公開 = オレンジ、止まる = 赤、補助 = 白 |
| 変異テスト | わざとコードを壊して、テストが落ちるかを確かめること。テストが本当に守っているかの確認 |
| 構造テスト | 設計の約束 (依存の向き・生成物のずれ・名前の実在) を、テストにしたもの |
| 回帰テスト | 見つかった不備の再発を防ぐテスト。再現 → 失敗するテスト → 修正 → 効くか確認 の順で足す |
| 冪等 (べきとう) | 何度実行しても、結果が同じこと (`check-mermaid --fix`・`quote_code.py`) |
| 決定的 | 同じ入力なら、同じ出力になること。集合の順序・時刻・一時パスに頼らない |
| `site/` (HTML 版) | Sphinx の HTML をコミットしたもの。生成物なので手で直さない。`site/.source-hash` の印で、元とのずれを検出する |
| 被依存数 (fan-in) / 依存数 (fan-out) | モジュールが何個から import されるか / 何個を import するか。被依存数が多いものは、変更の影響が広い ([講義 第 13 回](../lecture/13-capstone.md)) |
| 講義資料 | 基礎から保守・拡張までを、講義の形で学ぶ資料 (`docs/lecture/`)。引用と実行結果は、テストで元と一致を確かめる |
