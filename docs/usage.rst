使い方
======

コマンド
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - コマンド
     - 内容
   * - ``docspipeline init TARGET --project NAME --author A``
     - ``TARGET/docs`` に ``conf.py`` と雛形、``.github/workflows/docs.yml`` を作る。
       ``--package`` (Python のソース)・``--cpp`` (C++ のソース)・``--hou`` で構成を選ぶ。
       既存のファイルは ``--force`` を付けない限り上書きしない。
       CI の docstring の関門は、``--min-coverage`` (既定 80) 未満で **失敗する**。
       ``--package`` / ``--cpp`` に **実在しない場所** を指定すると、何も書かずに終了コード 2 で止まる。
   * - ``docspipeline build [DOCS]``
     - Sphinx でビルドする。既定は警告をエラー扱い (``-W --keep-going``)。
       ``-b confluence`` でも **公開はしない** (常に ``local``)。公開できるのは ``publish`` だけ。
       ``--require-mermaid`` では、保存済みの環境 (増分ビルドのキャッシュ) を使わず、全部を読み直す (``-E``)。
       前のビルドが「コードのまま」で済ませたページを、変更なしとして飛ばされると、方針が素通りするため。
   * - ``docspipeline linkcheck [DOCS]``
     - 外部リンクの切れを確認する。
   * - ``docspipeline coverage PATH...``
     - docstring が無い公開 API を一覧する。``--fail-under`` で基準を決められる。
       存在しないパス・構文エラーのファイルは、終了コード 2 のエラーにする (「100%」と黙って報告しない)。
       ``__all__`` は ``= [...]``・``: list[str] = [...]``・``+= [...]`` を読む。
       ``_`` で始まる名前のモジュール (``_compat.py``・``_impl/``) は、公開 API ではないので数えない。
   * - ``docspipeline check-diagrams [DOCS]``
     - ``.drawio`` に、書き出した SVG があるかを確認する。``DOCS`` が無ければ終了コード 2。
       ``_build``・``_generated``・``_doxygen``・``node_modules``・隠しディレクトリは探さない。
   * - ``docspipeline map PACKAGE``
     - ソースを構文解析して、モジュールの依存の地図を作る (Markdown の下書き / Mermaid / JSON)。
       ローカルで読むだけで、外部へは送信しない。``--fail-on-cycle`` で、循環があれば失敗させる。
       使い方は :doc:`learn/09-structure-map`。
   * - ``docspipeline doctor``
     - 手元で使える機能 (``mmdc``・``doxygen``・Confluence の設定など) を確認する。トークンの値は出さない。
   * - ``docspipeline confluence-check [DOCS]``
     - Confluence への接続・認証・権限を確認する。ページは変更しない。
   * - ``docspipeline publish [DOCS] --mode MODE``
     - Confluence 形式でビルドする。:doc:`confluence` を参照。``dryrun`` / ``publish`` では、Mermaid が画像にならなければ
       **失敗させる** (``DOCSPIPELINE_MERMAID_MISSING=error`` を自動で付け、全部を読み直す)。黙ってコードのままにすると、
       Confluence のページが、図の無いページに置き換わるため。

環境変数
--------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 名前
     - 内容
   * - ``DOCSPIPELINE_OFFLINE``
     - ``1`` で intersphinx と nitpicky を無効にする (外部サイトにつなげない環境用)
   * - ``DOCSPIPELINE_MERMAID_MISSING``
     - ``literal`` / ``warn`` / ``error`` (:doc:`design` を参照)
   * - ``DOCSPIPELINE_MMDC``
     - ``mmdc`` のパス。省略すると ``PATH`` と ``node_modules/.bin`` から探す
   * - ``DOCSPIPELINE_PUPPETEER_CONFIG``
     - ``mmdc`` に渡す Puppeteer の設定ファイル。CI などでサンドボックスを切るときに使う
   * - ``DOCSPIPELINE_SKIP_DOXYGEN``
     - ``1`` で Doxygen の実行を飛ばす (C++ の指示子は警告になるので、``--no-strict`` と併用する)

プロンプトのコピー
------------------

手順の説明に、そのまま Claude Code に渡せるプロンプトを載せられる。HTML では「プロンプトをコピー」ボタンが付く。

.. code-block:: text

   .. prompt:: 新しいリポジトリに docs/ を作る

      このリポジトリに DocsPipeline で docs/ を作ってください。
      docspipeline init と docspipeline build を実行し、警告が出たら原因を直してください。

Markdown (MyST) では、次のように書く。

.. code-block:: text

   ```{prompt} 新しいリポジトリに docs/ を作る
   このリポジトリに ...
   ```

* 題名は省略できる (既定: 「Claude Code に渡すプロンプト」)。
* Confluence など HTML 以外では、題名と普通のコードブロックになる。
* **秘密情報を書かない**。``TOKEN=値`` のような形があれば、値を伏せた警告を出す。環境変数は、名前だけを書く。
* 書き方の指針: 何をしてほしいか → 手順 → **してはいけないこと** (コミットしない、値を書き写さない、など) の順に書く。

設定の追加
----------

:func:`docspipeline.config.build_config` が返した値は、``conf.py`` の中で上書き・追記できる。

.. code-block:: python

   globals().update(build_config(confdir=__file__, project="X", author="me"))

   # 型変数など、解決できない参照を警告から外す
   nitpick_ignore_regex += [(r"py:class", r"mypkg\.T")]

使うときの注意
--------------

* ``TypeVar`` を使った型注釈は、nitpicky で未解決の参照になる。上のように外すか、型注釈を単純にする。
* autodoc はコードを ``import`` する。副作用のある ``import`` は、文書のビルドでも実行される。
  ``docspipeline coverage`` は ``import`` せずに構文だけを読む。
