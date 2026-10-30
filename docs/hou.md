# Houdini の hou を使うコード

## 目的

Houdini の外では `import hou` ができない。`hou` を使うコードも、Houdini なしで autodoc とテストが通るように、
スタブ ({py:mod}`docspipeline.stubs.hou`) を共有する。

## 仕組み

スタブの場所は `sys.path` の **末尾** に足す。Houdini の中では、本物の `hou` が先に見つかる。

```mermaid
%%{init: {"theme":"base","fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","themeVariables":{"fontFamily":"Noto Sans JP, Hiragino Sans, Meiryo, sans-serif","primaryColor":"#ffffff","primaryBorderColor":"#d0d5dd","primaryTextColor":"#101828","lineColor":"#667085","clusterBkg":"#f2f4f7","clusterBorder":"#d0d5dd","edgeLabelBackground":"#ffffff"},"flowchart":{"wrappingWidth":480,"nodeSpacing":40,"rankSpacing":56,"padding":14},"sequence":{"mirrorActors":false,"wrap":false,"width":150,"actorMargin":30,"messageMargin":34}}}%%
flowchart TD
    A["autodoc が<br/>import hou を実行"]:::proc --> B{"Houdini の中？<br/>(本物の hou が sys.path にある)"}:::plain
    B -->|"はい"| REAL["本物の hou を使う"]:::out
    B -->|"いいえ"| S{"use_hou_stub=True？"}:::plain
    S -->|"はい"| STUB["末尾のスタブを使う<br/>属性・継承・呼び出しを受け流す"]:::proc
    S -->|"いいえ"| ERR["ImportError<br/>autodoc が読み込めない"]:::stop
    STUB --> NIT["基底クラスの参照は<br/>nitpicky の警告から自動で外す"]:::plain
    classDef input fill:#dae8fc,stroke:#1a73e8,color:#101828
    classDef proc fill:#e6f4f1,stroke:#0f9d8a,color:#101828
    classDef out fill:#fff7ed,stroke:#e8710a,color:#101828
    classDef stop fill:#fef3f2,stroke:#d92d20,color:#101828
    classDef plain fill:#ffffff,stroke:#d0d5dd,color:#101828
```

## 使い方

```python
config = build_config(confdir=__file__, project="X", author="me", package_paths=["../src"], use_hou_stub=True)
globals().update(config)
```

## 見るポイント

- スタブの場所は `sys.path` の **末尾** に足す。Houdini の中で `sphinx-build` を動かすと、本物の `hou` が使われる。
- `hou.Node` のような属性は、継承できるクラスとして返る。`hou.node("/obj")` のような呼び出しも通るが、
  何も実装していないので、返る値に意味は無い。
- スタブを継承したクラスの基底クラスは、文書の上でリンクにならない。nitpicky の警告からは自動で外れる。

## 使うときの注意

- テストで値を返す挙動が必要なら、テスト側で必要な関数だけを差し替える。スタブを育てて本物に近づけない。
- DCCPanelKit の `StandaloneHost` と共有する構想は、そのリポジトリが無いため、ここでは実装していない。
  スタブは単独のファイル (`docspipeline/stubs/hou.py`) なので、必要になったら `PYTHONPATH` で共有できる。
