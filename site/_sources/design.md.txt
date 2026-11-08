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
        PARTS["scaffold・doctor・diagrams<br/>docstring_coverage・structure_map<br/>messages"]:::plain
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

### 契約と副作用の境界 (Z39) の取り込み方

設計書の第 5 弾の追補 (Z39) の考え方を、このリポジトリの **設計の約束** として取り入れた。外部のコードは使っていない。

- **契約の欄**: 主な関数に、事前条件・事後条件・不変条件を書く ([契約の表](contracts.md))。
  docstring の `Args` / `Raises` が事前条件、`Returns` が事後条件に当たる。契約は、AI に実装や変更を頼むときの指示文になる。
- **契約からテストを作る**: 表の各行に、検証するテストを対応づけた。不変条件は、1 つの例ではなく **いろいろな入力** (乱数の種を固定した
  生成・総当たりとの突き合わせを含む) で確かめる (`tests/test_contracts.py`)。表の関数とテストが実在することも、同じテストが確かめる。
- **副作用の境界**: 関数を、純粋 / 読み取り / 書き込み・起動の 3 層に分けた。外側の層が内側を呼ぶ。
  **純粋** の層は、`open`・`os.environ`・子プロセス・ネットワークを禁じた状態で呼んでも動き、同じ入力なら同じ出力になる
  (違反すると、テストが失敗する)。**読み取り** の層は、前後でディレクトリの中身が変わらない。
- **読む範囲の決め方**: 純粋な層は仕様を読めば足りる。書き込み・起動の層と、秘密を扱う部分 (`mask_secrets` など) は、深く読む。
  レビューの負担を、この線引きで減らす。

純粋な関数が、`environ=None` (省略すると `os.environ`) を許している点には、注意がいる。省略したときは純粋でなくなるので、
テストは、必ず `environ` を渡して確かめる。**この追補を取り入れる過程で、既存の関数に契約違反は見つからなかった** (3 通りの変異で、テストが失敗することは確かめた)。

### 第 6 弾の外部資料 (Z50・Z47・Z66 k) の取り込み方

設計書の第 6 弾の追補 (2026-11-08) は、3 つの考え方を挙げている。元の資料は、README と公開ページを **読んだだけ** で、何も導入・実行していない
(数値は発信者の主張で未測定)。この実装も、**形式と考え方だけ** を取り入れ、外部のコード・文章は使っていない。

| 項目 | 取り込み | 中身 |
|---|---|---|
| **Z50** 設計書のひな形をスキルにする | 実装 | `skills/design-doc/`: `SKILL.md` + `template.md` + `scripts/check_design_doc.py`。契約の欄 (Z39) つき |
| **Z47** 「読んだ / 推測した」の札 | 実装 | `docspipeline map` が、依存の辺に `EXTRACTED` / `INFERRED` を付ける |
| **Z66 k** 権利を層で書く | 一部 | README に層ごとの表を足した。**ライセンスそのものは未決定**で、`LICENSE` は作っていない |

**Z50: 設計書のひな形をスキルにする**

- スキル = `SKILL.md` (front matter は `name` と `description` だけ) + スクリプト + 資料、のフォルダ。形式は設計書の記述に基づく。
  資料の側の仕様 (`spec/`) と、各スキルのライセンスは、**確かめていない**。外部のスキルは、写していない。
- ひな形の見出しは、`docspipeline init` が作る設計ページ (`design.rst.tmpl`) と揃え、テストが食い違いを検出する。
  契約の表の列は、[契約の表](contracts.md) と同じ。検査 (`check_design_doc.py`) は、**このリポジトリ自身の契約の表を通す** ことで、規則が実態から離れないようにした。
- 検査は **書き忘れ** (見出し・空の欄・層の名前・`〈…〉` の残り) を見つけるだけで、契約の中身が正しいかは確かめない。
- Claude Code が、`.claude/skills/` に置いたこのスキルを実際に読み込んで使うことは、**確かめていない** (形式の検査とスクリプトのテストまで)。
- 導入先の `init` が、このスキルも書き出すようにする案は、採っていない (利用者が、使う側の `.claude/skills/` に写せば足りる)。

**Z47: 「読んだ / 推測した」の札**

- 設計書の追補は、Graphify の `EXTRACTED` (原文に明示) / `INFERRED` (推測) の札の発想を、自動生成した図に使う、としている (P9)。
  Graphify は導入していない。**札の付け方は自前**: 依存の種類から決まる (`structure_map.EDGE_LABELS`)。
- `import` 文 (関数の中のものを含む) は `EXTRACTED`。モジュール名と一致する文字列による参照は、その文字列が実際にモジュールを指すかを
  読んだだけでは確かめられないので `INFERRED`。**循環は読んだ辺だけで判定**し、推測で循環と断定しない。
- 出し方: 図の推測の辺に「推測」と書く / モジュール一覧に `(推測)` / 札つきの依存の表 / JSON の `edges`。「どこからも使われていない」の判定も、
  無いことからの推測として出す。
- 限界: 札は 2 値だけ。`EXTRACTED` の辺も、実行時に必ず起きるとは限らない (条件つきの `import` など)。AI による意味づけはしていないので、
  `INFERRED` は **文字列の一致** だけを指す。

**Z66 k: 権利を層で書く**

- コード・文章・図・名前を分けて書く、という書き方を、README の「権利」に取り入れた。
- いまの状態を、そのまま書いた: `LICENSE` が無く、コード・文章・図のライセンスは **未決定**。決めるのは作者で、この実装では決めていない
  (決めずに MIT などと書くと、事実と食い違う)。README の表と `LICENSE` の有無が食い違うと、テストが失敗する。
