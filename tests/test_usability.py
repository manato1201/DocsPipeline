"""使いやすさ (UX2 進捗・中断・完了 / UX4 エラーの書き方 / UX6 次の一手) の検査。

エラーは、**何が起きた / なぜ / 次にどうする** の 3 行で出る。
長い処理は、進み具合と、終わりと、Ctrl-C での中断が分かる。
"""

import re

import pytest

from docspipeline import cli, confluence, doctor, messages

FULL = {
    "CONFLUENCE_SERVER_URL": "https://example.atlassian.net/wiki/",
    "CONFLUENCE_SPACE_KEY": "DOCS",
    "CONFLUENCE_PARENT_PAGE": "Auto Docs",
    "CONFLUENCE_SERVER_USER": "me@example.com",
    "CONFLUENCE_API_TOKEN": "tok-0123456789abcdef",
}


def run(*argv):
    return cli.main(list(argv))


# ---- メッセージの部品 ----


def test_format_error_has_three_lines_what_why_next():
    text = messages.format_error("パスがありません: x", "打ち間違い", "パスを確かめる")
    assert text.splitlines() == ["エラー: パスがありません: x", "  原因: 打ち間違い", "  次の一手: パスを確かめる"]
    assert messages.format_error("a", "b", "c", label="中止").startswith("中止: a")


@pytest.mark.parametrize("empty", ["", "   ", "\n"])
@pytest.mark.parametrize("slot", ["what", "why", "next_step"])
def test_format_error_refuses_an_empty_part(slot, empty):
    parts = {"what": "a", "why": "b", "next_step": "c", slot: empty}
    with pytest.raises(ValueError, match=slot):
        messages.format_error(**parts)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0.0 秒"), (12.34, "12.3 秒"), (59.96, "1 分 0 秒"), (65, "1 分 5 秒"), (3725, "62 分 5 秒"), (-3, "0.0 秒")],
)
def test_format_elapsed(seconds, expected):
    assert messages.format_elapsed(seconds) == expected


# ---- どのエラーも 3 行 ----


def _no_confluence_env(monkeypatch):
    for name in confluence.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)


def _case_coverage_missing(tmp_path, monkeypatch):
    return ("coverage", str(tmp_path / "nope"), "--fail-under", "80"), 2


def _case_coverage_syntax_error(tmp_path, monkeypatch):
    (tmp_path / "bad.py").write_text("def (:\n", encoding="utf-8")
    return ("coverage", str(tmp_path)), 2


def _case_coverage_under_threshold(tmp_path, monkeypatch):
    (tmp_path / "m.py").write_text("def f():\n    pass\n", encoding="utf-8")
    return ("coverage", str(tmp_path), "--fail-under", "100"), 1


def _case_check_diagrams_missing_dir(tmp_path, monkeypatch):
    return ("check-diagrams", str(tmp_path / "nope")), 2


def _case_check_mermaid_missing(tmp_path, monkeypatch):
    return ("check-mermaid", str(tmp_path / "nope")), 2


def _case_map_not_a_package(tmp_path, monkeypatch):
    return ("map", str(tmp_path)), 2


def _case_init_missing_source(tmp_path, monkeypatch):
    return ("init", str(tmp_path), "--project", "P", "--author", "A", "--package", "../nope"), 2


def _case_init_refuses_to_overwrite(tmp_path, monkeypatch):
    args = ("init", str(tmp_path), "--project", "P", "--author", "A")
    assert run(*args) == 0
    return args, 1


def _case_publish_without_env(tmp_path, monkeypatch):
    _no_confluence_env(monkeypatch)
    return ("publish", str(tmp_path), "--mode", "dryrun"), 2


def _case_confluence_check_without_env(tmp_path, monkeypatch):
    _no_confluence_env(monkeypatch)
    return ("confluence-check", str(tmp_path)), 2


def _case_build_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: 1)
    return ("build", str(tmp_path)), 1


def _case_linkcheck_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: 1)
    return ("linkcheck", str(tmp_path)), 1


def _case_connection_test_fails_in_publish(tmp_path, monkeypatch):
    for name, value in FULL.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: 1)
    return ("publish", str(tmp_path), "--mode", "publish"), 1


def _case_connection_test_fails_alone(tmp_path, monkeypatch):
    for name, value in FULL.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: 1)
    return ("confluence-check", str(tmp_path)), 1


CASES = [
    _case_coverage_missing,
    _case_coverage_syntax_error,
    _case_coverage_under_threshold,
    _case_check_diagrams_missing_dir,
    _case_check_mermaid_missing,
    _case_map_not_a_package,
    _case_init_missing_source,
    _case_init_refuses_to_overwrite,
    _case_publish_without_env,
    _case_confluence_check_without_env,
    _case_build_fails,
    _case_linkcheck_fails,
    _case_connection_test_fails_in_publish,
    _case_connection_test_fails_alone,
]


@pytest.mark.parametrize("case", CASES, ids=lambda f: f.__name__.removeprefix("_case_"))
def test_every_error_says_what_why_and_the_next_step(case, tmp_path, monkeypatch, capsys):
    argv, expected_code = case(tmp_path, monkeypatch)
    capsys.readouterr()
    assert run(*argv) == expected_code
    err = capsys.readouterr().err
    block = re.search(r"^(エラー|失敗|中止|設定エラー): .+\n {2}原因: .+\n {2}次の一手: .+", err, re.MULTILINE)
    assert block, f"3 行の形になっていない:\n{err}"
    assert "Traceback" not in err
    assert FULL["CONFLUENCE_API_TOKEN"] not in err


