# 設計

## 全体の流れ

![書く (Python・Markdown・C++・図) → 組み立てる (Sphinx と拡張) → 届ける (HTML・Confluence)。下に、CI が守る項目](diagrams/system-overview.drawio.svg)

「書く」ものを、Sphinx と拡張が「組み立て」、HTML と Confluence に「届ける」。下の「守る」は、CI が毎回確かめる項目。
青い矢印は入力、オレンジは公開の経路を表す。

図は diagrams.net で開ける `.drawio` と、書き出した `.drawio.svg` の両方をリポジトリに置く。
生成の仕方と、図の足し方は [拡張のしかた](learn/04-extend.md) を参照。`docspipeline check-diagrams` が、書き出しの漏れを確認する。

## 設計方針

1. **既存の Markdown 文書を捨てない。** Sphinx 側で Markdown を読めるようにする (MyST)。
   読み物は Markdown (Mermaid の図つき) で書き、API リファレンスだけを reStructuredText で書く。
2. **生成物はコードの隣に置く。** 各リポジトリの `docs/` に `conf.py` を置き、共通の設定は
   {py:func}`docspipeline.config.build_config` から読み込む。
3. **公開は最後の工程。** 既定は `local` モードで、ネットワークにつながない。
4. **秘密情報は環境変数のみ。** API トークンを設定ファイルや文書に書かない。出力からも伏せる。

## 公開モード

公開は、段階を **一つずつ** 進める。既定は `local`。環境変数の不足や接続テストの失敗は、その場で止まる。

```mermaid
%%{init: {"theme":"base","fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","themeVariables":{"fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","primaryColor":"#ffffff","primaryBorderColor":"#d0d5dd","primaryTextColor":"#101828","lineColor":"#667085","clusterBkg":"#f2f4f7","clusterBorder":"#d0d5dd","edgeLabelBackground":"#ffffff"},"flowchart":{"wrappingWidth":480,"nodeSpacing":40,"rankSpacing":56,"padding":14},"sequence":{"mirrorActors":false,"wrap":false,"width":150,"actorMargin":30,"messageMargin":34}}}%%
stateDiagram-v2
    direction LR
    [*] --> local
    local: local<br/>出力だけ作る (既定)
    dryrun: dryrun<br/>接続して確認のみ
    publish: publish<br/>親ページ配下へ公開
    local --> dryrun: --mode dryrun<br/>(環境変数 5 つ + 接続テスト)
    dryrun --> publish: --mode publish<br/>(同じ条件)
    local --> [*]: 何も送らない
    dryrun --> [*]: 不足・失敗はここで終了
    publish --> [*]
```

## 依存の向き

`docspipeline` のモジュールは、Sphinx に依存するかどうかで二つに分かれる。
**core は Sphinx が無い環境でも動く**。Sphinx を `import` してよいのは、拡張だけ。

```mermaid
%%{init: {"theme":"base","fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","themeVariables":{"fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","primaryColor":"#ffffff","primaryBorderColor":"#d0d5dd","primaryTextColor":"#101828","lineColor":"#667085","clusterBkg":"#f2f4f7","clusterBorder":"#d0d5dd","edgeLabelBackground":"#ffffff"},"flowchart":{"wrappingWidth":480,"nodeSpacing":40,"rankSpacing":56,"padding":14},"sequence":{"mirrorActors":false,"wrap":false,"width":150,"actorMargin":30,"messageMargin":34}}}%%
flowchart TD
    SPHINX["Sphinx 本体"]:::input

    subgraph CORE["core (Sphinx なしで動く)"]
        CLI["cli"]:::plain
        PARTS["scaffold・doctor・diagrams<br/>docstring_coverage・structure_map"]:::plain
        MMDC["mmdc・files"]:::plain
        CONF["confluence<br/>公開の安全装置"]:::out
    end

    subgraph EXT["拡張 (Sphinx が要る)"]
        CFG["config<br/>build_config()"]:::proc
        PLUG["guard・mermaid<br/>doxygen・prompt"]:::proc
    end

    CLI --> PARTS
    CLI --> CONF
    PARTS --> MMDC
    CLI -.->|"子プロセスで起動"| SPHINX
    SPHINX -->|"conf.py"| CFG
    CFG --> CONF
    CFG -.->|"extensions の名前"| PLUG
    PLUG --> MMDC

    classDef input fill:#dae8fc,stroke:#1a73e8,color:#101828
    classDef proc fill:#e6f4f1,stroke:#0f9d8a,color:#101828
    classDef out fill:#fff7ed,stroke:#e8710a,color:#101828
    classDef stop fill:#fef3f2,stroke:#d92d20,color:#101828
    classDef plain fill:#ffffff,stroke:#d0d5dd,color:#101828
```

