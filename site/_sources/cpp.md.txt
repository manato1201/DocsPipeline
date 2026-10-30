# C++ の文書 (Doxygen + Breathe)

## 目的

C++ のヘッダーのコメントから、Python と同じ Sphinx の文書に API を取り込む。

## 仕組み

```mermaid
%%{init: {"theme":"base","fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","themeVariables":{"fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","primaryColor":"#ffffff","primaryBorderColor":"#d0d5dd","primaryTextColor":"#101828","lineColor":"#667085","clusterBkg":"#f2f4f7","clusterBorder":"#d0d5dd","edgeLabelBackground":"#ffffff"},"flowchart":{"wrappingWidth":480,"nodeSpacing":40,"rankSpacing":56,"padding":14},"sequence":{"mirrorActors":false,"wrap":false,"width":150,"actorMargin":30,"messageMargin":34}}}%%
flowchart TD
    H["ヘッダー<br/>Doxygen コメント"]:::input
    I["① builder-inited<br/>(Breathe より先に走る)"]:::proc
    G["② Doxyfile を作る<br/>XML だけを出す設定"]:::proc
    D["③ doxygen を実行<br/>古い xml/ は先に消す"]:::proc
    X["④ _doxygen/xml/"]:::plain
    B["⑤ Breathe<br/>doxygenclass などの指示子"]:::proc
    P["API ページ"]:::out
    ERR["ビルドを失敗させる<br/>(SKIP_DOXYGEN=1 で飛ばせる)"]:::stop
    WARN["Sphinx の警告<br/>-W で CI が止まる"]:::stop

    H --> D
    I --> G --> D --> X --> B --> P
    I -.->|"doxygen が無い"| ERR
    D -.->|"コメントの書式の誤り"| WARN

    classDef input fill:#dae8fc,stroke:#1a73e8,color:#101828
    classDef proc fill:#e6f4f1,stroke:#0f9d8a,color:#101828
    classDef out fill:#fff7ed,stroke:#e8710a,color:#101828
    classDef stop fill:#fef3f2,stroke:#d92d20,color:#101828
    classDef plain fill:#ffffff,stroke:#d0d5dd,color:#101828
```

1. `build_config(cpp_sources=[...])` を指定すると、Breathe と {py:mod}`docspipeline.doxygen` が有効になる。
2. Sphinx のビルドの最初に、{py:mod}`docspipeline.doxygen` が Doxyfile を作って `doxygen` を走らせ、
   XML を `docs/_doxygen/xml` に出す。古い XML は、先に消す (消した関数が文書に残り続けないように)。
3. 文書の側で `doxygenclass` などの指示子を使って、取り込む API を選ぶ。

```text
.. doxygenclass:: sample_engine::Index
   :members:
```

## 見るポイント

- 関数名・クラス名は、Doxygen がコードから読み取った名前がそのまま出る。手で書き写さない。
- Doxygen のコメントの書式の誤りは、Sphinx の警告として転送される。`-W` で CI が止まる。
- `examples/cpp_sample` が動作確認用のサンプル。

## 使うときの注意

- `doxygen` 本体は別途インストールする (`apt install doxygen` など)。
  無いとビルドは失敗する。手元で飛ばしたいときは `DOCSPIPELINE_SKIP_DOXYGEN=1` と `docspipeline build --no-strict`
  を組み合わせる (C++ の指示子が「XML が無い」という警告になる。`-W` のままでは失敗する)。
- コメントが無いこと自体は警告にならない (`WARN_IF_UNDOCUMENTED = NO`)。
  コメントの網羅は、`doxygenclass` の出力を目で確認する。`docspipeline coverage` は Python だけを対象にする。
- 実際の RAGReel (Qt / C++) のコードでは、まだ試していない。Qt のマクロ (`Q_OBJECT` など) が
  Doxygen に与える影響は、着手時に `cpp_predefined` で調整する。
