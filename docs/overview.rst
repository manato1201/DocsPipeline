概要
====

目的
----

コードの docstring から API 文書を作り、構成図を加えて、Confluence に公開できるようにする。
各リポジトリは ``docs/conf.py`` に名前と対象のパスを書くだけで、拡張・autodoc・Markdown の取り込み・
Confluence の安全設定を DocsPipeline から受け取る。

扱うもの
--------

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - 部品
     - 役割
     - このリポジトリでの場所
   * - Sphinx + autodoc / napoleon
     - Python の docstring (Google 形式) から API 文書を生成する
     - :mod:`docspipeline.config`
   * - MyST
     - 既存の Markdown 文書をそのまま取り込む
     - :mod:`docspipeline.config`
   * - Doxygen + Breathe
     - C++ のコメントから API 文書を生成する
     - :mod:`docspipeline.doxygen`
   * - Mermaid → SVG
     - Mermaid の図をビルド時に画像へ変換する
     - :mod:`docspipeline.mermaid`
   * - Confluence ビルダー
     - 専用の親ページ配下へ公開する
     - :mod:`docspipeline.confluence`
   * - ``hou`` スタブ
     - Houdini の外で ``hou`` を使うコードを文書化する
     - :mod:`docspipeline.stubs.hou`

.. image:: diagrams/system-overview.drawio.svg
   :alt: 書く・組み立てる・届ける・守る
   :width: 100%

最短の手順
----------

.. code-block:: bash

   $ pip install "docspipeline[docs,cpp,confluence] @ git+https://github.com/manato1201/DocsPipeline"
   $ docspipeline init . --project "My Tool" --author "me" --package ../src
   $ docspipeline build docs

``build`` は警告をエラー扱いにする。リンク切れ・未解決の参照があれば失敗する。

見るポイント
------------

* 公開は最後の工程。まずローカルの HTML で品質を確保する。公開先の設定が無くても、HTML までで完了できる。
* 既定のモードでは Confluence に一切つながらない (:doc:`confluence`)。
* 保守・拡張する人は、:doc:`learn/index` から読む。

使うときの注意
--------------

* 企業のコードや、企業の Confluence 連携の実装は、このリポジトリに持ち込まない。
* Mermaid の変換には ``mmdc`` (mermaid-cli) が要る。無い環境では、図はコードのまま表示される (:doc:`design`)。