実際の依存は、`docspipeline map docspipeline` で機械的に読み取れる ([機械の地図](learn/09-structure-map.md))。
`tests/test_structure_map.py` が、この向きを検査する。

## 判断の記録

### Doxygen と Sphinx の連携方式

Breathe を採用した。

- Breathe は Doxygen の XML を Sphinx の指示子 (`doxygenclass` など) で取り込む。
  取り込む対象を文書の側で選べるので、公開したい API だけを出せる。
- HTML をそのまま埋め込む方式は、Confluence に載せられないので除いた。
- ページを自動生成する方式は、生成したページの階層が Confluence の親ページ配下の階層と
  噛み合うか、確認できていないので採らなかった。
- どの方式も RAGReel の実際のコードでは試していない。ここでの比較は、サンプルのコードでの動作確認と、
  各拡張の説明に基づく。

### Mermaid の扱い

ビルド時に SVG へ変換し、HTML でも Confluence でも同じ画像を取り込む。文字は HTML ではなく SVG の
`<text>` で描かせる (`htmlLabels: false`)。画像として取り込む先で文字が消えるのを避けるため。
`mmdc` が無いときの挙動は `docspipeline_mermaid_missing` で決める。

```mermaid
%%{init: {"theme":"base","fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","themeVariables":{"fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","primaryColor":"#ffffff","primaryBorderColor":"#d0d5dd","primaryTextColor":"#101828","lineColor":"#667085","clusterBkg":"#f2f4f7","clusterBorder":"#d0d5dd","edgeLabelBackground":"#ffffff"},"flowchart":{"wrappingWidth":480,"nodeSpacing":40,"rankSpacing":56,"padding":14},"sequence":{"mirrorActors":false,"wrap":false,"width":150,"actorMargin":30,"messageMargin":34}}}%%
flowchart TD
    A["Mermaid の指示子を実行"]:::proc --> B["mmdc で SVG に変換<br/>(内容のハッシュでキャッシュ)"]:::proc
    B -->|"成功"| OK["画像として取り込む"]:::out
    B -->|"mmdc が無い / 変換に失敗"| P["方針を見る<br/>docspipeline_mermaid_missing"]:::plain
    P -->|"literal (既定)"| L["コードのまま表示"]:::plain
    P -->|"warn"| W["警告 + コードのまま表示"]:::plain
    P -->|"error"| E["ビルドを失敗させる"]:::stop
    classDef input fill:#dae8fc,stroke:#1a73e8,color:#101828
    classDef proc fill:#e6f4f1,stroke:#0f9d8a,color:#101828
    classDef out fill:#fff7ed,stroke:#e8710a,color:#101828
    classDef stop fill:#fef3f2,stroke:#d92d20,color:#101828
    classDef plain fill:#ffffff,stroke:#d0d5dd,color:#101828
```

| 値 | 挙動 |
|---|---|
| `literal` (既定) | コードをそのまま表示する |
| `warn` | 警告を出して、コードをそのまま表示する |
| `error` | ビルドを失敗させる。CI では `docspipeline build --require-mermaid` で、この値になる |

図の色とフォントは、GitHub (Markdown のまま) と HTML で揃える。各ブロックの 1 行目に、標準の `%%{init}%%` の行を置き、
`docspipeline check-mermaid` が確かめる (`--fix` で入れられる)。`docspipeline mermaid-style` が、その行と `classDef` の組を表示する。

### 外部資料 (Z16: oh-my-mermaid) の取り込み方

設計書の追補にある「コードから構造図と説明の階層を作る」という考え方を、**自前の** `docspipeline map` として実装した。
外部のツールは導入していない。

- 取り入れたもの: 「機械が読み取った事実 (依存の地図)」と「人が書く理由 (説明)」を **分けて持つ** 考え方。
  地図は事実なので毎回作り直せる。説明は人が書き、地図とのずれをテストで検出する。
- 導入しなかった理由: 外部ツールの中身 (SKILL.md・監査結果) を、この作業では確かめていない。また `omm push` のように、
  コードの情報を外部へアップロードする機能があるため、非公開のリポジトリには使えない。
  自前の `map` は、ローカルで読むだけで、何も送信しない。
