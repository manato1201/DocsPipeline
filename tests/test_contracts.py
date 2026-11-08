"""docs/contracts.md の契約と、副作用の境界の検査。

* 表の関数と、検証するテストが、実在する
* 「純粋」の関数は、ファイル・環境変数・子プロセス・ネットワークに触れず、同じ入力なら同じ出力になる
* 「読み取り」の関数は、何も書かず、子プロセスも起動しない
* 契約 (事後条件・不変条件) を、いろいろな入力で確かめる
"""

import ast
import builtins
import contextlib
import hashlib
import importlib
import io
import os
import random
import re
import shutil
import socket
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from docspipeline import (
    confluence,
    docstring_coverage,
    doctor,
    files,
    messages,
    mmdc,
    prompt,
    scaffold,
    structure_map,
)

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "docs" / "contracts.md"
LAYERS = ("純粋", "読み取り", "書き込み・起動")


def _rows() -> dict[str, tuple[str, list[str]]]:
    """契約の表から、``{関数名: (層, [テストの ID])}`` を作る。"""
    rows = {}
    in_table = False
    for line in CONTRACTS.read_text(encoding="utf-8").splitlines():
        if line.startswith("| 関数 | 層 |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("| `"):
            if line.startswith("|---"):
                continue
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == 6, line
        name = cells[0].strip("`")
        assert name not in rows, f"{name} が重複している"
        rows[name] = (cells[1], re.findall(r"tests/\w+\.py::\w+", cells[5]))
    return rows


ROWS = _rows()


def _resolve(name: str):
    module_name, *rest = name.split(".")
    obj = importlib.import_module(f"docspipeline.{module_name}")
    for part in rest:
        obj = getattr(obj, part)
    return obj


# ---- 表そのものの検査 ----


def test_the_table_has_every_layer():
    assert {layer for layer, _tests in ROWS.values()} == set(LAYERS)


@pytest.mark.parametrize("name", sorted(ROWS))
def test_every_function_in_the_table_exists(name):
    assert callable(_resolve(name))


@pytest.mark.parametrize("name", sorted(ROWS))
def test_every_row_names_tests_that_exist(name):
    _layer, ids = ROWS[name]
    assert ids, f"{name}: 検証するテストが無い"
    for test_id in ids:
        path, test_name = test_id.split("::")
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assert test_name in defined, f"{name}: {test_id} が無い"


# ---- 層の約束を守らせる道具 ----


def _deny(what: str):
    def raiser(*_args, **_kwargs):
        raise AssertionError(f"層の約束を破った: {what} に触れた")

    return raiser


class _DeniedEnviron:
    """``os.environ`` の代わり。触れたら、その時点で失敗する。"""

    def __getattr__(self, name):
        raise AssertionError(f"層の約束を破った: os.environ.{name} に触れた")

    def __getitem__(self, key):
        raise AssertionError("層の約束を破った: os.environ に触れた")

    def __contains__(self, key):
        raise AssertionError("層の約束を破った: os.environ に触れた")

    def __iter__(self):
        raise AssertionError("層の約束を破った: os.environ に触れた")


@contextlib.contextmanager
def no_io():
    """純粋な関数を呼ぶ間、ファイル・環境変数・子プロセス・ネットワークを禁じる。"""
    with contextlib.ExitStack() as stack:
        for target, what in (
            (builtins, "open"),
            (io, "open"),
            (subprocess, "Popen"),
            (subprocess, "run"),
            (shutil, "which"),
            (socket, "socket"),
            (os, "listdir"),
            (os, "scandir"),
            (Path, "read_text"),
            (Path, "write_text"),
            (Path, "exists"),
            (Path, "iterdir"),
            (Path, "mkdir"),
        ):
            stack.enter_context(mock.patch.object(target, what, _deny(f"{getattr(target, '__name__', target)}.{what}")))
        stack.enter_context(mock.patch.object(os, "environ", _DeniedEnviron()))
        yield


@contextlib.contextmanager
def no_writes_or_processes():
    """読み取りの関数を呼ぶ間、子プロセスとネットワークを禁じる (書き込みは、前後の比較で見る)。"""
    with contextlib.ExitStack() as stack:
        for target, what in ((subprocess, "Popen"), (subprocess, "run"), (socket, "socket")):
            stack.enter_context(mock.patch.object(target, what, _deny(f"{target.__name__}.{what}")))
        yield


def _snapshot(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ---- 純粋な層 ----

FULL = {
    "CONFLUENCE_SERVER_URL": "https://example.atlassian.net/wiki/",
    "CONFLUENCE_SPACE_KEY": "DOCS",
    "CONFLUENCE_PARENT_PAGE": "Auto Docs",
    "CONFLUENCE_SERVER_USER": "me@example.com",
    "CONFLUENCE_API_TOKEN": "tok-0123456789abcdef",
}


def _module(name: str, imports=()):
    return structure_map.Module(
        name=name,
        path=Path(name.replace(".", "/") + ".py"),
        is_package=name == "p",
        summary="",
        lines=1,
        public_api=0,
        imports=frozenset(imports),
        references=frozenset(),
        external=frozenset(),
    )


def _graph(edges: dict[str, set[str]] | None = None) -> structure_map.Graph:
    edges = edges or {"p.a": {"p.b"}, "p.b": {"p.a"}, "p.c": {"p.a"}}
    names = ["p", *sorted(set(edges) | {d for ds in edges.values() for d in ds})]
    return structure_map.Graph("p", tuple(_module(n, edges.get(n, ())) for n in names))


PURE_CALLS = {
    "confluence.current_mode": lambda: confluence.current_mode({confluence.MODE_ENV: " DryRun "}),
    "confluence.missing_env": lambda: confluence.missing_env({}),
    "confluence.sphinx_settings": lambda: confluence.sphinx_settings({}),
    "confluence.mask_secrets": lambda: confluence.mask_secrets(
        "t=tok-0123456789", {"CONFLUENCE_API_TOKEN": "tok-0123456789"}
    ),
    "mmdc.split_command": lambda: mmdc.split_command("a 'b c'", windows=False),
    "mmdc.check_mermaid_text": lambda: mmdc.check_mermaid_text("```mermaid\nflowchart LR\n```\n"),
    "mmdc.fix_mermaid_text": lambda: mmdc.fix_mermaid_text("```mermaid\nflowchart LR\n```\n"),
    "structure_map.Graph.cycles": lambda: _graph().cycles(),
    "structure_map.to_mermaid": lambda: structure_map.to_mermaid(_graph()),
    "structure_map.Graph.labeled_edges": lambda: _graph().labeled_edges(),
    "structure_map.to_markdown": lambda: structure_map.to_markdown(_graph()),
    "docstring_coverage.format_report": lambda: docstring_coverage.format_report(
        docstring_coverage.Report((docstring_coverage.Item(Path("a.py"), "f", "function", 3, False),))
    ),
    "doctor.exit_code": lambda: doctor.exit_code([doctor.Check("x", False, "d", required=True)]),
    "prompt.find_secret": lambda: prompt.find_secret("API_TOKEN=abcdef123456"),
    "messages.format_error": lambda: messages.format_error("何か", "理由", "対処"),
    "messages.format_elapsed": lambda: messages.format_elapsed(65),
    "doctor.format_checks": lambda: doctor.format_checks([doctor.Check("x", False, "d", hint="h")]),
}


def test_the_pure_layer_in_the_table_is_exactly_what_is_exercised():
    assert {n for n, (layer, _t) in ROWS.items() if layer == "純粋"} == set(PURE_CALLS)


@pytest.mark.parametrize("name", sorted(PURE_CALLS))
def test_pure_functions_touch_nothing_and_are_deterministic(name):
    call = PURE_CALLS[name]
    with no_io():
        first, second = call(), call()
    assert first == second


def test_the_sandbox_really_catches_a_function_that_touches_the_outside():
    # 道具そのものの確認: 環境変数・ファイルに触れる関数は、ここで失敗する
    with no_io(), pytest.raises(AssertionError, match=r"os\.environ"):
        confluence.current_mode()  # environ を省略 → os.environ を読む
    with no_io(), pytest.raises(AssertionError, match="open"):
        open("x")  # noqa: SIM115 (開く前に失敗する)


@pytest.mark.parametrize("raw", ["", "LOCAL", " dryrun ", "Publish", "\tpublish\n"])
def test_current_mode_contract(raw):
    mode = confluence.current_mode({confluence.MODE_ENV: raw})
    assert mode in confluence.MODES
    assert mode == (raw.strip().lower() or "local")


@pytest.mark.parametrize("raw", ["publsh", "1", "true", "local1", "off"])
def test_current_mode_never_turns_an_unknown_value_into_local(raw):
    with pytest.raises(confluence.ConfluenceSettingsError):
        confluence.current_mode({confluence.MODE_ENV: raw})


def test_missing_env_contract():
    rng = random.Random(7)
    for _ in range(40):
        present = {n for n in confluence.REQUIRED_ENV if rng.random() < 0.5}
        env = {n: f"VALUE-{n}" for n in present}
        env.update({n: "" for n in confluence.REQUIRED_ENV if n not in present and rng.random() < 0.5})  # 空も、未設定
        missing = confluence.missing_env(env)
        assert missing == [n for n in confluence.REQUIRED_ENV if n not in present]  # 定義の順・名前だけ
        assert not any("VALUE-" in m for m in missing)


def test_sphinx_settings_contract():
    for mode in confluence.MODES:
        env = {**FULL, confluence.MODE_ENV: mode, "CONFLUENCE_PUBLISH": "1"}
        before = dict(env)
        settings = confluence.sphinx_settings(env)
        assert env == before  # 引数を書き換えない
        assert settings == confluence.sphinx_settings(env)  # 決定的
        # どのモードでも: 手で作られたページを、消さない・奪わない・反応のあるページを上書きしない
        assert settings["confluence_cleanup_purge"] is False
        assert settings["confluence_cleanup_archive"] is False
        assert settings["confluence_publish_trample"] is False
        assert settings["confluence_publish_skip_commented_pages"] == "ignored-resolved"
        if mode == "local":
            assert settings["confluence_publish"] is False
            assert not [k for k in settings if re.search(r"server|api_token|space|parent", k)]
        else:
            assert settings["confluence_publish"] is True
            assert settings["confluence_publish_dryrun"] is (mode == "dryrun")
            assert settings["confluence_parent_page"] == FULL["CONFLUENCE_PARENT_PAGE"]


@pytest.mark.parametrize("mode", ["dryrun", "publish"])
@pytest.mark.parametrize("name", confluence.REQUIRED_ENV)
def test_sphinx_settings_stops_when_a_required_value_is_missing(mode, name):
    env = {**FULL, confluence.MODE_ENV: mode}
    del env[name]
    with pytest.raises(confluence.ConfluenceSettingsError) as caught:
        confluence.sphinx_settings(env)
    assert name in str(caught.value)  # 名前は出る
    assert FULL["CONFLUENCE_API_TOKEN"] not in str(caught.value)  # 値は出ない


def test_mask_secrets_contract():
    for token in ("abcdefgh", "tok-0123456789abcdef", "x" * 40):
        env = {"CONFLUENCE_API_TOKEN": token}
        for text in (f"a {token} b {token}", f"Authorization: {token}", token, "無関係な文字列"):
            masked = confluence.mask_secrets(text, env)
            assert token not in masked
            assert confluence.mask_secrets(masked, env) == masked  # 冪等
            if token not in text:
                assert masked == text
    # 8 文字未満は、通常の文字列まで潰すので、対象外 (契約の例外)
    assert confluence.mask_secrets("abc abc", {"CONFLUENCE_API_TOKEN": "abc"}) == "abc abc"
    assert confluence.mask_secrets("abc", {}) == "abc"


def _random_markdown(rng: random.Random) -> str:
    lines: list[str] = []
    for _ in range(rng.randint(0, 5)):
        lines += [rng.choice(["説明", "", "- 項目", "```python", "x = 1", "```"]) for _ in range(rng.randint(0, 3))]
        if rng.random() < 0.8:
            opening = rng.choice(["```mermaid", "````mermaid", "~~~mermaid", "```{mermaid}", "  ```mermaid"])
            fence = re.sub(r"\s|mermaid|\{|\}", "", opening)
            indent = re.match(r" *", opening).group(0)
            body = ["flowchart LR", "    A --> B"]
            if rng.random() < 0.4:
                body.insert(0, indent + mmdc.MERMAID_INIT)
            elif rng.random() < 0.3:
                body.insert(0, indent + '%%{init: {"theme":"dark"}}%%')
            lines += [opening, *body]
            if rng.random() < 0.9:  # たまに、閉じない
                lines.append(indent + fence)
    return "\n".join(lines) + "\n"


def test_fix_mermaid_text_contract():
    rng = random.Random(11)
    for _ in range(120):
        doc = _random_markdown(rng)
        fixed = mmdc.fix_mermaid_text(doc)
        assert mmdc.check_mermaid_text(fixed) == []  # 直したあとは、足りない所が無い
        assert mmdc.fix_mermaid_text(fixed) == fixed  # 冪等

        def without_init(text: str) -> list[str]:
            return [ln for ln in text.split("\n") if not ln.strip().startswith("%%{init")]

        assert without_init(fixed) == without_init(doc)  # init の行以外は、1 行も変わらない


def _brute_force_cycles(edges: set[tuple[str, str]], names: list[str]) -> list[list[str]]:
    reach = {n: {d for s, d in edges if s == n} for n in names}
    changed = True
    while changed:  # 推移閉包 (小さなグラフ専用)
        changed = False
        for n in names:
            more = set().union(*(reach[m] for m in reach[n])) - reach[n] if reach[n] else set()
            if more:
                reach[n] |= more
                changed = True
    components = {
        frozenset({n} | {m for m in reach[n] if n in reach[m]})
        for n in names
        if n in reach[n] or any(n in reach[m] and m in reach[n] for m in names if m != n)
    }
    return sorted(sorted(c) for c in components if len(c) > 1)


def test_graph_contract():
    rng = random.Random(3)
    for _ in range(80):
        names = [f"p.m{i}" for i in range(rng.randint(2, 7))]
        edges = {n: {d for d in names if rng.random() < 0.25} for n in names}
        graph = _graph(edges)
        cycles = graph.cycles()
        assert cycles == _brute_force_cycles(graph.edges(include_root=True), [m.name for m in graph.modules])
        assert all(len(c) >= 2 and c == sorted(c) for c in cycles)  # 2 つ以上・整列済み
        assert cycles == sorted(cycles)
        shuffled = structure_map.Graph("p", tuple(rng.sample(graph.modules, len(graph.modules))))
        assert shuffled.cycles() == cycles  # モジュールの並びに依存しない
        assert structure_map.to_mermaid(graph) == structure_map.to_mermaid(graph)  # 決定的


def _random_graph(rng: random.Random) -> structure_map.Graph:
    """import・遅延 import・文字列の参照を、ばらばらに持つ地図 (パッケージ自身への依存も混ぜる)。"""
    names = [f"p.m{i}" for i in range(rng.randint(2, 6))]
    modules = [structure_map.Module("p", Path("p/__init__.py"), True, "", 1, 0, frozenset(), frozenset(), frozenset())]

    def pick(owner: str) -> frozenset[str]:
        return frozenset(d for d in [*names, "p"] if d != owner and rng.random() < 0.25)

    for name in names:
        runtime, lazy, refs = pick(name), pick(name), pick(name)
        modules.append(
            structure_map.Module(
                name=name,
                path=Path(name.replace(".", "/") + ".py"),
                is_package=False,
                summary=rng.choice(["", "説明", "a | b"]),
                lines=rng.randint(1, 50),
                public_api=rng.randint(0, 4),
                imports=runtime,
                references=refs - runtime,  # scan_package と同じ: 実行時の import がある組は、参照に数えない
                external=frozenset(),
                deferred=lazy - runtime,
            )
        )
    return structure_map.Graph("p", tuple(modules))


def test_labeled_edges_contract():
    rng = random.Random(11)
    expected = {"import": "EXTRACTED", "deferred": "EXTRACTED", "reference": "INFERRED"}
    for _ in range(80):
        graph = _random_graph(rng)
        rows = graph.labeled_edges()
        assert rows == sorted(rows)  # 整列済み
        assert len(rows) == len(set(rows))  # 重複なし
        for _src, _dst, kind, label in rows:
            assert label == expected[kind]  # 種類から札が決まる。推測を、読んだことにしない
        for kind, label in expected.items():
            assert {(s, d) for s, d, k, _ in rows if k == kind} == graph.edges(kind)  # 欠けも余りも無い
            assert all(row[3] == label for row in rows if row[2] == kind)
        shuffled = structure_map.Graph("p", tuple(rng.sample(graph.modules, len(graph.modules))))
        assert shuffled.labeled_edges() == rows  # モジュールの並びに依存しない


def test_to_markdown_contract():
    rng = random.Random(5)
    for _ in range(60):
        graph = _random_graph(rng)
        text = structure_map.to_markdown(graph)
        assert text == structure_map.to_markdown(graph)  # 決定的
        assert "```{warning}" in text and "## 札の見方" in text  # 冒頭の警告と札の見方は、必ず入る
        table = text.split("## 依存の一覧 (札つき)")[1].split("\n\n")[1].splitlines()[2:]  # 見出し行と区切りを除く
        short = lambda n: n[len("p.") :] if n != "p" else n  # noqa: E731
        shown = [tuple(c.strip().split(" (")[0].strip("`") for c in row.strip("|").split("|")) for row in table]
        assert sorted(shown) == sorted((short(s), short(d), k, lab) for s, d, k, lab in graph.labeled_edges())
        # 推測だけで結ばれた依存は、モジュール一覧でも「(推測)」と分かる。読んだ依存には付かない
        guessed = graph.edges("reference") - graph.edges()
        for module in graph.modules:
            row = next(line for line in text.splitlines() if line.startswith(f"| `{short(module.name)}` | "))
            _, uses, _used_by = row.rstrip(" |").rsplit(" | ", 2)  # 「使う」の列だけを見る
            for src, dst in graph.edges() | graph.edges("reference"):
                if src == module.name:
                    assert (f"`{short(dst)}` (推測)" in uses) == ((src, dst) in guessed), (row, src, dst)


def test_format_error_contract():
    rng = random.Random(2)
    words = ["パス", "x.py:3", "--force", "docs/", "a b", "→", "'q'"]
    for _ in range(100):
        what, why, nxt = (" ".join(rng.choices(words, k=rng.randint(1, 4))) for _ in range(3))
        label = rng.choice(["エラー", "失敗", "中止"])
        text = messages.format_error(what, why, nxt, label=label)
        assert text.split("\n") == [f"{label}: {what}", f"  原因: {why}", f"  次の一手: {nxt}"]  # 常に 3 行
        assert text == messages.format_error(what, why, nxt, label=label)  # 決定的


def test_fix_mermaid_text_does_not_hang_on_an_unclosed_block():
    assert mmdc.check_mermaid_text(mmdc.fix_mermaid_text("```mermaid\nflowchart LR\n")) == []


# ---- 読み取りの層 ----


def _tree(root: Path) -> None:
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text('"""pkg."""\n', encoding="utf-8")
    (root / "pkg" / "a.py").write_text('"""a."""\nfrom . import b\n\n\ndef f():\n    """f."""\n', encoding="utf-8")
    (root / "pkg" / "b.py").write_text('"""b."""\n', encoding="utf-8")
    (root / ".venv").mkdir()
    (root / ".venv" / "x.py").write_text("x = 1\n", encoding="utf-8")


READ_CALLS = {
    "structure_map.scan_package": lambda root: structure_map.scan_package(root / "pkg"),
    "docstring_coverage.scan": lambda root: docstring_coverage.scan([root / "pkg"]),
    "scaffold.plan": lambda root: scaffold.plan(
        scaffold.Options(target=root / "out", project="P", author="A", package=("../pkg",))
    ),
    "files.iter_python_files": lambda root: list(files.iter_python_files([root])),
}


def test_the_read_layer_in_the_table_is_exactly_what_is_exercised():
    assert {n for n, (layer, _t) in ROWS.items() if layer == "読み取り"} == set(READ_CALLS)


@pytest.mark.parametrize("name", sorted(READ_CALLS))
def test_read_only_functions_change_nothing(name, tmp_path):
    _tree(tmp_path)
    before = _snapshot(tmp_path)
    with no_writes_or_processes():
        first = READ_CALLS[name](tmp_path)
        second = READ_CALLS[name](tmp_path)
    assert _snapshot(tmp_path) == before  # 中身が変わらない
    assert not (tmp_path / "out").exists()  # 新しく作らない
    assert first == second  # 同じ入力なら、同じ結果


def test_files_iter_python_files_is_sorted_and_skips_virtualenvs(tmp_path):
    _tree(tmp_path)
    found = [p.relative_to(tmp_path).as_posix() for p in files.iter_python_files([tmp_path])]
    assert found == sorted(found)
    assert not [p for p in found if p.startswith(".venv")]
