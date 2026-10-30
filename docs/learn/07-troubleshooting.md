# トラブルシュート

## 目的

**症状 → 原因 → 見るファイル** の順で、切り分けを速くする。まず `docspipeline doctor`。

## 見るポイント

### 最初の三手

1. `docspipeline doctor` — `mmdc`・`doxygen`・Sphinx・環境変数の有無が、一覧で出る (値は出ない)。
2. `rm -rf docs/_build docs/_generated docs/_doxygen` — キャッシュを消して、もう一度。
3. `docspipeline build docs --no-strict` — 警告をエラーにせず、**全部の警告を読む**。

```{prompt} ビルドが失敗した原因を切り分ける
docspipeline build docs が失敗します。原因を切り分けてください。

1. docspipeline doctor を実行し、NG・なし の項目を挙げる。
2. rm -rf docs/_build docs/_generated docs/_doxygen のあと、docspipeline build docs --no-strict で、全部の警告を出す。
3. 警告を種類ごとに分け、docs/learn/07-troubleshooting.md の「症状の一覧」と照らして、原因と直し方を提案する。
4. 提案だけを報告し、私が許可するまで、ファイルは書き換えない。
5. 出力に API トークンなどの値が混ざっていたら、報告に書き写さず、その旨だけを伝える。
```

### 症状の一覧

```{list-table}
:header-rows: 1
:widths: 30 36 34

* - 症状・メッセージ
  - 原因
  - 見る場所
* - Mermaid の図が、コードのまま出る
  - `mmdc` が見つからない (方針が `literal`)
  - `mermaid.find_mmdc`。`DOCSPIPELINE_MMDC` か `npm install @mermaid-js/mermaid-cli`
* - `mmdc が失敗しました: ...`
  - Chromium が起動できない。CI ではサンドボックスが原因のことが多い
  - `DOCSPIPELINE_PUPPETEER_CONFIG` に `{"args":["--no-sandbox"]}` の設定ファイルを渡す
* - `doxygen が見つかりません`
  - Doxygen が未導入
  - `doxygen.run_doxygen`。導入するか、`DOCSPIPELINE_SKIP_DOXYGEN=1` + `--no-strict`
* - `doxygen: ...` の警告
  - ヘッダーのコメントの書式の誤り
  - 該当のヘッダー。メッセージにファイルと行が出る
* - `Cannot find file: .../_doxygen/xml/index.xml`
  - Doxygen が走っていない (`SKIP` か、`cpp_sources` の指定漏れ)
  - `config.build_config(cpp_sources=...)`
* - `エラー: パスがありません: ...` / `ディレクトリがありません: ...` (終了コード 2)
  - `coverage` / `check-diagrams` に渡したパスの打ち間違い・移動。以前は「100%」「問題なし」と黙って成功していた
  - 渡したパスを確かめる。CI の設定 (`docs.yml`) のパスも
* - `エラー: ソースの場所がありません: ...` (`init`、終了コード 2)
  - `--package` / `--cpp` に、`docs/` から見て実在しない場所を指定した
  - `docs/` からの **相対パス** で、実在する場所を指定する。以前は、API ページが空の文書を黙って作っていた
* - `dryrun` / `publish` が、変更していないページまで読み直して遅い
  - 意図した動作。公開系のモードは、増分ビルドのキャッシュを使わない (`-E`)。Mermaid の方針が、前のビルドの結果で素通りしないように
  - 手元で速く確かめたいときは、`publish` の既定の `local` を使う
* - `エラー: ...py:12: 構文エラー: ...` (終了コード 2)
  - `coverage` / `map` が読んだファイルが、Python として解釈できない
  - メッセージのファイルと行。`--fail-on-cycle` の失敗 (終了コード 1) とは区別できる
* - `dryrun` / `publish` が「mmdc が見つかりません」で失敗する
  - 図が画像にならないまま公開すると、Confluence のページが図の無いページに置き換わるため、公開系のモードでは失敗させている
  - `mmdc` を入れる。確認は `docspipeline doctor`
* - `次の環境変数が未設定です: ...`
  - `dryrun` / `publish` に必要な設定が足りない
  - `confluence.REQUIRED_ENV`。名前だけが出る
* - `DOCSPIPELINE_CONFLUENCE_MODE は ... のいずれかにしてください`
  - モードの綴り間違い (黙って `local` にはしない)
  - `confluence.current_mode`
* - `py:class reference target not found: X`
  - 参照先が文書に無い。型変数、外部ライブラリの型など
  - `nitpick_ignore_regex` に足す ([使い方](../usage.rst))
* - 標準ライブラリの型の警告だけが出る
  - 外に出られず、intersphinx が読めない
  - `DOCSPIPELINE_OFFLINE=1` (nitpicky を切る)。CI では出ないはず
* - `autodoc: failed to import ...`
  - `package_paths` が違う。依存が入っていない。`import` 時に例外
  - `docs/conf.py` の `package_paths`。`hou` なら `use_hou_stub=True`
* - `unsupported code language for confluence: X`
  - Confluence のコードマクロが知らない言語名
  - 文書側で `bash`・`text` などに直す ([出力形式](../output-formats.rst))
* - `inline comment detected ... page not updated`
  - 未解決のインラインコメントが付いたページを、更新せずに飛ばした
  - Confluence 側でコメントを解決する。意図した動作
* - 公開が、親ページの外の同名ページで止まる
  - 手で作られたページを奪わない設定 (`trample` が `False`)
  - 題名を変える (`CONFLUENCE_PAGE_PREFIX`) か、親ページの下に移す。**設定を緩めない**
* - `docs/conf.py` を変えたのに反映されない
  - Sphinx の環境キャッシュ
  - `rm -rf docs/_build`
```

### 図が崩れた

* `python -m pytest -q tests/test_diagrams.py` — どのカードが、どれと重なっているかを名前で教えてくれる。
* 生成物が定義とずれた: `python tools/diagrams/build_diagrams.py` で作り直す。

## 使うときの注意

* **トークンを貼り付けて質問しない**。ログを共有するときは、`docspipeline` 経由の出力 (伏せ字済み) を使う。それでも念のため、`CONFLUENCE_API_TOKEN` の値で検索して、残っていないか確かめる。
* 公開に関わる不具合は、原因が分かるまで `publish` を再実行しない。`dryrun` で再現する。

## よくある誤り

* 警告を `--no-strict` で **消したまま** にする。見るためだけに使い、直したら戻す。
* キャッシュを消さずに、「直ったはず」と判断する。

## 関連

* [ビルドの内側](03-build-internals.md) — どの段階で出たメッセージか
* [Confluence への公開](../confluence.rst)