- 比べていないもの: Graphify (X3) の地図との比較は、Graphify を導入していないので **未実施**。

出力は「下書き」として扱う。推定を含むので、人が確認してから使い、そのまま公開しない
(出力の冒頭に、その旨の警告が入る)。使い方と限界は [機械の地図](learn/09-structure-map.md)。

### ASCII モチーフ (提案) の扱い

設計書の最新の追補にある「ASCII モチーフ」(蚕・繭、実装系統 B) は、**実装していない**。

- 設計書の側が「出す場所は、UI を作る段階で決める」「本文・操作部品には出さない」としている。
  DocsPipeline には、いまのところ UI が無い (CLI と、Sphinx が作る静的な HTML だけ)。
  出す場所が決まっていないものを、先に作らない。
- 上流 (ascii-sharks) の動作は、設計書の側で確認済み (型検査・ビルド成功、60fps) になった。
  未確認なのは、各プロジェクトへ組み込んだときの負荷。出す場所が決まらないうちは、負荷も測れない。
- UI を作る段階で採るなら、`prefers-reduced-motion` では静止画 1 枚にし、既存の色だけを使う
  (設計書の条件)。HTML のテーマ (furo) に足す場合は、本文の可読性とページの重さを、先に測ること。

### 「Copy prompt」(Z19) の取り込み方

手順の説明に、そのまま Claude Code に渡せるプロンプトのコピーボタンを付ける、という考え方を、**自前の** Sphinx 拡張
({py:mod}`docspipeline.prompt`) として実装した。外部のコード・画像・文章は使っていない。

- 書き方は `.. prompt:: 題名` (Markdown では、コードフェンスの言語名の代わりに `{prompt}` と題名を書く)。
  使い方は [使い方](usage.md) を参照。
- 標準のノード (`container`・`paragraph`・`literal_block`) だけで組み立てる。独自のノードを作らないので、
  Confluence などのビルダーでも、**題名と普通のコードブロック** として出る (ボタンは出ない)。
- ボタンは JavaScript で足す。JavaScript が無ければ、ボタンが無いだけで、本文は読めて、選択してコピーできる。
  `https` でないページ (`file://` など) では、`navigator.clipboard` の代わりに、選択して `copy` の命令を使う。
- 新しい色は足さない。テーマ (furo) の色の変数を使うので、ライトとダークの両方に合う。動きも付けない。
- **プロンプトに秘密情報を入れない**。トークンらしき `名前=値` の形があれば、値を伏せた警告を出す (`-W` で失敗)。
  手順書は広く読まれ、コピーされて、別の場所に貼られるため。

### PDFMathTranslate (Z31) は取り込まない

英語の PDF 資料を、レイアウトを保って日本語にする候補。設計書の方針どおり、**手元の道具としてのみ** 使い、
DocsPipeline には組み込まない。

- ライセンスが AGPL-3.0 で、コピーレフトが強い。このリポジトリのコード・依存・CI に入れると、
  このリポジトリのライセンスの扱いに影響しうる (法的な判断はしていない)。依存に足さず、コードを写さず、呼び出しもしない。
- DocsPipeline の目的 (docstring から API 文書を作り、公開する) と、直接のつながりが無い。
- 動作・翻訳の質・入力した PDF の扱い (外部へ送られるか) は、確かめていない。使うなら、導入前に確認する。

## よくある誤り

- `docs/conf.py` で例外を投げる実装にすると、Sphinx がスタックトレースつきの内部エラーとして出す。
  設定の誤りは `docspipeline_config_error` に入れて、{py:mod}`docspipeline.guard` が報告する。
- **core のモジュールから、Sphinx を import するモジュールを import する**。`docspipeline` の CLI は、
  Sphinx が入っていない環境でも動く (`init`・`coverage`・`map`・`doctor`)。Sphinx に依存してよいのは
  拡張 (`guard`・`mermaid`・`doxygen`・`prompt`) だけで、`mmdc` の探索のように両方が使う部品は、Sphinx に依存しない
  {py:mod}`docspipeline.mmdc` に置く。`tests/test_structure_map.py` が検査する。
- `confluence_*` の設定は、未設定だと同名の環境変数から補われる。公開の可否に関わる項目は、
  {py:func}`docspipeline.confluence.sphinx_settings` がすべて明示している。

## 関連

- [Confluence への公開](confluence.md)
- [運用手順](runbook.md)