- `docspipeline init` が作る雛形に、権利の欄を足すことは、していない (雛形リポジトリの標準にする案は、ライセンスが決まってから)。

### 使いやすさの提案 (UX1〜UX7) の取り込み方

設計書の側の「使いやすさの提案」(2026-11-04) は、全プロジェクト共通の 7 項目を挙げ、DocsPipeline には
「実装を始めるときに、UX1・UX2・UX4 を最初の部品として入れる」と書いている。DocsPipeline は **画面を持たない CLI** なので、
画面向けの項目は、CLI に置き換えられるものだけを取り入れた。提案の根拠は、設計書の語句の数え上げで、**アプリは操作されていない**
(この実装でも、手元の端末で動かして確かめたのは、テストが再現できる範囲まで)。

| 項目 | 取り込み | 中身 |
|---|---|---|
| **UX4 エラーの書き方の型** | 実装 | 何が起きた / なぜ / 次の一手の 3 行 (`messages.format_error`)。CLI の全てのエラーが通り、3 つのどれかが空だと例外。テストが、全てのエラーの経路で 3 行の形を確かめる |
| **UX2 進捗・取り消し・完了通知** | 実装 (CLI の範囲) | 始まり・終わり (経過時間)・`publish` の `[1/3]` の段階表示。**Ctrl-C** で子プロセスを止め、終了コード 130 (失敗とは区別)。端末の外への通知 (メール・チャット) は、CI の仕事で、実装していない |
| **UX6 空状態に「次の一手」** | 実装 (CLI の範囲) | `doctor` の使えない機能に、入れるコマンドなどを添える。成功した HTML のビルドに、開く場所を示す。`init` は、元から次の手順を示していた |
| UX1 取り消しと履歴 | 一部 | 画面の Undo は当たらない。代わりに **壊す操作を絞った**: `init` は既存を上書きしない (`--force` のときも、先にコミットして差分で戻せる、と案内する)。`check-mermaid` は `--fix` なしが確認だけ。公開は消さない。履歴の仕組みは作らない |
| UX5 続きから再開 | 未実装 | Sphinx の増分ビルドは、変わっていない文書を飛ばすが、**中断後の再実行が続きから動くかは、確かめていない** |
| UX3 状態を URL に | 対象外 | CLI に URL は無い。HTML 版は静的なので、ページごとの URL とアンカーで共有できる |
| UX7 キー操作・コマンドパレット | 未実装 | CLI のシェル補完 (`argcomplete` など) は、依存を増やすので、必要が出るまで入れない |

## 設計書の追補と、この実装での扱い

設計書の追補は、日付順に積まれている。**同じ話題が複数の追補にあるときは、新しい日付を優先する**。

| # | 追補 | 日付 | 設計書の状態 | この実装での扱い |
|---|---|---|---|---|
| 1 | 実務で運用するための拡張 | 2026-10-11 | — | Phase 5 (CI)・7 (更新の自動化)・`hou` のスタブは実装。Phase 6 は、ローカルの HTML と `site/` まで。Confluence の実環境は **未検証** |
| 2 | TakayuStudio 系 (T2・T11・T12) | 2026-10-15 | 提案 | 実装済み: 定型項目の雛形・[出力形式の表](output-formats.md)・ページ末尾の出典の注記 |
| 3 | 外部リソース (X3・X7・X16・Y9) | 2026-10-22 | 提案 | X16 (番号つきの図) は実装。X3 は、自前の `docspipeline map` で代える。X7・Y9 は、導入前に SKILL.md を読む前提で、取り込んでいない |
| 4 | 外部リソース 第 2 弾 (Y9) | 2026-10-23 | 提案 | 取り込んでいない (同上) |
| 5 | 外部リソース 第 3 弾の続き (Z16) | 2026-10-27 | 提案 | 自前の `docspipeline map` として実装 (上の「外部資料 (Z16: oh-my-mermaid) の取り込み方」) |
| 6 | ASCII モチーフ | 2026-10-27 | 提案・未実装 | 実装していない (出す場所が決まっていない) |
| 7 | 第 4 弾 (Z19・Z31) | 2026-10-30 | 提案・未実装 | Z19 は実装 (`prompt` 拡張)。Z31 は、ライセンス (AGPL-3.0) のため取り込まない |
| 8 | 第 5 弾 (Z39・副作用の境界・読む範囲) | 2026-11-02 | 提案・未実装 | 実装 (上の節と [契約の表](contracts.md)) |
| 9 | 使いやすさの提案 (UX1〜UX7) | 2026-11-04 | 提案・未実装 | 一部実装: UX4・UX2・UX6 (CLI の範囲)。UX1 は一部、UX5・UX7 は未実装、UX3 は対象外 (上の節) |
| 10 | 第 6 弾 (Z50・Z47・Z66 k) | 2026-11-08 | 提案・未実装 | Z50 は実装 (`skills/design-doc/`)。Z47 は実装 (`map` の札)。Z66 k は一部 (README の権利の層の表。ライセンスは未決定) |

設計書の「追補の索引」が、状態の語彙の元。進み具合は、設計書の側の `IMPLEMENTATION_PROGRESS` を参照 (このリポジトリには、含まれない)。
なお、設計書の索引には、第 6 弾 (2026-11-08) が **まだ載っていない** (本文には追補がある)。この表の 10 番は、本文から数えた。

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
- [契約と副作用の境界](contracts.md)
- [運用手順](runbook.md)
