# DocsPipeline

docstring から API 文書を自動生成し、構成図を加えて、Confluence に公開するための共通設定と CLI。

## どこから読むか

```mermaid
%%{init: {"theme":"base","fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","themeVariables":{"fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","primaryColor":"#ffffff","primaryBorderColor":"#d0d5dd","primaryTextColor":"#101828","lineColor":"#667085","clusterBkg":"#f2f4f7","clusterBorder":"#d0d5dd","edgeLabelBackground":"#ffffff"},"flowchart":{"wrappingWidth":480,"nodeSpacing":40,"rankSpacing":56,"padding":14},"sequence":{"mirrorActors":false,"wrap":false,"width":150,"actorMargin":30,"messageMargin":34}}}%%
flowchart TD
    START{{"あなたは？"}}:::plain
    START -->|"使う"| U["概要 → 使い方<br/>(利用者向け)"]:::input
    START -->|"保守・拡張する"| M["保守ガイド<br/>(learn/)"]:::proc
    START -->|"基礎から学ぶ"| L["講義資料<br/>(lecture/)"]:::out
    U --> U2["Confluence への公開 / 運用手順"]:::plain
    M --> M2["コードの読み方 →<br/>拡張のレシピ → テスト"]:::plain
    L --> L2["Python の基礎 → 解析 → Sphinx →<br/>安全設計 → テスト → 図 → CI"]:::plain
    classDef input fill:#dae8fc,stroke:#1a73e8,color:#101828
    classDef proc fill:#e6f4f1,stroke:#0f9d8a,color:#101828
    classDef out fill:#fff7ed,stroke:#e8710a,color:#101828
    classDef stop fill:#fef3f2,stroke:#d92d20,color:#101828
    classDef plain fill:#ffffff,stroke:#d0d5dd,color:#101828
```

| 読者 | 入口 |
|---|---|
| 文書を作って公開したい | [概要](overview.md) → [使い方](usage.md) → [Confluence への公開](confluence.md) |
| 保守・拡張したい | [保守ガイド](learn/index.md) |
| 基礎から、講義のように学びたい | [講義資料](lecture/index.md) (全 14 回。実行できる例と演習つき) |
| 文書を更新する | [運用手順](runbook.md) |

```{toctree}
:hidden:
:maxdepth: 2
:caption: 利用者向け

overview
design
usage
confluence
cpp
hou
output-formats
runbook
```

```{toctree}
:hidden:
:maxdepth: 2
:caption: 保守・拡張する人向け

learn/index
```

```{toctree}
:hidden:
:maxdepth: 1
:caption: 講義資料

lecture/index
```

```{toctree}
:hidden:
:caption: リファレンス

api
```
