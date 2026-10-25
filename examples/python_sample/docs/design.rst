設計
====

.. 構成と、その形にした理由を書く。図は docs/diagrams/ に置く (diagrams.net の .drawio と書き出した SVG)。

構成
----

判断の記録
----------

.. mermaid::
   :alt: 計測の流れ

   flowchart LR
       A["start()"] --> B["処理"] --> C["stop()"]
