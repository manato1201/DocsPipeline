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
   * - ``docspipeline build [DOCS]``
     - Sphinx でビルドする。既定は警告をエラー扱い (``-W --keep-going``)。
   * - ``docspipeline linkcheck [DOCS]``
     - 外部リンクの切れを確認する。
   * - ``docspipeline coverage PATH...``
     - docstring が無い公開 API を一覧する。``--fail-under`` で基準を決められる。
   * - ``docspipeline check-diagrams [DOCS]``
     - ``.drawio`` に、書き出した SVG があるかを確認する。
   * - ``docspipeline confluence-check [DOCS]``
     - Confluence への接続・認証・権限を確認する。ページは変更しない。
   * - ``docspipeline publish [DOCS] --mode MODE``
     - Confluence 形式でビルドする。:doc:`confluence` を参照。

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