def test_a_settings_error_raised_anywhere_is_reported_in_three_lines(tmp_path, monkeypatch, capsys):
    def bad_mode(_roots):
        raise confluence.ConfluenceSettingsError(
            "DOCSPIPELINE_CONFLUENCE_MODE は local, dryrun, publish のいずれかに (指定値: 'publsh')"
        )

    monkeypatch.setattr(cli.docstring_coverage, "scan", bad_mode)
    assert run("coverage", str(tmp_path)) == 2
    err = capsys.readouterr().err
    assert err.startswith("設定エラー: ") and "  原因: " in err and "  次の一手: docspipeline doctor" in err
    assert "publsh" in err  # 何を打ち間違えたかが分かる


def test_the_error_names_stay_visible_for_the_existing_messages(tmp_path, monkeypatch, capsys):
    # 既存の利用者・スクリプトが探す語句は、1 行目に残す
    run("coverage", str(tmp_path / "nope"))
    assert "エラー: パスがありません" in capsys.readouterr().err
    _no_confluence_env(monkeypatch)
    run("publish", str(tmp_path), "--mode", "publish")
    err = capsys.readouterr().err
    assert "次の環境変数が未設定です: CONFLUENCE_SERVER_URL" in err and "CONFLUENCE_API_TOKEN" in err


# ---- 進捗・完了・中断 (UX2) ----


def test_a_successful_build_reports_completion_time_and_where_to_look(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: 0)
    assert run("build", str(tmp_path)) == 0
    err = capsys.readouterr().err
    assert "html ビルドを始めます" in err
    assert re.search(r"完了: html \(\d+\.\d 秒\)", err)
    assert "次の一手: " in err and "index.html" in err


def test_other_builders_do_not_point_at_an_html_page(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: 0)
    assert run("build", str(tmp_path), "-b", "confluence") == 0
    err = capsys.readouterr().err
    assert "完了: confluence" in err and "index.html" not in err


def test_publish_shows_which_step_it_is_on(tmp_path, monkeypatch, capsys):
    for name, value in FULL.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: 0)
    assert run("publish", str(tmp_path), "--mode", "dryrun") == 0
    out = capsys.readouterr().out
    assert [m for m in re.findall(r"\[\d/\d\] \S+", out)] == [
        "[1/3] 環境変数の確認",
        "[2/3] 接続テスト",
        "[3/3] Confluence",
    ]
    assert run("publish", str(tmp_path), "--mode", "dryrun", "--skip-connection-test") == 0
    assert re.findall(r"\[\d/\d\]", capsys.readouterr().out) == ["[1/2]", "[2/2]"]
    assert run("publish", str(tmp_path)) == 0
    assert re.findall(r"\[\d/\d\]", capsys.readouterr().out) == ["[1/1]"]


class _InterruptedProcess:
    """出力を読んでいる途中で、利用者が Ctrl-C を押した子プロセス。"""

    def __init__(self, *args, **kwargs):
        self.terminated = False
        self.killed = False
        self.stdout = self._lines()

    def _lines(self):
        yield "building...\n"
        raise KeyboardInterrupt

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return -15


def test_ctrl_c_stops_the_child_and_says_what_to_do_next(monkeypatch, capsys):
    made = []

    def factory(*args, **kwargs):
        made.append(_InterruptedProcess())
        return made[-1]

    monkeypatch.setattr(cli.subprocess, "Popen", factory)
    assert cli._run(["sphinx"]) == cli.EXIT_INTERRUPTED == 130
    captured = capsys.readouterr()
    assert made[0].terminated and not made[0].killed
    assert "building..." in captured.out  # それまでの出力は残る
    assert captured.err.startswith("中断: ") and "  次の一手: " in captured.err


def test_an_interrupted_build_is_not_reported_as_a_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.subprocess, "Popen", lambda *a, **k: _InterruptedProcess())
    assert run("build", str(tmp_path)) == 130
    err = capsys.readouterr().err
    assert "中断: " in err and "失敗: " not in err and "完了:" not in err


def test_ctrl_c_in_a_command_that_runs_no_child_is_also_handled(tmp_path, monkeypatch, capsys):
    def interrupted(_roots):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.docstring_coverage, "scan", interrupted)
    assert run("coverage", str(tmp_path)) == 130
    assert "中断: " in capsys.readouterr().err


# ---- 次の一手 (UX6): doctor ----


def test_doctor_tells_the_next_step_only_for_items_that_are_not_ok():
    checks = [
        doctor.Check("A", True, "ok", hint="使われない"),
        doctor.Check("B", False, "無い", hint="B を入れる"),
        doctor.Check("C", False, "無い"),
    ]
    lines = doctor.format_checks(checks).splitlines()
    assert lines == ["[OK  ] A: ok", "[なし] B: 無い", "       次の一手: B を入れる", "[なし] C: 無い"]


def test_doctor_hints_are_present_for_the_failures_it_can_report(monkeypatch):
    monkeypatch.setenv(confluence.MODE_ENV, "publsh")
    monkeypatch.setenv(doctor.MMDC_ENV, "/no/such/mmdc")
    for name in confluence.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    failed = [c for c in doctor.run_checks() if not c.ok]
    assert {c.name for c in failed} >= {"mmdc (Mermaid → SVG)", "Confluence のモード", "Confluence の環境変数"}
    assert all(c.hint for c in failed)


def test_doctor_hints_never_contain_secret_values(monkeypatch, capsys):
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "tok-0123456789abcdef")
    run("doctor")
    assert "tok-0123456789abcdef" not in capsys.readouterr().out
