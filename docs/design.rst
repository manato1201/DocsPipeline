設計
====

全体の流れ
----------

.. image:: diagrams/system-overview.drawio.svg
   :alt: 書く (Python・Markdown・C++・図) → 組み立てる (Sphinx と拡張) → 届ける (HTML・Confluence)。下に、CI が守る項目

「書く」ものを、Sphinx と拡張が「組み立て」、HTML と Confluence に「届ける」。下の「守る」は、CI が毎回確かめる項目。
青い矢印は入力、オレンジは公開の経路を表す。

図は diagrams.net で開ける ``.drawio`` と、書き出した ``.drawio.svg`` の両方をリポジトリに置く。
生成の仕方と、図の足し方は :doc:`learn/04-extend` を参照。``docspipeline check-diagrams`` が、
書き出しの漏れを確認する。

設計方針
--------

1. **既存の Markdown 文書を捨てない。** Sphinx 側で Markdown を読めるようにし (MyST)、
   新規の API 文書と構成の文書だけを reStructuredText で書く。
2. **生成物はコードの隣に置く。** 各リポジトリの ``docs/`` に ``conf.py`` を置き、共通の設定は
   :func:`docspipeline.config.build_config` から読み込む。
3. **公開は最後の工程。** 既定は ``local`` モードで、ネットワークにつながない。
4. **秘密情報は環境変数のみ。** API トークンを設定ファイルや文書に書かない。出力からも伏せる。

公開モード
----------

.. mermaid::
   :alt: local から dryrun、publish へ段階的に進む

   flowchart LR
       L["local<br/>出力だけ作る (既定)"] --> D["dryrun<br/>接続して確認のみ"] --> P["publish<br/>親ページ配下へ公開"]

判断の記録
----------

Doxygen と Sphinx の連携方式
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Breathe を採用した。

* Breathe は Doxygen の XML を Sphinx の指示子 (``doxygenclass`` など) で取り込む。
  取り込む対象を文書の側で選べるので、公開したい API だけを出せる。
* HTML をそのまま埋め込む方式は、Confluence に載せられないので除いた。
* ページを自動生成する方式は、生成したページの階層が Confluence の親ページ配下の階層と
  噛み合うか、確認できていないので採らなかった。
  どの方式も RAGReel の実際のコードでは試していない。ここでの比較は、サンプルのコードでの動作確認と、
  各拡張の説明に基づく。

Mermaid の扱い
^^^^^^^^^^^^^^

ビルド時に SVG へ変換し、HTML でも Confluence でも同じ画像を取り込む。文字は HTML ではなく SVG の
``<text>`` で描かせる (``htmlLabels: false``)。画像として取り込む先で文字が消えるのを避けるため。
``mmdc`` が無いときの挙動は ``docspipeline_mermaid_missing`` で決める。

.. list-table::
   :header-rows: 1

   * - 値
     - 挙動
   * - ``literal`` (既定)
     - コードをそのまま表示する
   * - ``warn``
     - 警告を出して、コードをそのまま表示する
   * - ``error``
     - ビルドを失敗させる。CI では ``docspipeline build --require-mermaid`` で、この値になる

外部資料 (Z16: oh-my-mermaid) の取り込み方
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

設計書の追補にある「コードから構造図と説明の階層を作る」という考え方を、**自前の** ``docspipeline map`` として実装した。
外部のツールは導入していない。

* 取り入れたもの: 「機械が読み取った事実 (依存の地図)」と「人が書く理由 (説明)」を **分けて持つ** 考え方。
  地図は事実なので毎回作り直せる。説明は人が書き、地図とのずれをテストで検出する。
* 導入しなかった理由: 外部ツールの中身 (SKILL.md・監査結果) を、この作業では確かめていない。また ``omm push`` のように、
  コードの情報を外部へアップロードする機能があるため、非公開のリポジトリには使えない。
  自前の ``map`` は、ローカルで読むだけで、何も送信しない。
* 比べていないもの: Graphify (X3) の地図との比較は、Graphify を導入していないので **未実施**。

出力は「下書き」として扱う。推定を含むので、人が確認してから使い、そのまま公開しない
(出力の冒頭に、その旨の警告が入る)。使い方と限界は :doc:`learn/09-structure-map`。

よくある誤り
------------

* ``docs/conf.py`` で例外を投げる実装にすると、Sphinx がスタックトレースつきの内部エラーとして出す。
  設定の誤りは ``docspipeline_config_error`` に入れて、:mod:`docspipeline.guard` が報告する。
* **core のモジュールから、Sphinx を import するモジュールを import する**。``docspipeline`` の CLI は、
  Sphinx が入っていない環境でも動く (``init``・``coverage``・``map``・``doctor``)。Sphinx に依存してよいのは
  拡張 (``guard``・``mermaid``・``doxygen``) だけで、``mmdc`` の探索のように両方が使う部品は、Sphinx に依存しない
  :mod:`docspipeline.mmdc` に置く。``tests/test_structure_map.py`` が検査する。
* ``confluence_*`` の設定は、未設定だと同名の環境変数から補われる。公開の可否に関わる項目は、
  :func:`docspipeline.confluence.sphinx_settings` がすべて明示している。

関連
----

* :doc:`confluence`
* :doc:`runbook`
